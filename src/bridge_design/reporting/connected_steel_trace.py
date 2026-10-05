"""Formula, substitution and conclusion blocks shared by terminal and Word."""

from math import prod

from bridge_design.reporting.connected_audit import AuditStep, AuditTable, number
from bridge_design.reporting.connected_case_groups import case_label
from bridge_design.reporting.abutment_docx import (
    REF_FLEXURE, REF_SHEAR, REF_CRACK, REF_DEVELOPMENT, REF_TEMPERATURE,
)


def status(ratio):
    return "CUMPLE" if ratio <= 1 + 1e-8 else "NO CUMPLE"


def moment_demand_expression(row, moment='abs(Mu)', cracking='Mcr'):
    """Keep the minimum-capacity factor inside the conditional minimum."""
    return f'max({moment}, min({cracking}, {row["multiplier"]:.6g}*{moment}))'


def source(row):
    demand = row["demand"]
    origin = f"{row['region']}; {row.get('section_location', 'seccion')}; " if row.get("region") else ""
    return (f"{origin}{case_label(demand['case'])}; elemento {demand['element']}; s/L={demand['station']:.6g}; "
            f"x={row['x']:.6g}, y={row['y']:.6g} m; h={demand['depth_cm']:.6g} cm; "
            f"N={demand['axial']:.6g} Tn; M={demand['moment']:.6g} Tn.m; V={demand['shear']:.6g} Tn; cara {row['face']}.")


def steel_tables(steel, audit):
    rows = []
    for name, key, ratio in (("Flexion", "flexure", "flexure_ratio"),
                             ("Cortante", "shear", "shear_ratio"),
                             ("Fisuracion", "service", "crack_ratio")):
        row = audit[key]
        if row is not None:
            rows.append((name, source(row), number(row[ratio])))
    yield AuditTable(f"{steel.region}: secciones gobernantes independientes", ("Control", "Origen y ubicacion", "Indice"), tuple(rows),
                     "Cada control usa su propio caso y seccion; no se combinan maximos independientes. N se incluye en beta; no se verifica interaccion N-M. Caras e interiores; transiciones incluidas en losa central.")
    rows = []
    for limit_state in sorted({row["demand"]["limit_state"] for row in audit["areas"]}):
        candidates = [row for row in audit["areas"] if row["demand"]["limit_state"] == limit_state]
        for label, key in (("Flexion", "flexural_area"), ("Capacidad minima", "minimum_area")):
            row = max(candidates, key=lambda item: item[key])
            rows.append((f"{limit_state}: {label}", source(row), number(row[key])))
    yield AuditTable(f"{steel.region}: acero requerido por estado limite", ("Criterio", "Caso y seccion", "As cm2/m"), tuple(rows),
        "As se obtiene invirtiendo la misma resistencia rectangular con phi limitado por deformacion. "
        "El peralte usa la barra elegida. INF indica que la seccion simplemente reforzada no alcanza la demanda.")
    yield AuditTable(f"{steel.region}: acero adoptado por cara", ("Concepto", "Valor"), (
        ("As flexion cm2/m", number(steel.flexural_as_cm2_m)),
        ("As capacidad minima cm2/m", number(steel.capacity_minimum_as_cm2_m)),
        ("As temperatura cm2/m", number(steel.temperature_cm2_m)),
        ("As requerido flexion y minimos cm2/m", number(steel.required_as_cm2_m)),
        ("Principal", f"{steel.bar_label} @ {steel.spacing_m:.3f} m"),
        ("As proporcionado cm2/m", number(steel.area_per_face_cm2_m)),
        ("Transversal", f"{steel.transverse_bar_label} @ {steel.transverse_spacing_m:.3f} m"),
        ("As transversal proporcionado cm2/m", number(audit["transverse_area"])),
        ("Estado comprobaciones del armado", steel.status), ("Estado anclaje independiente", steel.anchor_status)),
        "As requerido no sustituye las comprobaciones de cortante y fisuracion. Dos caras iguales; "
        "no se acredita el acero de la cara comprimida. No se generan longitudes de barras sin detalle geometrico.")


