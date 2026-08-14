"""Centralized unit conversions used by the project."""

KG_CM2_PER_KSI = 70.3069578296
KSI_PER_KG_CM2 = 1.0 / KG_CM2_PER_KSI

KGF_M3_PER_TN_M3 = 1000.0
LB_FT3_PER_KGF_M3 = 0.0624279606
KCF_PER_LB_FT3 = 1.0 / 1000.0

KGF_M2_PER_PSF = 4.882427636
TN_M2_PER_KGF_M2 = 1.0 / 1000.0

TN_PER_KIP = 0.45359237
M_PER_FT = 0.3048
M_PER_IN = 0.0254


def kg_cm2_to_ksi(value: float) -> float:
    """Convert kgf/cm2 to ksi."""
    return value * KSI_PER_KG_CM2


def ksi_to_kg_cm2(value: float) -> float:
    """Convert ksi to kgf/cm2."""
    return value * KG_CM2_PER_KSI


def tn_m3_to_kgf_m3(value: float) -> float:
    """Convert metric ton-force per cubic meter to kgf/m3."""
    return value * KGF_M3_PER_TN_M3


def kgf_m3_to_kcf(value: float) -> float:
    """Convert kgf/m3 to kips per cubic foot."""
    return value * LB_FT3_PER_KGF_M3 * KCF_PER_LB_FT3


def tn_m3_to_kcf(value: float) -> float:
    """Convert metric ton-force per cubic meter to kips per cubic foot."""
    return kgf_m3_to_kcf(tn_m3_to_kgf_m3(value))


def ksf_to_tn_m2(value: float) -> float:
    """Convert ksf to metric ton-force per square meter."""
    psf = value * 1000.0
    return psf * KGF_M2_PER_PSF * TN_M2_PER_KGF_M2


def psf_to_tn_m2(value: float) -> float:
    """Convert psf to metric ton-force per square meter."""
    return value * KGF_M2_PER_PSF * TN_M2_PER_KGF_M2


def kip_to_tn(value: float) -> float:
    """Convert kip to metric ton-force."""
    return value * TN_PER_KIP


def ft_to_m(value: float) -> float:
    """Convert feet to meters."""
    return value * M_PER_FT


def m_to_ft(value: float) -> float:
    """Convert meters to feet."""
    return value / M_PER_FT


def inch_to_m(value: float) -> float:
    """Convert inches to meters."""
    return value * M_PER_IN


def m_to_in(value: float) -> float:
    """Convert meters to inches."""
    return value / M_PER_IN
