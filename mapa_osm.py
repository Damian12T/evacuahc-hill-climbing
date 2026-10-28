"""Mapa base del sector a partir de OpenStreetMap (© colaboradores de OpenStreetMap, ODbL).

La aplicación lee una copia local (datos/campus_osm.json) y funciona sin conexión.
Para volver a descargarla desde la API Overpass:

    python mapa_osm.py --descargar
"""

import argparse
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Tuple

from configuracion import ARCHIVO_OSM

URL_OVERPASS = "https://overpass-api.de/api/interpreter"
# Sur, oeste, norte, este: sector norte del campus alrededor de G, H y P1-P3.
CAJA = (-0.3170, -78.4482, -0.3118, -78.4434)
CLAVES = ("building", "highway", "leisure", "landuse", "natural", "amenity")


@dataclass
class Elemento:
    categoria: str          # edificio, verde, cancha, sendero, via, parqueadero
    nombre: str
    puntos: List[Tuple[float, float]]  # metros locales
    cerrado: bool


def descargar(ruta=ARCHIVO_OSM) -> int:
    sur, oeste, norte, este = CAJA
    caja = f"({sur},{oeste},{norte},{este})"
    consulta = "[out:json][timeout:60];(" + "".join(f'way["{k}"]{caja};' for k in CLAVES) + ");out geom;"
    peticion = urllib.request.Request(
        URL_OVERPASS, data=urllib.parse.urlencode({"data": consulta}).encode(),
        headers={"User-Agent": "evacuacion-espe-academico/1.0"})
    with urllib.request.urlopen(peticion, timeout=90) as respuesta:
        datos = json.load(respuesta)
    elementos = [
        {"tags": e.get("tags", {}), "geometria": [[p["lat"], p["lon"]] for p in e["geometry"]]}
        for e in datos["elements"] if e.get("geometry")
    ]
    salida = {
        "fuente": "© colaboradores de OpenStreetMap, licencia ODbL. Descargado mediante la API Overpass.",
        "caja_sur_oeste_norte_este": CAJA,
        "elementos": elementos,
    }
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False)
    return len(elementos)


def _categoria(tags: dict) -> str:
    if "building" in tags:
        return "edificio"
    if tags.get("leisure") == "pitch" or tags.get("leisure") == "sports_centre":
        return "cancha"
    if tags.get("leisure") in ("park", "garden") or tags.get("natural") in ("grassland", "wood", "scrub") \
            or tags.get("landuse") in ("grass", "forest", "meadow", "recreation_ground"):
        return "verde"
    if tags.get("amenity") in ("parking", "parking_space"):
        return "parqueadero"
    if tags.get("highway") in ("footway", "path", "pedestrian", "steps", "cycleway"):
        return "sendero"
    if "highway" in tags:
        return "via"
    return ""


def cargar(lat0: float, lon0: float, ruta=ARCHIVO_OSM) -> List[Elemento]:
    """Elementos del mapa en metros locales, proyectados alrededor de (lat0, lon0).

    Se usa el mismo origen que la calibración del grafo para que ambos coincidan.
    Devuelve una lista vacía si no existe la copia local.
    """
    from grafo_universidad import geo_a_metros

    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    elementos = []
    for e in datos["elementos"]:
        categoria = _categoria(e["tags"])
        if not categoria:
            continue
        puntos = [geo_a_metros(lat, lon, lat0, lon0) for lat, lon in e["geometria"]]
        cerrado = len(puntos) > 2 and e["geometria"][0] == e["geometria"][-1]
        elementos.append(Elemento(categoria, e["tags"].get("name", ""), puntos, cerrado))
    return elementos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mapa base OpenStreetMap del sector")
    parser.add_argument("--descargar", action="store_true", help="descarga de nuevo desde Overpass")
    if parser.parse_args().descargar:
        print(f"{descargar()} elementos guardados en {ARCHIVO_OSM}")
