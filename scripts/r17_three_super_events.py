from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials


TARGET_APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
HOTSPOT_TABLE_ID = "tbliWAJ0lHJfDTis"
ARTIFACT_PATH = REPO_ROOT / "artifacts" / "r17-three-super-events" / "result.json"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5
CHECKBOX_FIELD = 7
URL_FIELD = 15

L1_EVENT_TABLE_NAME = "L1_康波事件信号"
L1_MIRROR_TABLE_NAME = "L1_历史镜像"
L2_SIGNAL_TABLE_NAME = "L2_资产信号映射"
L15_TABLE_NAME = "L1.5_热点深度剖析"


EVENT_SIGNAL_OPTION_PATCHES = {
    "narrative_type": ["秩序崩塌", "技术跃迁", "范式转移"],
    "impact_direction": ["体系重构", "范式转移"],
}

MIRROR_OPTION_PATCHES = {
    "analogy_type": [
        "帝国末期地缘冲突",
        "货币体系信任断裂",
        "通用技术革命起点",
        "数字技术商业化起点",
        "封锁催生替代创新",
        "技术追赶冲击",
    ]
}

L1_BACKLINK_FIELDS: list[dict[str, Any]] = [
    {"field_name": "deep_analysis_id", "type": TEXT_FIELD},
    {"field_name": "escalation_probability", "type": NUMBER_FIELD},
    {"field_name": "duration_estimate", "type": TEXT_FIELD},
]


EVENT_SIGNAL_RECORDS: list[dict[str, Any]] = [
    {
        "event_id": "KBS-202202-001",
        "event_date": 1645660800000,
        "event_name": "俄罗斯全面入侵乌克兰·西方冻结俄央行外汇储备",
        "event_category": "战争/地缘",
        "kangbo_phase": "KB10",
        "event_summary": "2022年2月24日，俄罗斯对乌克兰发动全面军事入侵。48小时内，美欧宣布冻结俄罗斯央行约3000亿美元外汇储备——这是人类历史上首次对G20国家的央行储备实施冻结。SWIFT制裁、能源禁运、芯片出口管制接踵而至。欧洲天然气价格飙升10倍，全球粮食价格指数创历史新高。战争至今持续超过4年，成为二战以来欧洲最大规模常规战争。",
        "causal_chain": "北约东扩（1999波兰/2004波罗的海/2008乌克兰MAP讨论）→ 2014克里米亚危机（俄罗斯红线被触碰）→ 明斯克协议名存实亡 → 2021年秋俄军集结 → 2022年2月全面入侵 → 西方史无前例金融制裁（冻结央行储备=金融核弹）→ 能源武器化（Nord Stream爆炸）→ 全球供应链重组 → 去美元化加速 → 新不结盟运动兴起",
        "narrative_type": "秩序崩塌",
        "source_article": "综合：外汇储备冻结是Zoltan Pozsar(瑞信)所称的'布雷顿森林III'起点——commodity-based monetary order取代Treasury-based monetary order。Ray Dalio《变化中的世界秩序》将其定位为帝国末期的典型地缘冲突信号。",
        "impact_direction": "体系重构",
        "severity": 5,
        "scenario_shift": "冻结俄央行储备是全球货币体系的分水岭：各国央行开始质疑美元储备的安全性→黄金储备需求暴增→去美元化从口号变成行动（金砖扩容/人民币结算/黄金回流）。能源从commodity变成weapon，供应链从efficiency变成security。",
        "deep_analysis_id": "HDA-202202-001",
        "escalation_probability": 60,
        "duration_estimate": "已持续4年+，基准情景为冻结冲突（类似朝鲜半岛模式）。完全终结需要俄罗斯政权更迭或双方力量彻底耗尽，时间尺度可能是5-10年。",
    },
    {
        "event_id": "KBS-202211-001",
        "event_date": 1669766400000,
        "event_name": "ChatGPT发布·第六次康波技术起点",
        "event_category": "技术/产业",
        "kangbo_phase": "KB10",
        "event_summary": "2022年11月30日，OpenAI发布ChatGPT，5天内用户破百万，2个月破1亿——人类历史上增长最快的消费应用。这一刻标志着AI从实验室走向大众，成为第六次康波周期（2020s-2060s?）的技术起爆点。类比：1769年瓦特蒸汽机专利（KB01）、1879年爱迪生电灯（KB05）、1971年Intel 4004（KB08）。每一次康波的核心技术都经历'实验室→商业化→基础设施化→全面渗透'四个阶段，ChatGPT是AI进入'商业化'阶段的标志。",
        "causal_chain": "2012 AlexNet/深度学习突破 → 2017 Transformer架构(Attention is All You Need) → 2018-2022 GPT系列scaling law验证 → 2022.11 ChatGPT = AI的'iPhone时刻' → 算力需求爆发（NVIDIA数据中心收入从2022Q4的36亿→2024Q4的184亿，+411%）→ 电力/铜/冷却/光纤全产业链拉动 → 白领工作替代开始 → 新的经济结构和社会结构正在成形",
        "narrative_type": "技术跃迁",
        "source_article": "综合：Carlota Perez《技术革命与金融资本》框架——每次技术革命都经历Installation→Turning Point→Deployment四阶段。ChatGPT标志着AI进入Installation期的爆发阶段。NVIDIA CEO黄仁勋称之为'AI的iPhone时刻'。",
        "impact_direction": "技术跃迁",
        "severity": 5,
        "scenario_shift": "ChatGPT重新定义了科技投资的主线：AI算力（NVIDIA/AMD/台积电）→ AI基础设施（电力/铜/光纤/冷却）→ AI应用层（Microsoft/Google/Meta）→ AI颠覆的行业（白领服务/教育/医疗/法律）。这是一个20-30年的超级周期。",
        "deep_analysis_id": "HDA-202211-001",
        "escalation_probability": 95,
        "duration_estimate": "20-30年超级周期。类比：第一次工业革命（蒸汽机1769→铁路1830→全面工业化1870，约100年），电气化（1879→1920s大规模应用，约40年），互联网（1993→2020s全面渗透，约30年）。AI可能更快，因为软件的扩散速度远快于硬件。",
    },
    {
        "event_id": "KBS-202501-001",
        "event_date": 1737331200000,
        "event_name": "DeepSeek-R1发布·中国AI成本革命",
        "event_category": "技术/产业",
        "kangbo_phase": "KB10",
        "event_summary": "2025年1月20日，中国AI公司DeepSeek发布R1推理模型，性能比肩OpenAI o1但训练成本仅557万美元（GPT-4训练成本估计1亿+美元），推理成本低一个数量级。一夜之间登顶全球App Store下载榜。NVIDIA股价单日暴跌17%（市值蒸发近6000亿美元），创美股单日市值蒸发纪录。DeepSeek证明：AI不一定需要最先进的芯片——用更聪明的算法+更高效的训练方法，可以在受限条件下达到前沿水平。",
        "causal_chain": "美国芯片出口管制（2022年10月BIS禁令）→ 中国被迫在受限算力下创新 → DeepSeek用MoE架构+多头注意力优化+FP8量化突破效率瓶颈 → 以1/20成本达到GPT-4级别性能 → 证明'高端芯片垄断=AI垄断'的逻辑不成立 → NVIDIA估值逻辑被质疑 → 中国科技资产全面重估 → 东方AI路径获得全球认可",
        "narrative_type": "范式转移",
        "source_article": "综合：DeepSeek的技术突破被Nature、MIT Technology Review等顶级期刊报道。Andrej Karpathy（前Tesla AI总监）评价'这是AI领域的Sputnik时刻'。",
        "impact_direction": "范式转移",
        "severity": 5,
        "scenario_shift": "DeepSeek改变了AI投资的地理分布逻辑：从'只有美国能做AI'→'中国AI有独立路径且更便宜'。对资产的影响：NVIDIA高估值被挑战 | 中国科技股（恒生科技指数）结构性重估 | AI应用层（不只是算力层）开始获得关注。",
        "deep_analysis_id": "HDA-202501-001",
        "escalation_probability": 90,
        "duration_estimate": "DeepSeek不是一个事件，而是一个趋势的确认——中国AI将走出独立于美国的差异化路径。这个趋势是5-10年尺度的。",
    },
]


