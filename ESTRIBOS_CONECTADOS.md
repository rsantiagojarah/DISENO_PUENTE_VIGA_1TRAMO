# Análisis y diseño de estribos conectados

El comando `diseno-estribos-conectados` analiza dos estribos con cajuela y una
cimentación continua mediante FRAME 2D elástico de primer orden. Reutiliza la
geometría, los materiales, los empujes activos y las comprobaciones de concreto
del programa. La franja tiene 1,00 m de ancho perpendicular al plano del modelo.
Todas las dimensiones de ambos lados son editables; el PDF de referencia no
impone cotas al cálculo.

## Uso

### Nombres de combinaciones

Los casos identifican **Resistencia Ia**, **Resistencia Ib**, **Evento Extremo I**
y **Servicio I**, conforme a los nombres del módulo de estribos individuales.
Cada combinación se aplica globalmente a ambos estribos, losa y transiciones.
No se cruzan Ia/Ib independientemente por región: se eliminan las variantes
mixtas anteriormente identificadas como `111–222`. Las cargas físicas de cada
lado conservan sus valores y posiciones; global no significa cargas iguales.
Servicio I y Evento Extremo I ya eran globales y mantienen ese criterio.

Con un par de reacciones de tablero y frenado, se generan 10 casos: cuatro de
resistencia (Ia/Ib por dos sentidos), dos de servicio y cuatro sísmicos
(alternativas A/B por dos sentidos). Si se incluye la condición sin tablero,
se agregan siete: Ia, Ib, Servicio I y los cuatro sísmicos. El ejemplo queda
numerado C001–C017; por tanto, deben regenerarse reportes y exportaciones
anteriores y no compararse casos únicamente por su código C.
La selección global solicitada no incorpora automáticamente otros patrones
asimétricos de cargas; los escenarios físicos adicionales deben justificarse
e ingresarse como pares de cargas simultáneas.
`BR±1` solo aparece cuando existe frenado; `EQ±1` conserva el sentido sísmico global.
Los nombres se actualizan en terminal y reportes al volver a ejecutar el cálculo.

### Recubrimientos internos

Se adoptan 7,5 cm en ambas caras de pantallas, cajuelas, parapetos, zapatas,
losa central y transiciones. No se solicitan en consola ni aparecen como datos
en las nuevas plantillas YAML. El criterio adoptado es el de contacto con suelo
de la tabla 2.12.5.4.1 del Manual de Puentes MTC 2018, aplicado uniformemente
a estas regiones, sin distinguir caras. Es una hipótesis para concreto vaciado
en sitio, sin exposición marina ni abrasión; no sustituye la revisión de
durabilidad específica del proyecto.

Los recubrimientos se toman exclusivamente de los valores internos: las claves
de recubrimiento en YAML no se utilizan, incluso si indican valores mayores.
Los valores efectivos quedan registrados en las entradas de `resultados.json`
y se utilizan en los cálculos de armado. No modifican la rigidez bruta del
FRAME ni el contacto.

El resto del programa mantiene 5 cm en losa y voladizos del tablero, vigas y
diafragmas, y 5,08 cm en la barrera New Jersey. Estribos individuales y muros
adoptan 7,5 cm en pantallas, zapatas y dentellones. Estos son valores internos
adoptados, no una selección automática de todas las condiciones normativas.

### Ejecución

```powershell
diseno-estribos-conectados output modelo.yaml
diseno-estribos-conectados input modelo.yaml --verificar-malla
```

Sin argumentos se solicitan los datos por terminal, reutilizando las preguntas
del estribo individual. `input` y `output` sin ruta abren el selector de archivos.
Después del análisis se muestran alternativas de armadura principal y transversal
por región. Se puede conservar la propuesta, elegir un ítem o ingresar barra y
separación personalizadas, igual que en estribos. El programa recalcula flexión,
corte, fisuración, mínimos y desarrollo con el acero adoptado. Las alternativas
que no cumplen se identifican; conservarlas para revisión no aprueba el diseño.
Al terminar se pregunta si se desea generar Word y se abre el diálogo para
elegir su nombre y ubicación. Cancelar no elimina los demás resultados.
También se puede ejecutar mediante:

```powershell
python -m bridge_design.connected_main --help
bridge-design estribos-conectados input modelo.yaml
```

Para generar un caso exclusivamente de demostración:

```powershell
diseno-estribos-conectados output ejemplo.yaml --ejemplo
diseno-estribos-conectados input ejemplo.yaml --resultados output/ejemplo_conectados
```

