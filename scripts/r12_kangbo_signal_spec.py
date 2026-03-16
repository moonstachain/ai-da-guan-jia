from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


TARGET_APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
CONTROL_APP_TOKEN = "PHp2wURl2i6SyBkDtmGcuaEenag"
NEW_BASE_LINK = "https://h52xu4gwob.feishu.cn/wiki/INApw2UoXiSeMTkBMVFc5daVnle?from=from_copylink"
OLD_BASE_LINK = "https://h52xu4gwob.feishu.cn/wiki/Kd6FwZvHOiE2D3kSy33c2oQZnad?from=from_copylink"

ARTIFACT_ROOT = Path("artifacts") / "r12-kangbo-signal"
MANIFEST_FILE = ARTIFACT_ROOT / "kangbo_signal_schema_manifest.json"
SEED_DIR = ARTIFACT_ROOT / "seed-payloads"
TABLE_ID_MAP_FILE = ARTIFACT_ROOT / "table_ids.json"
SEED_RESULT_FILE = ARTIFACT_ROOT / "seed-result.json"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5
URL_FIELD = 15


TABLE_SPECS: list[dict[str, Any]] = [
    {
        "key": "event_signals",
        "table_name": "L1_康波事件信号",
        "primary_field": "event_id",
        "fields": [
            {"name": "event_id", "type": TEXT_FIELD},
            {"name": "event_date", "type": DATE_FIELD},
            {"name": "event_name", "type": TEXT_FIELD},
            {
                "name": "event_category",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": "战争/地缘"},
                        {"name": "货币/金融"},
                        {"name": "技术/产业"},
                        {"name": "制度/政策"},
                        {"name": "社会/人口"},
                    ]
                },
            },
            {
                "name": "kangbo_phase",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": f"KB{index:02d}"} for index in range(1, 11)]},
            },
            {"name": "event_summary", "type": TEXT_FIELD},
            {"name": "causal_chain", "type": TEXT_FIELD},
            {
                "name": "narrative_type",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": "恐惧主导"},
                        {"name": "贪婪主导"},
                        {"name": "政策驱动"},
                        {"name": "叙事真空"},
                        {"name": "混合"},
                    ]
                },
            },
            {"name": "source_article", "type": TEXT_FIELD},
            {"name": "source_url", "type": URL_FIELD},
            {
                "name": "impact_direction",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": "供给侧冲击"},
                        {"name": "需求侧冲击"},
                        {"name": "流动性冲击"},
                        {"name": "制度冲击"},
                        {"name": "技术冲击"},
                        {"name": "复合冲击"},
                    ]
                },
            },
            {"name": "severity", "type": NUMBER_FIELD},
            {"name": "scenario_shift", "type": TEXT_FIELD},
        ],
        "views": ["全部"],
    },
    {
        "key": "historical_mirrors",
        "table_name": "L1_历史镜像",
        "primary_field": "mirror_id",
        "fields": [
            {"name": "mirror_id", "type": TEXT_FIELD},
            {"name": "source_event_id", "type": TEXT_FIELD},
            {"name": "kangbo_event_id", "type": TEXT_FIELD},
            {"name": "kangbo_event_name", "type": TEXT_FIELD},
            {
                "name": "analogy_type",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": "供给冲击路径"},
                        {"name": "升级螺旋结构"},
                        {"name": "货币体系断裂"},
                        {"name": "霸权转移路径"},
                        {"name": "技术范式冲击"},
                        {"name": "制度崩塌路径"},
                        {"name": "信用危机路径"},
                    ]
                },
            },
            {"name": "similarity_score", "type": NUMBER_FIELD},
            {"name": "analogy_reasoning", "type": TEXT_FIELD},
            {"name": "key_difference", "type": TEXT_FIELD},
            {"name": "historical_asset_impact", "type": TEXT_FIELD},
        ],
        "views": ["全部"],
    },
    {
        "key": "asset_signals",
        "table_name": "L2_资产信号映射",
        "primary_field": "signal_id",
        "fields": [
            {"name": "signal_id", "type": TEXT_FIELD},
            {"name": "source_event_id", "type": TEXT_FIELD},
            {
                "name": "asset_class",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": "贵金属"},
                        {"name": "工业金属"},
                        {"name": "化工"},
                        {"name": "能源"},
                        {"name": "股票"},
                        {"name": "债券"},
                        {"name": "汇率"},
                        {"name": "现金"},
                    ]
                },
            },
            {"name": "asset_name", "type": TEXT_FIELD},
            {
                "name": "signal_layer",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": "L1结构信号"},
                        {"name": "L2政策信号"},
                        {"name": "L3战术信号"},
                    ]
                },
            },
            {
                "name": "direction",
                "type": SINGLE_SELECT_FIELD,
                "property": {
                    "options": [
                        {"name": "强多"},
                        {"name": "多"},
                        {"name": "中性"},
                        {"name": "空"},
                        {"name": "强空"},
                    ]
                },
            },
            {"name": "v2_indicator_trigger", "type": TEXT_FIELD},
            {"name": "position_action", "type": TEXT_FIELD},
            {"name": "stop_rule", "type": TEXT_FIELD},
            {"name": "historical_reference", "type": TEXT_FIELD},
            {
                "name": "confidence",
                "type": SINGLE_SELECT_FIELD,
                "property": {"options": [{"name": "高"}, {"name": "中"}, {"name": "低"}]},
            },
            {"name": "valid_until", "type": DATE_FIELD},
        ],
        "views": ["全部"],
    },
]


