# -*- coding: utf-8 -*-
"""审计 case_001 的逆序对（修正判据）。

判据：`_order_steps` 的输出是 **tier 单调**的（逆序对 = 0，见 §构造性证明）。
因此任何最终逆序都只能由 `_apply_depends` 引入，而 Kahn-by-rank 只会让步骤**变晚**。
⇒ 逆序 (A 在前, B 在后, tier[A] > tier[B]) 合理的充要条件：
   **B 被它自己的依赖推迟了**（B 有 depends_on，或其依赖链上有人有）。
"""
import re
import sys

sys.path.insert(0, 'online')
import plan_generator as pg  # noqa: E402

RAW, RUN_IDX = 'online/_test_v8_10_depends_raw.txt', 1
t = open(RAW, encoding='utf-8', errors='replace').read()
r = [x for x in t.split("请描述应急事件（输入 q 退出）：") if "正在解析事件" in x][RUN_IDX]

ms = list(re.finditer(r"\*\*步骤(\d+)\*\*：(.+)(?=\n)", r))
steps, deps = [], {}
for k, m in enumerate(ms):
    n = int(m.group(1))
    seg = r[m.end(): ms[k + 1].start() if k + 1 < len(ms) else len(r)]
    ty = re.search(r"- 优先级：(\S+)", seg)
    steps.append({"n": n, "tier": pg._effective_tier(ty.group(1) if ty else "?", None)})
    d = re.search(r"- 前置：需先完成 ([^\n]*)", seg)
    deps[n] = [int(x) for x in re.findall(r"\d+", d.group(1))] if d else []

# 反向可达：谁是"被推迟"的（有依赖 → 直接推迟；依赖链上游有依赖 → 传递推迟）
def has_dep_chain(n, seen=None):
    seen = seen or set()
    if n in seen:
        return False
    seen.add(n)
    if deps.get(n):
        return True
    return any(has_dep_chain(p, seen) for p in deps.get(n, []))


print("case_001 依赖边：", {n: deps[n] for n in sorted(deps) if deps[n]})
print()
inv = [(steps[i], steps[j]) for i in range(len(steps)) for j in range(i + 1, len(steps))
       if steps[i]["tier"] > steps[j]["tier"]]
print("%-4s %-24s %-14s %-10s %s" % ("#", "A(前) → B(后)", "tier", "判定", "归因"))
print("-" * 100)
ok = bad = 0
for k, (A, B) in enumerate(inv, 1):
    victim_dep = deps.get(B["n"])
    if has_dep_chain(B["n"]):
        ok += 1
        why = ("B 有前置 %s，被推迟" % victim_dep) if victim_dep else \
              ("B 的依赖链上游被推迟（B 自身无前置）")
    else:
        bad += 1
        why = "—— B 没有任何依赖链，却排在 A 之后 ——"
    print("%-4d 步骤%-3d → 步骤%-3d     tier%d>tier%d   %-10s %s"
          % (k, A["n"], B["n"], A["tier"], B["tier"], "✅ 合理" if has_dep_chain(B["n"]) else "❌ 无理由", why))
print("-" * 100)
print("\n合理（B 被自身依赖链推迟）：%d / %d" % (ok, len(inv)))
print("无理由：%d / %d" % (bad, len(inv)))
print("\n全部 B 的取值集合：", sorted({B["n"] for _, B in inv}))
