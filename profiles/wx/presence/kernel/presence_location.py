#!/usr/bin/env python3
"""Runtime location context and template resolution for Presence collectors."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from presence_common import local_now, read_json, runtime_path


_MISSING = object()
_FULL_LOCATION_TEMPLATE_RE = re.compile(r"^\$\{location\.([A-Za-z_][A-Za-z0-9_]*)\}$")
_LOCATION_TEMPLATE_RE = re.compile(r"\$\{location\.([A-Za-z_][A-Za-z0-9_]*)\}")
_MEMORY_CONTEXT_MARKERS_RE = re.compile(r"(?i)<\/?memory-context\b|hindsight\s+memory|system note:")
_MAX_LOCATION_LABEL_CHARS = 80


def sanitize_location_label(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"(?is)<memory-context\b[^>]*>.*?</memory-context>", "", text).strip()
    text = text.splitlines()[0].strip() if text.splitlines() else text
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if len(text) > _MAX_LOCATION_LABEL_CHARS:
        return ""
    if re.search(r"[\r\n<>]", text) or _MEMORY_CONTEXT_MARKERS_RE.search(text):
        return ""
    return text


def load_location_context(profile: dict[str, Any]) -> dict[str, Any]:
    data = read_json(runtime_path("location-context.json"), {})
    if not isinstance(data, dict) or not data.get("label"):
        return {}
    label = sanitize_location_label(data.get("label"))
    if not label:
        return {}
    data["label"] = label
    expires_at = data.get("expires_at")
    if expires_at:
        try:
            if datetime.fromisoformat(str(expires_at)) <= local_now(profile):
                return {}
        except Exception:
            return {}
    return data


def default_location(profile: dict[str, Any]) -> dict[str, Any]:
    world_policy = profile.get("world_policy") or {}
    resolution = world_policy.get("location_resolution") if isinstance(world_policy, dict) else {}
    anchor = (resolution or {}).get("default_anchor") if isinstance(resolution, dict) else {}
    anchor = anchor if isinstance(anchor, dict) else {}
    latitude = anchor.get("latitude", 31.2304)
    longitude = anchor.get("longitude", 121.4737)
    label = sanitize_location_label(anchor.get("label")) or "Shanghai"
    return {
        "label": label,
        "country_code": anchor.get("country_code") or "CN",
        "latitude": latitude,
        "longitude": longitude,
        "has_coordinates": latitude is not None and longitude is not None,
        "scope": "default_anchor",
        "source": "world_policy",
        "confidence": float(anchor.get("confidence", 0.7)),
        "render_visibility": (resolution or {}).get("render_visibility_default", "oblique_only") if isinstance(resolution, dict) else "oblique_only",
    }


def active_location(profile: dict[str, Any]) -> dict[str, Any]:
    fallback = default_location(profile)
    context = load_location_context(profile)
    if not context:
        return fallback

    latitude = context.get("latitude")
    longitude = context.get("longitude")
    has_coordinates = latitude is not None and longitude is not None
    return {
        "label": sanitize_location_label(context.get("label")) or fallback.get("label"),
        "country_code": context.get("country_code") or fallback.get("country_code") or "CN",
        "latitude": latitude if has_coordinates else None,
        "longitude": longitude if has_coordinates else None,
        "has_coordinates": has_coordinates,
        "scope": context.get("scope") or "confirmed_user_current",
        "source": context.get("source") or "runtime",
        "confidence": float(context.get("confidence", 1.0)),
        "updated_at": context.get("updated_at"),
        "expires_at": context.get("expires_at"),
        "render_visibility": context.get("render_visibility") or fallback.get("render_visibility") or "oblique_only",
    }


def resolve_location_templates(value: Any, profile: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    location = active_location(profile)
    resolved = _resolve(value, location)
    if resolved is _MISSING:
        resolved = None
    return resolved, {
        "label": sanitize_location_label(location.get("label")),
        "country_code": location.get("country_code"),
        "has_coordinates": bool(location.get("has_coordinates")),
        "scope": location.get("scope"),
        "source": location.get("source"),
        "confidence": location.get("confidence"),
        "updated_at": location.get("updated_at"),
        "render_visibility": location.get("render_visibility"),
    }


def _resolve(value: Any, location: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            resolved = _resolve(child, location)
            if resolved is _MISSING:
                continue
            if isinstance(resolved, dict) and not resolved:
                continue
            out[key] = resolved
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            resolved = _resolve(item, location)
            if resolved is not _MISSING:
                out.append(resolved)
        return out
    if not isinstance(value, str):
        return value

    full = _FULL_LOCATION_TEMPLATE_RE.match(value.strip())
    if full:
        replacement = location.get(full.group(1))
        if replacement is None or replacement == "":
            return _MISSING
        return replacement

    def replace(match: re.Match[str]) -> str:
        replacement = location.get(match.group(1))
        if replacement is None:
            return ""
        if match.group(1) == "label":
            return sanitize_location_label(replacement)
        return str(replacement)

    return _LOCATION_TEMPLATE_RE.sub(replace, value)