def steel_steps(steel, audit):
    flexure, shear, service = (audit[key] for key in ("flexure", "shear", "service"))
    demand = flexure["demand"]
    response = flexure["response"]
    substituted_demand = moment_demand_expression(
        flexure, f'{abs(demand["moment"]):.6g}', f'{flexure["cracking"]:.6g}')
    yield AuditStep("Peralte y acero de la seccion gobernante de flexion",
        "d = h - r - (db/2); As = Ab/s", "h: espesor cm; r: recubrimiento cm; db: diametro cm; s: separacion m.",
        f"d={demand['depth_cm']:.6g}-{flexure['cover']:.6g}-({flexure['diameter']:.6g}/2)={flexure['effective']:.6g} cm; "
        f"As={audit['bar_area']:.6g}/{steel.spacing_m:.6g}={steel.area_per_face_cm2_m:.6g} cm2/m.",
        source(flexure), "Los peraltes de las demas comprobaciones se calculan en sus propias secciones.", REF_FLEXURE)
    yield AuditStep("Momento minimo y demanda de capacidad",
        "Mcr = 1.072*2.01*sqrt(fc)*b*h^2/(6*100000); Md = " + moment_demand_expression(flexure),
        "b: 100 cm; h: espesor cm; fc: kgf/cm2; momentos: Tn.m/m.",
        f"fc={audit['concrete']:.6g}; h={demand['depth_cm']:.6g}; Mcr={flexure['cracking']:.6g}; "
        f"Md={substituted_demand}"
        f"={flexure['required_moment']:.6g} Tn.m/m.",
        f"Md={flexure['required_moment']:.6g} Tn.m/m; "
        f"As requerido=max({steel.flexural_as_cm2_m:.6g}, {steel.capacity_minimum_as_cm2_m:.6g}, "
        f"{steel.temperature_cm2_m:.6g})={steel.required_as_cm2_m:.6g} cm2/m.",
        "Los maximos de acero se obtienen revisando espesores y estados de toda la region, no solo esta seccion.",
        "Manual de Puentes MTC 2018, Art. 2.9.1.4.4.2; AASHTO LRFD 5.7.3.3.2.")
    yield AuditStep("Resistencia a flexion del acero elegido",
        "a = beta1*c; eps = 0.003*(d-c)/c; fs = min(fy, Es*eps); 0.85*fc*b*a = As*fs; Mr = phi*As*fs*(d-a/2)/100000",
        "c: eje neutro cm; a: bloque cm; Es: 2000000 kgf/cm2; phi: menor entre limite ingresado y factor por deformacion.",
        f"fc={audit['concrete']:.6g}; fy={audit['yield_strength']:.6g}; b=100; d={flexure['effective']:.6g}; "
        f"As={flexure['area']:.6g}; c={response['neutral_axis_depth_cm']:.6g}; "
        f"a={response['compression_block_depth_cm']:.6g}; eps={response['extreme_tensile_strain']:.6g}; "
        f"fs={response['steel_stress_kg_cm2']:.6g}; phi={flexure['phi']:.6g}.",
        f"Mr={flexure['capacity']:.6g} Tn.m/m; Md/Mr={flexure['required_moment']:.6g}/"
        f"{flexure['capacity']:.6g}={flexure['flexure_ratio']:.6g}.", status(flexure["flexure_ratio"]), REF_FLEXURE)
    if shear.get("shear_method") == "simplified":
        yield AuditStep("Cortante y procedimiento simplificado",
            "dv = max(0.9*d, 0.72*h); beta = 2; Vr = phi_v*0.265*beta*sqrt(fc)*100*dv/1000",
            "dv: cm; fc: kgf/cm²; V y Vr: tn/m; beta=2 según el procedimiento simplificado del módulo individual.",
            source(shear) + f" d={shear['effective']:.6g}; dv={shear['shear_depth']:.6g}; beta=2; "
            f"phi_v={audit['shear_phi']:.6g}; fc={audit['concrete']:.6g}.",
            f"Vr={shear['shear_capacity']:.6g} tn/m; abs(V)/Vr={shear['shear_ratio']:.6g}.",
            status(shear["shear_ratio"]), REF_SHEAR)
    else:
        yield from _general_shear_step(shear, audit)
    if service is not None and service.get("service_tension", True):
        yield AuditStep("Fisuracion y tension del acero en servicio",
            "fs = abs(Ms)*100000/(As*0.90*d); fs_usado = min(fs,0.60*fy); beta_s = 1+dc/(0.7*(h-dc)); "
            "smax = max(0, (123000/(beta_s*fs_usado*0.0980665)-20*dc)/1000)",
            "Ms: tn·m/m; fs: kgf/cm²; dc=r+db/2 en cm; smax: m; exposición=1.00; fs_lim=0.60*fy.",
            source(service) + f" As={service['area']:.6g}; d={service['effective']:.6g}; "
            f"dc={service['axis']:.6g}; beta_s={service['beta_service']:.6g}; fs={service['stress']:.6g}; "
            f"fs_usado={service['stress_used']:.6g}; fs_lim={service['stress_limit']:.6g}; s={steel.spacing_m:.6g} m.",
            f"smax={service['maximum_spacing']:.6g} m; fs/fs_lim={service['stress_ratio']:.6g}; "
            f"s/smax={service['spacing_ratio']:.6g}; indice={service['crack_ratio']:.6g}.",
            status(service["crack_ratio"]), REF_CRACK)
    elif service is not None:
        yield AuditStep("Fisuracion sin traccion de servicio",
            "Ms = 0; fs = 0", "Ms: momento de servicio en tn·m/m; fs: tensión por flexión en kgf/cm².",
            source(service) + f" As={service['area']:.6g} cm²/m; s={steel.spacing_m:.3f} m.",
            "Sin tracción por flexión en Servicio I; la ecuación de separación por fisuración no gobierna.",
            "Se mantienen las comprobaciones de acero mínimo y separación para temperatura y distribución.", REF_CRACK)
    yield from _temperature_and_development_steps(steel, audit, flexure)


