#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build one document-level table-of-contents chunk per AIEP0x manual.

Purpose
-------
The per-section chunk files answer "what does 1C1 say". Nothing answers "which
chapter is 轻伤事故 defined in" - a meta question the retriever cannot serve from
a corpus of body chunks alone. So each document also gets a single ``type="toc"``
chunk listing its whole heading tree.

Input   long_data/AIEP0x_RAG/03_markdown_reviewed/*.md   (reviewed markdown)
Output  long_data/AIEP0x_RAG/04_jsonl/AIEP0x_toc_chunks.jsonl   (exactly 1 line)

Rules
-----
1. Every ``#``..``######`` heading of every reviewed file is collected, in
   document order, and emitted as one indented line in the chunk's ``content``.
   Indentation is two spaces per level.
2. Level comes from the heading's own section code, not from its ``#`` depth,
   because the markdown levels are not uniform across documents:

       第 N 章 ...          -> level 1
       1A / 2B / 7D         -> level 2
       1C1 / 2B1 / 7A1      -> level 3
       anything else        -> one level below the nearest coded heading

   AIEP02-07 follow 第X章 / ## 2B / ### 2B1 / #### 主题. AIEP01 has no chapter
   heading at all and is shifted up one: its ``#`` is the 1A/1B/1C level and its
   ``##`` is 1C1. Reading the code instead of the ``#`` count handles both.
3. Review artefacts are not part of the manual and are skipped:
   headings starting with 复核备注 or 待人工确认.
4. Coded headings repeat in every file of their section (``# 第 2 章`` appears in
   all 14 AIEP02 files), so one entry is kept per section code document-wide.
   **When two files spell the same code differently, the longer title wins**
   ("同编码取标题较长者，信息更全") - AIEP12 spells 12A as both
   ``12A OCC 疏散至后备控制中心`` and ``12A 疏散至后备控制中心``, and the first
   carries more information. The rule is stated rather than implied: keying on
   whichever file was read first would make the outcome a side effect of the
   file sort, so renaming a file could silently flip the TOC.
   The surviving spelling is also what scopes that section's topics, so a topic
   under it is not emitted once per spelling.
   Uncoded topic headings are deduplicated per parent only - 引言 legitimately
   appears under both 1A and 1B and must survive in both.
5. Files are ordered by their section code, not by filename, so AIEP03's
   ``3A_引言`` sorts before ``3A2`` (plain filename order puts ``3A2`` first
   because '2' < '_'). A file with no code in its name sorts last in its
   document.

Known deviations, deliberately not corrected here
-------------------------------------------------
Each of these mirrors the markdown as written rather than guessing at the
original PDF. They are logged, with what to check, in
``long_data/reports/aiep_todo.md`` (T1-T4):

* T1 - AIEP01's reviewed markdown has no chapter heading at all, so its level-1
  line is synthesised from the source PDF name
  (00_raw/AIEP01-事故的呈报-...pdf). Spelled "第 1 章" to match the six documents
  whose chapter line is verbatim markdown.
* T2 - AIEP04's 4A heading reads 有人被列车卷入车底 in the markdown while the
  chapter line says 有人/物件被列车撞倒. The chunk follows the heading; the
  reviewed file was renamed to AIEP04_4A_有人被列车卷入车底.md so the filename
  mirrors the heading like every other reviewed file.
* T3 - AIEP06's 安排起复及移动事故列车.md is the only reviewed file whose section
  has no code in the filename or in its "## " heading (front matter section:
  安排起复及移动事故列车, status: verified). Uncoded files sort last, so it lands
  after 6B; its real number is unconfirmed (6C?).
* T4 - AIEP07's 7B/7C place 何谓非紧急情况 / 牵引电流故障 at the same markdown
  level as the role bullets under them, where 7D1/7D2 put theirs one level
  deeper. The TOC follows the markdown, so the two families indent differently.

Usage
-----
    python build_toc_jsonl.py            # rebuild every AIEP01-07 TOC chunk
    python build_toc_jsonl.py AIEP03     # rebuild one document only

Documents whose 03_markdown_reviewed/ holds no .md are skipped with a note.
All twelve documents listed above currently have reviewed markdown.

Superseded copies do not belong in 03_markdown_reviewed/. They repeat headings
the kept file already contributes, so they add nothing here, but they would make
the slicer emit the same section twice. AIEP12's two are archived in the sibling
directory ``03_markdown_reviewed_superseded/`` - a *sibling*, not a
subdirectory, so the ``*.md`` glob below cannot reach them. Verified 2026-09-29:
moving them changed neither this file's content nor its SHA256.

AIEP11's generator (``long_data/scripts/build_aiep11_jsonl.py``) imports this
module and calls ``collect``/``to_record`` for its TOC chunk, so the TOC has one
implementation whether it is produced by this script or by that one.
"""

import json
import re
import sys
from pathlib import Path

def _corpus_root(base):
    """The directory holding the AIEPxx_RAG folders.

    Moved from long_data/ into long_data/AIEP/ on 2026-09-30; probe rather than
    hard-code, so the layout can change back without this silently skipping
    every document (a wrong root yields "0 files, no headings", not an error).
    """
    nested = base / "AIEP"
    if nested.is_dir() and any(nested.glob("AIEP*_RAG")):
        return nested
    return base


ROOT = _corpus_root(Path(__file__).resolve().parent / "long_data")
DOCS = ["AIEP01", "AIEP02", "AIEP03", "AIEP04", "AIEP05", "AIEP06", "AIEP07",
        "AIEP08", "AIEP09", "AIEP10", "AIEP11", "AIEP12", "AIEP14", "AIEP15",
        "AIEP16", "AIEP17", "AIEP18", "AIEP19", "AIEP20", "AIEP21", "AIEP24",
        "AIEP25", "AIEP26", "AIEP27", "AIEP28", "AIEP29"]
REVIEWED_DIR = "03_markdown_reviewed"
OUT_DIR = "04_jsonl"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
CHAPTER_CODE_RE = re.compile(r"^第\s*\d+\s*章")
SECTION_CODE_RE = re.compile(r"^(\d+)([A-Z]+)(\d*)")
SKIP_TITLE_RE = re.compile(r"^(复核备注|待人工确认)")
# Some reviewed files hold several sections and are named after all of them
# ("AIEP10_10B4-10B7_驻守人员.md"). The sort key is the first code in the range.
FILENAME_CODE_RE = re.compile(r"^AIEP\d{2}_(\d+[A-Z]+\d*)(?:-\d+[A-Z]+\d*)?_")

# AIEP01 is the only document with no 章-level heading in its reviewed
# markdown. The name comes from the source PDF (00_raw/AIEP01-事故的呈报-...pdf),
# spelled "第 1 章" to match the six documents whose chapter line is verbatim md.
CHAPTER_FALLBACK = {"AIEP01": "第 1 章 事故的呈报"}

# Fields fixed for every TOC chunk, per spec. The chunk is a map of the whole
# document, not a piece of a page, so it has no real page - it is anchored to the
# cover - and version/effective_date inherit the corpus-wide pending values.
FIXED = {
    "section": "目录",
    "type": "toc",
    "source_page": "1",
    "printed_page": "封面",
    "version": "1.0",
    "effective_date": "待确认",
    "parent_id": None,
}


def sort_key(path):
    """Order files by section code (1A < 1C < 1C1), not by filename."""
    m = FILENAME_CODE_RE.match(path.name)
    if not m:
        return (99, "", 99, path.name)          # uncoded: last in its document
    code = m.group(1)
    c = SECTION_CODE_RE.match(code)
    return (int(c.group(1)), c.group(2), int(c.group(3) or 0), path.name)


def read_headings(path):
    """Yield (markdown level, heading text), skipping fenced code and review artefacts."""
    skipped = 0
    fenced = False
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            if FENCE_RE.match(raw):
                fenced = not fenced
                continue
            if fenced:
                continue
            m = HEADING_RE.match(raw)
            if not m:
                continue
            title = m.group(2).strip()
            if not title:
                continue
            if SKIP_TITLE_RE.match(title):
                skipped += 1
                continue
            yield len(m.group(1)), title
    if skipped:
        print("    (skipped %d review-artefact heading(s) in %s)" % (skipped, path.name))


def code_depth(title):
    """Level implied by the heading's own section code, or None if uncoded."""
    if CHAPTER_CODE_RE.match(title):
        return 1
    m = SECTION_CODE_RE.match(title)
    if m:
        return 3 if m.group(3) else 2
    return None


def code_of(title):
    """The code a heading carries, normalised, or None if it carries none.

    Used as the dedupe key for coded headings. Keying on the whole title instead
    lets one section appear twice when two files spell its heading differently:
    AIEP12 has "## 12A OCC 疏散至后备控制中心" in one file and
    "## 12A 疏散至后备控制中心" in another, and both reached the TOC.
    """
    for pattern in (CHAPTER_CODE_RE, SECTION_CODE_RE):
        m = pattern.match(title)
        if m:
            return re.sub(r"\s+", "", m.group(0))
    return None


def collect(doc):
    """Return [(depth, title), ...] for one document, in document order.

    Coded headings take their level from the code. An uncoded topic takes the
    level of the nearest coded heading above it, offset by how much deeper it
    sits in *that file's* markdown - the offset is what makes this survive
    AIEP01 (``# 1A`` + ``## 引言``) and AIEP02 (``## 2A`` + ``#### 沟通渠道``)
    alike, since the markdown levels are shifted by one between documents.
    """
    reviewed = ROOT / ("%s_RAG" % doc) / REVIEWED_DIR
    files = sorted(reviewed.glob("*.md"), key=sort_key)
    if not files:
        return None, files

    # Headings are read once, both to order the files and to walk them.
    headings = {path: list(read_headings(path)) for path in files}

    def order_key(path):
        """Within one section code, the file that declares that code's heading
        comes first.

        AIEP25 splits 25A into three files, and only 综览 carries the
        "## 25A 报告不如意事件" line; sorted by name alone it lands last, so the
        section's topics were emitted before the section itself. The test has to
        be against the file's OWN code - every file carries the "# 第 25 章"
        chapter heading, so merely "declares a coded heading" is true of all.
        """
        base = sort_key(path)
        own = path.stem.split("_")[1]
        declares = any(code_of(title) == own
                       for _level, title in headings[path])
        return base[:3] + (0 if declares else 1, base[3])

    files = sorted(files, key=order_key)

    entries, seen = [], set()
    code_at = {}                    # section code -> index of its entry in entries
    parent_path = ()                # codes of the enclosing 节/小节, for topic scope
    anchor = (0, 0)                 # (depth, markdown level) of nearest coded heading
    for path in files:
        for level, title in headings[path]:
            code = code_of(title)
            if code is not None:
                depth_of_code = code_depth(title)
                anchor = (depth_of_code, level)
                # One entry per section code, document-wide. Which spelling wins
                # is decided by title length, not by the order the files happen
                # to be read in: AIEP12 spells 12A two ways and the longer one
                # carries more information ("12A OCC 疏散至后备控制中心" vs
                # "12A 疏散至后备控制中心"). Relying on file order made the
                # result a side effect of the sort, which would flip if a file
                # were renamed.
                if code in code_at:
                    i = code_at[code]
                    if len(title) > len(entries[i][1]):
                        entries[i] = (depth_of_code, title)
                    canonical = entries[i][1]
                else:
                    code_at[code] = len(entries)
                    entries.append((depth_of_code, title))
                    canonical = title
                # Scope uses the canonical spelling too: if it used whichever
                # spelling this file happens to use, a topic under the same
                # section would get a different dedupe key per file and appear
                # once per spelling.
                if depth_of_code == 1:
                    parent_path = ()
                elif depth_of_code == 2:
                    parent_path = (canonical,)
                else:
                    parent_path = parent_path[:1] + (canonical,)
                continue
            depth = anchor[0] + max(1, level - anchor[1])
            key = ("topic", parent_path, title)   # topic: one per parent
            if key in seen:
                continue
            seen.add(key)
            entries.append((depth, title))

    if CHAPTER_FALLBACK.get(doc) and not any(d == 1 for d, _ in entries):
        entries.insert(0, (1, CHAPTER_FALLBACK[doc]))
    return entries, files


def to_record(doc, entries):
    content = "\n".join("  " * (depth - 1) + title for depth, title in entries)
    rec = {
        "chunk_id": "%s_toc_001" % doc,
        "doc_id": doc,
        "section": FIXED["section"],
        "title": "%s 目录" % doc,
        "type": FIXED["type"],
        "content": content,
        "source_page": FIXED["source_page"],
        "printed_page": FIXED["printed_page"],
        "version": FIXED["version"],
        "effective_date": FIXED["effective_date"],
        "parent_id": FIXED["parent_id"],
    }
    return rec


def write_jsonl(path, records):
    """Same bytes convention as the build_aiepNN_jsonl.py writers: UTF-8, no BOM,
    CRLF line endings, trailing newline."""
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv):
    wanted = [a.upper() for a in argv[1:]] or DOCS
    unknown = [d for d in wanted if d not in DOCS]
    if unknown:
        raise SystemExit("unknown document(s): %s (known: %s)"
                         % (", ".join(unknown), ", ".join(DOCS)))

    total = 0
    for doc in wanted:
        entries, files = collect(doc)
        if entries is None:
            print("%-8s SKIP - %s/%s holds no .md" % (doc, "%s_RAG" % doc, REVIEWED_DIR))
            continue
        if not entries:
            print("%-8s SKIP - %s file(s) but no headings" % (doc, len(files)))
            continue

        rec = to_record(doc, entries)
        if rec["parent_id"] is not None:
            raise SystemExit("%s: TOC chunk must not have a parent" % doc)

        out = ROOT / ("%s_RAG" % doc) / OUT_DIR / ("%s_toc_chunks.jsonl" % doc)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(out, [rec])
        total += 1
        print("%-8s %2d file(s) -> %2d heading(s), %3d line(s) of content, %d chunk"
              % (doc, len(files), len(entries), rec["content"].count("\n") + 1, 1))
    print("total: %d TOC chunk(s)" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
