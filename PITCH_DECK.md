# ⚡ Thunderstorm & Lightning Nowcasting (0–6 hr)
## SIH 2026 — Pitch Deck Outline
**Problem Statement ID:** SIH26072 | **Ministry:** Ministry of Earth Sciences (MoES)

---

## Slide 1: Title Slide

**Headline:** *"Predicting Thunderstorms Before They Strike"*

- **Project Name:** ThunderAI — Real-Time Thunderstorm & Lightning Nowcasting
- **Problem ID:** SIH26072
- **Ministry:** Ministry of Earth Sciences
- **Domain:** Disaster Management / AI for Weather
- **Team:** [Your Team Name]
- **Tagline:** *0–6 hour nowcasting in 5 seconds — no GPU required*

---

## Slide 2: The Problem

### Why This Matters

- **India records ~1.8 crore lightning strikes annually** — among the highest globally
- **Thunderstorms kill 2,000+ people in India every year** (IMD data)
- **Current IMD forecasts:** 12–24 hour resolution, regional scale — too coarse for actionable warnings
- **Aviation, agriculture, power grids, outdoor events** all need 0–6 hour hyperlocal warnings
- **Existing solutions** require supercomputers, satellite data pipelines, and hours of compute
- **Gap:** No lightweight, real-time, laptop-deployable nowcasting system exists for India

### Pain Points
| Stakeholder | Current Pain |
|-------------|--------------|
| IMD / Meteorologists | Manual interpretation, delayed warnings |
| Airlines | Flight diversions due to sudden weather |
| Farmers | No advance hail/lightning alert |
| Power Utilities | Grid failures from unpredicted storms |
| Common People | No hyperlocal "will it rain in 30 min?" |

---

## Slide 3: The Solution

### ThunderAI — Hybrid AI Nowcasting Engine

**What it does:** Predicts thunderstorm & lightning probability for the next 0–6 hours at hyperlocal scale, in under 5 seconds on any laptop.

**How it works (3-Stage Pipeline):**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  STAGE 1: INPUT │───▶│ STAGE 2: ENGINE │───▶│ STAGE 3: OUTPUT │
│                 │    │                 │    │                 │
│ • Satellite IR  │    │ • Optical Flow  │    │ • Risk Heatmap  │
│ • Radar Data    │    │   (OpenCV)      │    │ • Alert Levels  │
│ • Ground Obs    │    │ • XGBoost ML    │    │ • LLM Summary   │
│ • IMD Warnings  │    │ • Groq LLM      │    │ • Streamlit UI  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Key Differentiator:** Combines classical computer vision (optical flow for cloud motion) + ML (XGBoost for pattern recognition) + LLM (Groq for natural language alerts) — all running locally without GPU.

---

