"""Textos en lenguaje sencillo para personas que no conocen Hill Climbing.

Todo se genera a partir del resultado real de la búsqueda: no se inventan decisiones.
"""

from typing import List

import networkx as nx

from configuracion import CRITERIO_COSTO_HEURISTICA, VARIANTE_ESTOCASTICA, VELOCIDAD_MARCHA_MS
from modelos import (
    ESTADO_NODO_INEXISTENTE, ESTADO_OPTIMO_LOCAL, ESTADO_SIN_VECINOS, VECINO_ADMISIBLE, VECINO_VISITADO,
    ResultadoBusqueda,
)

QUE_ES_HILL_CLIMBING = (
    "Imagina que subes una colina con mucha niebla: solo ves los pasos que tienes alrededor. "
    "En cada momento das el paso que más te acerca a la cima, sin volver atrás.\n\n"
    "Así funciona Hill Climbing: desde donde estás, mira los caminos que salen de ese punto y "
    "elige el que más te acerca al punto de encuentro (medido en línea recta).\n\n"
    "Es rápido y fácil de entender, pero tiene un límite: a veces llega a un lugar donde ningún "
    "camino lo acerca más y se detiene antes de la meta. A eso se le llama «cima falsa»."
)


def _nombre(grafo: nx.Graph, nodo: str) -> str:
    return grafo.nodes[nodo]["nombre"] if nodo in grafo else nodo


def _metros(valor: float) -> str:
    return f"{valor:.0f} m"


def tiempo_a_pie(distancia_m: float) -> str:
    segundos = distancia_m / VELOCIDAD_MARCHA_MS
    if segundos < 60:
        return "menos de 1 minuto"
    minutos = round(segundos / 60)
    return f"unos {minutos} minuto{'s' if minutos != 1 else ''}"


def indicaciones(grafo: nx.Graph, resultado: ResultadoBusqueda) -> List[str]:
    """Instrucciones paso a paso, como las de un navegador, para una ruta encontrada."""
    if not resultado.exito:
        return []
    pasos = []
    for numero, (u, v) in enumerate(zip(resultado.ruta, resultado.ruta[1:]), 1):
        arista = grafo.edges[u, v]
        distancia = _metros(arista["longitud_m"])
        tipo = arista.get("tipo")
        if tipo == "interior":
            texto = f"Sal del {_nombre(grafo, u)} por el interior del edificio hasta la {_nombre(grafo, v)}."
        elif v == resultado.destino:
            texto = f"Entra a {_nombre(grafo, v)}: es tu punto de encuentro."
        else:
            texto = f"Camina por el sendero hasta el {_nombre(grafo, v)}."
        pasos.append(f"{numero}. {texto}  (≈ {distancia})")
    return pasos


def resumen(grafo: nx.Graph, resultado: ResultadoBusqueda, existe_camino: bool) -> str:
    """Una o dos frases con el resultado, para la parte superior de la pantalla."""
    destino = _nombre(grafo, resultado.destino)
    if resultado.exito:
        texto = (f"Ruta encontrada hasta {destino}: {resultado.distancia_total_m:.0f} m, "
                 f"{tiempo_a_pie(resultado.distancia_total_m)} caminando.")
        if len(resultado.intentos) > 1:
            texto += f" La encontró en el intento {len(resultado.intentos)}."
        return texto
    if resultado.estado == ESTADO_NODO_INEXISTENTE:
        return "No se pudo buscar: el origen o el destino no existen en el mapa."
    if not existe_camino:
        return f"No hay ningún camino abierto hasta {destino}. Elige otro punto de encuentro."
    return (f"No se encontró ruta hasta {destino}: la búsqueda se detuvo en {_nombre(grafo, resultado.nodo_final)}. "
            "Prueba otro punto de encuentro o activa «intentar varias veces».")


