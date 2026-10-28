"""Pruebas del algoritmo con grafos SINTÉTICOS.

Las coordenadas y longitudes de estos grafos son inventadas a propósito para forzar
cada situación; no representan el campus de la ESPE.
"""

import random
import sys
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configuracion import CRITERIO_COSTO_HEURISTICA, CRITERIO_HEURISTICA  # noqa: E402
from hill_climbing import (  # noqa: E402
    distancia_con_salida, distancia_euclidiana, hill_climbing, hill_climbing_con_reinicios,
)
from modelos import (  # noqa: E402
    ESTADO_EXITO, ESTADO_LIMITE_ITERACIONES, ESTADO_NODO_INEXISTENTE, ESTADO_OPTIMO_LOCAL,
    ESTADO_SIN_VECINOS, VECINO_ADMISIBLE, VECINO_NO_MEJORA, VECINO_VISITADO,
)


def grafo_sintetico(nodos, aristas, dirigido=True):
    """nodos: {id: (x, y)}; aristas: [(u, v, longitud)]."""
    grafo = nx.DiGraph() if dirigido else nx.Graph()
    for n, (x, y) in nodos.items():
        grafo.add_node(n, x=x, y=y, nombre=f"Sintético {n}", tipo="sintetico")
    for u, v, longitud in aristas:
        grafo.add_edge(u, v, longitud_m=longitud, transitable=True)
    return grafo


class PruebasEntradas(unittest.TestCase):
    def setUp(self):
        self.grafo = grafo_sintetico({"A": (0, 0), "B": (10, 0)}, [("A", "B", 10)])

    def test_origen_inexistente(self):
        r = hill_climbing(self.grafo, "Z", "B")
        self.assertFalse(r.exito)
        self.assertEqual(r.estado, ESTADO_NODO_INEXISTENTE)
        self.assertIn("Z", r.motivo)
        self.assertEqual(r.ruta, [])

    def test_destino_inexistente(self):
        r = hill_climbing(self.grafo, "A", "Z")
        self.assertFalse(r.exito)
        self.assertEqual(r.estado, ESTADO_NODO_INEXISTENTE)
        self.assertIn("Z", r.motivo)

    def test_criterio_desconocido(self):
        with self.assertRaises(ValueError):
            hill_climbing(self.grafo, "A", "B", criterio="otro")

    def test_origen_igual_destino(self):
        r = hill_climbing(self.grafo, "A", "A")
        self.assertTrue(r.exito)
        self.assertEqual(r.ruta, ["A"])
        self.assertEqual(r.distancia_total_m, 0.0)


