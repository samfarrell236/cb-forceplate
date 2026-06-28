"""Canada Basketball dark theme — Edge-style aesthetic, CB red accent.

Near-black surfaces, hairline rules, thin condensed display numerics, generous
space, flat (no rounded corners / no shadows). Single accent: CB red #C8102E.
Icons are flat inline SVG (stroke), never emoji.
"""
from __future__ import annotations

import base64
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"

# --- Palette ----------------------------------------------------------------
RED = "#C8102E"        # Canada Basketball red
RED_DIM = "#9E0C24"
BG = "#0a0a0a"
SURFACE = "#161616"
SURFACE_2 = "#1d1d1d"
RULE = "#262626"
INK = "#f2f2f2"
INK_MUTED = "#8a8a8a"
INK_FAINT = "#555555"
GO = "#4ade80"
MAINTAIN = "#facc15"      # yellow  — 1–10% deficit
CAUTION = "#f59e0b"       # orange  — 10–15% deficit
BACKOFF = "#f87171"       # red     — 15%+ deficit

BAND_COLORS = {"go": GO, "maintain": MAINTAIN, "caution": CAUTION, "backoff": BACKOFF}

# Plotly categorical sequence (CB red leads, then neutral inks)
PLOTLY_SEQUENCE = [RED, "#e0e0e0", INK_MUTED, RED_DIM, INK_FAINT]


# --- Flat stroke icons (Lucide-style, 1.6px) --------------------------------
_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" '
    'viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:middle">{p}</svg>'
)
_PATHS = {
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/>',
    "chart": '<path d="M3 3v18h18"/><rect x="7" y="11" width="3" height="6"/><rect x="12" y="7" width="3" height="10"/><rect x="17" y="13" width="3" height="4"/>',
    "trend": '<polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "scale": '<path d="M12 3v18"/><path d="m3 7 9-4 9 4"/><path d="M6 7l-3 6a3 3 0 0 0 6 0Z"/><path d="M18 7l-3 6a3 3 0 0 0 6 0Z"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    "alert": '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    "dot": '<circle cx="12" cy="12" r="6" fill="{c}" stroke="none"/>',
}


def icon(name: str, size: int = 18, color: str = INK) -> str:
    """Inline SVG markup for a flat stroke icon. Render with unsafe_allow_html."""
    p = _PATHS.get(name, _PATHS["dot"]).replace("{c}", color)
    return _ICON.format(s=size, c=color, p=p)


# --- Brand logo -------------------------------------------------------------
# Original maple-leaf-on-basketball mark used as the DEFAULT. The official
# Canada Basketball logo is trademarked and is NOT bundled — drop your licensed
# file at ui/assets/logo.(svg|png|jpg|webp) and it replaces this everywhere.
_LOGO_NAMES = ("logo.svg", "logo.png", "logo.jpg", "logo.jpeg", "logo.webp")

# Maple leaf (flat fill), symmetric about x=50, viewBox 0 0 100 100. Lobed
# silhouette with a stem — reads as a maple leaf, not a star burst.
_MAPLE_PATH = (
    "M50 6 "
    "L53 22 L61 18 L58 29 L71 25 L66 37 L82 40 L62 47 L68 60 L55 57 "
    "L58 72 L52 66 L53 94 "
    "L47 94 L48 66 L42 72 L45 57 L32 60 L38 47 L18 40 L34 37 L29 25 "
    "L42 29 L39 18 L47 22 Z"
)


def maple_mark(size: int = 34, leaf=INK, ring=RED) -> str:
    """Original brand mark: CB-red basketball roundel with a maple leaf + seams."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 100 100" style="display:block">'
        f'<circle cx="50" cy="50" r="47" fill="{ring}"/>'
        f'<path d="M50 3 A47 47 0 0 1 50 97" fill="none" stroke="{leaf}" '
        f'stroke-width="2" opacity="0.35"/>'
        f'<path d="M3 50 A47 47 0 0 1 97 50" fill="none" stroke="{leaf}" '
        f'stroke-width="2" opacity="0.35"/>'
        f'<g transform="translate(50 50) scale(0.66) translate(-50 -52)">'
        f'<path d="{_MAPLE_PATH}" fill="{leaf}"/></g></svg>'
    )


def _user_logo() -> Path | None:
    for n in _LOGO_NAMES:
        p = ASSETS / n
        if p.exists() and p.stat().st_size:
            return p
    return None


def logo_html(height: int = 34) -> str:
    """User's official logo if present in ui/assets, else the maple mark."""
    p = _user_logo()
    if p is None:
        return maple_mark(height)
    mime = "image/svg+xml" if p.suffix == ".svg" else f"image/{p.suffix[1:]}"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return (f'<img src="data:{mime};base64,{b64}" alt="Canada Basketball" '
            f'style="height:{height}px;width:auto;display:block"/>')


