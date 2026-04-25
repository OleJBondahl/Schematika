from __future__ import annotations

import argparse
import logging
import sys
import traceback
from pathlib import Path

from . import parse_file

logger = logging.getLogger(__name__)

_INSTALL_HINTS: dict[str, str] = {
    ".dxf": "Install ezdxf: pip install cad-parser[autocad]",
    ".kicad_sch": "Install kiutils: pip install cad-parser[kicad]",
    ".pdf": "Install PyMuPDF: pip install cad-parser[pdf]",
    ".svg": "Install lxml: pip install cad-parser[svg]",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cad_parser",
        description="Parse a CAD/schematic file and output structured JSON.",
    )
    parser.add_argument(
        "path", help="Path to the input file (.dxf, .kicad_sch, .pdf, .svg)"
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Write JSON output to FILE instead of stdout",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        metavar="N",
        help="JSON indentation level (default: 2)",
    )
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress all output except errors",
    )
    log_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def configure_logging(args: argparse.Namespace) -> None:
    if args.quiet:
        level = logging.ERROR
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(args)

    input_path = Path(args.path)

    if not input_path.exists():
        print(f"ERROR: File not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = parse_file(input_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except ImportError as exc:
        ext = input_path.suffix.lower()
        hint = _INSTALL_HINTS.get(
            ext, "Check that all optional dependencies are installed."
        )
        print(f"ERROR: Missing dependency — {exc}", file=sys.stderr)
        print(f"HINT:  {hint}", file=sys.stderr)
        sys.exit(1)
    except Exception:
        logger.debug("Unexpected error during parsing", exc_info=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    json_str = data.to_json(indent=args.indent)

    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        logger.info("Output written to %s", args.output)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