HOTSPOT_RECORDS: list[dict[str, Any]] = [
    {
        "analysis_id": "HDA-202202-001",
        "source_event_id": "KBS-202202-001",
        "analysis_date": 1645660800000,
        "headline": "布雷顿森林III的起点：当央行储备不再安全",
        "political_trigger": "普京面临北约持续东扩的安全焦虑（2008布加勒斯特峰会讨论乌克兰MAP是关键转折点），2014克里米亚行动的成功强化了'速战速决'认知模板。2021年秋季开始军事集结，2022年2月选择在北京冬奥会闭幕后发动入侵，试图复制克里米亚式的既成事实。",
        "policy_deadlock": "俄罗斯的常规外交工具在2021年末已全部失效：安全保证要求被北约拒绝，明斯克协议被双方视为缓兵之计，能源杠杆因欧洲LNG替代进展而逐渐弱化。普京的判断框架是'现在打比以后打代价更小'——乌克兰正在快速西化和军事化。",
        "only_exit": "全面军事入侵。普京的认知模板是2014克里米亚（72小时既成事实）+ 2008格鲁吉亚（5天战争），期望3天拿下基辅、斩首泽连斯基政权、扶植亲俄政府。",
        "adversary_incentive": "乌克兰在西方支持下的抵抗收益是累积性的：每持续一天，西方武器援助升级一级（标枪→海马斯→豹2→F-16→ATACMS），乌克兰军队作战经验增长，俄军消耗加深。泽连斯基从喜剧演员变成丘吉尔式战时领袖，国内政治合法性与战争绑定。",
        "adversary_time_preference": "均衡",
        "adversary_offramp": "双方都缺乏可接受的下台阶。俄罗斯：任何低于2022年2月实际控制线的结果都意味着'战略失败'。乌克兰：任何领土让步都意味着'背叛了为此牺牲的人'。这是典型的'双方都被自己的叙事锁定'的僵局。",
        "third_party_matrix": "美国：军事援助升级但避免直接参战，利用战争削弱俄罗斯+强化北约+卖军火+卖LNG→战略受益。欧洲：能源危机+难民潮+军费暴增→短期受损，但长期被迫完成能源转型和防务独立→被动转型。中国：俄罗斯折价能源+人民币结算扩大+去美元化加速→战略受益，但避免直接军事卷入。印度/全球南方：低价俄油+不选边→被动受益。格局：所有大国都有动机维持'不战不和'的现状。",
        "system_self_reinforcing": True,
        "dominant_narrative": "西方：'民主vs专制的文明冲突，必须支持乌克兰否则下一个是台湾'。俄罗斯：'北约逼到门口，不得不自卫'。",
        "counter_narrative": "真实的因果链比任何一方的叙事都复杂：北约东扩确实触碰了俄罗斯安全底线，但入侵是普京的战略误判（高估了俄军能力、低估了乌克兰抵抗意志和西方制裁决心）。冻结央行储备则是西方的核选项——有效惩罚了俄罗斯，但副作用是动摇了整个美元体系的信任基础。",
        "narrative_winner": "短期西方叙事占优（民主vs专制框架被全球主流媒体采用）。但长期来看，'央行储备不再安全'的叙事正在全球南方静悄悄地赢——表现为黄金储备暴增和去美元化加速。",
        "escalation_probability": 60,
        "duration_estimate": "已持续4年+。基准情景为冻结冲突5-10年。关键变量：美国大选后援助政策变化、俄罗斯经济承受力、乌克兰人口和兵源枯竭速度。",
        "termination_conditions": "A.谈判妥协（概率低，双方叙事锁定）B.俄罗斯政权更迭（概率低，普京控制稳固）C.乌克兰力量耗尽被迫接受现状（概率中，时间尺度2-3年）D.冻结冲突成为新常态（概率最高，类似朝鲜半岛）E.意外升级至核边缘（概率低但非零）",
        "base_case_scenario": "冻结冲突成为新常态。俄乌沿当前前线形成事实停火线，但无正式和平协议。欧洲完成能源转型但GDP增速永久性下移。去美元化缓慢但不可逆地推进。黄金作为'无国籍储备资产'的地位持续上升。",
        "investment_implication": "这不是一场会'结束'的战争——它是全球秩序重组的催化剂。核心投资含义：(1)黄金是去美元化的直接受益者——全球央行2022-2025年购金量创历史记录；(2)能源从commodity变成weapon——欧洲能源溢价成为结构性存在；(3)供应链从efficiency转向security——制造业回流、友岸外包受益；(4)国防股长期受益——欧洲军费从GDP 1%→2%+是十年级别趋势；(5)俄罗斯折价能源利好中国化工和制造业成本优势。",
    },
    {
        "analysis_id": "HDA-202211-001",
        "source_event_id": "KBS-202211-001",
        "analysis_date": 1669766400000,
        "headline": "第六次康波的iPhone时刻：AI从实验室走向文明基础设施",
        "political_trigger": "不是政治驱动，而是技术内生驱动。Scaling law（参数量×数据量×计算量的幂律关系）在2020-2022年被验证成立，ChatGPT是这条曲线突破人类感知阈值的那个点。类似1903年莱特兄弟试飞成功——技术早就在积累，但公众感知是突变的。",
        "policy_deadlock": "不适用（非政治事件）。但ChatGPT引发了新的政策困境：如何监管一个能力指数增长的技术？欧盟AI Act、中国AI监管条例、美国行政令都是对这个困境的回应。",
        "only_exit": "不适用。这不是一个'有出口'的事件，而是一个单向的技术奇点——AI能力只会继续增长，不会倒退。问题不是'AI会不会来'，而是'AI来了之后社会怎么适应'。",
        "adversary_incentive": "这里没有传统意义的'对手'。但AI竞赛的博弈结构是：美国（OpenAI/Google/Anthropic）vs 中国（百度/阿里/DeepSeek）vs 欧洲（被动方）。每一方都有'不能落后'的恐惧驱动——因为AI能力差距会转化为经济差距和军事差距。这是一个典型的军备竞赛结构。",
        "adversary_time_preference": "均衡",
        "adversary_offramp": "没有下台阶。AI竞赛是一个不可逆的单向过程——任何国家退出都意味着被淘汰。这与核军备竞赛类似，但更难控制，因为AI的扩散成本远低于核武器。",
        "third_party_matrix": "NVIDIA：算力垄断者，AI革命的'卖铲人'→最大直接受益者。台积电：唯一能制造先进AI芯片的代工厂→关键瓶颈和受益者。铜/电力/光纤：AI基础设施的物理层→水涨船高。白领服务业：被替代的第一批行业→结构性受损。新兴市场（印度/东南亚）：AI可能跳过工业化直接进入智能化→潜在受益。",
        "system_self_reinforcing": True,
        "dominant_narrative": "'AI将改变一切，NVIDIA是新的石油公司，不买就错过'——这个叙事在2023-2024年驱动了NVIDIA股价从150→950（+533%）。",
        "counter_narrative": "每次技术革命的Installation期都伴随着泡沫（1720南海泡沫/1840铁路狂热/2000互联网泡沫）。AI的长期价值是真实的，但短期估值可能已经透支了5-10年的增长。问题不是'AI有没有价值'，而是'多少价值已经被定价了'。",
        "narrative_winner": "目前'AI改变一切'的牛市叙事占优。但历史告诉我们：Installation期的泡沫破裂是技术革命的标准剧本，不是意外。破裂后才是真正的Deployment期——技术从金融投机的工具变成经济基础设施。",
        "escalation_probability": 95,
        "duration_estimate": "20-30年超级周期。当前处于Installation期（2022-2027?），之后可能经历一次调整（类似2000互联网泡沫），然后进入Deployment期（2028-2050s?）。",
        "termination_conditions": "技术革命没有'终结条件'——只有阶段转换。当前阶段的结束标志：AI泡沫破裂（NVIDIA估值回归合理）→ 进入Deployment期（AI成为基础设施而非投机标的）。",
        "base_case_scenario": "2025-2027年AI继续高速发展，NVIDIA/算力股维持强势但波动加大。2027-2028年可能出现一次显著调整（Installation→Turning Point）。之后AI进入Deployment期，真正的长期赢家从'卖铲人'转向'用铲人'。",
        "investment_implication": "核心判断：(1)NVIDIA是当前AI革命最确定的受益者，但估值已不便宜——适合持有不适合追高；(2)铜是AI的物理层瓶颈——每个数据中心需要大量铜用于电力传输和冷却，铜的AI需求是增量而非替代；(3)电力/能源是AI的另一个物理层瓶颈——数据中心用电量正在指数增长；(4)白领替代将在2-3年内成为现实——法律/会计/咨询/客服等行业面临结构性冲击；(5)中国AI（DeepSeek等）可能走出差异化路径——低成本+大市场+政策支持。",
    },
    {
        "analysis_id": "HDA-202501-001",
        "source_event_id": "KBS-202501-001",
        "analysis_date": 1737331200000,
        "headline": "AI的Sputnik时刻：当封锁催生了更高效的创新",
        "political_trigger": "美国2022年10月对华芯片出口管制（BIS Entity List + 先进GPU出口禁令）本意是遏制中国AI发展。但封锁催生了'约束下的创新'——DeepSeek被迫用更少的算力做更多的事，反而走出了一条更高效的技术路径。这是制裁的经典反效果（类似1973石油禁运倒逼日本发展节能汽车）。",
        "policy_deadlock": "美国的AI芯片封锁面临两难：加强封锁→中国自主芯片加速+替代方案涌现（DeepSeek证明了这一点），放松封锁→中国AI能力直接跃升。无论哪条路，中国AI的崛起都已不可阻挡。",
        "only_exit": "不适用。DeepSeek的成功不是某个人的决策结果，而是一个生态系统对外部约束的适应性进化。中国有14亿人口的市场、海量工程师、成本优势和强烈的追赶动机——这些结构性优势不会因为任何单一事件而消失。",
        "adversary_incentive": "OpenAI/Google/Anthropic面临的新压力：如果开源模型（DeepSeek是MIT开源的）能达到闭源模型的90%性能但成本低一个数量级，那闭源模型的商业模式（卖API）就面临结构性挑战。这将加速AI能力的'商品化'——算力层溢价下降，应用层价值上升。",
        "adversary_time_preference": "对手",
        "adversary_offramp": "没有下台阶——这是一场只有加速没有减速的技术竞赛。美国加强芯片封锁只会加速中国的替代方案，放松封锁则直接增强中国的能力。",
        "third_party_matrix": "中国科技股：结构性重估（恒生科技指数2025年1月后大幅反弹）→直接受益。NVIDIA：短期估值承压（垄断叙事被挑战），但长期AI算力需求仍在增长→短空长多。全球AI应用层：DeepSeek降低了AI使用门槛→应用创新加速→受益。全球南方：低成本AI意味着发展中国家也能用AI→长期受益。",
        "system_self_reinforcing": True,
        "dominant_narrative": "'DeepSeek证明中国AI已经追上来了，芯片封锁失败了'——这个叙事在2025年1-2月驱动了中国科技股的大幅反弹。",
        "counter_narrative": "更准确的叙事：DeepSeek证明的不是'中国追上了美国'，而是'AI效率提升的速度超过了算力增长的速度'。这对所有高估值的算力股（包括NVIDIA）都是挑战，同时对所有AI应用层都是利好。输家不是'美国'，是'高溢价算力'；赢家不是'中国'，是'高效率AI应用'。",
        "narrative_winner": "短期'中国AI崛起'叙事占优。长期来看，'AI效率革命'的叙事更准确——它不是一个零和博弈（美国输中国赢），而是整体AI成本曲线下移，所有人受益。",
        "escalation_probability": 90,
        "duration_estimate": "中国AI独立路径是5-10年尺度的结构性趋势。DeepSeek只是起点，后续会有更多中国AI公司在不同垂直领域突破。",
        "termination_conditions": "不适用。这不是一个会'终结'的事件，而是一个正在展开的趋势。唯一可能中断的情景：地缘冲突升级到切断中美技术交流的程度（如台海冲突），但即便如此也只是暂时延缓。",
        "base_case_scenario": "中美AI双头格局成形。美国在前沿模型和算力硬件上保持领先，中国在效率优化、应用落地和成本控制上建立优势。两条路径并行发展，相互竞争又相互学习。",
        "investment_implication": "核心判断：(1)中国科技股经历结构性重估——从'跟随美国折价'到'独立创新溢价'；(2)恒生科技指数/中概股是5年尺度的战略配置窗口；(3)AI应用层>AI算力层——DeepSeek降低成本后，真正的价值在'用AI做什么'而非'谁卖算力'；(4)NVIDIA短期承压但长期仍受益于总量增长——只是溢价空间被压缩；(5)港股/A股中的AI应用型公司（字节/腾讯/阿里/美团）可能是被低估的AI赢家。",
    },
]


