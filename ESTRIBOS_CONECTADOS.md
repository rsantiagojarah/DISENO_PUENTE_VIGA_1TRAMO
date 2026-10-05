# Análisis y diseño de estribos conectados

El comando `diseno-estribos-conectados` analiza dos estribos con cajuela y una
cimentación continua mediante FRAME 2D elástico de primer orden. Reutiliza la
geometría, los materiales, los empujes activos y las comprobaciones de concreto
del programa. La franja tiene 1,00 m de ancho perpendicular al plano del modelo.
Todas las dimensiones de ambos lados son editables; el PDF de referencia no
impone cotas al cálculo.

## Distribución de resortes

La entrada solicita la **cantidad total de nudos con resorte en la cimentación**
(41 por defecto, mínimo 4). En YAML se usa `cantidad_nudos_cimentacion` dentro de
`cimentacion`, en lugar de `paso_malla_m`.

El reparto conserva exactamente la cantidad pedida y coloca siempre un resorte
en cada extremo exterior de talón y bajo el eje de cada estribo. Los nudos son
equidistantes dentro de tres tramos: extremo izquierdo–eje izquierdo, entre
ejes y eje derecho–extremo derecho. La separación puede cambiar de un tramo a
otro para respetar esos puntos; el reparto es simétrico si la geometría lo es.

Los cambios de sección, límites del relleno y la restricción horizontal pueden
añadir nudos auxiliares al FRAME, pero no añaden resortes. Cada rigidez se calcula
como `ks * área tributaria`, tomando la mitad de la distancia al resorte vecino
a cada lado. La suma de áreas corresponde a la franja completa de cimentación.
Los gráficos dibujan todos los resortes reales y la salida distingue su cantidad
del número total de nudos estructurales.

Los YAML antiguos con `paso_malla_m` siguen siendo compatibles. Si se proporciona
también `cantidad_nudos_cimentacion`, prevalece la cantidad. `--verificar-malla`
compara el modelo solicitado con `2*N-1` nudos con resorte.

## Uso

La ejecución interactiva sigue el procedimiento del módulo de estribos individuales:

1. Ingreso de geometría, materiales, suelo, sismo y cargas de ambos estribos;
   cimentación, nudos con resorte y brazo adicional de frenado.
   Se usa el par de reacciones ya ingresado; la consola no solicita pares
   adicionales ni longitudes disponibles de anclaje. Las longitudes rectas
   disponibles siguen el detalle continuo definido para los estribos conectados:
   pantalla relleno y exterior, `D-r`; talón, `B-longitud_talon-r`, cruzando la
   pantalla hacia el borde de puntera; puntera, `B-longitud_puntera-r`, cruzando
   hacia el borde de talón. Losa superior e inferior: ancho de zapata menos
   recubrimiento. Parapeto relleno y exterior: altura total desde fondo de zapata
   menos recubrimiento. Las barras deben disponerse continuas según ese detalle;
   estas longitudes no representan la menor distancia a los dos extremos desde
   una estación FRAME. Se compara cada longitud disponible con ld recto y ld gancho
   con la condicion ld gancho <= ld recto. El estado muestra `RECTO Y CON GANCHO`,
   `SOLO GANCHO` o `NO CUMPLE`; sin longitud acreditada queda `PENDIENTE DETALLE`.
   Estos estados verifican longitudes; el acomodo y doblado de ganchos y los empalmes
   requieren detalle. Una longitud útil explícita en YAML conserva prioridad.
2. Análisis preliminar y tablas de distribuciones de acero, con áreas requeridas,
   áreas proporcionadas, exceso de acero y marca `RECOM.`, con el mismo formato
   de tabla de estribos individuales. Se muestran las opciones que cumplen el
   área por flexión y mínimos. La tabla no presenta índices de corte ni fisuración.
   El usuario elige por ítem o
   ingresa barra y separación personalizadas; Enter conserva la propuesta.
3. Recálculo con los aceros elegidos, cuadro de selección y resumen de contacto,
   capacidad portante, envolvente general NVM, flexión, cortante, servicio,
   mínimos, acero transversal, anclajes y equilibrio numérico. El cuadro de selección
   distingue `TABLA` y `USUARIO` y comprueba áreas. El resumen final muestra tablas
   de concepto/valor con Mu, Md, Mr, Vu, Vr y sus secciones gobernantes, y tablas
   separadas de fisuración (fs, límite y separaciones) y desarrollo/anclaje.
   Todas estas verificaciones usan la barra y separación elegidas.