La plantilla normal deja **balasto y fricción de interfaz sin valor**. Son
obligatorios. `--ejemplo` introduce expresamente `ks=3000 Tn/m³` y `mu=0.50`, que
no constituyen datos geotécnicos del proyecto. Los materiales, parámetros
sísmicos y brazo adicional de frenado también son referenciales, no datos del PDF.
No se deduce el balasto de la presión admisible.

En consola, `qadm` y el FS de capacidad portante se solicitan una sola vez,
al ingresar el primer estribo, y se comparten en toda la cimentación. El programa
convierte automáticamente de kg/cm² a Tn/m² (`1,35 kg/cm² = 13,5 Tn/m²`) y muestra
el valor adoptado sin volver a preguntarlo, incluso con estribos diferentes.
En las plantillas YAML se definen únicamente en `suelo_cimentacion`, mediante
`qadm_tn_m2` y `fs_capacidad_nominal`. Los archivos anteriores siguen siendo
compatibles: los valores comunes de ese bloque prevalecen sobre las copias
antiguas en `suelo_sismo` de cada estribo y se reutilizan en ambos lados.

Las reacciones iniciales del tablero indicadas por el usuario son, en Tn/m por
estribo: `PDC=8.959`, `PDW=0.545`, `PPL=0.762`, `PLL+IM=6.92` y `BR=1.33`.
Se ofrecen en ambos lados, tanto al ingresar por consola como en nuevas plantillas
YAML. Son editables e independientes por lado; los valores explícitos de archivos
existentes se respetan. No se modifican los valores del comando de estribo individual.

## Dimensiones iniciales del PDF

La entrada interactiva (Enter), las nuevas plantillas YAML y los valores iniciales
del dominio conectado utilizan `MDOELO DE PUENTEl.pdf`. No se alteran los valores
del comando de estribos individuales ni los datos expresos de archivos ya guardados.

| Dimensión | Valor inicial m |
| --- | ---: |
| Separación libre entre caras interiores | 13,10 |
| Ancho de cada zapata | 5,00 |
| Espesor de cada zapata | 1,50 |
| Talón exterior | 1,50 |
| Pantalla constante, confirmada por el usuario | 1,00 |
| Puntera interior, confirmada por el usuario | 2,50 |
| Espesor de losa central | 0,75 |
| Longitud de cada transición inferior | 1,00 |
| Altura recta de pantalla bajo transición de cajuela | 7,15 |
| Altura hasta asiento desde cara superior de zapata | 8,05 |
| Altura de parapeto sobre asiento, 0,90 + 0,25 | 1,15 |
| Altura del bloque de cajuela, 0,25 + 0,25 | 0,50 |
| Altura de transición de cajuela | 0,40 |
| Espesor de parapeto y retiro posterior t2 | 0,35 |
| Longitud horizontal de asiento | 1,00 |
| Transición frontal superior t1 | 0,00 |

La altura total desde fondo de zapata resulta `H=1,50+8,05+1,15=10,70 m`.
El contorno interior recto se representa sin ensanche frontal t1; la cota 0,30 m
dibujada por fuera del parapeto no se utiliza como ensanche de la pantalla.
La luz inicial entre centros de asientos se deduce como 14,10 m; las cargas del
tablero se ingresan, no se recalculan a partir de esta luz. No se agrega suelo
frontal sobre la cara superior de la cimentación.
La cimentación tiene longitud total de 18,10 m y el nodo Ux=0 queda en x=9,05 m.
Todas estas dimensiones siguen siendo editables para otros modelos.

## Geometría

Las secciones `estribo_izquierdo` y `estribo_derecho` utilizan las claves YAML del
comando `diseno-estribos`, incluyendo cajuela, parapeto, t1, t2 y transición.
La puntera mira hacia el vano y el talón hacia el relleno exterior. La coordenada
local del estribo existente se refleja en el lado izquierdo; el resultado global
tiene x positivo de izquierda a derecha y y positivo hacia arriba.

La separación libre se mide entre las caras interiores de las pantallas **en
su base**. Si `B_izq`, `B_der` son los anchos de zapatas y `p_izq`, `p_der` las
punteras, la longitud total es:

```text
L = B_izq + B_der + separacion_libre - p_izq - p_der
```

Las transiciones inferiores quedan dentro del espacio entre zapatas. La longitud
de losa de espesor constante debe resultar positiva. Una transición de longitud
cero representa un cambio brusco de sección. Se exige compatibilidad geométrica
de la cajuela: `longitud_apoyo + espesor_parapeto = espesor_superior + t1 + t2`.

