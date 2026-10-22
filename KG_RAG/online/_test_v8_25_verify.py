# -*- coding: utf-8 -*-
"""v8.25 验证：作战简报层（双层结构）+ 混合场景（环境诱因/潜在风险/耦合链/冲突消解）

重点守卫 v8.25 实际踩到的坑：**把 `_l()` 用在 dict 列表上**会静默清空整列，
表现为简报里「次生/衍生事件」「升级触发条件」被误渲染成「无」。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plan_generator as pg

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✅" if cond else "❌", name, ("  —— " + detail) if detail else ""))


# ============ 一、`_ld` vs `_l`：dict 列表陷阱 ============
print("\n== 1. dict 列表读取（v8.25 实际踩过的坑）==")
dlist = [{"event_type": "信号故障", "trigger": "同时发生"},
         {"event_type": "乘客受伤", "trigger": "撞击导致"}]
check("_l() 会把 dict 转成字符串 → isinstance 全 False（**这正是 bug 根因**）",
      all(not isinstance(x, dict) for x in pg._l(dlist)), str(pg._l(dlist))[:60])
check("_ld() 保留 dict", all(isinstance(x, dict) for x in pg._ld(dlist)))
check("_ld(None) → []", pg._ld(None) == [])
check("_ld('字符串') → []（非列表，不崩）", pg._ld("abc") == [])
check("_ld([]) → []", pg._ld([]) == [])
check("_ld 混合列表只留 dict", pg._ld([{"a": 1}, "x", 3]) == [{"a": 1}])

# ============ 二、完整 fixture ============
EV = {
    "severity": {
        "preliminary": {"level": "较大事故", "confidence": "中", "basis": "上游判定"},
        "level": "尚未成立",
        "correction": "核实重伤人数是否达 10 人以上",
        "tiers": [{"name": "较大", "threshold": "死亡3–9人", "hit": "未命中（缺死亡数字）"}],
        "conclusion": "逐条对照后：缺量化数字",
    },
    "response": {"level": "III", "authority": "事发地城市人民政府", "report_deadline": "30 分钟"},
    "impact": "早高峰暴雨期间列车撞击异物，信号故障、乘客受伤",
    "composite": {
        "risks": ["信号故障", "乘客受伤", "暴雨积水"],
        "interaction": "暴雨 + 信号故障 相互放大",
        "chains": [
            {"from": ["暴雨", "信号故障"], "to": "列车追尾", "why": "制动距离延长"},
            {"from": ["早高峰客流", "乘客受伤"], "to": "站台踩踏", "why": "伤员占位+客流涌入"},
        ],
        "conflicts": [
            {"conflict": "暴雨要求关闭车门防倒灌触电，疏散要求打开车门",
             "strategy": "先确认接触轨隔离、轨面无积水漏电，再手动开门疏散"},
        ],
    },
    "command": {
        "groups": [
            {"group": "综合协调与指挥调度", "direction": "统筹全局、跨组联动", "strategy": "①启动响应 ②动态调级"},
            {"group": "现场抢险与风险控制", "direction": "切断危险源", "strategy": "①隔离牵引电流 ②抢修"},
            {"group": "乘客疏散与医疗救护", "direction": "救人第一", "strategy": "①召唤救护 ②疏散"},
            {"group": "信息发布与运营调整", "direction": "防信息混乱", "strategy": "①广播 ②公交接驳"},
            {"group": "自创的第五组", "direction": "不该出现", "strategy": "应被丢弃"},
        ]
    },
}

OBJ = {
    "event": EV,
    "steps": [
        {"n": 1, "action": "隔离相关区段牵引电流", "action_type": "切断危险源",
         "role": ["行车调度员"], "role_category": "调度指挥", "basis": "AIEP01",
         "how_to": "①确认停电区段", "precondition": "无", "resources": "绝缘手套 2 副",
         "parallel_with": [], "depends_on": []},
        {"n": 2, "action": "组织站台乘客疏散并救治伤员", "action_type": "人身安全",
         "role": ["值班站长"], "role_category": "车站管理", "basis": "AIEP01",
         "how_to": "①清点人数", "precondition": "牵引电流已隔离", "resources": "担架 1 副",
         "parallel_with": [], "depends_on": [1]},
    ],
    "escalation": {
        "applicable": True, "current_level": "IV",
        "triggers": [
            {"condition": "重伤10人以上", "target_level": "III", "basis": "7.2 较大"},
            {"condition": "中断行车6小时以上", "target_level": "III", "basis": "7.2 较大"},
            # ★ 严格高于当前（IV）→ 保留
            {"condition": "死亡30人以上", "target_level": "I", "basis": "7.2 特别重大"},
            # ★ 等于当前级别 → **不是升级**，v8.26 守卫必须丢弃
            {"condition": "仅设备损坏", "target_level": "IV", "basis": "无"},
        ],
        "extra_steps": [],
    },
    "dimensions": {},
    "cautions": ["禁止未隔离牵引电流就进入区间", "禁止未确认区间无人就恢复行车"],
    "sources": [],
}

# event_profile：上游 event_understand 的新字段
PROFILE = {
    "event_types": ["列车撞击异物"],
    "severity": "较大事故",
    "environmental_factors": ["暴雨", "早高峰客流", "轨面湿滑"],
    "secondary_events": [{"event_type": "信号故障", "trigger": "撞击导致"},
                         {"event_type": "乘客受伤", "trigger": "撞击导致"}],
    "potential_risks": ["列车追尾", "乘客被困", "站台踩踏"],
}

md, warns = pg._render_markdown(OBJ, PROFILE)

# ============ 三、简报层 ============
print("\n== 2. 作战简报层（宏观）==")
check("简报置顶（H1）", md.lstrip().startswith("# 📑 作战简报"), md.lstrip()[:20])
for sec in ("## 一、等级研判与待核实项", "## 二、整体态势与耦合风险研判",
            "## 三、总体处置方向（按专业组统筹）", "## 四、处置盲点预警",
            "## 五、升级触发条件"):
    check("简报含 %s" % sec, sec in md)

check("环境诱因已渲染（来自 event_profile）", "暴雨、早高峰客流、轨面湿滑" in md)
check("★次生事件已渲染（旧 bug：此处曾显示「无」）", "信号故障、乘客受伤" in md)
check("潜在风险已渲染", "列车追尾、乘客被困、站台踩踏" in md)
check("★升级触发条件已渲染（旧 bug：此处曾显示「未给出」）", "重伤10人以上" in md)
check("简报不含「未给出升级触发条件」", "未给出升级触发条件" not in md)
check("简报不含「次生/衍生事件：无」", "**次生/衍生事件**：无" not in md)
# v8.26 升级守卫：同级目标是"无操作"，必须丢弃
check("★v8.26 同级触发条件被丢弃（非升级）", "仅设备损坏" not in md)
check("★v8.26 高跳目标保留（IV→I）", "死亡30人以上" in md and "**I 级**" in md)

check("耦合风险链推演渲染", "耦合风险链推演" in md and "暴雨 + 信号故障 → **列车追尾**" in md)
check("第二条链渲染", "早高峰客流 + 乘客受伤 → **站台踩踏**" in md)
check("冲突点渲染", "冲突点" in md and "关闭车门防倒灌触电" in md)
check("协同策略渲染", "协同策略" in md and "轨面无积水漏电" in md)

check("专业组四类全渲染",
      all(g in md for g in pg.COMMAND_GROUPS))
check("专业组带方向与核心策略", "**方向**：统筹全局、跨组联动" in md and "**核心策略**：①启动响应" in md)
check("★非法组名被丢弃（自创第五组）", "自创的第五组" not in md)

check("盲点预警渲染 cautions", "禁止未隔离牵引电流就进入区间" in md)

# ============ 四、详案层**不被破坏** ============
print("\n== 3. 详案层（微观）不被破坏 ==")
check("详案 H1 存在", "# 📋 详细执行方案" in md)
for sec in ("## 一、事件定性", "## 二、处置步骤", "## 三、按岗位执行视图",
            "## 四、升级预案", "## 五、四维覆盖", "## 六、关键注意事项", "## 七、溯源"):
    check("详案含 %s（章节号未动）" % sec, sec in md)
check("★v8.24 的 precondition 仍在", "牵引电流已隔离" in md and "- 前置条件：" in md)
check("★v8.24 的 resources 仍在", "绝缘手套 2 副" in md and "- 所需资源：" in md)
check("★basis 溯源仍在", "- 依据：AIEP01" in md)
check("简报在详案**之前**", md.index("# 📑 作战简报") < md.index("# 📋 详细执行方案"))

# ============ 五、兜底：模型漏填 groups ============
print("\n== 4. 兜底：模型漏填 command.groups ==")
import copy
obj2 = copy.deepcopy(OBJ)
obj2["event"].pop("command")
md2, _ = pg._render_markdown(obj2, PROFILE)
check("仍渲染出专业组段", "## 三、总体处置方向（按专业组统筹）" in md2)
check("显式标注「由代码兜底」（不冒充模型研判）", "由代码机械归并" in md2 or "由代码按步骤属性机械归并" in md2)
check("兜底不编造策略文字", "**核心策略**" not in md2.split("## 四、")[0].split("## 三、")[-1])

obj3 = copy.deepcopy(OBJ)
obj3["event"].pop("composite")
obj3["event"].pop("command")
md3, _ = pg._render_markdown(obj3, PROFILE)
check("无 composite/command 也不崩", isinstance(md3, str) and len(md3) > 0)

# ============ 六、上游 event_understand 契约 ============
print("\n== 5. event_understand 契约 ==")
import inspect
import event_understand as eu
src = inspect.getsource(eu.understand_event)
check("prompt 含 environmental_factors", "environmental_factors" in src)
check("prompt 含 potential_risks", "potential_risks" in src)
check("异常兜底含新字段", src.count('"environmental_factors": []') >= 1)
check("兼容分支含新字段", '"environmental_factors"' in src)

# ============ 七、主 Prompt 契约 ============
print("\n== 6. plan_generator 主 Prompt 契约 ==")
g = inspect.getsource(pg.generate_plan)
check("含约束（二十）", "（二十）" in g)
check("含混合场景段", "混合场景" in g and "多套规程融合" in g)
check("事件画像含环境诱因", "环境诱因（**放大器" in g)
check("硬性约束计数已更新为二十条", "二十条为强制要求" in g)
check("SCHEMA_SPEC 含 chains", '"chains"' in pg.SCHEMA_SPEC)
check("SCHEMA_SPEC 含 conflicts", '"conflicts"' in pg.SCHEMA_SPEC)
check("SCHEMA_SPEC 含 command.groups", '"command"' in pg.SCHEMA_SPEC and '"groups"' in pg.SCHEMA_SPEC)

print("\n" + "=" * 50)
print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  ❌ " + f)
    sys.exit(1)
print("✅ 全部通过")
