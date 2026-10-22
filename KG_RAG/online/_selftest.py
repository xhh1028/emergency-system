# -*- coding: utf-8 -*-
"""生成层一键自检：渲染冒烟 + 引用检查 + 降级链路区分。任一失败 → 退出码 1。

用法：  python online/_selftest.py        （在仓库根目录）
起因：v8.8 的 `int += list` 让渲染全线崩、10/10 降级为纯文本，而**单测全绿**——
      坏的是集成层，只有实跑才暴露。这个脚本把"实跑"压到秒级。
"""
import logging
import sys

sys.path.insert(0, 'online')
import plan_generator as pg          # noqa: E402

FAIL = []


def check(name, cond, detail=""):
    print(("  ✅ " if cond else "  ❌ ") + name + ("" if cond else "   ← " + str(detail)[:160]))
    if not cond:
        FAIL.append(name)


# ---------- 合成一张最小但有代表性的方案 JSON ----------
def _obj():
    return {
        "event": {
            "severity": {
                "preliminary": {"level": "一般", "confidence": "中", "basis": "自检用"},
                "level": "尚未成立",
                "correction": "核实伤亡/损失/中断数字后按 7.2 改判",
                "tiers": [{"name": "特别重大", "threshold": "死亡≥30", "hit": "未命中（无数据）"}],
                "conclusion": "四档均未命中",
            },
            "response": {"level": "IV", "authority": "事发地城市人民政府",
                         "report_deadline": "30分钟内"},
            "impact": "自检影响范围",
            "composite": {"risks": ["险情A", "险情B"], "interaction": "A 放大 B"},
        },
        "steps": [
            {"n": 1, "action": "隔离受影响区段牵引电流", "action_type": "切断危险源",
             "role": ["行车调度员"], "basis": "AIEP07 7C [步骤3]；GB/T 38707 14.2.15",
             "deadline_text": "目标3分钟内完成", "parallel_with": []},
            {"n": 2, "action": "测试伪造引用", "action_type": "信息报告",
             "role": ["值班站长"], "basis": "AIEP07 ZZZ [步骤9]",
             "deadline_text": "目标5分钟内完成", "parallel_with": []},
            {"n": 3, "action": "测试编号被切断", "action_type": "信息报告",
             "role": ["值班站长"], "basis": "AIEP07 7B [步骤8]；GB；T 38707 14.3.7",
             "deadline_text": "目标5分钟内完成", "parallel_with": []},
        ],
    }


PROFILE = {"primary_event": {"event_type": "列车脱轨", "severity_level": "较大事故"}}

print("== 1. 渲染冒烟（合成 JSON 过完整 _render_markdown）==")
try:
    md, warns = pg._render_markdown(_obj(), PROFILE)
    check("渲染不抛异常", True)
    check("产出步骤标题", md.count("**步骤") >= 2, md[:120])
    check("定级三段式齐全（初判/精确判定/触发修正）",
          all(k in md for k in ("**初判等级**", "**精确判定**", "**触发修正**")),
          [l for l in md.splitlines() if "等级" in l or "精确" in l][:4])
    check("含复合情形", "复合情形" in md)
    check("含置信自检", "置信自检" in md)
    check("含按岗位执行视图", "## 三、按岗位执行视图" in md)
    check("章节号连续（三之后是四）", "## 四、升级预案" in md and "## 三、升级预案" not in md)
    check("渲染 warnings 为空", warns == [], warns)
except Exception as e:
    import traceback
    traceback.print_exc()
    check("渲染不抛异常", False, e)

print("\n== 2. 引用可证实性 ==")
o, sp, nc, br = pg._check_citations("AIEP07 7C [步骤3]；GB/T 38707 14.2.15")
check("真实条款可证实", o == 2 and not sp, (o, sp))
o, sp, nc, br = pg._check_citations("AIEP07 ZZZ [步骤9]")
check("伪造章节 → 存疑", len(sp) == 1, sp)
o, sp, nc, br = pg._check_citations("AIEP08 8B3 [步骤1；7]；AIEP08 8C1")
check("括号内分号不误判", not sp, sp)
o, sp, nc, br = pg._check_citations("GB；T 38707 14.3.7")
check("`GB；T` 记为格式损坏", br is True and not sp, (br, sp))

