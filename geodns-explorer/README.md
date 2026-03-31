# GeoDNS Explorer

Visualize how DNS resolves differently across Indian cities. Query domains from anchor nodes in Mumbai, Delhi, Kolkata, Chennai, Bangalore, and Hyderabad to detect ISP-level blocking, NXDOMAIN variations, and GeoDNS routing.

## Architecture

```
┌──────────────┐    WireGuard     ┌───────────────┐
│  RPi Anchor  │◄────────────────►│   Cloud VM    │
│  mumbai-01   │  10.8.0.x:8053  │               │
│  (dig agent) │                 │  ┌──────────┐ │    ┌──────────┐
├──────────────┤                 │  │ FastAPI  │ │    │  Nginx   │
│  delhi-01    │◄───────────────►│  │ Backend  │◄├────┤ :80/:443 │◄── Users
│  kolkata-01  │                 │  │ :8000    │ │    │ /api/    │
│  chennai-01  │                 │  └──────────┘ │    │ static   │
│  bangalore-01│                 │  ┌──────────┐ │    └──────────┘
│  hyderabad-01│                 │  │ React    │ │
└──────────────┘                 │  │ Frontend │ │
                                 │  └──────────┘ │
                                 └───────────────┘
```

- **Anchor agents** (RPi): lightweight FastAPI wrappers around `dig`
- **Backend**: IP geolocation via ip-api.com (with /24 subnet cache), haversine nearest-anchor selection, async proxy to anchors
- **Frontend**: React + Vite + Tailwind, cinematic hero section, dark theme, query history (last 10 results)

---

## 1. Cloud VM Setup

Prerequisites: Ubuntu 22.04 server with WireGuard hub already configured.

```bash
git clone <repo-url> ~/geodns-explorer
cd ~/geodns-explorer

# Deploy (HTTP only, raw IP — no domain needed)
sudo bash deploy.sh
# App will be live at http://<your-cloud-VM-public-IP>
```

What `deploy.sh` does (in order):
1. Installs Python 3, Node.js 20 LTS, nginx
2. Creates backend venv, installs pip dependencies
3. Builds React frontend, copies to `/var/www/geodns-explorer/`
4. Configures nginx (SPA fallback + `/api/` proxy)
5. Creates and starts `geodns-backend` systemd service

### Adding a domain later (when ready)

```bash
# 1. Point your domain's A record to <cloud-VM-IP>
#    e.g. in Wix DNS: Type A | Host: geodns | Value: <cloud-VM-IP>
#    (gives you geodns.yourdomain.com)

# 2. Wait for DNS to propagate, verify with:
dig geodns.yourdomain.com A
# Replace geodns.yourdomain.com with your actual domain or subdomain

# 3. Re-run deploy:
sudo bash deploy.sh --domain geodns.yourdomain.com
# certbot runs automatically, HTTPS configured

# If using amiphoria.in: first add an A record in Wix DNS:
#   Type: A  |  Host: geodns  |  Value: <your cloud VM IP>
# Then: sudo bash deploy.sh --domain geodns.amiphoria.in
```

### deploy.sh options

```
--domain <domain>  Set nginx server_name + enable HTTPS via certbot
--port <port>      Backend port (default: 8000)
--dry-run          Print all steps without executing
```

---

## 2. Anchor (RPi) Setup

> **⚠️ WireGuard must be configured on the RPi first.** `anchor_setup.sh` installs the dig agent but does NOT configure WireGuard. The cloud backend reaches anchors via their WireGuard IPs (10.8.0.x). Without WireGuard, the anchor works locally but is unreachable from the backend.

For each Raspberry Pi:

```bash
# Copy the setup script to the RPi
scp anchor/anchor_setup.sh pi@<rpi-ip>:~/
scp anchor/anchor_agent.py pi@<rpi-ip>:~/
scp anchor/requirements.txt pi@<rpi-ip>:~/

# SSH in and run
ssh pi@<rpi-ip>
mkdir -p ~/anchor && mv anchor_setup.sh anchor_agent.py requirements.txt ~/anchor/
sudo bash ~/anchor/anchor_setup.sh --anchor-id mumbai-01
```

