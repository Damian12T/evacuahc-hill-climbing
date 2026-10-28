# Evacuación de los bloques G y H mediante Hill Climbing

Aplicación de escritorio en Python que busca una ruta de evacuación desde los bloques G y H de la
Universidad de las Fuerzas Armadas ESPE (campus Sangolquí) hasta un punto de encuentro, usando
**Hill Climbing** sobre un grafo de **NetworkX** y visualizándola con **Matplotlib** en una interfaz
**Tkinter**.

> **Prototipo académico.** Las rutas son un modelo aproximado y no han sido validadas por la Unidad de
> Seguridad de la ESPE. No es un sistema de evacuación certificado. En una emergencia real siga las
> instrucciones oficiales y la señalización del campus.

---

## 1. Problema y objetivo

Las personas de los bloques G y H deben llegar a un punto de encuentro. G y H no tienen puerta propia:
se sale por el interior hasta la puerta sur S del hall central y, desde allí, por senderos hacia tres
destinos modelados (Plaza ESPE, Área Verde ESPE y Canchas deportivas).

**Objetivo general:** implementar y demostrar una búsqueda de ruta basada en Hill Climbing sobre el
grafo documentado y mostrar con transparencia tanto sus aciertos como sus bloqueos.

## 2. Tecnologías

| Tecnología | Uso |
|---|---|
| Python 3 (probado con 3.13) | Lenguaje |
| NetworkX | Grafo dirigido del campus (`DiGraph`), atributos de nodos y aristas |
| Matplotlib | Dibujo del grafo, la ruta y cada iteración; integrado en Tkinter |
| Tkinter / ttk | Interfaz de escritorio |
| NumPy | Ajuste por mínimos cuadrados de la calibración (dependencia de Matplotlib) |

## 3. Fuentes y auditoría de datos

Materiales revisados: informe *Sistema inteligente de optimización de rutas de evacuación para los
bloques G y H mediante Búsqueda Tabú* (Flores, Bolaños y Gómez, 2026), croquis «Plano Campus ESPE»
(2017), mapa histórico de puntos de encuentro (Toulkeridis et al., 2019) y dos capturas del simulador
basado en Tabú.

### Datos reales utilizados

* **Topología:** 9 nodos y 8 aristas dirigidas (informe, sección 4).
* **Longitudes de las aristas** en metros, medidas sobre OpenStreetMap (informe, sección 4). Se comprobó que
  suman exactamente los recorridos completos del informe (G→P2 159,8 m; G→P1 229,8 m; G→P3 341,7 m;
  H→P2 135,8 m; H→P1 205,8 m; H→P3 317,7 m).
* **Coordenadas de P1, P2 y P3** (informe, sección 3).
* **Salida obligatoria por S** desde G y H (informe, sección 3).
* **Escenario con J → P1 bloqueado** (informe, sección 6 y anexo C).

### Datos estimados (deben verificarse)

* **Posiciones de G, H, S, K, J y L.** El informe solo da coordenadas geográficas de los destinos. Se
  midió la posición en píxeles de los nueve nodos en la captura del simulador (que reproduce la
  figura 2 del informe) y, con P1-P3 como puntos de control, se ajustó una transformación de
  semejanza píxel → metros. El ajuste es muy consistente (0,351 m/px, rotación −0,23°, error RMS
  0,28 m), lo que confirma que la figura está a escala y con el norte arriba, pero las posiciones de
  los demás nodos siguen siendo **estimaciones de figura**, no mediciones.
* **Trazado de los senderos:** se dibujan como segmentos rectos (plano esquemático).

### Datos no utilizados en la búsqueda

* **Flujos (personas/s) y cupos de los destinos.** Son supuestos didácticos del informe para su
  simulación de colas. Esta aplicación busca la ruta de una persona o grupo, no reparte población,
  así que se muestran solo como información.

### Faltantes y contradicciones detectadas

* No se recibieron **fotografías de los bloques G y H ni de los puntos de evacuación**. El mapa
  histórico se adjuntó dos veces (imágenes idénticas).
