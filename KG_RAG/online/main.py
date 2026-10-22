# -*- coding: utf-8 -*-
import json
import logging
import os
import re
import sys
import time
import traceback

import chromadb
from openai import OpenAI
from neo4j import GraphDatabase


def load_scene_map():
    """读取场景-章节映射表。

    路径不能写死成 CWD 相对（"online/scene_chapter_map.json"）：从 online/ 目录
    启动时该路径不存在，异常被 search_rag_full 吞掉后**场景过滤会被静默跳过**，
    表现为检索结果里混进无关章节。按"脚本同目录 -> CWD"顺序探测。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "scene_chapter_map.json"),
                 "online/scene_chapter_map.json",
                 "scene_chapter_map.json"):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except OSError:
            continue
    raise FileNotFoundError("scene_chapter_map.json（已试过脚本目录与 CWD）")


if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ================= 配置区 =================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
CHROMA_DIR = os.path.join(ROOT_DIR, "chroma_db")
EMBED_MODEL_DIR = os.path.join(ROOT_DIR, "models", "bge-base-zh-v1.5")
RAG_COLLECTION = "emergency_rag"
CASE_COLLECTION = "historical_cases"

bge_model = None
collection = None
case_collection = None

TOP_K_PER_QUERY = 4
MAX_DOCS = 8
MAX_DISTANCE = 0.6
# v8.24：规程原文是**第一依据**，图谱只作补充 → 原文预算上调，
# 让"原始文本切片"尽量完整进 prompt（截断会直接砍掉方案的动作来源）。
MAX_CONTEXT_CHARS = 12000

# ★ 新增：新文档关键词白名单（用于过滤时直接放行，不被场景过滤砍掉）
NEW_DOC_WHITELIST = [
    "GBT_38707", "GBT 38707", "GB_T_38707",
    "JTT1051", "JTT 1051", "JTT_1051",
    "国家城市轨道交通运营突发事件应急预案",
    "国家突发公共卫生事件应急预案",
    "城市轨道交通运营防汛防台风指南",
    "城际轨道交通防汛防洪应急预案",
    "城市轨道交通主要运营险性事件清单",
    "城市轨道交通运营险性事件快报表",
    "城市轨道交通运营险性事件信息报告与分析管理办法",
    "城市轨道交通运营突发事件应急演练管理办法",
]

# ★ 强制拉入上限：防止整篇规范把模型上下文挤爆
FORCE_MAX_PER_SOURCE = 10   # 优先来源（外部规范）单源上限
FORCE_MAX_PER_AIEP = 6      # AIEP 手册单源上限（正文检索已覆盖，少拉）
FORCE_MAX_TOTAL = 70        # 强制拉入总量上限
# 分档配额：不设档位时，优先档（外部规范）会按单源上限吃满总额度，实测 79 个
# 通过过滤的来源里只有 9 个能进上下文。分档 + 各档轮转后，手册档至少能覆盖 30 个来源。
FORCE_BUDGET_PRIORITY = 40  # 外部规范档
FORCE_BUDGET_MANUAL = 30    # 手册档
FORCE_BUDGET_FALLBACK = 12  # 场景键未命中时的兜底条数

# "必须保证进入上下文"的条款（pin）已改为按场景配置，写在 scene_chapter_map.json
# 每个场景的 "pins" 字段里，不再硬编码在代码中。原先的硬编码值是
# ("7.2" = 《国家预案》分级标准四档, "14.2.15" = GB/T 38707 大客流管控措施)，
# 实测 7.2 仅在 7 个场景生效、14.2.15 仅在 3 个场景生效（详见 online/_baseline.md），
# 配置里按实测逐场景登记，行为与硬编码时一致。

# 相关度粗排：命中这些要素的切片优先进入上下文（权重越高越先）
FORCE_HINT_WEIGHTS = (
    ("分级", 4), ("等级", 3), ("特别重大", 4), ("重大", 2), ("较大", 2),
    ("响应", 3), ("报告", 2), ("时限", 3), ("小时", 1),
    ("客流", 3), ("限流", 2), ("控制点", 2),
    ("疏散", 3), ("关停", 2), ("停运", 2),
    ("伤亡", 2), ("死亡", 2), ("重伤", 2), ("受伤", 1),
)

# 轮转分配时优先分给这些来源：分级标准、报告时限、大客流管控措施的出处都在外部规范里
FORCE_SOURCE_PRIORITY = (
    "GB_T_38707",
    "国家城市轨道交通运营突发事件应急预案",
    "城市轨道交通运营防汛防台风指南",
    "城际轨道交通防汛防洪应急预案",
    "国家突发公共卫生事件应急预案",
    "城市轨道交通运营突发事件应急演练管理办法",
    "城市轨道交通运营险性事件",
    "附件1_",
    "JTT1051",
)


def _source_rank(src):
    for i, prefix in enumerate(FORCE_SOURCE_PRIORITY):
        if prefix in src:
            return i
    return len(FORCE_SOURCE_PRIORITY)


def _hint_score(doc, meta):
    """粗排分数：切片是否含分级/响应/报告时限/客流/疏散等要素。"""
    text = str(meta.get("section", "")) + " " + str(doc)[:600]
    return sum(w for kw, w in FORCE_HINT_WEIGHTS if kw in text)


def _load_pins(scenes):
    """从 scene_chapter_map.json 取这些场景的 pin 条款。

    读不到（文件缺失/语法错误/字段不存在）一律返回空元组，只记一条 error 日志——
    pin 只是排序偏好，配置坏了不该让检索主流程崩。
    """
    if not scenes:
        return ()
    try:
        scene_map = load_scene_map()
    except Exception as e:
        logging.error("[pins] 场景配置加载失败，本次按无 pin 处理：%s", e)
        return ()
    pins = []
    for scene in scenes:
        cfg = scene_map.get(scene) or {}
        for p in cfg.get("pins") or ():
            if p not in pins:
                pins.append(p)
    return tuple(pins)


def _is_pinned(section, pins):
    """该 section 是否命中 pin（如国家预案 7.2、GB/T 14.2.15）。

    pins 为空元组时恒为 False —— 即"配置缺失则退化为不做置顶"，不影响取数。
    """
    s = str(section or "").strip()
    return any(s == p or s.startswith(p + ".") for p in pins)


def _fallback_contains(event_types, budget=FORCE_BUDGET_FALLBACK):
    """场景键未命中时的兜底：直接在正文里按关键词找条文。

    场景-章节映射是人工维护的白名单，覆盖不到的场景原本会**一条都拉不到**
    （实测"自动扶梯困人"拉入 0 条），只剩正文召回的十几条。这里把事件类型当成
    关键词、由长到短逐级截断去正文里找（"自动扶梯困人"→"自动扶梯"→"扶梯"…），
    第一个命中的长度即停，保证陌生场景也能退化成"有依据可用"，而不是彻底空手。
    """
    for et in event_types:
        probe = str(et).strip()
        if not probe:
            continue
        for n in range(len(probe), 1, -1):
            kw = probe[:n]
            try:
                res = collection.get(
                    where_document={"$contains": kw},
                    include=["documents", "metadatas"],
                    limit=budget,
                )
            except Exception as e:
                print(f"   （兜底检索失败：{e}）")
                return []
            docs = res.get("documents", []) or []
            if docs:
                pairs = list(zip(docs, res.get("metadatas", []) or []))
                print(f"   （场景未命中，兜底按关键词「{kw}」拉入 {len(pairs)} 条）")
                return pairs
    print("   （场景未命中，兜底也未找到相关条文）")
    return []

# ★ 场景强制拉入章节映射
#
# 键支持三种写法（由 _resolve_key() 按顺序解析）：
#   1. 完整文件名        "GB_T_38707-2020_21-22"       —— 精确命中一个切片文件
#   2. 文件名前缀/章节集  "AIEP06"、"AIEP09_9C"        —— 命中该前缀下的所有文件
#                          （AIEP06 命中 6A/6B；AIEP09_9C 命中 9C1/9C2）
#   3. 文档名_章节范围    "国家城市轨道交通运营突发事件应急预案_3-7"
#                          —— 只取该文档 section 落在 3~7 章内的切片
#
# 注意：旧配置里的 "GBT_38707-2020_11-15"（缺一个下划线）与裸 "AIEP06" 之类
# 在旧实现下全部落空（旧实现按文件名精确匹配），本版已按库内真实文件名修正，
# 并改为前缀匹配以支持章节集。
FORCE_INCLUDE_CHAPTERS = {
    "站内失火": [
        "AIEP09_9A", "AIEP09_9B1", "AIEP09_9B2",
        "AIEP11_11A1", "AIEP12_12B3",
        "GB_T_38707-2020_11-15", "GB_T_38707-2020_16-20",
        "国家城市轨道交通运营突发事件应急预案_3-7",
    ],
    "站外失火": ["AIEP09_9B3", "AIEP11_11A2", "AIEP15_15A2"],
    "列车失火": [
        "AIEP09_9C", "AIEP07_7D", "AIEP11_11A3",
        "GB_T_38707-2020_16-20",          # 含车辆火灾条款
        "国家城市轨道交通运营突发事件应急预案_3-7",
    ],
    "列车脱轨": [
        "AIEP06", "AIEP02", "AIEP07",
        "国家城市轨道交通运营突发事件应急预案_3-7",
    ],
    "列车分离": ["AIEP05", "AIEP02", "AIEP07"],
    "区间烟雾报警": ["AIEP09_9E", "AIEP09_9C", "AIEP07"],
    "暴雨": [
        "AIEP28", "AIEP27",
        "城市轨道交通运营防汛防台风指南（试行）_3-4",   # 预警响应 + 应对处置
        "城际轨道交通防汛防洪应急预案",
        "国家城市轨道交通运营突发事件应急预案_3-7",
    ],
    "暴雨导致列车区间迫停": [
        "AIEP02", "AIEP07_7D", "AIEP11_11A", "AIEP12_12B", "AIEP28_28E",
        "城市轨道交通运营防汛防台风指南（试行）_3-4",
        "GB_T_38707-2020_21-22",
    ],
    "暴雪": ["AIEP29", "AIEP27"],
    "地震": ["AIEP24", "AIEP27"],
    "车门异常": ["AIEP16", "AIEP05"],
    "信号异常": [
        "AIEP16", "AIEP20",
        "GB_T_38707-2020_11-15",
        "国家城市轨道交通运营突发事件应急预案_3-7",
    ],
    "恐怖袭击": ["AIEP08", "AIEP17", "AIEP12"],
    "气体泄漏": [
        "AIEP08_8C3", "AIEP08_8C4", "AIEP08_8C1", "AIEP08_8C2",
        "AIEP11_11A", "AIEP12_12B",
    ],
    "大客流": [
        "AIEP18", "AIEP19",
        "GB_T_38707-2020_21-22",              # 14.2.15 大客流管控措施在此文件
        "城市轨道交通运营突发事件应急演练管理办法",
    ],
    "乘客被困": ["AIEP02", "AIEP07", "AIEP12", "AIEP14", "AIEP03"],
    "隧道水淹": [
        "AIEP11_11A", "AIEP28_28D", "AIEP28_28E", "AIEP07",
        "城市轨道交通运营防汛防台风指南（试行）_3-4",
    ],
    "通信中断": [
        "AIEP02", "AIEP07", "AIEP12",
        "GB_T_38707-2020_11-15",
    ],
    "断电": [
        "AIEP02", "AIEP07", "AIEP11", "AIEP28",
        "GB_T_38707-2020_11-15",
        "国家城市轨道交通运营突发事件应急预案_3-7",
    ],
    "车辆段失火": ["AIEP10", "AIEP02", "AIEP12"],
    "隧道火灾": ["AIEP09_9C", "AIEP07_7D", "AIEP11_11A"],
    "列车迫停": ["AIEP02", "AIEP07", "AIEP12", "AIEP28"],
    "车站水淹": [
        "AIEP28_28C", "AIEP27", "AIEP12",
        "城市轨道交通运营防汛防台风指南（试行）_3-4",
        "城际轨道交通防汛防洪应急预案",
    ],
    "风道水淹": ["AIEP28_28D", "AIEP27", "AIEP11_11A"],
    "乘客受伤": ["AIEP02", "AIEP03", "AIEP07", "AIEP14"],
    "乘客突发疾病": [
        "AIEP02", "AIEP03", "AIEP12",
        "国家突发公共卫生事件应急预案",
    ],
    "恐吓事件": ["AIEP02", "AIEP08", "AIEP12", "AIEP17"],
}

LEVEL_TERMS = {"一级": "一类", "二级": "二类", "三级": "三类", "四级": "四类"}

SAFE_HEADERS = {
    "User-Agent": "StationRAG/1.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Accept-Encoding": "identity",
    "X-Stainless-Lang": "python",
    "X-Stainless-OS": "Windows",
    "X-Stainless-Arch": "x64",
    "X-Stainless-Runtime": "CPython",
    "X-Stainless-Runtime-Version": "3.10.11",
}

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    default_headers=SAFE_HEADERS
)

neo4j_driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
    warn_notification_severity="OFF",
)


# ================= 大模型调用 =================

def call_llm(prompt, retries=1):
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"【大模型调用失败】(第 {attempt + 1}/{retries + 1} 次) {type(e).__name__}: {e}")
            traceback.print_exc()
            if attempt < retries:
                time.sleep(1.5)
    print(f"【大模型最终失败】: {last_error}")
    return "抱歉，系统繁忙，请稍后重试。"


# ================= 资源初始化 =================

def load_encoder():
    from FlagEmbedding import FlagModel
    print("正在加载本地 BGE 向量模型（首次约 10 余秒）...")
    t0 = time.time()
    model = FlagModel(
        EMBED_MODEL_DIR,
        query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：",
        use_fp16=False,
    )
    print(f"BGE 模型加载完成，用时 {time.time() - t0:.1f}s")
    return model


def load_collection():
    global case_collection
    path = CHROMA_DIR

    try:
        chroma_client = chromadb.PersistentClient(path=path)
        col = chroma_client.get_collection(RAG_COLLECTION)
    except Exception as e:
        raise SystemExit(
            f"【致命错误】打不开规程向量库：{path}\n  集合：{RAG_COLLECTION}\n  原因：{e}\n"
            f"请先在 {ROOT_DIR} 目录下运行 offline/build_rag.py 建库。"
        )
    count = col.count()
    if count == 0:
        raise SystemExit(f"【致命错误】集合 {RAG_COLLECTION} 是空的。")
    print(f"规程库就绪：{RAG_COLLECTION} 共 {count} 条手册切片")

    try:
        case_collection = chroma_client.get_collection(CASE_COLLECTION)
        case_count = case_collection.count()
        print(f"案例库就绪：{CASE_COLLECTION} 共 {case_count} 个案例")
    except Exception as e:
        print(f"⚠️ 案例库未加载（{CASE_COLLECTION}）：{e}")
        case_collection = None

    return col


# ================= 复合事件场景匹配 =================

def _collect_event_types(event_profile):
    types = []
    primary = event_profile.get("primary_event")
    if primary and isinstance(primary, dict):
        t = primary.get("event_type", "")
        if t:
            types.append(t)
    for sec in event_profile.get("secondary_events", []) or []:
        if isinstance(sec, dict):
            t = sec.get("event_type", "")
            if t:
                types.append(t)
    if not types:
        t = event_profile.get("event_type", "")
        if t:
            types.append(t)
    return types


def _match_scenes(event_types, scene_map):
    matched = []
    used_keys = set()
    for et in event_types:
        for scene_key, rules in scene_map.items():
            if scene_key.startswith("_"):
                continue
            if scene_key in used_keys:
                continue
            if scene_key in et or et in scene_key:
                matched.append((scene_key, rules))
                used_keys.add(scene_key)
                break
    return matched


def _resolve_scenes(event_profile, event_types, scene_map):
    """**优先用受控 scene_key**（event_understand 从场景词表里选的）；缺失/非法 → 回退子串匹配。

    背景：`_match_scenes` 是纯字符串子串匹配，词面对不上就永远命中不了——
    实测 10 例真实案例里 4 例未命中，而**这 4 例的正确答案本来就在词表里**
    （"高架桥下仓库起火波及线路" vs `站外失火`、"隧道内边墙起火" vs `隧道火灾`、
    "疑似爆炸物品事件" vs `恐吓事件`、"乘客突发心脏骤停" vs `乘客突发疾病`）。
    受控归类把"事件类型→场景键"交给模型做语义判断；子串匹配**保留作兜底**，不再是一线机制。
    """
    raw = event_profile.get("scene_key") if isinstance(event_profile, dict) else None
    if isinstance(raw, str):
        raw = [raw]
    keys = []
    for k in (raw or []):
        k = str(k).strip()
        if k and not k.startswith("_") and k in scene_map and k not in keys:
            keys.append(k)
    if keys:
        return [(k, scene_map[k]) for k in keys], "受控归类"
    return _match_scenes(event_types, scene_map), "子串匹配"


def _merge_scene_rules(matched_rules, scene_map):
    merge_cfg = scene_map.get("_merge_rule", {})
    allowed_union = merge_cfg.get("allowed_union", True)
    forbidden_intersect = merge_cfg.get("forbidden_intersect", True)

    allowed_set = set()
    forbidden_sets = []
    for _, rules in matched_rules:
        allowed_set.update(rules.get("allowed", []))
        forbidden_sets.append(set(rules.get("forbidden", [])))

    if not forbidden_sets:
        forbidden_set = set()
    elif forbidden_intersect and len(forbidden_sets) > 1:
        forbidden_set = set.intersection(*forbidden_sets)
    else:
        forbidden_set = set()
        for s in forbidden_sets:
            forbidden_set.update(s)

    if not allowed_union:
        if len(matched_rules) > 1:
            allowed_set = set.intersection(*[set(r.get("allowed", [])) for _, r in matched_rules])

    return list(allowed_set), list(forbidden_set)


# ================= 检索层 =================

def retrieve_from_rag(encoder, collection, arms):
    RRF_K = 60.0
    hits = {}
    for arm in arms:
        try:
            embedding = encoder.encode_queries([arm])[0].tolist()
        except Exception as e:
            print(f"   （提示：查询编码失败 {e}）")
            continue
        try:
            result = collection.query(
                query_embeddings=[embedding],
                n_results=TOP_K_PER_QUERY,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            print(f"   （提示：向量库检索失败 {e}）")
            continue
        for rank, (cid, doc, meta, dist) in enumerate(zip(
                result["ids"][0], result["documents"][0],
                result["metadatas"][0], result["distances"][0])):
            if dist > MAX_DISTANCE:
                continue
            hit = hits.get(cid)
            if hit is None:
                hit = hits[cid] = {"id": cid, "doc": doc, "meta": meta,
                                   "distance": dist, "score": 0.0}
            hit["distance"] = min(hit["distance"], dist)
            hit["score"] += 1.0 / (RRF_K + rank + 1)
    return sorted(hits.values(), key=lambda h: (-h["score"], h["distance"]))[:MAX_DOCS]


def citation_label(meta):
    doc = str(meta.get("doc_name", "?")).replace("_chunks.jsonl", "")
    section = str(meta.get("section", "")).strip()
    return f"{doc} / {section}" if section else doc


def _is_new_doc(meta):
    """判断切片是否属于新入库的标准/规范文档"""
    src = str(meta.get("source_file", "")) + " " + str(meta.get("doc_name", ""))
    return any(kw in src for kw in NEW_DOC_WHITELIST)


_SOURCE_FILES_CACHE = None


def _available_sources():
    """库内实际存在的 source_file 清单（进程内只取一次）。"""
    global _SOURCE_FILES_CACHE
    if _SOURCE_FILES_CACHE is None:
        try:
            metas = collection.get(include=["metadatas"]).get("metadatas", []) or []
            _SOURCE_FILES_CACHE = sorted(
                {str(m.get("source_file", "")) for m in metas if m.get("source_file")}
            )
        except Exception as e:
            print(f"   （提示：读取 source_file 清单失败 {e}）")
            _SOURCE_FILES_CACHE = []
    return _SOURCE_FILES_CACHE


_RANGE_KEY_RE = re.compile(r"^(?P<doc>.+)_(?P<spec>\d+(?:[.\-]\d+)*)$")


def _resolve_key(key, available):
    """配置项 -> [(source_file, 章节范围或 None), ...]；解析不到返回 []。

    依次尝试：完整文件名 -> 文件名前缀 -> 文档名_章节范围。
    """
    for cand in (key, key + ".jsonl"):
        if cand in available:
            return [(cand, None)]
    hits = [f for f in available if f.startswith(key)]
    if hits:
        return [(f, None) for f in hits]
    m = _RANGE_KEY_RE.match(key)
    if m:
        doc, spec = m.group("doc"), m.group("spec")
        for cand in (doc, doc + ".jsonl"):
            if cand in available:
                return [(cand, spec)]
        hits = [f for f in available if f.startswith(doc)]
        if hits:
            return [(f, spec) for f in hits]
    return []


def _in_section_range(section, spec):
    """section 是否落在 spec 指定的章节范围内。

    spec 写法："7" 单章 ／ "3-7" 章区间 ／ "14.2" 精确前缀（命中 14.2.x）
    """
    s = str(section or "").strip()
    if not s:
        return False
    m = re.match(r"\d+", s)
    if "-" in spec:
        lo, _, hi = spec.partition("-")
        try:
            return bool(m) and int(lo) <= int(m.group(0)) <= int(hi)
        except ValueError:
            return False
    if "." in spec:
        return s == spec or s.startswith(spec + ".")
    return bool(m) and m.group(0) == spec


def _force_include_docs(event_types):
    """按场景强制拉入关键章节（章节级 + 单源/总量上限）。"""
    keys = set()
    scenes = []
    for et in event_types:
        for scene_key, chapter_keys in FORCE_INCLUDE_CHAPTERS.items():
            if scene_key in et or et in scene_key:
                keys.update(chapter_keys)
                if scene_key not in scenes:
                    scenes.append(scene_key)

    if not keys:
        return _fallback_contains(event_types)

    pins = _load_pins(scenes)
    scene_label = "+".join(scenes)

    available = _available_sources()
    if not available:
        return []

    # src -> None（整文件）或 {章节范围, ...}
    wanted = {}
    unresolved = []
    for key in sorted(keys):
        resolved = _resolve_key(key, available)
        if not resolved:
            unresolved.append(key)
            continue
        for src, spec in resolved:
            if spec is None:
                wanted[src] = None
            elif src not in wanted:
                wanted[src] = {spec}
            elif wanted[src] is not None:
                wanted[src].add(spec)

    if unresolved:
        print(f"   （强制拉入：{len(unresolved)} 个配置项未匹配到切片文件 {unresolved}）")
    if not wanted:
        return _fallback_contains(event_types)

    try:
        result = collection.get(
            where={"source_file": {"$in": sorted(wanted)}},
            include=["documents", "metadatas"],
        )
    except Exception as e:
        print(f"   （强制拉入失败：{e}）")
        return []

    docs = result.get("documents", []) or []
    metas = result.get("metadatas", []) or []

    picked = {}
    for doc, meta in zip(docs, metas):
        src = str(meta.get("source_file", ""))
        specs = wanted.get(src)
        if specs and not any(_in_section_range(meta.get("section", ""), sp)
                             for sp in specs):
            continue
        picked.setdefault(src, []).append((doc, meta))

    # 单源排序：关键条款置顶 -> 相关度粗排 -> (section, step) 保证可复现
    n_priority = len(FORCE_SOURCE_PRIORITY)
    priority_lists, manual_lists, capped = [], [], []
    for src in picked:
        rows = sorted(picked[src], key=lambda p: (
            0 if _is_pinned(p[1].get("section", ""), pins) else 1,
            -_hint_score(p[0], p[1]),
            str(p[1].get("section", "")),
            int(p[1]["step"]) if str(p[1].get("step", "")).isdigit() else 9999,
        ))
        rank = _source_rank(src)
        quota = FORCE_MAX_PER_SOURCE if rank < n_priority else FORCE_MAX_PER_AIEP
        if len(rows) > quota:
            capped.append("%s %d→%d" % (src, len(rows), quota))
            rows = rows[:quota]
        if rank < n_priority:
            priority_lists.append((src, rows))
        else:
            manual_lists.append((src, rows))

    priority_lists.sort(key=lambda p: (_source_rank(p[0]), p[0]))
    # 手册档按"最相关的一条有多相关"排序，让轮转追加的额度落在最贴题的章节上
    manual_lists.sort(key=lambda p: (-_hint_score(p[1][0][0], p[1][0][1]), p[0]))

    def take(lists, budget):
        """轮转取用：每轮每个来源各取一条。返回 (结果, 剩余, 余额, 已取来源集合)。

        轮转而不是按顺序取满——顺序取满会让排在前面的来源独占额度（实测 AIEP02
        吃光额度、GB/T 与国家预案被切光）；轮转又能保证"来源广"而不是只深挖几个。
        taken 只为诊断回传，不参与取数决策。
        """
        out, taken = [], set()
        while budget > 0 and lists:
            carry = []
            for src, rows in lists:
                if budget <= 0:
                    carry.append((src, rows))
                    continue
                out.append((src, rows[0]))
                taken.add(src)
                budget -= 1
                if len(rows) > 1:
                    carry.append((src, rows[1:]))
            lists = carry
        return out, lists, budget, taken

    p_pairs, p_left, _, p_taken = take(priority_lists, FORCE_BUDGET_PRIORITY)
    m_pairs, m_left, _, m_taken = take(manual_lists, FORCE_BUDGET_MANUAL)
    pairs = p_pairs + m_pairs
    taken = set(p_taken) | set(m_taken)
    # 某一档没取满时把余额让给另一档
    rest = FORCE_MAX_TOTAL - len(pairs)
    if rest > 0:
        more, _, _, more_taken = take(p_left + m_left, rest)
        pairs.extend(more)
        taken |= more_taken

    # ---- 配额诊断（只读，不改取数）----
    rows_by_src = dict(priority_lists + manual_lists)
    taken_by_src = {}
    for src, _ in pairs:
        taken_by_src[src] = taken_by_src.get(src, 0) + 1
    dropped_by_src = {src: len(rows) - taken_by_src.get(src, 0)
                      for src, rows in rows_by_src.items()}
    dropped = sum(dropped_by_src.values())
    logging.warning(
        "[budget] scene=%s filtered=%d entered=%d dropped=%d total_items=%d",
        scene_label, len(picked), len(taken), dropped, len(pairs))
    for src, n in sorted(dropped_by_src.items(), key=lambda kv: -kv[1])[:10]:
        if n > 0:
            logging.warning("  dropped src=%s n=%d", src, n)

    pairs = [(doc, meta) for _, (doc, meta) in pairs]

    pinned = sum(1 for _, m in pairs if _is_pinned(m.get("section", ""), pins))
    print(f"   （强制拉入 {len(pairs)} 条，覆盖 {len(taken)}/{len(picked)} 个来源，"
          f"关键条款命中 {pinned} 条"
          + ("；单源截断：" + "，".join(capped) if capped else "") + "）")
    return pairs


def search_rag_full(event_profile, top_k=15):
    try:
        event_types = _collect_event_types(event_profile)
        if not event_types:
            return "未检索到相关规程原文"

        print(f"   （识别事件类型：{event_types}）")

        primary_type = event_types[0]
        query_parts = [
            primary_type,
            " ".join(event_types[1:]) if len(event_types) > 1 else "",
            event_profile.get("location", ""),
            " ".join(event_profile.get("involved_devices", [])),
            " ".join(event_profile.get("involved_roles", [])),
        ]
        query = " ".join(str(p) for p in query_parts if p)

        query_vec = bge_model.encode_queries([query])[0].tolist()
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            include=["documents", "metadatas"],
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        combined = [(doc, meta or {}) for doc, meta in zip(docs, metas)]

        # ★ 诊断日志：打印过滤前候选切片的来源
        print("   【过滤前候选切片来源】")
        for doc, meta in combined[:20]:
            src = meta.get("doc_name") or meta.get("source_file", "?")
            sec = meta.get("section", "?")
            print(f"     - {src} / {sec}")

        try:
            scene_map = load_scene_map()
        except Exception as e:
            print(f"   （提示：场景映射表加载失败 {e}，跳过场景过滤）")
            scene_map = {}

        matched_rules, scene_src = _resolve_scenes(event_profile, event_types, scene_map)
        if matched_rules:
            print(f"   （匹配到场景[{scene_src}]：{[k for k, _ in matched_rules]}）")
            allowed_chapters, forbidden_chapters = _merge_scene_rules(matched_rules, scene_map)
            print(f"   （合并后 allowed={len(allowed_chapters)}条，forbidden={len(forbidden_chapters)}条）")

            if allowed_chapters or forbidden_chapters:
                filtered = []
                new_doc_passed = []  # ★ 新文档单独放行
                for doc, meta in combined:
                    src = str(meta.get("source_file", "")) + " " + str(meta.get("doc_name", ""))

                    # ★ 新文档白名单直接放行，不受场景过滤限制
                    if _is_new_doc(meta):
                        new_doc_passed.append((doc, meta))
                        continue

                    if any(f in src for f in forbidden_chapters):
                        continue
                    if any(a in src for a in allowed_chapters):
                        filtered.append((doc, meta))

                # ★ 新文档 + 场景过滤结果合并
                filtered = filtered + new_doc_passed

                if len(filtered) >= 3:
                    print(f"   （场景过滤生效：{len(combined)} → {len(filtered)} 条切片，其中新文档放行 {len(new_doc_passed)} 条）")
                    combined = filtered
                else:
                    print(f"   （场景过滤后仅 {len(filtered)} 条，保留原召回）")

        forced = _force_include_docs(event_types)

        existing_keys = set()
        merged = []

        def _key(doc, meta):
            return meta.get("chunk_id") or (meta.get("source_file", "") + "|" + str(hash(doc)))

        for doc, meta in combined:
            k = _key(doc, meta)
            if k not in existing_keys:
                existing_keys.add(k)
                merged.append((doc, meta))

        for doc, meta in forced:
            k = _key(doc, meta)
            if k not in existing_keys:
                existing_keys.add(k)
                merged.append((doc, meta))

        combined = merged
        print(f"   （合并后总计 {len(combined)} 条切片）")

        combined.sort(key=lambda pair: (
            pair[1].get("section", ""),
            int(pair[1]["step"]) if str(pair[1].get("step", "")).isdigit() else 9999,
        ))

        output = []
        for index, (doc, meta) in enumerate(combined):
            source_file = meta.get("source_file", meta.get("doc_name", ""))
            source = f"[来源：{source_file} - {meta.get('section', '')}]"
            step_info = f" [步骤{meta['step']}]" if meta.get("step") else ""
            output.append(f"【规程片段{index + 1}】{source}{step_info}\n{doc}")
        return "\n\n".join(output)
    except Exception as e:
        traceback.print_exc()
        return f"RAG 检索失败: {e}"


# ================= 案例检索 =================

def search_cases(event_profile, top_k=3):
    if case_collection is None:
        return "（案例库未加载）"

    try:
        event_types = _collect_event_types(event_profile)
        if not event_types:
            return "未检索到相似历史案例"

        primary = event_profile.get("primary_event") or {}
        severity = primary.get("severity_level") or event_profile.get("severity_level", "")
        scene = primary.get("scene_category") or event_profile.get("scene_category", "")

        query = " ".join([str(e) for e in event_types] + [str(severity), str(scene)])
        if not query.strip():
            return "未检索到相似历史案例"

        query_vec = bge_model.encode_queries([query])[0].tolist()
        results = case_collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        if not docs:
            return "未检索到相似历史案例"

        output = []
        for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
            sim = 1 - dist
            if sim < 0.5:
                continue
            sim_label = "高" if sim > 0.75 else "中" if sim > 0.6 else "低"
            output.append(
                f"【历史案例{meta.get('case_id', i+1)}】相似度：{sim:.2f}（{sim_label}）\n"
                f"事件类型：{meta.get('event_type', '')} | 事故等级：{meta.get('severity_level', '')}\n"
                f"事件描述：{doc}\n"
                f"采取的行动：{meta.get('actions_taken', '')}\n"
                f"结果：{meta.get('outcome', '')}\n"
                f"经验教训：{meta.get('lessons_learned', '')}\n"
                f"与规程的偏差：{meta.get('deviation', '无')}"
            )

        if not output:
            return "未检索到相似度足够高的历史案例"

        return "\n\n".join(output)
    except Exception as e:
        traceback.print_exc()
        return f"案例检索失败：{e}"


# ================= 图谱查询 =================

GRAPH_SEED_CYPHER = """
MATCH (n)
WHERE (n:Entity OR n:Condition)
  AND any(t IN $terms WHERE n.name CONTAINS t)
