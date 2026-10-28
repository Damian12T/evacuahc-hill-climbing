"""Pruebas de los textos en lenguaje sencillo (datos reales de campus.json)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configuracion import CRITERIO_HEURISTICA  # noqa: E402
from explicacion import explicar_fallo, explicar_paso, indicaciones, resumen, tiempo_a_pie  # noqa: E402
from grafo_universidad import construir_grafo, existe_camino_transitable  # noqa: E402
from hill_climbing import buscar  # noqa: E402


class PruebasExplicacion(unittest.TestCase):
    def setUp(self):
        self.grafo = construir_grafo()

    def test_indicaciones_de_una_ruta_encontrada(self):
        r = buscar(self.grafo, "H", "P2")
        lineas = indicaciones(self.grafo, r)
        self.assertEqual(len(lineas), len(r.ruta) - 1)
        self.assertTrue(lineas[0].startswith("1. Sal del Bloque H"))
        self.assertIn("21 m", lineas[0])
        self.assertIn("punto de encuentro", lineas[-1])
        self.assertIn("136 m", resumen(self.grafo, r, True))

    def test_sin_indicaciones_si_no_llega(self):
        r = buscar(self.grafo, "G", "P1", criterio=CRITERIO_HEURISTICA)
        self.assertFalse(r.exito)
        self.assertEqual(indicaciones(self.grafo, r), [])
        texto = explicar_fallo(self.grafo, r, existe_camino_transitable(self.grafo, "G", "P1"))
        self.assertIn("cima falsa", texto)
        self.assertIn("Acceso al camino de las canchas", texto)

    def test_fallo_sin_camino_posible(self):
        grafo = construir_grafo(bloqueadas=[("J", "P1")])
        r = buscar(grafo, "G", "P1")
        texto = explicar_fallo(grafo, r, existe_camino_transitable(grafo, "G", "P1"))
        self.assertIn("no existe ninguna forma", texto)

    def test_cada_paso_se_explica_con_lo_que_ocurrio(self):
        r = buscar(self.grafo, "H", "P2")
        for indice, paso in enumerate(r.pasos):
            texto = explicar_paso(self.grafo, r, indice)
            self.assertIn(self.grafo.nodes[paso.seleccionado]["nombre"], texto)
        segundo = explicar_paso(self.grafo, r, 1)
        self.assertIn("3 caminos", segundo)
        self.assertIn("lo alejaba del destino", segundo)  # L no mejora h desde S hacia P2

    def test_tiempo_a_pie(self):
        self.assertEqual(tiempo_a_pie(30), "menos de 1 minuto")
        self.assertEqual(tiempo_a_pie(135.8), "unos 2 minutos")


if __name__ == "__main__":
    unittest.main()
