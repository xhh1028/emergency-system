# -*- coding: utf-8 -*-
"""Build AIEP03 JSONL chunks from reviewed markdown.

Source : long_data/AIEP03_RAG/03_markdown_reviewed/*.md
Output : long_data/AIEP03_RAG/04_jsonl/AIEP03_<section>_chunks.jsonl

Notes
-----
* The 3A file holds two sections (3A 引言 + 3A1 一般指引), spanning pdf pages
  1-2. `section` varies between "3A 轻伤事故及三类延误" and "3A1 一般指引",
  while printed_page is labelled 3A-1 / 3A-2 for the whole file.

  These seven values carry a（待核对）suffix: AIEP04's raw extraction revealed
  that a page whose content straddles two subsections takes its footer from the
  dominant one (AIEP04 page 1 opens with the 4A 引言 but is footed 4A1-1). By
  that house style these pages would be 3A1-1 / 3A1-2, not 3A-1 / 3A-2. The
  scanned AIEP03 PDF cannot be rendered on this machine (no poppler/tesseract,
  no PDF library) so the real footer could not be read. Values are left as
  decided, marked 待核对, pending a look at the printed page. 3A2/3A3 pages are
  derived the same way but have no competing hypothesis.
* printed_page is DERIVED (1 PDF page = 1 printed page, counter per file); the
  scanned source PDF cannot be rendered here. source_page is exact, taken from
  the `===== Page N =====` markers in 02_markdown_raw/.
* `content` excludes the markdown headings - those live in `title`. This is a
  deliberate departure from the older root-level AIEP03_3A.jsonl, which
  prepended the heading path to every content string.
* The **重要：切勿使用或站在任何金属对象上** warning embedded in row 3 of the
  若电压 table stays inside that table_row per review decision; it is not
  lifted into its own notice chunk.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "long_data" / "AIEP03_RAG" / "04_jsonl"

DOC_ID = "AIEP03"
VERSION = "1.0"
EFFECTIVE_DATE = "待确认"

S3A = "3A 轻伤事故及三类延误"
S3A1 = "3A1 一般指引"
S3A2 = "3A2 处理触电"
S3A3 = "3A3 处理列车上的昏迷/受伤人士"

# ---------------------------------------------------------------- 3A
# (title, section, type, source_page, printed_page, content)
CHUNKS_3A = [
    ("引言", S3A, "text", "1", "3A-1（待核对）",
     "本章内容包含处理以下事件的方法及安全措施：\n"
     "- 轻伤事故及三类延误；\n"
     "- 袭击；\n"
     "- 危险事件。"),
    ("急救员", S3A1, "definition", "1", "3A-1（待核对）",
     "只有合格的急救员才可向伤者进行急救。"),
    ("急救箱", S3A1, "definition", "1", "3A-1（待核对）",
     "所有车站及其它地点均备有急救箱。急救箱：\n"
     "- 必须放于方便取用的位置，且\n"
     "- 不得挪作他用。"),
    ("进行急救的指引", S3A1, "list", "1", "3A-1（待核对）",
     "以下是进行急救的一般指引：\n"
     "- 需要支持，立刻求助；\n"
     "- 对伤者进行急救时，伤者坐下或卧下的姿势应根据情况而定；\n"
     "- 施行急救时，尽可能保障自己的安全；\n"
     "- 使用保护性衣物及设备；\n"
     "- 不要用手直接接触血液；\n"
     "- 不要给伤者服用任何药物；\n"
     "- 不要留下伤者单独一人。"),
    ("跟进行动", S3A1, "list", "2", "3A-2（待核对）",
     "以下说明发生事故、袭击及危险事件后应采取的跟进行动。\n"
     "- 如果伤亡涉及乘客则员工应尽量取得该件事故的任何独立目击证人的姓名、地址及联系电话。\n"
     "- 如果是员工受袭，伤亡涉及员工、承包商的员工，则无论是否有人受伤，"
     "任何直接牵涉该件事故的员工必须尽快通知其上司。\n"
     "- 如果伤亡涉嫌由于承包商的工程所导致，则必须将详情通知工地的承包商的高级主管或其代表。\n"
     "- 如果伤亡需要救护车到场，则地铁的主管人员必须安排员工陪同救伤队由指定入口前往伤者所处的位置。"),
    ("重要", S3A1, "notice", "2", "3A-2（待核对）",
     "重要：询问信息时，员工应体恤伤者或受惊的乘客。"),
    ("注意", S3A1, "notice", "2", "3A-2（待核对）",
     "注意：必须将遇袭后已采取的行动及证人资料详情，尽快向公交总队报告。"),
]

# ---------------------------------------------------------------- 3A2
CHUNKS_3A2 = [
    ("接触轨设备", S3A2, "list", "3", "3A2-1",
     "以下是处理接触轨设备触电的方法及安全措施。\n"
     "- 伤者身处接触轨设备 1 米范围内时，接触伤者前，先关断牵引电流。（见下文注意）\n"
     "- 伤者已完全移离带电的接触轨，且其身体任何部分都距离接触轨设备不少于 1 米时，"
     "伤者身上则不带危险电荷，与其接触也属于安全行为。\n"
     "- 确保你身体的任何部分和手持的任何物品不在接触轨设备 1 米范围内。\n"
     "- 不可走近任何连接或者触及带电轨道的对象 1 米范围内。"),
    ("注意", S3A2, "notice", "3", "3A2-1",
     "注意：遵循以下方法隔离牵引电流：\n"
     "- 要求行车调度员将电流关断，或\n"
     "- 操作紧急开关（如有）。"),
    ("非接触轨设备", S3A2, "text", "4", "3A2-2",
     "伤者触及非接触轨设备的带电导体时，须遵照下列方法和防范措施。"),
    ("超过 750 伏，或不知道电压值", S3A2, "table_row", "4", "3A2-2",
     "若电压：超过 750 伏，或不知道电压值；则："
     "- 接触伤者前，先切断电源\n"
     "- 立即将伤者移离导电体"),
    ("低于 750 伏，且开关按钮在附近", S3A2, "table_row", "4", "3A2-2",
     "若电压：- 低于 750 伏，且\n"
     "- 开关按钮在附近；则："
     "- 接触伤者前，先切断电源\n"
     "- 立即将伤者移开导电体"),
    ("低于 750 伏，且开关按钮不在附近或无法立即切断电源", S3A2, "table_row", "4", "3A2-2",
     "若电压：- 低于 750 伏，且\n"
     "- 开关按钮不在附近或无法立即切断电源；则："
     "- 站在干而不导电的物料上，例如木、厚报纸或橡胶\n"
     "- 立即将伤者移离导电体，利用：\n"
     "  - 双手，盖以不导电的物料，例如胶手套或干布料，或\n"
     "  - 一条干绳子或木棍（没有其它合适物料的情况下）\n"
     "\n"
     "重要：切勿使用或站在任何金属对象上"),
    ("移走伤者后", S3A2, "list", "5", "3A2-3",
     "伤者的外表可能看似死去或烧伤。将伤者移离带电的轨道或导电体后，须遵照下列指引：\n"
     "- 将伤者移至安全地方，最好在地面的高度；\n"
     "- 情况许可时，要求旁人召唤一名急救员到场照料伤者；\n"
     "- 立即召唤救护车到场；\n"
     "- 通知公交总队。"),
    ("救护车到达前", S3A2, "list", "5", "3A2-3",
     "救护车或急救人员到达前，须遵照以下指引：\n"
     "- 轻轻盖在烧伤的部位，可使用：\n"
     "  - 经消毒的干敷料（如纱布等），或\n"
     "  - 没有消毒敷料，也可使用任何干净清洁的材料。\n"
     "- 在伤处开始肿胀前，除去任何束缚伤处的衣饰。\n"
     "- 切勿尝试除去任何黏在烧伤部位的衣物。\n"
     "- 未经医生许可，切勿让伤者进食任何东西。\n"
     "- 未经医生许可，切勿让伤者走动。"),
]

# ---------------------------------------------------------------- 3A3
CHUNKS_3A3 = [
    ("引言", S3A3, "text", "6", "3A3-1",
     "本标题提供在不同情况下，处理列车上的昏迷/受伤人士的指引。"),
    ("迅即处理", S3A3, "procedure", "6", "3A3-1",
     "安全是公司营运的先决条件。因此，凡接获报告有乘客/员工昏迷/受伤时，必须：\n"
     "- 迅即处理；\n"
     "- 立即召唤救护车。"),
    ("在站台范围内，属于安全及适当的行为", S3A3, "table_row", "6", "3A3-1",
     "如果列车：在站台范围内；而且将有关人士移离列车：属于安全及适当的行为；则："
     "按需要用担架将有关人士移至站台的安全地方，实时替他/她进行急救"),
    ("在站台范围内，属于不安全及不适当的行为", S3A3, "table_row", "6", "3A3-1",
     "如果列车：在站台范围内；而且将有关人士移离列车：属于不安全及不适当的行为；则："
     "- 须安排 1 名员工在车上照料有关人士，直至救护人员到场\n"
     "- 根据情况，由曾经接受过急救训练的员工进行急救\n"
     "- 列车须停在站台，直至救护人员将有关人士移离列车"),
    ("在车站之间行驶", S3A3, "table_row", "6", "3A3-1",
     "如果列车：在车站之间行驶；而且将有关人士移离列车：不适用；则："
     "- 在下一站处理急救事宜\n"
     "- 须立即召唤救护车前往下一站"),
]

FILES = [("3A", CHUNKS_3A), ("3A2", CHUNKS_3A2), ("3A3", CHUNKS_3A3)]

OUT_DIR.mkdir(parents=True, exist_ok=True)

total = 0
for sec, chunks in FILES:
    lines = []
    for i, (title, section, type_, pg, pp, content) in enumerate(chunks, start=1):
        rec = {
            "chunk_id": "%s_%s_%03d" % (DOC_ID, sec, i),
            "doc_id": DOC_ID,
            "section": section,
            "title": title,
            "type": type_,
            "content": content,
            "source_page": pg,
            "printed_page": pp,
            "version": VERSION,
            "effective_date": EFFECTIVE_DATE,
            "parent_id": None,
        }
        lines.append(json.dumps(rec, ensure_ascii=False))
    out = OUT_DIR / ("%s_%s_chunks.jsonl" % (DOC_ID, sec))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    total += len(chunks)
    print("%-30s %2d chunks" % (out.name, len(chunks)))

print("total: %d chunks in %d files" % (total, len(FILES)))
