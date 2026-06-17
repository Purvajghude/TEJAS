"""Configuration loader.

Loads ``config.yaml`` from the repository root and resolves every path in the
``paths`` section to an absolute :class:`pathlib.Path` rooted at the repo.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

# Repository root = parent of the directory holding this file (tejas/).
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"


class Config:
    """Thin dict wrapper with attribute access and resolved paths."""

    def __init__(self, data: dict):
        self._data = data
        # Resolve declared paths relative to the repo root.
        self.paths = {
            key: (REPO_ROOT / value) for key, value in data.get("paths", {}).items()
        }

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    @property
    def solexs(self) -> dict:
        return self._data["solexs"]

    @property
    def detection(self) -> dict:
        return self._data["detection"]

    @property
    def hel1os(self) -> dict:
        return self._data["hel1os"]

    @property
    def goes(self) -> dict:
        return self._data["goes"]

    @property
    def forecast(self) -> dict:
        return self._data["forecast"]

    def ensure_dirs(self) -> None:
        """Create every output directory declared in ``paths``."""
        for key, path in self.paths.items():
            if key.startswith("raw") or key == "external":
                continue
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def load_config() -> Config:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return Config(data)
