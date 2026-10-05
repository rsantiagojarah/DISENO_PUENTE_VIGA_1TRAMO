from types import SimpleNamespace

from bridge_design.reporting.connected_face_report import face_demands
from bridge_design.reporting.connected_report_details import mathematical_symbols


def test_signed_envelope_faces_include_all_cases_without_crossing_signs():
    demands = [SimpleNamespace(moment=m, case=c) for m, c in
               ((12, "Resistencia Ia BR-1"), (-30, "Evento Extremo I B EQ+1"),
                (0, "Servicio I BR+1"), (15, "Sin tablero / Resistencia Ib"))]
    left = dict(face_demands("Pantalla izquierda", demands))
    right = dict(face_demands("Pantalla derecha", demands))
    footing = dict(face_demands("Zapata izquierda", demands))
    assert left["Exterior"] == right["Relleno"] == footing["Inferior"] == [demands[0], demands[2], demands[3]]
    assert left["Relleno"] == right["Exterior"] == footing["Superior"] == [demands[1]]
    assert dict(face_demands("Losa central", demands)) == footing


def test_math_symbols_preserve_case_names_and_scientific_numbers():
    assert mathematical_symbols("gamma_c; phi_b; eta_q; beta1; eps_s; mu; Delta_F") == "γ_c; φ_b; η_q; β1; ε_s; μ; Δ_F"
    assert mathematical_symbols("Resistencia Ia BR-1; 1.2e-06") == "Resistencia Ia BR-1; 1.2e-06"
