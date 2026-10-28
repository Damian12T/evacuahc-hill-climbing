"""Pruebas de la evacuación de todas las personas (búsqueda sencilla y Hill Climbing)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evacuacion_grupal import (  # noqa: E402
    _vecinos, busqueda_sencilla, crear_escenario, es_factible, estado_persona, hill_climbing_grupal, simular,
)
from grafo_universidad import construir_grafo  # noqa: E402


class PruebasEvacuacionGrupal(unittest.TestCase):
    def setUp(self):
        self.grafo = construir_grafo()
        self.escenario = crear_escenario(self.grafo, {"G": 80, "H": 60}, semilla=0)
        self.sencilla = busqueda_sencilla(self.escenario)
        self.hc = hill_climbing_grupal(self.escenario, self.sencilla)

    def test_grupos_de_diez_y_conservacion_de_personas(self):
        self.assertEqual(len(self.escenario.personas), 140)
        self.assertEqual(len(self.escenario.grupos), 14)
        for plan in (self.sencilla, self.hc):
            self.assertEqual(sum(plan.personas_por_destino.values()), 140)
            self.assertEqual(len(plan.recorridos), 140)

    def test_cupos_respetados(self):
        for plan in (self.sencilla, self.hc):
            for destino, personas in plan.personas_por_destino.items():
                self.assertLessEqual(personas, self.escenario.cupos[destino])

    def test_busqueda_sencilla_coincide_con_el_informe(self):
        # Informe, sección 8: caso simultáneo, semilla 0 -> P1 40, P2 100, P3 0 y T = 449,83 s.
        self.assertEqual(self.sencilla.personas_por_destino, {"P1": 40, "P2": 100, "P3": 0})
        self.assertAlmostEqual(self.sencilla.tiempo_total, 449.83, places=1)

    def test_hill_climbing_mejora_y_termina_en_optimo_local(self):
        self.assertLess(self.hc.tiempo_total, self.sencilla.tiempo_total)
        self.assertEqual(self.hc.historial[0], self.sencilla.tiempo_total)
        # Solo acepta mejoras: el historial nunca sube.
        for anterior, siguiente in zip(self.hc.historial, self.hc.historial[1:]):
            self.assertLess(siguiente, anterior)
        self.assertIn("Óptimo local", self.hc.motivo_parada)
        # Ningún vecino factible del resultado final es mejor.
        for asignacion, _ in _vecinos(self.escenario, self.hc.asignacion):
            if es_factible(self.escenario, asignacion):
                self.assertGreaterEqual(simular(self.escenario, asignacion).costo, self.hc.costo)

    def test_intervalo_minimo_de_admision(self):
        # En cada tramo, dos entradas consecutivas están separadas al menos 1/c segundos.
        entradas = {}
        for tramos in self.sencilla.recorridos.values():
            for t in tramos:
                entradas.setdefault((t.u, t.v), []).append(t.entrada)
        for (u, v), lista in entradas.items():
            intervalo = 1 / self.grafo.edges[u, v]["flujo_supuesto"]
            lista.sort()
            for a, b in zip(lista, lista[1:]):
                self.assertGreaterEqual(b - a, intervalo - 1e-9)

    def test_tramo_bloqueado_nunca_se_usa(self):
        grafo = construir_grafo(bloqueadas=[("J", "P1")])
        escenario = crear_escenario(grafo, {"G": 80, "H": 60}, semilla=0)
        plan = hill_climbing_grupal(escenario)
        self.assertEqual(plan.personas_por_destino["P1"], 0)
        for tramos in plan.recorridos.values():
            self.assertNotIn(("J", "P1"), [(t.u, t.v) for t in tramos])

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            crear_escenario(self.grafo, {"G": 0, "H": 0})
        with self.assertRaises(ValueError):
            crear_escenario(self.grafo, {"G": -5, "H": 10})
        with self.assertRaises(ValueError):
            crear_escenario(self.grafo, {"P1": 10})
        demasiadas = crear_escenario(self.grafo, {"G": 300, "H": 100})   # 400 > 340 de cupo total
        with self.assertRaises(ValueError):
            busqueda_sencilla(demasiadas)

    def test_estado_persona_en_el_tiempo(self):
        pid = self.escenario.grupos[0].personas[0]
        self.assertEqual(estado_persona(self.hc, pid, -1, "G")[0], "origen")
        ultimo = self.hc.recorridos[pid][-1]
        self.assertEqual(estado_persona(self.hc, pid, ultimo.salida + 1, "G")[0], "llegó")

    def test_reproducible_con_la_misma_semilla(self):
        otro = crear_escenario(self.grafo, {"G": 80, "H": 60}, semilla=0)
        self.assertEqual(hill_climbing_grupal(otro).asignacion, self.hc.asignacion)


if __name__ == "__main__":
    unittest.main()