# ---- v8.21：正则放宽（下划线 / 中文章节名）——改前 4/5 会被误报"存疑" ----
for _t in ("AIEP01_1C5 宣布进入运营紧急状态 [步骤1]",     # 下划线 + 章节名
           "AIEP01 1C5 宣布进入运营紧急状态",              # 空格（原本即通过，防回归）
           "AIEP07_7B 清人程序",                           # 下划线
           "AIEP01 1C5 宣布进入运营紧急状态 [步骤9]",
           "AIEP06 安排起复及移动事故列车"):                # 中文章节名（无编号）
    o, sp, nc, br = pg._check_citations(_t)
    check("可证实：%s" % _t[:26], o == 1 and not sp, (o, sp))
o, sp, nc, br = pg._check_citations("AIEP99_ZZZ 不存在的章节")
check("反例：伪造文档号 → 仍判存疑", len(sp) == 1, sp)
o, sp, nc, br = pg._check_citations("AIEP01_ZZZ 不存在的章节")
check("反例：真文档 + 伪章节 → 仍判存疑", len(sp) == 1, sp)

# ---------- 假 LLM 客户端 ----------
class _Msg:
    def __init__(self, c): self.content = c


class _Choice:
    def __init__(self, c): self.message = _Msg(c)


class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]


class _Completions:
    def __init__(self, c): self.c = c
    def create(self, **kw): return _Resp(self.c)


class _Chat:
    def __init__(self, c): self.completions = _Completions(c)


class FakeClient:
    def __init__(self, c): self.chat = _Chat(c)


class _Capture(logging.Handler):
    def __init__(self): super().__init__(); self.lines = []
    def emit(self, r): self.lines.append(r.getMessage())


def _run(valid_json_text, break_render):
    """跑一次 generate_plan，返回 (返回文本, 日志行)。"""
    cap = _Capture()
    logging.getLogger().addHandler(cap)
    orig = pg._render_markdown
    if break_render:
        pg._render_markdown = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom-render"))
    try:
        out = pg.generate_plan("测试描述", PROFILE, "RAG", "KG", "CASE", FakeClient(valid_json_text))
    finally:
        pg._render_markdown = orig
        logging.getLogger().removeHandler(cap)
    return out, cap.lines


print("\n== 3. 降级链路：渲染失败 ≠ 解析失败 ==")
valid = '{"event": {"severity": {}}, "steps": []}'
out, lines = _run(valid, break_render=True)
check("渲染失败：返回文本标明是**代码缺陷**", "渲染失败（代码缺陷" in out, out[:80])
check("渲染失败：绝不误报『不是合法 JSON』",
      not any("不是合法 JSON" in l for l in lines), [l for l in lines if "JSON" in l])
check("渲染失败：日志含『代码缺陷』", any("代码缺陷" in l for l in lines))

out, lines = _run("这不是JSON哈哈", break_render=False)
check("解析失败：报『两次均未产出合法 JSON』",
      any("两次均未产出合法 JSON" in l for l in lines), lines[-1:] if lines else [])
check("解析失败：不误报渲染失败", not any("渲染失败" in l for l in lines))

print("\n== 4. depends_on 受约束拓扑排序 ==")


def _S(n, dep=None):
    return {"n": n, "action": "动作%d" % n, "action_type": "人身安全",
            "role": ["值班站长"], "basis": "AIEP07 7C", "depends_on": dep or []}


class _Cap(logging.Handler):
    def __init__(self): super().__init__(); self.lines = []
    def emit(self, r): self.lines.append(r.getMessage())


def _apply(seq):
    cap = _Cap(); logging.getLogger().addHandler(cap)
    try:
        out = pg._apply_depends(list(seq), lambda m: cap.lines.append(m))
    finally:
        logging.getLogger().removeHandler(cap)
    return [s["n"] for s in out], cap.lines


seq = [_S(1), _S(2), _S(3)]
got, _ = _apply(seq)
check("无依赖 → 顺序逐位不变（零回归）", got == [1, 2, 3], got)

got, lines = _apply([_S(1), _S(2, [3]), _S(3)])
check("B 依赖后置的 A → A 被提到 B 之前", got == [1, 3, 2], got)
check("调整有日志", any("依赖导致顺序调整" in l for l in lines), lines[-1:])