La línea de referencia horizontal se sitúa en la cara superior común de la
cimentación, y=0. Los elementos utilizan `A=b*t`, `I=b*t³/12` y Ec calculado con
la función MTC existente. Las transiciones y pantallas variables se discretizan
con su espesor en el centro del elemento; el diseño verifica el espesor real en
las estaciones de comprobación. Los offsets opcionales trasladan cinemáticamente
el eje de referencia al centroide mediante brazos rígidos y conservan el
acoplamiento axial–flexión. La malla incluye los límites de secciones, las
uniones de pantallas, los límites de cargas y el nodo de referencia.

## Apoyos y contacto

Cada nodo tiene Ux, Uy y giro. Únicamente se restringe Ux en un nodo de la
cimentación. Por defecto se crea en `L/2`; `nodo_referencia_x_m` permite moverlo.
Uy sigue gobernado por el equilibrio con los resortes y el giro queda sin
restricción externa. Las uniones entre elementos permanecen rígidas.

El resorte nodal tiene `K_i = ks*b*L_tributaria`. Los extremos reciben media
longitud del elemento adyacente. La suma de áreas tributarias es `b*L`.
El suelo solo resiste compresión. El solucionador itera el conjunto de resortes
activos y rechaza inestabilidad, falta de convergencia o residuos de equilibrio
excesivos. Cada combinación se resuelve individualmente; no se superponen
resultados obtenidos con conjuntos de contacto diferentes.

La reacción central satisface `Rx + sum(Fx) = 0`. Debe ser aproximadamente cero
para cargas globalmente equilibradas, aunque existan esfuerzos N importantes en
la losa. Bajo desequilibrio, la reacción concentrada es una idealización del
apoyo lateral; su ubicación puede influir en los esfuerzos. No calcula el
desplazamiento global por deslizamiento ni la distribución de fricción en el suelo.

## Cargas y combinaciones

Se incluyen pesos propios de ambas pantallas, cajuelas, zapatas, transiciones y
losa, pesos de relleno, sobrecargas verticales y horizontales, reacciones DC/DW/LL
del tablero, frenado, inercia de concreto/relleno/tablero y empuje sísmico.

El empuje es **siempre activo**, por indicación del modelo. Se reutilizan Coulomb
y Mononobe–Okabe. El modelo de estribos admite el trasdós equivalente vertical
del módulo existente. La geometría escalonada determina pesos y excentricidades.

Como en el módulo individual, se distinguen:

- Presiones en la cara real de la pantalla, para sus esfuerzos locales.
- Resultante externa sobre el plano vertical del extremo del talón, para el
  equilibrio del conjunto muro más relleno.

La diferencia de fuerza y momento se transfiere a los nodos del talón repartida
por área tributaria. Esta transferencia aproximada conserva el equilibrio y
evita duplicar la componente vertical de fricción entre suelo y pantalla. Su
distribución local es una hipótesis del modelo, no un análisis continuo del relleno.

Se usan Resistencia Ia, Ib, Servicio I y Evento Extremo I del módulo existente.
Se cruzan las variantes Ia/Ib entre ambos lados y los factores DC de la losa.
Los dos patrones sísmicos existentes son `PAE+0.5PIR` y `max(0.5PAE,EH)+PIR`.
Para cada dirección global +X/-X, Mononobe–Okabe usa el signo relativo a cada
relleno y todas las inercias tienen un sentido global coherente. El incremento
sísmico positivo se aplica uniforme, como en estribos; una reducción se aplica
triangular para evitar presiones negativas. No hay análisis dinámico modal.

Las cargas izquierda/derecha son **pares simultáneos**. Una lista vacía en
`casos_simultaneos` utiliza el par definido en los estribos. Para múltiples
posiciones del tablero, incluir cada par explícitamente, por ejemplo:

```yaml
casos_simultaneos:
  - nombre: Vehiculo cerca del estribo izquierdo
    cargas_izquierda:
      pdc_carga_muerta_tablero_tn_m: 12.0
      pdw_superficie_tn_m: 1.8
      ppl_peatonal_tablero_tn_m: 0.0
      pll_im_vehicular_tn_m: 9.0
      br_frenado_tn_m: 1.5
    cargas_derecha:
      pdc_carga_muerta_tablero_tn_m: 12.0
      pdw_superficie_tn_m: 1.8
      ppl_peatonal_tablero_tn_m: 0.0
      pll_im_vehicular_tn_m: 3.0
      br_frenado_tn_m: 0.5
    factor_sobrecarga_izquierda: 1.0
    factor_sobrecarga_derecha: 0.0
```

