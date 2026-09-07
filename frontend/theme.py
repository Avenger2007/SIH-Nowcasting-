"""
frontend/theme.py
Design system for the nowcasting dashboard.

DESIGN LANGUAGE
---------------
Aerospace-console minimalism, in daylight.

The structural language is taken from aerospace mission sites: enormous
uppercase headlines with tight leading, hairline rules, tiny wide-tracked
eyebrow labels, ghost buttons, generous vertical rhythm, and content laid out
in full-width bands rather than boxes-inside-boxes. Restraint does the work -
one confident statement per band, and a lot of air around it.

The palette stays light. An operational warning tool is read on a projector in
a bright room and on phones in daylight, where dark themes wash out. So this
takes the aerospace *structure and typography* and renders it on sky rather
than on black.

TYPOGRAPHY
----------
Barlow for display and interface - a grotesque in the DIN lineage, which is
the family aerospace interfaces reach for. Inter for long-form body text,
where it is more readable at small sizes. Headlines are uppercase with
negative tracking; labels are uppercase with wide positive tracking. That
contrast between tight display and airy label type is most of the effect.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

# Sky - surfaces
SKY_50 = "#F5F9FE"
SKY_100 = "#E9F2FC"
SKY_200 = "#D4E4F5"
SKY_300 = "#AECBEB"
SURFACE = "#FFFFFF"
SURFACE_SOFT = "#FAFCFF"

# Storm - structure and brand
BLUE = "#1273D4"
BLUE_DEEP = "#0A4E96"
BLUE_DARK = "#062F5E"
INDIGO = "#4340C0"
VIOLET = "#7550D0"

# Lightning - attention
AMBER = "#DC7F06"
AMBER_SOFT = "#FFF4E2"
GOLD = "#EFB000"

# Semantic
GREEN = "#17834A"
GREEN_SOFT = "#E4F5EA"
RED = "#CC2E3C"
RED_SOFT = "#FDEBED"
SLATE = "#61748C"
SLATE_SOFT = "#EDF1F6"

# Ink
INK = "#08243F"
INK_SOFT = "#3C5876"
INK_FAINT = "#7389A3"

HAIRLINE = SKY_200
SHADOW_SM = "0 1px 2px rgba(8,36,63,.05), 0 2px 8px rgba(8,36,63,.04)"
SHADOW = "0 2px 4px rgba(8,36,63,.06), 0 14px 40px rgba(8,36,63,.09)"

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
    "simulated": "#F1ECFC",
    "unavailable": SLATE_SOFT,
    "needs_credentials": AMBER_SOFT,
}

SEVERITY_COLORS: Dict[str, str] = {
    "critical": RED,
    "high": AMBER,
    "medium": GOLD,
    "low": BLUE,
}

RISK_COLORS: Dict[str, str] = {
    "HIGH": RED,
    "MODERATE": AMBER,
    "LOW": GOLD,
    "MINIMAL": GREEN,
}


def global_css() -> str:
    """Application-wide styling."""
    return f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
  :root {{
    --ink: {INK};
    --ink-soft: {INK_SOFT};
    --ink-faint: {INK_FAINT};
    --blue: {BLUE};
    --hairline: {HAIRLINE};
    --display: 'Barlow', 'Inter', -apple-system, 'Segoe UI', sans-serif;
    --body: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
  }}

  .stApp {{
    background:
      radial-gradient(1400px 700px at 8% -12%, #D9EAFB 0%, rgba(217,234,251,0) 58%),
      radial-gradient(1100px 620px at 96% 2%, #E6E6FA 0%, rgba(230,230,250,0) 55%),
      linear-gradient(180deg, {SKY_50} 0%, #FFFFFF 40%, {SKY_50} 100%);
  }}
  html, body, [class*="css"] {{ font-family: var(--body); }}
  .block-container {{ padding-top: 1.2rem; max-width: 1420px; }}

  h1, h2, h3, h4, h5 {{
    font-family: var(--display) !important;
    color: {BLUE_DARK} !important;
    font-weight: 700 !important;
    letter-spacing: -.015em !important;
  }}
  p, li, span, label {{ color: {INK_SOFT}; }}
  a {{ color: {BLUE}; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  hr {{ border: none; border-top: 1px solid {HAIRLINE}; margin: 2.2rem 0; }}

  /* ================= display type ================= */

  .eyebrow {{
    font-family: var(--display);
    font-size: .70rem; font-weight: 600;
    letter-spacing: .34em; text-transform: uppercase;
    color: {BLUE}; margin-bottom: 18px;
  }}
  .eyebrow-rule {{
    display: flex; align-items: center; gap: 16px; margin-bottom: 22px;
  }}
  .eyebrow-rule::after {{
    content: ""; flex: 1; height: 1px; background: {HAIRLINE};
  }}

  .display {{
    font-family: var(--display);
    font-size: clamp(2.6rem, 6.2vw, 5.2rem);
    font-weight: 800; line-height: .94;
    letter-spacing: -.035em; text-transform: uppercase;
    color: {BLUE_DARK}; margin: 0 0 26px;
  }}
  .display-accent {{
    background: linear-gradient(100deg, {BLUE_DEEP} 0%, {BLUE} 40%, {INDIGO} 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }}

  .lede {{
    font-family: var(--body);
    font-size: 1.06rem; line-height: 1.72; color: {INK_SOFT};
    max-width: 780px; font-weight: 400;
  }}

  .section-h {{
    font-family: var(--display);
    font-size: clamp(1.7rem, 3.1vw, 2.5rem);
    font-weight: 700; line-height: 1.04;
    letter-spacing: -.028em; text-transform: uppercase;
    color: {BLUE_DARK}; margin: 0 0 14px;
  }}

  .band {{ padding: 58px 0 8px; }}
  .band-top {{ border-top: 1px solid {HAIRLINE}; }}

  /* ================= buttons ================= */

  .stButton > button {{
    font-family: var(--display) !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: .15em;
    font-size: .74rem !important;
    border-radius: 2px;
    border: 1px solid {SKY_300};
    background: {SURFACE};
    padding: .62rem 1rem;
    transition: all .16s ease;
  }}
  .stButton > button:hover {{
    border-color: {BLUE}; color: {BLUE_DEEP};
  }}
  .stButton > button[kind="primary"] {{
    background: {BLUE_DARK};
    border: 1px solid {BLUE_DARK};
  }}
  .stButton > button[kind="primary"]:hover {{
    background: {BLUE_DEEP}; border-color: {BLUE_DEEP};
  }}

  /*
   * Button label colour is set on the button AND on every descendant.
   * Streamlit wraps the label in an inner element, and a broad descendant
   * rule elsewhere (the sidebar, for instance) will otherwise win on that
   * inner node and leave the label invisible against a filled background.
   * This is a real bug that shipped once; the explicit descendant selector
   * is what prevents it.
   */
  .stButton > button[kind="primary"],
  .stButton > button[kind="primary"] * {{
    color: #FFFFFF !important;
  }}
  .stButton > button:not([kind="primary"]),
  .stButton > button:not([kind="primary"]) * {{
    color: {BLUE_DARK} !important;
  }}

  /* ================= surfaces ================= */

  .panel {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: 3px;
    padding: 22px 24px;
    margin-bottom: 14px;
  }}
  .panel-title {{
    font-family: var(--display);
    font-size: .66rem; letter-spacing: .26em; text-transform: uppercase;
    color: {INK_FAINT}; margin-bottom: 16px; font-weight: 600;
  }}

  .banner {{
    border-radius: 2px; padding: 16px 20px; margin-bottom: 12px;
    font-size: .9rem; line-height: 1.62; font-weight: 400;
    border: 1px solid; border-left-width: 3px;
  }}
  .banner-demo {{ background: #F6F2FE; border-color: {VIOLET}; color: #3B2A80; }}
  .banner-ok   {{ background: {GREEN_SOFT}; border-color: {GREEN}; color: #0F5C33; }}
  .banner-warn {{ background: {AMBER_SOFT}; border-color: {AMBER}; color: #85500A; }}
  .banner-info {{ background: {SKY_100}; border-color: {BLUE}; color: {BLUE_DARK}; }}

  /* ================= metrics ================= */

  .metric {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: 3px; padding: 18px 20px; height: 100%;
  }}
  .metric-label {{
    font-family: var(--display);
    font-size: .62rem; letter-spacing: .24em; text-transform: uppercase;
    color: {INK_FAINT}; margin-bottom: 10px; font-weight: 600;
  }}
  .metric-value {{
    font-family: var(--display);
    font-size: 2.0rem; font-weight: 700; color: {BLUE_DARK};
    line-height: 1; letter-spacing: -.03em;
  }}
  .metric-sub {{ font-size: .73rem; color: {INK_FAINT}; margin-top: 8px; }}

  /* Large statistic, aerospace style: thin, huge, wide-tracked caption */
  .stat {{ text-align: left; padding: 4px 0 0; }}
  .stat-v {{
    font-family: var(--display);
    font-size: clamp(2.4rem, 4.6vw, 3.6rem);
    font-weight: 300; line-height: .96; letter-spacing: -.035em;
    color: {BLUE_DARK};
  }}
  .stat-l {{
    font-family: var(--display);
    font-size: .64rem; letter-spacing: .26em; text-transform: uppercase;
    color: {INK_FAINT}; margin-top: 12px; font-weight: 600;
    padding-top: 12px; border-top: 1px solid {HAIRLINE};
  }}

  .chip {{
    display: inline-block; padding: 3px 11px; border-radius: 2px;
    font-family: var(--display);
    font-size: .62rem; font-weight: 600; letter-spacing: .16em;
    text-transform: uppercase; border: 1px solid;
  }}

  /* ================= source rows ================= */

  .src-row {{
    display: flex; align-items: center; gap: 16px;
    padding: 14px 16px; margin-bottom: 6px;
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-left: 3px solid;
    border-radius: 2px;
  }}
  .src-leg {{
    font-family: var(--display);
    font-weight: 600; font-size: .68rem; color: {BLUE_DARK};
    min-width: 92px; text-transform: uppercase; letter-spacing: .18em;
  }}
  .src-body {{ flex: 1; min-width: 0; }}
  .src-name {{ font-size: .84rem; color: {INK}; font-weight: 500; }}
  .src-msg {{ font-size: .74rem; color: {INK_FAINT}; margin-top: 4px; line-height: 1.5; }}
  .src-lat {{
    font-family: var(--display);
    font-size: .7rem; color: {INK_FAINT}; white-space: nowrap;
    letter-spacing: .06em;
  }}

  /* ================= issue cards ================= */

  .issue {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-left: 3px solid;
    border-radius: 2px; padding: 15px 18px; margin-bottom: 7px;
  }}
  .issue-head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .issue-id {{
    font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
    font-size: .68rem; color: {INK_FAINT}; font-weight: 600;
  }}
  .issue-title {{
    font-family: var(--display);
    font-size: .95rem; font-weight: 600; color: {BLUE_DARK};
    letter-spacing: -.01em;
  }}
  .issue-detail {{ font-size: .78rem; color: {INK_SOFT}; margin-top: 9px; line-height: 1.66; }}
  .issue-fix {{ font-size: .77rem; color: #10603A; margin-top: 7px; line-height: 1.66; }}
  .issue-next {{ font-size: .77rem; color: #85500A; margin-top: 7px; line-height: 1.66; }}

  /* ================= landing components ================= */

  .capability {{
    padding: 26px 0 0;
    border-top: 1px solid {HAIRLINE};
    height: 100%;
  }}
  .capability-n {{
    font-family: var(--display);
    font-size: .68rem; font-weight: 600; letter-spacing: .26em;
    margin-bottom: 14px;
  }}
  .capability-h {{
    font-family: var(--display);
    font-size: 1.22rem; font-weight: 700; color: {BLUE_DARK};
    text-transform: uppercase; letter-spacing: -.02em; margin-bottom: 10px;
  }}
  .capability-b {{ font-size: .86rem; color: {INK_SOFT}; line-height: 1.72; }}

  .spec {{ width: 100%; border-collapse: collapse; }}
  .spec td {{
    padding: 15px 0; font-size: .9rem;
    border-bottom: 1px solid {HAIRLINE}; color: {INK_SOFT};
    vertical-align: top;
  }}
  .spec tr:last-child td {{ border-bottom: none; }}
  .spec td:first-child {{
    font-family: var(--display);
    font-weight: 600; color: {INK_FAINT}; width: 210px;
    font-size: .66rem; text-transform: uppercase; letter-spacing: .22em;
    padding-right: 24px;
  }}

  .step {{
    display: flex; gap: 26px; align-items: flex-start;
    padding: 22px 0; border-bottom: 1px solid {HAIRLINE};
  }}
  .step:last-child {{ border-bottom: none; }}
  .step-n {{
    font-family: var(--display);
    flex: none; width: 46px;
    font-size: 1.5rem; font-weight: 300; color: {SKY_300};
    line-height: 1; letter-spacing: -.03em;
  }}
  .step-h {{
    font-family: var(--display);
    font-size: 1.02rem; font-weight: 600; color: {BLUE_DARK};
    text-transform: uppercase; letter-spacing: .01em; margin-bottom: 7px;
  }}
  .step-b {{ font-size: .85rem; color: {INK_SOFT}; line-height: 1.72; }}

  .leg {{
    padding: 22px 0 0; border-top: 2px solid; height: 100%;
  }}
  .leg-h {{
    font-family: var(--display);
    font-size: 1.06rem; font-weight: 700; color: {BLUE_DARK};
    text-transform: uppercase; letter-spacing: -.015em;
    margin: 12px 0 9px;
  }}
  .leg-b {{ font-size: .84rem; color: {INK_SOFT}; line-height: 1.7; }}

  .verdict {{
    padding: 26px 28px; border-radius: 3px; height: 100%;
    border: 1px solid {HAIRLINE}; border-top: 3px solid;
    background: {SURFACE};
  }}
  .verdict-h {{
    font-family: var(--display);
    font-size: 1.06rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: -.015em; margin-bottom: 12px; color: {BLUE_DARK};
  }}
  .verdict-b {{ font-size: .86rem; color: {INK_SOFT}; line-height: 1.74; }}

  /* ================= streamlit chrome ================= */

  section[data-testid="stSidebar"] {{
    background: {SURFACE};
    border-right: 1px solid {HAIRLINE};
  }}
  /*
   * Scoped deliberately. A blanket `section[data-testid="stSidebar"] *`
   * rule wins on button label nodes and makes filled buttons unreadable.
   */
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] li,
  section[data-testid="stSidebar"] .stCaption,
  section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
    color: {INK_SOFT};
  }}
  section[data-testid="stSidebar"] h3 {{
    font-family: var(--display); color: {BLUE_DARK} !important;
    text-transform: uppercase; letter-spacing: .12em;
    font-size: .82rem !important; font-weight: 600 !important;
  }}

  .stTabs [data-baseweb="tab-list"] {{
    gap: 0; border-bottom: 1px solid {HAIRLINE};
  }}
  .stTabs [data-baseweb="tab"] {{
    background: transparent; border-radius: 0;
    padding: 13px 22px; color: {INK_FAINT};
    font-family: var(--display);
    font-weight: 600; font-size: .72rem;
    text-transform: uppercase; letter-spacing: .16em;
    border-bottom: 2px solid transparent;
  }}
  .stTabs [aria-selected="true"] {{
    background: transparent !important; color: {BLUE_DARK} !important;
    border-bottom: 2px solid {BLUE_DARK};
  }}

  div[data-testid="stDataFrame"] {{
    border: 1px solid {HAIRLINE}; border-radius: 2px; overflow: hidden;
  }}
  .stAlert {{ border-radius: 2px; }}

  [data-testid="stMetricValue"] {{ font-family: var(--display); }}
</style>
"""


