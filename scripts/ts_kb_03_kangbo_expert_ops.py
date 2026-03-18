from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.create_kangbo_signal_tables import BRIDGE_SCRIPT, DEFAULT_ACCOUNT_ID, load_feishu_credentials
except ModuleNotFoundError:  # pragma: no cover
    from create_kangbo_signal_tables import BRIDGE_SCRIPT, DEFAULT_ACCOUNT_ID, load_feishu_credentials


REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ts-kb-03"
SEED_DIR = ARTIFACT_ROOT / "seed-payloads"
MANIFEST_FILE = ARTIFACT_ROOT / "kangbo_expert_schema_manifest.json"
TABLE_ID_MAP_FILE = ARTIFACT_ROOT / "table_ids.json"
SEED_RESULT_FILE = ARTIFACT_ROOT / "seed-result.json"
METADATA_FILE = ARTIFACT_ROOT / "metadata.json"

KANGBO_WIKI_LINK = "https://h52xu4gwob.feishu.cn/wiki/INApw2UoXiSeMTkBMVFc5daVnle?from=from_copylink"
TARGET_APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
MULTI_SELECT_FIELD = 4
DATE_FIELD = 5
URL_FIELD = 15

CAPTURE_DATE = "2026-03-17"
CAPTURE_DATE_MS = int(datetime(2026, 3, 17, tzinfo=timezone.utc).timestamp() * 1000)


def to_ms(date_text: str) -> int:
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def to_link_object(url: str) -> dict[str, str] | None:
    value = str(url or "").strip()
    if not value:
        return None
    return {"link": value, "text": value}


def ensure_artifact_root() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)


def run_bridge_sync(*, manifest_path: Path, apply: bool, account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, Any]:
    if not BRIDGE_SCRIPT.exists():
        raise RuntimeError(f"bridge script not found: {BRIDGE_SCRIPT}")
    creds = load_feishu_credentials(account_id)
    env = dict(os.environ)
    env["FEISHU_APP_ID"] = creds["app_id"]
    env["FEISHU_APP_SECRET"] = creds["app_secret"]
    command = [
        sys.executable,
        str(BRIDGE_SCRIPT),
        "sync-base-schema",
        "--link",
        KANGBO_WIKI_LINK,
        "--manifest",
        str(manifest_path),
        "--apply" if apply else "--dry-run",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    payload_text = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode != 0:
        raise RuntimeError(payload_text or f"bridge sync failed with exit code {completed.returncode}")
    return json.loads(payload_text)


def run_bridge_upsert(
    *,
    table_id: str,
    primary_field: str,
    payload_file: Path,
    apply: bool,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, Any]:
    if not BRIDGE_SCRIPT.exists():
        raise RuntimeError(f"bridge script not found: {BRIDGE_SCRIPT}")
    creds = load_feishu_credentials(account_id)
    env = dict(os.environ)
    env["FEISHU_APP_ID"] = creds["app_id"]
    env["FEISHU_APP_SECRET"] = creds["app_secret"]
    command = [
        sys.executable,
        str(BRIDGE_SCRIPT),
        "upsert-records",
        "--link",
        KANGBO_WIKI_LINK,
        "--table-id",
        table_id,
        "--primary-field",
        primary_field,
        "--payload-file",
        str(payload_file),
        "--apply" if apply else "--dry-run",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    payload_text = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode != 0:
        raise RuntimeError(payload_text or f"bridge upsert failed with exit code {completed.returncode}")
    return json.loads(payload_text)


def summarize_upsert_result(raw: dict[str, Any]) -> dict[str, Any]:
    summary = raw.get("summary") or {}
    preview = raw.get("preview") or {}
    result = raw.get("result") or {}
    if summary and not preview:
        preview = {
            "would_create": summary.get("creates"),
            "would_update": summary.get("updates"),
            "unchanged": summary.get("unchanged"),
            "errors": summary.get("errors"),
            "can_apply": summary.get("can_apply"),
        }
    if summary and not result and raw.get("mode") == "apply":
        result = {
            "created": summary.get("creates_applied", summary.get("creates")),
            "updated": summary.get("updates_applied", summary.get("updates")),
            "unchanged": summary.get("unchanged"),
            "errors": summary.get("errors"),
        }
    return {
        "mode": raw.get("mode"),
        "status": raw.get("status"),
        "row_count": raw.get("row_count"),
        "preview": preview or None,
        "result": result or None,
        "output_path": raw.get("output_path"),
        "preview_path": raw.get("preview_path"),
    }


TABLE_SPECS: list[dict[str, Any]] = [
    {
        "key": "expert_network",
        "table_name": "L2_专家智库",
        "primary_field": "expert_id",
        "views": ["全部"],
        "fields": [
            {"name": "expert_id", "type": TEXT_FIELD},
            {"name": "name", "type": TEXT_FIELD},
            {"name": "name_zh", "type": TEXT_FIELD},
            {
                "name": "tier",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": name} for name in ["T0", "T1", "T2", "T3"]]},
            },
            {
                "name": "layer",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": name}
                        for name in [
                            "宏观/货币秩序",
                            "交易/策略",
                            "行业/有色金属",
                            "行业/化工",
                            "TMT/计算机",
                            "TMT/电子半导体",
                            "TMT/通信",
                            "TMT/传媒互联网",
                            "海外机构研究",
                        ]
                    ]
                },
            },
            {"name": "domain", "type": TEXT_FIELD},
            {"name": "affiliation", "type": TEXT_FIELD},
            {
                "name": "region",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": name} for name in ["海外", "国内"]]},
            },
            {"name": "source_url", "type": URL_FIELD},
            {
                "name": "source_type",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": name}
                        for name in [
                            "付费研报",
                            "公开",
                            "卖方研报",
                            "公开+付费",
                            "公开研报+白皮书",
                            "公开+研报",
                            "公开文章+书籍",
                            "公开观点+媒体",
                            "公开季报+白皮书",
                        ]
                    ]
                },
            },
            {"name": "key_work", "type": TEXT_FIELD},
            {"name": "kangbo_relevance", "type": TEXT_FIELD},
            {
                "name": "last_tracked",
                "type": DATE_FIELD,
                "property": {"date_formatter": "yyyy-MM-dd", "auto_fill": False},
            },
            {
                "name": "tracking_frequency",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": name} for name in ["每日", "每周", "每月", "按需"]]},
            },
            {"name": "insight_count", "type": NUMBER_FIELD},
        ],
    },
    {
        "key": "expert_insights",
        "table_name": "L3_专家洞察",
        "primary_field": "insight_id",
        "views": ["全部"],
        "fields": [
            {"name": "insight_id", "type": TEXT_FIELD},
            {"name": "expert_id", "type": TEXT_FIELD},
            {
                "name": "insight_date",
                "type": DATE_FIELD,
                "property": {"date_formatter": "yyyy-MM-dd", "auto_fill": False},
            },
            {"name": "title", "type": TEXT_FIELD},
            {"name": "summary", "type": TEXT_FIELD},
            {"name": "source_url", "type": URL_FIELD},
            {
                "name": "source_type",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [{"name": name} for name in ["研报", "公众号", "视频", "演讲", "书籍", "社交媒体", "官网文章"]]
                },
            },
            {"name": "event_ref", "type": TEXT_FIELD},
            {
                "name": "kangbo_phase",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": name} for name in ["KB10", "KB11", "其他"]]},
            },
            {
                "name": "asset_class_impact",
                "type": MULTI_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": name}
                        for name in ["黄金", "原油", "铜", "美债", "A股", "港股", "美股", "加密", "汇率", "其他"]
                    ]
                },
            },
            {
                "name": "sentiment",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": name} for name in ["极度看多", "看多", "中性", "看空", "极度看空"]]},
            },
            {"name": "quality_score", "type": NUMBER_FIELD},
            {
                "name": "created_by",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": name} for name in ["Human", "Claude", "Codex"]]},
            },
        ],
    },
]


