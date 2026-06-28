"""Persistent local dataset store.

The app auto-loads every CSV here; uploads are saved into it (merged +
de-duplicated on load), so the user never re-uploads. Git-ignored (PII).
"""
from __future__ import annotations

import json
from pathlib import Path

STORE = Path(__file__).resolve().parent / "data" / "store"
SETTINGS_FILE = Path(__file__).resolve().parent / "data" / "settings.json"


def load_settings() -> dict:
    """Persisted user preferences (metric choices, scoring, thresholds, mapping)."""
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))


def files() -> list[Path]:
    return sorted(STORE.glob("*.csv")) if STORE.exists() else []


def signature(paths) -> tuple:
    """Cache key that changes when any stored file is added/updated/removed."""
    return tuple((p.name, p.stat().st_size, int(p.stat().st_mtime)) for p in paths)


def save(uploads, seen: set) -> int:
    """Persist newly uploaded exports. `seen` tracks (name,size) already saved."""
    STORE.mkdir(parents=True, exist_ok=True)
    saved = 0
    for uf in uploads:
        key = (uf.name, uf.size)
        if key in seen:
            continue
        (STORE / Path(uf.name).name).write_bytes(uf.getbuffer())
        seen.add(key)
        saved += 1
    return saved


def clear() -> None:
    for p in files():
        p.unlink(missing_ok=True)