Las cifras del bloque anterior son ilustrativas. La envolvente cubre los casos
ingresados, no genera automáticamente posiciones vehiculares nuevas.
`incluir_sin_tablero` agrega un caso con cargas del tablero nulas y los rellenos
y sus sobrecargas presentes. No equivale a todas las fases constructivas.

## Diseño y comprobaciones

- Se recuperan N, V, M con signos, incluyendo los extremos internos de las
  cargas polinómicas, y se verifican las demandas simultáneas por sección/caso.
- La armadura principal se selecciona del catálogo existente, con dos caras
  iguales. Se diseña por flexión y cortante, sin interacción axial–momento,
  por decisión del usuario. La flexión reutiliza la función del estribo individual:
  sección rectangular, acero de la cara traccionada y phi limitado por deformación,
  sin acreditar la contribución del acero de la cara comprimida.
- Se mantienen el mínimo de flexión y la armadura por temperatura/retracción.
  La armadura transversal por cara se dimensiona por el mínimo correspondiente.
- El corte emplea el procedimiento general compartido, sin término axial.
  Si el concreto no resiste, se informa NO CUMPLE.
- Servicio reutiliza la estimación del estribo individual `fs = |Ms|/(As*0.90*d)`.
  Se revisan tensión de acero y espaciamiento de fisuración, sin efecto axial.
- N se conserva en el análisis, diagramas y exportaciones, pero no se verifica
  flexocompresión ni flexotracción. Los momentos mantienen las transformaciones
  por offsets cuando están activadas. Un estado OK solo acredita las comprobaciones
  ejecutadas: no demuestra capacidad axial ni que su efecto sea despreciable.
- Se calculan las longitudes de desarrollo recto y con gancho reutilizando las
  funciones existentes. Las longitudes útiles deben ingresarse por región en
  `longitudes_rectas_anclaje_disponibles_m`; de lo contrario el estado es
  PENDIENTE DETALLE. La longitud con gancho no aprueba automáticamente su acomodo.
- Deslizamiento global: `H_d=abs(Rx)` frente a `phi*mu*sum(R_vertical)` de la misma
  combinación. No se agrega resistencia pasiva ni dentellón.
- Contacto: `q_i=R_i/area_i`, superficie activa, asentamientos y levantamientos.
  Servicio se compara con qadm. Para la comparación LRFD se conserva la
  aproximación del módulo existente `qn=FS*qadm`, con phi 0.55/0.80 para
  resistencia/evento extremo. Se utiliza la presión local Winkler y no una
  distribución rígida de Meyerhof. La excentricidad de la resultante se informa
  como resultado; no se le aplica automáticamente el criterio de zapata aislada.

Las deformaciones corresponden a secciones brutas elásticas y balasto lineal
en compresión. No incluyen fisuración en rigidez global, segundo orden,
consolidación, agua/subpresión ni interacción dinámica suelo–estructura.
La franja 2D no resuelve efectos tridimensionales locales de los apoyos.

## Salidas y validación

### Desarrollo verificable en terminal y Word

Ambas salidas utilizan una misma traza. El Word conserva entradas efectivas,
pesos por componente, expresiones de áreas del estribo individual, empujes
activos por lado, sentidos sísmicos y el cuadro resumen de factores.
Las propiedades FRAME por elemento y las acciones detalladas de cada
combinación se conservan en `auditoria.txt` y JSON, no en el Word ni en la
salida normal de la terminal. La terminal y `resumen.txt` presentan solamente
los resultados necesarios para revisar y adoptar el diseño.
Cada acción conserva su factor y sus resultantes Fx, Fy y Mz sin ponderar;
su suma ponderada reproduce el vector de cargas global del FRAME. Los momentos
globales se refieren a (0,0); los brazos de la descomposición geométrica son
locales desde la puntera y se identifican como tales.

La auditoría conserva resortes, áreas tributarias, reacciones, presiones y
asentamientos por nodo y combinación. El Word omite estas tablas nodales y
mantiene el resumen por caso y los gráficos de presiones y asentamientos.
Los asentamientos no se califican como conformes sin un límite admisible.
Se conservan los diagramas completos de N, V y M y contacto.

Por región se identifican separadamente las secciones gobernantes de flexión,
cortante y fisuración: combinación, elemento, estación, coordenadas, espesor y
cara traccionada. Las fórmulas y sustituciones desarrollan d, As, Mcr, capacidad
mínima, respuesta rectangular (c, a, deformación, tensión y phi), Mr, dv, beta,
Vr, fs de servicio, espaciamiento, temperatura y desarrollo. Los valores salen
de las mismas funciones que determinan los índices del diseño.

