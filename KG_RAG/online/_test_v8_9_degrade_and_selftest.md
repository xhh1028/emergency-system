# v8.9 补坑：降级链路说谎 + 缺自动守卫

日期：2026-10-09 ｜ **未 commit** ｜ 起因：v8.8 我自己引入 `int += list`，**10/10 渲染崩而单测全绿**

v8.8 我只修了那个 **bug**，没填它暴露出的**两个结构性坑**。本轮补掉。

---

## 坑 1｜渲染崩了，却记成"不是合法 JSON"

**原代码**（`generate_plan`）：
```python
obj = _extract_json(last_text)
if obj is not None:
    try:
        md, warns = _render_markdown(obj, event_profile)
        return md
    except Exception as e:
        logging.warning("[json] 渲染失败（attempt=%d）：%s", attempt, e)
logging.warning("[json] 第 %d 次输出不是合法 JSON（len=%d）", attempt, len(last_text))  # ← 掉到这里
```

`_extract_json` **成功了**、是 `_render_markdown` 抛异常，但控制流掉到下面，
打出的却是 **"不是合法 JSON"**——**日志在撒谎**，把排查方向从"代码缺陷"引到"模型输出不合格"。

**改后**：渲染异常单独分支、单独措辞、**带完整 traceback**，并且**不再落到那句日志**：
```
[plan] **渲染失败**（attempt=1；JSON 合法，渲染器抛异常 → 代码缺陷）：boom-render
[plan] Traceback (most recent call last): …
```

## 坑 2｜"降级为纯文本返回"，返回的其实是裸 JSON

**原代码**末尾：
```python
logging.warning("[json] 两次均未产出合法 JSON，降级为纯文本返回（内容未丢，但未经结构化渲染）")
return last_text          # ← last_text 是模型吐的**原始 JSON**，不是"纯文本规程"
```

措辞有两处不实：**① 未必是"未产出合法 JSON"**（可能是渲染崩）；**② 返回的不是"纯文本"**，是一坨裸 JSON。
v8.8 事故里用户看到的就是这个：**一坨 JSON + 一句"纯文本"**。

**改后**：两种失败分别返回、分别措辞——
```python
if render_error is not None:
    logging.warning("[json] 渲染器两次均抛异常（**代码缺陷，不是模型问题**）：%s", render_error)
    return (f"⚠️ **方案渲染失败（代码缺陷，非模型问题）**：{render_error}\n\n"
            f"以下为模型原始输出（**JSON 原文，未经渲染**，内容未丢）：\n\n{last_text}")
logging.warning("[json] 两次均未产出合法 JSON，降级返回模型原始输出（内容未丢，未经结构化渲染）")
return last_text
```

---

## 补的守卫：`online/_selftest.py`（一键，秒级）

把"实跑"压到秒级——**15 项检查**，通过 → 退出码 0，任一失败 → **退出码 1**：

| 组 | 检查 |
|---|---|
| **1 渲染冒烟** | 合成 JSON 过完整 `_render_markdown`：不抛异常、出步骤、含初判/复合/置信自检、`warnings` 为空 |
| **2 引用检查** | 真实条款可证实 / 伪造章节→存疑 / **括号内分号不误判** / `GB；T` 记为格式损坏 |
| **3 降级链路** | **渲染失败 ≠ 解析失败**：返回文本标明"代码缺陷"、**绝不误报"不是合法 JSON"**、日志含"代码缺陷"；解析失败报"两次均未产出合法 JSON"且不误报渲染失败 |

**退出码已实测**：正常 → `0`；人为破坏一项断言 → `1`（`❌ 自检失败 1 项：真实条款可证实`）。

用法：仓库根目录 `python online/_selftest.py`。
（原先那个 `_smoke_cite.py` 已被它取代并删除。）

---

## 复验

| 项 | 结果 |
|---|---|
| `_selftest.py` 全绿 | ✅ 15/15，退出码 0 |
| 失败时非零退出 | ✅ 强制失败 → 1 |
| **真实案例正常路径未受影响** | ✅ case_075 实跑：**EXIT=0、0 渲染失败/降级、14 步** |

---

## 留档

| 文件 | 说明 |
|---|---|
| `online/_selftest.py` | 一键自检（新增；取代 `_smoke_cite.py`） |
| `online/_test_v8_9_degrade_raw.txt` | case_075 复验输出 |
| `online/plan_generator.py` | 降级链路改：渲染失败/解析失败**分开记录与措辞** + `import traceback` |
