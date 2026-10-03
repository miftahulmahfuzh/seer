"""``python -m seer_engine [--dry-run] [-v] <command> ...``

Commands are the modules in ``seer_engine/commands/`` (names not starting with ``_``).
Each one exposes::

    HELP: str
    def add_arguments(p: argparse.ArgumentParser) -> None
    def run(args: argparse.Namespace) -> int     # args.dry_run and args.verbose are set

Adding a command means adding a module; this file never changes. ``run``'s return value
is the process exit code.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import pkgutil
import sys
import time
from collections.abc import Sequence
from types import ModuleType

from seer_engine import __version__, commands, config

log = logging.getLogger("seer_engine")

_HANDLER_FLAG = "_seer_engine_handler"


def discover() -> dict[str, ModuleType]:
    """Command name -> module, for every public module in seer_engine.commands, sorted."""
    found: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(commands.__path__):
        if info.name.startswith("_") or info.ispkg:
            continue
        module = importlib.import_module(f"{commands.__name__}.{info.name}")
        if not callable(getattr(module, "run", None)):
            raise TypeError(f"command module {module.__name__} has no run(args)")
        found[info.name] = module
    return dict(sorted(found.items()))


def _add_global_flags(p: argparse.ArgumentParser, *, suppress: bool) -> None:
    """--dry-run and -v. On subcommands the defaults are suppressed so the flags work on
    either side of the command name without one position resetting the other."""
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="do every read and compute every write, then roll back; nothing persists",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=argparse.SUPPRESS if suppress else 0,
        help="debug logging",
    )


def build_parser(modules: dict[str, ModuleType] | None = None) -> argparse.ArgumentParser:
    modules = discover() if modules is None else modules
    parser = argparse.ArgumentParser(
        prog="seer_engine", description="Seer data pipeline (bars, universe, FX, runs)."
    )
    parser.add_argument("--version", action="version", version=f"seer_engine {__version__}")
    _add_global_flags(parser, suppress=False)
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    for name, module in modules.items():
        help_text = getattr(module, "HELP", "")
        p = sub.add_parser(name, help=help_text, description=help_text)
        _add_global_flags(p, suppress=True)
        add_arguments = getattr(module, "add_arguments", None)
        if add_arguments is not None:
            add_arguments(p)
        p.set_defaults(_run=module.run)
    return parser


class _UtcFormatter(logging.Formatter):
    converter = time.gmtime


def setup_logging(verbose: int) -> None:
    """Log to stderr with UTC timestamps. Replaces only the handler this function added."""
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, _HANDLER_FLAG, False):
            root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        _UtcFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%SZ")
    )
    setattr(handler, _HANDLER_FLAG, True)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("urllib3", "yfinance", "peewee"):
        logging.getLogger(noisy).setLevel(logging.DEBUG if verbose > 1 else logging.WARNING)


def main(argv: Sequence[str] | None = None) -> int:
    config.load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    if args.dry_run:
        log.info("dry-run: every transaction will be rolled back")
    try:
        code = args._run(args)
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        log.error("interrupted")
        return 130
    except Exception:
        log.exception("command %r failed", args.command)
        return 1
    return int(code or 0)
