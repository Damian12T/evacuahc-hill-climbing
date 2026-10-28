"""Punto de entrada.

    python main.py               abre la aplicación de escritorio
    python main.py --evidencias  genera figuras y registro JSON en evidencias/ (sin ventana)
    python main.py --autoprueba  abre la ventana, ejecuta una búsqueda, guarda capturas y se cierra
"""

import argparse
import json
from dataclasses import asdict

from configuracion import (
    CRITERIO_COSTO_HEURISTICA, CRITERIO_HEURISTICA, DIRECTORIO_EVIDENCIAS, HEURISTICA_EUCLIDIANA,
    HEURISTICA_SALIDA, TEMA, VARIANTE_ESTOCASTICA, VARIANTE_MAXIMA_PENDIENTE,
)

CASOS_EVIDENCIA = [
    # (archivo, origen, destino, bloqueadas, heurística, criterio, variante)
    ("01_G_P2_exito", "G", "P2", [], HEURISTICA_SALIDA, CRITERIO_COSTO_HEURISTICA, VARIANTE_MAXIMA_PENDIENTE),
    ("02_H_P2_exito", "H", "P2", [], HEURISTICA_SALIDA, CRITERIO_COSTO_HEURISTICA, VARIANTE_MAXIMA_PENDIENTE),
    ("03_G_P3_exito_solo_h", "G", "P3", [], HEURISTICA_SALIDA, CRITERIO_HEURISTICA, VARIANTE_MAXIMA_PENDIENTE),
    ("04_G_P1_optimo_local", "G", "P1", [], HEURISTICA_SALIDA, CRITERIO_HEURISTICA, VARIANTE_MAXIMA_PENDIENTE),
    ("05_H_P2_euclidiana_pura_bloqueo", "H", "P2", [], HEURISTICA_EUCLIDIANA, CRITERIO_COSTO_HEURISTICA,
     VARIANTE_MAXIMA_PENDIENTE),
    ("06_H_P1_estocastico_reinicios", "H", "P1", [], HEURISTICA_SALIDA, CRITERIO_COSTO_HEURISTICA, VARIANTE_ESTOCASTICA),
    ("07_G_P1_acceso_bloqueado", "G", "P1", [("J", "P1")], HEURISTICA_SALIDA, CRITERIO_HEURISTICA,
     VARIANTE_MAXIMA_PENDIENTE),
]


def generar_evidencias():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from grafo_universidad import construir_grafo, existe_camino_transitable
    from hill_climbing import buscar
    from visualizacion import dibujar

    DIRECTORIO_EVIDENCIAS.mkdir(exist_ok=True)
    registro = []
    for archivo, origen, destino, bloqueadas, heuristica, criterio, variante in CASOS_EVIDENCIA:
        grafo = construir_grafo(bloqueadas=bloqueadas)
        r = buscar(grafo, origen, destino, heuristica=heuristica, criterio=criterio, variante=variante)
        figura, ejes = plt.subplots(1, 2, figsize=(16, 9.5), facecolor=TEMA["fondo"])
        dibujar(ejes[0], grafo, r, titulo=f"{origen} → {destino}: "
                                          f"{'ruta encontrada' if r.exito else r.descripcion_estado}")
        dibujar(ejes[1], grafo, r, paso=len(r.pasos) - 1, titulo=f"Última iteración ({len(r.pasos)})")
        figura.suptitle(f"Hill Climbing · heurística {heuristica} · selección {criterio} · variante {variante}"
                        + (f" · bloqueadas {bloqueadas}" if bloqueadas else ""), fontsize=11, color=TEMA["texto"])
        figura.tight_layout()
        figura.savefig(DIRECTORIO_EVIDENCIAS / f"{archivo}.png", dpi=110, facecolor=TEMA["fondo"])
        plt.close(figura)
        entrada = asdict(r)
        entrada["caso"] = archivo
        entrada["bloqueadas"] = bloqueadas
        entrada["existe_camino_en_grafo"] = existe_camino_transitable(grafo, origen, destino)
        registro.append(entrada)
        print(f"{archivo:<36} {r.descripcion_estado:<48} ruta={' -> '.join(r.ruta)}")

    with open(DIRECTORIO_EVIDENCIAS / "registro_busquedas.json", "w", encoding="utf-8") as salida:
        json.dump(registro, salida, ensure_ascii=False, indent=2)
    print(f"Evidencias guardadas en {DIRECTORIO_EVIDENCIAS}")


