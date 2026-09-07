"""Continuous piecewise-quadratic moments and their exact envelopes."""

from bisect import bisect_left
from dataclasses import dataclass
from math import copysign, sqrt


@dataclass(frozen=True)
class MomentCurve:
    # Each interval uses a*x*x + b*x + c in global coordinates.
    ends: tuple[float, ...]
    coefficients: tuple[tuple[float, float, float], ...]
    start: float = 0.0

    def value(self, x: float) -> float:
        index = min(bisect_left(self.ends, x), len(self.ends) - 1)
        a, b, c = self.coefficients[index]
        return (a * x + b) * x + c

    def samples(self, stations):
        xs = {self.start, *self.ends, *stations}
        left = self.start
        for right, (a, b, _) in zip(self.ends, self.coefficients):
            if a != 0.0 and left < -b / (2.0 * a) < right:
                xs.add(-b / (2.0 * a))
            left = right
        return tuple((x, self.value(x)) for x in sorted(xs))


def load_moment_curve(width, segments, points, reactions):
    ends = sorted({0.0, width, *(x for x, _ in reactions),
                   *(p.position_m for p in points),
                   *(s.start_m for s in segments), *(s.end_m for s in segments)})
    coefficients = []
    for left, right in zip(ends, ends[1:]):
        middle = (left + right) / 2.0
        a = b = c = 0.0
        for x, force in (*reactions, *((p.position_m, -p.p_tn) for p in points)):
            if x < middle:
                b += force
                c -= force * x
        for segment in segments:
            # Macaulay terms for the start/end of a uniform load.
            for x, q in ((segment.start_m, -segment.q_tn_m),
                         (segment.end_m, segment.q_tn_m)):
                if x < middle:
                    a += q / 2.0
                    b -= q * x
                    c += q * x * x / 2.0
        coefficients.append((a, b, c))
    return MomentCurve(tuple(ends[1:]), tuple(coefficients))


def _crossings(a, b, c, left, right):
    # Solve in a normalized local coordinate to avoid cancellation near x=0.
    length = right - left
    aa = a * length * length
    bb = (2.0 * a * left + b) * length
    cc = (a * left + b) * left + c
    scale = max(abs(aa), abs(bb), abs(cc), 1e-30)
    if abs(aa) <= 1e-13 * scale:
        roots = () if abs(bb) <= 1e-13 * scale else (-cc / bb,)
    else:
        discriminant = bb * bb - 4.0 * aa * cc
        if discriminant < 0.0:
            roots = ()
        else:
            q = -0.5 * (bb + copysign(sqrt(discriminant), bb))
            roots = (-bb / (2.0 * aa),) if q == 0.0 else (q / aa, cc / q)
    return sorted({left + root * length for root in roots if 0.0 < root < 1.0})


def combine_moment_curves(first, second, operation):
    """Add independent responses or retain their pointwise minimum/maximum."""
    if operation not in ("sum", "min", "max"):
        raise ValueError("Operacion de curva desconocida.")
    if first.start != second.start or first.ends[-1] != second.ends[-1]:
        raise ValueError("Las curvas deben cubrir el mismo tablero.")
    i = j = 0
    left = first.start
    ends, coefficients = [], []
    while i < len(first.ends) and j < len(second.ends):
        right = min(first.ends[i], second.ends[j])
        p, q = first.coefficients[i], second.coefficients[j]
        breaks = [] if operation == "sum" else _crossings(
            *(p[k] - q[k] for k in range(3)), left, right
        )
        for end in (*breaks, right):
            if end <= left:
                continue
            if operation == "sum":
                chosen = tuple(p[k] + q[k] for k in range(3))
            else:
                x = (left + end) / 2.0
                difference = ((p[0] - q[0]) * x + p[1] - q[1]) * x + p[2] - q[2]
                chosen = p if (difference >= 0.0) == (operation == "max") else q
            if coefficients and coefficients[-1] == chosen:
                ends[-1] = end
            else:
                ends.append(end)
                coefficients.append(chosen)
            left = end
        if first.ends[i] <= right:
            i += 1
        if second.ends[j] <= right:
            j += 1
    return MomentCurve(tuple(ends), tuple(coefficients), first.start)


def reduce_moment_curves(curves, operation):
    curves = list(curves)
    if not curves:
        raise ValueError("No hay curvas de momento.")
    # Balanced merging limits growth of intermediate envelopes.
    while len(curves) > 1:
        curves = [combine_moment_curves(curves[i], curves[i + 1], operation)
                  if i + 1 < len(curves) else curves[i]
                  for i in range(0, len(curves), 2)]
    return curves[0]
