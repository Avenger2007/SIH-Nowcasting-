"""
frontend/theme.py
Design system for the nowcasting dashboard.

Palette: "Monsoon Sky". Light, high-contrast and drawn from the subject matter
itself - the pale blue of clear sky, the deepening indigo of an approaching
storm, and the amber of a lightning flash for anything that needs attention.

Light backgrounds are a deliberate choice. This is an operational warning tool
that will be read on a projector in a bright room and on phones in daylight,
where dark themes wash out badly. Colour is reserved for meaning: a coloured
element on this page always encodes risk, status or provenance.
"""

from __future__ import annotations

from typing import Dict, Optional

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

# Sky - page and surface tones
SKY_50 = "#F4F9FF"      # page background, high cloud
SKY_100 = "#E7F1FC"     # subtle fills
SKY_200 = "#CFE3F7"     # borders, dividers
SKY_300 = "#A8CBEF"     # muted strokes
SURFACE = "#FFFFFF"     # cards
SURFACE_SOFT = "#FBFDFF"

# Storm - primary brand blues
BLUE = "#1273D4"        # primary
BLUE_DEEP = "#0B4F94"   # headings, emphasis
BLUE_DARK = "#08355F"   # darkest text-on-light
INDIGO = "#4C4BC7"      # secondary, storm cloud
VIOLET = "#7B5BD6"      # simulated / demonstration states

# Lightning - attention
AMBER = "#E8890C"       # warnings, moderate risk
AMBER_SOFT = "#FFF3E0"
GOLD = "#F2B705"        # lightning accent

# Semantic
GREEN = "#1E8E52"       # good, live, minimal risk
GREEN_SOFT = "#E6F6EC"
RED = "#D63A45"         # severe, critical
RED_SOFT = "#FDECEE"
SLATE = "#6B7C93"       # idle, unavailable
SLATE_SOFT = "#EEF2F7"

# Text
INK = "#10263F"         # primary text
INK_SOFT = "#44607F"    # secondary text
INK_FAINT = "#7C93AC"   # captions

SHADOW = "0 1px 2px rgba(16,38,63,.06), 0 8px 24px rgba(16,38,63,.07)"
SHADOW_SM = "0 1px 2px rgba(16,38,63,.06), 0 3px 10px rgba(16,38,63,.05)"

STATUS_COLORS: Dict[str, str] = {
    "live": GREEN,
    "cached": BLUE,
    "stale": AMBER,
    "simulated": VIOLET,
    "unavailable": SLATE,
    "needs_credentials": AMBER,
}

STATUS_SOFT: Dict[str, str] = {
    "live": GREEN_SOFT,
    "cached": SKY_100,
    "stale": AMBER_SOFT,
    "simulated": "#F1ECFD",
    "unavailable": SLATE_SOFT,
    "needs_credentials": AMBER_SOFT,
}

SEVERITY_COLORS: Dict[str, str] = {
    "critical": RED,
    "high": AMBER,
    "medium": GOLD,
    "low": BLUE,
}

# Risk bands, matching config.RISK_BANDS but tuned for a light background.
RISK_COLORS: Dict[str, str] = {
    "HIGH": RED,
    "MODERATE": AMBER,
    "LOW": GOLD,
    "MINIMAL": GREEN,
}