def logo_icon_path() -> str | None:
    """Path to a user logo for use as the Streamlit page_icon, if any."""
    p = _user_logo()
    return str(p) if p else None


def asset_img(filename: str, height: int = 18, css: str = "") -> str:
    """Embed an arbitrary image asset (e.g. a partner logo) as an <img>."""
    p = ASSETS / filename
    if not p.exists() or not p.stat().st_size:
        return ""
    ext = p.suffix.lstrip(".").lower()
    mime = "svg+xml" if ext == "svg" else ext
    b64 = base64.b64encode(p.read_bytes()).decode()
    return (f'<img src="data:image/{mime};base64,{b64}" alt="{p.stem}" '
            f'style="height:{height}px;width:auto;display:block;{css}"/>')


# --- CSS injected into the app ----------------------------------------------
def css() -> str:
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@500;600;700;800&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap');

:root {{
  --red: {RED}; --bg: {BG}; --surface: {SURFACE}; --rule: {RULE};
  --ink: {INK}; --muted: {INK_MUTED}; --faint: {INK_FAINT};
}}

html, body, [class*="css"], .stApp {{
  background: {BG} !important;
  color: {INK};
  font-family: 'Inter', system-ui, sans-serif;
}}
.stApp {{ font-size: 15px; }}

/* kill default chrome */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"] {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
/* fill available width so the page expands when the sidebar is collapsed */
.block-container {{ padding-top: 2.2rem; max-width: 100%;
  padding-left: 2.6rem; padding-right: 2.6rem; }}

/* -------- SIDEBAR NAV (vertical page links) -------- */
/* Only pin the width when EXPANDED — forcing min-width while collapsed would
   keep the layout slot reserved and stop the page reclaiming the space. */
[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {RULE}; }}
[data-testid="stSidebar"][aria-expanded="true"] {{
  width: 208px !important; min-width: 208px !important; max-width: 208px !important; }}
[data-testid="stSidebar"][aria-expanded="true"] > div:first-child {{ width: 208px !important; }}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding: 1.4rem 0.4rem; }}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.4rem; }}

/* keep the expand/collapse control visible + reachable in any Streamlit version */
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] {{
  visibility: visible !important; display: flex !important; opacity: 1 !important;
  z-index: 1000 !important; color: {INK} !important; }}
[data-testid="stSidebarCollapsedControl"] svg, [data-testid="collapsedControl"] svg,
[data-testid="stExpandSidebarButton"] svg {{ color: {INK} !important; fill: {INK} !important; }}
[data-testid="stSidebar"] .stButton > button {{
  background: transparent !important; border: none !important;
  border-left: 2px solid transparent !important; border-radius: 0 !important;
  color: {INK_MUTED} !important; justify-content: flex-start !important;
  text-align: left !important; text-transform: uppercase; letter-spacing: 0.14em;
  font-size: 12px; font-weight: 500; padding: 11px 16px !important; width: 100%; }}
[data-testid="stSidebar"] .stButton > button:hover {{
  color: {INK} !important; background: {SURFACE_2} !important; }}
[data-testid="stSidebar"] button[kind="primary"] {{
  color: {INK} !important; background: {SURFACE_2} !important;
  border-left: 2px solid {RED} !important; }}

/* flat everything */
* {{ border-radius: 0 !important; }}

h1, h2, h3, h4 {{
  font-family: 'Saira Condensed', 'Inter', sans-serif;
  text-transform: uppercase; letter-spacing: -0.01em; color: {INK};
  font-weight: 700;
}}

/* labels */
.cb-label {{ font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase;
  color: {INK_MUTED}; font-weight: 500; }}

/* metric tiles */
.cb-tile {{ border-top: 1px solid var(--rule); padding: 18px 0 14px; }}
.cb-metric {{ font-family: 'Saira Condensed', sans-serif; font-weight: 600;
  font-size: 52px; line-height: 0.9; letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums; color: {INK}; }}
.cb-metric .u {{ font-family: 'Inter'; font-size: 13px; color: {INK_MUTED};
  letter-spacing: 0.05em; font-weight: 400; margin-left: 8px; }}
