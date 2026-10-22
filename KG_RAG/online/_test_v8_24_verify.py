# -*- coding: utf-8 -*-
"""v8.24 验证：① 图谱脏节点过滤  ② 前置条件/所需资源 渲染

用**真实脏数据**（output/parsed_records.jsonl）当输入，不造样例。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main
from main import _kg_node_ok, _kg_clean_list
import plan_generator as pg

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✅" if cond else "❌", name, ("  —— " + detail) if detail else ""))


# ============ 一、图谱脏节点过滤 ============
print("\n== 1. 图谱节点名质量过滤（真实脏数据）==")
REC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "parsed_records.jsonl")
dirty_actions, dirty_roles = set(), set()
with open(REC, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("action_text"):
            dirty_actions.add(r["action_text"])
        if r.get("role"):
            dirty_roles.add(r["role"])

print("  样本：action_text %d 种 / role %d 种" % (len(dirty_actions), len(dirty_roles)))

# 已知脏条目（**逐条取自 parsed_records.jsonl 实录**，非编造）
# 分两级：Action 层从严（用户报的 bug 在这层）；Role/Entity 层从宽（岗位不能误杀）
strict_junk = [
    ("一律视作", "模态词被抽成动作 ← **用户报的原始 bug**"),
    ("应根据需要及时调整", "规范性从句（应…）"),
    ("同样有可能受水淹影响", "规范性从句（同样…）"),
    ("依照本章14A2的程序", "章节交叉引用"),
    ("须要求行车调度员按下表所述进行测试", "规范性从句（须…）"),
]
for w, why in strict_junk:
    check("【Action·严】脏节点被滤除：%s（%s）" % (w[:14], why),
          not _kg_node_ok(w, strict=True))

# 这两条**连宽模式也该滤除**（长度兜底 / 句子标点）
for w in ["必须与车辆段控制中心及安保部协调，调派维修及保安人员：巡视所有轨道",
          "使用灭火器扑救，并通知值班经理"]:
    check("【两级皆滤】%s…" % w[:12], not _kg_node_ok(w) and not _kg_node_ok(w, strict=True))
check("【宽模式】整句 role 被滤除",
      not _kg_node_ok("有关报告车辆段/停车场响起火警警报或车辆段/停车场失火的程序"))

# 合法节点**必须放行**（不能误杀，否则图谱与岗位分派就废了）
known_good = ["行车调度员", "值班站长", "道岔", "信号", "潜水泵", "灭火器",
              "紧急停车", "关闭扶梯", "疏散乘客", "启动消防喷淋"]
for w in known_good:
    check("【两级皆放行】%s" % w, _kg_node_ok(w) and _kg_node_ok(w, strict=True))

# ★ 关键回归：**长度不是判据** —— 这些长动作取自实录，必须保住
for w in ["使用无线电通知驾驶员立即停车", "关上门窗将火与空气隔绝",
          "实施大客流综合管理措施", "操作站台两边的紧急停车按钮",
          "维持未受影响的区间的列车服务"]:
    check("【Action·严】长动作仍放行：%s" % w, _kg_node_ok(w, strict=True))

# ★ 关键回归：**岗位不能误杀** —— 这些是宽模式必须保住的合法岗位
for w in ["有关驾驶员", "相关管理人员", "车站督导员、公安人员",
          "行车调度员、车辆段列车控制主管、车辆段管理员",
          "各专业指定人员及外委保洁人员", "负责编写有关报告的人员"]:
    check("【Role·宽】合法岗位放行：%s" % w, _kg_node_ok(w))

check("空串被滤除", not _kg_node_ok(""))
check("None 被滤除", not _kg_node_ok(None))
check("恰好 22 字放行（边界内）", _kg_node_ok("x" * 22))
check("23 字被滤除（边界外）", not _kg_node_ok("x" * 23))

# 列表过滤：脏条目剔掉、好条目留下
mixed = ["行车调度员", "一律视作", "道岔", "须要求行车调度员按下表所述进行测试"]
check("列表过滤（严）：只剔脏条目",
      _kg_clean_list(mixed, strict=True) == ["行车调度员", "道岔"],
      str(_kg_clean_list(mixed, strict=True)))

# ---- 真实数据存活率 ----
kept_r = [x for x in dirty_roles if _kg_node_ok(x)]
kept_a = [x for x in dirty_actions if _kg_node_ok(x, strict=True)]
rr = 100 * len(kept_r) / len(dirty_roles)
ra = 100 * len(kept_a) / len(dirty_actions)
check("Role 保留率 ≥95%%（岗位是分派依据，实测 %.1f%%）" % rr, rr >= 95)
check("Action 保留率 30%%~45%%（动作可低成本丢弃，实测 %.1f%%）" % ra, 30 <= ra <= 45)

# ============ 二、前置条件 / 所需资源 渲染 ============
print("\n== 2. 前置条件 / 所需资源 渲染 ==")

obj = {
    "event": {"severity": {"preliminary": {"level": "较大事故", "confidence": "中", "basis": "上游"},
                           "level": "较大事故", "tiers": [], "conclusion": "—"},
              "response": {"level": "III", "authority": "事发地城市人民政府", "report_deadline": "30 分钟"},
              "impact": "区间中断"},
    "steps": [
        {"n": 1, "action": "隔离相关区段牵引电流", "action_type": "切断危险源",
         "role": ["行车调度员"], "role_category": "调度指挥", "basis": "AIEP01",
         "how_to": "① 确认停电区段；② 挂接地线",
         "precondition": "无", "resources": "绝缘手套 2 副、接地线 1 套",
         "parallel_with": [], "depends_on": []},
        {"n": 2, "action": "组织人员进入区间疏散乘客", "action_type": "人身安全",
         "role": ["值班站长"], "role_category": "车站管理", "basis": "AIEP01",
         "how_to": "① 清点人数；② 沿疏散平台引导",
         "precondition": "牵引电流已隔离、区间已确认无电", "resources": "应急照明 4 具、担架 1 副",
         "parallel_with": [], "depends_on": [1]},
    ],
    "escalation": {"applicable": False},
    "dimensions": {},
    "cautions": [],
    "sources": [],
}

md, warns = pg._render_markdown(obj, {"event_types": ["列车脱轨"], "severity": "较大"})
print("  （渲染警告 %d 条：%s）" % (len(warns), "；".join(warns[:3]) or "无"))

check("前置条件（文字）已渲染：牵引电流已隔离", "牵引电流已隔离" in md)
check("所需资源已渲染：绝缘手套", "绝缘手套 2 副" in md)
check("所需资源已渲染：应急照明", "应急照明 4 具" in md)
check("「前置条件：」标签存在", "- 前置条件：" in md)
check("「所需资源：」标签存在", "- 所需资源：" in md)
# 与 depends_on 的「前置：需先完成 步骤N」**并存且可区分**（两者不是一回事）
check("depends_on 的步骤引用仍在：需先完成 步骤1", "需先完成 步骤1" in md)
check("文字前置条件 与 步骤引用 并存", ("- 前置条件：" in md) and ("需先完成 步骤1" in md))
check("按岗位执行视图含前置条件", "  - 前置条件：牵引电流已隔离" in md)
check("按岗位执行视图含所需资源", "  - 所需资源：绝缘手套 2 副" in md)

# ---- 缺失时必须显式标注，不能静默省略 ----
obj_missing = json.loads(json.dumps(obj, ensure_ascii=False))
for s in obj_missing["steps"]:
    s.pop("precondition", None)
    s.pop("resources", None)
md2, _ = pg._render_markdown(obj_missing, {"event_types": ["列车脱轨"], "severity": "较大"})
check("缺失前置条件 → 显式标注未提供", md2.count("- 前置条件：⚠️ **未提供**") == 2)
check("缺失所需资源 → 显式标注未提供", md2.count("- 所需资源：⚠️ **未提供**") == 2)

# ============ 三、Prompt 契约同步 ============
print("\n== 3. Prompt / Schema 契约同步 ==")
check("SCHEMA_SPEC 含 precondition 字段", '"precondition"' in pg.SCHEMA_SPEC)
check("SCHEMA_SPEC 含 resources 字段", '"resources"' in pg.SCHEMA_SPEC)
import inspect
src = inspect.getsource(pg.generate_plan)
check("主 Prompt 含八环节骨架", "八个环节逐项自查" in src)
check("主 Prompt 含约束（十九）", "（十九）" in src)
check("规程原文排在图谱之前", src.index("【规程原文片段") < src.index("【知识图谱事实"))
check("主 Prompt 提示图谱可能有脏数据", "脏数据" in src)

print("\n" + "=" * 50)
print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  ❌ " + f)
    sys.exit(1)
print("✅ 全部通过")
