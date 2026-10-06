"""General load criteria and their actual application to the connected FRAME."""

from dataclasses import replace

from bridge_design.domain.abutment import mononobe_okabe_active_coefficient
from bridge_design.domain.connected_geometry import global_x
from bridge_design.domain.connected_2_inputs import is_connected_2
from bridge_design.reporting.deck_docx import _add_native_equation, _body, _table
from bridge_design.reporting.connected_report_details import mathematical_symbols


def formulas(document, *expressions):
    for expression in expressions:
        _add_native_equation(document, mathematical_symbols(expression))


def reference(document, articles):
    _body(document, f"Referencia normativa: Manual de Puentes MTC 2018, {articles}.")


def write_load_criteria(document, result):
    data = result.inputs
    g = data.left.geometry
    _body(document, "Las acciones se definen sin ponderar para una franja transversal b=1 m. "
          "Las intensidades distribuidas están en tn/m, las fuerzas de la franja en tn y los momentos en tn·m. "
          "Los factores y signos del punto 5 se aplican al ensamblar cada caso simultáneo. "
          "El origen de cotas z es la cara superior de la cimentación; x crece de izquierda a derecha y z hacia arriba.")

    document.add_heading("4.1. Peso propio y carga vertical del relleno", level=2)
    formulas(document, "w_DC(x) = gamma_c*b*t(x)", "w_EV(x) = gamma_s*b*h_s(x)")
    weight_note = ("γ_c y γ_s son los pesos unitarios del concreto y del relleno; t(x) es el espesor y "
          "h_s(x) la altura efectiva de suelo sobre el concreto. El peso propio actúa verticalmente hacia abajo "
          "en pantallas, parapetos, cajuelas, zapatas, transiciones y losa central. "
          "Los espesores variables se integran por elemento. La cajuela conserva la excentricidad de su centroide "
          "respecto del eje FRAME mediante un momento equivalente.")
    soil_note = ("EV se aplica en talones y en la zona posterior de transición de cajuela según el perfil real "
          "del relleno. Si el suelo frontal supera la cara superior de zapata, también carga la puntera y su "
          "transición. La reducción local de EV responde al volumen ocupado por el concreto, no a un cambio "
          "del peso unitario. La losa central y sus transiciones tienen DC; la geometría ingresada no define "
          "relleno ni sobrecarga vertical de suelo sobre ellas. El relleno no incluye nuevamente el volumen de cajuela.")
    if is_connected_2(data):
        weight_note = ("γ_c y γ_s son los pesos unitarios del concreto y del relleno; t(x) es el espesor "
                       "y h_s(x) la altura efectiva de suelo. DC incluye la base uniforme completa, "
                       "las pantallas trapezoidales y los parapetos. Se integra el espesor variable de "
                       "la pantalla y se conserva la excentricidad de su peso respecto al eje FRAME.")
        soil_note = ("EV actúa únicamente sobre los talones exteriores, con relleno hasta la coronación "
                     "del parapeto. El tramo interior de la zapata combinada queda sin relleno ni sobrecarga vertical de suelo. "
                     "No existen punteras interiores ni transiciones de espesor en la base.")
    _body(document, weight_note)
    _body(document, soil_note)

    document.add_heading("4.2. Sobrecarga del relleno", level=2)
    formulas(document, "q_LS = gamma_s*h_eq + q_peatonal", "w_LS = b*q_LS", "p_LS = Ka*q_LS")
    _body(document, "h_eq es la altura equivalente de sobrecarga vehicular y q_peatonal la sobrecarga adicional "
          "del relleno. La acción vertical es uniforme sobre el talón exterior, detrás del retiro t2. "
          "La acción horizontal es uniforme sobre la cara real del estribo y se completa con la transferencia "
          "al plano virtual descrita en 4.3. Las dos componentes conservan los factores independientes del punto 5. "
          "PL es una reacción del tablero; q_peatonal pertenece al relleno y se considera por separado.")
    sides = (("Izquierdo", data.left, result.earth_parameters[0]),
             ("Derecho", data.right, result.earth_parameters[1]))
    common = data.left.soil == data.right.soil
    for label, side, p in sides[:1] if common else sides:
        q = side.materials.soil_unit_weight_kg_m3 / 1000 * p.live_surcharge_height_m + side.soil.pedestrian_surcharge_tn_m2
        origin = "altura equivalente adoptada" if side.soil.vehicular_surcharge_height_m is not None else "tabla de altura equivalente según H"
        _body(document, f"{'Ambos estribos' if common else label}: h_eq={p.live_surcharge_height_m:.3f} m "
              f"({origin}); q_peatonal={side.soil.pedestrian_surcharge_tn_m2:.3f} tn/m²; q_LS={q:.3f} tn/m².")

    document.add_heading("4.3. Empuje estático y transferencia al talón", level=2)
    _body(document, "Se adopta el estado activo de Coulomb. φ es la fricción interna, δ la fricción muro–suelo, "
          "β la pendiente del relleno y θ la inclinación de la cara desde la horizontal. El plano virtual exterior "
          "del talón usa θ=90° y δ=0; la cara real utiliza sus parámetros adoptados. Para calcular Ka se emplea:")
    formulas(document,
             "C = sqrt((sin(phi+delta)*sin(phi-beta))/(sin(theta-delta)*sin(theta+beta)))",
             "Ka = sin(theta+phi)^2/(sin(theta)^2*sin(theta-delta)*(1+C)^2)",
             "p_EH(z) = Ka*gamma_s*(H-z)", "P_EH = Ka*gamma_s*b*H^2/2",
             "P_LS = Ka*q_LS*b*H")
    _body(document, f"El plano virtual utiliza H={g.retained_height_m:.3f} m desde el fondo de zapata hasta "
          f"la superficie del relleno. La cara real sobre la zapata tiene altura H_c={g.stem_height_above_footing_m:.3f} m. "
          "En p_EH, z se mide desde la base del plano considerado. EH es triangular, con resultante a H/3; "
          "LS horizontal es uniforme, con resultante a H/2. Sobre la cara real el empuje se descompone "
          "según su ángulo y se aplica a los elementos de pantalla, transición, cajuela y parapeto.")
    for label, side, p in sides[:1] if common else sides:
        s = side.soil
        _body(document, f"{'Parámetros comunes' if common else label}: φ={s.friction_angle_deg:.2f}°; "
              f"δ={s.wall_soil_friction_deg:.2f}°; β={s.backfill_slope_deg:.2f}°; θ={s.wall_backface_angle_deg:.2f}°; "
              f"Ka virtual={p.ka:.4f}; Ka cara real={p.stem_ka:.4f}.")
    _body(document, "La diferencia entre las fuerzas y el momento del plano virtual y los aplicados sobre "
          "la cara real se transfiere a los nudos del talón, ponderada por sus áreas tributarias. "
          "Así se conserva el equilibrio del cuerpo estribo–relleno. Esta transferencia completa el mismo "
          "empuje; no representa una segunda carga externa ni resistencia por fricción bajo la cimentación.")
    formulas(document, "Delta_F = F_virtual - F_cara", "Delta_M = M_virtual - M_cara")
    reference(document, "Arts. 2.4.4.1.5.1 y 2.4.4.1.5.3")

    document.add_heading("4.4. Empuje e inercias sísmicas", level=2)
    s = data.left.soil
    formulas(document, "As = PGA*Fpga", "kh = 0.5*As", "kv = 0",
             "psi = atan(kh_local/(1-kv))", "P_AE = KAE*gamma_s*b*H^2/2")
    _body(document, f"Se adoptan PGA={s.pga:.3f} y Fpga={s.fpga:.3f}. "
          f"Se obtiene As={s.pga*s.fpga:.3f} y se utiliza kh={0.5*s.pga*s.fpga:.3f} "
          "para relleno y concreto, con kh=0.5·As y kv=0.")
    _body(document, "KAE se obtiene por Mononobe–Okabe con kv=0. El sentido global EQ se transforma al sentido "
          "relativo a cada relleno: kh_local=sentido_global·sentido_estribo·kh, con sentido_estribo=+1 a la "
          "izquierda y −1 a la derecha. En la expresión siguiente α=90°−θ es la inclinación desde la vertical; "
          "ψ es el ángulo sísmico. La evaluación virtual anula δ y conserva la inclinación registrada; "
          "la cara real conserva δ. Se utilizan las siguientes expresiones:")
    formulas(document,
             "C_AE = sqrt((sin(phi+delta)*sin(phi-psi-beta))/(cos(delta+alpha+psi)*cos(beta-alpha)))",
             "KAE = cos(phi-psi-alpha)^2/(cos(psi)*cos(alpha)^2*cos(delta+alpha+psi)*(1+C_AE)^2)")
    rows = []
    for index, (label, side, p) in enumerate(sides):
        for real in (False, True):
            actual = side if real else replace(side, soil=replace(side.soil, wall_soil_friction_deg=0.0))
            coefficients = [mononobe_okabe_active_coefficient(actual, horizontal_direction=sign*(1 if index == 0 else -1))[0]
                            for sign in (-1, 1)]
            rows.append((f"{label} / {'cara real' if real else 'plano virtual'}",
                         f"{p.stem_ka if real else p.ka:.4f}", *(f"{k:.4f}" for k in coefficients)))
    _table(document, ("Plano considerado", "Ka", "KAE EQ−", "KAE EQ+"), rows, widths=(76, 26, 29, 29))
    _body(document, "Para la alternativa A, si PAE≥PEH, se aplica el empuje estático triangular más un incremento "
          "uniforme Δp=(PAE−PEH)/(b·H), situado a H/2; si PAE<PEH, se aplica un triángulo con resultante PAE "
          "a H/3. Para B se conserva EH triangular si domina PEH; cuando domina 0.5·PAE, esa resultante "
          "se distribuye uniformemente a H/2. Cada perfil se aplica a la cara real y se completa por "
          "transferencia al talón, como en 4.3. Estas distribuciones son las hipótesis de aplicación del modelo.")
    formulas(document, "PIR = kh*(W_concreto + W_relleno)", "PEQ = As*(PDC + PDW)",
             "P_seis_A = PAE + 0.5*PIR", "P_seis_B = max(0.5*PAE, PEH) + PIR")
    _body(document, "PIR incluye el concreto de toda la estructura y el suelo sobre las zapatas. Se distribuye "
          "sobre los elementos conservando las alturas de los centroides de masa mediante fuerzas y momentos "
          "equivalentes. PEQ usa las reacciones permanentes del tablero por apoyo, con el coeficiente As "
          "sin reducción de 0.5, mediante una representación seudoestática de la transmisión del tablero. "
          f"Su cota adoptada es z_EQ=H_c−h_parapeto/2={g.stem_height_above_footing_m-g.seat_block_height_m/2:.3f} m "
          "y se traslada al nudo de cajuela con su momento equivalente.")
    _body(document, "En un mismo caso, PIR y PEQ conservan un único sentido global en ambos estribos. "
          "Los empujes mantienen su dirección física desde el relleno y cambian de magnitud según el sentido relativo. "
          "A y B son alternativas independientes: no se suman entre sí ni se añade EH nuevamente a PAE. "
          "Los factores de sobrecarga y carga viva se aplican por separado según el punto 5.")
    reference(document, "Arts. 2.8.1.1.14.1, 2.8.1.1.14.2 y 2.8.1.1.14.3; Apéndice A.11.3.1")

    document.add_heading("4.5. Reacciones verticales del tablero", level=2)
    formulas(document, "V_u = gamma_DC*PDC + gamma_DW*PDW + gamma_LL*(PLL_IM + PPL)",
             "M_V = (x_apoyo-x_nudo)*Fz")
    _body(document, "DC y DW corresponden a las reacciones permanentes; LL+IM y PL a las reacciones vehicular "
          "y peatonal del tablero. Se consideran por metro transversal y por apoyo, antes de ponderar. "
          "La tabla del punto 5 presenta el par izquierdo–derecho de una misma condición de carga.")
    for index, (label, side, _p) in enumerate(sides):
        geometry = side.geometry
        _body(document, f"{label}: apoyo en x={global_x(data,index,geometry.superstructure_load_x_m):.3f} m, "
              f"z_apoyo={geometry.stem_height_above_footing_m-geometry.seat_block_height_m:.3f} m. "
              "La fuerza vertical actúa hacia abajo y se traslada al eje FRAME con su excentricidad horizontal.")
    _body(document, "La cajuela transmite las acciones del tablero al estribo.")

    document.add_heading("4.6. Frenado y traslado de la fuerza al modelo", level=2)
    formulas(document, "BR_u = gamma_BR*BR", "z_BR = z_ref + h_adicional",
             "M_BR = -Fx_BR*(z_BR-z_nudo)")
    _body(document, "BR es la reacción horizontal de frenado adoptada por apoyo y por metro transversal. "
          "Se pondera con el factor de la combinación correspondiente.")
    z_ref = g.stem_height_above_footing_m
    seat = z_ref - g.seat_block_height_m
    z_br = z_ref + g.bridge_seat_to_bearing_height_m
    _body(document, f"La referencia geométrica actualmente adoptada es z_ref=H_c={z_ref:.3f} m, "
          f"superficie superior del relleno, con h_adicional={g.bridge_seat_to_bearing_height_m:.3f} m. "
          f"Resultan z_BR={z_br:.3f} m, z_nudo={seat:.3f} m y brazo={z_br-seat:.3f} m.")
    _body(document, "Se aplica Fx_BR en el nudo de cajuela y el momento del traslado vertical, con ambos signos "
          "globales de BR. La fuerza y ese momento representan una única acción llevada desde su altura "
          "física al nudo; no son cargas independientes. Los signos siguen M=x·Fz−z·Fx.")
    reference(document, "Art. 2.4.3.5")
