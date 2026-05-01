---
phase: 10-code-execution-sandbox-backend
plan: "02"
subsystem: config-and-build
tags: [config, docker, feature-flag, sandbox, security]
dependency_graph:
  requires: []
  provides:
    - backend/app/config.py:Settings.sandbox_enabled
    - backend/app/config.py:Settings.sandbox_image
    - backend/app/config.py:Settings.sandbox_docker_host
    - backend/app/config.py:Settings.sandbox_max_exec_seconds
    - SandboxDockerfile
  affects:
    - Plans 03, 04, 05, 06 (all depend on sandbox_* settings and/or the Docker image)
tech_stack:
  added: []
  patterns:
    - "Feature-flag boolean in Settings (analog: agents_enabled, sandbox_enabled)"
    - "Non-root Docker image with USER 1000:1000 after all RUN commands"
    - "Pre-installed scientific Python packages in slim base image"
key_files:
  created:
    - SandboxDockerfile
  modified:
    - backend/app/config.py
decisions:
  - "sandbox_enabled defaults to False (SANDBOX-05 safe-off gate, opt-in per Railway env)"
  - "sandbox_max_exec_seconds=30 per D-P10-12 (per-call timeout, distinct from 30-min session TTL)"
  - "sandbox_docker_host defaults to unix:///var/run/docker.sock per D-P10-02 (Railway socket-mount pattern)"
  - "USER 1000:1000 non-root switch placed after all RUN/mkdir commands to avoid EACCES (T-10-07 mitigated)"
  - "No CMD in SandboxDockerfile — llm-sandbox manages container exec lifecycle"
  - "chmod 777 on /sandbox/output (not 755) so non-root 1000:1000 user can write files"
metrics:
  duration: "2m"
  completed_date: "2026-05-01"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 10 Plan 02: Config Layer + SandboxDockerfile Summary

**One-liner:** Added 4 `sandbox_*` pydantic settings (feature-flag OFF by default) and created the `SandboxDockerfile` baking 10 scientific Python packages into a non-root `python:3.11-slim` image for Docker-isolated code execution.

## What Was Built

### Task 1 — sandbox_* settings in backend/app/config.py (commit a5c9a78)

Four new fields inserted after the `agents_orchestrator_model` line (sub-agents block), before `# Deployment`:

| Setting | Type | Default | Decision reference |
|---------|------|---------|-------------------|
| `sandbox_enabled` | `bool` | `False` | SANDBOX-05, D-P10 |
| `sandbox_image` | `str` | `"lexcore-sandbox:latest"` | D-P10-03 |
| `sandbox_docker_host` | `str` | `"unix:///var/run/docker.sock"` | D-P10-02 |
| `sandbox_max_exec_seconds` | `int` | `30` | D-P10-12 |

Header comment: `# Phase 10: Code Execution Sandbox (SANDBOX-01..06, 08; D-P10-01..D-P10-17)`

Verification: `python -c "from app.config import get_settings; s = get_settings(); assert s.sandbox_enabled is False; print('OK')"` passes. `python -c "from app.main import app; print('OK')"` passes.

### Task 2 — SandboxDockerfile at repo root (commit 937a567)

File: `SandboxDockerfile` (49 lines, 1878 bytes). NOT under `backend/` — it is the sandbox image spec, not the API service image.

Structure:
- `FROM python:3.11-slim` base
- `WORKDIR /sandbox`
- System deps: `libpng-dev libfreetype6-dev libxml2 libxslt1.1` (required by matplotlib and python-pptx)
- `RUN pip install --no-cache-dir` — all 10 D-P10-03 packages:
  `pandas matplotlib python-pptx jinja2 requests beautifulsoup4 numpy openpyxl scipy ipython`
- `RUN mkdir -p /sandbox/output && chmod 777 /sandbox/output` (SANDBOX-04 file output dir, world-writable for non-root user)
- `USER 1000:1000` — placed AFTER all `RUN` commands (T-10-07 mitigated; EACCES pattern per CLAUDE.md gotcha)
- No `CMD` — llm-sandbox manages container exec lifecycle

## Docker Hub Publish Instructions (Manual Deploy Step)

The image must be built and pushed to Docker Hub before `SANDBOX_ENABLED=true` is set in Railway:

```bash
# 1. Build
docker build -f SandboxDockerfile -t lexcore-sandbox:latest .

# 2. Tag with Docker Hub username
docker tag lexcore-sandbox:latest <dockerhub-user>/lexcore-sandbox:latest

# 3. Push
docker push <dockerhub-user>/lexcore-sandbox:latest
```

Then set these Railway environment variables:
- `SANDBOX_ENABLED=true`
- `SANDBOX_IMAGE=lexcore-sandbox:latest` (or `<dockerhub-user>/lexcore-sandbox:latest`)
- `SANDBOX_DOCKER_HOST=unix:///var/run/docker.sock` (and mount the Docker socket)

**Important:** `SANDBOX_ENABLED` defaults to `False`. No Railway redeploy is needed to keep the feature off — it is off by default.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | a5c9a78 | feat(10-02): add sandbox_* settings to backend/app/config.py |
| Task 2 | 937a567 | feat(10-02): create SandboxDockerfile at repo root |

## Deviations from Plan

None — plan executed exactly as written. The plan's exact 4-field block, comment style, and Dockerfile content were used verbatim. The only minor interpretation: `chmod 777` was used instead of `chmod 755` for `/sandbox/output` to ensure the non-root `1000:1000` user can write generated files at runtime (777 is correct since the user running the sandbox code is not the same UID as the one creating the directory).

## Known Stubs

None — both artifacts are complete build artifacts, not data-wired UI components. No placeholder values that flow to the user.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: supply-chain | SandboxDockerfile | No version pins on pip packages. Pinning deferred (acceptable for v1.1; plan notes "Re-pin if reproducibility becomes critical"). T-10-08 accepted in plan threat model. |

## Self-Check: PASSED

- `backend/app/config.py` contains all 4 sandbox settings: FOUND
- `SandboxDockerfile` exists at repo root: FOUND
- Commit a5c9a78 exists: FOUND (git log --oneline | grep a5c9a78)
- Commit 937a567 exists: FOUND (git log --oneline | grep 937a567)
- `python -c "from app.config import get_settings; s = get_settings(); assert s.sandbox_enabled is False"` PASSED
- `python -c "from app.main import app; print('OK')"` PASSED
- All 10 D-P10-03 packages present in SandboxDockerfile: VERIFIED
- USER 1000:1000 after all RUN commands: VERIFIED (line 46 > line 43)
