"""Replay the published Soldeoro inputs and adopted bars without UI dialogs.

Writes a numeric snapshot of the full workflow for before/after comparison.
The source Word is an output artifact, not an input format of diseno-tablero.
"""
from contextlib import ExitStack, redirect_stdout
from dataclasses import asdict
import json
from pathlib import Path
import sys
from unittest.mock import patch

from bridge_design import main as command
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain.interior_girder import custom_main_bar_placement_option, custom_shear_stirrup_option
from bridge_design.domain.rebar_catalog import custom_spacing_option


def spacing(cases):
    return tuple((f'{code}. {case.label}', custom_spacing_option(case, bar, pitch))
                 for code, case, bar, pitch in cases)


def run_snapshot(destination):
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/soldeoro_20261005.yaml'
    project = project_inputs_from_yaml(load_yaml_file(fixture))
    original_interior = command.collect_interior_girder_reinforcement_selection
    original_exterior = command.collect_exterior_girder_reinforcement_selection
    original_diaphragm = command.collect_diaphragm_reinforcement_selection

    def girders(reinforcement, shear, exterior=False):
        selected = list((original_exterior if exterior else original_interior)(reinforcement, shear))
        selected[0] = (selected[0][0], custom_main_bar_placement_option(reinforcement.main.placement_options, '1"', 20))
        selected[2] = (selected[2][0], next(o for o in reinforcement.skin.spacing_options.options if o.bar.label == '1/2"'))
        selected[-1] = (selected[-1][0], custom_shear_stirrup_option(shear, '1/2"', 2, .20 if exterior else .175))
        return tuple(selected)

    def diaphragm(reinforcement, element_name='diafragma'):
        selected = list(original_diaphragm(reinforcement, element_name))
        for index, steel in enumerate((reinforcement.negative, reinforcement.positive)):
            selected[index] = (selected[index][0], custom_main_bar_placement_option(steel.placement_options, '3/4"', 4))
        return tuple(selected)

    captured = []
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        stack.enter_context(patch('builtins.input', lambda prompt='': ''))
        stack.enter_context(patch.object(command, 'collect_reinforcement_spacing_selection', lambda r: spacing((
            ('A', r.negative.spacing_options, '5/8"', .15), ('B', r.positive.spacing_options, '5/8"', .15),
            ('C', r.temperature.spacing_options, '1/2"', .20), ('D', r.distribution.spacing_options, '1/2"', .20)))))
        stack.enter_context(patch.object(command, 'collect_cantilever_reinforcement_selection', lambda r: spacing((
            ('A', r.flexural_steel.spacing_options, '1/2"', .20), ('B', r.temperature_steel.spacing_options, '1/2"', .20)))))
        stack.enter_context(patch.object(command, 'collect_interior_girder_reinforcement_selection', girders))
        stack.enter_context(patch.object(command, 'collect_exterior_girder_reinforcement_selection', lambda r,s: girders(r,s,True)))
        stack.enter_context(patch.object(command, 'collect_diaphragm_reinforcement_selection', diaphragm))
        stack.enter_context(patch('bridge_design.reporting.generate_deck_docx_with_dialog', captured.append))
        output = stack.enter_context(destination.with_suffix('.txt').open('w', encoding='utf-8'))
        stack.enter_context(redirect_stdout(output))
        command.run_bridge_design(project)
    if len(captured) != 1:
        raise RuntimeError('El flujo no produjo exactamente un resultado completo.')
    data = asdict(captured[0])
    data.pop('audit_sections', None)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(destination)
    return captured[0]


if __name__ == '__main__':
    run_snapshot(sys.argv[1])
