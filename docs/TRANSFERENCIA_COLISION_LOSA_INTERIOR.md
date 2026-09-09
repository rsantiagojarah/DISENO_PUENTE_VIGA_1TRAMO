# Transferencia de colisión a la losa interior

Implementación: `domain/interior_collision.py`. Se activa cuando toda la base
de la barrera queda en el primer vano libre entre las dos primeras vigas.
Las bases sobre una viga, cruzando zonas o fuera de ese vano conservan su
advertencia de aplicabilidad. No se traslada su carga al voladizo por defecto.

## Fuentes y decisiones del modelo

- Manual de Puentes MTC 2018, art. 2.4.3.5.1.2: remisión a sección 13 AASHTO.
- Tabla 2.4.3.6.3-1, página impresa 101: Fv y Lv por nivel TL-1 a TL-6.
  Art. 2.4.3.6.3: las acciones horizontales y verticales no son simultáneas.
- [FHWA PSC, Design Step 4.10](https://www.fhwa.dot.gov/bridge/lrfd/pscus04.cfm):
  tracción de interfaz Rw/(Lc+2H), demanda de losa basada en Mc y diseño
  conservador As(M) + N/fy. Se conservan factores de resistencia inferiores
  a 1.0: flexión con compatibilidad del motor existente y máximo 0.90;
  componente de tracción con máximo 0.75.

El ejemplo FHWA corresponde a un voladizo. **Su distribución a 30 grados y
su coeficiente 0.40 no se extrapolan a la barrera interior.** Para esta se
adopta explícitamente una franja elástica continua de 1 m, con rigidez de
losa uniforme y apoyos verticales en ejes de vigas. No representa torsión
de vigas, rigidez horizontal de apoyos ni redistribución en planta.

Se aplica un par concentrado Mc conservado sin reducción por dispersión
en la losa. Si Ft excede Rw, se amplifica por Ft/Rw y la barrera no cumple.
La tracción es max(Ft,Rw)/(Lc+2H), conservada sin reducción en la región
interior. La distribución transversal de la base se acota aplicando el par
en cada extremo de su ancho; se conserva cada caso por separado. Las dos
barreras simétricas se impactan separadamente. Fv/Lv produce los casos
verticales independientes. Esta simplificación es una hipótesis de análisis,
no una disposición literal del manual para barreras interiores.

## Cálculo y resultados

El solucionador admite pares nodales con signo antihorario positivo. El
diagrama conserva los valores a ambos lados del salto de momento. Se
verifican suma de fuerzas y suma de momentos de cada caso. Se combinan DC
y DW en la misma sección con factores 0.90/1.25 y 0.65/1.50; CT=1.0.
Se incluyen extremos analíticos de los tramos parabólicos. No se suman
máximos de ubicaciones diferentes ni se mezcla M horizontal con N vertical.

El acero superior e inferior se calcula para cada diámetro real. Las
alternativas deben satisfacer área, separación y desarrollo recto sin
reducción por exceso. Se prescribe continuidad a través de la losa interior
y se comprueba la longitud disponible hacia ambos bordes, conservadoramente
desde el eje de la viga exterior. Si no cabe el desarrollo, se informa
NO CUMPLE: no se supone un gancho o un anclaje mecánico inexistente.

Las áreas son **mínimos totales por colisión**, no acero adicional que deba
sumarse al ordinario. El armado definitivo de cada cara debe cubrir ambos
diseños y mantener las verificaciones ordinarias de servicio y detalle.
Cambiar el diámetro requiere volver a comprobar el peralte y el anclaje;
las alternativas indicadas corresponden a su propio diámetro.

El corte utiliza el procedimiento general sin estribos, con tracción,
agregado efectivo cero conservador, y envolvente conservadora de M, V y N.
El anclaje de los dowels se vuelve a comprobar por capacidad sin la reducción
por exceso de acero del chequeo de barrera aislada.

Las reacciones exportadas son incrementos verticales simultáneos por caso,
en Tn/m longitudinal. No son las cargas totales de estribos. El modelo global
debe distribuir la acción horizontal y comprobar vigas, diafragmas y apoyos;
la aprobación local de la losa no aprueba automáticamente esos elementos.

## Regresión del YAML Sol de Oro

Con los datos existentes, el cálculo local entrega aproximadamente:

- Superior: As=9.564 cm²/m; alternativa 1/2 pulgada cada 0.125 m.
- Inferior: As=7.909 cm²/m; alternativa 1/2 pulgada cada 0.150 m.
- Corte: Vu=4.339 Tn/m; resistencia reducida=10.340 Tn/m.
- Desarrollo recto de esas alternativas: 0.912 m frente a 0.950 m disponible.
- Dowel por capacidad: requiere 19.38 cm frente a 17.50 cm declarado:
  **NO CUMPLE**. No se modifica automáticamente ese dato geométrico.
- Acero del voladizo por acciones directas: 3.600 cm²/m, independiente de lo anterior.

Pruebas: par sobre viga simplemente apoyada con solución cerrada, salto de
momento, equilibrio por caso, simetría, independencia horizontal/vertical,
TL-4/TL-5, diámetro real, anclaje por capacidad, y presencia de resultados
en las salidas de terminal, Word y PDF. La comprobación de contenido de
reportes no equivale a una revisión visual de un informe completo.
