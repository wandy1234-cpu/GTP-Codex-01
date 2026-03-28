"""YAML config loading utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_configs(base_dir: str | Path = "config") -> dict[str, dict[str, Any]]:
    base = Path(base_dir)
    return {
        "app": load_yaml(base / "app.yaml"),
        "data": load_yaml(base / "data.yaml"),
        "model": load_yaml(base / "model.yaml"),
        "backtest": load_yaml(base / "backtest.yaml"),
        "ui": load_yaml(base / "ui.yaml"),
    }
