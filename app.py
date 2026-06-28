"""Canada Basketball — Force Plate Analytics.

Orchestration only: load the saved dataset, resolve config (set on the Settings
page, persisted in session_state), render the header nav, and dispatch to a page
in views/*. Page-specific selections live on their own pages. Math lives in
analysis/*, data access in vald/*, UI atoms in ui/components.py.
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import streamlit as st

from vald import loader
from analysis import grouping
from ui import theme as T
import views
import store

st.set_page_config(page_title="Canada Basketball · Force Plate",
                   page_icon=T.logo_icon_path() or "🍁", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(T.css(), unsafe_allow_html=True)

PAGES = ["Overview", "Individual", "Team & Groups", "Settings"]
DISPATCH = {"Overview": views.overview, "Individual": views.individual,
            "Team & Groups": views.team}

# keys whose values persist to disk across sessions (preferences + selections)
_PERSIST_EXTRA = ("active_test", "group_basis", "ov_cohort")


def _is_persist_key(k):
    return k.startswith("set_") or k.startswith("map_") or k in _PERSIST_EXTRA


# seed persisted settings into session_state once per session (before widgets)
if not st.session_state.get("_settings_loaded"):
    for k, v in store.load_settings().items():
        st.session_state.setdefault(k, v)
    st.session_state["_settings_loaded"] = True


def persist_settings():
    """Write current preference/selection values back to disk if they changed."""
    data = {k: v for k, v in st.session_state.items()
            if _is_persist_key(k) and isinstance(v, (str, int, float, bool))}
    if data != st.session_state.get("_settings_snapshot"):
        store.save_settings(data)
        st.session_state["_settings_snapshot"] = data


def header():
    st.markdown(
        f"""<div class="cb-head">
        <div class="cb-rail"></div>
        <div>{T.logo_html(36)}</div>
        <div class="cb-word">CANADA BASKETBALL <span class="thin">· FORCE PLATE</span></div>
        </div><hr class="cb-redrule"/>""",
        unsafe_allow_html=True,
    )


def sidebar_nav(active):
    """Vertical page nav in the sidebar; returns the active page key."""
    with st.sidebar:
        vald = T.asset_img("vald_logo.webp", 27)
        if vald:
            # Centre the whole CB × VALD lockup as one unit in the sidebar.
            st.markdown(
                f'<div style="display:flex;align-items:center;justify-content:center;'
                f'gap:13px;padding:6px 0 22px">'
                f'{T.logo_html(36)}'
                f'<span style="color:{T.INK_FAINT};font-size:18px;font-weight:300">×</span>'
                f'<div style="display:flex;margin-left:-9px">{vald}</div></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div style="display:flex;justify-content:center;padding:6px 0 22px">'
                f'{T.logo_html(36)}</div>', unsafe_allow_html=True)
        for label in PAGES:
            if st.button(label, key=f"nav_{label}", width="stretch",
                         type="primary" if label == active else "secondary"):
                st.session_state["page"] = label
                active = label
    return active


def footer(d):
    persist_settings()
    st.markdown(
        f'<div style="margin-top:40px;padding-top:14px;border-top:1px solid {T.RULE}">'
        f'<span class="cb-legend">Creator: Sam Farrell · Canada Basketball '
        f'athletes only · {d["athlete"].nunique()} athletes · {len(d):,} readings · '
        f'auto-loaded from your saved dataset</span></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _load(signature, paths, overrides, exclude_junk):
    return loader.get_tests(list(paths), dict(overrides) if overrides else None,
                            exclude_junk=exclude_junk)


# ---------------------------------------------------------------------------
header()
page = sidebar_nav(st.session_state.get("page", "Overview"))

stored = store.files()
if not stored:
    # No data yet → force the Settings page so the user can add an export.
    views.settings.render(SimpleNamespace(df=None, has_group=False, has_dob=False,
                                          load_notes={}))
    st.stop()

# --- load (config read from session_state, defaults until set on Settings) --
exclude_junk = st.session_state.get("set_exclude", True)
detected = loader.detect_mapping(str(stored[0]))
overrides = {}
for f in ("athlete", "test_date", "test_type", "group", "dob"):
    v = st.session_state.get(f"map_{f}")
    if v and v != "(auto)" and v != detected.get(f):
        overrides[f] = v

paths = [str(p) for p in stored]
df = _load(store.signature(stored), tuple(paths),
           tuple(sorted(overrides.items())) if overrides else None, exclude_junk)
load_notes = df.attrs.get("load_notes", {})
if df.empty:
    st.warning("No numeric metrics found. Check Settings → Column mapping.")
    views.settings.render(SimpleNamespace(df=df, has_group=False, has_dob=False,
                                          load_notes=load_notes))
    st.stop()

has_dob = df["dob"].notna().any()
has_birthyear = df["birth_year"].notna().any()
has_group = df["group"].notna().any()

# Settings page: data + config only; build a minimal context for it.
if page == "Settings":
    views.settings.render(SimpleNamespace(df=df, has_group=has_group, has_dob=has_dob,
                                          has_birthyear=has_birthyear, load_notes=load_notes))
    footer(df)
    st.stop()

# --- resolve config for analysis pages --------------------------------------
# default grouping = age bands when birth years exist, else position, else all
default_group = ("Age band (FIBA)" if has_birthyear
                 else "Detected group" if has_group else "All athletes")
mode_label = st.session_state.get("set_group_mode", default_group)
mode_key = ("age_band" if mode_label.startswith("Age")
            else "detected" if mode_label.startswith("Detected") else "all")
base = df  # ungrouped: retains detected group (position) + birth_year
df = grouping.apply_grouping(base, mode_key)

test_types = sorted(df["test_type"].dropna().unique())
default_test = "CMJ" if "CMJ" in test_types else (test_types[0] if test_types else None)
rep_how = st.session_state.get("set_rep", "Latest").lower()
scaled = st.session_state.get("set_scoring", "Z-score").startswith("Scaled")
threshold = int(st.session_state.get("set_threshold", 10))

notes = []
if mode_key == "age_band":
    n_unknown = df.loc[df["group"] == grouping.UNKNOWN_BAND, "athlete"].nunique()
    if n_unknown:
        notes.append(f"{n_unknown} athlete(s) without a birth year excluded from bands")
elif not has_birthyear:
    notes.append("Map a Date of Birth column in Settings → Column mapping "
                 "to enable age-band grouping")

ctx = SimpleNamespace(
    df=df, base=base, test_types=test_types, default_test=default_test,
    rep_how=rep_how, scaled=scaled, asym_threshold=threshold, has_group=has_group,
    has_dob=has_dob, has_birthyear=has_birthyear, mode_key=mode_key,
    banner=" · ".join(notes), load_notes=load_notes,
)
DISPATCH[page].render(ctx)
footer(df)
