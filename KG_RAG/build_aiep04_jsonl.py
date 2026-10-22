# -*- coding: utf-8 -*-
"""Build AIEP04 JSONL chunks from reviewed markdown.

Source : long_data/AIEP04_RAG/03_markdown_reviewed/*.md
Output : long_data/AIEP04_RAG/04_jsonl/AIEP04_<section>_chunks.jsonl

Page numbering
--------------
Unlike AIEP01-03, AIEP04's raw extraction carries real printed-page footers, so
printed_page is READ from the document, not derived:

    ===== Page 1 ===== -> [页脚: 4A1-1]     ===== Page 4 ===== -> [页脚: 4A2-1]
    ===== Page 2 ===== -> [页脚: 4A1-2]     ===== Page 5 ===== -> [页脚: 4A2-2]
    ===== Page 3 ===== -> [页脚: 4A1-3]

Note page 1 is labelled 4A1-1 even though it opens with the 4A 引言 - the footer
follows the dominant subsection, so the 4A chunk legitimately gets 4A1-1.

AIEP04_p006-p012_raw.md is 0 bytes and there is no way to read the scanned PDF
on this machine (no poppler/tesseract, no PDF library), so pages 6-12 cannot be
read from the document. Pages for 4A3-4A7 therefore come from the legacy
long-chunk set in long_chunk_681片_待复核/long_chunk/JKR3_AIEP04_*.txt, whose
recorded footers are:

    条款  PDF页序  印刷页码
    4A3   6,7     4A3-1,4A3-2
    4A4   8       4A4-1
    4A5   9       4A5-1
    4A6   10,11   4A6-1,4A6-2
    4A7   12      4A7-1

That metadata is corroborated rather than assumed: for pages 1-5 it agrees
exactly with the document's OWN footers read from AIEP04_p001-p005_raw.md
([页脚: 4A1-1] ... [页脚: 4A2-2]) on all seven comparable entries.

4A3 and 4A6 each span two pages. Their step children carry the section's full
range (e.g. "6-7"), because the per-step page split is not recorded anywhere;
a true range is stated rather than an invented single page.

Step tables
-----------
Per review decision, a step table produces one `procedure` parent chunk holding
the whole flow, plus one `procedure_step` child per step carrying parent_id.
Row content is formatted per the table-header rule: `步骤：N；负责人员：X；行动：Y`.
Notes embedded inside a table cell stay in that cell rather than becoming
separate notice chunks (same decision as AIEP03).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "long_data" / "AIEP04_RAG" / "04_jsonl"

DOC_ID = "AIEP04"
VERSION = "1.0"
EFFECTIVE_DATE = "待确认"

SECTIONS = {
    "4A": "4A 有人被列车卷入车底",
    "4A1": "4A1 有人被列车撞倒",
    "4A2": "4A2 将被卷入车底的人移离轨道",
    "4A3": "4A3 顶起列车后移开被卷入车底的人",
    "4A4": "4A4 开动列车后移开被卷入车底的人",
    "4A5": "4A5 开动列车前移开被卷入车底的人",
    "4A6": "4A6 开动列车",
    "4A7": "4A7 列车驶离事发现场后",
}

# section -> (source_page, printed_page) for the whole section, or None if the
# page range is unknown because the raw extraction is missing.
PAGES = {
    "4A": ("1", "4A1-1"),
    "4A1": ("1-3", "4A1-1~4A1-3"),
    "4A2": ("4-5", "4A2-1~4A2-2"),
    "4A3": ("6-7", "4A3-1~4A3-2"),
    "4A4": ("8", "4A4-1"),
    "4A5": ("9", "4A5-1"),
    "4A6": ("10-11", "4A6-1~4A6-2"),
    "4A7": ("12", "4A7-1"),
}


def step_table(title, lead_in, items, page_of_step, owner_header=True):
    """Build a step table as one `procedure` parent + one child per step.

    items: list of ("step", number, owner, action) or ("group", label)
    page_of_step: callable(step_number) -> (source_page, printed_page)
    """
    specs = []
    lines = [lead_in] if lead_in else []
    for it in items:
        if it[0] == "group":
            lines.append(it[1])
            continue
        _, no, owner, action = it
        if owner_header and owner:
            lines.append("步骤：%s；负责人员：%s；行动：%s" % (no, owner, action))
        else:
            lines.append("步骤：%s；行动：%s" % (no, action))
    specs.append({"title": title, "type": "procedure", "content": "\n".join(lines),
                  "parent": None})

    for it in items:
        if it[0] != "step":
            continue
        _, no, owner, action = it
        if owner_header and owner:
            content = "步骤：%s；负责人员：%s；行动：%s" % (no, owner, action)
        else:
            content = "步骤：%s；行动：%s" % (no, action)
        specs.append({"title": "%s-步骤%s" % (title, no), "type": "procedure_step",
                      "content": content, "parent": 0, "pages": page_of_step(no)})
    return specs


CHUNKS = {}

# ---------------------------------------------------------------- 4A
CHUNKS["4A"] = [
    {"title": "引言", "type": "text", "parent": None, "pages": ("1", "4A1-1"),
     "content": "本章内容为接到有人被列车撞倒的报告后，相应处理办法。"},
]

# ---------------------------------------------------------------- 4A1
STEPS_4A1 = [
    ("step", 1, "驾驶员",
     "- 立刻停车；\n- 嘱咐乘客紧握扶手；\n- 通过列车无线电通信系统发出紧急通知，向行车调度员报告事件；\n"
     "- 通过广播系统通知乘客有关延误；\n- 停止列车所有运作，但确保无线电手持台功能正常；\n- 将控制钥匙交给主管人员"),
    ("step", 2, "行车调度员",
     "- 确定列车编号及位置；\n- 确定驾驶员停止列车所有运作，但确保无线电手持台功能正常；\n"
     "- 通知另一名行车调度员负责该行车线的列车调度；\n- 全力应付该事件"),
    ("step", 3, "行车调度员",
     "通知下列人员有人被列车撞倒：\n- 在站台值班的站务员；\n- 值班站长；\n- 值班经理；\n"
     "- 事故处理主任；\n- 车辆段管理员；\n- 乘务管理员"),
    ("step", 4, "行车调度员",
     "授权员工将无线电手持台转至「正线组」频道。\n"
     "注意：采用「正线组」频道可让有关行车线上所有员工互相通话"),
    ("step", 5, "在站台值班的站务员",
     "- 操作站台上的紧急停车按钮；\n- 向行车调度员及值班站长报告；\n- 在站台实施控制大客流措施；\n"
     "- 寻找事故的目击证人；\n- 被卷入车底的人的详细资料"),
    ("step", 6, "值班站长",
     "- 操作 IBP 上的紧急停车按钮，以停止有关轨道上所有列车行驶；\n- 按情况需要实施车站管制；\n"
     "- 指派一名车站员工在车站综控室当值；\n- 指示所有员工利用「正线组」频道通话。\n"
     "注意：实施车站管制，一般可停止乘客进入付费区"),
    ("step", 7, "相关车站的值班站长", "将无线电手持台调至「正线组」频道"),
    ("step", 8, "事故处理主任",
     "- 前往事发现场；\n- 按照程序协助救出轨道上的人。\n参考：详情请参见本节 4A2"),
    ("step", 9, "值班经理",
     "安排通知：\n- 急救中心派出救护车；\n- 车辆段控制中心派出紧急救援队；\n"
     "- 公安局公交总队；\n- 乘务室、站务室及政府关系部的奉命工作人员"),
    ("step", 10, "值班经理", "安排通过中央广播系统通知受影响区段的乘客"),
    ("step", 11, "值班经理",
     "接到有人被压于车轮下，需顶起列车才能将其救出的报告时，应作以下安排：宣布进入运营紧急状态"),
    ("step", 12, "乘务管理员", "- 安排人手接替涉及事故的驾驶员；\n- 预备后备列车以调整行车服务"),
]
CHUNKS["4A1"] = step_table(
    "程序", "下表说明有人被列车撞倒时应如何处理：", STEPS_4A1,
    lambda n: ("1", "4A1-1") if n <= 4 else ("2", "4A1-2"))
CHUNKS["4A1"][0]["pages"] = ("1-2", "4A1-1~4A1-2")
CHUNKS["4A1"] += [
    {"title": "寻找目击证人", "type": "list", "parent": None, "pages": ("3", "4A1-3"),
     "content": "车站员工，特别是在站台值班的站务员，必须设法寻找事故的目击证人。找到目击证人时，须：\n"
                "- 要求目击证人留下协助公安调查；\n- 会见目击证人；\n"
                "- 记录每位目击证人的姓名、地址及联系电话号码；\n- 记录所见所闻，并由目击证人签字。"},
    {"title": "注意", "type": "notice", "parent": None, "pages": ("3", "4A1-3"),
     "content": "注意：必须将目击证人提供的信息转交给现场的公安人员及事故处理主任。"},
]

# ---------------------------------------------------------------- 4A2
STEPS_4A2 = [
    ("step", 1, None,
     "携带以下物品前往站台：\n- 反光背心；\n- 安全帽；\n- 一次性的胶手套；\n- 电筒；\n- 无线电手持台"),
    ("step", 2, None,
     "向驾驶员及在站台值班的站务员查询事故的详情，包括：\n- 位置；\n- 涉及的人；\n- 目击证人"),
    ("step", 3, None, "与行车调度员安排隔离牵引电流及安全措施"),
    ("step", 4, None, "收取驾驶员的控制钥匙"),
    ("step", 5, None,
     "- 与 1 名车站员工前往轨道；\n- 如下搜索列车底部，寻找被撞倒的人：\n"
     "  - 由车头开始搜索；\n  - 沿列车两旁同时搜索"),
    ("step", 6, None, "找到被撞倒的人后，根据当时情况，按本题目内「移走被撞倒的人」的指引处理"),
]
CHUNKS["4A2"] = [
    {"title": "引言", "type": "list", "parent": None, "pages": ("4", "4A2-1"),
     "content": "在下列情况下可将被卷入车底的人移出轨道：\n"
                "- 先移开被卷入车底的人然后将列车驶离站台；\n"
                "- 将列车驶离站台，然后移开被卷入车底的人，或\n"
                "- 先顶起列车才将被卷入车底的人移开。"},
    {"title": "注意", "type": "notice", "parent": None, "pages": ("4", "4A2-1"),
     "content": "注意：必须先将列车顶起，才可救出被压在车轮下的人。"},
]
CHUNKS["4A2"] += step_table(
    "寻找被卷入车底的人", "值班站长须遵照以下程序，寻找被列车卷入车底的人。", STEPS_4A2,
    lambda n: ("4", "4A2-1"), owner_header=False)
for _spec in CHUNKS["4A2"]:
    if _spec["type"] == "procedure_step":
        _spec["parent"] = 2  # the parent sits at index 2 (after 引言 and 注意)
CHUNKS["4A2"] += [
    {"title": "移走被撞倒的人", "type": "text", "parent": None, "pages": ("5", "4A2-2"),
     "content": "寻获该名被撞倒的人后，按下表所列情况将其移走。"},
    {"title": "该名被卷入车底的人被压在车轮下", "type": "table_row", "parent": None,
     "pages": ("5", "4A2-2"),
     "content": "若：该名被卷入车底的人被压在车轮下；参见文件识别编号：4A3"},
    {"title": "该名被卷入车底的人并非压在车轮下，适宜开动列车后才移动该名伤者", "type": "table_row",
     "parent": None, "pages": ("5", "4A2-2"),
     "content": "若：- 该名被卷入车底的人并非压在车轮下；\n- 适宜开动列车后才移动该名伤者；"
                "参见文件识别编号：4A4"},
    {"title": "该名被卷入车底的人并非被压在车轮下，适宜开动列车前先移动该名伤者", "type": "table_row",
     "parent": None, "pages": ("5", "4A2-2"),
     "content": "若：- 该名被卷入车底的人并非被压在车轮下；\n- 适宜开动列车前先移动该名伤者；"
                "参见文件识别编号：4A5"},
    {"title": "移开伤者的步骤", "type": "list", "parent": None, "pages": ("5", "4A2-2"),
     "content": "按照以下步骤，将伤者移离轨道：\n"
                "- 只有曾接受急救训练的员工方可处理伤者。\n"
                "- 负责处理伤者的员工须戴上胶手套，避免接触伤者的血液。\n"
                "- 为顾及伤者的安危，将伤者移开轨道至安全地方时，须充分考虑他/她的伤势。\n"
                "- 若伤者看似没有生命迹象，也没有怀疑涉及刑事犯罪，值班站长须将该人移离轨道。\n"
                "- 在可行情况下，须尽量使用担架床及毛毯。\n"
                "- 照料伤者的值班站长必须在救护车抵达时：\n"
                "  - 向救护车的主管讲述当时的情况；\n  - 立即将伤者交给救护人员处理。"},
]

# ---------------------------------------------------------------- 4A3
STEPS_4A3 = [
    ("step", 1, "值班站长",
     "- 通知行车调度员有人被困车底；\n- 与行车调度员安排截断受影响范围的牵引电流；\n"
     "- 安排发生事故的列车清人；\n- 要求驾驶员将「高速断路器」(HSCB) 拨至断开位置；\n"
     "- 顶起列车前，先与行车调度员确定牵引电流已经隔离。\n"
     "注意：\n- 紧急救援队应负责顶起列车；\n"
     "- 若非需要将伤者救离险境，列车顶起后车轮与轨道距离必须少于 70 毫米"),
    ("step", 2, "行车调度员", "与系统调度员安排切断受影响范围的牵引电流"),
    ("step", 3, "值班经理", "通知紧急救援队有需要顶起事故列车"),
    ("step", 4, "驾驶员", "顶起列车前，将「高速断路器」(HSCB) 拨至断开位置"),
    ("step", 5, "值班站长",
     "按照本节 4A2 有关“移开伤者的步骤”，在可行情况下尽快将被卷入车底的人移离轨道"),
    ("step", 6, "值班站长",
     "将被卷入车底的人移开轨道后：\n- 确定轨道上没有任何人或障碍物；\n- 与行车调度员安排重新接通牵引电流"),
    ("step", 7, "行车调度员", "与系统调度员安排重新接通牵引电流"),
    ("step", 8, "- 行车调度员\n- 值班站长\n- 驾驶员\n- 在站台值班的站务员",
     "遵照本节 4A6 的程序开动列车"),
    ("step", 9, "值班站长", "遵照本节 4A7 的程序，安排列车驶离事发现场后的事宜"),
]
CHUNKS["4A3"] = step_table(
    "程序", "需要先顶起列车才能移动被卷入车底的人，可遵照以下程序。", STEPS_4A3,
    lambda n: PAGES["4A3"])

# ---------------------------------------------------------------- 4A4
STEPS_4A4 = [
    ("group", "1. 开动列车前"),
    ("step", "1.1", "值班站长",
     "- 确保被卷入车底的人安全，不会因列车开动而碰伤；\n- 指派 1 名员工或亲自陪同该人"),
    ("group", "2. 开动列车"),
    ("step", "2.1", "- 行车调度员\n- 值班站长\n- 驾驶员\n- 在站台值班的站务员",
     "遵照本章 4A6 的程序“开动列车”"),
    ("step", "2.2", "值班站长",
     "按照本节 4A2 有关“移开伤者的步骤”，在可行情况下尽快将被卷入车底的人移开轨道"),
    ("step", "2.3", "值班站长", "遵照本节 4A7 的程序，安排列车驶离事发现场后的事宜"),
]
CHUNKS["4A4"] = step_table(
    "程序", "需要先开动列车才能移动乘客，可遵照以下程序。", STEPS_4A4, lambda n: PAGES["4A4"])

# ---------------------------------------------------------------- 4A5
STEPS_4A5 = [
    ("step", 1, "值班站长",
     "按照本节 4A2 有关“移开伤者的步骤”，在可行的情况下尽快将被卷入车底的人移离轨道"),
    ("step", 2, "- 行车调度员\n- 值班站长\n- 驾驶员\n- 在站台值班的站务员",
     "遵照本节 4A6 的程序“开动列车”"),
    ("step", 3, "值班站长", "遵照本节 4A7 的程序，安排列车驶离事发现场后的事宜"),
]
CHUNKS["4A5"] = step_table(
    "程序", "需要在开动列车前移开被卷入车底的人，可遵照以下程序：", STEPS_4A5,
    lambda n: PAGES["4A5"])

# ---------------------------------------------------------------- 4A6
STEPS_4A6 = [
    ("step", 1, "值班站长",
     "被卷入车底的人是否移开轨道：\n· 若是：\n  - 确保轨道上没有任何人及设备；\n"
     "  - 将紧急停车按钮拨回「正常」位置；\n  - 通知行车调度员轨道已畅通无阻。\n· 若否：\n"
     "  - 确保被卷入车底的人及所有逗留在轨道上的人员远离列车，处于安全地方；\n"
     "  - 保持紧急停车按钮在「停车」位置"),
    ("step", 2, "值班站长",
     "若驾驶员不适合驾驶列车，安排一名合格的车站员工：\n· 陪同驾驶员，或\n· 驾驶列车，直至有人接替"),
    ("step", 3, "- 值班站长\n- 行车调度员", "双方商定：\n· 按情况需要安排清人；\n· 如何移动列车"),
    ("step", 4, "值班站长",
     "· 与驾驶员（或合格接替的车站员工）商议运作上的安排，包括车速及操作模式；\n· 将控制钥匙交还驾驶员"),
    ("step", 5, "- 驾驶员\n- 接替的驾驶员",
     "· 与值班站长确定运作上的安排，包括车速及操作模式；\n· 向值班站长取回控制钥匙；\n"
     "· 取得行车调度员授权开动列车"),
    ("step", 6, "行车调度员",
     "· 确保驾驶员/接替的驾驶员清楚明白运作安排；\n· 授权驾驶员/接替的驾驶员将列车驶离事发现场"),
    ("step", 7, "- 驾驶员\n- 接替的驾驶员", "获行车调度员授权后，按照商议的安排开动列车"),
    ("step", 8, "行车调度员",
     "安排：\n· 在首个适当地点替换事故列车；\n· 事故列车返回车辆段/停车场进行调查。\n"
     "注意：\n提醒车辆段/停车场调度员切勿清洗列车以保留证据，便于公安及调查人员进行调查"),
]
CHUNKS["4A6"] = step_table(
    "程序", "被卷入车底的人不论是否已移离轨道，开动列车前必须遵照以下程序：", STEPS_4A6,
    lambda n: PAGES["4A6"])

# ---------------------------------------------------------------- 4A7
STEPS_4A7 = [
    ("step", 1, "值班站长",
     "· 用粉笔划出乘客撞倒在轨道上的位置；\n· 用沙遮盖血渍；\n"
     "· 在以下行动完成后，通知行车调度员可以恢复列车服务：\n"
     "  - 轨道上已无任何人及工具；\n  - 紧急停车按钮已拨回「正常」位置。\n"
     "注意：\n上述行动可于稍后完成，避免延误恢复列车服务"),
    ("step", 2, "值班站长", "按情况需要取消车站管制"),
    ("step", 3, "行车调度员",
     "· 安排随后的列车进行轨道检查；\n· 恢复列车服务；\n· 计划对列车服务作必要调整"),
]
CHUNKS["4A7"] = step_table(
    "程序",
    "遇到下列情况时，值班站长及行车调度员须执行下列步骤：\n"
    "被卷入车底的人或物件已移离轨道；列车经已驶离事发现场。",
    STEPS_4A7, lambda n: PAGES["4A7"])

ORDER = ["4A", "4A1", "4A2", "4A3", "4A4", "4A5", "4A6", "4A7"]

OUT_DIR.mkdir(parents=True, exist_ok=True)

written, skipped = [], []
for sec in ORDER:
    if PAGES[sec] is None:
        skipped.append(sec)
        continue
    specs = CHUNKS[sec]
    ids = ["%s_%s_%03d" % (DOC_ID, sec, i) for i in range(1, len(specs) + 1)]
    lines = []
    for i, spec in enumerate(specs):
        pg, pp = spec.get("pages", PAGES[sec])
        if pg is None:
            raise SystemExit("section %s: page unknown for %r - re-extract the raw first"
                             % (sec, spec["title"]))
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
    written.append((out.name, len(specs)))

for name, n in written:
    print("%-30s %2d chunks" % (name, n))
if skipped:
    print("SKIPPED (pages 6-12 missing - re-extract AIEP04_p006-p012_raw.md): %s"
          % ", ".join(skipped))
print("written: %d files, %d chunks" % (len(written), sum(n for _, n in written)))