def _general_shear_step(shear, audit):
    yield AuditStep("Cortante y procedimiento general beta",
        "dv = max(0.9*d, 0.72*h); Mv = max(abs(M), abs(V)*dv/100); eps_s = max(0,1000*(Mv/(dv/100)+abs(V)+0.5*N)/(Es*As)); "
        "beta = 4.8*51/((1+750*eps_s)*(39+sxe)); Vr = phi_v*0.265*beta*sqrt(fc)*100*dv/1000",
        "N: tn/m, positivo en traccion; dv: cm; Mv: Tn.m; V: Tn; sx=dv/2.54 pulgadas; sxe=min(80,max(12,sx*1.38/(0.75+0.63))); Es=2000000 kgf/cm2.",
        source(shear) + f" d={shear['effective']:.6g}; dv={shear['shear_depth']:.6g}; As={shear['area']:.6g}; "
        f"Mv={shear['shear_moment_used']:.6g}; eps_s={shear['shear_strain']:.6g}; sx={shear['spacing_x_in']:.6g}; "
        f"sxe={shear['spacing_xe_in']:.6g}; beta={shear['beta']:.6g}; phi_v={audit['shear_phi']:.6g}; fc={audit['concrete']:.6g}.",
        f"Vr={shear['shear_capacity']:.6g} Tn/m; abs(V)/Vr={shear['shear_ratio']:.6g}.",
        status(shear["shear_ratio"]),
        "Manual de Puentes MTC 2018, Arts. 2.9.1.5.6.2.9, 2.9.1.5.6.3.3 y 2.9.1.5.6.3.4.2; "
        "AASHTO LRFD 5.8.2.9, 5.8.3.3 y 5.8.3.4.2.")


def _temperature_and_development_steps(steel, audit, flexure):
    temperature = audit["temperature"]
    yield AuditStep("Temperatura y acero transversal por cara",
        "As0 = 7.65*b*h*100/(2*(b+h)*fy); AsT = max(2.33,min(12.70,As0)); As_prov = Ab/s",
        "b,h: dimensiones del panel cm; fy: kgf/cm2; As: cm2/m por cara.",
        f"b={temperature['b_cm']:.6g}; h={temperature['h_cm']:.6g}; fy={audit['yield_strength']:.6g}; "
        f"As0={temperature['raw_as_cm2_m']:.6g}; AsT={steel.temperature_cm2_m:.6g}; "
        f"As principal={steel.area_per_face_cm2_m:.6g}; As transversal={audit['transverse_area']:.6g}.",
        f"AsT/As principal={steel.minimum_utilization:.6g}; AsT/As transversal={steel.transverse_utilization:.6g}; "
        f"separacion maxima de temperatura={temperature['maximum_spacing_m']:.6g} m.",
        status(max(steel.minimum_utilization, steel.transverse_utilization)), REF_TEMPERATURE)
    yield AuditStep("Desarrollo recto y gancho",
        "ldb = 2.4*db*fy/sqrt(fc); ld = max(ldb*producto_factores,30.48); "
        "ldh = max(0.076*db_cm*fy_kg/sqrt(fc_kg)*0.80,8*db_cm,15.24); extension = 16*db_cm",
        "En ldb usar db en pulgadas y tensiones en ksi, luego convertir a cm. ld, ldh y extension se expresan en cm.",
        f"db={flexure['diameter']:.6g} cm; fc={audit['concrete']:.6g} kgf/cm2; fy={audit['yield_strength']:.6g} kgf/cm2; "
        f"ldb={audit['basic_anchor_cm']:.6g} cm; factores ubicacion, revestimiento, ligero, confinamiento="
        f"{audit['anchor_factors']}; producto={prod(audit['anchor_factors']):.6g}; factor exceso=1.00.",
        f"ld={steel.required_straight_anchor_cm:.6g}; ldh={steel.required_hook_anchor_cm:.6g}; "
        f"extension={steel.hook_extension_cm:.6g}; disponible={number(steel.available_anchor_cm)} cm.",
        f"{steel.anchor_status}. Origen: {steel.anchor_source}. {steel.anchor_geometry_note} "
        "Se compara la longitud disponible por separado con ld recto y ld gancho. "
        "El gancho calculado no acredita acomodo; los empalmes requieren detalle.", REF_DEVELOPMENT)
