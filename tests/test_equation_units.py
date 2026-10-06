from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from bridge_design.reporting.deck_docx import _add_native_equation


def test_strict_comparisons_remain_outside_fraction_denominators():
    document = Document()
    document.styles.add_style('Equation', WD_STYLE_TYPE.PARAGRAPH)
    for operator in ('<', '>'):
        paragraph = _add_native_equation(document, f'S^2/n {operator} 16')
        fraction = paragraph._p.xpath('.//m:f')[0]
        assert ''.join(fraction.find(qn('m:den')).itertext()) == 'n'
        assert any(operator in text for text in paragraph._p.xpath('.//m:oMath/m:r/m:t/text()'))


def test_general_shear_beta_preserves_two_fractional_factors():
    document = Document()
    document.styles.add_style("Equation", WD_STYLE_TYPE.PARAGRAPH)
    paragraph = _add_native_equation(document, 'β = (4.8/(1+750·εs))·(51/(39+sxe))')
    fractions = paragraph._p.xpath('.//m:f')
    assert len(fractions) == 2
    assert not paragraph._p.xpath('.//m:den//m:f')
    assert [''.join(f.find(qn('m:num')).itertext()) for f in fractions] == ['4.8', '51']
    assert [''.join(f.find(qn('m:den')).itertext()) for f in fractions] == ['(1 + 750·εs)', '(39 + sxe)']


def test_report_units_stay_inline_and_calculation_divisions_remain_fractions():
    document = Document()
    document.styles.add_style("Equation", WD_STYLE_TYPE.PARAGRAPH)
    for text in ("Ec=2717585.754 tn/m²", "q=26.700 tn/m²", "fs=2520 kgf/cm²",
                 "M=12.5 tn·m/m", "γ=2.4 tn/m³"):
        paragraph = _add_native_equation(document, text)
        assert not paragraph._p.xpath(".//m:f")
        assert ''.join(paragraph._p.xpath(".//m:t/text()")) == text.replace('=', ' = ')
    paragraph = _add_native_equation(document, "q=R_i/A_i")
    assert len(paragraph._p.xpath(".//m:f")) == 1


def test_native_powers_bind_only_their_base_and_exponent():
    document = Document()
    document.styles.add_style("Equation", WD_STYLE_TYPE.PARAGRAPH)
    cases = (("I=b*t^3/12", "t", "3"),
             ("EH=Ka*gamma_s*H^2/2", "H", "2"),
             ("Mcr=1.1*sqrt(fc)*b*h^2/(6*100000)", "h", "2"),
             ("K=cos(a)^2*cos(b)^2", "(a)", "2"),
             ("Ec=x^0.33 kgf/cm²", "x", "0.33"),
             ("F=(a*b)^(-2)", "(a*b)", "(-2)"))
    for expression, base, exponent in cases:
        paragraph = _add_native_equation(document, expression)
        power = paragraph._p.xpath(".//m:sSup")[0]
        assert ''.join(power.find(qn("m:e")).itertext()) == base
        assert ''.join(power.find(qn("m:sup")).itertext()) == exponent
    assert len(_add_native_equation(document, "K=cos(a)^2*cos(b)^2")._p.xpath(".//m:sSup")) == 2
