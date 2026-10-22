# -*- coding: utf-8 -*-
"""v6 验收分析：解析 main.py 的 5-run 输出，输出占位/首分句/步数/逆序对/降级。"""
import re
import sys

TIER = {"人身安全": 1, "切断危险源": 1, "关键设备": 2, "运营调整": 3,
        "信息报告": 4, "恢复善后": 5}
# 验收侧收紧后的**动作词**词表（裁定第 6 点）
# 2026-10-09 同步：救治并入 急救|120（呼叫急救也是动作词）；挡水/疏散暂不变
ACC = {
    "挡水": re.compile(r"防洪板|沙包|挡水|排水设施|潜水泵|排雨泵"),
    "救治": re.compile(r"救护车|施救|救助|救治|送医|急救|120"),
    "疏散": re.compile(r"疏散|撤离|引导"),
}
SLOT_OF = {"挡水": 1, "救治": 2, "疏散": 3}


def first_clause(s):
    return s.split("；")[0].strip()


def parse_runs(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    parts = txt.split("请描述应急事件（输入 q 退出）：")
    return [p for p in parts if "正在解析事件" in p]


def analyze_run(chunk):
    out = {}
    # --- 步骤：**步骤N**：<action> 后跟 - 优先级：<type> ---
    steps = []
    for m in re.finditer(r"\*\*步骤(\d+)\*\*：(.+)", chunk):
        n = int(m.group(1))
        action = m.group(2).strip()
        tail = chunk[m.end():m.end() + 400]
        t = re.search(r"- 优先级：(\S+)", tail)
        atype = t.group(1).strip() if t else "?"
        steps.append({"n": n, "action": action, "type": atype,
                      "tier": TIER.get(atype, 6)})
    steps.sort(key=lambda s: s["n"])
    out["steps"] = steps
    out["n_steps"] = len(steps)

    # --- [rule] 占位日志 ---
    out["rule_ok"], out["rule_warn"] = [], []
    for line in re.findall(r"\[rule\] (.+)", chunk):
        mm = re.match(r"(\S+) → 槽位(\d+)（上限 (\d+)）首句=(.+)", line)
        if mm:
            out["rule_ok"].append({"name": mm.group(1), "slot": int(mm.group(2)),
                                   "bound": int(mm.group(3)), "logged": mm.group(4).strip()})
        elif line.startswith("WARNING"):
            out["rule_warn"].append(line)

    # --- 占位步骤的真实首分句（按 [rule] 日志前缀回填到渲染输出）---
    for r in out["rule_ok"]:
        key = r["logged"][:12]
        hit = next((s for s in steps if s["action"].startswith(key)), None)
        r["first_clause"] = first_clause(hit["action"]) if hit else r["logged"]
        fc = r["first_clause"]
        r["acc_hit"] = bool(ACC[r["name"]].search(fc))
        r["slot_ok"] = (r["slot"] == SLOT_OF[r["name"]])

    # --- 逆序对：tier 更高的步排在了 tier 更低的步之前 ---
    inv = 0
    for i in range(len(steps)):
        for j in range(i + 1, len(steps)):
            if steps[i]["tier"] > steps[j]["tier"]:
                inv += 1
    out["inversions"] = inv

    # --- 降级 / 重试 ---
    out["degrade"] = len(re.findall(r"两次均未产出合法 JSON", chunk))
    out["retry"] = len(re.findall(r"第 1 次输出解析失败，重试成功", chunk))
    out["count_drop"] = re.findall(r"\[count\] (.+)", chunk)
    out["tier_lines"] = re.findall(r"\[tier\] (.+)", chunk)
    return out


def main(path):
    runs = parse_runs(path)
    print("解析到 run 数：%d" % len(runs))
    for i, ch in enumerate(runs, 1):
        a = analyze_run(ch)
        print("\n" + "=" * 70)
        print("RUN %d   步数=%d   逆序对=%d   降级=%d   重试=%d"
              % (i, a["n_steps"], a["inversions"], a["degrade"], a["retry"]))
        placed = {r["name"]: r for r in a["rule_ok"]}
        for name in ("挡水", "救治", "疏散"):
            r = placed.get(name)
            if r:
                print("  [%s] 占位=是 槽位%d(期望%d,%s) 首分句命中=%s"
                      % (name, r["slot"], SLOT_OF[name],
                         "OK" if r["slot_ok"] else "错", "命中" if r["acc_hit"] else "未命中"))
                print("        首分句：%s" % r["first_clause"])
            else:
                print("  [%s] 占位=否  ← %s" % (name, "无告警?" if not a["rule_warn"] else "见告警"))
        for w in a["rule_warn"]:
            print("        WARN: %s" % w)
        # 每档分布
        dist = {}
        for s in a["steps"]:
            dist[s["tier"]] = dist.get(s["tier"], 0) + 1
        print("  tier分布(按位置): %s" % [s["tier"] for s in a["steps"]])
        if a["count_drop"]:
            for c in a["count_drop"]:
                print("  [count] %s" % c[:120])
    # 汇总
    print("\n" + "#" * 70)
    print("# 汇总")
    tot = [analyze_run(ch) for ch in runs]
    for name in ("挡水", "救治", "疏散"):
        ok = sum(1 for a in tot if any(r["name"] == name for r in a["rule_ok"]))
        okfc = sum(1 for a in tot if any(r["name"] == name and r["acc_hit"] for r in a["rule_ok"]))
        print("#  %s 占位 %d/%d，首分句命中收紧词表 %d/%d" % (name, ok, len(tot), okfc, len(tot)))
    ns = [a["n_steps"] for a in tot]
    print("#  步数：%s  极差=%d  区间内(12-15)=%d/%d" % (ns, max(ns) - min(ns),
          sum(1 for x in ns if 12 <= x <= 15), len(ns)))
    print("#  逆序对合计=%d   降级合计=%d" % (sum(a["inversions"] for a in tot),
                                        sum(a["degrade"] for a in tot)))


if __name__ == "__main__":
    main(sys.argv[1])