def global_css() -> str:
    """Application-wide styling."""
    return f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  .stApp {{
    background:
      radial-gradient(1200px 620px at 12% -8%, #DCEBFB 0%, rgba(220,235,251,0) 62%),
      radial-gradient(1000px 560px at 92% 4%, #E6E4FB 0%, rgba(230,228,251,0) 58%),
      linear-gradient(178deg, {SKY_50} 0%, #FFFFFF 46%, {SKY_50} 100%);
  }}
  html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
  }}
  .block-container {{ padding-top: 1.6rem; max-width: 1480px; }}

  h1, h2, h3, h4, h5 {{ color: {BLUE_DARK} !important; letter-spacing: -.01em; }}
  p, li, span, label, div {{ color: {INK_SOFT}; }}
  a {{ color: {BLUE}; }}
  hr {{ border-color: {SKY_200}; }}

  /* ---------- hero ---------- */
  .hero {{ text-align: center; padding: 10px 0 4px; }}
  .hero-eyebrow {{
    display: inline-block; margin-bottom: 12px;
    padding: 6px 14px; border-radius: 999px;
    background: {SURFACE}; border: 1px solid {SKY_200};
    box-shadow: {SHADOW_SM};
    font-size: .70rem; font-weight: 700; letter-spacing: .16em;
    text-transform: uppercase; color: {BLUE};
  }}
  .hero-title {{
    font-size: 2.85rem; font-weight: 800; line-height: 1.08;
    letter-spacing: -.03em; margin: 0 0 12px;
    background: linear-gradient(103deg, {BLUE_DEEP} 0%, {BLUE} 44%, {INDIGO} 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .hero-sub {{
    font-size: 1.02rem; color: {INK_SOFT}; max-width: 760px;
    margin: 0 auto; line-height: 1.65;
  }}

  /* ---------- surfaces ---------- */
  .panel {{
    background: {SURFACE};
    border: 1px solid {SKY_200};
    border-radius: 16px;
    padding: 20px 22px;
    margin-bottom: 16px;
    box-shadow: {SHADOW_SM};
  }}
  .panel-title {{
    font-size: .68rem; letter-spacing: .16em; text-transform: uppercase;
    color: {INK_FAINT}; margin-bottom: 14px; font-weight: 700;
  }}

  .banner {{
    border-radius: 14px; padding: 15px 19px; margin-bottom: 14px;
    font-size: .92rem; line-height: 1.62; font-weight: 500;
    border: 1px solid; border-left-width: 4px;
  }}
  .banner-demo {{
    background: #F5F1FE; border-color: {VIOLET}; color: #3F2E86;
  }}
  .banner-ok {{
    background: {GREEN_SOFT}; border-color: {GREEN}; color: #145C36;
  }}
  .banner-warn {{
    background: {AMBER_SOFT}; border-color: {AMBER}; color: #8A5206;
  }}
  .banner-info {{
    background: {SKY_100}; border-color: {BLUE}; color: {BLUE_DEEP};
  }}

  /* ---------- metrics ---------- */
  .metric {{
    background: {SURFACE};
    border: 1px solid {SKY_200};
    border-radius: 14px; padding: 16px 18px; height: 100%;
    box-shadow: {SHADOW_SM};
    transition: transform .16s ease, box-shadow .16s ease;
  }}
  .metric:hover {{ transform: translateY(-2px); box-shadow: {SHADOW}; }}
  .metric-label {{
    font-size: .64rem; letter-spacing: .14em; text-transform: uppercase;
    color: {INK_FAINT}; margin-bottom: 8px; font-weight: 700;
  }}
  .metric-value {{
    font-size: 1.72rem; font-weight: 750; color: {BLUE_DARK}; line-height: 1.1;
  }}
  .metric-sub {{ font-size: .74rem; color: {INK_FAINT}; margin-top: 6px; }}

  .chip {{
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: .66rem; font-weight: 700; letter-spacing: .09em;
    text-transform: uppercase; border: 1px solid;
  }}

  /* ---------- source rows ---------- */
  .src-row {{
    display: flex; align-items: center; gap: 14px;
    padding: 12px 14px; margin-bottom: 8px;
    background: {SURFACE};
    border: 1px solid {SKY_200};
    border-left: 3px solid;
    border-radius: 11px;
    box-shadow: {SHADOW_SM};
  }}
  .src-leg {{
    font-weight: 700; font-size: .74rem; color: {BLUE_DARK};
    min-width: 88px; text-transform: uppercase; letter-spacing: .08em;
  }}
  .src-body {{ flex: 1; min-width: 0; }}
  .src-name {{ font-size: .84rem; color: {INK}; font-weight: 550; }}
  .src-msg {{ font-size: .74rem; color: {INK_FAINT}; margin-top: 3px; line-height: 1.5; }}
  .src-lat {{ font-size: .7rem; color: {INK_FAINT}; white-space: nowrap; }}

  /* ---------- issue cards ---------- */
  .issue {{
    background: {SURFACE};
    border: 1px solid {SKY_200};
    border-left: 3px solid;
    border-radius: 12px; padding: 13px 16px; margin-bottom: 9px;
    box-shadow: {SHADOW_SM};
  }}
  .issue-head {{ display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }}
  .issue-id {{
    font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
    font-size: .68rem; color: {INK_FAINT}; font-weight: 600;
  }}
  .issue-title {{ font-size: .87rem; font-weight: 650; color: {BLUE_DARK}; }}
  .issue-detail {{ font-size: .77rem; color: {INK_SOFT}; margin-top: 8px; line-height: 1.62; }}
  .issue-fix {{ font-size: .76rem; color: #146B41; margin-top: 7px; line-height: 1.62; }}
  .issue-next {{ font-size: .76rem; color: #8A5206; margin-top: 7px; line-height: 1.62; }}

  /* ---------- landing page ---------- */
  .lp-card {{
    background: {SURFACE};
    border: 1px solid {SKY_200};
    border-radius: 18px; padding: 22px 24px; height: 100%;
    box-shadow: {SHADOW_SM};
    transition: transform .18s ease, box-shadow .18s ease;
  }}
  .lp-card:hover {{ transform: translateY(-3px); box-shadow: {SHADOW}; }}
  .lp-icon {{
    width: 42px; height: 42px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 21px; margin-bottom: 14px;
  }}
  .lp-h {{
    font-size: 1.02rem; font-weight: 700; color: {BLUE_DARK};
    margin-bottom: 8px; letter-spacing: -.01em;
  }}
  .lp-b {{ font-size: .85rem; color: {INK_SOFT}; line-height: 1.68; }}

  .lp-stat {{
    text-align: center; padding: 20px 12px;
    background: {SURFACE}; border: 1px solid {SKY_200};
    border-radius: 16px; box-shadow: {SHADOW_SM}; height: 100%;
  }}
  .lp-stat-v {{
    font-size: 2.0rem; font-weight: 800; line-height: 1;
    background: linear-gradient(103deg, {BLUE_DEEP}, {INDIGO});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .lp-stat-l {{
    font-size: .7rem; color: {INK_FAINT}; margin-top: 9px;
    text-transform: uppercase; letter-spacing: .11em; font-weight: 700;
  }}

  .ps-table {{ width: 100%; border-collapse: separate; border-spacing: 0; }}
  .ps-table td {{
    padding: 11px 14px; font-size: .86rem;
    border-bottom: 1px solid {SKY_200}; color: {INK_SOFT};
  }}
  .ps-table tr:last-child td {{ border-bottom: none; }}
  .ps-table td:first-child {{
    font-weight: 700; color: {BLUE_DARK}; width: 190px;
    font-size: .74rem; text-transform: uppercase; letter-spacing: .09em;
  }}

  .step {{
    display: flex; gap: 16px; align-items: flex-start;
    padding: 15px 0; border-bottom: 1px dashed {SKY_200};
  }}
  .step:last-child {{ border-bottom: none; }}
  .step-n {{
    flex: none; width: 32px; height: 32px; border-radius: 10px;
    background: linear-gradient(140deg, {BLUE}, {INDIGO});
    color: #fff; font-weight: 750; font-size: .84rem;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 3px 9px rgba(18,115,212,.28);
  }}
  .step-h {{ font-size: .92rem; font-weight: 650; color: {BLUE_DARK}; margin-bottom: 4px; }}
  .step-b {{ font-size: .82rem; color: {INK_SOFT}; line-height: 1.65; }}

  /* ---------- streamlit chrome ---------- */
  section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #FFFFFF 0%, {SKY_50} 100%);
    border-right: 1px solid {SKY_200};
  }}
  section[data-testid="stSidebar"] * {{ color: {INK_SOFT}; }}
  section[data-testid="stSidebar"] h3 {{ color: {BLUE_DARK} !important; }}

  .stTabs [data-baseweb="tab-list"] {{
    gap: 4px; border-bottom: 1px solid {SKY_200};
  }}
  .stTabs [data-baseweb="tab"] {{
    background: transparent; border-radius: 10px 10px 0 0;
    padding: 10px 18px; color: {INK_FAINT}; font-weight: 600;
    font-size: .88rem;
  }}
  .stTabs [aria-selected="true"] {{
    background: {SURFACE} !important; color: {BLUE_DEEP} !important;
    border: 1px solid {SKY_200}; border-bottom: 2px solid {BLUE};
  }}

  .stButton > button {{
    border-radius: 11px; font-weight: 650; border: 1px solid {SKY_200};
    box-shadow: {SHADOW_SM};
  }}
  .stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {BLUE} 0%, {INDIGO} 100%);
    border: none; color: #fff;
    box-shadow: 0 4px 14px rgba(18,115,212,.30);
  }}
  .stButton > button[kind="primary"]:hover {{
    box-shadow: 0 6px 20px rgba(18,115,212,.40);
  }}

  div[data-testid="stDataFrame"] {{
    border: 1px solid {SKY_200}; border-radius: 12px; overflow: hidden;
  }}
  .stAlert {{ border-radius: 12px; }}
</style>
"""


# --------------------------------------------------------------------------
# Fragments
# --------------------------------------------------------------------------

def hero(title: str, subtitle: str, eyebrow: str = "") -> str:
    eyebrow_html = f'<div class="hero-eyebrow">{eyebrow}</div>' if eyebrow else ""
    return (
        f'<div class="hero">{eyebrow_html}'
        f'<div class="hero-title">{title}</div>'
        f'<div class="hero-sub">{subtitle}</div></div>'
    )


def panel(title: str, body: str) -> str:
    return f'<div class="panel"><div class="panel-title">{title}</div>{body}</div>'


def metric(label: str, value: str, sub: str = "", color: Optional[str] = None) -> str:
    style = f' style="color:{color}"' if color else ""
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value"{style}>{value}</div>{sub_html}</div>'
    )


def chip(text: str, color: str, soft: Optional[str] = None) -> str:
    background = soft or f"{color}14"
    return (
        f'<span class="chip" style="background:{background};color:{color};'
        f'border-color:{color}44">{text}</span>'
    )


def status_chip(status: str) -> str:
    return chip(status, STATUS_COLORS.get(status, SLATE),
                STATUS_SOFT.get(status))


def source_row(leg: str, name: str, status: str, message: str,
               latency_ms: float) -> str:
    color = STATUS_COLORS.get(status, SLATE)
    return (
        f'<div class="src-row" style="border-left-color:{color}">'
        f'<div class="src-leg">{leg}</div>'
        f'<div class="src-body">'
        f'<div class="src-name">{name} &nbsp;{status_chip(status)}</div>'
        f'<div class="src-msg">{message}</div></div>'
        f'<div class="src-lat">{latency_ms:.0f} ms</div></div>'
    )


def issue_card(issue: Dict) -> str:
    severity = issue.get("severity", "low")
    color = SEVERITY_COLORS.get(severity, BLUE)
    fixed = issue.get("status") == "fixed"
    status_color = GREEN if fixed else AMBER
    status_soft = GREEN_SOFT if fixed else AMBER_SOFT

    html = (
        f'<div class="issue" style="border-left-color:{color}">'
        f'<div class="issue-head">'
        f'<span class="issue-id">{issue.get("id", "")}</span>'
        f'{chip(severity, color)}'
        f'{chip("resolved" if fixed else "open", status_color, status_soft)}'
        f'<span class="issue-title">{issue.get("title", "")}</span></div>'
        f'<div class="issue-detail">{issue.get("detail", "")}</div>'
    )
    if issue.get("impact"):
        html += f'<div class="issue-detail"><b>Impact:</b> {issue["impact"]}</div>'
    if issue.get("fix"):
        html += f'<div class="issue-fix"><b>Resolution:</b> {issue["fix"]}</div>'
    if issue.get("next_step"):
        html += f'<div class="issue-next"><b>Next:</b> {issue["next_step"]}</div>'
    return html + "</div>"


def feature_card(icon: str, title: str, body: str, tint: str = BLUE) -> str:
    return (
        f'<div class="lp-card">'
        f'<div class="lp-icon" style="background:{tint}15;color:{tint}">{icon}</div>'
        f'<div class="lp-h">{title}</div>'
        f'<div class="lp-b">{body}</div></div>'
    )


def stat_card(value: str, label: str) -> str:
    return (
        f'<div class="lp-stat"><div class="lp-stat-v">{value}</div>'
        f'<div class="lp-stat-l">{label}</div></div>'
    )


def step_row(number: int, title: str, body: str) -> str:
    return (
        f'<div class="step"><div class="step-n">{number}</div>'
        f'<div><div class="step-h">{title}</div>'
        f'<div class="step-b">{body}</div></div></div>'
    )


def spec_table(rows) -> str:
    body = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return f'<table class="ps-table">{body}</table>'
