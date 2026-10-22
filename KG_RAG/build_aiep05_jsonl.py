# -*- coding: utf-8 -*-
"""Build AIEP05 JSONL chunks from reviewed markdown.

Source : long_data/AIEP05_RAG/03_markdown_reviewed/*.md
Output : long_data/AIEP05_RAG/04_jsonl/AIEP05_<section>_chunks.jsonl

Page numbering
--------------
页码来源为旧长切片集（long_chunk_681片_待复核），无法独立复核，待原 PDF 确认。

AIEP05 has NO source PDF (00_raw/ is empty) and no 02_markdown_raw/, so pages
cannot be read from the document. They are taken instead from the legacy
long-chunk set in long_chunk_681片_待复核/long_chunk/JKR3_AIEP05_*.txt, which
recorded real footers (below). The legacy records cannot be independently
verified on this machine: there is no PDF and no OCR/rendering tooling
available, so their accuracy rests on the legacy pipeline having read the
printed footers correctly.

    JKR3_AIEP05_0001  运营紧急状态         PDF页序 1      印刷页码 5A1-1
    JKR3_AIEP05_0002  处理分离列车         PDF页序 1,2,3  印刷页码 5A1-1,5A1-2,5A1-3
    JKR3_AIEP05_0003  何时可移动分离列车    PDF页序 4      印刷页码 5A2-1
    JKR3_AIEP05_0004  移动分离列车指引      PDF页序 4      印刷页码 5A2-1

The step children of 处理分离列车 carry the parent's full 1-3 range: the table
spans those three pages and the per-step split is not recorded anywhere, so a
range is stated rather than an invented page number.

版本备注：旧管线记录的 页脚版次 为 "1.0,1.1"，即 处理分离列车 表格所在的第
1-3 页（印刷页 5A1-1~5A1-3）页脚版次并不一致，说明该文档可能经过后续修订。
这属于底层数据源的问题，不是本脚本的生成逻辑问题。`version` 按 schema 规定强制为 "1.0"。
2026-09-29 裁定：本手册为分册、无总版次，页脚标记的是该页所属修订批次，
故维持统一 1.0，不再逐页核对（见 reports/ragflow_config.md「已知限制」）。

TODO: 5A1 处理分离列车 表格的分组标题「1. 报告事故」与「2. 报告事故」完全
重复（见下方 STEPS_5A1 的两个 group 项），逻辑上说不通，疑为 OCR 或旧复核阶段
的错误。已按原文照录、未作修改。等取得原 PDF 后需核对第 1-3 页，确认第二个
标题是否为「2. 处理事故」或其他文字。

5A1's 运营紧急状态 paragraph and its 参考 paragraph are split into separate
chunks (definition / notice) per the slicing rules, whereas the legacy
JKR3_AIEP05_0001 bundled them into one.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "long_data" / "AIEP05_RAG" / "04_jsonl"

DOC_ID = "AIEP05"
VERSION = "1.0"
EFFECTIVE_DATE = "待确认"

S5A1 = "5A1 处理列车分离事件"
S5A2 = "5A2 移动分离列车"

STEPS_5A1 = [
    ("group", "1. 报告事故"),
    ("step", "1.1", "驾驶员",
     "- 停止列车所有运作，但确保无线电功能正常；\n"
     "- 利用广播通知列车内的乘客所发生的事故，以稳定情绪并告知其留在列车内，等待工作人员到场救援；\n"
     "- 通知行车调度员以下数据：\n"
     "  - 驾驶室的显示及其它征兆；\n  - 列车的准确位置；\n  - 列车分离的位置（如果可以确定）；\n"
     "  - 是否有乘客受伤；\n  - 事故的严重性及造成的损坏（若可以确定）；\n  - 列车的载客量；\n"
     "  - 任何可能需要的紧急服务；\n  - 列车的车次及车号"),
    # TODO: 疑似重复 - 与上面的「1. 报告事故」文字相同，待核对原 PDF（第 1-3 页）
    ("group", "2. 报告事故"),
    ("step", "2.1", "行车调度员",
     "- 将尾随事故列车的所有列车留在车站站台，避免有列车滞留在两站之间；\n"
     "- 若上行轨道与下行轨道之间并无隧道墙分隔，安排停止相邻轨道的行车；\n"
     "- 向驾驶员查询以下数据：\n"
     "  - 列车分离的位置；\n  - 是否有乘客受伤；\n  - 事故的严重性及造成的损坏；\n"
     "  - 列车的准确位置；\n  - 列车载客量；\n  - 任何可能需要的紧急服务；\n"
     "  - 列车的车次和车号；\n"
     "- 通知所有受影响的驾驶员有关事故及预计会延误多久；\n"
     "- 要求值班维修技术员前往事故列车现场；\n"
     "- 通知另一位当值的行车调度员负责列车调度工作"),
    ("step", "2.2", "行车调度员",
     "- 通知值班经理、事故处理主任、值班站长、乘务管理员、车辆段管理员和车辆段控制中心；\n"
     "- 规划行车安排"),
    ("step", "2.3", "值班经理",
     "- 宣布进入运营紧急状态；\n"
     "- 在事故处理主任抵达前，指示最近现场的车站值班站长担任事故处理主任；\n"
     "- 要求车辆段控制中心派出救援队；\n- 通知公交总队"),
    ("step", "2.4", "行车调度员",
     "- 列车若滞留在两站之间，须联络有关值班站长，确保已经亮起隧道灯及已关掉风机；\n"
     "- 与系统调度员安排隔离牵引电流；\n- 安排乘客下车；\n- 通知有关值班站长清人安排"),
]

LEAD_5A1 = "处理分离列车：驾驶员在确定列车分离后，有关人员须遵循以下程序："

# ---------------------------------------------------------------- 5A1
CHUNKS = {}
CHUNKS["5A1"] = [
    {"title": "运营紧急状态", "type": "definition", "parent": None, "pages": ("1", "5A1-1"),
     "content": "运营紧急状态：列车分离属于运营紧急状态。"},
    {"title": "参考", "type": "notice", "parent": None, "pages": ("1", "5A1-1"),
     "content": "参考：有关运营紧急状态的控制程序，请参见本手册第 2 章。"},
]
_proc_lines = [LEAD_5A1]
for _it in STEPS_5A1:
    if _it[0] == "group":
        _proc_lines.append(_it[1])
    else:
        _, _no, _owner, _act = _it
        _proc_lines.append("步骤：%s；负责人员：%s；行动：%s" % (_no, _owner, _act))
CHUNKS["5A1"].append({"title": "处理分离列车", "type": "procedure", "parent": None,
                      "pages": ("1-3", "5A1-1~5A1-3"), "content": "\n".join(_proc_lines)})
for _it in STEPS_5A1:
    if _it[0] != "step":
        continue
    _, _no, _owner, _act = _it
    CHUNKS["5A1"].append({
        "title": "处理分离列车-步骤%s" % _no, "type": "procedure_step", "parent": 2,
        "pages": ("1-3", "5A1-1~5A1-3"),
        "content": "步骤：%s；负责人员：%s；行动：%s" % (_no, _owner, _act)})

# ---------------------------------------------------------------- 5A2
CHUNKS["5A2"] = [
    {"title": "何时可移动分离列车", "type": "list", "parent": None, "pages": ("4", "5A2-1"),
     "content": "在任何情况下都不能移动分离列车的任何部分，直至：\n"
                "- 一切查勘、救援及公安的调查工作已完成；\n- 轨道已清理妥当。"},
    {"title": "移动分离列车指引", "type": "list", "parent": None, "pages": ("4", "5A2-1"),
     "content": "当勘查及救援工作完毕，轨道也清理完毕后，必须将列车移往最接近的车辆段/停车场或侧线。\n"
                "移动分离的列车时须遵照以下要求：\n"
                "- 事故处理主任在咨询过事故工程师后，须按事故处理主任的指示将列车分段或整列移走；\n"
                "- 不得钩接列车分离部分；\n"
                "- 列车头段若不能开动，须从车头将列车拖走；\n"
                "- 列车尾段若不能开动，须从车尾将列车推走。"},
]

SECTIONS = {"5A1": S5A1, "5A2": S5A2}
ORDER = ["5A1", "5A2"]

OUT_DIR.mkdir(parents=True, exist_ok=True)

total = 0
for sec in ORDER:
    specs = CHUNKS[sec]
    ids = ["%s_%s_%03d" % (DOC_ID, sec, i) for i in range(1, len(specs) + 1)]
    lines = []
    for i, spec in enumerate(specs):
        pg, pp = spec["pages"]
        parent = spec["parent"]
        rec = {
            "chunk_id": ids[i],
            "doc_id": DOC_ID,
            "section": SECTIONS[sec],
            "title": spec["title"],
            "type": spec["type"],
            "content": spec["content"],
            "source_page": pg,
            "printed_page": pp,
            "version": VERSION,
            "effective_date": EFFECTIVE_DATE,
            "parent_id": ids[parent] if parent is not None else None,
        }
        lines.append(json.dumps(rec, ensure_ascii=False))
    out = OUT_DIR / ("%s_%s_chunks.jsonl" % (DOC_ID, sec))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    total += len(specs)
    print("%-30s %2d chunks" % (out.name, len(specs)))

print("total: %d chunks in %d files" % (total, len(ORDER)))
