"""Construcción del grafo de evacuación a partir de datos/campus.json.

Coordenadas:
- P1, P2 y P3 tienen latitud y longitud documentadas en el informe.
- El resto de nodos solo tiene posición en píxeles sobre la figura de referencia.
Con los tres destinos como puntos de control se ajusta una transformación de
semejanza (escala, rotación y traslación) píxel -> metros, y con ella se estiman
las posiciones en metros de G, H, S, K, J y L. Las longitudes de las aristas NO se
calculan con esas posiciones: se usan las longitudes medidas que da el informe.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import networkx as nx
import numpy as np

from configuracion import ARCHIVO_CAMPUS, RADIO_TIERRA_M


@dataclass
class Calibracion:
    """Transformación píxel -> metros locales (x hacia el este, y hacia el norte)."""
    a: float
    b: float
    tx: float
    ty: float
    lat0: float
    lon0: float
    error_rms_m: float

    @property
    def metros_por_pixel(self) -> float:
        return math.hypot(self.a, self.b)

    @property
    def rotacion_grados(self) -> float:
        return math.degrees(math.atan2(self.b, self.a))

    def pixel_a_metros(self, px: float, py: float) -> Tuple[float, float]:
        u, v = px, -py  # en la imagen el eje y crece hacia abajo
        return self.a * u - self.b * v + self.tx, self.b * u + self.a * v + self.ty

    def metros_a_geo(self, x: float, y: float) -> Tuple[float, float]:
        lat = self.lat0 + math.degrees(y / RADIO_TIERRA_M)
        lon = self.lon0 + math.degrees(x / (RADIO_TIERRA_M * math.cos(math.radians(self.lat0))))
        return lat, lon


def geo_a_metros(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """Proyección equirectangular local alrededor de (lat0, lon0)."""
    x = math.radians(lon - lon0) * RADIO_TIERRA_M * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * RADIO_TIERRA_M
    return x, y


def cargar_datos(ruta: Path = ARCHIVO_CAMPUS) -> dict:
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def calibrar(nodos: List[dict]) -> Calibracion:
    """Ajusta por mínimos cuadrados la semejanza píxel -> metros con los nodos que tienen lat/lon."""
    control = [n for n in nodos if "lat" in n and "lon" in n and "px" in n]
    if len(control) < 2:
        raise ValueError("Se necesitan al menos dos nodos con latitud y longitud para calibrar.")
    lat0 = sum(n["lat"] for n in control) / len(control)
    lon0 = sum(n["lon"] for n in control) / len(control)

    filas, objetivo = [], []
    for n in control:
        u, v = n["px"][0], -n["px"][1]
        x, y = geo_a_metros(n["lat"], n["lon"], lat0, lon0)
        filas.append([u, -v, 1, 0])
        objetivo.append(x)
        filas.append([v, u, 0, 1])
        objetivo.append(y)
    solucion, *_ = np.linalg.lstsq(np.array(filas), np.array(objetivo), rcond=None)
    a, b, tx, ty = (float(valor) for valor in solucion)

    residuos = np.array(filas) @ solucion - np.array(objetivo)
    error_rms = float(math.sqrt(np.sum(residuos ** 2) / len(control)))
    return Calibracion(a, b, tx, ty, lat0, lon0, error_rms)


def construir_grafo(datos: dict = None, bloqueadas: Iterable[Tuple[str, str]] = ()) -> nx.DiGraph:
    """Devuelve el grafo dirigido del campus.

    Las aristas bloqueadas se conservan en el grafo con transitable=False para
    poder dibujarlas, pero Hill Climbing nunca las recorre.
    """
    datos = datos if datos is not None else cargar_datos()
    calibracion = calibrar(datos["nodos"])

    grafo = nx.DiGraph(calibracion=calibracion, descripcion=datos.get("descripcion", ""))
    for n in datos["nodos"]:
        if "lat" in n and "lon" in n:
            x, y = geo_a_metros(n["lat"], n["lon"], calibracion.lat0, calibracion.lon0)
            lat, lon, posicion = n["lat"], n["lon"], "documentada"
        else:
            x, y = calibracion.pixel_a_metros(*n["px"])
            lat, lon = calibracion.metros_a_geo(x, y)
            posicion = "estimada"
        grafo.add_node(
            n["id"], nombre=n["nombre"], tipo=n["tipo"], x=x, y=y, lat=lat, lon=lon,
            posicion=posicion, descripcion=n.get("descripcion", ""), fuente=n.get("fuente", ""),
            cupo_supuesto=n.get("cupo_supuesto"), salida_obligatoria=n.get("salida_obligatoria"), etiqueta=n.get("etiqueta"),
        )
    for n, atributos in grafo.nodes(data=True):
        salida = atributos["salida_obligatoria"]
        if salida is not None and salida not in grafo:
            raise ValueError(f"El nodo {n} declara una salida obligatoria inexistente: {salida}")

    for e in datos["aristas"]:
        for extremo in (e["origen"], e["destino"]):
            if extremo not in grafo:
                raise ValueError(f"La arista {e['origen']} -> {e['destino']} usa un nodo inexistente: {extremo}")
        grafo.add_edge(
            e["origen"], e["destino"], longitud_m=e["longitud_m"], flujo_supuesto=e.get("flujo_supuesto"),
            tipo=e.get("tipo", ""), descripcion=e.get("descripcion", ""), transitable=True,
        )

    aplicar_bloqueos(grafo, bloqueadas)
    return grafo


def aplicar_bloqueos(grafo: nx.DiGraph, bloqueadas: Iterable[Tuple[str, str]]) -> None:
    """Marca como no transitables las aristas indicadas (y habilita todas las demás)."""
    bloqueadas = {tuple(arista) for arista in bloqueadas}
    desconocidas = bloqueadas - set(grafo.edges)
    if desconocidas:
        raise ValueError(f"Aristas bloqueadas inexistentes: {sorted(desconocidas)}")
    for u, v in grafo.edges:
        grafo.edges[u, v]["transitable"] = (u, v) not in bloqueadas


def existe_camino_transitable(grafo: nx.DiGraph, origen: str, destino: str) -> bool:
    """Diagnóstico: ¿hay algún camino por aristas transitables?

    Solo se usa para explicar un fallo de Hill Climbing (distinguir "no existe
    camino" de "la búsqueda local no lo encontró"). Nunca construye la ruta.
    """
    if origen not in grafo or destino not in grafo:
        return False
    habilitado = nx.subgraph_view(grafo, filter_edge=lambda u, v: grafo.edges[u, v].get("transitable", True))
    return nx.has_path(habilitado, origen, destino)


def nodos_por_tipo(grafo: nx.DiGraph, tipo: str) -> List[str]:
    return sorted(n for n, datos in grafo.nodes(data=True) if datos["tipo"] == tipo)


def etiqueta(grafo: nx.DiGraph, nodo: str) -> str:
    return f"{nodo} · {grafo.nodes[nodo]['nombre']}"


def escenarios(datos: dict = None) -> Dict[str, dict]:
    datos = datos if datos is not None else cargar_datos()
    return datos.get("escenarios", {})