The script installs Python, creates a venv, and sets up a systemd service.

### Verify anchor is running

```bash
# On the RPi itself:
systemctl status anchor-agent

# Quick test:
curl -s -X POST http://localhost:8053/resolve \
  -H "Content-Type: application/json" \
  -d '{"domain":"cloudflare.com","record_type":"A"}' | python3 -m json.tool
```

---

## 3. Adding a New Anchor

1. **Add entry to `backend/anchors.json`:**
   ```json
   {
     "id": "jaipur-01",
     "city": "Jaipur",
     "wg_ip": "10.8.0.8",
     "lat": 26.9124,
     "lon": 75.7873
   }
   ```

2. **Set up WireGuard peer** on the new RPi (`wg_ip` must match)

3. **Run `anchor_setup.sh`** on the RPi:
   ```bash
   sudo bash anchor_setup.sh --anchor-id jaipur-01
   ```

4. **Restart backend** on the cloud VM:
   ```bash
   sudo systemctl restart geodns-backend
   ```

5. **No frontend rebuild needed** — anchors are loaded from JSON at runtime.

---

## 4. Checking Anchor Reachability

From the cloud VM, test each anchor via its WireGuard IP:

```bash
# Replace 10.8.0.2 with the anchor's wg_ip from anchors.json
curl -X POST http://10.8.0.2:8053/resolve \
  -H "Content-Type: application/json" \
  -d '{"domain":"google.com","record_type":"A"}'
```

Expected: JSON with `answers`, `query_time_ms`, `status: "OK"`, and `anchor_id`.

---

## 5. Viewing Logs

```bash
# Backend (cloud VM)
journalctl -u geodns-backend -f

# Anchor agent (on the RPi)
journalctl -u anchor-agent -f

# Nginx (cloud VM)
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log
```

---

## Troubleshooting

### Backend can't reach an anchor (timeout / UNREACHABLE)

```bash
# 1. Check WireGuard is running on the cloud VM
sudo wg show

# 2. Ping the anchor's WireGuard IP
ping -c 3 10.8.0.2

# 3. Check the anchor agent is running on the RPi
ssh pi@<rpi-ip> "systemctl status anchor-agent"

# 4. Test the anchor directly
curl -m 5 http://10.8.0.2:8053/health
```

If `ping` fails → WireGuard tunnel is down. Check `wg show` on both sides.

### Backend won't start

```bash
# Check the service logs
journalctl -u geodns-backend -n 30

# Common issues:
# - Missing anchors.json → must be in backend/ directory
# - Port conflict → another process on 8000
# - Broken venv → delete backend/venv/ and re-run deploy.sh
```

### Frontend shows "UNREACHABLE" for all anchors

1. First check the backend is running:
   ```bash
   curl http://localhost:8000/api/health
   # Expected: {"status":"ok","anchor_count":6}
   ```
2. If backend is OK → WireGuard is the issue (see "Backend can't reach an anchor" above)
3. If backend is down → `sudo systemctl restart geodns-backend`

---

## Project Structure

```
geodns-explorer/
├── anchor/
│   ├── anchor_agent.py       # FastAPI dig wrapper (runs on RPi)
│   ├── anchor_setup.sh       # RPi setup script (systemd service)
│   └── requirements.txt
├── backend/
│   ├── main.py               # FastAPI app (4 endpoints)
│   ├── geoip.py              # IP geolocation + haversine
│   ├── dns_proxy.py          # Async anchor communication
│   ├── anchors.json          # Anchor registry (6 cities)
│   ├── requirements.txt
│   └── tests/
│       ├── test_geoip.py     # 15 tests
│       └── test_dns_proxy.py # 4 tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts            # Typed fetch client
│   │   └── components/
│   │       ├── HeroSection.tsx
│   │       └── QuerySection.tsx
│   └── vite.config.ts
├── nginx/
│   └── geodns.conf           # Nginx site configuration
├── deploy.sh                 # One-command cloud VM deployment
└── README.md
```
