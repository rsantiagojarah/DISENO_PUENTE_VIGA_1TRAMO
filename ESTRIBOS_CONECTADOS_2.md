# Diseño de estribos conectados 2

`diseno-estribos-conectados-2` incorpora la forma de `ver_2l.pdf` como una
modalidad independiente. `diseno-estribos-conectados`, su plantilla y su carpeta
de resultados mantienen su funcionamiento.

## Uso

Ingreso interactivo, con Enter para conservar cada valor mostrado:

```powershell
diseno-estribos-conectados-2
```

Crear una plantilla editable, completar el módulo de balasto y ejecutar:

```powershell
diseno-estribos-conectados-2 output modelo_estribos_conectados_2.yaml
diseno-estribos-conectados-2 input modelo_estribos_conectados_2.yaml
```

Para ejecutar sin preguntas, conservar el acero propuesto y guardar la memoria:

```powershell
diseno-estribos-conectados-2 input modelo_estribos_conectados_2.yaml --automatico --verificar-malla
```

También se admiten `--sin-word` y `--resultados RUTA`. `output --ejemplo` crea
una plantilla con balasto **referencial** de 3000 tn/m³ para pruebas; la plantilla
normal lo deja vacío para que se introduzca el dato del proyecto. La ejecución
sin instalar el acceso de consola es `python -m bridge_design.connected_2_main`.
Al instalar o actualizar el proyecto se registra el nuevo comando con
`python -m pip install -e . --no-deps`.

## Geometría editable

Se ingresa una sola geometría, aplicada a ambos estribos. La cara exterior del
estribo es vertical y la interior varía linealmente desde la base hasta el
asiento. El parapeto queda alineado con el trasdós. La base es monolítica y tiene
espesor uniforme. El relleno exterior llega a la coronación del parapeto; sobre
el tramo interior de la zapata combinada no hay relleno. No se solicitan punteras, bloques de cajuela,
transiciones, alturas de relleno ni ángulos de trasdós que esta forma no necesita.

| Dimensión independiente | Valor inicial (m) |
| --- | ---: |
| Luz libre superior, entre caras interiores al nivel del asiento | 14,00 |
| Altura de pantalla desde la base hasta el asiento | 8,03 |
| Altura del parapeto sobre el asiento | 1,17 |
| Espesor del parapeto | 0,25 |
| Longitud horizontal del asiento | 0,55 |
| Espesor inferior de pantalla | 1,35 |
| Talón exterior de cada lado | 0,90 |
| Espesor uniforme de cimentación | 1,50 |

Se solicita además la altura adicional para frenado sobre la coronación:
1,80 m referenciales heredados del modelo actual, editables y no obtenidos del
PDF. Se conserva la convención y el brazo de aplicación del módulo compartido.

Las dimensiones dependientes se recalculan después de cada edición:

- Espesor superior = asiento + espesor de parapeto: **0,80 m**.
- Luz inferior = luz superior − 2 × (espesor inferior − superior): **12,90 m**.
- Ancho total = luz inferior + 2 × (espesor inferior + talón): **17,40 m**.
- Altura total desde fondo de base = espesor de base + altura de pantalla +
  altura de parapeto: **10,70 m**.

Las cotas dependientes se modifican mediante sus dimensiones de origen; no se
ingresan por duplicado. Se rechazan dimensiones incompatibles. El asiento y el
parapeto deben caber en el espesor inferior, y la luz inferior debe ser positiva.

## Cálculo y resultados compartidos

