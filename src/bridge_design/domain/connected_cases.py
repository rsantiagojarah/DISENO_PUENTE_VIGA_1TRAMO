"""Simultaneous two-sided LRFD cases; each is solved with its own contact set."""

from dataclasses import replace
from itertools import product

from bridge_design.domain.abutment import abutment_load_factors, pure_wall_load_inputs
from bridge_design.domain.connected_earth import earth_builder, surcharge_weight
from bridge_design.domain.connected_inputs import PairedBridgeCase
from bridge_design.domain.connected_loads import LoadBuilder, bridge_builders, gravity_builders


def paired_cases(data):
    cases = list(data.cases or (PairedBridgeCase("Par simultaneo ingresado", data.left.loads, data.right.loads),))
    if data.include_without_bridge:
        zero = pure_wall_load_inputs()
        cases.append(PairedBridgeCase("Sin tablero", zero, zero, bridge_present=False))
    return tuple(cases)


def connected_load_cases(data, mesh):
    permanent = gravity_builders(data, mesh)
    earth = {(side, kind, direction): earth_builder(data, mesh, side, kind, direction)
             for side in (0, 1) for kind in ("EH", "LS", "A", "B")
             for direction in ((-1, 1) if kind in ("A", "B") else (1,))}
    surcharge = [surcharge_weight(data, mesh, side) for side in (0, 1)]
    factors = abutment_load_factors(data.left.gamma_eq)
    for paired in paired_cases(data):
        bridge = bridge_builders(data, mesh, paired)
        resultants = {}
        has_braking = paired.left.braking_tn_m + paired.right.braking_tn_m > 0
        braking_directions = (-1, 1) if has_braking else (1,)
        combinations = []
        for global_factors, direction in product(factors[:2], braking_directions):
            braking_label = f" BR{direction:+d}" if has_braking else ""
            label = global_factors.name + braking_label
            combinations.append((label, global_factors, direction, "EH", 0))
        for direction in braking_directions:
            braking_label = f" BR{direction:+d}" if has_braking else ""
            combinations.append((f"Servicio I{braking_label}", factors[3], direction, "EH", 0))
        for direction, kind in product((-1, 1), ("A", "B")):
            combinations.append((f"Evento Extremo I {kind} EQ{direction:+d}", factors[2], direction, kind, direction))
        for label, global_factors, braking, kind, seismic in combinations:
            builder = LoadBuilder(mesh.frame)
            trace = []

            def add(part, factor, name):
                builder.add(part, factor)
                if part not in resultants:
                    vector = part.vector()
                    resultants[part] = (
                        sum(vector[0::3]), sum(vector[1::3]),
                        sum(node.x * vector[3 * index + 1] - node.y * vector[3 * index]
                            + vector[3 * index + 2] for index, node in enumerate(mesh.frame.nodes)))
                trace.append((name, factor, *resultants[part]))

            add(permanent["DCs"], global_factors.dc, "Losa y transiciones / DC")
            inertia_factor = 0.5 if kind == "A" else 1.0
            add(permanent["PIRs"], seismic * inertia_factor, "Losa y transiciones / PIR")
            for side_index in (0, 1):
                owner = str(side_index)
                side_name = "Izquierda" if side_index == 0 else "Derecha"
                factor = global_factors
                loads = (paired.left, paired.right)[side_index]
                live_scale = (paired.left_surcharge, paired.right_surcharge)[side_index]
                if factor.limit_state == "extreme" and live_scale == 0 and all(
                    value == 0 for value in (loads.pll_im_tn_m, loads.ppl_tn_m, loads.braking_tn_m)
                ):
                    factor = replace(factor, ll=0.0, br=0.0, ls_vertical=0.0, ls_horizontal=0.0)
                for name, multiplier in (("DC", factor.dc), ("EV", factor.ev)):
                    add(permanent[name + owner], multiplier, f"{side_name} / {name}")
                for name, multiplier in (("BDC", factor.dc), ("DW", factor.dw), ("LL", factor.ll),
                                         ("BR", factor.br * braking), ("PEQ", seismic)):
                    add(bridge[name + owner], multiplier, f"{side_name} / {name}")
                add(permanent["PIR" + owner], seismic * inertia_factor, f"{side_name} / PIR")
                add(surcharge[side_index], factor.ls_vertical * live_scale, f"{side_name} / LS vertical")
                add(earth[(side_index, "LS", 1)], factor.ls_horizontal * live_scale, f"{side_name} / LS empuje")
                add(earth[(side_index, kind, seismic or 1)], factor.eq if seismic else factor.eh,
                    f"{side_name} / Empuje {kind} EQ{seismic:+d}")
            yield replace(builder.case(f"{paired.name} / {label}", global_factors.limit_state), load_trace=tuple(trace))
