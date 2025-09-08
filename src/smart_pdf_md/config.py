"""Configuration file loading helpers.

Supports TOML (.toml), YAML (.yml/.yaml), and JSON (.json) formats.
Keys are normalized to lowercase with hyphens converted to underscores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json


def _norm_key(key: str) -> str:
    return key.replace("-", "_").lower()


def _normalize(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        nk = _norm_key(str(k))
        if isinstance(v, dict):
            out[nk] = _normalize(v)
        else:
            out[nk] = v
    return out


def load_config_file(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    suf = p.suffix.lower()
    if suf == ".toml":
        import tomllib  # Python 3.11+

        data = tomllib.loads(p.read_text(encoding="utf-8"))
        return _normalize(data)
    if suf in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore
        except Exception as e:  # pragma: no cover - optional dep
            raise RuntimeError("PyYAML is required to read YAML config files") from e
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("YAML config must be a mapping at the top level")
        return _normalize(data)
    if suf == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON config must be an object at the top level")
        return _normalize(data)
    raise ValueError(f"Unsupported config extension: {suf}")
