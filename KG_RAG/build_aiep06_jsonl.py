# -*- coding: utf-8 -*-
"""Build AIEP06 JSONL chunks from reviewed markdown.

Source : long_data/AIEP06_RAG/03_markdown_reviewed/*.md
Output : long_data/AIEP06_RAG/04_jsonl/AIEP06_<section>_chunks.jsonl

Page numbering
--------------
AIEP06 has no source PDF (00_raw/ is empty) and no 02_markdown_raw/, so pages
cannot be read from the document. They come from the legacy long-chunk set in
long_chunk_681片_待复核/long_chunk/JKR3_AIEP06_*.txt, which recorded real footers:

    JKR3_AIEP06_0001  6A 引言                PDF页序 1      印刷页码 6A-1
    JKR3_AIEP06_0002  6A 目标                PDF页序 1      印刷页码 6A-1
    JKR3_AIEP06_0003  6B 处理列车脱轨         PDF页序 2,3,4  印刷页码 6B-1,6B-2,6B-3
    JKR3_AIEP06_0004  安排起复及移动事故列车   PDF页序 5      印刷页码 6B-4

The 10 step children of 处理列车脱轨 carry the parent's full 2-4 range: the
table spans three pages and no per-step split is recorded, so a true range is
stated rather than an invented page number.

Notes
-----
* 6B's table has no step 9 - numbering jumps 8 -> 10, as in the original PDF.
  The reviewed file's `> **注**` blockquote explaining this is a reviewer
  annotation, not document text, so it is excluded from content (same treatment
  as `[？]` markers and 复核备注).
* The legacy metadata again records 页脚版次 "1.0,1.1" for the 6B table; the
  schema mandates version "1.0". Settled 2026-09-29: the manual is issued in
  fascicles with no overall version, so a footer marks a revision batch rather
  than a document version - see reports/ragflow_config.md 已知限制.
* 安排起复及移动事故列车 carries no chapter number in its frontmatter section,
  so its chunk_id prefix is the section name, as the requested output filename
  specifies.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "long_data" / "AIEP06_RAG" / "04_jsonl"

DOC_ID = "AIEP06"
VERSION = "1.0"
EFFECTIVE_DATE = "待确认"

S6A = "6A 列车脱轨处理指引"
S6B = "6B 列车脱轨处理"
S_MOVE = "安排起复及移动事故列车"

# ---------------------------------------------------------------- 6A
CHUNKS = {}
CHUNKS["6A"] = [
    {"title": "引言", "type": "text", "parent": None, "pages": ("1", "6A-1"),
     "content": "在正线或车辆段发生列车脱轨事故，并且运营服务受到影响。"},
    {"title": "目标", "type": "list", "parent": None, "pages": ("1", "6A-1"),
     "content": "- 建立标准的处理程序，以指导员工处理列车脱轨事故；\n"
                "- 使中断服务给乘客带来的影响最小化；\n"
                "- 处理任何的乘客受伤及/或其他情况。"},
]

# ---------------------------------------------------------------- 6B
STEPS_6B = [
    ("step", "1", "事故列车的驾驶员",
     "- 通知行车调度员以下细节：\n"
     "  - 发生列车脱轨事故\n  - 列车的车次及车号\n  - 事故列车所处的位置\n"
     "  - 事故列车是否阻塞其它轨道\n  - 是否有乘客受伤\n"
     "- 如果广播系统仍然可以使用，通知乘客列车出现故障，并要求乘客停留在车厢内直至救援人员前来"),
    ("step", "2", "行车调度员",
     "- 若上行轨道与下行轨道之间并无隧道墙分隔，安排停止相邻轨道的行车\n"
     "- 将尾随事故列车的所有列车留在车站站台，避免有列车滞留在两站之间\n"
     "- 指导事故列车的驾驶员离开驾驶室并且穿行整列车厢以寻找任何有关分离的迹象\n"
     "- 将事故情况通知正线上所有列车驾驶员及预计会延误多久\n"
     "- 要求值班经理召唤紧急救援队，并告知其尽可能多的细节信息，以便紧急救援队决定采取何种适合的行动"),
    ("step", "3", "事故列车的驾驶员",
     "- 通知乘客列车发生脱轨事故，驾驶员应离开驾驶室并穿行列车\n"
     "- 携带无线电手持台穿过车厢前往列车尾部，通知乘客列车故障，并要求乘客在停留在车厢内直至救援人员前来\n"
     "- 在检查后，通知行车调度员以下细节：\n"
     "  - 脱轨的程度，其中包括脱轨的车厢编号，以及旁边的轨道是否受到影响\n"
     "  - 任何可掌握的事故细节\n  - 列车所载乘客的大致数量\n"
     "- 若发生人员伤亡，则应陪同其直至救援人员到来；若无人员伤亡，返回列车驾驶室等待救援人员"),
    ("step", "4", "行车调度员",
     "- 通知值班经理进一步的事故消息\n- 如果其他轨道受到事故列车影响，实施必要的降级运行"),
    ("step", "5", "值班经理",
     "- 宣布进入运营紧急状态\n- 召唤车辆段控制中心派出紧急救援队进行救援行动\n"
     "- 通知故障报警中心发生该事故\n- 通知乘务管理员指派人员前往事故现场以支持救援行动"),
    ("step", "6", "故障报警中心",
     "- 通知事故工程师前往事发地点进行处理\n- 召唤相应的工程人员以便协助救援工作"),
    ("step", "7", "行车调度员", "通知事故处理主任：\n- 事故的准确地点\n- 安排车站员工前往协助"),
    ("step", "8", "有关的值班站长", "- 亮起隧道灯\n- 关闭风机\n- 做好相关的保护措施"),
    ("step", "10", "事故列车驾驶员",
     "- 等待车站员工到场协助清人及任何所需的救援工作\n- 留在事故列车附近以便协助调查工作"),
    ("step", "11", "行车调度员", "与值班经理就所需的降级运行方案达成共识"),
]

LEAD_6B = "当列车脱轨发生在正线上时，应遵循以下程序："
_6b_lines = [LEAD_6B] + [
    "步骤：%s；负责人员：%s；行动：%s" % (no, owner, act) for _, no, owner, act in STEPS_6B]
CHUNKS["6B"] = [
    {"title": "处理列车脱轨", "type": "procedure", "parent": None,
     "pages": ("2-4", "6B-1~6B-3"), "content": "\n".join(_6b_lines)},
]
for _no, _owner, _act in [(s[1], s[2], s[3]) for s in STEPS_6B]:
    CHUNKS["6B"].append({
        "title": "处理列车脱轨-步骤%s" % _no, "type": "procedure_step", "parent": 0,
        "pages": ("2-4", "6B-1~6B-3"),
        "content": "步骤：%s；负责人员：%s；行动：%s" % (_no, _owner, _act)})

# ---------------------------------------------------------------- 安排起复及移动事故列车
CHUNKS["安排起复及移动事故列车"] = [
    {"title": S_MOVE, "type": "list", "parent": None, "pages": ("5", "6B-4"),
     "content": "- 事故工程师应与事故处理主任就列车脱轨处理达成共识并确保已经为执行救援和起复的员工做好全部的安全防护准备。\n"
                "- 若事故列车影响到其他系统的运作，例如接触轨或轨道。事故工程师必须在进行列车起复前就该问题与其他有关工程师达成共识。\n"
                "- 当事故列车起复成功后，事故处理主任必须与事故工程师就移动事故列车的最佳方式达成一致。\n"
                "- 当满足以下情况后，方可移动事故的列车：\n"
                "  - 所有检查、救援、调查工作已经完成；\n  - 线路出清已完毕。\n"
                "- 在移动事故列车前，应取得事故处理主任授权并取得事故工程师确认。\n"
                "- 在移动事故列车前，应进行线路出清和轨道检查以确保安全。"},
]

SECTIONS = {"6A": S6A, "6B": S6B, "安排起复及移动事故列车": S_MOVE}
ORDER = ["6A", "6B", "安排起复及移动事故列车"]

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
    print("%-46s %2d chunks" % (out.name, len(specs)))

print("total: %d chunks in %d files" % (total, len(ORDER)))
