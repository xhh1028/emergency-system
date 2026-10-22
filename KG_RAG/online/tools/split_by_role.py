# -*- coding: utf-8 -*-
"""第 2 层（岗位分派）：把主方案按 `role_category` 拆成 **4 份岗位执行清单**。

输入：第 1 层主方案的 **JSON**（`generate_plan` 的中间产物）。
输出：4 段 Markdown（一类一段），或 `--out DIR` 落成 4 个文件。

两种取 JSON 的方式：
  1. `--plan plan.json`   直接读已存的主方案 JSON（离线、可复算）
  2. `--event "事件描述"` 跑**完整在线管道**（同 main.py：解析→检索→生成），
                         用**捕获包装**从 `_render_markdown` 取出 JSON
                         —— **不改动 `plan_generator.py`**（见下方 `_capture_obj`）

本脚本**只读**第 1 层产物，不修改第 1 层任何逻辑。
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ONLINE = os.path.dirname(_HERE)
if _ONLINE not in sys.path:
    sys.path.insert(0, _ONLINE)

import plan_generator as pg  # noqa: E402

CATS = ("一线执行", "调度指挥", "车站管理", "后勤安保")
_CAT_SLUG = {"一线执行": "1-一线执行", "调度指挥": "2-调度指挥",
             "车站管理": "3-车站管理", "后勤安保": "4-后勤安保"}


# ---------------- 拆分逻辑（纯函数，可单测） ----------------

def _cat_of(step):
    """该步的岗位类别；取不到 → ""（由调用方归入「未归类」并如实报出，不静默丢弃）。"""
    return pg._role_category(step)


def split(obj):
    """主方案 dict → (groups, unclassified, meta)。

    - groups: `{类别: [step, ...]}`，**组内按原 `n` 升序**（不重编）；
    - 每步给一个 `_upgraded` 标记：来自 `escalation.extra_steps` 的为 True；
    - **不丢步**：类别取不到的进 `unclassified`，调用方负责报出。
    """
    groups = {c: [] for c in CATS}
    unclassified = []

    def _add(step, upgraded):
        s = dict(step)                       # 浅拷贝：不改动第 1 层产物
        s["_upgraded"] = upgraded
        cat = _cat_of(s)
        (groups[cat] if cat in groups else unclassified).append(s)

    for s in (obj.get("steps") or []):
        if isinstance(s, dict):
            _add(s, False)

    esc = obj.get("escalation") or {}
    for t in (esc.get("extra_steps") or []):
        if isinstance(t, dict):
            _add(t, True)

    for c in CATS:
        groups[c].sort(key=lambda s: pg._n(s.get("n")))          # 按原 n 升序，保留原值
    unclassified.sort(key=lambda s: pg._n(s.get("n")))

    meta = {"escalation_applicable": bool(esc.get("applicable")),
            "total": sum(len(groups[c]) for c in CATS) + len(unclassified)}
    return groups, unclassified, meta


# ---------------- 渲染 ----------------

def render_category(cat, steps):
    """一类岗位一段 Markdown。空类**不空着**，如实说明。"""
    out = ["## %s · 任务清单（共 %d 步）" % (cat, len(steps)), ""]
    if not steps:
        out += ["> 本事件该类岗位**暂无独立任务**。", ""]
        return out
    for i, s in enumerate(steps, 1):
        tag = "【升级后】" if s.get("_upgraded") else ""
        # 括注只放**存在的**字段：升级增补步骤无 `n` / 无 `action_type` → 不渲染空洞的「n=?，其他」
        bits = []
        if pg._s(s.get("n")):
            bits.append("n=%s" % pg._s(s.get("n")))
        if pg._s(s.get("action_type")):
            bits.append(pg._s(s.get("action_type")))
        out.append("**步骤%d**%s%s"
                   % (i, ("（%s）" % "，".join(bits)) if bits else "", tag))
        # 「并列双岗」时标出该步的全部岗位，便于该类读者知道还要谁配合
        out.append("- 动作：%s" % pg._s(s.get("action")))
        out.append("- 岗位：%s" % "、".join(sorted(pg._role_set(s))))
        _ht = pg._how_to(s)
        if _ht:
            out.append("- 做法要点：%s" % _ht)
        out.append("- 依据：%s" % pg._s(s.get("basis")))
        out.append("")
    return out


def render_all(obj):
    """4 段（+ 未归类段）拼接。"""
    groups, unclassified, _ = split(obj)
    lines = []
    for c in CATS:
        lines += render_category(c, groups[c])
        lines += ["---", ""]
    if unclassified:
        lines += render_category("未归类（岗位类别缺失，须复核）", unclassified)
        lines += ["---", ""]
    if not any(groups[c] for c in CATS) and not unclassified:
        lines = ["> ⚠️ 主方案 **无任何步骤**（可能是「信息不足」拒绝生成的方案）——无可分派任务。", ""]
    return "\n".join(lines)


def write_files(obj, outdir):
    groups, unclassified, _ = split(obj)
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for c in CATS:
        p = os.path.join(outdir, "岗位清单_%s.md" % _CAT_SLUG[c])
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(render_category(c, groups[c])))
        paths.append(p)
    if unclassified:
        p = os.path.join(outdir, "岗位清单_9-未归类.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(render_category("未归类（岗位类别缺失，须复核）", unclassified)))
        paths.append(p)
    return paths


# ---------------- 从在线管道取 JSON（**不改** plan_generator.py） ----------------

def _capture_obj(fn):
    """调用 `fn()`（内部会走 `generate_plan` → `_render_markdown`），**捕获其 JSON 入参**。

    做法：临时把 `plan_generator._render_markdown` 换成包装函数 —— 只记录 `obj`
    再原样转调原函数。**`plan_generator.py` 一字未改**（进程内运行期替换）。
    """
    box = {}
    orig = pg._render_markdown

    def _wrapper(obj, event_profile=None):
        box.setdefault("obj", obj)
        return orig(obj, event_profile)

    pg._render_markdown = _wrapper
    try:
        md = fn()
    finally:
        pg._render_markdown = orig
    return box.get("obj"), md


def run_event(question):
    """跑完整在线管道（同 main.py），返回 (主方案 JSON, 渲染后的 Markdown)。"""
    import main as app                                   # 与 main.py 同源，不重复实现检索
    from event_understand import understand_event
    from plan_generator import generate_plan

    # ⚠️ 必须写回 main 的**模块级全局** —— 检索函数读的是全局变量、不是返回值：
    #    `bge_model` / `collection` 在 main.py 里初始为 `None`，只有其 `__main__` 段才赋值。
    #    漏写 → 检索静默失败（`'NoneType' has no attribute 'encode_queries'`），
    #    方案会在**没有规程上下文**的情况下生成。`case_collection` 由 load_collection 内部设置。
    app.bge_model = app.load_encoder()
    app.collection = app.load_collection()
    ep = understand_event(question, app.client)
    rag = app.search_rag_full(ep, top_k=15)
    kg = app.search_neo4j_subgraph(ep)
    cs = app.search_cases(ep, top_k=3)
    return _capture_obj(lambda: generate_plan(question, ep, rag, kg, cs, app.client))


def main():
    ap = argparse.ArgumentParser(description="按岗位拆主方案（第 2 层）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", help="主方案 JSON 文件路径")
    g.add_argument("--event", help="事件描述（跑在线管道生成主方案）")
    ap.add_argument("--out", help="输出目录（写 4 个文件）；不给则打印到屏幕")
    ap.add_argument("--dump-plan", help="把取得的 JSON 存到该路径（便于复算）")
    a = ap.parse_args()

    if a.plan:
        with open(a.plan, encoding="utf-8") as f:
            obj = json.load(f)
    else:
        obj, _md = run_event(a.event)
        if obj is None:
            print("⚠️ 未能从管道取到主方案 JSON（可能触发了「信息不足」前置门）", file=sys.stderr)
            obj = {"steps": [], "escalation": {}}

    if a.dump_plan:
        with open(a.dump_plan, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    if a.out:
        for p in write_files(obj, a.out):
            print("已写出：%s" % p)
    else:
        print(render_all(obj))


if __name__ == "__main__":
    main()
