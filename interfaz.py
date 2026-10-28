"""Interfaz de escritorio (Tkinter, tema oscuro) con figuras de Matplotlib integradas."""

import textwrap
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from configuracion import (
    ADVERTENCIA_SEGURIDAD, COLOR_DESTINO, COLORES, CRITERIO_COSTO_HEURISTICA, VARIANTE_ESTOCASTICA, DIRECTORIO_DATOS, DIRECTORIO_EVIDENCIAS,
    HEURISTICA_SALIDA, IMAGEN_CROQUIS, IMAGEN_MAPA_HISTORICO, LEMA_APP, NOMBRE_APP, NOMBRES_CRITERIO,
    NOMBRES_HEURISTICA,
    NOMBRES_VARIANTE, REINICIOS_POR_DEFECTO, SEMILLA_POR_DEFECTO, TEMA, VARIANTE_MAXIMA_PENDIENTE,
    VELOCIDAD_MARCHA_MS,
)
from grafo_universidad import (
    aplicar_bloqueos, cargar_datos, construir_grafo, escenarios, etiqueta, existe_camino_transitable,
    nodos_por_tipo,
)
from evacuacion_grupal import busqueda_sencilla, crear_escenario, hill_climbing_grupal, simular
from explicacion import QUE_ES_HILL_CLIMBING, explicar_fallo, explicar_paso, indicaciones, resumen
from hill_climbing import buscar, evaluar_destinos
from visualizacion import (
    crear_persona, crear_reloj, dibujar, dibujar_comparacion, dibujar_evolucion_grupal, dibujar_imagen,
    dibujar_perfil, dibujar_plan, dibujar_reparto, longitudes_tramos, metros, posicion_en_ruta,
    posiciones_personas,
)

INTERVALO_PASO_MS = 1100   # pausa entre iteraciones al animar la búsqueda
INTERVALO_CUADRO_MS = 50   # refresco de la animación del recorrido


def _clave_por_nombre(diccionario: dict, nombre: str) -> str:
    return next(clave for clave, valor in diccionario.items() if valor == nombre)


def _numero(valor: float, decimales: int = 1) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