* El **croquis** no identifica G, H ni P1-P3, y su leyenda indica «escala 1:200», que no corresponde
  a un plano de todo el campus. Por eso **no se superpone al grafo**: se muestra aparte.
* El **mapa histórico** muestra iconos de punto de encuentro sin coordenadas, y la guía institucional
  de 2019 habla de 14 puntos. No se puede vincular ningún icono con P1-P3 ni confirmar su vigencia.
* El informe ubica G y H en el edificio que OpenStreetMap llama «Bloque C y D». La identificación es
  del informe y ningún documento institucional la confirma.
* En la figura del informe, los tramos S → J y S → L parecen compartir corredor, pero el modelo los
  trata como aristas independientes. Se respeta el modelo documentado.
* Los destinos **no son necesariamente puntos de encuentro oficiales**: el propio informe aclara que
  su caso no reproduce un plan oficial de evacuación.

## 4. Modelo del grafo

* `nx.DiGraph`: el informe define las aristas como dirigidas (sentido de evacuación).
* **Nodos:** `id`, `nombre`, `tipo` (origen, salida, acceso, destino), `x`, `y` (metros locales,
  este/norte), `lat`, `lon`, `posicion` (documentada o estimada), `descripcion`, `fuente`,
  `cupo_supuesto` y `salida_obligatoria`.
* **Aristas:** `longitud_m`, `flujo_supuesto`, `tipo` (interior, exterior, acceso final),
  `descripcion` y `transitable`.
* Una arista bloqueada **se conserva** con `transitable=False` para dibujarla discontinua en rojo,
  pero Hill Climbing nunca la considera vecina.

```
G ──44,6──┐
          ├─> S ──57,0──> K ──58,2──> P2 Área Verde
H ──20,6──┘   ├──143,1──> J ──42,1──> P1 Plaza
              └──199,1──> L ──98,0──> P3 Canchas
```

## 5. Hill Climbing implementado

**Estado:** el nodo actual. **Valor del estado:** `h(n)`, la distancia estimada en metros hasta el
destino (menor es mejor).

En cada iteración (`hill_climbing.py`):

1. Se comprueba que el origen y el destino existen.
2. Se obtienen los vecinos por aristas **transitables**.
3. Cada vecino se clasifica como *ya visitado*, *no mejora h* o **admisible** (`h(v) < h(actual)`).
4. Si no hay vecinos, la búsqueda termina por **callejón sin salida**. Si ninguno es admisible,
   termina por **óptimo local**.
5. Entre los admisibles se elige el de menor `f(v)`, según el criterio seleccionado:
   * **Solo heurística:** `f(v) = h(v)` (escalada voraz clásica).
   * **Tramo + heurística:** `f(v) = d(actual, v) + h(v)`, donde `d` es la longitud medida del
     tramo. Penaliza los tramos largos que solo *parecen* acercarse al destino. Ambos términos
     están en metros. El costo acumulado completo no se suma porque es igual para todos los vecinos
     de un mismo nodo y no cambiaría la elección.
6. Se registra cada iteración: nodo actual, vecinos, `h`, `f`, estado de cada vecino, elegido y motivo.
7. Los empates se resuelven por menor `f`, luego menor `h` y luego identificador (determinista).

No hay retroceso ni memoria de movimientos prohibidos. El registro de visitados es una protección
explícita contra ciclos. Además, como `h` decrece estrictamente, ningún nodo puede repetirse.

### Heurísticas

* **Euclidiana con salida obligatoria (por defecto):** para G y H, `h(n) = |n − S| + |S − destino|`.
  El informe establece que estos bloques solo se abandonan por S. La línea recta desde un bloque
  atraviesa muros. Sigue siendo una cota inferior del recorrido.
* **Euclidiana pura:** distancia en línea recta. Se mantiene para demostrar el óptimo local: desde H,
  la puerta S queda *más lejos* de todos los destinos que el propio bloque, así que Hill Climbing no
  da ni el primer paso.

### Variantes (ambas son Hill Climbing)

