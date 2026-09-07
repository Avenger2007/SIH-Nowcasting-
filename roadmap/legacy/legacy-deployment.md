# 🚀 Streamlit Cloud Deployment Guide
## SIH 2026 — Thunderstorm & Lightning Nowcasting (SIH26072)

**GitHub Repo:** https://github.com/Avenger2007/SIH-Nowcasting-.git  
**Main Entry Point:** `app.py`  
**Deployment Target:** [Streamlit Cloud](https://streamlit.io/cloud)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Step-by-Step Deployment](#2-step-by-step-deployment)
3. [Adding Secrets (API Keys)](#3-adding-secrets-api-keys)
4. [Verifying Deployment](#4-verifying-deployment)
5. [Updating Deployment After Code Changes](#5-updating-deployment-after-code-changes)
6. [Troubleshooting Common Issues](#6-troubleshooting-common-issues)
7. [Useful Links](#7-useful-links)

---

## 1. Prerequisites

Before deploying, ensure you have:

- [ ] A **GitHub account** (the repo must be public or you need a paid Streamlit Cloud plan)
- [ ] The repo pushed to GitHub: `https://github.com/Avenger2007/SIH-Nowcasting-.git`
- [ ] A **Streamlit Cloud account** (free at [share.streamlit.io](https://share.streamlit.io))
- [ ] `requirements.txt` in the repo root (already present ✅)
- [ ] `app.py` as the main entry point (already present ✅)
- [ ] API keys ready:
  - **GROQ_API_KEY** — Get free key at [console.groq.com](https://console.groq.com)
  - **OPENWEATHER_API_KEY** — Get free key at [openweathermap.org/api](https://openweathermap.org/api)

---

## 2. Step-by-Step Deployment

### Step 1: Push Latest Code to GitHub

```bash
cd "C:/Users/ksg/Downloads/SIH 2026"
git add .
git commit -m "Prepare for Streamlit Cloud deployment"
git push origin main
```

> ⚠️ **Important:** `.streamlit/secrets.toml` is gitignored and will NOT be pushed. This is by design — secrets are added via the Streamlit Cloud dashboard (see Section 3).

### Step 2: Sign In to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **"Sign in"** → **"Continue with GitHub"**
3. Authorize Streamlit to access your GitHub account

### Step 3: Deploy the App

1. On the Streamlit Cloud dashboard, click **"New app"** (or **"Deploy an app"**)
2. Fill in the form:
   - **Repository:** `Avenger2007/SIH-Nowcasting-`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **Python version:** `3.11` (recommended, matches local)
3. Click **"Deploy!"**

### Step 4: Wait for Build

- Streamlit Cloud will:
  1. Clone your repo
  2. Install dependencies from `requirements.txt`
  3. Start the Streamlit server
- Build typically takes **2–5 minutes**
- Watch the build logs in real-time for errors

### Step 5: Access Your App

- Once deployed, your app will be live at:
  ```
  https://sih-nowcasting-XXXXX.streamlit.app
  ```
- The exact URL is shown in the Streamlit Cloud dashboard

---

## 3. Adding Secrets (API Keys)

Since `.streamlit/secrets.toml` is gitignored, you must add secrets via the Streamlit Cloud dashboard.

### Method: Streamlit Cloud Dashboard (Recommended)

1. Go to [share.streamlit.io](https://share.streamlit.io) and click on your deployed app
2. Click the **⚙️ Settings** (gear icon) in the bottom-right corner of the app page
   - Or click **"..."** (three dots) → **"Settings"**
3. Click **"Secrets"** in the left sidebar
4. Paste your secrets in TOML format:

```toml
GROQ_API_KEY = "gsk_your_groq_api_key_here"
OPENWEATHER_API_KEY = "your_openweathermap_api_key_here"
```

5. Click **"Save"**
6. The app will **automatically restart** with the new secrets

### How to Access Secrets in Code

Your `app.py` should read secrets like this:

```python
import streamlit as st

# Streamlit Cloud injects secrets into st.secrets
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
OPENWEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]
```

### ⚠️ Security Notes

- **Never** commit `.streamlit/secrets.toml` to git (it's already in `.gitignore` ✅)
- **Never** hardcode API keys in `app.py` or any committed file
- If a key is accidentally exposed, **rotate it immediately** (generate a new key from the provider dashboard)
- Streamlit Cloud secrets are encrypted at rest and only visible to app collaborators

---

## 4. Verifying Deployment

After deployment, verify everything works:

### ✅ Checklist

| Check | How to Verify |
|-------|---------------|
| App loads without errors | Open the URL, check for red error traces |
| No "ModuleNotFoundError" | Build logs show all packages installed |
| Secrets are working | App doesn't show "API key missing" errors |
| Satellite data loads | Check if satellite imagery displays |
| Weather API responds | Check if weather parameters populate |
| LLM alert generates | Check if Groq-powered alerts appear |
| Interactive elements work | Click buttons, change inputs, verify responses |

### Common Verification Steps

1. **Check Build Logs:**
   - In Streamlit Cloud dashboard, click your app → **"Logs"**
   - Look for `✅ Your app is deployed!` or any `ERROR` lines

2. **Test API Key Access:**
   - If the app shows "API key not configured", secrets weren't added correctly
   - Re-check Section 3 and ensure keys are saved in the dashboard

3. **Test Core Features:**
   - Load the app homepage
   - Trigger a prediction (if applicable)
   - Verify the LLM alert generation works
   - Check that maps/charts render

4. **Check Browser Console:**
   - Press `F12` → **Console** tab
   - Look for JavaScript errors (rare but possible with Folium/Plotly)

---

## 5. Updating Deployment After Code Changes

Streamlit Cloud supports **automatic redeployment** on every git push.

### Automatic Updates (Recommended)

```bash
# Make your changes locally
git add .
git commit -m "Update: describe your change"
git push origin main
```

- Streamlit Cloud detects the push within **~30 seconds**
- The app rebuilds and redeploys automatically
- No manual intervention needed

### Manual Reboot

If the app gets stuck or you need a fresh start:

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click on your app
3. Click **"..."** (three dots) → **"Reboot"**

### Updating Secrets

1. Go to app **Settings** → **Secrets**
2. Edit the TOML content
3. Click **"Save"** — app restarts automatically

### Updating Python Version

1. Go to app **Settings** → **"Advanced settings"**
2. Change the Python version
3. Click **"Save"** — app rebuilds with new version

### Viewing Update History

- In the Streamlit Cloud dashboard, each app shows a **deployment history**
- Click any past deployment to see its logs
- You can **roll back** to a previous working version if needed

---

## 6. Troubleshooting Common Issues

### ❌ "ModuleNotFoundError: No module named 'X'"

**Cause:** Missing dependency in `requirements.txt`

**Fix:**
```bash
# Add the missing package to requirements.txt locally
echo "missing-package>=1.0.0" >> requirements.txt
git add requirements.txt
git commit -m "Add missing dependency"
git push origin main
```

**Prevention:** Always test locally first:
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

### ❌ "API key not configured" / KeyError in secrets

**Cause:** Secrets not added in Streamlit Cloud dashboard

**Fix:**
1. Go to app **Settings** → **Secrets**
2. Add:
   ```toml
   GROQ_API_KEY = "your_key_here"
   OPENWEATHER_API_KEY = "your_key_here"
   ```
3. Click **"Save"**

---

### ❌ App Crashes on Startup

**Check build logs:**
1. In Streamlit Cloud, click your app → **"Logs"**
2. Look for the **last error** before crash

**Common causes:**
- Syntax error in `app.py` — test locally with `python -m py_compile app.py`
- Import error — ensure all imports are in `requirements.txt`
- File path issue — use relative paths, not absolute Windows paths

---

### ❌ "This app has exceeded its resource limits"

**Cause:** Free tier has limits (1 GB RAM, 1 CPU, 1 GB storage)

**Fix:**
- Reduce model size (use `joblib` with compression)
- Cache heavy computations with `@st.cache_data`
- Avoid loading large datasets into memory
- Consider upgrading to [Streamlit Cloud Teams](https://streamlit.io/cloud) if needed

---

### ❌ Slow Loading / Timeout

**Cause:** Heavy computation on every page load

**Fix:** Add caching to your Streamlit app:
```python
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_satellite_data():
    # Your data loading code
    return data
```

---

### ❌ "Repository not found" during deployment

**Cause:** Repo is private or URL is wrong

**Fix:**
- Ensure the repo is **public** (free tier requires public repos)
- Or upgrade to a paid plan for private repo access
- Double-check the repo name: `Avenger2007/SIH-Nowcasting-`

---

### ❌ Secrets Not Working After Save

**Fix:**
1. Ensure TOML syntax is correct (no trailing commas, proper quotes)
2. Click **"Reboot"** after saving secrets
3. Check that you're using `st.secrets["KEY_NAME"]` (not `os.environ`)

---

### ❌ OpenCV / System Dependency Issues

**Cause:** Some packages need system-level libraries

**Fix:** Add a `packages.txt` file in your repo root:
```
libgl1-mesa-glx
libglib2.0-0
```
Streamlit Cloud (Debian-based) will install these via `apt`.

---

### ❌ Folium/Map Not Rendering

**Cause:** JavaScript blocked or iframe issues

**Fix:**
- Use `st.components.v1.html()` to render Folium maps:
```python
import streamlit.components.v1 as components
map_html = folium_map._repr_html_()
components.html(map_html, height=500)
```

---

## 7. Useful Links

| Resource | URL |
|----------|-----|
| Streamlit Cloud | [share.streamlit.io](https://share.streamlit.io) |
| Streamlit Docs | [docs.streamlit.io](https://docs.streamlit.io) |
| Secrets Management | [docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management) |
| Groq Console | [console.groq.com](https://console.groq.com) |
| OpenWeatherMap API | [openweathermap.org/api](https://openweathermap.org/api) |
| GitHub Repo | [github.com/Avenger2007/SIH-Nowcasting-](https://github.com/Avenger2007/SIH-Nowcasting-) |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│              STREAMLIT CLOUD DEPLOYMENT                     │
├─────────────────────────────────────────────────────────────┤
│  1. Push code to GitHub                                     │
│  2. Go to share.streamlit.io → New app                      │
│  3. Select repo + branch + app.py                           │
│  4. Click Deploy                                            │
│  5. Add secrets in Settings → Secrets                       │
│  6. Verify app loads and features work                      │
├─────────────────────────────────────────────────────────────┤
│  UPDATE: git push origin main → auto-redeploys              │
│  SECRETS: Settings → Secrets → Save → auto-restarts         │
│  LOGS: App page → Logs tab                                  │
│  REBOOT: App page → "..." → Reboot                          │
└─────────────────────────────────────────────────────────────┘
```

---

*Last updated: September 2026 | SIH 2026 — Thunderstorm Nowcasting Team*