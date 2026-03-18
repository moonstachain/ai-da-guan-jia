#!/usr/bin/env python3
"""flomo -> 知识星球 candidate pipeline for AI大管家."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR.parents[1]
CODEX_HOME = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
FLOMO_ZSXQ_ROOT = ARTIFACTS_ROOT / "flomo-zsxq"
FLOMO_ZSXQ_RUNS_ROOT = FLOMO_ZSXQ_ROOT / "runs"
FLOMO_ZSXQ_CURRENT_ROOT = FLOMO_ZSXQ_ROOT / "current"
FLOMO_ZSXQ_CHECKPOINT_PATH = FLOMO_ZSXQ_CURRENT_ROOT / "checkpoint.json"
FLOMO_ZSXQ_NOTE_LEDGER_PATH = FLOMO_ZSXQ_CURRENT_ROOT / "note-ledger.json"
FLOMO_ZSXQ_POLL_RESULT_PATH = FLOMO_ZSXQ_CURRENT_ROOT / "latest-poll.json"
FLOMO_ZSXQ_PUBLISH_QUEUE_PATH = FLOMO_ZSXQ_CURRENT_ROOT / "publish-queue.json"
FLOMO_ZSXQ_ROLLOUT_STATE_PATH = FLOMO_ZSXQ_CURRENT_ROOT / "rollout-state.json"
FLOMO_ZSXQ_BACKFILL_RESULT_PATH = FLOMO_ZSXQ_CURRENT_ROOT / "latest-backfill.json"
FLOMO_MCP_SERVER_NAME = "flomo"
FLOMO_MCP_URL = "https://flomoapp.com/mcp"
DEFAULT_TAG = "#星球精选"
DEFAULT_POLL_LIMIT = 20
DEFAULT_BACKFILL_LIMIT = 200
DEFAULT_ZSXQ_URL = "https://www.zsxq.com/"
DEFAULT_ZSXQ_GROUP_URL = os.getenv("AI_DA_GUAN_JIA_ZSXQ_GROUP_URL", "https://wx.zsxq.com/group/15554854424522").strip() or "https://wx.zsxq.com/group/15554854424522"
DEFAULT_COLUMN_NAME = "原力小刺猬"
DEFAULT_SERIES_MODE = "ai_da_guan_jia_observer"
DEFAULT_IMAGE_SOURCE = "flomo_attachment"
DEFAULT_IMAGE_POLICY = "required"
DEFAULT_ROLLOUT_STAGE = "staged"
ROLLOUT_VERIFIED_THRESHOLD = 5
DEFAULT_HUMAN_ROLE = "小刺猬"
DEFAULT_AI_ROLE = "小精怪"
DEFAULT_PERSONA_VISIBILITY = "semi_explicit"
DEFAULT_STORY_MODEL = "hero_journey_dual_partner"
STORY_ARC_PLAN_PATH = SKILL_DIR / "story-arc-plan.md"
CHARACTER_CONTRACT_PATH = SKILL_DIR / "character-contract.md"
STORY_SOURCE_BUNDLE_PATH = SKILL_DIR / "story-source-bundle.json"
SERIAL_REQUIRED_SECTIONS = [
    "开场场景",
    "那一刻我看到了什么",
    "我当时为什么会这样判断",
    "这其实说明了 AI 的什么变化",
    "如果你是普通人，这件事和你有什么关系",
    "事实 / 观察 / 推断",
]
CODEX_BIN = Path("/Applications/Codex.app/Contents/Resources/codex")
ZSXQ_ASSISTANT_SCRIPT = CODEX_HOME / "skills" / "yuanli-zsxq-coevolution-assistant" / "scripts" / "yuanli_zsxq_assistant.py"
AI_DA_GUAN_JIA_SCRIPT = SCRIPT_DIR / "ai_da_guan_jia.py"
SWIFT_BIN = shutil.which("swift") or "/usr/bin/swift"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    seen: set[str] = set()
    normalized: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def normalize_tag(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("#") else f"#{text}"


def stable_hash(*parts: str) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def truncate(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    variants = [
        text,
        text.replace("Z", "+00:00"),
        text.replace("/", "-"),
    ]
    for candidate in variants:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).astimezone()
        except ValueError:
            continue
    return None


def canonical_timestamp(value: str | None) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return str(value or "").strip()
    return parsed.astimezone().isoformat(timespec="seconds")


def extract_tags(text: str) -> list[str]:
    tags = re.findall(r"(?<!\w)#([^\s#]+)", text or "")
    return normalize_list([f"#{tag}" for tag in tags])


def note_has_tag(note: dict[str, Any], tag: str) -> bool:
    normalized_tag = normalize_tag(tag)
    if not normalized_tag:
        return False
    tags = [normalize_tag(item) for item in normalize_list(note.get("tags"))]
    if normalized_tag in tags:
        return True
    return normalized_tag in extract_tags(str(note.get("content") or ""))


def normalize_slug_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    normalized = normalized.strip("-")
    return normalized or "unknown"


def default_flomo_source_url(memo_id: str) -> str:
    memo = str(memo_id or "").strip()
    if not memo:
        return ""
    return f"https://v.flomoapp.com/mine/?memo_id={memo}"


def resolve_codex_bin() -> Path:
    if CODEX_BIN.exists():
        return CODEX_BIN
    which = shutil.which("codex")
    if which:
        return Path(which)
    raise FileNotFoundError("Codex binary not found. Expected /Applications/Codex.app/Contents/Resources/codex.")


def read_mcp_config(name: str) -> dict[str, Any]:
    command = [str(resolve_codex_bin()), "mcp", "get", name, "--json"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if completed.returncode != 0:
        return {
            "configured": False,
            "enabled": False,
            "error": (completed.stderr or completed.stdout or "").strip(),
            "command": command,
        }
    stdout = completed.stdout or ""
    json_start = stdout.find("{")
    if json_start == -1:
        return {
            "configured": False,
            "enabled": False,
            "error": "codex mcp get returned no JSON payload.",
            "command": command,
        }
    payload = json.loads(stdout[json_start:])
    return {
        "configured": True,
        "enabled": bool(payload.get("enabled", True)),
        "payload": payload,
        "command": command,
        "error": "",
    }


def flomo_setup_hint() -> dict[str, Any]:
    return {
        "mcp_server": FLOMO_MCP_SERVER_NAME,
        "mcp_url": FLOMO_MCP_URL,
        "commands": [
            f"codex mcp add {FLOMO_MCP_SERVER_NAME} --url {FLOMO_MCP_URL}",
            f"codex mcp login {FLOMO_MCP_SERVER_NAME}",
        ],
        "official_doc": "https://help.flomoapp.com/advance/mcp/",
    }


def run_codex_exec_json(prompt: str, schema: dict[str, Any], *, timeout: int = 180) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="flomo-zsxq-codex-") as tempdir:
        temp_root = Path(tempdir)
        schema_path = temp_root / "schema.json"
        output_path = temp_root / "result.json"
        write_json(schema_path, schema)
        command = [
            str(resolve_codex_bin()),
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--cd",
            str(PROJECT_ROOT),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-",
        ]
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "command": command,
                "returncode": 124,
                "stdout": exc.stdout or "",
                "stderr": f"Codex exec timed out after {timeout} seconds.",
            }
        payload: dict[str, Any] = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            return payload
        if not output_path.exists():
            payload["returncode"] = 1
            payload["stderr"] = "Codex exec completed without a structured result."
            return payload
        try:
            payload["json"] = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            payload["returncode"] = 1
            payload["stderr"] = f"Structured output was not valid JSON: {exc}"
        return payload


def parse_last_message_json(text: str) -> dict[str, Any]:
    stripped = str(text or "").strip()
    if not stripped:
        raise json.JSONDecodeError("Empty last message.", stripped, 0)
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
    return json.loads(stripped)


def run_codex_exec_last_message(prompt: str, *, timeout: int = 180) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="flomo-zsxq-codex-plain-") as tempdir:
        temp_root = Path(tempdir)
        output_path = temp_root / "last_message.txt"
        command = [
            str(resolve_codex_bin()),
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--cd",
            str(PROJECT_ROOT),
            "--output-last-message",
            str(output_path),
            "-",
        ]
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "command": command,
                "returncode": 124,
                "stdout": exc.stdout or "",
                "stderr": f"Codex exec timed out after {timeout} seconds.",
            }
        payload: dict[str, Any] = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if not output_path.exists():
            return payload
        last_message = output_path.read_text(encoding="utf-8")
        payload["last_message"] = last_message
        try:
            payload["json"] = parse_last_message_json(last_message)
        except json.JSONDecodeError as exc:
            payload["json_error"] = f"Last message was not valid JSON: {exc}"
        return payload


def flomo_poll_schema() -> dict[str, Any]:
    note_properties = {
        "memo_id": {"type": "string"},
        "content": {"type": "string"},
        "updated_at": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "source_url": {"type": "string"},
        "deep_link": {"type": "string"},
        "has_image": {"type": "boolean"},
        "has_link": {"type": "boolean"},
        "has_voice": {"type": "boolean"},
        "image_urls": {"type": "array", "items": {"type": "string"}},
        "attachment_urls": {"type": "array", "items": {"type": "string"}},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {
                "type": "string",
                "enum": ["ready", "blocked_needs_user", "blocked_system"],
            },
            "blocked_reason": {"type": "string"},
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": note_properties,
                    "required": list(note_properties.keys()),
                },
            },
        },
        "required": ["status", "blocked_reason", "notes"],
    }


def build_flomo_poll_prompt(tag: str, checkpoint: dict[str, Any], limit: int) -> str:
    clean_tag = str(tag or "").strip().lstrip("#")
    after = str(checkpoint.get("last_source_update_at") or "").strip()
    after_note = after if after else "none"
    return f"""