* **Máxima pendiente (determinista):** elige siempre el mejor admisible.
* **Estocástico con reinicios:** elige al azar entre los admisibles, con probabilidad proporcional a
  la mejora `h(actual) − h(v)`. Si queda bloqueado, reinicia desde el origen con nuevas elecciones,
  hasta *N* reinicios y con semilla reproducible (*stochastic* y *random-restart hill climbing*,
  Russell y Norvig). Cada movimiento sigue exigiendo una mejora estricta de `h`: nunca acepta
  empeorar, no guarda memoria tabú y no usa otro algoritmo.

El diagnóstico «¿existe un camino?» (`nx.has_path`) solo se usa para **explicar** un fallo. Nunca
construye ni sustituye la ruta.

### Resultados obtenidos con los datos actuales

Heurística con salida obligatoria. G y H producen la misma decisión, porque ambos salen por S.

| Destino | Máx. pendiente, tramo + h | Máx. pendiente, solo h | Estocástico (semilla 0, 10 reinicios) |
|---|---|---|---|
| P1 Plaza | ✖ callejón en P2 (elige K) | ✖ óptimo local en L | ✔ G/H → S → J → P1 (2.º intento) |
| P2 Área Verde | ✔ → S → K → P2 | ✖ óptimo local en J | ✔ → S → K → P2 |
| P3 Canchas | ✖ callejón en P2 (elige K) | ✔ → S → L → P3 | ✔ → S → L → P3 |

Con J → P1 bloqueada **no existe camino a P1**, y todas las variantes lo informan sin forzar una ruta.
Con la heurística euclidiana pura, H queda bloqueado en el primer paso para cualquier destino.

Estos casos son la limitación esperada de una búsqueda local: Hill Climbing **no garantiza** encontrar
una ruta ni la más corta. Las decisiones dependen de posiciones estimadas: en S, `h(L) = 38,5 m`
frente a `h(J) = 42,1 m` hacia P1. Esa diferencia está dentro del margen de error de la estimación.

## 6. Diferencias con la Búsqueda Tabú del simulador de referencia

| | Simulador de referencia (Tabú) | Esta aplicación (Hill Climbing) |
|---|---|---|
| Decisión | Asignación conjunta de grupos de personas a rutas | Ruta nodo a nodo para un origen y un destino |
| Rutas | Fijadas con `shortest_path` de NetworkX | Construidas por la búsqueda local |
| Objetivo | Minimizar el tiempo de la última llegada (colas, flujos, cupos) | Reducir la distancia estimada al destino |
| Memoria | Lista tabú, aspiración, acepta empeorar | Sin memoria; solo acepta mejoras |
| Bloqueos locales | Los evita con la memoria y los movimientos que empeoran | Se informan; opcionalmente, reinicio aleatorio |

Del simulador solo se reutilizó la **referencia visual**: la posición de los nodos en su captura y la
idea de mostrar escenario, indicadores y bloqueos. No se copió su código ni su lógica.

Hill Climbing se eligió por requisito de la práctica y porque hace visible cada decisión heurística,
incluidos sus fallos. Eso tiene valor didáctico para contrastarlo con métodos con memoria como Tabú.

## 7. Interfaz

### Evacuación de todas las personas: búsqueda sencilla frente a Hill Climbing

En la sección **«👥 Evacuar a todas las personas»** se escribe cuántas personas hay en el Bloque G y en
el Bloque H. Por defecto son 80 y 60, la población estándar del informe. Hay dos botones:

* **🚶 Búsqueda sencilla:** cada grupo de 10 personas va al punto de encuentro más cercano por el
  camino más corto, mientras quede cupo (primero G y luego H). No tiene en cuenta las colas.
* **⛰ Hill Climbing:** parte de ese reparto y, en cada iteración, prueba todos los vecinos (mover un
  grupo a otro punto o intercambiar los puntos de dos grupos de distinto bloque o tamaño). Simula
  cada uno y aplica el que más reduce el tiempo hasta la última llegada, con la llegada media como
  desempate. Se detiene en un óptimo local, cuando ningún vecino mejora. No acepta empeorar ni usa
  memoria tabú. Se calcula en segundo plano para no congelar la ventana.

