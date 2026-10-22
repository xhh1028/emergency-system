# -*- coding: utf-8 -*-
"""固定输入排序自检（**不调 LLM**）：专抓「顺序错、却不违反任何不变量」的回归。

背景：`_selftest.py` 检的是占位数 / 逆序对 / 步数 / 降级这类**不变量**；
而「n 被当字符串排序」（字典序下 `"10" < "2"`）**不违反其中任何一条**——
它不改变占位、不制造逆序对、不改变步数，只是把档内顺序排错（且渲染层按位置
重编号，输出看起来仍是 1..N）。这类 bug 只能靠**逐位断言输出顺序**抓住。
本脚本即 v8.20 §三 抓到这个 bug 的那个测试，固化下来。

用法：python _test_order_n.py   （退出码 0 = 全过）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_generator as pg  # noqa: E402

nolog = lambda *a, **k: None  # noqa: E731
fails = []


def check(name, cond, detail=""):
    print(("  [OK] " if cond else "  [FAIL] ") + name + (("  -> " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def _steps(ns, at="人身安全"):
    """构造最小步骤字典（只含排序/合并/计数关心的字段）。"""
    return [{"n": n, "action": "动作%d" % n, "action_type": at, "role": []} for n in ns]


print("=" * 60)
print("固定输入排序自检（不调 LLM）")
print("=" * 60)

# ---- 1. _n 数值取号 ----
print("\n[1] _n 数值取号")
check("_n(3) == 3", pg._n(3) == 3)
check('_n("10") == 10', pg._n("10") == 10)
check('_n("步骤7") == 7', pg._n("步骤7") == 7)
check("_n(None) 给大哨兵", pg._n(None) >= 10 ** 6)
check('_n("") 给大哨兵', pg._n("") >= 10 ** 6)

# ---- 2. _order_steps 跨 10 保序（核心回归）----
print("\n[2] _order_steps 跨 10 保序（旧代码此处为 [1,10,11,12,2,3,...]）")
got = [s["n"] for s in pg._order_steps(_steps(range(1, 13)), [], nolog)]
check("输出顺序 == [1..12]", got == list(range(1, 13)), "实测 " + str(got))

# ---- 3. 跨档 (tier, n) 数值排序 ----
print("\n[3] 跨档按 (tier, n) 数值排序")
mixed = _steps([1, 2, 10, 11, 12], "人身安全") + _steps([3, 9], "关键设备")  # 关键设备=tier2
got = [(pg._tier(s), s["n"]) for s in pg._order_steps(mixed, [], nolog)]
exp = [(1, 1), (1, 2), (1, 10), (1, 11), (1, 12), (2, 3), (2, 9)]
check("(tier,n) 顺序正确", got == exp, "实测 " + str(got))

# ---- 4. _cap_steps 超 N_MAX → 丢弃 n 最大的尾部 ----
print("\n[4] _cap_steps 超 N_MAX=15 丢弃尾部（各类均未超分类上限）")
types = (["人身安全"] * 4 + ["切断危险源"] * 4 + ["关键设备"] * 3
         + ["运营调整"] * 3 + ["信息报告"] * 2 + ["恢复善后"] * 2)  # 合计 18，均 <= COUNT_RULES
steps = [{"n": i + 1, "action": "动作%d" % (i + 1), "action_type": t, "role": []}
         for i, t in enumerate(types)]
kept = pg._cap_steps(steps, set(), nolog)
kn = sorted(s["n"] for s in kept)
check("保留 15 步", len(kept) == 15, "实测 %d" % len(kept))
check("保留 n=1..15（丢弃 16/17/18）", kn == list(range(1, 16)), "实测 " + str(kn))

# ---- 5. _cap_steps 分类 cap 生效时保留 n 最小者 ----
print("\n[5] _cap_steps 分类 cap（人身安全上限 4）")
kn = sorted(s["n"] for s in pg._cap_steps(_steps(range(1, 17)), set(), nolog))
check("保留最早 4 步（n=1..4）", kn == [1, 2, 3, 4], "实测 " + str(kn))

# ---- 6. _merge_steps 保序 ----
print("\n[6] _merge_steps 跨 10 保序")
out = pg._merge_steps(_steps(range(1, 13), "信息报告"), set(), nolog)
got = [s["n"] for s in out]
check("合并后顺序 == [1..12]", got == list(range(1, 13)), "实测 " + str(got))

# ---- 7. 端到端（不调 LLM）：固定 JSON 走完整管道 → 渲染顺序 ----
# _render_markdown(obj) = 占位→合并→计数→排序→依赖→硬顺序→渲染，全程无 LLM。
print("\n[7] 端到端固定 JSON：渲染顺序须为 1..14（旧代码跨 10 后被打乱）")
import re as _re  # noqa: E402

obj = {
    "event": {
        "severity": {"preliminary": {"level": "较大", "basis": "测试用例"},
                     "level": "较大"},
        "response": {"level": "III级"},
    },
    "steps": [{"n": i, "action": "标记动作%d" % i, "action_type": "人身安全",
               "role": ["值班站长"], "basis": "", "deadline_minutes": 3}
              for i in range(1, 15)],
}
md, _warn = pg._render_markdown(obj, {})
labels = [int(x) for x in _re.findall(r"\*\*步骤(\d+)\*\*", md)]
# 简报会摘要列出少量动作，不能靠动作正文出现次数对半切分；详细方案的步骤标签
# 才是需要验证的主列表和岗位视图顺序。
expected = list(range(1, 15))
check("详细方案步骤标签 == [1..14] 两次", labels == expected * 2, "实测 " + str(labels))
check("主列表与岗位视图均保序", labels[:14] == expected and labels[14:] == expected,
      "主列表=%s；岗位视图=%s" % (labels[:14], labels[14:]))

print("\n" + "=" * 60)
if fails:
    print("[FAIL] %d 项未通过：%s" % (len(fails), fails))
    sys.exit(1)
print("[OK] 全部通过")
