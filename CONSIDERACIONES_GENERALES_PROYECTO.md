# Consideraciones generales del proyecto

## 1. Proposito

El presente proyecto tiene como objetivo desarrollar un programa en Python para
el diseno de un puente tipo viga-losa, ejecutado desde terminal y orientado a
calculos de ingenieria civil conforme a la normativa aplicable incluida en la
carpeta `docs`.

El codigo debe ser claro, verificable, modular y facil de extender, ya que el
programa incorporara nuevas funcionalidades conforme avance el desarrollo.

## 2. Referencias normativas

Las referencias tecnicas base del proyecto se encuentran en la carpeta `docs`:

- `Manual de Puentes MTC 2018 (PGA).pdf`
- `PUENTES.con.AASHTO.LRFD.2020.9th.Edition_Arturo.Rodriguez.Serquen.pdf`
- `280324845-Aci-Diseno-de-Puentes.pdf`

Todo modulo de calculo debe indicar claramente que articulo, tabla, ecuacion o
criterio normativo respalda el procedimiento implementado. Cuando exista una
diferencia entre referencias, el codigo debe permitir identificar el criterio
adoptado y dejar documentada la decision tecnica.

## 3. Stack tecnologico

El stack principal del proyecto sera:

- Lenguaje: Python 3
- Interfaz: terminal
- Formato de salida: ASCII
- Persistencia inicial: archivos de texto, JSON, CSV o similares cuando sea
  necesario
- Dependencias externas: minimas y justificadas

No se debe incorporar interfaz grafica en la etapa inicial. La prioridad es
contar con un nucleo de calculo robusto, testeable y mantenible.

## 4. Unidades del proyecto

El sistema de unidades del proyecto sera compatible con:

- Fuerza: Tn, kg
- Longitud: m, cm
- Tiempo: seg
- Otras unidades derivadas segun correspondan al calculo

Cada dato de entrada, resultado intermedio y salida debe declarar o inferir de
forma controlada sus unidades. Se debe evitar mezclar unidades dentro de una
misma funcion sin una conversion explicita.

Reglas minimas:

- Las entradas principales de geometria se manejaran preferentemente en `m`.
- Las dimensiones de detalle, acero y secciones podran manejarse en `cm`.
- Las cargas globales podran manejarse en `Tn`.
- Las verificaciones que requieran esfuerzo podran usar unidades consistentes
  derivadas, por ejemplo `kg/cm2` o `Tn/m2`.
- Toda conversion debe centralizarse en un modulo de unidades.

## 5. Arquitectura

La arquitectura sera monolitica modular por capas.

Esto significa que el sistema se ejecutara como una sola aplicacion, pero su
codigo estara separado en capas internas con responsabilidades claras. No se
usara una arquitectura de microservicios ni componentes distribuidos.

Capas principales:

- Capa de ingreso de datos: captura, lectura, normalizacion y validacion de
  entradas.
- Capa de nucleo de calculo: dominio, unidades, normativa, formulas y servicios
  de calculo estructural.
- Capa de resultados: almacenamiento interno, organizacion y evaluacion de
  resultados calculados.
- Capa de reportes: presentacion de resultados en terminal y generacion de
  reportes ASCII.

Regla de dependencias:

```text
Ingreso de datos -> Nucleo de calculo -> Resultados -> Reportes
```

Las dependencias deben avanzar en ese sentido. El nucleo de calculo no debe
depender de la terminal, de reportes ni de formatos especificos de entrada. La
capa de reportes solo debe presentar resultados ya calculados, no ejecutar
formulas de diseno.

Estructura base sugerida:

```text
src/
  bridge_design/
    __init__.py
    main.py
    input_layer/
      __init__.py
      cli_input.py
      file_input.py
      input_models.py
      input_validators.py
      input_normalizers.py
    config/
      __init__.py
      project_settings.py
    calculation_core/
      __init__.py
      domain/
        __init__.py
        geometry.py
        materials.py
        loads.py
        sections.py
      units/
        __init__.py
        converters.py
        unit_types.py
      codes/
        __init__.py
        mtc_2018.py
        aashto_lrfd_2020.py
        aci.py
      services/
        __init__.py
        load_combinations.py
        structural_analysis.py
        design_checks.py
    results_layer/
      __init__.py
      result_models.py
      result_status.py
      result_summary.py
    reports_layer/
      __init__.py
      ascii_tables.py
      terminal_report.py
      text_report.py
    tests/
      __init__.py
```