.cb-sub {{ font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: {INK_MUTED}; letter-spacing: 0.02em; margin-top: 6px; }}
.cb-delta {{ font-family: 'JetBrains Mono', monospace; font-size: 11px;
  letter-spacing: 0.02em; margin-left: 8px; }}

/* header band */
.cb-head {{ display:flex; align-items:center; gap:14px; padding-bottom: 6px; }}
.cb-rail {{ width:4px; height:34px; background: var(--red); }}
.cb-word {{ font-family:'Saira Condensed',sans-serif; font-weight:800;
  font-size:26px; text-transform:uppercase; letter-spacing:-0.01em; color:{INK}; }}
.cb-word .thin {{ color:{INK_MUTED}; font-weight:600; }}
.cb-redrule {{ border:0; border-top:2px solid var(--red); margin: 4px 0 0; }}

/* status dot */
.cb-dot {{ display:inline-block; width:9px; height:9px; border-radius:50% !important;
  margin-right:7px; vertical-align:middle; }}
.cb-chip {{ font-family:'JetBrains Mono',monospace; font-size:12px;
  letter-spacing:0.02em; color:{INK_MUTED}; }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 28px; border-bottom: 1px solid var(--rule); }}
.stTabs [data-baseweb="tab"] {{ background: transparent; padding: 10px 0;
  font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase;
  color: {INK_MUTED}; font-weight: 500; }}
.stTabs [aria-selected="true"] {{ color: {INK} !important;
  border-bottom: 2px solid var(--red) !important; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid var(--rule); }}
[data-testid="stSidebar"] * {{ color: {INK}; }}

/* inputs */
[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
  background: {SURFACE_2} !important; border: 1px solid var(--rule) !important;
  color: {INK} !important; }}

/* compact metric-card dropdowns (Individual page) — centred text */
[class*="st-key-ind_card_"] [data-baseweb="select"] > div {{
  min-height: 32px !important; padding-left: 26px !important; }}
[class*="st-key-ind_card_"] [data-baseweb="select"] * {{ font-size: 12px !important;
  text-align: center !important; }}
[class*="st-key-ind_card_"] [data-baseweb="select"] svg {{ height: 16px; width: 16px; }}

/* lowkey selectable metric titles in the radar's right column (tight rows) */
[class*="st-key-ind_prof_"] {{ margin-bottom: 0 !important; }}
[class*="st-key-ind_prof_"] [data-testid="stElementContainer"] {{ margin-bottom: 0 !important; }}
[class*="st-key-ind_prof_"] [data-baseweb="select"] > div {{
  min-height: 24px !important; background: transparent !important;
  border-color: transparent !important; padding-left: 0 !important; }}
[class*="st-key-ind_prof_"] [data-baseweb="select"] * {{ font-size: 11px !important;
  letter-spacing: 0.02em; }}
[class*="st-key-ind_prof_"] [data-baseweb="select"] svg {{ height: 14px; width: 14px;
  opacity: 0.5; }}
[class*="st-key-ind_prof_"] [data-baseweb="select"]:hover > div {{
  border-color: {RULE} !important; }}

/* buttons */
.stButton > button, .stDownloadButton > button {{
  background: transparent; border: 1px solid {INK}; color: {INK};
  text-transform: uppercase; letter-spacing: 0.12em; font-size: 11px;
  font-weight: 500; padding: 9px 16px; transition: all .15s; }}
.stButton > button:hover, .stDownloadButton > button:hover {{
  background: var(--red); border-color: var(--red); color: #fff; }}

/* dataframe */
[data-testid="stDataFrame"] {{ border: 1px solid var(--rule); }}

/* metric direction legend */
.cb-legend {{ font-family:'JetBrains Mono',monospace; font-size:11px;
  color:{INK_FAINT}; letter-spacing:0.02em; }}
hr {{ border-color: var(--rule); }}
</style>
"""


# --- Plotly layout ----------------------------------------------------------
def plotly_layout(**overrides) -> dict:
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=INK, size=13),
        colorway=PLOTLY_SEQUENCE,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(gridcolor=RULE, zerolinecolor=RULE, linecolor=RULE,
                   tickfont=dict(color=INK_MUTED, size=11)),
        yaxis=dict(gridcolor=RULE, zerolinecolor=RULE, linecolor=RULE,
                   tickfont=dict(color=INK_MUTED, size=11)),
        legend=dict(font=dict(color=INK_MUTED, size=11)),
        hoverlabel=dict(bgcolor=INK, font=dict(color=BG, family="JetBrains Mono")),
    )
    base.update(overrides)
    return base
