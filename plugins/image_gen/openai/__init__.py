"""OpenAI image generation backend.

Exposes OpenAI's ``gpt-image-2`` model at three quality tiers as an
:class:`ImageGenProvider` implementation. The tiers are implemented as
three virtual model IDs so the ``hermes tools`` model picker and the
``image_gen.model`` config key behave like any other multi-model backend:

    gpt-image-2-low     ~15s   fastest, good for iteration
    gpt-image-2-medium  ~40s   default — balanced
    gpt-image-2-high    ~2min  slowest, highest fidelity

All three hit the same underlying API model (``gpt-image-2``) with a
different ``quality`` parameter. Output is base64 JSON → saved under
``$HERMES_HOME/cache/images/``.

Selection precedence (first hit wins):

1. ``OPENAI_IMAGE_MODEL`` env var (escape hatch for scripts / tests)
2. ``image_gen.openai.model`` in ``config.yaml``
3. ``image_gen.model`` in ``config.yaml`` (when it's one of our tier IDs)
4. :data:`DEFAULT_MODEL` — ``gpt-image-2-medium``

OpenAI-compatible relay stations are supported via
``IMAGE_TOOLS_OPENAI_BASE_URL`` and ``IMAGE_TOOLS_OPENAI_MODEL``.
``source_image`` edit calls use ``images.edit`` with a local uploaded/generated
image path.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)


def _resolve_openai_api_key() -> str:
    """Return the image-generation OpenAI key, if configured."""
    return (
        os.environ.get("IMAGE_TOOLS_OPENAI_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()


def _resolve_openai_base_url() -> Optional[str]:
    """Return an optional OpenAI-compatible base URL for image gen."""
    value = (
        os.environ.get("IMAGE_TOOLS_OPENAI_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or ""
    ).strip()
    return value or None


def _resolve_openai_api_model() -> str:
    """Return the API model string sent to the OpenAI-compatible endpoint."""
    value = (
        os.environ.get("IMAGE_TOOLS_OPENAI_MODEL")
        or os.environ.get("OPENAI_IMAGE_API_MODEL")
        or ""
    ).strip()
    if value:
        return value

    cfg = _load_openai_config()
    openai_cfg = cfg.get("openai") if isinstance(cfg.get("openai"), dict) else {}
    if isinstance(openai_cfg, dict):
        configured = openai_cfg.get("api_model")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()

    return API_MODEL


def _resolve_openai_timeout() -> float:
    """Return image API timeout in seconds."""
    raw = (
        os.environ.get("IMAGE_TOOLS_OPENAI_TIMEOUT")
        or os.environ.get("OPENAI_IMAGE_TIMEOUT")
        or "1800"
    )
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return 1800.0
    return max(0.0, value)


def _normalize_local_image_path(value: str) -> Path:
    """Normalize a local path or file:// URL into a readable Path."""
    raw = (value or "").strip().strip("`\"'")
    if raw.startswith("file://"):
        parsed = urlparse(raw)
        raw = unquote(parsed.path or "")
        if os.name == "nt" and raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
            raw = raw[1:]
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"source_image does not exist or is not a file: {value}")
    return path


# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------
#
# All three IDs resolve to the same underlying API model with a different
# ``quality`` setting. ``api_model`` is what gets sent to OpenAI;
# ``quality`` is the knob that changes generation time and output fidelity.

API_MODEL = "gpt-image-2"

_MODELS: Dict[str, Dict[str, Any]] = {
    "gpt-image-2-low": {
        "display": "GPT Image 2 (Low)",
        "speed": "~15s",
        "strengths": "Fast iteration, lowest cost",
        "quality": "low",
    },
    "gpt-image-2-medium": {
        "display": "GPT Image 2 (Medium)",
        "speed": "~40s",
        "strengths": "Balanced — default",
        "quality": "medium",
    },
    "gpt-image-2-high": {
        "display": "GPT Image 2 (High)",
        "speed": "~2min",
        "strengths": "Highest fidelity, strongest prompt adherence",
        "quality": "high",
    },
}

DEFAULT_MODEL = "gpt-image-2-medium"

