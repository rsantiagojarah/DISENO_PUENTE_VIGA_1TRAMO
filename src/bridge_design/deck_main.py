"""Compatibility entry point for the full deck/superstructure design."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> None:
    """Run the complete slab, girder, barrier and diaphragm workflow."""
    from bridge_design.main import main as run_main

    run_main(argv)


if __name__ == "__main__":
    main()