L2_EXPERT_ROWS: list[dict[str, Any]] = [
    {
        "expert_id": "EXP-MACRO-001",
        "name": "Zoltan Pozsar",
        "name_zh": "佐尔坦·波扎尔",
        "tier": "T0",
        "layer": "宏观/货币秩序",
        "domain": "全球流动性·影子银行·布雷顿森林III",
        "affiliation": "Ex Uno Plures",
        "region": "海外",
        "source_url": "https://www.exunoplures.hu/",
        "source_type": "付费研报",
        "key_work": "Bretton Woods III 系列; War and Interest Rates; Mar-a-Lago Accord",
        "kangbo_relevance": "货币体系重构·outside money vs inside money",
        "last_tracked": "",
        "tracking_frequency": "每周",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-MACRO-002",
        "name": "Ray Dalio",
        "name_zh": "瑞·达里奥",
        "tier": "T0",
        "layer": "宏观/货币秩序",
        "domain": "债务周期·大国兴衰·全天候策略",
        "affiliation": "Bridgewater Associates",
        "region": "海外",
        "source_url": "https://www.principles.com/",
        "source_type": "公开文章+书籍",
        "key_work": "Principles for Dealing with the Changing World Order; Big Debt Crises",
        "kangbo_relevance": "债务超级周期·帝国兴衰",
        "last_tracked": "",
        "tracking_frequency": "每周",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-MACRO-003",
        "name": "翟东升",
        "name_zh": "翟东升",
        "tier": "T0",
        "layer": "宏观/货币秩序",
        "domain": "国际政治经济学·货币权力·金融秩序",
        "affiliation": "中国人民大学",
        "region": "国内",
        "source_url": "",
        "source_type": "公开",
        "key_work": "《货币权力》《大国博弈》系列",
        "kangbo_relevance": "美元霸权周期·中美金融脱钩",
        "last_tracked": "",
        "tracking_frequency": "每周",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-MACRO-004",
        "name": "卢麒元",
        "name_zh": "卢麒元",
        "tier": "T0",
        "layer": "宏观/货币秩序",
        "domain": "财税体制·资本外流·贫富分化",
        "affiliation": "独立学者",
        "region": "国内",
        "source_url": "",
        "source_type": "公开",
        "key_work": "税制改革系列·资本项目分析",
        "kangbo_relevance": "国内分配周期·财政货币协调",
        "last_tracked": "",
        "tracking_frequency": "每周",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TRADE-001",
        "name": "刘刚",
        "name_zh": "",
        "tier": "T1",
        "layer": "交易/策略",
        "domain": "全球资产配置·中国资产策略",
        "affiliation": "中金公司",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "海外配置月报·港股策略·全球资金流向",
        "kangbo_relevance": "全球资金流动·risk-on/risk-off",
        "last_tracked": "",
        "tracking_frequency": "每周",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TRADE-002",
        "name": "刘煜辉",
        "name_zh": "",
        "tier": "T1",
        "layer": "交易/策略",
        "domain": "宏观策略·货币政策·资产定价",
        "affiliation": "中国社科院/天风证券",
        "region": "国内",
        "source_url": "",
        "source_type": "公开+研报",
        "key_work": "流动性陷阱分析·A股策略框架",
        "kangbo_relevance": "中国宏观周期·政策脉冲",
        "last_tracked": "",
        "tracking_frequency": "每周",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TRADE-003",
        "name": "洪灏",
        "name_zh": "",
        "tier": "T1",
        "layer": "交易/策略",
        "domain": "全球宏观·中国市场策略·周期理论",
        "affiliation": "思睿集团",
        "region": "国内",
        "source_url": "",
        "source_type": "公开+付费",
        "key_work": "预测与现实系列·中国市场周期",
        "kangbo_relevance": "中国市场周期·全球风险情绪",
        "last_tracked": "",
        "tracking_frequency": "每周",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TRADE-004",
        "name": "秦小明",
        "name_zh": "",
        "tier": "T1",
        "layer": "交易/策略",
        "domain": "宏观逻辑·交易思维·金融教育",
        "affiliation": "独立",
        "region": "国内",
        "source_url": "",
        "source_type": "公开+付费",
        "key_work": "宏观逻辑链条系列·交易框架",
        "kangbo_relevance": "宏观传导链·交易节奏",
        "last_tracked": "",
        "tracking_frequency": "每月",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-FUND-001",
        "name": "AQR Capital",
        "name_zh": "AQR资本",
        "tier": "T1",
        "layer": "海外机构研究",
        "domain": "量化因子·资产配置·替代投资",
        "affiliation": "AQR Capital Management",
        "region": "海外",
        "source_url": "https://www.aqr.com/Insights/Research",
        "source_type": "公开研报+白皮书",
        "key_work": "Cliff Asness系列; Alternative Thinking; Factor Investing",
        "kangbo_relevance": "量化周期·估值因子",
        "last_tracked": "",
        "tracking_frequency": "每月",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-FUND-002",
        "name": "Citadel Securities",
        "name_zh": "城堡证券",
        "tier": "T1",
        "layer": "海外机构研究",
        "domain": "做市·流动性·市场微观结构",
        "affiliation": "Citadel/Citadel Securities",
        "region": "海外",
        "source_url": "https://www.citadelsecurities.com",
        "source_type": "公开观点+媒体",
        "key_work": "Ken Griffin市场观点; 流动性机制研究",
        "kangbo_relevance": "流动性周期·市场结构",
        "last_tracked": "",
        "tracking_frequency": "每月",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-FUND-003",
        "name": "GMO",
        "name_zh": "GMO",
        "tier": "T1",
        "layer": "海外机构研究",
        "domain": "价值投资·长期回报预测·泡沫识别",
        "affiliation": "Grantham, Mayo & van Otterloo",
        "region": "海外",
        "source_url": "https://www.gmo.com/insights",
        "source_type": "公开季报+白皮书",
        "key_work": "Jeremy Grantham泡沫系列; 7-Year Asset Class Forecast",
        "kangbo_relevance": "超级泡沫·估值均值回归",
        "last_tracked": "",
        "tracking_frequency": "每月",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-FUND-004",
        "name": "Man Institute",
        "name_zh": "Man集团研究院",
        "tier": "T1",
        "layer": "海外机构研究",
        "domain": "系统性策略·另类数据·趋势跟踪",
        "affiliation": "Man Group (AHL/GLG)",
        "region": "海外",
        "source_url": "https://www.man.com/maninstitute",
        "source_type": "公开研报+白皮书",
        "key_work": "Trend Following研究; 另类数据应用; 风险平价",
        "kangbo_relevance": "趋势周期·CTA策略",
        "last_tracked": "",
        "tracking_frequency": "每月",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-METAL-001",
        "name": "王鹤涛",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/有色金属",
        "domain": "有色金属·铜铝·新能源金属",
        "affiliation": "长江证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "铜价框架·新能源金属供需",
        "kangbo_relevance": "资源品超级周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-METAL-002",
        "name": "巨国贤",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/有色金属",
        "domain": "有色金属·贵金属·工业金属",
        "affiliation": "广发证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "黄金定价框架·铜铝供需",
        "kangbo_relevance": "资源品超级周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-METAL-003",
        "name": "邱祖学",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/有色金属",
        "domain": "有色金属·锂钴镍·资源品",
        "affiliation": "兴业证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "锂电金属产业链",
        "kangbo_relevance": "新能源金属周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-METAL-004",
        "name": "谢鸿鹤",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/有色金属",
        "domain": "有色金属·铜金·资源",
        "affiliation": "中泰证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "铜金比分析·有色周期框架",
        "kangbo_relevance": "资源品超级周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-CHEM-001",
        "name": "马太",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/化工",
        "domain": "基础化工·农化·新材料",
        "affiliation": "长江证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "化工景气周期·新材料",
        "kangbo_relevance": "制造业周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-CHEM-002",
        "name": "宋涛",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/化工",
        "domain": "化工·能源化工·精细化工",
        "affiliation": "申万宏源",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "能源化工产业链",
        "kangbo_relevance": "能源转型周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-CHEM-003",
        "name": "吴鑫然",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/化工",
        "domain": "化工·氟化工·新材料",
        "affiliation": "广发证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "新材料产业链分析",
        "kangbo_relevance": "新材料周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-CHEM-004",
        "name": "唐婕",
        "name_zh": "",
        "tier": "T2",
        "layer": "行业/化工",
        "domain": "化工·农药·化肥",
        "affiliation": "天风证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "农化产业链",
        "kangbo_relevance": "农业周期",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-CS-001",
        "name": "刘高畅",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/计算机",
        "domain": "计算机·AI应用·信创",
        "affiliation": "国盛证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "AI应用落地·信创产业链",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-CS-002",
        "name": "吕伟",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/计算机",
        "domain": "计算机·企业软件·云计算",
        "affiliation": "民生证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "SaaS·企业数字化",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-CS-003",
        "name": "刘雪峰",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/计算机",
        "domain": "计算机·AI·数据要素",
        "affiliation": "广发证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "AI产业链·数据要素",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-CS-004",
        "name": "缪欣君",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/计算机",
        "domain": "计算机·网络安全·AI",
        "affiliation": "天风证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "网安·AI应用",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-EE-001",
        "name": "王芳",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/电子半导体",
        "domain": "半导体·消费电子·功率器件",
        "affiliation": "中泰证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "半导体周期·国产替代",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-EE-002",
        "name": "刘双峰",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/电子半导体",
        "domain": "半导体·先进封装·设备",
        "affiliation": "中信建投",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "先进制程·设备国产化",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-EE-003",
        "name": "姚丹丹",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/电子半导体",
        "domain": "半导体·面板·LED",
        "affiliation": "国海证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "面板周期·MiniLED",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-COM-001",
        "name": "蒋颖",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/通信",
        "domain": "通信·算力·光模块",
        "affiliation": "开源证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "算力基建·光模块",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-COM-002",
        "name": "唐海清",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/通信",
        "domain": "通信·5G·卫星",
        "affiliation": "天风证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "5G应用·卫星通信",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-COM-003",
        "name": "朱型檩",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/通信",
        "domain": "通信·光通信·IDC",
        "affiliation": "中信建投",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "光通信产业链·IDC",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-MED-001",
        "name": "刘欣",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/传媒互联网",
        "domain": "传媒·游戏·AI应用",
        "affiliation": "天风证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "AI+传媒·游戏产业",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-MED-002",
        "name": "杨艾莉",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/传媒互联网",
        "domain": "传媒·互联网·教育",
        "affiliation": "中信建投",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "互联网平台·AI应用",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
    {
        "expert_id": "EXP-TMT-MED-003",
        "name": "吴劲草",
        "name_zh": "",
        "tier": "T2",
        "layer": "TMT/传媒互联网",
        "domain": "互联网·电商·社交",
        "affiliation": "东吴证券",
        "region": "国内",
        "source_url": "",
        "source_type": "卖方研报",
        "key_work": "电商格局·社交平台",
        "kangbo_relevance": "第六次康波技术",
        "last_tracked": "",
        "tracking_frequency": "按需",
        "insight_count": 0,
    },
]


T0_L3_ROWS: list[dict[str, Any]] = [
    {"insight_id": "INS-POZSAR-001", "expert_id": "EXP-MACRO-001", "insight_date": to_ms("2022-03-07"), "title": "Bretton Woods III 诞生", "summary": "冻结俄罗斯央行储备标志BW II终结，大宗商品取代国债成为储备锚，outside money崛起", "source_url": "https://www.exunoplures.hu/", "source_type": "研报", "event_ref": "KBS-202202-001", "kangbo_phase": "KB10", "asset_class_impact": ["黄金", "原油", "铜"], "sentiment": "看多", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-POZSAR-002", "expert_id": "EXP-MACRO-001", "insight_date": to_ms("2022-08-01"), "title": "战争经济下通胀不可控", "summary": "低通胀三根柱子(廉价劳动力/中国商品/俄罗斯天然气)全断，通胀是供给侧的，央行无法控制", "source_url": "https://www.exunoplures.hu/", "source_type": "研报", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["美债"], "sentiment": "看空", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-POZSAR-003", "expert_id": "EXP-MACRO-001", "insight_date": to_ms("2022-08-24"), "title": "信任崩塌→再工业化", "summary": "Chimerica离婚+Eurussia离婚→西方必须再工业化→财政驱动通胀是结构性的", "source_url": "https://www.exunoplures.hu/", "source_type": "研报", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["铜", "原油"], "sentiment": "看多", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-POZSAR-004", "expert_id": "EXP-MACRO-001", "insight_date": to_ms("2025-03-06"), "title": "Mar-a-Lago Accord", "summary": "特朗普可能推动新国际货币协议，通过关税+美元贬值+盟友分担防务来重塑全球经济秩序", "source_url": "https://www.exunoplures.hu/", "source_type": "官网文章", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["黄金", "汇率"], "sentiment": "看空", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-POZSAR-005", "expert_id": "EXP-MACRO-001", "insight_date": to_ms("2023-06-30"), "title": "Ex Uno Plures创立", "summary": "两条产品线：Money Banks & Bases(美元管道日常运行) + Money & World Order(BW III演进追踪)", "source_url": "https://www.exunoplures.hu/", "source_type": "官网文章", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["美债", "黄金"], "sentiment": "中性", "quality_score": 4, "created_by": "Claude"},
    {"insight_id": "INS-DALIO-001", "expert_id": "EXP-MACRO-002", "insight_date": to_ms("2026-03-14"), "title": "Big Cycle最危险阶段", "summary": "我们正处于Stage 5→6过渡期，类似1945年前而非战后。500年历史研究表明所有秩序都会崩塌重建", "source_url": "https://www.principles.com/", "source_type": "官网文章", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["黄金", "美股"], "sentiment": "极度看空", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-DALIO-002", "expert_id": "EXP-MACRO-002", "insight_date": to_ms("2026-01-21"), "title": "货币秩序正在崩溃", "summary": "Davos讲话：面临可怕选择——印钞还是让债务危机爆发？美国$38万亿国债是核心矛盾", "source_url": "https://www.principles.com/", "source_type": "官网文章", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["美债", "黄金"], "sentiment": "极度看空", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-DALIO-003", "expert_id": "EXP-MACRO-002", "insight_date": to_ms("2026-02-04"), "title": "资本战争临近", "summary": "Dubai讲话：我们处于资本战争边缘，国家通过控制资金流向互相攻击。类比1941年美国冻结日本资产", "source_url": "https://www.principles.com/", "source_type": "演讲", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["黄金", "美股", "美债"], "sentiment": "极度看空", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-DALIO-004", "expert_id": "EXP-MACRO-002", "insight_date": to_ms("2026-02-17"), "title": "世界秩序已正式崩塌", "summary": "X长帖：1945年后规则世界已死。贸易战→技术战→资本战→可能军事冲突的升级路径", "source_url": "https://www.principles.com/", "source_type": "社交媒体", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["黄金"], "sentiment": "极度看空", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-DALIO-005", "expert_id": "EXP-MACRO-002", "insight_date": to_ms("2025-10-01"), "title": "黄金配置10-15%", "summary": "黄金是资本战争中最安全的资产。法币贬值下名义回报有误导性，要看实际购买力", "source_url": "https://www.principles.com/", "source_type": "官网文章", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["黄金"], "sentiment": "看多", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-ZHAI-001", "expert_id": "EXP-MACRO-003", "insight_date": to_ms("2025-08-08"), "title": "美债是伪问题", "summary": "只要美元霸权不倒，美国真实国债为零。本币计价国债实质是对全球储蓄者征税", "source_url": "", "source_type": "演讲", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["美债"], "sentiment": "中性", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-ZHAI-002", "expert_id": "EXP-MACRO-003", "insight_date": to_ms("2019-05-01"), "title": "关税战的财政动机", "summary": "特朗普打关税不是因为贸易逆差而是联邦财政缺钱。2025年再次验证", "source_url": "", "source_type": "演讲", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["汇率"], "sentiment": "中性", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-ZHAI-003", "expert_id": "EXP-MACRO-003", "insight_date": to_ms("2026-01-28"), "title": "面对没有美国的世界", "summary": "美国战略收缩是趋势性的。特朗普2025下半年态度软化，中美进入讨价还价期", "source_url": "", "source_type": "演讲", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["A股", "港股"], "sentiment": "看多", "quality_score": 4, "created_by": "Claude"},
    {"insight_id": "INS-ZHAI-004", "expert_id": "EXP-MACRO-003", "insight_date": to_ms("2025-08-08"), "title": "西海岸战胜东海岸", "summary": "硅谷技术资本正在战胜华尔街金融资本，可能开启新时代", "source_url": "", "source_type": "演讲", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["美股"], "sentiment": "中性", "quality_score": 4, "created_by": "Claude"},
    {"insight_id": "INS-ZHAI-005", "expert_id": "EXP-MACRO-003", "insight_date": to_ms("2025-07-01"), "title": "《制裁与经济战》出版", "summary": "系统性研究大国经济战，制裁/关税/技术封锁/金融脱钩是大国博弈主要形式", "source_url": "", "source_type": "书籍", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["其他"], "sentiment": "中性", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-LU-001", "expert_id": "EXP-MACRO-004", "insight_date": to_ms("2026-03-01"), "title": "战争通胀与萧条并存", "summary": "最新判断：战争推高通胀但萧条同时来临，滞胀格局", "source_url": "", "source_type": "视频", "event_ref": "KBS-202602-001", "kangbo_phase": "KB10", "asset_class_impact": ["黄金", "原油"], "sentiment": "看空", "quality_score": 5, "created_by": "Claude"},
    {"insight_id": "INS-LU-002", "expert_id": "EXP-MACRO-004", "insight_date": to_ms("2026-01-04"), "title": "石油致命一跌", "summary": "经济危机临近，石油将迎致命一跌，贵金属需等石油方向明确后布局", "source_url": "", "source_type": "视频", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["原油", "黄金"], "sentiment": "看空", "quality_score": 4, "created_by": "Claude"},
    {"insight_id": "INS-LU-003", "expert_id": "EXP-MACRO-004", "insight_date": to_ms("2025-11-30"), "title": "现金为王+AI泡沫警告", "summary": "价值回归阶段，对AI泡沫和贵金属发出谨慎提醒", "source_url": "", "source_type": "视频", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["美股", "黄金"], "sentiment": "看空", "quality_score": 4, "created_by": "Claude"},
    {"insight_id": "INS-LU-004", "expert_id": "EXP-MACRO-004", "insight_date": to_ms("2025-12-14"), "title": "摩根出走信号", "summary": "摩根大通动向意味深长，头部金融资本紧锣密鼓，全球资本流动方向可能变化", "source_url": "", "source_type": "视频", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["美股", "其他"], "sentiment": "看空", "quality_score": 4, "created_by": "Claude"},
    {"insight_id": "INS-LU-005", "expert_id": "EXP-MACRO-004", "insight_date": to_ms("2025-07-27"), "title": "直接税是文明标配", "summary": "中国必须从间接税转向直接税，这是解决资本外逃和贫富分化的根本制度改革", "source_url": "", "source_type": "社交媒体", "event_ref": "", "kangbo_phase": "KB10", "asset_class_impact": ["A股"], "sentiment": "中性", "quality_score": 4, "created_by": "Claude"},
]


GENERIC_SOURCE_URLS = {
    "EXP-TRADE-001": "",
    "EXP-TRADE-002": "",
    "EXP-TRADE-003": "",
    "EXP-TRADE-004": "",
    "EXP-FUND-001": "https://www.aqr.com/Insights/Research",
    "EXP-FUND-002": "https://www.citadelsecurities.com/",
    "EXP-FUND-003": "https://www.gmo.com/insights",
    "EXP-FUND-004": "https://www.man.com/maninstitute",
}

T1_RAW_ROWS: list[dict[str, Any]] = [
    {"insight_id": "INS-LIUG-001", "expert_id": "EXP-TRADE-001", "title": "2026均衡配置", "summary": "告别单边押注，AI硬件+高股息对冲。跟随信用扩张方向", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["港股", "美股"]},
    {"insight_id": "INS-LIUG-002", "expert_id": "EXP-TRADE-001", "title": "恒指28-29K", "summary": "基准情形港股目标28000-29000，南向资金分化：保险稳配、散户可能回流A股", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["港股", "A股"]},
    {"insight_id": "INS-LIUG-003", "expert_id": "EXP-TRADE-001", "title": "AI非泡沫", "summary": "判断AI已到泡沫程度为时尚早，硬件端确定，应用端待兑现", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["美股", "A股"]},
    {"insight_id": "INS-LIUY-001", "expert_id": "EXP-TRADE-002", "title": "哑铃策略2026", "summary": "高股息压舱石+押国运成长，不变应万变", "sentiment": "看多", "source_type": "演讲", "asset_class_impact": ["A股", "黄金"]},
    {"insight_id": "INS-LIUY-002", "expert_id": "EXP-TRADE-002", "title": "AI端侧迁移", "summary": "从算力供应端向AI端侧迁移，中国制造业生态主导AI下半场闭环", "sentiment": "看多", "source_type": "演讲", "asset_class_impact": ["A股"]},
    {"insight_id": "INS-LIUY-003", "expert_id": "EXP-TRADE-002", "title": "美股All in AI拥挤", "summary": "全球资本All in AI布局极度拥挤，负反馈一旦触发将演变为流动性冲击", "sentiment": "看空", "source_type": "演讲", "asset_class_impact": ["美股"]},
    {"insight_id": "INS-HONG-001", "expert_id": "EXP-TRADE-003", "title": "850天周期底部已过", "summary": "中国市场2024年底确认周期底部，2025年回升验证判断", "sentiment": "看多", "source_type": "公众号", "asset_class_impact": ["A股", "港股"]},
    {"insight_id": "INS-HONG-002", "expert_id": "EXP-TRADE-003", "title": "美元流动性决定港股", "summary": "全球资金流动比国内政策更重要，美元流动性是理解港股的关键", "sentiment": "中性", "source_type": "公众号", "asset_class_impact": ["港股", "汇率"]},
    {"insight_id": "INS-HONG-003", "expert_id": "EXP-TRADE-003", "title": "AI泡沫谨慎", "summary": "技术革命初期伴随过度投资，真正回报在泡沫破裂后的应用普及阶段", "sentiment": "看空", "source_type": "公众号", "asset_class_impact": ["美股"]},
    {"insight_id": "INS-QIN-001", "expert_id": "EXP-TRADE-004", "title": "宏观是条件反射", "summary": "不预测，建立\"如果A则B\"框架。流动性是所有资产定价的底层变量", "sentiment": "中性", "source_type": "公众号", "asset_class_impact": ["其他"]},
    {"insight_id": "INS-QIN-002", "expert_id": "EXP-TRADE-004", "title": "中国核心矛盾", "summary": "财政想扩张vs信用传导不畅(地产/地方政府)，这是理解A股的关键", "sentiment": "中性", "source_type": "公众号", "asset_class_impact": ["A股"]},
    {"insight_id": "INS-QIN-003", "expert_id": "EXP-TRADE-004", "title": "趋势vs震荡", "summary": "分辨趋势和震荡：趋势中顺势重仓，震荡中轻仓等待", "sentiment": "中性", "source_type": "公众号", "asset_class_impact": ["其他"]},
    {"insight_id": "INS-AQR-001", "expert_id": "EXP-FUND-001", "title": "2025资产假设", "summary": "新兴市场预期回报最高，美国大盘股预期偏低。成长溢价过高", "sentiment": "中性", "source_type": "官网文章", "asset_class_impact": ["美股", "A股"]},
    {"insight_id": "INS-AQR-002", "expert_id": "EXP-FUND-001", "title": "逢低买入失败", "summary": "Buy the Dip一贯跑输买入持有，趋势跟踪比抄底更有效", "sentiment": "中性", "source_type": "官网文章", "asset_class_impact": ["美股"]},
    {"insight_id": "INS-GMO-001", "expert_id": "EXP-FUND-003", "title": "7年预测202602", "summary": "新兴市场股票预期回报最高，美国大盘成长股预期回报为负", "sentiment": "看空", "source_type": "官网文章", "asset_class_impact": ["美股"]},
    {"insight_id": "INS-GMO-002", "expert_id": "EXP-FUND-003", "title": "AI泡沫Installation期", "summary": "AI是真实技术革命但当前处于安装期泡沫。历史每次都经历泡沫→破裂→部署期获利", "sentiment": "看空", "source_type": "官网文章", "asset_class_impact": ["美股"]},
    {"insight_id": "INS-MAN-001", "expert_id": "EXP-FUND-004", "title": "趋势跟踪回撤正常", "summary": "2025年CTA回撤是正常的，历史数据显示6-12月后通常恢复。不要因短期放弃", "sentiment": "中性", "source_type": "官网文章", "asset_class_impact": ["其他"]},
    {"insight_id": "INS-MAN-002", "expert_id": "EXP-FUND-004", "title": "分散度利好趋势", "summary": "Liberation Day后市场分散度上升，对趋势跟踪有利。交易更多市场提升信息比率", "sentiment": "看多", "source_type": "官网文章", "asset_class_impact": ["其他"]},
    {"insight_id": "INS-CIT-001", "expert_id": "EXP-FUND-002", "title": "流动性温度计", "summary": "Citadel做市价差是市场微观结构的压力指标，价差扩大=流动性紧张信号", "sentiment": "中性", "source_type": "官网文章", "asset_class_impact": ["美股", "美债"]},
    {"insight_id": "INS-CIT-002", "expert_id": "EXP-FUND-002", "title": "全球做市格局", "summary": "作为全球最大做市商之一，其行为模式反映机构资金的风险偏好变化", "sentiment": "中性", "source_type": "官网文章", "asset_class_impact": ["美股"]},
]


T2_PROXY_ROWS: list[dict[str, Any]] = [
    {"insight_id": "INS-METAL-SUM", "expert_id": "EXP-METAL-001", "title": "有色2026继续看多", "summary": "2025年涨94.73%全行业第一，2026年从周期复苏转向战略价值重估。铜缺口84.8万吨", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["铜", "黄金"]},
    {"insight_id": "INS-METAL-LOGIC", "expert_id": "EXP-METAL-002", "title": "AI尽头是大宗商品", "summary": "AI→电力→新能源→关键矿产。有色金属从周期品变为\"新基建\"", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["铜", "其他"]},
    {"insight_id": "INS-CHEM-SUM", "expert_id": "EXP-CHEM-003", "title": "化工新材料国产替代", "summary": "中美脱钩倒逼氟化工/电子化学品/半导体特气国产替代", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["A股", "其他"]},
    {"insight_id": "INS-CHEM-AGRI", "expert_id": "EXP-CHEM-004", "title": "农化景气持续", "summary": "地缘冲突→粮食安全→农药化肥需求刚性", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["A股", "其他"]},
    {"insight_id": "INS-TMT-AI", "expert_id": "EXP-TMT-CS-001", "title": "AI从硬件到应用", "summary": "2025年硬件领涨，2026年核心问题是应用落地能否兑现", "sentiment": "中性", "source_type": "研报", "asset_class_impact": ["A股", "美股"]},
    {"insight_id": "INS-TMT-SEMI", "expert_id": "EXP-TMT-EE-002", "title": "半导体设备国产化", "summary": "美国BIS管制→中国被迫创新→DeepSeek验证路径→国产替代加速", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["A股", "美股"]},
    {"insight_id": "INS-TMT-COM", "expert_id": "EXP-TMT-COM-001", "title": "算力基建持续", "summary": "光模块/交换机/IDC需求受AI数据中心拉动，5-7万亿美元投资规模", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["A股"]},
    {"insight_id": "INS-TMT-MED", "expert_id": "EXP-TMT-MED-001", "title": "AIGC应用变现", "summary": "AI赋能游戏/广告/教育是最先变现的场景", "sentiment": "看多", "source_type": "研报", "asset_class_impact": ["A股", "港股"]},
]


def normalize_l3_row(row: dict[str, Any], *, quality_score: int, capture_date: int = CAPTURE_DATE_MS) -> dict[str, Any]:
    payload = deepcopy(row)
    if not payload.get("insight_date"):
        payload["insight_date"] = capture_date
    payload["source_url"] = to_link_object(str(payload.get("source_url") or GENERIC_SOURCE_URLS.get(str(payload["expert_id"]), "")))
    payload.setdefault("event_ref", "")
    payload.setdefault("kangbo_phase", "KB10")
    payload.setdefault("created_by", "Claude")
    payload.setdefault("quality_score", quality_score)
    if not payload.get("source_url"):
        payload.pop("source_url", None)
    return payload


def build_l3_rows() -> list[dict[str, Any]]:
    rows = [normalize_l3_row(row, quality_score=int(row.get("quality_score") or 4)) for row in T0_L3_ROWS]
    rows.extend(normalize_l3_row(row, quality_score=4) for row in T1_RAW_ROWS)
    rows.extend(normalize_l3_row(row, quality_score=3) for row in T2_PROXY_ROWS)
    return rows


def expert_source_url_map() -> dict[str, str]:
    result = {row["expert_id"]: row.get("source_url", "") for row in L2_EXPERT_ROWS}
    result.update(GENERIC_SOURCE_URLS)
    return result


def build_l2_rows() -> list[dict[str, Any]]:
    rows = deepcopy(L2_EXPERT_ROWS)
    counts: dict[str, int] = {}
    for row in build_l3_rows():
        expert_id = str(row["expert_id"])
        counts[expert_id] = counts.get(expert_id, 0) + 1
    for row in rows:
        row["insight_count"] = counts.get(str(row["expert_id"]), 0)
        row["source_url"] = to_link_object(str(row.get("source_url") or ""))
        if not row.get("source_url"):
            row.pop("source_url", None)
        if not row.get("last_tracked"):
            row.pop("last_tracked", None)
    return rows


def seed_rows(table_key: str) -> list[dict[str, Any]]:
    if table_key == "expert_network":
        return build_l2_rows()
    if table_key == "expert_insights":
        return build_l3_rows()
    raise KeyError(table_key)


def schema_manifest() -> dict[str, Any]:
    return {
        "base_name": "资产配置-300年康波周期智库",
        "tables": [
            {
                "table_name": table["table_name"],
                "primary_field": table["primary_field"],
                "fields": deepcopy(table["fields"]),
                "views": deepcopy(table["views"]),
            }
            for table in TABLE_SPECS
        ],
    }


def expected_counts() -> dict[str, int]:
    return {table["key"]: len(seed_rows(table["key"])) for table in TABLE_SPECS}


def write_manifest_json(path: Path = MANIFEST_FILE) -> Path:
    ensure_artifact_root()
    path.write_text(json.dumps(schema_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_seed_payloads(output_dir: Path = SEED_DIR) -> dict[str, Path]:
    ensure_artifact_root()
    result: dict[str, Path] = {}
    for table in TABLE_SPECS:
        path = output_dir / f"{table['key']}.json"
        path.write_text(json.dumps(seed_rows(table["key"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result[table["key"]] = path
    return result


def save_table_ids(table_ids: dict[str, str], path: Path = TABLE_ID_MAP_FILE) -> Path:
    ensure_artifact_root()
    path.write_text(json.dumps(table_ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_table_ids(path: Path = TABLE_ID_MAP_FILE) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_metadata(path: Path = METADATA_FILE) -> Path:
    ensure_artifact_root()
    payload = {
        "task_id": "TS-KB-03",
        "wiki_link": KANGBO_WIKI_LINK,
        "app_token": TARGET_APP_TOKEN,
        "capture_date": CAPTURE_DATE,
        "declared_l2_count_in_spec_prose": 32,
        "explicit_l2_count_from_rows": len(L2_EXPERT_ROWS),
        "l3_seed_count": len(build_l3_rows()),
        "notes": [
            "L2 prose count conflicts with explicit row count; execution keeps all enumerated rows.",
            "T2 board consensus seeds are mapped to representative expert_id proxies.",
            "T1/T2 seed dates default to archive capture date when the source corpus does not prove one exact publication date.",
        ],
        "counts": expected_counts(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def seed_payload_paths() -> dict[str, Path]:
    return {table["key"]: SEED_DIR / f"{table['key']}.json" for table in TABLE_SPECS}


def extract_table_ids(result: dict[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    tables = result.get("tables") or []
    for table in TABLE_SPECS:
        match = next((item for item in tables if item.get("table_name") == table["table_name"]), None)
        if not match:
            raise RuntimeError(f"table {table['table_name']} missing from bridge result")
        table_id = str(match.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"table {table['table_name']} did not return table_id")
        ids[table["key"]] = table_id
    return ids


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TS-KB-03 Kangbo expert registry and insight operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Write schema manifest, seed payloads, and metadata.")
    prepare.set_defaults(command="prepare")

    sync_schema = subparsers.add_parser("sync-schema", help="Sync L2/L3 schema to the Kangbo base via bridge.")
    schema_mode = sync_schema.add_mutually_exclusive_group(required=True)
    schema_mode.add_argument("--dry-run", action="store_true")
    schema_mode.add_argument("--apply", action="store_true")
    sync_schema.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    sync_schema.set_defaults(command="sync-schema")

    seed = subparsers.add_parser("seed-data", help="Upsert L2/L3 seed rows via bridge.")
    seed_mode = seed.add_mutually_exclusive_group(required=True)
    seed_mode.add_argument("--dry-run", action="store_true")
    seed_mode.add_argument("--apply", action="store_true")
    seed.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    seed.set_defaults(command="seed-data")
    return parser.parse_args(argv)


def command_prepare() -> int:
    manifest = write_manifest_json()
    payloads = write_seed_payloads()
    metadata = write_metadata()
    print(
        json.dumps(
            {
                "status": "prepared",
                "manifest_path": str(manifest),
                "payloads": {key: str(path) for key, path in payloads.items()},
                "metadata_path": str(metadata),
                "counts": expected_counts(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_sync_schema(*, apply_changes: bool, account_id: str) -> int:
    manifest_path = write_manifest_json()
    result = run_bridge_sync(manifest_path=manifest_path, apply=apply_changes, account_id=account_id)
    output = {
        "mode": "apply" if apply_changes else "dry-run",
        "status": result.get("status"),
        "tables": result.get("tables") or [],
        "output_path": result.get("output_path"),
    }
    if apply_changes:
        table_ids = extract_table_ids(result)
        save_table_ids(table_ids)
        output["table_ids"] = table_ids
        output["table_id_file"] = str(TABLE_ID_MAP_FILE)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def command_seed_data(*, apply_changes: bool, account_id: str) -> int:
    write_seed_payloads()
    write_metadata()
    table_ids = load_table_ids()
    payload_paths = seed_payload_paths()
    results: list[dict[str, Any]] = []
    for table in TABLE_SPECS:
        raw = run_bridge_upsert(
            table_id=table_ids[table["key"]],
            primary_field=table["primary_field"],
            payload_file=payload_paths[table["key"]],
            apply=apply_changes,
            account_id=account_id,
        )
        summary = summarize_upsert_result(raw)
        results.append(
            {
                "table_key": table["key"],
                "table_name": table["table_name"],
                "table_id": table_ids[table["key"]],
                "primary_field": table["primary_field"],
                "expected_rows": len(seed_rows(table["key"])),
                **summary,
            }
        )
    payload = {"mode": "apply" if apply_changes else "dry-run", "results": results}
    SEED_RESULT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "prepare":
        return command_prepare()
    if args.command == "sync-schema":
        return command_sync_schema(apply_changes=bool(args.apply), account_id=args.account_id)
    if args.command == "seed-data":
        return command_seed_data(apply_changes=bool(args.apply), account_id=args.account_id)
    raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
