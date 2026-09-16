# Troubleshooting Guide: [Component/Feature Name]

## Quick Diagnosis

### Symptom Flowchart
```
Does the app start? 
├─ NO → Check [Installation Checklist](#installation-checklist)
└─ YES
    ├─ Does it respond to input?
    │  ├─ NO → Check [Input Handling Issues](#input-handling-issues)
    │  └─ YES
    │     ├─ Does [feature] work?
    │     │  ├─ NO → Continue below
    │     │  └─ YES: No issues found
    └─ Other issues? → Scroll to specific section
```

## Common Issues

### Installation & Setup

#### Issue: Virtual environment not activating
**Symptoms:** Commands like `pip install` fail or Python is wrong version

**Diagnosis:**
```bash
which python3
echo $VIRTUAL_ENV  # Should show path to .venv
```

**Solutions:**
1. Recreate the virtual environment:
   ```bash
   rm -rf .venv
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r sidecar/requirements.txt
   ```

2. Verify activation:
   ```bash
   source .venv/bin/activate
   python3 -c "import sys; print(sys.prefix)"  # Should show .venv path
   ```

#### Issue: Missing dependencies
**Symptoms:** `ImportError` or `ModuleNotFoundError` when running sidecar

**Diagnosis:**
```bash
pip list | grep fastapi  # Check if fastapi is installed
pip show fastapi         # Get version info
```

**Solutions:**
```bash
# Reinstall all dependencies
pip install --upgrade -r sidecar/requirements.txt

# Install specific dependency
pip install fastapi==0.104.1
```

### Sidecar Issues

#### Issue: Sidecar won't start
**Symptoms:** Error when running `python3 -m sidecar`

**Diagnosis:**
```bash
# Check Python version
python3 --version  # Must be 3.11+

# Run with verbose output
python3 -m sidecar --debug

# Check logs
tail -f ~/.rigel/rigel.log
```

**Solutions:**
- Ensure Python 3.11+:
  ```bash
  python3.11 -m venv .venv
  source .venv/bin/activate
  ```

- Check for port conflicts:
  ```bash
  lsof -i :5140  # See what's using port 5140
  ```

- Clear any corrupted cache:
  ```bash
  rm -rf ~/.rigel/__pycache__
  ```

#### Issue: Sidecar crashes with database error
**Symptoms:** `sqlite3.OperationalError` or similar

**Diagnosis:**
```bash
# Check database integrity
sqlite3 ~/.rigel/rigel.db "PRAGMA integrity_check;"

# Check database file permissions
ls -la ~/.rigel/rigel.db
```

**Solutions:**
1. Repair database:
   ```bash
   sqlite3 ~/.rigel/rigel.db "VACUUM;"
   sqlite3 ~/.rigel/rigel.db "PRAGMA optimize;"
   ```

2. Reset database (⚠️ clears history):
   ```bash
   rm ~/.rigel/rigel.db
   # Sidecar will recreate it on next run
   python3 -m sidecar
   ```

#### Issue: API endpoint returns 500 error
**Symptoms:** `curl http://127.0.0.1:5140/api/rigel/...` returns error

**Diagnosis:**
```bash
# Check sidecar output for errors
# Check recent logs
sqlite3 ~/.rigel/rigel.db "SELECT * FROM error_log ORDER BY created_at DESC LIMIT 10;"
```

**Solutions:**
- Restart sidecar:
  ```bash
  # Kill existing process
  pkill -f "python3 -m sidecar"
  
  # Start fresh
  python3 -m sidecar
  ```

- Check brain.py for errors:
  ```bash
  python3 -m py_compile sidecar/brain.py
  ```

### Desktop App Issues

#### Issue: App doesn't load (web dev mode)
**Symptoms:** Blank page or connection refused at http://localhost:1425

**Diagnosis:**
```bash
# Check if dev server started
lsof -i :1425

# Check npm output for errors
npm run dev  # Look for error messages
```

**Solutions:**
1. Clear node modules and reinstall:
   ```bash
   cd desktop
   rm -rf node_modules package-lock.json
   npm install
   npm run dev
   ```

2. Check Node version:
   ```bash
   node --version  # Must be 18+
   ```

#### Issue: Tauri app won't start
**Symptoms:** Error when running `npm run tauri dev`

**Diagnosis:**
```bash
# Check Rust installation
cargo --version

# Check for Tauri-specific issues
npm run tauri dev  # Look for specific error
```

**Solutions:**
1. Update Rust:
   ```bash
   rustup update
   ```

2. Clear build cache:
   ```bash
   cd desktop
   rm -rf src-tauri/target
   npm run tauri dev
   ```

3. Reinstall Tauri:
   ```bash
   npm install @tauri-apps/cli@latest
   npm run tauri dev
   ```

