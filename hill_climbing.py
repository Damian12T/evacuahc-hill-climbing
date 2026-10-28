"""Hill Climbing para buscar una ruta de evacuación en el grafo del campus.

Estado: el nodo donde se encuentra la persona.
Valor del estado: h(n), estimación en metros de la distancia que falta hasta el
destino (menor es mejor; "subir la colina" equivale a reducir h).

En cada iteración:
1. Se toman los vecinos alcanzables por una arista transitable.
2. Un vecino es ADMISIBLE si no fue visitado y mejora estrictamente el estado:
   h(v) < h(actual).
3. Entre los admisibles se ordena con la función de evaluación f(v):
   - criterio "heuristica":        f(v) = h(v)
   - criterio "costo_heuristica":  f(v) = d(actual, v) + h(v)
   donde d es la longitud medida del tramo (informe). Así se penaliza un tramo
   largo que solo parece acercarse al destino. Ambos términos están en metros.
4. Si no hay vecinos admisibles, la búsqueda termina. No hay retroceso ni memoria
   de movimientos prohibidos: puede quedarse en un óptimo local aunque exista un
   camino en el grafo.

Variantes (ambas son Hill Climbing; ninguna recurre a otro algoritmo):
- Máxima pendiente: elige siempre el admisible de menor f (determinista).
- Estocástica con reinicios: elige al azar entre los admisibles, con probabilidad
  proporcional a la mejora h(actual) - h(v); si queda bloqueada, vuelve a empezar
  desde el origen con otra secuencia aleatoria, hasta un máximo de reinicios
  (Russell y Norvig, "stochastic" y "random-restart hill climbing").
"""

import math
import random
from typing import Callable, List, Optional

import networkx as nx

from configuracion import (
    CRITERIO_COSTO_HEURISTICA, CRITERIO_HEURISTICA, HEURISTICA_EUCLIDIANA, HEURISTICA_SALIDA,
    REINICIOS_POR_DEFECTO, SEMILLA_POR_DEFECTO, VARIANTE_ESTOCASTICA, VARIANTE_MAXIMA_PENDIENTE,
)
from modelos import (
    ESTADO_EXITO, ESTADO_LIMITE_ITERACIONES, ESTADO_NODO_INEXISTENTE, ESTADO_OPTIMO_LOCAL,
    ESTADO_SIN_VECINOS, ESTADO_SOLO_VISITADOS, VECINO_ADMISIBLE, VECINO_NO_MEJORA,
    VECINO_VISITADO, Candidato, Paso, ResultadoBusqueda,
)

Heuristica = Callable[[nx.Graph, str, str], float]


def _recta(grafo: nx.Graph, a: str, b: str) -> float:
    pa, pb = grafo.nodes[a], grafo.nodes[b]
    return math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])


def distancia_euclidiana(grafo: nx.Graph, nodo: str, destino: str) -> float:
    """h(n): distancia en línea recta (m) hasta el destino. Ignora muros y edificios."""
    return _recta(grafo, nodo, destino)


def distancia_con_salida(grafo: nx.Graph, nodo: str, destino: str) -> float:
    """h(n) euclidiana que respeta la salida obligatoria documentada.

    G y H no tienen puerta propia: se sale por el hall central hasta la puerta S
    (informe, sección 3). Para un nodo con salida obligatoria, la línea recta hasta
    el destino atraviesa muros; la estimación pasa por la salida:
    h(n) = |n - S| + |S - destino|. Sigue siendo un límite inferior del recorrido.
    """
    salida = grafo.nodes[nodo].get("salida_obligatoria")
    if salida and salida != destino and nodo != destino:
        return _recta(grafo, nodo, salida) + _recta(grafo, salida, destino)
    return _recta(grafo, nodo, destino)


HEURISTICAS = {
    HEURISTICA_SALIDA: distancia_con_salida,
    HEURISTICA_EUCLIDIANA: distancia_euclidiana,
}


def vecinos_transitables(grafo: nx.Graph, nodo: str) -> List[str]:
    """Sucesores (grafo dirigido) o vecinos (no dirigido) unidos por una arista transitable."""
    vecinos = grafo.successors(nodo) if grafo.is_directed() else grafo.neighbors(nodo)
    return sorted(v for v in vecinos if grafo.edges[nodo, v].get("transitable", True))


