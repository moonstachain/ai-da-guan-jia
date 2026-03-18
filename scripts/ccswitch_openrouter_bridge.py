#!/usr/bin/env python3
"""Prepare and activate OpenRouter-backed CC Switch providers.

This helper is designed to run on the target machine that hosts:
- ~/.cc-switch/cc-switch.db
- ~/.claude/settings.json
- ~/.codex/config.toml and ~/.codex/auth.json
- ~/.gemini/settings.json and ~/.gemini/.env

Typical usage on the remote machine:
  python3 scripts/ccswitch_openrouter_bridge.py prepare
  python3 scripts/ccswitch_openrouter_bridge.py activate --provider-id or-gpt54
  python3 scripts/ccswitch_openrouter_bridge.py verify
"""

from __future__ import annotations

import argparse
import copy
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time
from typing import Any


PLACEHOLDER_KEY = "__OPENROUTER_API_KEY__"

PROVIDERS = [
    ("or-gpt54", "OR GPT-5.4", "openai/gpt-5.4"),
    ("or-claude4", "OR Claude Sonnet 4", "anthropic/claude-sonnet-4"),
    ("or-gemini25", "OR Gemini 2.5 Pro", "google/gemini-2.5-pro-preview-03-25"),
    ("or-glm45", "OR GLM 4.5", "z-ai/glm-4.5"),
    ("or-kimi-k2", "OR Kimi K2", "moonshotai/kimi-k2"),
    ("or-minimax-m1", "OR MiniMax M1", "minimax/minimax-m1"),
]

REMOTE_OPENROUTER_URL = "https://openrouter.ai/api"
REMOTE_OPENROUTER_V1_URL = "https://openrouter.ai/api/v1"


def unix_ms() -> int:
    return int(time.time() * 1000)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:6] + "..." + value[-4:]