OPTIONAL MATCH (a:Action)-[:INVOLVES|REQUIRES]->(n)
OPTIONAL MATCH (r:Role)-[:EXECUTES]->(a)
RETURN labels(n)[0] AS node_label, n.name AS node,
       collect(DISTINCT a.name)[0..5] AS actions,
       collect(DISTINCT r.name)[0..5] AS roles,
       [] AS conditions
LIMIT 8
"""

GRAPH_ROLE_CYPHER = """
MATCH (r:Role)
WHERE any(t IN $terms WHERE r.name CONTAINS t)
MATCH (r)-[:EXECUTES]->(a:Action)
OPTIONAL MATCH (a)-[:REQUIRES]->(c:Condition)
RETURN 'Role' AS node_label, r.name AS node,
       collect(DISTINCT a.name)[0..5] AS actions,
       [] AS roles,
       collect(DISTINCT c.name)[0..5] AS conditions
LIMIT 5
"""


# ================= 图谱节点名质量过滤（v8.24）=================
# 背景：图谱由**离线正则抽取**，存在脏节点——**模态词 / 虚词被当成 Action**。
# 实测证据（output/parsed_records.jsonl 第 1–2 行）：
#   {"role": "公司范围、财物或员工受到的任何恐吓", "action_text": "一律视作", ...}
#   {"role": "所有枪械",                        "action_text": "一律视作", ...}
# 即"一律视作"被抽成了动作，且"角色"是一整句话。这类条目进 prompt 会把模型带偏
# （照着把"一律视作"编排成处置步骤）。
#
# 规则（**保守**：宁可少给，不可给错）：
#   ① 命中模态词 / 虚词黑名单 → 丢；  ② 名字过长（多半是一整句话）→ 丢。
# 只做**减负**，不做改写：过滤后的图谱仍只作"动作与岗位的补充参考"，第一依据永远是规程原文。
_KG_JUNK_WORDS = (
    "一律", "视作", "须", "不得", "应当", "应该", "必须", "否则", "一概", "凡是",
    "如下", "上述", "相关", "有关", "备注", "重要", "注意", "除非", "除外",
)
# ★ 判据的取舍依据（实测 output/parsed_records.jsonl，2646 条）：
#   **长度是坏判据** —— 8~12 字那一段反而更脏（"应根据需要及时调整""同样有可能受水淹影响"），
#   而 12~16 字那段才是真动作（"使用无线电通知驾驶员立即停车""必须将烟经由风井抽出站外"）。
#   真正区分"节点名 vs 规范性从句"的信号是下面三条：
_KG_CLAUSE_PREFIX = re.compile(      # ① 规范性从句开头（"应…""须…""按照…"）
    r"^(应|须|必须|必需|需要|同样|一律|凡|若|除非|按照|依照|依据|根据|不得)")
_KG_XREF = ("本章", "上述", "下列", "如下", "本题目", "该章", "本节", "本条")   # ② 章节交叉引用
# ③ 句子级标点。**注意不含"、"（顿号）** —— 顿号多是**并列实体名**
#    （"行车调度员、车辆段列车控制主管""车站督导员、公安人员"），那是合法节点，不能误杀。
_KG_SENT_PUNC = re.compile(r"[，。；：！？,;:]")
_KG_NODE_MAX_LEN = 22                # 兜底：挡住"车辆段控制中心及安保部协调…"这类整句（最长 75 字）


def _kg_node_ok(name, strict=False):
    """该图谱节点名是否**干净到可以进 prompt**。False → 调用方丢弃该条目。

    **按节点类型分级**（实测 output/parsed_records.jsonl 得出的取舍）：
    - `strict=False`（Role / Entity / Condition）—— 从宽。岗位是**分派依据**，
      实测严格模式下会误杀"有关驾驶员""相关管理人员""车站督导员、公安人员"等**合法岗位**，
      代价远大于收益，故只做长度与句子标点两道。
    - `strict=True`（**Action**）—— 从严。用户报的 bug 就在这一层
      （"一律视作"被抽成动作），且动作可**低成本丢弃**：prompt 里动作的第一依据是规程原文。
    """
    s = (name or "").strip()
    if not s:
        return False
    if len(s) > _KG_NODE_MAX_LEN:                    # 兜底：整句
        return False
    if _KG_SENT_PUNC.search(s):                      # ③ 逗号/分号/冒号 → 是从句，不是名字
        return False
    if not strict:
        return True
    if any(w in s for w in _KG_JUNK_WORDS):          # 模态词 / 虚词
        return False
    if _KG_CLAUSE_PREFIX.match(s):                   # ① 规范性从句
        return False
    if any(w in s for w in _KG_XREF):                # ② 章节交叉引用
        return False
    return True


def _kg_clean_list(names, strict=False):
    """过滤一组节点名（图谱里的 actions / roles / conditions 列表）。"""
    return [x for x in (names or []) if _kg_node_ok(x, strict=strict)]


def query_graph(terms):
    if not terms:
        return []
    rows = []
    try:
        with neo4j_driver.session(notifications_min_severity="OFF") as session:
            for cypher in (GRAPH_SEED_CYPHER, GRAPH_ROLE_CYPHER):
                try:
                    rows.extend(dict(record) for record in session.run(cypher, terms=terms))
                except Exception as e:
                    print(f"   （提示：图谱查询失败 {e}）")
    except Exception as e:
        print(f"   （提示：图谱连接失败 {e}）")
        return []

    # ---- 脏节点过滤：主节点脏 → 整行丢弃；列表里有脏条目 → 只剔脏条目 ----
    clean, dropped = [], []
    for row in rows:
        if not _kg_node_ok(row.get("node")):
            dropped.append(str(row.get("node")))
            continue
        row = dict(row)
        for k in ("actions", "roles", "conditions"):
            if row.get(k):
                # actions 是**动作层** → 从严；roles / conditions 从宽（岗位不能误杀）
                row[k] = _kg_clean_list(row[k], strict=(k == "actions"))
        clean.append(row)
    if dropped:
        logging.info("[kg] 过滤脏节点 %d 个：%s", len(dropped), "、".join(dropped[:5]))
    return clean


def search_neo4j_subgraph(event_profile):
    keywords = []
    all_candidates = (
        event_profile.get("involved_roles", []) +
        event_profile.get("involved_devices", []) +
        _collect_event_types(event_profile) +
        [event_profile.get("location", "")]
    )
    fallback_entities = [
        "车辆段列车控制主管", "行车调度员", "车站值班员", "值班站长",
        "道岔", "信号", "ATS控制台", "烟雾报警", "紧急停车",
        "雪停后", "暴雪", "降雪量", "火灾", "脱轨", "分离",
        "积水", "水淹", "乘客被困",
    ]
    for ent in all_candidates + fallback_entities:
        if ent and ent in str(event_profile):
            keywords.append(ent)

    if not keywords:
        return "未匹配到特定实体"

    try:
        scene_map = load_scene_map()
    except Exception:
        scene_map = {}

    event_types = _collect_event_types(event_profile)
    matched_rules, _ = _resolve_scenes(event_profile, event_types, scene_map)
    if matched_rules:
        allowed_chapters, _ = _merge_scene_rules(matched_rules, scene_map)
    else:
        allowed_chapters = []

    facts = []
    dropped = 0
    try:
        with neo4j_driver.session() as session:
            for kw in keywords:
                # 返回**分离的节点名**（而不是拼好的字符串）—— 这样才能逐名做质量过滤
                result = session.run("""
                    MATCH (n {name: $name})-[r*1..2]-(m)
                    RETURN n.name AS a, type(r[0]) AS rel, m.name AS b
                    LIMIT 10
                """, name=kw)
                for record in result:
                    a, b = record["a"], record["b"]
                    # 种子查询命中 :Entity / :Condition → **从宽**（实体/条件名保留价值高）
                    if not (_kg_node_ok(a) and _kg_node_ok(b)):
                        dropped += 1
                        continue
                    facts.append(f"{a} --[{record['rel']}]-- {b}")

                if allowed_chapters:
                    chapter_filter = " OR ".join([f"ns.section CONTAINS '{c}'" for c in allowed_chapters])
                    step_result = session.run(f"""
                        MATCH (a:Action)-[ns:NEXT_STEP]->(b:Action)
                        WHERE ({chapter_filter})
                          AND (a.name CONTAINS $keyword OR b.name CONTAINS $keyword)
                        RETURN a.name AS a, b.name AS b,
                               ns.step_from AS step_from,
                               ns.step_to AS step_to
                        ORDER BY ns.step_from
                        LIMIT 10
                    """, keyword=kw)
                else:
                    step_result = session.run("""
                        MATCH (a:Action)-[ns:NEXT_STEP]->(b:Action)
                        WHERE (a.name CONTAINS $keyword OR b.name CONTAINS $keyword)
                        RETURN a.name AS a, b.name AS b,
                               ns.step_from AS step_from,
                               ns.step_to AS step_to
                        ORDER BY ns.step_from
                        LIMIT 5
                    """, keyword=kw)

                for record in step_result:
                    a, b = record["a"], record["b"]
                    # NEXT_STEP 两端都是 :Action → **从严**（用户报的 bug 就在这一层）
                    if not (_kg_node_ok(a, strict=True) and _kg_node_ok(b, strict=True)):
                        dropped += 1
                        continue
                    facts.append(f"{a} --[NEXT_STEP]-- {b}"
                                 f"（步骤{record['step_from']}→{record['step_to']}）")
    except Exception as e:
        print(f"⚠️ 图谱查询失败：{e}")
        return "⚠️ 图谱服务暂不可用"

    if dropped:
        print(f"   （图谱：已滤除 {dropped} 条脏节点关系——模态词/超长节点名）")
        logging.info("[kg] search_neo4j_subgraph 滤除脏关系 %d 条", dropped)

    if not facts:
        return "图谱中未查询到相关关系"

    return "\n".join(list(set(facts)))


# ================= 查询路由 =================

ROUTER_PROMPT = """你是京港地铁《意外及事故紧急程序手册》检索系统的查询改写助手。

