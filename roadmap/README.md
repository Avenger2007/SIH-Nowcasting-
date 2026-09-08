# Roadmap & Documentation

Everything needed to understand, run, present and extend the thunderstorm
nowcasting system.

**Smart India Hackathon 2026 · Problem Statement SIH26072**
Ministry of Earth Sciences / India Meteorological Department

---

## Read in this order

| # | Document | What it covers | Read if you are |
|---|---|---|---|
| 01 | [Problem statement](01-problem-statement.md) | What was asked, what it means in practice, how we interpreted it | New to the project |
| 02 | [Setup](02-setup.md) | Install, run, API keys, troubleshooting | Getting it running |
| 03 | [Framework](03-framework.md) | Architecture, modules, data structures, design decisions | Reading the code |
| 04 | [Workflow](04-workflow.md) | What happens step by step when a nowcast runs | Explaining the system |
| 05 | [Data sources](05-data-sources.md) | Every source, its endpoint, status and licence | Working on ingestion |
| 06 | [The science](06-science.md) | Meteorology behind each feature and threshold | Defending the approach |
| 07 | [Verification](07-verification.md) | How skill is measured and why accuracy is banned | Reviewing results |
| 08 | [Model roadmap](08-model-roadmap.md) | What remains to make the model genuinely skilful | Planning next work |
| 09 | [Deployment](09-deployment.md) | Streamlit Cloud, Docker, VM, scheduling | Shipping it |
| 10 | [Presentation](10-presentation.md) | Slide-by-slide content for the SIH deck | Preparing the pitch |
| 11 | [Demo script](11-demo-script.md) | Minute-by-minute plan for the live demonstration | Presenting |
| 12 | [Q&A preparation](12-qa-preparation.md) | Hard questions and honest answers | About to be evaluated |

---

## The one-paragraph version

The system fuses live INSAT-3DS satellite imagery, IMD Doppler weather radar,
lightning observations and numerical model output into a 0 to 6 hour
thunderstorm and lightning probability for any Indian city. Satellite imagery
is georeferenced through the geostationary projection and calibrated to
brightness temperature in Kelvin. Cloud motion comes from dense optical flow
between consecutive scans. Eighty-eight named features drive a gradient-boosted
model that is bound to its inputs by an explicit feature contract, verified
with operational meteorological metrics, and cross-examined against the
physics before any warning is issued.

**Current honest status:** the pipeline is real and runs on live data. The
model is trained on synthetic labels and therefore has no measured forecast
skill yet. Connecting an observed lightning archive is the single remaining
step, and it is covered in [08-model-roadmap.md](08-model-roadmap.md).

---

## Quick commands

```bash
pip install -r requirements.txt      # install
streamlit run app.py                 # run the dashboard
python scripts/live_test.py Delhi    # prove the pipeline against live sources
python scripts/collect_frames.py --watch --interval 900   # build the frame buffer
pytest                               # offline tests
pytest -m live                       # include network tests
```

---

## Project status at a glance

| Data leg (named in the problem statement) | Status |
|---|---|
| Satellite | Live — INSAT-3DS / 3DR via the MOSDAC public gallery |
| Multiple radars | Live — IMD Doppler composites, decoded to reflectivity |
| Model data | Live — CAPE, CIN, Lifted Index, shear, precipitable water |
| Lightning | Adapter complete, awaiting an institutional data feed |

| Engineering | Count |
|---|---|
| Tracked issues | 45 |
| Resolved | 37 |
| Open, each with a documented next step | 4 |
| Automated tests | 77 (72 offline, 5 live) |