La estructura podra evolucionar, pero siempre respetando la separacion entre
ingreso de datos, nucleo de calculo, resultados y reportes.

## 6. Principios de diseno

El codigo debe seguir principios SOLID y DRY.

Aplicacion practica:

- Single Responsibility: cada modulo, clase o funcion debe tener una razon clara
  para cambiar.
- Open/Closed: las reglas normativas y verificaciones deben poder ampliarse sin
  romper calculos existentes.
- Liskov Substitution: si se definen interfaces o clases base, sus
  implementaciones deben ser intercambiables sin alterar el comportamiento
  esperado.
- Interface Segregation: evitar interfaces grandes; cada servicio debe exponer
  solo lo que necesita el consumidor.
- Dependency Inversion: los calculos de alto nivel no deben depender de detalles
  de entrada, salida o presentacion.
- DRY: no duplicar formulas, conversiones, validaciones ni textos normativos
  repetidos.

## 7. Limite de tamano por modulo

Cada archivo `.py` debe tener como maximo 350 lineas.

Si un modulo supera ese limite, debe dividirse por responsabilidad. Ejemplos:

- Separar validaciones de calculos.
- Separar formulas normativas de servicios de diseno.
- Separar generacion de reportes de los resultados numericos.
- Separar modelos de datos de logica de negocio.

El limite no debe resolverse eliminando claridad, comentarios utiles o pruebas.

## 8. Estilo de codigo

Reglas generales:

- Usar nombres descriptivos en ingles tecnico o espanol tecnico, pero mantener
  consistencia en todo el proyecto.
- Preferir funciones cortas y puras para formulas de calculo.
- Evitar variables globales mutables.
- Evitar numeros magicos; usar constantes con nombre.
- Documentar formulas con referencia normativa.
- Validar entradas antes de ejecutar calculos.
- Manejar errores con mensajes claros para terminal.
- Mantener compatibilidad con salida ASCII.

Ejemplo de documentacion esperada en una funcion:

```python
def calculate_design_moment(load: float, span: float) -> float:
    """Return design moment for a simply supported span.

    Units:
        load: Tn/m
        span: m
        return: Tn*m

    Reference:
        See applicable load model in docs/Manual de Puentes MTC 2018.
    """
    return load * span**2 / 8
```

## 9. Entrada de datos

La entrada inicial de datos sera por terminal o por archivos simples. El sistema
debe validar:

- Geometria del puente.
- Propiedades de materiales.
- Cargas permanentes.
- Cargas vehiculares o normativas.
- Factores de mayoracion y combinaciones.
- Parametros de diseno.

Toda entrada numerica debe verificar rango, tipo de dato y unidad esperada.

## 10. Salida en terminal

La salida debe ser clara y en formato ASCII.

Ejemplo de formato:

```text
============================================================
DISENO DE PUENTE VIGA-LOSA
============================================================
Luz del tramo                         : 18.00 m
Ancho total                           :  8.40 m
Numero de vigas                       :  4
Separacion entre vigas                :  2.20 m
------------------------------------------------------------
RESULTADOS PRINCIPALES
------------------------------------------------------------
Momento ultimo positivo               : 125.40 Tn*m
Cortante ultimo                       :  48.20 Tn
Estado de verificacion flexion        : CUMPLE
Estado de verificacion corte          : CUMPLE
============================================================
```

La salida no debe depender de caracteres especiales, simbolos Unicode ni
formatos que fallen en terminales basicas.

## 11. Capas y modulos principales esperados

### Capa de ingreso de datos

Contendra la interaccion inicial con el usuario o con archivos de entrada.

Responsabilidades:

