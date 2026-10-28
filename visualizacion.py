"""Dibujo con Matplotlib: mapa base, grafo, ruta, pasos de Hill Climbing y gráficas.

Las coordenadas del dibujo son metros locales (x este, y norte). El mapa base es de
OpenStreetMap con la misma proyección que el grafo. Los destinos usan coordenadas
documentadas; el resto de nodos, posiciones estimadas por calibración. Los tramos del
grafo se dibujan rectos: es un trazado esquemático, no el sendero exacto.
"""

from functools import lru_cache
from typing import List, Optional, Tuple

import matplotlib.image as mpimg
import matplotlib.patheffects as efectos
import networkx as nx
import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Polygon
from mpl_toolkits.axes_grid1.anchored_artists import AnchoredSizeBar

from configuracion import ARCHIVO_OSM, COLOR_DESTINO, COLORES, TEMA
from modelos import VECINO_ADMISIBLE, VECINO_NO_MEJORA, VECINO_VISITADO, ResultadoBusqueda

RADIO_NODO = 230  # tamaño (puntos²) de los círculos de nodo
CONTORNO = [efectos.withStroke(linewidth=3, foreground=COLORES["fondo"])]
CAJA_ETIQUETA = dict(boxstyle="round,pad=0.3", fc=COLORES["etiqueta_fondo"], ec="none", alpha=0.85)


def metros(valor: float) -> str:
    return f"{valor:,.1f}".replace(",", " ").replace(".", ",") + " m"


def color_nodo(grafo, nodo: str) -> str:
    tipo = grafo.nodes[nodo]["tipo"]
    if tipo == "destino":
        return COLOR_DESTINO.get(nodo, COLORES["destino"])
    return COLORES.get(tipo, COLORES["acceso"])


def _posiciones(grafo):
    return {n: (d["x"], d["y"]) for n, d in grafo.nodes(data=True)}


@lru_cache(maxsize=4)
def _mapa_base(lat0: float, lon0: float):
    from mapa_osm import cargar
    return cargar(lat0, lon0, ARCHIVO_OSM)


def _dibujar_mapa(ax, grafo) -> bool:
    calibracion = grafo.graph.get("calibracion")
    elementos = _mapa_base(calibracion.lat0, calibracion.lon0) if calibracion else []
    estilos_area = {
        "verde": (COLORES["verde"], COLORES["verde"], 0),
        "cancha": (COLORES["cancha"], COLORES["cancha"], 0),
        "parqueadero": (COLORES["parqueadero"], COLORES["parqueadero"], 0),
        "edificio": (COLORES["edificio"], COLORES["edificio_borde"], 1),
    }
    # Áreas primero (verdes debajo de edificios) y luego líneas.
    for categoria in ("verde", "parqueadero", "cancha", "edificio"):
        relleno, borde, capa = estilos_area[categoria]
        for e in elementos:
            if e.categoria == categoria and e.cerrado:
                ax.add_patch(Polygon(e.puntos, closed=True, fc=relleno, ec=borde, lw=0.6, zorder=0.2 + capa * 0.1))
    for e in elementos:
        if e.categoria in ("sendero", "via") and not (e.cerrado and e.categoria == "via"):
            xs, ys = zip(*e.puntos)
            if e.categoria == "sendero":
                ax.plot(xs, ys, color=COLORES["sendero"], lw=0.8, ls=(0, (3, 2)), zorder=0.4)
            else:
                ax.plot(xs, ys, color=COLORES["via"], lw=2.2, zorder=0.4, solid_capstyle="round")
    # Rótulos de lugares conocidos dentro del encuadre.
    for e in elementos:
        if e.nombre and e.cerrado and e.categoria in ("edificio", "verde"):
            xs, ys = zip(*e.puntos)
            ax.text(sum(xs) / len(xs), max(ys) - 6, e.nombre, ha="center", va="top", fontsize=7,
                    style="italic", color=COLORES["texto_suave"], alpha=0.75, zorder=0.6, clip_on=True)
    return bool(elementos)


def _dibujar_isolineas(ax, grafo, destino: str) -> None:
    """Curvas de nivel de la distancia en línea recta al destino ("la colina" que escala el algoritmo).

    Cada línea une los puntos a igual distancia del destino (cada 25 m). Hill Climbing solo
    acepta moverse a un nodo situado en una curva más interior que la del nodo actual.
    """
    cx, cy = grafo.nodes[destino]["x"], grafo.nodes[destino]["y"]
    xmin, xmax, ymin, ymax = encuadre(grafo)
    margen = 250
    xs = np.linspace(xmin - margen, xmax + margen, 260)
    ys = np.linspace(ymin - margen, ymax + margen, 260)
    malla_x, malla_y = np.meshgrid(xs, ys)
    distancia = np.hypot(malla_x - cx, malla_y - cy)
    color = COLOR_DESTINO.get(destino, COLORES["destino"])
    # Resplandor de la "cumbre": anillos rellenos que se desvanecen hacia fuera.
    ax.contourf(malla_x, malla_y, distancia, levels=[0, 12, 25, 40], colors=[color], alpha=0.10,
                zorder=0.65, antialiased=True)
    niveles = np.arange(25, 600, 25)
    curvas = ax.contour(malla_x, malla_y, distancia, levels=niveles, colors=COLORES["isolinea"],
                        linewidths=[1.0 if n % 100 == 0 else 0.55 for n in niveles], alpha=0.32, zorder=0.7)
    ax.clabel(curvas, levels=[n for n in niveles if n % 100 == 0], fmt="h=%d m", fontsize=6.5, inline=True,
              colors=COLORES["isolinea"])