Use the flomo MCP server only. Do not use shell commands or web browsing.

Task:
- Find recent flomo memos for the tag `{clean_tag}`.
- Prefer a tag search first. If needed, search memos by the same keywords.
- Return at most {limit} memos.
- Preserve memo text verbatim in `content`.
- Return only the memo id, content, updated_at, tags, source_url, deep_link, has_image, has_link, has_voice, image_urls, and attachment_urls.
- If MCP does not expose one of those fields, still include it with an empty string, `false`, or `[]`.
- If MCP is not authenticated or asks for user authorization, return `status = "blocked_needs_user"` and explain it in `blocked_reason`.
- If the MCP tool is available but fails for a non-auth reason, return `status = "blocked_system"` and explain it in `blocked_reason`.
- If no matching memos exist, return `status = "ready"` and an empty `notes` array.

Checkpoint:
- Last processed flomo update: `{after_note}`.
- Prefer memos updated at or after the checkpoint, but still return only true matches for `{clean_tag}`.
""".strip()


def build_flomo_poll_fallback_prompt(tag: str, checkpoint: dict[str, Any], limit: int) -> str:
    clean_tag = str(tag or "").strip().lstrip("#")
    after = str(checkpoint.get("last_source_update_at") or "").strip()
    after_note = after if after else "none"
    return f"""
Use the flomo MCP server only. Do not use shell commands or web browsing.

Task:
- Search recent flomo memos related to `{clean_tag}`.
- Use both memo search and tag search if needed.
- Prefer true tag matches for `{clean_tag}` over loose keyword matches.
- Return at most {limit} memos.
- For each memo return only `memo_id`, `content`, `updated_at`, `tags`, `source_url`, `deep_link`, `has_image`, `has_link`, `has_voice`, `image_urls`, and `attachment_urls`.
- If MCP does not expose one of those fields, still include it with an empty string, `false`, or `[]`.
- If MCP is not authenticated or asks for user authorization, return `status = "blocked_needs_user"` and explain it in `blocked_reason`.
- If the MCP tool is available but fails for a non-auth reason, return `status = "blocked_system"` and explain it in `blocked_reason`.
- If no matching memos exist, return `status = "ready"` and an empty `notes` array.

Checkpoint:
- Last processed flomo update: `{after_note}`.

