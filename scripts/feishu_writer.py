#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib import request

REPO_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import load_feishu_credentials


WIKI_TOKEN = "LO0uweNbDiVl6QkTUmgc3SfWnmf"
APP_TOKEN = "UeWubgnADaLw3tsjIB8cPup8ndf"
T01_TABLE_NAME = "T01_候选人主表"
T02_TABLE_NAME = "T02_AI简历分析"
LOCAL_TZ = timezone(timedelta(hours=8))


def now_ms() -> int:
    return int(datetime.now(LOCAL_TZ).timestamp() * 1000)


def req(api: FeishuBitableAPI, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return api._request(path, method=method, payload=payload)


def table_by_name(api: FeishuBitableAPI, app_token: str, table_name: str) -> dict[str, Any]:
    payload = req(api, "GET", f"/open-apis/bitable/v1/apps/{app_token}/tables?page_size=500")
    for item in (payload.get("data") or {}).get("items") or []:
        if str(item.get("name") or item.get("table_name") or "").strip() == table_name:
            return item
    raise RuntimeError(f"Missing Feishu table: {table_name}")


def create_record(api: FeishuBitableAPI, app_token: str, table_id: str, fields: dict[str, Any]) -> str:
    payload = req(api, "POST", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records", {"fields": fields})
    record = (payload.get("data") or {}).get("record") or {}
    record_id = str(record.get("record_id") or record.get("id") or "").strip()
    if not record_id:
        raise RuntimeError(f"Failed to create record in table {table_id}")
    return record_id


def resolve_app_token(api: FeishuBitableAPI) -> str:
    payload = req(api, "GET", f"/open-apis/wiki/v2/spaces/get_node?token={WIKI_TOKEN}")
    token = str((((payload.get("data") or {}).get("node") or {}).get("obj_token")) or "").strip()
    if not token:
        raise RuntimeError("Unable to resolve Feishu app token from wiki token.")
    return token


def extract_score(payload: dict[str, Any]) -> int | None:
    for key in (
        "overall_score",
        "score",
        "resume_score",
        "AI综合评分",
    ):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            match = re.search(r"(\d+)", value)
            if match:
                return int(match.group(1))
    return None


def extract_grade(payload: dict[str, Any]) -> str:
    for key in ("grade", "ai_grade", "AI等级"):
        value = str(payload.get(key) or "").strip().upper()
        if value in {"S", "A", "B", "C", "D"}:
            return value
    return ""


def stringify_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_t01_fields(
    resume_payload: dict[str, Any],
    score_payload: dict[str, Any],
    *,
    target_project: str,
    target_role: str,
    source_channel: str,
    tag: str,
) -> dict[str, Any]:
    ts = now_ms()
    fields = {
        "姓名": str(resume_payload.get("candidate_name") or resume_payload.get("source_name") or "未命名候选人").strip(),
        "目标项目": target_project,
        "目标岗位": target_role,
        "来源渠道": source_channel,
        "简历解析文本": str(resume_payload.get("plain_text") or "").strip(),
        "AI综合评分": extract_score(score_payload) or "",
        "AI等级": extract_grade(score_payload),
        "AI推荐意见": str(
            score_payload.get("recommendation_summary")
            or score_payload.get("summary")
            or score_payload.get("verdict_reasoning")
            or ""
        ).strip(),
        "当前阶段": "S1简历筛选",
        "创建时间": ts,
        "阶段更新时间": ts,
        "标签": [tag] if tag else [],
    }
    return {key: value for key, value in fields.items() if value not in ("", None, [], {})}


def build_t02_fields(
    resume_payload: dict[str, Any],
    score_payload: dict[str, Any],
    *,
    candidate_record_id: str,
    scorer_version: str,
) -> dict[str, Any]:
    ts = now_ms()
    prompt_trace = score_payload.get("thought_process") or score_payload.get("thinking") or ""
    model_output = stringify_json(score_payload)
    questions = score_payload.get("recommended_interview_questions") or []
    if isinstance(questions, list):
        question_text = "\n".join(f"- {str(item).strip()}" for item in questions if str(item).strip())
    else:
        question_text = str(questions or "").strip()
    fields = {
        "候选人": [candidate_record_id],
        "使用提示词版本": scorer_version,
        "AI思考过程": str(prompt_trace).strip(),
        "AI输出结果": model_output,
        "推荐面试问题": question_text,
        "分析时间": ts,
    }
    return {key: value for key, value in fields.items() if value not in ("", None, [], {})}


def send_webhook_message(webhook_url: str, text: str, *, dry_run: bool) -> dict[str, Any]:
    payload = {"msg_type": "text", "content": {"text": text}}
    if dry_run:
        return {"status": "dry_run", "channel": "webhook", "payload": payload}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req_obj = request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req_obj, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def send_chat_message(api: FeishuBitableAPI, chat_id: str, text: str, *, dry_run: bool) -> dict[str, Any]:
    payload = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }
    if dry_run:
        return {"status": "dry_run", "channel": "chat", "payload": payload}
    return req(api, "POST", "/open-apis/im/v1/messages?receive_id_type=chat_id", payload)


def maybe_notify(
    *,
    api: FeishuBitableAPI | None,
    candidate_name: str,
    grade: str,
    score: int | None,
    source_channel: str,
    notify_grades: set[str],
    webhook_url: str,
    chat_id: str,
    dry_run: bool,
) -> dict[str, Any] | None:
    if not grade or grade.upper() not in notify_grades:
        return None
    text = f"候选人命中重点等级：{candidate_name} | 等级 {grade} | 分数 {score or 'N/A'} | 渠道 {source_channel}"
    if webhook_url:
        return send_webhook_message(webhook_url, text, dry_run=dry_run)
    if chat_id and api is not None:
        return send_chat_message(api, chat_id, text, dry_run=dry_run)
    return {"status": "skipped", "reason": "no_notification_target", "text": text}


def ingest_candidate(
    resume_payload: dict[str, Any],
    score_payload: dict[str, Any],
    *,
    target_project: str,
    target_role: str,
    source_channel: str,
    tag: str,
    scorer_version: str,
    notify_grades: set[str],
    webhook_url: str,
    chat_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    t01_fields = build_t01_fields(
        resume_payload,
        score_payload,
        target_project=target_project,
        target_role=target_role,
        source_channel=source_channel,
        tag=tag,
    )
    result: dict[str, Any] = {
        "mode": "dry_run" if dry_run else "apply",
        "candidate_name": t01_fields.get("姓名"),
        "t01_fields": t01_fields,
        "notify_grades": sorted(notify_grades),
    }

    api: FeishuBitableAPI | None = None
    candidate_record_id = ""
    t02_fields: dict[str, Any] = {}

    if dry_run:
        t02_fields = build_t02_fields(
            resume_payload,
            score_payload,
            candidate_record_id="dry-run-record-id",
            scorer_version=scorer_version,
        )
        result["t02_fields"] = t02_fields
        result["notification"] = maybe_notify(
            api=None,
            candidate_name=str(t01_fields.get("姓名") or ""),
            grade=extract_grade(score_payload),
            score=extract_score(score_payload),
            source_channel=source_channel,
            notify_grades=notify_grades,
            webhook_url=webhook_url,
            chat_id=chat_id,
            dry_run=True,
        )
        return result

    creds = load_feishu_credentials()
    api = FeishuBitableAPI(creds["app_id"], creds["app_secret"])
    app_token = resolve_app_token(api)
    if app_token != APP_TOKEN:
        result["app_token_warning"] = {"expected": APP_TOKEN, "actual": app_token}

    t01_table_id = str(table_by_name(api, app_token, T01_TABLE_NAME).get("table_id") or "").strip()
    t02_table_id = str(table_by_name(api, app_token, T02_TABLE_NAME).get("table_id") or "").strip()
    if not t01_table_id or not t02_table_id:
        raise RuntimeError("Unable to resolve T01/T02 table ids.")

    candidate_record_id = create_record(api, app_token, t01_table_id, t01_fields)
    t02_fields = build_t02_fields(
        resume_payload,
        score_payload,
        candidate_record_id=candidate_record_id,
        scorer_version=scorer_version,
    )
    analysis_record_id = create_record(api, app_token, t02_table_id, t02_fields)

    result["candidate_record_id"] = candidate_record_id
    result["analysis_record_id"] = analysis_record_id
    result["t02_fields"] = t02_fields
    result["notification"] = maybe_notify(
        api=api,
        candidate_name=str(t01_fields.get("姓名") or ""),
        grade=extract_grade(score_payload),
        score=extract_score(score_payload),
        source_channel=source_channel,
        notify_grades=notify_grades,
        webhook_url=webhook_url,
        chat_id=chat_id,
        dry_run=False,
    )
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Write PROJ-TALENT resume + score data into Feishu T01/T02.")
    parser.add_argument("--resume-json", type=Path, required=True, help="Parsed resume JSON from resume_parser.py")
    parser.add_argument("--score-json", type=Path, required=True, help="Score JSON from talent_scorer.py or fallback payload")
    parser.add_argument("--target-project", default="八万四千")
    parser.add_argument("--target-role", default="私域运营负责人")
    parser.add_argument("--source-channel", default="自动采集")
    parser.add_argument("--tag", default="社招")
    parser.add_argument("--scorer-version", default="v1-local")
    parser.add_argument("--notify-grades", default="S,A,B", help="Comma-separated grades that should trigger notification")
    parser.add_argument("--notify-webhook", default="", help="Optional Feishu bot webhook URL")
    parser.add_argument("--notify-chat-id", default="", help="Optional Feishu chat_id for internal IM notifications")
    parser.add_argument("--apply", action="store_true", help="Actually write to Feishu")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    resume_payload = load_json(args.resume_json)
    score_payload = load_json(args.score_json)
    notify_grades = {item.strip().upper() for item in args.notify_grades.split(",") if item.strip()}
    result = ingest_candidate(
        resume_payload,
        score_payload,
        target_project=args.target_project,
        target_role=args.target_role,
        source_channel=args.source_channel,
        tag=args.tag,
        scorer_version=args.scorer_version,
        notify_grades=notify_grades,
        webhook_url=args.notify_webhook.strip(),
        chat_id=args.notify_chat_id.strip(),
        dry_run=not args.apply,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
