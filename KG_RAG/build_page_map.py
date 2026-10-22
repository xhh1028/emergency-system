#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harvest a page map from the delivered chunks, so pages survive without legacy.

Why this exists
---------------
Until 2026-09-30 every page number in the corpus came from the third-version
long-slice set ``long_chunk_681片_待复核/long_chunk/`` (``JKR3_AIEPxx_*.txt``):
the reviewed markdown carries no page footers, because the source PDFs are
scans. That directory has since been removed from the repository. Rebuilding a
document after that produced empty ``source_page``/``printed_page`` - which the
checker rejects as E2 - while the pages themselves were still sitting in the
already-delivered ``04_jsonl`` files.

So the pages are harvested back out of those files into a map the builder can
read exactly where it used to read the legacy dict:

    long_data/page_map.json
    {"AIEP29": {"29D": {"车辆段列车控制主管": ["10-11", "29D-3~29D-4"], ...}, ...}}

The key is ``(section code, page_key(topic))`` - the same normalisation
``pages_from_legacy`` builds - and the topic is taken from each chunk's
``title``, which is the clause heading the builder looks up.

This is derived data: regenerate it after re-slicing, and prefer a restored
legacy directory when one exists (``build_from_md.pages_from_legacy`` merges
this map underneath the legacy values).

Usage:  python build_page_map.py            # write long_data/page_map.json
        python build_page_map.py --check    # report, write nothing
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Import the builder's own normalisation and code rule: the map is worthless if
# it keys a topic even slightly differently from the lookup that reads it.
from build_from_md import SECTION_CODE_RE, page_key, _corpus_root  # noqa: E402

ROOT = Path(__file__).resolve().parent


def harvest(corpus):
    """{doc: {code: {topic_key: [source_page, printed_page]}}}"""
    out = {}
    counts = {}
    for doc_dir in sorted(p for p in corpus.glob("AIEP*_RAG") if p.is_dir()):
        doc = doc_dir.name.split("_")[0]
        themes = defaultdict(dict)
        n = seen = 0
        for path in sorted((doc_dir / "04_jsonl").glob("*.jsonl")):
            for line in open(path, encoding="utf-8"):
                if not line.strip():
                    continue
                rec = json.loads(line)
                n += 1
                src, prt = rec.get("source_page", ""), rec.get("printed_page", "")
                if not src and not prt:
                    continue
                # chunk_id = "<doc>_<code>_<NNN>"; the code can itself contain
                # an underscore (AIEP25 writes 25A_综览), so strip the trailing
                # ordinal instead of splitting on "_".
                m = re.match(r"^%s_(.+)_\d{3}$" % re.escape(doc), rec["chunk_id"])
                if not m:
                    continue
                id_code = m.group(1)
                # Key by the code the builder will LOOK UP, which it reads off
                # the chunk's section (falling back to the file's own code), not
                # by the code embedded in the chunk_id. They differ: AIEP12's
                # 12A1 sub-clauses sit in the 12A file but are looked up under
                # 12A1, and AIEP25's split 25A files are looked up under 25A.
                # Keying by chunk_id filed those pages where nothing reads them.
                sec_match = SECTION_CODE_RE.match(rec.get("section", "") or "")
                code = sec_match.group(0) if sec_match else id_code.split("_")[0]
                # The clause heading is what the builder looks up; a step chunk
                # ("X-步骤3") or a table row (first cell) adds a harmless extra
                # key, and the section string covers ancestor lookups.
                for topic in (rec.get("title", ""), rec.get("section", "")):
                    if not topic:
                        continue
                    key = page_key(topic)
                    if key not in themes[code]:
                        themes[code][key] = [src, prt]
                        seen += 1
        if themes:
            out[doc] = {code: dict(topics) for code, topics in themes.items()}
            counts[doc] = (n, seen)
    return out, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("--check", action="store_true", help="report, write nothing")
    args = ap.parse_args(argv)

    corpus = _corpus_root(ROOT / "long_data")
    data, counts = harvest(corpus)
    total = sum(v[1] for v in counts.values())
    print("语料根: %s" % corpus)
    print("%-9s %8s %10s" % ("doc", "chunks", "主题键"))
    for doc in sorted(data):
        print("%-9s %8d %10d" % (doc, counts[doc][0], counts[doc][1]))
    print("-" * 30)
    print("%-9s %8s %10d" % ("共 %d 份" % len(data), "", total))

    target = ROOT / "long_data" / "page_map.json"
    if args.check:
        print("\n--check：未写盘（目标 %s）" % target)
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print("\n已写入 %s（%.1f KB）" % (target, target.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
