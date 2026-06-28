"""Team / age-group / comparison page."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from analysis import normative as norm, asymmetry as asym, grouping
from ui import components as C, theme as T


def render(ctx):
    rep_how = ctx.rep_how

    C.section_label("users", "Team & groups")
    if ctx.banner:
        st.caption(ctx.banner)

    # --- page controls: test + group-by + metric --------------------------
    cc = st.columns([1.3, 1.6, 2])
    with cc[0]:
        test_type, metrics = C.test_picker(ctx.base, ctx.test_types, ctx.default_test)
    with cc[1]:
        gmode = C.group_picker(ctx)
    tdf = C.scoped_tdf(ctx, test_type, gmode)
    by_band = gmode == "age_band"
    with cc[2]:
        metric, unit, direction, _ = C.metric_picker(tdf, metrics, "team_metric")

    rep = norm.representative_values(tdf, metric, rep_how)
    rep["group"] = rep["group"].fillna("All Athletes")
    present = list(rep["group"].unique())
    if by_band:
        groups = [g for g in grouping.sort_bands(present) if g != grouping.UNKNOWN_BAND]
        default = groups
    else:
        groups = sorted(present)
        default = groups[: min(6, len(groups))]
    chosen = st.multiselect("Groups to compare", groups, default=default,
                            help="Compare age bands / squads / positions side by side.")
    if by_band:
        nu = tdf.loc[tdf["group"] == grouping.UNKNOWN_BAND, "athlete"].nunique()
        if nu:
            st.caption(f"{nu} athlete(s) without a birth year are excluded from age bands.")
    if not chosen:
        st.info("Select at least one group.")
        return
    sub = rep[rep["group"].isin(chosen)]

    # --- normative table ----------------------------------------------------
    ntab = _normative(sub, order=chosen)
    st.dataframe(ntab.style.format({c: "{:.1f}" for c in ntab.columns
                                    if c not in ("Group", "n")}),
                 width="stretch", hide_index=True)
    st.download_button("Export normative table (CSV)", ntab.to_csv(index=False).encode(),
                       file_name=f"normative_{test_type}_{metric}.csv".replace(" ", "_"))

    # --- group means ±SD + distribution -------------------------------------
    a, b = st.columns([1, 1])
    with a:
        C.section_label("chart", "Group means ±1 SD")
        means = sub.groupby("group")["value"].agg(["mean", "std"]).reindex(chosen)
        fig = go.Figure()
        fig.add_bar(x=means.index, y=means["mean"],
                    error_y=dict(type="data", array=means["std"], color=T.INK_MUTED, thickness=1),
                    marker_color=T.RED, marker_line_width=0,
                    hovertemplate="%{x}<br>mean %{y:.1f} " + unit + "<extra></extra>")
        fig.update_layout(**T.plotly_layout(height=360,
                          yaxis_title=f"{metric} [{unit}]" if unit else metric))
        C.show_chart(fig)
    with b:
        C.section_label("chart", "Distribution by group")
        fig = go.Figure()
        for grp in chosen:
            vals = sub[sub["group"] == grp]["value"]
            fig.add_box(y=vals, name=grp, marker_color=T.RED, line_color=T.INK_MUTED,
                        boxpoints="all", jitter=0.4, pointpos=0,
                        marker=dict(size=4, opacity=0.6),
                        hovertemplate="%{y:.1f} " + unit + "<extra></extra>")
        fig.update_layout(**T.plotly_layout(height=360, showlegend=False,
                          yaxis_title=f"{metric} [{unit}]" if unit else metric))
        C.show_chart(fig)

    st.markdown("---")

    # --- within-group ranking / quadrant ------------------------------------
    one = st.selectbox("Drill into group", chosen, key="team_one")
    view_mode = st.radio("View", ["Ranking", "Quadrant"], horizontal=True, key="team_view")
    g = sub[sub["group"] == one]

    if g.empty:
        st.info("No athletes in this group.")
    elif view_mode == "Ranking":
        C.show_chart(C.ranking_chart(g, metric, unit, direction))
        C.legend_bands()
    else:
        ymetrics = [m for m in metrics if m != metric]
        ymetric = st.selectbox("Y-axis metric", ymetrics,
                               index=min(1, len(ymetrics) - 1) if ymetrics else 0,
                               key="team_quad_y")
        ry = norm.representative_values(tdf, ymetric, rep_how)
        merged = g.merge(ry[["athlete", "value"]], on="athlete", suffixes=("_x", "_y"))
        if merged.empty:
            st.info("Not enough overlapping data for a quadrant.")
        else:
            mx, my = merged["value_x"].mean(), merged["value_y"].mean()
            fig = go.Figure()
            fig.add_vline(x=mx, line=dict(color=T.RULE, width=1))
            fig.add_hline(y=my, line=dict(color=T.RULE, width=1))
            fig.add_scatter(x=merged["value_x"], y=merged["value_y"], mode="markers+text",
                            text=merged["athlete"], textposition="top center",
                            textfont=dict(color=T.INK_MUTED, size=9),
                            marker=dict(color=T.RED, size=10, line=dict(width=0)),
                            hovertemplate="%{text}<br>%{x:.1f} / %{y:.1f}<extra></extra>")
            uy = C.unit_for(tdf, ymetric)
            fig.update_layout(**T.plotly_layout(height=520,
                              xaxis_title=f"{metric} [{unit}]" if unit else metric,
                              yaxis_title=f"{ymetric} [{uy}]" if uy else ymetric))
            C.show_chart(fig)
            st.caption("Crosshairs = group means. Top-right = strong on both.")

    # --- asymmetry by group -------------------------------------------------
    asym_mets = asym.asymmetry_metrics(tdf)
    if asym_mets:
        st.markdown("---")
        C.section_label("alert", f"Asymmetry · {one}")
        amet = st.selectbox("Asymmetry metric", asym_mets, key="team_asym")
        flags = asym.flag_asymmetries(tdf, ctx.asym_threshold, rep_how)
        fm = flags[(flags["metric"] == amet) & (flags["group"] == one)]
        if fm.empty:
            st.info("No asymmetry data for this group.")
        else:
            fig, shown = C.asym_bars(fm, ctx.asym_threshold)
            C.show_chart(fig)
            n_flag = int(fm["flagged"].sum())
            st.caption(f"{n_flag} of {len(fm)} athletes over {ctx.asym_threshold}%. "
                       "Green zone = within threshold; red bars exceed it.")


def _normative(sub, order=None):
    import pandas as pd
    rows = []
    for grp, g in sub.groupby("group"):
        s = norm.group_stats(g["value"])
        rows.append({"Group": grp, "n": s["n"], "Mean": s["mean"], "SD": s["sd"],
                     "CV%": s["cv"], "Min": s["min"], "P25": s["p25"],
                     "Median": s["median"], "P75": s["p75"], "P90": s["p90"], "Max": s["max"]})
    out = pd.DataFrame(rows)
    if order:
        out["__o"] = out["Group"].map({g: i for i, g in enumerate(order)})
        out = out.sort_values("__o").drop(columns="__o")
    else:
        out = out.sort_values("Group")
    return out.reset_index(drop=True)