class PruebasBusqueda(unittest.TestCase):
    def test_grafo_sin_conexiones(self):
        grafo = grafo_sintetico({"A": (0, 0), "B": (10, 0)}, [])
        r = hill_climbing(grafo, "A", "B")
        self.assertFalse(r.exito)
        self.assertEqual(r.estado, ESTADO_SIN_VECINOS)
        self.assertEqual(r.ruta, ["A"])
        self.assertEqual(len(r.pasos), 1)
        self.assertIsNone(r.pasos[0].seleccionado)

    def test_destino_desconectado(self):
        # A -> B, pero D está en otra componente.
        grafo = grafo_sintetico({"A": (0, 0), "B": (5, 0), "C": (20, 0), "D": (25, 0)},
                                [("A", "B", 5), ("C", "D", 5)])
        r = hill_climbing(grafo, "A", "D")
        self.assertFalse(r.exito)
        self.assertEqual(r.estado, ESTADO_SIN_VECINOS)
        self.assertEqual(r.ruta, ["A", "B"])
        self.assertIsNone(r.distancia_total_m)

    def test_bloqueo_en_optimo_local_aunque_exista_camino(self):
        # El único camino A -> R -> D obliga a alejarse primero (R está más lejos de D que A).
        grafo = grafo_sintetico({"A": (0, 0), "R": (-10, 0), "D": (10, 0)},
                                [("A", "R", 10), ("R", "D", 20)])
        self.assertTrue(nx.has_path(grafo, "A", "D"))
        r = hill_climbing(grafo, "A", "D")
        self.assertFalse(r.exito)
        self.assertEqual(r.estado, ESTADO_OPTIMO_LOCAL)
        self.assertEqual(r.ruta, ["A"])
        self.assertEqual(r.pasos[0].candidatos[0].estado, VECINO_NO_MEJORA)

    def test_varios_vecinos_elige_el_mejor_y_registra_todos(self):
        grafo = grafo_sintetico(
            {"A": (0, 0), "B": (6, 4), "C": (6, -1), "E": (-3, 0), "D": (10, 0)},
            [("A", "B", 7), ("A", "C", 7), ("A", "E", 3), ("B", "D", 6), ("C", "D", 5)])
        r = hill_climbing(grafo, "A", "D", criterio=CRITERIO_HEURISTICA)
        self.assertTrue(r.exito)
        primero = r.pasos[0]
        self.assertEqual([c.nodo for c in primero.candidatos], ["B", "C", "E"])
        estados = {c.nodo: c.estado for c in primero.candidatos}
        self.assertEqual(estados, {"B": VECINO_ADMISIBLE, "C": VECINO_ADMISIBLE, "E": VECINO_NO_MEJORA})
        self.assertEqual(primero.seleccionado, "C")  # h(C) ≈ 4,12 < h(B) ≈ 5,66
        self.assertEqual(r.ruta, ["A", "C", "D"])
        self.assertAlmostEqual(r.distancia_total_m, 12.0)

    def test_criterio_costo_mas_heuristica_penaliza_tramo_largo(self):
        # B parece más cerca de D, pero el tramo A -> B es muy largo.
        grafo = grafo_sintetico({"A": (0, 0), "B": (8, 0), "C": (5, 0), "D": (10, 0)},
                                [("A", "B", 50), ("A", "C", 5), ("B", "D", 2), ("C", "D", 5)])
        solo_h = hill_climbing(grafo, "A", "D", criterio=CRITERIO_HEURISTICA)
        costo_h = hill_climbing(grafo, "A", "D", criterio=CRITERIO_COSTO_HEURISTICA)
        self.assertEqual(solo_h.ruta, ["A", "B", "D"])
        self.assertEqual(costo_h.ruta, ["A", "C", "D"])
        self.assertAlmostEqual(costo_h.pasos[0].candidatos[0].valor, 50 + 2)  # f(B) = d + h

    def test_prevencion_de_ciclos(self):
        # Grafo no dirigido con ciclo A-B-C-A: el vecino ya visitado se marca y no se repite.
        grafo = grafo_sintetico({"A": (0, 0), "B": (5, 0), "C": (5, 5), "D": (10, 0)},
                                [("A", "B", 5), ("B", "C", 5), ("C", "A", 7), ("B", "D", 5)], dirigido=False)
        r = hill_climbing(grafo, "A", "D")
        self.assertTrue(r.exito)
        self.assertEqual(len(r.ruta), len(set(r.ruta)))
        segundo = r.pasos[1]
        self.assertEqual(segundo.nodo_actual, "B")
        self.assertEqual({c.nodo: c.estado for c in segundo.candidatos}["A"], VECINO_VISITADO)

    def test_limite_de_iteraciones(self):
        grafo = grafo_sintetico({"A": (0, 0), "B": (1, 0), "C": (2, 0), "D": (3, 0)},
                                [("A", "B", 1), ("B", "C", 1), ("C", "D", 1)])
        r = hill_climbing(grafo, "A", "D", max_iteraciones=1)
        self.assertFalse(r.exito)
        self.assertEqual(r.estado, ESTADO_LIMITE_ITERACIONES)

    def test_arista_no_transitable_se_ignora(self):
        grafo = grafo_sintetico({"A": (0, 0), "B": (5, 0), "C": (5, 3), "D": (10, 0)},
                                [("A", "B", 5), ("A", "C", 6), ("B", "D", 5), ("C", "D", 6)])
        grafo.edges["A", "B"]["transitable"] = False
        r = hill_climbing(grafo, "A", "D")
        self.assertEqual(r.ruta, ["A", "C", "D"])
        self.assertNotIn("B", [c.nodo for c in r.pasos[0].candidatos])

    def test_determinismo(self):
        grafo = grafo_sintetico({"A": (0, 0), "B": (5, 1), "C": (5, -1), "D": (10, 0)},
                                [("A", "B", 5), ("A", "C", 5), ("B", "D", 5), ("C", "D", 5)])
        rutas = {tuple(hill_climbing(grafo, "A", "D").ruta) for _ in range(5)}
        self.assertEqual(rutas, {("A", "B", "D")})  # empate resuelto por identificador


