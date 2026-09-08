# 09 · Deployment Guide

Four routes, from a five-minute demo host to a production service.

---

## Choosing a platform

The single fact that decides this: **Streamlit is a stateful server, not a
website.** The browser holds an open WebSocket to a Python process, and that
process keeps the session — the selected city, the loaded model, the INSAT
frame buffer — in memory between interactions. Any host that expects a
request to arrive, be answered, and be forgotten cannot run it.

That rules out the two platforms people usually ask about first.

| Platform | Runs this app? | Why |
|---|---|---|
| Streamlit Community Cloud | **Yes** | Purpose-built for it. Free, public URL, deploys from GitHub. |
| Hugging Face Spaces | **Yes** | Free, persistent container, native Streamlit SDK. The best second option. |
| Render / Railway / Fly.io | **Yes** | Ordinary container hosts. Paid, but the collector can run alongside. |
| Google Cloud Run | Yes, with care | Needs session affinity on, minimum instances above zero, and a mounted volume for the frame buffer. |
| **Vercel** | **No** | Serverless functions: request in, response out, process discarded. No persistent WebSocket, so the Streamlit session dies between clicks. The dependency set (xgboost, OpenCV, SciPy, pandas) also overruns the function bundle limit. Vercel is excellent at what it is for — a static or SSR frontend — and this is not that. |
| **Cloudflare Workers / Pages** | **No** | Workers are V8 isolates with strict CPU limits; Python support runs through Pyodide in WebAssembly, where xgboost and OpenCV are not available. Pages is static hosting. Cloudflare *Containers* could host it, but that is a much younger product than the alternatives above and buys nothing here. |

**Recommendation for SIH: stay on Streamlit Community Cloud.** It is free, the
URL is public so judges can open it on their own device, and it needs no
configuration this repository does not already carry. Moving to Vercel or
Cloudflare would mean rewriting the dashboard as a separate frontend against a
Python API — days of work that changes nothing an evaluator sees.

The one real reason to move is the ephemeral filesystem: Community Cloud
resets the container on redeploy, so the INSAT frame buffer starts empty and
cloud motion is unavailable until two scans accumulate. If that matters more
than convenience, take a container host from the table and run
`scripts/collect_frames.py` beside the dashboard on a mounted volume, as in
Option B below.

---

## Option A · Streamlit Community Cloud (recommended for SIH)

Free, public URL, deploys from GitHub. This is the right choice for a
hackathon submission — judges can open it on their own device.

### Steps

1. Push to GitHub (already done).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
3. **New app** → select the repository → branch `main` → main file `app.py`.
4. Under **Advanced settings**, set Python version to 3.11.
5. Deploy. First build takes 3–5 minutes.

### Secrets

Do not commit `.env`. In the app dashboard, open **Settings → Secrets** and
paste TOML:

```toml
GROQ_API_KEY = "gsk_..."
OPENWEATHER_API_KEY = "..."
MOSDAC_USERNAME = "..."
MOSDAC_PASSWORD = "..."
```

`config.get_secret()` reads Streamlit secrets before the environment, so this
works with no code change.

### Known constraints

**OpenCV must be headless.** Streamlit Cloud has no `libGL`, so plain
`opencv-python` fails at import. `requirements.txt` already pins
`opencv-python-headless`.

**Ephemeral filesystem.** The container is reset on redeploy, so the INSAT
frame buffer starts empty and cloud motion is unavailable until two scans
accumulate. Options:
- accept it — the UI states motion is unavailable, which is honest;
- run the frame collector on a separate always-on host and commit or sync the
  buffer;
- for a judged demo, run locally with a warm buffer.

**Resource limits.** About 1 GB RAM. The model is small and the pipeline fits
comfortably, but avoid raising `GRID_SIZE` much above 256.

**Cold start.** Apps sleep after inactivity and take ~30 s to wake. Open the
URL a few minutes before presenting.

---

## Option B · Docker

