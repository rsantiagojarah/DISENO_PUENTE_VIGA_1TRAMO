"""Load combination envelopes for bridge load effects."""

from dataclasses import dataclass
from typing import Literal

from bridge_design.domain.transverse_slab import (
    LoadCaseAnalysis,
    TransverseSlabAnalysisResult,
)

CombinationTarget = Literal["max", "min"]


@dataclass(frozen=True)
class LoadFactor:
    """Load factor with optional minimum value for permanent effects."""

    maximum: float
    minimum: float | None = None
    omit_when_favorable: bool = False

    def for_effect(self, effect: float, target: CombinationTarget) -> float:
        """Return the factor that makes the requested envelope more severe."""
        if self.omit_when_favorable:
            if target == "max" and effect < 0.0:
                return 0.0
            if target == "min" and effect > 0.0:
                return 0.0

        if self.minimum is None:
            return self.maximum
        if target == "max":
            return self.maximum if effect >= 0.0 else self.minimum
        return self.maximum if effect <= 0.0 else self.minimum


@dataclass(frozen=True)
class LoadCombination:
    """Regulatory load combination definition."""

    name: str
    limit_state: str
    dc: LoadFactor
    dw: LoadFactor
    pl: LoadFactor
    ll_im: LoadFactor


@dataclass(frozen=True)
class CombinedMomentResult:
    """Critical combined bending moment with source component moments."""

    combination_name: str
    limit_state: str
    direction: str
    position_m: float
    dc_moment_tn_m: float
    dc_factor: float
    dw_moment_tn_m: float
    dw_factor: float
    pl_moment_tn_m: float
    pl_factor: float
    ll_im_moment_tn_m: float
    ll_im_factor: float
    combined_moment_tn_m: float

    @property
    def dc_factored_tn_m(self) -> float:
        """Return factored DC contribution."""
        return self.dc_factor * self.dc_moment_tn_m

    @property
    def dw_factored_tn_m(self) -> float:
        """Return factored DW contribution."""
        return self.dw_factor * self.dw_moment_tn_m

    @property
    def pl_factored_tn_m(self) -> float:
        """Return factored PL contribution."""
        return self.pl_factor * self.pl_moment_tn_m

    @property
    def ll_im_factored_tn_m(self) -> float:
        """Return factored LL+IM contribution."""
        return self.ll_im_factor * self.ll_im_moment_tn_m


def default_transverse_slab_combinations() -> tuple[LoadCombination, ...]:
    """Return MTC/AASHTO combinations relevant to applied slab loads."""
    live = LoadFactor(1.75, omit_when_favorable=True)
    service_live = LoadFactor(1.00, omit_when_favorable=True)
    service_iii_live = LoadFactor(0.80, omit_when_favorable=True)
    return (
        LoadCombination(
            name="RESISTENCIA I",
            limit_state="Resistencia",
            dc=LoadFactor(1.25, 0.90),
            dw=LoadFactor(1.50, 0.65),
            pl=live,
            ll_im=live,
        ),
        LoadCombination(
            name="SERVICIO I",
            limit_state="Servicio",
            dc=LoadFactor(1.00),
            dw=LoadFactor(1.00),
            pl=service_live,
            ll_im=service_live,
        ),
        LoadCombination(
            name="SERVICIO III",
            limit_state="Servicio",
            dc=LoadFactor(1.00),
            dw=LoadFactor(1.00),
            pl=service_iii_live,
            ll_im=service_iii_live,
        ),
    )


def combine_transverse_slab_moments(
    result: TransverseSlabAnalysisResult,
    combinations: tuple[LoadCombination, ...] | None = None,
) -> tuple[CombinedMomentResult, ...]:
    """Return critical positive and negative combined moment per combination."""
    definitions = combinations or default_transverse_slab_combinations()
    rows: list[CombinedMomentResult] = []
    positions = _combined_positions(result.dc, result.dw, result.pl, result.ll_im_envelope)
    for combination in definitions:
        rows.append(_critical_combined_moment(result, combination, positions, "max"))
        rows.append(_critical_combined_moment(result, combination, positions, "min"))
    return tuple(rows)


def _critical_combined_moment(
    result: TransverseSlabAnalysisResult,
    combination: LoadCombination,
    positions: tuple[float, ...],
    target: CombinationTarget,
) -> CombinedMomentResult:
    candidates = (
        _combined_moment_at(result, combination, position, target)
        for position in positions
    )
    if target == "max":
        return max(candidates, key=lambda item: item.combined_moment_tn_m)
    return min(candidates, key=lambda item: item.combined_moment_tn_m)


def _combined_moment_at(
    result: TransverseSlabAnalysisResult,
    combination: LoadCombination,
    position: float,
    target: CombinationTarget,
) -> CombinedMomentResult:
    dc = _moment_at(result.dc.moment_samples_tn_m, position)
    dw = _moment_at(result.dw.moment_samples_tn_m, position)
    pl = _moment_at(result.pl.moment_samples_tn_m, position)
    ll_im = _envelope_moment_at(result.ll_im_envelope, position, target)

    dc_factor = combination.dc.for_effect(dc, target)
    dw_factor = combination.dw.for_effect(dw, target)
    pl_factor = combination.pl.for_effect(pl, target)
    ll_im_factor = combination.ll_im.for_effect(ll_im, target)
    combined = (
        dc_factor * dc
        + dw_factor * dw
        + pl_factor * pl
        + ll_im_factor * ll_im
    )
    return CombinedMomentResult(
        combination_name=combination.name,
        limit_state=combination.limit_state,
        direction="M+" if target == "max" else "M-",
        position_m=position,
        dc_moment_tn_m=dc,
        dc_factor=dc_factor,
        dw_moment_tn_m=dw,
        dw_factor=dw_factor,
        pl_moment_tn_m=pl,
        pl_factor=pl_factor,
        ll_im_moment_tn_m=ll_im,
        ll_im_factor=ll_im_factor,
        combined_moment_tn_m=combined,
    )


def _envelope_moment_at(
    case: LoadCaseAnalysis,
    position: float,
    target: CombinationTarget,
) -> float:
    samples = (
        case.max_moment_envelope_tn_m
        if target == "max"
        else case.min_moment_envelope_tn_m
    )
    return _moment_at(samples or case.moment_samples_tn_m, position)


def _combined_positions(*cases: LoadCaseAnalysis) -> tuple[float, ...]:
    values: set[float] = set()
    for case in cases:
        values.update(position for position, _ in case.moment_samples_tn_m)
        if case.max_moment_envelope_tn_m is not None:
            values.update(position for position, _ in case.max_moment_envelope_tn_m)
        if case.min_moment_envelope_tn_m is not None:
            values.update(position for position, _ in case.min_moment_envelope_tn_m)
    return tuple(sorted(values))


def _moment_at(samples: tuple[tuple[float, float], ...], position: float) -> float:
    if not samples:
        raise ValueError("No hay muestras de momento para combinar.")
    if position <= samples[0][0]:
        return samples[0][1]
    if position >= samples[-1][0]:
        return samples[-1][1]
    for left, right in zip(samples[:-1], samples[1:]):
        left_x, left_m = left
        right_x, right_m = right
        if left_x <= position <= right_x:
            if right_x == left_x:
                return left_m
            ratio = (position - left_x) / (right_x - left_x)
            return left_m + ratio * (right_m - left_m)
    return samples[-1][1]
