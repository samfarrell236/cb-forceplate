"""Grouping helpers.

Age banding uses the **FIBA birth-year method**: an athlete's category in a given
calendar year is the age they *turn* that year, so banding is done **per test
reading** (not once per athlete). An athlete tested across two calendar years can
fall in two bands. Example: born 2007 → tested 2024 = U17, tested 2026 = U19.
"""
from __future__ import annotations

import pandas as pd

# Tunable cutoffs -- trivially changeable.
SENIOR_MIN_AGE = 23     # turn-age >= this -> "Senior"
YOUTH_FLOOR_AGE = 14    # clamp anything younger to U14

UNKNOWN_BAND = "Unknown"


def fiba_band(birth_year, test_date, dob=None) -> str | None:
    """Age band for ONE reading, tied to the athlete's age at that test.

    Uses the athlete's **actual age on the test date** when a full DOB is known
    (e.g. a jump performed while 18 → 'U18'). Falls back to the birth-year
    turn-age (testYear − birthYear) when only a birth year is available, and is
    None when neither is known.
    """
    if pd.isna(test_date):
        return None
    if dob is not None and pd.notna(dob):
        age = age_at(dob, test_date)            # actual age at the jump
    elif birth_year is not None and pd.notna(birth_year):
        age = pd.Timestamp(test_date).year - int(birth_year)   # fallback
    else:
        return None
    if age is None:
        return None
    age = int(age)
    if age >= SENIOR_MIN_AGE:
        return "Senior"
    return f"U{max(age, YOUTH_FLOOR_AGE)}"


def band_sort_key(band: str) -> int:
    """Order bands youngest -> oldest -> Senior -> Unknown."""
    if band == "Senior":
        return 900
    if band == UNKNOWN_BAND:
        return 1000
    try:
        return int(str(band).lstrip("U"))
    except ValueError:
        return 950


def sort_bands(bands) -> list[str]:
    return sorted(bands, key=band_sort_key)


def apply_grouping(df: pd.DataFrame, mode: str = "detected") -> pd.DataFrame:
    """Return a copy of the tidy frame with `group` set per `mode`.

    mode='detected' -> keep the loaded group column (e.g. position); fallback
                       'All Athletes' when no group column was present.
    mode='age_band' -> FIBA birth-year band per reading; readings with no birth
                       year become 'Unknown' (excluded from band selectors).
    mode='all'      -> single 'All Athletes' cohort.
    """
    out = df.copy()
    if mode == "age_band":
        out["group"] = [
            fiba_band(by, td, dob) or UNKNOWN_BAND
            for by, td, dob in zip(out["birth_year"], out["test_date"], out["dob"])
        ]
        return out
    if mode == "all" or out["group"].isna().all():
        out["group"] = "All Athletes"
    else:
        out["group"] = out["group"].fillna("Unassigned")
    return out


# --- legacy age-at-date helpers (kept for utility / tests) ------------------
def age_at(dob, on_date) -> float | None:
    """Whole years from dob to on_date (calendar age, not FIBA)."""
    if pd.isna(dob) or pd.isna(on_date):
        return None
    dob, on_date = pd.Timestamp(dob), pd.Timestamp(on_date)
    years = on_date.year - dob.year
    if (on_date.month, on_date.day) < (dob.month, dob.day):
        years -= 1
    return float(years)
