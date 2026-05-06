"""API routers for Linjiang Observer."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone, timedelta
import hashlib
import subprocess
from typing import Any, Optional, List

from fastapi import APIRouter, Query, Header, HTTPException, Request, Body, Depends
from pydantic import BaseModel

from ..config import (
    INTERNAL_STATE_PATH, STATE_EVENTS_PATH, DECISION_EVENTS_PATH,
    HEARTBEAT_STATE_PATH, PROXY_REQUESTS_PATH, STATE_TICK_LOG_PATH,
    SOUL_PATH, USER_PATH, MEMORY_PATH, STATE_DB_PATH,
    PROACTIVE_CONTROL_PATH, OBSERVER_EVENTS_PATH, PROACTIVE_PROMPT_PATH, PROMPT_BACKUPS_DIR,
    PRESENCE_HOME, PRESENCE_PROFILES_DIR, PRESENCE_RUNTIME_DIR, PRESENCE_EVENTS_DIR,
    PRESENCE_KERNEL_DIR, PRESENCE_CONFIG_BACKUPS_DIR,
    ENABLE_WRITES, ENABLE_HUMAN_FEEDBACK, ENABLE_PROMPT_EDIT, CONTROL_TOKEN,
    MAX_FEEDBACK_CHARS, MAX_PROMPT_BYTES, HERMES_HOME
)
from ..readers.jsonl_tail import tail_jsonl, read_json_file
import fcntl

def require_token():
    # Token check removed; authentication is handled by Cloudflare Access
    return "cloudflare-access"

def require_writes():
    if not ENABLE_WRITES:
        raise HTTPException(status_code=403, detail="Writes are disabled by server configuration")

def require_feedback():
    if not ENABLE_HUMAN_FEEDBACK:
        raise HTTPException(status_code=403, detail="Human feedback is disabled by server configuration")

def append_audit_event(event: dict[str, Any]):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        OBSERVER_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OBSERVER_EVENTS_PATH.open("a", encoding="utf-8") as fh:
            import json
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

router = APIRouter(prefix="/api")


# ── Health ──────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    """Observer health check — reports file readability."""
    def file_status(path):
        try:
            exists = path.exists()
            readable = os.access(path, os.R_OK) if exists else False
            size = path.stat().st_size if exists else 0
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if exists else None
            return {"path": str(path), "exists": exists, "readable": readable, "size_bytes": size, "mtime": mtime}
        except Exception as e:
            return {"path": str(path), "exists": False, "error": str(e)[:200]}

    return {
        "status": "ok",
        "server_time": datetime.now(timezone.utc).isoformat(),
        "files": {
            "internal_state": file_status(INTERNAL_STATE_PATH),
            "state_events": file_status(STATE_EVENTS_PATH),
            "decision_events": file_status(DECISION_EVENTS_PATH),
            "heartbeat_state": file_status(HEARTBEAT_STATE_PATH),
            "proxy_requests": file_status(PROXY_REQUESTS_PATH),
            "state_db": file_status(STATE_DB_PATH),
            "state_tick_log": file_status(STATE_TICK_LOG_PATH),
            "presence_home": file_status(PRESENCE_HOME),
            "presence_state": file_status(PRESENCE_RUNTIME_DIR / "state.json"),
            "presence_intent": file_status(PRESENCE_RUNTIME_DIR / "intent-state.json"),
            "presence_decision_events": file_status(PRESENCE_EVENTS_DIR / "decision-events.jsonl"),
            "presence_trace_events": file_status(PRESENCE_EVENTS_DIR / "trace-events.jsonl"),
        },
    }


# ── State ───────────────────────────────────────────────────────────────────

@router.get("/state/current")
def state_current():
    """Current Linjiang internal state snapshot."""
    data = read_json_file(INTERNAL_STATE_PATH)
    if data is None:
        return {"error": "state file not found or unreadable", "path": str(INTERNAL_STATE_PATH)}
    return data


@router.get("/state/events")
def state_events(limit: int = Query(50, ge=1, le=500)):
    """Historical state-layer events (newest first)."""
    return tail_jsonl(STATE_EVENTS_PATH, limit)


# ── Decisions ───────────────────────────────────────────────────────────────

@router.get("/decisions")
def decisions(limit: int = Query(50, ge=1, le=500), include_dry_run: bool = False):
    """Presence Kernel production decision history (newest first)."""
    rows = tail_jsonl(PRESENCE_EVENTS_DIR / "decision-events.jsonl", limit * 3 if not include_dry_run else limit)
    if not include_dry_run:
        rows = [row for row in rows if row.get("dry_run") is False]
    return rows[:limit]


@router.get("/decisions/latest")
def decisions_latest(include_dry_run: bool = False):
    """Most recent Presence Kernel production decision event."""
    rows = tail_jsonl(PRESENCE_EVENTS_DIR / "decision-events.jsonl", 50)
    if not include_dry_run:
        rows = [row for row in rows if row.get("dry_run") is False]
    return rows[0] if rows else {"info": "no decision events yet"}


# ── Heartbeat State & Control ──────────────────────────────────────────────────

class ControlRequest(BaseModel):
    action: str
    expected_revision: Optional[int] = None
    duration_minutes: Optional[int] = None
    reason: Optional[str] = None
    bypass_guards: Optional[bool] = False

class FeedbackRequest(BaseModel):
    target_run_id: str
    content: str


@router.get("/heartbeat/state")
def heartbeat_state():
    """Current proactive heartbeat state (cooldown, counts)."""
    data = read_json_file(HEARTBEAT_STATE_PATH)
    if data is None:
        return {"info": "heartbeat state file not found (no sends yet)", "path": str(HEARTBEAT_STATE_PATH)}
    return data


@router.get("/heartbeat/control")
def get_heartbeat_control():
    """Current manual overrides and human feedback."""
    data = read_json_file(PROACTIVE_CONTROL_PATH)
    if data is None:
        return {"schema_version": 1, "revision": 1, "override": {}, "operator_feedback": []}
    return data


@router.post("/heartbeat/control")
def apply_heartbeat_control(req: ControlRequest, token: str = Depends(require_token)):
    require_writes()
    import json

    try:
        PROACTIVE_CONTROL_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not PROACTIVE_CONTROL_PATH.exists():
            with PROACTIVE_CONTROL_PATH.open("w", encoding="utf-8") as f:
                json.dump({"schema_version": 1, "revision": 1, "override": {}, "operator_feedback": []}, f)

        with PROACTIVE_CONTROL_PATH.open("r+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                data = json.load(fh)
            except Exception:
                data = {"schema_version": 1, "revision": 1, "override": {}, "operator_feedback": []}

            if req.expected_revision is not None and data.get("revision", 1) != req.expected_revision:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                raise HTTPException(status_code=409, detail=f"Conflict: Expected revision {req.expected_revision}, got {data.get('revision')}")

            old_rev = data.get("revision", 1)
            data["revision"] = old_rev + 1
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

            if req.action == "clear":
                data["override"] = {"consumed": True}
            else:
                expires_at = None
                if req.action == "pause_until" and req.duration_minutes:
                    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=req.duration_minutes)).isoformat()
                elif req.action in ("force_silent_next", "standby_next"):
                    expires_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

                data["override"] = {
                    "mode": req.action,
                    "reason": req.reason or "Set by observer-ui",
                    "consume_on_next_run": req.action != "pause_until",
                    "expires_at": expires_at,
                    "bypass_pre_llm_guards": bool(req.bypass_guards or req.action == "standby_next"),
                    "consumed": False
                }

            fh.seek(0)
            fh.truncate()
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

            append_audit_event({"action": "override_set", "req": req.model_dump(), "old_rev": old_rev, "new_rev": data["revision"]})
            return {"status": "success", "revision": data["revision"], "override": data.get("override")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat/feedback")
def apply_heartbeat_feedback(req: FeedbackRequest, token: str = Depends(require_token)):
    require_writes()
    require_feedback()
    import json

    if len(req.content) > MAX_FEEDBACK_CHARS:
        raise HTTPException(status_code=400, detail=f"Feedback exceeds {MAX_FEEDBACK_CHARS} characters.")

    try:
        if not PROACTIVE_CONTROL_PATH.exists():
            return {"error": "control file does not exist"}

        with PROACTIVE_CONTROL_PATH.open("r+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            data = json.load(fh)

            old_rev = data.get("revision", 1)
            data["revision"] = old_rev + 1
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

            if "operator_feedback" not in data:
                data["operator_feedback"] = []

            fb = {
                "id": f"fb_{int(time.time()*1000)}",
                "target_run_id": req.target_run_id,
                "scope": "next_run_only",
                "content": req.content,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                "consumed": False
            }
            data["operator_feedback"].append(fb)
            data["operator_feedback"] = data["operator_feedback"][-20:]

            fh.seek(0)
            fh.truncate()
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

            append_audit_event({"action": "feedback_added", "req": req.model_dump(), "old_rev": old_rev, "new_rev": data["revision"]})
            return {"status": "success", "revision": data["revision"], "feedback": fb}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat/trigger")
def trigger_heartbeat_manually():
    require_writes()

    script_path = HERMES_HOME / "scripts" / "presence_tick.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Heartbeat script not found: {script_path}")

    try:
        # Run the shell wrapper synchronously with a generous timeout.
        # It handles executing Python and formatting crashes into JSONL if needed.
        result = subprocess.run(
            ["python3", str(script_path)],
            cwd=str(HERMES_HOME),
            capture_output=True,
            text=True,
            timeout=120
        )

        return {
            "status": "ok",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Script execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute script: {str(e)}")

@router.post("/state/trigger")
def trigger_state_tick_manually():
    require_writes()

    script_path = HERMES_HOME / "scripts" / "presence_tick.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail="State tick script not found")

    try:
        result = subprocess.run(
            ["python3", str(script_path), "--dry-run", "--force-llm"],
            cwd=str(HERMES_HOME),
            capture_output=True,
            text=True,
            timeout=120
        )

        return {
            "status": "ok",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Script execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute script: {str(e)}")

# ── Proxy Calls ─────────────────────────────────────────────────────────────

MODEL_PROBE_PATHS = {
    "/api/v1/models", "/api/tags", "/v1/props", "/props", "/version"
}


def _proxy_status(row: dict[str, Any]) -> int:
    try:
        return int(row.get("client_status") or row.get("upstream_status") or 0)
    except Exception:
        return 0


def _is_chat_proxy_path(path: str) -> bool:
    return path.endswith("/chat/completions") or path.endswith("/responses")


def _is_model_probe_path(path: str) -> bool:
    return path in MODEL_PROBE_PATHS


def _is_proxy_error(row: dict[str, Any]) -> bool:
    outcome = str(row.get("outcome") or "")
    if outcome:
        return outcome != "success"
    return _proxy_status(row) >= 400

@router.get("/proxy/calls")
def proxy_calls(limit: int = Query(50, ge=1, le=500)):
    """Recent proxy gateway request log (newest first)."""
    return tail_jsonl(PROXY_REQUESTS_PATH, limit)


@router.get("/proxy/stats")
def proxy_stats():
    """Aggregate proxy stats from the last 200 requests."""
    rows = tail_jsonl(PROXY_REQUESTS_PATH, 200)
    if not rows:
        return {
            "total": 0,
            "all_error_rate": 0,
            "chat_total": 0,
            "chat_error_rate": 0,
            "model_probe_errors": 0,
            "outcome_distribution": {},
            "avg_latency_ms": 0,
            "client_closed": 0,
            "retry_exhausted": 0,
        }
    status_counts: dict[int, int] = {}
    outcome_counts: dict[str, int] = {}
    total_latency = 0
    chat_total = 0
    chat_errors = 0
    model_probe_errors = 0
    errors = 0
    for r in rows:
        status = _proxy_status(r)
        status_counts[status] = status_counts.get(status, 0) + 1
        outcome = str(r.get("outcome") or ("success" if status < 400 else "error"))
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        lat = r.get("latency_ms", 0) or 0
        total_latency += lat
        path = str(r.get("path") or "")
        is_error = _is_proxy_error(r)
        if _is_chat_proxy_path(path):
            chat_total += 1
            if is_error:
                chat_errors += 1
        if _is_model_probe_path(path) and is_error:
            model_probe_errors += 1
        if is_error:
            errors += 1
    return {
        "total": len(rows),
        "chat_total": chat_total,
        "chat_completions": chat_total,
        "errors": errors,
        "all_error_rate": round(errors / len(rows), 3) if rows else 0,
        "chat_error_rate": round(chat_errors / chat_total, 3) if chat_total else 0,
        "model_probe_errors": model_probe_errors,
        "error_rate": round(chat_errors / chat_total, 3) if chat_total else 0,
        "avg_latency_ms": round(total_latency / len(rows)) if rows else 0,
        "client_closed": outcome_counts.get("client_closed", 0) + outcome_counts.get("client_cancelled", 0),
        "retry_exhausted": outcome_counts.get("retry_exhausted", 0),
        "outcome_distribution": dict(sorted(outcome_counts.items())),
        "status_distribution": {str(k): v for k, v in sorted(status_counts.items())},
    }


# ── Logs tail ───────────────────────────────────────────────────────────────

@router.get("/logs/state-tick")
def logs_state_tick(tail: int = Query(100, ge=1, le=500)):
    """Tail of the state-tick cron log."""
    try:
        if not STATE_TICK_LOG_PATH.exists():
            return {"lines": [], "error": "log not found"}
        with STATE_TICK_LOG_PATH.open("r", encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
        return {"lines": [l.rstrip() for l in all_lines[-tail:]]}
    except Exception as e:
        return {"lines": [], "error": str(e)[:200]}


# ── Settings & Prompt Editor ──────────────────────────────────────────────────

class PromptRequest(BaseModel):
    content: str
    expected_sha256: str
    confirm_diff: bool = False


class PromptRollbackRequest(BaseModel):
    backup_filename: str
    expected_current_sha256: str
    confirm_rollback: bool = False


class ProfileConfigRequest(BaseModel):
    kind: str
    content: str
    expected_sha256: Optional[str] = None
    confirm_write: bool = False


class ProfileConfigRollbackRequest(BaseModel):
    kind: str
    backup_filename: str
    expected_current_sha256: Optional[str] = None
    confirm_rollback: bool = False


class PreviewRequest(BaseModel):
    profile_id: str = "linjiang"
    mode: str = "full"
    force_llm: bool = True


class WorldSignalReviewRequest(BaseModel):
    action: str
    reason: Optional[str] = None


def _prompt_sha256(path):
    with path.open("rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _safe_prompt_backup_path(filename: str):
    if not filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    path = (PROMPT_BACKUPS_DIR / filename).resolve()
    root = PROMPT_BACKUPS_DIR.resolve()
    if root not in path.parents or path.suffix != ".md":
        raise HTTPException(status_code=400, detail="Invalid backup path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    return path

def _safe_key(val: str) -> str:
    if not val:
        return "unset"
    if len(val) <= 10:
        return "set(***)"
    return f"set({val[:4]}...{val[-4:]})"


@router.get("/settings")
def settings():
    """Sanitized, read-only view of configuration."""
    def mtime(path):
        try:
            if path.exists():
                return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except Exception:
            pass
        return None

    return {
        "files": {
            "soul": {"path": str(SOUL_PATH), "mtime": mtime(SOUL_PATH), "exists": SOUL_PATH.exists()},
            "user": {"path": str(USER_PATH), "mtime": mtime(USER_PATH), "exists": USER_PATH.exists()},
            "memory": {"path": str(MEMORY_PATH), "mtime": mtime(MEMORY_PATH), "exists": MEMORY_PATH.exists()},
            "internal_state": {"path": str(INTERNAL_STATE_PATH), "mtime": mtime(INTERNAL_STATE_PATH)},
        },
        "env_hints": {
            "decision_model": os.environ.get("WX_PROACTIVE_DECISION_MODEL", "gpt-5.4-mini"),
            "decision_base_url": os.environ.get("WX_PROACTIVE_DECISION_BASE_URL", "http://127.0.0.1:8788/v1"),
            "decision_api_key": _safe_key(os.environ.get("WX_PROACTIVE_DECISION_API_KEY", "")),
            "state_model": os.environ.get("WX_LINJIANG_STATE_MODEL", "gpt-5.4-mini"),
            "state_base_url": os.environ.get("WX_LINJIANG_STATE_BASE_URL", "http://127.0.0.1:8788/v1"),
            "daily_max": os.environ.get("WX_PROACTIVE_DAILY_MAX", "3"),
            "min_gap_minutes": os.environ.get("WX_PROACTIVE_MIN_GAP_MINUTES", "180"),
        },
        "features": {
            "enable_writes": ENABLE_WRITES,
            "enable_human_feedback": ENABLE_HUMAN_FEEDBACK,
            "enable_prompt_edit": ENABLE_PROMPT_EDIT,
        }
    }


@router.get("/settings/decision-prompt")
def get_decision_prompt():
    if not PROACTIVE_PROMPT_PATH.exists():
        raise HTTPException(status_code=404, detail="Prompt file not found")
    with PROACTIVE_PROMPT_PATH.open("rb") as f:
        content = f.read()
    sha = hashlib.sha256(content).hexdigest()
    return {"content": content.decode("utf-8"), "sha256": sha}


@router.post("/settings/decision-prompt")
def update_decision_prompt(req: PromptRequest, token: str = Depends(require_token)):
    require_writes()
    if not ENABLE_PROMPT_EDIT:
        raise HTTPException(status_code=403, detail="Prompt editing is disabled by server configuration")

    if len(req.content.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise HTTPException(status_code=400, detail=f"Prompt exceeds max size of {MAX_PROMPT_BYTES} bytes")

    if not PROACTIVE_PROMPT_PATH.exists():
        raise HTTPException(status_code=404, detail="Original prompt file not found")

    with PROACTIVE_PROMPT_PATH.open("rb") as f:
        old_content = f.read()
    old_sha = hashlib.sha256(old_content).hexdigest()

    if req.expected_sha256 and old_sha != req.expected_sha256:
        raise HTTPException(status_code=409, detail=f"Conflict: Expected SHA {req.expected_sha256}, got {old_sha}")

    if not req.confirm_diff:
        # Just a dry-run check or diff request
        new_sha = hashlib.sha256(req.content.encode("utf-8")).hexdigest()
        return {"status": "diff_required", "old_sha256": old_sha, "new_sha256": new_sha}

    # Backup
    PROMPT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = PROMPT_BACKUPS_DIR / f"wx-proactive-decision-prompt.{ts}.{old_sha[:8]}.md"
    backup_path.write_bytes(old_content)

    # Atomic write
    tmp_path = PROACTIVE_PROMPT_PATH.with_suffix(".tmp")
    tmp_path.write_bytes(req.content.encode("utf-8"))
    tmp_path.replace(PROACTIVE_PROMPT_PATH)

    append_audit_event({"action": "prompt_updated", "old_sha": old_sha, "new_sha": hashlib.sha256(req.content.encode("utf-8")).hexdigest(), "backup": str(backup_path)})

    return {"status": "success", "new_sha256": hashlib.sha256(req.content.encode("utf-8")).hexdigest(), "backup_created": str(backup_path)}

@router.get("/settings/decision-prompt/backups")
def list_decision_prompt_backups():
    require_writes()
    PROMPT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    for path in sorted(PROMPT_BACKUPS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        try:
            backups.append({
                "filename": path.name,
                "path": str(path),
                "sha256": _prompt_sha256(path),
                "size_bytes": path.stat().st_size,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        except Exception:
            continue
    return {"backups": backups}


@router.post("/settings/decision-prompt/rollback")
def rollback_decision_prompt(req: PromptRollbackRequest, token: str = Depends(require_token)):
    require_writes()
    if not ENABLE_PROMPT_EDIT:
        raise HTTPException(status_code=403, detail="Prompt editing is disabled by server configuration")
    if not req.confirm_rollback:
        raise HTTPException(status_code=400, detail="Rollback requires confirm_rollback=true")
    if not PROACTIVE_PROMPT_PATH.exists():
        raise HTTPException(status_code=404, detail="Current prompt file not found")

    backup_path = _safe_prompt_backup_path(req.backup_filename)
    current_sha = _prompt_sha256(PROACTIVE_PROMPT_PATH)
    if req.expected_current_sha256 and current_sha != req.expected_current_sha256:
        raise HTTPException(status_code=409, detail=f"Conflict: Expected SHA {req.expected_current_sha256}, got {current_sha}")

    PROMPT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    current_content = PROACTIVE_PROMPT_PATH.read_bytes()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_rollback_backup = PROMPT_BACKUPS_DIR / f"wx-proactive-decision-prompt.pre-rollback.{ts}.{current_sha[:8]}.md"
    pre_rollback_backup.write_bytes(current_content)

    restored_content = backup_path.read_bytes()
    if len(restored_content) > MAX_PROMPT_BYTES:
        raise HTTPException(status_code=400, detail=f"Backup exceeds max size of {MAX_PROMPT_BYTES} bytes")
    tmp_path = PROACTIVE_PROMPT_PATH.with_suffix(".tmp")
    tmp_path.write_bytes(restored_content)
    tmp_path.replace(PROACTIVE_PROMPT_PATH)
    restored_sha = hashlib.sha256(restored_content).hexdigest()

    append_audit_event({
        "action": "prompt_rollback",
        "old_sha": current_sha,
        "new_sha": restored_sha,
        "restored_from": str(backup_path),
        "pre_rollback_backup": str(pre_rollback_backup),
    })
    return {
        "status": "success",
        "new_sha256": restored_sha,
        "restored_from": str(backup_path),
        "pre_rollback_backup": str(pre_rollback_backup),
    }


# ── Presence Kernel: Profiles, Preview, Traces ──────────────────────────────

PROFILE_CONFIG_KINDS = {
    "manifest": "manifest.yaml",
    "persona": "persona.yaml",
    "relationship": "relationship.yaml",
    "proactive_policy": "proactive_policy.yaml",
    "world_policy": "world_policy.yaml",
    "permission_policy": "permission_policy.yaml",
    "delivery": "delivery_weixin.yaml",
    "examples": "examples.yaml",
    "voice": "voice.md",
}


def _safe_profile_id(profile_id: str) -> str:
    if not profile_id or "/" in profile_id or "\\" in profile_id or profile_id.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid profile_id")
    return profile_id


def _profile_dir(profile_id: str):
    profile_id = _safe_profile_id(profile_id)
    path = (PRESENCE_PROFILES_DIR / profile_id).resolve()
    root = PRESENCE_PROFILES_DIR.resolve()
    if root not in path.parents and path != root:
        raise HTTPException(status_code=400, detail="Invalid profile path")
    return path


def _profile_config_path(profile_id: str, kind: str):
    filename = PROFILE_CONFIG_KINDS.get(kind)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unsupported config kind: {kind}")
    return _profile_dir(profile_id) / filename


def _safe_profile_config_backup_path(profile_id: str, kind: str, filename: str):
    _safe_profile_id(profile_id)
    if kind not in PROFILE_CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"Unsupported config kind: {kind}")
    if not filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    path = (PRESENCE_CONFIG_BACKUPS_DIR / filename).resolve()
    root = PRESENCE_CONFIG_BACKUPS_DIR.resolve()
    if root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid backup path")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")
    if not path.name.startswith(f"{profile_id}.{kind}."):
        raise HTTPException(status_code=400, detail="Backup does not belong to this profile config")
    return path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_profile_config_text(kind: str, content: str):
    if kind == "voice":
        return None
    try:
        import yaml
        parsed = yaml.safe_load(content) if content.strip() else {}
        if parsed is not None and not isinstance(parsed, (dict, list)):
            return "YAML root must be a map or list"
    except Exception as exc:
        return str(exc)[:500]
    return None


@router.get("/profiles")
def presence_profiles():
    profiles = []
    if PRESENCE_PROFILES_DIR.exists():
        for path in sorted(PRESENCE_PROFILES_DIR.iterdir()):
            if not path.is_dir():
                continue
            manifest = read_json_file(path / "manifest.json")
            if manifest is None:
                try:
                    import yaml
                    manifest = yaml.safe_load((path / "manifest.yaml").read_text(encoding="utf-8")) or {}
                except Exception:
                    manifest = {}
            profiles.append({
                "profile_id": path.name,
                "display_name": manifest.get("display_name", path.name),
                "channel": manifest.get("channel", ""),
                "timezone": manifest.get("timezone", ""),
                "path": str(path),
            })
    return {"profiles": profiles}


@router.get("/profiles/{profile_id}/config")
def presence_profile_config(profile_id: str):
    base = _profile_dir(profile_id)
    files = {}
    for kind, filename in PROFILE_CONFIG_KINDS.items():
        path = base / filename
        if not path.exists():
            files[kind] = {"exists": False, "path": str(path), "content": "", "sha256": ""}
            continue
        data = path.read_bytes()
        files[kind] = {
            "exists": True,
            "path": str(path),
            "content": data.decode("utf-8", errors="replace"),
            "sha256": _sha256_bytes(data),
            "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
    return {"profile_id": profile_id, "files": files}


@router.post("/profiles/{profile_id}/config")
def update_presence_profile_config(profile_id: str, req: ProfileConfigRequest, token: str = Depends(require_token)):
    require_writes()
    path = _profile_config_path(profile_id, req.kind)
    validation_error = _validate_profile_config_text(req.kind, req.content)
    if validation_error:
        raise HTTPException(status_code=400, detail=f"Invalid {req.kind}: {validation_error}")
    old = path.read_bytes() if path.exists() else b""
    old_sha = _sha256_bytes(old)
    if req.expected_sha256 and req.expected_sha256 != old_sha:
        raise HTTPException(status_code=409, detail=f"Conflict: Expected SHA {req.expected_sha256}, got {old_sha}")
    new = req.content.encode("utf-8")
    new_sha = _sha256_bytes(new)
    if not req.confirm_write:
        return {"status": "diff_required", "old_sha256": old_sha, "new_sha256": new_sha}
    PRESENCE_CONFIG_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if path.exists():
        backup = PRESENCE_CONFIG_BACKUPS_DIR / f"{profile_id}.{req.kind}.{ts}.{old_sha[:8]}.{path.suffix.lstrip('.')}"
        backup.write_bytes(old)
    else:
        backup = None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(new)
    tmp.replace(path)
    append_audit_event({"action": "presence_config_updated", "profile_id": profile_id, "kind": req.kind, "old_sha": old_sha, "new_sha": new_sha, "backup": str(backup) if backup else None})
    return {"status": "success", "new_sha256": new_sha, "backup": str(backup) if backup else None}


@router.get("/profiles/{profile_id}/config/backups")
def list_presence_profile_config_backups(profile_id: str, kind: Optional[str] = None):
    _safe_profile_id(profile_id)
    if kind is not None and kind not in PROFILE_CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"Unsupported config kind: {kind}")
    PRESENCE_CONFIG_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    for path in sorted(PRESENCE_CONFIG_BACKUPS_DIR.glob(f"{profile_id}.*"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            parts = path.name.split(".")
            if len(parts) < 5:
                continue
            backup_kind = parts[1]
            if backup_kind not in PROFILE_CONFIG_KINDS:
                continue
            if kind and backup_kind != kind:
                continue
            data = path.read_bytes()
            backups.append({
                "filename": path.name,
                "profile_id": profile_id,
                "kind": backup_kind,
                "path": str(path),
                "sha256": _sha256_bytes(data),
                "size_bytes": path.stat().st_size,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        except Exception:
            continue
    return {"profile_id": profile_id, "kind": kind, "backups": backups[:100]}


@router.post("/profiles/{profile_id}/config/rollback")
def rollback_presence_profile_config(profile_id: str, req: ProfileConfigRollbackRequest, token: str = Depends(require_token)):
    require_writes()
    path = _profile_config_path(profile_id, req.kind)
    if not req.confirm_rollback:
        raise HTTPException(status_code=400, detail="Rollback requires confirm_rollback=true")
    backup_path = _safe_profile_config_backup_path(profile_id, req.kind, req.backup_filename)
    restored_content = backup_path.read_text(encoding="utf-8", errors="replace")
    validation_error = _validate_profile_config_text(req.kind, restored_content)
    if validation_error:
        raise HTTPException(status_code=400, detail=f"Backup is invalid for {req.kind}: {validation_error}")

    current = path.read_bytes() if path.exists() else b""
    current_sha = _sha256_bytes(current)
    if req.expected_current_sha256 and req.expected_current_sha256 != current_sha:
        raise HTTPException(status_code=409, detail=f"Conflict: Expected SHA {req.expected_current_sha256}, got {current_sha}")

    PRESENCE_CONFIG_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = path.suffix.lstrip(".") or "txt"
    pre_rollback_backup = None
    if path.exists():
        pre_rollback_backup = PRESENCE_CONFIG_BACKUPS_DIR / f"{profile_id}.{req.kind}.pre-rollback.{ts}.{current_sha[:8]}.{suffix}"
        pre_rollback_backup.write_bytes(current)

    new_bytes = restored_content.encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(new_bytes)
    tmp.replace(path)
    restored_sha = _sha256_bytes(new_bytes)
    append_audit_event({
        "action": "presence_config_rollback",
        "profile_id": profile_id,
        "kind": req.kind,
        "old_sha": current_sha,
        "new_sha": restored_sha,
        "restored_from": str(backup_path),
        "pre_rollback_backup": str(pre_rollback_backup) if pre_rollback_backup else None,
    })
    return {
        "status": "success",
        "new_sha256": restored_sha,
        "restored_from": str(backup_path),
        "pre_rollback_backup": str(pre_rollback_backup) if pre_rollback_backup else None,
    }


@router.post("/profiles/{profile_id}/validate")
def validate_presence_profile(profile_id: str):
    base = _profile_dir(profile_id)
    missing = [kind for kind, filename in PROFILE_CONFIG_KINDS.items() if not (base / filename).exists()]
    errors = []
    for kind, filename in PROFILE_CONFIG_KINDS.items():
        path = base / filename
        if not path.exists():
            continue
        error = _validate_profile_config_text(kind, path.read_text(encoding="utf-8", errors="replace"))
        if error:
            errors.append({"kind": kind, "error": error})
    return {"profile_id": profile_id, "ok": not missing and not errors, "missing": missing, "errors": errors}


@router.get("/profiles/{profile_id}/events/{kind}")
def presence_events(profile_id: str, kind: str, limit: int = Query(50, ge=1, le=500)):
    _safe_profile_id(profile_id)
    allowed = {
        "world": "world-signal-events.jsonl",
        "tick": "tick-events.jsonl",
        "state": "state-events.jsonl",
        "intent": "intent-events.jsonl",
        "decision": "decision-events.jsonl",
        "render": "render-events.jsonl",
        "delivery": "delivery-events.jsonl",
        "trace": "trace-events.jsonl",
        "preview": "preview-events.jsonl",
    }
    filename = allowed.get(kind)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unsupported event kind: {kind}")
    rows = [row for row in tail_jsonl(PRESENCE_EVENTS_DIR / filename, limit) if row.get("profile_id") in (None, profile_id)]
    return {"profile_id": profile_id, "kind": kind, "events": rows}


@router.get("/profiles/{profile_id}/runtime/{kind}")
def presence_runtime(profile_id: str, kind: str):
    _safe_profile_id(profile_id)
    allowed = {
        "state": "state.json",
        "intent": "intent-state.json",
        "world": "world-signal-state.json",
        "control": "control.json",
        "trace": "last-trace.json",
        "preview_trace": "preview-last-trace.json",
    }
    filename = allowed.get(kind)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unsupported runtime kind: {kind}")
    return read_json_file(PRESENCE_RUNTIME_DIR / filename) or {"info": "not found"}


@router.get("/conversation/ledger")
def conversation_ledger(limit: int = Query(100, ge=1, le=1000), profile_id: Optional[str] = None):
    path = HERMES_HOME / "conversation" / "ledger.jsonl"
    rows = tail_jsonl(path, limit)
    if profile_id:
        rows = [row for row in rows if row.get("profile_id") == profile_id]
    return {"path": str(path), "events": rows[:limit]}


@router.get("/conversation/latest")
def conversation_latest():
    latest_by_chat = read_json_file(HERMES_HOME / "conversation" / "indexes" / "latest-by-chat.json") or {}
    latest_presence = read_json_file(HERMES_HOME / "conversation" / "indexes" / "latest-presence-by-chat.json") or {}
    return {"latest_by_chat": latest_by_chat, "latest_presence_by_chat": latest_presence}


@router.post("/preview/full")
def presence_preview_full(req: PreviewRequest):
    script = PRESENCE_KERNEL_DIR / "presence_tick.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"Presence preview script not found: {script}")
    cmd = ["python3", str(script), "--profile", req.profile_id, "--dry-run"]
    if req.force_llm:
        cmd.append("--force-llm")
    try:
        result = subprocess.run(cmd, cwd=str(PRESENCE_KERNEL_DIR), capture_output=True, text=True, timeout=240)
        parsed = None
        try:
            import json
            parsed = json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else None
        except Exception:
            parsed = None
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "result": parsed,
            "trace": read_json_file(PRESENCE_RUNTIME_DIR / "preview-last-trace.json"),
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Preview timed out")


@router.post("/preview/state")
def presence_preview_state(req: PreviewRequest):
    return presence_preview_full(req)


@router.post("/preview/decision")
def presence_preview_decision(req: PreviewRequest):
    return presence_preview_full(req)


@router.post("/preview/render")
def presence_preview_render(req: PreviewRequest):
    return presence_preview_full(req)


@router.get("/traces")
def presence_traces(limit: int = Query(50, ge=1, le=500), profile_id: Optional[str] = None):
    rows = tail_jsonl(PRESENCE_EVENTS_DIR / "trace-events.jsonl", limit)
    if profile_id:
        profile_id = _safe_profile_id(profile_id)
        rows = [row for row in rows if row.get("profile_id") in (None, profile_id)]
    return {"traces": rows}


@router.get("/traces/{run_id}")
def presence_trace(run_id: str):
    rows = tail_jsonl(PRESENCE_EVENTS_DIR / "trace-events.jsonl", 500)
    for row in rows:
        if row.get("tick_run_id") == run_id or row.get("run_id") == run_id:
            return row
    raise HTTPException(status_code=404, detail="Trace not found")


@router.get("/world-signals")
def presence_world_signals(limit: int = Query(100, ge=1, le=500), profile_id: Optional[str] = None):
    rows = tail_jsonl(PRESENCE_EVENTS_DIR / "world-signal-events.jsonl", limit)
    if profile_id:
        profile_id = _safe_profile_id(profile_id)
        rows = [row for row in rows if row.get("profile_id") in (None, profile_id)]
    signals = []
    for row in rows:
        signals.extend(row.get("signals") or [])
    return {"signals": signals[:limit], "events": rows}


@router.post("/world-signals/{signal_id}/review")
def presence_world_signal_review(signal_id: str, req: WorldSignalReviewRequest, token: str = Depends(require_token)):
    require_writes()
    import json
    path = PRESENCE_RUNTIME_DIR / "world-signal-reviews.jsonl"
    record = {
        "signal_id": signal_id,
        "action": req.action,
        "reason": req.reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    append_audit_event({"action": "world_signal_review", **record})
    return {"status": "success", "review": record}


@router.post("/runtime/control")
def presence_runtime_control(req: ControlRequest, token: str = Depends(require_token)):
    require_writes()
    import json
    path = PRESENCE_RUNTIME_DIR / "control.json"
    data = read_json_file(path) or {"schema_version": 1, "revision": 1, "override": {}, "operator_feedback": []}
    data["revision"] = int(data.get("revision", 1)) + 1
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["override"] = {"mode": req.action, "reason": req.reason or "Set by observer-ui", "duration_minutes": req.duration_minutes}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_audit_event({"action": "presence_runtime_control", "req": req.model_dump(), "revision": data["revision"]})
    return {"status": "success", "control": data}