El tiempo se calcula con el **modelo de colas del informe (sección 6)**. Una persona que llega a un
tramo en `a` entra en `b = max(a, q)`, la siguiente admisión pasa a `q = b + 1/c` y sale en
`b + d/v`. Flujos, cupos (Plaza 100, Área Verde 100, Canchas 140), velocidades (1,0-1,4 m/s) y
reacción (0-15 s) son **supuestos didácticos** del informe. La población se genera con la semilla 0.

El mapa muestra cada camino con un grosor proporcional a las personas que lo usan y cuántas llegan a
cada punto frente a su cupo. **▲ Ver el recorrido** anima a todas las personas, con contador de
llegadas y colas. **▶ Ver cómo decide** recorre los cambios de Hill Climbing uno a uno. Arriba del
mapa se alterna entre los dos repartos.

Comprobación con el informe (80 + 60 personas, simultánea, semilla 0):

| | Informe | Esta aplicación |
|---|---|---|
| Asignación inicial / búsqueda sencilla | P1 40 · P2 100 · P3 0, T = 449,83 s | P1 40 · P2 100 · P3 0, T = 449,8 s |
| Optimización | Búsqueda Tabú: P1 90 · P2 50, T = 292,25 s | Hill Climbing: P1 90 · P2 50, T = 293,8 s (−35 %), 5 iteraciones |
| Acceso a P1 bloqueado | Tabú: P2 70 · P3 70, T = 344,87 s | Hill Climbing: P2 70 · P3 70, T = 344,9 s |

Hill Climbing queda muy cerca de Tabú en esta red pequeña, pero no garantiza el óptimo global. Con
más personas mejora menos, porque los cupos dejan poco margen para redistribuir: con 280 personas,
468 s → 373 s (−20 %).

### Modo sencillo (por defecto) y modo experto

La aplicación arranca en **modo sencillo**, pensado para quien no conoce el algoritmo. Se cambia de
modo con el selector de la cabecera.

| | Modo sencillo | Modo experto |
|---|---|---|
| Controles | Dos preguntas con botones grandes: «¿Dónde estás?» y «¿A dónde quieres llegar?»; casillas «intentar varias veces» y «acceso a la Plaza cerrado» | Heurística, criterio, variante, reinicios, semilla y bloqueo de cada conexión |
| Configuración de búsqueda | Fija: heurística con salida por S, tramo + heurística y, si se marca «intentar varias veces», variante estocástica con 10 reinicios (semilla 0) | La que elija el usuario |
| Mapa | Sin isolíneas ni fórmulas; «ESTÁS AQUÍ», «⚑ PUNTO DE ENCUENTRO», tramos de la ruta numerados ①②③ y nombres de los lugares | Isolíneas de `h`, valores `h` y `f`, flujos y cupos supuestos |
| Paso a paso | Cada opción marcada como «✔ va por aquí», «✕ aleja» o «acerca, pero es peor», con un subtítulo que explica la decisión en una frase | Tabla de iteraciones con `h(v)`, `f(v)` y estado |
| Panel derecho | Pestaña **📋 Guía**: resultado, indicaciones tipo GPS («1. Sal del Bloque H por el interior… (≈ 21 m)»), «¿Por qué no llegó?», «¿Cómo decidió la computadora?», una analogía de Hill Climbing y el aviso de seguridad | Guía, perfil de escalada, pasos, detalle y datos del modelo |

Todos los textos del modo sencillo se generan en `explicacion.py` a partir del resultado real de la
búsqueda: no se inventan decisiones.

### Identidad visual

La aplicación se llama **EvacuaHC** (el nombre se cambia en `configuracion.py`). Su identidad
visual parte de la metáfora de Hill Climbing: el punto de encuentro es la **cumbre**, la heurística
`h` se dibuja como **curvas de nivel** sobre el mapa y la búsqueda se presenta como una **escalada**.
La paleta es propia (índigo, violeta y ámbar), distinta de la del simulador de referencia. Tiene
tres columnas:

