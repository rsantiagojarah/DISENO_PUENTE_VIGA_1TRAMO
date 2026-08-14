"""Reusable reinforcing bar catalog and spacing options."""

from dataclasses import dataclass
from math import floor

from bridge_design.validation.input_validators import require_non_negative, require_positive

DEFAULT_SPACING_STEP_M = 0.025
DEFAULT_MIN_SPACING_M = 0.10
DEFAULT_MAX_SPACING_M = 0.30


@dataclass(frozen=True)
class ReinforcingBar:
    """Catalog reinforcing bar."""

    label: str
    area_cm2: float
    diameter_cm: float

    def __post_init__(self) -> None:
        require_positive(self.area_cm2, f"area {self.label}")
        require_positive(self.diameter_cm, f"diametro {self.label}")


@dataclass(frozen=True)
class SpacingGrid:
    """Spacing grid and reference limits for bar distributions."""

    step_m: float = DEFAULT_SPACING_STEP_M
    minimum_m: float = DEFAULT_MIN_SPACING_M
    maximum_m: float = DEFAULT_MAX_SPACING_M

    def __post_init__(self) -> None:
        require_positive(self.step_m, "paso de espaciamiento")
        require_positive(self.minimum_m, "espaciamiento minimo")
        require_positive(self.maximum_m, "espaciamiento maximo")
        if self.maximum_m < self.minimum_m:
            raise ValueError("El espaciamiento maximo debe ser mayor o igual al minimo.")


@dataclass(frozen=True)
class ReinforcementSpacingOption:
    """One spacing option for a required reinforcement area."""

    item: int
    bar: ReinforcingBar
    spacing_m: float
    required_area_cm2_m: float
    provided_area_cm2_m: float
    is_compliant: bool
    is_recommended: bool = False

    @property
    def excess_percent(self) -> float:
        """Return excess steel over required area."""
        if self.required_area_cm2_m <= 0.0:
            return 0.0
        return (self.provided_area_cm2_m / self.required_area_cm2_m - 1.0) * 100.0


@dataclass(frozen=True)
class ReinforcementCaseOptions:
    """Spacing options for one calculated steel case."""

    label: str
    required_area_cm2_m: float
    options: tuple[ReinforcementSpacingOption, ...]

    @property
    def recommended(self) -> ReinforcementSpacingOption | None:
        """Return recommended option when any diameter complies."""
        for option in self.options:
            if option.is_recommended:
                return option
        return None


REINFORCING_BAR_CATALOG: tuple[ReinforcingBar, ...] = (
    ReinforcingBar("6 mm", 0.28, 0.60),
    ReinforcingBar("8 mm", 0.50, 0.80),
    ReinforcingBar('3/8"', 0.71, 0.95),
    ReinforcingBar('1/2"', 1.29, 1.27),
    ReinforcingBar('5/8"', 2.00, 1.59),
    ReinforcingBar('3/4"', 2.84, 1.91),
    ReinforcingBar('1"', 5.00, 2.54),
)


def generate_spacing_options(
    label: str,
    required_area_cm2_m: float,
    spacing_grid: SpacingGrid | None = None,
    first_item: int = 1,
) -> ReinforcementCaseOptions:
    """Return bar spacing options for every catalog diameter."""
    require_non_negative(required_area_cm2_m, f"As requerido {label}")
    grid = spacing_grid or SpacingGrid()
    options = tuple(
        _spacing_option_for_bar(first_item + index, bar, required_area_cm2_m, grid)
        for index, bar in enumerate(REINFORCING_BAR_CATALOG)
    )
    recommended = _recommended_option(options, grid)
    if recommended is None:
        return ReinforcementCaseOptions(label, required_area_cm2_m, options)
    return ReinforcementCaseOptions(
        label=label,
        required_area_cm2_m=required_area_cm2_m,
        options=tuple(
            ReinforcementSpacingOption(
                item=option.item,
                bar=option.bar,
                spacing_m=option.spacing_m,
                required_area_cm2_m=option.required_area_cm2_m,
                provided_area_cm2_m=option.provided_area_cm2_m,
                is_compliant=option.is_compliant,
                is_recommended=option.item == recommended.item,
            )
            for option in options
        ),
    )


def _spacing_option_for_bar(
    item: int,
    bar: ReinforcingBar,
    required_area_cm2_m: float,
    grid: SpacingGrid,
) -> ReinforcementSpacingOption:
    if required_area_cm2_m == 0.0:
        spacing = grid.maximum_m
    else:
        calculated_spacing = bar.area_cm2 / required_area_cm2_m
        spacing = _round_spacing_down(calculated_spacing, grid.step_m)
        if spacing > grid.maximum_m:
            spacing = grid.maximum_m
        if spacing <= 0.0:
            spacing = grid.step_m
    provided = bar.area_cm2 / spacing
    return ReinforcementSpacingOption(
        item=item,
        bar=bar,
        spacing_m=spacing,
        required_area_cm2_m=required_area_cm2_m,
        provided_area_cm2_m=provided,
        is_compliant=provided + 1e-9 >= required_area_cm2_m,
    )


def _recommended_option(
    options: tuple[ReinforcementSpacingOption, ...],
    grid: SpacingGrid,
) -> ReinforcementSpacingOption | None:
    compliant = tuple(
        option
        for option in options
        if option.is_compliant
        and grid.minimum_m <= option.spacing_m <= grid.maximum_m
    )
    if not compliant:
        compliant = tuple(option for option in options if option.is_compliant)
    if not compliant:
        return None
    return min(
        compliant,
        key=lambda option: (
            option.provided_area_cm2_m - option.required_area_cm2_m,
            -option.spacing_m,
        ),
    )


def _round_spacing_down(value_m: float, step_m: float) -> float:
    return round(floor(value_m / step_m + 1e-9) * step_m, 3)
