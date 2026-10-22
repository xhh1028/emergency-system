# -*- coding: utf-8 -*-
"""v8.26 验证：定级对照表 + 阈值口径 + 保守初判标注 + 升级守卫

需求要点：
  ① 定级只认四项量化指标，禁止主观措辞
  ② 四项均缺失 → 明说"无法精确分级" + 保守初判 + "非国标量化判定"标注
  ③ 阈值一律 `X人以上Y人以下`（含 X 不含 Y），不写 `10-49` 这类简写
  ④ 升级：目标必须严格高于当前；Ⅰ级 → "已达最高响应级别"
  ⑤ 新增"定级依据对照表"（按指标转置）
"""
import copy
import inspect
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


# ============ 一、代码权威阈值表 ============
print("\n== 1. 7.2 阈值表（代码权威，不由模型重述）==")
T = pg._GRADE_TABLE
check("四项指标齐备", set(T) == set(pg.GRADE_METRICS), str(list(T)))
check("档次顺序固定", pg.GRADE_ORDER == ("特别重大", "重大", "较大", "一般"))

check("死亡·重大 = 10人以上30人以下（旧写法 10–29）", T["死亡人数"]["重大"] == "10人以上30人以下")
check("死亡·较大 = 3人以上10人以下（旧写法 3–9）", T["死亡人数"]["较大"] == "3人以上10人以下")
check("重伤·较大 = 10人以上50人以下（旧写法 10–49）", T["重伤人数"]["较大"] == "10人以上50人以下")
check("重伤·重大 = 50人以上100人以下（旧写法 50–99）", T["重伤人数"]["重大"] == "50人以上100人以下")
check("★一般档经济损失**有 50 万下限**", T["直接经济损失"]["一般"] == "50万元以上1000万元以下")
check("★特别重大档**无**连续中断行车条目", "无此条" in T["连续中断行车"]["特别重大"])
check("重大档连续中断 = 24小时以上",
      T["连续中断行车"]["重大"] == "24小时以上")
check("较大档连续中断 = 6小时以上24小时以下",
      T["连续中断行车"]["较大"] == "6小时以上24小时以下")
check("一般档连续中断 = 2小时以上6小时以下",
      T["连续中断行车"]["一般"] == "2小时以上6小时以下")

# 口径回归：**不得**出现 `10-49` `3–9` 这类区间简写
import re
bad = [(m, g, v) for m in T for g, v in T[m].items()
       if re.search(r"\d\s*[-–~]\s*\d", v)]
check("★全表无区间简写（10-49 / 3–9 等）", not bad, str(bad))

# ============ 二、metrics 读取与补齐 ============
print("\n== 2. metrics 读取 / 补齐 / 容错 ==")
rows = pg._metric_rows({})
check("整块缺失 → 补齐 4 行", len(rows) == 4 and [r["name"] for r in rows] == list(pg.GRADE_METRICS))
check("缺失行 value = 未提供", all(r["value"] == "未提供" for r in rows))
check("缺失行 level = 待核实", all(r["level"] == "待核实" for r in rows))

rows = pg._metric_rows({"metrics": [
    {"name": "死亡人数", "value": "2 人", "level": "一般"},
    {"name": "重伤人数", "value": "未提供", "level": "重大"},        # 值缺失 → 强制待核实
    {"name": "不存在的指标", "value": "x", "level": "一般"},          # 非法指标名 → 忽略
]})
by = {r["name"]: r for r in rows}
check("只认四种指标名，未知项被忽略", len(rows) == 4)
check("已有值原样保留", by["死亡人数"]["value"] == "2 人" and by["死亡人数"]["level"] == "一般")
check("★value=未提供 时 level 强制为待核实", by["重伤人数"]["level"] == "待核实")
check("模型漏填的指标行仍补齐", by["直接经济损失"]["value"] == "未提供")

rows = pg._metric_rows({"metrics": [{"name": "死亡人数", "value": "2人", "level": "瞎写的档"}]})
check("非法 level → 待核实", {r["name"]: r for r in rows}["死亡人数"]["level"] == "待核实")
for _blank in ("", "无", "—", "N/A", "null", "-"):
    r = pg._metric_rows({"metrics": [{"name": "死亡人数", "value": _blank, "level": "一般"}]})
    check("空值写法 %r 视同未提供" % _blank, r[0]["value"] == "未提供")

# ============ 三、对照表渲染 ============
print("\n== 3. 定级依据对照表 ==")
tbl = pg._render_grade_table({})
check("表头含四指标列", "| 指标 | 当前数值 |" in tbl[0] and "对应等级" in tbl[0])
check("分隔行存在", tbl[1].startswith("|---"))
check("★共 4 行数据（四项指标）", len(tbl) == 6, "总行数 %d" % len(tbl))
check("阈值列由代码填（含以上/以下写法）", "10人以上30人以下" in "\n".join(tbl))
check("未提供 → 标为待核实", "**待核实**" in "\n".join(tbl))

# ============ 四、端到端渲染：四项均缺失 ============
print("\n== 4. 四项均缺失（保守初判路径）==")