Reproducible, and the route to any cloud VM or Kubernetes cluster.

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# opencv-python-headless still needs a few shared libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", "--server.address=0.0.0.0"]
```

```bash
docker build -t nowcasting .
docker run -p 8501:8501 --env-file .env nowcasting
```

To keep the frame buffer across restarts, mount a volume:

```bash
docker run -p 8501:8501 --env-file .env \
  -v $(pwd)/data/cache:/app/data/cache nowcasting
```

### With the frame collector alongside

```yaml
# docker-compose.yml
services:
  dashboard:
    build: .
    ports: ["8501:8501"]
    env_file: .env
    volumes: ["./data/cache:/app/data/cache"]

  collector:
    build: .
    entrypoint: ["python", "scripts/collect_frames.py",
                 "--watch", "--interval", "900"]
    volumes: ["./data/cache:/app/data/cache"]
    restart: unless-stopped
```

```bash
docker compose up -d
```

This is the recommended shape for a real deployment: the collector keeps the
buffer warm so cloud motion is always available.

---

## Option C · Virtual machine

Any small Linux VM. Tested on Ubuntu 22.04, 2 vCPU / 4 GB.

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv git

git clone https://github.com/Avenger2007/SIH-Nowcasting-.git
cd SIH-Nowcasting-
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### systemd services

`/etc/systemd/system/nowcast-dashboard.service`

```ini
[Unit]
Description=Thunderstorm nowcasting dashboard
After=network-online.target

[Service]
Type=simple
User=nowcast
WorkingDirectory=/opt/SIH-Nowcasting-
EnvironmentFile=/opt/SIH-Nowcasting-/.env
ExecStart=/opt/SIH-Nowcasting-/.venv/bin/streamlit run app.py \
          --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/nowcast-collector.service`

```ini
[Unit]
Description=INSAT frame collector
After=network-online.target

[Service]
Type=simple
User=nowcast
WorkingDirectory=/opt/SIH-Nowcasting-
ExecStart=/opt/SIH-Nowcasting-/.venv/bin/python scripts/collect_frames.py \
          --watch --interval 900
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nowcast-dashboard nowcast-collector
sudo systemctl status nowcast-dashboard
```

### Reverse proxy with TLS

```nginx
server {
    listen 443 ssl;
    server_name nowcast.example.in;

    ssl_certificate     /etc/letsencrypt/live/nowcast.example.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nowcast.example.in/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_read_timeout 86400;
    }
}
```

The WebSocket upgrade headers are required — Streamlit will not work without
them.

---

## Option D · Windows

For a laptop demo, Task Scheduler keeps the buffer warm:

```powershell
schtasks /create /tn "INSATCollector" `
  /tr "C:\path\.venv\Scripts\python.exe C:\path\scripts\collect_frames.py" `
  /sc minute /mo 15 /f
```

---

## Pre-demonstration checklist

- [ ] Frame collector running for at least an hour — confirms cloud motion
- [ ] `python scripts/live_test.py Delhi` shows 3+ legs live
- [ ] `pytest` passes (68 offline)
- [ ] App opened once to warm caches and wake the host
- [ ] A second city tried, to show it is not hardcoded
- [ ] Offline fallback understood, in case venue Wi-Fi fails

**If the venue has no internet**, the system still runs: satellite falls back
to the labelled simulator, and every panel states that clearly. Practise
saying so — an evaluator who sees "SIMULATED" appear and hears you explain the
fallback will trust the rest of the system more, not less.

---

## Monitoring in production

- Data-leg status is exposed in the **Data sources** tab with per-source
  latency.
- `utils.datasources.radar.network_status()` probes the radar network.
- `mosdac.buffer_status()` reports frame-buffer depth.

For a real deployment, alert on: zero live legs, frame buffer not growing for
over 90 minutes, and any source latency above 60 seconds.

---

## Scaling notes

The current design is a single-user interactive dashboard. For an operational
service:

- Split ingestion from serving. Run collectors on a schedule writing to a
  store; serve precomputed nowcasts.
- Cache aggressively — the same INSAT scan serves every user for 30 minutes.
- Move to gridded output (see [08-model-roadmap.md](08-model-roadmap.md)) and
  serve tiles rather than per-request point forecasts.
- Put a queue between ingestion and inference so a slow government endpoint
  cannot stall user requests.
