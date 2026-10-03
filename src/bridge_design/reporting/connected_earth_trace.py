"""Trace both earth-pressure faces and both global earthquake directions."""

from dataclasses import replace
from types import SimpleNamespace

from bridge_design.domain.abutment import mononobe_okabe_active_coefficient
from bridge_design.reporting.abutment_docx import REF_EARTH
from bridge_design.reporting.abutment_docx_detail import coulomb_ka_trace, surcharge_height_trace
from bridge_design.reporting.connected_audit import AuditStep


def earth_steps(result):
    for side_index, side in enumerate((result.inputs.left, result.inputs.right)):
        label = "Izquierda" if side_index == 0 else "Derecha"
        direction = 1 if side_index == 0 else -1
        context = SimpleNamespace(inputs=side, pressures=result.earth_parameters[side_index])
        yield AuditStep(f"{label}: altura equivalente de sobrecarga", *surcharge_height_trace(context), REF_EARTH)
        for face in (False, True):
            plane = "cara real" if face else "plano virtual del talon"
            yield AuditStep(f"{label}: Coulomb, {plane}", *coulomb_ka_trace(context, stem_face=face), REF_EARTH)
            actual = side if face else replace(side, soil=replace(side.soil, wall_soil_friction_deg=0.0))
            for seismic in (-1, 1):
                coefficient, angle = mononobe_okabe_active_coefficient(actual, horizontal_direction=seismic * direction)
                soil = actual.soil
                horizontal = seismic * direction * 0.5 * soil.pga * soil.fpga
                yield AuditStep(f"{label}: Mononobe Okabe, {plane}, EQ{seismic:+d}",
                    "kh=sentido_local*0.5*PGA*Fpga; psi=atan(kh); "
                    "kAE=cos(phi-psi-theta)^2/(cos(psi)*cos(theta)^2*cos(delta+theta+psi)*"
                    "(1+sqrt(sin(phi+delta)*sin(phi-psi-beta)/(cos(delta+theta+psi)*cos(beta-theta))))^2)",
                    "phi: friccion; delta: interfaz; beta: pendiente; theta: inclinacion desde vertical; kv=0; angulos en grados.",
                    f"PGA={soil.pga:.6g}; Fpga={soil.fpga:.6g}; sentido_local={seismic*direction:+d}; kh={horizontal:.6g}; "
                    f"psi={angle:.6g}; phi={soil.friction_angle_deg:.6g}; delta={soil.wall_soil_friction_deg:.6g}; "
                    f"beta={soil.backfill_slope_deg:.6g}; theta={90-soil.wall_backface_angle_deg:.6g}.",
                    f"kAE={coefficient:.8g}.",
                    "Empuje activo. Se ensambla con su sentido relativo al relleno y no se duplica con las inercias PIR.", REF_EARTH)
