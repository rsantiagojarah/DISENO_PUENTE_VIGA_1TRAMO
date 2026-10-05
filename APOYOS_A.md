# Dimensionamiento de apoyos de neopreno - Método A

`diseno-apoyos-A` dimensiona un apoyo rectangular zunchado sin agujeros ni PTFE para un puente de concreto armado construido en sitio. Incluye geometría, movimientos, compresión, capas, zunchos por servicio y fatiga, estabilidad, deflexiones y fricción. No dimensiona ni verifica el pedestal ni las conexiones sísmicas externas. La fricción insuficiente se informa expresamente.

## Ejecución

```powershell
diseno-apoyos-A
diseno-apoyos-A output modelo_apoyos_A.yaml
diseno-apoyos-A input modelo_apoyos_A.yaml --sin-word
diseno-apoyos-A input modelo_apoyos_A.yaml --word memoria_A.docx --json calculo_A.json
```

Sin argumentos se ingresan los datos en consola. Se conserva la exportación Word y JSON desde el mismo registro numérico. El comando aplica alcance neopreno incluso a los YAML antiguos de alcance completo. El motor interno conserva las comprobaciones externas para compatibilidad, pero el comando no las ejecuta.

## Salida de terminal en cuadros

La salida predeterminada organiza el resumen, cargas, composición, resultados principales, verificaciones y observaciones en cuadros de texto. En las verificaciones se muestra valor, límite, uso del límite y estado. Las deformaciones unitarias se presentan en porcentaje; el uso del límite es otro porcentaje (valor/límite), no la deformación. Las unidades se mantienen visibles y los datos faltantes se muestran como tales.

Por defecto, después del resumen se desarrolla cada cálculo en un cuadro con fórmula, variables y unidades, reemplazo numérico, resultado, comparación con el límite, uso porcentual, estado y referencia. No es necesario activar ninguna opción. Para solicitar solamente el resumen:

```powershell
diseno-apoyos-A --resumen
diseno-apoyos-A input modelo_apoyos_A.yaml --sin-word --resumen
```

El formato se ajusta entre 72 y 112 columnas. Los cálculos, los estados, el Word y el JSON no cambian por este formato de presentación.

## Compresión automática con Serquén

Enter en la pregunta de curvas usa las gráficas de Serquén p.231, Fig. C14.7.6.3.3-1, para Shore A 50 o 60. Se incorporan las seis curvas de factor de forma S=3,4,5,6,9,12 para cada dureza. Se interpola linealmente en esfuerzo y luego en S, sin extrapolar. Los esfuerzos de la figura se convierten de ksi a kgf/cm² con 70.306957964; los porcentajes se dividen entre 100.

El registro muestra los puntos y fracciones utilizados. La digitalización es una lectura referencial, no una curva de ensayo de producto. Se conservan las cuatro lecturas de la p.238 únicamente como comprobación independiente del ejemplo, sin imponerlas a otras geometrías. La tolerancia de contraste del ejemplo es 0.15 puntos porcentuales de deformación; no constituye una cota del error en toda la gráfica.

También se puede escribir `G` para ingresar lecturas propias, `E` para utilizar explícitamente la aproximación elástica anterior, o una ruta YAML con curvas del fabricante. Las curvas suministradas tienen prioridad sobre el método automático. Una curva insuficiente o una consulta fuera de cobertura no se sustituye silenciosamente por otra fórmula.

En YAML:

```yaml
compresion:
  metodo: serquen  # o elastico
  fuente: ''
  tipo: fabricante
  shore_a: 60
  puntos: []
```

Con puntos vacíos y método serquen se carga la referencia incorporada para la dureza del apoyo. Con puntos explícitos se utilizan esos puntos, su tipo y procedencia. Cada S necesita origen `[S, 0, 0]` y al menos otro punto de esfuerzo/deformación. La dureza debe coincidir. Para curvas propias, la deformación se expresa como decimal.

## Selección geométrica

El largo L es longitudinal; W es transversal. La altura H incluye todo el caucho y todo el acero. Los valores propuestos se conservan, sin ajustarlos silenciosamente.

| Modo | Función |
|---|---|
| medida | Composición a medida; prueba capas y zunchos, y calcula el espesor exterior compatible con H si se propone. |
| usuales | Parejas hri/hs de p.224: 8/2, 10/3, 12/3 y 15/4 mm; no equivalen por sí solas a un producto comercial. |
| semirecubierto | Filas carreteras de las tablas pp.225-227. |
| recubierto | Filas carreteras de p.228, con 5 mm de recubrimiento lateral según la descripción p.224. |

Para búsqueda YAML, fijar ancho y las dimensiones deseadas y dejar en `null` las variables libres:

```yaml
geometria:
  ancho_cm: 40
  largo_cm: 30
  altura_total_cm: 7.5
  seleccion: medida
  capa_interior_cm: null
  capa_exterior_cm: null
  numero_capas_interiores: null
  zuncho_cm: null
  rotacion_catalogo_rad: null
```