def longitud_ruta(grafo: nx.Graph, ruta: List[str]) -> Optional[float]:
    """Suma de longitudes medidas; None si algún tramo no tiene longitud."""
    total = 0.0
    for u, v in zip(ruta, ruta[1:]):
        longitud = grafo.edges[u, v].get("longitud_m")
        if longitud is None:
            return None
        total += longitud
    return total


def _nombre_heuristica(heuristica: Heuristica) -> str:
    for clave, funcion in HEURISTICAS.items():
        if funcion is heuristica:
            return clave
    return getattr(heuristica, "__name__", "personalizada")


def hill_climbing(
    grafo: nx.Graph,
    origen: str,
    destino: str,
    heuristica: Heuristica = distancia_con_salida,
    criterio: str = CRITERIO_COSTO_HEURISTICA,
    max_iteraciones: Optional[int] = None,
    aleatorio: Optional[random.Random] = None,
) -> ResultadoBusqueda:
    """Un recorrido de Hill Climbing desde el origen.

    Con aleatorio=None se usa máxima pendiente; con un random.Random, la elección
    entre vecinos admisibles es estocástica (ponderada por la mejora de h).
    """
    if criterio not in (CRITERIO_COSTO_HEURISTICA, CRITERIO_HEURISTICA):
        raise ValueError(f"Criterio desconocido: {criterio}")
    variante = VARIANTE_MAXIMA_PENDIENTE if aleatorio is None else VARIANTE_ESTOCASTICA

    def terminar(exito, estado, motivo, ruta=(), visitados=(), pasos=()):
        ruta = list(ruta)
        return ResultadoBusqueda(
            origen=origen, destino=destino, criterio=criterio, exito=exito, estado=estado,
            motivo=motivo, ruta=ruta, visitados=list(visitados), pasos=list(pasos),
            distancia_total_m=longitud_ruta(grafo, ruta) if exito else None,
            heuristica=_nombre_heuristica(heuristica), variante=variante,
        )

    faltantes = [n for n in (origen, destino) if n not in grafo]
    if faltantes:
        return terminar(False, ESTADO_NODO_INEXISTENTE,
                        f"No existe en el grafo: {', '.join(map(str, faltantes))}.")

    limite = max_iteraciones if max_iteraciones is not None else grafo.number_of_nodes()
    actual = origen
    ruta = [origen]
    visitados = {origen}
    pasos: List[Paso] = []

    while actual != destino:
        if len(pasos) >= limite:
            return terminar(False, ESTADO_LIMITE_ITERACIONES,
                            f"Se alcanzó el límite de {limite} iteraciones sin llegar a {destino}.",
                            ruta, ruta, pasos)

        h_actual = heuristica(grafo, actual, destino)
        candidatos = []
        for vecino in vecinos_transitables(grafo, actual):
            longitud = grafo.edges[actual, vecino].get("longitud_m")
            h_vecino = heuristica(grafo, vecino, destino)
            if criterio == CRITERIO_COSTO_HEURISTICA:
                valor = (longitud or 0.0) + h_vecino
            else:
                valor = h_vecino
            if vecino in visitados:
                estado = VECINO_VISITADO
            elif h_vecino < h_actual:
                estado = VECINO_ADMISIBLE
            else:
                estado = VECINO_NO_MEJORA
            candidatos.append(Candidato(vecino, longitud, h_vecino, valor, estado))

        admisibles = [c for c in candidatos if c.estado == VECINO_ADMISIBLE]
        iteracion = len(pasos) + 1

        if not candidatos:
            motivo = f"{actual} no tiene vecinos transitables (callejón sin salida)."
            pasos.append(Paso(iteracion, actual, h_actual, candidatos, None, motivo))
            return terminar(False, ESTADO_SIN_VECINOS, motivo, ruta, ruta, pasos)

        if not admisibles and all(c.estado == VECINO_VISITADO for c in candidatos):
            motivo = f"Todos los vecinos de {actual} ya fueron visitados (se evita un ciclo)."
            pasos.append(Paso(iteracion, actual, h_actual, candidatos, None, motivo))
            return terminar(False, ESTADO_SOLO_VISITADOS, motivo, ruta, ruta, pasos)

        if not admisibles:
            motivo = (f"Óptimo local en {actual}: h({actual}) = {h_actual:.1f} m y ningún vecino "
                      f"tiene una h menor. Hill Climbing no retrocede.")
            pasos.append(Paso(iteracion, actual, h_actual, candidatos, None, motivo))
            return terminar(False, ESTADO_OPTIMO_LOCAL, motivo, ruta, ruta, pasos)

        if aleatorio is None:
            # Desempate determinista: menor f, luego menor h, luego identificador.
            elegido = min(admisibles, key=lambda c: (c.valor, c.h, c.nodo))
            if len(admisibles) == 1:
                motivo = f"{elegido.nodo} es el único vecino que mejora h ({h_actual:.1f} -> {elegido.h:.1f} m)."
            else:
                motivo = (f"{elegido.nodo} tiene la menor f = {elegido.valor:.1f} entre "
                          f"{len(admisibles)} vecinos que mejoran h.")
        else:
            pesos = [h_actual - c.h for c in admisibles]
            elegido = aleatorio.choices(admisibles, weights=pesos, k=1)[0]
            total = sum(pesos)
            reparto = ", ".join(f"{c.nodo} {p / total:.0%}" for c, p in zip(admisibles, pesos))
            motivo = f"{elegido.nodo} elegido al azar entre los que mejoran h (probabilidades: {reparto})."
        pasos.append(Paso(iteracion, actual, h_actual, candidatos, elegido.nodo, motivo))

        actual = elegido.nodo
        ruta.append(actual)
        visitados.add(actual)

    return terminar(True, ESTADO_EXITO, f"Se alcanzó {destino} en {len(pasos)} iteraciones.",
                    ruta, ruta, pasos)