* **Izquierda, configuración en tres pasos:** ① origen (G/H) y punto de encuentro (P1-P3);
  ② estrategia (heurística, criterio de selección, variante, reinicios y semilla); ③ escenario
  (casillas para bloquear conexiones y botón del escenario del informe). Debajo, el botón principal
  *Escalar · calcular ruta*, y *Ver grafo completo*, *Croquis y mapas*, *Guardar figura* y
  *Reiniciar*.
* **Centro, franja de indicadores y mapa:**
  * **Franja de indicadores:** estado (⚑ cumbre alcanzada o ✖ motivo del bloqueo), ruta, distancia,
    tiempo a pie, iteraciones y vecinos evaluados.
  * **Mapa base real de OpenStreetMap:** edificios, áreas verdes, canchas, senderos y vías, con el
    grafo encima.
  * **Isolíneas de `h`:** curvas de nivel cada 25 m de distancia al destino elegido, con resplandor
    en la cumbre. Muestran por qué el algoritmo prefiere un vecino: solo se mueve a una curva más
    interior.
  * **Colores de los nodos:** origen magenta; P1 coral, P2 celeste y P3 dorado.
  * **Rutas y tramos:** la ruta encontrada va en verde con resplandor; un recorrido que se detuvo,
    en ámbar con «✕ se detiene aquí»; los tramos bloqueados, en rojo discontinuo.
  * **Referencias del mapa:** simbología, escala de 50 m (aproximada), norte y atribución.
  * **▶ Ver la escalada:** recorre las iteraciones. En cada una marca el nodo actual y muestra
    junto a cada vecino `h`, `f` y si fue elegido o descartado. Si llega al destino, continúa con la
    evacuación simulada.
  * **▲ Simular evacuación:** un «escalador» (triángulo) avanza por la ruta a 1,2 m/s, la velocidad
    media que supone el informe. Un reloj `t = … s` acompaña el avance, que se controla con la barra
    de tiempo y la de velocidad. Solo es tiempo de marcha: no hay colas ni tiempo de reacción.
  * **◀ Paso / Paso ▶ / Resultado final:** navegación manual por las iteraciones.
* **Derecha, pestañas:**
  * **⛰ Escalada:**
    * **Perfil de escalada:** altura ganada `h(origen) − h(n)` en cada iteración. La cumbre es la
      línea discontinua. Si la búsqueda se queda por debajo, aparece como **«cima falsa (óptimo
      local)»** o **«callejón sin salida»**. Los vecinos evaluados se marcan a la altura que habrían
      dado.
    * **Metros escalados hacia cada cumbre:** misma configuración hacia P1, P2 y P3. Una barra
      rayada indica que no llegó. **No** recomienda el punto «más seguro».
  * **Pasos:** tabla de iteraciones y vecinos. Al seleccionar una fila se dibuja esa iteración.
  * **Detalle:** informe textual completo con diagnóstico.
  * **Datos del modelo:** coordenadas (documentadas o estimadas), aristas, calibración y pendientes.

El mapa base también sirve de **comprobación independiente** de la calibración: G y H caen sobre las
alas del edificio «Bloque C y D», P2 dentro del «Area Verde ESPE» y P3 sobre las canchas.

## 8. Estructura del proyecto

```
evacuacion_universitaria/
├── main.py               entrada: interfaz, --evidencias, --autoprueba
├── interfaz.py           ventana Tkinter y conexión con algoritmo y figura
├── hill_climbing.py      algoritmo, heurísticas y variantes
├── grafo_universidad.py  carga de datos, calibración y construcción del grafo
├── visualizacion.py      dibujo con Matplotlib: mapa, grafo, pasos, animación y gráficas
├── mapa_osm.py           mapa base de OpenStreetMap (copia local y descarga opcional)
├── explicacion.py        textos en lenguaje sencillo (indicaciones, decisiones, fallos)
├── evacuacion_grupal.py  personas por bloque, simulación de colas, búsqueda sencilla y Hill Climbing de reparto
├── modelos.py            dataclasses del registro de búsqueda
├── configuracion.py      rutas, constantes, colores y textos
├── requirements.txt
├── datos/                campus.json, campus_osm.json y README de procedencia (las imágenes de terceros no se incluyen)
├── tests/                test_hill_climbing.py (sintético), test_grafo.py y test_explicacion.py (datos reales)
└── evidencias/           salidas generadas por --evidencias (no versionadas)
```