def build(sev):
    return {
        "event": {"severity": sev, "response": {"level": "IV", "authority": "事发地城市人民政府",
                                                "report_deadline": "30 分钟"},
                  "impact": "地下深埋区间列车火灾"},
        "steps": [{"n": 1, "action": "隔离相关区段牵引电流", "action_type": "切断危险源",
                   "role": ["行车调度员"], "role_category": "调度指挥", "basis": "AIEP01",
                   "how_to": "①确认停电区段", "precondition": "无", "resources": "绝缘手套",
                   "parallel_with": [], "depends_on": []}],
        "escalation": {"applicable": True, "current_level": "IV", "triggers": [], "extra_steps": []},
        "dimensions": {}, "cautions": [], "sources": [],
    }

SEV_MISS = {"preliminary": {"level": "较大事故", "confidence": "中", "basis": "保守初判"},
            "level": "尚未成立", "tiers": [], "conclusion": "缺量化数字",
            "correction": "核实重伤人数是否达 10 人以上"}
md, _ = pg._render_markdown(build(SEV_MISS), {"event_types": ["隧道火灾"]})

check("★明说「四项定级指标均缺失，无法对照国家标准进行精确分级」",
      "四项定级指标均缺失，无法对照国家标准进行精确分级" in md)
check("★有「保守初判等级」", "保守初判等级" in md and "较大事故" in md)
check("★有「此为保守推断，非国家标准量化判定」标注",
      "此为保守推断，非国家标准量化判定" in md)
check("★对照表 4 行全为待核实", md.count("**待核实**") == 4, "实际 %d" % md.count("**待核实**"))
check("待核实项列出四项", "待核实项" in md and "死亡人数" in md and "连续中断行车" in md)

# ---- 部分指标已有 ----
SEV_PART = {"preliminary": {"level": "一般事故", "confidence": "低", "basis": "保守初判"},
            "level": "尚未成立", "tiers": [], "conclusion": "部分缺失",
            "correction": "核实中断时长",
            "metrics": [{"name": "死亡人数", "value": "2 人", "level": "一般"},
                        {"name": "重伤人数", "value": "未提供", "level": "待核实"},
                        {"name": "直接经济损失", "value": "未提供", "level": "待核实"},
                        {"name": "连续中断行车", "value": "未提供", "level": "待核实"}]}
md2, _ = pg._render_markdown(build(SEV_PART), {"event_types": ["区间火灾"]})
check("部分已有 → **不**走「四项均缺失」分支", "四项定级指标均缺失" not in md2)
check("部分已有 → 走「尚未成立」分支", "尚未成立" in md2)
check("部分已有 → 待核实项只列缺失的 3 项", "待核实项" in md2 and "死亡人数" not in md2.split("待核实项")[1].split("\n")[0])
check("部分已有 → 待核实标为 3 行", md2.count("**待核实**") == 3, "实际 %d" % md2.count("**待核实**"))
check("已有指标的值进表", "2 人" in md2)

# ============ 五、升级守卫 ============
print("\n== 5. 升级守卫（无循环 / 无降级）==")
check("_lvl_rank：I 最高", pg._lvl_rank("I级") == 1 and pg._lvl_rank("IV") == 4)
check("_lvl_rank：无法识别 → 0", pg._lvl_rank("信息不足") == 0)

cur, trg, flag = pg._esc_level_and_triggers({"current_level": "III", "triggers": [
    {"condition": "重伤10人以上", "target_level": "II"},     # 升一级 → 留
    {"condition": "死亡30人以上", "target_level": "I"},      # 高跳 → 留
    {"condition": "无事升级", "target_level": "III"},        # **同级** → 丢
    {"condition": "往回退", "target_level": "IV级"},         # **降级** → 丢
]})
check("当前 III 只保留 2 条（II / I）", len(trg) == 2, str([t["condition"] for t in trg]))
check("★同级目标被丢弃（不是升级）", all("无事升级" not in t["condition"] for t in trg))
check("★降级目标被丢弃", all("往回退" not in t["condition"] for t in trg))
check("★高跳目标保留（III→I，不逐级 +1）",
      any(t["target_level"] == "I" for t in trg))
check("'IV级' 能归一化成 IV（守卫生效的前提）", pg._norm_level("IV级") == "IV")

cur, trg, flag = pg._esc_level_and_triggers({"current_level": "I", "triggers": [
    {"condition": "任何", "target_level": "II"}]})
check("★当前 I 级 → 触发条件清空", trg == [])
check("★当前 I 级 → flag = max（已达最高响应级别）", flag == "max")

md3, _ = pg._render_markdown(
    dict(build(SEV_MISS), escalation={"applicable": True, "current_level": "I",
                                      "triggers": [{"condition": "x", "target_level": "II"}],
                                      "extra_steps": []}),
    {"event_types": ["隧道火灾"]})
check("★渲染「已达最高响应级别」", "已达最高响应级别" in md3)
check("★I 级时不渲染升级条目", "升级为 **II 级**" not in md3)
check("I 级时给出「报请…提高应对层级」的正确表述",
      "提高应对层级" in md3)

