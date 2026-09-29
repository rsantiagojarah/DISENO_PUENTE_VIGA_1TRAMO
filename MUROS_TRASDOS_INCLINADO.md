# Muros con trasdós vertical o inclinado

La entrada existente `suelo_sismo.theta_cara_posterior_desde_horizontal_grados`
se admite en terminal y YAML. El relleno está en el trasdós: a la derecha en
el esquema del programa. Puede reflejarse la sección sin cambiar su cálculo.

- **Automático (predeterminado):** en la consola pulse Enter o escriba `auto`.
  Calcula θ con los espesores y H-D, adoptando cara exterior vertical.
- θ = 90°: trasdós vertical; mantiene los espesores ingresados.
- θ < 90°: la coronación del trasdós se retira hacia la puntera.
- Retiro b = (H-D) tan(90°-θ).
- Para cara exterior vertical y todo el ensanche hacia el relleno:
  θ = 90° - atan((e_inferior-e_superior)/(H-D)).
- Se permite θ_mínimo <= θ <= 90°, con θ_mínimo dado por esa expresión.
  Se rechazan geometrías que requieran voladizo del fuste hacia la puntera.

Para la imagen de referencia, la altura de pantalla sobre zapata es 6,25 m,
el espesor inferior 1,00 m y el superior 0,50 m. Resulta θ = 85,42607874°.
La entrada de altura total H debe sumar a esos 6,25 m el espesor D de zapata.
La imagen no acota D; no se ha sustituido el YAML personal del usuario.

El nuevo caso inclinado admite relleno horizontal (β=0), interfaz lisa (δ=0),
sin agua y sin cohesión, con las demás hipótesis existentes del cálculo activo.
No se ha habilitado la inclinación del estribo con cajuela. La consola indica
el ángulo calculado y el adoptado. Las nuevas plantillas YAML incluyen:

```yaml
suelo_sismo:
  theta_cara_posterior_desde_horizontal_grados: auto
```

También se calcula automáticamente si esa clave se omite o es nula. Si se
modifican los espesores o H-D, se recalcula al cargar el archivo. Los YAML con
un valor numérico explícito conservan ese ángulo; use `90` para trasdós vertical.
Con espesores iguales, el resultado automático es 90°. El modo automático
mantiene la validación de β=0 y δ=0 cuando resulte un trasdós inclinado; no
sustituye silenciosamente por otra geometría si los datos son incompatibles.

## Cuerpos de cálculo y trazabilidad

La estabilidad externa considera muro y suelo sobre el talón, con empuje en
un plano virtual vertical por el extremo del talón. Incluye el volumen triangular
sobre el trasdós inclinado y la sobrecarga sobre su proyección horizontal. El
coeficiente global no cambia por inclinar la cara interna del conjunto. Sí
cambian los pesos, centroides, inercia y presiones de contacto.

El diseño de pantalla usa Coulomb y Mononobe-Okabe sobre la cara real. En M-O
la inclinación desde la vertical es α=90°-θ. Las fuerzas normales a la cara
se descomponen en Px=P cosα, Py=P sinα, con Py hacia abajo. El momento en
cada corte incluye Px*y-Py*(x_cara-x_centro) y el momento desfavorable del
peso del fuste. No se acredita el momento favorable de dicho peso ni la
compresión axial como incremento de resistencia. Se integra la masa real por
encima del corte para la inercia y se conservan las dos combinaciones PAE/PIR.

El talón inclinado incorpora el equilibrio del suelo sobre el trasdós: peso,
sobrecarga, reacción opuesta de la pantalla y acciones externas e inerciales.
Las fuerzas de la cara real no se vuelven a sumar a la estabilidad global.
Las longitudes principales se miden siguiendo la inclinación del acero.
Los reportes diferencian ambos planos y el esquema dibuja el trasdós adoptado.

## Referencias

- FHWA NHI-06-089, Vol. II, sección 10.4.2, p. 10-20: plano vertical por el
  talón para el conjunto de muro en voladizo y suelo retenido.
  https://www.fhwa.dot.gov/engineering/geotech/pubs/nhi06089.pdf
- FHWA NHI-10-024, ecuación 7-6: Mononobe-Okabe con inclinación del muro.
  https://highways.fhwa.dot.gov/sites/fhwa.dot.gov/files/FHWA-NHI-10-024.pdf
- Manual de Puentes MTC 2018, Art. 2.8.1.1.14.1: envolvente de las dos
  combinaciones de empuje e inercia ya adoptadas en el proyecto.

La validación incluye equilibrio independiente de cuñas de Coulomb y M-O,
centroides por polígonos, integración de momentos y cierre de fuerzas verticales.