Las opciones de acero muestran As requerido por flexión y mínimos junto con
As proporcionado. Cumplir el área no sustituye cortante ni servicio. Se recalcula
la traza al cambiar barra o separación. No se inventan cortes, longitudes de
barras ni acomodos de ganchos a partir del detalle del estribo aislado.

`resultados.json` incluye `calculation_audit`, con verificaciones numéricas y
tablas compartidas; `cargas_combinadas.csv` contiene acciones base y ponderadas.
El Word mantiene el formato común de estribos y desarrolla las operaciones,
no solo índices. Las limitaciones del análisis y del diseño sin interacción
axial se mantienen expresamente.

Por defecto se escribe en `output/estribos_conectados`:

- `resumen.txt` con las armaduras adoptadas y verificaciones finales.
- `auditoria.txt` con propiedades, cargas, contacto nodal y desarrollo detallado.
- `resultados.json`: entradas, malla, cargas, combinaciones, contacto y diseño.
- `elementos.csv`, `nodos.csv`, `esfuerzos.csv` y `cargas_combinadas.csv` con
  unidades explícitas.
- Figuras de geometría y contacto de la cimentación completa.
- `modelo_axial.png`, `modelo_cortante.png` y `modelo_momento.png`: cada diagrama
  se dibuja sobre la estructura completa, con ambos estribos, cajuelas, zapatas,
  transiciones, losa y resortes. Estas mismas figuras se incorporan al Word.

Los diagramas usan la misma escala geométrica en x/y y una escala de esfuerzos
común para todos los elementos de cada figura. Azul identifica el mínimo y rojo
el máximo de resistencia y evento extremo. La ordenada positiva sigue la normal
local: arriba en la cimentación e izquierda en ambas pantallas. Se indican los
extremos globales con su caso y los extremos de cimentación y de cada estribo.
Las curvas se trazan por elemento, sin unir saltos ni ramas distintas, e incluyen
las estaciones de extremos internos de todas las combinaciones. No son una
deformada ni un único estado simultáneo: cada extremo puede proceder de otro caso.

La memoria Word opcional se guarda donde se elija al finalizar. Reutiliza el
formato de estribos: A4, márgenes de 25,4 mm, Arial Narrow 11, título de portada
22, interlineado 1,5, contenido justificado, portada, índice, encabezado,
paginación, secciones numeradas, tablas y ecuaciones nativas de Word.
`--sin-word` omite la pregunta y generación de Word, pero no la selección de acero;
`--resultados RUTA` cambia la carpeta de TXT, JSON, CSV y gráficos.
Para automatización explícita sin preguntas, usar `input ARCHIVO --automatico`:
conserva la propuesta de acero y guarda Word en la carpeta de resultados.
Combinar con `--sin-word` para omitirlo. Los archivos de resultados registran
las barras, separaciones, comprobaciones y elecciones adoptadas.
`--verificar-malla` compara los máximos globales al dividir el paso por dos;
las variaciones se presentan sin declarar convergencia por una tolerancia fija.
Una comprobación más exigente puede revisar curvas por estación en los CSV.

Las pruebas cubren soluciones analíticas de vigas y barras, offsets,
complementariedad del contacto, equilibrio, simetría, cargas desequilibradas,
preservación de pesos/centroides, fricción muro–relleno, signos sísmicos,
geometría asimétrica, refinamiento, compatibilidad de secciones RC y la CLI.

## Referencias de implementación

- Manual de Puentes MTC 2018 de `docs`: artículos referenciados en las funciones
  compartidas de estribos, módulo del concreto, corte, fisuración y desarrollo.
- [Elemento elástico FRAME de referencia](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/elasticBeamColumn.html).
- [Transformaciones con offsets](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/geomTransf/Linear.html).
- [Material elástico sin tracción](https://opensees.berkeley.edu/OpenSees/manuals/usermanual/169.htm).
- [FHWA Manual for Refined Analysis in Bridge Design and Evaluation](https://www.fhwa.dot.gov/bridge/pubs/hif18046.pdf), compatibilidad e interacción de secciones.
- [FHWA GEC 6 Shallow Foundations](https://www.fhwa.dot.gov/engineering/geotech/pubs/010943.pdf), deslizamiento y fricción de interfaz.

Estas referencias documentan la formulación; OpenSees no es una dependencia.