任务：
1. 判断意图：
   - "definition"：用户在问某个事件、术语、等级是什么 / 怎么定义 / 怎么划分
   - "procedure"：用户在问怎么做 / 如何处置 / 谁负责 / 呈报流程
2. 生成 3 条检索词，从三个角度覆盖，提高召回：
   - 角度1：专业术语
   - 角度2：手册可能使用的同义说法
   - 角度3：业务模块（如「呈报事故」「大客流管理」「运营紧急状态」「恐吓事件」）
3. 抽取 1~3 个 2~8 字的核心术语放进 kg_terms，用于知识图谱检索。

只输出 JSON，不要任何 Markdown 标记，格式如下：
{"intent": "definition", "queries": ["检索词1", "检索词2", "检索词3"], "kg_terms": ["术语1", "术语2"]}

用户原始问题："""

QUESTION_WORDS = ["请问", "怎么样", "怎么办", "是什么", "什么是", "什么意思",
                  "怎么", "如何", "哪些", "什么", "为什么", "多少", "是否",
                  "应该", "需要", "介绍一下", "介绍", "告诉我", "呢", "吗"]


def fallback_terms(question):
    text = question
    for word in QUESTION_WORDS:
        text = text.replace(word, "")
    text = text.strip(" 　?？。.，,、!！：:")
    return [text] if 2 <= len(text) <= 12 else []


def normalize_terms(terms):
    out = []
    for term in terms:
        term = str(term).strip()
        if not term:
            continue
        variants = [term]
        for level, klass in LEVEL_TERMS.items():
            if level in term:
                variants.append(term.replace(level, klass))
        for variant in variants:
            if len(variant) >= 2 and variant not in out:
                out.append(variant)
    return out[:12]


def route_question(question):
    try:
        raw = call_llm(ROUTER_PROMPT + question)
        raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.S)
            if not match:
                raise
            result = json.loads(match.group(0))
        intent = result.get("intent", "definition")
        if intent not in ("definition", "procedure"):
            intent = "definition"
        queries = [str(q).strip() for q in result.get("queries", []) if str(q).strip()]
        terms = normalize_terms(result.get("kg_terms", []))
        if queries:
            print(f"   -> 意图: {intent} | 检索词: {queries} | 图谱词: {terms}")
            return intent, queries, terms
        print("   路由结果缺少检索词，降级处理")
    except Exception as e:
        print(f"   路由失败，降级处理: {e}")
    terms = normalize_terms(fallback_terms(question))
    return "definition", [question], terms


# ================= 答案生成 =================

GROUNDING_RULES = """你是京港地铁《意外及事故紧急程序手册》的问答助手，必须遵守以下铁律：