- Solicitar datos desde terminal.
- Leer datos desde archivos simples cuando se implemente.
- Validar tipo, rango y unidad esperada.
- Normalizar datos antes de enviarlos al nucleo de calculo.
- Convertir entradas externas en modelos internos limpios.

Esta capa no debe contener formulas de diseno ni criterios normativos.

### Capa de nucleo de calculo

Contendra el dominio tecnico y los servicios de calculo.

Responsabilidades:

- Modelar geometria del tablero, vigas, losa, materiales, cargas y secciones.
- Centralizar conversiones de unidades.
- Implementar formulas, factores, limites y reglas normativas.
- Ejecutar analisis estructural.
- Calcular distribucion de cargas.
- Generar combinaciones de carga.
- Ejecutar verificaciones de resistencia y servicio.

Esta capa no debe leer datos desde terminal ni generar reportes. Cada formula
normativa debe indicar la referencia tecnica usada.

### Capa de resultados

Contendra los objetos de salida del nucleo de calculo.

Responsabilidades:

- Almacenar resultados numericos.
- Registrar estados de verificacion, por ejemplo `CUMPLE` o `NO CUMPLE`.
- Agrupar resultados por componente, etapa o tipo de verificacion.
- Preparar resumenes tecnicos reutilizables por la capa de reportes.

Esta capa no debe imprimir directamente en terminal ni recalcular formulas.

### Capa de reportes

Contendra la presentacion final de resultados.

Responsabilidades:

- Formatear tablas ASCII.
- Generar reportes de texto.
- Presentar resultados en terminal.
- Ordenar resultados para lectura tecnica clara.
- Mostrar unidades en cada magnitud relevante.

Esta capa solo debe consumir objetos de la capa de resultados.

## 12. Pruebas

Se debe incorporar pruebas automatizadas conforme avance el desarrollo.

Prioridades:

- Conversiones de unidades.
- Formulas normativas.
- Combinaciones de carga.
- Verificaciones de resistencia.
- Casos conocidos de referencia.
- Validacion de entradas invalidas.

Cada formula critica debe tener al menos una prueba con resultado esperado.

## 13. Escalabilidad funcional

El proyecto debe permitir incorporar progresivamente:

- Nuevos tipos de puentes.
- Nuevas combinaciones de carga.
- Nuevos criterios normativos.
- Verificaciones adicionales.
- Generacion de reportes mas completos.
- Lectura de datos desde archivos.
- Exportacion de resultados.
- Integracion futura con interfaces graficas o web, sin modificar el nucleo de
  calculo.

Para lograrlo, el nucleo de dominio y calculo no debe depender de la CLI.

## 14. Criterios de aceptacion del codigo

Antes de considerar listo un modulo nuevo, debe cumplir:

- Archivo menor o igual a 350 lineas.
- Responsabilidad unica y clara.
- Sin duplicacion innecesaria.
- Entradas validadas.
- Unidades documentadas.
- Referencia normativa indicada si aplica.
- Salida ASCII si el modulo genera texto.
- Pruebas o caso manual verificable.
- Nombres claros y consistentes.

## 15. Convenciones iniciales

Convenciones recomendadas:

- Usar `dataclasses` para entidades simples del dominio.
- Usar `typing` para anotar entradas y salidas.
- Usar `pytest` para pruebas automatizadas.
- Usar `ruff` o herramienta equivalente para estilo cuando se configure el
  proyecto.
- Mantener dependencias externas al minimo.

## 16. Regla de desarrollo

Cada nueva funcionalidad debe implementarse siguiendo este flujo:

1. Identificar la referencia normativa aplicable.
2. Definir entradas, salidas y unidades.
3. Crear o reutilizar modelos del dominio.
4. Implementar formulas en el modulo normativo correspondiente.
5. Coordinar el calculo en un servicio.
6. Validar entradas.
7. Presentar resultados en ASCII.
8. Agregar prueba o caso de verificacion.
9. Confirmar que ningun modulo supera 350 lineas.

Este documento debe usarse como guia base para generar y revisar codigo del
proyecto.

## 17. Comando de muro de concreto armado en cantilever

