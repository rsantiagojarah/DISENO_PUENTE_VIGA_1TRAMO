"""Presentación técnica en español del apoyo Método A."""

CONTROL_IDS = {"ROTATION", "HEIGHT_TARGET"}


def title(step):
    return {
        "EPS_ID": "Deformación interior por carga permanente",
        "EPS_IT": "Deformación interior por carga total sin impacto",
        "EPS_ED": "Deformación exterior por carga permanente",
        "EPS_ET": "Deformación exterior por carga total sin impacto",
        "CREEP": "Deflexión diferida por fluencia del elastómero",
        "JOINT": "Deflexión por carga viva y fluencia en la junta",
        "STABILITY_L": "Estabilidad longitudinal",
        "STABILITY_W": "Estabilidad transversal",
    }.get(step.id, step.title)


def number(value, unit="", *, percent=False):
    if value is None:
        return "No determinada"
    if percent:
        return f"{100 * value:.3f} %"
    return f"{value:.5g}" + (f" {unit}" if unit and unit != "-" else "")


def status(step):
    return {"REFERENCIAL": "CUMPLE",
            "CUMPLE (ESTIMADO)": "CUMPLE",
            "PENDIENTE": "No determinada",
            "CUMPLE": "CUMPLE", "NO CUMPLE": "NO CUMPLE"}.get(step.status, step.status)


def result_status(result):
    """Veredicto de las comprobaciones; la fuente se explica por separado."""
    return {"CONFORME": "CUMPLE", "REFERENCIAL": "CUMPLE",
            "ESTIMADO": "CUMPLE", "NO CONFORME": "NO CUMPLE",
            "NO CUMPLE": "NO CUMPLE", "PENDIENTE": "No determinada"}.get(result.status, result.status)


def design_checks(result):
    # La altura solicitada y la dirección de giro son condiciones del diseño,
    # no verificaciones resistentes. Sus fallos siguen afectando el estado global.
    return tuple(s for s in result.checks if s.id not in CONTROL_IDS)


def compression_basis(result):
    curve = result.inputs.compression_curve
    if curve is None:
        return "Modelo elástico aproximado para la deformación por compresión."
    if curve.kind == "referencia":
        return "Deformaciones obtenidas por interpolación de curvas de referencia; valores de cálculo orientativos."
    return "Deformaciones obtenidas de las curvas de compresión del producto: " + curve.source


def conclusion(result):
    if result.status == "NO CONFORME":
        return "El apoyo no satisface las condiciones de diseño evaluadas."
    if result.status == "PENDIENTE":
        return "La evaluación no está determinada para todas las condiciones de diseño."
    if result.status == "ESTIMADO":
        return "Las comprobaciones numéricas son favorables bajo el modelo elástico aproximado adoptado."
    if result.status == "REFERENCIAL":
        return "Las comprobaciones numéricas son favorables con las curvas de referencia adoptadas."
    return "El apoyo satisface las comprobaciones evaluadas con las propiedades y acciones adoptadas."
