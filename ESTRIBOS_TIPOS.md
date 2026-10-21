# Modelos de estribo individual A y B

`diseno-estribos` permite elegir la geometria antes del ingreso de datos. El modelo
A conserva la geometria y los resultados anteriores. El modelo B representa
`MODELO_B_ESTRIBO.pdf`: parapeto, cabezal, transicion posterior y cara exterior
inclinada continua desde la zapata hasta el asiento del tablero.

Ambos usan el mismo procedimiento de estabilidad y concreto armado: cargas,
combinaciones con y sin puente, eventos sismicos A/B, contacto y capacidad
portante, deslizamiento y dentellon, pantalla, talon, puntera, seleccion de acero,
minimos, fisuracion, desarrollo y corte de barras. La memoria Word identifica
el modelo y dibuja su geometria real.

## Uso

```powershell
diseno-estribos
diseno-estribos --tipo B
diseno-estribos output mi_modelo_b.yaml --tipo B
diseno-estribos input modelo_estribo_B.yaml
```

Sin `--tipo`, el ingreso manual pregunta A/B y Enter conserva A. En YAML se usa
`geometria.tipo_estribo: B`. Los YAML anteriores que omiten esta clave conservan A.
Una seleccion `--tipo` al leer YAML debe coincidir con el modelo declarado en el
archivo; no transforma una geometria A en B silenciosamente.

`modelo_estribo_B.yaml` es un ejemplo editable. Sus valores son referenciales:
el PDF solo define la forma, no proporciona dimensiones numericas, materiales,
cargas ni parametros geotecnicos del proyecto.

## Correspondencia de dimensiones del modelo B

| PDF | Clave en geometria | Definicion |
| --- | --- | --- |
| H | altura_relleno_activo_m | Desde fondo de zapata hasta coronacion |
| B | ancho_zapata_m | Ancho total de cimentacion |
| D | espesor_zapata_m | Espesor de cimentacion |
| L_punta | longitud_puntera_m | Borde exterior a cara exterior de pantalla en la base |
| L_talon | Calculada | B - L_punta - t_inf |
| t_inf | espesor_inferior_pantalla_m | Espesor real de pantalla en la base |
| t_sup | espesor_superior_pantalla_m | Ancho del nucleo rectangular, region 4 |
| t2 | retiro_superior_relleno_t2_m | Proyeccion posterior de la transicion |
| b_parap. | espesor_parapeto_posterior_m | Ancho del parapeto |
| h_parap. | altura_cajuela_m | Altura del parapeto sobre el asiento |
| N | longitud_cajuela_m, opcional | Asiento horizontal libre |
| h | altura_suelo_frontal_m | Desde fondo de zapata hasta suelo frontal |
| Altura de bloque | altura_bloque_cajuela_m | Altura de la region 2 |
| Altura de transicion | altura_transicion_m | Altura de la region 3 |

El cierre geometrico exige `N + b_parapeto = t_sup + t2`. En consola N se calcula.
En YAML, si se omite `longitud_cajuela_m`, tambien se calcula; si se proporciona,
se comprueba esa igualdad. No todas estas dimensiones son independientes.
El ancho real de pantalla a cada altura se obtiene de sus dos caras, incluyendo
la pendiente exterior continua y la transicion posterior.
El minimo por temperatura usa el espesor medio real del panel bajo la transicion;
en B ese espesor medio no es simplemente `(t_inf+t_sup)/2`.

La pendiente exterior se define con altura `H-D-h_parapeto` y ensanche
`t_inf-t_sup`; no se introduce una transicion frontal t1. Se conservan las
regiones de concreto 1-6 y relleno 7-11. Sus areas y centroides se calculan con
poligonos; la carga del tablero se ubica en el centro de N. El brazo del suelo
triangular de la region 8 sobre el talon es `2*t2/3` desde la cara posterior de
la pantalla, coherente con el inventario global.

Los ejes internos se conservan: x desde borde de puntera hacia talon, y desde
fondo de zapata. La figura B se refleja para mostrar talon a la izquierda y
puntera a la derecha, como el PDF. Las tablas y los diagramas de contacto
mantienen el eje x interno. Las longitudes de barras de la cara del relleno
incluyen la transicion inclinada; los cortes prolongan ld sobre ese recorrido.

## Alcance

Esta opcion corresponde al estribo individual en voladizo con relleno horizontal
del esquema (`beta=0`, cara equivalente de empujes `theta=90`). La friccion
muro-suelo puede ingresarse y usa las funciones existentes de transferencia al
talon. Otras pendientes de relleno se rechazan explicitamente en B.

El parapeto, cabezal y transicion participan en geometria, masas y brazos. El
armado local del parapeto y cabezal, el apoyo concentrado, doblados y acomodo de
barras requieren su diseno y detalle especificos; no se presentan como verificados
por el diseno de pantalla y zapata. Las comprobaciones de anclaje conservan el
alcance del modulo existente.

Los comandos de muros y de estribos conectados FRAME conservan sus modelos
actuales. No se admite B en un FRAME conectado sin adaptar y verificar antes
sus cargas distribuidas y su discretizacion.

## Verificacion

`tests/test_abutment_model_b.py` comprueba areas y centroides contra valores
calculados independientemente, cierre de superficies, integrales de espesor,
pesos e inercia, posicion del tablero, equilibrio de cargas sobre el talon,
recorrido de barras, variantes sin puntera, seleccion de acero, YAML,
consola y dibujo. Las pruebas existentes conservan el control del modelo A.
