#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build RAG JSONL chunks by parsing the reviewed markdown. No hand-typed text.

Why this exists
---------------
build_aiep01_jsonl.py .. build_aiep10_jsonl.py all hold their chunk text as
hand-typed Python literals; none of them reads the markdown. Every mismatch
found so far traces back to that: AIEP02_2B5 says 达成 where the markdown says
达致, AIEP03_3A2 says 截断 where the markdown says 切断, and AIEP02_2B3 carries a
sentence the reviewed markdown had deleted. Hand-typing 19 more documents would
keep manufacturing that class of error, so from AIEP11 on the text comes from
the markdown and nothing else.

Usage
-----
    python build_from_md.py AIEP11                    # build one document
    python build_from_md.py AIEP11 AIEP12             # build several
    python build_from_md.py --audit AIEP10            # compare with what is there
    python build_from_md.py --audit AIEP10 --verbose  # and show the differences

--audit builds in memory and compares against the existing 04_jsonl without
writing anything, which is how this generator is validated against the ten
documents that were sliced by hand before it existed.

Input   long_data/AIEPXX_RAG/03_markdown_reviewed/*.md
Output  long_data/AIEPXX_RAG/04_jsonl/AIEPXX_<code>_chunks.jsonl
        long_data/AIEPXX_RAG/04_jsonl/AIEPXX_toc_chunks.jsonl   (via build_toc_jsonl)

Type policy
-----------
The same six rules AIEP08-10 follow, now applied mechanically:

1. A table with a 步骤 column -> one ``procedure`` parent holding the lead-in
   plus every step verbatim, and one ``procedure_step`` child per step. A phase
   row (a step cell that is a label with an empty action cell) goes into the
   parent as a label line and gets no child.
   With ``merge_step_tables`` a run of consecutive step tables in one clause
   becomes a single procedure instead - see the AIEP14 entry in DOC_OVERRIDES:
   the deciding question is whether the step *numbers* run on across the tables
   and reference each other, which makes the split a layout choice rather than a
   program boundary.
2. A table without a 步骤 column -> one ``table_row`` per row, content shaped
   ``表头：值；表头：值``. A row's first cell is its ``title``. The lead-in line
   above such a table becomes its own ``text`` chunk.
3. A standalone ``注意``/``重要`` block -> one ``notice`` chunk.
4. ``X 是指…`` -> ``definition``.
5. A clause whose body is bullets -> ``list``, with the lead-in sentence kept.
6. Anything else -> ``text``.

Fields
------
* ``section`` - the deepest ancestor heading that carries a section code
  (``8B3``, ``10A1``, ``2E2``), else the deepest ancestor heading, else the
  chapter. Matches how AIEP08-10 label their chunks.
* ``title`` - the clause's own heading, verbatim.
* ``source_page`` / ``printed_page`` - see page provenance below.
* ``version`` / ``effective_date`` - the corpus-wide values.

Page provenance
---------------
The reviewed markdown carries no page fields, so pages are resolved in order of
preference: the ``===== Page N =====`` markers of ``02_markdown_raw/`` if that
directory exists (this is what AIEP02/03 did), else the third-version long chunk
set ``JKR3_AIEPXX_*`` if it covers the document (this is what AIEP05-10 did).
If neither exists the page fields are written empty and the run prints a loud
warning: a page number is never invented.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _corpus_root(base):
    """The directory holding the AIEPxx_RAG folders.

    They sat directly under long_data/ until 2026-09-30, when all 26 were moved
    into long_data/AIEP/. Probing for the nested layout keeps this working either
    way instead of hard-coding a path that a reorganisation silently breaks -
    a wrong root makes the builder see zero documents, not an error.
    """
    nested = base / "AIEP"
    if nested.is_dir() and any(nested.glob("AIEP*_RAG")):
        return nested
    return base


LONG_DATA = _corpus_root(ROOT / "long_data")
LEGACY = ROOT / "long_chunk_681片_待复核" / "long_chunk"

# Page provenance harvested from the delivered chunks (build_page_map.py).
# LEGACY is authoritative when it exists; this is what keeps pages resolvable
# after that directory was removed from the repo on 2026-09-30.
PAGE_MAP_PATH = ROOT / "long_data" / "page_map.json"
_PAGE_MAP_CACHE = None


def _page_map():
    """The harvested page map for every document, loaded once per run."""
    global _PAGE_MAP_CACHE
    if _PAGE_MAP_CACHE is None:
        try:
            with open(PAGE_MAP_PATH, encoding="utf-8") as fh:
                _PAGE_MAP_CACHE = json.load(fh)
        except (OSError, ValueError):
            _PAGE_MAP_CACHE = {}
    return _PAGE_MAP_CACHE

VERSION = "1.0"
EFFECTIVE_DATE = "待确认"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SEP_RE = re.compile(r"^\|?\s*[-:| ]+\|?\s*$")
REVIEW_RE = re.compile(r"^#{1,6}\s*复核备注")
SECTION_CODE_RE = re.compile(r"^\d+[A-Z]+\d*")
CHAPTER_RE = re.compile(r"^第\s*\d+\s*章")
# The colon sits inside the bold marker in this corpus ("**注意：**"), so it has
# to be matched before the closing "**", not after it.
# A markdown image, "![描述](../assets/x.png)". clean() turns it into the
# corpus's own placeholder, "[图片：描述]".
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
NOTICE_RE = re.compile(r"^(?:\*\*)?(注意|重要)\s*[：:]\s*(?:\*\*)?\s*(.*)$")
BULLET_RE = re.compile(r"^\s*[-•]\s+")
BLOCKQUOTE_RE = re.compile(r"^\s*>\s?")
ORDERED_RE = re.compile(r"^(\d+)\.\s+(.*)$")
# The manual numbers its flow-chart nodes 1.1, 1.2 inside an outer list item
# ("1. **1.1 [A] …**", later ones with a ↓ in front), so the node's own number
# is the one to use. Deliberately NOT anchored: search() with an anchored
# pattern only matches at index 0, so "↓ 1.2 …" would fall back to the outer
# ordinal. Callers bound how far along the line it may match instead.
# A line that announces a flow-chart node: optional list marker, optional ↓,
# the node number, then the node's text. Kept in one pattern so the node can be
# found at the top level ("2. ↓ 1.2 …") or nested ("  - 1.4 …"). The trailing
# letter is for AIEP21's split nodes (1.3a / 1.3b), which are separate steps.
NODE_LINE_RE = re.compile(r"^\s*(?:[-•]\s+|\d+\.\s+)?(?P<arrow>↓\s*)?"
                          r"(?P<node>\d+\.\d+[a-z]?)\s*(?P<rest>.*)$")
DEFINITION_RE = re.compile(r"是指")
# A body that still carries the arrows and judgement nodes of a converted flow
# chart is prose, not a step list: AIEP09 9C2 and AIEP10 10A1 are whole-chunk
# texts. Splitting them on their bullets would invent a step ordering.
FLOW_RE = re.compile(r"流程图|走向|→")
# A table whose first column is just a row number (AIEP14's 四种情况 uses
# "1".."4") gives every row an indistinguishable title. Those rows get their
# column header prepended, so the title reads "情况 1". Roman numerals count for
# the same reason - AIEP24 24A1's 烈度 column runs I..XII, and a chunk titled
# "V" says nothing. Corpus-wide only AIEP24's two tables have such a first cell.
NUMERIC_CELL_RE = re.compile(r"^[0-9０-９]{1,2}$|^[IVX]{1,5}$")
# A short bare line sitting directly above a step table names the group rather
# than introducing it: AIEP14 14A2 lays one 1..11 flow out as
# "**使用载客列车**", "**使用指定的无载客列车**", "**后续**". Without this every
# group's procedure would be titled 程序 and they would be indistinguishable.
GROUP_LABEL_RE = re.compile(r"^[^\n：。；，、]{1,16}$")
# Column names that mark a table as an ordered procedure. 步骤 is the manual's
# usual word (121 tables); 阶段 is used once, by AIEP16 16A6's 调查程序, whose
# five phases are an ordered sequence exactly like a 步骤 column. Adding it here
# rather than special-casing that document keeps the rule "an ordered table is a
# procedure" independent of which noun the header happens to use.
STEP_HEADERS = ("步骤", "阶段")


# --------------------------------------------------------------------------- #
# Markdown -> elements
# --------------------------------------------------------------------------- #

class Heading(object):
    def __init__(self, level, text, line):
        self.level, self.text, self.line = level, text, line


class Table(object):
    def __init__(self, header, rows, line):
        self.header, self.rows, self.line = header, rows, line


class Notice(object):
    def __init__(self, label, body, line):
        self.label, self.body, self.line = label, body, line


class Block(object):
    """Prose and bullets are one element: a lead-in plus its list, or prose."""

    def __init__(self, lines, line):
        self.lines, self.line = lines, line

    @property
    def is_bullets(self):
        return any(BULLET_RE.match(l) for l in self.lines)


def clean(text):
    """Strip the inline markup the corpus stores as plain text."""
    text = text.replace("<br>", "\n").replace("&nbsp;", " ")
    # "**重要：** 如生命受到威胁" is stored as "重要：如生命…" - the marker's own
    # trailing space goes with the marker, or every such cell gains a stray space.
    text = re.sub(r"\*\*(注意|重要)[：:]\*\*[ \t]*", r"\1：", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # An escaped asterisk is a footnote marker, not a literal backslash:
    # AIEP19 19A's "\\* 尽管控制方案被停止…" is stored as "* 尽管…".
    text = text.replace("\\*", "*")
    # "[？]" is the reviewer's flag, never manual text: slicing rule 4 keeps it
    # out of content (the per-document builders of AIEP01-09 stripped it, and
    # AIEP08/09 assert its absence). The generic builder carried 复核备注
    # stripping but not this one, so AIEP25 25A's bare marker was the only one
    # left in the corpus. Only the marker itself goes; a marker followed by an
    # inline review note has no instance under this builder yet.
    text = text.replace("[？]", "")
    # A figure is stored as the corpus's placeholder, "[图片：描述]": its pixels
    # are not retrievable text, and "![](../assets/x.png)" carries a repo-relative
    # link that does not resolve (AIEP28 28G is the corpus's only markdown image;
    # AIEP27 27A already writes its figure cells as "[图片：…]"). The description
    # is manual text and stays; the link goes. Global rather than per-document
    # because "![" occurs in exactly one file of the whole corpus, so no
    # delivered chunk can be touched by it.
    text = IMAGE_RE.sub(lambda m: "[图片：%s]" % m.group(1).strip(), text)
    return text


def split_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return [clean(c) for c in cells]


def open_bullet_item(pending):
    """True when ``pending`` ends inside the text of a bullet item.

    A list item's text may run on to indented continuation lines - 26A3 writes
    "- 考虑因素" and then "  根据内部调查…" under it - so the last line alone
    does not say whether an item is still open. Walk back over indented and
    blank lines to the first line that is neither, counting an indented bullet
    ("  - 建议…") as a bullet: if that line is one, the item is open.
    """
    for line in reversed(pending):
        if BULLET_RE.match(line):
            return True
        if line.strip() and not line[:1].isspace():
            return False
    return False


def parse_markdown(path):
    """[(Heading | Table | Notice | Block), ...] for one reviewed file."""
    raw = path.read_text(encoding="utf-8").split("\n")
    start = front_matter_end(raw)
    elements = []
    pending = []            # accumulated prose/bullet lines
    table_buf = []
    fenced = False

    def flush_pending():
        if pending:
            elements.append(Block(list(pending), 0))
            del pending[:]

    i = start
    while i < len(raw):
        line = raw[i]
        if REVIEW_RE.match(line):
            break                                   # review commentary: not manual
        if FENCE_RE.match(line):
            if fenced:
                fenced = False
                i += 1
                continue
            flush_pending()
            fenced = True
            i += 1
            body = []
            while i < len(raw) and not FENCE_RE.match(raw[i]):
                body.append(clean(raw[i]))
                i += 1
            if body:
                elements.append(Block(body, 0))     # diagram content, markers gone
            continue
        if line.lstrip().startswith(">"):
            # A blockquote is markup, not content: AIEP18 18B's 图例 is written
            # as "> 图例：" / "> - **A** = …". The marker is dropped and the text
            # kept, exactly as <br> and ** are handled elsewhere.
            line = BLOCKQUOTE_RE.sub("", line, count=1)
            if line.strip():
                pending.append(clean(line))
            i += 1
            continue
        m = HEADING_RE.match(line)
        if m:
            flush_pending()
            elements.append(Heading(len(m.group(1)), clean(m.group(2)), i))
            i += 1
            continue
        if line.lstrip().startswith("|"):
            flush_pending()
            table_buf = [line]
            i += 1
            while i < len(raw) and raw[i].lstrip().startswith("|"):
                table_buf.append(raw[i])
                i += 1
            header, rows = None, []
            for ln in table_buf:
                if SEP_RE.match(ln):
                    continue
                cells = split_row(ln)
                if header is None:
                    header = cells
                else:
                    rows.append(cells)
            if header and rows:
                elements.append(Table(header, rows, 0))
            continue
        if NOTICE_RE.match(line) and not BULLET_RE.match(line):
            # Read the pending lines BEFORE flushing them: they are what say
            # whether a bullet item is still open above this notice. Flushing
            # first is why the old ``prev_bullet`` test never fired - it always
            # looked at an empty list.
            prev_bullet = bool(pending and BULLET_RE.match(pending[-1]))
            item_open = open_bullet_item(pending)
            flush_pending()
            label, rest = NOTICE_RE.match(line).groups()
            body = [rest] if rest.strip() else []
            # A marker alone on its line keeps a newline before its body
            # ("注意：\n火警扑熄后…"); one followed by text on the same line does
            # not ("注意：若最后证实…"). Both forms are in the corpus.
            glued = bool(rest.strip())
            j = i + 1
            nxt = next_nonblank(raw, i)
            # A notice carrying its own text, dropped into the middle of a
            # bullet list, is a one-line notice: the bullets that follow
            # continue the list rather than becoming its body. Requiring
            # ``glued`` keeps the other shape intact - a bare "注意：" followed
            # by bullets owns them (AIEP09 9A), because there the bullets ARE
            # its body. The 26A3 case needed ``open_bullet_item``: its notice
            # sits after "- 考虑因素" plus that item's continuation line, and
            # the last-line test missed the open item, so the notice swallowed
            # 结论/建议/签字人 and the next 注意 with them.
            inline = glued and BULLET_RE.match(nxt or "") and (
                prev_bullet or item_open)
            if not inline:
                while j < len(raw):
                    nxtline = raw[j]
                    if nxtline.strip() and (HEADING_RE.match(nxtline) or
                                            nxtline.lstrip().startswith("|") or
                                            FENCE_RE.match(nxtline) or
                                            REVIEW_RE.match(nxtline)):
                        break
                    if nxtline.strip():
                        body.append(clean(nxtline))
                    j += 1
            text = "\n".join(b for b in body if b.strip())
            elements.append(Notice(label, ("%s：%s" % (label, text)) if glued
                                   else ("%s：\n%s" % (label, text)), i))
            i = j if not inline else i + 1
            continue
        if line.strip():
            pending.append(clean(line))
        i += 1
    flush_pending()
    return elements


def front_matter_end(raw):
    if not raw or raw[0].strip() != "---":
        return 0
    for i in range(1, min(len(raw), 30)):
        if raw[i].strip() == "---":
            return i + 1
    return 0


def front_matter_value(path, key):
    """Read one front-matter field, e.g. the ``section:`` of a reviewed file."""
    raw = path.read_text(encoding="utf-8").split("\n")
    end = front_matter_end(raw)
    if not end:
        return ""
    for line in raw[1:end - 1]:
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def select_files(md_files, skips=()):
    """[(path, code), ...] - one file per (code, declared section), largest wins.

    Two files can share a section code for opposite reasons, and the section
    they declare is what tells them apart:

    * The same section written twice - AIEP12 has an unfinished 12A6 draft
      beside the file that superseded it, and a smaller copy of 12D2 beside the
      full one. Both declare the same ``section:``, and the extra is a subset,
      so the larger file is kept and the other is reported as skipped.
    * Different sections that happen to share a code - AIEP25 splits 25A into
      three files (综览, 员工伤亡报告流程, 原因定义与补充资料) whose ``section:``
      lines differ. None supersedes another, so all three are kept. Keying on
      the code alone would have silently dropped two of them.

    When a code ends up on more than one surviving file, each gets the third
    underscore-separated field of its filename appended ("25A_综览"), so the
    chunk files and chunk_ids stay distinct.

    Deliberately NOT keyed on front-matter ``status``: AIEP01-04 are
    ``status: reviewed`` and are all legitimately part of the corpus, so
    requiring ``verified`` would drop four documents without saying so.
    """
    groups, order, skipped = {}, [], []
    for path in md_files:
        if path.name in skips:
            skipped.append((path.name, "listed in skip_files"))
            continue
        code = path.stem.split("_")[1]
        # A file with no declared section is its own group, keyed by name.
        section = front_matter_value(path, "section") or path.stem
        key = (code, section)
        if key not in groups:
            groups[key] = path
            order.append(key)
        elif path.stat().st_size > groups[key].stat().st_size:
            skipped.append((groups[key].name, "superseded by " + path.name))
            groups[key] = path
        else:
            skipped.append((path.name, "superseded by " + groups[key].name))

    counts = Counter(key[0] for key in order)
    out = []
    for key in order:
        path = groups[key]
        code = key[0]
        if counts[code] > 1:
            parts = path.stem.split("_")
            if len(parts) > 2:
                code = "%s_%s" % (code, parts[2])
        out.append((path, code))
    return out, skipped


def next_nonblank(raw, i):
    for j in range(i + 1, len(raw)):
        if raw[j].strip():
            return raw[j]
    return ""


# --------------------------------------------------------------------------- #
# Elements -> chunks
# --------------------------------------------------------------------------- #

def section_of(stack):
    """The deepest ancestor heading carrying a section code, else the deepest."""
    coded = [h.text for h in stack if SECTION_CODE_RE.match(h.text)]
    if coded:
        return coded[-1]
    if stack:
        return stack[-1].text
    return ""


def clause_section(stack, code, overrides, own):
    """``section_of``, with the file's code prefixed where the file declares it.

    ``own`` is the heading that opens the clause - or, for content standing
    before the file's first heading, the deepest heading on the stack. A file
    named in the document's ``section_code_prefix_files`` writes its sections as
    "<code> <own heading>": 25A's three files have uncoded clause headings, so
    without this 综览 would report its coded ancestor's text ("25A 报告不如意
    事件", which reads as if it were the section itself) and the other two would
    report a bare heading carrying no code at all.

    Only ``own`` is taken from the clause: the code comes from the file, so the
    mapping invents no text and a coded heading (25B-25E's "## 25B 呈报事故")
    keeps the plain ``section_of`` result. The section string feeds the page
    lookup through its leading code only (see ``section_code`` below), and
    ``code.split("_")[0]`` is the same token the lookup already falls back to -
    so this renames the field without moving any page.
    """
    if code in (overrides.get("section_code_prefix_files") or ()) and own \
            and not SECTION_CODE_RE.match(own):
        return "%s %s" % (code.split("_")[0], own)
    return section_of(stack)


def column_label(header):
    """The canonical cell label, not the header's exact wording.

    AIEP10 10B9's table heads its second column 负责人员及行动 and the corpus
    still labels the value 行动, so 行动 wins when it appears at all; 负责人员
    is the other label the corpus uses. Any other column keeps its own header.
    """
    if "行动" in header:
        return "行动"
    if "负责人员" in header:
        return "负责人员"
    return header.strip()


def render_step_table(table, lead):
    """(parent_content, [(step_no, content), ...]) for a 步骤 table.

    Non-step columns are labelled with their own header text, so a table with a
    负责人员 column renders 步骤：N；负责人员：X；行动：Y and a table without
    one renders 步骤：N；行动：Y - the two shapes AIEP08-10 already use.
    """
    si = next((i for i, h in enumerate(table.header)
               if any(word in h for word in STEP_HEADERS)), 0)
    others = [i for i in range(len(table.header)) if i != si]
    body, children = [], []
    for row in table.rows:
        cells = row + [""] * (len(table.header) - len(row))
        step = cells[si].strip()
        parts = [c.strip() for c in (cells[i] for i in others) if c.strip()]
        if not parts:                           # phase row: a label, not a step
            if step:
                body.append(step)
            continue
        labelled = []
        for i in others:
            value = cells[i].strip()
            if value:
                labelled.append("%s：%s" % (column_label(table.header[i]), value))
        line = "步骤：%s；%s" % (step, "；".join(labelled))
        body.append(line)
        children.append((step, line))
    content = (lead + "\n" if lead else "") + "\n".join(body)
    return content, children


def table_row_content(header, row):
    parts = []
    for h, c in zip(header, row + [""] * (len(header) - len(row))):
        if c:
            parts.append("%s：%s" % (h, c))
    return "；".join(parts)


def row_prefix(title, ancestors, overrides):
    """A field prepended to every table row, taken from a heading.

    AIEP12's 12D2/12D3 split one table into "##### 4 号线车站" and
    "##### 大兴线车站". Sliced per station, a row like 高米店南 / B1 口 would
    otherwise lose which line it belongs to, so the line name is carried into the
    content. The value comes from the heading in the markdown - nothing here is
    written by hand - and the trailing 车站 is dropped to leave "4 号线".

    The heading is usually the clause's OWN title: 4 号线车站 carries no prose,
    so it opens a clause whose only element is the table. Ancestors are checked
    too, for the case where the split heading does carry a lead-in.
    """
    pattern = overrides.get("row_prefix_ancestor_re")
    if not pattern:
        return ""
    field = overrides.get("row_prefix_field", "线路")
    for heading in [title] + list(reversed(ancestors)):
        m = re.match(pattern, heading or "")
        if m:
            return "%s：%s；" % (field, m.group(1))
    return ""


def topic_chunks(section, title, elements, pages, overrides, ancestors=()):
    """Chunks for one clause: its heading plus the elements under it.

    A clause's prose and bullets accumulate into ONE chunk, flushed only when a
    table or a notice interrupts. That is the shape AIEP08-10 use: a lead-in
    sentence and the list under it are one ``list`` chunk, not two, and a
    paragraph that follows the list (a 参考 line, say) stays with it.

    Blank lines inside a clause are dropped. The hand-built chunks are not
    consistent about them - AIEP10_10A2_004 closes the gap between its lead-in
    and its bullets while AIEP10_10B10-10B12_004 keeps it - so one rule is
    picked (compact) rather than mirroring an artefact.
    """
    page, printed = pages
    out = []
    buf = []

    def flush(kind=None):
        if not buf:
            return
        lines = [l for l in buf if l.strip()]
        del buf[:]
        text = "\n".join(lines).strip()
        if not text:
            return
        if overrides.get("numbered_list_as_steps"):
            # A clause whose body is an ordered list is a flow written as a
            # list rather than a table (AIEP18 18B's 流程图). Split it into one
            # procedure and one child per node, the shape rule 1 asks for.
            head, steps = split_ordered_steps(lines)
            if steps:
                body = head + ["\n".join("步骤：%s；行动：%s" % (n, t)
                                         for n, t in steps)]
                out.append(new(section, title, "procedure",
                               "\n".join(body).strip(), page, printed))
                for n, t in steps:
                    out.append(new(section, "%s-步骤%s" % (title, n),
                                    "procedure_step", "步骤：%s；行动：%s" % (n, t),
                                    page, printed, parent="prev"))
                return
        type_ = kind
        if type_ is None:
            if FLOW_RE.search(text):
                type_ = "text"
            elif any(BULLET_RE.match(l) for l in lines):
                type_ = "list"
            elif DEFINITION_RE.search(text):
                type_ = "definition"
            else:
                type_ = "text"
        forced = overrides.get("force_type_titles", {}).get(title)
        if forced:
            type_ = forced
        out.append(new(section, title, type_, text, page, printed))

    # merge_step_tables: consecutive step tables in one clause become ONE
    # procedure whose content carries the labels between them, instead of one
    # procedure per table. See DOC_OVERRIDES["AIEP14"] for why.
    merge_steps = bool(overrides.get("merge_step_tables"))
    whole_text = overrides.get("whole_table_as_text")
    proc = None

    def flush_proc():
        nonlocal proc
        if proc is None:
            return
        body = "\n".join(l for l in proc["content"] if l.strip()).strip()
        out.append(new(section, proc["title"], "procedure", body, page, printed))
        for step, line in proc["children"]:
            out.append(new(section, "%s-步骤%s" % (proc["title"], step),
                            "procedure_step", line, page, printed, parent="prev"))
        proc = None

    lead = None
    i = 0
    while i < len(elements):
        el = elements[i]
        if isinstance(el, Table):
            if any(w in h for h in el.header for w in STEP_HEADERS):
                lead = "\n".join(buf).strip()
                del buf[:]
                if merge_steps:
                    if proc is None:
                        proc = {"title": title, "content": [], "children": []}
                        if lead:
                            proc["content"].append(lead)
                    elif lead:
                        proc["content"].append(lead)   # label between tables
                    content, children = render_step_table(el, "")
                    proc["content"].extend(content.split("\n"))
                    proc["children"].extend(children)
                    i += 1
                    continue
                # A bare label above the table names this group; it stays in the
                # content as well, so no markdown text is lost to the title.
                group = lead if GROUP_LABEL_RE.match(lead) else title
                content, children = render_step_table(el, lead or "")
                out.append(new(section, group, "procedure", content, page, printed))
                for step, line in children:
                    # "prev": the procedure this group starts with. Resolved per
                    # file in finalize, because a topic-local index is wrong once
                    # the topics of a file are concatenated.
                    out.append(new(section, "%s-步骤%s" % (group, step),
                                    "procedure_step", line, page, printed,
                                    parent="prev"))
                lead = None
            elif whole_text and (whole_text is True or title in whole_text):
                # Keep the clause's prose and its table in ONE text chunk. Used
                # where the table's rows carry no context of their own: AIEP19's
                # 检查点站台 rows are just station names, and only the paragraph
                # above the table says which line they belong to. Row-slicing
                # would put "黄村西大街 / 中关村" in a chunk with no mention of
                # 4 号线, and a question about 4 号线 would not reach it.
                flush_proc()
                body = [l for l in buf if l.strip()]
                del buf[:]
                for row in el.rows:
                    body.append(table_row_content(el.header, row))
                out.append(new(section, title, "text", "\n".join(body).strip(),
                               page, printed))
            elif title in overrides.get("whole_table_titles", ()):
                rows = "\n".join(table_row_content(el.header, r) for r in el.rows)
                flush_proc()
                flush()
                out.append(new(section, title, "table_row", rows, page, printed))
            elif overrides.get("group_rows_by_first_cell"):
                # One chunk per RUN of consecutive rows sharing a first cell.
                # AIEP24 24B1's 指引 table has nine rows but four intensity
                # bands (I 至 IV ×2, V 至 VI ×2, VII ×3, VII 以上 ×2), and the
                # band is what a reader looks up. Per-document because the same
                # shape occurs in six documents already delivered (AIEP01, 03,
                # 10, 12, 19), where regrouping would rewrite their chunks.
                flush_proc()
                flush()
                prefix = row_prefix(title, ancestors, overrides)
                strip_marker = bool(overrides.get("strip_title_markers"))
                merged = []
                for row in el.rows:
                    cells = row + [""] * (len(el.header) - len(row))
                    key = clean_title(cells[0], strip_marker)
                    if merged and first_cell(merged[-1][0], el.header,
                                             strip_marker) == key:
                        merged[-1].append(row)
                    else:
                        merged.append([row])
                # Only a table that actually groups keeps its first cell
                # verbatim ("I 至 IV"). Where every group is a single row the
                # table is an ordinary per-row one, so it gets the usual header
                # prefix - otherwise turning this switch on for a document would
                # also strip the prefix from its other tables (24A1's 烈度 column
                # would read I, II, … instead of 烈度 I, 烈度 II, …).
                grouped = any(len(g) > 1 for g in merged)
                for group in merged:
                    key = first_cell(group[0], el.header, strip_marker)
                    if (not grouped and len(el.rows) > 1
                            and NUMERIC_CELL_RE.match(key)):
                        key = "%s %s" % (el.header[0].strip(), key)
                    body = "\n".join(table_row_content(el.header, r) for r in group)
                    out.append(new(section, key, "table_row", prefix + body,
                                   page, printed))
            else:
                flush_proc()
                flush()
                prefix = row_prefix(title, ancestors, overrides)
                # A first column that says the same thing on every row cannot
                # tell one row from another - AIEP19 19B's 检查点站台 table has
                # "（车站）" down the whole column - so the title comes from the
                # cells after it. Opt-in per document: applying it corpus-wide
                # would also rewrite AIEP12 12D1's two titles, and that file has
                # already been delivered.
                const_first = (len(el.rows) > 1 and
                               len({(r[0] if r else "") for r in el.rows}) == 1)
                use_following = (const_first and
                                 overrides.get("row_title_from_following_cells"))
                for row in el.rows:
                    cells = row + [""] * (len(el.header) - len(row))
                    j = next((i for i, c in enumerate(cells) if c), None)
                    key = clean_title(cells[j] if j is not None else "",
                                      bool(overrides.get("strip_title_markers")))
                    if (j is not None and len(el.rows) > 1
                            and NUMERIC_CELL_RE.match(key.strip())):
                        # Row numbers are not names: label the chunk with the
                        # column header so it reads "情况 1", not "1". Only in a
                        # table with several rows - a lone number in a one-row
                        # table is a value, not a position in a sequence, so it
                        # is left alone.
                        key = "%s %s" % (el.header[j].strip(), key.strip())
                    elif use_following:
                        rest = [c.split("\n")[0].strip() for c in cells[1:] if c.strip()]
                        if rest:
                            key = " / ".join(rest)
                    out.append(new(section, key, "table_row",
                                    prefix + table_row_content(el.header, row),
                                    page, printed))
            i += 1
            continue
        if isinstance(el, Notice):
            flush_proc()
            flush()
            out.append(new(section, el.label, "notice", el.body, page, printed))
            i += 1
            continue
        buf.extend(el.lines)
        i += 1
    flush_proc()
    flush()
    return out


def clean_title(text, strip_marker=False):
    """A cell's text as a chunk title: first line, optionally no list marker.

    AIEP25 25E's roster row names two people in one cell ("- 运营总管<br>- 工程
    总管"), so its title is the first name rather than "- 运营总管".

    ``strip_marker`` is opt-in because a title carrying a stray "- " is not only
    AIEP25's problem: AIEP12_12A7_003's title is "- 带上所有关于管理夜间工程
    领域的文件前往控制车站". Stripping it there would improve the title but
    rewrite a file that has already been delivered, so the strip waits until
    that document is re-uploaded for another reason. Logged as A30.
    """
    line = (text or "").strip().split("\n")[0].strip()
    m = BULLET_RE.match(line)
    return line[m.end():].strip() if (m and strip_marker) else line


def first_cell(row, header, strip_marker=False):
    """The row's identifying cell, as used for a chunk title."""
    cells = row + [""] * (len(header) - len(row))
    return clean_title(cells[0], strip_marker)


def split_ordered_steps(lines):
    """(lead_lines, [(node_id, text), ...]) for a flow written as a list.

    Used by ``numbered_list_as_steps`` (AIEP18 18B, AIEP19 19B). The manual
    numbers its flow-chart nodes 1.1, 1.2 … and everything before node 1.1 is
    the header. Nodes are found wherever they start a line, at the top level or
    inside a nested bullet, because the two documents distribute them
    differently:

        AIEP18  "1. **1.1 [A] …**"          one node per top-level item
        AIEP19  "- **1.2 事故处理主任**："   two nodes nested under one item

    A node keeps every line up to the next node, so nothing is dropped; framing
    lines between nodes (AIEP19's 「左侧注释」「并行分支」) end up at the end of the
    preceding node's text. List markers and the node's own number are removed -
    the number becomes the step id, so stating it twice would be noise - while
    the ↓ sequence arrows stay, since they carry meaning.

    A body with no node numbers at all falls back to the ordered list's own
    numbering, one step per item.
    """
    head, steps, cur = [], [], None
    for line in lines:
        m = NODE_LINE_RE.match(line)
        if m:
            if cur is not None:
                steps.append(cur)
            text = ((m.group("arrow") or "") + m.group("rest")).strip()
            cur = [m.group("node"), text]
            continue
        if cur is not None:
            cur[1] = (cur[1] + "\n" + line).strip()
        else:
            head.append(line)
    if cur is not None:
        steps.append(cur)
    if steps:
        return head, [(s, t) for s, t in steps]

    # No node numbers: fall back to the list's own numbering.
    head, steps, cur = [], [], None
    for line in lines:
        m = ORDERED_RE.match(line)
        if m:
            if cur is not None:
                steps.append(cur)
            cur = [m.group(1), m.group(2).strip()]
            continue
        if cur is not None:
            cur[1] = (cur[1] + "\n" + line).strip()
        else:
            head.append(line)
    if cur is not None:
        steps.append(cur)
    return head, [(s, t) for s, t in steps]


def new(section, title, type_, content, page, printed, parent=None):
    return {"section": section, "title": title, "type": type_, "content": content,
            "source_page": page, "printed_page": printed, "_parent": parent}


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

def pages_from_raw(doc):
    """topic heading -> PDF page, from the ``===== Page N =====`` raw markers.

    Only the PDF page is recoverable this way. The printed page ("10A1-1") also
    encodes the section, and no rule for deriving it from the PDF page alone is
    established - AIEP02/03's builders each hard-coded their own - so it is left
    empty rather than guessed, and the legacy set is preferred when it exists
    because it carries both fields.
    """
    raw_dir = LONG_DATA / ("%s_RAG" % doc) / "02_markdown_raw"
    if not raw_dir.is_dir():
        return {}
    out, page = {}, 1
    for path in sorted(raw_dir.glob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except OSError:
            continue
        for line in lines:
            m = re.match(r"^=====\s*Page\s+(\d+)\s*=====", line.strip())
            if m:
                page = int(m.group(1))
                continue
            m = HEADING_RE.match(line)
            if m:
                out.setdefault(m.group(2).strip(), str(page))
    return out


def page_key(text):
    """Normalise a heading for matching between the markdown and the legacy set.

    The legacy filenames sanitise "/" and "-" into "_" ("在车辆段/停车场正门
    当值指引" is stored as 在车辆段_停车场正门当值指引), so an exact comparison
    misses every title containing them. Punctuation and spacing are therefore
    dropped on both sides.
    """
    return re.sub(r"[\s/_\-－—·（）()、，,。.]", "", text or "")


def pages_from_legacy(doc):
    """normalised topic title -> (source_page, printed_page), from the legacy set."""
    out = {}
    for path in sorted(LEGACY.glob("JKR3_%s_*.txt" % doc)):
        meta = {}
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.rstrip("\r\n")
                    if line.startswith("【正文】"):
                        break
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
        except OSError:
            continue
        # The filename is JKR3_<doc>_<n>_<code>_<section>_<topic>. The legacy
        # names cannot say where the section ends and the topic begins, because
        # they turn "/" into "_": a section of 车辆段/停车场处理降雪天气
        # contributes an "_" of its own, and splitting on the first one leaves
        # the topic as 停车场处理降雪天气_车辆段_停车场DCC - a key no clause title
        # contains. AIEP29 29D's DCC clause was filed against the preceding
        # clause's page that way (the slicer warned "inherited the preceding
        # clause's page"). Register every suffix of the tail instead: the real
        # topic is always one of them, legacy_lookup prefers the longest match,
        # and the whole tail is kept as a key for the entries that stop at the
        # section (JKR3_AIEP12_0018_12A4_控制车站的职责.txt carries that
        # section's own body, so its name doubles as the topic).
        m = re.match(r"^JKR3_%s_\d+_(\d+[A-Z]+\d*)_(.+)\.txt$" % doc, path.name)
        code = m.group(1) if m else ""
        rest = m.group(2) if m else path.stem
        parts = rest.split("_")
        topics = ["_".join(parts[i:]) for i in range(len(parts))]
        pdf, printed = meta.get("PDF页序", ""), meta.get("印刷页码", "")
        for topic in topics:
            out[(code, page_key(topic))] = (as_range(pdf, "-"),
                                            as_range(printed, "~"))
    # The legacy long-slice set that carried every page number was removed from
    # the repository on 2026-09-30 (the reviewed markdown has no page footers -
    # the sources are scans). The same (code, topic) -> (source, printed) pairs
    # are harvested out of the delivered chunks by build_page_map.py, so a
    # rebuild still resolves pages instead of shipping empty fields (E2).
    # setdefault, not assignment: a restored legacy directory stays authoritative.
    for code, topics in _page_map().get(doc, {}).items():
        for topic, pages in topics.items():
            out.setdefault((code, topic), tuple(pages))
    return out


def as_range(value, sep):
    """Collapse a legacy comma list into a range: "3,4,5" -> "3-5".

    The legacy set lists every page of a span ("24A1-1,24A1-2,24A1-3"), but the
    chunk schema holds one range. Replacing each comma with the separator - the
    first thing this did - produced "24A1-1~24A1-2~24A1-3", which no longer
    matches the format the checker accepts, and 36 W16 warnings followed. Two
    already-delivered documents fix the convention: AIEP05 writes 5A1-1~5A1-3
    and AIEP06 writes 6B-1~6B-3 for exactly this shape.
    """
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if len(parts) <= 1:
        return value.strip()
    return "%s%s%s" % (parts[0], sep, parts[-1])


def legacy_lookup(legacy, code, heading):
    """Exact (section code, topic) match, else the longest contained topic.

    The key must include the section code: clause titles repeat across sections
    (报告详情 is in both 9C1 and 9E, 程序 in every 10B4-10B7 section), so a map
    keyed on the title alone silently returns whichever came last.

    Containment then covers the legacy set naming a clause more fully than the
    markdown does - 10B8's 列车离开车辆段 is stored as 列车离开车辆段/停车场.
    """
    key = page_key(heading)
    if not key:
        return "", ""
    if (code, key) in legacy:
        return legacy[(code, key)]
    best = ""
    for c, candidate in legacy:
        if c != code:
            continue
        if key in candidate or candidate in key:
            if len(candidate) > len(best):
                best = candidate
    return legacy[(code, best)] if best else ("", "")


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

APPROXIMATED = []
INHERITED = []


def build_document(doc, audit=False, verbose=False):
    doc_dir = LONG_DATA / ("%s_RAG" % doc)
    md_dir = doc_dir / "03_markdown_reviewed"
    out_dir = doc_dir / "04_jsonl"
    if not md_dir.is_dir():
        raise SystemExit("no %s" % md_dir)

    legacy = pages_from_legacy(doc)
    raw_pages = pages_from_raw(doc)
    overrides = DOC_OVERRIDES.get(doc, {})
    files, skipped = select_files(sorted(md_dir.glob("*.md")),
                                  overrides.get("skip_files", ()))
    for name, why in skipped:
        print("    (skipped %s: %s)" % (name, why))
    results = []
    for md, code_override in files:
        code = code_override or md.stem.split("_")[1]
        elements = parse_markdown(md)
        last_pages = None             # page of the last clause resolved, per file
        stack, page, printed = [], "", ""
        topics, cur = [], None
        for el in elements:
            label_re = overrides.get("subheading_label_re")
            if isinstance(el, Heading):
                if (label_re and not SECTION_CODE_RE.match(el.text)
                        and re.match(label_re, el.text)):
                    # A sub-heading that names a part of a flow is a label, not
                    # a clause of its own. AIEP20 20B writes its flow as
                    # "#### 1. OCC 人员的准备" … "#### 4. 开始作业", each holding
                    # its nodes; AIEP25 25A's 综览 writes a 7×3 flow chart as
                    # "#### 第 1 行：…" … "#### 第 3 行：…". Opening a clause per
                    # part would split one flow into four. The text joins the
                    # enclosing clause as a label line, and the stack is left
                    # alone so the nodes that follow stay with that clause.
                    if cur is not None:
                        cur["elements"].append(Block([el.text], 0))
                    continue
                # A coded heading opens a section and is not closed by an
                # uncoded heading at the same level: AIEP10's 10A1 file has
                # "### 10A1 …" and "### 程序" side by side, and 程序 belongs to
                # 10A1. Without this the section is popped and every chunk in
                # such a file loses its section and its page.
                while stack and stack[-1].level >= el.level and not (
                        SECTION_CODE_RE.match(stack[-1].text)
                        and not SECTION_CODE_RE.match(el.text)):
                    stack.pop()
                stack.append(el)
                # A coded heading opens a clause; an uncoded one is a topic
                # inside the clause that is already open.
                if cur is not None:
                    topics.append(cur)
                cur = {"section": clause_section(stack, code, overrides, el.text),
                       "title": el.text,
                       "ancestors": [h.text for h in stack[:-1]],
                       "page": page, "printed": printed, "elements": []}
                continue
            if cur is None:
                own = stack[-1].text if stack else ""
                cur = {"section": clause_section(stack, code, overrides, own),
                       "title": "",
                       "ancestors": [h.text for h in stack],
                       "page": page, "printed": printed, "elements": []}
            cur["elements"].append(el)
        if cur is not None:
            topics.append(cur)

        recs = []
        for t in topics:
            if not t["elements"] or not t["title"]:
                continue
            pg, pp = t["page"], t["printed"]
            # The legacy set is coarser than the markdown: 9C2's three
            # 驾驶员 sub-flows are one legacy chunk titled 驾驶员应采取的行动.
            # So an unmatched clause inherits from its nearest coded ancestor.
            code_m = SECTION_CODE_RE.match(t["section"])
            section_code = code_m.group(0) if code_m else ""
            # Some files carry no coded heading at all (AIEP25's 25A split has
            # only "### 员工伤亡报告流程"), so the section cannot be read off the
            # headings. Fall back to the file's own code: the legacy page set
            # keys on the same code, and without it the lookup returns nothing
            # and the chunk ships with empty page fields - an E2 error.
            section_code = section_code or code.split("_")[0]
            # The clause's own name: exact, then containment, because the legacy
            # set may spell it more fully (10B8's 列车离开车辆段 is stored as
            # 列车离开车辆段/停车场).
            pg, pp = legacy_lookup(legacy, section_code, t["title"])
            if not pg:
                pg = raw_pages.get(t["title"], "")
            # Ancestors: EXACT only. Containment here is too loose - AIEP25's
            # 综览 clause has the ancestor "25A 报告不如意事件", the legacy entry
            # for the section's own lead-in is keyed "报告不如意事件", and that
            # substring matched, filing the flow chart on page 3 when it is on
            # page 1. An ancestor that the legacy set does not name outright
            # should leave the clause to the fallbacks below.
            for heading in reversed(t["ancestors"]):
                if pg:
                    break
                pg, pp = legacy.get((section_code, page_key(heading)), ("", ""))
                if not pg:
                    pg = raw_pages.get(heading, "")
            if not pg and last_pages:
                # The markdown names a clause the legacy set does not (AIEP19's
                # 响应车站 and 检查点站台 sit between 定义 and 值班经理的行动 and
                # are missing from it). The manual is sequential, so the
                # preceding clause's page is a far better guess than the
                # section's first page - for AIEP19 it gives 19B-2~19B-3 where
                # the section's first page would have given 19B-1.
                pg, pp = last_pages
                INHERITED.append(t["title"])
            elif not pg and section_code:
                # Nothing before it in this file: fall back to the section's
                # first page. Both kinds of approximation are listed at the end
                # of the run, so a reader can see which chunks carry a guess.
                first = min((legacy[k] for k in legacy if k[0] == section_code),
                            default=None)
                if first:
                    pg, pp = first
                    APPROXIMATED.append(t["title"])
            if pg:
                last_pages = (pg, pp)
            recs.extend(topic_chunks(t["section"], t["title"], t["elements"],
                                     (pg, pp), overrides, t["ancestors"]))
        results.append((code, recs))
    return results, out_dir


# Per-document policy that the six mechanical rules cannot express. These name
# headings, never content, so nothing here is hand-typed prose.
DOC_OVERRIDES = {
    # 10D's three depots are cut as one chunk per table so a row like
    # 停车库 / 值班维修工程师 keeps its depot in context (requested).
    "AIEP10": {"whole_table_titles": ("车辆段的火警纠察", "停车场的火警纠察",
                                      "南兆路车辆段的火警纠察")},
    "AIEP12": {
        # 12D2/12D3 split their table by line under "##### 4 号线车站" and
        # "##### 大兴线车站"; per-station rows carry the line so a row like
        # 高米店南 / B1 口 still says which line it belongs to.
        "row_prefix_ancestor_re": r"^(4 号线|大兴线)车站$",
        # No skip_files entry: the two superseded copies that used to sit in
        # 03_markdown_reviewed/ were moved to 03_markdown_reviewed_superseded/
        # on 2026-09-29, so there is nothing left to skip. select_files() would
        # still catch them by the largest-wins rule if they ever came back.
    },
    "AIEP14": {
        # 14A2 lays ONE flow out as four tables split by the bold labels
        # **使用载客列车**, **使用指定的无载客列车** and **后续**. The evidence
        # that the labels are layout, not program boundaries:
        #   * the step numbers run 1..11 unbroken across all four tables;
        #   * steps cross the labels by number - step 2 says "若否，进行步骤 5"
        #     (in the third table) and step 4 says "进行步骤 9" (in the fourth),
        #     so a reader must jump between groups to follow one path;
        #   * the labels are emphasis on their own line, the same device the
        #     manual uses for prose headings elsewhere.
        # So the four tables become one procedure of 11 steps, with the labels
        # kept as sub-paragraph markers inside the parent's content.
        # (Settled 2026-09-29, item A23 in reports/aiep_todo.md.)
        "merge_step_tables": True,
    },
    "AIEP18": {
        # 18B's 流程图：主要人力后援的配置 is a flow written as an ordered list
        # (nodes 1.1-1.5) rather than a table, so the step-table rule cannot see
        # it. Turned on per document, not globally: AIEP16 16A2's 流程图 is also
        # an ordered list and is deliberately kept whole as one text chunk, so a
        # corpus-wide rule would break that.
        "numbered_list_as_steps": True,
    },
    "AIEP19": {
        # 19B's 流程图 is a flow written as an ordered list (nodes 1.1-1.6),
        # same shape as AIEP18 18B's - but the nodes sit at different depths:
        # 1.1 and 1.6 start top-level items, while 1.2/1.3 and 1.4/1.5 are
        # nested under the two 「并行分支」 items. split_ordered_steps finds a
        # node wherever it starts a line, so both layouts work.
        "numbered_list_as_steps": True,
        # 19B's 检查点站台 table is kept whole with the paragraph above it. Its
        # rows are bare station names, and only that paragraph says which line
        # they belong to ("4 号线车站 3 分钟之内没有列车到达"), so slicing by row
        # produces chunks that a 4 号线 question cannot reach. The 三级别 table
        # (3 rows) and the 控制拥挤矩阵 (24 rows) stay per-row: they carry their
        # own context and the matrix would be far too large as one chunk.
        "whole_table_as_text": ("检查点站台",),
        # row_title_from_following_cells is deliberately NOT set any more: it
        # only affected the 检查点站台 table (whose first column is all
        # "（车站）"), and that table is no longer sliced by row.
    },
    "AIEP20": {
        # 20B's flow is written as four numbered sub-headings
        # ("#### 1. OCC 人员的准备" … "#### 4. 开始作业"), each carrying its own
        # nodes (1.1-1.3, 2.1-2.2, 3.1, 4.1-4.2). The four branches are parallel
        # steps of ONE flow, not four flows, so the sub-headings are labels
        # inside the clause and the eight nodes become its steps.
        "subheading_label_re": r"^\d+\.\s+",
        "numbered_list_as_steps": True,
    },
    "AIEP21": {
        # 21B's flow is one ordered list of seven nodes (1.1, 1.2, 1.3, 1.3a,
        # 1.3b, 1.4, 1.5) with the three parallel branches written as plain
        # bullets inside it, so this document needs numbered_list_as_steps and
        # not numbered_subheadings_as_labels: 21B has no "#### 1. …" headings
        # at all. (Measured: setting the sub-heading switch too changes nothing.)
        "numbered_list_as_steps": True,
    },
    "AIEP24": {
        # 24B1's 指引 table lists nine rows under four intensity bands, each
        # band with its own 负责人员; the band is the unit a reader looks up, so
        # one chunk per band. The other tables in this document have distinct
        # first cells, so the switch is a no-op for them.
        "group_rows_by_first_cell": True,
    },
    "AIEP25": {
        # 25A 综览 draws a 7-column x 3-row flow chart as "#### 第 1 行：…" …
        # "#### 第 3 行：…". Those are the chart's rows, not separate clauses, so
        # the whole chart stays one chunk. (The chart's own text then contains
        # 流程图, which is what makes that chunk a text rather than a list.)
        "subheading_label_re": r"^第\s*\d+\s*行",
        # 25A 员工伤亡报告流程 is a flow written as bullets; the corpus rule would
        # call that a list, but a flow chart is asked to be one text chunk, so
        # the type is forced. 综览 is listed too - it lands on text anyway (its
        # text says 流程图), and saying so keeps the intent explicit.
        "force_type_titles": {"员工伤亡报告流程": "text", "综览": "text"},
        # 25E's roster row that names 运营总管 and 工程总管 in one cell yields a
        # title of "- 运营总管"; the marker goes. Opt-in only because the same
        # strip would rewrite AIEP12_12A7_003, a delivered chunk (see A30).
        "strip_title_markers": True,
        # 25A is split across three files whose clause headings carry no code,
        # so their sections came out uneven: 综览 took its coded ancestor's text
        # ("25A 报告不如意事件") while the other two fell back to the bare
        # heading ("员工伤亡报告流程"). Naming the three files gives every 25A
        # chunk the form "<code> <own heading>", which is the AIEP10 precedent
        # for a file spanning several sub-sections (10B10-10B12 ->
        # "10B10 OCC 员工"). 25B-25E are deliberately absent: their coded
        # "## 25B …" heading already is the clause's section, so the same rule
        # would rename every chunk in them after its topic heading.
        "section_code_prefix_files": ("25A_综览", "25A_员工伤亡报告流程",
                                      "25A_报告不如意事件"),
    },
}


def finalize(doc, code, recs):
    """Assign ids, resolve parent links, and put the fields in canonical order."""
    out = []
    for i, r in enumerate(recs, start=1):
        r = dict(r)
        r["chunk_id"] = "%s_%s_%03d" % (doc, code, i)
        out.append(r)
    last_procedure = None
    for i, r in enumerate(out):              # index, not out.index(r): identical
        parent = r.pop("_parent")            # chunks would match the wrong one
        if parent == "prev":
            if last_procedure is None:
                raise SystemExit("%s: procedure_step before any procedure" % r["chunk_id"])
            parent = last_procedure
        if r["type"] == "procedure":
            last_procedure = i
        r["parent_id"] = out[parent]["chunk_id"] if isinstance(parent, int) else None
        if r["type"] == "procedure_step" and r["parent_id"] is None:
            raise SystemExit("%s: procedure_step without parent" % r["chunk_id"])
        if not r["content"].strip():
            raise SystemExit("%s: empty content" % r["chunk_id"])
        r["doc_id"] = doc
        r["version"] = VERSION
        r["effective_date"] = EFFECTIVE_DATE
    order = ("chunk_id", "doc_id", "section", "title", "type", "content",
             "source_page", "printed_page", "version", "effective_date", "parent_id")
    return [{k: r[k] for k in order} for r in out]


def compact(text):
    """Drop blank lines and trailing space, for comparing two renderings."""
    return "\n".join(l.rstrip() for l in text.split("\n") if l.strip())


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--audit", action="store_true",
                    help="compare with existing 04_jsonl; write nothing")
    ap.add_argument("--verbose", type=int, nargs="?", const=3, default=0,
                    help="in --audit, show up to N differing chunks per file")
    ap.add_argument("--out", default=None,
                    help="write here as <out>/AIEPXX_RAG/04_jsonl/ instead of into "
                         "long_data; used to exercise write mode without touching "
                         "data that has already been validated")
    args = ap.parse_args(argv[1:])

    for doc in [d.upper() for d in args.docs]:
        results, out_dir = build_document(doc, audit=args.audit)
        total = 0
        tally = [0, 0, 0]           # exact, equal ignoring blank lines, different
        for code, recs in results:
            records = finalize(doc, code, recs)
            total += len(records)
            if args.audit:
                existing = out_dir / ("%s_%s_chunks.jsonl" % (doc, code))
                old = []
                if existing.exists():
                    with open(existing, "r", encoding="utf-8") as fh:
                        old = [json.loads(l) for l in fh if l.strip()]
                diffs = []
                exact = len(old) == len(records)
                for a, b in zip(old, records):
                    if a["content"] != b["content"]:
                        exact = False
                        diffs.append((a, b))
                for a, b in zip(old, records):
                    same_fields = all(a[k] == b[k] for k in
                                      ("type", "title", "source_page", "printed_page"))
                    if a["content"] == b["content"] and same_fields:
                        tally[0] += 1
                    elif (compact(a["content"]) == compact(b["content"])
                          and same_fields):
                        tally[1] += 1
                    else:
                        tally[2] += 1
                print("%-8s new=%3d existing=%3d  %s" % (
                    code, len(records), len(old),
                    "IDENTICAL" if exact and old else
                    ("%d content diff(s)" % len(diffs) if old else "no existing file")))
                if args.verbose:
                    for a, b in diffs[:args.verbose]:
                        print("    existing %s/%s: %r" % (a["chunk_id"], a["type"],
                                                          a["content"][:70]))
                        print("    new      %s/%s: %r" % (b["chunk_id"], b["type"],
                                                          b["content"][:70]))
                        print("    same ignoring blank lines: %s" % (
                            compact(a["content"]) == compact(b["content"])))
            else:
                target = out_dir if not args.out else \
                    Path(args.out) / ("%s_RAG" % doc) / "04_jsonl"
                write_jsonl(target / ("%s_%s_chunks.jsonl" % (doc, code)), records)
                print("%-8s %3d chunks -> %s_%s_chunks.jsonl" % (code, len(records), doc, code))
        print("%s total: %d chunks in %d file(s)" % (doc, total, len(results)))
        if INHERITED:
            print("%s WARNING: %d clause(s) inherited the preceding clause's page "
                  "because no page source named them: %s"
                  % (doc, len(INHERITED), ", ".join(sorted(set(INHERITED))[:6])))
            if not args.audit:
                print("    (confirm these before shipping: the page is the "
                      "neighbour's, not necessarily the clause's)")
        if APPROXIMATED:
            print("%s WARNING: %d clause(s) took their section's first page because "
                  "no page source named them: %s"
                  % (doc, len(APPROXIMATED), ", ".join(sorted(set(APPROXIMATED))[:6])))
            if not args.audit:
                print("    (confirm these before shipping: the page may be the "
                      "section's, not the clause's)")
        del APPROXIMATED[:]
        del INHERITED[:]
        if args.audit and sum(tally):
            n = sum(tally)
            print("%s agreement: %d/%d identical, %d equal ignoring blank lines, "
                  "%d differ" % (doc, tally[0], n, tally[1], tally[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
