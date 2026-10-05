# Diseño de apoyos elastoméricos Método A

`diseno-apoyos-A` calcula apoyos rectangulares reforzados con zunchos de acero según el Manual de Puentes MTC 2018, artículo 2.10.4. Genera una memoria Word con el formato de `diseno-apoyos-neopreno` y un registro JSON reproducible. La referencia académica es el archivo APOYOS.pdf de Arturo Rodríguez Serquén, páginas impresas 229 a 239.

## Ejecución

Desde la carpeta del proyecto, con el paquete instalado mediante `python -m pip install -e . --no-deps`:

```powershell
diseno-apoyos-A
diseno-apoyos-A --help
diseno-apoyos-A output modelo_apoyos_A.yaml
diseno-apoyos-A input modelo_apoyos_A.yaml
diseno-apoyos-A input modelo_apoyos_A.yaml --word memoria_A.docx --json calculo_A.json
diseno-apoyos-A input modelo_apoyos_A.yaml --sin-word --json calculo_A.json
```

Sin argumentos, el programa pide los datos en la terminal. Con `input` u `output` sin ruta abre un selector de YAML. Después del cálculo abre el diálogo para guardar Word, salvo que se indique `--word` o `--sin-word`. Cancelar el Word conserva los resultados de consola y permite exportar JSON.

Si el comando todavía no está registrado, se puede ejecutar su módulo desde esta carpeta:

```powershell
python -m bridge_design.cli.bearing_a_cli input modelo_apoyos_A.yaml --sin-word
```

## Alcance y unidades

Se considera un apoyo rectangular sin agujeros ni PTFE, bajo compresión, con Shore A 50 o 60. L es longitudinal y W transversal. La rotación principal debe ocurrir alrededor del eje transversal. Otros tipos de apoyo, levantamiento y superficies deslizantes requieren un modelo diferente.

Las fuerzas se ingresan por apoyo en toneladas-fuerza (Tn), con 1 Tn = 1000 kgf. Los esfuerzos son kgf/cm² y los espesores son cm. La longitud de expansión es la distancia efectiva desde el punto fijo, en m; no necesariamente la luz completa. LL se ingresa sin impacto y el incremento IM se declara por separado. IM participa en esfuerzos de servicio y Resistencia I del concreto, pero se excluye del límite de deformación por compresión de MTC 2.10.4.3.3.

## Geometría manual y selección automática

Las dimensiones ingresadas se conservan exactamente. Un apoyo insuficiente produce verificaciones `NO CUMPLE`; el programa no aumenta su tamaño ni recorta sus capas para hacerlo cumplir.

Para buscar automáticamente, escribir `null` en los valores no adoptados de `geometria`: `largo_cm`, `capa_interior_cm`, `capa_exterior_cm`, `numero_capas_interiores` y `zuncho_cm`. El ancho siempre se declara. La búsqueda prueba espesores interiores de 0.5, 0.8, 1.0, 1.2, 1.5 y 2.0 cm, exteriores compatibles, largos enteros en cm y hasta el límite de capas configurado. El zuncho se redondea hacia arriba a incrementos de 1 mm, con mínimo práctico de 2 mm. Debe confirmarse la disponibilidad del fabricante.

Se elige el menor largo con una composición viable, luego la menor altura y cantidad de capas. Se verifica por separado el concreto y las resistencias externas. Si no hay candidato dentro de los límites, el programa devuelve un error explícito. Con curvas declaradas, el candidato debe quedar dentro de su cobertura.

El límite normativo de aplicabilidad es `S_i²/n_eff < 22`. Se adopta además el criterio conservador del comentario transcrito en APOYOS.pdf: 20 para tres o más capas interiores y 16 para apoyos cuadrados o clasificados como casi cuadrados. Un apoyo exactamente cuadrado activa automáticamente 16; el usuario debe clasificar los casi cuadrados con `casi_cuadrado: true`.

## Compresión y respaldo de los datos

La sección `compresion` admite tablas con puntos `[S, sigma_kg_cm2, epsilon_decimal]`. Por ejemplo, una deformación de 4.45 % se ingresa como `0.0445`. Cada factor S debe tener el origen `[S, 0, 0]` y al menos otro punto, con esfuerzos únicos crecientes y deformaciones no decrecientes.

Se interpola linealmente primero en esfuerzo y después en S. El registro conserva los puntos que rodean cada consulta y sus fracciones de interpolación. No se extrapola. Una consulta fuera de la tabla deja la deformación y sus verificaciones pendientes.

Con `tipo: fabricante`, indicar la procedencia del ensayo, producto, lote, dureza y revisión aplicables. El programa comprueba la consistencia numérica; la identificación y autenticidad del certificado deben verificarse contra el producto. Con `tipo: referencia`, la tabla sirve para una comprobación académica y produce estado `REFERENCIAL`.