End your response with one compact JSON object only:
{{
  "status": "ready|blocked_needs_user|blocked_system",
  "blocked_reason": "",
  "notes": [
    {{
      "memo_id": "...",
      "content": "...",
      "updated_at": "...",
      "tags": ["..."],
      "source_url": "",
      "deep_link": "",
      "has_image": false,
      "has_link": false,
      "has_voice": false,
      "image_urls": [],
      "attachment_urls": []
    }}
  ]
}}
""".strip()


def normalize_flomo_payload(
    payload: dict[str, Any],
    *,
    mcp_state: dict[str, Any],
    exec_result: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "status": "blocked_system",
            "blocked_reason": "flomo MCP result was not a JSON object.",
            "notes": [],
            "mcp_state": mcp_state,
            "exec_result": exec_result,
        }
    payload["mcp_state"] = mcp_state
    payload["exec_result"] = exec_result
    normalized_notes: list[dict[str, Any]] = []
    for item in payload.get("notes", []):
        if not isinstance(item, dict):
            continue
        note = {
            "memo_id": str(item.get("memo_id") or "").strip(),
            "content": str(item.get("content") or "").strip(),
            "updated_at": canonical_timestamp(str(item.get("updated_at") or "").strip()),
            "tags": normalize_list(item.get("tags")),
            "source_url": str(item.get("source_url") or default_flomo_source_url(str(item.get("memo_id") or ""))).strip(),
            "deep_link": str(item.get("deep_link") or "").strip(),
            "has_image": bool(item.get("has_image")),
            "has_link": bool(item.get("has_link")),
            "has_voice": bool(item.get("has_voice")),
            "image_urls": normalize_list(item.get("image_urls")),
            "attachment_urls": normalize_list(item.get("attachment_urls")),
        }
        if not note["memo_id"] or not note["content"]:
            continue
        normalized_notes.append(note)
    payload["notes"] = normalized_notes
    return payload


def read_flomo_candidates(tag: str, checkpoint: dict[str, Any], limit: int) -> dict[str, Any]:
    mcp_state = read_mcp_config(FLOMO_MCP_SERVER_NAME)
    if not mcp_state.get("configured"):
        return {
            "status": "blocked_needs_user",
            "blocked_reason": "flomo MCP server is not configured in Codex.",
            "setup_hint": flomo_setup_hint(),
            "notes": [],
            "mcp_state": mcp_state,
        }
    if not mcp_state.get("enabled", False):
        return {
            "status": "blocked_needs_user",
            "blocked_reason": "flomo MCP server exists but is disabled.",
            "setup_hint": flomo_setup_hint(),
            "notes": [],
            "mcp_state": mcp_state,
        }
    prompt = build_flomo_poll_prompt(tag=tag, checkpoint=checkpoint, limit=limit)
    result = run_codex_exec_json(prompt, flomo_poll_schema())
    if int(result.get("returncode", 1)) != 0:
        fallback_prompt = build_flomo_poll_fallback_prompt(tag=tag, checkpoint=checkpoint, limit=limit)
        fallback = run_codex_exec_last_message(fallback_prompt)
        if int(fallback.get("returncode", 1)) == 0 and isinstance(fallback.get("json"), dict):
            payload = normalize_flomo_payload(
                dict(fallback["json"]),
                mcp_state=mcp_state,
                exec_result={
                    "mode": "last_message_fallback",
                    "returncode": fallback.get("returncode", 0),
                    "stdout": fallback.get("stdout", ""),
                    "stderr": fallback.get("stderr", ""),
                },
            )
            payload["setup_hint"] = flomo_setup_hint()
            return payload
        primary_reason = str(result.get("stderr") or result.get("stdout") or "codex exec failed").strip()
        fallback_reason = str(
            fallback.get("stderr")
            or fallback.get("stdout")
            or fallback.get("json_error")
            or fallback.get("last_message")
            or ""
        ).strip()
        reason = fallback_reason or primary_reason
        status = "blocked_needs_user" if "oauth" in reason.lower() or "login" in reason.lower() else "blocked_system"
        return {
            "status": status,
            "blocked_reason": reason,
            "notes": [],
            "mcp_state": mcp_state,
            "setup_hint": flomo_setup_hint(),
            "exec_result": {
                "mode": "fallback_failed",
                "primary": {
                    "returncode": result.get("returncode", 1),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                },
                "fallback": {
                    "returncode": fallback.get("returncode", 1),
                    "stdout": fallback.get("stdout", ""),
                    "stderr": fallback.get("stderr", ""),
                    "json_error": fallback.get("json_error", ""),
                },
            },
        }
    payload = normalize_flomo_payload(
        dict(result.get("json", {})),
        mcp_state=mcp_state,
        exec_result={
            "mode": "output_schema",
            "returncode": result.get("returncode", 0),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        },
    )
    payload["setup_hint"] = flomo_setup_hint()
    return payload


def load_zsxq_assistant_module():
    if not ZSXQ_ASSISTANT_SCRIPT.exists():
        raise FileNotFoundError(f"Missing yuanli-zsxq-coevolution-assistant script: {ZSXQ_ASSISTANT_SCRIPT}")
    module_name = "flomo_zsxq_yuanli_zsxq_assistant"
    spec = importlib.util.spec_from_file_location(module_name, ZSXQ_ASSISTANT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {ZSXQ_ASSISTANT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ai_da_guan_jia_module():
    target_path = AI_DA_GUAN_JIA_SCRIPT.resolve()
    for module in list(sys.modules.values()):
        module_path = getattr(module, "__file__", "")
        if module_path and Path(module_path).resolve() == target_path:
            return module
    try:
        return importlib.import_module("ai_da_guan_jia")
    except Exception:
        pass
    module_name = "flomo_zsxq_ai_da_guan_jia"
    spec = importlib.util.spec_from_file_location(module_name, AI_DA_GUAN_JIA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {AI_DA_GUAN_JIA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_pipeline_options(args: Any) -> dict[str, Any]:
    return {
        "tag": str(getattr(args, "tag", DEFAULT_TAG) or DEFAULT_TAG).strip() or DEFAULT_TAG,
        "column_name": str(getattr(args, "column_name", DEFAULT_COLUMN_NAME) or DEFAULT_COLUMN_NAME).strip() or DEFAULT_COLUMN_NAME,
        "series_mode": str(getattr(args, "series_mode", DEFAULT_SERIES_MODE) or DEFAULT_SERIES_MODE).strip() or DEFAULT_SERIES_MODE,
        "image_source": str(getattr(args, "image_source", DEFAULT_IMAGE_SOURCE) or DEFAULT_IMAGE_SOURCE).strip() or DEFAULT_IMAGE_SOURCE,
        "image_policy": str(getattr(args, "image_policy", DEFAULT_IMAGE_POLICY) or DEFAULT_IMAGE_POLICY).strip() or DEFAULT_IMAGE_POLICY,
        "rollout_stage": str(getattr(args, "rollout_stage", DEFAULT_ROLLOUT_STAGE) or DEFAULT_ROLLOUT_STAGE).strip() or DEFAULT_ROLLOUT_STAGE,
        "group_url": str(getattr(args, "group_url", DEFAULT_ZSXQ_GROUP_URL) or DEFAULT_ZSXQ_GROUP_URL).strip() or DEFAULT_ZSXQ_GROUP_URL,
    }


def load_rollout_state() -> dict[str, Any]:
    payload = load_optional_json(FLOMO_ZSXQ_ROLLOUT_STATE_PATH)
    if payload:
        return payload
    return {
        "updated_at": "",
        "rollout_stage": DEFAULT_ROLLOUT_STAGE,
        "verified_manual_publish_count": 0,
        "auto_final_send_unlocked": False,
        "verified_note_ids": [],
    }


def refresh_rollout_state(ledger: dict[str, Any], *, rollout_stage: str) -> dict[str, Any]:
    verified_note_ids = [
        str(item.get("source_note_id") or "").strip()
        for item in ledger.get("notes", [])
        if str(item.get("publish_state") or "").strip() == "published"
        and str(item.get("final_human_confirmation") or "").strip() == "granted"
    ]
    verified_note_ids = [item for item in verified_note_ids if item]
    payload = {
        "updated_at": iso_now(),
        "rollout_stage": rollout_stage,
        "verified_manual_publish_count": len(verified_note_ids),
        "verified_note_ids": verified_note_ids,
        "verified_threshold": ROLLOUT_VERIFIED_THRESHOLD,
        "auto_final_send_unlocked": rollout_stage != "staged" or len(verified_note_ids) >= ROLLOUT_VERIFIED_THRESHOLD,
    }
    write_json(FLOMO_ZSXQ_ROLLOUT_STATE_PATH, payload)
    return payload


def flomo_run_id(note_id: str, created_at: str) -> str:
    stamp = (parse_datetime(created_at) or now_local()).strftime("%Y%m%d-%H%M%S-%f")
    return f"flomo-zsxq-{stamp}-{stable_hash(note_id)[:8]}"


def run_dir_for(run_id: str, created_at: str) -> Path:
    dt = parse_datetime(created_at) or now_local()
    return ensure_dir(FLOMO_ZSXQ_RUNS_ROOT / dt.strftime("%Y-%m-%d") / run_id)


def find_run_dir(run_id: str) -> Path:
    for date_dir in sorted(FLOMO_ZSXQ_RUNS_ROOT.glob("*")):
        candidate = date_dir / run_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"flomo-zsxq run not found: {run_id}")


def build_flomo_capture(note: dict[str, Any], *, run_id: str, title: str) -> dict[str, Any]:
    content = str(note.get("content") or "").strip()
    paragraphs = [line.strip() for line in content.splitlines() if line.strip()]
    material_status = "ready" if len(content) >= 60 else "partial" if len(content) >= 24 else "needs_more_material"
    return {
        "run_id": run_id,
        "created_at": iso_now(),
        "title": title,
        "identity": {
            "account": "原力星球",
            "role": "星主 + 共进化实验者",
            "voice_rule": "真实记录，不装权威",
        },
        "source_mode": "flomo_mcp",
        "source_skill": "ai-da-guan-jia",
        "source_system": "flomo_mcp",
        "source_note_id": str(note.get("memo_id") or "").strip(),
        "source_tag_matched": True,
        "source_tags": normalize_list(note.get("tags")),
        "source_url": str(note.get("source_url") or "").strip(),
        "deep_link": str(note.get("deep_link") or "").strip(),
        "materials": [
            {
                "id": "note-01",
                "source_type": "note",
                "path": "",
                "title": truncate(paragraphs[0] if paragraphs else title, 48),
                "char_count": len(content),
                "paragraph_count": len(paragraphs),
                "evidence_level": "工作笔记",
                "preview": truncate(content, 220),
                "paragraphs": paragraphs[:8],
            }
        ],
        "source_mix": {"note": 1},
        "themes": [truncate(paragraphs[0] if paragraphs else title, 28)],
        "material_sufficiency": {
            "status": material_status,
            "total_chars": len(content),
            "distinct_source_types": ["note"],
            "open_questions": [] if material_status != "needs_more_material" else ["这条 flomo 记录偏短，需要补一段更具体的场景或结论。"],
        },
        "timeline": [
            {
                "order": 1,
                "source_type": "note",
                "title": truncate(paragraphs[0] if paragraphs else title, 48),
            }
        ],
    }


def classify_entry_type(note: dict[str, Any]) -> str:
    text = "\n".join([str(note.get("content") or ""), " ".join(normalize_list(note.get("tags")))]).lower()
    method_keywords = ["方法", "步骤", "清单", "checklist", "原则", "框架", "模板"]
    experiment_keywords = ["实验", "测试", "验证", "试了", "复盘", "ab", "a/b"]
    if any(keyword in text for keyword in method_keywords):
        return "方法卡"
    if any(keyword in text for keyword in experiment_keywords):
        return "实验记录"
    return "觉醒日志"


def retag_suggestions(entry_type: str, tags: list[str]) -> list[str]:
    cleaned: list[str] = [entry_type]
    for tag in tags:
        normalized = tag.lstrip("#").strip()
        if not normalized or normalized == DEFAULT_TAG.lstrip("#"):
            continue
        cleaned.append(normalized)
        if len(cleaned) >= 3:
            break
    if "原力星球" not in cleaned and len(cleaned) < 3:
        cleaned.append("原力星球")
    return normalize_list(cleaned)[:3]


def build_action_prompt(packet: dict[str, Any]) -> str:
    question_hook = str(packet.get("question_hook") or "").strip()
    if question_hook:
        return question_hook
    title = str(packet.get("title") or "这条记录").strip()
    return f"如果你也对「{truncate(title, 18)}」有共鸣，最想继续追问哪一步？"


def render_source_markdown(note: dict[str, Any]) -> str:
    lines = [
        "# flomo Source",
        "",
        f"- `memo_id`: `{note['memo_id']}`",
        f"- `updated_at`: `{note['updated_at']}`",
        f"- `tags`: {' | '.join(note['tags']) or 'none'}",
        f"- `source_url`: {note['source_url'] or 'none'}",
        f"- `deep_link`: {note['deep_link'] or 'none'}",
        "",
        "## 原文",
        "",
        str(note.get("content") or "").rstrip(),
        "",
    ]
    return "\n".join(lines)


def render_publish_preview(packet: dict[str, Any], note: dict[str, Any]) -> str:
    lines = [
        "# Publish Preview",
        "",
        f"- `run_id`: `{packet['run_id']}`",
        f"- `source_system`: `{packet.get('source_system', 'flomo_mcp')}`",
        f"- `source_note_id`: `{packet.get('source_note_id', note.get('memo_id', ''))}`",
        f"- `post_type`: `{packet.get('post_type', '')}`",
        f"- `target_column_name`: `{packet.get('target_column_name', '')}`",
        f"- `title`: {packet.get('title', '')}",
        f"- `tags`: {' | '.join(normalize_list(packet.get('tag_suggestions'))) or 'none'}",
        "",
        "## 给成员的一句话",
        "",
        build_action_prompt(packet),
        "",
        "## 正文预览",
        "",
        str(packet.get("body_markdown") or "").rstrip(),
        "",
        "## 发布前检查",
        "",
    ]
    for item in normalize_list(packet.get("manual_confirmation_items")):
        lines.append(f"- [ ] {item}")
    lines.append("")
    return "\n".join(lines)


def render_initial_review(publish_result: dict[str, Any], note: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    next_prompts = {
        "run_id": publish_result["run_id"],
        "next_diary": [
            "把这条 flomo 候选整理成更完整的一次共进化日志。",
            "补一段最能证明这次变化的真实场景。",
        ],
        "next_method": [
            "把这条记录里最可复制的动作抽成三步方法卡。",
        ],
        "next_qa": [
            build_action_prompt({"title": note.get("content", ""), "question_hook": ""}),
        ],
    }
    review = "\n".join(
        [
            "# Review",
            "",
            f"- Publish status: {publish_result.get('status', 'draft_ready')}",
            f"- Reviewed at: {iso_now()}",
            "",
            "## Current state",
            "",
            "- 这条内容已经生成本地草稿与 publish packet。",
            "- 还没有进行最终发布，发布前仍需人工确认。",
            "",
            "## Next best topic",
            "",
            f"- 下一条最自然的承接问题：{next_prompts['next_qa'][0]}",
            "",
        ]
    )
    return review, next_prompts


def clean_note_title(note: dict[str, Any]) -> str:
    content = str(note.get("content") or "").strip()
    first_line = content.splitlines()[0] if content else str(note.get("memo_id") or "")
    title = re.sub(r"(?<!\w)#[^\s#]+", "", first_line).strip(" -:：")
    return truncate(title or str(note.get("memo_id") or "未命名记录"), 48)


def run_vision_ocr(image_path: Path, output_path: Path) -> dict[str, Any]:
    if not image_path.exists():
        return {"status": "blocked_system", "blocked_reason": f"Screenshot missing: {image_path}", "text": ""}
    if not SWIFT_BIN or not Path(SWIFT_BIN).exists():
        return {"status": "blocked_system", "blocked_reason": "Swift runtime is unavailable for OCR.", "text": ""}
    swift_code = """
