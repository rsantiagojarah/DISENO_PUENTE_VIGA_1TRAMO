# Informe de revisión de cálculos y criterios de ingeniería

Actualización del código (8 de septiembre de 2026): véase
[implementación y estado de H18–H34](IMPLEMENTACION_AUDITORIA_H18_H34.md).
El diagnóstico que sigue conserva la versión y los resultados de la auditoría original.

Proyecto: DISEÑO_PUENTE_VIGA_1TRAMO  
Fecha: 6 de septiembre de 2026  
Versión de referencia del repositorio: `715b60f`  
Normativa solicitada: Manual de Puentes MTC 2018  
Modalidad: revisión del código existente, sin modificar código fuente ni tests.

## 1. Dictamen ejecutivo

**Sí se encontraron errores de cálculo y de verificación, además de modelos que necesitan justificación de ingeniería. El programa, en su estado revisado, no permite concluir que todos sus resultados cumplen el Manual de Puentes MTC 2018.**

Lo más importante no es la presentación del programa: existen situaciones en las que una comprobación indica «OK», «CUMPLE» o una armadura recomendada, aunque no se satisface la condición resistente correspondiente. También hay errores que aparecen con los datos predeterminados, no únicamente con entradas extremas.

Ejemplos demostrados:

| Comprobación | Resultado del código | Comprobación independiente | Hallazgo |
|---|---|---|---|
| Pantalla del estribo predeterminado | Capacidad indicada: 77.651 Tn·m/m, cumple | Para Resistencia I: 0.90 Mn = 69.886 < Mu = 71.488 Tn·m/m | H01 |
| Estribos de viga, sección de ejemplo | Ofrece opciones conformes | Vu = 238.140 Tn > resistencia máxima factorizada = 226.800 Tn | H02 |
| Apoyo móvil de ejemplo | Todas las comprobaciones indican OK | H térmica = 5.248 Tn > fricción disponible = 4.000 Tn | H03 |
| PEP fijo con sismo calculado automáticamente | Restricción fija: demanda 0, OK | El propio módulo calcula H sísmica = 20 Tn | H04 |
| Excentricidad sísmica del estribo predeterminado | e = 1.423 m < límite del código 1.828 m | Con γEQ = 0.50, límite MTC = 1.332 m | H07 |

Se documentan **34 hallazgos** y **6 observaciones de alcance/justificación**. Los hallazgos no equivalen a 34 fallas simultáneas de un puente particular: varios dependen de la geometría o del modo seleccionado. Se especifica cuándo son condicionales, cuándo son conservadores y cuándo pueden reducir la seguridad.

**Recomendación:** no utilizar por sí solos los estados globales «OK» ni los detalles automáticos como aprobación de un diseño constructivo. Primero deben resolverse los hallazgos críticos y altos y recalcularse los elementos afectados. Este informe identifica cambios recomendados, pero no los implementa.

## 2. Alcance, método y fuentes

### 2.1 Alcance efectivamente revisado

Se revisaron las formulaciones y los flujos de cálculo de los módulos de materiales, cargas, combinaciones, losa transversal, voladizo, barrera, vigas interiores/exteriores, detallado de vigas, diafragmas, estribo, muro en voladizo y las tres familias de apoyos. También se revisaron las utilidades compartidas de armaduras, fisuración, unidades, demandas PEP, curvas de elastómeros y las transferencias de reacciones relevantes para el estribo.

El análisis se centró en fórmulas, equilibrio, unidades, condiciones de aplicabilidad, factores de carga/resistencia y coherencia entre demanda, sección adoptada y comprobación final. Se ejecutaron comprobaciones numéricas puntuales mediante llamadas al código y cálculos independientes en memoria; no se usó la aprobación de los tests como prueba de cumplimiento normativo.

No se elaboró un modelo independiente completo de un puente específico ni se verificaron planos constructivos, estudio de suelos o condiciones reales de emplazamiento. Tampoco se certifica la ausencia de cualquier otro error en todas las combinaciones posibles de entradas o en todos los formatos de exportación. La cobertura corresponde a los módulos de cálculo existentes, no a una certificación integral de una obra.

### 2.2 Fuentes y jerarquía

Fuente técnica principal: `docs/Manual de Puentes MTC 2018 (PGA).pdf`, disponible en el proyecto. Se consultó su texto y se inspeccionó visualmente la ecuación de armadura superficial de la página impresa 335. Las páginas citadas en este informe son las **páginas impresas del manual**; en este archivo PDF su posición es cuatro páginas mayor.

