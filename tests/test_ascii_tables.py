from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table


class _TerminalOutput:
    def isatty(self) -> bool:
        return True


class _RedirectedOutput:
    def isatty(self) -> bool:
        return False


def test_audit_titles_are_plain_text_when_output_is_redirected(monkeypatch) -> None:
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("BRIDGE_DESIGN_FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("BRIDGE_DESIGN_NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout", _RedirectedOutput())

    lines = audit_block_title("1", "DISENO DE LOSA", 40)

    assert all("\033[" not in line for line in lines)


def test_terminal_output_uses_single_professional_accent(monkeypatch) -> None:
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("BRIDGE_DESIGN_FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("BRIDGE_DESIGN_NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout", _TerminalOutput())

    block_lines = audit_block_title("1", "DISENO DE LOSA", 40)
    subtitle_lines = audit_subtitle("2", "ACERO PRINCIPAL", 40)

    assert all(line.startswith("\033[34m") for line in block_lines + subtitle_lines)


def test_forced_color_uses_single_professional_accent(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("BRIDGE_DESIGN_NO_COLOR", raising=False)
    monkeypatch.setenv("BRIDGE_DESIGN_FORCE_COLOR", "1")

    block_lines = audit_block_title("1", "DISENO DE LOSA", 40)
    subtitle_lines = audit_subtitle("2", "ACERO PRINCIPAL", 40)

    assert all(line.startswith("\033[34m") for line in block_lines + subtitle_lines)


def test_no_color_overrides_terminal_color(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("sys.stdout", _TerminalOutput())

    lines = audit_block_title("1", "DISENO DE LOSA", 40)

    assert all("\033[" not in line for line in lines)


def test_boxed_table_wraps_long_cells_to_max_width() -> None:
    lines = boxed_table(
        ("Area PDF", "Formula A", "Formula x"),
        (
            (
                "11 Relleno triangular frontal",
                "b11 * (h_frontal - D) / 2; b11=(h_frontal - D)*(e_inf - e_sup)/(ALTURA_TOTAL - D - altura_cajuela - altura_bloque_cajuela - altura_transicion)",
                "PUNTERA + b11/3",
            ),
        ),
        max_width=80,
    )

    assert max(len(line) for line in lines) <= 80
    assert len(lines) > 5


def test_boxed_table_separates_wrapped_data_rows() -> None:
    lines = boxed_table(
        ("Verificacion", "Formula"),
        (
            ("Compresion sigma_s <= G*S", "sigma_s = R/A ; sigma_s <= Gmin*S"),
            ("Deflexion capa <= 0.09 h", "delta_total = eps_total*h <= 0.09*h"),
        ),
        max_width=60,
    )

    border = lines[0]
    first_row_start = next(
        index for index, line in enumerate(lines) if "Compresion" in line
    )
    second_row_start = next(
        index for index, line in enumerate(lines) if "Deflexion" in line
    )

    assert border in lines[first_row_start + 1 : second_row_start]
