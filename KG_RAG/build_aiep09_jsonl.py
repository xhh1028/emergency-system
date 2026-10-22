#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice AIEP09 (处理火警或冒烟事件) into RAG JSONL chunks.

Input   long_data/AIEP09_RAG/03_markdown_reviewed/*.md   (8 files, status: verified)
Output  long_data/AIEP09_RAG/04_jsonl/AIEP09_<code>_chunks.jsonl   (8 files)

Sources of each field
---------------------
* content / title / section - verbatim from the reviewed markdown. Nothing is
  reworded, reordered or summarised; the review artefact is dropped (rule 4):
  every 复核备注 block, including the two that describe the page-footer version
  mix. ``<br>`` inside a table cell becomes a newline; ``**`` bold markers are
  dropped and the label kept (``**注意：**`` -> ``注意：``, with the single space
  that followed an inline marker collapsed so 注意：/重要： reads as one label).
* source_page / printed_page - from the third-version long chunk set
  (``long_chunk_681片_待复核/long_chunk/JKR3_AIEP09_*.txt``), which carries
  ``PDF页序`` / ``印刷页码`` per topic. AIEP09's reviewed markdown has no page
  footers and no front-matter page fields, and the source PDF is a scan, so this
  legacy metadata is the only available provenance and could not be re-verified
  against the PDF.
* version - written as ``1.0`` for the whole document, following AIEP05-08.
  Both the legacy footers and the reviewed markdown's own 复核备注 agree that
  the printed version is mixed: 9A page 2 (9A-2) and 9C2 pages 1-3 and 5-6
  (9C2-1..9C2-3, 9C2-5, 9C2-6) carry 2010 年 5 月 1.1, everything else 2009 年
  6 月 1.0. Recording that per page would raise a W14 version warning per
  section, so the corpus-wide uniform value is kept. Settled 2026-09-29: the
  manual is issued in fascicles with no overall version, so a page footer marks
  that page's revision batch, not a document version - see closed item A6 in
  ``long_data/reports/aiep_todo.md`` and 已知限制 in ``reports/ragflow_config.md``.
* effective_date - 待确认, as everywhere else in the corpus.

Type policy (same six rules as AIEP08, stated again because the corpus is not
uniform)
---------------------------------------------------------------------------
1. A table with a 步骤 column -> one ``procedure`` parent holding the lead-in
   plus every step verbatim, and one ``procedure_step`` child per step, with
   ``parent_id`` pointing at the parent.
2. A table without a 步骤 column -> one ``table_row`` per row.
3. A standalone ``**注意：**`` / ``**重要：**`` block -> one ``notice`` chunk,
   ``title`` 注意/重要, content ``注意：<正文>``. A 注意/重要 that sits *inside*
   a table cell (9B3 烟经由通风井进入 step 2, 9C2 step 1.4) stays in the cell and
   does not also become a notice chunk.
4. ``X 是指…`` -> ``definition`` (9E 轨道范围).
5. A clause whose body is a lead-in line plus bullet points -> ``list``.
6. Introductory and descriptive prose -> ``text``, including 9C2's two 流程图概览
   sections, which are the OCR rendering of a diagram: they are kept whole as
   one chunk each rather than split, because their arrows and judgement nodes
   are not numbered steps and splitting them would invent a step ordering.

Known deviations / open items
-----------------------------
Every item below is logged in ``long_data/reports/aiep_todo.md`` (A6-A9), which is
the master ledger; when one is resolved, remove the matching note here too.
* 9C2 驾驶员应采取的行动 spans PDF pages 12-13 (9C2-2, 9C2-3). The legacy set
  recorded the range for the topic as a whole, not the break per sub-table, so
  all three role sub-flows carry the range. Their per-table page is unverified.
* 9C2 驾驶员应采取的行动 holds three ``#####`` sub-headings (1. 事故列车的驾驶员,
  2. 尾随列车的驾驶员, 3. 事故站台相邻轨道的驾驶员), each with its own step
  table, so it becomes three ``procedure`` groups rather than one. Their titles
  are the sub-headings verbatim, ordinals included, because the step numbers
  inside them (1.1, 2.1, 3.1) are keyed to those ordinals.
* The reviewed markdown records two 流程图概览 as converted from screenshots
  (AIEP09_9C2 复核备注 2). The conversion is not reproducible from the PDF here,
  so the text is taken as reviewed.
* 9B1 站内失火 opens a 节 heading of its own (``## 9B 处理车站失火``) that the
  9B2/9B3 files do not repeat; the 9B1 chunks use the 小节 as ``section``
  ("9B1 站内失火") exactly as 9B2/9B3 do, and the 9B line survives only in the
  TOC.
"""

import json
from pathlib import Path

OUT_ROOT = Path(__file__).resolve().parent / "long_data"
DOC = "AIEP09"
VERSION = "1.0"
EFFECTIVE_DATE = "待确认"


def C(section, title, type_, content, source_page, printed_page, _parent=None):
    return {"section": section, "title": title, "type": type_, "content": content,
            "source_page": source_page, "printed_page": printed_page, "_parent": _parent}


def steps(section, title, lead, rows, source_page, printed_page):
    """[parent, *children] for a 步骤 table. rows: (n, owner|None, action).

    ``lead`` is "" when the markdown puts the table straight under its heading
    with no lead-in sentence (9B1 确定火警警报属实, 9C2's role tables); in that
    case the parent is just the steps.
    """
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


def append(dst, specs):
    """Append a group, shifting its parent references past what is already there."""
    offset = len(dst)
    for s in specs:
        if s["_parent"] is not None:
            s["_parent"] += offset
    dst.extend(specs)
    return dst


# --------------------------------------------------------------------------- #
# 9A 处理火警或冒烟的指引                                     PDF 1-4 / 9A-1..9A-4
# --------------------------------------------------------------------------- #

def build_9A():
    S = "9A 处理火警或冒烟的指引"
    return "9A", [
        C(S, "引言", "text",
          "本章记载了处理火警和冒烟事件的方法，并说明在以下地点发生火警时应采取的行动：\n"
          "- 车站内；\n- 列车上；\n- 轨道范围内。\n"
          "\n参考：有关处理车辆段/停车场内失火的程序，请参见本手册第 10 章。",
          "1", "9A-1"),
        C(S, "安全", "text",
          "灭火的首要原则是保障生命安全。一旦安全受到威胁，所有人员必须立即由受影响范围撤退至安全地点。",
          "1", "9A-1"),
        C(S, "火警警报", "list",
          "铁路上响起火警警报时，必须采取以下的行动：\n"
          "- 任何人凡身处车辆段/停车场和附属建筑物，必须实时疏散。\n"
          "- 任何人凡身处车站机房/设备房，必须离开该房间并向值班站长报告。\n"
          "- 任何人凡身处车站办公室和公众范围，必须留意值班站长指示及随时准备疏散。\n"
          "- 任何人凡身处车站综控室，必须提高警觉，如果安全受到威胁，随时准备疏散。",
          "1", "9A-1"),
        C(S, "注意", "notice",
          "注意：\n"
          "- 为免烟通过新风进气装置渗入车站综控室，车站综控室的主管人员可关掉车站综控室的空调系统。\n"
          "- 员工发现警报响起的原因，须实时通知当地负责人员。",
          "1", "9A-1"),
        C(S, "首要行动", "list",
          "任何员工如发现地铁范围内任何地方失火或冒烟，必须：\n"
          "- 按规定通知消防部门。\n"
          "- 使用电话或无线电手持台或经由有关车站的值班站长，立即通过行车调度员要求消防部门到场处理。\n"
          "- 在安全情况下，尝试将烟火扑熄。",
          "2", "9A-2"),
        C(S, "报告内容", "list",
          "须通知行车调度员以下详细数据：\n"
          "- 利用以下数据说明起火的准确位置：\n"
          "  - 轨道的标示，或\n"
          "  - 任何用作标记的建筑物等。\n"
          "- 估计的起火原因\n"
          "- 火势。",
          "2", "9A-2"),
        C(S, "维持电力供应", "list",
          "- 火警发生时，除非生命或设备的安全受到威胁，否则必须维持电力供应，"
          "包括接触轨设备的牵引电流。\n"
          "- 若牵引电流供应系统受到任何影响，也须尽量维持各区段的电力供应，"
          "必要时可减少行车班次。",
          "2", "9A-2"),
        C(S, "告知消防部门有关环控系统的运作", "text",
          "运营主管人员须在消防部门现场主管抵达事发现场时，向他/她解释环境控制系统的运作安排。"
          "随后的各项运作，也应先取得他/她的同意。",
          "2", "9A-2"),
        C(S, "一般指引", "list",
          "以下是灭火的一般指引：\n"
          "- 采用以下方法灭火：\n"
          "  - 将物件与空气隔绝，或\n"
          "  - 将温度降至对象的燃烧点以下。\n"
          "- 关上门窗将火与空气隔绝。\n"
          "- 必须关上与未受影响范围之间的所有门窗及任何其它通道口。\n"
          "- 灭火时，必须在安全情况下尽量靠近并对准燃烧火焰底部。\n"
          "- 电器起火，只能用气体灭火，不可用水。\n"
          "- 用沙扑灭轨道扣件上的明火时，必须在火熄灭后，继续将扣件完全埋在沙下。\n"
          "- 必须立即移走火场附近的易燃物品。\n"
          "- 有人身上的衣物着火，应：\n"
          "  - 协助他/她平躺在地上；\n"
          "  - 用毛毯、外衣、地毯或其它类似的对象覆盖或包裹身体；\n"
          "  - 切勿让他/她在地面滚动，以免火势蔓延至身体其它没有着火的部分。",
          "3", "9A-3"),
        C(S, "可列为运营紧急状态", "list",
          "在以下情况下，可将火警列为运营紧急状态：\n"
          "- 自动设备不能将火扑灭；\n"
          "- 人员生命或铁路结构受到严重威胁；\n"
          "- 有可能最终影响行车线的列车服务。",
          "3", "9A-3"),
        C(S, "现场主管的责任", "list",
          "不论火警现场是否有消防人员或装备，现场主管，即有关值班站长或当值主管工程师"
          "必须时刻对下列各项负责：\n"
          "- 乘客及员工的安全。\n"
          "- 消防人员的安全。\n"
          "- 与消防部门现场主管保持联络，确保铁路上的电气设备或行车不会对消防人员的安全构成威胁。\n"
          "- 确保行车服务受阻程度减至最低。\n"
          "- 无论消防部门是否已采取安全措施，消防人员需要进入或横过轨道范围时，"
          "必须调派瞭望员或采取其它安全措施。",
          "4", "9A-4"),
        C(S, "保持联系", "list",
          "现场负责人须与公安、消防、医疗单位的负责人员建立联系，并提供以下数据：\n"
          "- 发生事故的准确位置；\n"
          "- 牵引电流或其它电源是否已截断及隔离；\n"
          "- 前往轨道是否安全；\n"
          "- 是否有人被困事发现场。",
          "4", "9A-4"),
    ]


# --------------------------------------------------------------------------- #
# 9B1 站内失火                                                          PDF 5
# --------------------------------------------------------------------------- #

def build_9B1():
    S = "9B1 站内失火"
    recs = []
    append(recs, steps(S, "确定火警警报属实", "",
        [(1, "值班站长",
          "火警警报响起时，从 FAS 确认位置，并派 1 名车站员工前往该房间/范围查看"),
         (2, "车站员工",
          "- 带同无线电手持台前往该房间/范围\n"
          "- 找出响起警报的原因\n"
          "- 实时通知值班站长是否：\n"
          "  - 发生火警\n"
          "  - 触动了防火系统"),
         (3, "车站员工",
          "若是发生火警：\n"
          "- 按需要手动操作防火系统，或\n"
          "- 若情况安全，使用灭火器灭火\n"
          "- 与现场保持安全距离，并警告其它人远离该处，直至消防人员到场"),
         (4, "值班站长",
          "确定火警警报属实后：\n"
          "- 实时通知行车调度员召唤消防\n"
          "- 遵照：\n"
          "  - 本手册 12B1 至 B3 及 12C1 所述的车站疏散程序\n"
          "  - 各车站自行制定的应变措施\n"
          "如警报为误鸣，通知行车调度员、站内所有员工、承包商及租户")],
        "5", "9B1-1"))
    recs.append(C(S, "恢复行车服务", "list",
                  "- 与值班站长确定站内的火已熄灭，烟也已明显消散后，行车调度员须允许列车驶经该站。"
                  "待值班站长确定车站可以重开后，方可恢复该站的行车服务。\n"
                  "- 值班站长应根据车站火警后的损毁程度或水淹情况，决定全面或局部重开车站。",
                  "5", "9B1-1"))
    return "9B1", recs


# --------------------------------------------------------------------------- #
# 9B2 邻站失火                                                          PDF 6
# --------------------------------------------------------------------------- #

def build_9B2():
    S = "9B2 邻站失火"
    return "9B2", [
        C(S, "人手后援方案", "text",
          "以下措施有助缓解事故发生时的人手紧张情况：制定「综合人力后援方案」。",
          "6", "9B2-1"),
        C(S, "调配后备人手", "list",
          "- 若有车站失火，「人手增援控制车站」的值班站长，必须根据「综合人力后援方案」作好准备，"
          "调配适当人员到事发车站增援。\n"
          "- 邻站的负责人也须随时候命，听从当值站区长的调配。",
          "6", "9B2-1"),
        C(S, "通风安排", "list",
          "若有车站失火，各邻站的值班站长必须：\n"
          "- 将环境控制系统转由车站控制；\n"
          "- 按照失火车站值班站长的指示，操作环境控制系统设备。",
          "6", "9B2-1"),
        C(S, "注意", "notice",
          "注意：\n"
          "- 若未能由车站操控环境控制系统，改由中央操控并通知 OCC 的系统调度员。\n"
          "- 紧急通风的安排按个别情况需要而定。"
          "事发车站的值班站长须决定向邻站要求在通风安排上提供哪一方面的协助。",
          "6", "9B2-1"),
    ]


# --------------------------------------------------------------------------- #
# 9B3 站外失火                                                PDF 7-8 / 9B3-1..2
# --------------------------------------------------------------------------- #

def build_9B3():
    S = "9B3 站外失火"
    recs = [
        C(S, "站外失火产生的烟", "text",
          "随着空气的自然流动，站外失火时产生的烟可能会扩散至站内。"
          "此外，下列原因也会令站外的烟进入站内：\n"
          "- 通风设备的运作，可能会导致站外的烟经由通风井进入站内。\n"
          "- 列车移动的活塞效应，可能会导致站外的烟经由车站入口进入站内。",
          "7", "9B3-1"),
    ]
    append(recs, steps(S, "烟经由通风井进入",
        "一旦发现有烟经由通风井进入站内，必须执行以下程序阻截烟继续进入。",
        [(1, "值班站长",
          "- 如有需要：\n"
          "  - 取得所管辖车站的环境控制系统设备的控制权\n"
          "  - 通过 IBP 盘停止已启用的所有模式，以便将受影响车站公众范围的通风设备关掉，防止烟扩散\n"
          "- 通知行车调度员安排：\n"
          "  - 将有关通风设备关掉\n"
          "  - 关闭相应的风闸"),
         (2, "行车调度员",
          "指示系统调度员操作有关环境控制系统设备\n"
          "注意：\n与系统调度员商议后，由值班站长重设车站 IBP 盘"),
         (3, "系统调度员", "依照行车调度员的指示，操作环境控制系统设备")],
        "7", "9B3-1"))
    append(recs, steps(S, "烟经由入口进入",
        "有烟经由车站入口扩散到了公众范围时，应遵行以下程序。",
        [(1, "值班站长",
          "- 通知行车调度员，说明烟的浓度\n"
          "- 关闭有关的入口\n"
          "- 取得所管辖车站的环境控制系统设备的控制权\n"
          "- 按本手册 11A 的规定，操作环境控制系统设备"),
         (2, "行车调度员",
          "值班站长是否报告车站浓烟密布：\n- 若是，进行步骤 3\n- 若否，程序到此完结"),
         (3, "行车调度员",
          "指示各邻站的值班站长：\n"
          "- 取得所管辖车站的环境控制系统设备的控制权\n"
          "- 通过 IBP 盘停止已启用的所有模式，以便将受影响车站公众范围的通风设备关掉，防止烟扩散\n"
          "- 操作环境控制系统设备，以帮助驱散受影响车站的浓烟"),
         (4, "各邻站值班站长",
          "- 取得所管辖车站的环境控制系统设备的控制权\n"
          "- 按本手册 11A 的规定，操作环境控制系统设备")],
        "8", "9B3-2"))
    return "9B3", recs


# --------------------------------------------------------------------------- #
# 9C1 一般指引                                               PDF 9-10 / 9C1-1..2
# --------------------------------------------------------------------------- #

def build_9C1():
    S = "9C1 一般指引"
    return "9C1", [
        C(S, "报告详情", "list",
          "报告列车失火或冒烟时，必须将下列详情通知行车调度员或值班站长：\n"
          "- 列车的位置；\n"
          "- 列车编号/列车车次；\n"
          "- 起火的位置，例如由头端墙算起第 4 节；\n"
          "- 起火或冒烟的车厢编号（若有资料）；\n"
          "- 火势或烟的浓度，及是否有人受伤或有设备损毁。",
          "9", "9C1-1"),
        C(S, "立即清人", "list",
          "若失火时列车正处于两站之间，驾驶员应遵照下列的指示：\n"
          "- 列车可以安全驶至下一站：必须驶至下一站及在站台清人；\n"
          "- 列车无法安全驶至下一站：必须通知行车调度员及立即清人。",
          "9", "9C1-1"),
        C(S, "重要", "notice",
          "重要：\n在紧急情况下，即使驾驶员与行车调度员的沟通中断而未能取得授权，也必须清人。",
          "9", "9C1-1"),
        C(S, "受影响列车停在车站", "list",
          "若列车在站内失火，驾驶员应：\n- 清人；\n- 停止该列车的载客服务。",
          "9", "9C1-1"),
        C(S, "受影响列车停在隧道内", "list",
          "列车在隧道内失火时，驾驶员必须采取下述行动：\n"
          "- 列车可以驶至下一站：必须将列车驶至下一站清人，及停止该列车的载客服务。\n"
          "- 列车无法驶至下一站：必须待行车调度员确定清人路线已停止行车并关断牵引电流后，立即清人。",
          "10", "9C1-2"),
        C(S, "运营紧急状态", "text",
          "列车失火而停在隧道内属于运营紧急状态。\n"
          "\n参考：有关运营紧急状态的控制程序，请参见本手册第 2 章。",
          "10", "9C1-2"),
        C(S, "相邻隧道的行车", "list",
          "- 在不影响烟的流向和清人程序的情况下，在由事故处理主任确认并授权下，"
          "行车调度员可授权失火隧道相邻的另一条隧道继续行车。\n"
          "- 列车必须以「ATPM」模式行驶，时速不得超过 40 公里。",
          "10", "9C1-2"),
    ]


# --------------------------------------------------------------------------- #
# 9C2 在岛式站台和侧式站台处理列车失火                       PDF 11-16 / 9C2-1..6
# --------------------------------------------------------------------------- #

def build_9C2():
    S = "9C2 在岛式站台和侧式站台处理列车失火"
    recs = [
        C(S, "一般规则", "list",
          "在岛式站台和侧式站台处理列车失火时，必须遵照下列规则：\n"
          "- 尽快让事故列车的所有乘客下车。\n"
          "- 若站台安全门（只限岛式站台）及/或车门未能打开，须立即清人至轨道。\n"
          "- 阻止任何列车进入报告发生火警的车站。在安全情况下，"
          "须安排列车经由折返线反向行车或调头，返回出发站台清人。\n"
          "- 安排正在事故车站执行站台职务的列车尽快离开。",
          "11", "9C2-1"),
        C(S, "紧急风扇操作指引", "list",
          "环控系统调度员按行车调度员的指示操作紧急风扇时，须遵守下列指引：\n"
          "- 若进行单端清人，须操作紧急风扇供应新风，让乘客疏散时逆风而行。\n"
          "- 若进行双端清人，须沿着行车方向操作紧急风扇。",
          "11", "9C2-1"),
        C(S, "值班经理应采取的行动", "text",
          "获行车调度员通知，岛式站台或侧式站台有列车失火后，值班经理须宣布进入运营紧急状态。",
          "11", "9C2-1"),
        C(S, "行车信息助理应采取的行动", "list",
          "宣布进入运营紧急状态后，行车信息助理须立即：\n"
          "- 如获值班经理授权，通知消防部门和公交总队；\n"
          "- 利用中央信息发布系统发布信息。",
          "11", "9C2-1"),
    ]
    append(recs, steps(S, "行车调度员应采取的行动", "",
        [(1, None, "- 通知值班经理、行车信息助理和系统调度员\n- 切勿关断牵引电流"),
         (2, None, "迅速阻止尾随列车进入受影响范围"),
         (3, None,
          "截停相邻轨道上的列车：\n"
          "- 岛形/侧式站台：如列车未能截停并停靠在事故站台相邻的轨道上，"
          "必须指示驾驶员立即驾驶列车离开\n"
          "- 只限岛式站台：如列车未能截停并停在事故车站与上一站之间，"
          "必须用无线电指示驾驶员不要在事故车站停车")],
        "12", "9C2-2"))
    # 驾驶员应采取的行动: three ##### sub-headings, each with its own step
    # table, so three flows. Pages 12-13 (9C2-2, 9C2-3) belong to the topic as a
    # whole; the break per sub-table is not recorded in the legacy set.
    append(recs, steps(S, "1. 事故列车的驾驶员", "",
        [("1.1", None, "- 开启客用车门和站台安全门\n- 用预录广播系统通知乘客"),
         ("1.2", None,
          "尝试用以下方法了解情况，观察有否起火或冒烟的迹象：\n"
          "- 打开驾驶室门，探视车厢的情况\n"
          "- 走出站台，沿着车身查看"),
         ("1.3", None, "向行车调度员汇报，并进行清人"),
         ("1.4", None,
          "- 向行车调度员汇报最新的清人情况\n"
          "- 目检车厢，确保所有乘客已下车\n"
          "- 完成清人后，让车门打开，关断列车\n"
          "- 向值班站长/事故处理主任报到\n"
          "重要：如生命受到威胁，立即逃离火场")],
        "12-13", "9C2-2~9C2-3"))
    append(recs, steps(S, "2. 尾随列车的驾驶员", "",
        [("2.1", None,
          "在行车调度员的指示下，立即停车。是否能截停列车：\n"
          "- 如是，进行步骤 2.2\n"
          "- 如否，按下表进行：\n"
          "  - 岛式站台：继续前进，一旦看见列车起火或冒烟，立即操作紧急停车按钮；"
          "在行车调度员授权下，经由折返线反向行车或调头；清人\n"
          "  - 侧式站台：继续前进，通过列车自动保护系统，在事故列车前自动停车，"
          "或一旦看见列车起火或冒烟，立即操作紧急停车按钮；在行车调度员授权下反向行车；清人"),
         ("2.2", None,
          "- 如列车停在站台，按行车调度员授权，立即清人\n"
          "- 如列车停在两站之间，经行车调度员授权返回车站，及清人")],
        "12-13", "9C2-2~9C2-3"))
    append(recs, steps(S, "3. 事故站台相邻轨道的驾驶员", "",
        [("3.1", None,
          "在行车调度员的指示下，立即停车。如列车…必须…：\n"
          "- 岛式站台：\n"
          "  - 能停下：立即清人\n"
          "  - 未能停下：在行车调度员的授权下，不在事故车站停车\n"
          "- 侧式站台：\n"
          "  - 在站台且可以停下：立即清人\n"
          "  - 在两站之间且可以停下：在行车调度员的授权下反向行车，然后清人\n"
          "  - 未能停下：\n"
          "    - 一旦看见列车起火或冒烟，立即操作紧急停车按钮\n"
          "    - 在行车调度员的授权下反向行车，然后清人\n"
          "    - 停靠在事故站台相邻的站台：紧急清人")],
        "12-13", "9C2-2~9C2-3"))
    append(recs, steps(S, "值班站长应采取的行动", "",
        [(1, None, "操作两个站台的紧急停车按钮"),
         (2, None, "遵照应变计划疏散车站，随即关闭车站"),
         (3, None, "设立事故控制站，担任事故处理主任，控制现场")],
        "14", "9C2-4"))
    recs += [
        C(S, "岛式站台流程图概览", "text",
          "【事故列车部分】\n"
          "- 事故列车的驾驶员：开启客用车门和站台安全门 → 尝试了解情况，观察是否有起火或冒烟的迹象 "
          "→ 向行车调度员汇报及清人 → 向行车调度员汇报最新的清人情况和起火冒烟的迹象变化，"
          "及完成清人后，让车门打开，关断列车，向值班站长/事故处理主任报到\n"
          "- 行车调度员：通知值班经理、行车信息助理和系统调度员；切勿关断牵引电流\n"
          "- 值班经理：宣布进入运营紧急状态\n"
          "- 行车信息助理：通知公交总队，及利用中央信息发布系统发放信息\n"
          "- 值班站长：操作站台两边的紧急停车按钮 → 疏散车站，随时关闭车站 → 设立事故控制站\n"
          "\n【尾随列车部分】\n"
          "- 行车调度员：迅速组织列车避免进入受影响的范围\n"
          "- 尾随列车的驾驶员：列车继续前进\n"
          "- 判断能否截停列车：\n"
          "  - 否 → 行车调度员：使用无线电通知驾驶员立即停车 → "
          "尾随列车的驾驶员：若看见前面列车起火或冒烟，立即操作紧急停车按钮；"
          "值班站长：收到列车失火的报告后，立即操作紧急停车按钮\n"
          "  - 是 → 判断列车位置：\n"
          "    - 在站台 → 尾随列车的驾驶员：进行清人\n"
          "    - 在两站之间 → 尾随列车的驾驶员：反向行车至后一站和通过折返线掉头\n"
          "\n【事故站台相邻轨道的列车部分】\n"
          "- 行车调度员：截停列车，停止相邻轨道上的所有行车\n"
          "- 判断能否截停列车：\n"
          "  - 是 → 相邻轨道的列车驾驶员：进行清人\n"
          "  - 否 → 判断列车位置：\n"
          "    - 停在事故站台的另一侧 → 行车调度员：指示列车驾驶员立即驶离事故车站\n"
          "    - 停在事故车站与上一站之间 → 行车调度员：用无线电通知驾驶员越站不停",
          "15", "9C2-5"),
        C(S, "侧式站台流程图概览", "text",
          "【事故列车部分】\n"
          "- 同岛式站台\n"
          "\n【尾随列车部分】\n"
          "- 行车调度员：迅速组织列车避免进入受影响的范围\n"
          "- 尾随列车的驾驶员：列车继续前进\n"
          "- 判断能否截停列车：\n"
          "  - 是 → 判断列车位置：\n"
          "    - 在站台 → 尾随列车的驾驶员：进行清人\n"
          "    - 在两站之间 → 尾随列车的驾驶员：获授权后反向行车\n"
          "  - 否 → 行车调度员：使用无线电通知驾驶员立即停车 → "
          "尾随列车的驾驶员：通过列车自动保护系统，在事故列车前自动停车；"
          "或若看见前面列车起火或冒烟，立即操作紧急停车按钮\n"
          "\n【事故站台相邻轨道的列车部分】\n"
          "- 行车调度员：迅速组织列车避免进入受影响范围\n"
          "- 相邻轨道的驾驶员：列车继续前进\n"
          "- 判断能否截停列车：\n"
          "  - 是 → 判断列车位置：\n"
          "    - 在站台 → 相邻轨道的驾驶员：进行清人\n"
          "    - 在两站之间 → 相邻轨道的驾驶员：获授权后反向行车\n"
          "  - 否 → 值班站长：收到列车失火的报告后，立即操作紧急停车按钮；"
          "相邻轨道的驾驶员：若看见列车起火或冒烟，立即操作紧急停车按钮 → 判断列车可否开往下一站：\n"
          "    - 是 → 行车调度员：通知驾驶员立即将列车驶离发生事故的车站\n"
          "    - 否 → 相邻轨道的驾驶员：紧急清人",
          "16", "9C2-6"),
    ]
    return "9C2", recs


# --------------------------------------------------------------------------- #
# 9D 处理铁路附近的火警                                      PDF 17-18 / 9D-1..2
# --------------------------------------------------------------------------- #

def build_9D():
    S = "9D 处理铁路附近的火警"
    recs = [
        C(S, "报告火警", "list",
          "任何员工在铁路附近范围发现火警，例如发现有草/垃圾在焚烧时，"
          "必须立即向行车调度员报告下列详情：\n"
          "- 火警的真实详细地点；\n"
          "- 受影响的行车线；\n"
          "- 火势；\n"
          "- 铁路受影响的可能性。",
          "17", "9D-1"),
    ]
    append(recs, steps(S, "行车调度员的行动",
        "行车调度员接到铁路附近范围发生火警的报告时，应遵照下表程序：",
        [(1, None, "要求消防部门协助"),
         (2, None, "通知所有驾驶员铁路附近范围发生火警"),
         (3, None, "火势是否局限在围栏以外范围？\n- 若是，进行步骤 5\n- 若否，进行步骤 4"),
         (4, None, "火势是否有机会蔓延至围栏以内范围？\n- 若是，进行步骤 5\n- 若否，进行步骤 6"),
         (5, None,
          "指示 1 名车站员工：\n"
          "- 前往事发现场\n"
          "- 在指定的出入口等候消防人员，并引领他们前往火警现场"),
         (6, None,
          "火势或烟的扩散情况是否有可能影响驾驶员的视线？\n"
          "- 若是，指示所有列车经过受影响范围时减慢车速\n- 若否，进行步骤 7"),
         (7, None,
          "消防部门的灭火行动是否影响列车驶过时的安全？\n"
          "- 若是，阻止列车驶往/驶近受影响范围\n"
          "- 若否，提醒所有驾驶员经过受影响范围时须加倍小心")],
        "17", "9D-1"))
    append(recs, steps(S, "前往现场的车站员工应遵照的程序",
        "前往火警现场的车站员工须遵照下表的程序。",
        [(1, None, "与值班站长确定：\n- 火警的确实地点\n- 指定的出入口"),
         (2, None, "使用最快捷的途径前往指定的出入口"),
         (3, None, "与消防人员会合，并引领他们前往火警现场"),
         (4, None, "提醒消防人员切勿走近行车线"),
         (5, None, "与消防部门现场主管协商灭火方法"),
         (6, None,
          "是否使用消防龙头灭火：\n"
          "- 若是：\n"
          "  - 确保以下设备不受影响：\n"
          "    - 接触轨\n"
          "    - 其它轨旁设备\n"
          "  - 进行步骤 7\n"
          "- 若否，进行步骤 7"),
         (7, None,
          "消防部门的灭火行动是否影响列车驶过时的安全？\n"
          "- 若是：\n"
          "  - 与行车调度员安排阻止列车驶往/驶近受影响范围\n"
          "  - 进行步骤 8\n"
          "- 若否，进行步骤 8"),
         (8, None, "消防人员撤离后，查看现场情况并向行车调度员报告")],
        "18", "9D-2"))
    return "9D", recs


# --------------------------------------------------------------------------- #
# 9E 处理轨道范围的火警                                      PDF 19-20 / 9E-1..2
# --------------------------------------------------------------------------- #

def build_9E():
    S = "9E 处理轨道范围的火警"
    return "9E", [
        C(S, "轨道范围", "definition",
          "轨道范围是指车站、隧道和行车线露天段的轨道和轨旁位置。",
          "19", "9E-1"),
        C(S, "火警或冒烟的可能成因", "list",
          "以下是引致轨道范围失火或冒烟的可能成因：\n"
          "- 垃圾暗燃或着火；\n"
          "- 受流器与接触轨产生拉弧现象。",
          "19", "9E-1"),
        C(S, "报告详情", "list",
          "任何员工如发现轨道范围失火或冒烟，必须以最迅速的方法，"
          "立即向行车调度员报告以下数据：\n"
          "- 起火地点；\n- 火势；\n- 估计的起火成因；\n- 行车安全是否受影响。",
          "19", "9E-1"),
        C(S, "行车调度员应采取的行动", "list",
          "行车调度员接获轨道范围发生火警或冒烟的报告后，应该：\n"
          "- 需要时安排系统调度员操作紧急风扇，将烟雾抽走；\n"
          "- 决定行车安排和衡量是否需要疏散；\n"
          "- 安排车站员工在安全情况下调查起火原因和灭火；\n"
          "- 通知驾驶员如何调度列车服务；\n"
          "- 通过故障报警中心召唤紧急救援队到现场。",
          "19", "9E-1"),
        C(S, "灭火用具", "list",
          "前往火警现场进行调查的车站员工须携带以下物品：\n"
          "- 1 个二氧化碳灭火器；\n- 1 桶沙。",
          "19", "9E-1"),
        C(S, "注意", "notice",
          "注意：如没有二氧化碳灭火器，可使用化学粉剂灭火器。",
          "19", "9E-1"),
        C(S, "处理垃圾着火", "list",
          "轨道范围内有垃圾着火时，车站员工须：\n"
          "- 在安全情况下用灭火器进行扑救；\n"
          "- 火种熄灭后，清除残余的垃圾。",
          "19", "9E-1"),
        C(S, "处理接地轨道扣件引起的火警", "list",
          "若轨道范围内的火警是由接地的轨道扣件引起，车站员工须：\n"
          "- 在安全情况下用二氧化碳灭火器进行扑救。\n"
          "- 用沙完全盖着轨道扣件上的火，熄灭后也不要清除沙粒"
          "（截断电子短路前，扣件可能会再起火）。\n"
          "- 如没有受过有关训练，切勿试图清除引起电子短路的对象"
          "（例如电缆、铁屑、轨道扣件等）。\n"
          "- 向行车调度员报告行车安全是否受到影响，并按其指示行动。",
          "20", "9E-2"),
    ]


FILES = (build_9A, build_9B1, build_9B2, build_9B3, build_9C1, build_9C2,
         build_9D, build_9E)

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
        print("%-6s %3d chunks -> %s" % (code, len(records), out.name))
    print("total: %d chunks" % total)


if __name__ == "__main__":
    main()
