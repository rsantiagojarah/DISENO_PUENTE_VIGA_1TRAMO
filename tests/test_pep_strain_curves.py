from bridge_design.domain.pep_strain_curves import compressive_strain_from_curve


def test_strain_curve_aashto():
    look = compressive_strain_from_curve(60, 6.0, 51.85)
    assert 0.02 < look.epsilon < 0.08
    assert "C14.7.6.3.3-1" in look.source
