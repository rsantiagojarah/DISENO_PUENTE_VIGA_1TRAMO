from types import SimpleNamespace
import unittest

from reportlab.graphics.shapes import PolyLine, String

from bridge_design.reporting.deck_charts import (
    envelope_diagram,
    strength_diagram_envelopes,
    strength_moment_envelopes,
)


def _case(
    samples,
    *,
    upper=None,
    lower=None,
    shear=(),
    shear_upper=None,
    shear_lower=None,
):
    return SimpleNamespace(
        moment_samples_tn_m=samples,
        max_moment_envelope_tn_m=upper,
        min_moment_envelope_tn_m=lower,
        shear_samples_tn=shear,
        max_shear_samples_tn=shear_upper,
        min_shear_samples_tn=shear_lower,
    )


class DeckChartTests(unittest.TestCase):
    def test_transverse_strength_moment_envelopes_remain_separate(self) -> None:
        dc = _case(((0.0, -10.0), (1.0, 5.0)))
        dw = _case(((0.0, -2.0), (1.0, 1.0)))
        pl = _case(((0.0, 1.0), (1.0, 1.0)))
        ll = _case(
            ((0.0, 0.0), (1.0, 2.0)),
            upper=((0.0, 0.0), (1.0, 2.0)),
            lower=((0.0, -3.0), (1.0, 0.0)),
        )
        result = SimpleNamespace(dc=dc, dw=dw, pl=pl, ll_im_envelope=ll)

        upper, lower, shears = strength_moment_envelopes(
            result,
            include_pl=True,
            transverse=True,
        )

        self.assertEqual(upper, ((0.0, -8.55), (1.0, 13.0)))
        self.assertEqual(lower, ((0.0, -20.75), (1.0, 5.15)))
        self.assertEqual(shears, ())

    def test_strength_shear_envelopes_remain_signed_and_separate(self) -> None:
        moments = ((0.0, 0.0), (1.0, 0.0))
        dc = _case(moments, shear=((0.0, 2.0), (1.0, -2.0)))
        dw = _case(moments, shear=((0.0, 1.0), (1.0, -1.0)))
        pl = _case(moments, shear=((0.0, 0.5), (1.0, -0.5)))
        ll = _case(
            moments,
            upper=moments,
            lower=moments,
            shear=((0.0, 4.0), (1.0, 4.0)),
            shear_upper=((0.0, 3.0), (1.0, 4.0)),
            shear_lower=((0.0, -4.0), (1.0, -3.0)),
        )
        result = SimpleNamespace(dc=dc, dw=dw, pl=pl, ll_im_envelope=ll)

        diagrams = strength_diagram_envelopes(
            result,
            include_pl=True,
        )

        self.assertEqual(diagrams.shear_upper, ((0.0, 10.125), (1.0, 4.55)))
        self.assertEqual(diagrams.shear_lower, ((0.0, -4.55), (1.0, -10.125)))

    def test_moment_diagram_draws_and_labels_both_envelopes(self) -> None:
        drawing = envelope_diagram(
            ((0.0, 0.0), (1.0, 4.0), (2.0, 0.0)),
            lower_samples=((0.0, 0.0), (1.0, -3.0), (2.0, 0.0)),
            title="Envolventes de momento",
            y_label="M (Tn.m)",
            legend_symbol="V",
        )

        curves = [item for item in drawing.contents if isinstance(item, PolyLine)]
        labels = [item.text for item in drawing.contents if isinstance(item, String)]

        self.assertEqual(len(curves), 2)
        self.assertIn("Vmax - superior", labels)
        self.assertIn("Vmin - inferior", labels)


if __name__ == "__main__":
    unittest.main()