El proyecto incluye un flujo de terminal para disenar un muro de contencion puro
de concreto armado en cantilever, evaluado por franja longitudinal de 1.00 m.
El comando `diseno-muros` considera solo muro cantilever simple: zapata
rectangular con puntera y talon, pantalla trapezoidal con espesor superior e
inferior, altura frontal de suelo, sin cajuela, sin apoyos, sin tablero y sin
retiro superior `t2`. Las cargas de superestructura se anulan siempre en este
modo, aun cuando se pasen por YAML o API.
El flujo de muro expone una API de dominio propia en
`bridge_design.domain.cantilever_wall`; internamente reutiliza el motor
compartido de estructuras cantilever de contencion para evitar duplicar
formulas.

Comandos simples en espanol:

```powershell
diseno-tablero
diseno-estribos
diseno-apoyos
diseno-muros
```

Comandos disponibles:

```powershell
bridge-design tablero
bridge-design muro
bridge-cantilever-wall-design
bridge-muro-cantilever
```

`diseno-tablero` ejecuta el procedimiento completo de la superestructura:
losa transversal, acero de losa, control de fisuracion, viga interior, viga
exterior, detalle de acero de vigas, barrera, losa en voladizo, diafragmas y
resumen de reacciones para estribos.

Alcance normativo y de calculo:

- Manual de Puentes MTC 2018 / AASHTO LRFD.
- Empuje activo de suelo por Coulomb.
- Sobrecarga vehicular equivalente sobre relleno, interpolada segun la altura.
- Empuje sismico por Mononobe-Okabe mediante `kAE`.
- Componentes sismicas del muro y relleno: `EQterr` y `PIR`.
- Combinacion `Evento Extremo I` para condiciones sismicas.
- Verificaciones LRFD de volteo, deslizamiento y presion de contacto.
- Criterio de presion suelo-zapata:
  - Para presion admisible con `qadm`, se usa `Servicio I` con Meyerhof:
    `B' = B - 2|e|` y `q = V/B' <= qadm`.
  - Para capacidad portante LRFD, se usan `Resistencia I` y `Evento
    Extremo I` con Meyerhof: `q = Vu/B' <= phi*qn`, adoptando
    `qn = FS*qadm` cuando solo se ingresa `qadm`.
  - Para diseno estructural de talon y puntera se usa la envolvente de
    `Resistencia I` y `Evento Extremo I` con presion lineal trapezoidal o
    triangular, sin traccion del suelo.
  - Para fisuracion se usa `Servicio I` con la presion lineal de servicio.
- Diseno estructural de pantalla, talon y puntera.
- Control de fisuracion, desarrollo/anclaje y cuadro de acero.

## 18. Memoria de calculo Word del tablero

El comando `diseno-tablero` genera automaticamente una memoria de calculo Word
despues de completar el analisis y la seleccion de armaduras. Una ventana nativa
permite elegir el nombre y la ubicacion del archivo; si se cancela la ventana,
los resultados de terminal se conservan y no se crea el documento.

Caracteristicas del reporte:

- Formato A4 con fuente Arial Narrow, encabezado, pie y numeracion de paginas.
- Desarrollo de formula general, leyenda, sustitucion numerica, resultado,
  criterio adoptado y referencia normativa.
- Secciones para datos de entrada, losa transversal, vigas interior y exterior,
  barrera, losa en voladizo, diafragmas y reacciones para estribos.
- Diagramas de las envolventes factorizadas de momento y cortante empleadas en
  el diseno, ubicados junto al componente correspondiente.
- Tablas reservadas para comparaciones y resumenes donde mejoran la lectura.
- Desarrollo numerico limitado a las estaciones criticas y a la opcion de acero
  adoptada, con verificaciones de servicio, fatiga, fisuracion, desarrollo y
  detalle.
- Comentario tecnico posterior a cada comprobacion, indicando el criterio que
  gobierna y la medida necesaria si la verificacion no cumpliera.

La capa de reporte consume resultados ya calculados y el acero seleccionado por
el usuario; no modifica ni duplica el nucleo de calculo estructural.