## Slide 4: Technical Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                      │
│  INSAT-3D/3DR · IMD AWS · GFS/NWP · Lightning Network       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   PROCESSING ENGINE                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ OpenCV       │  │ XGBoost      │  │ Groq LLM API     │  │
│  │ Optical Flow │  │ Classifier   │  │ (Llama-3.1)      │  │
│  │ (Cloud Motion│  │ (Storm/Light │  │ (Alert Narration │  │
│  │  Vectors)    │  │  ning Prob.) │  │  & Reasoning)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Fusion Layer (Weighted Ensemble)            │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    OUTPUT / VISUALIZATION                    │
│  Streamlit Dashboard · REST API · SMS/Email Alerts          │
└─────────────────────────────────────────────────────────────┘
```

**Tech Stack:**
- **Language:** Python 3.11+
- **CV/Optical Flow:** OpenCV (Farneback + Lucas-Kanade)
- **ML Model:** XGBoost (gradient boosted trees)
- **LLM:** Groq API (Llama-3.1-70B, 500+ tok/s)
- **Dashboard:** Streamlit
- **Data:** NumPy, Pandas, xarray, rasterio
- **Deployment:** Any laptop, no GPU needed

---

## Slide 5: Innovation Highlights

### What Makes ThunderAI Different

| Feature | Existing Systems | ThunderAI |
|---------|-----------------|-----------|
| **Compute** | Supercomputer / Cloud GPU | Any laptop, CPU-only |
| **Latency** | 30–120 minutes | **< 5 seconds** |
| **Resolution** | District-level (50km) | **Hyperlocal (1–5 km)** |
| **Cost** | ₹50L+ infrastructure | **Zero hardware cost** |
| **Explainability** | Black-box NWP models | **LLM-generated reasoning** |
| **Deployment** | Centralized | **Edge-ready, offline-capable** |

### 3 Core Innovations:
1. **Hybrid AI Fusion:** Classical optical flow (physics-based) + XGBoost (data-based) — best of both worlds, no deep learning GPU needed
2. **LLM-Powered Alerts:** Groq LLM translates model outputs into human-readable, actionable warnings with reasoning
5. **Zero-GPU Nowcasting:** Proves that effective weather AI doesn't require expensive infrastructure — democratizes access

---

## Slide 6: How It Works — Step by Step

### The 5-Second Prediction Pipeline

```
Step 1: INGEST (0.5s)     → Fetch latest satellite IR + radar frame
Step 2: OPTICAL FLOW (1s) → Compute cloud motion vectors (OpenCV)
Step 3: FEATURE EXTRACT   → Extract 47 features (motion, texture, intensity)
Step 4: XGBoost PREDICT   → Storm probability + lightning risk score
Step 5: LLM NARRATE       → Groq generates alert text + reasoning
Step 6: VISUALIZE         → Streamlit renders heatmap + alert panel
```

**Total: < 5 seconds end-to-end**

---

## Slide 7: Demo Script (For Judges)

### Live Demo Flow (3 Minutes)

| Time | Action | What Judges See |
|------|--------|-----------------|
| 0:00 | **Open Streamlit app** | Clean dashboard with India map |
| 0:15 | **Select region** (e.g., Delhi NCR) | Satellite IR overlay appears |
| 0:30 | **Click "Nowcast"** | Progress bar: 5 stages execute |
| 0:45 | **Results appear** | Color-coded risk heatmap (Green→Red) |
| 1:00 | **Click alert panel** | LLM-generated warning: *"High probability of thunderstorm in Delhi NCR within 2–3 hours. Cloud motion vectors indicate convergence from NW. Recommend grounding outdoor activities."* |
| 1:30 | **Show time-series** | 0–6 hr probability curve |
| 1:45 | **Compare regions** | Side-by-side: Delhi (high risk) vs Chennai (low risk) |
| 2:00 | **Show latency counter** | "Prediction generated in 4.2 seconds" |
| 2:15 | **Explain the "why"** | Feature importance chart + optical flow vectors |
| 2:30 | **Mobile view** | Responsive layout for field officers |
| 2:45 | **Alert dispatch** | Simulated SMS/email to stakeholders |
| 3:00 | **Q&A** | Open for questions |

---

## Slide 8: Impact & Scalability

### Who Benefits

| Sector | Impact | Scale |
|--------|--------|-------|
| **Disaster Management** | Early warnings save lives | 700+ districts |
| **Aviation** | Reduce weather-related delays | 150+ airports |
| **Agriculture** | Protect crops from hail/lightning | 14 crore farmers |
| **Power Grid** | Prevent transformer failures | All state DISCOMs |
| **Defense** | Secure installations & operations | Military bases |
| **Sports/Events** | Crowd safety | Every outdoor event |

### Scalability Path
- **Phase 1:** Delhi NCR pilot (current)
- **Phase 2:** 10 major cities
- **Phase 3:** Pan-India (all 700 districts)
- **Phase 4:** SAARC region export
- **Integration:** IMD's existing Mausam app, NDMA alert system

---

## Slide 9: Team Roles

### Our Team

| Role | Responsibility | Skills |
|------|---------------|--------|
| **Team Lead / PM** | Coordination, presentation, timeline | Project management, communication |
| **ML Engineer** | XGBoost model, feature engineering | Python, scikit-learn, XGBoost |
| **CV Engineer** | Optical flow, satellite data processing | OpenCV, image processing, rasterio |
| **Backend Developer** | Data pipeline, API, integration | Python, FastAPI, data engineering |
| **Frontend Developer** | Streamlit dashboard, visualization | Streamlit, Plotly, UI/UX |
| **LLM Specialist** | Groq integration, prompt engineering | LLM APIs, NLP, prompt design |
| **Domain Expert** | Meteorology knowledge, validation | Atmospheric science, IMD data |

---

## Slide 10: Future Roadmap

### Where We're Headed

```
2026 (SIH)          2026 (Post-SIH)       2027                2028
─────────────       ──────────────        ──────────────      ──────────────
✅ MVP Working      📌 IMD Pilot          🚀 Pan-India        🌍 SAARC Export
✅ 1 Region         📌 10 Cities          🚀 Mobile App       🚀 API Platform
✅ Core ML          📌 Real-time Data     🚀 Edge Device      🚀 Insurance API
✅ LLM Alerts       📌 NDMA Integration   🚀 Cyclone Addon    🚀 Climate Model
```

### Planned Enhancements
- **Satellite direct feed** (INSAT-3DR real-time)
- **Lightning detection network** integration
- **Mobile app** for field officers
- **Voice alerts** in regional languages
- **API-as-a-Service** for third-party apps
- **Cyclone & flood** nowcasting extension

---

## Slide 11: Budget

### Zero-Cost Development Model

| Item | Cost (₹) | Notes |
|------|----------|-------|
| **Compute** | 0 | CPU-only laptop, no GPU |
| **Cloud/API** | 0 | Groq free tier (500 tok/s) |
| **Data** | 0 | IMD open data, INSAT public |
| **Software** | 0 | All open-source (Python, OpenCV, XGBoost, Streamlit) |
| **Hardware** | 0 | Existing laptops |
| **Total** | **₹ 0** | — |

### If Funded (SIH Grant ₹1L):
| Item | Cost (₹) |
|------|----------|
| Groq API upgrade (production) | 20,000 |
| Cloud hosting (Streamlit Cloud) | 15,000 |
| Domain + SMS gateway | 10,000 |
| Dataset acquisition (if needed) | 25,000 |
| Miscellaneous | 30,000 |
| **Total** | **₹1,00,000** |

---

## Slide 12: Closing / Call to Action

### Why ThunderAI Should Win

1. ✅ **Solves a real problem** — 2,000+ deaths/year from thunderstorms
2. ✅ **Technically innovative** — Hybrid AI, zero-GPU, 5-second latency
3. ✅ **Immediately deployable** — Works on any laptop today
4. ✅ **Massively scalable** — From 1 city to 700 districts
5. ✅ **Zero cost to build** — Open-source stack, free APIs
6. ✅ **Aligned with national priorities** — NDMA, IMD, Digital India

### Our Ask
> *"We don't need a supercomputer to save lives. We need smart AI that works everywhere."*

**Let's make India thunderstorm-ready.**

---

## Appendix: Quick Reference

### Problem Statement Summary
> Develop an AI/ML-based system for 0–6 hour thunderstorm and lightning nowcasting using satellite, radar, and ground observation data. The system should provide hyperlocal, real-time warnings with minimal computational requirements.

### Key Metrics
- **Latency:** < 5 seconds
- **Forecast window:** 0–6 hours
- **Spatial resolution:** 1–5 km
- **Compute:** CPU-only, any laptop
- **Accuracy target:** > 85% POD (Probability of Detection)

### Data Sources
- INSAT-3D/3DR satellite imagery
- IMD Doppler Weather Radar
- Ground-based AWS observations
- GLD360 lightning detection network
- GFS/NWP model outputs

---

*Prepared for SIH 2026 — Software Edition*
*Team: [Your Team Name] | Contact: [email] | GitHub: [repo-link]*