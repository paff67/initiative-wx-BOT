# Hermes Observer Overlay

This directory contains the Observer source used by the wx proactive presence system.

Runtime deployment path on the VPS:

```text
/home/hermes/hermes-observer
```

Tracked here:

- FastAPI backend source under `backend/app/`
- React/Vite frontend source under `frontend/`
- package manifests needed to rebuild the frontend

Not tracked:

- `node_modules/`
- frontend `dist/`
- backend virtualenvs
- logs and runtime state