import AppKit
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("usage: ocr.swift <image> <output>\\n", stderr)
    exit(2)
}
let imageURL = URL(fileURLWithPath: args[1])
let outputURL = URL(fileURLWithPath: args[2])
guard let image = NSImage(contentsOf: imageURL) else {
    fputs("load_failed\\n", stderr)
    exit(3)
}
var rect = NSRect(origin: .zero, size: image.size)
guard let cgImage = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
    fputs("cgimage_failed\\n", stderr)
    exit(4)
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
    let observations = request.results ?? []
    let text = observations.compactMap { observation -> String? in
        return observation.topCandidates(1).first?.string
    }.joined(separator: "\\n")
    try text.write(to: outputURL, atomically: true, encoding: .utf8)
    print(text.count)
} catch {
    fputs("ocr_failed\\n", stderr)
    exit(5)
}
"""
    with tempfile.TemporaryDirectory(prefix="flomo-zsxq-ocr-") as tempdir:
        swift_path = Path(tempdir) / "vision_ocr.swift"
        swift_path.write_text(swift_code, encoding="utf-8")
        completed = subprocess.run(
            [str(SWIFT_BIN), str(swift_path), str(image_path), str(output_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    if completed.returncode != 0:
        return {
            "status": "blocked_system",
            "blocked_reason": str(completed.stderr or completed.stdout or "Vision OCR failed.").strip(),
            "text": text,
        }
    return {"status": "ready", "blocked_reason": "", "text": text}


def capture_image_evidence(
    note: dict[str, Any],
    *,
    run_dir: Path,
    image_source: str,
    image_policy: str,
    session: str | None = None,
) -> dict[str, Any]:
    evidence_dir = ensure_dir(run_dir / "image-evidence")
    manifest_path = run_dir / "image-manifest.json"
    manifest: dict[str, Any] = {
        "run_id": run_dir.name,
        "created_at": iso_now(),
        "memo_id": str(note.get("memo_id") or ""),
        "image_source": image_source,
        "image_policy": image_policy,
        "status": "blocked_system",
        "blocked_reason": "",
        "source_url": str(note.get("source_url") or default_flomo_source_url(str(note.get("memo_id") or ""))),
        "has_image": bool(note.get("has_image")),
        "attachment_urls": normalize_list(note.get("attachment_urls")),
        "image_urls": normalize_list(note.get("image_urls")),
        "image_count": 0,
        "image_candidates": [],
        "ocr_text": "",
        "ocr_text_excerpt": "",
        "page_text_excerpt": "",
        "evidence_paths": [],
    }
    if image_source != DEFAULT_IMAGE_SOURCE:
        manifest["status"] = "blocked_system"
        manifest["blocked_reason"] = f"Unsupported image source: {image_source}"
        write_json(manifest_path, manifest)
        return manifest
    if not manifest["has_image"] and not manifest["attachment_urls"] and not manifest["image_urls"]:
        manifest["status"] = "blocked_needs_user" if image_policy == "required" else "ready"
        manifest["blocked_reason"] = "Flomo memo does not expose any attachment images."
        write_json(manifest_path, manifest)
        return manifest

    adagj = load_ai_da_guan_jia_module()
    working_dir = ensure_dir(run_dir / "playwright" / "flomo-attachments")
    session_name = session or adagj.tool_glue_playwright_session_name(run_dir.name, "flomo-attachments")
    open_command = ["open", manifest["source_url"]]
    open_result = adagj.run_playwright_cli(open_command, session=session_name, cwd=working_dir, timeout=180)
    manifest["open_result"] = open_result
    if int(open_result.get("returncode", 1)) != 0:
        manifest["status"] = "blocked_system"
        manifest["blocked_reason"] = "Flomo memo page could not be opened for attachment capture."
        write_json(manifest_path, manifest)
        return manifest

    adagj.tool_glue_wait(2, session=session_name, cwd=working_dir)
    probe = adagj.tool_glue_probe_page(session=session_name, cwd=working_dir)
    manifest["probe"] = probe.get("payload", {})
    page_text = str((probe.get("payload") or {}).get("text") or "").strip()
    manifest["page_text_excerpt"] = truncate(page_text, 1200)
    if adagj.tool_glue_text_looks_login_blocked(page_text):
        manifest["status"] = "blocked_needs_user"
        manifest["blocked_reason"] = "Flomo browser session needs login before attachment images can be read."
        write_json(manifest_path, manifest)
        return manifest

    image_probe_script = """
    const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
    const isVisible = (node) => {
      if (!node) return false;
      const style = window.getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") return false;
      const rect = node.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    };
    const images = [...document.querySelectorAll("img")]
      .filter((node) => isVisible(node))
      .map((node, index) => ({
        index: index + 1,
        src: node.currentSrc || node.src || "",
        alt: normalize(node.alt || node.getAttribute("aria-label") || ""),
        width: Math.round(node.getBoundingClientRect().width),
        height: Math.round(node.getBoundingClientRect().height),
      }))
      .filter((node) => node.src || node.alt);
    console.log(JSON.stringify({ image_count: images.length, images }));
    """
    image_probe = adagj.tool_glue_run_page_script(image_probe_script, session=session_name, cwd=working_dir, timeout=60)
    image_probe_payload = adagj.tool_glue_parse_json_from_output(image_probe.get("stdout") or "")
    if isinstance(image_probe_payload, dict):
        manifest["image_count"] = int(image_probe_payload.get("image_count") or 0)
        manifest["image_candidates"] = image_probe_payload.get("images", [])

    evidence = adagj.tool_glue_capture_page_evidence(session=session_name, cwd=evidence_dir, prefix="flomo-attachment-page")
    screenshot_path = Path(str(evidence.get("screenshot") or ""))
    snapshot_path = Path(str(evidence.get("snapshot") or ""))
    manifest["evidence_paths"] = [item for item in [str(screenshot_path), str(snapshot_path)] if item]

    ocr_path = evidence_dir / "flomo-attachment-page-ocr.txt"
    ocr_result = run_vision_ocr(screenshot_path, ocr_path) if screenshot_path.exists() else {
        "status": "blocked_system",
        "blocked_reason": "Attachment screenshot was not created.",
        "text": "",
    }
    manifest["ocr_status"] = str(ocr_result.get("status") or "")
    manifest["ocr_text"] = str(ocr_result.get("text") or "")
    manifest["ocr_text_excerpt"] = truncate(manifest["ocr_text"], 1200)
    if ocr_path.exists():
        manifest["evidence_paths"].append(str(ocr_path.resolve()))

    readable_alt = " ".join(
        truncate(str(item.get("alt") or ""), 120)
        for item in manifest.get("image_candidates", [])
        if str(item.get("alt") or "").strip()
    ).strip()
    if int(manifest.get("image_count") or 0) <= 0:
        manifest["status"] = "blocked_system"
        manifest["blocked_reason"] = "Flomo memo page opened, but no visible attachment images were detected."
    elif not manifest["ocr_text"].strip() and not readable_alt:
        manifest["status"] = "blocked_system"
        manifest["blocked_reason"] = "Attachment images were captured, but no readable OCR or alt-text evidence was extracted."
    else:
        manifest["status"] = "ready"
        manifest["blocked_reason"] = ""
    write_json(manifest_path, manifest)
    return manifest


def augment_capture_with_image_evidence(capture: dict[str, Any], image_manifest: dict[str, Any]) -> dict[str, Any]:
    augmented = dict(capture)
    materials = list(augmented.get("materials", []))
    evidence_paths = normalize_list(image_manifest.get("evidence_paths"))
    if evidence_paths:
        materials.append(
            {
                "id": "image-01",
                "source_type": "image_attachment",
                "path": evidence_paths[0],
                "title": "flomo 附件截图证据",
                "char_count": len(str(image_manifest.get("ocr_text") or "")),
                "paragraph_count": max(1, len([line for line in str(image_manifest.get("ocr_text") or "").splitlines() if line.strip()])),
                "evidence_level": "截图实证",
                "preview": truncate(str(image_manifest.get("ocr_text_excerpt") or image_manifest.get("page_text_excerpt") or ""), 220),
                "paragraphs": [truncate(str(image_manifest.get("ocr_text_excerpt") or image_manifest.get("page_text_excerpt") or ""), 220)],
            }
        )
    augmented["materials"] = materials
    source_mix = dict(augmented.get("source_mix") or {})
    if evidence_paths:
        source_mix["image_attachment"] = 1
    augmented["source_mix"] = source_mix
    sufficiency = dict(augmented.get("material_sufficiency") or {})
    open_questions = normalize_list(sufficiency.get("open_questions"))
    if str(image_manifest.get("status") or "") != "ready":
        open_questions.append(str(image_manifest.get("blocked_reason") or "Image evidence is required before drafting."))
        sufficiency["status"] = "needs_more_material"
    distinct_source_types = normalize_list(sufficiency.get("distinct_source_types"))
    if evidence_paths and "image_attachment" not in distinct_source_types:
        distinct_source_types.append("image_attachment")
    sufficiency["distinct_source_types"] = distinct_source_types
    sufficiency["open_questions"] = open_questions
    augmented["material_sufficiency"] = sufficiency
    return augmented


def scene_reconstruction_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "opening_scene": {"type": "string"},
            "what_i_saw": {"type": "string"},
            "why_i_judged_it": {"type": "string"},
            "ai_change": {"type": "string"},
            "reader_relevance": {"type": "string"},
            "facts": {"type": "array", "items": {"type": "string"}},
            "observations": {"type": "array", "items": {"type": "string"}},
            "inferences": {"type": "array", "items": {"type": "string"}},
            "caveats": {"type": "array", "items": {"type": "string"}},
            "question_hook": {"type": "string"},
        },
        "required": [
            "title",
            "opening_scene",
            "what_i_saw",
            "why_i_judged_it",
            "ai_change",
            "reader_relevance",
            "facts",
            "observations",
            "inferences",
            "caveats",
            "question_hook",
        ],
    }


def build_scene_reconstruction_prompt(note: dict[str, Any], image_manifest: dict[str, Any], *, column_name: str) -> str:
    return f"""
You are rewriting one flomo memo into a knowledge-planet serial entry for ordinary readers who are still new to AI.

Hard rules:
- Write in simplified Chinese.
- Use first-person human observer voice.
- Be warm and understandable for beginners.
- Only use evidence from the memo text plus the extracted screenshot evidence below.
- Do not invent UI details, dates, or actions that are not supported by the source.
- Keep `facts`, `observations`, and `inferences` separated.
- Keep the recurring world half-explicit rather than fully fictionalized.
- The human role is `{DEFAULT_HUMAN_ROLE}` and the AI role is `{DEFAULT_AI_ROLE}`.
- Use a hero's-journey rhythm: one concrete task difficulty, two partners crossing one threshold together.
- Do not turn the entry into fantasy dialogue, cartoon banter, or invented backstory.

