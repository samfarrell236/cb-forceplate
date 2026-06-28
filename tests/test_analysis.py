"""Unit tests for the analysis + loader layers. Run: pytest -q"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import normative as norm, asymmetry as asym, grouping  # noqa: E402
from vald import schema, loader  # noqa: E402


# --- percentile interpolation ----------------------------------------------
def test_percentiles_linear_interpolation():
    vals = [10, 20, 30, 40]
    pc = norm.percentiles(vals, qs=(25, 50, 75))
    assert pc[50] == pytest.approx(25.0)        # median of 4 evenly spaced
    assert pc[25] == pytest.approx(17.5)
    assert pc[75] == pytest.approx(32.5)


def test_percentile_of_direction():
    vals = [10, 20, 30, 40, 50]
    # higher-is-better: 50 is top
    assert norm.percentile_of(50, vals, "higher") == pytest.approx(90.0)
    # lower-is-better: 10 is top -> high percentile
    assert norm.percentile_of(10, vals, "lower") == pytest.approx(90.0)
    # closer-to-zero: 10 (smallest magnitude) ranks best
    assert norm.percentile_of(10, vals, "zero") == pytest.approx(90.0)


# --- z-score sign -----------------------------------------------------------
def test_zscore_sign_and_value():
    assert norm.zscore(12, 10, 2) == pytest.approx(1.0)
    assert norm.zscore(8, 10, 2) == pytest.approx(-1.0)
    assert np.isnan(norm.zscore(8, 10, 0))      # zero SD -> nan, not div0


def test_z_band_respects_direction():
    assert norm.z_band(1.0, "higher") == "go"
    assert norm.z_band(1.0, "lower") == "backoff"   # high value bad when lower better
    assert norm.z_band(-1.0, "lower") == "go"
    assert norm.z_band(1.5, "zero") == "backoff"     # big magnitude bad
    assert norm.z_band(0.2, "zero") == "go"


# --- group-stat aggregation -------------------------------------------------
def test_group_stats():
    s = norm.group_stats([10, 12, 14, 16, 18])
    assert s["n"] == 5
    assert s["mean"] == pytest.approx(14.0)
    assert s["sd"] == pytest.approx(np.std([10, 12, 14, 16, 18], ddof=1))
    assert s["min"] == 10 and s["max"] == 18
    assert s["cv"] == pytest.approx(s["sd"] / 14.0 * 100)


def test_group_stats_empty():
    s = norm.group_stats([])
    assert s["n"] == 0 and np.isnan(s["mean"])


# --- age-at-test banding ----------------------------------------------------
def test_band_uses_actual_age_at_test_when_dob_known():
    dob = pd.Timestamp("2007-09-15")
    # before the birthday in 2025 the athlete is still 17 -> U17
    assert grouping.fiba_band(2007, pd.Timestamp("2025-03-01"), dob) == "U17"
    # after the birthday they are 18 -> U18 (the jump is tied to age-at-time)
    assert grouping.fiba_band(2007, pd.Timestamp("2025-10-01"), dob) == "U18"
    # the same jump, banded by turn-age only (no dob), would read a year higher
    assert grouping.fiba_band(2007, pd.Timestamp("2025-03-01")) == "U18"


def test_band_cutoffs_and_fallbacks():
    # senior cutoff + youth floor (using actual age via dob)
    assert grouping.fiba_band(2000, pd.Timestamp("2026-06-01"),
                              pd.Timestamp("2000-01-01")) == "Senior"   # 26
    assert grouping.fiba_band(2004, pd.Timestamp("2026-06-01"),
                              pd.Timestamp("2004-01-01")) == "U22"
    assert grouping.fiba_band(2015, pd.Timestamp("2026-06-01"),
                              pd.Timestamp("2015-01-01")) == "U14"      # 11 -> floor
    # birth-year-only fallback still works
    assert grouping.fiba_band(2004, pd.Timestamp("2026-01-01")) == "U22"
    # missing everything
    assert grouping.fiba_band(None, pd.Timestamp("2026-01-01")) is None
    assert grouping.fiba_band(2007, pd.NaT) is None


def test_fiba_band_sort_order():
    bands = ["Senior", "U16", "U22", "Unknown", "U14"]
    assert grouping.sort_bands(bands) == ["U14", "U16", "U22", "Senior", "Unknown"]


def test_apply_grouping_age_band_per_reading():
    # one athlete, two tests in different calendar years crossing a band boundary
    df = pd.DataFrame({
        "athlete": ["A", "A"], "dob": pd.to_datetime(["2007-05-01", "2007-05-01"]),
        "birth_year": pd.array([2007, 2007], dtype="Int64"),
        "group": [pd.NA, pd.NA], "test_type": ["CMJ", "CMJ"],
        "test_date": pd.to_datetime(["2024-03-01", "2026-06-15"]),
        "metric": ["Jump Height", "Jump Height"], "value": [30.0, 40.0],
        "unit": ["cm", "cm"], "side": [None, None],
    })
    # actual age at each test (dob 2007-05-01): 2024-03-01 -> 16, 2026-06-15 -> 19
    out = grouping.apply_grouping(df, "age_band")
    assert list(out["group"]) == ["U16", "U19"]   # same athlete, two bands
    rep = norm.representative_values(out, "Jump Height", "latest")
    assert set(rep["group"]) == {"U16", "U19"}     # one rep value per band


def test_apply_grouping_unknown_when_no_birth_year():
    df = pd.DataFrame({
        "athlete": ["B"], "dob": [pd.NaT], "birth_year": pd.array([pd.NA], dtype="Int64"),
        "group": [pd.NA], "test_type": ["CMJ"], "test_date": pd.to_datetime(["2026-01-01"]),
        "metric": ["Jump Height"], "value": [35.0], "unit": ["cm"], "side": [None],
    })
    out = grouping.apply_grouping(df, "age_band")
    assert out["group"].iloc[0] == grouping.UNKNOWN_BAND


def test_parse_birth_year_formats():
    assert schema.parse_birth_year("2003-11-26") == 2003
    assert schema.parse_birth_year("11/26/2003") == 2003
    assert schema.parse_birth_year("c. 2007") == 2007
    assert schema.parse_birth_year("1998") == 1998
    assert schema.parse_birth_year("") is None
    assert schema.parse_birth_year(None) is None


# --- asymmetry parsing + flagging ------------------------------------------
def test_parse_asymmetry_sides():
    assert schema.parse_asymmetry("1.4 R") == (1.4, "R")
    assert schema.parse_asymmetry("16 L") == (-16.0, "L")
    assert schema.parse_asymmetry("0 ") == (0.0, None)
    assert schema.parse_asymmetry("") == (None, None)
    assert schema.parse_asymmetry("7.5") == (7.5, None)  # numeric (future API)


def test_scaled_score_anchors():
    vals = [10, 20, 30, 40, 50]  # mean 30
    assert norm.scaled_score(30, vals, "higher") == pytest.approx(50.0)   # mean -> 50
    assert norm.scaled_score(50, vals, "higher") == pytest.approx(100.0)  # best -> 100
    assert norm.scaled_score(10, vals, "higher") == pytest.approx(0.0)    # worst -> 0
    # lower-is-better inverts: smallest value is best
    assert norm.scaled_score(10, vals, "lower") == pytest.approx(100.0)
    assert norm.scaled_score(50, vals, "lower") == pytest.approx(0.0)


def test_athlete_value_bases():
    import pandas as _pd
    from analysis import athlete as _ath
    df = _pd.DataFrame({
        "athlete": ["A"] * 3, "dob": [_pd.NaT] * 3, "group": ["G"] * 3,
        "test_type": ["CMJ"] * 3,
        "test_date": _pd.to_datetime(["2026-01-01", "2026-06-01", "2026-06-20"]),
        "metric": ["Jump Height"] * 3, "value": [30.0, 40.0, 44.0],
        "unit": ["cm"] * 3, "side": [None] * 3,
    })
    assert _ath._athlete_value(df, "A", "Jump Height", "latest") == 44.0
    assert _ath._athlete_value(df, "A", "Jump Height", "alltime") == 38.0  # mean of all
    # recent (last 30d before latest = 2026-06-20) covers Jun 1 + Jun 20
    assert _ath._athlete_value(df, "A", "Jump Height", "recent", 30) == 42.0


def test_best_fit_slope_direction():
    import pandas as _pd
    dates = _pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
    bf = norm.best_fit(dates, [10, 12, 14])  # rising
    assert bf is not None
    assert bf[1][1] > bf[1][0]               # end higher than start
    assert norm.best_fit(dates[:1], [10]) is None  # too few points


def test_deficit_band_thresholds():
    assert norm.deficit_band(-5) == "go"      # surplus
    assert norm.deficit_band(0.5) == "go"
    assert norm.deficit_band(1) == "maintain"
    assert norm.deficit_band(9.9) == "maintain"
    assert norm.deficit_band(10) == "caution"
    assert norm.deficit_band(14.9) == "caution"
    assert norm.deficit_band(15) == "backoff"
    assert norm.deficit_band(40) == "backoff"
    assert norm.deficit_band(float("nan")) == "go"


def test_value_deficit_directions():
    # higher-better: 10% below mean -> 10% deficit
    assert norm.value_deficit(90, 100, "higher") == pytest.approx(10.0)
    assert norm.value_deficit(110, 100, "higher") == pytest.approx(-10.0)  # surplus
    # lower-better: above the reference is the deficit
    assert norm.value_deficit(110, 100, "lower") == pytest.approx(10.0)
    # asymmetry: the magnitude is the deficit (no reference needed)
    assert norm.value_deficit(12, None, "zero") == pytest.approx(12.0)


def test_metric_direction_defaults():
    assert norm.metric_direction("Jump Height (Imp-Mom)") == "higher"
    assert norm.metric_direction("Peak Landing Force") == "lower"
    assert norm.metric_direction("Concentric Impulse % (Asym)") == "zero"


def test_flag_asymmetries_threshold():
    df = pd.DataFrame({
        "athlete": ["A", "B"], "dob": [pd.NaT, pd.NaT], "group": ["G", "G"],
        "test_type": ["CMJ", "CMJ"], "test_date": pd.to_datetime(["2026-01-01", "2026-01-01"]),
        "metric": ["Concentric Impulse % (Asym)"] * 2,
        "value": [4.0, 16.0], "unit": ["%", "%"], "side": ["R", "L"],
    })
    out = asym.flag_asymmetries(df, threshold=10)
    flagged = dict(zip(out["athlete"], out["flagged"]))
    assert flagged["A"] is False and flagged["B"] is True


def test_recent_asymmetry_flags_rules():
    metric = "Concentric Impulse % (Asym)"
    base = dict(dob=pd.NaT, group="G", test_type="CMJ", metric=metric,
                unit="%")
    rows = [
        # A: stable low asymmetry -> not flagged
        dict(athlete="A", test_date="2026-06-01", value=4.0, side="R"),
        dict(athlete="A", test_date="2026-06-20", value=5.0, side="R"),
        # B: latest over 15% -> flagged on the absolute rule
        dict(athlete="B", test_date="2026-06-01", value=16.0, side="L"),
        dict(athlete="B", test_date="2026-06-20", value=18.0, side="L"),
        # C: under 15% but a >=10pt jump from the 30-day average -> flagged on change
        dict(athlete="C", test_date="2026-06-01", value=2.0, side="R"),
        dict(athlete="C", test_date="2026-06-20", value=14.0, side="R"),
    ]
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["test_date"] = pd.to_datetime(df["test_date"])
    out = asym.recent_asymmetry_flags(df, abs_threshold=15, change_threshold=10)
    f = dict(zip(out["athlete"], out["flagged"]))
    why = dict(zip(out["athlete"], out["reason"]))
    assert f["A"] is False
    assert f["B"] is True and "over 15%" in why["B"]
    assert f["C"] is True and "shift" in why["C"]


# --- loader round-trips a wide VALD export with group + DOB ------------------
def test_wide_export_round_trip():
    import io
    csv = (
        "Name,Test Type,Group,Date of Birth,Date,Time,BW [KG],"
        "Jump Height (Imp-Mom) [cm],Concentric Impulse % (Asym) (%)\n"
        "Liam Roy,CMJ,U18 Men,2008/05/02,2026/01/10,10:00 AM,78.4,38.2,4.1 R\n"
        "Noah Cote,CMJ,Senior Men,2003/03/11,2026/01/12,11:00 AM,92.1,45.6,12.0 L\n"
    )
    tidy = loader.get_tests(io.StringIO(csv))
    assert not tidy.empty
    assert set(schema.TIDY_COLUMNS) == set(tidy.columns)
    assert tidy["test_type"].eq("CMJ").all()
    # asymmetry metric present, signed, with sides
    asy = tidy[tidy["metric"].str.contains("Asym")]
    assert not asy.empty
    assert set(asy["side"].dropna()) <= {"L", "R"}
    # groups + dob survived
    assert tidy["group"].notna().any()
    assert tidy["dob"].notna().any()


# --- VALD-format reading: sentinels, junk profiles, same-day re-tests -------
def test_is_junk_name():
    assert schema.is_junk_name("Tests Test")
    assert schema.is_junk_name("Test 1")
    assert schema.is_junk_name("test")
    assert schema.is_junk_name("")
    assert not schema.is_junk_name("Brett Dobson")
    assert not schema.is_junk_name("Tester Q. Athlete")  # 'test' not a whole word
    assert not schema.is_junk_name("Isaiah Eniojukan")


def test_minus_one_sentinel_and_nonpositive_nulled():
    import io
    csv = (
        "Name,Test Type,Date,Time,BW [KG],Jump Height (Imp-Mom) [cm]\n"
        "Real One,CMJ,2026/01/01,10:00 AM,-1,40\n"      # BW sentinel -> missing
        "Real Two,CMJ,2026/01/01,10:00 AM,80,0\n"        # JH 0 -> invalid trial
        "Real Three,CMJ,2026/01/01,10:00 AM,82,42\n"
    )
    tidy = loader.get_tests(io.StringIO(csv))
    bw = tidy[tidy["metric"].str.contains("BW", case=False)]
    assert (bw["value"] > 0).all()            # the -1 BW was dropped
    jh = tidy[tidy["metric"].str.contains("Jump Height")]
    assert (jh["value"] > 0).all()            # the 0 jump height was dropped
    assert tidy.attrs["load_notes"]["values_nulled_sentinel"] >= 1
    assert tidy.attrs["load_notes"]["values_nulled_nonpositive"] >= 1


def test_same_day_retests_preserved():
    import io
    csv = (
        "Name,Test Type,Date,Time,Jump Height (Imp-Mom) [cm]\n"
        "A Athlete,CMJ,2026/04/03,2:23 PM,42.4\n"
        "A Athlete,CMJ,2026/04/03,4:15 PM,34.6\n"   # same day, different session
    )
    tidy = loader.get_tests(io.StringIO(csv))
    jh = tidy[tidy["metric"].str.contains("Jump Height")]
    assert len(jh) == 2                         # both kept, not collapsed
    assert jh["test_date"].nunique() == 2       # distinct timestamps


def test_junk_profiles_excluded_with_notes():
    import io
    csv = (
        "Name,Test Type,Date,Time,Jump Height (Imp-Mom) [cm]\n"
        "Tests Test,CMJ,2026/01/01,10:00 AM,30\n"
        "Real Athlete,CMJ,2026/01/01,10:00 AM,40\n"
    )
    tidy = loader.get_tests(io.StringIO(csv), exclude_junk=True)
    assert set(tidy["athlete"]) == {"Real Athlete"}
    assert "Tests Test" in tidy.attrs["load_notes"]["excluded_profiles"]
    # opt-out keeps them
    keep = loader.get_tests(io.StringIO(csv), exclude_junk=False)
    assert "Tests Test" in set(keep["athlete"])