class PruebasHeuristicasYVariantes(unittest.TestCase):
    def test_heuristica_con_salida_obligatoria(self):
        grafo = grafo_sintetico({"A": (0, 0), "S": (-3, 0), "D": (10, 0)}, [("A", "S", 3), ("S", "D", 13)])
        grafo.nodes["A"]["salida_obligatoria"] = "S"
        self.assertAlmostEqual(distancia_euclidiana(grafo, "A", "D"), 10)
        self.assertAlmostEqual(distancia_con_salida(grafo, "A", "D"), 3 + 13)
        # Con euclidiana pura, alejarse hasta la salida parece empeorar: óptimo local.
        self.assertEqual(hill_climbing(grafo, "A", "D", distancia_euclidiana).estado, ESTADO_OPTIMO_LOCAL)
        self.assertEqual(hill_climbing(grafo, "A", "D", distancia_con_salida).ruta, ["A", "S", "D"])

    def test_estocastico_con_reinicios_supera_callejon(self):
        # B parece mejor pero es un callejón; C lleva al destino.
        grafo = grafo_sintetico({"A": (0, 0), "B": (9, 0), "C": (4, 3), "D": (10, 3)},
                                [("A", "B", 9), ("A", "C", 5), ("C", "D", 6)])
        determinista = hill_climbing(grafo, "A", "D", criterio=CRITERIO_HEURISTICA)
        self.assertEqual(determinista.estado, ESTADO_SIN_VECINOS)
        r = hill_climbing_con_reinicios(grafo, "A", "D", criterio=CRITERIO_HEURISTICA, max_reinicios=30, semilla=3)
        self.assertTrue(r.exito)
        self.assertEqual(r.ruta, ["A", "C", "D"])
        self.assertEqual(len(r.intentos), int(r.intentos[-1].split(":")[0].split()[-1]))

    def test_estocastico_respeta_mejora_y_reproducible(self):
        grafo = grafo_sintetico({"A": (0, 0), "B": (9, 0), "C": (4, 3), "D": (10, 3)},
                                [("A", "B", 9), ("A", "C", 5), ("C", "D", 6)])
        r1 = hill_climbing_con_reinicios(grafo, "A", "D", max_reinicios=5, semilla=7)
        r2 = hill_climbing_con_reinicios(grafo, "A", "D", max_reinicios=5, semilla=7)
        self.assertEqual(r1.intentos, r2.intentos)
        for paso in r1.pasos:
            if paso.seleccionado:
                elegido = next(c for c in paso.candidatos if c.nodo == paso.seleccionado)
                self.assertLess(elegido.h, paso.h_actual)

    def test_estocastico_sin_camino_agota_reinicios(self):
        grafo = grafo_sintetico({"A": (0, 0), "D": (10, 0)}, [])
        r = hill_climbing_con_reinicios(grafo, "A", "D", max_reinicios=3, semilla=0)
        self.assertFalse(r.exito)
        self.assertEqual(len(r.intentos), 4)

    def test_eleccion_estocastica_solo_entre_admisibles(self):
        grafo = grafo_sintetico({"A": (0, 0), "B": (-5, 0), "C": (5, 0), "D": (10, 0)},
                                [("A", "B", 5), ("A", "C", 5), ("C", "D", 5)])
        for semilla in range(20):
            r = hill_climbing(grafo, "A", "D", aleatorio=random.Random(semilla))
            self.assertEqual(r.ruta, ["A", "C", "D"])


if __name__ == "__main__":
    unittest.main()
