"""Estructuras de datos que registran la ejecución de Hill Climbing."""

from dataclasses import dataclass, field
from typing import List, Optional

# Estados de cada vecino evaluado en una iteración.
VECINO_ADMISIBLE = "admisible"
VECINO_NO_MEJORA = "no mejora h"
VECINO_VISITADO = "ya visitado"

# Estados finales de la búsqueda.
ESTADO_EXITO = "exito"
ESTADO_NODO_INEXISTENTE = "nodo_inexistente"
ESTADO_SIN_VECINOS = "sin_vecinos"
ESTADO_SOLO_VISITADOS = "solo_visitados"
ESTADO_OPTIMO_LOCAL = "optimo_local"
ESTADO_LIMITE_ITERACIONES = "limite_iteraciones"

DESCRIPCION_ESTADO = {
    ESTADO_EXITO: "Destino alcanzado",
    ESTADO_NODO_INEXISTENTE: "Origen o destino inexistente",
    ESTADO_SIN_VECINOS: "Bloqueado: sin vecinos transitables",
    ESTADO_SOLO_VISITADOS: "Bloqueado: todos los vecinos ya fueron visitados",
    ESTADO_OPTIMO_LOCAL: "Bloqueado: óptimo local (ningún vecino mejora h)",
    ESTADO_LIMITE_ITERACIONES: "Detenido: límite de iteraciones",
}


@dataclass
class Candidato:
    """Un vecino evaluado durante una iteración."""
    nodo: str
    longitud_m: Optional[float]
    h: float
    valor: float
    estado: str


@dataclass
class Paso:
    """Una iteración de Hill Climbing: desde dónde se evaluó, qué se vio y qué se decidió."""
    iteracion: int
    nodo_actual: str
    h_actual: float
    candidatos: List[Candidato]
    seleccionado: Optional[str]
    motivo: str


@dataclass
class ResultadoBusqueda:
    origen: str
    destino: str
    criterio: str
    exito: bool
    estado: str
    motivo: str
    ruta: List[str] = field(default_factory=list)
    visitados: List[str] = field(default_factory=list)
    pasos: List[Paso] = field(default_factory=list)
    distancia_total_m: Optional[float] = None
    heuristica: str = ""
    variante: str = ""
    # Resumen de cada intento (solo la variante estocástica hace más de uno).
    intentos: List[str] = field(default_factory=list)

    @property
    def iteraciones(self) -> int:
        return len(self.pasos)

    @property
    def nodo_final(self) -> Optional[str]:
        return self.ruta[-1] if self.ruta else None

    @property
    def descripcion_estado(self) -> str:
        return DESCRIPCION_ESTADO.get(self.estado, self.estado)
