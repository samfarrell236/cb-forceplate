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
    """Persist newly uploaded exports. `seen` tracks (name,size) already saved.

    Excel exports (.xlsx/.xls) are converted to CSV on the way in so the rest of
    the pipeline only ever deals with CSV.
    """
    STORE.mkdir(parents=True, exist_ok=True)
    saved = 0
    for uf in uploads:
        key = (uf.name, uf.size)
        if key in seen:
            continue
        name = Path(uf.name).name
        if name.lower().endswith((".xlsx", ".xls")):
            import io
            import pandas as pd
            df = pd.read_excel(io.BytesIO(uf.getbuffer()), dtype=str)
            (STORE / (Path(name).stem + ".csv")).write_text(
                df.to_csv(index=False), encoding="utf-8-sig")
        else:
            (STORE / name).write_bytes(uf.getbuffer())
        seen.add(key)
        saved += 1
    return saved


def clear() -> None:
    for p in files():
        p.unlink(missing_ok=True)
