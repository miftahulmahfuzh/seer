"""Environment configuration.

Values come from the process environment. Locally they are also read from the repo-root
``.env.local`` (or the file named by ``SEER_ENV_FILE``) with python-dotenv, which never
overrides a variable that is already set. The file is parsed, never ``source``d: it holds
an unquoted ``&`` that a shell would misread.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# engine/src/seer_engine/config.py -> parents: seer_engine, src, engine, <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]

_loaded = False


class ConfigError(RuntimeError):
    """A required setting is missing."""


def env_file() -> Path:
    """The dotenv file load_env() reads: $SEER_ENV_FILE, else <repo root>/.env.local."""
    override = os.environ.get("SEER_ENV_FILE")
    return Path(override) if override else REPO_ROOT / ".env.local"


def load_env() -> Path | None:
    """Load the dotenv file into os.environ without overriding existing variables.

    Returns the path that was loaded, or None when the file does not exist (CI).
    Safe to call more than once.
    """
    global _loaded
    _loaded = True
    path = env_file()
    if not path.is_file():
        return None
    load_dotenv(path, override=False)
    return path


def get(name: str) -> str | None:
    """The value of ``name``, or None when unset or empty."""
    if not _loaded:
        load_env()
    value = os.environ.get(name)
    return value if value else None


def require(name: str) -> str:
    """The value of ``name``; raises ConfigError when unset or empty."""
    value = get(name)
    if value is None:
        raise ConfigError(f"{name} is not set (checked the environment and {env_file()})")
    return value