Sin tabla se calcula una estimación elástica de predimensionamiento, identificada como tal. Sus verificaciones quedan `PENDIENTE`: esa expresión no se presenta como una curva normativa ni como un ensayo del fabricante.

## Conexiones y concreto

Para un tramo, la fuerza sísmica de conexión puede calcularse como `As` por la carga permanente tributaria en cada dirección restringida. Para varios tramos deben ingresarse las fuerzas del análisis. La envolvente horizontal de Resistencia I se ingresa desde el análisis del puente y debe incluir frenado, temperatura y las combinaciones pertinentes.

`GA·Delta/h` es una reacción horizontal de servicio, no una resistencia sísmica. Si la fricción es insuficiente, se exige retención para la reacción horizontal completa. No se descuenta fricción ni reacción térmica de la demanda sísmica. La retención debe permitir el movimiento del apoyo expansivo.

Las resistencias longitudinal y transversal son resistencias **de diseño** de dispositivos externos. Su fuente debe identificar una memoria o certificado que cubra acero, soldaduras/pernos, anclajes, concreto y la trayectoria resistente. Este comando verifica esas capacidades declaradas; no dimensiona los elementos externos de esa memoria. Cuando son necesarias y no se suministran, la conexión queda `PENDIENTE`.

Se verifica el aplastamiento del pedestal con Resistencia I. Por defecto `A2=A1`; solo declarar un A2 mayor cuando su geometría similar, concéntrica y contenida en el pedestal esté justificada. El programa rechaza como verificación un A2 menor al área cargada.

## Resultados y estados

La memoria contiene entradas, geometría, movimiento, compresión, zunchos por servicio y fatiga, estabilidad, deflexión instantánea y diferida, fricción, conexiones, aplastamiento y esquema de capas. Cada operación conserva fórmula, leyenda, sustitución, resultado, unidad y referencia. Los controles incluyen límite y ratio cuando puede calcularse.

Los estados globales, en orden de prioridad, son:

| Estado | Significado |
|---|---|
| NO CONFORME | Al menos una verificación incumple. |
| PENDIENTE | Faltan datos o respaldo para alguna verificación. |
| REFERENCIAL | Se utilizan datos académicos de compresión. |
| CONFORME | Todas las verificaciones cumplen con los datos y fuentes declarados. |

El JSON conserva todas las entradas normalizadas, las dimensiones realmente adoptadas, 40 registros de cálculo, la versión del algoritmo y el SHA256 de las entradas. El Word y la consola se generan a partir de ese mismo registro. El hash identifica entradas; no certifica ni firma el diseño.

## Comprobación con el PDF

El archivo `ejemplo_apoyos_A_serquen.yaml` reproduce el problema 4.1. Puede regenerarse y ejecutarse:

```powershell
diseno-apoyos-A ejemplo ejemplo_apoyos_A_serquen.yaml
diseno-apoyos-A input ejemplo_apoyos_A_serquen.yaml --word memoria_ejemplo_A.docx --json ejemplo_A.json
```

Resultados de control: servicio 92 Tn; planta 300 × 450 mm; cuatro capas interiores de 15 mm; dos exteriores de 8 mm; cinco zunchos de 2 mm; altura 86 mm; movimiento 3.6408 cm; reacción horizontal 9.092898 Tn. Se utilizan las cuatro lecturas de deformación del cuadro del PDF, no una digitalización general de sus gráficas. Los resultados conservan todos los decimales y pueden diferir ligeramente de los redondeos del libro.

El ejemplo tiene estado `REFERENCIAL`. Su fuente no define sismo y se desactivan esas demandas únicamente para reproducir el ejercicio; no debe usarse como configuración sísmica de un puente real.

Las pruebas automatizadas incluyen esta comparación, geometrías insuficientes sin modificación, límites estrictos, curvas fuera de cobertura, temperaturas de expansión, IM, datos no finitos, resistencias sísmicas insuficientes, búsqueda acotada y exportaciones Word/JSON.

## Fuentes

[Manual de Puentes MTC 2018 en el portal oficial](https://portal.mtc.gob.pe/transportes/caminos/normas_carreteras/manuales.html), artículos 2.10.4, 2.10.3.3.5, 2.10.3.3.6, 2.4.3.9.2, 2.4.3.11.8, 2.4.5.3.1 y 2.8.1.4. Los artículos AASHTO indicados corresponden a las correlaciones de esa edición del Manual.

APOYOS.pdf, Arturo Rodríguez Serquén, páginas impresas 229 a 239: procedimiento de Método A y problema 4.1.