def explicar_fallo(grafo: nx.Graph, resultado: ResultadoBusqueda, existe_camino: bool) -> str:
    if resultado.exito or resultado.estado == ESTADO_NODO_INEXISTENTE:
        return ""
    lugar = _nombre(grafo, resultado.nodo_final)
    destino = _nombre(grafo, resultado.destino)
    if not existe_camino:
        return (f"Con los caminos bloqueados que elegiste, no existe ninguna forma de llegar a {destino}. "
                "Ningún método podría encontrar una ruta.")
    if resultado.estado == ESTADO_SIN_VECINOS:
        motivo = f"Llegó a {lugar} y desde allí no salen más caminos."
    elif resultado.estado == ESTADO_OPTIMO_LOCAL:
        motivo = (f"En {lugar} ningún camino lo acercaba más a {destino}, así que se detuvo. "
                  "Es una «cima falsa»: parecía el mejor lugar, pero no era la meta.")
    else:
        motivo = f"Se detuvo en {lugar}."
    return (f"{motivo}\n\nSí existe un camino hasta {destino}, pero Hill Climbing no lo vio porque solo "
            "mira un paso adelante. Puedes elegir otro punto de encuentro o activar «intentar varias "
            "veces», que repite la búsqueda tomando a veces otro camino.")


def explicar_paso(grafo: nx.Graph, resultado: ResultadoBusqueda, indice: int) -> str:
    """La decisión de una iteración, en una o dos frases."""
    paso = resultado.pasos[indice]
    actual = _nombre(grafo, paso.nodo_actual)
    destino = _nombre(grafo, resultado.destino)
    if not paso.candidatos:
        return f"En {actual} no hay más caminos hacia adelante, así que la búsqueda se detiene."
    opciones = [_nombre(grafo, c.nodo) for c in paso.candidatos]
    if paso.seleccionado is None:
        return (f"En {actual} había {len(opciones)} camino(s), pero ninguno acercaba más a {destino}. "
                "La búsqueda se detiene aquí (cima falsa).")
    elegido = next(c for c in paso.candidatos if c.nodo == paso.seleccionado)
    nombre_elegido = _nombre(grafo, elegido.nodo)
    if len(paso.candidatos) == 1:
        frase = f"Desde {actual} solo hay un camino: hacia {nombre_elegido}."
    elif resultado.variante == VARIANTE_ESTOCASTICA:
        frase = (f"Desde {actual} había {len(opciones)} caminos. Entre los que acercan a {destino}, "
                 f"eligió {nombre_elegido} con algo de azar (más probabilidad al que más acerca).")
    elif resultado.criterio == CRITERIO_COSTO_HEURISTICA:
        frase = (f"Desde {actual} había {len(opciones)} caminos. Eligió {nombre_elegido} porque, sumando lo "
                 f"que se camina en ese tramo y lo que aún falta, es la opción más corta "
                 f"(≈ {elegido.valor:.0f} m).")
    else:
        frase = (f"Desde {actual} había {len(opciones)} caminos. Eligió {nombre_elegido} porque es el punto "
                 f"que queda más cerca de {destino} en línea recta (≈ {elegido.h:.0f} m).")
    descartes = []
    for c in paso.candidatos:
        if c.nodo == paso.seleccionado:
            continue
        if c.estado == VECINO_VISITADO:
            descartes.append(f"{_nombre(grafo, c.nodo)} (ya había pasado por ahí)")
        elif c.estado != VECINO_ADMISIBLE:
            descartes.append(f"{_nombre(grafo, c.nodo)} (lo alejaba del destino)")
        elif resultado.variante == VARIANTE_ESTOCASTICA:
            descartes.append(f"{_nombre(grafo, c.nodo)} (también acercaba; esta vez no salió elegido)")
        else:
            descartes.append(f"{_nombre(grafo, c.nodo)} (también acercaba, pero era peor opción)")
    if descartes:
        frase += " Descartó: " + "; ".join(descartes) + "."
    return frase
