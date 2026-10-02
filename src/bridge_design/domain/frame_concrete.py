"""Two-face RC strip checks by strain compatibility, MTC/AASHTO 5.7.2 and 5.7.4.

Axial compression is positive in this module. Moments are about the centroid.
The maximum compression is conservatively limited to 0.80 phi P0.
"""

from functools import lru_cache

from bridge_design.domain.concrete_flexure import mtc_beta1, mtc_flexural_resistance_factor


@lru_cache(maxsize=4096)
def interaction_curve(depth_cm, cover_axis_cm, area_per_face, concrete_strength, steel_yield, phi_limit=0.90):
    if depth_cm <= 2 * cover_axis_cm or area_per_face <= 0:
        raise ValueError("Seccion insuficiente para dos caras de acero y sus recubrimientos.")
    if 2 * area_per_face >= 100 * depth_cm:
        raise ValueError("Area de acero incompatible con la seccion.")
    beta = mtc_beta1(concrete_strength)
    depths = (cover_axis_cm, depth_cm - cover_axis_cm)
    maximum = 0.80 * min(phi_limit, 0.75) * (
        0.85 * concrete_strength * (100 * depth_cm - 2 * area_per_face)
        + 2 * area_per_face * steel_yield) / 1000
    rows = [(-min(phi_limit, 0.90) * 2 * area_per_face * steel_yield / 1000, 0.0)]
    for index in range(241):
        neutral = depth_cm * 10**(-5 + index * 8 / 240)
        block = min(beta * neutral, depth_cm)
        concrete = 0.85 * concrete_strength * 100 * block
        axial = concrete
        moment = concrete * (depth_cm / 2 - block / 2)
        strains = [0.003 * (neutral - position) / neutral for position in depths]
        for position, strain in zip(depths, strains):
            stress = min(steel_yield, max(-steel_yield, 2_000_000 * strain))
            if position <= block:
                stress -= 0.85 * concrete_strength
            force = stress * area_per_face
            axial += force
            moment += force * (depth_cm / 2 - position)
        phi = min(phi_limit, mtc_flexural_resistance_factor(max(0.0, -min(strains))))
        point = (phi * axial / 1000, max(0.0, phi * moment / 100000))
        if point[0] <= maximum:
            rows.append(point)
        elif rows[-1][0] < maximum:
            previous = rows[-1]
            ratio = (maximum - previous[0]) / (point[0] - previous[0])
            rows.append((maximum, previous[1] + ratio * (point[1] - previous[1])))
    rows.append((maximum, 0.0))
    return tuple(rows)


def moment_capacity(curve, compression):
    if compression < curve[0][0] - 1e-8 or compression > curve[-1][0] + 1e-8:
        return -1.0
    capacity = 0.0
    for first, last in zip(curve, curve[1:]):
        if min(first[0], last[0]) - 1e-9 <= compression <= max(first[0], last[0]) + 1e-9:
            if abs(last[0] - first[0]) < 1e-10:
                capacity = max(capacity, first[1], last[1])
            else:
                ratio = (compression - first[0]) / (last[0] - first[0])
                capacity = max(capacity, first[1] + ratio * (last[1] - first[1]))
    return capacity


@lru_cache(maxsize=16384)
def service_tension_stress(depth_cm, cover_axis_cm, area_per_face, modulus, compression, moment):
    """Cracked elastic section: concrete tension zero, two elastic steel layers."""
    half = depth_cm / 2
    positions = (half - cover_axis_cm, -half + cover_axis_cm)
    strain = compression * 1000 / (modulus * 100 * depth_cm + 4_000_000 * area_per_face)
    curvature = moment * 100000 / (modulus * 100 * depth_cm**3 / 12
                                   + 4_000_000 * area_per_face * positions[0]**2)
    target_force, target_moment = compression * 1000, moment * 100000
    for _ in range(60):
        lower, upper = -half, half
        if abs(curvature) < 1e-25:
            if strain <= 0:
                upper = lower
        elif curvature > 0:
            lower = min(half, max(-half, -strain / curvature))
        else:
            upper = max(-half, min(half, -strain / curvature))
        integrals = [100 * (upper**power - lower**power) / power for power in (1, 2, 3)]
        tangent_00 = modulus * integrals[0]
        tangent_01 = modulus * integrals[1]
        tangent_11 = modulus * integrals[2]
        force = modulus * (strain * integrals[0] + curvature * integrals[1])
        bending = modulus * (strain * integrals[1] + curvature * integrals[2])
        for position in positions:
            layer_strain = strain + curvature * position
            stiffness = area_per_face * (2_000_000 - (modulus if layer_strain > 0 else 0.0))
            force += stiffness * layer_strain
            bending += stiffness * layer_strain * position
            tangent_00 += stiffness
            tangent_01 += stiffness * position
            tangent_11 += stiffness * position**2
        residual_force = target_force - force
        residual_moment = target_moment - bending
        if max(abs(residual_force), abs(residual_moment) / depth_cm) < 1e-7 * max(
            1.0, abs(target_force), abs(target_moment) / depth_cm
        ):
            return tuple(max(0.0, -2_000_000 * (strain + curvature * position)) for position in positions)
        determinant = tangent_00 * tangent_11 - tangent_01**2
        if determinant <= 0:
            raise ValueError("Seccion de servicio singular.")
        strain += (residual_force * tangent_11 - residual_moment * tangent_01) / determinant
        curvature += (residual_moment * tangent_00 - residual_force * tangent_01) / determinant
    raise ValueError("No converge la seccion fisurada de servicio.")