4. Exportación de resultados y elección del nombre y ubicación del Word mediante
   la misma ventana de guardado del módulo individual. Cancelar la ventana omite
   el Word y conserva los resultados exportados.

Se eligen 16 distribuciones cuando existe puntera, con un unico armado comun para ambos estribos:
cuatro en pantalla y cuatro en parapeto (vertical relleno/exterior y horizontal relleno/exterior),
cuatro en zapata (talón, puntera, transversal superior/inferior) y cuatro en la losa
(longitudinal y transversal, superior/inferior). Cada cara principal utiliza su
envolvente con signo. La cara exterior se dimensiona por mínimos y por flexión si
el FRAME produce tracción en ella. Talón y puntera conservan el criterio individual
de una distribución longitudinal gobernante por zona, continua en ambas caras.
Los mínimos de pantallas y zapatas reutilizan las funciones del módulo individual;
los longitudinales de zapatas y losa usan el cortante simplificado, y los verticales
el procedimiento general. La fisuración compara fs real con su límite y usa
fs acotado por el límite para el espaciamiento, como en estribos individuales.
Las transiciones y cajuelas permanecen en el modelo FRAME con su geometría,
rigidez y cargas. Su armado queda excluido del diseño, recomendaciones,
selección de acero, verificaciones de servicio/anclaje y cuadros de resumen
de la consola y la memoria.
En consola los materiales se ingresan una sola vez y se comparten entre ambos
estribos, sus zapatas y la losa. La geometria se ingresa una sola vez y es comun a ambos lados.
Los recubrimientos de pantallas, cajuelas, parapetos, zapatas y losa se adoptan
internamente en 7,5 cm; no se solicitan en la consola.
Las separaciones mínima y máxima y el incremento son internos, iguales a los
del módulo individual: 0,10 m, 0,30 m y 0,025 m respectivamente. La distribución
adoptada se elige posteriormente en las tablas de acero o se ingresa personalizada.
Las propuestas que no cumplen se identifican expresamente; conservarlas para
revisión no modifica su estado. `--automatico` conserva la propuesta sin solicitar
selección, para ejecuciones desde YAML.

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
Al terminar se abre el diálogo para
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

La plantilla normal deja **el balasto sin valor**; es obligatorio.
`--ejemplo` introduce expresamente `ks=3000 Tn/m³`, que no constituye un dato
geotécnico del proyecto. No se solicita fricción de interfaz suelo-concreto,
porque deslizamiento no forma parte de las verificaciones del reporte.
Los YAML anteriores que contienen el coeficiente siguen siendo compatibles.
Los materiales, parámetros
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

El bloque comun `estribo` utiliza las claves YAML del
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
- La armadura se selecciona del catálogo existente, independientemente por cara
  y dirección. Se diseña por flexión y cortante, sin interacción axial–momento,
  por decisión del usuario. La flexión reutiliza la función del estribo individual:
  sección rectangular, acero de la cara traccionada y phi limitado por deformación,
  sin acreditar la contribución del acero de la cara comprimida.
- Se mantienen el mínimo de flexión y la armadura por temperatura/retracción.
  La armadura transversal por cara se dimensiona por el mínimo correspondiente.
- El corte emplea el procedimiento general compartido en verticales y el
  general también en zapatas y losa, incluyendo 0.5 Nu en la deformación longitudinal.
  Nu es positivo en tracción; la deformación negativa se limita a cero.
  Si el concreto no resiste, se informa NO CUMPLE.
- Servicio reutiliza la estimación del estribo individual `fs = |Ms|/(As*0.90*d)`.
  Se revisan tensión de acero y espaciamiento de fisuración, sin efecto axial.
- N se conserva en el análisis, diagramas y exportaciones, pero no se verifica
  flexocompresión ni flexotracción. Los momentos mantienen las transformaciones
  por offsets cuando están activadas. Un estado OK solo acredita las comprobaciones
  ejecutadas: no demuestra capacidad axial ni que su efecto sea despreciable.
