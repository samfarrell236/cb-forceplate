"""Settings page — data source, column mapping, and global analysis config.

Widget values persist in session_state under stable keys (set_*, map_*) and are
read back by app.py to drive every analysis page.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from vald import loader
from ui import components as C, theme as T
import store


def render(sctx):
    df = sctx.df  # may be None if no data yet

    # --- Data source --------------------------------------------------------
    C.section_label("database", "Data source")
    st.caption("Your dataset is saved locally and loads automatically each visit. "
               "Add exports any time — they are merged and de-duplicated.")
    uploads = st.file_uploader("Add VALD ForceDecks export(s) — CSV or Excel",
                               type=["csv", "xlsx", "xls"],
                               accept_multiple_files=True, key="set_uploader")
    if uploads:
        n = store.save(uploads, st.session_state.setdefault("_saved_uploads", set()))
        if n:
            st.success(f"Added {n} file(s) to your dataset.")
            st.rerun()

    stored = store.files()
    if stored:
        cols = st.columns([3, 1])
        with cols[0]:
            for p in stored:
                st.markdown(f'{T.icon("check", 13, T.GO)} <span class="cb-chip">{p.name}</span>',
                            unsafe_allow_html=True)
        with cols[1]:
            if st.button("Clear dataset", width="stretch"):
                store.clear()
                st.session_state.pop("_saved_uploads", None)
                st.rerun()
    else:
        st.info("No data yet — add a VALD export above to begin.")
        return

    if df is None or df.empty:
        return

    st.markdown("---")

    # --- Analysis configuration --------------------------------------------
    C.section_label("chart", "Analysis configuration")
    a, b = st.columns(2)
    with a:
        _radio("set_rep", "Representative value per athlete",
               ["Latest", "Best", "Mean"], default="Latest")
        st.caption("Test type and grouping (incl. FIBA age bands) are chosen on "
                   "each page — Overview, Individual, Team & Groups.")
    with b:
        _radio("set_scoring", "Scoring display", ["Z-score", "Scaled 0–100"],
               default="Z-score",
               help="Scaled = Hawkin modified z: 50 = group mean, 100 = best, 0 = worst.")
        _slider("set_threshold", "Asymmetry flag threshold (%)", 5, 20, 10)
        if "set_exclude" not in st.session_state:
            st.session_state["set_exclude"] = True
        st.toggle("Exclude test/demo profiles", key="set_exclude",
                  help="Drop VALD placeholder profiles (e.g. 'Tests Test').")

    # --- Overview latest-tests metric columns ------------------------------
    st.markdown("---")
    C.section_label("trend", "Overview · Latest-tests metric columns")
    st.caption("The three metrics shown in the Overview's Latest-tests table "
               "(metric 1 also drives the Overview KPI tile, leaderboard and trend).")
    dt = "CMJ" if "CMJ" in (df["test_type"].unique()) else df["test_type"].iloc[0]
    ovm = C.ordered_perf_metrics(
        sorted(df[df["test_type"] == dt]["metric"].dropna().unique()))
    if ovm:
        mc = st.columns(3)
        for i, key in enumerate(("set_ov_m1", "set_ov_m2", "set_ov_m3")):
            with mc[i]:
                _select(key, f"Metric {i + 1}", ovm,
                        default=ovm[i] if i < len(ovm) else ovm[0])

    # --- Column mapping -----------------------------------------------------
    with st.expander("Column mapping (override auto-detect)", expanded=False):
        st.caption("Detected from the export headers. Override only if a column is wrong.")
        try:
            headers = [h.strip() for h in
                       pd.read_csv(stored[0], nrows=0, encoding="utf-8-sig").columns]
        except Exception:
            headers = []
        detected = loader.detect_mapping(str(stored[0]))
        for field in ("athlete", "test_date", "test_type", "group", "dob"):
            opts = ["(auto)"] + headers
            cur = st.session_state.get(f"map_{field}", "(auto)")
            idx = opts.index(cur) if cur in opts else 0
            st.selectbox(f"{field}  ·  auto: {detected.get(field) or 'none'}",
                         opts, index=idx, key=f"map_{field}")

    # --- Dataset summary ----------------------------------------------------
    st.markdown("---")
    C.section_label("database", "Dataset summary")
    k = st.columns(4)
    with k[0]:
        C.tile("Athletes", str(df["athlete"].nunique()), "", "in dataset")
    with k[1]:
        C.tile("Readings", f"{len(df):,}", "", "metric values")
    with k[2]:
        C.tile("Files", str(len(stored)), "", "in store")
    with k[3]:
        last = df["test_date"].max()
        C.tile("Latest", last.strftime("%b %d") if pd.notna(last) else "—", "",
               last.strftime("%Y") if pd.notna(last) else "")
    ln = sctx.load_notes or {}
    bits = []
    if ln.get("rows_excluded"):
        bits.append(f"{ln['rows_excluded']} test/demo rows excluded")
    nulled = ln.get("values_nulled_sentinel", 0) + ln.get("values_nulled_nonpositive", 0)
    if nulled:
        bits.append(f"{nulled} invalid readings cleaned (-1 / non-positive)")
    if ln.get("excluded_profiles"):
        bits.append("excluded: " + ", ".join(ln["excluded_profiles"][:6]))
    if bits:
        st.caption(" · ".join(bits))


# --- widgets that persist via key -------------------------------------------
# When a key is already in session_state (seeded from disk), let the widget read
# it from there instead of also passing a default — avoids Streamlit's warning.
def _select(key, label, options, default=None, **kw):
    if not options:
        return
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]      # drop a persisted value invalid for this test
    if key in st.session_state:
        st.selectbox(label, options, key=key, **kw)
    else:
        idx = options.index(default) if default in options else 0
        st.selectbox(label, options, index=idx, key=key, **kw)


def _radio(key, label, options, default=None, **kw):
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]
    if key in st.session_state:
        st.radio(label, options, key=key, **kw)
    else:
        idx = options.index(default) if default in options else 0
        st.radio(label, options, index=idx, key=key, **kw)


def _slider(key, label, lo, hi, default, **kw):
    if key in st.session_state:
        st.slider(label, lo, hi, key=key, **kw)
    else:
        st.slider(label, lo, hi, default, key=key, **kw)