1. 只能依据下面【手册原文】作答。不得使用你自身的行业常识、其他城市或公司的标准、以及任何网络知识。
2. 每条结论后面必须标注出处，格式为（文档名 / 章节）。
3. 如果【手册原文】没有覆盖用户所问的内容，必须直接回答「手册中未找到相关规定」。
4. 【知识图谱信息】只能用来补充「相关处置动作」和「责任岗位」。
5. 不要提及「检索」「向量」「上下文」「系统内部」等实现细节，直接给答案。"""

INTENT_HINT = {
    "definition": "用户在询问概念、等级或定义。请优先给出手册原文中的定义，关键阈值要原样引用。",
    "procedure": "用户在询问处置流程。请按手册给出的顺序列出动作步骤，并注明责任岗位。",
}

# ★ 新增：应急预案生成的强约束
PLAN_RULES = """
【复合事件处置方案强约束】
在生成处置方案时，必须遵守以下要求：

1. 【分级必须对照标准】
   判定事故等级时，必须逐条对照《国家城市轨道交通运营突发事件应急预案》7.2 的四档标准
   （死亡人数 / 重伤人数 / 经济损失 / 中断时长），明确命中哪一条。
   如果信息不足，必须写"信息不足，暂按一般事件处置，持续跟踪升级"，禁止用"推断"。

