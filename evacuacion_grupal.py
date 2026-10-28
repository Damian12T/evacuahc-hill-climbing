"""Evacuación de varias personas: búsqueda sencilla frente a Hill Climbing.

Planteamiento tomado del informe del grupo (secciones 4 a 6):
- Las personas de G y H se organizan en grupos de 10; cada grupo sigue una única ruta.
- Cada punto de encuentro tiene un cupo y cada tramo un flujo máximo (personas/s).
  Ambos son SUPUESTOS DIDÁCTICOS del informe, no aforos medidos.
- Modelo de colas por tramo (informe, sección 6): una persona que llega en el instante a
  entra en b = max(a, q), donde q es la siguiente admisión libre; luego q = b + 1/c
  (c = flujo del tramo) y sale en b + d/v (d = longitud, v = su velocidad).
- Velocidad individual uniforme entre 1,0 y 1,4 m/s y reacción entre 0 y 15 s (supuestos).

Se comparan dos formas de repartir los grupos entre los puntos de encuentro:
- Búsqueda sencilla: cada grupo va al punto más cercano por el camino más corto mientras
  quede cupo (primero los grupos de G y luego los de H). No mira las colas.
- Hill Climbing: parte de la búsqueda sencilla y, en cada iteración, evalúa todos los
  vecinos (mover un grupo a otro punto o intercambiar los puntos de dos grupos) y se
  queda con el que más reduce el tiempo total. Se detiene cuando ningún vecino mejora
  (óptimo local). No acepta empeorar ni usa memoria de movimientos prohibidos.

Objetivo: F = (T, A), donde T es el instante en que llega la última persona y A la
media de llegada; se compara primero T y A solo desempata.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx

TAMANO_GRUPO = 10
VELOCIDAD_MIN, VELOCIDAD_MAX = 1.0, 1.4
REACCION_MAX = 15.0
MAX_ITERACIONES_HC = 100


@dataclass
class Persona:
    id: int
    origen: str
    grupo: int
    velocidad: float
    salida: float     # instante en que empieza a moverse (reacción + retraso del bloque)


@dataclass
class Grupo:
    id: int
    origen: str
    personas: List[int]

    @property
    def tamano(self) -> int:
        return len(self.personas)


@dataclass
class Escenario:
    grafo: nx.DiGraph
    personas: List[Persona]
    grupos: List[Grupo]
    rutas: Dict[Tuple[str, str], List[str]]   # (origen, destino) -> nodos
    cupos: Dict[str, int]


@dataclass
class Tramo:
    u: str
    v: str
    llegada: float    # llegó a la cola del tramo
    entrada: float    # empezó a recorrerlo
    salida: float     # terminó de recorrerlo


@dataclass
class Plan:
    """Una asignación (destino de cada grupo) y su simulación completa."""
    nombre: str
    asignacion: Tuple[str, ...]
    tiempo_total: float                    # T: llegada de la última persona
    llegada_media: float                   # A
    espera_media: float
    distancia_total: float                 # persona·m
    personas_por_destino: Dict[str, int]
    recorridos: Dict[int, List[Tramo]]     # id de persona -> tramos con tiempos
    historial: List[float] = field(default_factory=list)   # T en cada iteración (Hill Climbing)
    movimientos: List[str] = field(default_factory=list)
    asignaciones: List[Tuple[str, ...]] = field(default_factory=list)   # asignación tras cada iteración
    evaluaciones: int = 0
    motivo_parada: str = ""

    @property
    def costo(self) -> Tuple[float, float]:
        return self.tiempo_total, self.llegada_media


# ---------------------------------------------------------------- escenario
def crear_escenario(grafo: nx.DiGraph, personas_por_bloque: Dict[str, int], semilla: int = 0,
                    retrasos: Optional[Dict[str, float]] = None) -> Escenario:
    """Genera personas y grupos de forma reproducible y obtiene una ruta por origen y destino."""
    for bloque, cantidad in personas_por_bloque.items():
        if bloque not in grafo or grafo.nodes[bloque]["tipo"] != "origen":
            raise ValueError(f"{bloque} no es un bloque de origen.")
        if not isinstance(cantidad, int) or cantidad < 0:
            raise ValueError(f"El número de personas de {bloque} debe ser un entero mayor o igual que 0.")
    if sum(personas_por_bloque.values()) == 0:
        raise ValueError("Debe haber al menos una persona que evacuar.")

    retrasos = retrasos or {}
    aleatorio = random.Random(semilla)
    personas, grupos = [], []
    for bloque in sorted(personas_por_bloque):   # G y luego H, como en el informe
        cantidad = personas_por_bloque[bloque]
        for inicio in range(0, cantidad, TAMANO_GRUPO):
            grupo = Grupo(len(grupos), bloque, [])
            for _ in range(min(TAMANO_GRUPO, cantidad - inicio)):
                persona = Persona(len(personas), bloque, grupo.id,
                                  aleatorio.uniform(VELOCIDAD_MIN, VELOCIDAD_MAX),
                                  aleatorio.uniform(0, REACCION_MAX) + retrasos.get(bloque, 0.0))
                personas.append(persona)
                grupo.personas.append(persona.id)
            grupos.append(grupo)

    # Rutas candidatas: el camino por tramos transitables hacia cada destino. En esta red hay
    # un único camino por par (informe, sección 2), así que el reparto es la decisión real.
    habilitado = nx.subgraph_view(grafo, filter_edge=lambda u, v: grafo.edges[u, v].get("transitable", True))
    destinos = sorted(n for n, d in grafo.nodes(data=True) if d["tipo"] == "destino")
    rutas = {}
    for bloque in personas_por_bloque:
        for destino in destinos:
            if nx.has_path(habilitado, bloque, destino):
                rutas[(bloque, destino)] = nx.shortest_path(habilitado, bloque, destino, weight="longitud_m")
    cupos = {d: grafo.nodes[d].get("cupo_supuesto") or 0 for d in destinos}
    return Escenario(grafo, personas, grupos, rutas, cupos)


def destinos_posibles(escenario: Escenario, grupo: Grupo) -> List[str]:
    return sorted(d for (o, d) in escenario.rutas if o == grupo.origen)


def longitud(escenario: Escenario, origen: str, destino: str) -> float:
    ruta = escenario.rutas[(origen, destino)]
    return sum(escenario.grafo.edges[u, v]["longitud_m"] for u, v in zip(ruta, ruta[1:]))


def es_factible(escenario: Escenario, asignacion: Tuple[str, ...]) -> bool:
    ocupacion: Dict[str, int] = {}
    for grupo, destino in zip(escenario.grupos, asignacion):
        if (grupo.origen, destino) not in escenario.rutas:
            return False
        ocupacion[destino] = ocupacion.get(destino, 0) + grupo.tamano
    return all(ocupacion[d] <= escenario.cupos.get(d, 0) for d in ocupacion)


# ---------------------------------------------------------------- simulación de colas
def simular(escenario: Escenario, asignacion: Tuple[str, ...], nombre: str = "") -> Plan:
    grafo = escenario.grafo
    ruta_de = {}
    for grupo, destino in zip(escenario.grupos, asignacion):
        for pid in grupo.personas:
            ruta_de[pid] = escenario.rutas[(grupo.origen, destino)]

    # Cada persona espera en el primer nodo de su ruta desde su instante de salida.
    listo = {p.id: p.salida for p in escenario.personas}   # instante en que llega al siguiente tramo
    posicion = {p.id: 0 for p in escenario.personas}       # índice del nodo actual en su ruta
    recorridos = {p.id: [] for p in escenario.personas}
    velocidad = {p.id: p.velocidad for p in escenario.personas}

    # El grafo no tiene ciclos: cada tramo se procesa una vez, en orden topológico.
    orden = {n: i for i, n in enumerate(nx.topological_sort(grafo))}
    for u, v in sorted(grafo.edges, key=lambda e: (orden[e[0]], orden[e[1]])):
        en_tramo = [pid for pid, ruta in ruta_de.items()
                    if posicion[pid] < len(ruta) - 1 and ruta[posicion[pid]] == u and ruta[posicion[pid] + 1] == v]
        if not en_tramo:
            continue
        datos = grafo.edges[u, v]
        intervalo = 1.0 / datos["flujo_supuesto"]
        siguiente_admision = float("-inf")
        for pid in sorted(en_tramo, key=lambda p: (listo[p], p)):   # orden de llegada; empate por id
            llegada = listo[pid]
            entrada = max(llegada, siguiente_admision)
            siguiente_admision = entrada + intervalo
            salida = entrada + datos["longitud_m"] / velocidad[pid]
            recorridos[pid].append(Tramo(u, v, llegada, entrada, salida))
            listo[pid] = salida
            posicion[pid] += 1

    llegadas = [listo[pid] for pid in ruta_de]
    esperas = [t.entrada - t.llegada for tramos in recorridos.values() for t in tramos]
    por_destino: Dict[str, int] = {d: 0 for d in escenario.cupos}
    distancia = 0.0
    for grupo, destino in zip(escenario.grupos, asignacion):
        por_destino[destino] += grupo.tamano
        distancia += grupo.tamano * longitud(escenario, grupo.origen, destino)
    return Plan(nombre, tuple(asignacion), max(llegadas), sum(llegadas) / len(llegadas),
                sum(esperas) / len(ruta_de), distancia, por_destino, recorridos)


# ---------------------------------------------------------------- búsquedas
def busqueda_sencilla(escenario: Escenario) -> Plan:
    """Cada grupo al punto más cercano con cupo libre (no considera las colas)."""
    ocupacion = {d: 0 for d in escenario.cupos}
    asignacion = []
    for grupo in escenario.grupos:
        for destino in sorted(destinos_posibles(escenario, grupo),
                              key=lambda d: (longitud(escenario, grupo.origen, d), d)):
            if ocupacion[destino] + grupo.tamano <= escenario.cupos[destino]:
                ocupacion[destino] += grupo.tamano
                asignacion.append(destino)
                break
        else:
            raise ValueError("No hay cupo suficiente en los puntos de encuentro alcanzables "
                             f"(cupos supuestos: {escenario.cupos}).")
    plan = simular(escenario, tuple(asignacion), "Búsqueda sencilla")
    plan.historial = [plan.tiempo_total]
    plan.motivo_parada = "Asignación directa: cada grupo al punto más cercano con cupo."
    return plan


def _vecinos(escenario: Escenario, asignacion: Tuple[str, ...]):
    """Mover un grupo a otro destino, o intercambiar los destinos de dos grupos."""
    for i, grupo in enumerate(escenario.grupos):
        for destino in destinos_posibles(escenario, grupo):
            if destino != asignacion[i]:
                nueva = list(asignacion)
                nueva[i] = destino
                yield tuple(nueva), f"grupo {i + 1} ({grupo.origen}) pasa de {asignacion[i]} a {destino}"
    for i in range(len(escenario.grupos)):
        for j in range(i + 1, len(escenario.grupos)):
            if asignacion[i] == asignacion[j]:
                continue
            gi, gj = escenario.grupos[i], escenario.grupos[j]
            # Intercambiar dos grupos iguales del mismo bloque apenas cambia nada: se omite.
            if gi.origen == gj.origen and gi.tamano == gj.tamano:
                continue
            nueva = list(asignacion)
            nueva[i], nueva[j] = asignacion[j], asignacion[i]
            yield tuple(nueva), f"grupos {i + 1} ({gi.origen}) y {j + 1} ({gj.origen}) intercambian destino"


def hill_climbing_grupal(escenario: Escenario, inicial: Optional[Plan] = None,
                         max_iteraciones: int = MAX_ITERACIONES_HC) -> Plan:
    actual = inicial or busqueda_sencilla(escenario)
    historial = [actual.tiempo_total]
    asignaciones = [actual.asignacion]
    movimientos = []
    cache = {actual.asignacion: actual.costo}
    evaluaciones = 0
    motivo = f"Se alcanzó el máximo de {max_iteraciones} iteraciones."
    for _ in range(max_iteraciones):
        mejor, mejor_costo, mejor_movimiento = None, actual.costo, ""
        for asignacion, descripcion in _vecinos(escenario, actual.asignacion):
            if not es_factible(escenario, asignacion):
                continue
            if asignacion not in cache:
                cache[asignacion] = simular(escenario, asignacion).costo
                evaluaciones += 1
            if cache[asignacion] < mejor_costo:
                mejor, mejor_costo, mejor_movimiento = asignacion, cache[asignacion], descripcion
        if mejor is None:
            motivo = "Óptimo local: ningún vecino reduce el tiempo total."
            break
        actual = simular(escenario, mejor)
        historial.append(actual.tiempo_total)
        asignaciones.append(actual.asignacion)
        movimientos.append(mejor_movimiento)
    actual.nombre = "Hill Climbing"
    actual.historial = historial
    actual.asignaciones = asignaciones
    actual.movimientos = movimientos
    actual.evaluaciones = evaluaciones
    actual.motivo_parada = motivo
    return actual


# ---------------------------------------------------------------- animación
def estado_persona(plan: Plan, pid: int, t: float, origen: str) -> Tuple[str, str, float]:
    """Dónde está una persona en el instante t.

    Devuelve (situación, nodo o tramo, fracción): situación es "origen", "cola", "tramo" o
    "llegó"; para "tramo" la fracción indica cuánto lleva recorrido.
    """
    tramos = plan.recorridos[pid]
    if not tramos or t < tramos[0].llegada:
        return "origen", origen, 0.0
    for tramo in tramos:
        if t < tramo.entrada:
            return "cola", tramo.u, 0.0
        if t < tramo.salida:
            return "tramo", f"{tramo.u}>{tramo.v}", (t - tramo.entrada) / (tramo.salida - tramo.entrada)
    return "llegó", tramos[-1].v, 1.0