# ============ 六、事故等级 → 响应级别 1:1 硬映射 ============
print("\n== 6. 事故等级 → 响应级别（1:1 硬映射）==")
G2R = pg.GRADE_TO_RESPONSE
check("特别重大 → Ⅰ级", G2R.get("特别重大") == "I")
check("重大 → Ⅱ级", G2R.get("重大") == "II")
check("较大 → Ⅲ级", G2R.get("较大") == "III")
check("一般 → Ⅳ级", G2R.get("一般") == "IV")
check("映射无缺档", set(G2R) == set(pg.GRADE_ORDER))

# ★ 子串陷阱：'特别重大' 含 '重大'，归一化必须先匹配长的
check("★_norm_grade 不被子串骗：'特别重大事故' ≠ '重大'",
      pg._norm_grade("特别重大事故") == "特别重大", pg._norm_grade("特别重大事故"))
check("_norm_grade('较大') == 较大", pg._norm_grade("较大") == "较大")
check("_norm_grade('III级（较大）') == 较大", pg._norm_grade("III级（较大）") == "较大")
check("_norm_grade 垃圾值 → ''", pg._norm_grade("信息不足") == "")

# 当前生效等级的选取：精确判定成立 → 用它；否则用保守初判
check("精确判定成立 → 取精确判定",
      pg._grade_of({"level": "较大事故", "preliminary": {"level": "重大"}}) == "较大")
check("精确判定未成立 → 取保守初判",
      pg._grade_of({"level": "尚未成立", "preliminary": {"level": "较大事故"}}) == "较大")
check("两者都取不到 → ''", pg._grade_of({}) == "")

# ---- 渲染：保守初判定级时同步写出建议响应级别 ----
mdg, _ = pg._render_markdown(build(SEV_MISS), {"event_types": ["隧道火灾"]})
check("★渲染「级别推导」行", "**级别推导**" in mdg)
check("★保守初判标注在推导里", "（保守初判）" in mdg)
check("★较大 → 响应级别 III 级", "响应级别 **III 级**" in mdg)
check("★责任主体按 4.1 绑定为市级", "事发地城市人民政府" in mdg)

# 精确判定成立时的推导
SEV_OK = {"preliminary": {"level": "一般事故", "confidence": "低", "basis": "保守初判"},
          "level": "重大事故", "tiers": [], "conclusion": "命中重大"}
mdg2, _ = pg._render_markdown(build(SEV_OK), {"event_types": ["隧道火灾"]})
check("精确判定「重大」→ 响应级别 II 级", "响应级别 **II 级**" in mdg2)
check("重大 → 省级人民政府", "事发地省级人民政府" in mdg2)
check("精确判定时标注「精确判定」", "（精确判定）" in mdg2)

# ---- 覆盖：模型填错级别时按映射修正 ----
OBJ_BAD = build(SEV_MISS)                      # 保守初判 = 较大 → 应为 III
OBJ_BAD["event"]["response"] = {"level": "I", "authority": "事发地省级人民政府",
                                "report_deadline": "30 分钟"}
mdg3, _ = pg._render_markdown(OBJ_BAD, {"event_types": ["隧道火灾"]})
check("★模型填 Ⅰ 级被覆盖为 III 级", "响应级别 **III 级**" in mdg3)
check("★责任主体随之从省级改回市级", "事发地城市人民政府" in mdg3)
check("覆盖时**不**再出现省级", "省级人民政府" not in mdg3)

# ============ 七、Prompt 契约 ============
print("\n== 6. Prompt / Schema 契约 ==")
g = inspect.getsource(pg.generate_plan)
check("prompt 载明「含 X 不含 Y」口径", "含 X、不含 Y" in g or "含 X 不含 Y" in g)
check("prompt 禁止区间简写", "10–49 人" in g and "禁止写" in g)
check("prompt 含「四项定级指标均缺失」表述", "四项定级指标均缺失" in g)
check("prompt 含「此为保守推断，非国家标准量化判定」", "此为保守推断，非国家标准量化判定" in g)
check("prompt 禁止「按可能后果推断」（精确判定用）", "按可能后果推断" in g)
check("prompt 写明升级目标由阈值决定、非 +1", "不是「当前级别 +1」" in g or "不是" in g)
check("prompt 载明 Ⅳ→Ⅰ 反例", "严重漏响应" in g)
check("SCHEMA_SPEC 含 metrics", '"metrics"' in pg.SCHEMA_SPEC)

import event_understand as eu
esrc = inspect.getsource(eu.understand_event)
check("event_understand 不再以「按可能后果推断」作依据",
      "按\"可能后果\"推断" not in esrc and "按可能后果推断" in esrc)  # 仅出现在禁止语中
check("event_understand 载明保守初判标注", "非国标量化判定" in esrc)
check("event_understand 保留场景规则（行为未变）",
      "涉及隧道、地下空间、密闭空间的人员被困" in esrc)

print("\n" + "=" * 50)
print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  ❌ " + f)
    sys.exit(1)
print("✅ 全部通过")
