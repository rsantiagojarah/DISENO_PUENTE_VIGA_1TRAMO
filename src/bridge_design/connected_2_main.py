"""Separate ver_2l command using the complete original connected design workflow."""

from bridge_design.connected_main import ConnectedCommand, main as run_connected_command
from bridge_design.cli.connected_2_prompts import collect_connected_2_inputs
from bridge_design.cli.connected_2_yaml import COMMAND, connected_2_inputs_from_yaml, connected_2_yaml_template


def main(argv=None):
    return run_connected_command(argv, profile=ConnectedCommand(
        COMMAND, "estribos_conectados_2",
        "Dos estribos iguales segun ver_2l.pdf: base uniforme, pantallas inclinadas hacia el interior, "
        "relleno hasta parapeto y sin relleno interior. FRAME y Winkler solo a compresion.",
        collect_connected_2_inputs, connected_2_inputs_from_yaml, connected_2_yaml_template))


if __name__ == "__main__":
    main()