Se reutilizan el modelo FRAME 2D de franja de 1 m, resortes Winkler solo a
compresión, cargas, empujes, combinaciones, verificaciones de concreto, opciones
y selección de acero, servicio, anclajes, auditoría y exportadores existentes.
Se conserva la base normativa del módulo original:
[Manual de Puentes MTC 2018](https://www.gob.pe/institucion/mtc/normas-legales/4441255-19-2018-mtc-14).
La nueva modalidad adapta la geometría; no introduce fórmulas de diseño paralelas.

Las reacciones iniciales por metro de estribo se conservan: PDC=8,959;
PDW=0,545; PPL=0,762; PLL+IM=6,92 y BR=1,33 tn/m. Se pueden editar y, como en
el comando original, introducir reacciones distintas del lado derecho para un
mismo caso simultáneo. Materiales, geometría y criterios de armado son comunes.

Con la configuración inicial se generan 17 combinaciones y 12 distribuciones
de acero: cuatro de pantalla, cuatro de parapeto y cuatro de **Zapata combinada**
(longitudinal superior e inferior y transversal superior e inferior). Toda la
cimentación se diseña como una zapata continua, incluidos los talones y los tramos
bajo las pantallas. Cada cara conserva la envolvente de todas sus secciones y
combinaciones. No se presenta una selección independiente de losa central.
Los controles y límites
de aplicación siguen siendo los del comando original, incluido su diseño por
flexión y cortante sin comprobación de interacción axial-momento.

Las longitudes de desarrollo se calculan con las funciones compartidas. En la
zapata combinada se reutiliza la comprobación del espacio recto disponible en las
secciones gobernantes de resistencia, suponiendo barras continuas. Para acreditar
otra longitud útil de continuidad dentro de la zapata, se utiliza el bloque YAML
existente `longitudes_rectas_anclaje_disponibles_m` con el nombre de distribución.

La salida predeterminada es `output/estribos_conectados_2/`: resumen, auditoría,
JSON, CSV, gráficos de la forma real, cargas y envolventes. La memoria automática
se llama `memoria_estribos_conectados_2.docx`; en modo interactivo se elige su
destino con la ventana habitual. Los controles que no cumplen se conservan
visibles en el informe; ejecutar el ejemplo no convierte sus valores en un
diseño aprobado.

## Cortes del acero longitudinal de la zapata

El esquema de `aceros.pdf` se interpreta como refuerzo adicional **superior
central** y refuerzos adicionales **inferiores en ambos extremos**. Las cotas
del dibujo son referencias de disposición; se calculan con las dimensiones,
las cargas y el acero elegido. Se mantiene el cálculo existente de corte de
pantalla. Los comandos anteriores conservan su comportamiento.

Cada selección de barra y separación recalcula las dos propuestas. El programa
conserva las posiciones de la parrilla y evalúa cortar una barra de cada N,
manteniendo las demás continuas. Los ciclos prácticos caben en la franja
transversal de un metro. Se comprueban el mínimo de acero y el hueco real de
2s entre barras continuas, también para fisuración; la separación equivalente
se utiliza únicamente para representar su área de acero. No se terminan barras
adyacentes ni más del 50 % en una misma sección.

Los puntos teóricos cubren todos los elementos donde el acero remanente no
cumple flexión, cortante o servicio, incluyendo picos alejados del muro. La
disposición final es simétrica y toma el caso más desfavorable de ambos lados.
La prolongación adoptada es `max(ld existente, d, 15db, L libre/20)`, redondeando
los extremos hacia una mayor longitud de barra al centímetro. Se verifica la
prolongación de las barras continuas y toda la envolvente del tramo reducido.
Se reutilizan las verificaciones de sección, temperatura, desarrollo y la
prolongación mínima que ya utilizaba el diseño del voladizo.

Referencia: Manual de Puentes MTC 2018, Art. 2.6.5.6.1.2.1 (páginas 201–202),
AASHTO LRFD 5.11.1.2.1. El uso de ld como prolongación adicional del refuerzo
cortado es una decisión conservadora compartida con el criterio de pantalla.

Si el armado completo falla, la separación o el mínimo impiden retirar barras,
o las prolongaciones eliminan el tramo donde se ahorraría acero, se muestra
**NO APLICA** con el motivo y se conserva el acero continuo. Una propuesta
**APLICA** informa patrón, acero remanente, cortes teóricos y definitivos,
distancias desde las caras interiores, longitudes horizontales e índices de
comprobación. Los ganchos, doblados y empalmes no se suman ficticiamente a esas
longitudes horizontales; mantienen su verificación de detalle independiente.

El detalle de un corte adoptado se incluye en el resumen final, la auditoría,
JSON, Word, `cortes_zapata.csv` y `cortes_zapata.png`. El gráfico sólo dibuja
cortes que resultaron aplicables. La propuesta se recalcula al cambiar el acero
y no modifica las solicitaciones del modelo estructural.

## Selección de cortes

En la pantalla del relleno y en las dos caras longitudinales de la zapata, la
tabla de acero continuo sigue eligiéndose por número de ítem. Debajo aparece
una tabla corta **CORTES**. Cada fila es un corte de 1 de cada 2, con la misma
barra: `s mayor` donde hay más acero y `s menor = 2s` donde hay menos. Solo
entran filas que ya cumplen flexión, cortante, fisuración y mínimos en cada
tramo. Se escribe `C1`, `C2`, etc.

En la zapata superior hay más acero en el centro y menos en los extremos. En la
inferior hay más acero en los extremos y menos en el centro. La cota es la
distancia desde cada cara interior. En la pantalla, `s mayor` va desde la base
hasta el corte y `s menor` sigue hasta la coronación; la cota es la altura
sobre la cara superior de la base. Hay un solo corte por acero. Un ítem
numérico deja ese diámetro y esa separación en toda la longitud.

El total se verifica con la envolvente completa. El continuo se verifica con los
esfuerzos locales de los sectores donde queda solo; un fallo del continuo aislado
en el centro no lo invalida si allí existe adicional suficiente. Si el total
falla o el continuo no puede cumplir fuera del adicional después de prolongarlo,
no se acepta un corte. No se cambian silenciosamente las familias solicitadas.
Las cotas del dibujo, como 1.78 m, no se imponen como longitudes válidas.

Las tablas compartidas por consola y Word y el archivo `zonas_zapata.csv`
identifican extremo izquierdo, centro y extremo derecho, áreas totales efectivas,
separación real, momento de servicio local, esfuerzo del acero, límites e índices
de flexión, cortante, fisuración y mínimo. JSON guarda tanto la selección como
esas comprobaciones. Los elementos que lindan con los cortes se incluyen
completos en ambas zonas de forma conservadora. El gráfico distingue las
familias continuas y adicionales. Una nueva selección elimina resultados previos.

## Corte de pantalla

En el comando 2, el corte del acero vertical hacia el relleno conserva la barra
elegida y deja arriba exactamente el doble de separación: con `1" @ 0.10 m`
abajo continúa `1" @ 0.20 m`; con `1" @ 0.125 m` abajo continúa `1" @ 0.25 m`.
La altura se mide sobre la cara superior de la base. Se verifican flexión,
cortante, servicio y mínimo con el acero remanente. Si el doble de separación
supera el máximo de la malla, no cubre el acero mínimo o el remanente no cumple,
esa fila no aparece. El comando original mantiene su propia separación superior.