## 9. Instalación y ejecución (Windows)

```powershell
cd evacuahc-hill-climbing
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v    # pruebas
python main.py                             # aplicación
python main.py --evidencias                # regenera figuras y registro en evidencias/
python main.py --autoprueba                # abre la ventana, la prueba, captura y se cierra
python mapa_osm.py --descargar             # opcional: vuelve a descargar el mapa base (requiere Internet)
```

La aplicación funciona sin conexión: usa la copia local `datos/campus_osm.json`. Si ese archivo
falta, el grafo se dibuja igual, pero sin mapa de fondo.

Para modificar nodos, conexiones o coordenadas, consulte [datos/README.md](../datos/README.md).

## 10. Pruebas

Hay 44 pruebas en total, y todas pasaron en la última ejecución (`python -m unittest discover -s tests -v`).
`tests/test_evacuacion_grupal.py` comprueba:

* que se conservan todas las personas y se respetan los cupos;
* que la búsqueda sencilla coincide con el informe;
* que Hill Climbing solo mejora y termina en un óptimo local real (ningún vecino es mejor);
* que se respeta el intervalo mínimo `1/c` de cada tramo;
* que nunca se usa un tramo bloqueado;
* que se rechazan las entradas inválidas y que el resultado es reproducible.
`tests/test_explicacion.py` comprueba que las indicaciones y explicaciones del modo sencillo
coinciden con lo que hizo la búsqueda.

* `tests/test_hill_climbing.py` usa **grafos sintéticos** con coordenadas inventadas a propósito. No
  representan el campus. Cubren: origen y destino inexistentes, criterio inválido, origen igual al
  destino, grafo sin conexiones, destino desconectado, óptimo local con camino existente, varios
  vecinos (elección y registro), criterio tramo + h, prevención de ciclos, límite de iteraciones,
  arista no transitable, determinismo, heurística con salida obligatoria y variante estocástica
  (supera un callejón, es reproducible, solo elige mejoras y agota los reinicios).
* `tests/test_grafo.py` usa los **datos reales**: topología, longitudes frente al informe, calibración,
  bloqueos, rutas válidas desde G y H, óptimo local con euclidiana pura, que J → P1 nunca se use
  bloqueada, que la ruta sea una secuencia de aristas transitables y que la figura resalte los tramos
  correctos.

`python main.py --autoprueba` abrió la ventana real, calculó H → P2, recorrió los pasos, simuló el
recorrido (113,2 s de marcha), aplicó el escenario bloqueado y abrió la ventana del croquis. Las
capturas seleccionadas están en `docs/screenshots/`.

## 11. Limitaciones

* Hill Climbing es una búsqueda local: puede detenerse en un óptimo local o en un callejón aunque
  exista un camino, y no garantiza la ruta más corta.
* Las posiciones de 6 de los 9 nodos son estimadas, y la heurística hereda ese error.
* La red es pequeña: hay una sola ruta por par origen-destino, como reconoce el propio informe.
* No se modelan colas, densidad, movilidad reducida, escaleras, anchura física ni la evolución del
  peligro. Los bloqueos son escenarios fijos definidos por el usuario.
* La transitabilidad real puede cambiar por sismos, incendios, lahares o escombros.

## 12. Seguridad y validación

* Una ruta calculada **no** se marca como segura. Es una ruta *modelada*, no *verificada*.
* La cercanía no implica seguridad: la idoneidad de cada punto de encuentro debe validarla la Unidad
  de Seguridad de la ESPE según la amenaza.
* Antes de cualquier uso real hacen falta planos vigentes, coordenadas medidas de todos los nodos,
  confirmación de los puntos de encuentro oficiales y validación institucional de los recorridos.
