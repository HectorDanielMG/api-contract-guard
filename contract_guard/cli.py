"""Interfaz de línea de comandos de Contract Guard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import ContractError, compare_files
from .render import render_markdown, render_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contract-guard",
        description="Detecta cambios potencialmente incompatibles entre contratos OpenAPI 3.x.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser("compare", help="compara una especificación anterior con una nueva")
    compare.add_argument("before", help="contrato anterior en JSON o YAML")
    compare.add_argument("after", help="contrato nuevo en JSON o YAML")
    compare.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    compare.add_argument("--output", help="guarda el informe en un archivo")
    compare.add_argument("--fail-on-breaking", action="store_true", help="devuelve 1 si detecta incompatibilidades")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = compare_files(args.before, args.after)
    except ContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        output = json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"
    elif args.format == "markdown":
        output = render_markdown(report)
    else:
        output = render_text(report) + "\n"

    if args.output:
        try:
            Path(args.output).write_text(output, encoding="utf-8")
        except OSError as exc:
            print(f"No se pudo guardar el informe: {exc}", file=sys.stderr)
            return 2
    else:
        print(output, end="")

    if args.fail_on_breaking and report.breaking:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
