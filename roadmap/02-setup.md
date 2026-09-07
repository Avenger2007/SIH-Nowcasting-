# 02 · Setup

## Requirements

- Python 3.10 or newer
- About 500 MB of disk for dependencies and the frame cache
- An internet connection for live data
- **No GPU.** The whole system runs on CPU.

---

## Install

```bash
git clone https://github.com/Avenger2007/SIH-Nowcasting-.git
cd SIH-Nowcasting-

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`. The home page loads
immediately; press **Run nowcast** in the sidebar to fetch live data.

---

## API keys

**None are required.** The three data legs that matter most work with no
credentials at all:

| Source | Credential | Without it |
|---|---|---|
| INSAT satellite imagery | none | Works |
| IMD Doppler radar | none | Works |
| NWP convective parameters | none | Works |
| Administrative boundaries | none | Works |
| OpenWeatherMap | optional key | Falls back to model analysis |
| Groq (LLM alert phrasing) | optional key | Falls back to template alerts |
| MOSDAC calibrated L1B | free account | Falls back to public browse imagery |
| Lightning network | institutional | Lightning features report as unobserved |

To add optional keys:

```bash
cp .env.example .env
```

Then edit `.env`. Never commit it — it is already in `.gitignore`.

```ini
GROQ_API_KEY=gsk_...
OPENWEATHER_API_KEY=...
MOSDAC_USERNAME=...
MOSDAC_PASSWORD=...
```

The sidebar shows which credentials are detected, so you can confirm they
loaded.

---

## Before a live demonstration

**Start the frame collector at least an hour beforehand.** The MOSDAC gallery
publishes only the newest scan, so cloud motion needs at least two distinct
scans in the buffer. Without it, the motion field is zero and the dashboard
will correctly say motion is unavailable.

```bash
python scripts/collect_frames.py --watch --interval 900
```

INSAT-3DS completes a full disk every 30 minutes; polling every 15 minutes
catches each scan without hammering the endpoint. Frames are deduplicated by
content hash, so repeated fetches of the same scan do not create false motion.

Leave it running in a second terminal. Verify with:

```bash
python -c "from utils.datasources import mosdac; print(mosdac.buffer_status())"
```

You want `total_frames` of 2 or more.

---

## Verify the installation

```bash
# Offline tests - should be 56 passed
pytest

# Live tests against real endpoints - should be 5 passed
pytest -m live

# Full pipeline against live data
python scripts/live_test.py Delhi
```

The live test prints each data leg with its status and latency, the extracted
features, the model output and the generated bulletin. If three or four legs
report `live`, everything is working.

---

## Retraining the model

The shipped model is a demonstration model fitted to synthetic data. To
regenerate it:

```bash
python -m utils.predictor
```

To train on real observed lightning labels, see
[08-model-roadmap.md](08-model-roadmap.md).

---

## Troubleshooting

**`ImportError: libGL.so.1` on a server or container**
The requirements pin `opencv-python-headless` precisely to avoid this. If you
installed `opencv-python` separately, remove it:
```bash
pip uninstall opencv-python -y && pip install opencv-python-headless
```

**`FeatureContractError: ... legacy v1 format`**
The model file predates the feature contract. Regenerate it:
```bash
python -m utils.predictor
```

**Cloud motion always reads zero**
Only one distinct satellite scan is buffered. Run the frame collector — see
above.

**A data leg reports `unavailable`**
Normal and expected. Government endpoints have outages, and only three IMD
radar sites currently publish public products. The nowcast degrades with a
stated confidence note rather than failing.

**Boundaries do not appear**
ISRO Bhuvan is unreachable. This is deliberate behaviour: the system does not
substitute a foreign dataset, because those depict a different boundary. Check
connectivity to `bhuvan-vec1.nrsc.gov.in`.

**Windows: `Filename too long` when cloning**
```bash
git config --system core.longpaths true
```

**Port already in use**
```bash
streamlit run app.py --server.port 8502
```

---

## Project layout

```
app.py                  Dashboard entry point
config.py               Thresholds, endpoints, satellite and radar network
ISSUES.json             Engineering register, rendered live in the UI

utils/
  calibration.py        8-bit counts to Kelvin
  geo.py                Geostationary projection
  features.py           88 named features
  optical_flow.py       Cloud motion and advection
  predictor.py          Feature contract, model card, model
  metrics.py            Verification metrics
  consistency.py        Model-versus-physics cross-check
  llm_alert.py          Bulletin generation
  datasources/          One module per data source

frontend/
  landing.py            Home page
  globe.py              3D network view
  theme.py              Design system

scripts/
  live_test.py          End-to-end smoke test
  collect_frames.py     Frame buffer collector
  train_real.py         Training on observed labels

roadmap/                This documentation
tests/                  61 tests
```
