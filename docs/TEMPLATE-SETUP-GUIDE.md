# Setup Guide: [Feature/Component Name]

## Overview
Step-by-step instructions for setting up [feature/component], including prerequisites, configuration, and verification.

## Prerequisites

### System Requirements
- **OS:** macOS 12+ / Windows 11+ / Linux (X11/Wayland)
- **RAM:** [Recommended amount]
- **Disk Space:** [Required space]
- **Network:** [If applicable]

### Software Dependencies
| Dependency | Version | How to Install |
|-----------|---------|-----------------|
| Python | 3.11+ | [brew install python@3.11](https://brew.sh) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | stable | [rustup](https://rustup.rs) |

### Environment Setup
Do you already have the main Rigel environment set up? Confirm by running:
```bash
python3 --version  # Should be 3.11+
node --version     # Should be 18+
cargo --version    # Should exist
```

## Step-by-Step Setup

### Step 1: [First Setup Task]
**Goal:** [What this accomplishes]

```bash
# Command to run
cd rigel
python3 -m venv .venv
source .venv/bin/activate
```

**Expected Output:**
```
(.venv) $ 
```

**Troubleshooting:**
- **Error:** `venv: command not found`
  - **Solution:** Install Python development headers: `brew install python3-dev`

### Step 2: [Second Setup Task]
**Goal:** [What this accomplishes]

```bash
pip install -r sidecar/requirements.txt
```

**Verification:**
```bash
python3 -c "import fastapi; print(fastapi.__version__)"
```

### Step 3: [Third Setup Task]
**Goal:** [What this accomplishes]

```bash
cd desktop
npm install
```

**Expected Output:**
```
added XXX packages in XXs
```

## Configuration

### Environment Variables
Create or update `.env` file in the project root:

```bash
# Required
RIGEL_DB_PATH=~/.rigel/rigel.db
SIDECAR_PORT=5140
DESKTOP_PORT=1425

# Optional
DEBUG=false
LOG_LEVEL=info
```

### Configuration Files
- **File:** `sidecar/config.py`
  - **Purpose:** Sidecar configuration
  - **Required Settings:**
    - `DATABASE_URL`: Path to SQLite database
    - `API_PORT`: Port for FastAPI server

- **File:** `desktop/vite.config.ts`
  - **Purpose:** Frontend build configuration
  - **Key Settings:**
    - `server.port`: Development server port
    - `build.target`: Build target

## Running

### Development Mode
**Terminal 1 - Sidecar:**
```bash
cd rigel
source .venv/bin/activate
python3 -m sidecar
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:5140
```

**Terminal 2 - Desktop (web preview):**
```bash
cd rigel/desktop
npm run dev
```

Expected output:
```
  ➜  Local:   http://localhost:1425/
```

**Terminal 2 Alternative - Desktop (native window):**
```bash
cd rigel/desktop
npm run tauri dev
```

### Production Build
```bash
# Build desktop app
cd rigel/desktop
npm run build
npm run tauri build  # Creates native bundles

# Or run web build only
npm run build:web
```

## Verification

### Health Check Checklist
- [ ] Sidecar API responds to requests
  ```bash
  curl http://127.0.0.1:5140/api/rigel/health
  ```
  Expected: `{"status": "healthy"}`

- [ ] Database is initialized
  ```bash
  ls -la ~/.rigel/rigel.db
  ```
  Expected: File exists

- [ ] Desktop app loads
  - Navigate to http://localhost:1425 (web) or check native window (Tauri)
  - Orb is visible and animated
  - Console loads without errors

- [ ] Can send messages
  - Type a test message in the console
  - Message appears in transcript
  - Sidecar logs the message

### Testing Commands
```bash
# Test API endpoints
curl http://127.0.0.1:5140/api/rigel/logs | python3 -m json.tool

# Check database
sqlite3 ~/.rigel/rigel.db ".tables"

# View recent logs
sqlite3 ~/.rigel/rigel.db "SELECT * FROM conversation_log ORDER BY created_at DESC LIMIT 5;"
```

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'fastapi'`
**Cause:** Dependencies not installed or wrong virtual environment
**Solution:**
```bash
source .venv/bin/activate
pip install -r sidecar/requirements.txt
```

### Issue: `Port 5140 already in use`
**Cause:** Sidecar already running or another process using the port
**Solution:**
```bash
# Find process
lsof -i :5140
# Kill it
kill -9 <PID>
```

### Issue: `npm ERR! code ERESOLVE`
**Cause:** Node/npm version mismatch
**Solution:**
```bash
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Issue: Tauri build fails with `cargo not found`
**Cause:** Rust not installed
**Solution:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## Next Steps
- [ ] Read [Architecture Overview](TEMPLATE-ARCHITECTURE.md)
- [ ] Explore [API Documentation](TEMPLATE-API-ENDPOINT.md)
- [ ] Run [Feature Guide](TEMPLATE-FEATURE.md)
- [ ] Check [Contributing Guide](README.md#contributing)

## Getting Help
- **Stuck?** Check [Troubleshooting](#troubleshooting) above
- **Have questions?** Open an issue on GitHub
- **Want to contribute?** See [Contributing Guide](../../CONTRIBUTING.md)