SEED_PAYLOADS: dict[str, list[dict[str, Any]]] = {
    "event_signals": [
        {
            "event_id": "KBS-202602-001",
            "event_date": 1772236800000,
            "event_name": "美国斩首伊朗最高领袖·霍尔木兹封锁",
            "event_category": "战争/地缘",
            "kangbo_phase": "KB10",
            "event_summary": "2026年2月28日，美军对伊朗发动斩首行动击杀最高领袖。IRGC封锁霍尔木兹海峡，11天内日均通行船只从153艘降至13艘，航道布设水雷。油价从战前55美元飙升至近100美元。7名美军阵亡。特朗普所期望的四到五周快速胜利未出现。",
            "causal_chain": "国内政治困局（支持率37%/IEEPA关税违宪/经济数据恶化/中期选举压力）→ 常规政策工具全部堵死（减税需国会/贸易信誉耗尽/Fed不降息）→ 转换舞台至军事领域（总统可单方面行动）→ 以委内瑞拉模板误判伊朗 → IRGC封锁霍尔木兹（意识形态军队vs腐败军队）→ 俄/中/欧各自理性选择均指向升级 → 系统走向无人想要的结局",
            "narrative_type": "恐惧主导",
            "source_article": "Aelia Capitolina (@Areskapitalon)《从谎言到战争的必然路径》：将2026美伊斩首与1964北部湾事件做结构性类比——约翰逊因支持率和选举压力将可能不存在的攻击包装为开战理由，62年后特朗普面临相同的困境。核心论点：当每个参与者按本性做最容易的选择时，系统自动走向无人想要的结局。文章还做了1914萨拉热窝类比：斩首=刺杀斐迪南，移除制动器（哈梅内伊=斐迪南），释放更激进力量（IRGC瓦希迪+莫杰塔巴），同盟连锁反应启动。",
            "impact_direction": "复合冲击",
            "severity": 5,
            "scenario_shift": "A黄金赛道 40%→55% | B流动性冲击 20%→30% | C改革成功 15%→5% | D政策失败 15%→8% | E牛市终结 10%→2%。核心逻辑：霍尔木兹封锁是供给侧通胀冲击，叠加Fed无法降息+财政空间极有限+就业已转负，情景A和B概率大幅上升，C和E几乎归零。",
        }
    ],
    "historical_mirrors": [
        {
            "mirror_id": "MIR-202602-001-A",
            "source_event_id": "KBS-202602-001",
            "kangbo_event_id": "KBE-055",
            "kangbo_event_name": "1973第一次石油危机",
            "analogy_type": "供给冲击路径",
            "similarity_score": 9,
            "analogy_reasoning": "1973赎罪日战争触发阿拉伯石油禁运，油价从3美元涨至12美元（4倍）；2026斩首行动触发IRGC封锁霍尔木兹，油价从55涨至近100美元。两次都是地缘军事事件引发石油供给侧冲击，进而触发全面通胀。历史上最接近的类比，但当前更严重——1973年霍尔木兹海峡并未被封锁，全球20%石油通道未被切断。",
            "key_difference": "1973年霍尔木兹未被封锁，仅是阿拉伯国家选择性禁运；2026年是物理性封锁+水雷。1973年美国是净进口国但有战略储备；2026年叠加AI白领替代+信贷周期见顶+就业已转负的恶化中经济周期。1973年Fed最终以沃尔克式加息解决；2026年36万亿国债使激进加息几乎不可能。",
            "historical_asset_impact": "1973-74：油价×4（3→12美元）| 美股（道琼斯）跌45% | 黄金从42涨至180美元（+328%）| 美元大幅贬值 | CPI通胀率飙至14% | 美债收益率上行 | 美股随后两年持续下跌近50%",
        },
        {
            "mirror_id": "MIR-202602-001-B",
            "source_event_id": "KBS-202602-001",
            "kangbo_event_id": "KBE-033",
            "kangbo_event_name": "1914第一次世界大战",
            "analogy_type": "升级螺旋结构",
            "similarity_score": 8,
            "analogy_reasoning": "1914萨拉热窝刺杀→奥匈最后通牒→同盟连锁反应→四年世界大战。2026斩首行动→IRGC封锁→激活真主党/胡塞/伊拉克什叶派→中东全域扩散。两次核心结构完全一致：触发事件移除制动器（斐迪南=哈梅内伊），释放更激进力量，所有参与者做有限理性选择但合力导向灾难。1914没有领导人想要四年战争和两千万人死亡；2026每个参与者也只是想要'比现在多一点'。",
            "key_difference": "1914是多极均势体系崩塌（五大帝国对称博弈）；2026是霸权国主动发起但不具备快速终结能力（不对称博弈）。1914工业产能转化为军事产能需要时间；2026金融市场反应速度远快于军事进展。1914中立方（比利时）因地理位置被动卷入；2026中立方（沙特/阿联酋）因IRGC无人机攻击被动卷入。",
            "historical_asset_impact": "1914-18：黄金从各国流向美国（安全资产逻辑）| 欧洲货币体系崩溃 | 工业品（钢铁/铜/化工品）暴涨 | 美股先跌后涨（战争经济刺激）| 粮食价格翻倍 | 英镑/法郎/马克贬值，美元相对走强",
        },
        {
            "mirror_id": "MIR-202602-001-C",
            "source_event_id": "KBS-202602-001",
            "kangbo_event_id": "KBE-053",
            "kangbo_event_name": "1971尼克松冲击",
            "analogy_type": "货币体系断裂",
            "similarity_score": 7,
            "analogy_reasoning": "1971美元与黄金脱钩，全球货币体系重定价，黄金从35涨至120美元。2026若冲突持续且美国被迫解除对俄油制裁来缓解供给（文章已指出此趋势），等于用战争拆解自己建立的制裁体系，美元信用体系加速裂变。两次都是美国的单边行动导致自身构建的国际秩序遭到反噬。",
            "key_difference": "1971是主动的政策选择（关闭黄金窗口），可控；2026是被动的地缘后果（战争引发的连锁反应），不可控。1971之后美元通过石油美元体系重新锚定；2026若霍尔木兹长期封锁，石油美元体系的物理基础（中东石油通道）本身被切断。",
            "historical_asset_impact": "1971-73：黄金从35涨至120美元（+243%）| 美股震荡但未崩盘 | 商品全面上涨 | 美元指数大跌 | 全球通胀上行 | 日元/德国马克大幅升值 | 布雷顿森林体系正式终结",
        },
    ],
    "asset_signals": [
        {
            "signal_id": "SIG-202602-001-AU",
            "source_event_id": "KBS-202602-001",
            "asset_class": "贵金属",
            "asset_name": "黄金(XAUUSD/AU)",
            "signal_layer": "L1结构信号",
            "direction": "强多",
            "v2_indicator_trigger": "V-01 GVZ飙升>35（战时恐慌）→ 先触发减仓规则；等降波至GVZ<22后触发加仓窗口。P-04 DXY若破95确认弱美元，叠加加仓。",
            "position_action": "当前GVZ>35，按波动率规则先减至底仓10%。等GVZ回落至22以下，分3-5笔在10个交易日内加仓至25%（目标仓位从20%上调至25%，因情景A概率上升至55%）。",
            "stop_rule": "黄金无绝对止损（底仓逻辑）。波动率管理：GVZ>35减至底仓10%，GVZ 28-35维持15%，GVZ 22-28维持20%，GVZ<22满配25%。",
            "historical_reference": "KBE-055（1973石油危机）：黄金42→180美元（+328%）| KBE-053（1971尼克松冲击）：黄金35→120美元（+243%）| 两次供给侧+货币体系冲击叠加时，黄金都实现3-4倍涨幅。",
            "confidence": "高",
            "valid_until": 1782777600000,
        },
        {
            "signal_id": "SIG-202602-001-AG",
            "source_event_id": "KBS-202602-001",
            "asset_class": "贵金属",
            "asset_name": "白银(XAGUSD/AG)",
            "signal_layer": "L1结构信号",
            "direction": "强多",
            "v2_indicator_trigger": "V-02 VXSLV飙升（流动性恶化）→ 暂停操作。V-06 白银Bid-Ask价差异常放大 → 绝对暂停。等VXSLV回落+价差正常化后恢复。",
            "position_action": "当前流动性恶化，暂停所有白银操作。等VXSLV回落至正常水平+Bid-Ask价差恢复正常后，分批建仓至15%。弹性大于黄金但风险也更大。",
            "stop_rule": "VXSLV>35或Bid-Ask异常放大时全部暂停。正常环境下跟随黄金规则。",
            "historical_reference": "历史上白银在地缘危机中波动率远高于黄金，1973-80白银从2涨至50美元（+2400%）但中间多次腰斩。需严格流动性管理。",
            "confidence": "中",
            "valid_until": 1782777600000,
        },
        {
            "signal_id": "SIG-202602-001-CL",
            "source_event_id": "KBS-202602-001",
            "asset_class": "能源",
            "asset_name": "WTI原油",
            "signal_layer": "L2政策信号",
            "direction": "多",
            "v2_indicator_trigger": "油价已突破$80（V2.0原油策略震荡低吸区间已突破）。需重新评估：若霍尔木兹持续封锁，原油不再是震荡品种而是趋势品种。",
            "position_action": "已有5%底仓持有，不追高。若VIX回落至25以下且封锁持续，评估加仓至10%。若封锁解除或停火信号出现，回到5%震荡策略。",
            "stop_rule": "原油跌破$60止损（封锁解除信号）。VIX>40全面清仓。注意：原油在战时可能双向巨幅波动，严控仓位。",
            "historical_reference": "KBE-055（1973石油危机）：油价从3涨至12美元（+300%）| 当前从55涨至100（+82%），若封锁持续可能进一步至120-150（参考1979第二次石油危机油价从15涨至40）。",
            "confidence": "中",
            "valid_until": 1745971200000,
        },
        {
            "signal_id": "SIG-202602-001-CU",
            "source_event_id": "KBS-202602-001",
            "asset_class": "工业金属",
            "asset_name": "铜(HG/CU)",
            "signal_layer": "L2政策信号",
            "direction": "中性",
            "v2_indicator_trigger": "V-04 铜期权波动率飙升（战时避险）。P-03 10Y-2Y利差仍在走阔（陡峭化未破坏）。两个信号冲突 → 中性等待。",
            "position_action": "维持现有仓位，不加不减。铜的长期逻辑（AI基建+供给约束）未变，但短期受VIX>30的全面减仓规则约束。等VIX回落至25以下+铜自身波动率降至低位时恢复加仓。",
            "stop_rule": "跟随V2.0铜策略规则：高波减仓。VIX>30全品种减仓执行。",
            "historical_reference": "1973石油危机期间铜价先跌后涨，工业金属受需求下行和供给中断双重力量拉扯。关键变量是战争是否扩散至实体经济需求端。",
            "confidence": "中",
            "valid_until": 1745971200000,
        },
        {
            "signal_id": "SIG-202602-001-SPX",
            "source_event_id": "KBS-202602-001",
            "asset_class": "股票",
            "asset_name": "S&P500/美股",
            "signal_layer": "L3战术信号",
            "direction": "强空",
            "v2_indicator_trigger": "V-03 VIX>30触发全品种减仓。叠加V2.0年报季规程（年报季前减仓）。P-02 US10Y上行（油价推动通胀→Fed无法降息→分母端恶化）。",
            "position_action": "立即减仓至5%以下。V2.0策略明确：VIX>30时全品种减仓。当前叠加三重利空（霍尔木兹封锁→油价→通胀→Fed困境，36万亿国债→财政空间归零，就业已转负+消费者信心崩溃）。Trump Put失效——战时舞台上股市下跌被叙事为'敌人造成的损害'而非政策失败。",
            "stop_rule": "VIX回落至25以下+停火信号明确后，评估是否回到10%配置。若地面部队进入伊朗，清仓至0%。",
            "historical_reference": "KBE-055（1973石油危机）：美股随后两年跌近50%。但1973年三个条件（战争支出刺激经济/Fed可宽松/石油供应未切断）尚存；2026年三个条件全部断裂。文章论证历史上从未有大国发动战争的直接后果是切断自己经济命脉的供应。",
            "confidence": "高",
            "valid_until": 1745971200000,
        },
        {
            "signal_id": "SIG-202602-001-DXY",
            "source_event_id": "KBS-202602-001",
            "asset_class": "汇率",
            "asset_name": "美元指数(DXY)",
            "signal_layer": "L2政策信号",
            "direction": "空",
            "v2_indicator_trigger": "P-04 DXY在战前已处于弱势趋势。战争加速美元信用裂变：被迫解除对俄油制裁=拆解自身制裁体系，欧洲央行加速卖美元买黄金。",
            "position_action": "不直接做空美元，而是通过加仓贵金属和非美资产间接表达。若DXY破95，确认弱美元趋势加速，贵金属目标仓位再上调5%。",
            "stop_rule": "若DXY反弹>103（改革成功情景C），触发减贵金属信号。",
            "historical_reference": "KBE-053（1971尼克松冲击）：美元指数大幅下跌，非美货币全面升值。KBE-055（1973石油危机）：美元继续贬值。两次美国主导的秩序冲击都加速了美元走弱。",
            "confidence": "高",
            "valid_until": 1782777600000,
        },
        {
            "signal_id": "SIG-202602-001-CHEM",
            "source_event_id": "KBS-202602-001",
            "asset_class": "化工",
            "asset_name": "甲醇/苯乙烯/PTA",
            "signal_layer": "L2政策信号",
            "direction": "多",
            "v2_indicator_trigger": "油价上涨推高化工成本→但中国煤化工体系在高油价下获得替代优势。P-05 USDCNH下行（人民币走强）利好中国化工股。V2.0化工策略逻辑：去库完成+股票先行。",
            "position_action": "维持20%化工仓位。文章指出中国在高油价环境下处境最舒适（104天战略石油储备+煤化工替代+光伏产能）。化工是中国受益于高油价环境的直接表达。",
            "stop_rule": "若VIX>40触发流动性应急机制，化工减至10%。若中国经济数据意外恶化，减至10%。",
            "historical_reference": "高油价历史上利好煤化工替代路径。1973石油危机推动了全球化工产业向低成本能源国转移。当前中国的煤化工体系是全球最完整的，战略定位类似1973后的中东石化产业。",
            "confidence": "中",
            "valid_until": 1782777600000,
        },
    ],
}