#### Issue: Orb isn't animating or appears frozen
**Symptoms:** Orb displays but doesn't breathe/pulse

**Diagnosis:**
```bash
# Check browser console for JavaScript errors
# Open DevTools (F12 in web mode)
# Check console tab for errors

# Check if browser supports CSS animations
# Inspect computed styles on orb element
```

**Solutions:**
1. Clear cache and reload:
   ```bash
   # Hard refresh in browser (Cmd+Shift+R / Ctrl+Shift+R)
   ```

2. Check CSS in RigelOrb component
3. Restart dev server

#### Issue: Messages not appearing in transcript
**Symptoms:** Can type but messages don't show up

**Diagnosis:**
```bash
# Check if sidecar receives the message
curl -X POST http://127.0.0.1:5140/api/rigel/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'

# Check database for recent entries
sqlite3 ~/.rigel/rigel.db "SELECT * FROM conversation_log ORDER BY created_at DESC LIMIT 5;"
```

**Solutions:**
1. Check browser console for errors (F12)
2. Verify sidecar is running and accessible
3. Check network tab to see if requests are being sent
4. Restart both sidecar and desktop app

### Communication Issues

#### Issue: Desktop can't reach sidecar
**Symptoms:** Connection refused errors, timeouts

**Diagnosis:**
```bash
# Test direct connection
curl http://127.0.0.1:5140/api/rigel/health

# Check if sidecar is actually running
ps aux | grep sidecar

# Check firewall
sudo lsof -i :5140
```

**Solutions:**
1. Start sidecar explicitly:
   ```bash
   cd rigel
   source .venv/bin/activate
   python3 -m sidecar
   ```

2. Verify port:
   ```bash
   # If 5140 is in use, kill the process
   lsof -i :5140
   kill -9 <PID>
   ```

3. Check for firewall issues:
   ```bash
   # macOS
   sudo pfctl -s nat | grep 5140
   ```

## Advanced Debugging

### Enable Debug Logging

**Sidecar:**
```python
# In sidecar/app.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Desktop:**
```typescript
// In desktop/src/App.tsx
const DEBUG = true;
if (DEBUG) {
  console.log('Message:', ...args);
}
```

### Inspect Database Directly
```bash
# Open SQLite shell
sqlite3 ~/.rigel/rigel.db

# Useful queries
.tables                              # List all tables
SELECT * FROM conversation_log;      # View all messages
SELECT * FROM command_intents;       # View logged commands
.schema conversation_log             # View table structure
SELECT COUNT(*) FROM conversation_log; # Count messages
```

### Monitor Sidecar in Real-Time
```bash
# Terminal 1: Start sidecar with debug output
python3 -m sidecar --debug

# Terminal 2: Monitor database changes
sqlite3 ~/.rigel/rigel.db ".mode list" ".changes on"

# Terminal 3: Watch log file
tail -f ~/.rigel/rigel.log
```

### Test API Endpoints Directly
```bash
# Chat endpoint
curl -X POST http://127.0.0.1:5140/api/rigel/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'

# Get logs
curl http://127.0.0.1:5140/api/rigel/logs | python3 -m json.tool

# Health check
curl http://127.0.0.1:5140/api/rigel/health
```

## Performance Issues

### App is slow / sluggish
**Diagnosis:**
```bash
# Check system resources
top -o %MEM  # Memory usage
top -o %CPU  # CPU usage

# Check database size
du -h ~/.rigel/rigel.db

# Check number of records
sqlite3 ~/.rigel/rigel.db "SELECT COUNT(*) FROM conversation_log;"
```

**Solutions:**
1. Archive old messages:
   ```bash
   sqlite3 ~/.rigel/rigel.db "DELETE FROM conversation_log WHERE created_at < datetime('now', '-90 days');"
   ```

2. Optimize database:
   ```bash
   sqlite3 ~/.rigel/rigel.db "VACUUM; PRAGMA optimize;"
   ```

3. Clear browser cache (web mode)

## Still Stuck?

### Next Steps
1. **Check logs:**
   ```bash
   tail -f ~/.rigel/rigel.log
   ```

2. **Search existing issues:**
   - GitHub Issues: [project issues](https://github.com/tseneadza/rigel/issues)

3. **Enable verbose mode:**
   ```bash
   DEBUG=true python3 -m sidecar
   ```

4. **Create a bug report:**
   Include:
   - Exact error message
   - Steps to reproduce
   - Output of `python3 --version && node --version && cargo --version`
   - Relevant log excerpts

## Resources
- [Setup Guide](TEMPLATE-SETUP-GUIDE.md)
- [Architecture Guide](TEMPLATE-ARCHITECTURE.md)
- [API Documentation](TEMPLATE-API-ENDPOINT.md)
