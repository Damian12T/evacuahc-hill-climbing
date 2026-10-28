"""Pruebas del grafo REAL (datos/campus.json) y de su representación gráfica."""

import sys
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configuracion import (  # noqa: E402
    COLORES, CRITERIO_COSTO_HEURISTICA, CRITERIO_HEURISTICA, HEURISTICA_EUCLIDIANA, HEURISTICA_SALIDA,
    VARIANTE_ESTOCASTICA,
)
from grafo_universidad import (  # noqa: E402
    aplicar_bloqueos, cargar_datos, construir_grafo, existe_camino_transitable,
)
from hill_climbing import buscar, evaluar_destinos  # noqa: E402
from modelos import ESTADO_EXITO, ESTADO_OPTIMO_LOCAL  # noqa: E402
from visualizacion import dibujar  # noqa: E402


class PruebasDatos(unittest.TestCase):
    def setUp(self):
        self.grafo = construir_grafo()

    def test_topologia_del_informe(self):
        self.assertTrue(self.grafo.is_directed())
        self.assertEqual(self.grafo.number_of_nodes(), 9)
        self.assertEqual(self.grafo.number_of_edges(), 8)
        self.assertEqual(sorted(n for n, d in self.grafo.nodes(data=True) if d["tipo"] == "destino"),
                         ["P1", "P2", "P3"])

    def test_longitudes_coinciden_con_recorridos_del_informe(self):
        # Informe, sección 4: recorridos completos desde G y H.
        esperados = {("G", "K", "P2"): 159.8, ("G", "J", "P1"): 229.8, ("G", "L", "P3"): 341.7,
                     ("H", "K", "P2"): 135.8, ("H", "J", "P1"): 205.8, ("H", "L", "P3"): 317.7}
        for (origen, acceso, destino), total in esperados.items():
            ruta = [origen, "S", acceso, destino]
            suma = sum(self.grafo.edges[u, v]["longitud_m"] for u, v in zip(ruta, ruta[1:]))
            self.assertAlmostEqual(suma, total, places=1, msg=ruta)

    def test_calibracion_consistente(self):
        cal = self.grafo.graph["calibracion"]
        self.assertLess(cal.error_rms_m, 2.0)           # P1-P3 encajan con una sola escala
        self.assertLess(abs(cal.rotacion_grados), 3.0)  # la figura tiene el norte arriba
        for n in ("P1", "P2", "P3"):
            self.assertEqual(self.grafo.nodes[n]["posicion"], "documentada")
        for n in ("G", "H", "S", "K", "J", "L"):
            self.assertEqual(self.grafo.nodes[n]["posicion"], "estimada")

    def test_bloqueo_conserva_arista_y_la_marca(self):
        grafo = construir_grafo(bloqueadas=[("J", "P1")])
        self.assertIn(("J", "P1"), grafo.edges)
        self.assertFalse(grafo.edges["J", "P1"]["transitable"])
        self.assertFalse(existe_camino_transitable(grafo, "G", "P1"))
        aplicar_bloqueos(grafo, [])
        self.assertTrue(existe_camino_transitable(grafo, "G", "P1"))

    def test_bloqueo_de_arista_inexistente(self):
        with self.assertRaises(ValueError):
            construir_grafo(bloqueadas=[("G", "P1")])

    def test_arista_con_nodo_inexistente(self):
        datos = cargar_datos()
        datos["aristas"].append({"origen": "S", "destino": "X", "longitud_m": 1})
        with self.assertRaises(ValueError):
            construir_grafo(datos)


class PruebasRutasReales(unittest.TestCase):
    def setUp(self):
        self.grafo = construir_grafo()

    def test_ruta_valida_desde_G(self):
        r = buscar(self.grafo, "G", "P2", heuristica=HEURISTICA_SALIDA, criterio=CRITERIO_COSTO_HEURISTICA)
        self.assertEqual(r.estado, ESTADO_EXITO)
        self.assertEqual(r.ruta, ["G", "S", "K", "P2"])
        self.assertAlmostEqual(r.distancia_total_m, 159.8, places=1)

    def test_ruta_valida_desde_H(self):
        r = buscar(self.grafo, "H", "P2", heuristica=HEURISTICA_SALIDA, criterio=CRITERIO_COSTO_HEURISTICA)
        self.assertEqual(r.estado, ESTADO_EXITO)
        self.assertEqual(r.ruta, ["H", "S", "K", "P2"])
        self.assertAlmostEqual(r.distancia_total_m, 135.8, places=1)

    def test_euclidiana_pura_queda_atrapada_en_H(self):
        # Para salir de H hay que ir a S, que está más lejos de todos los destinos.
        for destino in ("P1", "P2", "P3"):
            r = buscar(self.grafo, "H", destino, heuristica=HEURISTICA_EUCLIDIANA)
            self.assertEqual(r.estado, ESTADO_OPTIMO_LOCAL)
            self.assertTrue(existe_camino_transitable(self.grafo, "H", destino))

    def test_P1_bloqueado_nunca_se_usa(self):
        grafo = construir_grafo(bloqueadas=[("J", "P1")])
        for r in evaluar_destinos(grafo, "G", ["P1", "P2", "P3"], criterio=CRITERIO_HEURISTICA,
                                  variante=VARIANTE_ESTOCASTICA, max_reinicios=10, semilla=0):
            self.assertNotIn(("J", "P1"), set(zip(r.ruta, r.ruta[1:])))
            if r.destino == "P1":
                self.assertFalse(r.exito)


class PruebasRepresentacion(unittest.TestCase):
    def test_ruta_es_secuencia_de_aristas_transitables(self):
        grafo = construir_grafo()
        r = buscar(grafo, "G", "P3", criterio=CRITERIO_HEURISTICA)
        self.assertTrue(r.exito)
        self.assertEqual(r.ruta[0], "G")
        self.assertEqual(r.ruta[-1], "P3")
        for u, v in zip(r.ruta, r.ruta[1:]):
            self.assertTrue(grafo.edges[u, v]["transitable"])
        self.assertEqual(r.visitados, r.ruta)
        self.assertEqual(r.iteraciones, len(r.ruta) - 1)

    def test_figura_resalta_los_tramos_de_la_ruta(self):
        grafo = construir_grafo(bloqueadas=[("J", "P1")])
        r = buscar(grafo, "G", "P2")
        figura, ax = plt.subplots()
        dibujar(ax, grafo, r)
        flechas = [p for p in ax.patches if isinstance(p, FancyArrowPatch)]
        self.assertEqual(len(flechas), grafo.number_of_edges())
        color_ruta = matplotlib.colors.to_rgba(COLORES["ruta"])
        color_bloq = matplotlib.colors.to_rgba(COLORES["arista_bloqueada"])
        self.assertEqual(sum(f.get_edgecolor() == color_ruta for f in flechas), len(r.ruta) - 1)
        self.assertEqual(sum(f.get_edgecolor() == color_bloq for f in flechas), 1)
        # Vista paso a paso de cada iteración sin errores.
        for indice in range(len(r.pasos)):
            dibujar(ax, grafo, r, paso=indice)
        plt.close(figura)


if __name__ == "__main__":
    unittest.main()