_MODEL_ALIASES = {
    "gpt-image2": DEFAULT_MODEL,
    "gpt-image-2": DEFAULT_MODEL,
}

_SIZES = {
    "landscape": "1536x1024",
    "square": "1024x1024",
    "portrait": "1024x1536",
}


def _load_openai_config() -> Dict[str, Any]:
    """Read ``image_gen`` from config.yaml (returns {} on any failure)."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen config: %s", exc)
        return {}


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    """Decide which tier to use and return ``(model_id, meta)``."""
    env_override = os.environ.get("OPENAI_IMAGE_MODEL")
    if env_override:
        env_override = _MODEL_ALIASES.get(env_override, env_override)
    if env_override and env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_openai_config()
    openai_cfg = cfg.get("openai") if isinstance(cfg.get("openai"), dict) else {}
    candidate: Optional[str] = None
    if isinstance(openai_cfg, dict):
        value = openai_cfg.get("model")
        if isinstance(value, str):
            value = _MODEL_ALIASES.get(value, value)
        if isinstance(value, str) and value in _MODELS:
            candidate = value
    if candidate is None:
        top = cfg.get("model")
        if isinstance(top, str):
            top = _MODEL_ALIASES.get(top, top)
        if isinstance(top, str) and top in _MODELS:
            candidate = top

    if candidate is not None:
        return candidate, _MODELS[candidate]

    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OpenAIImageGenProvider(ImageGenProvider):
    """OpenAI ``images.generate`` backend — gpt-image-2 at low/medium/high."""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI"

    def is_available(self) -> bool:
        if not _resolve_openai_api_key():
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta["display"],
                "speed": meta["speed"],
                "strengths": meta["strengths"],
                "price": "varies",
            }
            for model_id, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "OpenAI",
            "badge": "paid",
            "tag": "gpt-image-2 at low/medium/high quality tiers",
            "env_vars": [
                {
                    "key": "IMAGE_TOOLS_OPENAI_KEY",
                    "prompt": "OpenAI API key for image generation",
                    "url": "https://platform.openai.com/api-keys",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="openai",
                aspect_ratio=aspect,
            )

        api_key = _resolve_openai_api_key()
        if not api_key:
            return error_response(
                error=(
                    "IMAGE_TOOLS_OPENAI_KEY or OPENAI_API_KEY not set. Run "
                    "`hermes tools` → Image Generation → OpenAI to configure "
                    "an OpenAI API key."
                ),
                error_type="auth_required",
                provider="openai",
                aspect_ratio=aspect,
            )

        try:
            import openai
        except ImportError:
            return error_response(
                error="openai Python package not installed (pip install openai)",
                error_type="missing_dependency",
                provider="openai",
                aspect_ratio=aspect,
            )

        tier_id, meta = _resolve_model()
        api_model = _resolve_openai_api_model()
        size = _SIZES.get(aspect, _SIZES["square"])

        # gpt-image-2 returns b64_json unconditionally and REJECTS
        # ``response_format`` as an unknown parameter. Don't send it.
        payload: Dict[str, Any] = {
            "model": api_model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "quality": meta["quality"],
        }

        try:
            base_url = _resolve_openai_base_url()
            timeout = _resolve_openai_timeout()
            client_kwargs: Dict[str, Any] = {"api_key": api_key}
            if timeout > 0:
                client_kwargs["timeout"] = timeout
            if base_url:
                client_kwargs["base_url"] = base_url
            client = openai.OpenAI(**client_kwargs)
            response = client.images.generate(**payload)
        except Exception as exc:
            logger.debug("OpenAI image generation failed", exc_info=True)
            return error_response(
                error=f"OpenAI image generation failed: {exc}",
                error_type="api_error",
                provider="openai",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        data = getattr(response, "data", None) or []
        if not data:
            return error_response(
                error="OpenAI returned no image data",
                error_type="empty_response",
                provider="openai",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        first = data[0]
        b64 = getattr(first, "b64_json", None)
        url = getattr(first, "url", None)
        revised_prompt = getattr(first, "revised_prompt", None)

        if b64:
            try:
                saved_path = save_b64_image(b64, prefix=f"openai_{tier_id}")
            except Exception as exc:
                return error_response(
                    error=f"Could not save image to cache: {exc}",
                    error_type="io_error",
                    provider="openai",
                    model=tier_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            image_ref = str(saved_path)
        elif url:
            # Defensive — gpt-image-2 returns b64 today, but fall back
            # gracefully if the API ever changes.
            image_ref = url
        else:
            return error_response(
                error="OpenAI response contained neither b64_json nor URL",
                error_type="empty_response",
                provider="openai",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra: Dict[str, Any] = {"size": size, "quality": meta["quality"]}
        extra["api_model"] = api_model
        if revised_prompt:
            extra["revised_prompt"] = revised_prompt

        return success_response(
            image=image_ref,
            model=tier_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="openai",
            extra=extra,
        )

    def edit(
        self,
        *,
        prompt: str,
        source_image: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="openai",
                aspect_ratio=aspect,
            )

        try:
            source_path = _normalize_local_image_path(source_image)
        except Exception as exc:
            return error_response(
                error=str(exc),
                error_type="invalid_source_image",
                provider="openai",
                prompt=prompt,
                aspect_ratio=aspect,
            )

        api_key = _resolve_openai_api_key()
        if not api_key:
            return error_response(
                error=(
                    "IMAGE_TOOLS_OPENAI_KEY or OPENAI_API_KEY not set. Run "
                    "`hermes tools` → Image Generation → OpenAI to configure "
                    "an OpenAI API key."
                ),
                error_type="auth_required",
                provider="openai",
                aspect_ratio=aspect,
            )

        try:
            import openai
        except ImportError:
            return error_response(
                error="openai Python package not installed (pip install openai)",
                error_type="missing_dependency",
                provider="openai",
                aspect_ratio=aspect,
            )

        tier_id, meta = _resolve_model()
        api_model = _resolve_openai_api_model()
        size = _SIZES.get(aspect, _SIZES["square"])
        payload: Dict[str, Any] = {
            "model": api_model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "quality": meta["quality"],
        }

        try:
            base_url = _resolve_openai_base_url()
            timeout = _resolve_openai_timeout()
            client_kwargs: Dict[str, Any] = {"api_key": api_key}
            if timeout > 0:
                client_kwargs["timeout"] = timeout
            if base_url:
                client_kwargs["base_url"] = base_url
            client = openai.OpenAI(**client_kwargs)
            with source_path.open("rb") as image_file:
                response = client.images.edit(image=image_file, **payload)
        except Exception as exc:
            logger.debug("OpenAI image edit failed", exc_info=True)
            return error_response(
                error=f"OpenAI image edit failed: {exc}",
                error_type="api_error",
                provider="openai",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        data = getattr(response, "data", None) or []
        if not data:
            return error_response(
                error="OpenAI returned no image data",
                error_type="empty_response",
                provider="openai",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        first = data[0]
        b64 = getattr(first, "b64_json", None)
        url = getattr(first, "url", None)
        revised_prompt = getattr(first, "revised_prompt", None)

        if b64:
            try:
                saved_path = save_b64_image(b64, prefix=f"openai_edit_{tier_id}")
            except Exception as exc:
                return error_response(
                    error=f"Could not save edited image to cache: {exc}",
                    error_type="io_error",
                    provider="openai",
                    model=tier_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            image_ref = str(saved_path)
        elif url:
            image_ref = url
        else:
            return error_response(
                error="OpenAI response contained neither b64_json nor URL",
                error_type="empty_response",
                provider="openai",
                model=tier_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra: Dict[str, Any] = {
            "size": size,
            "quality": meta["quality"],
            "api_model": api_model,
            "source_image": str(source_path),
        }
        if revised_prompt:
            extra["revised_prompt"] = revised_prompt

        return success_response(
            image=image_ref,
            model=tier_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="openai",
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Plugin entry point — wire ``OpenAIImageGenProvider`` into the registry."""
    ctx.register_image_gen_provider(OpenAIImageGenProvider())
