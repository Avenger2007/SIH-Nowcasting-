# 📡 SIH 2026 — Thunderstorm & Lightning Nowcasting (0-6 hr)
## PS Number: SIH26072 | Ministry of Earth Sciences (MoES)

**GitHub Repo:** https://github.com/Avenger2007/SIH-Nowcasting-.git

**Team:** [Your Name(s)]
**College:** [Your College]

---

## 🎯 Problem Statement
Develop an AI/ML-based system for nowcasting (0-6 hours) of thunderstorms and lightning using satellite, radar, and observational weather data.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT DASHBOARD                       │
│  • Live satellite imagery display                            │
│  • Thunderstorm probability gauge                            │
│  • LLM-generated alert text                                  │
│  • Interactive map overlay (Folium)                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    CORE ML PIPELINE                          │
│  Stage 1: Optical Flow (OpenCV Farneback) — cloud motion     │
│  Stage 2: XGBoost — thunderstorm probability                 │
│  Stage 3: Groq Llama 3.1 — natural language alert            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                            │
│  • MOSDAC/ISRO INSAT-3D satellite imagery                    │
│  • OpenWeatherMap API (CAPE, CIN, humidity, wind)            │
│  • IMD radar composites                                      │
│  • SRTM terrain elevation data                               │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Innovation: Hybrid AI Approach

| Component | Technology | Why |
|---|---|---|
| Cloud Motion | Optical Flow (Farneback) | No training needed, runs in seconds on CPU |
| Convection Prediction | XGBoost | Trains in minutes on CPU, interpretable |
| Alert Generation | Groq Llama 3.1 (free) | Natural language, zero cost |
| Dashboard | Streamlit | Pure Python, free deployment |

**No GPU required. Entire pipeline runs on any laptop.**

---

## 📊 Data Sources

| Data | Source | Access |
|---|---|---|
| INSAT-3D Satellite | MOSDAC (ISRO) | Free API (mdapi) |
| Weather Parameters | OpenWeatherMap | Free tier (1000/day) |
| Terrain Elevation | SRTM | Free via `elevation` package |
| Radar Composites | IMD | Public images |

---

## 🛠️ Tech Stack

- **Language:** Python 3.11+
- **ML:** XGBoost, scikit-learn, OpenCV
- **LLM:** Groq API (Llama 3.1-8B)
- **Dashboard:** Streamlit, Folium
- **Deployment:** Streamlit Cloud (free)

---

## 📁 Project Structure

```
sih-nowcasting/
├── app.py                  ← Main Streamlit application
├── requirements.txt        ← Dependencies
├── README.md               ← This file
├── .gitignore              ← Ignore API keys, cache
├── models/
│   └── xgb_model.json      ← Trained XGBoost model
├── utils/
│   ├── satellite.py        ← Satellite data fetching
│   ├── optical_flow.py     ← Cloud motion vectors
│   ├── features.py         ← Feature engineering
│   ├── predictor.py        ← XGBoost inference
│   └── llm_alert.py        ← Groq LLM alert generation
├── data/
│   └── sample_images/      ← Sample satellite images
└── assets/
    └── style.css           ← Custom styling
```

---

## 🚀 Quick Start

```bash
# Clone repo
git clone https://github.com/[your-username]/sih-nowcasting.git
cd sih-nowcasting

# Install dependencies
pip install -r requirements.txt

# Set API keys
cp .env.example .env
# Edit .env with your GROQ_API_KEY and OPENWEATHER_API_KEY

# Run locally
streamlit run app.py
```

---

## 📈 Results

| Metric | Value |
|---|---|
| Prediction Lead Time | 0-6 hours |
| Inference Time | ~5 seconds |
| Model Size | ~2 MB |
| Training Time | ~10 minutes |
| Hardware | CPU only (no GPU) |

---

## 🏆 Why This Wins

1. **Zero GPU needed** — runs on any laptop during judging
2. **Real meteorological science** — hybrid AI + physics approach
3. **Live demo possible** — pull real-time satellite data
4. **Zero ideas submitted** — no competition yet (0/500)
5. **Scalable** — can cover all of India with satellite data
