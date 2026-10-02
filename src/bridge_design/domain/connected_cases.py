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
        braking_directions = (-1, 1) if paired.left.braking_tn_m + paired.right.braking_tn_m > 0 else (1,)
        combinations = []
        for left_index, right_index, slab_index, direction in product((0, 1), (0, 1), (0, 1), braking_directions):
            label = f"Resistencia I {left_index + 1}{right_index + 1}{slab_index + 1} BR{direction:+d}"
            combinations.append((label, factors[left_index], factors[right_index],
                                 factors[slab_index].dc, direction, "EH", 0))
        for direction in braking_directions:
            combinations.append((f"Servicio I BR{direction:+d}", factors[3], factors[3], 1.0, direction, "EH", 0))
        for direction, kind in product((-1, 1), ("A", "B")):
            combinations.append((f"Evento Extremo I {kind} EQ{direction:+d}", factors[2], factors[2],
                                 1.0, direction, kind, direction))
        for label, left_factors, right_factors, slab_dc, braking, kind, seismic in combinations:
            builder = LoadBuilder(mesh.frame)
            builder.add(permanent["DCs"], slab_dc)
            inertia_factor = 0.5 if kind == "A" else 1.0
            builder.add(permanent["PIRs"], seismic * inertia_factor)
            for side_index, side_factors in enumerate((left_factors, right_factors)):
                owner = str(side_index)
                factor = side_factors
                loads = (paired.left, paired.right)[side_index]
                live_scale = (paired.left_surcharge, paired.right_surcharge)[side_index]
                if factor.limit_state == "extreme" and live_scale == 0 and all(
                    value == 0 for value in (loads.pll_im_tn_m, loads.ppl_tn_m, loads.braking_tn_m)
                ):
                    factor = replace(factor, ll=0.0, br=0.0, ls_vertical=0.0, ls_horizontal=0.0)
                for name, multiplier in (("DC", factor.dc), ("EV", factor.ev)):
                    builder.add(permanent[name + owner], multiplier)
                for name, multiplier in (("BDC", factor.dc), ("DW", factor.dw), ("LL", factor.ll),
                                         ("BR", factor.br * braking), ("PEQ", seismic)):
                    builder.add(bridge[name + owner], multiplier)
                builder.add(permanent["PIR" + owner], seismic * inertia_factor)
                builder.add(surcharge[side_index], factor.ls_vertical * live_scale)
                builder.add(earth[(side_index, "LS", 1)], factor.ls_horizontal * live_scale)
                builder.add(earth[(side_index, kind, seismic or 1)], factor.eq if seismic else factor.eh)
            yield builder.case(f"{paired.name} / {label}", left_factors.limit_state)