2. 【必须覆盖四个维度】处置方案必须明确覆盖以下四个维度，缺一不可：
   ① 人员疏散：疏散路径、集合点、弱势群体优先原则
   ② 关停决策：明确是否关闭出入口/车站、是否区段/线路停运，引用具体条款
   ③ 信息报告：明确报告对象、时限（如"1小时内书面快报"）、报告格式
   ④ 大客流管控：引用 GB/T 38707 14.2.15 的具体措施（如设置客流控制点、改变扶梯走向等）

3. 【步骤排序原则】
   处置步骤必须按"人员安全 > 关键设施 > 其他"的优先级排序。
   涉及人员伤亡时，救治和疏散必须进入前 3 步。

4. 【判定等级后必须输出】
   响应级别 + 责任主体（省级/市级/运营单位）+ 报告时限。
"""


def build_final_prompt(question, intent, hits, graph_rows):
    if hits:
        blocks = []
        for hit in hits:
            meta = hit["meta"]
            blocks.append(
                f"【来源】{citation_label(meta)}"
                f"（版本 {meta.get('version', '?')}，相似度距离 {hit['distance']:.3f}）\n{hit['doc']}"
            )
        rag_context = "\n\n".join(blocks)
        if len(rag_context) > MAX_CONTEXT_CHARS:
            rag_context = rag_context[:MAX_CONTEXT_CHARS] + "\n\n……（原文过长，后续片段已截断）"
    else:
        rag_context = "（没有任何手册原文命中）"

    if graph_rows:
        lines = []
        for row in graph_rows:
            parts = []
            if row.get("actions"):
                parts.append("相关动作：" + "；".join(row["actions"]))
            if row.get("roles"):
                parts.append("责任岗位：" + "；".join(row["roles"]))
            if row.get("conditions"):
                parts.append("触发条件：" + "；".join(row["conditions"]))
            detail = " | ".join(parts) if parts else "（无关联动作）"
            lines.append(f"- {row.get('node_label')}「{row.get('node')}」{detail}")
        graph_context = "\n".join(lines)
    else:
        graph_context = "（未命中相关图谱节点）"

    return f"""{GROUNDING_RULES}