got, lines = _apply([_S(1), _S(2, [9])])
check("悬空依赖 → 丢弃并告警", got == [1, 2] and any("悬空" in l for l in lines), (got, lines))

got, lines = _apply([_S(1, [1]), _S(2)])
check("自引用 → 丢弃并告警", got == [1, 2] and any("依赖自身" in l for l in lines), (got, lines))

got, lines = _apply([_S(1, [2]), _S(2, [1])])
check("环 → 保持原顺序并告警", got == [1, 2] and any("循环依赖" in l for l in lines), (got, lines))

print("\n== 5. HARD_ORDER_RULES（5 条代码层硬先后兜底）==")


def _HS(action, atype="人身安全"):
    return {"n": 1, "action": action, "action_type": atype, "role": ["值班站长"],
            "basis": "AIEP07 7C", "parallel_with": [], "depends_on": []}


def _ho(seq):
    cap = _Cap(); logging.getLogger().addHandler(cap)
    try:
        out = pg._enforce_hard_order(list(seq), lambda m: cap.lines.append(m))
    finally:
        logging.getLogger().removeHandler(cap)
    return [s["action"][:8] for s in out], cap.lines


check("规则表恰为 5 条", len(pg.HARD_ORDER_RULES) == 5,
      [r[0] for r in pg.HARD_ORDER_RULES])

got, lines = _ho([_HS("广播宣布疏散车站"), _HS("按压紧急停车按钮阻止列车移动")])
check("停车→疏散：B 在前时 A 被交换到前", got[0].startswith("按压"), got)
check("  有交换日志", any("停车→疏散" in l and "已交换" in l for l in lines), lines)

got, lines = _ho([_HS("引导乘客向站台两端疏散"), _HS("清点人数并向值班站长报告")])
check("疏散→清点：清点在前时被交换到后", got[0].startswith("引导"), got)

got, _ = _ho([_HS("隔离受限区段牵引电流"), _HS("组织员工进入区间救援")])
check("隔离电流→进轨道：A 已在前 → 不动", got[0].startswith("隔离"), got)

got, _ = _ho([_HS("车站广播通知乘客保持镇定")])
check("只有 A、没有 B → 不误触发", got == ["车站广播通知乘客"], got)

got, lines = _ho([_HS("通过车站广播宣布疏散车站，引导乘客撤离")])
check("同一步 A、B 同步且顺序正确 → 无需调整（不误报已交换）",
      got == ["通过车站广播宣布"] and not any("已交换" in l for l in lines), (got, lines))

got, lines = _ho([_HS("无关动作甲"), _HS("无关动作乙")])
check("A、B 均无 → 记『未误触发』", any("未误触发" in l for l in lines), lines)

got, lines = _ho([_HS("要求消防部门到场支援"), _HS("引导乘客向站台两端疏散")])
check("召唤外部力量→疏散：A 已在前 → 不动", got[0].startswith("要求消防"), got)

got, lines = _ho([_HS("引导乘客向站台两端疏散"), _HS("要求消防部门到场支援")])
check("召唤外部力量→疏散：疏散在前时被交换到前", got[0].startswith("要求消防"), got)
check("  有交换日志", any("召唤外部力量→疏散" in l and "已交换" in l for l in lines), lines)

print("\n== 6. 定级三段式（初判 → 精确判定 → 触发修正）==")
_o2 = _obj()
_o2["event"]["severity"] = {
    "preliminary": {"level": "特别重大", "confidence": "中",
                    "basis": "上游判定 ＋ 区间隧道爆炸起火、多节车厢坍塌、大量乘客伤亡"},
    "level": "尚未成立",
    "correction": "核实死亡≥30 或重伤≥100 或损失≥1亿 → 特别重大；死亡10–29 或重伤50–99 → 重大",
    "tiers": [{"name": "特别重大", "threshold": "死亡≥30", "hit": "未命中（缺四项数字）"}],
    "conclusion": "缺量化数据",
}
_o2["event"]["response"] = {"level": "I", "authority": "事发地省级人民政府",
                            "report_deadline": "立即报告"}
