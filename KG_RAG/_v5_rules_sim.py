"""v5：模拟 POSITION_RULES 在同档内执行时的协调问题。只读数据，不改代码。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

TIER = {"人身安全": 1, "切断危险源": 1, "关键设备": 2, "运营调整": 3,
        "信息报告": 4, "恢复善后": 5}
KOU = r"防洪板|沙包|挡水|排水设施|潜水泵"
JIU = r"救护车|施救|救助|救治"
SHU = r"宣布疏散|疏散车站"
NOTIFY = r"通知行车调度员|向行车调度员"
CROWD = r"客流控制点|限流|铁马|回形线路|客流管控"
RULES = [("挡水", KOU, 3), ("救治", JIU, 3), ("疏散", SHU, 5),
         ("通知调度", NOTIFY, 6), ("客流管控", CROWD, 8)]

t = io.open("online/_probe_A.txt", encoding="utf-8").read()
parts = [b for b in re.split(r"\n请描述应急事件（输入 q 退出）：\n> ?", t)
         if "## 一、事件定性" in b]


def parse(b):
    out = []
    for m in re.finditer(r"\*\*步骤(\d+)\*\*[：:](.*?)(?=\n\*\*步骤|\Z)", b, re.S):
        seg = m.group(2)
        ty = re.search(r"- 优先级：(\S+)", seg)
        out.append({"n": int(m.group(1)), "action": seg.strip().split("\n")[0],
                    "type": ty.group(1) if ty else "其他"})
    return out


def tier_of(s): return TIER.get(s["type"], 6)


def pos_of(seq, pat):
    for i, s in enumerate(seq, 1):
        if re.search(pat, s["action"]):
            return i, s
    return None, None


def apply_rule(seq, pat, bound):
    """把首个匹配且超限的步骤，移到「同档内最早位置」（绝不跨档）。返回是否发生移动。"""
    p, step = pos_of(seq, pat)
    if step is None or p <= bound:
        return seq, False
    seq = [x for x in seq if x is not step]
    t = tier_of(step)
    idx = len(seq)
    for i, x in enumerate(seq):
        if tier_of(x) == t:
            idx = i
            break
    else:
        for i, x in enumerate(seq):
            if tier_of(x) > t:
                idx = i
                break
    seq.insert(idx, step)
    return seq, True


def run(order, label):
    out = {"挡水": [], "救治": [], "疏散": [], "通知调度": [], "客流管控": [],
           "inv": 0, "pass": {k: 0 for k, _, _ in RULES}}
    for b in parts:
        steps = parse(b)
        seq = sorted(steps, key=lambda s: (tier_of(s), s["n"]))   # v4 排序
        for name in order:
            pat, bound = next((p, bd) for n2, p, bd in RULES if n2 == name)
            seq, _ = apply_rule(seq, pat, bound)
        for name, pat, bound in RULES:
            p, _ = pos_of(seq, pat)
            out[name].append(p)
            if p and p <= bound:
                out["pass"][name] += 1
        r = [tier_of(s) for s in seq]
        out["inv"] += sum(1 for i in range(len(r)) for j in range(i + 1, len(r)) if r[i] > r[j])
    f = lambda xs: " ".join(str(x) if x else "-" for x in xs)
    print("--- %s ---" % label)
    for name in ("挡水", "救治", "疏散", "通知调度", "客流管控"):
        print("   %-8s %s  合格 %d/10" % (name, f(out[name]), out["pass"][name]))
    print("   同档移动后逆序对 = %d" % out["inv"])
    return out


A = run(["挡水", "救治", "疏散", "通知调度", "客流管控"], "A 挡水优先")
B = run(["救治", "挡水", "疏散", "通知调度", "客流管控"], "B 救治优先")
C = run(["疏散", "通知调度", "客流管控", "挡水", "救治"], "C 先做有 n 优势的（挡水/救治最后，靠 n 分）")

print()
print("=== 你要的逐样本：救治 >3 的样本，规则执行前后的位置 ===")
print("%-6s %-10s %-14s %-14s %-14s" % ("次", "排序后", "A挡水规则后", "A救治规则后", "B救治规则后"))
for k, b in enumerate(parts, 1):
    steps = parse(b)
    base = sorted(steps, key=lambda s: (tier_of(s), s["n"]))
    p0, _ = pos_of(base, JIU)
    a1 = apply_rule(base, KOU, 3)[0]
    pa1, _ = pos_of(a1, JIU)
    a2 = apply_rule(a1, JIU, 3)[0]
    pa2, _ = pos_of(a2, JIU)
    b1 = apply_rule(base, JIU, 3)[0]
    pb1, _ = pos_of(b1, JIU)
    mark = " ←" if p0 and p0 > 3 else ""
    print("%-6d %-10s %-14s %-14s %-14s%s" % (k, p0, pa1, pa2, pb1, mark))