def ensure_artifact_root() -> Path:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_ROOT


def schema_manifest() -> dict[str, Any]:
    return {
        "base_name": "康波事件信号系统V2",
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


def table_spec_by_key(table_key: str) -> dict[str, Any]:
    for table in TABLE_SPECS:
        if table["key"] == table_key:
            return deepcopy(table)
    raise KeyError(f"Unknown table key: {table_key}")


def seed_rows(table_key: str) -> list[dict[str, Any]]:
    return deepcopy(SEED_PAYLOADS[table_key])


def expected_record_counts() -> dict[str, int]:
    return {table_key: len(rows) for table_key, rows in SEED_PAYLOADS.items()}


def write_manifest_json(path: Path = MANIFEST_FILE) -> Path:
    ensure_artifact_root()
    path.write_text(json.dumps(schema_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_seed_payloads(output_dir: Path = SEED_DIR) -> dict[str, Path]:
    ensure_artifact_root()
    output_dir.mkdir(parents=True, exist_ok=True)
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


def seed_payload_paths() -> dict[str, Path]:
    return {table["key"]: SEED_DIR / f"{table['key']}.json" for table in TABLE_SPECS}


def save_seed_result(payload: dict[str, Any], path: Path = SEED_RESULT_FILE) -> Path:
    ensure_artifact_root()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
