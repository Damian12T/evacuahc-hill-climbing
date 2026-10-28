"""Rutas, colores y textos compartidos por los módulos de la aplicación."""

from pathlib import Path

DIRECTORIO_BASE = Path(__file__).resolve().parent
DIRECTORIO_DATOS = DIRECTORIO_BASE / "datos"
DIRECTORIO_EVIDENCIAS = DIRECTORIO_BASE / "evidencias"

ARCHIVO_CAMPUS = DIRECTORIO_DATOS / "campus.json"
ARCHIVO_OSM = DIRECTORIO_DATOS / "campus_osm.json"
IMAGEN_CROQUIS = DIRECTORIO_DATOS / "croquis_campus_espe.png"
IMAGEN_MAPA_HISTORICO = DIRECTORIO_DATOS / "mapa_puntos_encuentro_2019.png"

# Radio medio terrestre usado para la proyección local (equirectangular).
# A la escala del sector (unos 300 m) el error de esta aproximación es despreciable.
RADIO_TIERRA_M = 6_371_000.0

# Criterios de evaluación de vecinos para Hill Climbing.
CRITERIO_COSTO_HEURISTICA = "costo_heuristica"
CRITERIO_HEURISTICA = "heuristica"
NOMBRES_CRITERIO = {
    CRITERIO_COSTO_HEURISTICA: "Tramo + heurística  f(v) = d(u,v) + h(v)",
    CRITERIO_HEURISTICA: "Solo heurística  f(v) = h(v)",
}

HEURISTICA_SALIDA = "salida_obligatoria"
HEURISTICA_EUCLIDIANA = "euclidiana"
NOMBRES_HEURISTICA = {
    HEURISTICA_SALIDA: "Euclidiana con salida obligatoria (G, H -> S)",
    HEURISTICA_EUCLIDIANA: "Euclidiana pura (ignora muros)",
}

VARIANTE_MAXIMA_PENDIENTE = "maxima_pendiente"
VARIANTE_ESTOCASTICA = "estocastica"
NOMBRES_VARIANTE = {
    VARIANTE_MAXIMA_PENDIENTE: "Máxima pendiente (determinista)",
    VARIANTE_ESTOCASTICA: "Estocástico con reinicios",
}
REINICIOS_POR_DEFECTO = 10
SEMILLA_POR_DEFECTO = 0

# Velocidad de marcha para la animación del recorrido. El informe (sección 6) supone
# velocidades uniformes entre 1,0 y 1,4 m/s; se usa el valor medio. Es un supuesto.
VELOCIDAD_MARCHA_MS = 1.2

# Identidad de la aplicación. La metáfora visual es la de la escalada: el punto de
# encuentro es la "cumbre" y las isolíneas de h son las curvas de nivel.
NOMBRE_APP = "EvacuaHC"
LEMA_APP = "Hill Climbing hacia los puntos de encuentro · bloques G y H · ESPE Sangolquí"

# Tema índigo de la interfaz y del mapa.
TEMA = {
    "fondo": "#0d0f1a",
    "panel": "#151829",
    "deslizador": "#9d8cff",
    "tarjeta": "#1c2036",
    "borde": "#2c3152",
    "control": "#232846",
    "control_activo": "#30365e",
    "texto": "#eceefe",
    "texto_suave": "#9499c2",
    "acento": "#6c5ce7",
    "acento_activo": "#8173f0",
    "acento2": "#ffb547",
    "ok": "#8be36a",
    "mal": "#ff8fa3",
    "aviso_fondo": "#24203a",
    "aviso_texto": "#ffd38a",
}

COLORES = {
    "fondo": "#141729",
    "edificio": "#2e3352",
    "edificio_borde": "#454b75",
    "verde": "#18302a",
    "cancha": "#1d3d33",
    "parqueadero": "#1c2038",
    "sendero": "#4a5080",
    "via": "#3a3f66",
    "isolinea": "#a9a6ff",
    "arista": "#c7cbef",
    "arista_bloqueada": "#ff4d6d",
    "ruta": "#8be36a",
    "ruta_fallida": "#ffa94d",
    "visitado": "#c7cbef",
    "actual": "#ffe28a",
    "candidato": "#c9b8ff",
    "descartado": "#7a7fa8",
    "origen": "#e056fd",
    "salida": "#262b4a",
    "acceso": "#262b4a",
    "destino": "#ffb547",
    "texto": "#eceefe",
    "texto_suave": "#a3a8d0",
    "etiqueta_fondo": "#0d0f1a",
}

# Color propio de cada punto de encuentro ("cumbres" posibles).
COLOR_DESTINO = {"P1": "#ff7a59", "P2": "#4cc9f0", "P3": "#f7d154"}

ADVERTENCIA_SEGURIDAD = (
    "PROTOTIPO ACADÉMICO. Las rutas son un modelo aproximado y no han sido validadas "
    "por la Unidad de Seguridad de la ESPE. En una emergencia real siga las "
    "instrucciones oficiales y la señalización del campus."
)