def hill_climbing_con_reinicios(
    grafo: nx.Graph,
    origen: str,
    destino: str,
    heuristica: Heuristica = distancia_con_salida,
    criterio: str = CRITERIO_COSTO_HEURISTICA,
    max_reinicios: int = REINICIOS_POR_DEFECTO,
    semilla: int = SEMILLA_POR_DEFECTO,
) -> ResultadoBusqueda:
    """Hill Climbing estocástico; reinicia desde el origen mientras quede bloqueado.

    Devuelve el primer intento que llega al destino o, si ninguno lo logra, el último.
    El campo `intentos` resume cada intento para poder mostrarlo.
    """
    if max_reinicios < 0:
        raise ValueError("El número de reinicios no puede ser negativo.")
    aleatorio = random.Random(semilla)
    resumen = []
    resultado = None
    for intento in range(1, max_reinicios + 2):
        resultado = hill_climbing(grafo, origen, destino, heuristica, criterio, aleatorio=aleatorio)
        resumen.append(f"Intento {intento}: {' -> '.join(resultado.ruta) or '-'} · {resultado.descripcion_estado}")
        if resultado.exito or resultado.estado == ESTADO_NODO_INEXISTENTE:
            break
    resultado.intentos = resumen
    if len(resumen) > 1:
        resultado.motivo += f" (intento {len(resumen)} de hasta {max_reinicios + 1}; semilla {semilla})"
    return resultado


def buscar(grafo: nx.Graph, origen: str, destino: str, heuristica: str = HEURISTICA_SALIDA,
           criterio: str = CRITERIO_COSTO_HEURISTICA, variante: str = VARIANTE_MAXIMA_PENDIENTE,
           max_reinicios: int = REINICIOS_POR_DEFECTO, semilla: int = SEMILLA_POR_DEFECTO) -> ResultadoBusqueda:
    """Punto de entrada usado por la interfaz: traduce las opciones a una llamada concreta."""
    funcion_h = HEURISTICAS[heuristica]
    if variante == VARIANTE_MAXIMA_PENDIENTE:
        resultado = hill_climbing(grafo, origen, destino, funcion_h, criterio)
        resultado.intentos = [f"Intento 1: {' -> '.join(resultado.ruta) or '-'} · {resultado.descripcion_estado}"]
        return resultado
    if variante == VARIANTE_ESTOCASTICA:
        return hill_climbing_con_reinicios(grafo, origen, destino, funcion_h, criterio, max_reinicios, semilla)
    raise ValueError(f"Variante desconocida: {variante}")


def evaluar_destinos(grafo: nx.Graph, origen: str, destinos: List[str], **opciones) -> List[ResultadoBusqueda]:
    """Ejecuta Hill Climbing por separado hacia cada destino. No decide cuál es el más seguro."""
    return [buscar(grafo, origen, destino, **opciones) for destino in destinos]
