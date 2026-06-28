"""Canonical schema + VALD header aliasing.

Everything downstream of the loader works on a single tidy/long DataFrame with
these canonical columns, so a future API loader only has to return the same
shape:

    athlete, dob, group, test_type, test_date, metric, value, unit, side

`side` is non-null only for asymmetry metrics (the dominant side, "L"/"R").
"""
from __future__ import annotations

import re

# --- Canonical tidy columns -------------------------------------------------
TIDY_COLUMNS = [
    "athlete",
    "dob",
    "birth_year",
    "group",
    "test_type",
    "test_date",
    "metric",
    "value",
    "unit",
    "side",
]

# --- Header aliases (lower-cased, stripped) ---------------------------------
# Maps a canonical meta field -> list of accepted header spellings. Matching is
# fuzzy: exact, then substring. The sidebar lets the user override.
META_ALIASES = {
    "athlete":    ["profile", "name", "athlete", "player"],
    "test_date":  ["date utc", "test date", "date"],
    "test_type":  ["test type", "test"],
    "group":      ["group", "squad", "team", "position"],
    "dob":        ["date of birth", "dob", "birth date"],
    "birth_year": ["birth year", "birthyear", "year of birth", "yob"],
}

# Meta columns that are never treated as metrics, even when numeric.
NON_METRIC_HEADERS = {
    "name", "profile", "athlete", "player",
    "externalid", "external id",
    "test type", "test",
    "date", "date utc", "test date",
    "time",
    "tags",
    "date of birth", "dob", "birth date", "birth year",
    "group", "squad", "team", "position",
    "reps",
    "additional load",
    "age", "height", "bio confidence",
}


def base_header(h: str) -> str:
    """Normalised header with unit/asym brackets removed — for meta matching."""
    s = _UNIT_RE.sub("", str(h))
    s = re.sub(r"\([^)]*\)", "", s)
    return norm_header(s)

# Bodyweight is kept as a metric (useful), but detected so we can also expose it
# as athlete context.
BODYWEIGHT_HEADERS = {"bw", "body weight", "bodyweight", "weight"}

_UNIT_RE = re.compile(r"\[([^\]]+)\]|\(([^)]*%)\)")
_ASYM_VALUE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([LR])?\s*$", re.IGNORECASE)

# VALD encodes a missing/un-calculated result as -1. Treat it as missing.
MISSING_SENTINEL = -1.0

# Force-plate performance metrics are strictly-positive magnitudes, so a value
# <= 0 is an invalid/failed trial. Exceptions are metrics that can legitimately
# be signed (e.g. countermovement depth/displacement) — those are left as-is.
SIGNED_OK_HINTS = ("depth", "displacement", "position", "velocity at")

# Header that carries clock time, combined with the date into a full timestamp
# so same-day re-tests stay distinct.
TIME_HEADERS = {"time", "test time", "time utc"}

# Demo / test placeholder profiles seeded in VALD Hub that aren't real athletes.
_JUNK_NAME_RE = re.compile(
    r"^\s*(tests?|demo|sample|delete|dummy|vald|admin|asdf|xxx+)\b"
    r"|^\s*test\s*\d*\s*$",
    re.IGNORECASE,
)


_YEAR_RE = re.compile(r"(19|20)\d{2}")


def parse_birth_year(raw) -> int | None:
    """Extract a 4-digit birth year from a DOB / Birth Year cell.

    Handles 'YYYY-MM-DD', 'YYYY/MM/DD', 'MM/DD/YYYY', 'DD/MM/YYYY', bare 'YYYY',
    and approximate 'c. YYYY' (the 'c.' prefix is dropped). Returns None if no
    plausible year is present.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in {"nan", "na", "none", "-"}:
        return None
    m = _YEAR_RE.search(s.replace("c.", " "))
    if not m:
        return None
    y = int(m.group(0))
    return y if 1900 <= y <= 2100 else None


def is_junk_name(name) -> bool:
    """True for VALD demo/test placeholder profiles (not real athletes)."""
    s = str(name).strip()
    if not s or s.lower() == "nan":
        return True
    return bool(_JUNK_NAME_RE.match(s))


def signed_ok(metric: str) -> bool:
    """True if a metric can legitimately be <= 0 (don't null its non-positives)."""
    m = str(metric).lower()
    return any(h in m for h in SIGNED_OK_HINTS)


def norm_header(h: str) -> str:
    """Lower-case, collapse whitespace, strip trailing units for matching."""
    return re.sub(r"\s+", " ", str(h)).strip().lower()


def parse_unit(header: str) -> str:
    """Pull a unit out of a header: 'Peak Power [W]' -> 'W', '... (%)' -> '%'."""
    m = _UNIT_RE.search(str(header))
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


def clean_metric_name(header: str) -> str:
    """Human-readable metric label: drop the unit bracket, tidy spacing.

    Keeps asymmetry identifiable — '(Asym)' becomes 'Asymmetry' so downstream
    direction detection still recognises it from the metric name alone.
    """
    name = _UNIT_RE.sub("", str(header))
    name = re.sub(r"\(asym[a-z]*\)", "Asymmetry", name, flags=re.IGNORECASE)
    name = name.replace("%", "")
    return re.sub(r"\s+", " ", name).strip()


def is_asymmetry_header(header: str) -> bool:
    h = norm_header(header)
    return "asym" in h or "asymmetry" in h or "l:r" in h or "left:right" in h


def parse_asymmetry(raw) -> tuple[float | None, str | None]:
    """Parse VALD side-coded asymmetry cells.

    Real export stores asymmetry as a magnitude plus a dominant-side letter,
    e.g. ``"1.4 R"``, ``"16 L"``, ``"0 "``. We return a *signed* value using
    the convention **R = positive, L = negative**, and the side letter. Sign is
    only directional; thresholds use the magnitude (see analysis.asymmetry).

    Returns (signed_value, side) or (None, None) if unparseable.
    """
    if raw is None:
        return None, None
    s = str(raw).strip()
    if s == "" or s.lower() in {"nan", "na", "-"}:
        return None, None
    m = _ASYM_VALUE_RE.match(s)
    if not m:
        # Already-numeric exports (future API) fall through to plain float.
        try:
            return float(s), None
        except ValueError:
            return None, None
    mag = float(m.group(1))
    side = (m.group(2) or "").upper() or None
    if side == "L":
        return -mag, "L"
    return mag, side  # R or no side -> positive / unsigned


def detect_meta(headers: list[str]) -> dict[str, str | None]:
    """Best-guess mapping canonical meta field -> actual header. None if absent."""
    normalized = {norm_header(h): h for h in headers}
    out: dict[str, str | None] = {}
    for field, aliases in META_ALIASES.items():
        found = None
        # exact first
        for alias in aliases:
            if alias in normalized:
                found = normalized[alias]
                break
        # then substring
        if found is None:
            for alias in aliases:
                for nh, orig in normalized.items():
                    if alias in nh:
                        found = orig
                        break
                if found:
                    break
        out[field] = found
    return out
