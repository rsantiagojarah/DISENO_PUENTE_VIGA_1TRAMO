"""Shared pipe-load trace for terminal, Word and PDF reports."""
from dataclasses import replace


def pipe_input_lines(project):
    pipe = project.transverse_slab.load_layout.pipe
    if pipe is None or pipe.q_tn_m == 0:
        return ()
    span = project.interior_girder.span_length_m
    return (
        "TUBERIA LONGITUDINAL — CARGA VERTICAL DW",
        f"Peso total en operacion: {pipe.weight_kg_m:.3f} kg/m = {pipe.q_tn_m:.6f} Tn/m; "
        f"x={pipe.x_from_left_m:.3f} m desde el borde exterior izquierdo de la losa.",
        f"Carga uniforme en toda la luz L={span:.3f} m; peso total={pipe.q_tn_m*span:.3f} Tn; "
        f"incremento global por apoyo={pipe.q_tn_m*span/2:.3f} Tn, sin factor.",
        "El peso ingresado incluye tubo lleno y accesorios. No se suma agua automaticamente.",
        "Reparto por el modelo transversal existente, con apoyos verticales en los ejes de vigas.",
        "Reacciones fisicas de la tuberia (Tn/m; signo conservado): " + "; ".join(
            f"V{i+1}={q:.6f}" for i, q in enumerate(project.girder_pipe_loads)),
        "Diseno longitudinal: se agrega max(reaccion de tuberia, 0) a DW, sin aprovechar reducciones favorables. "
        "Las reacciones para estribos usan los valores fisicos con signo, no esa envolvente conservadora.",
    )


def pipe_comparison_rows(data):
    """Compare controlling Strength I moments, keeping the same other load cases."""
    from bridge_design.domain import transverse_slab as ts, interior_girder as ig, exterior_girder as eg
    from bridge_design.domain.load_combinations import combine_transverse_slab_moments
    from bridge_design.domain._cantilever_slab_calculations import combine_cantilever_moments
    p = data.project_inputs
    if not pipe_input_lines(p):
        return ()
    g = p.transverse_slab.geometry
    layout = replace(p.transverse_slab.load_layout, pipe=None)
    dw = ts.solve_load_case(g, p.materials, "DW sin tuberia", ts._dw_segments(p.materials, layout), ())
    previous = replace(data.transverse_result, dw=dw)
    rows = []
    for direction in ("M+", "M-"):
        moments = []
        for analysis in (previous, data.transverse_result):
            moments.append(max(abs(r.combined_moment_tn_m) for r in combine_transverse_slab_moments(analysis)
                               if r.combination_name == "RESISTENCIA I" and r.direction == direction))
        rows.append(("Losa " + direction, *moments, "Tn*m/m"))
    for group in data.girder_groups:
        pg = group.project_inputs
        geom = pg.exterior_girder if group.exterior else pg.interior_girder
        width = geom.asphalt_tributary_width_m if group.exterior else geom.effective_asphalt_width_m
        q = p.materials.asphalt.specific_weight_tn_m3 * p.materials.asphalt.thickness_m * width
        old = replace(group.result, dw=ig._solve_static_longitudinal_case(geom, "DW sin tuberia", (q,), ()))
        combine = eg.combine_exterior_girder_moments if group.exterior else ig.combine_interior_girder_moments
        moments = [next(r.combined_moment_tn_m for r in combine(a) if r.combination_name == "RESISTENCIA I")
                   for a in (old, group.result)]
        rows.append(("Viga " + group.label, *moments, "Tn*m"))
    for group in data.cantilever_groups:
        effects = tuple(e for e in group.result.load_effects if e.label != "DW - tuberia llena")
        before = max(abs(r.design_moment_tn_m) for r in combine_cantilever_moments(effects) if r.limit_state == "Resistencia")
        rows.append(("Volado " + group.side, before,
                     group.result.controlling_strength.design_moment_tn_m, "Tn*m/m"))
    return tuple((name, f"{before:.6f}", f"{after:.6f}", unit) for name, before, after, unit in rows)