- Se calculan las longitudes de desarrollo recto y con gancho reutilizando las
  funciones existentes. La longitud recta disponible se estima desde las secciones
  críticas de ambas caras hasta los extremos compatibles con la geometría y el
  recubrimiento; no se permite atravesar un cambio de sección fuera del concreto.
  Se compara la menor longitud a ambos lados con ld. Las longitudes verificadas
  de `longitudes_rectas_anclaje_disponibles_m` conservan prioridad cuando se ingresan
  en YAML. La longitud con gancho no aprueba automáticamente su acomodo.
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
- Memoria Word con el nombre y ubicación elegidos en la ventana de guardado,
  después de seleccionar el acero, con el formato aprobado de referencia.
  Con `--automatico` se guarda `memoria_estribos_conectados.docx` en resultados.
- `modelo_axial.png`, `modelo_cortante.png` y `modelo_momento.png`: cada diagrama
  se dibuja sobre la estructura completa, con ambos estribos, cajuelas, zapatas,
  transiciones, losa y resortes. Estas mismas figuras se incorporan al Word.

Los diagramas usan la misma escala geométrica en x/y y una escala de esfuerzos
común para todos los elementos de cada figura. Azul identifica el mínimo y rojo
el máximo de todas las combinaciones, incluido Servicio I. La ordenada positiva sigue la normal
local: arriba en la cimentación e izquierda en ambas pantallas. Se indican los
extremos globales con su caso y los extremos de cimentación y de cada estribo.
Las curvas se trazan por elemento, sin unir saltos ni ramas distintas, e incluyen
las estaciones de extremos internos de todas las combinaciones. No son una
deformada ni un único estado simultáneo: cada extremo puede proceder de otro caso.

La memoria Word solicita nombre y ubicación después de cada ejecución interactiva de
análisis, salvo que se indique `--sin-word`. Se actualiza con los datos y el acero
de esa ejecución. Reutiliza el
formato de estribos: A4, márgenes de 25,4 mm, Arial Narrow 11, título de portada
22, interlineado 1,5, contenido justificado, portada, índice, encabezado,
paginación, secciones numeradas, tablas y ecuaciones nativas de Word.
La memoria se organiza en doce apartados: bases y alcance; geometría, materiales
y suelo; idealización y resortes; determinación y aplicación de cargas; casos
simultáneos y combinaciones; resultados estructurales; contacto y geotecnia;
concreto armado por región; desarrollo y detalle; verificación numérica;
resumen y conclusiones; referencias y anexos. Explica el método de análisis y
los criterios, las fórmulas y la aplicación de DC, EV, LS, EH, EQ y BR al FRAME,
sin ejemplos numéricos por nudo ni descomposiciones de pesos repetidas. Documenta
las hipótesis de empuje activo, reducción sísmica, transferencia al talón y
altura de frenado que requieren sustento del proyecto. Las figuras de cargas, deformada nodal
de servicio y esquemas de armadura no se incorporan al Word.

Las tablas se reservan para comparaciones: geometría común de ambos estribos,
materiales, factores, reacciones simultáneas, resultados geotécnicos y resumen
del armado. No se duplican tablas de entradas, auditoría, nudos ni elementos;
los desarrollos detallados quedan en los anexos TXT, JSON y CSV. Los esquemas
de acero no definen longitudes de corte, doblados, empalmes ni acomodo de ganchos.
Las verificaciones del acero elegido se desarrollan como la memoria de referencia:
expresión, definición de símbolos, sustitución numérica y conclusión para cada
control gobernante de flexión, cortante, servicio y anclaje. Se conserva el caso y
la sección de cada control, usando la envolvente de todas las combinaciones y
ambos estribos. La temperatura se desarrolla por región y conserva las áreas
colocadas en cada cara y dirección. La fisuración sin tracción de servicio se identifica como no
gobernante, sin calcular separaciones artificiales. Las conclusiones identifican
las distribuciones que no cumplen y los anclajes rectos insuficientes.
Los casos se identifican por el nombre de la combinación. Las envolventes NVM
se separan en Resistencia Ia, Resistencia Ib, Servicio I y Evento Extremo I por
cada par simultáneo y por condición con o sin tablero. Evento Extremo I reúne
A/B y ambos sentidos sísmicos. Al final del apartado 6 se presenta la envolvente
general NVM de todas las combinaciones, referencia para el diseño del apartado 8.
El concreto armado se desarrolla una sola vez por región, con sus controles
gobernantes y los esfuerzos simultáneos de cada sección. Se omiten los diseños
de transiciones y cajuelas, sus apartados de servicio y detallado y sus filas de resumen.