# --------------------------------------------------------------------------
# Fragments
# --------------------------------------------------------------------------

def eyebrow(text: str, rule: bool = False) -> str:
    """Small wide-tracked uppercase label."""
    cls = "eyebrow eyebrow-rule" if rule else "eyebrow"
    return f'<div class="{cls}">{text}</div>'


def hero(title: str, subtitle: str, eyebrow_text: str = "") -> str:
    """Full-width opening statement."""
    top = eyebrow(eyebrow_text) if eyebrow_text else ""
    return (
        f'<div style="padding:34px 0 10px">{top}'
        f'<div class="display display-accent">{title}</div>'
        f'<div class="lede">{subtitle}</div></div>'
    )


def section(title: str, lede: str = "", eyebrow_text: str = "") -> str:
    """Band heading with an optional eyebrow and standfirst."""
    top = eyebrow(eyebrow_text, rule=True) if eyebrow_text else ""
    body = f'<div class="lede">{lede}</div>' if lede else ""
    return (
        f'<div class="band band-top">{top}'
        f'<div class="section-h">{title}</div>{body}</div>'
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


def stat(value: str, label: str) -> str:
    """Large thin figure over a hairline caption."""
    return (
        f'<div class="stat"><div class="stat-v">{value}</div>'
        f'<div class="stat-l">{label}</div></div>'
    )


def chip(text: str, color: str, soft: Optional[str] = None) -> str:
    background = soft or f"{color}12"
    return (
        f'<span class="chip" style="background:{background};color:{color};'
        f'border-color:{color}40">{text}</span>'
    )


def status_chip(status: str) -> str:
    return chip(status, STATUS_COLORS.get(status, SLATE), STATUS_SOFT.get(status))


def source_row(leg: str, name: str, status: str, message: str,
               latency_ms: float) -> str:
    color = STATUS_COLORS.get(status, SLATE)
    return (
        f'<div class="src-row" style="border-left-color:{color}">'
        f'<div class="src-leg">{leg}</div>'
        f'<div class="src-body">'
        f'<div class="src-name">{name} &nbsp;{status_chip(status)}</div>'
        f'<div class="src-msg">{message}</div></div>'
        f'<div class="src-lat">{latency_ms:.0f} MS</div></div>'
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


def capability(number: str, title: str, body: str, tint: str = BLUE) -> str:
    """Numbered capability, ruled above."""
    return (
        f'<div class="capability" style="border-top-color:{tint}">'
        f'<div class="capability-n" style="color:{tint}">{number}</div>'
        f'<div class="capability-h">{title}</div>'
        f'<div class="capability-b">{body}</div></div>'
    )


def leg_card(name: str, body: str, label: str, color: str) -> str:
    """One data leg with a status chip and a coloured top rule."""
    return (
        f'<div class="leg" style="border-top-color:{color}">'
        f'{chip(label, color)}'
        f'<div class="leg-h">{name}</div>'
        f'<div class="leg-b">{body}</div></div>'
    )


def verdict(title: str, body: str, color: str) -> str:
    return (
        f'<div class="verdict" style="border-top-color:{color}">'
        f'<div class="verdict-h">{title}</div>'
        f'<div class="verdict-b">{body}</div></div>'
    )


def step_row(number: int, title: str, body: str) -> str:
    return (
        f'<div class="step"><div class="step-n">{number:02d}</div>'
        f'<div><div class="step-h">{title}</div>'
        f'<div class="step-b">{body}</div></div></div>'
    )


def spec_table(rows: Iterable[Tuple[str, str]]) -> str:
    body = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return f'<table class="spec">{body}</table>'


# Retained for compatibility with existing call sites.
def feature_card(icon: str, title: str, body: str, tint: str = BLUE) -> str:
    return capability(icon, title, body, tint)


def stat_card(value: str, label: str) -> str:
    return stat(value, label)
