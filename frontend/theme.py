"""
frontend/theme.py
Design tokens and reusable HTML fragments for the dashboard.

One dark "operations console" palette, defined once. The original project had
two dashboards with duplicated inline CSS that had already drifted apart.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

INK = "#05070f"
PANEL = "#0b1424"
PANEL_BG = "#0c1426"
PANEL_EDGE = "rgba(120, 180, 255, 0.16)"
TEXT = "#e6eefc"
TEXT_DIM = "rgba(180, 205, 240, 0.72)"
TEXT_FAINT = "rgba(150, 180, 220, 0.45)"

ACCENT = "#63b8ff"
ACCENT_WARM = "#ffd23f"
GOOD = "#35e08a"
WARN = "#ff8c1a"
BAD = "#ff3b52"
IDLE = "#4a5a78"

STATUS_COLORS: Dict[str, str] = {
    "live": GOOD,
    "cached": "#5ec8d8",
    "stale": ACCENT_WARM,
    "simulated": "#b57cff",
    "unavailable": IDLE,
    "needs_credentials": WARN,
}

SEVERITY_COLORS: Dict[str, str] = {
    "critical": BAD,
    "high": WARN,
    "medium": ACCENT_WARM,
    "low": ACCENT,
}


def global_css() -> str:
    """Application-wide styling."""
    return f"""