def _flecha(ax, p1, p2, color, ancho, estilo="solid", zorder=2, alpha=1.0):
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle="-|>", mutation_scale=13, color=color, linewidth=ancho,
        linestyle=estilo, shrinkA=9, shrinkB=9, zorder=zorder, alpha=alpha, capstyle="round",
    ))


def encuadre(grafo) -> Tuple[float, float, float, float]:
    pos = _posiciones(grafo).values()
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    return min(xs) - 75, max(xs) + 85, min(ys) - 30, max(ys) + 40


def dibujar(ax, grafo: nx.DiGraph, resultado: Optional[ResultadoBusqueda] = None,
            paso: Optional[int] = None, titulo: str = "", sencillo: bool = False, leyenda: bool = True) -> None:
    """Dibuja mapa, grafo y, si se indica, la ruta o el estado tras un paso.

    paso=None muestra el resultado final; paso=k (0..n-1) muestra la iteración k.
    sencillo=True oculta los datos técnicos (isolíneas, h, f, flujos) y muestra la ruta
    numerada con rótulos en lenguaje cotidiano, para quien no conoce el algoritmo.
    """
    ax.clear()
    ax.set_facecolor(COLORES["fondo"])
    pos = _posiciones(grafo)
    hay_mapa = _dibujar_mapa(ax, grafo)
    if not sencillo and resultado is not None and resultado.destino in pos:
        _dibujar_isolineas(ax, grafo, resultado.destino)

    ruta, paso_actual = [], None
    if resultado is not None and resultado.ruta:
        if paso is None:
            ruta = resultado.ruta
        else:
            paso_actual = resultado.pasos[paso]
            ruta = resultado.ruta[: paso + 1]
    tramos_ruta = set(zip(ruta, ruta[1:]))
    # Verde: ruta que llega al destino. Ámbar: recorrido de una búsqueda que se detuvo.
    fallida = resultado is not None and not resultado.exito and paso is None
    color_ruta = COLORES["ruta_fallida"] if fallida else COLORES["ruta"]

    # Resplandor bajo la ruta.
    if len(ruta) > 1:
        xs, ys = zip(*(pos[n] for n in ruta))
        ax.plot(xs, ys, color=color_ruta, lw=14, alpha=0.18, solid_capstyle="round", zorder=1.5)
        ax.plot(xs, ys, color=color_ruta, lw=8, alpha=0.25, solid_capstyle="round", zorder=1.6)
    if fallida and ruta:
        x, y = pos[ruta[-1]]
        ax.scatter([x + 7], [y + 7], marker="X", s=170, c=COLORES["arista_bloqueada"], edgecolors="white",
                   linewidths=1.2, zorder=8)
        ax.text(x + 14, y + 7, "la búsqueda se detuvo aquí" if sencillo else "se detiene aquí", fontsize=7.5,
                fontweight="bold", va="center", zorder=8, color=COLORES["arista_bloqueada"], path_effects=CONTORNO)

    # Aristas: una flecha por arista (transitable, bloqueada o de la ruta).
    for u, v, datos in grafo.edges(data=True):
        p1, p2 = pos[u], pos[v]
        medio = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        if not datos.get("transitable", True):
            _flecha(ax, p1, p2, COLORES["arista_bloqueada"], 2.4, "--", zorder=2)
            ax.text(medio[0] + 5, medio[1], "CERRADO" if sencillo else "BLOQUEADA", color=COLORES["arista_bloqueada"],
                    fontsize=8, fontweight="bold", zorder=6, path_effects=CONTORNO)
            continue
        en_ruta = (u, v) in tramos_ruta
        _flecha(ax, p1, p2, color_ruta if en_ruta else COLORES["arista"],
                3.6 if en_ruta else 1.5, zorder=3 if en_ruta else 2,
                alpha=1.0 if en_ruta else (0.45 if sencillo and ruta else 0.75))
        texto = f"{datos['longitud_m']:.0f} m"
        if datos.get("flujo_supuesto") and not sencillo:
            texto += f" · {datos['flujo_supuesto']:g}/s".replace(".", ",")
        if sencillo and en_ruta and paso is None:
            # Número del tramo, igual que en las indicaciones paso a paso.
            numero = ruta.index(u) + 1
            ax.text(medio[0], medio[1], str(numero), ha="center", va="center", fontsize=8.5, fontweight="bold",
                    color=COLORES["etiqueta_fondo"], zorder=7,
                    bbox=dict(boxstyle="circle,pad=0.3", fc=color_ruta, ec="white", lw=1.2))
            texto = ""
        if not texto:
            continue
        # Rótulo desplazado a la derecha del sentido de la arista para no tapar el trazo.
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        largo = (dx * dx + dy * dy) ** 0.5 or 1.0
        ox, oy = dy / largo * 8, -dx / largo * 8
        ax.text(medio[0] + ox, medio[1] + oy, texto, fontsize=6.6, color=COLORES["texto"], zorder=6,
                ha="left" if ox >= 0 else "right", va="center", bbox=CAJA_ETIQUETA)

    # Halo de nodos visitados.
    if ruta:
        xs, ys = zip(*(pos[n] for n in ruta))
        ax.scatter(xs, ys, s=RADIO_NODO * 3.2, c=COLORES["visitado"], alpha=0.22, zorder=3, linewidths=0)

    # Evaluación de vecinos en la iteración mostrada.
    if paso_actual is not None:
        x, y = pos[paso_actual.nodo_actual]
        ax.scatter([x], [y], s=RADIO_NODO * 4.5, facecolors="none", edgecolors=COLORES["actual"],
                   linewidths=3, zorder=4)
        for c in paso_actual.candidatos:
            cx, cy = pos[c.nodo]
            elegido = c.nodo == paso_actual.seleccionado
            color = (COLORES["ruta"] if elegido else
                     COLORES["candidato"] if c.estado == VECINO_ADMISIBLE else COLORES["descartado"])
            _flecha(ax, (x, y), (cx, cy), color, 3.0 if elegido else 1.8, "solid" if elegido else ":", zorder=4)
            if sencillo:
                rotulo = "✔ va por aquí" if elegido else {
                    VECINO_ADMISIBLE: "acerca, pero es peor", VECINO_NO_MEJORA: "✕ aleja",
                    VECINO_VISITADO: "✕ ya pasó"}[c.estado]
            else:
                simbolo = "✔ ELEGIDO" if elegido else {
                    VECINO_ADMISIBLE: "mejora h", VECINO_NO_MEJORA: "✕ no mejora",
                    VECINO_VISITADO: "✕ visitado"}[c.estado]
                rotulo = f"h = {c.h:.1f}   f = {c.valor:.1f}\n{simbolo}"
            ax.text(cx + 8, cy + 7, rotulo, fontsize=7.3, color=color, fontweight="bold", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.35", fc=COLORES["etiqueta_fondo"], ec=color, lw=1.2, alpha=0.95))

    # Anillos discontinuos que marcan el origen y el destino de la búsqueda.
    if resultado is not None:
        for nodo in (resultado.origen, resultado.destino):
            if nodo in pos:
                ax.scatter(*pos[nodo], s=RADIO_NODO * 5, facecolors="none", edgecolors=color_nodo(grafo, nodo),
                           linewidths=1.8, linestyle="--", zorder=4.5)

    # Nodos: círculo con letra; destinos con su color y rótulo.
    for n, d in grafo.nodes(data=True):
        x, y = pos[n]
        destacado = resultado is not None and n in (resultado.origen, resultado.destino)
        ax.scatter([x], [y], s=RADIO_NODO * (1.35 if d["tipo"] in ("origen", "destino") else 1),
                   c=color_nodo(grafo, n), edgecolors="white", linewidths=2.6 if destacado else 1.6, zorder=5)
        ax.text(x, y, n, ha="center", va="center", color="white", fontsize=7.5 if len(n) > 1 else 8.5,
                fontweight="bold", zorder=6)
        if d["tipo"] == "origen":
            a_la_derecha = d.get("etiqueta") == "derecha"
            ax.text(x + (10 if a_la_derecha else -10), y + 10, d["nombre"], ha="left" if a_la_derecha else "right",
                    fontsize=8.5, fontweight="bold", color="white", zorder=7, path_effects=CONTORNO)
        elif d["tipo"] == "destino":
            rotulo = d["nombre"]
            if d.get("cupo_supuesto") and not sencillo:
                rotulo += f"\ncupo supuesto {d['cupo_supuesto']}"
            ax.text(x, y - 9, rotulo, ha="center", va="top", fontsize=7.3, fontweight="bold", color="white",
                    zorder=6, bbox=CAJA_ETIQUETA)
        elif sencillo:
            ax.text(x + 9, y, d["nombre"], ha="left", va="center", fontsize=6.6, style="italic",
                    color=COLORES["texto_suave"], zorder=6, path_effects=CONTORNO)

    # Marcadores cotidianos para quien no conoce el algoritmo.
    if sencillo and resultado is not None and paso is None:  # en la vista paso a paso estorbarían
        for nodo, texto, color, desplazamiento in (
                (resultado.origen, "ESTÁS AQUÍ", COLORES["origen"], (40, 30)),
                (resultado.destino, "⚑ PUNTO DE ENCUENTRO", color_nodo(grafo, resultado.destino), (70, -30))):
            if nodo in pos:
                ax.annotate(texto, pos[nodo], xytext=desplazamiento, textcoords="offset points", ha="center",
                            va="center",
                            fontsize=8, fontweight="bold", color=COLORES["etiqueta_fondo"], zorder=9,
                            bbox=dict(boxstyle="round,pad=0.35", fc=color, ec="white", lw=1),
                            arrowprops=dict(arrowstyle="-", color=color, lw=1.5))

    # Encuadre: se garantiza ver todo el grafo y se amplía el mapa hasta llenar el panel.
    # Se fija el área de datos (no los límites) y Matplotlib la amplía al dibujar
    # según la forma del panel, también al redimensionar la ventana.
    xmin, xmax, ymin, ymax = encuadre(grafo)
    ax.dataLim.set_points(np.array([[xmin, ymin], [xmax, ymax]]))
    ax.set_autoscale_on(True)
    ax.margins(0)
    ax.set_aspect("equal", adjustable="datalim")
    ax.autoscale_view()
    ax.set_xticks([])
    ax.set_yticks([])
    for borde in ax.spines.values():
        borde.set_color(TEMA["borde"])
    _escala_y_norte(ax)
    if not leyenda:
        pass
    elif sencillo:
        _leyenda_sencilla(ax)
    else:
        _leyenda(ax, paso_actual is not None)
    fuente = ("Mapa: © colaboradores de OpenStreetMap (ODbL) · tramos esquemáticos · flujos y cupos supuestos"
              if hay_mapa else "Sin mapa base (falta datos/campus_osm.json) · tramos esquemáticos")
    ax.text(0.01, 0.008, fuente, transform=ax.transAxes, ha="left", va="bottom", fontsize=6.3,
            color=COLORES["texto_suave"], zorder=9, path_effects=CONTORNO)
    ax.set_title(titulo or "Grafo de evacuación · bloques G y H", fontsize=11, color=COLORES["texto"],
                 fontweight="bold", pad=8)


def _escala_y_norte(ax):
    # Anclados a las esquinas del panel: siguen en su sitio aunque cambie el tamaño de la ventana.
    barra = AnchoredSizeBar(ax.transData, 50, "50 m (aprox.)", loc="lower right", pad=0.6, borderpad=0.8,
                            sep=3, color="white", frameon=False, size_vertical=1.2,
                            fontproperties=FontProperties(size=7))
    barra.set_zorder(9)
    ax.add_artist(barra)
    ax.annotate("", xy=(0.03, 0.97), xytext=(0.03, 0.91), xycoords="axes fraction", zorder=9,
                arrowprops=dict(arrowstyle="-|>", color="white", lw=1.5))
    ax.text(0.03, 0.975, "N", transform=ax.transAxes, ha="center", va="bottom", fontsize=9,
            fontweight="bold", color="white", zorder=9)


def _leyenda(ax, modo_paso: bool):
    elementos = [
        Line2D([], [], marker="o", ls="", mfc=COLORES["origen"], mec="white", ms=8, label="Bloque de origen"),
        Line2D([], [], marker="o", ls="", mfc=COLORES["acceso"], mec="white", ms=8, label="Salida S / acceso"),
    ] + [
        Line2D([], [], marker="o", ls="", mfc=color, mec="white", ms=8, label=f"{n} punto de encuentro")
        for n, color in COLOR_DESTINO.items()
    ] + [
        Line2D([], [], color=COLORES["ruta"], lw=3.5, label="Ruta de Hill Climbing"),
        Line2D([], [], color=COLORES["ruta_fallida"], lw=3.5, label="Recorrido sin llegar"),
        Line2D([], [], color=COLORES["arista_bloqueada"], lw=2, ls="--", label="Conexión bloqueada"),
        Line2D([], [], marker="o", ls="", color=COLORES["visitado"], alpha=0.45, ms=11, label="Nodo visitado"),
        Line2D([], [], color=COLORES["isolinea"], lw=1, alpha=0.6, label="Isolínea de h (cada 25 m)"),
    ]
    if modo_paso:
        elementos += [
            Line2D([], [], marker="o", ls="", mfc="none", mec=COLORES["actual"], mew=2.5, ms=12, label="Nodo actual"),
            Line2D([], [], color=COLORES["candidato"], lw=2, ls=":", label="Vecino que mejora h"),
            Line2D([], [], color=COLORES["descartado"], lw=2, ls=":", label="Vecino descartado"),
        ]
    leyenda = ax.legend(handles=elementos, loc="upper left", bbox_to_anchor=(0.06, 0.995), fontsize=6.8, ncol=1,
                        framealpha=0.88, title="Simbología", title_fontsize=7.5,
                        facecolor=COLORES["etiqueta_fondo"], edgecolor=TEMA["borde"], labelcolor=COLORES["texto"],
                        borderpad=0.6, handletextpad=0.5, columnspacing=1.0)
    leyenda.get_title().set_color(COLORES["texto_suave"])
    leyenda.set_zorder(10)


def _leyenda_sencilla(ax):
    elementos = [
        Line2D([], [], marker="o", ls="", mfc=COLORES["origen"], mec="white", ms=9, label="Dónde estás"),
        Line2D([], [], marker="o", ls="", mfc=COLORES["destino"], mec="white", ms=9, label="Punto de encuentro"),
        Line2D([], [], color=COLORES["ruta"], lw=4, label="Camino encontrado"),
        Line2D([], [], color=COLORES["ruta_fallida"], lw=4, label="Hasta dónde llegó (sin éxito)"),
        Line2D([], [], color=COLORES["arista"], lw=1.5, alpha=0.6, label="Otros caminos"),
        Line2D([], [], color=COLORES["arista_bloqueada"], lw=2, ls="--", label="Camino cerrado"),
    ]
    leyenda = ax.legend(handles=elementos, loc="upper left", bbox_to_anchor=(0.06, 0.995), fontsize=7.5,
                        framealpha=0.9, facecolor=COLORES["etiqueta_fondo"], edgecolor=TEMA["borde"],
                        labelcolor=COLORES["texto"], borderpad=0.7, handletextpad=0.6)
    leyenda.set_zorder(10)


# ---------------------------------------------------------------- evacuación de varias personas
def dibujar_plan(ax, grafo, escenario, plan, titulo: str, sencillo: bool = False) -> None:
    """Mapa con el reparto de un plan: grosor de cada tramo según las personas que lo usan."""
    dibujar(ax, grafo, None, titulo=titulo, sencillo=sencillo, leyenda=False)
    pos = _posiciones(grafo)
    elementos = [Line2D([], [], marker="o", ls="", mfc=color, mec="white", ms=7,
                        label=f"Va a {grafo.nodes[d]['nombre']}") for d, color in COLOR_DESTINO.items() if d in grafo]
    elementos += [Line2D([], [], color="white", lw=6, alpha=0.45, label="Camino usado (más grueso = más gente)"),
                  Line2D([], [], color=COLORES["arista_bloqueada"], lw=2, ls="--", label="Camino cerrado")]
    caja = ax.legend(handles=elementos, loc="lower left", bbox_to_anchor=(0.005, 0.04), fontsize=7.3,
                     framealpha=0.9, facecolor=COLORES["etiqueta_fondo"], edgecolor=TEMA["borde"],
                     labelcolor=COLORES["texto"], title="Cada punto es una persona", title_fontsize=7.5)
    caja.get_title().set_color(COLORES["texto_suave"])
    caja.set_zorder(10)
    flujo: dict = {}
    destinos_tramo: dict = {}
    for grupo, destino in zip(escenario.grupos, plan.asignacion):
        ruta = escenario.rutas[(grupo.origen, destino)]
        for u, v in zip(ruta, ruta[1:]):
            flujo[(u, v)] = flujo.get((u, v), 0) + grupo.tamano
            destinos_tramo.setdefault((u, v), set()).add(destino)
    for (u, v), personas in flujo.items():
        destinos = destinos_tramo[(u, v)]
        color = COLOR_DESTINO.get(next(iter(destinos)), COLORES["ruta"]) if len(destinos) == 1 else "#ffffff"
        (x1, y1), (x2, y2) = pos[u], pos[v]
        ax.plot([x1, x2], [y1, y2], color=color, lw=2 + personas / 9, alpha=0.45, solid_capstyle="round",
                zorder=1.7)
    for destino, personas in plan.personas_por_destino.items():
        x, y = pos[destino]
        cupo = escenario.cupos.get(destino, 0)
        color = COLOR_DESTINO.get(destino, COLORES["destino"])
        ax.text(x + 14, y + 14, f"{personas} personas\ncupo {cupo}", fontsize=8, fontweight="bold", zorder=9,
                color=COLORES["etiqueta_fondo"] if personas else COLORES["texto_suave"], va="bottom",
                bbox=dict(boxstyle="round,pad=0.35", fc=color if personas else COLORES["etiqueta_fondo"],
                          ec=color, lw=1.2, alpha=0.95))
    for bloque in sorted({g.origen for g in escenario.grupos}):
        total = sum(g.tamano for g in escenario.grupos if g.origen == bloque)
        x, y = pos[bloque]
        a_la_derecha = grafo.nodes[bloque].get("etiqueta") == "derecha"
        ax.text(x + (10 if a_la_derecha else -10), y - 4, f"{total} personas", ha="left" if a_la_derecha else "right",
                va="top", fontsize=7.5, fontweight="bold",
                zorder=9, color=COLORES["etiqueta_fondo"],
                bbox=dict(boxstyle="round,pad=0.25", fc=COLORES["origen"], ec="white", lw=0.8))


def _espiral(centro, k: int, paso: float = 2.1):
    """Posición k-ésima de un racimo compacto (espiral de ángulo áureo) alrededor de un punto."""
    radio = paso * np.sqrt(k + 0.5)
    angulo = k * 2.399963
    return centro[0] + radio * np.cos(angulo), centro[1] + radio * np.sin(angulo)


def posiciones_personas(grafo, escenario, plan, t: float):
    """Coordenadas y colores de cada persona en el instante t, y un resumen de la situación.

    Las personas en cola o ya llegadas se agrupan en racimos junto al nodo correspondiente.
    """
    from evacuacion_grupal import estado_persona

    pos = _posiciones(grafo)
    destino_de = {}
    for grupo, destino in zip(escenario.grupos, plan.asignacion):
        for pid in grupo.personas:
            destino_de[pid] = destino
    racimos: dict = {}
    coordenadas, colores = [], []
    resumen = {"llegaron": 0, "en_cola": 0, "colas": {}}
    for persona in escenario.personas:
        situacion, lugar, fraccion = estado_persona(plan, persona.id, t, persona.origen)
        if situacion == "tramo":
            u, v = lugar.split(">")
            x = pos[u][0] + (pos[v][0] - pos[u][0]) * fraccion
            y = pos[u][1] + (pos[v][1] - pos[u][1]) * fraccion
        else:
            k = racimos.get((situacion, lugar), 0)
            racimos[(situacion, lugar)] = k + 1
            x, y = _espiral(pos[lugar], k)
            if situacion == "llegó":
                resumen["llegaron"] += 1
            elif situacion == "cola":
                resumen["en_cola"] += 1
                resumen["colas"][lugar] = resumen["colas"].get(lugar, 0) + 1
        coordenadas.append((x, y))
        colores.append(COLOR_DESTINO.get(destino_de[persona.id], COLORES["ruta"]))
    return np.array(coordenadas), colores, resumen


def dibujar_evolucion_grupal(ax, plan_sencillo, plan_hc) -> None:
    """Cómo baja el tiempo total en cada iteración de Hill Climbing."""
    ax.clear()
    _estilo_grafica(ax, "Hill Climbing: tiempo hasta la última llegada [s]")
    if plan_hc is None:
        ax.text(0.5, 0.5, "Pulse «Hill Climbing» para ver cómo mejora", transform=ax.transAxes,
                ha="center", va="center", fontsize=8.5, color=COLORES["texto_suave"])
        ax.set_xticks([])
        ax.set_yticks([])
        return
    xs = list(range(len(plan_hc.historial)))
    ax.fill_between(xs, plan_hc.historial, min(plan_hc.historial) * 0.9, color=COLORES["ruta"], alpha=0.15)
    ax.plot(xs, plan_hc.historial, color=COLORES["ruta"], lw=2.4, marker="o", ms=5, zorder=4)
    ax.annotate(f"{plan_hc.historial[0]:.0f} s\n(búsqueda sencilla)", (0, plan_hc.historial[0]), xytext=(8, -4),
                textcoords="offset points", fontsize=7.3, color=COLORES["texto"], va="top")
    ax.annotate(f"{plan_hc.historial[-1]:.0f} s\n(óptimo local)", (xs[-1], plan_hc.historial[-1]),
                xytext=(-6, 10), textcoords="offset points", ha="right", fontsize=7.3, fontweight="bold",
                color=COLORES["ruta"])
    ax.set_xlabel("Iteración (cada una aplica la mejor mejora)", fontsize=7.5, color=COLORES["texto_suave"])
    ax.set_xticks(xs if len(xs) <= 20 else xs[::max(1, len(xs) // 10)])
    ax.set_ylim(min(plan_hc.historial) * 0.9, max(plan_hc.historial) * 1.08)


def dibujar_reparto(ax, grafo, escenario, plan_sencillo, plan_hc) -> None:
    """Personas por punto de encuentro con cada búsqueda frente al cupo supuesto."""
    ax.clear()
    _estilo_grafica(ax, "Personas por punto  ·  línea = cupo supuesto")
    if plan_sencillo is None:
        ax.text(0.5, 0.5, "Pulse «Búsqueda sencilla» o «Hill Climbing»", transform=ax.transAxes,
                ha="center", va="center", fontsize=8.5, color=COLORES["texto_suave"])
        ax.set_xticks([])
        ax.set_yticks([])
        return
    destinos = sorted(escenario.cupos)
    ancho = 0.38
    for i, destino in enumerate(destinos):
        color = COLOR_DESTINO.get(destino, COLORES["destino"])
        valor = plan_sencillo.personas_por_destino.get(destino, 0)
        ax.bar(i - ancho / 2, valor, ancho, color="none", edgecolor=color, hatch="///", lw=1.2, zorder=3)
        ax.text(i - ancho / 2, valor + 2, str(valor), ha="center", fontsize=7.5, color=COLORES["texto_suave"])
        if plan_hc is not None:
            valor = plan_hc.personas_por_destino.get(destino, 0)
            ax.bar(i + ancho / 2, valor, ancho, color=color, zorder=3)
            ax.text(i + ancho / 2, valor + 2, str(valor), ha="center", fontsize=7.5, fontweight="bold",
                    color=COLORES["texto"])
        ax.hlines(escenario.cupos[destino], i - 0.45, i + 0.45, colors=COLORES["texto_suave"], linestyles="--",
                  lw=1, zorder=4)
    ax.set_xticks(range(len(destinos)))
    ax.set_xticklabels([f"{d} {grafo.nodes[d]['nombre']}" for d in destinos], fontsize=7.2)
    ax.set_ylim(0, max(escenario.cupos.values()) * 1.2)
    elementos = [Line2D([], [], color=COLORES["texto_suave"], lw=6, alpha=0.5, label="Búsqueda sencilla (rayado)"),
                 Line2D([], [], color=COLORES["ruta"], lw=6, label="Hill Climbing (relleno)")]
    ax.legend(handles=elementos, fontsize=6.5, loc="upper left", facecolor=TEMA["tarjeta"], edgecolor=TEMA["borde"],
              labelcolor=COLORES["texto"])


# ---------------------------------------------------------------- recorrido animado
def longitudes_tramos(grafo, ruta: List[str]) -> List[float]:
    return [grafo.edges[u, v]["longitud_m"] for u, v in zip(ruta, ruta[1:])]


def posicion_en_ruta(grafo, ruta: List[str], recorrido_m: float) -> Tuple[float, float]:
    """Punto del dibujo tras recorrer `recorrido_m` metros (longitudes medidas) a lo largo de la ruta.

    Cada tramo se dibuja recto, así que la posición dentro del tramo es proporcional
    a la fracción de su longitud medida que ya se recorrió.
    """
    pos = _posiciones(grafo)
    if len(ruta) == 1:
        return pos[ruta[0]]
    restante = max(0.0, recorrido_m)
    for (u, v), longitud in zip(zip(ruta, ruta[1:]), longitudes_tramos(grafo, ruta)):
        if restante <= longitud:
            fraccion = restante / longitud if longitud else 1.0
            return (pos[u][0] + (pos[v][0] - pos[u][0]) * fraccion,
                    pos[u][1] + (pos[v][1] - pos[u][1]) * fraccion)
        restante -= longitud
    return pos[ruta[-1]]


def crear_persona(ax, color: str):
    """Marcador del "escalador" que evacúa (triángulo; se actualiza con set_offsets)."""
    halo = ax.scatter([], [], s=520, c=color, alpha=0.22, linewidths=0, zorder=11)
    punto = ax.scatter([], [], s=150, marker="^", c=color, edgecolors="white", linewidths=1.8, zorder=12)
    return halo, punto


def crear_reloj(ax):
    return ax.text(0.985, 0.985, "", transform=ax.transAxes, ha="right", va="top", family="monospace",
                   fontsize=12, fontweight="bold", color="white", zorder=12,
                   bbox=dict(boxstyle="round,pad=0.4", fc=COLORES["etiqueta_fondo"], ec=TEMA["borde"], alpha=0.95))


# ---------------------------------------------------------------- gráficas del panel
def _estilo_grafica(ax, titulo: str):
    ax.set_facecolor(TEMA["tarjeta"])
    ax.set_title(titulo, fontsize=9, color=COLORES["texto"], loc="left", pad=6)
    ax.tick_params(colors=COLORES["texto_suave"], labelsize=7.5)
    for borde in ax.spines.values():
        borde.set_color(TEMA["borde"])
    ax.grid(color=TEMA["borde"], lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def dibujar_perfil(ax, resultado: Optional[ResultadoBusqueda], paso: Optional[int] = None) -> None:
    """Perfil de escalada: altura ganada = h(origen) − h(n) en cada iteración.

    La cumbre (altura h(origen)) es el destino. Un óptimo local aparece como una "cima falsa":
    el perfil se detiene por debajo de la cumbre porque ningún vecino sube más.
    """
    ax.clear()
    _estilo_grafica(ax, "Perfil de escalada  ·  h(origen) − h(n)  [m]")
    if resultado is None or not resultado.pasos:
        ax.text(0.5, 0.5, "Calcule una ruta para ver el perfil de escalada", transform=ax.transAxes,
                ha="center", va="center", fontsize=8.5, color=COLORES["texto_suave"])
        ax.set_xticks([])
        ax.set_yticks([])
        return
    h0 = resultado.pasos[0].h_actual
    alturas = [h0 - p.h_actual for p in resultado.pasos]
    if resultado.exito:
        alturas.append(h0)
    xs = list(range(len(alturas)))
    ultimo = len(resultado.pasos) - 1 if paso is None else paso
    visibles = min(len(alturas), ultimo + 2)
    color_cima = COLOR_DESTINO.get(resultado.destino, COLORES["destino"])

    # Cumbre (meta) como línea de referencia.
    ax.axhline(h0, color=color_cima, lw=1.2, ls="--", alpha=0.8, zorder=2)
    ax.text(0.01, h0, f"  cumbre = {resultado.destino} (h = 0)", transform=ax.get_yaxis_transform(),
            va="bottom", fontsize=7, fontweight="bold", color=color_cima)

    # Silueta de la montaña: tramo ya escalado más intenso que el pendiente.
    color_perfil = COLORES["ruta"] if resultado.exito else COLORES["ruta_fallida"]
    ax.fill_between(xs, alturas, min(0, min(alturas)) - 5, color=color_perfil, alpha=0.08, zorder=1)
    ax.fill_between(xs[:visibles], alturas[:visibles], min(0, min(alturas)) - 5, color=color_perfil,
                    alpha=0.22, zorder=1.5)
    ax.plot(xs[:visibles], alturas[:visibles], color=color_perfil, lw=2.4, zorder=4, solid_joinstyle="round")
    for i, nodo in enumerate(resultado.ruta[:visibles]):
        ax.scatter([i], [alturas[i]], s=46, c=color_perfil, edgecolors="white", linewidths=1, zorder=5)
        ax.annotate(nodo, (i, alturas[i]), xytext=(0, 8), textcoords="offset points", ha="center",
                    fontsize=7.5, fontweight="bold", color=COLORES["texto"], path_effects=CONTORNO)

    # Vecinos evaluados en cada iteración: altura que habrían dado.
    for i, p in enumerate(resultado.pasos[: ultimo + 1]):
        for c in p.candidatos:
            if c.nodo == p.seleccionado:
                continue
            mejora = c.estado == VECINO_ADMISIBLE
            color = COLORES["candidato"] if mejora else COLORES["descartado"]
            ax.scatter([i + 1], [h0 - c.h], marker="o" if mejora else "x", s=24, c=color, zorder=3)
            ax.annotate(c.nodo, (i + 1, h0 - c.h), xytext=(5, 0), textcoords="offset points", fontsize=6.5,
                        va="center", color=color)

    # Escalador en la posición actual y desenlace.
    ax.scatter([visibles - 1], [alturas[visibles - 1]], marker="^", s=120, c=color_cima, edgecolors="white",
               linewidths=1.3, zorder=6)
    if paso is None:
        x_fin, y_fin = len(alturas) - 1, alturas[-1]
        if resultado.exito:
            texto, color = "⚑ cumbre alcanzada", COLORES["ruta"]
        elif resultado.estado == "optimo_local":
            texto, color = "cima falsa (óptimo local)", COLORES["arista_bloqueada"]
        else:
            texto, color = "callejón sin salida", COLORES["arista_bloqueada"]
        ax.annotate(texto, (x_fin, y_fin), xytext=(-6, -16), textcoords="offset points", ha="right",
                    fontsize=7.5, fontweight="bold", color=color, path_effects=CONTORNO)

    ax.set_xlabel("Iteración", fontsize=7.5, color=COLORES["texto_suave"])
    ax.set_xticks(range(len(alturas) + 1))
    ax.set_xlim(-0.4, len(alturas) + 0.3)
    todas = alturas + [h0 - c.h for p in resultado.pasos for c in p.candidatos]
    ax.set_ylim(min(0, min(todas)) - 8, max(h0, max(todas)) * 1.15 + 5)


def dibujar_comparacion(ax, grafo, resultados: List[ResultadoBusqueda]) -> None:
    """Metros recorridos hacia cada destino con la misma configuración (no indica seguridad)."""
    ax.clear()
    _estilo_grafica(ax, "Metros escalados hacia cada cumbre  ·  rayado = no llegó")
    if not resultados:
        ax.text(0.5, 0.5, "Calcule una ruta para comparar los puntos de encuentro", transform=ax.transAxes,
                ha="center", va="center", fontsize=8.5, color=COLORES["texto_suave"])
        ax.set_xticks([])
        ax.set_yticks([])
        return
    nombres, alturas = [], []
    for i, r in enumerate(resultados):
        recorrido = sum(longitudes_tramos(grafo, r.ruta)) if len(r.ruta) > 1 else 0.0
        color = COLOR_DESTINO.get(r.destino, COLORES["destino"])
        if r.exito:
            ax.bar(i, recorrido, color=color, width=0.6, zorder=3)
            etiqueta = f"✔ {recorrido:.1f} m".replace(".", ",")
        else:
            ax.bar(i, recorrido, color="none", edgecolor=color, hatch="///", width=0.6, lw=1.4, zorder=3)
            etiqueta = f"✖ se detuvo en {r.nodo_final}"
        ax.text(i, recorrido + 6, etiqueta, ha="center", fontsize=7.3, fontweight="bold",
                color=COLORES["ruta"] if r.exito else COLORES["arista_bloqueada"])
        nombres.append(f"{r.destino} {grafo.nodes[r.destino]['nombre']}" if r.destino in grafo else r.destino)
        alturas.append(recorrido)
    ax.set_xticks(range(len(resultados)))
    ax.set_xticklabels(nombres, fontsize=7.2)
    ax.set_ylim(0, max(alturas + [50]) * 1.3)


def dibujar_imagen(ax, ruta_imagen, titulo: str, nota: str) -> None:
    """Muestra una imagen de referencia sin deformarla (relación de aspecto original)."""
    ax.clear()
    ax.imshow(mpimg.imread(str(ruta_imagen)))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(titulo, fontsize=11, color=COLORES["texto"])
    ax.text(0.5, -0.03, nota, transform=ax.transAxes, ha="center", va="top", fontsize=8, wrap=True,
            color=COLORES["texto_suave"])