md2, _ = pg._render_markdown(_o2, PROFILE)
check("初判等级 = 上游判定", "- **初判等级**：特别重大" in md2, md2[:260])
check("精确判定：无数字 → 尚未成立（不给第二个等级）", "**尚未成立**" in md2)
check("声明『当前按初判等级处置』", "当前按「初判等级」处置" in md2)
check("触发修正 行存在", "- **触发修正**" in md2)
check("tiers 仍逐条诚实写未命中", "未命中" in md2)
check("I 级响应 / 省级主体不被误改",
      "I级" in md2 and "省级人民政府" in md2, [l for l in md2.splitlines() if "响应级别" in l])

_o3 = _obj()
_o3["event"]["severity"] = {
    "preliminary": {"level": "重大", "confidence": "中", "basis": "上游判定重大"},
    "level": "较大事故",
    "correction": "…",
    "tiers": [{"name": "较大", "threshold": "…", "hit": "命中第1、2条"}],
    "conclusion": "…",
}
md3, _ = pg._render_markdown(_o3, PROFILE)
check("精确判定与初判不一致时 → 显式暴露分歧",
      "与初判不一致" in md3 and "覆盖初判" in md3, md3[:300])

print("\n== 7. 信息不足时拒绝生成（前置门）==")
check("上游事件类型=未识别 → 拦截",
      pg._insufficient_info({"primary_event": {"event_type": "未识别"}})[0])
check("无事件画像 → 拦截", pg._insufficient_info({})[0])
check("等级未识别 → 拦截",
      pg._insufficient_info({"primary_event": {"event_type": "列车脱轨",
                                               "severity_level": "未识别"}})[0])
check("有类型且等级在 → 放行",
      not pg._insufficient_info({"primary_event": {"event_type": "列车脱轨",
                                                   "severity_level": "较大事故"}})[0])
_mdi = pg._insufficient_plan("测试原因")
check("拦截模板**不含任何处置步骤**", "**步骤" not in _mdi and "- **不适用**" in _mdi)
check("拦截模板含补充指引", "请补充以下信息" in _mdi)

# 渲染后兜底：方案自己无法定级 → 截断
_o4 = _obj()
_o4["event"]["severity"] = {
    "preliminary": {"level": "无法初判", "confidence": "低", "basis": "描述无信号"},
    "level": "尚未成立", "correction": "—",
    "tiers": [], "conclusion": "无法定级",
}
md4, _ = pg._render_markdown(_o4, PROFILE)
check("方案自身无法定级 → 处置步骤被截断", "**步骤" not in md4 and "信息不足" in md4)

print("\n== 8. 危险源处理检查（只告警，不上硬顺序）==")


def _hz(prof, actions):
    cap = _Cap(); logging.getLogger().addHandler(cap)
    seq = [{"n": i + 1, "action": a, "action_type": "人身安全", "role": ["值班站长"],
            "depends_on": []} for i, a in enumerate(actions)]
    try:
        pg._check_hazard(prof, seq, lambda m: cap.lines.append(m))
    finally:
        logging.getLogger().removeHandler(cap)
    return cap.lines


_l = _hz({"primary_event": {"event_type": "站台火灾"}}, ["组织乘客疏散", "拨打119"])
check("火灾场景无灭火动作 → WARNING",
      any("WARNING" in x and "火灾/爆炸" in x for x in _l), _l)
_l = _hz({"primary_event": {"event_type": "站台火灾"}}, ["使用灭火器扑救初期火情", "组织疏散"])
check("火灾场景有灭火动作 → ✅ 不告警",
      any("✅" in x for x in _l) and not any("WARNING" in x for x in _l), _l)
_l = _hz({"primary_event": {"event_type": "站内持刀伤人"}}, ["安保人员隔离行凶者"])
check("袭击场景命中 KW_ATTACK", any("✅" in x and "持械袭击" in x for x in _l), _l)
_l = _hz({"primary_event": {"event_type": "车站不明气体泄漏"}}, ["关闭相关阀门隔离气体源"])
check("气体场景命中 KW_GAS", any("✅" in x and "有毒气体" in x for x in _l), _l)
_l = _hz({"primary_event": {"event_type": "乘客突发疾病"}}, ["实施急救"])
check("非危险源场景 → 不触发（不误报）", _l == [], _l)

print()
if FAIL:
    print("❌ 自检失败 %d 项：%s" % (len(FAIL), "；".join(FAIL)))
    sys.exit(1)
print("✅ 全部通过")
