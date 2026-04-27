# Agent Filesystem Sandboxing Options

Goal: prevent the agent process from reading or modifying its own source code.

---

## Option 1: bubblewrap (recommended)

Unprivileged Linux namespace sandbox — no root required, available on most distros.

```bash
bwrap --ro-bind /usr /usr --ro-bind /lib /lib \
      --bind /home/gokhan/Projects/langbox/models models \
      --bind /tmp /tmp \
      --unshare-all \
      uv run python main.py
```

Mount only what the agent needs (models, data dirs). Source tree is never mounted.

**Pros:** lightweight, no root, no containers  
**Cons:** requires tuning bind mounts for your env paths

---

## Option 2: systemd service sandboxing

Add sandboxing directives to the unit file if running as a service.

```ini
[Service]
ExecStart=/home/gokhan/Projects/langbox/.venv/bin/python main.py
WorkingDirectory=/home/gokhan/Projects/langbox

ReadOnlyPaths=/
ReadWritePaths=/tmp /home/gokhan/.langbox-data
InaccessiblePaths=/home/gokhan/Projects/langbox
NoNewPrivileges=true
ProtectHome=read-only
PrivateTmp=true
```

**Pros:** persistent across reboots, integrates with journald logging  
**Cons:** requires a service unit file, slightly more setup

---

## Option 3: Docker container

Mount only models, `.env`, and a data volume — source stays on the host.

```yaml
# docker-compose.agent.yml
services:
  langbox:
    build: .
    volumes:
      - ./models:/app/models:ro
      - ./.env:/app/.env:ro
      - langbox-data:/app/data
    environment:
      - MODEL_PATH=/app/models
```

**Pros:** strongest isolation, reproducible environment  
**Cons:** most overhead, needs a Dockerfile, adds complexity alongside existing MongoDB compose

---

## Option 4: Python-level path guard (weakest)

A `pathlib` allowlist in any file-access tool or skill handler:

```python
ALLOWED_ROOTS = [Path("/tmp"), Path.home() / ".langbox-data"]

def safe_open(path: str):
    p = Path(path).resolve()
    if not any(p.is_relative_to(r) for r in ALLOWED_ROOTS):
        raise PermissionError(f"Access to {p} is not allowed")
    return open(p)
```

**Pros:** zero infrastructure, easy to add per-skill  
**Cons:** bypassable via subprocess calls; not a real sandbox

---

## Comparison

| Option        | Root required | Overhead | Strength | Setup effort |
|---------------|---------------|----------|----------|--------------|
| bubblewrap    | No            | Minimal  | Strong   | Low          |
| systemd       | No            | Minimal  | Strong   | Medium       |
| Docker        | No (rootless) | High     | Strongest| High         |
| Python guard  | No            | None     | Weak     | Very low     |
