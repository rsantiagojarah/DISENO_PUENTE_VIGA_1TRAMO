"""Present the calculated skew correction without changing design results."""

from bridge_design.codes.skew import SKEW_SHEAR_REFERENCE


def skew_input_lines(project):
    if not project.skew_angle_deg:
        return []
    lines = [f"Angulo de esviaje                    : {project.skew_angle_deg:10.3f} grados"]
    if project.skew_angle_deg:
        lines.extend([
            "Lineas de apoyo paralelas con igual esviaje.",
            "Cv conservador: todas las vigas, ambos extremos y toda la luz.",
            "Solo cortante vehicular; momentos sin reduccion por esviaje.",
            "Armadura principal de losa perpendicular a las vigas.",
            SKEW_SHEAR_REFERENCE,
        ])
        for name, geometry in (("interior", project.interior_girder),
                               ("exterior", project.exterior_girder)):
            trace = geometry.skew_correction
            lines.append(f"Viga {name}: L={trace.span_ft:.5f} ft; ts={trace.slab_thickness_in:.5f} in; "
                         f"Kg={trace.longitudinal_stiffness_in4:.5f} in4; Cv={trace.factor:.6f}")
            lines.append(f"gV base={geometry.live_load_shear_distribution_factor_g:.6f}; gV aplicado=Cv*gV base.")
    return lines


def skew_shear_trace(geometry, analysis):
    trace = geometry.skew_correction
    return (
        "Cv = 1 + 0.20 (12 L ts^3 / Kg)^0.3 tan(alpha); gV = Cv gV,base",
        "alpha: esviaje desde la perpendicular al eje (grados); L: luz (ft); "
        "ts: espesor de losa (in); Kg: rigidez longitudinal n(I+A eg^2) (in4), n=1; "
        "gV,base: distribucion sin esviaje; Cv: correccion de cortante.",
        f"alpha={trace.angle_deg:.3f} grados\nL={trace.span_ft:.5f} ft\n"
        f"ts={trace.slab_thickness_in:.5f} in\nKg={trace.longitudinal_stiffness_in4:.5f} in4\n"
        f"Cv=1+0.20*(12*{trace.span_ft:.5f}*{trace.slab_thickness_in:.5f}^3/"
        f"{trace.longitudinal_stiffness_in4:.5f})^0.3*tan({trace.angle_deg:.3f} grados)"
        f"={trace.factor:.6f}\n"
        f"gV={trace.factor:.6f}*{geometry.live_load_shear_distribution_factor_g:.6f}"
        f"={analysis.shear_distribution_factor_g:.6f}.",
        f"Cv={trace.factor:.6f}; gV aplicado={analysis.shear_distribution_factor_g:.6f}.",
        "Lineas de apoyo paralelas con igual esviaje. Se conserva Cv en todas las vigas, "
        "ambos extremos y toda la luz, sin disminucion hacia el centro. "
        "La correccion afecta al cortante vehicular, incluido el camion de fatiga; "
        "DC, DW y PL conservan sus valores. Los momentos no se reducen por esviaje. "
        "Armadura principal de losa perpendicular a las vigas.",
    )