class AplicacionEvacuacion:
    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.datos = cargar_datos()
        self.grafo = construir_grafo(self.datos)
        self.escenarios = escenarios(self.datos)
        self.resultado = None
        self.comparacion = []
        self.paso = None            # None = vista del resultado final
        self._tarea = None          # identificador de raiz.after de la animación activa
        self._persona = None        # artistas de la persona animada
        self._reloj = None
        self._tiempo = 0.0
        self._tiempo_total = 0.0
        self._sincronizando_barra = False
        self.var_sencillo = tk.BooleanVar(value=True)  # la aplicación arranca en modo sencillo
        # Evacuación de todas las personas (búsqueda sencilla frente a Hill Climbing).
        self.vista = "ruta"          # "ruta" (una persona) o "personas" (todos los grupos)
        self.escenario_grupal = None
        self.plan_sencillo = None
        self.plan_hc = None
        self.var_plan = tk.StringVar(value="hc")
        self.iteracion_grupal = None  # iteración de Hill Climbing mostrada al animar el reparto
        self._planes_intermedios = {}
        self._multitud = None
        self._info_multitud = None

        raiz.title(f"{NOMBRE_APP} · Evacuación de los bloques G y H con Hill Climbing")
        raiz.geometry("1500x920")
        raiz.minsize(1200, 760)
        raiz.configure(bg=TEMA["fondo"])
        try:
            raiz.state("zoomed")  # maximizada en Windows
        except tk.TclError:
            pass
        self._configurar_estilo()

        self._crear_cabecera()
        cuerpo = ttk.Frame(raiz, padding=(10, 8, 10, 10))
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        self._crear_panel_configuracion(cuerpo)
        self._crear_panel_mapa(cuerpo)
        self._crear_panel_derecho(cuerpo)
        self._mostrar_datos_modelo()
        self._cambiar_modo()
        self.reiniciar()

    # ------------------------------------------------------------------ estilo
    def _configurar_estilo(self):
        t = TEMA
        estilo = ttk.Style(self.raiz)
        estilo.theme_use("clam")
        estilo.configure(".", background=t["fondo"], foreground=t["texto"], fieldbackground=t["control"],
                         bordercolor=t["borde"], lightcolor=t["borde"], darkcolor=t["borde"],
                         troughcolor=t["control"], focuscolor=t["borde"], font=("Segoe UI", 9))
        estilo.configure("TFrame", background=t["fondo"])
        estilo.configure("Panel.TFrame", background=t["panel"])
        estilo.configure("TLabel", background=t["panel"], foreground=t["texto"])
        estilo.configure("Suave.TLabel", background=t["panel"], foreground=t["texto_suave"], font=("Segoe UI", 8))
        estilo.configure("TLabelframe", background=t["panel"], bordercolor=t["borde"], relief="solid")
        estilo.configure("TLabelframe.Label", background=t["panel"], foreground=t["texto_suave"],
                         font=("Segoe UI", 8, "bold"))
        estilo.configure("TButton", background=t["control"], foreground=t["texto"], borderwidth=0,
                         padding=(8, 5), font=("Segoe UI", 9, "bold"))
        estilo.map("TButton", background=[("active", t["control_activo"]), ("disabled", t["panel"])],
                   foreground=[("disabled", t["texto_suave"])])
        estilo.configure("Acento.TButton", background=t["acento"], foreground="white", font=("Segoe UI", 10, "bold"),
                         padding=(8, 8))
        estilo.map("Acento.TButton", background=[("active", t["acento_activo"])])
        estilo.configure("Cumbre.TButton", background=t["acento2"], foreground=t["fondo"],
                         font=("Segoe UI", 9, "bold"), padding=(8, 5))
        estilo.map("Cumbre.TButton", background=[("active", "#ffc66e"), ("disabled", t["panel"])])
        estilo.configure("Animar.TButton", background="#3a2f5e", foreground=t["acento2"])
        estilo.map("Animar.TButton", background=[("active", "#4a3d78")])
        estilo.configure("TCombobox", fieldbackground=t["control"], background=t["control"], foreground=t["texto"],
                         arrowcolor=t["texto"], padding=4)
        estilo.map("TCombobox", fieldbackground=[("readonly", t["control"])], foreground=[("readonly", t["texto"])],
                   selectbackground=[("readonly", t["control"])], selectforeground=[("readonly", t["texto"])])
        self.raiz.option_add("*TCombobox*Listbox.background", t["control"])
        self.raiz.option_add("*TCombobox*Listbox.foreground", t["texto"])
        self.raiz.option_add("*TCombobox*Listbox.selectBackground", t["acento"])
        self.raiz.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))
        estilo.configure("TSpinbox", fieldbackground=t["control"], foreground=t["texto"], arrowcolor=t["texto"],
                         background=t["control"])
        estilo.configure("TCheckbutton", background=t["panel"], foreground=t["texto"],
                         indicatorbackground=t["control"], indicatorforeground=t["ok"])
        estilo.map("TCheckbutton", background=[("active", t["panel"])],
                   indicatorbackground=[("selected", t["acento"])], indicatorforeground=[("selected", "white")])
        estilo.configure("TNotebook", background=t["panel"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        estilo.configure("TNotebook.Tab", background=t["control"], foreground=t["texto_suave"], padding=(12, 5),
                         borderwidth=0)
        estilo.map("TNotebook.Tab", background=[("selected", t["tarjeta"])], foreground=[("selected", t["texto"])])
        estilo.configure("Treeview", background=t["tarjeta"], fieldbackground=t["tarjeta"], foreground=t["texto"],
                         rowheight=22, borderwidth=0)
        estilo.configure("Treeview.Heading", background=t["control"], foreground=t["texto"], borderwidth=0,
                         font=("Segoe UI", 8, "bold"))
        estilo.map("Treeview", background=[("selected", t["control_activo"])])
        estilo.configure("Horizontal.TScale", background=t["deslizador"], troughcolor=t["control"],
                         bordercolor=t["panel"], lightcolor=t["deslizador"], darkcolor=t["deslizador"])
        estilo.configure("Vertical.TScrollbar", background=t["control"], troughcolor=t["panel"],
                         arrowcolor=t["texto"])

    # ------------------------------------------------------------------ construcción
    def _crear_cabecera(self):
        t = TEMA
        cabecera = tk.Frame(self.raiz, bg=t["panel"], padx=18, pady=10)
        cabecera.pack(fill="x")
        marca = tk.Frame(cabecera, bg=t["panel"])
        marca.pack(side="left")
        tk.Label(marca, text="⛰", bg=t["panel"], fg=t["acento2"], font=("Segoe UI Emoji", 24)).pack(side="left")
        textos = tk.Frame(marca, bg=t["panel"])
        textos.pack(side="left", padx=(10, 0))
        nombre = tk.Frame(textos, bg=t["panel"])
        nombre.pack(anchor="w")
        tk.Label(nombre, text=NOMBRE_APP[:-2], bg=t["panel"], fg=t["texto"],
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(nombre, text=NOMBRE_APP[-2:], bg=t["panel"], fg=t["deslizador"],
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(textos, text=LEMA_APP, bg=t["panel"], fg=t["texto_suave"], font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(cabecera, text="  PROTOTIPO ACADÉMICO  ", bg=t["aviso_fondo"], fg=t["aviso_texto"],
                 font=("Segoe UI", 8, "bold"), padx=6, pady=3).pack(side="right")
        # Selector de modo: sencillo (para quien no conoce el algoritmo) o experto (todos los datos).
        selector = tk.Frame(cabecera, bg=t["borde"], padx=1, pady=1)
        selector.pack(side="right", padx=16)
        for texto, valor in (("👤  Modo sencillo", True), ("🔬  Modo experto", False)):
            tk.Radiobutton(selector, text=texto, variable=self.var_sencillo, value=valor, indicatoron=False,
                           font=("Segoe UI", 9, "bold"), bg=t["control"], fg=t["texto"], selectcolor=t["acento"],
                           activebackground=t["control_activo"], activeforeground=t["texto"], relief="flat",
                           bd=0, padx=14, pady=6, cursor="hand2", command=self._cambiar_modo).pack(side="left")
        # Franja bicolor: violeta (búsqueda) y ámbar (cumbre).
        franja = tk.Frame(self.raiz, bg=t["panel"], height=3)
        franja.pack(fill="x")
        tk.Frame(franja, bg=t["acento"], height=3).place(relx=0, rely=0, relwidth=0.7, relheight=1)
        tk.Frame(franja, bg=t["acento2"], height=3).place(relx=0.7, rely=0, relwidth=0.3, relheight=1)
        tk.Label(self.raiz, text="⚠  " + ADVERTENCIA_SEGURIDAD, bg=t["fondo"], fg=t["aviso_texto"],
                 font=("Segoe UI", 8), anchor="w", justify="left", padx=18, pady=4).pack(fill="x")

    def _crear_panel_configuracion(self, padre):
        # Panel con desplazamiento vertical: su contenido no cabe entero en pantallas bajas.
        contenedor = tk.Frame(padre, bg=TEMA["panel"])
        contenedor.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        lienzo = tk.Canvas(contenedor, bg=TEMA["panel"], highlightthickness=0, width=340)
        barra = ttk.Scrollbar(contenedor, orient="vertical", command=lienzo.yview)
        lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        lienzo.pack(side="left", fill="y", expand=True)
        panel = ttk.Frame(lienzo, style="Panel.TFrame", padding=10)
        lienzo.create_window((0, 0), window=panel, anchor="nw")
        panel.bind("<Configure>", lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all"),
                                                             width=panel.winfo_reqwidth()))

        def rueda(evento):
            lienzo.yview_scroll(int(-evento.delta / 120), "units")
        contenedor.bind("<Enter>", lambda _e: lienzo.bind_all("<MouseWheel>", rueda))
        contenedor.bind("<Leave>", lambda _e: lienzo.unbind_all("<MouseWheel>"))

        modos = ttk.Frame(panel, style="Panel.TFrame")
        modos.pack(fill="x")
        self.panel_sencillo = ttk.Frame(modos, style="Panel.TFrame")
        self.panel_experto = ttk.Frame(modos, style="Panel.TFrame")

        ruta = ttk.LabelFrame(self.panel_experto, text="  ①  ORIGEN Y PUNTO DE ENCUENTRO  ", padding=8)
        ruta.pack(fill="x")
        busqueda = ttk.LabelFrame(self.panel_experto, text="  ②  ESTRATEGIA DE BÚSQUEDA  ", padding=8)
        busqueda.pack(fill="x", pady=(10, 0))
        self.var_origen = tk.StringVar()
        self.var_destino = tk.StringVar()
        self.var_heuristica = tk.StringVar(value=NOMBRES_HEURISTICA[HEURISTICA_SALIDA])
        self.var_criterio = tk.StringVar(value=NOMBRES_CRITERIO[CRITERIO_COSTO_HEURISTICA])
        self.var_variante = tk.StringVar(value=NOMBRES_VARIANTE[VARIANTE_MAXIMA_PENDIENTE])
        self.var_reinicios = tk.IntVar(value=REINICIOS_POR_DEFECTO)
        self.var_semilla = tk.IntVar(value=SEMILLA_POR_DEFECTO)

        self.origenes = [etiqueta(self.grafo, n) for n in nodos_por_tipo(self.grafo, "origen")]
        self.destinos = [etiqueta(self.grafo, n) for n in nodos_por_tipo(self.grafo, "destino")]
        self.var_origen.set(self.origenes[0])
        self.var_destino.set(self.destinos[0])

        filas = [
            (ruta, "Bloque de origen", self.var_origen, self.origenes),
            (ruta, "Punto de encuentro (cumbre)", self.var_destino, self.destinos),
            (busqueda, "Heurística h(n)", self.var_heuristica, list(NOMBRES_HEURISTICA.values())),
            (busqueda, "Selección entre vecinos", self.var_criterio, list(NOMBRES_CRITERIO.values())),
            (busqueda, "Variante de Hill Climbing", self.var_variante, list(NOMBRES_VARIANTE.values())),
        ]
        for contenedor, texto, variable, valores in filas:
            ttk.Label(contenedor, text=texto).pack(anchor="w", pady=(5, 1))
            combo = ttk.Combobox(contenedor, textvariable=variable, values=valores, state="readonly", width=34)
            combo.pack(fill="x")
            combo.bind("<<ComboboxSelected>>", lambda _e: self._configuracion_cambiada())

        estocastico = ttk.Frame(busqueda, style="Panel.TFrame")
        estocastico.pack(fill="x", pady=(8, 0))
        ttk.Label(estocastico, text="Reinicios").grid(row=0, column=0, sticky="w")
        self.spin_reinicios = ttk.Spinbox(estocastico, from_=0, to=50, textvariable=self.var_reinicios, width=5,
                                          command=self._configuracion_cambiada)
        self.spin_reinicios.grid(row=0, column=1, padx=(6, 14))
        ttk.Label(estocastico, text="Semilla").grid(row=0, column=2, sticky="w")
        self.spin_semilla = ttk.Spinbox(estocastico, from_=0, to=9999, textvariable=self.var_semilla, width=6,
                                        command=self._configuracion_cambiada)
        self.spin_semilla.grid(row=0, column=3, padx=6)
        ttk.Label(busqueda, text="Reinicios y semilla solo afectan a la variante estocástica.",
                  style="Suave.TLabel").pack(anchor="w", pady=(3, 0))

        bloqueos = ttk.LabelFrame(self.panel_experto, text="  ③  ESCENARIO · CONEXIONES BLOQUEADAS  ", padding=8)
        bloqueos.pack(fill="x", pady=(10, 0))
        self.vars_bloqueo = {}
        casillas = ttk.Frame(bloqueos, style="Panel.TFrame")
        casillas.pack(fill="x")
        for indice, (u, v, d) in enumerate(self.grafo.edges(data=True)):
            variable = tk.BooleanVar(value=False)
            self.vars_bloqueo[(u, v)] = variable
            ttk.Checkbutton(casillas, text=f"{u} → {v} ({_numero(d['longitud_m'])} m)",
                            variable=variable, command=self._bloqueos_cambiados).grid(
                row=indice // 2, column=indice % 2, sticky="w", padx=(0, 8), pady=1)
        botones_esc = ttk.Frame(bloqueos, style="Panel.TFrame")
        botones_esc.pack(fill="x", pady=(6, 0))
        botones_esc.columnconfigure((0, 1), weight=1)
        ttk.Button(botones_esc, text="Informe: P1 bloqueado",
                   command=lambda: self._cargar_escenario("acceso_P1_bloqueado")).grid(row=0, column=0, sticky="ew")
        ttk.Button(botones_esc, text="Habilitar todas", command=lambda: self._cargar_escenario("normal")).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

        self._crear_panel_sencillo(self.panel_sencillo)

        self.boton_calcular = ttk.Button(panel, text="⛰  ESCALAR · CALCULAR RUTA", style="Acento.TButton",
                                         command=self.calcular)
        self.boton_calcular.pack(fill="x", pady=(12, 0))

        self._crear_seccion_personas(panel)

        acciones = ttk.Frame(panel, style="Panel.TFrame")
        acciones.pack(fill="x", pady=(12, 0))
        acciones.columnconfigure((0, 1), weight=1)
        for indice, (texto, comando) in enumerate([
            ("Ver grafo completo", self.ver_grafo_completo),
            ("Croquis y mapas", self.ver_croquis),
            ("Guardar figura…", self.guardar_figura),
            ("Reiniciar", self.reiniciar),
        ]):
            ttk.Button(acciones, text=texto, command=comando).grid(
                row=1 + indice // 2, column=indice % 2, sticky="ew", pady=(5, 0), padx=(0 if indice % 2 == 0 else 5, 0))

    def _crear_seccion_personas(self, padre):
        """Número de personas por bloque y las dos búsquedas de reparto (sencilla y Hill Climbing)."""
        t = TEMA
        self.marco_personas = ttk.LabelFrame(padre, text="  👥  EVACUAR A TODAS LAS PERSONAS  ", padding=8)
        self.marco_personas.pack(fill="x", pady=(14, 0))
        self.vars_personas = {}
        filas = ttk.Frame(self.marco_personas, style="Panel.TFrame")
        filas.pack(fill="x")
        for fila, (bloque, inicial) in enumerate((("G", 80), ("H", 60))):   # población estándar del informe
            ttk.Label(filas, text=f"Personas en el {self.grafo.nodes[bloque]['nombre']}",
                      font=("Segoe UI", 10)).grid(row=fila, column=0, sticky="w", pady=3)
            variable = tk.StringVar(value=str(inicial))
            self.vars_personas[bloque] = variable
            ttk.Spinbox(filas, from_=0, to=340, increment=10, textvariable=variable, width=6,
                        font=("Segoe UI", 11, "bold")).grid(row=fila, column=1, sticky="e", padx=(10, 0), pady=3)
        filas.columnconfigure(0, weight=1)
        ttk.Label(self.marco_personas, style="Suave.TLabel", wraplength=300, justify="left",
                  text="Se organizan en grupos de 10. Cupos supuestos: Plaza 100, Área Verde 100, "
                       "Canchas 140 (total 340).").pack(anchor="w", pady=(4, 8))
        botones = ttk.Frame(self.marco_personas, style="Panel.TFrame")
        botones.pack(fill="x")
        botones.columnconfigure((0, 1), weight=1)
        self.boton_sencilla = ttk.Button(botones, text="🚶 Búsqueda\nsencilla", style="TButton",
                                         command=self.evacuar_sencilla)
        self.boton_sencilla.grid(row=0, column=0, sticky="nsew", padx=(0, 4), ipady=4)
        self.boton_hc = ttk.Button(botones, text="⛰ Hill\nClimbing", style="Cumbre.TButton",
                                   command=self.evacuar_hill_climbing)
        self.boton_hc.grid(row=0, column=1, sticky="nsew", ipady=4)
        self.lbl_estado_grupal = tk.Label(self.marco_personas, text="", bg=t["panel"], fg=t["aviso_texto"],
                                          font=("Segoe UI", 8), anchor="w", justify="left", wraplength=300)
        self.lbl_estado_grupal.pack(fill="x", pady=(6, 0))

    def _crear_panel_sencillo(self, padre):
        """Dos preguntas grandes para quien no conoce el algoritmo; usa una configuración fija."""
        t = TEMA

        def pregunta(texto, ayuda):
            tk.Label(padre, text=texto, bg=t["panel"], fg=t["texto"], font=("Segoe UI", 13, "bold"),
                     anchor="w").pack(fill="x", pady=(8, 0))
            tk.Label(padre, text=ayuda, bg=t["panel"], fg=t["texto_suave"], font=("Segoe UI", 8),
                     anchor="w", justify="left", wraplength=320).pack(fill="x", pady=(0, 6))

        def opcion(contenedor, variable, valor, texto, color):
            marco = tk.Frame(contenedor, bg=color, padx=0, pady=0)
            boton = tk.Radiobutton(
                marco, text=texto, variable=variable, value=valor, indicatoron=False, anchor="w",
                font=("Segoe UI", 11, "bold"), bg=t["control"], fg=t["texto"], selectcolor=t["acento"],
                activebackground=t["control_activo"], activeforeground=t["texto"], relief="flat", bd=0,
                padx=12, pady=9, cursor="hand2", command=self._configuracion_cambiada)
            boton.pack(fill="x", padx=(6, 0))
            return marco

        pregunta("1. ¿Dónde estás?", "Elige el bloque en el que te encuentras.")
        fila = tk.Frame(padre, bg=t["panel"])
        fila.pack(fill="x")
        fila.columnconfigure((0, 1), weight=1)
        for columna, valor in enumerate(self.origenes):
            nodo = valor.split(" · ")[0]
            opcion(fila, self.var_origen, valor, f"🏢  {self.grafo.nodes[nodo]['nombre']}",
                   COLORES["origen"]).grid(row=0, column=columna, sticky="ew", padx=(0, 6) if columna == 0 else 0)

        pregunta("2. ¿A dónde quieres llegar?", "Elige el punto de encuentro. Se elige a mano: estar más cerca "
                                               "no significa que sea el más seguro.")
        for valor in self.destinos:
            nodo = valor.split(" · ")[0]
            opcion(padre, self.var_destino, valor, f"⚑  {self.grafo.nodes[nodo]['nombre']}",
                   COLOR_DESTINO.get(nodo, t["acento2"])).pack(fill="x", pady=(0, 6))

        pregunta("3. Opciones", "")
        self.var_reintentar = tk.BooleanVar(value=True)
        ttk.Checkbutton(padre, text="Si no llega, intentar varias veces\n(prueba otros caminos al azar)",
                        variable=self.var_reintentar, command=self._configuracion_cambiada).pack(anchor="w")
        self.var_plaza_cerrada = tk.BooleanVar(value=False)
        ttk.Checkbutton(padre, text="Simular que el acceso a la Plaza\nestá cerrado (caso del informe)",
                        variable=self.var_plaza_cerrada,
                        command=lambda: self._cargar_escenario(
                            "acceso_P1_bloqueado" if self.var_plaza_cerrada.get() else "normal")).pack(
            anchor="w", pady=(6, 0))

    def _crear_franja_indicadores(self, padre):
        """Fila de "chips" sobre el mapa: estado de la escalada y métricas principales."""
        t = TEMA
        franja = tk.Frame(padre, bg=t["panel"])
        franja.pack(side="top", fill="x", pady=(0, 6))

        def chip(columna, ancho_minimo):
            marco = tk.Frame(franja, bg=t["tarjeta"], highlightbackground=t["borde"], highlightthickness=1)
            marco.grid(row=0, column=columna, sticky="nsew", padx=(0 if columna == 0 else 6, 0))
            franja.columnconfigure(columna, weight=1, minsize=ancho_minimo)
            barra = tk.Frame(marco, bg=t["acento"], width=4)
            barra.pack(side="left", fill="y")
            interior = tk.Frame(marco, bg=t["tarjeta"], padx=10, pady=6)
            interior.pack(side="left", fill="both", expand=True)
            interior.marco = marco
            return interior, barra

        principal, self.barra_estado = chip(0, 300)
        self.lbl_escenario = tk.Label(principal, bg=t["tarjeta"], fg=t["texto_suave"], font=("Segoe UI", 8, "bold"),
                                      anchor="w")
        self.lbl_escenario.pack(fill="x")
        self.lbl_estado = tk.Label(principal, bg=t["tarjeta"], fg=t["texto_suave"], font=("Segoe UI", 13, "bold"),
                                   anchor="w", justify="left", wraplength=360)
        self.lbl_estado.pack(fill="x")
        self.lbl_ruta = tk.Label(principal, bg=t["tarjeta"], fg=t["ok"], font=("Segoe UI", 9, "bold"), anchor="w",
                                 justify="left", wraplength=360)
        self.lbl_ruta.pack(fill="x")
        self.lbl_config = tk.Label(principal, bg=t["tarjeta"], fg=t["texto_suave"], font=("Segoe UI", 7),
                                   anchor="w", justify="left", wraplength=360)
        self.lbl_config.pack(fill="x")

        self.metricas = {}
        self.titulos_metricas = {}
        self.chips_tecnicos = []   # se ocultan en modo sencillo
        for columna, (clave, titulo) in enumerate([
            ("distancia", "DISTANCIA"), ("tiempo", f"A PIE ({_numero(VELOCIDAD_MARCHA_MS)} m/s*)"),
            ("iteraciones", "ITERACIONES"), ("evaluados", "VECINOS EVALUADOS"),
        ], start=1):
            interior, _ = chip(columna, 110)
            if clave in ("iteraciones", "evaluados"):
                self.chips_tecnicos.append((interior.marco, columna))
            etiqueta_titulo = tk.Label(interior, text=titulo, bg=t["tarjeta"], fg=t["texto_suave"],
                                       font=("Segoe UI", 7, "bold"))
            etiqueta_titulo.pack(anchor="w")
            self.titulos_metricas[clave] = (etiqueta_titulo, titulo)
            valor = tk.Label(interior, text="—", bg=t["tarjeta"], fg=t["texto"], font=("Segoe UI", 14, "bold"))
            valor.pack(anchor="w")
            self.metricas[clave] = valor

    def _crear_panel_mapa(self, padre):
        panel = ttk.Frame(padre, style="Panel.TFrame", padding=6)
        panel.grid(row=0, column=1, sticky="nsew")
        self._crear_franja_indicadores(panel)
        # Tamaño inicial pequeño: el lienzo se expande para ocupar el espacio libre.
        self.figura = Figure(figsize=(5.5, 5.5), dpi=100, facecolor=TEMA["panel"])
        self.ax = self.figura.add_subplot(111)
        self.figura.subplots_adjust(left=0.01, right=0.99, top=0.955, bottom=0.01)
        self.canvas = FigureCanvasTkAgg(self.figura, master=panel)

        controles = ttk.Frame(panel, style="Panel.TFrame", padding=(4, 6, 4, 0))
        controles.pack(side="bottom", fill="x")
        fila1 = ttk.Frame(controles, style="Panel.TFrame")
        fila1.pack(fill="x")
        self.boton_animar = ttk.Button(fila1, text="▶ Ver la escalada", style="Animar.TButton",
                                       command=self.animar_busqueda)
        self.boton_animar.pack(side="left")
        self.boton_recorrido = ttk.Button(fila1, text="▲ Simular evacuación", style="Animar.TButton",
                                          command=self.simular_recorrido)
        self.boton_recorrido.pack(side="left", padx=4)
        self.boton_pausa = ttk.Button(fila1, text="⏸ Pausa", command=self.detener_animacion)
        self.boton_pausa.pack(side="left")
        # Selector del reparto que se ve en el mapa (solo con la evacuación de todas las personas).
        self.selector_plan = tk.Frame(fila1, bg=TEMA["borde"], padx=1, pady=1)
        for texto, valor in (("Búsqueda sencilla", "sencilla"), ("Hill Climbing", "hc")):
            tk.Radiobutton(self.selector_plan, text=texto, variable=self.var_plan, value=valor, indicatoron=False,
                           font=("Segoe UI", 9, "bold"), bg=TEMA["control"], fg=TEMA["texto"],
                           selectcolor=TEMA["acento"], activebackground=TEMA["control_activo"],
                           activeforeground=TEMA["texto"], relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                           command=self._plan_cambiado).pack(side="left")
        self.nav_pasos = ttk.Frame(fila1, style="Panel.TFrame")
        self.nav_pasos.pack(side="left")
        ttk.Separator(self.nav_pasos, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(self.nav_pasos, text="◀ Paso", command=lambda: self._mover_paso(-1)).pack(side="left")
        ttk.Button(self.nav_pasos, text="Paso ▶", command=lambda: self._mover_paso(1)).pack(side="left", padx=4)
        ttk.Button(self.nav_pasos, text="Resultado final", command=self._ver_final).pack(side="left")
        self.etiqueta_vista = ttk.Label(fila1, text="", style="Suave.TLabel")
        self.etiqueta_vista.pack(side="right")

        fila2 = ttk.Frame(controles, style="Panel.TFrame")
        fila2.pack(fill="x", pady=(8, 2))
        ttk.Label(fila2, text="Tiempo (s)").pack(side="left")
        self.var_tiempo = tk.DoubleVar(value=0.0)
        self.escala_tiempo = ttk.Scale(fila2, from_=0, to=1, variable=self.var_tiempo, command=self._tiempo_movido)
        self.escala_tiempo.pack(side="left", fill="x", expand=True, padx=8)
        self.etiqueta_tiempo = ttk.Label(fila2, text="0,0", width=7)
        self.etiqueta_tiempo.pack(side="left")
        ttk.Label(fila2, text="Velocidad ×").pack(side="left", padx=(12, 0))
        self.var_velocidad = tk.DoubleVar(value=8.0)
        ttk.Scale(fila2, from_=1, to=30, variable=self.var_velocidad, length=120,
                  command=lambda _v: self.etiqueta_velocidad.configure(
                      text=f"{self.var_velocidad.get():.0f}")).pack(side="left", padx=6)
        self.etiqueta_velocidad = ttk.Label(fila2, text="8", width=3)
        self.etiqueta_velocidad.pack(side="left")

        self.canvas.get_tk_widget().configure(bg=TEMA["panel"], highlightthickness=0)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def _crear_panel_derecho(self, padre):
        t = TEMA
        panel = ttk.Frame(padre, style="Panel.TFrame", padding=10)
        panel.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        self.cuaderno = ttk.Notebook(panel, width=460)
        self.cuaderno.pack(fill="both", expand=True)

        # Guía en lenguaje cotidiano (pestaña principal del modo sencillo).
        self.texto_guia = self._texto(self.cuaderno)
        self.texto_guia.configure(font=("Segoe UI", 10), padx=16, pady=14, spacing1=2, spacing3=4)
        self.texto_guia.tag_configure("titulo", font=("Segoe UI", 15, "bold"), spacing3=8)
        self.texto_guia.tag_configure("ok", foreground=t["ok"])
        self.texto_guia.tag_configure("mal", foreground=t["mal"])
        self.texto_guia.tag_configure("seccion", font=("Segoe UI", 11, "bold"), foreground=t["acento2"],
                                      spacing1=14, spacing3=4)
        self.texto_guia.tag_configure("paso", lmargin1=6, lmargin2=24, spacing3=6)
        self.texto_guia.tag_configure("actual", background=t["control_activo"])
        self.texto_guia.tag_configure("suave", foreground=t["texto_suave"], font=("Segoe UI", 9))
        self.texto_guia.tag_configure("aviso", foreground=t["aviso_texto"], font=("Segoe UI", 9))
        self.tab_guia = self.texto_guia.master
        self.cuaderno.add(self.tab_guia, text="📋 Guía")

        marco_graficas = tk.Frame(self.cuaderno, bg=t["tarjeta"])
        self.figura_graficas = Figure(figsize=(4.6, 6.5), dpi=100, facecolor=t["tarjeta"])
        self.ax_perfil = self.figura_graficas.add_subplot(211)
        self.ax_comparacion = self.figura_graficas.add_subplot(212)
        self.figura_graficas.subplots_adjust(left=0.1, right=0.97, top=0.95, bottom=0.07, hspace=0.38)
        self.canvas_graficas = FigureCanvasTkAgg(self.figura_graficas, master=marco_graficas)
        self.canvas_graficas.get_tk_widget().configure(bg=t["tarjeta"], highlightthickness=0)
        self.canvas_graficas.get_tk_widget().pack(fill="both", expand=True)
        tk.Label(marco_graficas, text="* velocidad media supuesta en el informe; solo tiempo de marcha.",
                 bg=t["tarjeta"], fg=t["texto_suave"], font=("Segoe UI", 7)).pack(anchor="w", padx=8, pady=(0, 4))
        self.cuaderno.add(marco_graficas, text="⛰ Escalada")
        self.tab_escalada = marco_graficas

        marco_pasos = tk.Frame(self.cuaderno, bg=t["tarjeta"])
        columnas = ("actual", "vecino", "tramo", "h", "f", "estado")
        self.arbol_pasos = ttk.Treeview(marco_pasos, columns=columnas, show="tree headings", height=12)
        self.arbol_pasos.heading("#0", text="Iter.")
        self.arbol_pasos.column("#0", width=50, stretch=False)
        for col, titulo, ancho in [("actual", "Actual (h)", 88), ("vecino", "Vecino", 60), ("tramo", "Tramo", 58),
                                   ("h", "h(v)", 56), ("f", "f(v)", 56), ("estado", "Estado", 96)]:
            self.arbol_pasos.heading(col, text=titulo)
            self.arbol_pasos.column(col, width=ancho, anchor="center")
        self.arbol_pasos.tag_configure("elegido", background="#1f5c4a")
        self.arbol_pasos.tag_configure("descartado", foreground=t["texto_suave"])
        self.arbol_pasos.tag_configure("iteracion", font=("Segoe UI", 9, "bold"))
        self.arbol_pasos.bind("<<TreeviewSelect>>", self._paso_seleccionado)
        self.arbol_pasos.pack(fill="both", expand=True)
        tk.Label(marco_pasos, text="Decisión de la iteración seleccionada", bg=t["tarjeta"], fg=t["texto_suave"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=6, pady=(8, 0))
        self.texto_motivo = self._texto_simple(marco_pasos, alto=7)
        self.texto_motivo.pack(fill="x", padx=6, pady=(2, 6))
        self.cuaderno.add(marco_pasos, text="Pasos")
        self.tab_pasos = marco_pasos

        self.texto_resultados = self._texto(self.cuaderno)
        self.cuaderno.add(self.texto_resultados.master, text="Detalle")
        self.texto_datos = self._texto(self.cuaderno)
        self.cuaderno.add(self.texto_datos.master, text="Datos del modelo")
        self.pestanas_tecnicas = [self.tab_escalada, self.tab_pasos, self.texto_resultados.master,
                                  self.texto_datos.master]

    def _texto_simple(self, padre, alto: int) -> tk.Text:
        return tk.Text(padre, height=alto, wrap="word", font=("Segoe UI", 9), relief="flat", bg=TEMA["control"],
                       fg=TEMA["texto"], padx=8, pady=6, state="disabled")

    def _texto(self, padre) -> tk.Text:
        marco = tk.Frame(padre, bg=TEMA["tarjeta"])
        texto = tk.Text(marco, wrap="word", font=("Consolas", 9), relief="flat", padx=10, pady=10,
                        bg=TEMA["tarjeta"], fg=TEMA["texto"], insertbackground=TEMA["texto"])
        barra = ttk.Scrollbar(marco, command=texto.yview)
        texto.configure(yscrollcommand=barra.set, state="disabled")
        barra.pack(side="right", fill="y")
        texto.pack(side="left", fill="both", expand=True)
        return texto

    @staticmethod
    def _escribir(widget: tk.Text, contenido: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", contenido)
        widget.configure(state="disabled")

    # ------------------------------------------------------------------ opciones
    def _opciones(self) -> dict:
        if self.var_sencillo.get():
            # Configuración fija y explicada: heurística con salida por S, tramo + heurística y,
            # si se pide, reinicios aleatorios. Sigue siendo Hill Climbing.
            return {
                "heuristica": HEURISTICA_SALIDA,
                "criterio": CRITERIO_COSTO_HEURISTICA,
                "variante": VARIANTE_ESTOCASTICA if self.var_reintentar.get() else VARIANTE_MAXIMA_PENDIENTE,
                "max_reinicios": REINICIOS_POR_DEFECTO,
                "semilla": SEMILLA_POR_DEFECTO,
            }
        try:
            reinicios = int(self.spin_reinicios.get())
            semilla = int(self.spin_semilla.get())
        except ValueError:
            raise ValueError("Reinicios y semilla deben ser números enteros.")
        if not 0 <= reinicios <= 50:
            raise ValueError("Los reinicios deben estar entre 0 y 50.")
        if semilla < 0:
            raise ValueError("La semilla no puede ser negativa.")
        return {
            "heuristica": _clave_por_nombre(NOMBRES_HEURISTICA, self.var_heuristica.get()),
            "criterio": _clave_por_nombre(NOMBRES_CRITERIO, self.var_criterio.get()),
            "variante": _clave_por_nombre(NOMBRES_VARIANTE, self.var_variante.get()),
            "max_reinicios": reinicios,
            "semilla": semilla,
        }

    def _origen(self) -> str:
        return self.var_origen.get().split(" · ")[0]

    def _destino(self) -> str:
        return self.var_destino.get().split(" · ")[0]

    def _reiniciar_barra_tiempo(self):
        self._sincronizando_barra = True
        self.var_tiempo.set(0.0)
        self._sincronizando_barra = False
        self.etiqueta_tiempo.configure(text=_numero(0.0))

    def _invalidar(self, mensaje: str):
        self.detener_animacion()
        self._reiniciar_barra_tiempo()
        self.resultado = None
        self.comparacion = []
        self.paso = None
        self.vista = "ruta"
        self.escenario_grupal = self.plan_sencillo = self.plan_hc = None
        self.iteracion_grupal = None
        self.lbl_estado_grupal.configure(text="")
        self._actualizar_barra_controles()
        self._limpiar_pasos()
        self._redibujar()
        self._actualizar_tarjeta()
        self._actualizar_guia()
        self._escribir(self.texto_resultados, mensaje)

    def _actualizar_barra_controles(self):
        """Selector de reparto solo con todas las personas; pasos de la ruta solo en modo experto."""
        self.selector_plan.pack_forget()
        self.nav_pasos.pack_forget()
        if self.vista == "personas":
            self.selector_plan.pack(side="left", padx=(10, 0), after=self.boton_pausa)
        elif not self.var_sencillo.get():
            self.nav_pasos.pack(side="left", after=self.boton_pausa)

    def _ir_a_pasos(self):
        self.cuaderno.select(self.tab_guia if self.var_sencillo.get() else self.tab_pasos)

    def _cambiar_modo(self):
        """Muestra u oculta todo lo técnico según el modo elegido."""
        sencillo = self.var_sencillo.get()
        self.detener_animacion()
        if sencillo:
            self.panel_experto.pack_forget()
            self.panel_sencillo.pack(fill="x")
            for marco, _ in self.chips_tecnicos:
                marco.grid_remove()
            for pestana in self.pestanas_tecnicas:
                self.cuaderno.hide(pestana)
            self.boton_calcular.configure(text="🔍  BUSCAR RUTA")
            self.boton_animar.configure(text="▶ Ver cómo decide")
            self.boton_recorrido.configure(text="▲ Ver el recorrido")
        else:
            self.panel_sencillo.pack_forget()
            self.panel_experto.pack(fill="x")
            for marco, _ in self.chips_tecnicos:
                marco.grid()
            for pestana in self.pestanas_tecnicas:
                self.cuaderno.add(pestana)
            self.boton_calcular.configure(text="⛰  ESCALAR · CALCULAR RUTA")
            self.boton_animar.configure(text="▶ Ver la escalada")
            self.boton_recorrido.configure(text="▲ Simular evacuación")
        self.cuaderno.select(self.tab_guia if sencillo else self.tab_escalada)
        self._actualizar_barra_controles()
        if self.vista == "personas":
            # El reparto de personas no depende del modo: solo cambia cómo se presenta.
            self._actualizar_vista_personas()
        # Las opciones de búsqueda de ruta difieren entre modos: el resultado anterior deja de valer.
        elif self.resultado is not None:
            self._invalidar("Se cambió de modo. Pulse el botón de búsqueda de nuevo.")
        else:
            self._redibujar()
            self._actualizar_tarjeta()
            self._actualizar_guia()

    def _actualizar_guia(self):
        """Pestaña «Guía»: resultado, indicaciones y decisiones en lenguaje cotidiano."""
        texto = self.texto_guia
        texto.configure(state="normal")
        texto.delete("1.0", "end")
        r = self.resultado
        g = self.grafo
        if self.vista == "personas":
            self._escribir_guia_grupal(texto)
            texto.configure(state="disabled")
            return
        if r is None:
            texto.insert("end", "¿Cómo usar esta aplicación?\n", "titulo")
            for linea in ("1. Elige en qué bloque estás (G o H).",
                          "2. Elige a qué punto de encuentro quieres llegar.",
                          "3. Pulsa «Buscar ruta». La ruta aparece en el mapa y aquí verás las indicaciones.",
                          "4. Con «Ver cómo decide» verás, paso a paso, por qué la computadora eligió cada camino."):
                texto.insert("end", linea + "\n", "paso")
            texto.insert("end", "¿Qué es Hill Climbing?\n", "seccion")
            texto.insert("end", QUE_ES_HILL_CLIMBING + "\n")
            texto.insert("end", "Importante\n", "seccion")
            texto.insert("end", ADVERTENCIA_SEGURIDAD + "\n", "aviso")
            texto.configure(state="disabled")
            return

        existe = existe_camino_transitable(g, r.origen, r.destino)
        texto.insert("end", "✔ ¡Ruta encontrada!\n" if r.exito else "✖ No se encontró ruta\n",
                     ("titulo", "ok" if r.exito else "mal"))
        texto.insert("end", resumen(g, r, existe) + "\n")
        if r.exito:
            texto.insert("end", "Cómo llegar\n", "seccion")
            for linea in indicaciones(g, r):
                texto.insert("end", linea + "\n", "paso")
            texto.insert("end", "Los números coinciden con los del mapa. Distancias medidas sobre el mapa del "
                                "campus; tiempo calculado a paso normal (1,2 m/s), sin contar aglomeraciones.\n",
                         "suave")
        else:
            texto.insert("end", "¿Por qué no llegó?\n", "seccion")
            texto.insert("end", explicar_fallo(g, r, existe) + "\n")

        if r.pasos:
            texto.insert("end", "¿Cómo decidió la computadora?\n", "seccion")
            for indice in range(len(r.pasos)):
                etiquetas = ("paso", "actual") if indice == self.paso else ("paso",)
                texto.insert("end", f"Paso {indice + 1}. {explicar_paso(g, r, indice)}\n", etiquetas)
            if len(r.intentos) > 1:
                texto.insert("end", f"Hizo {len(r.intentos)} intentos: los primeros se quedaron atascados y "
                                    "volvió a empezar tomando otros caminos.\n", "suave")

        texto.insert("end", "¿Qué es Hill Climbing?\n", "seccion")
        texto.insert("end", QUE_ES_HILL_CLIMBING + "\n")
        texto.insert("end", "Importante\n", "seccion")
        texto.insert("end", ADVERTENCIA_SEGURIDAD + "\n", "aviso")
        if texto.tag_ranges("actual"):
            texto.see("actual.first")
        texto.configure(state="disabled")

    def _configuracion_cambiada(self):
        if self.resultado is not None:
            self._invalidar("La configuración cambió. Pulse «Calcular ruta» para ejecutar Hill Climbing de nuevo.")
        else:
            self._redibujar()            # actualiza el título con el nuevo origen o destino
            self._actualizar_tarjeta()

    def _bloqueos_cambiados(self):
        aplicar_bloqueos(self.grafo, [arista for arista, var in self.vars_bloqueo.items() if var.get()])
        if ("J", "P1") in self.vars_bloqueo:
            self.var_plaza_cerrada.set(self.vars_bloqueo[("J", "P1")].get())
        self._mostrar_datos_modelo()
        bloqueadas = [f"{u} → {v}" for (u, v), var in self.vars_bloqueo.items() if var.get()]
        self._invalidar("Conexiones bloqueadas: " + (", ".join(bloqueadas) or "ninguna") +
                        "\n\nPulse «Calcular ruta» para ejecutar Hill Climbing con este escenario.")

    def _cargar_escenario(self, clave: str):
        bloqueadas = {tuple(a) for a in self.escenarios.get(clave, {}).get("bloqueadas", [])}
        for arista, variable in self.vars_bloqueo.items():
            variable.set(arista in bloqueadas)
        self._bloqueos_cambiados()

    # ------------------------------------------------------------------ acciones
    def calcular(self) -> bool:
        try:
            opciones = self._opciones()
        except ValueError as error:
            messagebox.showerror("Entrada inválida", str(error))
            return False
        self.detener_animacion()
        self._reiniciar_barra_tiempo()
        self.vista = "ruta"
        self.escenario_grupal = self.plan_sencillo = self.plan_hc = None
        self._actualizar_barra_controles()
        self.lbl_estado_grupal.configure(text="")
        self.resultado = buscar(self.grafo, self._origen(), self._destino(), **opciones)
        # Misma configuración hacia cada destino, para la gráfica comparativa.
        self.comparacion = evaluar_destinos(self.grafo, self._origen(), nodos_por_tipo(self.grafo, "destino"),
                                            **opciones)
        self.paso = None
        self._mostrar_resultado()
        self._llenar_pasos()
        self._redibujar()
        self._actualizar_tarjeta()
        self._actualizar_guia()
        return True

    def mostrar_pasos(self):
        if self.resultado is None and not self.calcular():
            return
        if not self.resultado.pasos:
            messagebox.showinfo("Pasos", "La búsqueda no realizó iteraciones (revise el origen y el destino).")
            return
        self.detener_animacion()
        self.paso = 0
        self._ir_a_pasos()
        self._sincronizar_paso()

    def ver_grafo_completo(self):
        self.detener_animacion()
        self.paso = None
        dibujar(self.ax, self.grafo, None, titulo="Grafo completo del modelo · 9 nodos, 8 aristas dirigidas")
        self._persona = self._reloj = None
        self.canvas.draw_idle()
        self.etiqueta_vista.configure(text="Vista: grafo completo")

    def reiniciar(self):
        self._invalidar(
            "Seleccione el bloque de origen y el punto de encuentro, y pulse «Calcular ruta».\n\n"
            "Hill Climbing avanza siempre hacia un vecino que reduce la distancia estimada h al destino. "
            "Si ningún vecino la reduce, se detiene: es una búsqueda local y puede no encontrar una ruta "
            "aunque exista.\n\n" + ADVERTENCIA_SEGURIDAD)
        self.cuaderno.select(self.tab_guia if self.var_sencillo.get() else self.tab_escalada)

    def guardar_figura(self):
        DIRECTORIO_EVIDENCIAS.mkdir(exist_ok=True)
        ruta = filedialog.asksaveasfilename(initialdir=DIRECTORIO_EVIDENCIAS, defaultextension=".png",
                                            filetypes=[("Imagen PNG", "*.png")], initialfile="ruta_hill_climbing.png")
        if ruta:
            self.figura.savefig(ruta, dpi=150, facecolor=self.figura.get_facecolor())

    def ver_croquis(self):
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Croquis y mapas de referencia (no alineados con el grafo)")
        ventana.geometry("1150x820")
        ventana.configure(bg=TEMA["panel"])
        cuaderno = ttk.Notebook(ventana)
        cuaderno.pack(fill="both", expand=True)
        imagenes = [
            ("Croquis del campus", IMAGEN_CROQUIS, "Plano campus ESPE (10/01/2017)",
             "Croquis general del campus. No identifica los bloques G y H ni los puntos P1-P3, y su escala "
             "declarada (1:200) no corresponde a un plano del campus; por eso no se superpone al grafo."),
            ("Puntos de encuentro 2019", IMAGEN_MAPA_HISTORICO, "Mapa histórico de puntos de encuentro",
             "Toulkeridis et al. (2019), figura 52. Evidencia histórica, sin coordenadas ni verificación de vigencia "
             "en 2026. Los letreros SALIDA son accesos, no puntos de reunión."),
            ("Referencia: simulador Tabú", DIRECTORIO_DATOS / "referencia_simulador_tabu.png",
             "Captura del simulador anterior (Búsqueda Tabú)",
             "Usada solo para medir la posición de los nodos y como referencia visual. Su algoritmo no se reutiliza."),
        ]
        for titulo_pestana, ruta, titulo, nota in imagenes:
            marco = tk.Frame(cuaderno, bg=TEMA["panel"])
            cuaderno.add(marco, text=titulo_pestana)
            figura = Figure(figsize=(11, 7.6), dpi=100, facecolor=TEMA["panel"])
            ax = figura.add_subplot(111)
            figura.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.06)
            try:
                dibujar_imagen(ax, ruta, titulo, nota)
            except (FileNotFoundError, OSError):
                ax.axis("off")
                ax.text(0.5, 0.5, f"Imagen de referencia de terceros no incluida en el repositorio:\n{ruta.name}\n"
                        "Consulte datos/README.md para obtenerla.", ha="center", va="center", color="white")
            lienzo = FigureCanvasTkAgg(figura, master=marco)
            NavigationToolbar2Tk(lienzo, marco).update()
            lienzo.get_tk_widget().pack(fill="both", expand=True)
            lienzo.draw()

    # ------------------------------------------------------------------ evacuación de todas las personas
    def _leer_personas(self) -> dict:
        personas = {}
        for bloque, variable in self.vars_personas.items():
            texto = variable.get().strip()
            if not texto.isdigit():
                raise ValueError(f"Escribe un número entero (0 o más) de personas para el "
                                 f"{self.grafo.nodes[bloque]['nombre']}.")
            personas[bloque] = int(texto)
        total = sum(personas.values())
        if total == 0:
            raise ValueError("Escribe al menos una persona en algún bloque.")
        return personas

    def _preparar_evacuacion(self):
        """Valida la entrada y crea el escenario con la misma población para ambas búsquedas."""
        personas = self._leer_personas()
        escenario = crear_escenario(self.grafo.copy(), personas, semilla=SEMILLA_POR_DEFECTO)
        return escenario, busqueda_sencilla(escenario)

    def evacuar_sencilla(self):
        try:
            escenario, plan = self._preparar_evacuacion()
        except ValueError as error:
            messagebox.showerror("No se puede evacuar", str(error))
            return
        self._mostrar_planes(escenario, plan, None, "sencilla")

    def evacuar_hill_climbing(self):
        try:
            escenario, plan_sencillo = self._preparar_evacuacion()
        except ValueError as error:
            messagebox.showerror("No se puede evacuar", str(error))
            return
        # Con muchas personas tarda unos segundos: se calcula en segundo plano.
        self.detener_animacion()
        for boton in (self.boton_sencilla, self.boton_hc, self.boton_calcular):
            boton.state(["disabled"])
        self.lbl_estado_grupal.configure(text="⏳ Hill Climbing está probando repartos…")
        self.raiz.configure(cursor="watch")
        salida = {}

        def trabajo():
            try:
                salida["plan"] = hill_climbing_grupal(escenario, plan_sencillo)
            except Exception as error:  # se muestra al usuario en el hilo principal
                salida["error"] = error

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()

        def comprobar():
            if hilo.is_alive():
                self.raiz.after(100, comprobar)
                return
            for boton in (self.boton_sencilla, self.boton_hc, self.boton_calcular):
                boton.state(["!disabled"])
            self.raiz.configure(cursor="")
            if "error" in salida:
                self.lbl_estado_grupal.configure(text="")
                messagebox.showerror("Error en Hill Climbing", str(salida["error"]))
                return
            self._mostrar_planes(escenario, plan_sencillo, salida["plan"], "hc")

        self.raiz.after(100, comprobar)

    def _mostrar_planes(self, escenario, plan_sencillo, plan_hc, visible: str):
        self.detener_animacion()
        self._reiniciar_barra_tiempo()
        self.escenario_grupal = escenario
        self.plan_sencillo = plan_sencillo
        self.plan_hc = plan_hc
        self._planes_intermedios = {}
        self.var_plan.set(visible)
        self.iteracion_grupal = None
        self.vista = "personas"
        self.resultado = None
        self.paso = None
        self._limpiar_pasos()
        self._actualizar_barra_controles()
        if plan_hc is None:
            self.lbl_estado_grupal.configure(
                text=f"Búsqueda sencilla: la última persona llega a los {plan_sencillo.tiempo_total:.0f} s.")
        else:
            reduccion = 100 * (1 - plan_hc.tiempo_total / plan_sencillo.tiempo_total)
            self.lbl_estado_grupal.configure(
                text=f"Hill Climbing: {plan_sencillo.tiempo_total:.0f} s → {plan_hc.tiempo_total:.0f} s "
                     f"({reduccion:.1f} % menos).")
        self._actualizar_vista_personas()

    def _plan_visible(self):
        if self.var_plan.get() == "hc" and self.plan_hc is not None:
            return self.plan_hc
        return self.plan_sencillo

    def _plan_cambiado(self):
        if self.var_plan.get() == "hc" and self.plan_hc is None:
            self.var_plan.set("sencilla")
            messagebox.showinfo("Hill Climbing", "Primero pulsa el botón «Hill Climbing» para calcular su reparto.")
        self.detener_animacion()
        self.iteracion_grupal = None
        self._reiniciar_barra_tiempo()
        self._actualizar_vista_personas()

    def _actualizar_vista_personas(self):
        self._redibujar()
        self._actualizar_tarjeta()
        self._actualizar_guia()
        self._mostrar_resultado_grupal()
        self.cuaderno.select(self.tab_guia if self.var_sencillo.get() else self.tab_escalada)

    def _plan_de_iteracion(self, indice: int):
        """Reparto (simulado) que tenía Hill Climbing tras la iteración `indice`."""
        if indice not in self._planes_intermedios:
            self._planes_intermedios[indice] = simular(self.escenario_grupal, self.plan_hc.asignaciones[indice])
        return self._planes_intermedios[indice]

    def _animar_hill_climbing_grupal(self):
        """Muestra el reparto de cada iteración y qué cambió; al final, anima a las personas."""
        if self.plan_hc is None:
            messagebox.showinfo("Hill Climbing", "Primero pulsa el botón «Hill Climbing».")
            return
        self.detener_animacion()
        self.var_plan.set("hc")
        self.iteracion_grupal = 0
        self._actualizar_vista_personas()

        def siguiente():
            if self.iteracion_grupal is not None and self.iteracion_grupal < len(self.plan_hc.asignaciones) - 1:
                self.iteracion_grupal += 1
                self._redibujar()
                self._actualizar_guia()
                self._tarea = self.raiz.after(INTERVALO_PASO_MS, siguiente)
            else:
                self.iteracion_grupal = None
                self._tarea = None
                self._redibujar()
                self._actualizar_guia()
                self._tarea = self.raiz.after(INTERVALO_PASO_MS // 2, self.simular_recorrido)

        self._tarea = self.raiz.after(INTERVALO_PASO_MS, siguiente)

    def _escribir_guia_grupal(self, texto: tk.Text):
        """Guía en lenguaje cotidiano para la evacuación de todas las personas."""
        g = self.grafo
        s, h = self.plan_sencillo, self.plan_hc
        total = len(self.escenario_grupal.personas)

        def reparto(plan):
            return ", ".join(f"{n} a {g.nodes[d]['nombre']}" for d, n in plan.personas_por_destino.items() if n)

        if h is None:
            texto.insert("end", "🚶 Búsqueda sencilla\n", "titulo")
            texto.insert("end", f"Las {total} personas tardan {s.tiempo_total:.0f} s "
                                f"(≈ {s.tiempo_total / 60:.1f} min) en llegar todas.\n")
        else:
            reduccion = 100 * (1 - h.tiempo_total / s.tiempo_total)
            texto.insert("end", f"⛰ Hill Climbing: {reduccion:.0f} % más rápido\n", ("titulo", "ok"))
            texto.insert("end", f"Las {total} personas llegan todas en {h.tiempo_total:.0f} s, frente a "
                                f"{s.tiempo_total:.0f} s con la búsqueda sencilla.\n")

        texto.insert("end", "Búsqueda sencilla: ¿qué hace?\n", "seccion")
        texto.insert("end", "Cada grupo va al punto de encuentro más cercano por el camino más corto, mientras "
                            "quede cupo. No tiene en cuenta que mucha gente junta forma colas.\n", "paso")
        texto.insert("end", f"Resultado: {reparto(s)}. Espera media en colas: {s.espera_media:.0f} s.\n", "paso")
        if s.personas_por_destino.get("P2", 0) >= 50:
            texto.insert("end", "Problema: el acceso al Área Verde es estrecho (0,3 personas por segundo, valor "
                                "supuesto), así que allí se forma una cola larga.\n", ("paso", "mal"))

        texto.insert("end", "Hill Climbing: ¿qué hace?\n", "seccion")
        texto.insert("end", "Empieza con el reparto de la búsqueda sencilla. En cada paso prueba todos los "
                            "cambios posibles (mandar un grupo a otro punto, o intercambiar dos grupos), simula "
                            "cuánto tardarían todos y aplica el cambio que más reduce el tiempo. Cuando ningún "
                            "cambio mejora, se detiene.\n", "paso")
        if h is None:
            texto.insert("end", "Pulsa «Hill Climbing» para ver cómo mejora este reparto.\n", ("paso", "suave"))
        else:
            texto.insert("end", f"Resultado: {reparto(h)}. Espera media en colas: {h.espera_media:.0f} s.\n", "paso")
            texto.insert("end", "Los cambios que hizo, uno por iteración:\n", "paso")
            for indice, (movimiento, tiempo) in enumerate(zip(h.movimientos, h.historial[1:]), 1):
                etiquetas = ("paso", "actual") if indice == self.iteracion_grupal else ("paso",)
                texto.insert("end", f"  {indice}. {self._movimiento_legible(movimiento)} → todos llegan en "
                                    f"{tiempo:.0f} s\n", etiquetas)
            texto.insert("end", f"Se detuvo porque ningún otro cambio reducía el tiempo (óptimo local). Probó "
                                f"{h.evaluaciones} repartos distintos.\n", "suave")

        texto.insert("end", "Cómo leer el mapa\n", "seccion")
        texto.insert("end", "El grosor de cada camino indica cuántas personas lo usan, y el color, a qué punto "
                            "van. Con «Ver el recorrido» se ve a cada persona moverse; los racimos junto a un "
                            "punto son personas haciendo cola. Arriba puedes cambiar entre «Búsqueda sencilla» "
                            "y «Hill Climbing».\n", "paso")
        texto.insert("end", "Importante\n", "seccion")
        texto.insert("end", "Cupos, flujos, velocidades (1,0-1,4 m/s) y tiempos de reacción (0-15 s) son "
                            "supuestos didácticos del informe, no mediciones. " + ADVERTENCIA_SEGURIDAD + "\n",
                     "aviso")
        if texto.tag_ranges("actual"):
            texto.see("actual.first")

    def _movimiento_legible(self, movimiento: str) -> str:
        """Traduce «grupo 3 (G) pasa de P2 a P1» usando los nombres de los lugares."""
        for nodo in sorted(self.grafo.nodes, key=len, reverse=True):
            if self.grafo.nodes[nodo]["tipo"] == "destino":
                movimiento = movimiento.replace(f" {nodo}", f" {self.grafo.nodes[nodo]['nombre']}")
        return movimiento[0].upper() + movimiento[1:]

    def _mostrar_resultado_grupal(self):
        s, h = self.plan_sencillo, self.plan_hc
        lineas = ["EVACUACIÓN DE TODAS LAS PERSONAS", "",
                  f"Población: {len(self.escenario_grupal.personas)} personas en "
                  f"{len(self.escenario_grupal.grupos)} grupos (semilla {SEMILLA_POR_DEFECTO})", ""]
        for plan in (s, h):
            if plan is None:
                continue
            lineas += [f"{plan.nombre}:",
                       f"  Última llegada (T): {plan.tiempo_total:.2f} s · llegada media: {plan.llegada_media:.2f} s",
                       f"  Espera media en colas: {plan.espera_media:.2f} s · distancia: {plan.distancia_total:.0f} "
                       f"persona·m",
                       "  Personas por destino: " + ", ".join(f"{d} {n}" for d, n in plan.personas_por_destino.items()),
                       f"  {plan.motivo_parada}"]
            if plan.movimientos:
                lineas.append(f"  Iteraciones: {len(plan.movimientos)} · repartos evaluados: {plan.evaluaciones}")
                lineas += [f"    {i}. {m} → T = {t:.1f} s"
                           for i, (m, t) in enumerate(zip(plan.movimientos, plan.historial[1:]), 1)]
            lineas.append("")
        lineas.append("Flujos, cupos, velocidades (1,0-1,4 m/s) y reacción (0-15 s) son supuestos del informe.")
        self._escribir(self.texto_resultados, "\n".join(lineas))

    # ------------------------------------------------------------------ animaciones
    def detener_animacion(self):
        if self._tarea is not None:
            self.raiz.after_cancel(self._tarea)
            self._tarea = None

    def animar_busqueda(self):
        """Recorre las iteraciones de Hill Climbing y, si llegó al destino, anima el recorrido."""
        if self.vista == "personas":
            self._animar_hill_climbing_grupal()
            return
        if self.resultado is None and not self.calcular():
            return
        if not self.resultado.pasos:
            return
        self.detener_animacion()
        self._ir_a_pasos()
        self.paso = 0
        self._sincronizar_paso()

        def siguiente():
            if self.paso is not None and self.paso < len(self.resultado.pasos) - 1:
                self.paso += 1
                self._sincronizar_paso()
                self._tarea = self.raiz.after(INTERVALO_PASO_MS, siguiente)
            else:
                self._tarea = None
                self._ver_final()
                if len(self.resultado.ruta) > 1:
                    self._tarea = self.raiz.after(INTERVALO_PASO_MS // 2, self.simular_recorrido)

        self._tarea = self.raiz.after(INTERVALO_PASO_MS, siguiente)

    def simular_recorrido(self):
        """Una persona avanza por la ruta a velocidad de marcha supuesta (o hasta donde se detuvo).

        Con la evacuación de todas las personas, se mueven todas según la simulación de colas.
        """
        if self.vista != "personas" and self.resultado is None and not self.calcular():
            return
        if self.vista != "personas" and len(self.resultado.ruta) < 2:
            messagebox.showinfo("Recorrido", "Hill Climbing no salió del origen: no hay recorrido que simular.")
            return
        self.detener_animacion()
        self._preparar_recorrido()
        self._fijar_tiempo(0.0)
        paso_s = INTERVALO_CUADRO_MS / 1000

        def cuadro():
            nuevo = self._tiempo + paso_s * self.var_velocidad.get()
            self._fijar_tiempo(min(nuevo, self._tiempo_total))
            self._tarea = self.raiz.after(INTERVALO_CUADRO_MS, cuadro) if nuevo < self._tiempo_total else None

        self._tarea = self.raiz.after(INTERVALO_CUADRO_MS, cuadro)

    def _preparar_recorrido(self):
        if self.vista == "personas":
            if self.iteracion_grupal is not None or self._multitud is None:
                self.iteracion_grupal = None
                self._redibujar()
                self._actualizar_guia()
            if self._multitud is None:
                self._multitud = self.ax.scatter([], [], s=22, edgecolors="white", linewidths=0.4, zorder=11)
                self._reloj = crear_reloj(self.ax)
                self._info_multitud = self.ax.text(
                    0.985, 0.915, "", transform=self.ax.transAxes, ha="right", va="top", fontsize=8.5,
                    color="white", zorder=12, bbox=dict(boxstyle="round,pad=0.4", fc=TEMA["fondo"],
                                                        ec=TEMA["borde"], alpha=0.95))
            self._tiempo_total = self._plan_visible().tiempo_total
            self.escala_tiempo.configure(to=max(self._tiempo_total, 0.1))
            return
        if self.paso is not None or self._persona is None:
            self.paso = None
            self._redibujar()
        if self._persona is None:
            color = COLOR_DESTINO.get(self.resultado.destino, TEMA["ok"])
            self._persona = crear_persona(self.ax, color)
            self._reloj = crear_reloj(self.ax)
        self._tiempo_total = sum(longitudes_tramos(self.grafo, self.resultado.ruta)) / VELOCIDAD_MARCHA_MS
        self.escala_tiempo.configure(to=max(self._tiempo_total, 0.1))

    def _fijar_tiempo(self, segundos: float):
        """Coloca a la persona en el instante indicado (usado por la animación y la barra de tiempo)."""
        if self.vista == "personas":
            self._fijar_tiempo_personas(segundos)
            return
        if self.resultado is None or len(self.resultado.ruta) < 2:
            return
        if self._persona is None:
            self._preparar_recorrido()
        self._tiempo = segundos
        x, y = posicion_en_ruta(self.grafo, self.resultado.ruta, segundos * VELOCIDAD_MARCHA_MS)
        for artista in self._persona:
            artista.set_offsets([(x, y)])
        fin = segundos >= self._tiempo_total - 1e-9
        if fin:
            sufijo = (f"  ✔ llegó a {self.resultado.destino}" if self.resultado.exito
                      else f"  ✖ detenido en {self.resultado.nodo_final}")
        else:
            sufijo = ""
        self._reloj.set_text(f"t = {segundos:6.1f} s{sufijo}")
        self._sincronizando_barra = True
        self.var_tiempo.set(segundos)
        self._sincronizando_barra = False
        self.etiqueta_tiempo.configure(text=_numero(segundos))
        self.etiqueta_vista.configure(text="Vista: recorrido simulado (tiempo de marcha, sin colas)")
        self.canvas.draw_idle()

    def _fijar_tiempo_personas(self, segundos: float):
        if self.plan_sencillo is None:
            return
        if self._multitud is None:
            self._preparar_recorrido()
        self._tiempo = segundos
        plan = self._plan_visible()
        coordenadas, colores, resumen_t = posiciones_personas(self.grafo, self.escenario_grupal, plan, segundos)
        self._multitud.set_offsets(coordenadas)
        self._multitud.set_facecolors(colores)
        total = len(self.escenario_grupal.personas)
        self._reloj.set_text(f"t = {segundos:6.1f} s" + ("  ✔ todos llegaron" if resumen_t["llegaron"] == total
                                                          else ""))
        colas = " · ".join(f"{self.grafo.nodes[n]['nombre']}: {c}" for n, c in
                           sorted(resumen_t["colas"].items(), key=lambda e: -e[1])[:2])
        self._info_multitud.set_text(f"llegaron {resumen_t['llegaron']}/{total}\n"
                                     f"en cola {resumen_t['en_cola']}" + (f"\n{colas}" if colas else ""))
        self._sincronizando_barra = True
        self.var_tiempo.set(segundos)
        self._sincronizando_barra = False
        self.etiqueta_tiempo.configure(text=_numero(segundos))
        self.etiqueta_vista.configure(text=f"Vista: {plan.nombre} · personas en movimiento")
        self.canvas.draw_idle()

    def _tiempo_movido(self, _valor):
        if self._tarea is not None or self._sincronizando_barra:
            return  # la propia animación mueve la barra
        if self.vista == "personas":
            if self.plan_sencillo is not None:
                self._preparar_recorrido()
                self._fijar_tiempo(min(self.var_tiempo.get(), self._tiempo_total))
            return
        if self.resultado is None:
            return
        if len(self.resultado.ruta) > 1:
            self._preparar_recorrido()
            self._fijar_tiempo(min(self.var_tiempo.get(), self._tiempo_total))

    # ------------------------------------------------------------------ presentación
    def _titulo(self) -> str:
        if self.vista == "personas":
            if self.iteracion_grupal is not None:
                return (f"Hill Climbing · iteración {self.iteracion_grupal} de {len(self.plan_hc.movimientos)} · "
                        f"todos llegan en {self.plan_hc.historial[self.iteracion_grupal]:.0f} s")
            plan = self._plan_visible()
            return (f"{plan.nombre}: {len(self.escenario_grupal.personas)} personas · "
                    f"todos llegan en {plan.tiempo_total:.0f} s")
        if self.var_sencillo.get():
            origen = self.grafo.nodes[self._origen()]["nombre"]
            destino = self.grafo.nodes[self._destino()]["nombre"]
            if self.resultado is not None and self.paso is not None:
                return f"Así decide la computadora · paso {self.paso + 1} de {len(self.resultado.pasos)}"
            return f"Cómo llegar desde el {origen} hasta {destino}"
        if self.resultado is None:
            return "Grafo de evacuación · seleccione origen y destino"
        r = self.resultado
        base = f"Hill Climbing: {r.origen} → {r.destino}"
        if self.paso is not None:
            return f"{base} · iteración {self.paso + 1} de {len(r.pasos)}"
        return f"{base} · {'ruta encontrada' if r.exito else r.descripcion_estado}"

    def _redibujar(self):
        sencillo = self.var_sencillo.get()
        self._persona = self._reloj = None  # ax.clear() elimina los artistas animados
        self._multitud = self._info_multitud = None
        if self.vista == "personas":
            self._redibujar_personas(sencillo)
            return
        dibujar(self.ax, self.grafo, self.resultado, self.paso, self._titulo(), sencillo=sencillo)
        if sencillo and self.resultado is not None and self.paso is not None:
            # Subtítulo sobre el mapa con la decisión de este paso, en palabras.
            self.ax.text(0.5, 0.03, textwrap.fill(explicar_paso(self.grafo, self.resultado, self.paso), 95),
                         transform=self.ax.transAxes, ha="center", va="bottom", fontsize=9, color="white",
                         zorder=12, bbox=dict(boxstyle="round,pad=0.6", fc=TEMA["fondo"], ec=TEMA["acento2"],
                                              lw=1.5, alpha=0.95))
        self.canvas.draw_idle()
        dibujar_perfil(self.ax_perfil, self.resultado, self.paso)
        dibujar_comparacion(self.ax_comparacion, self.grafo, self.comparacion)
        self.canvas_graficas.draw_idle()
        if self.resultado is None:
            self.etiqueta_vista.configure(text="")
        elif self.paso is None:
            self.etiqueta_vista.configure(text="Vista: resultado final")
        else:
            self.etiqueta_vista.configure(text=f"Vista: iteración {self.paso + 1} de {len(self.resultado.pasos)}")

    def _redibujar_personas(self, sencillo: bool):
        if self.iteracion_grupal is not None:
            plan = self._plan_de_iteracion(self.iteracion_grupal)
        else:
            plan = self._plan_visible()
        dibujar_plan(self.ax, self.grafo, self.escenario_grupal, plan, self._titulo(), sencillo=sencillo)
        if self.iteracion_grupal is not None:
            if self.iteracion_grupal == 0:
                texto = (f"Punto de partida: el reparto de la búsqueda sencilla. Todos llegan en "
                         f"{self.plan_hc.historial[0]:.0f} s.")
            else:
                anterior = self.plan_hc.historial[self.iteracion_grupal - 1]
                actual = self.plan_hc.historial[self.iteracion_grupal]
                texto = (f"Cambio {self.iteracion_grupal}: "
                         f"{self._movimiento_legible(self.plan_hc.movimientos[self.iteracion_grupal - 1])}. "
                         f"El tiempo baja de {anterior:.0f} s a {actual:.0f} s.")
            self.ax.text(0.5, 0.03, textwrap.fill(texto, 95), transform=self.ax.transAxes, ha="center",
                         va="bottom", fontsize=9.5, color="white", zorder=12,
                         bbox=dict(boxstyle="round,pad=0.6", fc=TEMA["fondo"], ec=TEMA["acento2"], lw=1.5,
                                   alpha=0.95))
        self.canvas.draw_idle()
        dibujar_evolucion_grupal(self.ax_perfil, self.plan_sencillo, self.plan_hc)
        dibujar_reparto(self.ax_comparacion, self.grafo, self.escenario_grupal, self.plan_sencillo, self.plan_hc)
        self.canvas_graficas.draw_idle()
        self.etiqueta_vista.configure(text=f"Vista: reparto de {plan.nombre or 'Hill Climbing'}")

    def _actualizar_tarjeta_personas(self):
        t = TEMA
        s, h = self.plan_sencillo, self.plan_hc
        plan = self._plan_visible()
        total = len(self.escenario_grupal.personas)
        self.lbl_escenario.configure(text=f"EVACUACIÓN DE {total} PERSONAS · {plan.nombre.upper()}")
        if h is None:
            self.lbl_estado.configure(text=f"Todos llegan en {s.tiempo_total:.0f} s", fg=t["texto"])
            self.lbl_ruta.configure(text="Pulsa «Hill Climbing» para intentar mejorarlo.", fg=t["texto_suave"])
            self.barra_estado.configure(bg=t["acento"])
        else:
            reduccion = 100 * (1 - h.tiempo_total / s.tiempo_total)
            self.lbl_estado.configure(text=f"{s.tiempo_total:.0f} s → {h.tiempo_total:.0f} s  (−{reduccion:.0f} %)",
                                      fg=t["ok"])
            self.lbl_ruta.configure(text="Búsqueda sencilla → Hill Climbing (tiempo hasta que llega el último)",
                                    fg=t["ok"])
            self.barra_estado.configure(bg=t["ok"])
        self.lbl_config.configure(text="")
        valores = {
            "distancia": ("ÚLTIMA LLEGADA", f"{plan.tiempo_total:.0f} s"),
            "tiempo": ("ESPERA MEDIA EN COLAS", f"{plan.espera_media:.0f} s"),
            "iteraciones": ("ITERACIONES HC", str(len(h.movimientos)) if h else "—"),
            "evaluados": ("REPARTOS PROBADOS", str(h.evaluaciones) if h else "—"),
        }
        for clave, (titulo, valor) in valores.items():
            self.titulos_metricas[clave][0].configure(text=titulo)
            self.metricas[clave].configure(text=valor, fg=t["texto"])

    def _actualizar_tarjeta(self):
        t = TEMA
        r = self.resultado
        if self.vista == "personas":
            self._actualizar_tarjeta_personas()
            return
        for etiqueta_titulo, titulo in self.titulos_metricas.values():
            etiqueta_titulo.configure(text=titulo)
        if self.var_sencillo.get():
            self._actualizar_tarjeta_sencilla()
            return
        if r is None:
            self.lbl_escenario.configure(text=f"ESCALADA {self._origen()} → {self._destino()}")
            self.lbl_estado.configure(text="Lista para escalar", fg=t["texto_suave"])
            self.lbl_ruta.configure(text="Pulse «Escalar · calcular ruta» o «Ver la escalada».", fg=t["texto_suave"])
            self.barra_estado.configure(bg=t["acento"])
            for valor in self.metricas.values():
                valor.configure(text="—", fg=t["texto"])
            self.lbl_config.configure(text="")
            return
        destino = self.grafo.nodes[r.destino]["nombre"] if r.destino in self.grafo else r.destino
        self.lbl_escenario.configure(text=f"ESCALADA {r.origen} → {r.destino} · {destino.upper()}")
        self.lbl_estado.configure(text=("⚑ Cumbre alcanzada" if r.exito else "✖ " + r.descripcion_estado),
                                  fg=t["ok"] if r.exito else t["mal"])
        self.barra_estado.configure(bg=t["ok"] if r.exito else t["mal"])
        self.lbl_ruta.configure(text=" → ".join(r.ruta) + ("" if r.exito else "   (sin llegar al destino)"),
                                fg=t["ok"] if r.exito else t["mal"])
        evaluados = sum(len(p.candidatos) for p in r.pasos)
        if r.exito and r.distancia_total_m is not None:
            self.metricas["distancia"].configure(text=metros(r.distancia_total_m), fg=t["ok"])
            self.metricas["tiempo"].configure(text=f"≈ {r.distancia_total_m / VELOCIDAD_MARCHA_MS:.0f} s", fg=t["ok"])
        else:
            self.metricas["distancia"].configure(text="no aplica", fg=t["mal"])
            self.metricas["tiempo"].configure(text="no aplica", fg=t["mal"])
        self.metricas["iteraciones"].configure(text=str(r.iteraciones), fg=t["texto"])
        self.metricas["evaluados"].configure(text=str(evaluados), fg=t["texto"])
        intentos = max(1, len(r.intentos))
        self.lbl_config.configure(text=f"{len(r.visitados)} nodos visitados · {intentos} "
                                       f"intento{'s' if intentos > 1 else ''} · "
                                       f"{NOMBRES_VARIANTE.get(r.variante, r.variante)}")

    def _actualizar_tarjeta_sencilla(self):
        t = TEMA
        r = self.resultado
        g = self.grafo
        origen = g.nodes[self._origen()]["nombre"]
        destino = g.nodes[self._destino()]["nombre"]
        self.lbl_escenario.configure(text=f"DESDE {origen.upper()}  →  HASTA {destino.upper()}")
        self.lbl_config.configure(text="")
        if r is None:
            self.lbl_estado.configure(text="Elige dónde estás y a dónde vas", fg=t["texto"])
            self.lbl_ruta.configure(text="Luego pulsa «Buscar ruta».", fg=t["texto_suave"])
            self.barra_estado.configure(bg=t["acento"])
            for valor in self.metricas.values():
                valor.configure(text="—", fg=t["texto"])
            return
        nombres = " → ".join(g.nodes[n]["nombre"] for n in r.ruta)
        if r.exito:
            self.lbl_estado.configure(text="✔ ¡Ruta encontrada!", fg=t["ok"])
            self.lbl_ruta.configure(text=nombres, fg=t["ok"])
            self.barra_estado.configure(bg=t["ok"])
            self.metricas["distancia"].configure(text=f"{r.distancia_total_m:.0f} m", fg=t["ok"])
            minutos = r.distancia_total_m / VELOCIDAD_MARCHA_MS / 60
            self.metricas["tiempo"].configure(text=f"≈ {max(1, round(minutos))} min", fg=t["ok"])
        else:
            self.lbl_estado.configure(text="✖ No se encontró ruta", fg=t["mal"])
            self.lbl_ruta.configure(text="Mira la explicación en la Guía, a la derecha.", fg=t["mal"])
            self.barra_estado.configure(bg=t["mal"])
            self.metricas["distancia"].configure(text="—", fg=t["mal"])
            self.metricas["tiempo"].configure(text="—", fg=t["mal"])

    def _mostrar_resultado(self):
        r = self.resultado
        g = self.grafo
        lineas = [
            f"Origen:      {etiqueta(g, r.origen) if r.origen in g else r.origen}",
            f"Destino:     {etiqueta(g, r.destino) if r.destino in g else r.destino}",
            f"Heurística:  {NOMBRES_HEURISTICA.get(r.heuristica, r.heuristica)}",
            f"Selección:   {NOMBRES_CRITERIO[r.criterio]}",
            f"Variante:    {NOMBRES_VARIANTE.get(r.variante, r.variante)}",
            "",
            f"ESTADO:      {'✔ ' if r.exito else '✖ '}{r.descripcion_estado}",
            f"Terminación: {r.motivo}",
            "",
            "Ruta obtenida:" if r.exito else "Recorrido hasta detenerse:",
        ]
        for i, nodo in enumerate(r.ruta, 1):
            lineas.append(f"  {i}. {etiqueta(g, nodo)}")
        if r.exito and r.distancia_total_m is not None:
            lineas.append(f"\nDistancia total: {metros(r.distancia_total_m)}")
            lineas.append("  (suma de longitudes medidas por el grupo sobre OpenStreetMap)")
            lineas.append(f"Tiempo de marcha: ≈ {r.distancia_total_m / VELOCIDAD_MARCHA_MS:.0f} s a "
                          f"{_numero(VELOCIDAD_MARCHA_MS)} m/s (supuesto; sin colas ni reacción)")
        else:
            lineas.append("\nDistancia total: no aplica (no se alcanzó el destino)")
        lineas += [
            f"Nodos visitados: {len(r.visitados)}  ({', '.join(r.visitados) or '—'})",
            f"Iteraciones:     {r.iteraciones}",
        ]
        if len(r.intentos) > 1:
            lineas.append(f"\nIntentos (variante estocástica, {len(r.intentos)}):")
            lineas += [f"  {t}" for t in r.intentos]

        if self.comparacion:
            lineas.append("\nMisma configuración hacia cada punto de encuentro:")
            for c in self.comparacion:
                estado = (f"✔ {' → '.join(c.ruta)} ({metros(c.distancia_total_m)})" if c.exito
                          else f"✖ {c.descripcion_estado} (se detuvo en {c.nodo_final})")
                lineas.append(f"  {c.destino}: {estado}")
            lineas.append("  (No indica cuál es el punto más seguro.)")

        lineas.append("\nObservaciones:")
        if not r.exito and r.estado != "nodo_inexistente":
            if existe_camino_transitable(g, r.origen, r.destino):
                lineas.append("  • Diagnóstico: SÍ existe un camino transitable en el grafo, pero Hill Climbing "
                              "no lo encontró. Es la limitación de la búsqueda local (óptimo local o callejón sin "
                              "salida). Pruebe otra heurística, otro criterio o la variante estocástica. No se "
                              "recurre a otro algoritmo para completar la ruta.")
            else:
                lineas.append("  • Diagnóstico: NO existe ningún camino transitable hacia este destino con las "
                              "conexiones habilitadas. Ninguna búsqueda podría encontrar una ruta.")
            lineas.append("    (El diagnóstico usa nx.has_path solo para explicar el fallo; no forma parte de "
                          "Hill Climbing.)")
        lineas += [
            "  • Las posiciones de G, H, S, K, J y L son estimadas (calibradas con P1-P3); la heurística es "
            "aproximada.",
            "  • Ruta modelada, no verificada por la Unidad de Seguridad. Un punto más cercano no es "
            "necesariamente más seguro.",
            "  • Cupos y flujos del informe son supuestos didácticos y no intervienen en esta búsqueda de ruta.",
        ]
        self._escribir(self.texto_resultados, "\n".join(lineas))

    def _limpiar_pasos(self):
        self.arbol_pasos.delete(*self.arbol_pasos.get_children())
        self._escribir(self.texto_motivo, "")

    def _llenar_pasos(self):
        self._limpiar_pasos()
        for indice, p in enumerate(self.resultado.pasos):
            padre = self.arbol_pasos.insert(
                "", "end", iid=f"paso{indice}", text=str(p.iteracion), open=True, tags=("iteracion",),
                values=(f"{p.nodo_actual} ({p.h_actual:.1f})", "→ " + (p.seleccionado or "ninguno"), "", "", "",
                        "avanza" if p.seleccionado else "SE DETIENE"))
            if not p.candidatos:
                self.arbol_pasos.insert(padre, "end", text="", values=("", "—", "", "", "", "sin vecinos"),
                                        tags=("descartado",))
            for c in p.candidatos:
                elegido = c.nodo == p.seleccionado
                self.arbol_pasos.insert(
                    padre, "end", text="",
                    values=("", c.nodo, f"{c.longitud_m:.1f}" if c.longitud_m is not None else "—",
                            f"{c.h:.1f}", f"{c.valor:.1f}", "ELEGIDO" if elegido else c.estado),
                    tags=("elegido",) if elegido else (() if c.estado == "admisible" else ("descartado",)))

    def _paso_seleccionado(self, _evento=None):
        seleccion = self.arbol_pasos.selection()
        if not seleccion or self.resultado is None:
            return
        item = seleccion[0]
        padre = self.arbol_pasos.parent(item) or item
        indice = int(padre.replace("paso", ""))
        if indice != self.paso:
            self.paso = indice
            self._redibujar()
        self._escribir(self.texto_motivo, self._texto_paso(indice))

    def _texto_paso(self, indice: int) -> str:
        p = self.resultado.pasos[indice]
        lineas = [f"Iteración {p.iteracion}. Nodo actual {p.nodo_actual}, h = {p.h_actual:.1f} m."]
        if p.candidatos:
            lineas.append("Vecinos: " + "; ".join(
                f"{c.nodo} (h={c.h:.1f}, f={c.valor:.1f}, {c.estado})" for c in p.candidatos) + ".")
        lineas.append(("Decisión: " if p.seleccionado else "Terminación: ") + p.motivo)
        return "\n".join(lineas)

    def _sincronizar_paso(self):
        item = f"paso{self.paso}"
        if self.arbol_pasos.exists(item):
            self.arbol_pasos.selection_set(item)
            self.arbol_pasos.see(item)
        self._redibujar()
        self._escribir(self.texto_motivo, self._texto_paso(self.paso))
        if self.var_sencillo.get():
            self._actualizar_guia()

    def _mover_paso(self, delta: int):
        if self.resultado is None or not self.resultado.pasos:
            return
        self.detener_animacion()
        actual = self.paso if self.paso is not None else (-1 if delta > 0 else len(self.resultado.pasos))
        self.paso = max(0, min(len(self.resultado.pasos) - 1, actual + delta))
        self._ir_a_pasos()
        self._sincronizar_paso()

    def _ver_final(self):
        self.paso = None
        self.arbol_pasos.selection_remove(self.arbol_pasos.selection())
        self._redibujar()
        if self.var_sencillo.get():
            self._actualizar_guia()

    def _mostrar_datos_modelo(self):
        g = self.grafo
        cal = g.graph["calibracion"]
        lineas = ["NODOS (x este, y norte en metros locales)", ""]
        for n, d in g.nodes(data=True):
            lineas.append(f"{n:<3}{d['nombre']}")
            lineas.append(f"   tipo {d['tipo']} · x={d['x']:.1f} y={d['y']:.1f} · posición {d['posicion'].upper()}")
            lineas.append(f"   lat {d['lat']:.5f}, lon {d['lon']:.5f}" +
                          ("" if d["posicion"] == "documentada" else " (estimada)"))
        lineas += ["", "ARISTAS (dirigidas; longitudes medidas del informe, sección 4)", ""]
        for u, v, d in g.edges(data=True):
            estado = "transitable" if d["transitable"] else "BLOQUEADA"
            lineas.append(f"{u:>2} → {v:<3} {metros(d['longitud_m']):>9} · flujo supuesto "
                          f"{d['flujo_supuesto']} p/s · {estado}")
        lineas += [
            "", "CALIBRACIÓN píxel → metros",
            f"   puntos de control P1, P2, P3 · {cal.metros_por_pixel:.4f} m/px · rotación "
            f"{cal.rotacion_grados:.2f}° · error RMS {cal.error_rms_m:.2f} m",
            "   Comprobación independiente: G y H caen sobre el edificio «Bloque C y D» de OpenStreetMap.",
            "", "MAPA BASE",
            "   © colaboradores de OpenStreetMap (ODbL), copia local en datos/campus_osm.json.",
            "", "DATOS PENDIENTES DE VERIFICACIÓN",
            "   • Coordenadas reales de G, H, S, K, J y L (hoy estimadas).",
            "   • Trazado real de los senderos (los tramos se dibujan rectos).",
            "   • Vigencia y seguridad de P1-P3 como puntos de encuentro oficiales.",
            "   • Restricciones de sentido y estado de los accesos ante cada amenaza.",
            "   • Fotografías de G, H y de los puntos de evacuación (no recibidas).",
        ]
        self._escribir(self.texto_datos, "\n".join(lineas))


def activar_dpi():
    """En Windows con escalado de pantalla, evita que el sistema emborrone y recorte la ventana."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass  # otros sistemas o versiones antiguas de Windows


def ejecutar():
    activar_dpi()
    raiz = tk.Tk()
    AplicacionEvacuacion(raiz)
    raiz.mainloop()
