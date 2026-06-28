# Canada Basketball — Force Plate Analytics

A courtside force-plate dashboard for Canada Basketball's S&C department. Ingests
VALD ForceDecks CSV exports, runs sports-science analysis within and across
athletes, and builds **pseudo-normative** reference data from Canada Basketball's
own athletes.

Dark, minimal "Edge"-style aesthetic in Canada Basketball red (`#C8102E`). Flat
stroke icons, no emoji.

```
pip install -r requirements.txt
streamlit run app.py
```

The app is **upload-only**: drop one or more VALD ForceDecks CSV exports into the
sidebar uploader to begin (multiple files are merged). No data is bundled.

**Branding:** put your licensed Canada Basketball logo at
`ui/assets/logo.png` (or `.svg`) and it appears in the header, sidebar, empty
state, and favicon. The official logo is trademarked and is not shipped with the
project — see `ui/assets/README.md`.

---

## What it does

Three+1 views (tabs):

1. **Normative profile** — per-group reference table (n, mean, SD, CV%, min, P25,
   median, P75, P90, max) + bar chart of group means with ±1 SD whiskers. Export
   to CSV.
2. **Athlete trend** — pick an athlete: time-series vs their group-mean line;
   headline tiles (latest/best/mean, n tests, group mean, z-score, percentile,
   status); a table of *all* metrics latest-vs-norm.
3. **Squad compare** — pick a group: horizontal athlete ranking coloured by
   z-band, with a dashed group-mean line.
4. **Asymmetry** — flags any L:R asymmetry metric whose magnitude exceeds a
   configurable threshold (default 10%).

All reference data is **pseudo-normative** — built from Canada Basketball
athletes, not an external population. The UI states this explicitly.

---

## VALD ForceDecks quirks the loader handles

Real VALD "Results Export" CSVs differ from a "textbook" export, and the loader
reads them correctly:

- **Date + Time → one timestamp**, so legitimate same-day re-tests stay distinct
  (a naive de-dup on athlete+date collapses them and loses data).
- **`-1` missing sentinel** → treated as missing on every metric (VALD writes
  `-1` for un-calculated results, e.g. bodyweight).
- **Non-positive force/impulse/height** → treated as failed trials and dropped
  (signed metrics like depth/displacement are exempt).
- **Test/demo placeholder profiles** (`Tests Test`, `Test 1`, …) → excluded by
  default; toggle in the sidebar, with the excluded count surfaced.
- **Side-coded asymmetry cells** like `"1.4 R"`, `"16 L"`, `"0 "` → parsed into a
  signed percentage (**R = +, L = −**) plus the dominant side. Thresholds use the
  magnitude; the sign is only directional.
- **No `Group` / `Date of Birth` columns** → the app pools every athlete into one
  cohort and says so; age-band / group logic activates automatically once those
  columns are present in the export.

All cleaning is **counted and shown** in the UI banner, never silent. The loader
is generic: every numeric column that isn't a known meta field becomes a metric
(with its `[unit]` parsed from the header), so IMTP / SJ / Drop Jump / hop-land
tests work with no code changes.

---

## Exporting from VALD Hub

VALD Hub → **Dashboard** → **Results Export** → **ForceDecks** → download the
(wide) CSV. The loader strips the BOM, handles quoted fields, auto-detects the
key columns (with a sidebar override), and concatenates multiple uploaded files.

Add `Group`/`Squad` and `Date of Birth` columns to the export to unlock
group-based and age-band (U16–Senior) normative grouping.

---

## Project structure

```
cb-forceplate/
  app.py                 # Streamlit UI only
  vald/
    schema.py            # canonical columns, header aliases, asymmetry parsing
    loader.py            # get_tests() -> tidy long DataFrame; VALD cleaning
    api.py               # STUB for VALD External ForceDecks API (documented, not wired)
  analysis/
    normative.py         # metric direction, group stats, z-scores, percentiles, scaled score
    athlete.py           # per-athlete trend, delta-vs-prev, profile scores
    asymmetry.py         # L:R asymmetry flagging
    grouping.py          # detected-group vs age-band-from-DOB
  ui/
    theme.py             # dark CB theme (CSS), flat SVG icons, logo, plotly layout
    assets/              # drop logo.png / logo.svg here (not bundled)
  tests/
    test_analysis.py     # pytest — analysis + VALD-format reading
  data/                  # empty — app is upload-only, no bundled data
  .streamlit/config.toml # dark theme + CB primary colour
```

**The architecture is the point:** data access (`vald/`) is separated from
analysis (`analysis/`) from UI (`app.py`). Everything downstream of the loader
works on one tidy/long DataFrame:

`athlete, dob, group, test_type, test_date, metric, value, unit, side`

So the data source can change without touching the analysis or UI.

---

## Tests

```
pytest -q
```

Covers percentile interpolation, z-score sign + zero-SD handling, direction-aware
z-banding, scaled-score anchors, best-fit slope, group-stat aggregation, age-band
bucketing + birthday boundary, side-coded asymmetry parsing, threshold flagging,
and VALD-format reading: `-1` sentinels, non-positive trials, junk-profile
exclusion, same-day re-test preservation, and a wide-export round-trip.

---

## Switching from CSV to the VALD API later

`vald/api.py` is a documented stub with the same `get_tests()` contract as the
CSV loader. When credentials arrive:

1. Set `VALD_CLIENT_ID` / `VALD_CLIENT_SECRET` (and region) in the environment or
   a `.env` file — **never hard-coded**.
2. Implement `_get_token()` (OAuth2 client-credentials), `_resolve_tenant()`
   (Tenants API → `tenantId`), and the `/tests?tenantId=…&modifiedFromUtc=…`
   paging + per-test results fetch.
3. Map results into the canonical tidy DataFrame (`schema.TIDY_COLUMNS`).
4. In `app.py`, change one import:
   ```python
   # from vald.loader import get_tests
   from vald.api import get_tests
   ```

No analysis or UI code changes — every view already speaks the tidy shape.

---

## Branding

Canada Basketball red `#C8102E` on near-black `#0a0a0a`, hairline `#262626`
rules, Saira Condensed display numerics, Inter body, JetBrains Mono for stat
captions. Flat (no rounded corners, no shadows), single red accent, flat inline
SVG icons. Status colours: green (above norm) / amber (within) / red (below),
direction-aware.