MIRROR_RECORDS: list[dict[str, Any]] = [
    {
        "mirror_id": "MIR-202202-001-A",
        "source_event_id": "KBS-202202-001",
        "kangbo_event_id": "KBE-033",
        "kangbo_event_name": "1914第一次世界大战",
        "analogy_type": "帝国末期地缘冲突",
        "similarity_score": 8,
        "analogy_reasoning": "1914：奥匈帝国因安全焦虑入侵塞尔维亚，触发同盟连锁反应，演变为四年世界大战。2022：俄罗斯因北约东扩焦虑入侵乌克兰，触发西方制裁连锁反应，演变为长期消耗战。共同结构：衰落帝国的安全焦虑→预防性战争→严重低估对手联盟反应→被自己的行动锁定在无法退出的战争中。",
        "key_difference": "1914是对称的多极均势崩塌（五大帝国），2022是非对称的核大国vs非核国家+西方代理支持。核武器的存在阻止了直接大国对抗，但使冲突更难终结（任何一方都不会被彻底击败）。",
        "historical_asset_impact": "1914-18：黄金从各国流向美国（安全资产逻辑）| 欧洲货币体系崩溃 | 工业品供应断裂后暴涨 | 战争债券成为主要融资工具 | 美国从债务国变成债权国。",
    },
    {
        "mirror_id": "MIR-202202-001-B",
        "source_event_id": "KBS-202202-001",
        "kangbo_event_id": "KBE-053",
        "kangbo_event_name": "1971尼克松冲击",
        "analogy_type": "货币体系信任断裂",
        "similarity_score": 9,
        "analogy_reasoning": "1971：美国单方面关闭黄金窗口，全球货币体系的信任基础从'美元可兑换黄金'变成'美元靠美国信用'。2022：西方冻结俄央行储备，全球储备体系的信任基础从'主权资产不可侵犯'变成'政治不正确的国家资产随时可被冻结'。两次事件都是：霸权国为解决短期问题，动用了动摇长期信任基础的核选项。",
        "key_difference": "1971是美国主动选择（关闭黄金窗口），可控。2022是被动的制裁反应（冻结央行储备），副作用不可控——一旦证明央行储备可以被冻结，这个信任就无法恢复。",
        "historical_asset_impact": "1971-80：黄金从35涨至850美元（+2329%）| 美元指数大幅下跌 | 大宗商品全面上涨（石油从3→40美元）| 通胀失控 | 全球货币体系进入浮动汇率时代。2022-至今的平行：黄金从1800涨至3000+（+67%且仍在加速），各国央行黄金购买量创记录。",
    },
    {
        "mirror_id": "MIR-202211-001-A",
        "source_event_id": "KBS-202211-001",
        "kangbo_event_id": "KBE-004",
        "kangbo_event_name": "1765第一次工业革命启动",
        "analogy_type": "通用技术革命起点",
        "similarity_score": 9,
        "analogy_reasoning": "1765蒸汽机启动了第一次工业革命：机械动力替代人力/畜力，从纺织→采矿→运输→制造全面渗透。2022 ChatGPT启动了AI革命：智能替代人类认知劳动，从文本→代码→图像→科研全面渗透。共同结构：通用技术（GPT=General Purpose Technology）一旦突破应用阈值，就会以指数速度渗透所有行业。",
        "key_difference": "蒸汽机是物理世界的技术，扩散速度受限于基础设施建设（工厂/铁路/港口）。AI是数字世界的技术，扩散速度只受限于算力和数据，远快于任何前代技术革命。",
        "historical_asset_impact": "KB01-KB03（1765-1848）：英国工业品产出增长10倍+ | 棉纺/煤/铁成为主导资产 | 农业占GDP从50%降至20% | 城市化率从20%→50% | 投资回报率从3%→10%+。",
    },
    {
        "mirror_id": "MIR-202211-001-B",
        "source_event_id": "KBS-202211-001",
        "kangbo_event_id": "KBE-065",
        "kangbo_event_name": "1993万维网商业化",
        "analogy_type": "数字技术商业化起点",
        "similarity_score": 8,
        "analogy_reasoning": "1993年Mosaic浏览器让互联网从学术网络变成大众工具，催生了dot-com泡沫（1995-2000）→ 泡沫破裂 → 真正的互联网经济（Google/Amazon/Facebook）。2022 ChatGPT让AI从研究工具变成大众工具，正在催生AI泡沫（2023-?）→ 预期将经历调整 → 真正的AI经济。",
        "key_difference": "互联网泡沫中，大部分公司死了但幸存者（Amazon/Google）成了万亿市值。AI泡沫中，NVIDIA是确定的幸存者（类似思科但有真实盈利），但AI应用层的赢家尚未确定。",
        "historical_asset_impact": "1993-2000：NASDAQ从700→5048（+621%）→ 2002跌至1114（-78%）→ 2015回到5048。泡沫期思科市值达5500亿→ 跌去80%但公司活着。Amazon从107→5.97（-94%）→ 2024市值2万亿。教训：对的技术+错的估值=短期灾难+长期暴富。",
    },
    {
        "mirror_id": "MIR-202501-001-A",
        "source_event_id": "KBS-202501-001",
        "kangbo_event_id": "KBE-055",
        "kangbo_event_name": "1973第一次石油危机",
        "analogy_type": "封锁催生替代创新",
        "similarity_score": 8,
        "analogy_reasoning": "1973阿拉伯石油禁运→日本被迫发展节能技术→丰田精益生产+混动汽车→日本汽车业反超美国。2022美国芯片封锁→中国被迫发展高效AI→DeepSeek低成本高性能路径→可能在AI效率上反超。共同结构：资源封锁不会消灭需求，只会倒逼替代创新，而替代方案往往比原方案更高效。",
        "key_difference": "1973是物理资源（石油）封锁，替代需要数十年基础设施建设。2022是技术产品（芯片）封锁，替代可以通过算法优化在数年内实现——DeepSeek只用了2年就证明了这一点。",
        "historical_asset_impact": "1973后日本汽车股10年涨10倍+ | 日本GDP从全球第3升至第2 | 美国汽车三巨头市占从90%降至60%。暗示：中国AI效率创新可能在5-10年内重塑全球AI产业格局。",
    },
    {
        "mirror_id": "MIR-202501-001-B",
        "source_event_id": "KBS-202501-001",
        "kangbo_event_id": "KBE-069",
        "kangbo_event_name": "1957苏联发射Sputnik",
        "analogy_type": "技术追赶冲击",
        "similarity_score": 7,
        "analogy_reasoning": "1957苏联Sputnik震惊美国——'他们怎么能在太空领先？'→美国反应：NASA成立/DARPA创建/教育大投入→10年后登月。2025 DeepSeek震惊硅谷——'他们怎么能用这么少的芯片做到？'→美国反应：加大AI投入/芯片封锁可能调整/开源生态竞争加剧。",
        "key_difference": "Sputnik是国家竞争（美苏），DeepSeek是生态竞争（开源vs闭源、效率vs算力）。DeepSeek的影响面更广——它不只挑战了美国的AI领先地位，更挑战了'AI需要无限算力'的基本假设。",
        "historical_asset_impact": "Sputnik后美国航天/国防股大涨 | NASA预算从1957的8900万→1966的59亿（+66倍）| 太空竞赛催生了半导体、通信、GPS等技术。暗示：DeepSeek冲击可能催化新一轮AI投入竞赛。",
    },
]