En modo medida con H fija se prueban también espesores de acero mayores que el mínimo: 2,3,4,5,6,8 y 10 mm. La búsqueda prioriza menor largo y altura; para la misma H fija, menor espesor de acero, luego menos capas. Los espesores resultantes requieren confirmación de fabricación. Una composición totalmente manual se verifica sin cambiarla. Una H manual incompatible produce NO CUMPLE; una búsqueda sin solución devuelve error explícito.

## Catálogo de Serquén

Se transcribieron 119 filas de planta/capacidad para carreteras: 96 semirecubiertas y 23 recubiertas. Se incluyen solo las columnas de composición que tienen rotación legible y al menos una capa interior. El n del catálogo cuenta zunchos; el programa usa `capas interiores = n - 1` y dos capas exteriores de medio espesor interior, siguiendo pp.224-228.

El catálogo usa el lado corto como L en la dirección del movimiento. No se intercambian los ejes automáticamente porque la capacidad de rotación depende de la orientación. Se compara la carga de servicio con N tabulado en kN (1 Tn = 9.80665 kN), el desplazamiento con u en mm y la rotación de servicio con alpha en milirradianes. La rotación de análisis debe ingresarse en radianes. Sin ella, la comprobación específica de catálogo queda pendiente, aunque la rotación implícita del Método A se compruebe geométricamente.

Los apoyos recubiertos conservan dimensiones exteriores para identificar la fila; el área efectiva y S usan el núcleo descontando los 5 mm laterales. La memoria identifica esa hipótesis; el detalle del fabricante debe confirmarla. Las capacidades tabuladas no reemplazan las verificaciones del Método A. Las columnas en negrita del libro no son las únicas que se pueden consultar.

Las gráficas no cubren S mayor que 12. Algunos apoyos de catálogo tienen factores exteriores por encima de ese valor: en esos casos se conservan los controles calculables y se informa la falta de cobertura para las deflexiones, sin extrapolar. La selección prioriza menos comprobaciones pendientes, luego menor L y H. No se atribuye conformidad a una comprobación sin datos.

Hay posibles erratas en el documento: por ejemplo, p.226 muestra 10.0 mrad para la tercera composición de lado 100 mm después de 30 y 60; esa casilla se excluye, sin inventar 90. Las otras cifras tabuladas se transcriben como aparecen (incluidas las excepciones de desplazamiento); además siempre se verifica el límite de corte del Método A. No se extrapolan casillas vacías ni se asume disponibilidad comercial actual.

## Entradas del proyecto

Las fuerzas son reacciones por apoyo, en Tn; longitudes en cm y m; esfuerzos en kgf/cm². En consola se proponen DC=27.470, DW=0.169, PL=4.669, LL=16.444 e IM=5.427 Tn. Esta separación LL/IM supone 33% de impacto sobre vehículo sin carril dentro de 21.871 Tn; permanece identificada como hipótesis por confirmar. El YAML conserva sus propias cargas.

La longitud efectiva es desde el punto de movimiento nulo, no necesariamente la luz completa. La retracción se ingresa desde el cálculo o hipótesis declarada del tablero; el programa no la obtiene de las gráficas del elastómero. El postensado se fija en cero y el comando rechaza valores distintos de cero. La comprobación interna del ejemplo postensado 4.1 se conserva como regresión, no como plantilla para este comando.

## Estados y alcance de la conclusión

| Estado | Significado |
|---|---|
| NO CONFORME | Existe al menos un incumplimiento numérico. |
| PENDIENTE | Falta una consulta dentro de la cobertura o un dato necesario. |
| ESTIMADO | Controles favorables con la aproximación elástica elegida expresamente. |
| REFERENCIAL | Controles favorables con gráficas, tablas o lecturas referenciales; la consola indica CUMPLE según la referencia. |
| CONFORME | Todas las comprobaciones incluidas cumplen con las fuentes declaradas; no es certificación independiente del producto. |

Las figuras del libro permiten reproducir el procedimiento académico y contrastar resultados; no sustituyen la documentación del apoyo fabricado. Ni el hash ni una prueba automatizada certifican el proyecto.

## Fuente y validación

Fuente aportada: `568062706-PUENTES-con-AASHTO-LRFD-2020-9th-Edition-Arturo-Rodriguez-Serquen.pdf`, extracto de 17 páginas, impresas 223-239. SHA256: `06e99d60cb5bc0ef43f2f87b848ce27a7f57a1bef8ce0bfcffffbb8428573f2e`.

Datos incorporados: `src/bridge_design/domain/serquen_bearings.py`. La imagen de las curvas tiene 614x1004 píxeles; el archivo documenta la calibración de ejes. Las lecturas se revisaron superponiéndolas a las curvas. Para el problema 4.1, la digitalización da delta total aproximadamente 0.319 cm frente a 0.323 cm del libro, y delta de carga viva más creep 0.151 cm frente a 0.153 cm. Las pruebas conservan además el contraste exacto con las cuatro lecturas originales de la p.238.

La validación cubre unidades, interpolación, ausencia de extrapolación, ambas durezas, selección usual y de catálogo, preservación de dimensiones, recubrimiento, rotación faltante/excesiva, geometrías insuficientes y exportación de resultados.