La edición se contrastó con la [Resolución Directoral N.° 19-2018-MTC/14](https://www.gob.pe/institucion/mtc/normas-legales/4441255-19-2018-mtc-14), que aprueba el Manual de Puentes, y con el [catálogo oficial de manuales del MTC](https://portal.mtc.gob.pe/transportes/caminos/normas_carreteras/manuales.html).

Para aclarar el comportamiento barrera–voladizo se consultó además el [ejemplo oficial FHWA de diseño de tablero y voladizo](https://www.fhwa.dot.gov/bridge/lrfd/pscus04.cfm). Se usa como fundamento de ingeniería AASHTO, no como sustitución automática de la normativa peruana.

Las memorias y ejemplos del proyecto se consideraron documentación del modelo, no demostraciones independientes de validez. Una etiqueta «MTC» o una referencia AASHTO en el código no acredita por sí sola que la ecuación implementada corresponda al artículo citado.

### 2.3 Criterio de clasificación

- **Crítica:** comprobación que puede aprobar una condición insegura o perder una acción esencial.
- **Alta:** error que puede subestimar demanda, sobreestimar capacidad o generar un detalle no válido.
- **Media:** inconsistencia, desviación condicionada o cálculo conservador que debe corregirse, sin demostrar inseguridad general.
- **Observación:** limitación o hipótesis que requiere justificación; no se presenta como una infracción demostrada para todos los casos.

«Confirmado» significa que el defecto de formulación o del flujo de datos se identifica en el código. No significa que todos los resultados de ese módulo sean incorrectos. Las ubicaciones se expresan como `archivo.py:línea` y corresponden a la versión revisada. Salvo indicación contraria, los archivos están en `src/bridge_design/domain/`.

## 3. Matriz de cobertura por módulo

| Módulo o familia | Evaluación de las formulaciones revisadas | Referencias del informe |
|---|---|---|
| `materials.py`, `units/converters.py` | Conversiones principales y formulación de Ec coherentes dentro de su rango declarado; no se encontró un error aritmético específico en estas operaciones | O06 sobre validación |
| `loads.py`, `codes/mtc_2018.py` | Base HL-93, IM y presencia múltiple reconocibles; confusión entre ancho cargado y carril de diseño | H14 |
| `load_combinations.py` | Factores básicos DC, DW y LL de Resistencia I/Servicio I coherentes; el resultado depende de que los patrones de carga sean completos | H14, H15, H20, H29 |
| `transverse_slab.py`, `reinforcement.py` | Modelo de franjas utilizable con restricciones; mínimos, sección efectiva, patrones y ancho de franja requieren corrección | H08–H10, H12–H16 |
| `cantilever_slab.py` y sus tres auxiliares | Cargas gravitatorias con brazos de palanca reconocibles; omisión de LL fuera del rango de cuchilla y modelo incompleto de colisión | H08–H10, H12, H13, H16–H18 |
| `barrier.py` | Modelo de líneas de fluencia para una sección particular; geometría general y submodelo resistente pueden divergir | H09, H18, H19; O04, O05 |
| `interior_girder.py` | Análisis de viga simple y base de distribución/fatiga reconocibles; selección resistente, armaduras mínimas/superficiales y cortante de carril observados | H02, H08–H16 |
| `exterior_girder.py` | Hereda problemas del núcleo de vigas; la ampliación automática de capas añade una limitación importante | H02, H08–H16 |
| `girder_detailing.py` | Detallado parcial; algunas comprobaciones posteriores sí verifican capacidad, pero no subsanan todo el diseño inicial | H02, H08; O04 |
| `diaphragm.py` | No se acredita la distribución longitudinal de cargas empleada; hereda problemas de armadura y selección de estribos | H02, H08–H10, H12, H14; O01 |
| `abutment.py` | Hallazgos demostrados en resistencia de pantalla, estabilidad sísmica, zapata, cortante, geometría y dentellón | H01, H07–H09, H12, H13, H16, H20–H27; O02–O04 |
| `cantilever_wall.py` | Reutiliza y normaliza el motor de estribos; no constituye un cálculo independiente que evite sus errores | Hallazgos compartidos de `abutment.py`, en especial H26 |
| `elastomeric_bearing.py` | Base del Método A identificable; movimientos, carga de resistencia y estados de anclaje requieren corrección | H28–H30, H33 |
| `simple_neoprene_support.py` | Comprobación global de apoyo móvil puede aprobar fricción insuficiente; fijo limitado al detalle de pasadores implementado | H03, H28, H29; O04 |
| `pep_bearing.py` | Distingue pad y aparato completo, pero pierde la demanda sísmica automática en una ruta y mezcla estados | H04, H28–H32 |
| `pep_steel_components.py` | Errores en distribución de momento y transferencia de tracción al concreto; anclaje de grupo incompleto | H05, H06, H29, H31 |
| `pep_demands.py` | Conservar casos completos es positivo; esa intención no evita los errores de transferencia posteriores | H04, H29; O06 |
| `pep_strain_curves.py` | Interpolación y datos no garantizan una curva físicamente consistente | H32 |
| `pep_normative_matrix.py` | Matriz documental; no sustituye una verificación ni valida las funciones que referencia | O06 |
| `rebar_catalog.py`, `crack_control.py` | Áreas/separaciones básicas reconocibles; existe recomendación físicamente imposible y control parcial de fisuración | H12, H13 |
| `sampling.py`, `project_inputs.py`, validadores | Interpolación/agregación auxiliares; no se encontró una ecuación estructural independiente errónea; quedan controles de dominio | O06 |
| Resumen de reacciones en `cli/ascii_output.py` | Suma máximos de vigas sin demostrar simultaneidad global | H34 |

## 4. Hallazgos detallados

### H01. Factor de resistencia incorrecto en la pantalla del estribo

**Gravedad: crítica. Confirmado, con reproducción sobre los datos predeterminados.**

Ubicación: `abutment.py:239`, `_structural_design` en línea 1652, `_stem_design_demands` en línea 2437.

`stem_design_phi_for_as` vale 1.00. El diseño toma el mayor momento entre Resistencia I y Evento Extremo y utiliza ese mismo factor para dimensionar/verificar la pantalla. No separa las resistencias de cada estado límite.

El MTC 2.7.1.1.4.2a, página 218, establece φ = 0.90 para secciones de concreto armado controladas por tracción en resistencia. La eventual utilización de φ = 1.00 en evento extremo no autoriza a usarlo en Resistencia I.

En el cálculo predeterminado:

- Mu de Resistencia I = 71.488083 Tn·m/m.
- Mu de Evento Extremo = 72.436292 Tn·m/m.
- Capacidad presentada con φ = 1.00 = 77.650859 Tn·m/m.
- Capacidad para Resistencia I, incluso manteniendo todas las otras hipótesis del código: 0.90 × 77.650859 = 69.885773 Tn·m/m.

Por tanto, **69.885773 < 71.488083**. La aprobación de la pantalla no es válida para Resistencia I. Se debe dimensionar por el máximo requerimiento de acero de los distintos estados, no por el máximo momento bruto con un único φ.

### H02. Selección automática de estribos sin verificar la resistencia máxima

**Gravedad: crítica. Confirmado.**

Ubicación: `interior_girder.py:1921`, `_generate_shear_stirrup_options`; utilizado también por viga exterior y diafragma.

El código calcula `phi_vn = phi * min(Vc + Vs, nominal_limit)`, pero marca `is_compliant` únicamente con área transversal y separación. La función ni siquiera recibe Vu para comprobar `phi_vn >= Vu`.

Ejemplo con f'c = 280 kgf/cm², fy = 4200 kgf/cm², bw = 30 cm, dv = 120 cm y φ = 0.90: la resistencia máxima factorizada es 226.800 Tn. Para Vu = 238.140 Tn, las opciones con suficiente Av/s se marcan conformes aunque ninguna puede superar aquel límite.

Fundamento: MTC 2.9.1.5.6.3, resistencia nominal y límite superior del modelo seccional de cortante. Agregar estribos no elimina el límite de compresión del concreto.

Debe comprobarse el límite antes de recomendar armaduras y verificarse explícitamente φVn ≥ Vu en cada opción. Las rutas de estribo personalizado y ciertas estaciones de detallado sí realizan comprobaciones adicionales: esto reduce, pero no elimina, la inconsistencia de la selección automática.

### H03. El apoyo móvil simple aprueba una fricción insuficiente

**Gravedad: crítica. Confirmado, con ejemplo numérico.**

Ubicación: `simple_neoprene_support.py:420`, `_movable_plate_checks`.

La comprobación mostrada es Hpad ≤ μRDC, pero el límite realmente comparado es `max(friction, h_pad)`. Así, Hpad nunca supera su propio límite. La nota reconoce que hace falta una guía/anclaje, pero la ausencia de ese detalle no impide la aprobación global.

Ejemplo: MOVIL_PLACAS; neopreno 60 × 40 × 5 cm; Shore 60; RDC = 20 Tn; restantes cargas verticales = 0; luz 30 m; temperatura predeterminada de costa; μ = 0.20; planchas predeterminadas. Se obtiene Hpad = 5.247867 Tn y fricción = 4.000 Tn. La fila imprime 5.248 ≤ 4.000 y, aun así, da «OK»; todas las filas del resultado dan «OK».

Debe fallar o quedar pendiente hasta comprobar un mecanismo real de transferencia. Una advertencia textual no equivale al diseño de ese mecanismo.

### H04. La acción sísmica automática del PEP fijo no llega a sus componentes

**Gravedad: crítica. Confirmado, con reproducción.**

Ubicación: `pep_bearing.py:407`, ruta de verificación; transferencia a `ComponentDemands` aproximadamente en línea 840.

Cuando no se introduce H sísmica explícita, el módulo calcula una acción a partir de As y la carga permanente. Para el apoyo fijo, sin embargo, las componentes finalmente transmitidas utilizan `dem.h_eq_long_tn` y `dem.h_eq_trans_tn`, no el valor sísmico resuelto.

Ejemplo: PEP fijo, RDC = 100 Tn, restantes cargas y H explícitas nulas, As predeterminado = 0.20. El resultado informa H sísmica = 20 Tn y H de anclaje = 20 Tn; las dos filas de restricción fija presentan demanda 0 y «OK». La ruta de placas/pernos recibe H = 0.

Debe existir una única demanda sísmica resuelta, con dirección y combinación definidas, usada tanto por el informe como por cada componente. El fallo se refiere a la ruta automática; introducir una H explícita puede evitarlo.

### H05. Distribución incorrecta del momento entre pernos

**Gravedad: crítica. Confirmado por equilibrio.**

Ubicación: `pep_steel_components.py:335`, dentro de `verify_bolts_and_welds`.

Para un momento alrededor del eje transversal el código usa `M*x/(Σx² + Σy²)`. Ese denominador polar corresponde a otro problema de distribución, no a la flexión uniaxial indicada. En el modelo elástico lineal descrito por sus comentarios, corresponde `M*x/Σx²`, con signos y zona de compresión compatibles.

Ejemplo: cuatro posiciones (±20, ±20) cm y M = 10 Tn·m. El código asigna 6.25 Tn como máximo por momento; la distribución elástica uniaxial proporciona 12.50 Tn. El campo lineal calculado con el denominador polar sólo equilibra la mitad del momento de este ejemplo.

La solución definitiva debe considerar contacto placa–concreto y anclas sólo a tracción. No basta con cambiar un denominador si el modelo de contacto no corresponde al detalle real.

### H06. Anclaje al concreto: se pierde la tracción por momento y se aproxima indebidamente el grupo

**Gravedad: crítica. Confirmado.**

Ubicación: `pep_steel_components.py:469`, `verify_concrete_anchorage`.

La tracción de cálculo se toma exclusivamente como `t_uplift/n`. No recibe la tracción producida por el momento que sí aparece en la comprobación del acero de los pernos. Para momento distinto de cero y levantamiento global nulo, las verificaciones de tracción del concreto presentan demanda cero.

El mismo módulo calcula el cono de arrancamiento del grupo como `n * Nb * psi`, y el propio comentario admite que no considera el solapamiento de áreas proyectadas. No utiliza las coordenadas para construir el área efectiva del grupo ni resuelve la rotura del concreto por cortante hacia un borde. El área de cabeza para extracción se infiere del diámetro del vástago, en lugar de representar el detalle real.

Se requiere transferir las tracciones efectivas de los pernos al modelo del concreto y verificar los modos aplicables con geometría real, bordes, separaciones, condición de fisuración y edición normativa expresamente adoptada. No se propone aquí una ecuación ACI aislada como reemplazo automático del conjunto de requisitos MTC/AASHTO.

### H07. Límite de excentricidad sísmica distinto del MTC 2018

**Gravedad: crítica. Confirmado, afecta el caso predeterminado.**

Ubicación: `abutment.py:1558`, selección de `minimum_contact_ratio` y cálculo de `e_limit`.

El límite sísmico del código es e ≤ 7B/18, al exigir un tercio de longitud de contacto. MTC 2.8.1.1.14.1, página 247, exige otra condición: resultante en el tercio central para γEQ = 0 y en las ocho décimas centrales para γEQ = 1, con interpolación.

En términos de excentricidad absoluta:

`e_lim = B * [1/6 + γEQ * (0.4 - 1/6)]`.

Para γEQ = 0.50 y B = 4.70 m: e_lim = 1.331667 m. El programa permite 1.827778 m y aprueba e = 1.422570 m en el estado sísmico predeterminado con puente.

La longitud comprimida y la posición normativa de la resultante son comprobaciones relacionadas, pero no intercambiables con los límites actuales. Deben verificarse por separado.

### H08. El peralte efectivo no representa necesariamente la armadura adoptada

**Gravedad: alta. Confirmado; efecto dependiente del detalle seleccionado.**

Ubicación: `reinforcement.py:307`, `interior_girder.py:603`, `:1032`, `:1676`, `:1696`; `exterior_girder.py:730`; rutas análogas de diafragma, voladizo y estribo.

El dimensionamiento utiliza un diámetro supuesto y un peralte de una capa. Después se seleccionan otros diámetros o varias capas sin actualizar de forma consistente el centroide del acero y repetir la resistencia. La viga exterior incrementa el número admisible de capas para hacer caber el área, pero no cierra una comprobación geométrica/resistente con todas las capas reales.

Una segunda o tercera capa eleva el centroide de las barras inferiores y reduce d. Calcular la capacidad con d de la capa inferior sobreestima el brazo interno. Algunas verificaciones posteriores cambian el diámetro, pero siguen sin reconstruir el centroide multicapa.

Fundamento: equilibrio y compatibilidad de la sección, MTC 2.7.2.4 y 2.9.1.4. Debe calcularse d con el detalle realmente adoptado, aclarando si el recubrimiento se mide a estribo o barra principal, e iterarse hasta cumplir resistencia, servicio y espacio disponible.

### H09. Las funciones de flexión no comprueban el dominio de deformaciones

**Gravedad: alta. Confirmado, con contraejemplo.**

Ubicación: `reinforcement.py:182`, `flexural_steel_area_cm2`; `interior_girder.py:978`, cálculo de sección T; fórmulas equivalentes en barrera y estribo.

La raíz de la ecuación rectangular garantiza equilibrio algebraico suponiendo acero a fy, pero no demuestra que éste fluya ni que la sección sea controlada por tracción. La discriminante positiva no es un criterio de ductilidad.

Ejemplo: b = 100 cm, d = 20 cm, f'c = 280 kgf/cm², fy = 4200 kgf/cm², φ = 0.90, Mu = 40 Tn·m. La función devuelve As = 84.152876 cm² y a = 14.850507 cm. Con β1 = 0.85, c = 17.471185 cm y εt ≈ 0.000434, incompatibles con asumir acero a fy y sección controlada por tracción.

MTC 2.7.1.1.4.2a, página 218, distingue factores según deformación y menciona εt = 0.005 para el extremo controlado por tracción. Deben verificarse compatibilidad, fluencia y φ antes de aceptar la solución. No se recomienda sustituir esto por un antiguo límite fijo de c/d sin comprobar su aplicabilidad a la edición solicitada.

### H10. Los mínimos de flexión no se contrastan con el criterio del MTC

**Gravedad: alta. Confirmado como verificación ausente.**

Ubicación: `reinforcement.py:141` y `:237`; `interior_girder.py:2001`; herencia en viga exterior y diafragma; `_cantilever_slab_calculations.py`.

En losas se usa la cuantía de retracción/temperatura como mínimo de flexión. En vigas se utiliza `max(0.8√f'c/fy, 14/fy) bw d`. Estas expresiones no comprueban explícitamente el mínimo resistente exigido por MTC 2.9.1.4.4.2, páginas 333–334, basado en el menor de 1.33Mu y el momento de fisuración definido allí.

Ejemplo orientativo del defecto: franja b = 100 cm, h = 20 cm, d = 14.205 cm y Mu = 2 Tn·m. El acero por resistencia es 3.815161 cm², mayor que 0.0018bh = 3.60 cm², pero sólo restituye Mu. Con acero A615 grado 60 y concreto normal, el Mcr del artículo es aproximadamente 2.40 Tn·m, menor que 1.33Mu = 2.66 y mayor que 2.00. La fórmula de área mínima no asegura ese requisito; la selección discreta puede o no cubrirlo accidentalmente.

Debe verificarse la resistencia de la armadura adoptada frente al mínimo normativo. Los coeficientes de Mcr dependen del tipo de acero: no corresponde imponer 1.2frS como valor universal. El estribo tiene una comprobación específica de mínimo, aunque su aproximación también debe vincularse al acero realmente adoptado.

### H11. Fórmula incorrecta de armadura superficial lateral de vigas

**Gravedad: alta. Confirmado mediante lectura visual de la ecuación.**

Ubicación: `interior_girder.py:2022`; utilizada también por la viga exterior.

El código calcula `Ask = 0.0012 * bw_cm * (d_cm - 90)` por cara y por metro. MTC 2.9.1.4.4.3, página 335, ecuación -2, presenta `0.012(d_in - 30)` en in²/ft, para los miembros a los que aplica el requisito. Su conversión es `0.1(d_cm - 76.2)` en cm²/m por cara, antes de considerar el límite de área del propio artículo.

Para d = 140 cm y bw = 40 cm: código 2.40 cm²/m; expresión normativa 6.38 cm²/m. La diferencia no es un redondeo: el código introduce una dependencia de bw que la expresión citada no tiene y desplaza su término constante.

Además, el límite de separación normativa es el menor de d/6 y 300 mm; el módulo utiliza un máximo configurable de 300 mm sin aplicar automáticamente d/6. Para d = 140 cm, d/6 = 233 mm.

Debe implementarse conjuntamente el rango de aplicación, el área por cara, su límite respecto al acero longitudinal y el espaciamiento. El ejemplo de área supone que ese límite de área no gobierna.

### H12. El catálogo puede recomendar una separación imposible

**Gravedad: alta. Confirmado, con reproducción.**

Ubicación: `rebar_catalog.py:194`, `_spacing_option`; `_recommended_option` aproximadamente en línea 222.

Si ninguna opción cumple el intervalo de separación, la selección recurre a cualquier opción con área suficiente. La conformidad se basa en área, no en separación mínima ni espacio libre real.

Ejemplo ejecutado: As requerida = 200 cm²/m; intervalo solicitado 0.10–0.30 m; paso 0.025 m. El resultado recomendado es barra de 1 pulgada a 0.025 m, marcada conforme. Su diámetro es 0.0254 m: **la separación entre ejes es menor que el diámetro**, de modo que las barras se superponen.

También deben imponerse los máximos normativos de separación según elemento y espesor, no únicamente un máximo genérico del catálogo. Se debe devolver «sin solución con este catálogo/geometría» cuando no exista un detalle construible, sin relajar silenciosamente restricciones.

### H13. El control de fisuración puede ocultar un esfuerzo de servicio excesivo

**Gravedad: alta. Confirmado.**

Ubicación: `crack_control.py:140`; `abutment.py:2039`; revisión de fisuración en `_cantilever_slab_checks.py`.

Se calcula el esfuerzo del acero, se sustituye por `min(fs, 0.60fy)` y se decide el cumplimiento sólo mediante espaciamiento. Si fs real excede 0.60fy, la fila puede aprobar igualmente.

MTC 2.9.1.4.4.3, página 334, exige que el esfuerzo de servicio no exceda 0.60fy. Limitar numéricamente el esfuerzo usado en una ecuación no demuestra ese límite.

Se requieren dos comprobaciones: esfuerzo real admisible y espaciamiento de fisuración, con las hipótesis de sección y acciones axiales correspondientes. Las vigas tienen verificaciones adicionales de esfuerzos de servicio que pueden detectar algunos casos; no debe atribuirse esa protección a los módulos que no la poseen.

### H14. Carriles de diseño y patrones transversales incompletos

**Gravedad: alta. Confirmado; incidencia dependiente del ancho del tablero.**

Ubicación: `codes/mtc_2018.py:876`, datos HL-93; funciones de distribución exterior en líneas 584 y 614; `transverse_slab.py:373`; `diaphragm.py:252` y generación de vehículos.

El dato `design_lane_width_m` vale 10 ft = 3.048 m. MTC 2.4.3.2.1 distingue carriles de diseño —en general de 3.60 m, con sus excepciones— del ancho transversal de aplicación de la carga de carril. El dato de 10 ft se utiliza para contar o colocar carriles en algunas funciones, mientras la losa transversal emplea 3.60 m.

La losa y el diafragma sólo analizan uno o dos vehículos/carriles. No rechazan de forma general tableros para los que deban estudiarse más. Además, el grupo transversal se mueve con separación fija entre vehículos, sin explorar todas las posiciones independientes desfavorables permitidas. Las cargas peatonales se combinan como un patrón conjunto, sin una envolvente completa de presencia por zonas.

Debe separarse ancho de carril, ancho cargado y espaciamiento de ruedas, determinar los carriles realmente admisibles y formar los patrones exigidos por MTC 2.4.3.2.3 y sus condiciones. Las diferencias pueden sobredimensionar unas vigas y subestimar otras; no tienen un único signo conservador.

### H15. La carga de carril no se ubica para maximizar el cortante interior

**Gravedad: alta. Confirmado por línea de influencia.**

Ubicación: `interior_girder.py:1257`, `_solve_moving_vehicle_case`; funciones de cortante en líneas 1511 y 1526. Afecta también la viga exterior.

La carga uniforme de carril se mantiene en toda la luz. Para momento positivo de una viga simplemente apoyada esto es apropiado; para cortante en una sección interior, la línea de influencia cambia de signo y debe cargarse la parte desfavorable.

Para sección x, luz L y carga de carril w, sin factores de distribución:

`V_carril, código = w(L/2 - x)`.

La contribución máxima positiva al cargar desde x hasta L es:

`V_carril, máximo = w(L - x)²/(2L)`.

La diferencia es `w x²/(2L)`. En el centro de luz el código aporta cero, pero la carga parcial aporta wL/8. El defecto es independiente de la búsqueda correcta de posición del camión. Deben formarse envolventes positivas y negativas de carril compatibles con el efecto buscado.

### H16. Inconsistencia de unidades al cambiar el ancho de franja

**Gravedad: alta para anchos distintos de 1 m. Confirmado.**

Ubicación: `transverse_slab.py:32`, generadores de cargas; `reinforcement.py:237`; `_cantilever_slab_loads.py:95`; `abutment.py:1109`, `:1261`, `:1274` y diseño estructural por metro.

Las entradas permiten variar la longitud/ancho de franja. Sin embargo, en la losa varias cargas permanecen expresadas para un metro, mientras la sección y la normalización del acero cambian. En el voladizo, la cuchilla se multiplica por la franja y otras acciones permanecen por metro. En el estribo se multiplican pesos de concreto y suelo por la franja, mientras otras fuerzas, presiones de contacto y resistencias siguen tratadas por metro.

No existe una escala homogénea de fuerzas, momentos, sección y salida. El valor predeterminado de 1 m oculta el problema. Debe fijarse obligatoriamente una franja unitaria o escalar todo el cálculo de forma consistente y devolver magnitudes claramente totales o por metro.

### H17. Al salir del rango de la cuchilla, el voladizo pierde la carga vehicular

**Gravedad: alta. Confirmado.**

Ubicación: `_cantilever_slab_loads.py:99`.

Cuando el volado supera el límite de aplicación de la carga tipo cuchilla —6 ft en la constante utilizada—, el código añade una nota y no añade ninguna carga vehicular alternativa. El dimensionamiento continúa con las acciones restantes.

MTC 2.4.3.2.3.4 permite una sustitución simplificada bajo determinadas condiciones; salir de su rango no elimina las ruedas reales ni su efecto. Además, debe comprobarse la distancia definida por el artículo, no identificar automáticamente toda distancia desde el borde con la distancia normativa.

Se requiere un cálculo alternativo de ruedas/distribución o bloquear el diseño como fuera de alcance. La nota existente es útil, pero insuficiente para que el dimensionamiento siga tratándose como completo.

### H18. La colisión barrera–voladizo se reduce a una flexión insuficientemente justificada

**Gravedad: alta. Omisión confirmada; magnitud del déficit dependiente de la barrera.**

Ubicación: `_cantilever_slab_checks.py:33`, `design_barrier_collision`; dimensionamiento en `_cantilever_slab_calculations.py`.

El código obtiene `Ft/(Lc + 2H)` y lo multiplica por H, sumándolo al momento permanente. Utiliza Ft solicitado, no necesariamente la resistencia desarrollable de la barrera. El acero del voladizo se dimensiona a flexión sin incorporar una tracción axial simultánea derivada de esa transferencia.

El criterio de diseño por capacidad de la conexión y la acción combinada de flexión y tracción están ilustrados en el [ejemplo oficial FHWA para voladizos con parapeto de concreto](https://www.fhwa.dot.gov/bridge/lrfd/pscus04.cfm): el tablero debe poder recibir la resistencia de la barrera y se considera la tracción simultánea por colisión. Esta referencia fundamenta la observación de ingeniería; los artículos MTC generales citados por la función no demuestran que su simplificación sea equivalente.

Debe verificarse el mecanismo completo, las secciones críticas, el momento y la tracción simultáneos, así como los casos de colisión aplicables. No se afirma que todo voladizo calculado resulte insuficiente, sino que la formulación actual no acredita el requisito.

### H19. La geometría de la barrera y su submodelo resistente pueden representar secciones diferentes

**Gravedad: alta cuando se personaliza la geometría. Confirmado.**

Ubicación: `barrier.py`, `BarrierGeometry`, `BarrierSectionModel` y `new_jersey_image_default` aproximadamente en línea 110.

La geometría global admite altura, ancho de base y área, pero los segmentos para Mc/Mw contienen alturas, peraltes y armaduras de una barrera particular. No hay una reconstrucción automática ni una validación completa de correspondencia entre ambos modelos.

Cambiar la altura/base/área puede modificar pesos, brazos o longitud crítica sin cambiar coherentemente la sección que proporciona la resistencia. El peso lineal usado por el tablero también procede de un dato de materiales separado de la geometría resistente de barrera.

Debe existir una geometría única que genere pesos y secciones resistentes, o exigirse y comprobarse explícitamente toda la información de los segmentos. El modelo predeterminado de una barrera concreta no debe interpretarse como un modelo general de cualquier barrera.

### H20. El talón mezcla factores de carga incompatibles con la reacción de suelo

**Gravedad: alta. Confirmado.**

Ubicación: `abutment.py:2515`, `_heel_design_demands`.

Las acciones descendentes del talón siempre usan 1.25 para concreto, 1.35 para suelo y 1.75 para sobrecarga. La reacción ascendente procede, en cambio, del estado recibido, que puede tener factores mínimos o corresponder a Evento Extremo.

Restar cargas de una combinación a la reacción de otra no constituye un diagrama de cuerpo libre consistente. Puede aumentar o reducir el momento neto; no basta con llamarlo conservador. El valor absoluto final oculta además el signo.

Fundamento: equilibrio del elemento y MTC 2.8.1.1.13, página 247, respecto a la presión de contacto utilizada para diseño estructural, junto con las combinaciones de 2.4.5.3.1.

Debe reconstruirse cada caso del talón con factores únicos, integrar su presión correspondiente y conservar el signo para diseñar la cara traccionada.

### H21. La selección de casos para zapata no garantiza su envolvente estructural

**Gravedad: alta. Confirmado como cobertura incompleta.**

Ubicación: `abutment.py:653`, llamada a `_structural_design`; selección de caso sísmico en `:1483`; diseño en `:1652`.

El cálculo sísmico forma dos alternativas, pero resume una mediante una severidad global de estabilidad. La alternativa más desfavorable para estabilidad no tiene por qué maximizar la flexión o el cortante local del talón/puntera. Para estribos con puente, el diseño estructural utiliza los estados con puente, aunque también se calculan estados sin puente.

Además, el detallado asigna esencialmente talón superior y puntera inferior, sin construir de forma completa las envolventes de inversión de momento. La puntera considera la reacción ascendente sin descontar todas las cargas descendentes locales: suele ser conservador para flexión inferior, pero no resuelve una posible inversión.

Deben recorrerse todos los casos físicos y estados aplicables, incluidos los constructivos que correspondan, y obtener por separado M+, M− y V. No debe seleccionarse el acero local mediante un indicador global de estabilidad.

### H22. La capacidad de cortante de estribo/muro emplea d en lugar de dv

**Gravedad: alta. Confirmado.**

Ubicación: `abutment.py:1757`, `_reinforced_case`; cálculo resistente en `:2990`.

El módulo calcula un peralte efectivo de cortante dv para β, pero entrega el peralte de flexión d a la expresión de Vc. El modelo seccional MTC 2.9.1.5.6 utiliza dv.

En la pantalla predeterminada: d = 84.0475 cm, dv = 75.64275 cm. La capacidad presentada es 34.692003 Tn/m. Sustituir únicamente d por dv, sin cambiar β ni otros datos, produce 31.222803 Tn/m. La capacidad actual es 11.11 % mayor que esa capacidad coherente.

Esto no demuestra por sí solo que el cortante predeterminado falle; demuestra una sobreestimación de resistencia que puede cambiar el resultado de casos próximos al límite. Se debe usar el mismo dv en todas las partes de la formulación.

### H23. Condición equivocada para β simplificado y límites omitidos de sxe

**Gravedad: alta. Confirmado.**

Ubicación: `abutment.py:2919`, `_footing_simplified_shear_eligible`; `:2928`, `_general_shear_beta`.

Para aceptar β = 2 en zapatas se compara el **espesor de la pantalla** con 3dv. MTC 2.9.1.5.6.3.4.1, página 387, se refiere a la **distancia entre el punto de cortante nulo y la cara de columna/pilar/tabique**, no al espesor de éste. Una pantalla delgada no convierte automáticamente una zapata larga en elegible para el procedimiento simplificado.

En el procedimiento general tampoco se imponen los límites 12 in ≤ sxe ≤ 80 in expresados en MTC 2.9.1.5.6.3.4.2, página 388. Un sxe calculado demasiado pequeño puede aumentar artificialmente β.

Se requiere determinar la elegibilidad con el diagrama real de cortante, aplicar todos los límites del procedimiento elegido y no mezclar partes de modelos simplificado/general sin sus condiciones.

### H24. Incoherencia entre el empuje estático y el sísmico para pared inclinada

**Gravedad: alta para geometrías fuera del caso vertical predeterminado. Confirmado.**

Ubicación: `abutment.py:1006`, `coulomb_active_coefficient`; `:1044`, `mononobe_okabe_active_coefficient`; aplicación en `:1274`.

El cálculo estático permite variar el ángulo del trasdós, pero Mononobe–Okabe se formula para una pared vertical sin usar de manera equivalente ese dato. Se pierde incluso la coincidencia estático/sísmico cuando la aceleración tiende a cero.

Ejemplo con φ del suelo = 30°, fricción de pared y pendiente nulas, PGA = 0: para pared vertical ambos coeficientes son 0.333333. Al cambiar el ángulo de pared a 75°, Ka estático es 0.449490 y Kae permanece 0.333333. El incremento sísmico puede resultar negativo sin sismo por una inconsistencia geométrica.

Asimismo, al activar fricción suelo–pared debe descomponerse coherentemente la resultante en horizontal y vertical; el tratamiento actual no desarrolla toda esa descomposición. Debe unificarse la convención angular y la geometría de los dos modelos o restringirse la entrada al caso realmente implementado.

### H25. Coeficientes invertidos en el momento del dentellón

**Gravedad: alta. Confirmado por integración.**

Ubicación: `abutment.py:2712`, `_key_base_moment_tn_m`.

Para presión lineal de p superior a p inferior y empotramiento en la unión superior con la zapata, el momento es:

`M = H² * (p_superior + 2 p_inferior) / 6`.

El código usa `H² * (2 p_superior + p_inferior) / 6`. Otorga el brazo mayor a la presión próxima al empotramiento.

En el ejemplo con datos predeterminados de geometría y suelo y dentellón activado, la función arroja 0.7546 Tn·m/m frente a 0.8162 Tn·m/m por integración. Con presión triangular que parte de cero arriba, el valor del código sería la mitad del correcto.

Debe corregirse la integración respecto al empotramiento real y conservar consistencia con las presiones utilizadas para resistencia pasiva y diseño estructural.

### H26. Centroide incorrecto del ensanche triangular en muro puro

**Gravedad: media. Confirmado; conservador para el momento estabilizador hacia la puntera del ejemplo.**

Ubicación: `abutment.py:1076`, rama `is_pure_wall` de `_concrete_components`.

Se usa `x = puntera + Δespesor/3`, pero para el triángulo de ensanche representado junto a la pantalla rectangular corresponde `x = puntera + 2Δespesor/3`. La rama de estribo sí usa esta segunda posición para el ensanche inferior.

Con puntera = 1.10 m y Δespesor = 0.60 m: código x = 1.30 m; centroide correcto x = 1.50 m. Para el componente de 4.248 Tn/m se reduce el momento estabilizador en 0.8496 Tn·m/m.

Debe corregirse el centroide y recalcular equilibrio y presiones. Que el efecto sea conservador para una comprobación no hace geométricamente válida la formulación ni garantiza el mismo signo en todas las salidas.

### H27. El corte de barras de pantalla usa una geometría distinta de la del estribo

**Gravedad: alta para el estribo con cambios de sección. Confirmado.**

Ubicación: `abutment.py:2188`, `:2336` y `:2372`, `_stem_thickness_at_height_m`; geometría de componentes en `:1111`.

Para cortar armadura se interpola linealmente el espesor inferior–superior a lo largo de toda la altura. Sin embargo, el estribo se descompone en ensanche inferior, pantalla superior, transiciones y cajuela: no es ese trapecio continuo.

Con datos predeterminados, el ensanche inferior termina a 3.40 m sobre la zapata. Allí la pantalla de ese modelo alcanza 0.30 m, mientras la función de detallado devuelve aproximadamente 0.554 m. Puede sobreestimar d y aceptar una reducción prematura de acero.

Debe obtenerse la sección local del mismo modelo geométrico usado en el resto del cálculo y verificar la armadura remanente con anclaje efectivo. La interpolación sí puede representar un muro realmente trapezoidal, pero no este estribo escalonado.

### H28. El movimiento térmico predeterminado omite la expansión que puede gobernar

**Gravedad: alta. Confirmado.**

Ubicación: `pep_bearing.py:97` y `:191`; `simple_neoprene_support.py:100`; `elastomeric_bearing.py`, `BearingMovements`.

La ruta automática toma instalación menos temperatura mínima. No compara con temperatura máxima menos instalación. En el módulo de apoyo laminado existe una alternativa de rango completo, pero la ruta predeterminada conserva el problema.

Ejemplo con valores de selva del propio programa: Tmin = 10 °C, Tmax = 50 °C, instalación = 20 °C. Se usa ΔT = 10 °C, aunque hacia expansión hay 30 °C. Para L = 15 m, α = 10.8×10⁻⁶/°C y γTU = 1.20: desplazamiento considerado 0.1944 cm; expansión 0.5832 cm, tres veces mayor.

Debe obtenerse la envolvente de ambos sentidos con los movimientos permanentes y las condiciones de instalación reales. PEP permite desplazamientos explícitos: introducir una envolvente correcta puede evitar la ruta defectuosa, pero no valida el valor automático.

### H29. Se comparan acciones de servicio con capacidades de resistencia

**Gravedad: alta. Confirmado en las rutas nominales.**

Ubicación: `simple_neoprene_support.py:226`, comprobación de concreto; `elastomeric_bearing.py`, comprobación de apoyo sobre concreto; `pep_bearing.py`, creación de `ComponentDemands` y aplastamiento del concreto aproximadamente en línea 964.

Las propiedades de demanda suman DC + DW + LL (+ IM/PL según módulo) como servicio. Esa suma se utiliza en comprobaciones contra φPn o para componentes de acero rotulados como resistencia. No se genera sistemáticamente la combinación factorizada vertical correspondiente.

El Método A del elastómero utiliza verificaciones de servicio, pero eso no autoriza a utilizar automáticamente la misma reacción para acero, concreto y anclajes en resistencia. El código del apoyo simple sí factoriza el frenado en una ruta; ello no subsana la reacción vertical.

Debe conservarse una familia de casos de servicio y otra de resistencia/evento extremo, con componentes simultáneas. Introducir manualmente cargas ya factorizadas en campos denominados de servicio trasladaría el problema a las verificaciones del elastómero; no es una solución general.

### H30. Una fuerza elástica de servicio se trata como capacidad horizontal

**Gravedad: alta. Confirmado como interpretación mecánica no justificada.**

Ubicación: `elastomeric_bearing.py`, cálculo de capacidad horizontal/anclaje; `pep_bearing.py:407`, variables `horiz_cap` y `h_anchor`.

`Hpad = G A Δservicio / h` es la reacción elástica para un desplazamiento de servicio adoptado. No es, por sí sola, la resistencia horizontal última ni el límite de desplazamiento sísmico. El programa combina ese valor con la fricción mediante un máximo para decidir cuánto anclaje exigir ante sismo.

En ese modelo, aumentar el desplazamiento térmico puede aumentar la supuesta «capacidad» y reducir el anclaje sísmico requerido, sin comprobar una mayor capacidad real del aparato. Esto no define una trayectoria de cargas consistente.

Debe distinguirse reacción elástica, capacidad de fricción, desplazamiento admisible, resistencia del dispositivo y acciones de los elementos de restricción. El reparto sísmico debe derivarse de rigideces y restricciones reales, con comprobaciones de fuerza y desplazamiento.

### H31. El autodiseño de anclajes cambia las placas después de verificarlas

**Gravedad: alta, condicionada a que el algoritmo cambie la geometría. Confirmado por flujo de ejecución.**

Ubicación: `pep_bearing.py`, bloque de placas/anclajes aproximadamente en líneas 870–930; `pep_steel_components.py:635`, `auto_design_anchors`.

Se verifican las placas iniciales y después el autodiseño de anclajes puede aumentar sus dimensiones y modificar su espesor. Los resultados anteriores se conservan. La búsqueda de anclajes verifica pernos y concreto, pero no llama a `verify_plate` para la placa modificada.

Por tanto, la geometría finalmente devuelta puede no ser la que corresponde a las comprobaciones de placa mostradas. Aumentar dimensiones en planta no garantiza que una placa mantenga suficiente resistencia a flexión.

Después de cualquier cambio geométrico deben invalidarse y repetirse las verificaciones dependientes hasta que el conjunto completo corresponda a una misma configuración final.

### H32. Curvas de compresión del PEP con respuesta no física y aviso de extrapolación incompleto

**Gravedad: alta para decisiones de deformación; trazabilidad insuficiente. Confirmado.**

Ubicación: `pep_strain_curves.py:15`, tabla de puntos; `:65`, consulta; `:104`, interpolación por esfuerzo.

Para esfuerzos por debajo del primer punto se devuelve la deformación de ese primer punto. Así, Shore 60, S = 5 y σ = 0 producen ε = 0.025, con `extrapolated=False`. Una curva de deformación por carga, sin deformación inicial modelada, debe pasar por el origen.

La mezcla de columnas con rangos distintos genera además irregularidades. Para Shore 60 y σ = 40 kgf/cm²: ε(S=8) = 0.028; ε(S=11.25) = 0.029; ε(S=12) = 0.018. El punto intermedio no sigue la tendencia esperada al aumentar el confinamiento geométrico, y a σ = 40 queda por debajo del primer esfuerzo tabulado de su columna.

Los comentarios remiten a valores típicos de ejemplos, mientras la salida afirma «puntos digitalizados verificables». Se requiere una fuente trazable de curvas/datos del fabricante, validación del origen y monotonicidad, y control del rango local de cada columna. Puede distorsionarse tanto la deformación permanente como la diferencia atribuida a carga viva.

### H33. El apoyo laminado considera «ANCLAR» equivalente a cumplimiento completo

**Gravedad: alta. Confirmado en el estado global.**

Ubicación: `elastomeric_bearing.py:260`, `DesignCheck.ok`; `ElastomericBearingDesignResult.overall_ok`.

La propiedad `ok` devuelve verdadero tanto para «OK» como para «ANCLAR». El resultado global puede ser conforme aunque el módulo únicamente haya calculado una fuerza que necesita anclaje y no haya diseñado/verificado ese anclaje.

Es aceptable informar que el pad cumple y que requiere restricción externa. No es equivalente a afirmar que el aparato completo está resuelto. Debe distinguirse «cumple el elastómero» de «conjunto completo verificado» y mantener como pendiente el diseño externo.

### H34. El resumen para estribos suma máximos de vigas que no necesariamente son simultáneos

**Gravedad: alta si se utiliza como demanda física global; condición conservadora no universal. Confirmado.**

Ubicación: `src/bridge_design/cli/ascii_output.py:1976`, `_abutment_live_reaction_row`; `interior_girder.py:1257`, almacenamiento de reacciones de cargas móviles.

El resumen suma el máximo cortante de cada tipo de viga multiplicado por su cantidad. Los máximos de viga interior y exterior proceden de posiciones/distribuciones transversales distintas y no se demuestra que puedan coexistir en un mismo estado de tráfico. El resultado no es necesariamente la reacción global de una configuración real.

Puede constituir una cota conservadora para ciertas acciones verticales desfavorables, pero no debe utilizarse sin distinción para efectos estabilizadores o para interacciones que dependen de componentes simultáneas. Se necesitan reacciones globales por caso, equilibrio con la carga total y envolventes adecuadas al efecto buscado.

Asimismo, las reacciones guardadas junto al momento máximo longitudinal corresponden a esa posición del vehículo, no necesariamente al máximo de reacción de apoyo. Deben diferenciarse claramente ambos conceptos al transferir resultados a apoyos y estribos.

## 5. Observaciones de ingeniería que requieren justificación

### O01. Modelo de reparto de cargas al diafragma

Ubicación: `diaphragm.py:945`, `_vehicle_loads_at_position`, y propiedades de `DiaphragmBeamGeometry`.

La suma de cargas de ejes del vehículo se transforma en dos cargas transversales mediante una proporción entre longitud tributaria y ancho equivalente. La longitud tributaria predeterminada está ligada al espesor del diafragma. No se resuelve la posición longitudinal de cada eje respecto al diafragma con una línea/superficie de influencia ni la deformabilidad conjunta de vigas y tablero.

La hipótesis podría utilizarse como modelo particular respaldado por un análisis independiente; no se encontró una demostración de su aplicabilidad general. También debe distinguirse diafragma de apoyo de diafragma intermedio. **No se acredita el diseño general del diafragma únicamente con esta formulación.** Se recomienda contrastarlo con un modelo de emparrillado, placa/viga u otra idealización justificada para la geometría real, además de corregir los errores heredados de armadura.

### O02. Reducción sísmica kh = 0.5 As condicionada a desplazamiento admisible

Ubicación: `abutment.py:1044`, `:1274`, `:2437` y funciones relacionadas.

El factor 0.5 se aplica de forma fija. MTC 2.8.1.1.14, páginas 249–251, vincula la reducción sísmica de ciertos muros a su posibilidad de desplazamiento y a la aceptación de esas deformaciones. No es una reducción universal para cualquier estribo restringido por superestructura, cimentación o elementos vecinos.

Se debe documentar la movilidad admisible y habilitar el caso sin reducción cuando corresponda. Esta observación es condicional: **no se afirma que kh = 0.5 As sea siempre incorrecto**.

### O03. Hipótesis geotécnicas e hidráulicas insuficientes para aprobación integral

Ubicación: `AbutmentSoilInputs`, `_allowable_factored_bearing` en `abutment.py:1609` y generadores de empujes.

La reconstrucción de una resistencia nominal mediante FS × q admisible requiere que esa q provenga de la misma resistencia y no de un límite de asentamiento. Se debe conservar la procedencia geotécnica, método y factor de resistencia aplicable.

No se desarrolla una envolvente general con nivel freático, presión hidrostática, subpresión, pesos sumergidos y pérdida de resistencia pasiva por excavación/socavación. El MTC 2.4.2.2, página 90, requiere considerar condiciones de saturación del relleno. Un escenario seco puede ser admisible si se justifica, pero no acredita todos los escenarios de un puente.

Tampoco debe confundirse estabilidad externa del muro con estabilidad global del terreno. Los parámetros de resistencia pasiva y su altura efectiva deben corresponder al terreno que realmente permanecerá frente a la estructura.

### O04. Desarrollo, cortes de barras y anclajes no equivalen a un detalle constructivo completo

Ubicación: `girder_detailing.py:256`, `:548`; `abutment.py:2082`, `:2729`, `:2761`; desarrollo en barrera/voladizo; apoyo simple fijo.

Se reconocen fórmulas de desarrollo y prolongaciones, pero el conjunto necesita comprobar, entre otros, longitud disponible desde la sección crítica correcta, soporte real, gancho/doblado, confinamiento, condición de barra superior, transferencia de tracción longitudinal asociada a cortante y armadura remanente efectivamente desarrollada. En vigas la longitud puede quedar limitada por los extremos del modelo de luz sin un modelo completo de penetración en el apoyo.

En zapatas, usar la longitud nominal de talón como disponibilidad de anclaje no demuestra que exista esa distancia del lado necesario respecto a la sección crítica. En la barrera, factores de reducción de anclaje necesitan sus condiciones geométricas reales. El apoyo simple fijo verifica pasadores, pero no sustituye el diseño del concreto y del empotramiento del conjunto.

Debe revisarse el detalle físico; no basta con que una longitud numérica o un área de acero figure como suficiente.

### O05. Alcance global del puente y de las barreras

El programa aborda familias de comprobaciones, pero no acredita por sí solo todas las acciones y etapas de un puente: torsión y distribución espacial, restricciones de apoyo, secuencia constructiva, estabilidad durante montaje, acciones térmicas restringidas, viento, aspectos sísmicos globales, socavación y estados geotécnicos específicos deben justificarse según el proyecto.

En barreras, la resistencia calculada por líneas de fluencia no certifica por sí sola un nivel de contención TL. Deben corresponder sección, altura, armadura, juntas, extremos, anclaje, acciones aplicables y evidencia de desempeño de la configuración adoptada. No todas estas verificaciones tienen que pertenecer al mismo software, pero deben quedar explícitamente fuera de su aprobación automática cuando no se realizan.

### O06. Trazabilidad, validación numérica y estados informativos

Algunas referencias son genéricas o remiten a AASHTO sin fijar inequívocamente la edición; deben depurarse contra el MTC 2018. Una matriz de referencias documentales no ejecuta comprobaciones. No se identificó como error la adopción de Fatiga I = 1.50: coincide con la tabla MTC 2.4.5.3.1-1, página 133.

Las filas que presentan demanda igual a límite y estado «OK» para registrar fuerzas o rotaciones deberían identificarse como **resultado informativo**, no como prueba resistente. Tampoco se debe señalar automáticamente como error que el Método A no implemente todas las ecuaciones del Método B: hay que revisar las condiciones del método elegido.

Los validadores necesitan rechazar valores no finitos y combinaciones geométricas imposibles. El muestreo de cargas móviles necesita un control de convergencia: un paso fijo no demuestra que se haya encontrado el máximo exacto. Se recomienda distinguir estados «cumple», «no cumple», «fuera de alcance», «pendiente» e «informativo», sin permitir que los últimos tres den aprobación global.

## 6. Comprobaciones que no se identificaron como errores específicos

Es importante no confundir un programa con errores con un programa en el que todo esté mal. En la revisión se reconocieron bases coherentes, sujetas a los límites anteriores:

- Conversiones principales entre Tn-f, kgf, cm, m y unidades inglesas, así como la formulación de Ec y sus límites de entrada.
- Equilibrio elemental de cargas puntuales/uniformes de viga simplemente apoyada y construcción de momentos longitudinales.
- Distinción camión/tándem, variación de separación de ejes del camión y tratamiento básico de IM.
- Factores básicos de Resistencia I: DC máximo 1.25, DW máximo 1.50 y LL 1.75; Servicio I con factores unitarios para esas acciones; Fatiga I con 1.50 e IM de fatiga del 15 %.
- Estructura de las expresiones usuales de distribución de vigas T, con la salvedad de carriles, geometría y condiciones de aplicabilidad.
- Forma básica de φMn para una sección que realmente esté dentro de las hipótesis de acero a fy y dominio de deformaciones admisible.
- Factor de forma rectangular del elastómero y fuerza elástica GAΔ/h, **cuando esta última se interpreta como reacción para un desplazamiento y no como capacidad última**.
- Conservación de casos completos en las utilidades de demandas PEP, aunque las rutas de transferencia y estados límite requieren correcciones.

Estas observaciones no certifican cada función para todas sus entradas ni neutralizan los hallazgos del informe.

## 7. Reproducción mínima de ejemplos

Los siguientes fragmentos son instrucciones de diagnóstico, no modificaciones propuestas. Se ejecutan desde la raíz del proyecto, con `src` en el camino de importación. Las pruebas realizadas durante la revisión se ejecutaron en memoria con `python -B`; no se añadieron a los tests del proyecto.

### 7.1 Pantalla predeterminada

```python
import sys
sys.path.insert(0, "src")
import bridge_design.domain.abutment as a

r = a.solve_abutment_design()
print(a._stem_design_demands(r.inputs, r.pressures))
print(r.stem_design)
# Resistencia I: Mu = 71.4880833333 Tn·m/m.
# Capacidad indicada con phi = 1: 77.6508590118 Tn·m/m.
# Con phi = 0.90: 69.8857731106 < 71.4880833333.
```

### 7.2 Fricción insuficiente con aprobación del apoyo móvil

```python
import bridge_design.domain.simple_neoprene_support as s

r = s.design_simple_neoprene_support(s.SimpleSupportInputs(
    support_type="MOVIL_PLACAS",
    geometry=s.SimpleNeopreneGeometry(60, 40, 5),
    demands=s.SimpleSupportDemands(20, 0, 0, 0, span_length_m=30),
    plates=s.ExternalSteelPlatePair(),
))
print(r.h_pad_tn, r.friction_capacity_tn, r.overall_ok)
# 5.24786688, 4.0, True
```

### 7.3 Demanda sísmica del PEP fijo

```python
import bridge_design.domain.pep_bearing as p

d = p.PepServiceDemands("EE", "eq", "p", "a", 100, 0, 0)
r = p.design_pep_bearing(p.PepBearingInputs(
    "FIJO", p.PepGeometry(60, 40, 5), d,
))
print(r.h_eq_gov_tn, r.h_anchor_report_tn)
print([(c.name, c.demand) for c in r.checks if "fija" in c.name])
# H sísmica y H de anclaje: 20 Tn.
# Demandas de las dos restricciones fijas: 0 Tn.
# Este ejemplo ilustra la pérdida de demanda; no afirma aprobación
# global del aparato sin ingresar sus placas y anclajes.
```

### 7.4 Separación imposible y deformación a esfuerzo cero

```python
from bridge_design.domain.rebar_catalog import generate_spacing_options, SpacingGrid
from bridge_design.domain.pep_strain_curves import compressive_strain_from_curve

op = generate_spacing_options(
    "alta demanda", 200,
    SpacingGrid(step_m=0.025, minimum_m=0.10, maximum_m=0.30),
)
print(op.recommended)
# Barra de 1 pulgada, separación 0.025 m, conforme y recomendada.
print(compressive_strain_from_curve(60, 5, 0))
# epsilon = 0.025; extrapolated = False.
```

## 8. Orden recomendado de corrección y criterios de cierre

No se ejecutó ninguna de estas correcciones.

| Prioridad | Trabajo recomendado | Evidencia exigible para darlo por cerrado |
|---|---|---|
| 1 | H01–H07: factores resistentes, límite de cortante, falsa aprobación de fricción, demanda sísmica y anclajes, excentricidad | Cada ejemplo del informe debe producir el rechazo o requerimiento correcto; equilibrio y estado límite trazables |
| 2 | H08–H13: sección real, deformaciones, mínimos, armadura superficial, espaciamiento y fisuración | Recalcular la resistencia y servicio de la disposición física adoptada; no aceptar opciones imposibles |
| 3 | H14–H18 y H34: carriles, patrones, envolventes, franja y transferencia de colisión/reacciones | Líneas de influencia o modelo independiente; suma de reacciones igual a cargas simultáneas; límites de aplicabilidad explícitos |
| 4 | H19–H27: geometría de barrera/estribo, talón/puntera, cortante y dentellón | Diagramas de cuerpo libre con un único caso; integración de presiones; secciones geométricas coherentes a cada altura |
| 5 | H28–H33: movimientos y aparato de apoyo completo | Envolventes térmicas de ambos signos; casos LRFD separados; mismo detalle final en todas las verificaciones; curvas trazables |
| 6 | O01–O06: hipótesis, verificaciones externas y documentación | Memoria que justifique simplificaciones y declare qué comprueba el programa y qué queda a cargo del diseñador |

Después de las correcciones se recomienda contrastar al menos un caso manual trazable por módulo, casos próximos al límite y casos deliberadamente no admisibles. La verificación debe empezar por la formulación, como se solicitó, y luego respaldarse con pruebas de regresión; un test que reproduce la misma fórmula equivocada no constituye validación independiente.

## 9. Conclusión final y estado del trabajo

El código contiene una base aprovechable de cálculo, pero **no está libre de errores ni se puede considerar integralmente alineado con el MTC 2018 en su estado actual**. Se han demostrado errores en factores de resistencia, criterios de aprobación, equilibrio de anclajes, excentricidad sísmica, armaduras, integración de presiones y transferencia de cargas. Otros módulos requieren acotar o justificar sus modelos.

La revisión fue de diagnóstico: **no se modificaron archivos de código fuente ni tests**. Se creó este informe y se generaron archivos auxiliares de lectura del manual en `tmp_pdf_text/`. No se efectuaron cambios de diseño ni se reemplazaron resultados existentes del proyecto.

El informe permite priorizar correcciones y verificar su cierre. No constituye una memoria de cálculo corregida ni una aprobación profesional de un puente particular; para ello hacen falta el recálculo posterior y la revisión del responsable del diseño con los datos reales de la obra.