El apartado 7 presenta cuatro envolventes de presiones y asentamientos:
Resistencia Ia, Resistencia Ib, Servicio I y Evento Extremo I. Cada una reúne
todos sus casos con y sin tablero. Las presiones proceden del análisis de cada
caso mediante reacción del resorte dividida por su área tributaria. Se desarrolla
qlím y se verifica la presión máxima de cada envolvente. Se declara la hipótesis
de capacidad nominal FS·qadm y no se acredita cumplimiento de asentamientos sin
un límite admisible. El Word no desarrolla
deslizamiento ni utiliza Meyerhof como demanda de presión.
La presión límite mantiene la aproximación nominal FS·qadm ya implementada.
`--sin-word` omite la generación de Word, pero no la selección de acero;
`--resultados RUTA` cambia la carpeta de TXT, JSON, CSV y gráficos. El Word
interactivo solicita ubicación mediante ventana; en modo automático usa esa carpeta.
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

## Armado comun de estribo

El YAML nuevo contiene un solo bloque `estribo` para geometria, materiales, suelo
y criterios de armado. `cargas_tablero_derecho` permite modificar las reacciones
del derecho sin duplicar geometria. Los archivos antiguos con `estribo_izquierdo`
y `estribo_derecho` siguen siendo legibles cuando geometria, materiales y criterios
de armado coinciden; una incompatibilidad produce un error explicito.

El FRAME conserva los dos estribos, las cargas simultaneas y sus resortes. Se
identifican primero las caras fisicas de cada lado y luego se agrupan sus
secciones en Pantalla, Zapata y Parapeto. Cada distribucion comun se comprueba
en todas las secciones de ambos lados y todos los casos, manteniendo M y V
simultaneos. Las verificaciones de flexion, cortante y servicio conservan su
propio lado, elemento y combinacion gobernante, visibles en consola y Word.
Las longitudes rectas disponibles siguen el detalle continuo definido: pantalla
en zapata, losa dentro del ancho de zapata y parapeto en toda la altura del estribo,
menos recubrimiento. Talon y puntera cruzan la pantalla hasta el borde opuesto
de zapata; no se limita el anclaje al propio voladizo. Una eleccion de acero comun
se aplica a ambos lados; la losa conserva sus cuatro distribuciones propias.


## Opcion de corte de acero de pantalla

Las tablas de opciones y el resumen final presentan un corte solo para el
acero vertical del relleno de pantalla, calculado con la distribucion
propuesta o elegida. El acero vertical exterior conserva su distribucion
continua y no genera propuesta de corte en consola, JSON ni memoria Word.
Se reutiliza el motor de estribos individuales: misma barra, continuidad de
una de cada N barras, altura teorica, prolongacion ld, altura constructiva y
longitudes de barras cortadas y continuas. Se exporta en `resultados.json`
y en la memoria Word. Es una opcion de detalle; el armado uniforme sigue
siendo la distribucion seleccionada para las verificaciones generales.

El adaptador conectado comprueba la envolvente FRAME de ambos lados por cara,
incluidos flexion, cortante, servicio y minimos en todo el tramo superior.
Conserva elementos completos y su espesor menor al buscar el corte, sin
suponer que la demanda disminuye monotonamente con la altura. La propuesta
puede ser conservadora y depende de la malla del analisis. Las alturas parten
de la cara superior de zapata y las longitudes llegan al inicio de la
transicion de cajuela: el parapeto conserva su distribucion independiente.
El detalle de union con la cajuela se resuelve aparte.

`NO APLICA` indica que no hay reduccion admisible con el acero elegido o que
la distribucion no cumple sus comprobaciones. `NO CONVIENE` indica que la
prolongacion de desarrollo lleva el corte al extremo superior del tramo.
Una seleccion nueva recalcula la opcion; el programa no impone el corte.


### Secciones de diseño de zapatas

Talón y puntera se separan por las caras físicas de la pantalla. Los elementos
bajo la pantalla no pertenecen a ninguna de las dos distribuciones. Se conserva
el valor de N, V y M del elemento inmediatamente exterior a cada cara, sin
aprovechar el traslado de la sección de cortante por compresión en el apoyo.
También se revisan las estaciones interiores y los extremos recuperados por el
FRAME, con sus esfuerzos simultáneos. Cada control selecciona su propio máximo
de utilización. Las transiciones inferiores se comprueban con el armado de la
losa central, sus materiales y recubrimiento, usando el espesor de cada sección.
Los reportes identifican las caras y las transiciones cuando gobiernan.
Esta modificación no incorpora interacción axial-momento en flexión.
