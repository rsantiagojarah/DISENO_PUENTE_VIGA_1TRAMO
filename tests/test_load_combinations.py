from bridge_design.domain.load_combinations import combine_transverse_slab_moments
from bridge_design.domain.transverse_slab import (
    LoadCaseAnalysis,
    TransverseSlabAnalysisResult,
)


def _case(
    name: str,
    samples: tuple[tuple[float, float], ...],
    max_samples: tuple[tuple[float, float], ...] | None = None,
    min_samples: tuple[tuple[float, float], ...] | None = None,
) -> LoadCaseAnalysis:
    max_positive = max(samples, key=lambda item: item[1])
    max_negative = min(samples, key=lambda item: item[1])
    return LoadCaseAnalysis(
        name=name,
        max_positive_moment_tn_m=max_positive[1],
        max_positive_position_m=max_positive[0],
        max_negative_moment_tn_m=max_negative[1],
        max_negative_position_m=max_negative[0],
        support_reactions_tn=(),
        moment_samples_tn_m=samples,
        max_moment_envelope_tn_m=max_samples,
        min_moment_envelope_tn_m=min_samples,
    )


def test_transverse_slab_combinations_use_moments_at_same_station() -> None:
    dc = _case("DC", ((0.0, -10.0), (1.0, 5.0)))
    dw = _case("DW", ((0.0, -2.0), (1.0, 1.0)))
    pl = _case("PL", ((0.0, 1.0), (1.0, 1.0)))
    ll = _case(
        "LL+IM",
        ((0.0, 0.0), (1.0, 2.0)),
        max_samples=((0.0, 0.0), (1.0, 2.0)),
        min_samples=((0.0, -3.0), (1.0, 0.0)),
    )
    result = TransverseSlabAnalysisResult(
        dc=dc,
        dw=dw,
        pl=pl,
        ll_im_one_truck=ll,
        ll_im_two_trucks=ll,
        ll_im_envelope=ll,
        dynamic_load_allowance=0.33,
        equivalent_strip_width_positive_m=1.0,
        equivalent_strip_width_negative_m=1.0,
    )

    combined = combine_transverse_slab_moments(result)
    strength_positive = next(
        row
        for row in combined
        if row.combination_name == "RESISTENCIA I" and row.direction == "M+"
    )
    strength_negative = next(
        row
        for row in combined
        if row.combination_name == "RESISTENCIA I" and row.direction == "M-"
    )

    assert strength_positive.position_m == 1.0
    assert round(strength_positive.combined_moment_tn_m, 3) == 13.000
    assert strength_negative.position_m == 0.0
    assert strength_negative.pl_factor == 0.0
    assert round(strength_negative.combined_moment_tn_m, 3) == -20.750