def autoprueba():
    """Comprueba que la ventana se construye y funciona; guarda capturas en evidencias/."""
    import tkinter as tk

    from interfaz import AplicacionEvacuacion, activar_dpi

    DIRECTORIO_EVIDENCIAS.mkdir(exist_ok=True)
    activar_dpi()
    raiz = tk.Tk()
    app = AplicacionEvacuacion(raiz)

    def capturar(nombre):
        # Al frente durante la captura, para no fotografiar otras ventanas del escritorio.
        raiz.attributes("-topmost", True)
        raiz.lift()
        raiz.focus_force()
        raiz.update()
        raiz.after(300)
        raiz.update()
        app.figura.savefig(DIRECTORIO_EVIDENCIAS / f"{nombre}_figura.png", dpi=120,
                           facecolor=app.figura.get_facecolor())
        try:
            from PIL import ImageGrab
            x, y = raiz.winfo_rootx(), raiz.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + raiz.winfo_width(), y + raiz.winfo_height())).save(
                DIRECTORIO_EVIDENCIAS / f"{nombre}_ventana.png")
        except Exception as error:  # la captura de pantalla es opcional
            print(f"No se pudo capturar la ventana: {error}")
        finally:
            raiz.attributes("-topmost", False)

    def secuencia():
        try:
            # Modo sencillo (el de inicio).
            print("Modo inicial sencillo:", app.var_sencillo.get())
            capturar("interfaz_00_sencillo_inicio")
            app.var_origen.set(app.origenes[1])                     # H
            app.var_destino.set(app.destinos[1])                    # P2
            app.calcular()
            print("Sencillo H -> P2:", app.resultado.descripcion_estado, " -> ".join(app.resultado.ruta))
            capturar("interfaz_01_sencillo_ruta")
            app.mostrar_pasos()
            app._mover_paso(1)
            capturar("interfaz_02_sencillo_como_decide")
            app.simular_recorrido()
            app.detener_animacion()
            app._fijar_tiempo(app._tiempo_total * 0.6)              # instante intermedio fijo
            print(f"Recorrido simulado: {app._tiempo_total:.1f} s en total")
            capturar("interfaz_03_sencillo_recorrido")
            app.var_reintentar.set(False)
            app.var_destino.set(app.destinos[0])                    # P1 sin reintentos: se atasca
            app.calcular()
            print("Sencillo H -> P1 sin reintentos:", app.resultado.descripcion_estado)
            capturar("interfaz_04_sencillo_sin_ruta")
            app.var_reintentar.set(True)

            # Evacuación de todas las personas: búsqueda sencilla y Hill Climbing (80 en G, 60 en H).
            app.evacuar_sencilla()
            print(f"Búsqueda sencilla: T = {app.plan_sencillo.tiempo_total:.1f} s",
                  app.plan_sencillo.personas_por_destino)
            capturar("interfaz_05_personas_sencilla")
            app.evacuar_hill_climbing()
            while app.plan_hc is None:                               # espera al cálculo en segundo plano
                raiz.update()
                raiz.after(50)
            print(f"Hill Climbing: T = {app.plan_hc.tiempo_total:.1f} s", app.plan_hc.personas_por_destino)
            app.simular_recorrido()
            app.detener_animacion()
            app._fijar_tiempo(90.0)
            capturar("interfaz_06_personas_hill_climbing")

            # Modo experto.
            app.var_sencillo.set(False)
            app._cambiar_modo()
            app._cargar_escenario("acceso_P1_bloqueado")
            app.calcular()
            print("Experto H -> P1 con J->P1 bloqueada:", app.resultado.descripcion_estado)
            capturar("interfaz_07_experto_P1_bloqueado")
            app.mostrar_pasos()
            capturar("interfaz_08_experto_pasos")
            app._cargar_escenario("normal")
            app.evacuar_hill_climbing()
            while app.plan_hc is None:
                raiz.update()
                raiz.after(50)
            capturar("interfaz_09_experto_personas")
            app._cargar_escenario("normal")
            app.ver_croquis()
            raiz.update()
            print("Ventana de croquis abierta:", len(raiz.winfo_children()) > 0)
            print("Autoprueba de interfaz completada.")
        finally:
            raiz.destroy()

    raiz.after(1500, secuencia)
    raiz.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Evacuación de los bloques G y H mediante Hill Climbing")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--evidencias", action="store_true", help="genera figuras y registro en evidencias/")
    grupo.add_argument("--autoprueba", action="store_true", help="abre la ventana, la prueba y se cierra")
    argumentos = parser.parse_args()
    if argumentos.evidencias:
        generar_evidencias()
    elif argumentos.autoprueba:
        autoprueba()
    else:
        from interfaz import ejecutar
        ejecutar()


if __name__ == "__main__":
    main()
