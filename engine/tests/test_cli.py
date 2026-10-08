"""Command discovery, global flags and exit codes. No database needed."""

from __future__ import annotations

import argparse
import re
import sys
import textwrap

import pytest

from seer_engine import cli, commands, config


def test_discovers_migrate():
    assert "migrate" in cli.discover()


def test_help_lists_migrate(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "migrate" in capsys.readouterr().out


@pytest.fixture
def fake_command(tmp_path, monkeypatch):
    """Drop a new module into the commands package path, as a later phase would."""
    (tmp_path / "zz_fake.py").write_text(
        textwrap.dedent(
            '''
            HELP = "fake command for tests"
            CALLS = []

            def add_arguments(p):
                p.add_argument("--code", type=int, default=0)
                p.add_argument("--boom", choices=["none", "error", "config"], default="none")

            def run(args):
                CALLS.append(args)
                if args.boom == "error":
                    raise RuntimeError("boom")
                if args.boom == "config":
                    from seer_engine.config import ConfigError
                    raise ConfigError("MISSING is not set")
                return args.code
            '''
        )
    )
    monkeypatch.setattr(commands, "__path__", [*commands.__path__, str(tmp_path)])
    yield "zz_fake"
    sys.modules.pop("seer_engine.commands.zz_fake", None)


def test_new_module_becomes_a_command_without_editing_cli(fake_command):
    assert fake_command in cli.discover()
    assert cli.main([fake_command]) == 0
    module = sys.modules["seer_engine.commands.zz_fake"]
    args = module.CALLS[-1]
    assert args.dry_run is False and args.verbose == 0


def test_return_value_is_exit_code(fake_command):
    assert cli.main([fake_command, "--code", "3"]) == 3


@pytest.mark.parametrize(
    "argv",
    [["--dry-run", "zz_fake"], ["zz_fake", "--dry-run"], ["-v", "zz_fake", "--dry-run"]],
)
def test_dry_run_flag_either_side_of_command(fake_command, argv):
    assert cli.main(argv) == 0
    args = sys.modules["seer_engine.commands.zz_fake"].CALLS[-1]
    assert args.dry_run is True


def test_verbose_flag(fake_command):
    cli.main(["-v", fake_command])
    assert sys.modules["seer_engine.commands.zz_fake"].CALLS[-1].verbose == 1


def test_exception_exits_1(fake_command, capsys):
    assert cli.main([fake_command, "--boom", "error"]) == 1
    assert "boom" in capsys.readouterr().err


def test_config_error_exits_2(fake_command, capsys):
    assert cli.main([fake_command, "--boom", "config"]) == 2
    assert "MISSING is not set" in capsys.readouterr().err


def test_logs_go_to_stderr_with_utc_timestamps(fake_command, capsys):
    cli.main(["--dry-run", fake_command])
    out, err = capsys.readouterr()
    assert out == ""
    assert re.search(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ INFO ", err, re.M)


def test_config_load_env_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / "x.env"
    env.write_text("SEER_T_A=from-file\nSEER_T_B=a&b\n")
    monkeypatch.setenv("SEER_ENV_FILE", str(env))
    monkeypatch.setenv("SEER_T_A", "from-env")
    monkeypatch.setenv("SEER_T_B", "placeholder")
    monkeypatch.delenv("SEER_T_B")  # absent now, and removed again on teardown
    assert config.load_env() == env
    assert config.get("SEER_T_A") == "from-env"
    assert config.get("SEER_T_B") == "a&b"


def test_config_require_raises(monkeypatch):
    monkeypatch.delenv("SEER_T_MISSING", raising=False)
    with pytest.raises(config.ConfigError):
        config.require("SEER_T_MISSING")


# --------------------------------------------------------------- every --help must format


def _every_parser(parser: argparse.ArgumentParser) -> list[argparse.ArgumentParser]:
    """``parser`` and every subparser reachable from it, depth-first.

    Subparsers are only reachable through the ``choices`` mapping of the ``_SubParsersAction``
    that created them, and the action list is private. That is the whole public surface argparse
    offers for walking a parser tree, and a test is the right place to use it: the alternative is
    to maintain a hand-written list of command names, which is exactly the thing that goes stale.
    """
    out = [parser]
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            for child in choices.values():
                if isinstance(child, argparse.ArgumentParser):
                    out.extend(_every_parser(child))
    return out


def test_every_parsers_help_text_formats_without_raising():
    """`lab --help` crashed with `ValueError: unsupported format character ','`.

    argparse runs every ``help=`` string through %-interpolation in
    ``HelpFormatter._expand_help``, so a help string that writes a percentage as ``0.1%`` is
    read as a format spec and the whole ``--help`` dies. Nothing catches it: the string is only
    interpolated when that particular parser's help is rendered, so the bug sits in a subparser
    until somebody runs ``--help`` on it. One did, in ``lab costs``, for about a week.

    This walks every parser the CLI builds and formats each one's help. ``format_help()`` is the
    call ``--help`` makes just before it exits, so it does the interpolation without printing or
    raising ``SystemExit`` -- which is why this asserts on the formatting rather than on output.
    """
    parsers = _every_parser(cli.build_parser())
    assert len(parsers) > 10, (
        "the parser walk found almost nothing, so this test is not covering the subparsers it "
        "exists for -- check _every_parser against the argparse version in use"
    )
    broken = []
    for p in parsers:
        try:
            text = p.format_help()
        except Exception as exc:  # noqa: BLE001 -- the point is that NOTHING may escape
            broken.append(f"  {p.prog}: {type(exc).__name__}: {exc}")
            continue
        if not text.strip():
            broken.append(f"  {p.prog}: formatted to nothing")
    assert not broken, (
        "`--help` raises or renders empty for these parsers. A bare `%` in a `help=` string is "
        "the usual cause -- write it `%%`; `description=` and `epilog=` are not interpolated and "
        "must stay single:\n" + "\n".join(broken)
    )
