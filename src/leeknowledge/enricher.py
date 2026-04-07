"""
Enrichment stage implementation.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

try:  # pragma: no cover - dependency availability varies in the shell.
    import httpx  # type: ignore
except ImportError:  # pragma: no cover - exercised when dev deps are absent.
    httpx = None

try:  # pragma: no cover - dependency availability varies in the shell.
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised when dev deps are absent.
    yaml = None

from leeknowledge.db import (
    APP_DB_PATH,
    get_connection,
    get_url_cache_entry,
    initialize_database,
    insert_enrichment,
    list_unenriched_bookmarks,
    upsert_url_cache,
)

DEFAULT_LLM_CONFIG_PATH = Path("config/llm.yaml")
PROMPT_VERSION = "1"
SCHEMA_VERSION = "1"
DEFAULT_URL_TIMEOUT_SECONDS = 15.0
DEFAULT_MODEL_TIMEOUT_SECONDS = 60.0


class EnrichmentError(RuntimeError):
    """Raised when enrichment cannot proceed safely."""


class EnrichmentConfigError(EnrichmentError):
    """Raised when the local LLM config is missing or malformed."""


class EnrichmentRuntimeError(EnrichmentError):
    """Raised when the enrichment provider fails unexpectedly."""


@dataclass(frozen=True)
class ResolvedEnricherConfig:
    """Resolved provider and role configuration for the enricher."""

    provider_name: str
    provider_type: str
    provider_command: str
    provider_args: tuple[str, ...]
    provider_response_format: str | None
    provider_text_field: str | None
    provider_timeout: float
    model: str
    temperature: float | None
    json_mode: bool


@dataclass(frozen=True)
class ResolvedUrl:
    """Replayable URL resolution output for a single raw URL."""

    original_url: str
    resolved_url: str
    page_title: str | None = None
    page_description: str | None = None
    cached_at: str | None = None


@dataclass(frozen=True)
class EnrichmentRunResult:
    """Summary of a completed enrichment run."""

    processed_bookmark_count: int
    inserted_enrichment_count: int
    skipped_existing_count: int
    placeholder_count: int
    cached_url_count: int
    failed_bookmark_count: int
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION


ModelRunner = Callable[[ResolvedEnricherConfig, str], Any]
HttpClientFactory = Callable[[], Any]


def load_llm_config(config_path: Path | str = DEFAULT_LLM_CONFIG_PATH) -> dict[str, Any]:
    """Load the local LLM config and fail fast on missing or malformed files."""

    resolved_path = Path(config_path)
    if not resolved_path.exists():
        raise EnrichmentConfigError(
            f"Missing LLM config at {resolved_path}. Copy config/llm.example.yaml to "
            "config/llm.yaml before running enrich."
        )

    try:
        config_text = resolved_path.read_text()
        raw_config = (
            yaml.safe_load(config_text)
            if yaml is not None
            else _simple_yaml_load(config_text)
        )
    except Exception as exc:  # pragma: no cover - defensive around parser edge cases.
        raise EnrichmentConfigError(
            f"Could not parse LLM config at {resolved_path}: {exc}"
        ) from exc

    if not isinstance(raw_config, Mapping):
        raise EnrichmentConfigError(
            f"LLM config at {resolved_path} must contain a top-level mapping."
        )

    llm_config = raw_config.get("llm")
    if not isinstance(llm_config, Mapping):
        raise EnrichmentConfigError(
            f"LLM config at {resolved_path} must contain an 'llm' mapping."
        )

    return dict(llm_config)


def resolve_enricher_config(
    config_path: Path | str = DEFAULT_LLM_CONFIG_PATH,
) -> ResolvedEnricherConfig:
    """Resolve the provider and model settings for the enricher role."""

    llm_config = load_llm_config(config_path)
    providers = llm_config.get("providers")
    roles = llm_config.get("roles")
    default_role = llm_config.get("default_role", "enricher")

    if not isinstance(providers, Mapping):
        raise EnrichmentConfigError("LLM config is missing a providers mapping.")
    if not isinstance(roles, Mapping):
        raise EnrichmentConfigError("LLM config is missing a roles mapping.")

    role_config = roles.get(default_role)
    if not isinstance(role_config, Mapping):
        raise EnrichmentConfigError(
            f"LLM config does not define the default role '{default_role}'."
        )

    provider_name = role_config.get("provider")
    if not isinstance(provider_name, str) or not provider_name:
        raise EnrichmentConfigError(
            "The enricher role must reference a provider name."
        )

    provider_config = providers.get(provider_name)
    if not isinstance(provider_config, Mapping):
        raise EnrichmentConfigError(
            f"LLM config does not define provider '{provider_name}'."
        )

    provider_command = provider_config.get("command")
    if not isinstance(provider_command, str) or not provider_command:
        raise EnrichmentConfigError(
            f"Provider '{provider_name}' must define a command."
        )

    provider_args = provider_config.get("args", [])
    if not isinstance(provider_args, Iterable) or isinstance(provider_args, (str, bytes)):
        raise EnrichmentConfigError(
            f"Provider '{provider_name}' args must be a sequence."
        )

    provider_timeout = provider_config.get("timeout", DEFAULT_MODEL_TIMEOUT_SECONDS)
    if not isinstance(provider_timeout, (int, float)):
        raise EnrichmentConfigError(
            f"Provider '{provider_name}' timeout must be numeric."
        )

    model = role_config.get("model")
    if not isinstance(model, str) or not model:
        raise EnrichmentConfigError("The enricher role must define a model.")

    temperature = role_config.get("temperature")
    if temperature is not None and not isinstance(temperature, (int, float)):
        raise EnrichmentConfigError("The enricher role temperature must be numeric.")

    return ResolvedEnricherConfig(
        provider_name=provider_name,
        provider_type=str(provider_config.get("type", "")),
        provider_command=provider_command,
        provider_args=tuple(str(arg) for arg in provider_args),
        provider_response_format=str(provider_config.get("response_format"))
        if provider_config.get("response_format") is not None
        else None,
        provider_text_field=str(provider_config.get("text_field"))
        if provider_config.get("text_field") is not None
        else None,
        provider_timeout=float(provider_timeout),
        model=model,
        temperature=float(temperature) if temperature is not None else None,
        json_mode=bool(role_config.get("json_mode", False)),
    )


def enrich_bookmarks(
    db_path: Path | str = APP_DB_PATH,
    config_path: Path | str = DEFAULT_LLM_CONFIG_PATH,
    model_runner: ModelRunner | None = None,
    http_client_factory: HttpClientFactory | None = None,
) -> EnrichmentRunResult:
    """Enrich bookmarks stored in SQLite."""

    enricher_config = resolve_enricher_config(config_path)
    resolved_db_path = initialize_database(db_path)
    run_model = model_runner or run_enrichment_model
    client_factory = http_client_factory or _default_http_client_factory

    processed_count = 0
    inserted_count = 0
    skipped_existing_count = 0
    placeholder_count = 0
    cached_url_count = 0
    failed_count = 0

    with get_connection(resolved_db_path) as connection:
        bookmarks = list_unenriched_bookmarks(connection)
        for bookmark in bookmarks:
            processed_count += 1
            raw_urls = _load_json_list(bookmark["raw_urls"])
            resolved_urls, resolved_cache_count = _resolve_bookmark_urls(
                connection,
                raw_urls,
                client_factory,
            )
            cached_url_count += resolved_cache_count
            prompt = build_enrichment_prompt(bookmark, resolved_urls)

            try:
                model_output = run_model(enricher_config, prompt)
                payload = _coerce_model_payload(model_output, enricher_config)
                enrichment_record = _build_valid_enrichment_record(
                    bookmark["tweet_id"],
                    payload,
                    enricher_config,
                )
            except EnrichmentError as exc:
                failed_count += 1
                enrichment_record = _build_placeholder_record(
                    bookmark["tweet_id"],
                    enricher_config,
                    validation_status=_validation_status_for_exception(exc),
                )
                placeholder_count += 1
            except Exception as exc:  # pragma: no cover - defensive on provider bugs.
                failed_count += 1
                enrichment_record = _build_placeholder_record(
                    bookmark["tweet_id"],
                    enricher_config,
                    validation_status=f"error:{type(exc).__name__}",
                )
                placeholder_count += 1

            if insert_enrichment(connection, enrichment_record):
                inserted_count += 1
            else:
                skipped_existing_count += 1

    return EnrichmentRunResult(
        processed_bookmark_count=processed_count,
        inserted_enrichment_count=inserted_count,
        skipped_existing_count=skipped_existing_count,
        placeholder_count=placeholder_count,
        cached_url_count=cached_url_count,
        failed_bookmark_count=failed_count,
    )


def run_enrichment_model(config: ResolvedEnricherConfig, prompt: str) -> str:
    """Invoke the configured provider and return its raw text response."""

    if config.provider_type != "codex_cli":
        raise EnrichmentRuntimeError(
            f"Unsupported enricher provider type: {config.provider_type!r}"
        )

    command = [config.provider_command, *config.provider_args]
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=config.provider_timeout,
            check=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise EnrichmentRuntimeError(
            f"Enrichment provider timed out after {config.provider_timeout} seconds."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise EnrichmentRuntimeError(
            f"Enrichment provider failed with exit code {exc.returncode}. {stderr}"
        ) from exc
    except OSError as exc:
        raise EnrichmentRuntimeError(f"Failed to launch enrichment provider: {exc}") from exc

    stdout = completed.stdout.strip()
    if not stdout:
        raise EnrichmentRuntimeError("Enrichment provider returned no output.")

    return stdout


def build_enrichment_prompt(
    bookmark: Mapping[str, Any],
    resolved_urls: Iterable[ResolvedUrl],
) -> str:
    """Build a strict prompt for the enrichment model."""

    urls_block = []
    for entry in resolved_urls:
        lines = [f"- original_url: {entry.original_url}", f"  resolved_url: {entry.resolved_url}"]
        if entry.page_title:
            lines.append(f"  page_title: {entry.page_title}")
        if entry.page_description:
            lines.append(f"  page_description: {entry.page_description}")
        urls_block.append("\n".join(lines))

    prompt_lines = [
        "You are enriching an X bookmark record.",
        f"prompt_version: {PROMPT_VERSION}",
        f"schema_version: {SCHEMA_VERSION}",
        "Return exactly one JSON object with these keys:",
        "- summary: string",
        "- tags: array of strings",
        "- entities: array of strings",
        "- topic: string",
        "Use only the bookmark text, author metadata, resolved URLs, and page metadata.",
        "Do not invent facts or quote source text unless needed for fidelity.",
        "",
        "Bookmark:",
        f"tweet_id: {_bookmark_value(bookmark, 'tweet_id')}",
        f"author_username: {_bookmark_value(bookmark, 'author_username')}",
        f"author_display_name: {_bookmark_value(bookmark, 'author_display_name')}",
        f"created_at: {_bookmark_value(bookmark, 'created_at')}",
        f"text: {_bookmark_value(bookmark, 'text')}",
        f"raw_urls: {_load_json_list(_bookmark_value(bookmark, 'raw_urls'))}",
        "resolved_urls:",
    ]

    if urls_block:
        prompt_lines.extend(urls_block)
    else:
        prompt_lines.append("- none")

    prompt_lines.extend(
        [
            "",
            "Output JSON only.",
        ]
    )
    return "\n".join(prompt_lines)


def _coerce_model_payload(
    model_output: Any,
    config: ResolvedEnricherConfig,
) -> Mapping[str, Any]:
    if isinstance(model_output, Mapping):
        if config.provider_text_field and config.provider_text_field in model_output:
            text_output = model_output[config.provider_text_field]
            if isinstance(text_output, str):
                return _parse_json_payload(text_output)
        return _parse_json_payload(model_output)

    if isinstance(model_output, str):
        return _parse_json_payload(model_output)

    raise EnrichmentRuntimeError(
        f"Unsupported model output type: {type(model_output).__name__}"
    )


def _parse_json_payload(payload: str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        candidate = payload
    else:
        try:
            candidate = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise EnrichmentRuntimeError("Enrichment output was not valid JSON.") from exc

    if not isinstance(candidate, Mapping):
        raise EnrichmentRuntimeError("Enrichment output must be a JSON object.")

    return dict(candidate)


def _build_valid_enrichment_record(
    tweet_id: str,
    payload: Mapping[str, Any],
    config: ResolvedEnricherConfig,
) -> dict[str, Any]:
    summary = payload.get("summary")
    tags = payload.get("tags")
    entities = payload.get("entities")
    topic = payload.get("topic")

    if not isinstance(summary, str) or not summary.strip():
        raise EnrichmentRuntimeError("Enrichment output is missing a summary string.")
    if not isinstance(topic, str) or not topic.strip():
        raise EnrichmentRuntimeError("Enrichment output is missing a topic string.")

    valid_tags = _validate_string_list(tags, "tags")
    valid_entities = _validate_string_list(entities, "entities")

    return {
        "tweet_id": tweet_id,
        "summary": summary.strip(),
        "tags": valid_tags,
        "entities": valid_entities,
        "topic": topic.strip(),
        "model": config.model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "validation_status": "valid",
        "enriched_at": _utc_now(),
    }


def _build_placeholder_record(
    tweet_id: str,
    config: ResolvedEnricherConfig,
    validation_status: str,
) -> dict[str, Any]:
    return {
        "tweet_id": tweet_id,
        "summary": None,
        "tags": None,
        "entities": None,
        "topic": None,
        "model": config.model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "validation_status": validation_status,
        "enriched_at": _utc_now(),
    }


def _validation_status_for_exception(exc: Exception) -> str:
    message = str(exc).lower()
    if "not valid json" in message or "must be a json object" in message:
        return "invalid_json"
    if "timed out" in message:
        return "timeout"
    if "must be an array" in message or "must contain only strings" in message:
        return "schema_validation_failed"
    if "missing a summary" in message or "missing a topic" in message:
        return "schema_validation_failed"
    return "failed"


def _validate_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise EnrichmentRuntimeError(
            f"Enrichment output field '{field_name}' must be an array of strings."
        )

    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise EnrichmentRuntimeError(
                f"Enrichment output field '{field_name}' must contain only strings."
            )
        candidate = item.strip()
        if candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


def _resolve_bookmark_urls(
    connection,
    raw_urls: Iterable[Any],
    client_factory: HttpClientFactory,
) -> tuple[list[ResolvedUrl], int]:
    resolved_urls: list[ResolvedUrl] = []
    cache_updates = 0
    for raw_url in raw_urls:
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        original_url = raw_url.strip()
        cached_row = get_url_cache_entry(connection, original_url)
        if cached_row is not None:
            resolved_urls.append(
                ResolvedUrl(
                    original_url=original_url,
                    resolved_url=str(cached_row["resolved_url"] or original_url),
                    page_title=cached_row["page_title"],
                    page_description=cached_row["page_description"],
                    cached_at=cached_row["cached_at"],
                )
            )
            continue

        resolved_url = original_url
        page_title = None
        page_description = None
        try:
            with client_factory() as client:
                response = client.get(
                    original_url,
                    follow_redirects=True,
                    timeout=DEFAULT_URL_TIMEOUT_SECONDS,
                )
                resolved_url = str(getattr(response, "url", original_url))
                html = getattr(response, "text", "") or ""
                page_title, page_description = _extract_page_metadata(html)
        except Exception:
            resolved_url = original_url
            page_title = None
            page_description = None

        cached_at = _utc_now()
        cache_entry = {
            "original_url": original_url,
            "resolved_url": resolved_url,
            "page_title": page_title,
            "page_description": page_description,
            "cached_at": cached_at,
        }
        upsert_url_cache(connection, cache_entry)
        cache_updates += 1
        resolved_urls.append(
            ResolvedUrl(
                original_url=original_url,
                resolved_url=resolved_url,
                page_title=page_title,
                page_description=page_description,
                cached_at=cached_at,
            )
        )

    return resolved_urls, cache_updates


def _extract_page_metadata(html: str) -> tuple[str | None, str | None]:
    if not html:
        return None, None

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = _clean_html_text(title_match.group(1)) if title_match else None

    description_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    description = _clean_html_text(description_match.group(1)) if description_match else None

    return title, description


def _clean_html_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"<[^>]+>", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _load_json_list(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str) and item.strip()]
    return []


def _default_http_client_factory() -> Any:
    if httpx is None:
        raise EnrichmentConfigError(
            "httpx is required for URL expansion. Install the dev dependencies before running enrich."
        )
    return httpx.Client(follow_redirects=True)


def _bookmark_value(bookmark: Mapping[str, Any], key: str) -> Any:
    try:
        return bookmark[key]
    except Exception:
        return getattr(bookmark, key, None)


def _simple_yaml_load(text: str) -> Any:
    """Parse the small YAML subset used by config/llm.yaml."""

    lines = [line.rstrip() for line in text.splitlines()]
    index = 0

    def parse_block(expected_indent: int) -> dict[str, Any]:
        nonlocal index
        result: dict[str, Any] = {}
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                index += 1
                continue

            indent = len(line) - len(line.lstrip(" "))
            if indent < expected_indent:
                break
            if indent > expected_indent:
                raise ValueError(f"Unexpected indentation on line {index + 1}")

            if ":" not in stripped:
                raise ValueError(f"Invalid YAML line {index + 1}: {line}")

            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            index += 1
            if raw_value:
                result[key] = _parse_scalar(raw_value)
                continue

            result[key] = parse_block(expected_indent + 2)
        return result

    parsed = parse_block(0)
    if index < len(lines):
        # Consume trailing blank lines but reject malformed leftovers.
        for line in lines[index:]:
            if line.strip() and not line.strip().startswith("#"):
                raise ValueError(f"Unexpected content near line {index + 1}")
    return parsed


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if value.startswith(("[", "{")):
        return ast.literal_eval(value)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return ast.literal_eval(value)
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