{PLAN_RULES}

【当前提问类型】{INTENT_HINT[intent]}

【手册原文】（共 {len(hits)} 段，按相关度排序）
{rag_context}

【知识图谱信息】（仅作动作与岗位补充；**图谱可能有脏数据，与手册原文冲突时以原文为准**）
{graph_context}

【用户问题】{question}

请严格按上述铁律作答，并逐条标注出处。"""


# ================= 核心流程 =================

def process_user_query(user_query, encoder, collection):
    print(f"\n[用户输入]：{user_query}")

    print("1. 正在调用 DeepSeek 判定意图并改写查询...")
    intent, queries, terms = route_question(user_query)

    print("2. 正在检索手册向量库...")
    arms = list(dict.fromkeys([user_query] + queries))[:4]
    hits = retrieve_from_rag(encoder, collection, arms)
    if hits:
        for hit in hits:
            print(f"   [{hit['distance']:.3f}] {citation_label(hit['meta'])}")
    else:
        print("   （没有命中的手册段落）")

    print("3. 正在检索 Neo4j 知识图谱...")
    graph_rows = query_graph(terms)
    if graph_rows:
        for row in graph_rows:
            print(f"   {row.get('node_label')}「{row.get('node')}」")
    else:
        print("   （未命中图谱节点）")

    print("4. 正在生成最终答案...")
    answer = call_llm(build_final_prompt(user_query, intent, hits, graph_rows))
    print("================ 最终回答 ================")
    print(answer)
    print("==========================================")
    return answer


if __name__ == "__main__":
    from event_understand import understand_event
    from plan_generator import generate_plan

    llm_client = client
    print("=" * 60)
    print("  轨道交通应急事件智能处置方案生成系统")
    print("=" * 60)

    try:
        bge_model = load_encoder()
        collection = load_collection()

        while True:
            try:
                question = input("\n请描述应急事件（输入 q 退出）：\n> ")
            except (EOFError, KeyboardInterrupt):
                break

            question = question.strip()
            if question.lower() == "q":
                break
            if not question:
                continue

            try:
                print("\n🧠 正在解析事件...")
                event_profile = understand_event(question, llm_client)
                primary = event_profile.get("primary_event") or {}
                print(f"   事件类型：{primary.get('event_type') or event_profile.get('event_type', '未识别')}")
                print(f"   事故等级（上游判定，下游须沿用；无量化数据时会标注未经数字核实）："
                      f"{primary.get('severity_level') or event_profile.get('severity_level', '未识别')}")
                print(f"   位置：{event_profile.get('location', '未识别')}")
                print(f"   涉及岗位：{event_profile.get('involved_roles', [])}")
                sec_events = event_profile.get("secondary_events", [])
                if sec_events:
                    print(f"   次生事件：{[s.get('event_type') for s in sec_events if isinstance(s, dict)]}")

                print("\n🔍 正在检索规程...")
                rag_context = search_rag_full(event_profile, top_k=15)
                print("🔍 正在抽取图谱子图...")
                kg_context = search_neo4j_subgraph(event_profile)

                print("🔍 正在检索历史案例...")
                case_context = search_cases(event_profile, top_k=3)
                preview = case_context[:100].replace("\n", " ")
                print(f"   （案例检索预览：{preview}...）")

                print("\n🤖 正在生成处置方案...\n")
                try:
                    answer = generate_plan(
                        question, event_profile, rag_context, kg_context,
                        case_context, llm_client
                    )
                except TypeError:
                    print("   （提示：plan_generator.py 还是旧签名，未接收 case_context）")
                    answer = generate_plan(
                        question, event_profile, rag_context, kg_context, llm_client
                    )

                print("\n" + "=" * 60)
                print(answer)
                print("=" * 60)
            except Exception:
                print("【本次事件处理失败】")
                traceback.print_exc()
    finally:
        neo4j_driver.close()

    print("\n已退出。")
