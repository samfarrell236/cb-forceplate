"""Data access layer.

`get_tests()` is the single entry point every view depends on. It returns one
tidy/long DataFrame in the canonical shape (see schema.TIDY_COLUMNS). Today it
reads VALD ForceDecks CSV exports; later, `vald.api` returns the same shape and
this module is swapped one line at a time.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

from . import schema


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_tests(
    sources: list[str | Path | io.BytesIO] | str | Path | io.BytesIO,
    overrides: dict[str, str] | None = None,
    exclude_junk: bool = True,
) -> pd.DataFrame:
    """Load one or more VALD CSV exports into a single tidy DataFrame.

    Parameters
    ----------
    sources : path(s) or file-like object(s) (e.g. Streamlit UploadedFile).
    overrides : optional {canonical_meta_field: header} to force the column map.
    exclude_junk : drop VALD demo/test placeholder profiles (default True).

    The returned frame carries cleaning stats in ``df.attrs['load_notes']``.
    """
    if not isinstance(sources, (list, tuple)):
        sources = [sources]
    results = [_load_one(src, overrides, exclude_junk) for src in sources]
    results = [r for r in results if r is not None and not r[0].empty]
    if not results:
        empty = pd.DataFrame(columns=schema.TIDY_COLUMNS)
        empty.attrs["load_notes"] = {}
        return empty

    tidy = pd.concat([r[0] for r in results], ignore_index=True)
    # De-dup TRUE duplicates only. test_date is a full timestamp (date + time),
    # so legitimate same-day re-tests have distinct timestamps and are kept.
    tidy = tidy.drop_duplicates(
        subset=["athlete", "test_type", "test_date", "metric", "side"]
    ).reset_index(drop=True)

    # merge per-file cleaning notes
    notes = {"excluded_profiles": [], "rows_excluded": 0,
             "values_nulled_sentinel": 0, "values_nulled_nonpositive": 0}
    for _, n in results:
        notes["excluded_profiles"] = sorted(
            set(notes["excluded_profiles"]) | set(n.get("excluded_profiles", [])))
        for k in ("rows_excluded", "values_nulled_sentinel", "values_nulled_nonpositive"):
            notes[k] += n.get(k, 0)
    # DOB / birth year is an athlete attribute — backfill within each athlete so
    # one tagged row covers all of that athlete's tests.
    if "birth_year" in tidy and tidy["birth_year"].notna().any():
        by = tidy.groupby("athlete")["birth_year"].transform(
            lambda s: s.dropna().iloc[0] if s.notna().any() else pd.NA)
        tidy["birth_year"] = by.astype("Int64")
    if "dob" in tidy and tidy["dob"].notna().any():
        tidy["dob"] = tidy.groupby("athlete")["dob"].transform(
            lambda s: s.dropna().iloc[0] if s.notna().any() else pd.NaT)

    tidy.attrs["load_notes"] = notes
    return tidy


def detect_mapping(source: str | Path | io.BytesIO) -> dict[str, str | None]:
    """Expose the auto-detected meta mapping so the UI can show / let edit it."""
    wide = _read_wide(source)
    return schema.detect_meta(list(wide.columns))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _read_wide(source) -> pd.DataFrame:
    """Read a raw export to a wide DataFrame. Strips BOM, handles quoting."""
    if hasattr(source, "read"):
        try:
            source.seek(0)
        except Exception:
            pass
        wide = pd.read_csv(source, dtype=str, encoding="utf-8-sig", skipinitialspace=False)
    else:
        wide = pd.read_csv(Path(source), dtype=str, encoding="utf-8-sig")
    # VALD headers carry trailing spaces ('Jump Height ... [cm] ') — normalise.
    wide.columns = [str(c).strip() for c in wide.columns]
    return wide


def _load_one(source, overrides: dict[str, str] | None,
              exclude_junk: bool = True) -> tuple[pd.DataFrame, dict] | None:
    """Parse one export -> (tidy DataFrame, cleaning-notes dict)."""
    wide = _read_wide(source)
    if wide.empty:
        return None

    headers = list(wide.columns)
    mapping = schema.detect_meta(headers)
    if overrides:
        mapping.update({k: v for k, v in overrides.items() if v})

    athlete_col = mapping.get("athlete")
    if athlete_col is None:
        raise ValueError(
            "Could not find an athlete/name column. Use the sidebar mapping "
            "override to point at the right column."
        )

    # --- meta columns -------------------------------------------------------
    athlete = wide[athlete_col].astype(str).str.strip()
    test_type = (
        wide[mapping["test_type"]].astype(str).str.strip()
        if mapping.get("test_type") else pd.Series(["Unknown"] * len(wide))
    )
    # date + time -> a single timestamp so same-day re-tests stay distinct
    time_col = next((h for h in headers if schema.norm_header(h) in schema.TIME_HEADERS), None)
    test_date = (
        _parse_datetime(wide[mapping["test_date"]],
                        wide[time_col] if time_col else None)
        if mapping.get("test_date") else pd.Series([pd.NaT] * len(wide))
    )
    group = (
        wide[mapping["group"]].astype(str).str.strip()
        if mapping.get("group") else pd.Series([np.nan] * len(wide))
    )
    dob = _parse_datetime(wide[mapping["dob"]]) if mapping.get("dob") else pd.Series([pd.NaT] * len(wide))
    # birth year: an explicit Birth Year column wins, else derive from DOB.
    if mapping.get("birth_year"):
        birth_year = wide[mapping["birth_year"]].map(schema.parse_birth_year)
    elif mapping.get("dob"):
        birth_year = wide[mapping["dob"]].map(schema.parse_birth_year)
    else:
        birth_year = pd.Series([None] * len(wide))

    meta = pd.DataFrame({
        "athlete": athlete,
        "dob": dob,
        "birth_year": pd.array(birth_year, dtype="Int64"),
        "group": group,
        "test_type": test_type,
        "test_date": test_date,
    })

    notes = {"excluded_profiles": [], "rows_excluded": 0,
             "values_nulled_sentinel": 0, "values_nulled_nonpositive": 0}

    # drop blank athletes; optionally drop VALD demo/test placeholder profiles
    valid = meta["athlete"].astype(bool) & (meta["athlete"].str.lower() != "nan")
    if exclude_junk:
        junk = meta["athlete"].map(schema.is_junk_name)
        notes["excluded_profiles"] = sorted(meta.loc[junk & valid, "athlete"].unique())
        notes["rows_excluded"] = int((junk & valid).sum())
        valid &= ~junk
    meta = meta[valid]
    if meta.empty:
        return pd.DataFrame(columns=schema.TIDY_COLUMNS), notes

    # --- metric columns: everything numeric that isn't a known meta column --
    used = {mapping.get(k) for k in
            ("athlete", "test_type", "test_date", "group", "dob", "birth_year")}
    used.add(time_col)
    metric_cols = [
        h for h in headers
        if h not in used and schema.base_header(h) not in schema.NON_METRIC_HEADERS
    ]

    long_rows = []
    for col in metric_cols:
        unit = schema.parse_unit(col)
        name = schema.clean_metric_name(col)
        raw = wide.loc[meta.index, col]

        if schema.is_asymmetry_header(col):
            parsed = raw.map(schema.parse_asymmetry)
            values = parsed.map(lambda t: t[0])
            sides = parsed.map(lambda t: t[1])
            unit = unit or "%"
        else:
            values = pd.to_numeric(
                raw.astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce",
            )
            # VALD missing sentinel (-1) -> NaN
            sentinel = values.eq(schema.MISSING_SENTINEL)
            notes["values_nulled_sentinel"] += int(sentinel.sum())
            values = values.mask(sentinel)
            # strictly-positive magnitudes: <= 0 is a failed trial
            if not schema.signed_ok(name):
                nonpos = values.le(0)
                notes["values_nulled_nonpositive"] += int(nonpos.sum())
                values = values.mask(nonpos)
            sides = pd.Series([None] * len(raw), index=raw.index)

        block = meta.copy()
        block["metric"] = name
        block["value"] = values.values
        block["unit"] = unit
        block["side"] = sides.values
        block = block[block["value"].notna()]
        if not block.empty:
            long_rows.append(block)

    if not long_rows:
        return pd.DataFrame(columns=schema.TIDY_COLUMNS), notes

    tidy = pd.concat(long_rows, ignore_index=True)[schema.TIDY_COLUMNS]
    return tidy, notes


def _parse_datetime(date_s: pd.Series, time_s: pd.Series | None = None) -> pd.Series:
    """Parse VALD date (+ optional clock time) into a timestamp.

    Dates are 'YYYY/MM/DD'; times are 12-hour like '4:15 PM'. Falling back to a
    generic parser keeps ISO 'Date UTC' exports working too.
    """
    d = date_s.astype(str).str.strip()
    if time_s is not None:
        combined = (d + " " + time_s.astype(str).str.strip()).str.strip()
        out = pd.to_datetime(combined, errors="coerce", format="%Y/%m/%d %I:%M %p")
        if out.notna().any():
            # rows whose time failed still get the date
            date_only = pd.to_datetime(d, errors="coerce", format="%Y/%m/%d")
            return out.fillna(date_only)
    out = pd.to_datetime(d, errors="coerce", format="%Y/%m/%d")
    if out.isna().all():
        out = pd.to_datetime(d, errors="coerce")
    return out