Target series:
- Column name: `{column_name}`
- Reader profile: 对 AI 相对陌生的普通人类读者
- Story model: `{DEFAULT_STORY_MODEL}`
- Persona visibility: `{DEFAULT_PERSONA_VISIBILITY}`

Memo content:
{note.get("content", "")}

Memo tags:
{", ".join(normalize_list(note.get("tags")))}

Screenshot OCR evidence:
{image_manifest.get("ocr_text", "")}

Screenshot page evidence:
{image_manifest.get("page_text_excerpt", "")}

Return one compact JSON object only.
""".strip()


def fallback_scene_reconstruction(note: dict[str, Any], image_manifest: dict[str, Any], *, column_name: str) -> dict[str, Any]:
    title = clean_note_title(note)
    ocr_excerpt = truncate(str(image_manifest.get("ocr_text_excerpt") or image_manifest.get("page_text_excerpt") or ""), 220)
    content = str(note.get("content") or "").strip()
    return {
        "title": f"【{column_name}】{title}",
        "opening_scene": f"那天我像往常一样在整理工作现场，小刺猬这边先碰到的还是一个具体难题，而小精怪真正被看见，是从这句记录开始的：{truncate(content, 60)}",
        "what_i_saw": truncate(content, 180),
        "why_i_judged_it": "我会把它标成“星球精选”，通常不是因为一句话漂亮，而是因为这背后已经露出了一个任务难题如何被人和 AI 一起往前推的拐点。",
        "ai_change": "这类记录往往说明，AI 不再只是一个被动问答框，而开始在真实协作里承担更明确的组织、校准或推进作用。",
        "reader_relevance": "如果你对 AI 还不熟，这样的变化最值得关注的地方，是它开始从“陪你聊一聊”走向“陪你把一个难题往前解决”。",
        "facts": [truncate(content, 160), ocr_excerpt] if ocr_excerpt else [truncate(content, 160)],
        "observations": ["我观察到，这条记录本身已经带有明显的任务现场感，而且能看出小刺猬和小精怪开始形成稳定分工。"] + ([f"截图里还能补出一些上下文：{ocr_excerpt}"] if ocr_excerpt else []),
        "inferences": ["我的推断是，这不是一次孤立的灵感，而是小刺猬和小精怪这条连续剧里又一次跨过门槛的阶段性信号。"],
        "caveats": ["截图 OCR 只保留了可提取到的文字，未提取到的视觉细节不会被当成事实。"],
        "question_hook": "如果你第一次把 AI 当成搭档，你最在意它先帮你做哪一类事？",
    }


def generate_scene_reconstruction(note: dict[str, Any], image_manifest: dict[str, Any], *, column_name: str) -> dict[str, Any]:
    prompt = build_scene_reconstruction_prompt(note, image_manifest, column_name=column_name)
    result = run_codex_exec_json(prompt, scene_reconstruction_schema(), timeout=180)
    if int(result.get("returncode", 1)) == 0 and isinstance(result.get("json"), dict):
        payload = dict(result["json"])
        payload["generation_mode"] = "codex_exec"
        return payload
    payload = fallback_scene_reconstruction(note, image_manifest, column_name=column_name)
    payload["generation_mode"] = "fallback_template"
    payload["generation_error"] = str(result.get("stderr") or result.get("stdout") or "codex exec failed").strip()
    return payload


def build_series_tag_suggestions(entry_type: str, column_name: str) -> list[str]:
    return normalize_list([column_name, entry_type, "原力星球"])[:3]


def build_series_plan(
    note: dict[str, Any],
    scene: dict[str, Any],
    image_manifest: dict[str, Any],
    *,
    run_id: str,
    column_name: str,
    series_mode: str,
    rollout_stage: str,
    group_url: str,
) -> dict[str, Any]:
    entry_type = classify_entry_type(note)
    caveats = normalize_list(scene.get("caveats"))
    if str(image_manifest.get("ocr_status") or "") != "ready":
        caveats.append("截图 OCR 仍有盲区，正文只引用已提取到的文字证据。")
    return {
        "run_id": run_id,
        "entry_type": entry_type,
        "material_status": "ready",
        "themes": [clean_note_title(note)],
        "core_conclusion": str(scene.get("ai_change") or "").strip(),
        "tag_suggestions": build_series_tag_suggestions(entry_type, column_name),
        "manual_confirmation_items": [
            "确认正文只使用了 memo 原文和截图可见证据。",
            f"确认目标栏目为 {column_name}。",
            "确认事实 / 观察 / 推断三层没有混写。",
            "确认 staged rollout 当前允许的发布边界。",
        ],
        "risk_items": caveats,
        "open_questions": [],
        "source_mode": "flomo_mcp",
        "source_skill": "ai-da-guan-jia",
        "source_system": "flomo_mcp",
        "source_note_id": note["memo_id"],
        "source_tag_matched": True,
        "question_hook": str(scene.get("question_hook") or "").strip(),
        "target_column_name": column_name,
        "series_name": column_name,
        "series_mode": series_mode,
        "human_role": DEFAULT_HUMAN_ROLE,
        "ai_role": DEFAULT_AI_ROLE,
        "persona_visibility": DEFAULT_PERSONA_VISIBILITY,
        "story_model": DEFAULT_STORY_MODEL,
        "story_arc_plan_path": str(STORY_ARC_PLAN_PATH.resolve()),
        "character_contract_path": str(CHARACTER_CONTRACT_PATH.resolve()),
        "story_source_bundle_path": str(STORY_SOURCE_BUNDLE_PATH.resolve()),
        "rollout_stage": rollout_stage,
        "group_url": group_url,
        "image_policy": DEFAULT_IMAGE_POLICY,
        "image_manifest_path": str((run_dir_for(run_id, note["updated_at"]) / "image-manifest.json").resolve()) if note.get("updated_at") else "",
    }


def normalize_publish_packet(packet: dict[str, Any], pipeline_options: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(packet)
    column_name = str(normalized.get("target_column_name") or pipeline_options["column_name"] or DEFAULT_COLUMN_NAME).strip()
    normalized["target_column_name"] = column_name
    normalized["column_suggestions"] = normalize_list(normalized.get("column_suggestions")) or [column_name]
    normalized["series_name"] = str(normalized.get("series_name") or column_name).strip()
    normalized["series_mode"] = str(normalized.get("series_mode") or pipeline_options["series_mode"] or DEFAULT_SERIES_MODE).strip()
    normalized["rollout_stage"] = str(normalized.get("rollout_stage") or pipeline_options["rollout_stage"] or DEFAULT_ROLLOUT_STAGE).strip()
    normalized["group_url"] = str(normalized.get("group_url") or pipeline_options["group_url"] or DEFAULT_ZSXQ_GROUP_URL).strip()
    normalized["human_role"] = str(normalized.get("human_role") or DEFAULT_HUMAN_ROLE).strip()
    normalized["ai_role"] = str(normalized.get("ai_role") or DEFAULT_AI_ROLE).strip()
    normalized["persona_visibility"] = str(normalized.get("persona_visibility") or DEFAULT_PERSONA_VISIBILITY).strip()
    normalized["story_model"] = str(normalized.get("story_model") or DEFAULT_STORY_MODEL).strip()
    normalized["story_arc_plan_path"] = str(normalized.get("story_arc_plan_path") or STORY_ARC_PLAN_PATH.resolve())
    normalized["character_contract_path"] = str(normalized.get("character_contract_path") or CHARACTER_CONTRACT_PATH.resolve())
    normalized["story_source_bundle_path"] = str(normalized.get("story_source_bundle_path") or STORY_SOURCE_BUNDLE_PATH.resolve())
    return normalized


def render_serial_draft(scene: dict[str, Any], plan: dict[str, Any], image_manifest: dict[str, Any]) -> str:
    facts = normalize_list(scene.get("facts"))
    observations = normalize_list(scene.get("observations"))
    inferences = normalize_list(scene.get("inferences"))
    tags = normalize_list(plan.get("tag_suggestions"))
    ocr_excerpt = truncate(str(image_manifest.get("ocr_text_excerpt") or ""), 200)
    lines = [
        "---",
        f"run_id: {plan['run_id']}",
        f"entry_type: {plan['entry_type']}",
        "material_status: ready",
        f"title: {scene['title']}",
        f"target_column_name: {plan['target_column_name']}",
        f"series_mode: {plan['series_mode']}",
        f"human_role: {plan.get('human_role', DEFAULT_HUMAN_ROLE)}",
        f"ai_role: {plan.get('ai_role', DEFAULT_AI_ROLE)}",
        f"persona_visibility: {plan.get('persona_visibility', DEFAULT_PERSONA_VISIBILITY)}",
        f"story_model: {plan.get('story_model', DEFAULT_STORY_MODEL)}",
        "tags:",
    ]
    lines.extend([f"  - {tag}" for tag in tags])
    lines.extend(
        [
            "---",
            "",
            f"# {scene['title']}",
            "",
            "## 开场场景",
            "",
            str(scene.get("opening_scene") or "").strip(),
            "",
            "## 那一刻我看到了什么",
            "",
            str(scene.get("what_i_saw") or "").strip(),
            "",
            "## 我当时为什么会这样判断",
            "",
            str(scene.get("why_i_judged_it") or "").strip(),
            "",
            "## 这其实说明了 AI 的什么变化",
            "",
            str(scene.get("ai_change") or "").strip(),
            "",
            "## 如果你是普通人，这件事和你有什么关系",
            "",
            str(scene.get("reader_relevance") or "").strip(),
            "",
            "## 事实 / 观察 / 推断",
            "",
            "### 事实",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in facts])
    lines.extend(["", "### 观察", ""])
    lines.extend([f"- {item}" for item in observations])
    lines.extend(["", "### 推断", ""])
    lines.extend([f"- {item}" for item in inferences])
    if ocr_excerpt:
        lines.extend(
            [
                "",
                "## 截图证据摘录",
                "",
                ocr_excerpt,
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_blocked_review(blocked_result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    reason = str(blocked_result.get("message") or blocked_result.get("blocked_reason") or "Unknown blocker").strip()
    next_prompts = {
        "run_id": blocked_result["run_id"],
        "next_diary": ["补齐截图证据后，再继续这条观察记。"],
        "next_method": ["把这次卡住的原因写成一条图片门禁规则。"],
        "next_qa": ["下一步需要先补登录、附件，还是 selector？"],
    }
    review = "\n".join(
        [
            "# Review",
            "",
            f"- Publish status: {blocked_result.get('status', 'blocked')}",
            f"- Reviewed at: {iso_now()}",
            "",
            "## Blocking reason",
            "",
            f"- {reason}",
            "",
        ]
    )
    return review, next_prompts


def ensure_candidate_bundle(
    note: dict[str, Any],
    *,
    run_id: str,
    created_at: str,
    poll_run_id: str,
    pipeline_options: dict[str, Any],
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_dir = run_dir_for(run_id, created_at)
    zsxq = load_zsxq_assistant_module()
    title = clean_note_title(note)
    capture = build_flomo_capture(note, run_id=run_id, title=title)
    source_path = run_dir / "source.md"
    flomo_source = {
        "source_system": "flomo_mcp",
        "source_note_id": note["memo_id"],
        "source_tag_matched": True,
        "memo_id": note["memo_id"],
        "updated_at": note["updated_at"],
        "tags": note["tags"],
        "source_url": note["source_url"],
        "deep_link": note["deep_link"],
        "has_image": bool(note.get("has_image")),
        "has_link": bool(note.get("has_link")),
        "has_voice": bool(note.get("has_voice")),
        "image_urls": normalize_list(note.get("image_urls")),
        "attachment_urls": normalize_list(note.get("attachment_urls")),
        "content": note["content"],
        "target_column_name": pipeline_options["column_name"],
        "series_mode": pipeline_options["series_mode"],
    }
    source_path.write_text(render_source_markdown(note), encoding="utf-8")
    capture["materials"][0]["path"] = str(source_path.resolve())
    write_json(run_dir / "flomo-source.json", flomo_source)
    image_manifest = capture_image_evidence(
        note,
        run_dir=run_dir,
        image_source=pipeline_options["image_source"],
        image_policy=pipeline_options["image_policy"],
    )
    capture = augment_capture_with_image_evidence(capture, image_manifest)
    write_json(run_dir / "capture.json", capture)

    if pipeline_options["image_policy"] == "required" and str(image_manifest.get("status") or "") != "ready":
        blocked_status = str(image_manifest.get("status") or "blocked_system")
        publish_result = {
            "run_id": run_id,
            "created_at": iso_now(),
            "status": blocked_status,
            "source_system": "flomo_mcp",
            "source_note_id": note["memo_id"],
            "source_tag_matched": True,
            "publish_state": blocked_status,
            "final_human_confirmation": "pending",
            "blocked_reason": str(image_manifest.get("blocked_reason") or ""),
            "message": str(image_manifest.get("blocked_reason") or "Image evidence is required before drafting."),
            "target_column_name": pipeline_options["column_name"],
        }
        write_json(run_dir / "publish-result.json", publish_result)
        review_text, next_prompts = render_blocked_review(publish_result)
        (run_dir / "review.md").write_text(review_text, encoding="utf-8")
        write_json(run_dir / "next-prompts.json", next_prompts)
        checkpoint = {
            "run_id": run_id,
            "poll_run_id": poll_run_id,
            "source_system": "flomo_mcp",
            "source_note_id": note["memo_id"],
            "source_tag_matched": True,
            "source_updated_at": note["updated_at"],
            "processed_at": iso_now(),
            "fingerprint": stable_hash(note["memo_id"], note["updated_at"], note["content"]),
            "publish_state": blocked_status,
            "final_human_confirmation": "pending",
            "target_column_name": pipeline_options["column_name"],
            "series_mode": pipeline_options["series_mode"],
            "image_status": str(image_manifest.get("status") or ""),
        }
        write_json(run_dir / "checkpoint.json", checkpoint)
        return run_dir, {}, {}, checkpoint

    scene = generate_scene_reconstruction(note, image_manifest, column_name=pipeline_options["column_name"])
    write_json(run_dir / "scene-reconstruction.json", scene)

    plan = build_series_plan(
        note,
        scene,
        image_manifest,
        run_id=run_id,
        column_name=pipeline_options["column_name"],
        series_mode=pipeline_options["series_mode"],
        rollout_stage=pipeline_options["rollout_stage"],
        group_url=pipeline_options["group_url"],
    )
    write_json(run_dir / "entry-plan.json", plan)
    series_metadata = {
        "run_id": run_id,
        "created_at": iso_now(),
        "series_name": pipeline_options["column_name"],
        "target_column_name": pipeline_options["column_name"],
        "series_mode": pipeline_options["series_mode"],
        "human_role": DEFAULT_HUMAN_ROLE,
        "ai_role": DEFAULT_AI_ROLE,
        "persona_visibility": DEFAULT_PERSONA_VISIBILITY,
        "story_model": DEFAULT_STORY_MODEL,
        "story_arc_plan_path": str(STORY_ARC_PLAN_PATH.resolve()),
        "character_contract_path": str(CHARACTER_CONTRACT_PATH.resolve()),
        "story_source_bundle_path": str(STORY_SOURCE_BUNDLE_PATH.resolve()),
        "rollout_stage": pipeline_options["rollout_stage"],
        "required_sections": SERIAL_REQUIRED_SECTIONS,
        "source_note_id": note["memo_id"],
        "source_updated_at": note["updated_at"],
        "image_manifest_path": str((run_dir / "image-manifest.json").resolve()),
    }
    write_json(run_dir / "series-metadata.json", series_metadata)

    draft = render_serial_draft(scene, plan, image_manifest)
    (run_dir / "serial-draft.md").write_text(draft, encoding="utf-8")
    (run_dir / "draft.md").write_text(draft, encoding="utf-8")
    meta = zsxq.parse_simple_frontmatter(draft)
    packet = zsxq.prepare_publish_packet(run_dir, draft, meta, plan)
    packet["source_system"] = "flomo_mcp"
    packet["source_note_id"] = note["memo_id"]
    packet["source_tag_matched"] = True
    packet["publish_state"] = "draft_ready"
    packet["final_human_confirmation"] = "pending"
    packet["question_hook"] = build_action_prompt(packet)
    packet["target_column_name"] = pipeline_options["column_name"]
    packet["column_suggestions"] = [pipeline_options["column_name"]]
    packet["series_name"] = pipeline_options["column_name"]
    packet["series_mode"] = pipeline_options["series_mode"]
    packet["rollout_stage"] = pipeline_options["rollout_stage"]
    packet["group_url"] = pipeline_options["group_url"]
    packet["human_role"] = DEFAULT_HUMAN_ROLE
    packet["ai_role"] = DEFAULT_AI_ROLE
    packet["persona_visibility"] = DEFAULT_PERSONA_VISIBILITY
    packet["story_model"] = DEFAULT_STORY_MODEL
    packet["story_arc_plan_path"] = str(STORY_ARC_PLAN_PATH.resolve())
    packet["character_contract_path"] = str(CHARACTER_CONTRACT_PATH.resolve())
    packet["story_source_bundle_path"] = str(STORY_SOURCE_BUNDLE_PATH.resolve())
    write_json(run_dir / "publish-packet.json", packet)
    (run_dir / "publish-preview.md").write_text(render_publish_preview(packet, note), encoding="utf-8")

    publish_result = {
        "run_id": run_id,
        "created_at": iso_now(),
        "status": "draft_ready",
        "source_system": "flomo_mcp",
        "source_note_id": note["memo_id"],
        "source_tag_matched": True,
        "publish_state": "draft_ready",
        "final_human_confirmation": "pending",
        "message": "Serial draft and publish packet are ready locally. Final send still requires staged verification.",
        "target_column_name": pipeline_options["column_name"],
    }
    write_json(run_dir / "publish-result.json", publish_result)
    review_text, next_prompts = render_initial_review(publish_result, note)
    (run_dir / "review.md").write_text(review_text, encoding="utf-8")
    write_json(run_dir / "next-prompts.json", next_prompts)

    checkpoint = {
        "run_id": run_id,
        "poll_run_id": poll_run_id,
        "source_system": "flomo_mcp",
        "source_note_id": note["memo_id"],
        "source_tag_matched": True,
        "source_updated_at": note["updated_at"],
        "processed_at": iso_now(),
        "fingerprint": stable_hash(note["memo_id"], note["updated_at"], note["content"]),
        "publish_state": "draft_ready",
        "final_human_confirmation": "pending",
        "target_column_name": pipeline_options["column_name"],
        "series_mode": pipeline_options["series_mode"],
        "image_status": str(image_manifest.get("status") or ""),
    }
    write_json(run_dir / "checkpoint.json", checkpoint)
    return run_dir, plan, packet, checkpoint


def load_note_ledger() -> dict[str, Any]:
    payload = load_optional_json(FLOMO_ZSXQ_NOTE_LEDGER_PATH)
    notes = payload.get("notes")
    if not isinstance(notes, list):
        payload["notes"] = []
    return payload


def ledger_by_note_id(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in ledger.get("notes", []):
        if not isinstance(item, dict):
            continue
        note_id = str(item.get("source_note_id") or "").strip()
        if note_id:
            rows[note_id] = item
    return rows


def save_note_ledger(ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = iso_now()
    ledger["notes"] = sorted(
        [item for item in ledger.get("notes", []) if isinstance(item, dict)],
        key=lambda item: (str(item.get("latest_note_updated_at") or ""), str(item.get("source_note_id") or "")),
        reverse=True,
    )
    write_json(FLOMO_ZSXQ_NOTE_LEDGER_PATH, ledger)


def queue_publish_state(item: dict[str, Any]) -> str:
    publish_state = str(item.get("publish_state") or "").strip()
    if publish_state != "draft_ready":
        return publish_state
    run_dir_text = str(item.get("latest_run_dir") or "").strip()
    run_dir = Path(run_dir_text) if run_dir_text else None
    if not run_dir or not run_dir.exists():
        run_id = str(item.get("latest_run_id") or "").strip()
        if not run_id:
            return "blocked_system"
        try:
            run_dir = find_run_dir(run_id)
        except FileNotFoundError:
            return "blocked_system"
    if not (run_dir / "publish-packet.json").exists():
        return "blocked_system"
    if not (run_dir / "serial-draft.md").exists():
        return "blocked_system"
    image_manifest = load_optional_json(run_dir / "image-manifest.json")
    if str(image_manifest.get("status") or "") != "ready":
        return "blocked_system"
    return publish_state


def refresh_publish_queue(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    queue = sorted(
        [
            {
                "source_note_id": str(item.get("source_note_id") or ""),
                "latest_run_id": str(item.get("latest_run_id") or ""),
                "publish_state": queue_publish_state(item),
                "final_human_confirmation": str(item.get("final_human_confirmation") or ""),
                "title": str(item.get("title") or ""),
                "latest_note_updated_at": str(item.get("latest_note_updated_at") or ""),
                "target_column_name": str(item.get("target_column_name") or DEFAULT_COLUMN_NAME),
            }
            for item in ledger.get("notes", [])
            if str(item.get("publish_state") or "") != "published"
        ],
        key=lambda item: (str(item.get("latest_note_updated_at") or ""), str(item.get("source_note_id") or "")),
    )
    write_json(FLOMO_ZSXQ_PUBLISH_QUEUE_PATH, {"updated_at": iso_now(), "queue": queue})
    return queue


def should_materialize(note: dict[str, Any], existing: dict[str, Any] | None) -> bool:
    if not existing:
        return True
    previous = str(existing.get("latest_note_updated_at") or "").strip()
    current = str(note.get("updated_at") or "").strip()
    previous_dt = parse_datetime(previous)
    current_dt = parse_datetime(current)
    if previous_dt and current_dt:
        return current_dt > previous_dt
    return current != previous


def build_poll_summary(
    *,
    poll_run_id: str,
    tag: str,
    fetched: dict[str, Any],
    created_runs: list[dict[str, Any]],
    skipped_note_ids: list[str],
) -> dict[str, Any]:
    return {
        "poll_run_id": poll_run_id,
        "created_at": iso_now(),
        "tag": tag,
        "status": str(fetched.get("status") or "ready"),
        "blocked_reason": str(fetched.get("blocked_reason") or "").strip(),
        "fetched_notes": len(fetched.get("notes", [])),
        "created_runs": created_runs,
        "created_count": len(created_runs),
        "skipped_note_ids": skipped_note_ids,
        "setup_hint": fetched.get("setup_hint", {}),
    }


def render_poll_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# flomo -> 知识星球 Poll Summary",
        "",
        f"- `poll_run_id`: `{summary['poll_run_id']}`",
        f"- `status`: `{summary['status']}`",
        f"- `tag`: `{summary['tag']}`",
        f"- `fetched_notes`: {summary['fetched_notes']}",
        f"- `created_count`: {summary['created_count']}",
        "",
    ]
    blocked_reason = str(summary.get("blocked_reason") or "").strip()
    if blocked_reason:
        lines.extend(["## Blocked reason", "", blocked_reason, ""])
    if summary.get("created_runs"):
        lines.append("## New candidate runs")
        lines.append("")
        for item in summary["created_runs"]:
            lines.append(f"- `{item['run_id']}` ← `{item['source_note_id']}` ({item['publish_state']})")
        lines.append("")
    return "\n".join(lines)


def materialize_fetched_notes(
    fetched: dict[str, Any],
    *,
    created_at: str,
    poll_run_id: str,
    pipeline_options: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    ledger = load_note_ledger()
    ledger_index = ledger_by_note_id(ledger)
    created_runs: list[dict[str, Any]] = []
    skipped_note_ids: list[str] = []
    for raw_note in fetched.get("notes", []):
        note = {
            "memo_id": str(raw_note.get("memo_id") or "").strip(),
            "content": str(raw_note.get("content") or "").strip(),
            "updated_at": canonical_timestamp(str(raw_note.get("updated_at") or "").strip()),
            "tags": normalize_list(raw_note.get("tags")),
            "source_url": str(raw_note.get("source_url") or default_flomo_source_url(str(raw_note.get("memo_id") or ""))).strip(),
            "deep_link": str(raw_note.get("deep_link") or "").strip(),
            "has_image": bool(raw_note.get("has_image")),
            "has_link": bool(raw_note.get("has_link")),
            "has_voice": bool(raw_note.get("has_voice")),
            "image_urls": normalize_list(raw_note.get("image_urls")),
            "attachment_urls": normalize_list(raw_note.get("attachment_urls")),
        }
        if not note["memo_id"] or not note["content"] or not note_has_tag(note, pipeline_options["tag"]):
            continue
        existing = ledger_index.get(note["memo_id"])
        if not should_materialize(note, existing):
            skipped_note_ids.append(note["memo_id"])
            continue
        run_id = flomo_run_id(note["memo_id"], note["updated_at"] or created_at)
        run_dir, _plan, _packet, note_checkpoint = ensure_candidate_bundle(
            note,
            run_id=run_id,
            created_at=note["updated_at"] or created_at,
            poll_run_id=poll_run_id,
            pipeline_options=pipeline_options,
        )
        entry = existing or {"source_note_id": note["memo_id"], "run_ids": []}
        entry["source_system"] = "flomo_mcp"
        entry["source_note_id"] = note["memo_id"]
        entry["source_tag_matched"] = True
        entry["title"] = clean_note_title(note)
        entry["latest_note_updated_at"] = note["updated_at"]
        entry["latest_run_id"] = run_id
        entry["latest_run_dir"] = str(run_dir.resolve())
        entry["source_url"] = note["source_url"]
        entry["deep_link"] = note["deep_link"]
        entry["target_column_name"] = pipeline_options["column_name"]
        entry["series_mode"] = pipeline_options["series_mode"]
        entry["image_status"] = str(note_checkpoint.get("image_status") or "")
        entry["publish_state"] = str(note_checkpoint.get("publish_state") or "draft_ready")
        entry["final_human_confirmation"] = str(note_checkpoint.get("final_human_confirmation") or "pending")
        entry["run_ids"] = normalize_list([*normalize_list(entry.get("run_ids")), run_id])
        ledger_index[note["memo_id"]] = entry
        created_runs.append(
            {
                "run_id": run_id,
                "run_dir": str(run_dir.resolve()),
                "source_note_id": note["memo_id"],
                "publish_state": entry["publish_state"],
                "checkpoint_path": str((run_dir / "checkpoint.json").resolve()),
                "fingerprint": note_checkpoint["fingerprint"],
            }
        )

    ledger["notes"] = list(ledger_index.values())
    save_note_ledger(ledger)
    refresh_publish_queue(ledger)
    refresh_rollout_state(ledger, rollout_stage=pipeline_options["rollout_stage"])
    return ledger, created_runs, skipped_note_ids


def command_flomo_zsxq_poll(args: argparse.Namespace) -> int:
    created_at = str(getattr(args, "created_at", "") or iso_now())
    poll_run_id = str(getattr(args, "run_id", "") or flomo_run_id("poll", created_at))
    pipeline_options = build_pipeline_options(args)
    tag = pipeline_options["tag"]
    limit = int(getattr(args, "limit", DEFAULT_POLL_LIMIT) or DEFAULT_POLL_LIMIT)
    ensure_dir(FLOMO_ZSXQ_CURRENT_ROOT)
    checkpoint = load_optional_json(FLOMO_ZSXQ_CHECKPOINT_PATH)
    fetched = read_flomo_candidates(tag=tag, checkpoint=checkpoint, limit=limit)
    _ledger, created_runs, skipped_note_ids = materialize_fetched_notes(
        fetched,
        created_at=created_at,
        poll_run_id=poll_run_id,
        pipeline_options=pipeline_options,
    )

    last_source_update_at = checkpoint.get("last_source_update_at", "")
    if fetched.get("notes"):
        timestamps = [str(item.get("updated_at") or "").strip() for item in fetched["notes"] if str(item.get("updated_at") or "").strip()]
        if timestamps:
            last_source_update_at = max(timestamps)
    checkpoint_payload = {
        "updated_at": iso_now(),
        "poll_run_id": poll_run_id,
        "tag": tag,
        "last_source_update_at": last_source_update_at,
        "last_status": str(fetched.get("status") or "ready"),
        "last_blocked_reason": str(fetched.get("blocked_reason") or "").strip(),
        "created_count": len(created_runs),
        "target_column_name": pipeline_options["column_name"],
        "series_mode": pipeline_options["series_mode"],
        "rollout_stage": pipeline_options["rollout_stage"],
    }
    write_json(FLOMO_ZSXQ_CHECKPOINT_PATH, checkpoint_payload)

    summary = build_poll_summary(
        poll_run_id=poll_run_id,
        tag=tag,
        fetched=fetched,
        created_runs=created_runs,
        skipped_note_ids=skipped_note_ids,
    )
    write_json(FLOMO_ZSXQ_POLL_RESULT_PATH, summary)
    (FLOMO_ZSXQ_CURRENT_ROOT / "latest-poll.md").write_text(render_poll_summary(summary), encoding="utf-8")

    print(f"poll_run_id: {poll_run_id}")
    print(f"status: {summary['status']}")
    print(f"fetched_notes: {summary['fetched_notes']}")
    print(f"created_count: {summary['created_count']}")
    print(f"checkpoint_path: {FLOMO_ZSXQ_CHECKPOINT_PATH}")
    print(f"ledger_path: {FLOMO_ZSXQ_NOTE_LEDGER_PATH}")
    if created_runs:
        print(f"latest_run_id: {created_runs[0]['run_id']}")
    if summary["status"] == "blocked_needs_user":
        return 1
    if summary["status"] == "blocked_system":
        return 2
    return 0


def command_flomo_zsxq_backfill(args: argparse.Namespace) -> int:
    created_at = str(getattr(args, "created_at", "") or iso_now())
    backfill_run_id = str(getattr(args, "run_id", "") or flomo_run_id("backfill", created_at))
    pipeline_options = build_pipeline_options(args)
    limit = int(getattr(args, "limit", DEFAULT_BACKFILL_LIMIT) or DEFAULT_BACKFILL_LIMIT)
    ensure_dir(FLOMO_ZSXQ_CURRENT_ROOT)
    fetched = read_flomo_candidates(tag=pipeline_options["tag"], checkpoint={}, limit=limit)
    _ledger, created_runs, skipped_note_ids = materialize_fetched_notes(
        fetched,
        created_at=created_at,
        poll_run_id=backfill_run_id,
        pipeline_options=pipeline_options,
    )
    summary = build_poll_summary(
        poll_run_id=backfill_run_id,
        tag=pipeline_options["tag"],
        fetched=fetched,
        created_runs=created_runs,
        skipped_note_ids=skipped_note_ids,
    )
    summary["mode"] = "backfill"
    summary["target_column_name"] = pipeline_options["column_name"]
    write_json(FLOMO_ZSXQ_BACKFILL_RESULT_PATH, summary)
    print(f"backfill_run_id: {backfill_run_id}")
    print(f"status: {summary['status']}")
    print(f"created_count: {summary['created_count']}")
    print(f"backfill_result_path: {FLOMO_ZSXQ_BACKFILL_RESULT_PATH}")
    if summary["status"] == "blocked_needs_user":
        return 1
    if summary["status"] == "blocked_system":
        return 2
    return 0


def publish_state_from_result(result: dict[str, Any]) -> tuple[str, str]:
    status = str(result.get("status") or "").strip()
    lowered = status.lower()
    message = str(result.get("message") or result.get("blocked_reason") or "").strip()
    combined = f"{status} {message}".lower()
    if "published" in lowered:
        return "published", "granted"
    if "blocked_needs_user" in lowered or "auth" in combined or "login" in combined:
        return "blocked_needs_user", "pending"
    if "blocked_system" in lowered:
        return "blocked_system", "pending"
    if "auth" in combined or "login" in combined:
        return "blocked_needs_user", "pending"
    if "blocked" in lowered or "missing_" in lowered or "selector" in combined or "browser" in combined:
        return "blocked_system", "pending"
    if "manual_confirmation_required" in lowered:
        return "manual_confirmation_required", "pending"
    if "failed_partial" in lowered:
        return "failed_partial", "pending"
    return "draft_ready", "pending"


def command_flomo_zsxq_publish(args: argparse.Namespace) -> int:
    run_id = str(getattr(args, "run_id", "") or "").strip()
    if not run_id:
        raise ValueError("--run-id is required")
    run_dir = find_run_dir(run_id)
    flomo_source = read_json(run_dir / "flomo-source.json")
    pipeline_options = build_pipeline_options(args)
    image_manifest = load_optional_json(run_dir / "image-manifest.json")
    if str(image_manifest.get("status") or "") != "ready":
        result = {
            "run_id": run_id,
            "created_at": iso_now(),
            "status": str(image_manifest.get("status") or "blocked_system"),
            "source_system": "flomo_mcp",
            "source_note_id": flomo_source["memo_id"],
            "source_tag_matched": True,
            "publish_state": str(image_manifest.get("status") or "blocked_system"),
            "final_human_confirmation": "pending",
            "blocked_reason": str(image_manifest.get("blocked_reason") or "Image evidence is required before publishing."),
            "message": str(image_manifest.get("blocked_reason") or "Image evidence is required before publishing."),
            "target_column_name": pipeline_options["column_name"],
        }
        write_json(run_dir / "publish-result.json", result)
        print(f"run_id: {run_id}")
        print(f"status: {result['status']}")
        print(f"publish_state: {result['publish_state']}")
        print(f"publish_result_path: {run_dir / 'publish-result.json'}")
        return 1 if result["publish_state"] == "blocked_needs_user" else 2

    packet_path = run_dir / "publish-packet.json"
    if not packet_path.exists():
        raise FileNotFoundError(f"Missing publish packet for run {run_id}: {packet_path}")
    packet = normalize_publish_packet(read_json(packet_path), pipeline_options)
    write_json(packet_path, packet)
    adagj = load_ai_da_guan_jia_module()
    zsxq = load_zsxq_assistant_module()
    ledger = load_note_ledger()
    rollout = refresh_rollout_state(ledger, rollout_stage=pipeline_options["rollout_stage"])
    requested_final_send = bool(getattr(args, "final_send", False))
    manual_approval = bool(getattr(args, "manual_approval", False))
    final_send_allowed = requested_final_send and (bool(rollout.get("auto_final_send_unlocked")) or manual_approval)
    rollout_locked = requested_final_send and not final_send_allowed

    if not bool(getattr(args, "apply", False)):
        result = {
            "run_id": run_id,
            "created_at": iso_now(),
            "status": "draft_ready",
            "source_system": "flomo_mcp",
            "source_note_id": flomo_source["memo_id"],
            "source_tag_matched": True,
            "publish_state": "draft_ready",
            "final_human_confirmation": "pending",
            "message": "Local serial draft is ready. Run with --apply to open the publish flow.",
            "target_column_name": str(packet.get("target_column_name") or pipeline_options["column_name"]),
        }
    else:
        web_result = adagj.tool_glue_run_zsxq_publish_web(
            packet,
            execute=True,
            headed=not bool(getattr(args, "headless", False)),
            session=getattr(args, "session", None),
            final_send=final_send_allowed,
        )
        publish_state, final_confirmation = publish_state_from_result(web_result)
        result = {
            **web_result,
            "run_id": str(web_result.get("run_id") or run_id),
            "source_system": "flomo_mcp",
            "source_note_id": flomo_source["memo_id"],
            "source_tag_matched": True,
            "publish_state": publish_state,
            "final_human_confirmation": final_confirmation,
            "target_column_name": str(packet.get("target_column_name") or pipeline_options["column_name"]),
            "requested_final_send": requested_final_send,
            "final_send_allowed": final_send_allowed,
            "rollout_locked": rollout_locked,
            "rollout_state": rollout,
        }
        if rollout_locked:
            result["publish_state"] = "manual_confirmation_required"
            result["final_human_confirmation"] = "pending"
            result["message"] = (
                "Staged rollout is still locked. The page was prepared, but final send stayed disabled until five verified manual publishes are complete."
            )
        elif publish_state == "manual_confirmation_required" and not result.get("message"):
            result["message"] = "Publish page is ready. Stop here and ask the user before the final send."
    write_json(run_dir / "publish-result.json", result)

    if result["publish_state"] == "published":
        review_text, next_prompts = zsxq.build_review(run_dir, result, [])
    else:
        review_text, next_prompts = render_initial_review(result, flomo_source)
    (run_dir / "review.md").write_text(review_text + ("\n" if not review_text.endswith("\n") else ""), encoding="utf-8")
    write_json(run_dir / "next-prompts.json", next_prompts)

    checkpoint = load_optional_json(run_dir / "checkpoint.json")
    checkpoint["publish_state"] = result["publish_state"]
    checkpoint["final_human_confirmation"] = result["final_human_confirmation"]
    checkpoint["updated_at"] = iso_now()
    write_json(run_dir / "checkpoint.json", checkpoint)

    ledger = load_note_ledger()
    ledger_index = ledger_by_note_id(ledger)
    entry = ledger_index.get(flomo_source["memo_id"])
    if entry:
        entry["publish_state"] = result["publish_state"]
        entry["final_human_confirmation"] = result["final_human_confirmation"]
        entry["latest_run_id"] = run_id
        entry["latest_run_dir"] = str(run_dir.resolve())
        entry["target_column_name"] = str(packet.get("target_column_name") or pipeline_options["column_name"])
        if result["publish_state"] == "published":
            entry["published_url"] = str(result.get("published_url") or result.get("post_url") or "")
        ledger_index[flomo_source["memo_id"]] = entry
        ledger["notes"] = list(ledger_index.values())
        save_note_ledger(ledger)
        refresh_publish_queue(ledger)
        refresh_rollout_state(ledger, rollout_stage=pipeline_options["rollout_stage"])

    print(f"run_id: {run_id}")
    print(f"status: {result.get('status', '')}")
    print(f"publish_state: {result['publish_state']}")
    print(f"final_human_confirmation: {result['final_human_confirmation']}")
    print(f"publish_result_path: {run_dir / 'publish-result.json'}")
    if result["publish_state"] == "blocked_needs_user":
        return 1
    if result["publish_state"] == "blocked_system":
        return 2
    return 0