SIGNAL_RECORDS: list[dict[str, Any]] = [
    {
        "signal_id": "SIG-202202-001-AU",
        "source_event_id": "KBS-202202-001",
        "asset_class": "贵金属",
        "asset_name": "黄金(XAUUSD)",
        "signal_layer": "L1结构信号",
        "direction": "强多",
        "v2_indicator_trigger": "央行储备冻结→全球央行去美元化→黄金作为'无国籍储备资产'需求暴增。2022-2025年全球央行年购金量从400吨翻倍至1000吨+。",
        "position_action": "长期战略持仓。每次GVZ<18回调都是加仓窗口。这是十年级别的结构性牛市，不是事件驱动的短期交易。",
        "stop_rule": "黄金无绝对止损。只在GVZ>35时减至底仓。结构性持仓不因短期波动退出。",
        "historical_reference": "KBE-053（1971尼克松冲击）：黄金35→850（+2329%）用了9年。当前从1800起步，如果类比幅度，远期目标极高。",
        "confidence": "高",
        "valid_until": 1924905600000,
    },
    {
        "signal_id": "SIG-202202-001-NG",
        "source_event_id": "KBS-202202-001",
        "asset_class": "能源",
        "asset_name": "欧洲天然气(TTF)",
        "signal_layer": "L2政策信号",
        "direction": "多",
        "v2_indicator_trigger": "Nord Stream爆炸后欧洲永久失去俄罗斯管道气→LNG溢价成为结构性存在→欧洲工业能源成本相比美国/中国永久性抬升20-40%。",
        "position_action": "不直接做多TTF（波动太大），而是做多受益于欧洲能源溢价的中国化工股（煤化工替代逻辑）和美国LNG出口商。",
        "stop_rule": "若俄乌达成和平协议且管道气恢复，逻辑失效。但概率极低。",
        "historical_reference": "1973石油危机后的产业转移：高能源成本地区的制造业向低成本地区迁移是不可逆的。",
        "confidence": "中",
        "valid_until": 1861833600000,
    },
    {
        "signal_id": "SIG-202202-001-DXY",
        "source_event_id": "KBS-202202-001",
        "asset_class": "汇率",
        "asset_name": "美元指数(DXY)",
        "signal_layer": "L1结构信号",
        "direction": "空",
        "v2_indicator_trigger": "冻结央行储备→去美元化加速→美元作为全球储备货币的份额从60%缓慢下降→黄金/人民币/多极货币体系替代。这是一个10年尺度的慢趋势，不是短期交易信号。",
        "position_action": "不直接做空美元。通过加仓贵金属和非美资产（中国/印度/东南亚）间接表达。DXY破95确认弱美元趋势。",
        "stop_rule": "DXY反弹>110则暂停（说明避险需求短期压过去美元化趋势）。",
        "historical_reference": "KBE-053（1971尼克松冲击）后DXY从120跌至85（-29%），用了7年。当前去美元化的驱动力更强（地缘政治化+央行储备不安全）。",
        "confidence": "高",
        "valid_until": 1924905600000,
    },
    {
        "signal_id": "SIG-202211-001-NVDA",
        "source_event_id": "KBS-202211-001",
        "asset_class": "股票",
        "asset_name": "NVIDIA(NVDA)",
        "signal_layer": "L1结构信号",
        "direction": "强多",
        "v2_indicator_trigger": "AI算力需求指数增长→NVIDIA数据中心收入从2022Q4的36亿→2024Q4的184亿（+411%）→ GPU垄断地位（市占80%+）→ CUDA生态护城河。",
        "position_action": "长期持有核心仓位。回调20%+是加仓窗口。不追高——当VIX>30或NASDAQ跌>15%时减仓，等波动消化后回补。",
        "stop_rule": "若AI scaling law被证伪（AI能力停止随算力增长而提升），或AMD/自研芯片大规模替代GPU，逻辑失效。但目前无此迹象。",
        "historical_reference": "MIR-202211-001-B（互联网泡沫）：思科市值5500亿后跌80%但公司存活。NVIDIA的区别：有真实的、加速增长的盈利，不是PPT故事。",
        "confidence": "高",
        "valid_until": 1861833600000,
    },
    {
        "signal_id": "SIG-202211-001-CU",
        "source_event_id": "KBS-202211-001",
        "asset_class": "工业金属",
        "asset_name": "铜(HG/CU)",
        "signal_layer": "L1结构信号",
        "direction": "强多",
        "v2_indicator_trigger": "AI数据中心用铜量是传统建筑的5-10倍→全球数据中心电力需求2023-2030年预计翻3倍→每MW电力传输需要~5吨铜→AI+电动车+电网升级三重需求叠加→铜矿供给增长仅2%/年→供需缺口持续扩大。",
        "position_action": "长期战略持仓。铜价回调到GVZ<18窗口加仓。低波买进、高波减仓、滚动做多。",
        "stop_rule": "若全球经济衰退导致AI投资大幅缩减（类似2000-2002），铜需求短期会下降。跟随V2.0铜策略规则：VIX>30减仓。",
        "historical_reference": "每次技术革命都有对应的'物理层瓶颈资产'：蒸汽机→煤/铁，电气化→铜/石油，互联网→光纤/硅。AI→铜/电力/稀土。",
        "confidence": "高",
        "valid_until": 1924905600000,
    },
    {
        "signal_id": "SIG-202211-001-TSLA",
        "source_event_id": "KBS-202211-001",
        "asset_class": "股票",
        "asset_name": "Tesla(TSLA)",
        "signal_layer": "L2政策信号",
        "direction": "多",
        "v2_indicator_trigger": "Tesla不只是车企——FSD自动驾驶是AI在物理世界的最大应用场景之一→Dojo超级计算机+Optimus机器人→AI+能源+机器人三位一体。但估值争议大，波动剧烈。",
        "position_action": "不作为核心仓位，作为AI主题的卫星配置。仓位控制在5%以内。大幅回调（-30%+）时加仓。",
        "stop_rule": "FSD大规模商业化持续推迟或竞争对手（Waymo/华为）明显领先时减仓。",
        "historical_reference": "类比早期Amazon——市场长期在'汽车公司估值'和'科技公司估值'之间摇摆。最终取决于AI/机器人业务能否兑现。",
        "confidence": "中",
        "valid_until": 1830297600000,
    },
    {
        "signal_id": "SIG-202501-001-HSTECH",
        "source_event_id": "KBS-202501-001",
        "asset_class": "股票",
        "asset_name": "恒生科技指数/中国科技股",
        "signal_layer": "L1结构信号",
        "direction": "强多",
        "v2_indicator_trigger": "DeepSeek证明中国AI有独立路径→中国科技股从'美国AI折价跟随'重估为'独立AI溢价'→恒生科技指数2025年1月后大幅反弹→结构性重估刚刚开始。",
        "position_action": "战略性建仓中国AI相关资产。分批买入恒生科技ETF或个股（腾讯/阿里/字节/美团）。每次回调10%加仓一批。",
        "stop_rule": "若中美地缘冲突急剧升级（台海）或中国AI监管大幅收紧，暂停加仓。但不清仓——因为AI趋势不可逆。",
        "historical_reference": "MIR-202501-001-A（1973石油危机后日本汽车）：封锁催生的替代创新一旦成功，被封锁方的资产重估是5-10年级别的。",
        "confidence": "高",
        "valid_until": 1861833600000,
    },
    {
        "signal_id": "SIG-202501-001-NVDA2",
        "source_event_id": "KBS-202501-001",
        "asset_class": "股票",
        "asset_name": "NVIDIA(NVDA)",
        "signal_layer": "L2政策信号",
        "direction": "中性",
        "v2_indicator_trigger": "DeepSeek证明'更少芯片也能做好AI'→NVIDIA垄断溢价被压缩→短期估值承压。但长期AI算力总需求仍在增长（DeepSeek降低成本→更多人用AI→总算力需求反而增加）。Jevons悖论：效率提升不减少总需求，反而增加。",
        "position_action": "维持现有仓位不加不减。NVIDIA从'独占垄断'变成'领先但被挑战'，估值中枢下移但盈利增长继续。若PE回调至25-30x（从当前40x+），是大幅加仓窗口。",
        "stop_rule": "若NVIDIA数据中心收入连续两个季度环比下降，说明AI算力需求确实见顶，此时减仓。",
        "historical_reference": "类比2000年思科：互联网泡沫中思科估值过高→泡沫破裂跌80%→但互联网流量继续增长→思科盈利恢复但估值再也没回到2000年高点。NVIDIA可能走类似路径。",
        "confidence": "中",
        "valid_until": 1830297600000,
    },
    {
        "signal_id": "SIG-202501-001-CNY",
        "source_event_id": "KBS-202501-001",
        "asset_class": "汇率",
        "asset_name": "人民币(USDCNH)",
        "signal_layer": "L2政策信号",
        "direction": "多",
        "v2_indicator_trigger": "DeepSeek+中国AI生态崛起→外资重新流入中国科技资产→人民币需求增加→叠加去美元化大趋势→USDCNH从7.3向6.8-7.0方向回归。",
        "position_action": "不直接做多人民币汇率（波动大且受政策干预）。通过加仓港股/A股中国AI资产间接表达人民币升值预期。",
        "stop_rule": "若中美关系急剧恶化或中国经济数据持续走弱（PMI<48连续3个月），暂停。",
        "historical_reference": "2005-2013年人民币升值周期（8.28→6.05）：当时的驱动力是中国制造业崛起。当前的新驱动力是中国AI/科技崛起。",
        "confidence": "中",
        "valid_until": 1861833600000,
    },
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the three R17 Kangbo super-events into the live Feishu base.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    return parser.parse_args(argv)


def api(client: FeishuClient, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = client._request(method, path, body)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    code = payload.get("code", 0)
    if code not in (0, "0", None):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def paged_items(client: FeishuClient, path: str, *, page_size: int = 500) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = {"page_size": page_size}
        if page_token:
            query["page_token"] = page_token
        payload = api(client, "GET", f"{path}?{urlencode(query)}")
        data = payload.get("data", {}) or {}
        items.extend(list(data.get("items", []) or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token") or "").strip()
        if not page_token:
            break
    return items


def list_tables(client: FeishuClient, app_token: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables")


def list_fields(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields")


def list_records(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/records")


def sanitize_property(field_type: int, property_value: Any) -> dict[str, Any] | None:
    if not isinstance(property_value, dict) or not property_value:
        return None
    if field_type == SINGLE_SELECT_FIELD:
        options = []
        for option in property_value.get("options", []) or []:
            if not isinstance(option, dict):
                continue
            name = str(option.get("name") or "").strip()
            if not name:
                continue
            cleaned = {"name": name}
            if option.get("id"):
                cleaned["id"] = option["id"]
            if option.get("color") is not None:
                cleaned["color"] = option["color"]
            options.append(cleaned)
        return {"options": options} if options else None
    return dict(property_value)


def table_id_by_name(client: FeishuClient, app_token: str, table_name: str) -> str:
    for table in list_tables(client, app_token):
        if str(table.get("name") or "").strip() == table_name:
            return str(table.get("table_id") or "").strip()
    raise RuntimeError(f"table not found: {table_name}")


def field_lookup(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for field in fields:
        name = str(field.get("field_name") or field.get("name") or "").strip()
        if name:
            result[name] = field
    return result


def ensure_fields(
    client: FeishuClient,
    app_token: str,
    table_id: str,
    field_specs: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> list[str]:
    current_fields = field_lookup(list_fields(client, app_token, table_id))
    created: list[str] = []
    for spec in field_specs:
        field_name = spec["field_name"]
        if field_name in current_fields:
            continue
        if dry_run:
            created.append(field_name)
            continue
        api(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            {"field_name": field_name, "type": spec["type"]},
        )
        created.append(field_name)
    return created


def ensure_single_select_options(
    client: FeishuClient,
    app_token: str,
    table_id: str,
    field_name: str,
    required_options: list[str],
    *,
    dry_run: bool,
) -> list[str]:
    fields = field_lookup(list_fields(client, app_token, table_id))
    current = fields.get(field_name)
    if current is None:
        raise RuntimeError(f"field not found: {field_name} in {table_id}")
    property_payload = dict(current.get("property") or {})
    existing_options = list(property_payload.get("options") or [])
    existing_names = {str(option.get("name") or "").strip() for option in existing_options}
    missing = [name for name in required_options if name not in existing_names]
    if not missing:
        return []
    if dry_run:
        return missing
    merged_options = []
    for option in existing_options:
        name = str(option.get("name") or "").strip()
        if not name:
            continue
        cleaned = {"name": name}
        if option.get("id"):
            cleaned["id"] = option["id"]
        if option.get("color") is not None:
            cleaned["color"] = option["color"]
        merged_options.append(cleaned)
    for name in missing:
        merged_options.append({"name": name})
    api(
        client,
        "PUT",
        f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{current['field_id']}",
        {
            "field_name": field_name,
            "type": int(current.get("type") or SINGLE_SELECT_FIELD),
            "property": {"options": merged_options},
        },
    )
    return missing


def record_key(record: dict[str, Any], primary_field: str) -> str:
    return str((record.get("fields") or {}).get(primary_field) or "").strip()


def upsert_rows(
    client: FeishuClient,
    app_token: str,
    table_id: str,
    primary_field: str,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
    omit_empty_source_url: bool = False,
) -> list[dict[str, Any]]:
    existing = {record_key(record, primary_field): record for record in list_records(client, app_token, table_id)}
    results = []
    for row in rows:
        fields = deepcopy(row)
        if omit_empty_source_url and not fields.get("source_url"):
            fields.pop("source_url", None)
        key = str(fields.get(primary_field) or "").strip()
        current = existing.get(key)
        if dry_run:
            results.append(
                {
                    "action": "update" if current else "create",
                    "primary_field": primary_field,
                    "primary_value": key,
                    "fields": fields,
                    "record_id": str(current.get("record_id") or current.get("id") or "") if current else "",
                }
            )
            continue
        if current:
            record_id = str(current.get("record_id") or current.get("id") or "").strip()
            payload = api(client, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}", {"fields": fields})
            results.append({"action": "update", "primary_value": key, "record_id": record_id, "payload": payload})
            continue
        payload = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", {"fields": fields})
        record = ((payload.get("data") or {}).get("record") or {})
        results.append(
            {
                "action": "create",
                "primary_value": key,
                "record_id": str(record.get("record_id") or record.get("id") or "").strip(),
                "payload": payload,
            }
        )
    return results


def readback_by_primary(client: FeishuClient, app_token: str, table_id: str, primary_field: str, primary_values: list[str]) -> list[dict[str, Any]]:
    values = set(primary_values)
    return [record for record in list_records(client, app_token, table_id) if record_key(record, primary_field) in values]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    creds = load_feishu_credentials(args.account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    client = FeishuClient()
    if not client.available:
        raise SystemExit("FEISHU_APP_ID / FEISHU_APP_SECRET are required")

    table_ids = {
        "event_signals": table_id_by_name(client, TARGET_APP_TOKEN, L1_EVENT_TABLE_NAME),
        "hotspots": HOTSPOT_TABLE_ID,
        "historical_mirrors": table_id_by_name(client, TARGET_APP_TOKEN, L1_MIRROR_TABLE_NAME),
        "asset_signals": table_id_by_name(client, TARGET_APP_TOKEN, L2_SIGNAL_TABLE_NAME),
    }

    option_updates = {
        "event_signals": {},
        "historical_mirrors": {},
    }
    created_backlink_fields = ensure_fields(
        client,
        TARGET_APP_TOKEN,
        table_ids["event_signals"],
        L1_BACKLINK_FIELDS,
        dry_run=args.dry_run,
    )
    for field_name, options in EVENT_SIGNAL_OPTION_PATCHES.items():
        option_updates["event_signals"][field_name] = ensure_single_select_options(
            client, TARGET_APP_TOKEN, table_ids["event_signals"], field_name, options, dry_run=args.dry_run
        )
    for field_name, options in MIRROR_OPTION_PATCHES.items():
        option_updates["historical_mirrors"][field_name] = ensure_single_select_options(
            client, TARGET_APP_TOKEN, table_ids["historical_mirrors"], field_name, options, dry_run=args.dry_run
        )

    event_results = upsert_rows(
        client,
        TARGET_APP_TOKEN,
        table_ids["event_signals"],
        "event_id",
        EVENT_SIGNAL_RECORDS,
        dry_run=args.dry_run,
        omit_empty_source_url=True,
    )
    hotspot_results = upsert_rows(
        client,
        TARGET_APP_TOKEN,
        table_ids["hotspots"],
        "analysis_id",
        HOTSPOT_RECORDS,
        dry_run=args.dry_run,
    )
    mirror_results = upsert_rows(
        client,
        TARGET_APP_TOKEN,
        table_ids["historical_mirrors"],
        "mirror_id",
        MIRROR_RECORDS,
        dry_run=args.dry_run,
    )
    signal_results = upsert_rows(
        client,
        TARGET_APP_TOKEN,
        table_ids["asset_signals"],
        "signal_id",
        SIGNAL_RECORDS,
        dry_run=args.dry_run,
    )

    readback = None
    if not args.dry_run:
        readback = {
            "event_signals": readback_by_primary(
                client,
                TARGET_APP_TOKEN,
                table_ids["event_signals"],
                "event_id",
                [row["event_id"] for row in EVENT_SIGNAL_RECORDS],
            ),
            "hotspots": readback_by_primary(
                client,
                TARGET_APP_TOKEN,
                table_ids["hotspots"],
                "analysis_id",
                [row["analysis_id"] for row in HOTSPOT_RECORDS],
            ),
            "historical_mirrors": readback_by_primary(
                client,
                TARGET_APP_TOKEN,
                table_ids["historical_mirrors"],
                "mirror_id",
                [row["mirror_id"] for row in MIRROR_RECORDS],
            ),
            "asset_signals": readback_by_primary(
                client,
                TARGET_APP_TOKEN,
                table_ids["asset_signals"],
                "signal_id",
                [row["signal_id"] for row in SIGNAL_RECORDS],
            ),
        }

    counts = {}
    for key, table_id in table_ids.items():
        counts[key] = len(list_records(client, TARGET_APP_TOKEN, table_id))

    payload = {
        "mode": "dry-run" if args.dry_run else "apply",
        "target_app_token": TARGET_APP_TOKEN,
        "table_ids": table_ids,
        "created_backlink_fields": created_backlink_fields,
        "option_updates": option_updates,
        "results": {
            "event_signals": event_results,
            "hotspots": hotspot_results,
            "historical_mirrors": mirror_results,
            "asset_signals": signal_results,
        },
        "counts": counts,
        "readback": readback,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