def backup_files(paths: list[Path], backup_root: Path) -> None:
    files_root = backup_root / "files"
    files_root.mkdir(parents=True, exist_ok=True)
    home = Path.home()
    for path in paths:
        if not path.exists():
            continue
        rel = path.relative_to(home)
        target = files_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def strip_codex_provider_section(raw: str) -> str:
    lines = raw.splitlines()
    kept: list[str] = []
    skip_provider_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[model_providers."):
            skip_provider_block = True
            continue
        if skip_provider_block and stripped.startswith("[") and not stripped.startswith("[model_providers."):
            skip_provider_block = False
        if skip_provider_block:
            continue
        if stripped.startswith("model_provider ="):
            continue
        if stripped.startswith("model ="):
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    return cleaned + "\n" if cleaned else ""


def top_level_assignment_keys(raw: str) -> set[str]:
    keys: set[str] = set()
    current_table: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current_table = stripped
            continue
        if current_table is None and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key:
                keys.add(key)
    return keys


def strip_duplicate_root_keys(raw: str, duplicate_keys: set[str]) -> str:
    if not duplicate_keys:
        return raw.strip() + ("\n" if raw.strip() else "")
    kept: list[str] = []
    current_table: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_table = stripped
            kept.append(line)
            continue
        if current_table is None and "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in duplicate_keys:
                continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    return cleaned + ("\n" if cleaned else "")


def split_toml_root_and_tables(raw: str) -> tuple[str, str]:
    root_lines: list[str] = []
    table_lines: list[str] = []
    in_tables = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_tables = True
        if in_tables:
            table_lines.append(line)
        else:
            root_lines.append(line)
    root = "\n".join(root_lines).strip()
    tables = "\n".join(table_lines).strip()
    return root, tables


def read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def write_env_file(path: Path, env_map: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in sorted(env_map.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def extract_provider_api_key(app_type: str, payload: dict[str, Any]) -> str:
    if app_type == "claude":
        env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
        return str(env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or "").strip()
    if app_type == "codex":
        auth = payload.get("auth") if isinstance(payload.get("auth"), dict) else {}
        return str(auth.get("OPENAI_API_KEY") or "").strip()
    if app_type == "gemini":
        env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
        return str(env.get("GEMINI_API_KEY") or "").strip()
    return ""


class BridgeContext:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home or Path.home()
        self.ccswitch_dir = self.home / ".cc-switch"
        self.db_path = self.ccswitch_dir / "cc-switch.db"
        self.ccswitch_settings_path = self.ccswitch_dir / "settings.json"
        self.ccswitch_logs_dir = self.ccswitch_dir / "logs"
        self.ccswitch_backups_dir = self.ccswitch_dir / "backups"
        self.claude_settings_path = self.home / ".claude" / "settings.json"
        self.codex_config_path = self.home / ".codex" / "config.toml"
        self.codex_auth_path = self.home / ".codex" / "auth.json"
        self.gemini_settings_path = self.home / ".gemini" / "settings.json"
        self.gemini_env_path = self.home / ".gemini" / ".env"

    def ensure_base_dirs(self) -> None:
        self.ccswitch_dir.mkdir(parents=True, exist_ok=True)
        self.ccswitch_backups_dir.mkdir(parents=True, exist_ok=True)
        self.ccswitch_logs_dir.mkdir(parents=True, exist_ok=True)

    def backup_snapshot(self, label: str) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_root = self.home / "backups" / f"ccswitch-cutover-{label}-{ts}"
        backup_root.mkdir(parents=True, exist_ok=True)
        paths = [
            self.db_path,
            self.ccswitch_settings_path,
            self.claude_settings_path,
            self.codex_config_path,
            self.codex_auth_path,
            self.gemini_settings_path,
            self.gemini_env_path,
        ]
        backup_files(paths, backup_root)
        return backup_root

    def connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Missing CC Switch database: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def query_template(conn: sqlite3.Connection, app_type: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT p.*, e.url AS endpoint_url
        FROM providers p
        LEFT JOIN provider_endpoints e
          ON e.provider_id = p.id AND e.app_type = p.app_type
        WHERE p.app_type = ? AND p.name = 'OpenRouter'
        ORDER BY p.is_current DESC, p.created_at DESC
        LIMIT 1
        """,
        (app_type,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Could not find OpenRouter template for {app_type}")
    return dict(row)


def set_common_configs(ctx: BridgeContext, conn: sqlite3.Connection) -> None:
    claude_settings = load_json(ctx.claude_settings_path, {})
    claude_common = copy.deepcopy(claude_settings)
    claude_common.pop("env", None)

    codex_common = strip_codex_provider_section(ctx.codex_config_path.read_text(encoding="utf-8"))
    gemini_common = load_json(ctx.gemini_settings_path, {})

    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("common_config_claude", json.dumps(claude_common, ensure_ascii=False)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("common_config_codex", codex_common),
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("common_config_gemini", json.dumps(gemini_common, ensure_ascii=False)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("common_config_legacy_migrated_v1", "true"),
    )


def update_claude_config(template_config: dict[str, Any], model_id: str, api_key: str) -> dict[str, Any]:
    config = copy.deepcopy(template_config)
    env = config.setdefault("env", {})
    env["ANTHROPIC_BASE_URL"] = REMOTE_OPENROUTER_URL
    env["ANTHROPIC_AUTH_TOKEN"] = api_key
    env["ANTHROPIC_API_KEY"] = api_key
    env["ANTHROPIC_MODEL"] = model_id
    env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model_id
    env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model_id
    env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model_id
    config["apiFormat"] = "openai_chat"
    config["api_format"] = "openai_chat"
    config["openrouterCompatMode"] = True
    config["openrouter_compat_mode"] = True
    return config


def update_codex_config(template_config: dict[str, Any], model_id: str, api_key: str) -> dict[str, Any]:
    config = copy.deepcopy(template_config)
    auth = config.setdefault("auth", {})
    auth["auth_mode"] = "apikey"
    auth["OPENAI_API_KEY"] = api_key
    raw = config.get("config", "")
    if re.search(r'(?m)^model = ".*"$', raw):
        raw = re.sub(r'(?m)^model = ".*"$', f'model = "{model_id}"', raw)
    else:
        raw = f'model = "{model_id}"\n' + raw
    if re.search(r'(?m)^model_provider = ".*"$', raw):
        raw = re.sub(r'(?m)^model_provider = ".*"$', 'model_provider = "openrouter"', raw)
    elif "[model_providers.openrouter]" not in raw:
        raw = 'model_provider = "openrouter"\n' + raw
    if "[model_providers.openrouter]" not in raw:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += (
            '\n[model_providers.openrouter]\n'
            'name = "openrouter"\n'
            f'base_url = "{REMOTE_OPENROUTER_V1_URL}"\n'
            'wire_api = "responses"\n'
            'requires_openai_auth = true\n'
        )
    config["config"] = raw.strip() + "\n"
    return config


def update_gemini_config(template_config: dict[str, Any], model_id: str, api_key: str) -> dict[str, Any]:
    config = copy.deepcopy(template_config)
    env = config.setdefault("env", {})
    env["GEMINI_API_KEY"] = api_key
    env["GEMINI_MODEL"] = model_id
    env["GOOGLE_GEMINI_BASE_URL"] = REMOTE_OPENROUTER_URL
    cfg = config.setdefault("config", {})
    security = cfg.setdefault("security", {})
    auth = security.setdefault("auth", {})
    auth["selectedType"] = "gemini-api-key"
    return config


def upsert_provider_rows(ctx: BridgeContext, conn: sqlite3.Connection) -> None:
    templates = {
        "claude": query_template(conn, "claude"),
        "codex": query_template(conn, "codex"),
        "gemini": query_template(conn, "gemini"),
    }
    next_sort_index = 100
    now = unix_ms()
    for provider_id, name, model_id in PROVIDERS:
        for app_type in ("claude", "codex", "gemini"):
            template = templates[app_type]
            base_settings = json.loads(template["settings_config"])
            base_meta = json.loads(template["meta"] or "{}")
            endpoint_url = template["endpoint_url"]

            if app_type == "claude":
                settings_config = update_claude_config(base_settings, model_id, PLACEHOLDER_KEY)
            elif app_type == "codex":
                settings_config = update_codex_config(base_settings, model_id, PLACEHOLDER_KEY)
            else:
                settings_config = update_gemini_config(base_settings, model_id, PLACEHOLDER_KEY)

            base_meta["modelId"] = model_id
            base_meta["managedBy"] = "ccswitch_openrouter_bridge"
            base_meta["preparedAt"] = now

            notes = f"Prepared by ccswitch_openrouter_bridge for {model_id}"
            conn.execute(
                """
                INSERT OR REPLACE INTO providers (
                    id, app_type, name, settings_config, website_url, category,
                    created_at, sort_index, notes, icon, icon_color, meta,
                    is_current, in_failover_queue, cost_multiplier,
                    limit_daily_usd, limit_monthly_usd, provider_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    app_type,
                    name,
                    json.dumps(settings_config, ensure_ascii=False, separators=(",", ":")),
                    template["website_url"],
                    template["category"],
                    now,
                    next_sort_index,
                    notes,
                    template["icon"],
                    template["icon_color"],
                    json.dumps(base_meta, ensure_ascii=False, separators=(",", ":")),
                    0,
                    0,
                    template["cost_multiplier"],
                    template["limit_daily_usd"],
                    template["limit_monthly_usd"],
                    template["provider_type"],
                ),
            )
            conn.execute(
                "DELETE FROM provider_endpoints WHERE provider_id = ? AND app_type = ?",
                (provider_id, app_type),
            )
            if endpoint_url:
                conn.execute(
                    """
                    INSERT INTO provider_endpoints (provider_id, app_type, url, added_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (provider_id, app_type, endpoint_url, now),
                )
        next_sort_index += 10


def update_all_provider_keys(conn: sqlite3.Connection, api_key: str) -> None:
    rows = conn.execute(
        """
        SELECT id, app_type, settings_config
        FROM providers
        WHERE id IN ({})
          AND app_type IN ('claude', 'codex', 'gemini')
        """.format(",".join("?" for _ in PROVIDERS)),
        tuple(provider_id for provider_id, _, _ in PROVIDERS),
    ).fetchall()
    for row in rows:
        payload = json.loads(row["settings_config"])
        if row["app_type"] == "claude":
            env = payload.setdefault("env", {})
            env["ANTHROPIC_AUTH_TOKEN"] = api_key
            env["ANTHROPIC_API_KEY"] = api_key
        elif row["app_type"] == "codex":
            payload.setdefault("auth", {})["OPENAI_API_KEY"] = api_key
        elif row["app_type"] == "gemini":
            payload.setdefault("env", {})["GEMINI_API_KEY"] = api_key
        conn.execute(
            "UPDATE providers SET settings_config = ? WHERE id = ? AND app_type = ?",
            (json.dumps(payload, ensure_ascii=False, separators=(",", ":")), row["id"], row["app_type"]),
        )


def find_prepared_api_key(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT app_type, settings_config
        FROM providers
        WHERE id IN ({})
          AND app_type IN ('claude', 'codex', 'gemini')
        ORDER BY created_at DESC
        """.format(",".join("?" for _ in PROVIDERS)),
        tuple(provider_id for provider_id, _, _ in PROVIDERS),
    ).fetchall()
    for row in rows:
        payload = json.loads(row["settings_config"])
        api_key = extract_provider_api_key(str(row["app_type"]), payload)
        if api_key and api_key != PLACEHOLDER_KEY:
            return api_key
    return ""


def set_current_provider(conn: sqlite3.Connection, provider_id: str) -> None:
    for app_type in ("claude", "codex", "gemini"):
        conn.execute("UPDATE providers SET is_current = 0 WHERE app_type = ?", (app_type,))
        conn.execute(
            "UPDATE providers SET is_current = 1 WHERE app_type = ? AND id = ?",
            (app_type, provider_id),
        )


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None or row["value"] is None:
        return default
    return str(row["value"])


def write_claude_live(ctx: BridgeContext, conn: sqlite3.Connection, provider_id: str) -> str:
    row = conn.execute(
        "SELECT settings_config FROM providers WHERE id = ? AND app_type = 'claude'",
        (provider_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Missing claude provider row for {provider_id}")
    provider_cfg = json.loads(row["settings_config"])
    common_cfg = json.loads(get_setting(conn, "common_config_claude", "{}") or "{}")
    merged = merge_dict(common_cfg, provider_cfg)
    dump_json(ctx.claude_settings_path, merged)
    return merged["env"]["ANTHROPIC_MODEL"]


def write_codex_live(ctx: BridgeContext, conn: sqlite3.Connection, provider_id: str) -> str:
    row = conn.execute(
        "SELECT settings_config FROM providers WHERE id = ? AND app_type = 'codex'",
        (provider_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Missing codex provider row for {provider_id}")
    provider_cfg = json.loads(row["settings_config"])
    common_cfg = get_setting(conn, "common_config_codex", "")
    provider_toml = provider_cfg.get("config", "").strip()
    common_root, common_tables = split_toml_root_and_tables(common_cfg)
    provider_root, provider_tables = split_toml_root_and_tables(provider_toml)
    common_root_keys = top_level_assignment_keys(common_root)
    provider_duplicate_keys = {
        key for key in top_level_assignment_keys(provider_toml)
        if key in common_root_keys and key not in {"model_provider", "model"}
    }
    provider_root = strip_duplicate_root_keys(provider_root, provider_duplicate_keys).strip()
    pieces = [piece for piece in [provider_root, common_root, provider_tables, common_tables] if piece.strip()]
    combined = "\n\n".join(pieces)
    ctx.codex_config_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.codex_config_path.write_text(combined.strip() + "\n", encoding="utf-8")

    auth_payload = load_json(ctx.codex_auth_path, {})
    auth_payload.update(provider_cfg.get("auth", {}))
    dump_json(ctx.codex_auth_path, auth_payload)

    match = re.search(r'(?m)^model = "(.*)"$', provider_root)
    return match.group(1) if match else ""


def write_gemini_live(ctx: BridgeContext, conn: sqlite3.Connection, provider_id: str) -> str:
    row = conn.execute(
        "SELECT settings_config FROM providers WHERE id = ? AND app_type = 'gemini'",
        (provider_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Missing gemini provider row for {provider_id}")
    provider_cfg = json.loads(row["settings_config"])
    common_cfg = json.loads(get_setting(conn, "common_config_gemini", "{}") or "{}")
    merged_settings = merge_dict(common_cfg, provider_cfg.get("config", {}))
    dump_json(ctx.gemini_settings_path, merged_settings)

    existing_env = read_env_file(ctx.gemini_env_path)
    existing_env.update(provider_cfg.get("env", {}))
    write_env_file(ctx.gemini_env_path, existing_env)
    return existing_env.get("GEMINI_MODEL", "")


def update_ccswitch_settings(ctx: BridgeContext, provider_id: str) -> None:
    settings_payload = load_json(ctx.ccswitch_settings_path, {})
    settings_payload["currentProviderClaude"] = provider_id
    settings_payload["currentProviderCodex"] = provider_id
    settings_payload["currentProviderGemini"] = provider_id
    dump_json(ctx.ccswitch_settings_path, settings_payload)


def command_prepare(ctx: BridgeContext) -> int:
    ctx.ensure_base_dirs()
    backup_root = ctx.backup_snapshot("prepare")
    with ctx.connect() as conn:
        set_common_configs(ctx, conn)
        upsert_provider_rows(ctx, conn)
        conn.commit()

    print(f"backup_dir={backup_root}")
    print("prepared_provider_ids=" + ",".join(provider_id for provider_id, _, _ in PROVIDERS))
    return 0


def command_activate(ctx: BridgeContext, provider_id: str, api_key: str | None) -> int:
    provider_ids = {item[0] for item in PROVIDERS}
    if provider_id not in provider_ids:
        raise SystemExit(f"Unknown provider id: {provider_id}")
    if not api_key:
        api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        with ctx.connect() as conn:
            api_key = find_prepared_api_key(conn)
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("OpenRouter API key: ")
    if not api_key:
        raise SystemExit("Missing OpenRouter API key. Set OPENROUTER_API_KEY or run interactively.")

    backup_root = ctx.backup_snapshot(f"activate-{provider_id}")
    with ctx.connect() as conn:
        update_all_provider_keys(conn, api_key)
        set_current_provider(conn, provider_id)
        claude_model = write_claude_live(ctx, conn, provider_id)
        codex_model = write_codex_live(ctx, conn, provider_id)
        gemini_model = write_gemini_live(ctx, conn, provider_id)
        update_ccswitch_settings(ctx, provider_id)
        conn.commit()

    print(f"backup_dir={backup_root}")
    print(f"activated_provider={provider_id}")
    print(f"claude_model={claude_model}")
    print(f"codex_model={codex_model}")
    print(f"gemini_model={gemini_model}")
    print(f"api_key={redact(api_key)}")
    return 0


def command_verify(ctx: BridgeContext) -> int:
    with ctx.connect() as conn:
        current_rows = conn.execute(
            """
            SELECT id, app_type, name, is_current
            FROM providers
            WHERE app_type IN ('claude', 'codex', 'gemini')
              AND is_current = 1
            ORDER BY app_type
            """
        ).fetchall()
    current_map = {row["app_type"]: (row["id"], row["name"]) for row in current_rows}

    claude_payload = load_json(ctx.claude_settings_path, {})
    codex_raw = ctx.codex_config_path.read_text(encoding="utf-8") if ctx.codex_config_path.exists() else ""
    gemini_env = read_env_file(ctx.gemini_env_path)

    claude_env = claude_payload.get("env", {})
    claude_model = claude_env.get("ANTHROPIC_MODEL") or claude_env.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "")
    codex_model_match = re.search(r'(?m)^model = "(.*)"$', codex_raw)
    codex_model = codex_model_match.group(1) if codex_model_match else ""
    gemini_model = gemini_env.get("GEMINI_MODEL", "")

    print(f"current_claude_provider={current_map.get('claude', ('', ''))[0]}")
    print(f"current_codex_provider={current_map.get('codex', ('', ''))[0]}")
    print(f"current_gemini_provider={current_map.get('gemini', ('', ''))[0]}")
    print(f"claude_model={claude_model}")
    print(f"codex_model={codex_model}")
    print(f"gemini_model={gemini_model}")
    print(f"claude_base_url={claude_env.get('ANTHROPIC_BASE_URL', '')}")
    print(f"gemini_base_url={gemini_env.get('GOOGLE_GEMINI_BASE_URL', '')}")
    print(f"codex_has_openrouter={'openrouter.ai/api/v1' in codex_raw}")
    print(f"codex_cli_exists={(ctx.home / '.local/bin/codex').exists()}")
    print(f"claude_cli_exists={(ctx.home / '.local/bin/claude').exists()}")
    print(f"gemini_cli_exists={(ctx.home / '.local/bin/gemini').exists()}")
    print(f"ccswitch_app_exists={(ctx.home / 'Applications/CC Switch.app').exists()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("prepare", help="Back up current state and prepare six OpenRouter providers.")

    activate = sub.add_parser("activate", help="Store the OpenRouter key, switch current provider, and write live configs.")
    activate.add_argument("--provider-id", default="or-gpt54", help="Provider id to activate. Default: or-gpt54")
    activate.add_argument("--api-key", default="", help="Optional OpenRouter API key. Prefer env or interactive prompt.")

    sub.add_parser("verify", help="Print current provider and live config summary.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ctx = BridgeContext()
    if args.command == "prepare":
        return command_prepare(ctx)
    if args.command == "activate":
        return command_activate(ctx, args.provider_id, args.api_key or None)
    if args.command == "verify":
        return command_verify(ctx)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
