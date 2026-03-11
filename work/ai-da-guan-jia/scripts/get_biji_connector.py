#!/usr/bin/env python3
"""Minimal Get笔记 OpenAPI connector with normalized results."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


DEFAULT_BASE_URL = "https://open-api.biji.com/getnote/openapi"
DEFAULT_ASK_PATH = "/knowledge/search"
DEFAULT_RECALL_PATH = "/knowledge/search/recall"
SKILL_ROOT = Path(__file__).resolve().parents[1]
STATE_ENV_PATH = SKILL_ROOT / "state" / "get-biji.env"


class GetBijiConfigError(RuntimeError):
    """Raised when required Get笔记 config is missing."""


class GetBijiAPIError(RuntimeError):
    """Raised when the remote Get笔记 API returns an error."""


def _read_state_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


@dataclass(frozen=True)
class GetBijiConfig:
    api_key: str
    topic_id: str
    base_url: str
    timeout_seconds: int
    ask_path: str
    recall_path: str

    @classmethod
    def from_env(cls, *, topic_id: str | None = None) -> "GetBijiConfig":
        state_env = _read_state_env(STATE_ENV_PATH)
        api_key = os.getenv("GET_BIJI_API_KEY", state_env.get("GET_BIJI_API_KEY", "")).strip()
        resolved_topic_id = (topic_id or os.getenv("GET_BIJI_TOPIC_ID", state_env.get("GET_BIJI_TOPIC_ID", ""))).strip()
        base_url = os.getenv("GET_BIJI_BASE_URL", state_env.get("GET_BIJI_BASE_URL", DEFAULT_BASE_URL)).strip().rstrip("/")
        timeout_raw = os.getenv("GET_BIJI_TIMEOUT_SECONDS", state_env.get("GET_BIJI_TIMEOUT_SECONDS", "30")).strip()
        ask_path = os.getenv("GET_BIJI_ASK_PATH", state_env.get("GET_BIJI_ASK_PATH", DEFAULT_ASK_PATH)).strip() or DEFAULT_ASK_PATH
        recall_path = os.getenv("GET_BIJI_RECALL_PATH", state_env.get("GET_BIJI_RECALL_PATH", DEFAULT_RECALL_PATH)).strip() or DEFAULT_RECALL_PATH
        if not api_key:
            raise GetBijiConfigError("Missing GET_BIJI_API_KEY.")
        if not resolved_topic_id:
            raise GetBijiConfigError("Missing GET_BIJI_TOPIC_ID.")
        try:
            timeout_seconds = max(1, int(timeout_raw))
        except ValueError as exc:
            raise GetBijiConfigError("GET_BIJI_TIMEOUT_SECONDS must be an integer.") from exc
        return cls(
            api_key=api_key,
            topic_id=resolved_topic_id,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            ask_path=ask_path,
            recall_path=recall_path,
        )


@dataclass(frozen=True)
class RecallHit:
    content: str
    title: str
    source: str
    score: float | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerResult:
    source: str
    operation: str
    success: bool
    topic_id: str
    query: str
    answer: str
    hits: list[dict[str, Any]]
    raw_response_path: str
    verification_note: str
    error: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = self.metadata or {}
        return payload


@dataclass(frozen=True)
class RecallResult:
    source: str
    operation: str
    success: bool
    topic_id: str
    query: str
    hits: list[dict[str, Any]]
    raw_response_path: str
    verification_note: str
    error: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = self.metadata or {}
        return payload


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Connection": "keep-alive",
        "X-OAuth-Version": "1",
    }


def _endpoint(base_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{normalized_path}"


def _extract_answer(payload: dict[str, Any]) -> str:
    container = payload.get("c")
    if isinstance(container, dict):
        for key in ["answers", "answer", "msg"]:
            value = str(container.get(key) or "").strip()
            if value and value != "[END]":
                return value
    answer = str(payload.get("answer") or "").strip()
    if answer:
        return answer
    if isinstance(payload.get("data"), dict):
        data = payload["data"]
        answer = str(data.get("answer") or "").strip()
        if answer:
            return answer
        outputs = data.get("outputs")
        if isinstance(outputs, dict):
            for key in ["answer", "text", "output"]:
                value = str(outputs.get(key) or "").strip()
                if value:
                    return value
    choices = payload.get("choices")
    if isinstance(choices, list):
        for item in choices:
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            if isinstance(message, dict):
                content = str(message.get("content") or "").strip()
                if content:
                    return content
    return ""


def _candidate_hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        payload.get("records"),
        payload.get("data"),
        payload.get("documents"),
        payload.get("results"),
    ]
    container = payload.get("c")
    if isinstance(container, dict):
        candidates.extend(
            [
                container.get("data"),
                container.get("records"),
                container.get("results"),
                container.get("ref_list"),
            ]
        )
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("records"),
                data.get("data"),
                data.get("documents"),
                data.get("results"),
                data.get("retriever_resources"),
            ]
        )
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _normalize_hit(item: dict[str, Any]) -> RecallHit:
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    title = str(
        item.get("title")
        or item.get("name")
        or metadata.get("title")
        or metadata.get("document_name")
        or ""
    ).strip()
    content = str(
        item.get("content")
        or item.get("segment")
        or item.get("text")
        or item.get("document")
        or metadata.get("content")
        or ""
    ).strip()
    source = str(
        item.get("source")
        or item.get("type")
        or item.get("recall_source")
        or item.get("document_name")
        or metadata.get("source")
        or metadata.get("url")
        or ""
    ).strip()
    raw_score = item.get("score", metadata.get("score"))
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None
    return RecallHit(content=content, title=title, source=source, score=score, metadata=metadata)


def _verification_note(success: bool, *, hits: list[dict[str, Any]], answer: str, error: str) -> str:
    if error:
        return error
    if answer:
        return "API returned a non-empty answer payload."
    if success and hits:
        return f"API returned {len(hits)} retrieval hits."
    if success:
        return "API call succeeded but produced no hits."
    return "API call failed."


def _request_json(
    *,
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(url=url, data=body, headers=_headers(api_key), method="POST")
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            raw_text = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        raw_text = exc.read().decode("utf-8", errors="replace")
        raise GetBijiAPIError(f"HTTP {exc.code}: {raw_text}") from exc
    except urllib_error.URLError as exc:
        raise GetBijiAPIError(f"Network error: {exc.reason}") from exc
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GetBijiAPIError(f"API returned non-JSON response: {raw_text[:300]}") from exc


def ask(
    *,
    question: str,
    raw_response_path: Path,
    topic_id: str | None = None,
    knowledge_base_id: str | None = None,
    user: str = "ai-da-guan-jia",
    response_mode: str = "blocking",
) -> AnswerResult:
    query = question.strip()
    if not query:
        raise ValueError("question cannot be empty")
    config = GetBijiConfig.from_env(topic_id=topic_id)
    payload: dict[str, Any] = {
        "question": query,
        "topic_ids": [config.topic_id],
    }
    if knowledge_base_id:
        payload["knowledge_base_id"] = knowledge_base_id.strip()
    response = _request_json(
        url=_endpoint(config.base_url, config.ask_path),
        api_key=config.api_key,
        payload=payload,
        timeout_seconds=config.timeout_seconds,
    )
    write_json(raw_response_path, response)
    hits = [_normalize_hit(item).to_dict() for item in _candidate_hits(response)]
    answer = _extract_answer(response)
    response_header = response.get("h")
    success = bool(
        answer
        or hits
        or (isinstance(response_header, dict) and int(response_header.get("c", 1) or 1) == 0)
        or response.get("data")
    )
    return AnswerResult(
        source="get_biji_api",
        operation="get_biji.ask",
        success=success,
        topic_id=config.topic_id,
        query=query,
        answer=answer,
        hits=hits,
        raw_response_path=str(raw_response_path.resolve()),
        verification_note=_verification_note(success, hits=hits, answer=answer, error=""),
        metadata={
            "request": payload,
            "base_url": config.base_url,
            "ask_path": config.ask_path,
            "response_mode": response_mode,
            "user": user,
        },
    )


def recall(
    *,
    query: str,
    raw_response_path: Path,
    topic_id: str | None = None,
    knowledge_base_id: str | None = None,
    top_k: int = 5,
) -> RecallResult:
    text = query.strip()
    if not text:
        raise ValueError("query cannot be empty")
    config = GetBijiConfig.from_env(topic_id=topic_id)
    payload: dict[str, Any] = {
        "question": text,
        "topic_id": config.topic_id,
        "top_k": max(1, int(top_k)),
    }
    if knowledge_base_id:
        payload["knowledge_base_id"] = knowledge_base_id.strip()
    response = _request_json(
        url=_endpoint(config.base_url, config.recall_path),
        api_key=config.api_key,
        payload=payload,
        timeout_seconds=config.timeout_seconds,
    )
    write_json(raw_response_path, response)
    hits = [_normalize_hit(item).to_dict() for item in _candidate_hits(response)]
    return RecallResult(
        source="get_biji_api",
        operation="get_biji.recall",
        success=True,
        topic_id=config.topic_id,
        query=text,
        hits=hits,
        raw_response_path=str(raw_response_path.resolve()),
        verification_note=_verification_note(True, hits=hits, answer="", error=""),
        metadata={
            "request": payload,
            "base_url": config.base_url,
            "recall_path": config.recall_path,
            "hit_count": len(hits),
        },
    )
