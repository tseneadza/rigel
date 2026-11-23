# Checking the sidecars (Rigel and OSA)

Two Python sidecars run on this Mac. They are different programs. Check them by path, not by name.

| Name | Folder it runs from | Process to look for | Port |
|---|---|---|---|
| Rigel | `~/Codehome/rigel` | `python -m sidecar` | 5140 |
| OSA / AgenticOS | `~/Codehome/AgenticOS` | `gui.sidecar` | none on 5140 |

## Check if running

```bash
# Rigel
pgrep -fl "python -m sidecar"

# OSA / AgenticOS
pgrep -fl "gui.sidecar"

# Who is listening on Rigel's port (5140)
lsof -nP -iTCP:5140 -sTCP:LISTEN
```

No output means that sidecar is not running.

To see which folder a process came from:

```bash
ps -o pid,ppid,etime,command -p <PID>
```

## Stop

```bash
# Rigel (stops until you start it again)
pkill -f "python -m sidecar"
```

OSA is managed by launchd (`~/Library/LaunchAgents/com.agentcos.sidecar.plist`), which restarts it when it stops. Stopping it with `kill` only works for a moment. To stop it for good:

```bash
launchctl unload ~/Library/LaunchAgents/com.agentcos.sidecar.plist
```

To start it again:

```bash
launchctl load ~/Library/LaunchAgents/com.agentcos.sidecar.plist
```

## Start Rigel's sidecar (from the Rigel repo)

```bash
cd ~/Codehome/rigel
nohup .venv/bin/python -m sidecar > /tmp/rigel-sidecar.log 2>&1 &
```

Log: `/tmp/rigel-sidecar.log`.

## Suggested aliases (not yet added to ~/.zshrc)

```bash
alias rigel-status='pgrep -fl "python -m sidecar" || echo "Rigel sidecar: not running"'
alias osa-status='pgrep -fl "gui.sidecar" || echo "OSA sidecar: not running"'
alias rigel-port='lsof -nP -iTCP:5140 -sTCP:LISTEN'
alias rigel-stop='pkill -f "python -m sidecar"'
alias osa-off='launchctl unload ~/Library/LaunchAgents/com.agentcos.sidecar.plist'
alias osa-on='launchctl load ~/Library/LaunchAgents/com.agentcos.sidecar.plist'
```

Add them to `~/.zshrc`, then run `source ~/.zshrc`.
