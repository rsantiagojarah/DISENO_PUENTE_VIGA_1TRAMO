# Implementación de la auditoría desde H18

Fecha: 8 de septiembre de 2026.

Revisión del código que permanece en el repositorio. El informe original se
conserva como diagnóstico histórico; este documento registra las modificaciones
y sus límites. Las correcciones cambian resultados y detalles respecto de la
hoja de referencia anterior.

| Hallazgo | Tratamiento en el código actual |
|---|---|
| H18 | **Cerrado para el alcance de la barrera de concreto implementada.** Se usa max(Ft,Rw), N=F/(Lc+2H), Mc y As(M)+N/(phi·fy). Se evalúan los casos 1 horizontal en A, distribución en B y C, caso 2 vertical no gobernante para parapeto de concreto y caso 3 DC+LL. La conexión verifica yield-line, fricción, dowels y desarrollo; el estado global exige todos esos controles. |
| H19 | El perfil resistente implementado se limita expresamente al New Jersey de H=0.85 m, base=0.375 m y A=0.202875 m². Se rechazan geometrías y segmentos incompatibles. En ProjectInputs, el peso se deriva de A·gamma; se unifica el ancho de barrera y se ajusta la zona de asfalto y la distancia de la viga exterior a su cara. El recorrido vehicular explícito se conserva. |
| H20 | Cada estado conserva sus factores y componentes verticales. El talón utiliza esos mismos factores en sus cargas descendentes y reacción; incluye el concreto que proyecta sobre el talón y las cargas del tablero que caigan en él. Se conserva el signo de M y V. |
| H21 | La zapata recorre Resistencia Ia/Ib, ambas alternativas sísmicas y estados con/sin puente. Se guardan extremos con signo y se dimensiona conservadoramente el máximo absoluto **en ambas caras** de cada voladizo de zapata. Se descuentan las cargas descendentes de puntera y se integra el contacto parcial por tramos. Servicio también considera con/sin puente. |
| H22 | Vc usa el mismo dv almacenado en el resultado de beta; se actualiza la sustitución en la memoria. |
| H23 | Se elimina la elegibilidad basada en espesor de pantalla. Zapata/dentellón utilizan el procedimiento general mientras no se determine la ubicación real de cortante nulo. Se limita sxe a 12–80 in. |
| H24 | Se restringe el motor a trasdós vertical y delta=0. Se rechazan otras geometrías en API/YAML y se controla la entrada interactiva. |
| H25 | Momento del dentellón: H²·(p_sup+2p_inf)/6. |
| H26 | Centroide del ensanche triangular de muro: puntera+2·delta_espesor/3. |
| H27 | Espesor local por tramos de la geometría del estribo; el muro conserva su trapecio. La reducción de barras comprueba los intervalos restantes y los cambios de sección, además del punto de corte. |
| H28 | Envolvente térmica en ambos sentidos. En el laminado, los acortamientos se suman a la contracción y se restan de la expansión; se conserva el modo explícito de rango completo. Consola y memorias muestran el nuevo criterio. |
| H29 | Se separa la reacción de servicio del neopreno de 1.25DC+1.50DW+1.75(LL+IM+PL), según las acciones disponibles, para concreto y compresión de placas del apoyo simple. |
| H30 | GA·Delta/h queda como reacción de servicio. No se deduce del sismo; la restricción externa recibe la fuerza sísmica completa y se conserva la exigencia por fricción insuficiente en servicio. No se diseña el anclaje externo en el módulo laminado. |
| H31 | No aplicable: pep_bearing.py y pep_steel_components.py ya no existen. No se reintroducen. |
| H32 | Curvas heredadas con origen cero, control del rango local, rechazo de no finitos y eliminación de columnas incompatibles. Se identifican como ilustrativas, con verified_source=False y estado PENDIENTE DATOS DE FABRICANTE; no se inventa una fuente certificada. |
| H33 | ANCLAR ya no equivale a OK. Se distingue elastomer_ok de overall_ok. |
| H34 | Nuevo motor de reacciones globales HL-93 por casos físicos, con presencia múltiple, IM en ejes, carga de carril y tráfico nulo. Cada caso conserva ambas reacciones y equilibra fuerzas y momentos. Los máximos de cada apoyo pertenecen a casos distintos. Consola, PDF y Word consumen estos casos; las reacciones por viga en la posición de Mmax se identifican aparte. |

## Criterios y alcance

Para H18 se siguió el criterio de acero adicional por tracción descrito en el
[ejemplo oficial FHWA, diseño del voladizo](https://www.fhwa.dot.gov/bridge/lrfd/pscus04.cfm).
Se adopta conservadoramente el mayor momento disponible y se añade el acero
axial. El alcance cerrado corresponde al perfil New Jersey validado; una barrera
distinta se rechaza hasta reconstruir su geometría y conexión. Para cerrar la trazabilidad de H32 se
necesitan curvas de fabricante o una digitalización documentada.

H28–H30 se corrigieron en las familias de apoyos existentes. Las menciones a PEP
en esos hallazgos, y H31, no justifican reconstruir los módulos eliminados.
Las observaciones O01–O06 del informe son límites de ingeniería y de alcance;
esta implementación no constituye un modelo integral del puente, un estudio
geotécnico/hidráulico ni una certificación del nivel TL de la barrera.

Los nuevos módulos y pruebas se mantienen por debajo de 350 líneas. Los módulos
históricos que ya excedían ese tamaño no se han reorganizado integralmente.

## Verificación

Resultado: **261 pruebas aprobadas** en la suite completa y **37 pruebas
aprobadas** en la comprobación específica posterior. Sin errores de espacios
en `git diff --check` para el código, las pruebas y el informe modificados.

Se añadieron 22 pruebas de regresión, incluyendo equilibrio de fuerza y momento
de las reacciones globales, integración del dentellón, equilibrio del talón por
caso, geometría local, dv, sxe, expansión térmica, combinación de resistencia,
colisión con tracción y estados pendientes. Se actualizaron las expectativas
que reproducían los cálculos observados en la auditoría.

Comando de suite completa:

```text
python -m pytest -q --basetemp=output/pytest_h18_final -p no:cacheprovider
```

Las pruebas incluyen generación de memorias Word/PDF y comandos YAML. Esto
verifica la integración del software; no certifica el diseño de una obra.
