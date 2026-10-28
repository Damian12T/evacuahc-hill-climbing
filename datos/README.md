# Datos del modelo

| Archivo | Contenido | Uso |
|---|---|---|
| `campus.json` | Nodos, aristas y escenarios del grafo | Fuente única de datos de la aplicación |
| `campus_osm.json` | Edificios, áreas verdes, canchas, senderos y vías del sector (© colaboradores de OpenStreetMap, ODbL; API Overpass, 26/10/2026) | Solo mapa de fondo; no interviene en la búsqueda |
| `croquis_campus_espe.png` *(no incluido)* | "Plano Campus ESPE" (S. Valladares, 10/01/2017) | Solo visualización (ventana «Ver croquis y mapas») |
| `mapa_puntos_encuentro_2019.png` *(no incluido)* | Mapa histórico de puntos de encuentro (Toulkeridis et al., 2019, fig. 52) | Solo visualización |
| `referencia_simulador_tabu.png` *(no incluido)* | Captura del simulador anterior (Búsqueda Tabú) | Medición de las posiciones en píxeles de los nodos |

> **Imágenes de terceros:** las tres imágenes marcadas como *no incluidas* pertenecen a sus autores y no se
> redistribuyen en este repositorio. La aplicación funciona sin ellas: la ventana «Croquis y mapas» muestra un aviso
> en su lugar. Si dispone de ellas, colóquelas en `datos/` con el nombre indicado.

## Procedencia de cada dato de `campus.json`

| Dato | Estado | Fuente |
|---|---|---|
| Nodos G, H, S, K, J, L, P1, P2, P3 y sus nombres | Documentado | Informe, secciones 3 y 4 |
| 8 aristas dirigidas y sus longitudes en metros | Documentado (medido sobre OSM) | Informe, sección 4 |
| Flujo por arista y cupo de P1-P3 | Supuesto didáctico (no se usa en la búsqueda) | Informe, sección 4 |
| Lat/lon de P1, P2, P3 | Documentado | Informe, sección 3 |
| Posición en píxeles de los 9 nodos | Medido en `referencia_simulador_tabu.png` | Panel izquierdo, imagen de 1999 × 1125 px |
| Posición en metros de G, H, S, K, J, L | **Estimada** | Calibración con P1-P3 (error RMS ≈ 0,3 m) |
| Salida obligatoria de G y H por S | Documentado | Informe, sección 3 |
| Escenario «J → P1 bloqueado» | Documentado | Informe, sección 6 y anexo C |

## Cómo sustituir o ampliar datos

* **Coordenadas verificadas de un nodo:** añada `"lat"` y `"lon"` al nodo. La aplicación usará esas
  coordenadas en lugar de la estimación. Con tres o más nodos con lat/lon, la calibración usa todos
  ellos como puntos de control. Conserve `"px"`, que se sigue usando para calibrar los nodos que no
  tienen coordenadas.
* **Nuevo nodo:** añada un objeto con `id`, `nombre`, `tipo` (`origen`, `salida`, `acceso` o `destino`),
  `px` (posición en la imagen de referencia) y, si las conoce, `lat`/`lon`.
* **Nueva conexión:** añada `{"origen", "destino", "longitud_m"}` en `aristas`. Las aristas son
  dirigidas (sentido de evacuación). Si un tramo puede recorrerse en ambos sentidos y eso es
  relevante, añada las dos direcciones.
* **Nuevo escenario de bloqueo:** añada una entrada en `escenarios` con la lista `bloqueadas`.

Después de cualquier cambio, ejecute `python -m unittest discover -s tests -v`. Algunas pruebas de
`test_grafo.py` comprueban cifras del informe (9 nodos, 8 aristas, longitudes de los recorridos) y
fallarán a propósito si el modelo cambia: actualícelas junto con los datos.