<style>
  .stApp {{
    background:
      radial-gradient(ellipse at 20% -10%, #13233f 0%, {INK} 55%, #03050b 100%);
  }}
  .block-container {{ padding-top: 2.0rem; max-width: 1500px; }}

  h1, h2, h3, h4 {{ color: {TEXT} !important; letter-spacing: 0.2px; }}
  p, li, span, label {{ color: {TEXT_DIM}; }}

  .hero {{
    text-align: center;
    padding: 6px 0 20px;
  }}
  .hero-title {{
    font-size: 2.35rem; font-weight: 800; letter-spacing: -0.5px;
    background: linear-gradient(96deg, #8fd4ff 0%, #c9a4ff 52%, #ffb37c 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 6px;
  }}
  .hero-sub {{
    font-size: 0.92rem; color: {TEXT_FAINT}; letter-spacing: 2.6px;
    text-transform: uppercase;
  }}

  .panel {{
    background: linear-gradient(160deg,
      rgba(18, 32, 58, 0.82) 0%, rgba(9, 16, 32, 0.9) 100%);
    border: 1px solid {PANEL_EDGE};
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 14px;
  }}
  .panel-title {{
    font-size: 0.72rem; letter-spacing: 2.2px; text-transform: uppercase;
    color: {TEXT_FAINT}; margin-bottom: 12px; font-weight: 700;
  }}

  .banner {{
    border-radius: 12px; padding: 14px 18px; margin-bottom: 14px;
    font-size: 0.93rem; line-height: 1.6; font-weight: 500;
    border-left: 4px solid;
  }}
  .banner-demo {{
    background: rgba(181, 124, 255, 0.13);
    border-color: #b57cff; color: #e3d0ff;
  }}
  .banner-ok {{
    background: rgba(53, 224, 138, 0.12);
    border-color: {GOOD}; color: #c4f5dd;
  }}
  .banner-warn {{
    background: rgba(255, 140, 26, 0.13);
    border-color: {WARN}; color: #ffdfc0;
  }}

  .metric {{
    background: linear-gradient(155deg,
      rgba(22, 40, 72, 0.85), rgba(10, 18, 36, 0.9));
    border: 1px solid {PANEL_EDGE};
    border-radius: 12px; padding: 15px 17px; height: 100%;
  }}
  .metric-label {{
    font-size: 0.66rem; letter-spacing: 1.7px; text-transform: uppercase;
    color: {TEXT_FAINT}; margin-bottom: 7px; font-weight: 700;
  }}
  .metric-value {{
    font-size: 1.62rem; font-weight: 750; color: {TEXT}; line-height: 1.15;
  }}
  .metric-sub {{ font-size: 0.74rem; color: {TEXT_FAINT}; margin-top: 5px; }}

  .chip {{
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: 0.68rem; font-weight: 700; letter-spacing: 1.1px;
    text-transform: uppercase;
  }}

  .src-row {{
    display: flex; align-items: center; gap: 12px;
    padding: 10px 12px; margin-bottom: 7px;
    background: rgba(14, 26, 48, 0.55);
    border: 1px solid rgba(120, 180, 255, 0.1);
    border-left: 3px solid;
    border-radius: 9px;
  }}
  .src-leg {{
    font-weight: 700; font-size: 0.78rem; color: {TEXT};
    min-width: 82px; text-transform: uppercase; letter-spacing: 0.9px;
  }}
  .src-body {{ flex: 1; min-width: 0; }}
  .src-name {{ font-size: 0.82rem; color: {TEXT}; }}
  .src-msg {{ font-size: 0.72rem; color: {TEXT_FAINT}; margin-top: 2px; }}
  .src-lat {{ font-size: 0.7rem; color: {TEXT_FAINT}; white-space: nowrap; }}

  .issue {{
    border: 1px solid rgba(120, 180, 255, 0.12);
    border-left: 3px solid;
    border-radius: 9px; padding: 11px 14px; margin-bottom: 8px;
    background: rgba(12, 22, 42, 0.6);
  }}
  .issue-head {{
    display: flex; align-items: center; gap: 9px; flex-wrap: wrap;
  }}
  .issue-id {{
    font-family: 'Cascadia Code', Consolas, monospace;
    font-size: 0.68rem; color: {TEXT_FAINT};
  }}
  .issue-title {{ font-size: 0.85rem; font-weight: 650; color: {TEXT}; }}
  .issue-detail {{
    font-size: 0.75rem; color: {TEXT_DIM}; margin-top: 7px; line-height: 1.6;
  }}
  .issue-fix {{
    font-size: 0.74rem; color: #a8e6c4; margin-top: 6px; line-height: 1.6;
  }}
  .issue-next {{
    font-size: 0.74rem; color: #ffd9a8; margin-top: 6px; line-height: 1.6;
  }}

  section[data-testid="stSidebar"] {{
    background: linear-gradient(185deg, #0a1424 0%, #070c18 100%);
    background-color: #08101f;
    border-right: 1px solid {PANEL_EDGE};
  }}
  .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
  .stTabs [data-baseweb="tab"] {{
    background: rgba(18, 32, 58, 0.5);
    border-radius: 9px 9px 0 0; padding: 9px 17px;
    color: {TEXT_DIM};
  }}
  .stTabs [aria-selected="true"] {{
    background: rgba(60, 120, 200, 0.28) !important;
    color: {TEXT} !important;
  }}
</style>
"""


def hero(title: str, subtitle: str) -> str:
    return (
        f'<div class="hero">'
        f'<div class="hero-title">{title}</div>'
        f'<div class="hero-sub">{subtitle}</div>'
        f'</div>'
    )


def panel(title: str, body: str) -> str:
    return (
        f'<div class="panel"><div class="panel-title">{title}</div>{body}</div>'
    )


def metric(label: str, value: str, sub: str = "", color: Optional[str] = None) -> str:
    style = f' style="color:{color}"' if color else ""
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="metric">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value"{style}>{value}</div>'
        f'{sub_html}</div>'
    )


def chip(text: str, color: str) -> str:
    return (
        f'<span class="chip" style="background:{color}22;color:{color};'
        f'border:1px solid {color}55">{text}</span>'
    )


def source_row(leg: str, name: str, status: str, message: str,
               latency_ms: float) -> str:
    color = STATUS_COLORS.get(status, IDLE)
    return (
        f'<div class="src-row" style="border-left-color:{color}">'
        f'<div class="src-leg">{leg}</div>'
        f'<div class="src-body">'
        f'<div class="src-name">{name} &nbsp;{chip(status, color)}</div>'
        f'<div class="src-msg">{message}</div>'
        f'</div>'
        f'<div class="src-lat">{latency_ms:.0f} ms</div>'
        f'</div>'
    )


def issue_card(issue: Dict) -> str:
    severity = issue.get("severity", "low")
    color = SEVERITY_COLORS.get(severity, ACCENT)
    fixed = issue.get("status") == "fixed"
    status_color = GOOD if fixed else WARN
    status_text = "FIXED" if fixed else "OPEN"

    html = (
        f'<div class="issue" style="border-left-color:{color}">'
        f'<div class="issue-head">'
        f'<span class="issue-id">{issue.get("id", "")}</span>'
        f'{chip(severity, color)}'
        f'{chip(status_text, status_color)}'
        f'<span class="issue-title">{issue.get("title", "")}</span>'
        f'</div>'
        f'<div class="issue-detail">{issue.get("detail", "")}</div>'
    )
    if issue.get("impact"):
        html += f'<div class="issue-detail"><b>Impact:</b> {issue["impact"]}</div>'
    if issue.get("fix"):
        html += f'<div class="issue-fix"><b>Fix:</b> {issue["fix"]}</div>'
    if issue.get("next_step"):
        html += f'<div class="issue-next"><b>Next:</b> {issue["next_step"]}</div>'
    html += "</div>"
    return html
