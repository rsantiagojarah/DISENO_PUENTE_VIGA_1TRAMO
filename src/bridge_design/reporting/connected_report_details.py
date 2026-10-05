"""Numeric calculation narratives without duplicate input or audit tables."""

from bridge_design.reporting.deck_docx import _body, _calc, _add_native_equation
import re


def mathematical_symbols(text):
    symbols = {"gamma": "γ", "phi": "φ", "eta": "η", "beta": "β",
               "eps": "ε", "mu": "μ", "Delta": "Δ", "lambda": "λ",
               "theta": "θ", "psi": "ψ", "alpha": "α", "delta": "δ"}
    return re.sub(r"\b(gamma|phi|eta|beta|eps|mu|Delta|lambda|theta|psi|alpha|delta)(?=\b|_|\d)",
                  lambda match: symbols[match.group()], text).replace("cm2", "cm²").replace("Tn.m", "tn·m")


def compact_decimal_zeros(text):
    """Remove padding zeros from displayed decimals without further rounding.

    Version/article numbers and scientific notation retain their original text.
    The analysis values and exported numeric data are never modified.
    """
    def compact(match):
        integer, fraction = match.groups()
        fraction = fraction.rstrip("0")
        if not fraction and integer in ("-0", "+0"):
            integer = "0"
        return integer + ("." + fraction if fraction else "")
    return re.sub(r"(?<![\w.])([+-]?\d+)\.(\d+)(?!\w|\.\d)", compact, text)


def calculation(document, title, formula, legend, substitution, result, comment="", reference=""):
    _calc(document, *(mathematical_symbols(compact_decimal_zeros(value)) for value in (title, formula, legend, substitution,
          result.replace("disponible=None cm", "longitud disponible no ingresada"), comment)),
          reference)


def write_springs(document, result):
    data, mesh = result.inputs, result.mesh
    if data.foundation_node_count is None:
        _body(document, f"Malla heredada por paso máximo de {data.mesh_size_m:.3f} m; "
              f"se obtienen {len(mesh.frame.springs)} nudos con resorte.")
    else:
        _body(document, f"Se solicitaron y se colocaron {len(mesh.frame.springs)} nudos con resorte, "
              "equidistantes dentro de cada tramo delimitado por los extremos de talón y los ejes de los estribos. "
              "Los nudos auxiliares de geometría no añaden resortes.")
    _body(document, "El suelo se representa mediante resortes verticales de Winkler, con rigidez K_i=ks·A_i. "
          "El área tributaria comprende la mitad de la distancia a cada vecino; en los extremos se considera el tramo existente.")
    _add_native_equation(document, "A_i = b*(L_izq/2 + L_der/2)")
    _add_native_equation(document, "K_i = ks*A_i")
    _body(document, "L_izq y L_der son distancias entre resortes en m; A_i está en m², ks en tn/m³ y K_i en tn/m. "
          "Control de cobertura: las áreas tributarias deben cubrir la franja completa de ancho b=1 m y longitud L.")
    _add_native_equation(document, "ΣA_i = b*L")


def write_model_description(document, result):
    """General model, formulas and solution method without numerical examples."""
    data, mesh = result.inputs, result.mesh
    _body(document, f"El conjunto se representa mediante un FRAME 2D de franja de 1 m, con "
          f"{len(mesh.frame.nodes)} nudos y {len(mesh.frame.elements)} elementos Euler Bernoulli. "
          "Cada nudo tiene desplazamientos horizontal y vertical y un giro. Las uniones transmiten axial, cortante y momento. "
          f"Los offsets de sección están {'activados' if data.section_offsets else 'desactivados'}.")
    _body(document, "Se emplean secciones brutas elásticas: b es el ancho de franja, t el espesor y Ec el módulo "
          "de elasticidad del concreto. Los espesores variables se discretizan por tramos. Las propiedades son:")
    for formula in ("A = b*t", "I = b*t^3/12", "EI = Ec*I"):
        _add_native_equation(document, formula)
    _body(document, "Ec se calcula según el Manual de Puentes MTC 2018, Artículo 2.5.4.4.")
    _body(document, f"Se restringe Ux en el nudo {mesh.reference_node}, ubicado en x={data.reference_position_m:.3f} m, "
          "para impedir la traslación horizontal del conjunto. Uy y el giro permanecen libres de restricciones fijas. "
          "La reacción horizontal corresponde a este apoyo; el contacto vertical con el suelo se resuelve mediante resortes.")
    write_springs(document, result)
    _body(document, "El método de rigidez por elementos finitos ensambla los elementos, los resortes en contacto "
          "y las cargas de cada combinación. Con las condiciones de apoyo aplicadas, el equilibrio se expresa como:")
    _add_native_equation(document, "K*u = F")
    _body(document, "K es la matriz de rigidez, u los desplazamientos y giros y F las fuerzas y momentos nodales. "
          "El contacto se actualiza iterativamente: se retiran resortes en tracción y se permite recuperar contacto "
          "hasta alcanzar equilibrio con reacciones compresivas. Cada combinación conserva sus resortes activos. "
          "De la solución se obtienen esfuerzos, reacciones, presiones y asentamientos.")
