"""The store and cache defaults honour their environment variables (lab insight 208).

A worktree has no ``engine/.research``, ``engine/.research-sv`` or ``engine/.cache/eodhd`` of its
own: all three are gitignored, and the defaults derive from the running module's repo root. M0117's
promised survivorship check was skipped in a Sera worktree for exactly that reason. These tests pin
the fallback chain ``flag > $VAR > checkout default``. They parse arguments and nothing more, so
they cannot reach a store, the network or a database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from seer_engine import cli, research
from seer_engine.commands import survivorship_store as sv_cmd
from seer_engine.lab import store
from seer_engine.lab import survivorship_check as svc

ENV_VARS = ("SEER_SV_STORE", "SEER_RESEARCH_STORE", "SEER_EODHD_CACHE")


@pytest.fixture
def env(monkeypatch):
    """A monkeypatch with none of the three variables set, whatever the caller's shell exports."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def _parse(*argv: str):
    # build_parser runs every command's add_arguments, so the env is read here, at parse time
    return cli.build_parser().parse_args(list(argv))


# ---- lab survivorship ---------------------------------------------------------------------


def test_lab_survivorship_defaults_to_this_checkout_without_the_variables(env):
    args = _parse("lab", "survivorship", "M0001")
    assert args.sv_store == research.SV_STORE_DIR
    assert args.store == research.STORE_DIR


def test_lab_survivorship_sv_store_honours_seer_sv_store(env, tmp_path):
    env.setenv("SEER_SV_STORE", str(tmp_path / "sv"))
    env.setenv("SEER_RESEARCH_STORE", str(tmp_path / "dev"))
    args = _parse("lab", "survivorship", "M0001")
    assert args.sv_store == tmp_path / "sv"
    assert args.store == tmp_path / "dev"


def test_lab_survivorship_flag_beats_the_variable(env, tmp_path):
    env.setenv("SEER_SV_STORE", str(tmp_path / "from-env"))
    args = _parse("lab", "survivorship", "M0001", "--sv-store", str(tmp_path / "from-flag"))
    assert args.sv_store == tmp_path / "from-flag"


def test_lab_survivorship_empty_variable_falls_back(env):
    env.setenv("SEER_SV_STORE", "")
    assert _parse("lab", "survivorship", "M0001").sv_store == research.SV_STORE_DIR


def test_lab_survivorship_help_formats_and_names_the_variable(env, capsys):
    with pytest.raises(SystemExit) as exc:
        _parse("lab", "survivorship", "--help")
    assert exc.value.code == 0
    assert "SEER_SV_STORE" in capsys.readouterr().out


# ---- survivorship_store -------------------------------------------------------------------


def test_survivorship_store_defaults_to_this_checkout_without_the_variables(env):
    args = _parse("survivorship_store")
    assert args.out == research.SV_STORE_DIR
    assert args.source == research.STORE_DIR
    assert args.cache == sv_cmd.CACHE_DIR


def test_survivorship_store_defaults_honour_the_variables(env, tmp_path):
    env.setenv("SEER_SV_STORE", str(tmp_path / "sv"))
    env.setenv("SEER_RESEARCH_STORE", str(tmp_path / "dev"))
    env.setenv("SEER_EODHD_CACHE", str(tmp_path / "eodhd"))
    args = _parse("survivorship_store", "--build")
    assert (args.out, args.source, args.cache) == (tmp_path / "sv", tmp_path / "dev", tmp_path / "eodhd")


def test_survivorship_store_flags_beat_the_variables(env, tmp_path):
    for var in ENV_VARS:
        env.setenv(var, str(tmp_path / "from-env"))
    args = _parse(
        "survivorship_store",
        "--out", str(tmp_path / "o"), "--source", str(tmp_path / "s"), "--cache", str(tmp_path / "c"),
    )
    assert (args.out, args.source, args.cache) == (tmp_path / "o", tmp_path / "s", tmp_path / "c")


def test_survivorship_store_help_formats_and_names_the_variables(env, capsys):
    with pytest.raises(SystemExit) as exc:
        _parse("survivorship_store", "--help")
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for var in ENV_VARS:
        assert var in out


# ---- the refusal says how to reach the main checkout --------------------------------------


def test_a_missing_store_names_both_variables(tmp_path):
    with pytest.raises(store.LabError) as exc:
        svc.peek_purpose(Path(tmp_path / "nowhere"))
    message = str(exc.value)
    assert "SEER_SV_STORE" in message and "SEER_RESEARCH_STORE" in message
