"""Matriz de requisitos normativos para apoyos elastomericos PEP (Metodo A).

Fuentes prioritarias:
- Manual de Puentes MTC 2018 Art. 2.10 / 2.10.4
- AASHTO LRFD Art. 14.7.5 / 14.7.6 / 14.8.3 / 14.6.3
- Serquen Cap. 4 solo como apoyo explicativo
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PepNormativeRequirement:
    requisito: str
    articulo_mtc: str
    articulo_aashto: str
    tipo_apoyo: str
    estado_limite: str
    ecuacion: str
    variables: str
    unidades: str
    implementacion: str


PEP_NORMATIVE_MATRIX: tuple[PepNormativeRequirement, ...] = (
    PepNormativeRequirement(
        "Factor de forma rectangular sin agujeros",
        "MTC 2.10.3.1 / 2.10.4",
        "AASHTO 14.7.5.1-1",
        "FIJO y MOVIL_PEP_CORTE",
        "Geometria",
        "S = L*W / [2*h*(L+W)]",
        "L, W, h",
        "cm, adimensional",
        "IMPLEMENTADO",
    ),
    PepNormativeRequirement(
        "Propiedades G y creep por dureza Shore A",
        "MTC 2.10.4.2",
        "AASHTO 14.7.6.2 Tabla 14.7.6.2-1",
        "FIJO y MOVIL_PEP_CORTE",
        "Material",
        "Gmin-Gmax; a_cr",
        "Shore A 50/60/70",
        "kg/cm2, -",
        "IMPLEMENTADO",
    ),
    PepNormativeRequirement(
        "Esfuerzo de compresion PEP",
        "MTC 2.10.4.3.2",
        "AASHTO 14.7.6.3.2 (limites PEP)",
        "FIJO y MOVIL_PEP_CORTE",
        "Servicio",
        "sigma_s <= 1.00*G*S ; sigma_s <= 0.80 ksi",
        "R, A, Gmin, S",
        "kg/cm2",
        "IMPLEMENTADO",
    ),
    PepNormativeRequirement(
        "Deflexion por compresion",
        "MTC 2.10.4.3.3",
        "AASHTO 14.7.6.3.3 / 14.7.5.3.6",
        "FIJO y MOVIL_PEP_CORTE",
        "Servicio",
        "delta = eps*h ; delta <= 0.09*h",
        "eps, h",
        "cm",
        "IMPLEMENTADO (curva AASHTO digitalizada / manual / estimacion)",
    ),
    PepNormativeRequirement(
        "Creep",
        "MTC 2.10.4.3.3",
        "AASHTO 14.7.5.3.6-3 / Tabla 14.7.6.2-1",
        "FIJO y MOVIL_PEP_CORTE",
        "Servicio",
        "delta_lt = delta_d*(1+a_cr)",
        "a_cr, delta_d",
        "cm",
        "IMPLEMENTADO",
    ),
    PepNormativeRequirement(
        "Cortante / desplazamiento",
        "MTC 2.10.4.3.4",
        "AASHTO 14.7.6.3.4-1",
        "MOVIL_PEP_CORTE (N.A. FIJO con restriccion externa)",
        "Servicio",
        "h >= 2*Delta_s",
        "h, Delta_s",
        "cm",
        "IMPLEMENTADO",
    ),
    PepNormativeRequirement(
        "Rotacion Metodo A",
        "MTC 2.10.4.3.5",
        "AASHTO 14.7.6.3.5 / C14.7.6.1",
        "FIJO y MOVIL_PEP_CORTE",
        "Servicio",
        "Implicita en geometria y esfuerzos Metodo A",
        "theta_s (dato)",
        "rad",
        "IMPLEMENTADO (registro theta; sin ecuacion Metodo B)",
    ),
    PepNormativeRequirement(
        "Estabilidad",
        "MTC 2.10.4.3.6",
        "AASHTO 14.7.6.3.6",
        "FIJO y MOVIL_PEP_CORTE",
        "Servicio",
        "h <= L/3 ; h <= W/3",
        "h, L, W",
        "cm",
        "IMPLEMENTADO",
    ),
    PepNormativeRequirement(
        "Fuerza horizontal por deformacion",
        "MTC 2.10.2.1.1",
        "AASHTO 14.6.3.1",
        "MOVIL_PEP_CORTE / FIJO si CORTE_EN_ELASTOMERO",
        "Servicio / Resistencia / EE",
        "H = G*A*Delta/h",
        "Gmax, A, Delta, h",
        "Tn",
        "IMPLEMENTADO",
    ),
    PepNormativeRequirement(
        "Restriccion apoyo fijo = 100% H",
        "MTC 2.10.4.3.8 / 2.10.3.3.7",
        "AASHTO 14.8 / 3.10.9",
        "FIJO",
        "Resistencia / Evento Extremo",
        "H_restriccion = H_demanda",
        "Hx, Hy",
        "Tn",
        "IMPLEMENTADO (demanda 100% H + diseno placas/pernos/anclaje)",
    ),
    PepNormativeRequirement(
        "Anclaje / friccion elastomero",
        "MTC 2.10 / anclaje apoyos",
        "AASHTO 14.8.3 / C14.8.3.1",
        "MOVIL_PEP_CORTE",
        "Servicio / EE",
        "mu=0.20 cuando aplique; no sustituye restriccion fija",
        "mu, PDC, Hu",
        "Tn",
        "IMPLEMENTADO (criterio reportado)",
    ),
    PepNormativeRequirement(
        "Incremento 10% si corte impedido",
        "MTC 2.10.4.3.2",
        "AASHTO 14.7.6.3.2",
        "FIJO",
        "Servicio",
        "No aplicado automaticamente",
        "-",
        "-",
        "NO APLICADO (aplicabilidad a PEP no verificada en fuentes cargadas)",
    ),
    PepNormativeRequirement(
        "Placas externas, pernos, soldadura, anclaje a concreto",
        "MTC 2.10 / acero / conexiones",
        "AASHTO Sec. 6 / 14.8 / AWS",
        "FIJO y MOVIL_PEP_CORTE",
        "Resistencia / EE / Fatiga",
        "Segun articulos de acero y anclaje",
        "placas, pernos, soldaduras, f'c",
        "varios",
        "IMPLEMENTADO (AASHTO Sec.6 / ACI 318 Cap.17 referenciado)",
    ),
    PepNormativeRequirement(
        "Presion local en concreto / bearing",
        "MTC 2.8.1.4",
        "AASHTO 5.7.5",
        "FIJO y MOVIL_PEP_CORTE",
        "Resistencia",
        "phi*0.85*f'c*A1*m",
        "f'c, A1, A2",
        "kg",
        "IMPLEMENTADO (opcional)",
    ),
)


def format_pep_normative_matrix() -> str:
    """Return a compact printable matrix."""
    lines = [
        "MATRIZ NORMATIVA PEP (Metodo A)",
        "Req | MTC | AASHTO | Tipo | EL | Ecuacion | Impl.",
        "-" * 96,
    ]
    for item in PEP_NORMATIVE_MATRIX:
        lines.append(
            f"{item.requisito} | {item.articulo_mtc} | {item.articulo_aashto} | "
            f"{item.tipo_apoyo} | {item.estado_limite} | {item.ecuacion} | {item.implementacion}"
        )
    return "\n".join(lines)
