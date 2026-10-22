#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice AIEP10 (处理车辆段/停车场失火) into RAG JSONL chunks.

Input   long_data/AIEP10_RAG/03_markdown_reviewed/*.md   (14 files, status: verified)
Output  long_data/AIEP10_RAG/04_jsonl/AIEP10_<code>_chunks.jsonl   (14 files)

Three of the reviewed files each hold several manual sections, and are named
after all of them: 10B4-10B7 驻守人员 (four sections), 10B8-10B9 (two), and
10B10-10B12 (three). They still produce one JSONL per file, and each chunk's
``section`` names the 小节 it actually came from.

Sources of each field
---------------------
* content / title / section - verbatim from the reviewed markdown. Nothing is
  reworded, reordered or summarised; the review artefacts are dropped (rule 4):
  every 复核备注 block, including the two that describe the flowchart
  conversion and the 10D2-10D4 proofreading. ``<br>`` inside a table cell
  becomes a newline; ``**`` bold markers are dropped and the label kept
  (``**注意：**`` -> ``注意：``).
* source_page / printed_page - from the third-version long chunk set
  (``long_chunk_681片_待复核/long_chunk/JKR3_AIEP10_*.txt``), which carries
  ``PDF页序`` / ``印刷页码`` per topic. It covers all 30 pages of the manual and
  every topic in the reviewed markdown, so no page is interpolated. The reviewed
  markdown has no page footers and no front-matter page fields, and the source
  PDF is a scan, so this legacy metadata is the only available provenance and
  could not be re-verified against the PDF.
* version - written as ``1.0`` for the whole document, following AIEP05-09.
  The legacy footers say pages 16 (10B5-1), 29 (10D3-1) and 30 (10D4-1) carry
  1.1 and the other 27 pages 1.0; recording that per page would raise a W14
  version warning per section, so the uniform value is kept. Settled
  2026-09-29: the manual is issued in fascicles with no overall version, so a
  page footer marks that page's revision batch, not a document version - see
  closed item A13 in ``long_data/reports/aiep_todo.md``.
* effective_date - 待确认, as everywhere else in the corpus.

Type policy (same six rules as AIEP08/09)
----------------------------------------
1. A table with a 步骤 column -> one ``procedure`` parent holding the lead-in
   plus every step verbatim, and one ``procedure_step`` child per step, with
   ``parent_id`` pointing at the parent.
2. A table without a 步骤 column -> one ``table_row`` per row, content shaped
   ``表头：值；表头：值``. A non-step table's lead-in is its own ``text`` chunk,
   as in AIEP04_4A2_010.
3. A standalone ``**注意：**`` / ``**重要：**`` block -> one ``notice`` chunk,
   ``title`` 注意/重要, content ``注意：<正文>``. A 注意 inside a table cell
   (10B4 step 1.2) stays in the cell and does not also become a notice chunk.
4. ``X 是指…`` -> ``definition`` (none in this document).
5. A clause whose body is a lead-in line plus bullet points -> ``list``.
6. Introductory and descriptive prose -> ``text``, including 10A1's 流程图走向,
   which is the OCR rendering of a flow chart: kept whole as one chunk rather
   than split, because its nodes are not numbered steps and splitting them
   would invent a step ordering.

Two deviations from the rules above, both requested
--------------------------------------------------
* 10D2/10D3/10D4's three fire-warden rosters are cut as **one ``table_row``
  chunk per depot**, not one per row, so a row like 停车库 / 值班维修工程师
  keeps its depot in context. The depot name itself is not synthesised into the
  content: it lives in the chunk's ``section`` ("10D2 马家堡车辆段") and in the
  lead-in ``text`` chunk ("以下是马家堡车辆段的火警纠察安排表："). ``table_row``
  is kept rather than ``text`` so the tabular signal survives downstream, even
  though the chunk holds a whole table.
* The 10B4-10B7 step tables have **phase separator rows** ("1. 消防人员到场前"
  with an empty action cell) between groups of steps. A phase row is a label,
  not a step, so it becomes a line of the ``procedure`` parent's content and
  gets no ``procedure_step`` child of its own.

Known deviations / open items
-----------------------------
Every item below is logged in ``long_data/reports/aiep_todo.md`` (A13-A17), which
is the master ledger; when one is resolved, remove the matching note here too.
* 10D4 ends with two bullets ("火警纠察任命前应进行培训；每年需进行培训内容
  的回顾。") that sit under no heading of their own, so they take 10D4's section
  and the nearest heading as title. They read as general rules about fire-warden
  appointment rather than as South Zhaolu-specific ones.
* 10A5's step 3 cites 本章 10B4 while step 5 cites 本章 10B, and the reviewed
  file's own 复核备注 flags the difference as unconfirmed.
* 10A1's 流程图走向 is a conversion from a screenshot (its 复核备注 says so);
  the conversion is not reproducible from the PDF here, so the text is taken as
  reviewed.
* 10B11's 驾驶员的职责 says 下表 but the markdown body is a bullet list, not a
  table; the chunks follow the body (``list``).
"""

import json
from pathlib import Path

OUT_ROOT = Path(__file__).resolve().parent / "long_data"
DOC = "AIEP10"
VERSION = "1.0"
EFFECTIVE_DATE = "待确认"


def C(section, title, type_, content, source_page, printed_page, _parent=None):
    return {"section": section, "title": title, "type": type_, "content": content,
            "source_page": source_page, "printed_page": printed_page, "_parent": _parent}


def steps(section, title, lead, rows, source_page, printed_page):
    """[parent, *children] for a 步骤 table. rows: (n, owner|None, action)."""
    lines = []
    for n, owner, action in rows:
        if owner is None:
            lines.append("步骤：%s；行动：%s" % (n, action))
        else:
            lines.append("步骤：%s；负责人员：%s；行动：%s" % (n, owner, action))
    body = "\n".join(lines)
    parent = C(section, title, "procedure", (lead + "\n" + body) if lead else body,
               source_page, printed_page)
    out = [parent]
    for (n, _, _), line in zip(rows, lines):
        out.append(C(section, "%s-步骤%s" % (title, n), "procedure_step", line,
                     source_page, printed_page, _parent=0))
    return out


def phased_steps(section, title, lead, groups, source_page, printed_page):
    """[parent, *children] for a 步骤 table split into phases.

    ``groups`` is [(phase label | None, [(step, action), ...]), ...]. The phase
    label is a row of the table whose action cell is empty; it labels the steps
    under it, so it goes into the parent's content and gets no child.
    """
    body, numbered = [], []
    for label, rows in groups:
        if label is not None:
            body.append(label)
        for n, action in rows:
            line = "步骤：%s；行动：%s" % (n, action)
            body.append(line)
            numbered.append((n, line))
    text = "\n".join(body)
    parent = C(section, title, "procedure", (lead + "\n" + text) if lead else text,
               source_page, printed_page)
    out = [parent]
    for n, line in numbered:
        out.append(C(section, "%s-步骤%s" % (title, n), "procedure_step", line,
                     source_page, printed_page, _parent=0))
    return out


def append(dst, specs):
    """Append a group, shifting its parent references past what is already there."""
    offset = len(dst)
    for s in specs:
        if s["_parent"] is not None:
            s["_parent"] += offset
    dst.extend(specs)
    return dst


def roster(section, chief, lead, title, rows, source_page, printed_page):
    """One depot's fire-warden roster: 总火警纠察, the lead-in, then the table.

    The table is one chunk rather than one per row (see module docstring). The
    depot name is not synthesised into the content: it is in ``section`` and in
    the lead-in, which the markdown supplies verbatim.
    """
    body = "\n".join("区域：%s；位置：%s；火警纠察：%s" % r for r in rows)
    return [C(section, "总火警纠察", "text", chief, source_page, printed_page),
            C(section, title, "text", lead, source_page, printed_page),
            C(section, title, "table_row", body, source_page, printed_page)]


# --------------------------------------------------------------------------- #
# 10A 证实发生火警前                                            PDF 1 / 10A-1
# --------------------------------------------------------------------------- #

def build_10A():
    S = "10A 证实发生火警前"
    return "10A", [
        C(S, "引言", "text",
          "本章说明处理车辆段/停车场响起火警警报或有人报告失火时须遵守的程序。",
          "1", "10A-1"),
        C(S, "负责员工", "list",
          "车辆段/停车场失火时，下列员工均有责任处理火警，或疏散车辆段/停车场内的员工：\n"
          "- 派驻在车辆段/停车场的保安负责人及属下保安员；\n"
          "- 当值高级值班维修工程师；\n"
          "- 车辆段管理员；\n"
          "- 车辆段列车控制主管；\n"
          "- 紧邻失火车辆段/停车场的车站值班站长；\n"
          "- 火警纠察；\n"
          "- 故障报警中心/车辆段调度中心的主管人员。",
          "1", "10A-1"),
        C(S, "参考", "text",
          "处理车辆段/停车场以外地方的火警，请参考本手册第 9 章。",
          "1", "10A-1"),
    ]


# --------------------------------------------------------------------------- #
# 10A1 响起火警警报或接获火警报告                              PDF 2 / 10A1-1
# --------------------------------------------------------------------------- #

def build_10A1():
    S = "10A1 响起火警警报或接获火警报告"
    return "10A1", [
        C(S, "程序", "text",
          "下图说明出现以下情况时的处理过程：\n"
          "- 车辆段/停车场响起火警警报，或\n"
          "- 接获车辆段/停车场火警报告。\n"
          "\n流程图走向：\n"
          "1. 车辆段/停车场响起火警警报，或接获车辆段/停车场火警报告\n"
          "2. ↓ 保安人员通知车辆段列车控制主管及安保部负责人（参见：本节 10A2）\n"
          "3. 分两条并行路径：\n"
          "   - 车辆段列车控制主管召唤紧急服务及通知有关人员（参见：本节 10A2）\n"
          "   - 火警纠察协助没有特别职务的员工撤离该建筑物（参见：本节 10A3 及 A4）\n"
          "4. ↓ 车辆段列车控制主管调派一名人员前往现场：\n"
          "   - 查证火警是否属实，及\n"
          "   - 收集有关火警的资料（参见：本节 10A5）\n"
          "5. ↓ 判断：是否发生火警？\n"
          "   - 否 → 通知有关人员及恢复正常职务\n"
          "   - 是 → 通知有关人员及采取行动（参见：本章 10B）",
          "2", "10A1-1"),
    ]


# --------------------------------------------------------------------------- #
# 10A2 发生火警/响起火警警报时须通知的人员                      PDF 3 / 10A2-1
# --------------------------------------------------------------------------- #

def build_10A2():
    S = "10A2 发生火警/响起火警警报时须通知的人员"
    return "10A2", [
        C(S, "车辆段管理员", "text",
          "故障报警中心内的火警指示灯亮起时，车辆段管理员必须通知安保部保安工作负责人"
          "查证是否同样接到火警警报。",
          "3", "10A2-1"),
        C(S, "车辆段列车控制主管", "list",
          "- 在响起火警警报或接获火警报告时，车辆段列车控制主管必须通知：\n"
          "  - 消防部门；\n"
          "  - 行车调度员；\n"
          "  - 安保部保安工作负责人。\n"
          "- 并必须通知上述人员：\n"
          "  - 准确的受影响位置；\n"
          "  - 已采取的行动。",
          "3", "10A2-1"),
        C(S, "行车调度员", "text",
          "车辆段/停车场响起火警警报或接获火警报告时，行车调度员必须通知值班经理。",
          "3", "10A2-1"),
        C(S, "值班经理", "list",
          "车辆段/停车场响起火警警报或接获火警报告时，值班经理必须通知：\n"
          "- 可直接通往该车辆段的车站的值班站长；\n"
          "- 消防部门、急救部门，以及公安局公交总队。",
          "3", "10A2-1"),
        C(S, "注意", "notice",
          "注意：若最后证实是火警警报误鸣，值班经理须立即通知上述各单位/人员。",
          "3", "10A2-1"),
        C(S, "参考", "text",
          "有关报告车辆段/停车场响起火警警报或车辆段/停车场失火的程序，请参见本手册 10B。",
          "3", "10A2-1"),
    ]


# --------------------------------------------------------------------------- #
# 10A3 火警纠察                                                 PDF 4 / 10A3-1
# --------------------------------------------------------------------------- #

def build_10A3():
    S = "10A3 火警纠察"
    recs = []
    append(recs, steps(S, "响起火警警报时",
        "下表说明响起火警警报时，火警纠察及总火警纠察须采取的行动：",
        [(1, "火警纠察", "离开前确保所有人员已撤离所负责的范围"),
         (2, "火警纠察", "- 前往集合地点\n- 向总火警纠察报告"),
         (3, "火警纠察",
          "向总火警纠察报告负责范围的疏散情况，包括是否有人：\n"
          "- 未前往集合地点报到\n- 被困，或\n- 受伤")],
        "4", "10A3-1"))
    recs.append(C(S, "车辆段/停车场的火警纠察", "text",
                  "有关各车辆段/停车场的火警纠察的详情，请参见本章 10D1 至 10D3 火警纠察名单。",
                  "4", "10A3-1"))
    return "10A3", recs


# --------------------------------------------------------------------------- #
# 10A4 疏散指引                                                 PDF 5 / 10A4-1
# --------------------------------------------------------------------------- #

def build_10A4():
    S = "10A4 疏散指引"
    return "10A4", [
        C(S, "一般指引", "list",
          "响起火警警报时，除获派特别职务者外，车辆段/停车场内所有人员必须：\n"
          "- 停止工作并关掉所有设备；\n"
          "- 在安全情况下，关好所有门窗，但不要上锁；\n"
          "- 在安全情况下，将任何没有存放在危险品仓库的危险品移到空旷地方，尤其是：\n"
          "  - 爆炸品；\n"
          "  - 压缩气体。\n"
          "- 有秩序而镇定地沿着指定的逃生路线，疏散到指定的集合地点，然后；\n"
          "- 在集合地点等候火警纠察的进一步指示。\n"
          "\n参考：有关火警纠察的详情，请参见本节 10A3。",
          "5", "10A4-1"),
        C(S, "逃生路线及集合地点", "list",
          "指定的逃生路线及集合地点平面图张贴于：\n"
          "- 安全门旁；\n"
          "- 车辆段/停车场内其它显眼位置。",
          "5", "10A4-1"),
        C(S, "有特别职务的员工", "list",
          "- 响起火警警报时，以下员工须执行特别职务：\n"
          "  - 列车上的驾驶员；\n"
          "  - 故障报警中心内的员工；\n"
          "  - 车辆段调度中心/信号楼内的员工。\n"
          "- 上述人员必须：\n"
          "  - 在安全情况下留守原处；\n"
          "  - 按有关负责人的指示采取行动。",
          "5", "10A4-1"),
    ]


# --------------------------------------------------------------------------- #
# 10A5 查证是否发生火警                                 PDF 6-7 / 10A5-1..10A5-2
# --------------------------------------------------------------------------- #

def build_10A5():
    S = "10A5 查证是否发生火警"
    recs = []
    append(recs, steps(S, "程序",
        "响起火警警报时，车辆段列车控制主管及其员工必须遵照下表的程序，确定火警警报是否属实。",
        [(1, "车辆段列车控制主管",
          "指派 1 名人员前赴响起火警警报的现场：\n"
          "- 查看是否发生火警\n- 在指定的时间内报告有关情况"),
         (2, "被派前赴现场人员",
          "- 带上以下物品前赴现场：\n"
          "  - 无线电手持台\n"
          "  - 手提灭火器（如可行）\n"
          "- 找出响起火警警报的原因"),
         (3, "被派前赴现场人员",
          "是否发生火警：\n"
          "- 若是：\n"
          "  - 在指定的时间内，向车辆段列车控制主管报告所需的详细资料\n"
          "  - 遵照本章 10B4 的程序\n"
          "- 若否：\n"
          "  - 若知道响起火警警报的原因，在指定的时间内向车辆段列车控制主管报告\n"
          "  - 返回工作岗位"),
         (4, "车辆段列车控制主管",
          "在指定时间内，是否接获前往警报现场人员的报告：\n"
          "- 若是，进行步骤 5\n- 若否，指派另一名人员前往现场。重复步骤 2 及 3"),
         (5, "车辆段列车控制主管",
          "是否发生火警：\n"
          "- 若是：\n"
          "  - 将有关发现通知行车调度员\n"
          "  - 遵照本章 10B 的程序\n"
          "- 若否：\n"
          "  - 将有关发现通知行车调度员\n"
          "  - 通知有关人员所接获的火警警报只属误报\n"
          "  - 指派 1 名安保部保安前往车辆段/停车场正门接应消防部门的人员")],
        "6", "10A5-1"))
    recs.append(C(S, "被指派的人员查证后的报告", "list",
                  "经查看火警警报现场并确定火警警报属实后，被指派人员必须立即向"
                  "车辆段列车控制主管报告下列资料：\n"
                  "- 警报的起因；\n"
                  "- 起火的确实地点及可能受影响的范围；\n"
                  "- 火警的性质，例如，正在焚烧或可能被焚烧的物料；\n"
                  "- 受阻的轨道；\n"
                  "- 受影响的列车；\n"
                  "- 受伤及损坏程度；\n"
                  "- 灭火及探测设备的状况；\n"
                  "- 灭火工作的进展；\n"
                  "- 是否需要紧急服务。",
                  "7", "10A5-2"))
    return "10A5", recs


# --------------------------------------------------------------------------- #
# 10B1 证实发生火警后须通知的人员                      PDF 8-9 / 10B1-1..10B1-2
# --------------------------------------------------------------------------- #

def build_10B1():
    S = "10B1 证实发生火警后须通知的人员"
    return "10B1", [
        C(S, "车辆段列车控制主管", "list",
          "证实发生火警后，车辆段列车控制主管必须通知：\n"
          "- 行车调度员；\n- 车辆段经理/高级值班维修工程师。",
          "8", "10B1-1"),
        C(S, "行车调度员", "list",
          "证实发生火警后，行车调度员必须通知：\n"
          "- 值班经理；\n"
          "- 行车信息助理；\n"
          "- 事故处理主任；\n"
          "- 车辆段管理员；\n"
          "- 乘务排班室的乘务督导员；\n"
          "- 车辆段调度中心/故障报警中心；\n"
          "- 可直接前往车辆段/停车场的值班站长；\n"
          "- 消防部门和公安局公交总队。",
          "8", "10B1-1"),
        C(S, "值班经理", "text",
          "证实发生火警后，值班经理必须通知：消防部门、急救部门和公安局公交总队。",
          "8", "10B1-1"),
        C(S, "车辆段负责人员", "list",
          "接获行车调度员通知发生火警后，车辆段负责人员必须按下述通知有关人员：\n"
          "- 若火势影响或有可能影响仓库（车辆段），须通知当值仓务主管。\n"
          "- 若火势影响或有可能影响食堂（车辆段/停车场），须通知行政及保安负责人。\n"
          "- 若火势影响或有可能影响培训中心（停车场），须通知培训经理（运营）。\n"
          "- 若火势影响或有可能影响行政办公楼，须通知行政及保安负责人。\n"
          "- 若火势影响或有可能影响司乘公寓（车辆段/停车场），须通知行政公寓值班主管。",
          "9", "10B1-2"),
    ]


# --------------------------------------------------------------------------- #
# 10B2 事故控制                                       PDF 10-12 / 10B2-1..10B2-3
# --------------------------------------------------------------------------- #

def build_10B2():
    S = "10B2 事故控制"
    return "10B2", [
        C(S, "现场主管", "text",
          "证实发生火警后，当值主管工程师须负责监督相关工作，直至所指派的人员前来接替。",
          "10", "10B2-1"),
        C(S, "安保部保安工作负责人", "list",
          "安保部保安工作负责人或安保经理所指派的人员必须尽快：\n"
          "- 前往现场报到。\n"
          "- 采取行政措施重新编配或加强保安的人手，例如，从其它地方抽调保安警卫。",
          "10", "10B2-1"),
        C(S, "当值高级值班维修工程师须采取的行动", "list",
          "证实发生火警后，当值高级值班维修工程师必须往现场报到，并：\n"
          "- 立刻履行事故处理主任的职责，直至被正式接替为止。\n"
          "- 负责联络工作直至被正式接替为止。\n"
          "- 按下述调派员工：\n"
          "  - 若车辆段列车控制主管未有时间带上/穿戴以下物品前赴现场：无线电手持台、"
          "反光背心，须指派 1 名员工将该等物品交给车辆段列车控制主管；\n"
          "  - 若车辆段列车控制主管不在场，须确保车辆段调度中心的现场主管已指派"
          "值班维修技术督导员：暂代车辆段列车控制主管一职，执行车辆段列车控制主管所有职责。\n"
          "\n参考：有关事故处理主任的角色及职责，请参见本手册 2B2。",
          "10", "10B2-1"),
        C(S, "车辆段列车控制主管应采取的行动", "list",
          "证实发生火警时，车辆段列车控制主管必须：\n"
          "- 带上无线电手持台。\n"
          "- 穿戴：反光背心。\n"
          "- 前往火警现场报到及评估情况。\n"
          "- 使用无线电手持台，向现场的主管报告当时身处的地点。\n"
          "- 收到安保部保安通知第一辆消防部门车辆将抵达时，在车辆通道的约定位置接应"
          "或指派一名人员接应该车辆。\n"
          "- 通知消防部门的主管下列安排：\n"
          "  - 路面行车安排（请参见本节 10B8）；\n"
          "  - 消防部门车辆进出车辆段/停车场的安排；\n"
          "  - 牵引电流的安排（请参见本节 10B9）；\n"
          "  - 通风设备的安排。\n"
          "- 留守现场与消防人员协调工作，直至：\n"
          "  - 事故完满解决；\n"
          "  - 消防人员撤离车辆段/停车场。",
          "11", "10B2-2"),
        C(S, "注意", "notice",
          "注意：在紧急情况下，如车辆段列车控制主管不在场，"
          "车辆段调度中心的值班维修技术督导员必须暂代车辆段列车控制主管执行上述职责。",
          "11", "10B2-2"),
        C(S, "安保部负责人", "list",
          "若公安的现场主管要求安保部负责保安工作的负责人陪同前往火警现场，"
          "安保部负责保安工作的负责人必须：\n"
          "- 指派 1 名员工陪同该现场主管前往火警现场；\n"
          "- 立刻通知车辆段列车控制主管。",
          "12", "10B2-3"),
        C(S, "通信", "list",
          "必须建立并维持下列有效的通信方式：\n"
          "- 车辆段列车控制主管与消防部门现场主管须商定联络方式，例如：\n"
          "  - 当面对话，或\n"
          "  - 通过安保部保安传递信息。\n"
          "- 下列人员须利用无线电通信：\n"
          "  - 安保部；\n"
          "  - 车辆段列车控制主管；\n"
          "  - 参与处理事故的所有员工。",
          "12", "10B2-3"),
        C(S, "使用呼吸装置的范围", "list",
          "若消防部门现场主管进入了须使用呼吸装置的范围：\n"
          "- 车辆段列车控制主管必须留在该范围入口。\n"
          "- 须派 1 名保安人员驻守该入口，负责为消防部门现场主管及车辆段列车控制主管传递消息。",
          "12", "10B2-3"),
    ]


# --------------------------------------------------------------------------- #
# 10B3 现场主管                                       PDF 13-14 / 10B3-1..10B3-2
# --------------------------------------------------------------------------- #

def build_10B3():
    S = "10B3 现场主管"
    recs = []
    append(recs, steps(S, "消防部门人员到场前的程序", "",
        [(1, None,
          "指派安保部保安驻守：\n"
          "- 火警现场，执行本节 10B4 内详述的职责\n"
          "- 车辆段/停车场正门，执行本节 10B5 内详述的职责"),
         (2, None,
          "- 确保 1 名安保部保安在行人闸口当值\n"
          "- 指示该名保安执行本节 10B6 内详述的职责"),
         (3, None, "安排将有关的荧光服交给事故处理主任"),
         (4, None,
          "指派 1 名安保部保安，在车辆段/停车场正门对入位置，"
          "张贴一张印有「车辆段/停车场紧急事故，员工一律到集合地点报到」字句的警告告示")],
        "13", "10B3-1"))
    recs.append(C(S, "其它负责事项", "list",
                  "现场主管可能需要按情况履行下表所列的其它职责。\n"
                  "\n- 若车辆段/停车场设有紧急出入闸，便须确保在需要时，"
                  "有 1 名安保部保安前去开闸。\n"
                  "\n参考：详情请参见本节 10B7。\n"
                  "\n- 若出入通道因任何理由被阻塞，便须通知下列人员：\n"
                  "  - 车辆段列车控制主管；\n"
                  "  - 事故处理主任；\n"
                  "  - 负责护送任务的安保部保安；\n"
                  "  - 派驻车辆段/停车场正门的安保部保安。",
                  "13", "10B3-1"))
    append(recs, steps(S, "消防部门人员到场后的程序",
        "消防的人员抵达后，现场主管必须遵照以下程序。",
        [(1, None,
          "向消防人员报告情况，包括：\n"
          "- 任何伤亡资料\n"
          "- 该范围内有什么潜在危险，例如带电的设备\n"
          "- 灭火设备的位置，例如消防龙头及灭火筒\n"
          "- 车辆段/停车场内通往火场的安全通道"),
         (2, None,
          "安排将合适的荧光服交给以下的现场主管：\n"
          "- 消防部门\n- 公安人员或者消防人员\n- 救护车服务")],
        "14", "10B3-2"))
    recs.append(C(S, "灭火期间", "list",
                  "灭火期间，现场主管必须完成以下职务。\n"
                  "\n- 若操作了任何花洒、水帘、通风扇或风闸或使用了惰性气体，"
                  "应通知车辆段列车控制主管，及事故处理主任。\n"
                  "- 若消防部门要求操作有关通风系统的设备，应遵照消防部门要求处理。",
                  "14", "10B3-2"))
    return "10B3", recs


# --------------------------------------------------------------------------- #
# 10B4-10B7 驻守人员                                PDF 15-18 / 10B4-1..10B7-1
# --------------------------------------------------------------------------- #

def build_10B4_10B7():
    recs = []
    S4 = "10B4 驻守火警现场的人员"
    append(recs, phased_steps(S4, "程序",
        "驻守在火警现场的安保部保安必须遵照以下程序：",
        [("1. 消防人员到场前", [
            ("1.1", "协助任何在火场中的伤者"),
            ("1.2", "在安全的情况下，以一切可行的方法灭火\n"
                    "注意：\n若轨道范围失火，并可能由接地轨道扣件引起，"
                    "须遵照本手册 9E「处理接地轨道扣件引起的火警」的步骤（最后一项除外）"),
            ("1.3", "若出现以下情况，操作手动喷气装置：\n"
                    "- 设有自动灭火设备的房间失火\n"
                    "- 无迹象显示自动灭火设备已开始自动操作")]),
         ("2. 消防人员到场后", [("2.1", "将灭火的最新情况通知现场主管")])],
        "15", "10B4-1"))

    S5 = "10B5 驻守车辆段/停车场正门的人员"
    append(recs, phased_steps(S5, "程序",
        "驻守车辆段/停车场正门的安保部保安必须遵照以下程序：",
        [("1. 消防人员到场前", [("1.1", "保持车辆段/停车场正门畅通无阻")]),
         ("2. 消防人员到场后", [
             ("2.1", "是否有人员为消防部门车辆引路：\n"
                     "- 若是，程序到此完结\n"
                     "- 若否，将前往车辆段列车控制主管所在地点的路线告知该消防车辆司机")])],
        "16", "10B5-1"))
    recs.append(C(S5, "在车辆段/停车场正门当值指引", "list",
                  "安保部保安在车辆段/停车场正门当值期间，必须遵照下列指引：\n"
                  "- 指示任何已进入车辆段/停车场的人：\n"
                  "  - 前往集合地点；\n"
                  "  - 等候现场主管的进一步指示。\n"
                  "- 禁止任何人/车辆进入车辆段/停车场，处理事故的有关人员/车辆除外。\n"
                  "- 照常准许车辆驶离车辆段/停车场。\n"
                  "- 勿让公众人士接近车辆段/停车场。\n"
                  "- 阻止记者、电台或电视台的工作人员进入车辆段/停车场，除非有以下人员陪同：\n"
                  "  - 政府关系部员工，或\n"
                  "  - 高级运营/工程执行人员。\n"
                  "- 记录出入车辆段/停车场的紧急救援车辆数目，然后报知现场主管。",
                  "16", "10B5-1"))

    S6 = "10B6 驻守行人闸口的人员"
    append(recs, phased_steps(S6, "程序",
        "驻守在行人闸口的安保部保安必须遵照以下程序：",
        [("1. 消防人员到场前", [
            ("1.1", "关闭行人闸"),
            ("1.2", "向安保部报到"),
            ("1.3", "与车辆段列车控制主管商定一处合适位置作为车辆进出的通道，"
                    "以便车辆段列车控制主管或其指派人员在该处接应第一辆消防部门车辆"),
            ("1.4", "带上：\n- 无线电手持台\n- 所拟定通道上手控升降横栏的钥匙"),
            ("1.5", "前往车辆段/停车场正门"),
            ("1.6", "在车辆段/停车场正门等候，准备：\n- 执行带领任务\n- 按现场主管的指示行动")]),
         ("2. 消防人员到场后", [
             ("2.1", "通知车辆段列车控制主管"),
             ("2.2", "指示司机将车辆驶往商定的地点"),
             ("2.3", "获车辆段列车控制主管授权后，将沿途的手控升降横栏升起"),
             ("2.4", "告知消防部门车辆上的人员沿途会有的潜在危险，尤其是带电的设备"),
             ("2.5", "消防人员是否需要前往轨道？\n"
                     "- 若是：\n"
                     "  - 取得车辆段列车控制主管的授权\n"
                     "  - 在消防人员前往轨道时，充当瞭望员提供保护\n"
                     "- 若否，程序到此完结")])],
        "17", "10B6-1"))

    S7 = "10B7 驻守紧急出入闸的人员"
    append(recs, phased_steps(S7, "程序",
        "安保部保安如获安保部负责保安工作的负责人指派，前往车辆段/停车场的紧急出入闸"
        "接应消防部门车辆时，必须遵照以下程序。",
        [("1. 消防人员到场前", [
            ("1.1", "带上无线电手持台"),
            ("1.2", "领取紧急出入闸的钥匙"),
            ("1.3", "与车辆段列车控制主管确定：\n- 消防部门车辆的出入路线\n- 停泊地点"),
            ("1.4", "是否需要升起手控升降横栏：\n"
                    "- 若是：\n"
                    "  - 领取有关横栏的钥匙\n"
                    "  - 打开出入路线沿途横栏的锁并把横栏升起\n"
                    "  - 前往紧急出入闸\n"
                    "  - 进行步骤 1.5\n"
                    "- 若否，进行步骤 1.5"),
            ("1.5", "打开紧急出入闸，等候消防部门车辆到达")]),
         ("2. 消防人员到场后", [
             ("2.1", "通知消防部门：\n- 出入路线\n- 停泊地点"),
             ("2.2", "消防车辆是否需要横越轨道：\n"
                     "- 若是：\n"
                     "  - 先取得车辆段列车控制主管的授权，然后才让车辆驶离紧急出入闸的范围\n"
                     "  - 进行步骤 2.3\n"
                     "- 若否，进行步骤 2.3"),
             ("2.3", "指示他们沿出入路线前往停泊地点")])],
        "18", "10B7-1"))
    return "10B4-10B7", recs


# --------------------------------------------------------------------------- #
# 10B8-10B9 行车与牵引电流                          PDF 19-21 / 10B8-1..10B9-2
# --------------------------------------------------------------------------- #

def build_10B8_10B9():
    S8 = "10B8 行车"
    recs = [
        C(S8, "停止行车", "list",
          "火势危及车辆段/停车场轨道或行车安全时，车辆段列车控制主管必须指示车辆段管理员"
          "停止列车在车辆段/停车场内行走。准备开动或正在行走的列车必须停驶。\n"
          "\n列车必须驶离：\n- 行人道，或\n- 平交道口。",
          "19", "10B8-1"),
        C(S8, "协议行车安排", "list",
          "下述人员必须参与商议列车进出车辆段/停车场的安排或限制：\n"
          "- 行车调度员；\n- 车辆段列车控制主管；\n- 车辆段管理员。",
          "19", "10B8-1"),
        C(S8, "列车离开车辆段", "list",
          "车辆段列车控制主管只可在以下情况授权列车离开车辆段/停车场，提供载客服务：\n"
          "- 行车不阻碍消防人员出入事发现场，或\n"
          "- 已就行车安排与消防部门现场主管达成共识。",
          "19", "10B8-1"),
        C(S8, "列车进入车辆段/停车场", "list",
          "所有列车一律不准驶入车辆段/停车场，除非车辆段列车控制主管征询以下人员后允许进入：\n"
          "- 事故处理主任；\n"
          "- 消防部门现场主管。\n"
          "\n列车不获准进入车辆段/停车场时，行车调度员必须安排该列车：\n"
          "- 继续提供载客服务，或\n"
          "- 暂时停放在：\n"
          "  - 侧线上，或\n"
          "  - 终点站。",
          "19", "10B8-1"),
    ]
    S9 = "10B9 牵引电流的安排"
    recs += [
        C(S9, "牵引电流供应", "list",
          "全车辆段/停车场必须维持牵引电流供应，除非个别设备：\n"
          "- 有危险，或\n- 危及车辆段/停车场内人员的安全。",
          "20", "10B9-1"),
        C(S9, "谁授权开关", "text",
          "凡开关牵引电流必须由车辆段列车控制主管授权，而车辆段管理员亦须同时获悉有关安排。",
          "20", "10B9-1"),
    ]
    append(recs, steps(S9, "由中央关断",
        "车辆段/停车场发生火警时，若不需要由当地关断或隔离牵引电流，"
        "须遵照以下程序将牵引电流截断：",
        [(1, None, "车辆段列车控制主管指示车辆段管理员要求系统调度员，将有关轨道的牵引电源截断"),
         (2, None, "车辆段管理员要求系统调度员按指示截断牵引电流"),
         (3, None, "系统调度员：\n- 截断有关轨道的牵引电流\n- 将安排告知车辆段管理员"),
         (4, None, "车辆段管理员通知车辆段列车控制主管已将牵引电流截断"),
         (5, None,
          "车辆段列车控制主管：\n"
          "- 用试电棒测试已截断电流的接触轨设备\n"
          "- 将有关安排告知消防部门现场主管\n"
          "- 清楚说明断电区的界限\n"
          "- 安排在隔离点装设接地棒")],
        "20", "10B9-1"))
    append(recs, steps(S9, "当地关断",
        "车辆段/停车场发生火警时，若须由当地关断或隔离牵引电流，"
        "车辆段列车控制主管须遵照以下程序：",
        [(1, None, "向系统调度员查询由当地关断或隔离有关轨道的牵引电流所需的安排"),
         (2, None, "进行当地关断或隔离"),
         (3, None, "用试电棒测试已关断电流的接触轨设备"),
         (4, None, "在隔离点装设接地棒"),
         (5, None, "将有关安排通知消防部门现场主管，并清楚说明断电区的界限")],
        "21", "10B9-2"))
    return "10B8-10B9", recs


# --------------------------------------------------------------------------- #
# 10B10-10B12 OCC 员工与乘务站务与调度中心                  PDF 22-24 / *_1
# --------------------------------------------------------------------------- #

def build_10B10_10B12():
    S10 = "10B10 OCC 员工"
    recs = [
        C(S10, "值班经理的职责", "list",
          "证实发生火警后，值班经理必须按照下述执行有关程序：\n"
          "- 若消防部门要求开启车辆段/停车场紧急出入闸，让消防车辆驶入，"
          "值班经理须通知安保部负责人，并要求车辆段人员等候，以配合其工作。\n"
          "- 若火势演变成一类延误及以上的事故时，"
          "值班经理须遵照本手册 1C5 及第 2 章的规定通知行政经理。",
          "22", "10B10-1"),
        C(S10, "行车调度员", "list",
          "证实发生火警后，行车调度员必须：\n"
          "- 向有关的车辆段管理员或车辆段列车控制主管查询任何有关列车出入车辆段/停车场的限制。\n"
          "- 为确保紧急故障报告不受中断，接获故障报警中心/车辆段调度中心的现场主管通知后，"
          "应安排通过中央信息发布系统公布各临时中心的地点及联络电话。",
          "22", "10B10-1"),
    ]
    S11 = "10B11 车辆段/停车场内或附近的乘务和站务员工"
    recs += [
        C(S11, "值班站长的职责", "text",
          "证实发生火警后，车辆段/停车场相邻车站的值班站长应尽可能调派员工驻守所有进出点，"
          "防止任何人进入车辆段/停车场。",
          "23", "10B11-1"),
        C(S11, "驾驶员的职责", "list",
          "证实发生火警后，驾驶员必须遵照下表所述的指引。\n"
          "\n- 若列车驾驶员/轨道车技术员在电动列车/工程列车上，便须通过无线电向"
          "车辆段管理员报告，在安全情况下，留在驾驶室内维持无线电接通及随时等候进一步指示。\n"
          "- 若列车驾驶员/轨道车技术员不在电动列车/工程列车上，便应根据何处较接近及安全，"
          "向车辆段调度中心或行政及安保部报到。",
          "23", "10B11-1"),
    ]
    S12 = "10B12 故障报警中心/车辆段调度中心/信号楼"
    recs += [
        C(S12, "员工的安全", "text",
          "所有故障报警中心/车辆段调度中心/信号楼的现场主管必须严禁辖下员工进入受影响范围，"
          "惟直接处理事故者则除外。",
          "24", "10B12-1"),
        C(S12, "车辆段调度中心/信号楼的现场主管", "list",
          "车辆段调度中心的现场主管必须遵照下表指示，并委派 1 名员工在本章 10D2 至 10D3 "
          "所指定的位置，展示写有「平台下现正发生火警，切勿进入平台下范围」字句的警告牌。\n"
          "\n- 若车辆段列车控制主管不在场，必须指派值班维修技术督导员代为执行"
          "车辆段列车控制主管的职务。\n"
          "- 若火势影响轨道，并需要截断接触轨的电流，"
          "必须指派一名员工将 1 支试电棒交给车辆段列车控制主管。",
          "24", "10B12-1"),
    ]
    append(recs, steps(S12, "车辆段管理员应采取的行动",
        "经行政及保安负责人及/或车辆段列车控制主管证实，"
        "发生冒烟或火警并影响车辆段/停车场轨道后，车辆段管理员必须执行下表的程序：",
        [(1, None,
          "使用无线电通话器指示车辆段/停车场内所有在列车上的列车驾驶员：\n"
          "- 尽快将列车停在不阻碍行人道及平交道口的位置\n"
          "- 除非受烟火影响，否则应留在驾驶室内，并维持列车的无线电接通"),
         (2, None,
          "通知行车调度员：\n"
          "- 接获车辆段列车控制主管通知受火警影响的确实地点\n"
          "- 任何有关列车出入车辆段/停车场的限制"),
         (3, None,
          "若火势已演变成一类延误及以上的事故，与车辆段列车控制主管达致共识后，"
          "遵照本手册第 2 章的规定")],
        "24", "10B12-1"))
    return "10B10-10B12", recs


# --------------------------------------------------------------------------- #
# 10C 车辆段/停车场恢复正常运作                      PDF 25-26 / 10C-1..10C-2
# --------------------------------------------------------------------------- #

def build_10C():
    S = "10C 车辆段/停车场恢复正常运作"
    return "10C", [
        C(S, "现场主管", "list",
          "火警扑熄后，现场主管必须按下述通知有关人员：\n"
          "- 在火警扑熄后必须通知行车调度员。\n"
          "- 在集合地点的员工可以安全返回工作岗位时，必须通知在车辆段/停车场正门报到"
          "前往集合地点的员工，及每一名火警纠察，再由他/她转告所负责的人员。",
          "25", "10C-1"),
        C(S, "恢复正常运作前", "list",
          "车辆段/停车场恢复正常运作前，必须先完成以下工作：\n"
          "- 火警纠察必须接获现场主管通知，指示他/她所负责的员工可返回工作岗位。\n"
          "- 车辆段列车控制主管必须安排清理任何损坏的物品及车辆，"
          "及检查所有车辆段/停车场轨道，确保轨道上没有障碍物。\n"
          "- 安保部保安人员必须在火警扑熄，以及消防人员已撤离车辆段/停车场后：\n"
          "  - 确保所有路面车辆已离开轨道范围；\n"
          "  - 升降横栏已放下，并加上挂锁；\n"
          "  - 通知车辆段列车控制主管已查证以上事项。\n"
          "- 结构维护工程师必须检验建筑结构。\n"
          "- 线路维护工程师检验轨道及确定轨道可以安全行车。\n"
          "- 电子维修工程师必须检验接触轨设备，及确定接触轨设备可供使用。",
          "25", "10C-1"),
        C(S, "注意", "notice",
          "注意：\n火警扑熄后，只需详细检查怀疑遭火警损坏的接触轨设备的轨道，其余只需简单检视。",
          "25", "10C-1"),
        C(S, "事故处理主任", "list",
          "以下两项符合事故处理主任的要求，车辆段/停车场可恢复正常运作：\n"
          "- 当时的情况；\n"
          "- 本题目内「恢复正常运作前」所详述的各项工作已完成。",
          "26", "10C-2"),
        C(S, "车辆段列车控制主管的职责", "text",
          "车辆段/停车场将恢复正常运作时，车辆段列车控制主管必须通知所有获悉有关事故的人"
          "事故已告一段落，并已恢复正常运作。",
          "26", "10C-2"),
    ]


# --------------------------------------------------------------------------- #
# 10D 火警纠察名单                     PDF 27-30 / 10D1-1..10D4-1
# --------------------------------------------------------------------------- #

def build_10D():
    SD = "10D 火警纠察名单"
    SD1 = "10D1 车辆段/停车场火警纠察的任命"
    recs = [
        C(SD, "引言", "text",
          "本附录包括各车辆段/停车场的：火警纠察名单。", "27", "10D1-1"),
        C(SD1, "火警纠察是谁", "text",
          "火警纠察是由不同车辆段/停车场组别主管任命，负责在指定的地点内若发生火警，"
          "协助管理人员的安全。其中一名火警纠察会获委派为总火警纠察。",
          "27", "10D1-1"),
        C(SD1, "个人资料", "list",
          "组别主管必须按照下表所述将火警纠察的详细资料交给行政及保安督导员：\n"
          "- 若火警纠察是在办公时间内工作：须通知行政及保安督导员该名火警纠察的姓名、"
          "职位及联络电话。\n"
          "- 若火警纠察需轮班，须通知行政及保安督导员该名火警纠察的职位及联络电话。",
          "27", "10D1-1"),
        C(SD1, "注意", "notice",
          "注意：上述数据有任何更改时，组别主管必须尽快通知行政部的主管。",
          "27", "10D1-1"),
    ]
    append(recs, roster("10D2 马家堡车辆段",
        "马家堡车辆段的总火警纠察由值班维修工程师担任，"
        "若不在场则由高级值班维修技术督导员代任。",
        "以下是马家堡车辆段的火警纠察安排表：", "车辆段的火警纠察",
        [("车务禁区", "停车库", "值班维修工程师"),
         ("车务禁区", "列检库", "值班维修工程师"),
         ("车务禁区", "架临修库", "二线维修工程师"),
         ("车务禁区", "内燃机车和特种车库", "轨道车工程师"),
         ("车务禁区", "其他", "当值车辆段列车控制主管"),
         ("非车务禁区", "行政办公楼（饭堂、浴室）", "行政及保安负责人"),
         ("非车务禁区", "供电通号维修车间、信号楼", "当值设施室主管工程师"),
         ("非车务禁区", "综合维修车间", "当值故障报警中心主管"),
         ("非车务禁区", "材料库", "当值仓务主管"),
         ("非车务禁区", "司乘公寓、公安用房", "行政公寓值班主管")],
        "28", "10D2-1"))

    append(recs, roster("10D3 龙背村停车场",
        "龙背村停车场的总火警纠察由值班维修工程师担任，"
        "若不在场则由高级值班维修技术督导员代任。",
        "以下是龙背村停车场的火警纠察安排表：", "停车场的火警纠察",
        [("车务禁区", "食堂、司乘、办公、培训中心", "高级维修技术督导员"),
         ("车务禁区", "停车库、洗刷库", "高级值班维修技术员"),
         ("车务禁区", "信号楼", "当值车辆段列车控制主管"),
         ("车务禁区", "司乘公寓", "行政公寓值班主任"),
         ("车务禁区", "其他", "当值车辆段列车控制主管")],
        "29", "10D3-1"))

    append(recs, roster("10D4 南兆路车辆段",
        "南兆路车辆段的总火警纠察由值班维修工程师担任，"
        "若不在场则由高级值班维修技术督导员代任。",
        "以下是南兆路车辆段火警纠察安排表：", "南兆路车辆段的火警纠察",
        [("车务禁区", "停车库", "值班维修工程师"),
         ("车务禁区", "联检库", "值班维修工程师"),
         ("车务禁区", "工程车库", "轨道车工程师"),
         ("车务禁区", "其他", "当值车辆段列车控制主管"),
         ("非车务禁区", "综合办公楼", "行政及安保负责人"),
         ("非车务禁区", "食堂", "行政负责人"),
         ("非车务禁区", "混合变电所（1 层）", "当值供电主管"),
         ("非车务禁区", "混合变电所（2 层）", "当值段务设备主管"),
         ("非车务禁区", "锅炉房", "当值段务主管"),
         ("非车务禁区", "通信信号楼（1 层）", "当值通信主管"),
         ("非车务禁区", "通信信号楼（2 层）", "当值信号主管"),
         ("非车务禁区", "综合维修中心（1-3 层）", "当值工务主管"),
         ("非车务禁区", "综合维修中心（4-5 层）", "安保负责人"),
         ("非车务禁区", "物资总库", "当值仓务主管"),
         ("非车务禁区", "司乘公寓", "行政公寓值班主管")],
        "30", "10D4-1"))
    recs.append(C("10D4 南兆路车辆段", "南兆路车辆段的火警纠察", "list",
                  "- 火警纠察任命前应进行培训；\n- 每年需进行培训内容的回顾。",
                  "30", "10D4-1"))
    return "10D", recs


FILES = (build_10A, build_10A1, build_10A2, build_10A3, build_10A4, build_10A5,
         build_10B1, build_10B2, build_10B3, build_10B4_10B7, build_10B8_10B9,
         build_10B10_10B12, build_10C, build_10D)

FIELD_ORDER = ("chunk_id", "doc_id", "section", "title", "type", "content",
               "source_page", "printed_page", "version", "effective_date", "parent_id")


def finalize(code, recs):
    """Assign chunk_ids, resolve parent refs, and check the result is sound."""
    for i, r in enumerate(recs, start=1):
        r["chunk_id"] = "%s_%s_%03d" % (DOC, code, i)
    out = []
    for r in recs:
        parent = r.pop("_parent")
        record = {
            "chunk_id": r["chunk_id"], "doc_id": DOC, "section": r["section"],
            "title": r["title"], "type": r["type"], "content": r["content"],
            "source_page": r["source_page"], "printed_page": r["printed_page"],
            "version": VERSION, "effective_date": EFFECTIVE_DATE,
            "parent_id": recs[parent]["chunk_id"] if parent is not None else None,
        }
        assert list(record) == list(FIELD_ORDER), r["chunk_id"]
        if not record["content"].strip():
            raise SystemExit("%s: empty content" % record["chunk_id"])
        if "[？]" in record["content"] or "复核备注" in record["content"]:
            raise SystemExit("%s: review artefact leaked into content" % record["chunk_id"])
        out.append(record)

    ids = {r["chunk_id"] for r in out}
    has_child = {r["parent_id"] for r in out if r["parent_id"]}
    for r in out:
        if r["parent_id"] is not None:
            if r["parent_id"] not in ids:
                raise SystemExit("%s: parent_id %s does not resolve" % (r["chunk_id"], r["parent_id"]))
            if r["type"] != "procedure_step":
                raise SystemExit("%s: has parent but is %s" % (r["chunk_id"], r["type"]))
        if r["type"] == "procedure_step" and r["parent_id"] is None:
            raise SystemExit("%s: procedure_step without parent" % r["chunk_id"])
        if r["type"] == "procedure" and r["chunk_id"] not in has_child:
            raise SystemExit("%s: procedure has no children" % r["chunk_id"])
    return out


def main():
    total = 0
    for builder in FILES:
        code, recs = builder()
        records = finalize(code, recs)
        out = OUT_ROOT / ("%s_RAG" % DOC) / "04_jsonl" / ("%s_%s_chunks.jsonl" % (DOC, code))
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
        total += len(records)
        print("%-12s %3d chunks -> %s" % (code, len(records), out.name))
    print("total: %d chunks" % total)


if __name__ == "__main__":
    main()
