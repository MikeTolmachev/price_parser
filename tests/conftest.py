from __future__ import annotations

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _run_from_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests run with the project root as working directory."""
    monkeypatch.chdir(PROJECT_ROOT)
