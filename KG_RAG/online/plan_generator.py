# -*- coding: utf-8 -*-
"""路线 B 第二步：LLM 出 JSON → 代码排序/合并/计数/定阶段 → 还原 Markdown。

第一步（JSON 化，`v0.4.0-json-channel`）保持不变的：
- prompt 与 JSON 解析、重试 1 次、降级为纯文本的链路
- `parallel_with` 仍保留在 JSON、仍渲染，**不参与排序**
- `escalation.extra_steps` 走独立管道：不参与 steps[] 的合并/截断/排序

第二步新增（本文件）：
- TIER 五档 + sort_key=(TIER, n)
- 方案 D：第 1 档里 挡水/救治/疏散 批量占位 1/2/3，其余第 1 档按 n 排第 4 位起
- POSITION_RULES 只留 3 条（挡水≤3、救治≤3、疏散≤5）；tier≥2 的上限删除，改档位偏移诊断
- COUNT_RULES + MERGE_RULE（同类同角色合并，定位=防掺水）
- stage_of(n, action_type)：位置分箱 + 恢复善后例外
- norm_role()
"""
import glob
import json
import logging
import os
import re
import traceback


def _get_event_types(event_profile):
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


def _get_severity(event_profile):
    primary = event_profile.get("primary_event")
    if primary and isinstance(primary, dict):
        return (
            primary.get("severity_level") or primary.get("severity") or "未知",
            primary.get("severity_reason", ""),
        )
    return (
        event_profile.get("severity_level") or event_profile.get("severity") or "未知",
        event_profile.get("severity_reason", ""),
    )


# ================= 排序 / 计数 / 阶段 的规则表 =================

STAGES = [
    ("先期处置", "阶段一 先期处置（0–3 分钟）"),
    ("现场处置", "阶段二 现场处置（3–15 分钟）"),
    ("扩大响应", "阶段三 扩大响应（15–60 分钟）"),
    ("恢复善后", "阶段四 恢复善后（1 小时后）"),
]
STAGE_KEYS = [k for k, _ in STAGES]
STAGE_HEAD = dict(STAGES)

# 阶段 → 时限（展示用）：阶段由位置推导，时限由阶段推导，二者恒定一致。
# LLM 的 deadline_text 保留在 JSON 只为留痕，**不再直接渲染**（重排后它会与阶段脱节）。
STAGE_DEADLINE = {"先期处置": "目标 3 分钟内完成", "现场处置": "目标 15 分钟内完成",
                  "扩大响应": "目标 60 分钟内完成", "恢复善后": "1 小时后持续推进"}
STAGE_MINUTES = {"先期处置": 3, "现场处置": 15, "扩大响应": 60, "恢复善后": 60}

# 五档：人身安全 与 切断危险源 同档（救人/挡水本就同时展开，见 v4 §2 实测）
TIER = {"人身安全": 1, "切断危险源": 1, "关键设备": 2, "运营调整": 3,
        "信息报告": 4, "恢复善后": 5}
TIER_OTHER = 6

# ---- 场景化 TIER 覆盖（v1：只有 TIER 场景相关；见 _design_scene_tier_config.md）----
# 默认表 TIER 保持不变；scene_tier_map.json 只登记"要覆盖的场景"，未列出的场景走默认。
TIER_MAP_FILE = "scene_tier_map.json"
_TIER_OVERRIDES = None          # 惰性加载：{scene: {action_type: tier}}


def _load_tier_map():
    """读 scene_tier_map.json 的 tier_overrides。缺失/损坏 → {}（回退默认，不崩）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, TIER_MAP_FILE),
                 os.path.join("online", TIER_MAP_FILE),
                 TIER_MAP_FILE):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except OSError:
            continue                                    # 换下一个候选路径
        except (ValueError, TypeError) as e:
            logging.warning("[tier] %s 解析失败：%s → 全部场景用默认 TIER", path, e)
            return {}
        out = {}
        for scene, cfg in (data or {}).items():
            if not isinstance(cfg, dict):
                continue
            ov = cfg.get("tier_overrides")
            if not isinstance(ov, dict):
                continue
            clean = {}
            for at, t in ov.items():
                if isinstance(t, bool) or not isinstance(t, int):
                    logging.warning("[tier] %s.%s 档号需为整数，已忽略（%r）", scene, at, t)
                    continue
                clean[_s(at)] = t
            if clean:
                out[scene] = clean
        logging.warning("[tier] 场景 TIER 覆盖已加载：%s", out or "（空，全部用默认）")
        return out
    logging.warning("[tier] %s 未找到 → 全部场景用默认 TIER", TIER_MAP_FILE)
    return {}


def _tier_overrides():
    global _TIER_OVERRIDES
    if _TIER_OVERRIDES is None:
        _TIER_OVERRIDES = _load_tier_map()
    return _TIER_OVERRIDES


def _effective_tier(action_type, scene):
    """场景覆盖优先；未命中 / scene 为 None → 默认 TIER。"""
    at = _s(action_type)
    if scene:
        ov = _tier_overrides().get(scene)
        if ov and at in ov:
            return ov[at]
    return TIER.get(at, TIER_OTHER)


def _scene_key(event_profile, tier_map):
    """按**主事件**的 event_type，在配置的场景键里定位当前场景；无命中 → None。

    只认主事件、不认次生事件：暴雨的主事件是「暴雨导致车站积水倒灌」，
    但其次生常含「大客流拥挤」——若纳入次生匹配，暴雨会被误判成大客流场景
    （验收要求"暴雨无回归"，即必须走默认 TIER）。
    子串规则（scene_key in et or et in scene_key）与检索层 _match_scenes 一致，
    但不依赖 main.py。
    """
    primary = event_profile.get("primary_event")
    et = _s(primary.get("event_type")) if isinstance(primary, dict) else ""
    if not et:
        et = _s(event_profile.get("event_type"))
    for scene in (tier_map or {}):
        if scene.startswith("_"):
            continue
        if et and (scene in et or et in scene):
            return scene
    return None


# ---- 置信自检（v8.4）：把"系统自己也没底的地方"显式说出来 ----
_SCENE_KEYS = None


def _load_scene_keys():
    """**只读**读 scene_chapter_map.json 的场景键（缺失/损坏 → 空列表，不崩）。

    仅供置信自检——判断事件类型能否对上检索层使用的场景键；不参与检索、不改检索层。
    """
    global _SCENE_KEYS
    if _SCENE_KEYS is not None:
        return _SCENE_KEYS
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "scene_chapter_map.json"),
                 os.path.join("online", "scene_chapter_map.json"),
                 "scene_chapter_map.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except OSError:
            continue
        except (ValueError, TypeError) as e:
            logging.warning("[scene] scene_chapter_map.json 解析失败：%s → 跳过场景自检", e)
            _SCENE_KEYS = []
            return _SCENE_KEYS
        _SCENE_KEYS = [k for k in (data or {}) if not str(k).startswith("_")]
        return _SCENE_KEYS
    logging.warning("[scene] scene_chapter_map.json 未找到 → 跳过场景自检")
    _SCENE_KEYS = []
    return _SCENE_KEYS


def _scene_match_note(event_profile):
    """按检索层 _match_scenes 同款规则（**全部**事件类型 × 子串互含）自检场景匹配。

    返回 (matched_keys, note)。**只报告，不修检索**——命中偏差（如把"桥下仓库火灾"
    当成"车站房间火警"）无法自动识别，因此这里只把"对上了哪些场景键"摊给用户看。
    """
    if not isinstance(event_profile, dict):
        return [], "无法自检（无事件画像）"
    keys = _load_scene_keys()
    if not keys:
        return [], "无法自检（场景键缺失）"
    # 与检索层同一条优先级链：先看受控 scene_key，再回退子串匹配（否则自检与实际检索不一致）
    raw = event_profile.get("scene_key")
    if isinstance(raw, str):
        raw = [raw]
    ctrl = [str(k).strip() for k in (raw or []) if str(k).strip() in keys]
    if ctrl:
        return ctrl, "✅ **受控归类**命中场景键 %s（由事件解析给出）" % ctrl
    types = [_s(t) for t in _get_event_types(event_profile)]
    if not types:
        return [], "无法自检（事件类型缺失）"
    matched = [k for k in keys if any(k in et or et in k for et in types if et)]
    if matched:
        return matched, "✅ 子串匹配命中场景键 %s（**未经受控归类**，请留意）" % matched
    return [], ("⚠️ **未对上任何场景键**——检索层将走关键词兜底，引用条款可能不贴切；"
                "请重点核对每步「依据」是否真对应本次事件")


def _confidence_checks(event_profile, sev, risks, cite_stat=None):
    """置信自检的逐条文案（全部由代码判定，不由 LLM 生成）。"""
    matched, note = _scene_match_note(event_profile)
    out = [("场景匹配", note)]
    cs = cite_stat or {}
    if cs.get("total"):
        if not cs.get("susp") and not cs.get("broken"):
            out.append(("引用可证实性", "✅ %d 条规程引用**全部可在库中查到**" % cs["ok"]))
        else:
            msg = ("⚠️ 可证实 %d 条，**存疑 %d 条**" % (cs["ok"], cs["susp"]))
            if cs.get("broken"):
                msg += "（另有引用编号**被分号切断**，如 `GB；T 38707`）"
            if cs.get("samples"):
                msg += "；存疑样例：%s" % "、".join(cs["samples"][:3])
            out.append(("引用可证实性", msg))
    if cs.get("nonclause"):
        out.append(("非条款来源", "ℹ️ %d 条引用来自知识图谱/案例经验等**非规程来源**，不等同于规程条款"
                    % cs["nonclause"]))
    out.append(("复合险情",
                "✅ 已识别 %d 类" % len(risks) if risks
                else "⚠️ 未识别为多险并发——**若实际存在多险叠加，本清单可能不全**"))
    _lvl = _s(sev.get("level"))
    _tiers = [t for t in (sev.get("tiers") or []) if isinstance(t, dict)]
    _all_miss = bool(_tiers) and all("未命中" in _s(t.get("hit")) for t in _tiers)
    if not _lvl or _lvl == "尚未成立" or _lvl.startswith("信息不足"):
        out.append(("定级", "⚠️ **未定级**（精确判定尚未成立）——现按「初判等级」处置，**须以现场核实为准**"))
    elif _all_miss:
        out.append(("定级", "⚠️ **无量化数据**：等级「%s」由**定性事实判定**（非 7.2 数字命中）——"
                           "**须以现场核实为准**" % _lvl))
    else:
        out.append(("定级", "✅ 已按 7.2 对照定级"))
    return out


# ---- 引用可证实性自检（v8.8）：把 `依据` 逐条回查规程库，机械证伪"编造条款" ----
_CITE_INDEX = None
_CITE_SPLIT = re.compile(r"[；;]")
_CITE_BREAK = re.compile(r"GB\s*[；;，,、]\s*T")     # "GB；T 38707" —— 分号切进了标准号


def _load_citation_index():
    """**只读**建规程库索引（AIEP 切片 + JSON 文档），供把 `依据` 逐条回查。

    数据源与检索层同源（`long_data/AIEP/**/*_chunks.jsonl` + `long_data/JSON/*.jsonl`）；
    用 jsonl 而非 chroma：**不依赖向量模型、确定性、可离线复算**。
    """
    global _CITE_INDEX
    if _CITE_INDEX is not None:
        return _CITE_INDEX
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    aiep, jdocs = {}, {}
    try:
        for f in glob.glob(os.path.join(root, "long_data", "AIEP", "**", "*_chunks.jsonl"),
                           recursive=True):
            for line in open(f, encoding="utf-8", errors="replace"):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                did, sec = _s(d.get("doc_id")), _s(d.get("section"))
                if did:
                    aiep.setdefault(did, set()).add(sec.split()[0] if sec else "")
        for f in glob.glob(os.path.join(root, "long_data", "JSON", "*.jsonl")):
            for line in open(f, encoding="utf-8", errors="replace"):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                dn, sec = _s(d.get("doc_name")), _s(d.get("section"))
                if dn:
                    jdocs.setdefault(dn, set()).add(sec)
    except OSError as e:
        logging.warning("[cite] 规程库索引建立失败：%s → 跳过引用自检", e)
    _CITE_INDEX = (aiep, jdocs)
    return _CITE_INDEX


def _split_cites(txt):
    """按「；」切分引用，但**跳过方括号内**——模型会写 `[步骤1；7]`、标题里也带「；」。"""
    out, buf, depth = [], [], 0
    for ch in txt:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        if ch == "；" and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def _check_citations(basis):
    """逐条核对 `依据`。返回 (可证实数, 存疑列表, 非条款来源列表, 是否发现编号被切断)。

    - **可证实**：AIEP 文档/章节、或已知文档的条款号在库中查得到；
    - **存疑**：文档或章节**查不到**（`GB；T` 这类格式损坏会先修复再查，并单独记为"格式损坏"）；
    - **非条款来源**：知识图谱事实 / 案例经验 / 描述性文字——不是幻觉，但**不该当"规程依据"**。
    """
    aiep, jdocs = _load_citation_index()
    if not aiep and not jdocs:
        return 0, [], [], False
    raw = _s(basis)
    broken = bool(_CITE_BREAK.search(raw))
    txt = _CITE_BREAK.sub("GB/T", raw)
    ok, susp, nonc = 0, [], []
    for c in (x.strip() for x in _split_cites(txt)):
        if not c:
            continue
        if c.startswith("知识图谱") or re.search(r"案例\d*经验|经验$|^附录", c) \
                or not re.match(r"[A-Za-z0-9一-鿿]", c):
            nonc.append(c)
            continue
        # v8.21：放宽到**允许下划线分隔**与**中文章节名**。
        # 原式 `AIEP\s*(\d+)\s*([0-9A-Za-z]+)` 吃到 `_`/中文就回溯：`AIEP01_1C5` 被切成
        # `AIEP00`+`1` → 误报"存疑"（模型照抄上下文里的 source_file，含下划线）。
        # 放宽后**仍检查章节是否在索引里** → 真编造（AIEP99_ZZZ）照样判存疑，防编造能力不削弱。
        m = re.match(r"AIEP\s*(\d+)\s*[_\-]?\s*([0-9A-Za-z一-鿿]+)", c)
        if m:
            did, sec = "AIEP%02d" % int(m.group(1)), m.group(2).upper()
            if did in aiep and sec in aiep[did]:
                ok += 1
            else:
                susp.append(c)
            continue
        # 标准号别名：方案常写 "GB/T 38707 14.2.15"，库里的 doc_name 是 "GBT 38707-2020(…)"
        flat = re.sub(r"\s+", "", c).lower()
        if flat.startswith(("gb/t38707", "gbt38707", "gb38707")):
            gbt = next((dn for dn in jdocs if "38707" in dn), None)
            msec = re.search(r"(\d+(?:\.\d+)+)", c)
            if gbt and (not msec or any(s.startswith(msec.group(1)) for s in jdocs[gbt])):
                ok += 1
            else:
                susp.append(c)
            continue
        hit = [dn for dn in jdocs if dn[:14] in c]
        if hit:
            if any(s and s[:6] in c for s in jdocs[hit[0]]):
                ok += 1
            else:
                susp.append(c)          # 认得出是哪份文档、但条款号对不上 → 存疑
            continue
        nonc.append(c)                  # 认不出任何来源前缀（断裂片段/描述性文字）→ 不计入存疑
    return ok, susp, nonc, broken


ACTION_TYPES = ("人身安全", "切断危险源", "关键设备", "运营调整", "信息报告", "恢复善后")

# 位置规则：挡水/救治/疏散/召唤外部力量，都落在第 1 档内（因此可在同档内满足，不破坏单调性）
KW_KOU = re.compile(r"防洪板|沙包|挡水|排水设施|潜水泵|排雨泵|沙袋|排水泵|防淹门")   # 只收「动作」用词；"防止雨水倒灌"是意图，已按裁定移除
KW_JIU = re.compile(r"救护车|施救|救助|救治|致电120|急救|紧急救护|紧急救治|送医|送往医院")
KW_SHU = re.compile(r"宣布疏散|疏散车站|疏散乘客|疏散站台|疏散撤离|疏散.{0,8}引导|组织.{0,6}疏散|引导.{0,18}疏散|引导.{0,18}撤离|撤离车站")
# v8.19b：召唤**外部力量**（消防/公安/救护）——是处置动作，不是"信息报告"。
# 词表命中式，覆盖不稳（同 KW_* 家族），且由 `has_external_need` 门控 → 只在需要外部力量的场景生效。
KW_CALL = re.compile(
    r"(?:要求|请求|呼叫|召唤|联系|联络|致电|拨打|报警|报请|提请|通知)[^，。；]{0,6}"
    r"(?:消防(?!设施|喷淋|栓|泵|器材)|公安|救护|急救|紧急服务|医疗机构|119|110|120)"
    r"|(?:消防|公安|救护|急救)[^，。；]{0,4}(?:到场|增援|支援|协助)")
# v8.20.1 补 `拨打|报警`：「立即拨打 110、120 报警」是恐袭场景最常见写法，
# 原动词表（要求/请求/呼叫/召唤/…）不含「拨打」→ 恐袭用例召唤规则整条落空（全量回归发现 1）。
# 危险源**场景**触发词（只看事件画像）。`_EXTERNAL_SCENE` 与 `HAZARD_TRIGGERS` 共用，
# 避免两处各写一份而漂移。
KW_FIRE_SCENE = re.compile(r"火灾|失火|起火|火警|爆炸|纵火")
KW_ATTACK_SCENE = re.compile(r"持刀|持械|行凶|袭击|砍伤|恐怖|劫持")
KW_GAS_SCENE = re.compile(r"有毒气体|不明气体|气体泄漏|瓦斯|可燃气体|毒气")
POSITION_RULES = (("挡水", KW_KOU, 3, 1), ("召唤外部力量", KW_CALL, 3, 4),
                  ("救治", KW_JIU, 3, 2), ("疏散", KW_SHU, 5, 3))
#                                              (名称, 关键词, 上限, 分配槽位)
# 召唤占第 4 槽（v8.19b 裁定）：挡水/救治/疏散 三类安全动作的槽位语义**不动**；
# `_order_steps` 的前置截断已从 3 放宽到 4（见该函数）。
# ⚠️ **认领顺序**（v8.19c 裁定）：召唤**必须排在救治之前** —— `_demand_slots` 按本表顺序认领，
#    而 KW_JIU（救治）含「救护车|急救」，会命中召唤句「召唤消防、**救护车**到场」并**抢先认领**，
#    致召唤规则落空、真救治步骤丢槽位。槽位号（第 4 元素）不因此改变，只改**谁先认领**。

# B：只有这两类启用合并（探针显示掺水集中在尾部这两类）；
#    人身安全/切断危险源/关键设备/运营调整 不合并——安全动作的粒度必须保留。
MERGE_TYPES = {"信息报告", "恢复善后"}
MERGE_MAX_ABSORB = 1                 # D：每步最多并入 1 条，防止巨步

# 计数规则（防掺水）：合并之后若仍超上限，从尾部丢弃
COUNT_RULES = {"人身安全": 4, "切断危险源": 4, "关键设备": 3,
               "运营调整": 3, "信息报告": 3, "恢复善后": 2}
N_MIN, N_MAX = 12, 15

# 阶段分箱：位置决定阶段；恢复善后是唯一例外（无论位置都归阶段四）
STAGE_BINS = ((1, 3, "先期处置"), (4, 8, "现场处置"),
              (9, 12, "扩大响应"), (13, 10 ** 6, "恢复善后"))

NOTICE_LINES = "、"


def _s(v, default=""):
    """安全取字符串（LLM 可能给 null / 数字 / 列表）。"""
    if v is None:
        return default
    if isinstance(v, list):
        return NOTICE_LINES.join(_s(x) for x in v if _s(x))
    return str(v).strip()


def _n(v, default=10 ** 6):
    """取步骤号的**数值**（排序专用）。

    LLM 可能给 3 / "3" / "步骤3" / None；取首个数字串转 int。
    无数字时给大哨兵 → 排序落到最后（并列哨兵时由稳定排序保持原有相对次序）。

    ⚠️ **禁止**用 `_s(v)` 当排序 key：`_s` 返回字符串，字典序下 `"10" < "2"`，
    会把 10/11/12… 插到 1 后面，打乱所有跨过 10 的方案（本 bug 见 v8.20 笔记）。
    """
    m = re.search(r"\d+", _s(v))
    return int(m.group(0)) if m else default


def _l(v):
    """安全取列表。字符串按常见分隔符切开，容错 LLM 抖动。"""
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in (_s(i) for i in v) if x]
    return [p.strip() for p in re.split(r"[；;、,，/]", _s(v)) if p.strip()]


def _ld(v):
    """安全取 **dict 列表**（如 `tiers` / `secondary_events` / `triggers` / `chains`）。

    ⚠️ **不要用 `_l()` 取 dict 列表**：`_l()` 会把元素**转成字符串**（它面向字符串列表），
    dict 被 `str()` 之后就再也过不了 `isinstance(x, dict)`，整列会**被静默清空**。
    v8.25 曾因此在作战简报里把「次生/衍生事件」「升级触发条件」误渲染成「无」。
    代码库既有约定是 `(x or [])` + `isinstance` 过滤（见 `tiers` / `fallback` 的渲染）。
    """
    return [x for x in (v or []) if isinstance(x, dict)] if isinstance(v, list) else []


def _lvl(v, default=""):
    """级别补"级"字，与 v2.1 的写法对齐（"IV" → "IV级"）。"""
    s = _s(v, default)
    if s and not s.endswith("级") and not s.startswith("信息不足"):
        s += "级"
    return s


# ---- 4.1 响应级别 ↔ 责任主体 绑定（《国家城市轨道交通运营突发事件应急预案》4.1）----
_LVL_AUTHORITY = {"I": "事发地省级人民政府", "II": "事发地省级人民政府",
                  "III": "事发地城市人民政府", "IV": "事发地城市人民政府"}


def _norm_level(v):
    """'IV' / 'IV级' / 'iv' → 'IV'；'信息不足…' 或空 → ''。"""
    s = _s(v).strip()
    if not s or s.startswith("信息不足"):
        return ""
    return s.replace("级", "").strip().upper()


_LVL_RANK = {"I": 1, "II": 2, "III": 3, "IV": 4}     # **数字越小，级别越高**


def _lvl_rank(v):
    """响应级别的高低序：I=1 … IV=4（越小越高）。无法识别 → 0。"""
    return _LVL_RANK.get(_norm_level(v), 0)


# ================= 7.2 四档定级基准表（**代码权威**，v8.26）=================
# 为什么把阈值**写死在代码里**、而不让模型每次重述：
#   约束（一）里已经记着教训 —— 模型曾编出"重大：6–24 小时""较大：2–6 小时"这种
#   **整体错位的阈值**。阈值是**静态事实**，模型每重述一次就多一次漂移机会。
#   所以：**阈值列一律由代码渲染**，模型只负责填"本事件该指标的当前数值"。
#
# 口径（按需求方确认）：`X人以上Y人以下` = **含 X、不含 Y**。
#   → "3人以上10人以下" = 3~9 人（= 旧写法 "3–9 人"），"10人以上30人以下" = 10~29 人。
# `特别重大` 档 **7.2 无"连续中断行车"条目** —— 中断再长也不单独构成特别重大。
GRADE_ORDER = ("特别重大", "重大", "较大", "一般")
GRADE_METRICS = ("死亡人数", "重伤人数", "直接经济损失", "连续中断行车")
_GRADE_TABLE = {
    "死亡人数": {"特别重大": "≥30 人", "重大": "10人以上30人以下",
               "较大": "3人以上10人以下", "一般": "3人以下"},
    "重伤人数": {"特别重大": "≥100 人", "重大": "50人以上100人以下",
               "较大": "10人以上50人以下", "一般": "10人以下"},
    "直接经济损失": {"特别重大": "≥1 亿元", "重大": "5000万元以上1亿元以下",
                "较大": "1000万元以上5000万元以下", "一般": "50万元以上1000万元以下"},
    "连续中断行车": {"特别重大": "—（7.2 无此条）", "重大": "24小时以上",
                "较大": "6小时以上24小时以下", "一般": "2小时以上6小时以下"},
}
# 值位若写成这些，等同于"未提供"（模型抖动兜底）
_NO_VALUE = ("", "无", "未提供", "未给出", "未识别", "未知", "none", "null", "-", "—", "n/a")


def _metric_rows(sev):
    """取 `severity.metrics` 并补齐四项，返回 [{name, value, level}]（顺序固定）。

    模型漏填整块 / 漏填某一行 → 该行按「未提供 / 待核实」渲染，**不省略**。
    """
    given = {}
    for m in _ld(sev.get("metrics")):
        nm = _s(m.get("name"))
        if nm in GRADE_METRICS:
            given[nm] = m
    rows = []
    for nm in GRADE_METRICS:
        m = given.get(nm) or {}
        val = _s(m.get("value"))
        if val.strip().lower() in _NO_VALUE:
            val = "未提供"
        lv = _s(m.get("level"))
        if val == "未提供" or lv not in GRADE_ORDER:
            lv = "待核实"
        rows.append({"name": nm, "value": val, "level": lv})
    return rows


# ---- 事故等级 ↔ 响应级别：**1:1 硬映射**（业务硬规则，v8.26）----
# 依据：事故等级与响应级别的对应关系 ——
#   特别重大 → **Ⅰ级**；重大 → **Ⅱ级**；较大 → **Ⅲ级**；一般 → **Ⅳ级**。
# 与 `_LVL_AUTHORITY`（4.1）配合：**Ⅰ/Ⅱ → 事发地省级人民政府；Ⅲ/Ⅳ → 事发地城市人民政府**。
# ★ 为什么硬编码而不是让模型填：**响应级别决定"谁负责"**（省级还是市级），
#   属责任划分，不能由模型自由裁量。实测模型填出过与事故等级不一致的级别。
#   不一致时**以本映射为准**并告警（见 `_render_markdown`）。
GRADE_TO_RESPONSE = {"特别重大": "I", "重大": "II", "较大": "III", "一般": "IV"}


def _norm_grade(v):
    """'较大事故' / '较大' / 'Ⅲ级（较大）' → '较大'；取不到 → ''。

    ⚠️ 按 `GRADE_ORDER` **顺序**匹配 —— `特别重大` 含子串 `重大`，
    必须先匹配更长的那个，否则"特别重大"会被误判成"重大"。
    """
    s = _s(v)
    for g in GRADE_ORDER:
        if g in s:
            return g
    return ""


def _grade_of(sev):
    """取**当前生效的事故等级**：精确判定成立则用它，否则用**保守初判**。取不到 → ""。"""
    precise = _s(sev.get("level"))
    on_miss = (not precise) or precise == "尚未成立" or precise.startswith("信息不足")
    if not on_miss:
        return _norm_grade(precise)
    pre = sev.get("preliminary") if isinstance(sev.get("preliminary"), dict) else {}
    return _norm_grade(_s(pre.get("level")))


def _render_grade_table(sev):
    """定级依据对照表（按**指标**转置；阈值列由代码填）。"""
    rows = _metric_rows(sev)
    T = ["| 指标 | 当前数值 | 国家标准阈值（特别重大 / 重大 / 较大 / 一般） | 对应等级 |",
         "|---|---|---|---|"]
    for r in rows:
        th = " / ".join(_GRADE_TABLE[r["name"]][g] for g in GRADE_ORDER)
        lv = "**待核实**" if r["level"] == "待核实" else r["level"]
        T.append("| %s | %s | %s | %s |" % (r["name"], r["value"], th, lv))
    return T


def _authority_matches(authority, expected):
    """宽松匹配变体：只看「省/市 + 人民政府」这层语义，容忍措辞差异。"""
    a = _s(authority)
    if not a:
        return False
    if "省级" in expected:
        return "省" in a and "人民政府" in a
    if "城市" in expected:
        return "市" in a and "人民政府" in a
    return True


def _norm_role(r):
    """角色归一化：去括号注释与空白。'值班站长（视察评估）' → '值班站长'。"""
    return re.sub(r"[（(][^）)]*[）)]", "", _s(r)).strip()


def _role_set(step):
    return {x for x in (_norm_role(r) for r in _l(step.get("role"))) if x}


# ---- 岗位四大类（v8.22）：供第 2 层（工作流）按类分派 ----
ROLE_CATEGORIES = ("一线执行", "调度指挥", "车站管理", "后勤安保")
_ROLE_CAT_KW = (
    # 顺序即优先级：先匹配到的类别胜（并列岗位跨类时取"更靠前"的一类）
    ("后勤安保", r"公安|消防|医疗|医护|急救人员|救护|维修|维护人员|工程|技术员|防暴|安保|武警"),
    ("调度指挥", r"行车调度|系统调度|值班调度|调度员|OCC|控制中心"),
    ("车站管理", r"值班站长|值班经理|站长|经理|事故处理主任|主管|主任"),
    ("一线执行", r"列车?司[机机员]|驾驶员|站务员|车站员工|员工|站台?人员|售票|安检|保洁"),
)


def _cat_of_role(name):
    """按**单个角色名**关键词判类别（供「按岗位执行视图」的表头用）；取不到 → ""。"""
    blob = _s(name)
    for cat, pat in _ROLE_CAT_KW:
        if re.search(pat, blob):
            return cat
    return ""


# ---- 专业职能组四类（v8.25）：**作战简报层**的总方向分组 ----
# 与上面的 `ROLE_CATEGORIES` **不是一个维度**，别混用：
#   ROLE_CATEGORIES = "这活归谁干"（人事归属），用于按岗位执行视图（详案层）；
#   COMMAND_GROUPS  = "这股力量往哪使劲"（职能方向），用于作战简报（宏观层）。
# 四类名固定（模型只能从这四选），便于下游按组聚合。
COMMAND_GROUPS = ("综合协调与指挥调度", "现场抢险与风险控制",
                  "乘客疏散与医疗救护", "信息发布与运营调整")
_COMMAND_ICON = {"综合协调与指挥调度": "🛡️", "现场抢险与风险控制": "🚧",
                 "乘客疏散与医疗救护": "🧑‍🤝‍🧑", "信息发布与运营调整": "📡"}
# 代码兜底：模型没给 `groups` 时，按 **action_type / role_category** 把步骤归进四组。
# 理由与 `_role_category` 同：渲染不能因模型漏填而空缺。
_GROUP_BY_ACTION = {
    "人身安全": "乘客疏散与医疗救护",
    "切断危险源": "现场抢险与风险控制",
    "关键设备": "现场抢险与风险控制",
    "运营调整": "信息发布与运营调整",
    "信息报告": "信息发布与运营调整",
    "恢复善后": "信息发布与运营调整",
}
_GROUP_BY_ROLE_CAT = {"调度指挥": "综合协调与指挥调度", "车站管理": "综合协调与指挥调度",
                      "后勤安保": "现场抢险与风险控制", "一线执行": "乘客疏散与医疗救护"}


def _llm_groups(ev):
    """模型给的 `event.command.groups`（已归一化，只认四类名）。取不到 → []。"""
    cmd = ev.get("command") if isinstance(ev.get("command"), dict) else {}
    out = []
    for g in _ld(cmd.get("groups")):
        if not isinstance(g, dict):
            continue
        name = _s(g.get("group"))
        if name not in COMMAND_GROUPS:
            continue        # 类别名必须从四类里选，自创的一律丢弃（与 role_category 同款约束）
        out.append({"group": name,
                    "direction": _s(g.get("direction")),
                    "strategy": _s(g.get("strategy"))})
    return out


def _derive_groups(seq):
    """**代码兜底**：模型漏填 `groups` 时，按 action_type / role_category 把步骤归进四组。

    只做机械聚合，**不编造策略**——生成的方向文字会显式标注「由代码兜底」，
    避免读者把兜底文字误当成模型研判。
    """
    buckets = {g: [] for g in COMMAND_GROUPS}
    for s in seq:
        g = _GROUP_BY_ACTION.get(_s(s.get("action_type")))
        if g is None:
            g = _GROUP_BY_ROLE_CAT.get(_role_category(s))
        if g:
            buckets[g].append(s)
    out = []
    for g in COMMAND_GROUPS:
        rows = buckets[g]
        if not rows:
            continue
        acts = [_first_sentence(x.get("action"))[:40] for x in rows[:3]]
        out.append({"group": g, "direction": "", "strategy": "",
                    "derived": True, "n": len(rows), "acts": acts})
    return out


def _chains_of(comp):
    """耦合风险链推演（`composite.chains`）；容错读取，取不到 → []。"""
    out = []
    for c in _ld(comp.get("chains")):
        if not isinstance(c, dict):
            continue
        frm = [x for x in _l(c.get("from")) if _s(x)]
        to = _s(c.get("to"))
        if frm and to:
            out.append({"from": frm, "to": to, "why": _s(c.get("why"))})
    return out


def _conflicts_of(comp):
    """处置冲突与协同策略（`composite.conflicts`）；容错读取，取不到 → []。"""
    out = []
    for c in _ld(comp.get("conflicts")):
        if not isinstance(c, dict):
            continue
        k, v = _s(c.get("conflict")), _s(c.get("strategy"))
        if k:
            out.append({"conflict": k, "strategy": v})
    return out


def _role_category(step):
    """该步的岗位大类：**LLM 填的 `role_category` 优先**（须为四类之一），否则按 `role` 关键词兜底。

    兜底是**防御性**的 —— 渲染与分派不能因模型漏填/填错而空缺；两类都取不到 → 返回 ""。
    """
    v = _s(step.get("role_category"))
    if v in ROLE_CATEGORIES:
        return v
    blob = " ".join(_role_set(step)) or _s(step.get("role"))
    return _cat_of_role(blob)


def _how_to(step):
    """该步的「做法要点」原文（2–4 个动作点）；缺失 → 返回 ""。"""
    return _s(step.get("how_to"))


# ---- v8.24：前置条件 / 所需资源 ----
# 与 depends_on **不是一回事**，两者并存、互不替代：
#   depends_on  → **步骤引用**（硬先后），渲染成「前置：需先完成 步骤N」；
#   本字段      → **执行前提的文字描述**（如"牵引电流已隔离"），渲染成「前置条件：…」。
# 后者是下游"个人 Agent"判断"这一步轮不轮到我做"的依据，不能用步骤号代替。
def _precondition(step):
    """该步的「前置条件」原文（文字条件）；缺失 → 返回 ""。"""
    return _s(step.get("precondition"))


def _resources(step):
    """该步的「所需资源」原文（物资 / 设备 / 人力）；缺失 → 返回 ""。"""
    return _s(step.get("resources"))


# ---- 前置门：信息不足时**拒绝生成方案** ----
# 理由：无法识别事件时若照常生成步骤，模型只能"万能模板 + 硬套兜底拉到的规程"
# （实测：输入「某地铁站出事了，你处理一下。」→ 11 步方案，依据 11/11 来自
#   AIEP28 28C「处理车站水淹」）。**那种方案被照着执行，比不输出更危险。**
_BLIND = ("", "未识别", "未知", "无", "none", "unknown", "null")
_REQUIRED_INFO = (
    "1. 事件性质（火灾 / 爆炸 / 脱轨 / 撞击 / 拥挤踩踏 / 袭击 / 设备故障 …）",
    "2. 发生位置（车站 / 站台 / 区间 / 隧道 / 出入口 / 车辆段 …）",
    "3. 已知伤亡或险情（有人受伤 / 被困 / 冒烟 / 起火 / 有异常气味 …）",
    "4. 当前状态（是否可控 / 是否需要外部力量 / 是否已影响行车）",
)


def _insufficient_info(event_profile):
    """上游是否根本没识别出事件。返回 `(是否拦截, 原因)`。"""
    if not isinstance(event_profile, dict):
        return True, "无事件画像"
    types = [_s(t).lower() for t in _get_event_types(event_profile)]
    no_type = (not types) or all(t in _BLIND for t in types)
    lvl, _ = _get_severity(event_profile)
    no_sev = _s(lvl).lower() in _BLIND
    if no_type and no_sev:
        return True, "事件类型与事故等级**均未识别**（描述里没有任何可判别的信号）"
    if no_type:
        return True, "**事件类型未识别**"
    if no_sev:
        return True, "**事故等级未识别**"
    return False, ""


def _insufficient_plan(reason):
    """信息不足时输出的替代文本——**只有定性说明与补充指引，没有任何处置步骤**。"""
    return ("## 一、事件定性\n\n"
            "- **状态**：**信息不足，无法生成处置方案**\n"
            "- **原因**：%s\n"
            "- **请补充以下信息后重试**：\n" % reason
            + "\n".join("  " + x for x in _REQUIRED_INFO) + "\n\n"
            "---\n\n"
            "## 二、处置步骤\n\n"
            "- **不适用**（信息不足，待补充后重新生成）\n\n"
            "---\n\n"
            "> 说明：本系统**不会**在事件无法识别时硬套规程——"
            "那种\"看着完整、依据却来自无关规章\"的方案，**被照着执行比不输出更危险**。\n")


def _tier(step, scene=None):
    return _effective_tier(step.get("action_type"), scene)


def _deadline(v):
    """deadline_minutes 取整数，缺失给每类默认值（仅展示用）。"""
    m = re.search(r"\d+", _s(v))
    if m:
        return int(m.group(0))
    return {"人身安全": 3, "切断危险源": 5, "关键设备": 10,
            "运营调整": 20, "信息报告": 3, "恢复善后": 60}.get(_s(v), 30)


def _first_sentence(action):
    """动作的首句（第一个「；」之前）。占位匹配只看首句，防止命中合并进来的后半句。"""
    return _s(action).split("；")[0]


def _demand_slots(steps, flags, log, scene=None):
    """A：在**合并之前**的原始 steps 上定槽位；只认「首句即该动作」的步骤。

    若某规则找不到首句命中的步骤，就**不占位**（如实告警），不拿含关键词的
    复合步骤去凑——那是 LLM 把两个动作写进同一句造成的，属 prompt 层问题。
    """
    t1 = [s for s in steps if _tier(s, scene) == 1]
    claimed, out = set(), []
    for name, pat, bound, slot in POSITION_RULES:
        if not flags.get(name):
            continue
        cands = [x for x in t1 if id(x) not in claimed]
        s = next((x for x in cands if pat.search(_first_sentence(x.get("action")))), None)
        if s is None:
            near = next((x for x in cands if pat.search(_s(x.get("action")))), None)
            if near is not None:
                log("[rule] WARNING %s 没有「首句即%s动作」的第 1 档步骤 → 不占位"
                    "（最近一步首句=「%s」，关键词在其后续分句，不拿它凑）"
                    % (name, name, _first_sentence(near.get("action"))[:34]))
            else:
                log("[rule] WARNING %s 全文无 %s 动作的第 1 档步骤 → 不占位"
                    % (name, name))
            continue
        claimed.add(id(s))
        out.append((slot, name, s, bound))
    return out


# ================= 合并（防掺水）=================

def _merge_steps(steps, reserved, log, scene=None):
    """B+D+E：只合并 信息报告/恢复善后；同 tier；每步最多并入 1 条；占位步骤不参与。"""
    out = []
    for s in sorted(steps, key=lambda x: _n(x.get("n"))):
        if id(s) in reserved or _s(s.get("action_type")) not in MERGE_TYPES:
            out.append(s)
            continue
        host = None
        for h in out:
            if id(h) in reserved or h.get("_absorbed"):
                continue                                     # 占位 / 已并入过（D）
            if _s(h.get("action_type")) != _s(s.get("action_type")):
                continue
            if _tier(h, scene) != _tier(s, scene):
                continue                                     # E
            shared = _role_set(h) & _role_set(s)
            if not shared:
                continue
            union = _role_set(h) | _role_set(s)
            if len(union) > 3:
                log("[merge-skip] 步骤%s 与 步骤%s 共享角色=%s，但并集 %d>3 → 不合并"
                    % (h.get("n"), s.get("n"), "/".join(sorted(shared)), len(union)))
                continue
            host = h
            break
        if host is None:
            out.append(s)
            continue
        # ---- 附属字段归属（v3 §1）----
        host["action"] = _s(host.get("action")) + "；" + _s(s.get("action"))
        host["role"] = sorted(_role_set(host) | _role_set(s))
        seen, basis = set(), []
        for b in _l(host.get("basis")) + _l(s.get("basis")):
            if b not in seen:
                seen.add(b)
                basis.append(b)
        host["basis"] = "；".join(basis)
        host["deadline_minutes"] = min(_deadline(host.get("deadline_minutes")),
                                       _deadline(s.get("deadline_minutes")))
        host["parallel_with"] = list(dict.fromkeys(
            _l(host.get("parallel_with")) + _l(s.get("parallel_with"))))
        fbs, fseen = [], set()
        for fb in list(host.get("fallback") or []) + list(s.get("fallback") or []):
            if isinstance(fb, dict):
                c = _s(fb.get("condition"))
                if c not in fseen:
                    fseen.add(c)
                    fbs.append(fb)
        host["fallback"] = fbs
        host["case_ref"] = host.get("case_ref") or s.get("case_ref")
        host["secondary_of"] = host.get("secondary_of") or s.get("secondary_of")
        host["_absorbed"] = True
        log('[merge] type=%s host=步骤%s 首句="%s" 并入=["%s"] role并集=%s case_ref=%s fallback=%d'
            % (_s(host.get("action_type")), host.get("n"),
               _first_sentence(host.get("action"))[:24],
               _first_sentence(s.get("action"))[:24], host["role"],
               (_s((host.get("case_ref") or {}).get("id")) or "null"), len(fbs)))
    return out


def _cap_steps(steps, reserved, log):
    """分类上限只在**总量超标**时启用；占位步骤（挡水/救治/疏散）永不被丢。不足 N_MIN 不补齐。

    合并后总量 ≤ N_MAX 时不做分类 cap：分类 cap 的目的是**防掺水**，
    不是把已达标的方案强砍到 N_MIN 以下。
    """
    if len(steps) > N_MAX:
        kept = []
        for t in {_s(s.get("action_type")) for s in steps}:
            group = [s for s in steps if _s(s.get("action_type")) == t]
            group.sort(key=lambda s: (id(s) not in reserved, _n(s.get("n"))))   # 占位优先保留
            cap = COUNT_RULES.get(t, 99)
            if len(group) > cap:
                log("[count] type=%s 有 %d 步 > 上限 %d，从尾部丢弃：%s"
                    % (t, len(group), cap, [_first_sentence(x.get("action"))[:16]
                                            for x in group[cap:]]))
                group = group[:cap]
            kept += group
        steps = kept
    steps = sorted(steps, key=lambda s: _n(s.get("n")))
    if len(steps) > N_MAX:
        drop = [s for s in steps if id(s) not in reserved]
        drop = drop[-(len(steps) - N_MAX):] if len(steps) - N_MAX < len(drop) else drop
        drop_ids = {id(s) for s in drop}
        log("[count] 合计 %d 步 > N_MAX=%d，丢弃尾部：%s"
            % (len(steps), N_MAX, [_first_sentence(x.get("action"))[:16] for x in drop]))
        steps = [s for s in steps if id(s) not in drop_ids]
    if len(steps) < N_MIN:
        log("[count] WARNING 仅 %d 步 < N_MIN=%d，不补齐（不编造）" % (len(steps), N_MIN))
    return steps


# ================= 排序（方案 D：第 1 档批量分配）=================

# ---- 是否需要外部力量（消防/公安/救护）——「召唤外部力量」位置规则的启用条件 ----
_EXTERNAL_SCENE = re.compile("|".join(
    p.pattern for p in (KW_FIRE_SCENE, KW_ATTACK_SCENE, KW_GAS_SCENE)))
_EXTERNAL_ABSENT = re.compile(
    r"(?:消防|公安|救护|急救|外部力量|支援力量)[^，。；]{0,6}(?:未|尚未)(?:到场|到达|抵达)"
    r"|需要.{0,4}(?:外部力量|支援)|请求.{0,4}支援")


def _external_need(event_profile):
    """是否需要**外部力量**：决定「召唤外部力量」位置规则是否启用。

    只看**事件画像**（类型 / key_facts / 位置），**不看方案步骤** —— 否则模型自己写了
    "召唤消防"就把 flag 置真，变成自证（同 `_check_hazard` 的理由）。
    """
    blob = _hazard_blob(event_profile)
    # ① 场景本身需要外部力量（触发词与 HAZARD_TRIGGERS 同源）
    if _EXTERNAL_SCENE.search(blob):
        return True
    # ② 描述里明确外部力量"未到场 / 需支援"
    return bool(_EXTERNAL_ABSENT.search(blob))


def _flags(event_profile, steps):
    """规则前置条件：取自事件画像 + 步骤正文（防非防汛场景误触发）。"""
    blob = _s(event_profile) + " " + " ".join(_s(s.get("action")) for s in steps)
    return {
        # "积水" 收窄（v8.19c）：裸词会命中恢复善后的「检查现场…积水…」→ 假阳性。
        "挡水": bool(KW_KOU.search(blob)) or bool(re.search(
            r"水淹|内涝|水浸|积水.{0,4}(?:倒灌|漫|深|进入|上涨|严重|涌)", blob)),
        "救治": bool(KW_JIU.search(blob)) or bool(re.search(r"受伤|伤亡|重伤|死亡|摔倒", blob)),
        "疏散": bool(KW_SHU.search(blob)) or "疏散" in blob,
        "召唤外部力量": _external_need(event_profile),
    }


def _order_steps(steps, demanded, log, scene=None):
    """挡水/救治/疏散 批量占位 1/2/3；其余第 1 档按 n；tier≥2 按 (tier, n)。"""
    if len(demanded) > 4:
        log("[rule-conflict] 第 1 档有 %d 步声称要进前 4，按 挡水>救治>疏散>召唤 取前 4；被挤后：%s"
            % (len(demanded), [_first_sentence(x[2].get("action"))[:16]
                               for x in sorted(demanded)[4:]]))
        demanded = sorted(demanded)[:4]
    t1 = [s for s in steps if _tier(s, scene) == 1]
    front = [s for _, _, s, _ in sorted(demanded, key=lambda x: x[0])]
    front_ids = {id(s) for s in front}
    rest1 = sorted([s for s in t1 if id(s) not in front_ids], key=lambda s: _n(s.get("n")))
    rest = sorted([s for s in steps if _tier(s, scene) > 1],
                  key=lambda s: (_tier(s, scene), _n(s.get("n"))))
    seq = front + rest1 + rest
    for slot, name, s, bound in sorted(demanded, key=lambda x: x[0]):
        log("[rule] %s → 槽位%d（上限 %d）首句=%s" % (name, slot, bound,
                                              _first_sentence(s.get("action"))[:26]))
    return seq


# ---- HARD_ORDER_RULES：**不依赖 LLM 声明**的代码层硬先后兜底 ----
# v8.2 只做了「隔离电流→进轨道」一条；v8.11 扩成 4 条表，由同一引擎执行。
# ⚠️ 词表命中式的**覆盖不稳**（措辞一变就漏）——所以它是**兜底层**，不是一线机制；
#    一线机制是 prompt（十四）+ `depends_on`（通用，但取决于 LLM 是否声明）。
KW_TRACTION_ISO = re.compile(
    r"隔离.{0,6}牵引电流|关断.{0,6}牵引电流|切断.{0,6}牵引电流"
    r"|轨道馈电断路器.{0,6}(?:打开|断开)|牵引电流.{0,4}隔离")
KW_ENTER_TRACK = re.compile(
    r"进入.{0,4}(?:区间|轨道|隧道)|前往.{0,4}(?:区间|轨道|隧道)"
    r"|派人.{0,4}(?:到|往).{0,4}区间|上轨道|巡查轨道|沿途查看轨道|区间巡查|轨道巡查")
KW_HALT = re.compile(
    r"紧急停车|停车按钮|阻止列车\S{0,6}移动|保持列车静止|采取紧急制动|扣停|停车待命")
KW_EVAC = re.compile(
    r"宣布疏散|疏散车站|疏散乘客|疏散站台|疏散撤离|疏散.{0,8}引导|组织.{0,6}疏散"
    r"|引导.{0,18}疏散|引导.{0,18}撤离|撤离车站")
KW_BROADCAST = re.compile(r"(?:车站|列车)广播|PA|扬声器|乘客信息系统|PIS")
KW_HEADCOUNT = re.compile(
    r"清点|核对\S{0,4}人数|确认\S{0,8}已撤离|查看是否\S{0,8}撤离|确认\S{0,6}无人"
    r"|集合地点报到|集合点报到")

HARD_ORDER_RULES = (
    # (规则名, 必须更早的 A, 必须更晚的 B)
    ("停车→疏散", KW_HALT, KW_EVAC),
    ("隔离电流→进轨道", KW_TRACTION_ISO, KW_ENTER_TRACK),
    ("广播→疏散", KW_BROADCAST, KW_EVAC),
    ("疏散→清点", KW_EVAC, KW_HEADCOUNT),
    # v8.19b：先召唤外部力量，再疏散/清人。
    # ⚠️ 与位置规则（召唤=槽4，排在疏散=槽3 之后）方向**相反** → 同时命中时本条会
    #    把召唤换到疏散之前（硬顺序 > 软槽位，见 `_enforce_hard_order` 的裁定）。
    ("召唤外部力量→疏散", KW_CALL, KW_EVAC),
)


# ---- 危险源处理检查（v8.17）：**只告警，不上硬顺序** ----
# 先观察 prompt（十五）约束下 LLM 能否自主补出"处理危险源"的步骤；补不出再考虑硬约束。
KW_FIRE = re.compile(r"灭火|扑救|消防喷淋|消防设施|使用灭火器")
KW_ATTACK = re.compile(r"控制.{0,4}行凶|隔离.{0,4}行凶|封锁.{0,4}行凶|制止.{0,4}袭击|反恐响应")
KW_GAS = re.compile(r"隔离.{0,4}气体源|关闭.{0,4}阀门|切断.{0,4}气源")

HAZARD_TRIGGERS = (
    # (场景名, 触发词——只看**事件画像**, 必须命中的动作词, 该做的动作)
    ("火灾/爆炸", KW_FIRE_SCENE, KW_FIRE, "灭火 / 扑救"),
    ("持械袭击", KW_ATTACK_SCENE, KW_ATTACK, "控制 / 隔离行凶者"),
    ("有毒气体", KW_GAS_SCENE, KW_GAS, "隔离气体源 / 关阀门"),
)


def _hazard_blob(event_profile):
    """危险源判据的**公共取词**：只用事件描述类字段（类型 / 次生 / key_facts / 位置）。

    **不看方案步骤**（会自我掩蔽）、**不看 `scene_key`**（是归类结果，实测「不明气体泄漏」
    会被归类成 `站内失火` 而误触发火灾判据）。`_check_hazard` / `_external_need` / 火灾补入共用。
    """
    if not isinstance(event_profile, dict):
        return ""
    parts = [_s(t) for t in _get_event_types(event_profile)]
    for se in (event_profile.get("secondary_events") or []):
        if isinstance(se, dict):
            parts.append(_s(se.get("event_type")))
    parts += [_s(x) for x in (event_profile.get("key_facts") or [])]
    parts.append(_s(event_profile.get("location")))
    return " ".join(p for p in parts if p)


def _check_hazard(event_profile, seq, log):
    """事件涉持续危险源时，检查方案里**有没有步骤处理危险源本身**。

    ⚠️ **告警位**：本函数在 `_inject_hazard_step` **之后**调用（见 `_render_markdown`），
    故火灾/气体被补入后会报 ✅ —— 读作「**修复后**方案已包含」；补入动作本身见 `[inject]` 行。
    """
    if not isinstance(event_profile, dict):
        return
    blob = _hazard_blob(event_profile)
    for name, trig, pat, what in HAZARD_TRIGGERS:
        if not trig.search(blob):
            continue
        # 报**位置**而非 s["n"]：此时还没重编号（补入步骤的 n 还是占位值），
        # 而 seq 的顺序就是最终渲染顺序，位置 == 渲染后的步骤号。
        hit = [i + 1 for i, s in enumerate(seq) if pat.search(_s(s.get("action")))]
        if hit:
            log("[hazard] %s场景：✅ 已安排「%s」——步骤 %s"
                % (name, what, "、".join(str(x) for x in hit[:4])))
        else:
            log("[hazard] WARNING **%s场景未安排「%s」的动作**——方案可能只处理了后果"
                "（疏散 / 救治 / 报告 / 排烟），没处理危险源本身" % (name, what))


def _fire_role(event_profile):
    """火灾补入步骤的岗位：区间/列车/车厢 → 列车驾驶员；站内 → 站务员。"""
    b = _hazard_blob(event_profile)
    if re.search(r"列车|车厢|受电弓|车载|驾驶室", b):
        return ["列车驾驶员", "车站员工"]
    return ["站务员", "车站员工"]


def _inject_hazard_step(seq, event_profile, front_n, log):
    """方案缺**危险源处置**动作时，补入一条**安全底线动作**。

    - **气体泄漏**（v8.18）：缺则补（触发=场景键含"气体泄漏"；本轮**未改动**）。
    - **火灾/爆炸**（v8.19b）：缺则补 —— 三份火灾用例证明 LLM 补出灭火是**概率行为**
      （案例1 步骤1有 / 案例3 无 / 案例5 步骤13太靠后），不能只靠 prompt（十五）。

    **依据明标为「系统补入」**：本系统原则是"不编造"，但"危险源不除、后果会持续产生"
    不能只告警了事；这条是**预定义的安全底线**，不冒充"来自本次检索到的条款"。

    插入位置：紧跟占位槽位之后（`front_n`），保证落得尽量靠前，**又不会挤掉既有槽位**。
    """
    if not isinstance(event_profile, dict):
        return seq
    raw = event_profile.get("scene_key")
    raw = [raw] if isinstance(raw, str) else (raw or [])

    # ---- 气体泄漏（v8.18）：触发条件与动作**逐字未改** ----
    if any("气体泄漏" in _s(k) for k in raw):
        if any(KW_GAS.search(_s(s.get("action"))) for s in seq):
            log("[hazard] 气体泄漏：方案**已含**处理气体源的步骤 → 不补入")
            return seq
        step = {"n": 9999,
                "action": "值班站长安排车站员工在确认安全的前提下关闭相关区域通风系统、"
                          "切断可能的气源（关闭相关阀门），并在安全位置持续监测气体浓度",
                "action_type": "切断危险源", "role": ["值班站长", "车站员工"],
                "basis": "（系统补入：危险源处置安全底线动作，非本次检索到的规程条款）",
                "deadline_text": "目标 5 分钟内完成",
                "parallel_with": [], "depends_on": []}
        pos = min(max(int(front_n or 0), 0), 3, len(seq))
        seq.insert(pos, step)
        log("[hazard] 气体泄漏：方案**缺处理气体源的动作** → 已于第 %d 位补入安全底线步骤" % (pos + 1))
        if len(seq) > N_MAX:                       # 注入在 _cap_steps **之后**，故可超 N_MAX 1 步
            log("[inject] 因注入安全底线步骤，步数 N=%d > N_MAX=%d，保留（安全动作优先）"
                % (len(seq), N_MAX))
        return seq

    # ---- 火灾/爆炸（v8.19b）----
    # 排除气体场景：气体泄漏即便被 event_understand 归类成"站内失火"，也不补**火灾**步骤。
    blob = _hazard_blob(event_profile)
    if KW_FIRE_SCENE.search(blob) and not KW_GAS_SCENE.search(blob):
        if any(KW_FIRE.search(_s(s.get("action"))) for s in seq):
            log("[hazard] 火灾/爆炸：方案**已含**灭火/扑救动作 → 不补入")
            return seq
        role = _fire_role(event_profile)
        log("[hazard] WARNING 火灾/爆炸场景：**原方案未安排「灭火 / 扑救」动作**"
            "（将补入安全底线步骤）")
        step = {"n": 9999,
                "action": "%s在确保自身安全的前提下，使用就近灭火器或消防设施对起火部位"
                          "进行扑救，火势超出可控范围时立即撤离" % role[0],
                "action_type": "切断危险源", "role": role,
                "basis": "（系统补入：危险源处置安全底线动作，非本次检索到的规程条款）",
                "deadline_text": "目标 3 分钟内完成",
                "parallel_with": [], "depends_on": []}
        pos = min(max(int(front_n or 0), 0), 3, len(seq))
        seq.insert(pos, step)
        log("[inject] 火灾/爆炸：方案**缺灭火动作** → 已于第 %d 位补入安全底线步骤" % (pos + 1))
        if len(seq) > N_MAX:                       # 注入在 _cap_steps **之后**，故可超 N_MAX 1 步
            log("[inject] 因注入安全底线步骤，步数 N=%d > N_MAX=%d，保留（安全动作优先）"
                % (len(seq), N_MAX))
    return seq


def _enforce_hard_order(seq, log):
    """每条 `HARD_ORDER_RULES` 要求「最早的 A」排在「最早的 B」之前。

    违反则**只交换这一对**；多条规则会互相牵动 → **迭代到不动点（上限 4 轮）**。
    一律跳过并如实记日志的坏情况：
      - A 或 B 缺失 → 该规则对本方案不适用；
      - 同一步同时命中 A、B → **不交换**（自交换=空操作），只核 action 内子串先后。
    """
    hit, exhausted = [], False
    for _pass in range(4):
        changed = False
        for name, pat_a, pat_b in HARD_ORDER_RULES:
            a = next((i for i, s in enumerate(seq)
                      if pat_a.search(_s(s.get("action")))), None)
            b = next((i for i, s in enumerate(seq)
                      if pat_b.search(_first_sentence(s.get("action")))), None)
            if a is None or b is None or a < b:
                continue
            if a == b:
                act = _s(seq[a].get("action"))
                ma, mb = pat_a.search(act), pat_b.search(_first_sentence(act))
                if ma and mb and ma.start() < mb.start():
                    log("[safety] %s：步骤%d 内 A、B 同步且顺序正确 → 无需调整" % (name, a + 1))
                else:
                    log("[safety] WARNING %s：步骤%d 的 action 内 A@%s 与 B@%s 顺序存疑，请人工复核"
                        % (name, a + 1, ma.start() if ma else "-", mb.start() if mb else "-"))
                continue
            # 注意：这里的「步骤N」是**交换前的位置**，与最终渲染编号未必一致 ——
            # 因此带上动作片段，便于事后核对到底是哪两步被换。
            log("[safety] %s：步骤%d「%s」(A) 与 步骤%d「%s」(B) 顺序违规 → 已交换"
                % (name, a + 1, _s(seq[a].get("action"))[:18],
                   b + 1, _s(seq[b].get("action"))[:18]))
            seq[a], seq[b] = seq[b], seq[a]
            hit.append(name)
            changed = True
        if not changed:
            break
        exhausted = _pass == 3
    if exhausted:
        log("[safety] WARNING %d 条硬顺序规则在 4 轮内未收敛，请人工复核"
            % len(HARD_ORDER_RULES))
    log("[safety] 硬顺序规则 %d 条：本次命中 %s" % (len(HARD_ORDER_RULES), hit or "无（未误触发）"))
    return seq


def _apply_depends(seq, log):
    """按 `depends_on` 做**受约束拓扑排序**：依赖=硬约束，传入的 tier 顺序=软偏好。

    做法：以传入顺序 `seq` 的位次为 rank，Kahn 算法每次取"依赖已满足、rank 最小"的一步。
    - **无依赖声明时 → 原顺序逐位不变**（零回归）；
    - 有依赖时 → 被依赖者只能**往后挪**、不会往前，即"最小必要位移"；
    - 环 / 悬空 / 自引用 → 记日志并**丢弃该条依赖**（不让坏边把排序拖死）。
    """
    n_of = {}
    for i, s in enumerate(seq, 1):
        m = re.search(r"\d+", _s(s.get("n")))
        n_of.setdefault(int(m.group(0)) if m else i, s)
    rank = {id(s): i for i, s in enumerate(seq)}
    deps, dangling, cyclic_hint = {}, 0, []
    for s in seq:
        need = set()
        for x in _l(s.get("depends_on")):
            m = re.search(r"\d+", _s(x))
            if not m:
                continue
            t = n_of.get(int(m.group(0)))
            if t is None:
                dangling += 1
                log("[dep] 步骤%s 的 depends_on=%s **查无此步（悬空）** → 丢弃该依赖"
                    % (_s(s.get("n")), m.group(0)))
                continue
            if id(t) == id(s):
                log("[dep] 步骤%s **依赖自身** → 丢弃" % _s(s.get("n")))
                continue
            need.add(id(t))
        deps[id(s)] = need
    if dangling == 0 and not any(deps.values()):
        return seq                                   # 无任何有效依赖 → 原样返回（零回归）

    out, done, remaining = [], set(), list(seq)
    while remaining:
        ready = [s for s in remaining if deps[id(s)] <= done]
        if not ready:
            cyc = [_s(s.get("n")) for s in remaining]
            log("[dep] 检测到**循环依赖**（涉及步骤 %s）→ 环内保持原顺序，不再调整" % cyc)
            cyclic_hint += cyc
            out.extend(sorted(remaining, key=lambda s: rank[id(s)]))
            break
        ready.sort(key=lambda s: rank[id(s)])
        pick = ready[0]
        remaining.remove(pick)
        done.add(id(pick))
        out.append(pick)

    moved = [(rank[id(s)] + 1, i + 1, _s(s.get("n"))) for i, s in enumerate(out)
             if rank[id(s)] != i]
    if moved:
        log("[dep] 依赖导致顺序调整（旧位次→新位次）：%s"
            % "，".join("步骤%s：%d→%d" % (n, a, b) for a, b, n in moved[:8]))
    return out


def _tier_diagnostic(seq, log, scene=None):
    """档位偏移诊断（取代 v3 的 通知≤6 / 客流≤8 两条硬上限）。"""
    start = {}
    for i, s in enumerate(seq, 1):
        start.setdefault(_tier(s, scene), i)
    log("[tier] 各档起始位: " + "、".join("第%d档→%d" % (k, v) for k, v in sorted(start.items())))
    for name, pat, expect in (("通知调度", re.compile(r"通知行车调度员|向行车调度员"), 6),
                              ("客流管控", re.compile(r"客流控制点|限流|铁马|回形线路|客流管控"), 8)):
        i = next((k for k, s in enumerate(seq, 1) if pat.search(_s(s.get("action")))), None)
        if i and i > expect:
            log("[tier] %s 最早落在第 %d 位（期望 ≤%d）；根因是更高档位共占 %d 步，非该步骤本身"
                % (name, i, expect, i - 1))


def _stage_of(n, action_type):
    """阶段 = 位置分箱；恢复善后是唯一例外（无论位置都归阶段四）。"""
    if _s(action_type) == "恢复善后":
        return "恢复善后"
    for lo, hi, name in STAGE_BINS:
        if lo <= n <= hi:
            return name
    return "恢复善后"


# ================= Markdown 还原（与 v2.1 同构） =================

def _check_deadline(n, stage, llm_text, log):
    """LLM 的 deadline_text 不再直接渲染；与阶段推导不符时告警（原文留痕在 JSON）。"""
    want = STAGE_MINUTES.get(stage)
    if not _s(llm_text):
        log("[deadline] 步骤%s 未填 deadline_text（阶段=%s，按阶段渲染）" % (n, stage))
        return
    m = re.search(r"\d+", _s(llm_text))
    if not m:
        log("[deadline] 步骤%s deadline_text 无数字「%s」（阶段=%s，按阶段渲染）"
            % (n, _s(llm_text)[:20], stage))
        return
    if want is not None and int(m.group(0)) != want:
        log("[deadline] 步骤%s 时限与阶段不符：LLM「%s」vs 阶段「%s」→ 按阶段渲染"
            % (n, _s(llm_text)[:20], STAGE_DEADLINE.get(stage)))


def _phr(parallel_with, host_n, old2new, stage_of_n, total, log):
    """【可并行】行（纯展示，不参与排序）。

    先把 LLM 的**原始 n** 经 old2new 映射到**重排后的 n**，再逐条校验：
    自引用 / 悬空 / 跨阶段 一律丢弃并告警；全部丢弃则不渲染本行。
    """
    ns = []
    for x in _l(parallel_with):
        m = re.search(r"\d+", _s(x))
        if not m:
            continue
        old = int(m.group(0))
        new = old2new.get(old, old)
        if new == host_n:
            log("[phr] 步骤%d 并行自引用（原 %d）→ 丢弃" % (host_n, old))
            continue
        if not 1 <= new <= total:
            log("[phr] 步骤%d 并行悬空（原 %d → %d，全文共 %d 步）→ 丢弃"
                % (host_n, old, new, total))
            continue
        if stage_of_n.get(new) != stage_of_n.get(host_n):
            log("[phr] 步骤%d 并行跨阶段（→ 步骤%d 属%s，本步属%s）→ 丢弃"
                % (host_n, new, stage_of_n.get(new), stage_of_n.get(host_n)))
            continue
        ns.append(new)
    return sorted(set(ns))


_STEP_REF = re.compile(r"步骤\s*(\d+|[一二三四五六七八九十]+)")
_CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_int(s):
    """'七' / '十一' / '二十一' → 7 / 11 / 21；无法解析 → None。"""
    if not s:
        return None
    if "十" not in s:
        return _CN_DIGIT.get(s) if len(s) == 1 else None
    a, _, b = s.partition("十")
    tens = _CN_DIGIT.get(a, 1) if a else 1
    ones = _CN_DIGIT.get(b, 0) if b else 0
    return tens * 10 + ones


def _check_step_refs(steps, log):
    """正文（action / fallback[].action）内嵌的「步骤N」引用不随重排更新 → **只告警、不改写**。

    不自动重映射：自由文本里的"步骤N"用正则改写易误判（未必真指该步），改错比不改更危险；
    先把它暴露出来，等 prompt 约束后仍出现，再据此设计重映射。
    """
    cur = {s["n"]: _first_sentence(s.get("action"))[:20] for s in steps}
    hits = 0
    for s in steps:
        texts = [("action", _s(s.get("action")))]
        for i, fb in enumerate(s.get("fallback") or []):
            if isinstance(fb, dict):
                texts.append(("fallback[%d].action" % i, _s(fb.get("action"))))
        for field, txt in texts:
            for m in _STEP_REF.finditer(txt):
                tok = m.group(1)
                ref = int(tok) if tok.isdigit() else _cn_to_int(tok)
                seg = txt[max(0, m.start() - 6):m.end() + 8]
                hits += 1
                log("[step-ref] 步骤%s 的 %s 内嵌「%s」——该编号现指向 步骤%s（%s）｜片段「…%s…」"
                    % (s["n"], field, m.group(0), ref if ref is not None else "?",
                       cur.get(ref, "不存在此步"), seg))
    if hits:
        log("[step-ref] 合计 %d 处内嵌步骤号引用（排序后未重映射，详见上文逐条）" % hits)
    return hits


def _depends_ns(depends_on, old2new, host_n):
    """把 `depends_on` 的**原始 n** 经 old2new 映射到重排后的 n（与 parallel_with 同款）。返回列表。"""
    ns = []
    for x in _l(depends_on):
        m = re.search(r"\d+", _s(x))
        if not m:
            continue
        new = old2new.get(int(m.group(0)))
        if new and new != host_n:
            ns.append(new)
    return sorted(set(ns))


def _render_steps(steps, log, cite=None):
    """按 stage_of() 计算出的阶段分组；组内保持新序号顺序。"""
    old2new = {}                                     # 排序前 n → 排序后 n（供 parallel_with 重映射）
    for i, s in enumerate(steps, 1):
        m = re.search(r"\d+", _s(s.get("n")))
        if m:
            old2new[int(m.group(0))] = i
        s["n"] = i
        s["stage"] = _stage_of(i, s.get("action_type"))
    stage_of_n = {s["n"]: s["stage"] for s in steps}
    total = len(steps)
    _check_step_refs(steps, log)
    buckets = {k: [] for k in STAGE_KEYS}
    for s in steps:
        buckets[s["stage"]].append(s)
    out = []
    for key in STAGE_KEYS:
        rows = buckets[key]
        if not rows:
            continue
        out.append("### " + STAGE_HEAD[key])
        out.append("")
        for s in rows:
            out.append("**步骤%s**：%s" % (s["n"], _s(s.get("action"))))
            _check_deadline(s["n"], s["stage"], s.get("deadline_text"), log)
            deadline = STAGE_DEADLINE.get(s["stage"], "目标 60 分钟内完成")
            out.append("- 阶段/时限：%s · %s" % (s["stage"], deadline))
            out.append("- 优先级：%s" % _s(s.get("action_type"), "其他"))
            out.append("- 岗位：%s" % "、".join(sorted(_role_set(s))))
            # v8.22：岗位四大类（第 2 层按类分派用）+ 做法要点（第 3 层个人 Agent 的展开起点）
            # 缺失时**显式标注**（不静默省略）—— 便于验收"每步都有"这条。
            out.append("- 岗位类别：%s" % (_role_category(s) or "⚠️ **未识别**"))
            out.append("- 做法要点：%s" % (_how_to(s) or "⚠️ **未提供**"))
            # v8.24：前置条件（**文字前提**，不是步骤引用）/ 所需资源
            # 缺失时同样**显式标注**（不静默省略）—— 便于验收"每步都有"这条。
            out.append("- 前置条件：%s" % (_precondition(s) or "⚠️ **未提供**"))
            out.append("- 所需资源：%s" % (_resources(s) or "⚠️ **未提供**"))
            out.append("- 依据：%s" % _s(s.get("basis")))
            _sp = (cite or {}).get(id(s))
            if _sp:
                out.append("- ⚠️ **引用存疑**（规程库中查不到该条款）：%s" % "；".join(_sp[:3]))
            _dns = _depends_ns(s.get("depends_on"), old2new, s["n"])
            s["_deps_new"] = _dns                      # 供「按岗位执行视图」复用
            if _dns:
                out.append("- 前置：需先完成 " + "、".join("步骤%d" % n for n in _dns))
            _pns = _phr(s.get("parallel_with"), s["n"], old2new, stage_of_n, total, log)
            s["_phr_new"] = _pns                       # 供「按岗位执行视图」复用
            if _pns:
                out.append("- 并行：【可并行】可与"
                           + "、".join("步骤%d" % n for n in _pns) + "同时进行")
            cr = s.get("case_ref")
            if isinstance(cr, dict) and _s(cr.get("id")):
                out.append("- 借鉴：【借鉴案例%s】%s" % (_s(cr.get("id")), _s(cr.get("note"))))
            for fb in (s.get("fallback") or []):
                if isinstance(fb, dict):
                    out.append("- 【备用：%s】步骤：%s" % (_s(fb.get("condition")), _s(fb.get("action"))))
            if _s(s.get("secondary_of")):
                out.append("- (次生：%s)" % _s(s.get("secondary_of")))
            out.append("")
    return out


def _render_role_view(steps):
    """按岗位重排：每个岗位一条自己的执行线。

    理由：**现场是分岗执行的**——值班站长拿到那份按优先级排的线性清单，得自己从十几步里
    挑出自己的那几步、并判断谁和谁同时在做。本节把同一份方案按 `role` 重排。
    **纯机械重排**：只用已渲染好的 `_deps_new` / `_phr_new`（已重编号），不引入任何新判断。
    """
    by_role = {}
    for s in steps:
        for r in sorted(_role_set(s)):
            by_role.setdefault(r, []).append(s)
    if not by_role:
        return []
    out = ["", "---", "", "## 三、按岗位执行视图", "",
           "> 现场**分岗执行**。本节把上面的方案按岗位重排——每个岗位只看自己这一条线；",
           "> 步骤号与上面「二、处置步骤」中的编号一致。", ""]
    # 步骤多的岗位排前面（通常是主责岗位）
    for r in sorted(by_role, key=lambda x: (-len(by_role[x]), x)):
        rows = by_role[r]
        # v8.22：岗位标注里带**类别**（本视图按具体角色分组，类别属该组属性 → 放表头，
        # 不逐步重复；「岗位：X（类别）」的逐行写法见 §二 主方案的「- 岗位类别：」行）。
        _rcat = _cat_of_role(r)
        out.append("### %s%s（%d 步）" % (r, " · " + _rcat if _rcat else "", len(rows)))
        out.append("")
        for s in rows:
            out.append("- **步骤%d** ｜ %s · %s ｜ %s"
                       % (s["n"], _s(s.get("action_type"), "其他"), s["stage"],
                          _s(s.get("action"))))
            _ht = _how_to(s)                      # v8.22：具体做法（与主方案 how_to 同源）
            if _ht:
                out.append("  - 具体做法：%s" % _ht)
            # v8.24：现场分岗执行时，"我能不能开始"（前置条件）与"我要带什么"（所需资源）
            # 是本视图最该回答的两问 —— 只在该步写了才渲染，避免每行都挂"无"。
            _pre = _precondition(s)
            if _pre:
                out.append("  - 前置条件：%s" % _pre)
            _res = _resources(s)
            if _res:
                out.append("  - 所需资源：%s" % _res)
            marks = []
            if s.get("_deps_new"):
                marks.append("**前置**：需先完成 " + "、".join("步骤%d" % x for x in s["_deps_new"]))
            if s.get("_phr_new"):
                marks.append("**可并行**：步骤" + "、".join(str(x) for x in s["_phr_new"]))
            if marks:
                out.append("  - " + "；".join(marks))
        out.append("")
    return out


def _esc_level_and_triggers(esc, log=None):
    """升级预案：当前响应级别 + **已过滤**的升级触发条件。返回 `(cur, triggers, flag)`。

    v8.26 两条守卫（对应需求方"升级逻辑无循环错误"）：

    ① **同级 / 降级触发一律丢弃**。目标级别不高于当前级别就不是"升级"——
       渲染成"IV 级事件可升级为 IV 级"会让读者误以为存在操作，实为**无操作**。
    ② **当前已是 I 级 → 不存在更高级别**：触发条件整段不渲染，返回 `flag="max"`，
       由调用方渲染「已达最高响应级别」。

    ⚠️ 目标级别**由阈值决定，不是"当前级别 + 1"**：当前 IV 级时若触发条件是"死亡≥30 人"
    （特别重大），正确目标是 **I 级**而非 III 级 —— 强行逐级 +1 会**漏响应**。
    """
    cur = _norm_level(esc.get("current_level")) or "IV"   # 与渲染默认值保持一致
    if cur == "I":
        return cur, [], "max"
    out = []
    for t in _ld(esc.get("triggers")):
        tgt = _norm_level(t.get("target_level"))
        if not tgt:
            continue
        if _lvl_rank(tgt) >= _lvl_rank(cur):              # 同级或更低 → 不是升级
            if log:
                log("[esc] 触发条件「%s」目标 %s 不高于当前 %s → 丢弃（非升级）"
                    % (_s(t.get("condition"))[:24], tgt, cur))
            continue
        out.append(t)
    return cur, out, ""


def _render_brief(ev, sev, resp, comp, esc, cautions, seq, event_profile, log=None):
    """作战简报（v8.25）：**指挥员视角**的宏观层，置于整份方案最顶部。

    只回答"全局怎么打"——等级研判、耦合风险链、专业组方向、盲点、升级条件。
    细节（逐步动作 / 岗位 / 依据 / 前置条件 / 资源）一律**留在下层详案**，此处不重复。
    """
    B = ["# 📑 作战简报", ""]
    pre = sev.get("preliminary") if isinstance(sev.get("preliminary"), dict) else {}
    pre_lvl = _s(pre.get("level")) or "无法初判"
    precise = _s(sev.get("level"))
    on_miss = (not precise) or precise == "尚未成立" or precise.startswith("信息不足")

    # ---- 一、等级研判与待核实项 ----
    B += ["## 一、等级研判与待核实项", ""]
    _c = _s(pre.get("confidence"))
    rows = _metric_rows(sev)
    got = [r["name"] for r in rows if r["value"] != "未提供"]
    miss = [r["name"] for r in rows if r["value"] == "未提供"]
    if on_miss:
        if not got:
            # 四项**全**缺失 —— 按需求方指定口径：明说"无法精确分级"，再给保守初判
            B.append("- **精确判定**：**四项定级指标均缺失，无法对照国家标准进行精确分级**")
        else:
            B.append("- **精确判定**：**尚未成立** —— 已有 %d 项指标（%s），"
                     "但均**未命中任何一档**，无法精确分级" % (len(got), "、".join(got)))
        B.append("- **保守初判等级**：**%s**%s" % (pre_lvl, ("（置信：%s）" % _c) if _c else ""))
        B.append("  - ⚠️ **此为保守推断，非国家标准量化判定** —— 依据的是对**同类事件极端危险性**"
                 "的一般认识，**仅用于确定响应规模与处置力度，不得作为事故定级结论**")
    else:
        B.append("- **初判等级**：%s%s" % (pre_lvl, ("（置信：%s）" % _c) if _c else ""))
        B.append("- **精确判定**：**%s**（已对照 7.2 标准命中）" % precise)
    if miss:
        B.append("- **⚠️ 待核实项**（缺失指标，现场须**第一时间核准**；阈值见下表）：%s"
                 % "、".join(miss))
    B.append("")
    B.append("- **定级依据对照表**（口径：`X人以上Y人以下` = **含 X 不含 Y**）：")
    B += _render_grade_table(sev)
    B.append("")
    if _s(sev.get("correction")):
        B.append("- **触发修正**：%s" % _s(sev.get("correction")))
    B.append("- **响应级别建议**：%s ｜ 责任主体：%s ｜ 报告时限：%s"
             % (_lvl(_s(resp.get("level"))), _s(resp.get("authority")),
                _s(resp.get("report_deadline"))))
    _dg = _s(resp.get("_grade_derived"))
    if _dg:
        # ★ 需求：已按"保守初判"定了事故等级时，**同步写出**建议的响应级别（及推导来源）
        B.append("  - **级别推导**：事故等级「**%s**」%s → 响应级别 **%s 级**（1:1 映射）；"
                 "责任主体按 4.1 绑定 → **%s**"
                 % (_dg, "（保守初判）" if on_miss else "（精确判定）",
                    _norm_level(resp.get("level")), _s(resp.get("authority"))))
    B.append("")

    # ---- 二、整体态势与耦合风险研判 ----
    B += ["## 二、整体态势与耦合风险研判", ""]
    pinfo = event_profile if isinstance(event_profile, dict) else {}
    B.append("- **主事件**：%s" % (_s(ev.get("impact")) or "（未填写）"))
    envs = [_s(x) for x in _l(pinfo.get("environmental_factors")) if _s(x)]
    secs = [_s(s.get("event_type")) for s in _ld(pinfo.get("secondary_events"))]
    pots = [_s(x) for x in _l(pinfo.get("potential_risks")) if _s(x)]
    B.append("- **环境诱因**：%s" % ("、".join(envs) if envs else "无"))
    B.append("- **次生/衍生事件**：%s" % ("、".join(x for x in secs if x) if any(secs) else "无"))
    B.append("- **潜在风险**（尚未发生，需防）：%s" % ("、".join(pots) if pots else "无"))
    risks = [_s(x) for x in _l(comp.get("risks")) if _s(x)]
    if risks:
        B.append("- **多险并发**：本事件同时包含 **%d 类险情**——%s"
                 % (len(risks), "；".join(risks)))
    if _s(comp.get("interaction")):
        B.append("  - **相互放大**：%s" % _s(comp.get("interaction")))
    chains = _chains_of(comp)
    if chains:
        B.append("- **⚠️ 耦合风险链推演**：")
        for k, c in enumerate(chains, 1):
            B.append("  %d. %s → **%s**%s"
                     % (k, " + ".join(c["from"]), c["to"],
                        ("（%s）" % c["why"]) if c["why"] else ""))
    conflicts = _conflicts_of(comp)
    if conflicts:
        B.append("- **⚔️ 处置冲突与协同**：")
        for c in conflicts:
            B.append("  - **冲突点**：%s" % c["conflict"])
            if c["strategy"]:
                B.append("  - **协同策略**：%s" % c["strategy"])
    B.append("")

    # ---- 三、总体处置方向（按专业组统筹）----
    B += ["## 三、总体处置方向（按专业组统筹）", ""]
    groups = _llm_groups(ev)
    if groups:
        for g in groups:
            B += ["### %s %s" % (_COMMAND_ICON.get(g["group"], ""), g["group"]), ""]
            if g["direction"]:
                B.append("- **方向**：%s" % g["direction"])
            if g["strategy"]:
                B.append("- **核心策略**：%s" % g["strategy"])
            B.append("")
    else:
        derived = _derive_groups(seq)
        if derived:
            B.append("> ⚠️ 模型未给出专业组方向，**以下由代码按步骤属性机械归并**（非模型研判）。")
            B.append("")
            for g in derived:
                B += ["### %s %s（%d 步）" % (_COMMAND_ICON.get(g["group"], ""),
                                              g["group"], g["n"]), ""]
                B.append("- **本组主要动作**：%s"
                         % "；".join(x for x in g["acts"] if x))
                B.append("")
        else:
            B.append("- （无可归并的处置步骤）")
            B.append("")

    # ---- 四、处置盲点预警 ----
    B += ["## 四、处置盲点预警（最容易出事的地方）", ""]
    cautions = [_s(c) for c in _l(cautions) if _s(c)]
    if cautions:
        for k, c in enumerate(cautions[:4], 1):
            B.append("%d. %s" % (k, c))
    elif pots:
        for k, c in enumerate(pots[:4], 1):
            B.append("%d. %s（由潜在风险推得）" % (k, c))
    else:
        B.append("- （未识别出特定盲点）")
    B.append("")

    # ---- 五、升级触发条件 ----
    B += ["## 五、升级触发条件", ""]
    cur, triggers, flag = _esc_level_and_triggers(esc, log)
    B.append("- **当前响应级别**：%s 级" % cur)
    if flag == "max":
        B.append("- **已达最高响应级别（Ⅰ级）** —— 不存在更高级别可升级。")
        B.append("  若事态进一步扩大，应报请**省级人民政府 / 国务院**提高应对层级，"
                 "而非「升级响应级别」。")
    elif triggers:
        for t in triggers:
            B.append("- 若发生 **%s** → 升级为 **%s 级**%s"
                     % (_s(t.get("condition")), _norm_level(t.get("target_level")),
                        ("（依据：%s）" % _s(t.get("basis"))) if _s(t.get("basis")) else ""))
    else:
        B.append("- （未给出升级触发条件；或所给条件均**不高于当前级别**，"
                 "已按「非升级」丢弃）")
    B.append("")
    return B


def _render_markdown(obj, event_profile=None):
    """JSON → 方案。返回 (markdown, warnings)。"""
    def log(msg):
        logging.warning("[plan] %s", msg)

    warn = []
    ev = obj.get("event") or {}
    sev = ev.get("severity") or {}
    resp = ev.get("response") or {}
    raw_steps = [s for s in (obj.get("steps") or []) if isinstance(s, dict)]

    # ---- v8.26：响应级别由**事故等级**按 1:1 硬映射推导（业务硬规则）----
    # 事故等级取**当前生效**的那个：精确判定成立用它，否则用**保守初判**。
    # 推导结果**覆盖**模型填的 `level`/`authority` —— 响应级别决定"谁负责"（省级还是市级），
    # 属责任划分，不由模型裁量；不一致处**告警留痕**。
    _grade = _grade_of(sev)
    _rl = GRADE_TO_RESPONSE.get(_grade, "")
    _model_rl = _norm_level(resp.get("level"))
    if _rl:
        if _model_rl and _model_rl != _rl:
            log("[resp] 模型填的响应级别「%s」与「事故等级 %s → %s」1:1 映射不符 → 按映射修正"
                % (_model_rl, _grade, _rl))
        resp = dict(resp)
        resp["level"] = _rl
        _exp_auth = _LVL_AUTHORITY.get(_rl, "")
        if _exp_auth:
            resp["authority"] = _exp_auth
        resp["_grade_derived"] = _grade
    if not raw_steps:
        warn.append("steps 为空")
    # ---- 场景化 TIER（v1）：从 event_profile 反推场景；未命中 → None 用默认表 ----
    scene = _scene_key(event_profile, _tier_overrides())
    if scene:
        log("[tier] 场景=%s → TIER 覆盖=%s" % (scene, _tier_overrides().get(scene)))
    # ---- 第二步管道：A 先占位 → 合并 → 计数 → 排序 → 重编号/阶段 ----
    flags = _flags(event_profile, raw_steps)
    demanded = _demand_slots(raw_steps, flags, log, scene)   # A：在原始 steps 上定槽位
    reserved = {id(s) for _, _, s, _ in demanded}            # 占位步骤不参与合并/丢弃
    merged = _merge_steps(raw_steps, reserved, log, scene)
    kept = _cap_steps(merged, reserved, log)
    seq = _order_steps(kept, demanded, log, scene)
    seq = _apply_depends(seq, log)                           # 硬先后：depends_on 参与排序
    seq = _enforce_hard_order(seq, log)                      # 代码层硬先后兜底（4 条规则），最后发言
    seq = _inject_hazard_step(seq, event_profile, len(demanded), log)   # 气体泄漏：缺气源处置则补入
    _tier_diagnostic(seq, log, scene)

    # ---- 引用可证实性：把每步 `依据` 逐条回查规程库（机械证伪"编造条款"）----
    cite_map, c_ok, c_susp, c_nonc, c_broken = {}, 0, [], [], False
    for _st in seq:
        _o, _sp, _nc, _br = _check_citations(_st.get("basis"))
        cite_map[id(_st)] = _sp
        c_ok += _o
        c_susp += _sp
        c_nonc += _nc
        c_broken = c_broken or _br
    cite_stat = {"total": c_ok + len(c_susp), "ok": c_ok, "susp": len(c_susp),
                 "samples": c_susp, "nonclause": len(c_nonc), "broken": c_broken}
    _check_hazard(event_profile, seq, log)                   # 危险源是否被处理（只告警）

    # ---- v8.25 双层结构：顶部「作战简报」（宏观，指挥员读）+ 下部「详细执行方案」（微观，一线读）----
    # 详案层章节号**保持原样不动**（一~七）—— `_selftest.py` 断言了
    # `## 三、按岗位执行视图` / `## 四、升级预案` 的字面存在；简报自成 H1、自编号。
    comp = ev.get("composite") if isinstance(ev.get("composite"), dict) else {}
    esc = obj.get("escalation") if isinstance(obj.get("escalation"), dict) else {}
    L = _render_brief(ev, sev, resp, comp, esc, obj.get("cautions"), seq, event_profile, log)
    L += ["", "---", "",
          "# 📋 详细执行方案", "",
          "> ⚠️ **本方案为自动生成的初判草案，须经现场负责人复核后方可执行。**", "",
          "## 一、事件定性", ""]
    # ---- 定级三段式：初判 → 精确判定 → 触发修正 ----
    pre = sev.get("preliminary") if isinstance(sev.get("preliminary"), dict) else {}
    pre_lvl = _s(pre.get("level")) or "无法初判"
    precise = _s(sev.get("level"))
    on_miss = (not precise) or precise == "尚未成立" or precise.startswith("信息不足")
    # 渲染后兜底：**方案自己都说「无法初判 + 尚未成立」，或模型交空步骤 → 截断，不渲染处置步骤**
    if (pre_lvl == "无法初判" and on_miss) or not raw_steps:
        logging.warning("[plan] 方案自身无法定级或 steps 为空 → 截断处置步骤")
        return _insufficient_plan(
            "事件画像与生成的方案**均无法判定等级**；描述里没有可支撑处置的具体信号"), warn
    _pa = []
    if _s(pre.get("confidence")):
        _pa.append("置信：%s" % _s(pre.get("confidence")))
    if pre_lvl == "无法初判":
        _pa.append('上游亦未给出等级 → 按"信息不足，暂按一般事件处置，持续跟踪升级"')
    _basis = _s(pre.get("basis"))
    L.append("- **初判等级**：%s%s%s"
             % (pre_lvl, ("（%s）" % " · ".join(_pa)) if _pa else "",
                ("　依据：%s" % _basis) if _basis else ""))
    if not on_miss:
        _ov = ""
        if pre_lvl != "无法初判" and _s(pre_lvl).replace("事故", "") != precise.replace("事故", ""):
            _ov = "　**与初判不一致 → 已按 7.2 覆盖初判**"
        L.append("- **精确判定**：**%s**%s" % (precise, _ov))
    else:
        L.append("- **精确判定**：**尚未成立**（缺量化数字）→ **当前按「初判等级」处置**")
    if _s(sev.get("correction")):
        L.append("- **触发修正**：%s" % _s(sev.get("correction")))
    tiers = [t for t in (sev.get("tiers") or []) if isinstance(t, dict)]
    tiers_all_miss = bool(tiers) and all("未命中" in _s(t.get("hit")) for t in tiers)
    if tiers:
        L.append("- **分级对照**：逐条对照《国家城市轨道交通运营突发事件应急预案》7.2 四档标准：")
        for t in tiers:
            L.append("  - %s：%s —— %s" % (_s(t.get("name")), _s(t.get("threshold")), _s(t.get("hit"))))
    else:
        L.append("- **分级对照**：逐条对照《国家城市轨道交通运营突发事件应急预案》7.2 四档标准：%s"
                 % _s(sev.get("conclusion")))
    if _s(sev.get("conclusion")):
        L.append("  - **结论**：%s" % _s(sev.get("conclusion")))
    lvl_raw = _s(resp.get("level"))
    authority = _s(resp.get("authority"))
    expected_auth = _LVL_AUTHORITY.get(_norm_level(lvl_raw), "")
    if expected_auth and not _authority_matches(authority, expected_auth):
        log("[resp] 责任主体与响应级别不符：level=%s 应为「%s」，实际「%s」→ 按 4.1 修正"
            % (lvl_raw or "（空）", expected_auth, authority or "（空）"))
        authority = expected_auth
    L.append("- **响应级别**：%s ｜ **责任主体**：%s ｜ **报告时限**：%s"
             % (_lvl(lvl_raw), authority, _s(resp.get("report_deadline"))))
    _dg2 = _s(resp.get("_grade_derived"))
    if _dg2:
        L.append("- **级别推导**：事故等级「**%s**」→ 响应级别 **%s 级**（1:1 硬映射）；"
                 "责任主体由响应级别按 4.1 绑定（Ⅰ/Ⅱ → 省级；Ⅲ/Ⅳ → 市级）"
                 % (_dg2, _norm_level(lvl_raw)))
    L.append("- **影响范围**：%s" % _s(ev.get("impact")))
    risks = _l(comp.get("risks"))
    if risks:
        L.append("- **复合情形**：本事件同时包含 **%d 类险情**——" % len(risks))
        for k, x in enumerate(risks, 1):
            L.append("  %d. %s" % (k, x))
        if _s(comp.get("interaction")):
            L.append("  - **相互影响**：%s" % _s(comp.get("interaction")))
    else:
        L.append("- **复合情形**：未识别为多险并发（`composite` 为空）")
    L.append("- **置信自检**（以下由代码判定，非模型自述）：")
    for _k, _v in _confidence_checks(event_profile, sev, risks, cite_stat):
        L.append("  - %s：%s" % (_k, _v))
    L += ["", "---", "", "## 二、处置步骤", ""]
    L += _render_steps(seq, log, cite_map)
    L += _render_role_view(seq)

    # ---- 升级预案：extra_steps 独立管道（不合并/不截断/不排序）----
    # （`esc` 已在函数开头读取，此处不再重复赋值）
    L += ["---", "", "## 四、升级预案", ""]
    if esc.get("applicable") is False:
        L.append("- 不适用")
    else:
        _cur, _trig, _flag = _esc_level_and_triggers(esc, log)
        L.append("- **当前按**：%s级处置" % _cur)
        if _flag == "max":
            L.append("- **已达最高响应级别（Ⅰ级）** —— 不存在更高级别可升级；"
                     "事态扩大应报请省级人民政府 / 国务院提高应对层级。")
        else:
            L.append("- **升级触发条件**：满足以下任一条件即升级：")
            for t in _trig:
                L.append("  - %s → 升级为 %s 级（依据：%s）"
                         % (_s(t.get("condition")), _norm_level(t.get("target_level")),
                            _s(t.get("basis"))))
            if not _trig:
                L.append("  - （未给出；或所给条件均不高于当前级别，已按「非升级」丢弃）")
        L.append("- **升级后增补的步骤**：")
        for i, t in enumerate([t for t in (esc.get("extra_steps") or []) if isinstance(t, dict)], 1):
            # v8.22：增补步骤带 role_category（四类之一；缺失由 _role_category 兜底）
            L.append("  %d. %s（岗位：%s（%s）；依据：%s）"
                     % (i, _s(t.get("action")), _s(t.get("role")),
                        _role_category(t) or "未识别", _s(t.get("basis"))))

    dim = obj.get("dimensions") or {}
    e, sd = dim.get("evacuation") or {}, dim.get("shutdown") or {}
    rp, cc = dim.get("reporting") or {}, dim.get("crowd_control") or {}
    L += ["", "---", "", "## 五、四维覆盖", ""]
    L.append("- **① 人员疏散**：疏散路径：%s；集合点：%s；弱势群体优先：%s（依据：%s）"
             % (_s(e.get("path")), _s(e.get("meeting_point")), _s(e.get("priority")), _s(e.get("basis"))))
    L.append("- **② 关停决策**：关闭出入口/车站：%s；区段或线路停运：%s（依据：%s）"
             % (_s(sd.get("entrances")), _s(sd.get("section_or_line")), _s(sd.get("basis"))))
    L.append("- **③ 信息报告**：报告对象：%s；时限：%s；报告格式：%s（依据：%s）"
             % (_s(rp.get("target")), _s(rp.get("deadline")), _s(rp.get("format")), _s(rp.get("basis"))))
    L.append("- **④ 大客流管控**：%s（依据：%s）"
             % (_s(cc.get("measures")), _s(cc.get("basis"), "GB/T 38707 14.2.15")))

    L += ["", "---", "", "## 六、关键注意事项", ""]
    for i, c in enumerate([c for c in (obj.get("cautions") or []) if _s(c)], 1):
        L.append("%d. %s" % (i, _s(c)))

    L += ["", "---", "", "## 七、溯源", ""]
    for s in (obj.get("sources") or []):
        L.append("- %s" % (_s(s.get("ref")) if isinstance(s, dict) else _s(s)))

    return "\n".join(L).rstrip() + "\n", warn


def _extract_json(text):
    """剥离围栏/前后说明，取最外层 JSON 对象；失败返回 None。"""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        obj = json.loads(t[i:j + 1])
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


SCHEMA_SPEC = f"""【输出格式：只输出一个 JSON 对象，不要任何解释文字、不要 Markdown 围栏】
{{
  "event": {{
    "severity": {{
      "preliminary": {{"level": "特别重大|重大|较大|一般|无法初判", "confidence": "高|中|低",
                       "basis": "初判依据（上游判定 + 描述里出现的信号）"}},
      "level": "**精确判定**：有量化数字且命中某档时写该档名（如\"较大事故\"）；无量化数字时**必须写\"尚未成立\"**",
      "correction": "**触发修正**：核实哪些数字、达到什么区间后按 7.2 改判为哪一档（一句话）",
      "metrics": [                     // v8.26：**定级依据对照表**的四行（四项指标逐一，**顺序固定**）
        {{"name": "死亡人数",             // 四选一：死亡人数|重伤人数|直接经济损失|连续中断行车
          "value": "描述里给出的该项数值（如「2 人」「约 500 万元」）；**未给出就写「未提供」**",
          "level": "特别重大|重大|较大|一般|**待核实**  —— 该指标**单独**对照 7.2 落在哪一档"}}
        // ↑ 四项都要写，**共 4 行**。阈值列**由代码渲染**，你不要重述阈值。
      ],
      "tiers": [                       // 四档逐一对照，每档一行
        {{"name": "特别重大",
          "threshold": "**逐字照抄**约束（一）的基准表（口径：X人以上Y人以下 = 含 X 不含 Y）",
          "hit": "未命中（原因）或 命中第X条"}}
      ],
      "conclusion": "逐条对照 7.2 后的结论（一句话）"
    }},
    "response": {{"level": "IV", "authority": "<按 4.1 填写>", "report_deadline": "具体时限"}},
    "impact": "影响范围（一句话）",
    "composite": {{
      "risks": ["险情1", "险情2"],
      "interaction": "一句话说明这些险情如何相互放大",
      "chains": [                      // **耦合风险链推演**（见约束二十）：每条链写清"谁+谁 → 推出什么风险"
        {{"from": ["暴雨", "信号故障"], "to": "追尾风险",
          "why": "降级运行下制动距离延长、区间追踪间隔被压缩"}}
      ],
      "conflicts": [                   // **处置冲突与协同**：两条处置要求互相打架时怎么同时满足
        {{"conflict": "暴雨要求关闭车门防雨水倒灌触电，但疏散要求打开车门",
          "strategy": "先确认轨道无积水无漏电，在防触电前提下手动开门疏散，并同步设置挡水板"}}
      ]
    }},
    "command": {{                      // **宏观指挥层**（见约束二十）：供作战简报用
      "groups": [
        {{"group": "综合协调与指挥调度|现场抢险与风险控制|乘客疏散与医疗救护|信息发布与运营调整  **四选一**",
          "direction": "该专业组的**总方向**（一句话，要有高度）",
          "strategy": "核心策略：2–3 个动作点，用 ①②③ 分隔（说"往哪个方向发力"，**不写逐步操作**）"}}
      ]
    }}
  }},

  "steps": [
    {{
      "n": 1,                          // 整数，从 1 连续编号
      "action": "该步动作原文（含条件分支时也写全）",
      "how_to": "**做法要点**：2–4 个动作点，用 ①②③④ 分隔（比 action 细一档；不写按键/话术/逐字稿，见约束（十七））",
      "precondition": "**前置条件**：执行本步的**前提**（文字描述，如「牵引电流已隔离」「危险源已确认」）；确实无前提时写「无」。见约束（十九）",
      "resources": "**所需资源**：本步需要的物资 / 设备 / 人力（如「潜水泵 2 台、沙包 20 只、4 人」）；确实不需要时写「无」。见约束（十九）",
      "action_type": "人身安全|切断危险源|关键设备|运营调整|信息报告|恢复善后  六选一",
      "stage": "先期处置|现场处置|扩大响应|恢复善后  四选一",
      "deadline_text": "目标 X 分钟内完成",
      "role": ["执行岗位"],             // 数组；一个岗位或并列岗位
      "role_category": "一线执行|调度指挥|车站管理|后勤安保  四选一（见约束（十八））",
      "basis": "规程章节 [步骤号] 或规范条款号",
      "parallel_with": [2, 3],          // 可并行步骤的 n；没有就写 []
      "depends_on": [1],                // **必须先完成**的步骤 n（硬先后）；没有就写 []
      "fallback": [{{"condition": "若…", "action": "…"}}],   // 【备用】分支；没有就写 []
      "secondary_of": "次生事件名或 null",
      "case_ref": {{"id": "case_1", "note": "一句话"}}       // 无则写 null
    }}
  ],

  "escalation": {{
    "applicable": true,                 // "事故等级"为"信息不足"时必须 true
    "current_level": "IV",
    "triggers": [{{"condition": "重伤≥10人", "target_level": "III", "basis": "7.2 较大事件"}}],
    "extra_steps": [{{"action": "…", "role": ["…"], "role_category": "一线执行|调度指挥|车站管理|后勤安保  四选一", "basis": "…"}}]
  }},

  "dimensions": {{
    "evacuation": {{"path": "…", "meeting_point": "…", "priority": "…", "basis": "…"}},
    "shutdown": {{"entrances": "…", "section_or_line": "…", "basis": "…"}},
    "reporting": {{"target": "…", "deadline": "…", "format": "…", "basis": "…"}},
    "crowd_control": {{"measures": ["…", "…"], "basis": "GB/T 38707 14.2.15"}}
  }},

  "cautions": ["禁止行为 1", "禁止行为 2"],          // 最多 3 条
  "sources": [{{"ref": "AIEP28 28C [步骤1-10]", "kind": "规程"}}]
}}
"""

RETRY_SUFFIX = """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【上一次输出不是合法 JSON。本次**只输出一个 JSON 对象**，
不要任何解释文字、不要 ``` 围栏、不要 Markdown 标题。】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def generate_plan(user_description, event_profile, rag_context, kg_context, case_context, llm_client):
    """生成处置方案：LLM 出 JSON → 代码排序/合并/计数/定阶段 → Markdown。"""

    event_types = _get_event_types(event_profile)
    primary_type = event_types[0] if event_types else "未识别"
    secondary_types = event_types[1:] if len(event_types) > 1 else []
    severity, severity_reason = _get_severity(event_profile)

    # ---- 前置门：上游根本没识别出事件 → **直接拒绝生成，连 LLM 都不调** ----
    blocked, why = _insufficient_info(event_profile)
    if blocked:
        logging.warning("[plan] **信息不足，拒绝生成方案**：%s（未调用 LLM）", why)
        return _insufficient_plan(why)
    location = event_profile.get("location", "未识别")
    roles = event_profile.get("involved_roles", [])

    # ---- v8.25：环境诱因 / 潜在风险 / 混合场景判定 ----
    # 上游 `event_understand.py` 新增这两个字段；这里是**防御性读取**
    # （老画像无此键 → []，不崩）。
    env_factors = [_s(x) for x in _l(event_profile.get("environmental_factors")) if _s(x)]
    pot_risks = [_s(x) for x in _l(event_profile.get("potential_risks")) if _s(x)]
    # 判定"混合场景"：**有环境诱因** 且 **有次生事件或潜在风险** —— 单靠次生事件不够，
    # 因为纯设备故障引发的次生（如"设备故障→乘客滞留"）并不构成"多套规程要融合"。
    mixed = bool(env_factors) and bool(secondary_types or pot_risks)
    if mixed:
        mixed_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【本事件为**混合场景** —— 多套规程融合，不要只按一套展开】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本事件**不是单一事件**，上面的【规程原文片段】来自**多套预案**（如暴雨预案 + 信号故障规程
+ 大客流管控 + 医疗救护）。请按下列规则融合：
- **环境诱因**：{('、'.join(env_factors)) or '无'}
- **已发生的次生事件**：{('、'.join(secondary_types)) or '无'}
- **潜在风险**：{('、'.join(pot_risks)) or '无'}

**融合规则**：
1. **多套都要覆盖** —— 每套规程的核心动作都要在 `steps` 里有落点，**不得只讲主事件那套**。
2. **冲突必须显式消解** —— 两套规程要求打架时（典型："关车门防雨水倒灌触电" vs
   "开车门清人疏散"），**不得各写一步了事**，必须在 `composite.conflicts` 里写明
   冲突点与协同策略。
3. **环境诱因是放大器** —— 同样的动作在暴雨 / 湿滑 / 大客流条件下**先决条件不同**，
   `precondition` 必须体现这些外部条件（如"轨面无积水漏电""已确认接触轨无电"）。
4. **剔除无关部分** —— 某套规程中与本事件无关的动作**不要硬塞**（非水淹事件不抄排水步骤）。
"""
    else:
        mixed_section = ""

    has_cases = bool(case_context) and "未检索到" not in case_context and "未加载" not in case_context
    if has_cases:
        case_section = f"""
【相似历史案例（可选参考，相似度低可忽略）】
{case_context}
"""
    else:
        case_section = "（本次未检索到相似历史案例，请完全依据规程生成方案）"

    prompt = f"""你是轨道交通应急指挥专家。请根据以下资料，生成一套**精简、可执行**的处置方案。
**输出必须是一个 JSON 对象**（字段见文末），由系统渲染成正式方案。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【第一优先级：规范步骤】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**方案必须以规程为准，做到：**
1. 步骤有逻辑、有先后顺序，现场人员可以照着执行。
2. 每步明确标注执行岗位（不能只写"值班站长"，要具体到"值班站长"、"车站员工"、"行车调度员"、"驾驶员"等）。
3. 每步标注依据条款（AIEP章节 + 步骤号），可溯源。
4. 岗位分派准确，不能让A岗位做B岗位的事。
5. 严禁编造规程里没有的动作。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【第二优先级：案例参考（加分项，不是必须）】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 若有相似案例（相似度≥0.6），可借鉴其实操细节或偏差教训，填进该步的 `case_ref` 字段。
2. 若案例相似度低（<0.6）或无案例，**不要强行引用**，`case_ref` 写 null。
3. 案例只补充细节，不能替代规程条款，也不能改变步骤顺序。
4. 案例与规程冲突时，以规程为准。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【事件画像】
- 主事件：{primary_type}
- 次生事件：{', '.join(secondary_types) if secondary_types else '无'}
- 环境诱因（**放大器，直接改变先决条件**）：{', '.join(env_factors) if env_factors else '无'}
- 潜在风险（**尚未发生，需预防**）：{', '.join(pot_risks) if pot_risks else '无'}
- 上游判定等级（**合法依据，必须沿用**）：{severity}｜依据：{severity_reason}
- 位置：{location}
- 涉及岗位：{', '.join(roles)}

【规程原文片段（**第一依据**：方案的动作只能来自这里）】
{rag_context}

【知识图谱事实（**仅作动作与岗位的补充参考**）】
{kg_context}
（注：图谱节点可能含**脏数据**——例如把"一律视作""须""不得"这类**模态词/虚词**误作动作，
  或节点名是一整句话。**凡图谱内容与上面的规程原文冲突，一律以规程原文为准；
  图谱里读不通、不像具体动作的条目，直接忽略，不得据此编造步骤。**）

{case_section}

【用户原始描述】
{user_description}
{mixed_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【前置条件：是否生成方案】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**若满足以下任一条件，禁止生成具体处置步骤**——`steps` 必须为空数组 `[]`，
并在 `severity.conclusion` 里照实写清缺什么，**不得用"万能模板"凑步骤**：
1. 主事件类型为"未识别"或为空；
2. 你无法从描述中判断这是什么事件（如"某地出事了""处理一下"这类没有具体信息的描述）；
3. 没有任何可支撑动作的场景信号（火灾 / 爆炸 / 脱轨 / 撞击 / 拥挤 / 袭击 / 设备故障 / 人员伤病…一个都没有）。

理由：**无法识别事件时硬套规程，比不输出更危险**——读者可能照着执行，
而每一步的「依据」来自一份与本次事件无关的规章。

反例（明确禁止）：事件性质未知时，写"步骤1：若涉及水淹则挡水、若涉及火灾则灭火、若涉及人员受伤则施救"
——那是**不知道该做什么时把所有可能都列一遍**，不是方案。

若事件**可识别**（哪怕信息不完整，例如"站台有乘客晕倒""区间列车起火"），**照常生成完整方案**。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【流程覆盖：八个环节逐项自查（v8.24）】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
生成前，用下表的**八个环节**当骨架逐项过一遍——**每个环节都要有落点，不得凭空跳过**。
左列是环节（你的**思考清单**），右列说明该环节的步骤在 `stage` 字段里**该填什么**：

| 环节 | 说明 | `stage` 填 |
|---|---|---|
| 1 监测预警 | 事件发现、险情确认 | 先期处置 |
| 2 先期处置 | 到场、初步控制、**救人为先** | 先期处置 |
| 3 分级响应 | 判定等级、启动对应响应 | —（不产生步骤，见下） |
| 4 现场处置 | 危险源处置、设备抢修、运营调整 | 现场处置 |
| 5 资源调度 | 物资 / 人力 / 外部力量的调配与到位 | 现场处置 / 扩大响应 |
| 6 人员疏散与医疗救护 | 疏散引导、现场施救、送医 | **先期处置 / 现场处置** |
| 7 信息上报 | 内部通报、对外通告 | 现场处置 / 扩大响应 |
| 8 后期恢复 | 恢复行车、现场清理、复盘 | 恢复善后 |

**三条使用规则**：
1. **「环节」是覆盖清单，不是 `stage` 的取值** —— `stage` 仍**四选一**
   （先期处置 / 现场处置 / 扩大响应 / 恢复善后），照上表映射过去。
2. **第 3 环节「分级响应」不产生步骤** —— 它已由 `event.severity`（定级三段式）与
   `event.response`（级别 / 责任主体 / 时限）承担；**不要**再单列"启动Ⅲ级响应"之类的步骤凑数。
3. **第 6 环节必须靠前** —— "疏散 / 医疗救护"属**人身安全**，必须落在**先期处置或现场处置**，
   **不得**排到"资源调度"之后（人等资源 = 时序矛盾）。
   确实不适用的环节（如本事件无预警阶段）可以没有对应步骤，但**有落点的环节一个都不能漏**。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【硬性约束：以下二十条为强制要求，不得违反、不得省略】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

（一）分级必须对照标准，禁止**凭空**推断
`severity.tiers` 必须逐条对照《国家城市轨道交通运营突发事件应急预案》7.2 的四档标准
（死亡人数 / 重伤人数 / 经济损失 / 中断时长），每档写 `hit`：
**`hit` 只能基于描述里给出的数字**——命中写"命中第X条"，否则写"未命中（缺少哪项数字）"。
**不得**把定性事实（如"大量伤亡""车厢坍塌""涉及隧道"）写成某一档的"命中"——
7.2 是**纯量化**标准，那类事实只能用来支撑「初判等级」（`preliminary`），不能算作 7.2 命中。

**对照基准表（`tiers` 的 `threshold` 必须逐字照抄本表，禁止自行改写阈值或编造数值）**：

**★ 阈值口径（强制）：一律写 `X人以上Y人以下`，含义是**含 X、不含 Y**。
禁止写 `10–49 人` `50-99人` 这类**区间简写**——现场按简写判读会把边界数字归错档。**

| 档次 | 死亡人数 | 重伤人数 | 直接经济损失 | 连续中断行车 |
|---|---|---|---|---|
| 特别重大 | ≥30 人 | ≥100 人 | ≥1 亿元 | **—（7.2 无此条）** |
| 重大 | 10人以上30人以下 | 50人以上100人以下 | 5000万元以上1亿元以下 | 24小时以上 |
| 较大 | 3人以上10人以下 | 10人以上50人以下 | 1000万元以上5000万元以下 | 6小时以上24小时以下 |
| 一般 | **3人以下（不含3人）** | **10人以下（不含10人）** | **50万元以上1000万元以下** | 2小时以上6小时以下 |

**注意三条易错处**：① **特别重大档没有"连续中断行车"** —— 中断再长也只到"重大"
（除非死亡/重伤/损失够特别重大）；② 一般档经济损失**有 50 万元下限**，不是"<1000 万元"；
③ 最低档用"**以下**"而非"以上…以下"配对写法，且**不含本数**（3 人以下 = 1~2 人，
3 人整即入"较大"档）。

**本条口径适用全篇**：`tiers`、`metrics`、`correction` 里凡出现阈值，
**一律用 `X人以上Y人以下` 写法**，不得写成 `10-49` `50–99` 这类简写。

**特别注意"连续中断行车"这一列**——它最容易被写错（曾出现"重大：6–24 小时""较大：2–6 小时"这种整体错位的编造）。
**本表适用全篇**：`tiers`、`correction`（触发修正）里凡写到阈值，**都必须逐字取自本表**，不得自行换算或编造（例如不得写"中断 20～60 分钟"这类表中没有的区间）。
`severity.level`（**精确判定**）按下列规则确定：
1. 描述里**有量化数据** → 直接对照上表命中定级，写该档名（如"较大事故"）；
2. 描述里**没有量化数据** → **必须写 `尚未成立`**；上游判定作为「初判等级」保留在 `preliminary` 里，**不得丢弃**。
**禁止**：编造描述里没有的数字；用"按可能后果推断""估计为""大致属于"这类**无依据**的措辞定级。
（注：**有依据的上游判定 ≠ 编造**——上游判定必须原样保留在 `preliminary`，不得覆盖、也不得改写成"信息不足"。）

**（一·补）定级采用「填 metrics → 初判 → 精确判定 → 触发修正」四步式**：

**第零步 · 填 `severity.metrics`（四项指标逐一，**共 4 行、顺序固定**）**
- `name` 四选一：死亡人数 / 重伤人数 / 直接经济损失 / 连续中断行车；
- `value`：**描述里给出的**该项数值；**没给出就写「未提供」**——**不得留空、不得编造**；
- `level`：该指标**单独**对照基准表落在哪一档；**`value` 为「未提供」→ 必须写「待核实」**。
- 阈值列**由代码渲染**，你不要重述阈值。

**第一步 · 初判（`severity.preliminary`）**
- 上游已有明确等级（非"未知"/"信息不足"）→ **必须沿用**为初判等级，**不得改写**；
- 上游也无 → `preliminary.level` 填 `无法初判`。
- `confidence`：高 / 中 / 低（反映依据强度）；`basis`：一句话写清初判依据（上游判定 ＋ 描述里的信号）。
- ⚠️ **初判是"保守推断"，不是国标量化判定** —— 其依据是**同类事件的极端危险性**
  （如隧道 / 地下 / 密闭空间 + 人员被困 → 按更重处置），用途是**定响应规模与处置力度**，
  **不得**表述成"符合 7.2 第X档"。**严禁**用"按可能后果推断""基于定性风险评估"
  这类**主观措辞**作为 `severity.level`（精确判定）的依据。

**第二步 · 精确判定（`severity.level`）**
- 描述**有量化数字** → 逐条对照基准表，**命中即写该档名**（如"较大事故"），并**覆盖初判**；
- **四项指标全无** → 写 `尚未成立`，并在 `tiers` 里逐条写"未命中（缺哪项数字）"。
  此种情形代码会渲染成 **"四项定级指标均缺失，无法对照国家标准进行精确分级"**
  ＋ **"保守初判等级：X"** ＋ **"⚠️ 此为保守推断，非国家标准量化判定"** ——
  你只需把 `metrics` 四项如实填「未提供 / 待核实」即可。
- **部分指标已有** → **只使用已有指标**对照；缺失的照实写「未提供」，
  代码会把它们列入 **"待核实项"** 并附国家标准阈值。
- ⚠️ **不得在缺数字时给出第二个等级**——那会让读者不知道该按哪个处置。

**第三步 · 触发修正（`severity.correction`）**
- 一句话写清："**核实哪些数字、达到什么区间后，按 7.2 改判为哪一档**"。

（`basis` 只允许依据描述中已出现的事实，**不得引入描述未提及的数字**。）

（二）必须输出响应级别与报告义务（`event.response`）
- `level`：I / II / III / IV
- **★ 与事故等级 1:1 对应（v8.26，硬规则）**：`level` 必须与**事故等级**严格对应，
  **不得跳级、不得错配** —— **特别重大 → Ⅰ级；重大 → Ⅱ级；较大 → Ⅲ级；一般 → Ⅳ级**。
  （描述无量化数字、只能给"保守初判"时，按**保守初判的等级**取对应响应级别。）
  代码会按该映射**校验并覆盖**，不一致会告警 —— 请一开始就填对。
- `authority`：**必须与 `level` 绑定，不得自行推断**（依据：《国家城市轨道交通运营突发事件应急预案》4.1）
  - I 级 / II 级 → `事发地省级人民政府`
  - III 级 / IV 级 → `事发地城市人民政府`
- `report_deadline`：按规程写具体时限

（三）必须覆盖四个维度（`dimensions`），缺一不可
① `evacuation`：疏散路径、集合点、弱势群体（老人/儿童/残障/受伤人员）优先原则
② `shutdown`：是否关闭出入口/车站、是否区段或线路停运，`basis` 引用具体条款
③ `reporting`：报告对象、时限、报告格式
④ `crowd_control`：引用 GB/T 38707 14.2.15 的具体措施（客流控制点、改变扶梯走向、
   回形线路等），有几条列几条

（四）步骤优先级（`steps[].action_type` 六选一）
1. 人身安全（救人、疏散弱势群体）
2. 切断危险源（挡水、排水、断电、隔离）
3. 关键设备（信号、供电、通信）
4. 运营调整（停运、改线、客流管控）
5. 信息报告（上报、对外通告）
6. 恢复善后
步骤顺序必须按此优先级排，**不允许低优先级步骤排在高优先级步骤前面**。
★ 防汛 / 水淹类事件中，"挡水 / 排水"必须：落在**先期处置**、**不晚于第 5 步**、
  并在 `parallel_with` 里写上救人/疏散步骤的 n。
  理由：水不挡，后续救人、疏散、保设备都会在更深的积水里做。

（五）阶段与时限（`steps[].stage` + `steps[].deadline_text`）
- `stage` 四选一：先期处置（0–3 分钟） / 现场处置（3–15 分钟） / 扩大响应（15–60 分钟） / 恢复善后（1 小时后）
- `deadline_text` 必须写"目标 X 分钟内完成"，**不得只写"立即"**

（六）并行必须显式标注（`steps[].parallel_with`）
同时发生的事件（积水倒灌、设备故障、列车迫停、乘客拥挤受伤）**不得强行拉成线性顺序**。
可同时进行的步骤，必须在 `parallel_with` 里列出对方步骤的 `n`（没有则写 []）。

（七）**未定级**（`severity.level` 为 `尚未成立`，或为"信息不足…"）时必须给出升级预案（`escalation`）
- `applicable` 必须为 true
- `triggers`：满足任一条件即升级（写出阈值，如"重伤10人以上""连续中断6小时以上"）
- `extra_steps`：升级后需要追加的动作（**独立列表，不计入 steps 的步数**）

**★ 升级到哪一级：由阈值决定，不是「当前级别 +1」（v8.26）**
1. 触发条件命中哪一档事故标准，就升级到**该档对应的响应级别**：
   **特别重大 → Ⅰ级；重大 → Ⅱ级；较大 → Ⅲ级；一般 → Ⅳ级**。
   ⚠️ **反例（明确禁止）**：当前 Ⅳ 级时，把"死亡≥30 人"写成"升级为 **Ⅲ** 级" ——
   那是**特别重大**事故，正确目标是 **Ⅰ 级**；写成 Ⅲ 级会**严重漏响应**。
2. **目标级别必须严格高于当前级别**。目标等于或低于当前级别的触发条件**不要写** ——
   那不是"升级"，是**无操作**（会让读者以为有事可做）。代码会丢弃这类条目并告警。
3. **当前已是 Ⅰ 级** → `triggers` 写 `[]`（**不存在更高级别**）；
   代码会渲染成"**已达最高响应级别**"。此时"事态扩大"的正确表述是
   「**报请省级人民政府 / 国务院提高应对层级**」，**不是**"升级响应级别"。

（八）输出前自查（逐条核对，任一条不满足就**改好再输出**）
1. 本事件是否涉及**水淹 / 积水**？若涉及："挡水 / 排水"是否已在**先期处置**、不晚于第 5 步、
   `parallel_with` 是否已指向救人/疏散步骤？——这是本类事件最容易犯的错，必须逐字确认。
2. `steps` 合计是否 **≤ 15 步**？超出则合并同类动作，不要靠加步数堆内容。
3. 每一步是否都有 `deadline_text`（"目标 X 分钟内完成"）？
4. 可同时进行的步骤是否都填了 `parallel_with`？
5. `severity.level` 为 `尚未成立`（或"信息不足…"）时，`escalation.applicable` 是否为 true 且 `triggers`/`extra_steps` 非空？
6. **每个 `action` 是否只含一个动作**？"挡水 / 救治 / 疏散"的**首分句**是否就是该动作本身
   （而不是被写在"前往现场视察""搜集事件信息"等步骤的第 2 个分句里）？
7. 每一步是否都写了 `precondition` 与 `resources`？（写了"无"也算写了，**不能空着**）
8. 【八环节】**逐项**过一遍了没有？第 6 环节（疏散 / 医疗救护）是否落在 **先期处置 / 现场处置**？
9. **时序矛盾**检查：是否存在"未断电就进区间""未处置危险源就靠近施救""未施救就送医"？
10. 【混合场景】有环境诱因时，`composite.conflicts` 是否真找出了**规程间的冲突**？
    `command.groups` 的 `direction`/`strategy` 是否**没有**写成逐步操作、没有点名个人？

（九）每步单一动作原则
每个 `action` **只描述一个主要动作**。
**禁止**用"同时""并""在…过程中"把两个**不同优先级**的动作写进同一个 `action`。
若场景确实需要同时做两件事，必须**拆成两个独立步骤**，并用 `parallel_with` 互相声明并行。

（十）关键动作必须独立成首句
以下三类动作若出现，**必须是该步骤 `action` 的第一个分句**（即第一个「；」之前）：
- 挡水 / 排水：防洪板、沙包、挡水、排水设施、潜水泵
- 救治 / 送医：救护车、施救、救助、救治、送医
- 疏散：疏散、撤离、引导
**反例（明确禁止）**：
  "值班站长前往现场视察评估，同时指派员工携带防洪板、沙包实施挡水" ✗
  → 必须拆成两步：
     步骤A："值班站长前往现场视察评估"；
     步骤B："指派员工携带防洪板、沙包实施挡水"。

（十一）关键动作不可遗漏
若本事件涉及下列情形，**必须至少有一个步骤以该动作为首分句**：
- 涉及水淹 / 积水 → 至少一个挡水 / 排水步骤
- 涉及人员伤亡（受伤 / 重伤 / 死亡）→ 至少一个救治 / 送医步骤
- 涉及疏散 / 大客流 → 至少一个疏散步骤
缺少该步骤时，**不要用别的动作"顺带提及"，必须单独列一步**。

（十二）不要用"步骤N"引用其他步骤
`action` 与 `fallback[].action` 正文里**一律禁止出现"步骤N"式的交叉引用**。
如需表达"处理完 A 后进入 B"，改用文字描述（如"完成搜索后按本方案对应程序处理"）。
理由：步骤会经排序/合并重新编号，正文里写死的编号会随之失效、指向错误步骤。

（十三）复合事件必须显式拆解
本类事件往往是**多种险情叠加**，不得只讲一种。必须在 `event.composite` 里写清：
- `risks`：本事件**同时包含的几类风险**——逐条列出，**不要合并成一句**
- `interaction`：这些风险**如何相互放大**（如"脱轨阻断行车 → 区间乘客滞留 → 客流积压进一步拖慢救援"）
`steps` 仍按优先级给出**一条**可执行主线；`composite` 只负责说清"多险并发"的结构，不替代 steps。

（十四）硬性先后必须用 `depends_on` 声明
若某一步**不做完前置就不能做**（不是"通常接着做"，而是**硬先后**），必须在 `depends_on` 里写出前置步骤的 `n`。
典型必须声明的情形：
- **"进入区间/轨道/隧道" 依赖 "隔离牵引电流"**（电未断，人不能进）；
- **"送医/转运" 依赖 "现场施救"**（人没救就谈不上送）；
- **"恢复行车" 依赖 "确认区间无人、无障碍、安全装置已拆除"**。
约束：`depends_on` 只写**真正的硬先后**；不得引用不存在的步骤号、不得引用自身、**不得成环**。
代码会据此重排（依赖优先于优先级顺序），并校验悬空/自环/环。

（十五）危险源处理原则
若事件涉及**持续危险源**，必须安排**至少一个"处理危险源"的独立步骤**，排在阶段一或阶段二：
- 火灾 / 爆炸 → 「使用灭火器 / 消防设施扑救」「启动消防喷淋」「隔离可燃物」
- 持械袭击 → 「配合公安控制 / 隔离行凶者」「封锁行凶者所在区域」
- 有毒气体泄漏 → 「隔离气体源」「关闭相关阀门」
- 带电设备事故 → 「隔离电源」
- 列车相撞 / 脱轨 → 「阻止后续列车进入」「隔离相关区段电源」

**禁止只处理后果（疏散 / 救治 / 报告 / 排烟），不处理危险源本身** —— 危险源不除，后果会持续产生。
若场景里**不存在持续危险源**（如"乘客突发疾病"），此约束**不适用**。

（十六）召唤外部力量的归类与位置
"召唤消防 / 公安 / 救护"是**处置动作**（消防来灭火、公安来控制行凶者、救护来救治伤员），
其 `action_type` **必须**是"人身安全"或"切断危险源"，**不得**标成"信息报告"。
"信息报告"**仅**用于"向调度 / 主管部门报告事件情况"这类**内部通报**。
凡事件**需要外部力量**（火灾 / 爆炸 / 袭击 / 有毒气体，或描述里明确"消防 / 公安 / 救护未到场"），
**必须**安排一条"召唤外部力量"的**独立**步骤，排在**阶段一**（先期处置），不得拖到扩大响应之后。

（十七）"做法要点"（`how_to` 字段）
每一步**必须**写 `how_to` —— **2 到 4 个动作点**，说明"这一步包含哪几件具体的事"，用 ①②③④ 分隔。

**粒度要求**（这是本方案的关键分界线）：
- 比 `action` **细一档**，但**不写"按键 / 话术 / 逐字稿"**（那是下游"个人 Agent"层的事）；
- 例：`action="通过车站广播宣布疏散车站"` → `how_to="① 广播内容避免引起恐慌；② 同步开启所有闸机；③ 关停扶梯并派人引导楼梯口；④ 通知站内租户"`
- 例：`action="使用灭火器扑救起火部位"` → `how_to="① 就近取灭火器；② 从上风向接近；③ 火势超出可控范围立即撤离"`
**禁止**把 `how_to` 写成 `action` 的复述（同一句话换个说法）。
**禁止**编造规程里没有的操作；不确定时写「按 XX 规程执行」。

（十八）岗位分类
每步的 `role` 必须**同时**标出 `role_category`，**只能**取以下四类**之一**：
- **一线执行** —— 列车司机、驾驶员、站务员、车站员工
- **调度指挥** —— 行车调度员、系统调度员、值班调度员
- **车站管理** —— 值班站长、值班经理、事故处理主任
- **后勤安保** —— 公安、消防、医疗、维修人员

并列岗位跨类时，取**主导**该步的那一类（如"值班站长安排车站员工…"记 **车站管理**）。
升级预案 `escalation.extra_steps` 的每条**也要**写 `role_category`（同为四类之一；**不写** `how_to`）。

（十九）每步必须写「前置条件」与「所需资源」，并做**时序矛盾自查**（v8.24）

**（1）`precondition`（前置条件）** —— 执行本步**开始之前**必须已经成立的条件，用**文字**写：
- 写具体前提，如"牵引电流已隔离""危险源已确认并控制""防洪板已就位"；**确实无前提就写"无"**（不能空着）。
- ★ **不得**在这里写步骤号（如"步骤3已完成"）—— 需要**硬先后**请用 `depends_on`（见约束十四）。
- 两者**并存、互不替代**：`depends_on` 是**步骤引用**（渲染成"前置：需先完成 步骤N"），
  `precondition` 是**执行前提的文字描述**。存在硬先后时，**两者都要写**。

**（2）`resources`（所需资源）** —— 本步需要的物资 / 设备 / 人力，**写具体**：
- 如"潜水泵 2 台、沙包 20 只、4 人"；**确实不需要就写"无"**（不能空着）。
- 不要写"相关设备""必要的物资"这类**没有信息量**的措辞。

**（3）时序矛盾自查（强制）** —— 输出前**逐对**检查步骤先后，下列"先后颠倒"**一律禁止**：

| 禁止的写法 | 正确顺序 |
|---|---|
| 未隔离牵引电流，就"人员进入区间 / 轨道 / 隧道" | **先断牵引电流，后人进** |
| 未挡水 / 排水，就"进入积水的车站 / 区间作业" | **先挡水排水，后人进** |
| 未处置危险源（灭火 / 隔离气体源 / 控制行凶者），就"靠近现场施救" | **先处置危险源，后靠近施救** |
| 未现场施救，就"送医 / 转运" | **先施救，后送医** |
| 未确认区间无人 / 无障碍，就"恢复行车" | **先确认清空，后恢复行车** |

凡存在上述先后关系，**必须同时**：
① 在后者的 `depends_on` 里写上前者的 `n`；
② 在后者的 `precondition` 里用文字重述该前提。
**只写其中一项不算合规** —— `depends_on` 供代码重排，`precondition` 供现场人员判读。

（二十）宏观指挥层：耦合风险链、冲突消解、专业组方向（v8.25）

本方案是**双层**的：顶部「作战简报」供**指挥员**看宏观，下部「详细执行方案」供**一线**照着做。
`event.composite` 与 `event.command` 是**简报层的数据源**，必须填写：

**（1）耦合风险链推演 —— `composite.chains[]`**
不要只罗列险情，必须写出**推演链**："谁 + 谁 → 推出什么风险"：
- `from`：参与耦合的**两个或以上**要素（主事件 / 环境诱因 / 次生事件，写名称）；
- `to`：**推演出的风险**——是**尚未发生**的，不是已发生的次生事件；
- `why`：机理，一句话。
- 例：`from=["暴雨","信号故障"], to="列车追尾", why="降级运行下制动距离延长、追踪间隔被压缩"`
- 至少 1 条；确为单一险情、无耦合时可写 `[]`。

**（2）处置冲突与协同 —— `composite.conflicts[]`**
多险并发时，**两套规程的要求常常互相打架**。必须显式找出**冲突点**并给出**协同策略**：
- 典型：暴雨/积水要求"关闭车门、切断电源"防触电，疏散却要求"打开车门清人"；
  灭火要求"打开排烟"，防毒烟扩散却要求"关闭防火卷帘"。
- `conflict` 写清**哪两条要求冲突**；`strategy` 写**怎么同时满足**（给出优先序与前提条件）。
- **找不到冲突就写 `[]`** —— 但多险并发时务必认真找，**这是本层最有价值的部分**。

**（3）专业组总方向 —— `event.command.groups[]`**
按**专业职能组**（**不是**按具体岗位）给出宏观方向，`group` **只能**四选一：
- **综合协调与指挥调度** —— 统筹全局、跨组联动、响应级别动态调整
- **现场抢险与风险控制** —— 切断危险源、防次生灾害、保障抢险安全
- **乘客疏散与医疗救护** —— 保障生命安全、防拥挤踩踏、检伤分类
- **信息发布与运营调整** —— 防信息混乱、公交接驳、按规定时限上报
写作要求：`direction` 与 `strategy` 是**给指挥员看的发力方向**，
**不得**写成逐步操作、不得点名具体个人、不得写工具型号——那些在下层 `steps` 里。

⚠️ **简报层不得重复详案层内容**：`chains` / `conflicts` / `command.groups` 里
**不要**出现"步骤N"式引用，也不要复述 `steps[].action` 原文。

{SCHEMA_SPEC}"""

    # ---- 调用 + 解析：失败重试 1 次，再失败降级为纯文本（第一步链路，未改动）----
    # 注意：**「解析失败」与「渲染失败」是两种完全不同的失败**——前者怪模型输出，
    # 后者是**代码缺陷**（JSON 合法却渲染崩）。必须分开记录，否则日志会把人引错方向。
    last_text = ""
    render_error = None
    for attempt in (1, 2):
        try:
            response = llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt + (RETRY_SUFFIX if attempt == 2 else "")}],
                temperature=0.2
            )
            last_text = response.choices[0].message.content or ""
        except Exception as e:
            print(f"⚠️ 方案生成失败：{e}")
            return f"""⚠️ 大模型服务暂不可用，以下为本地检索到的原始规程资料：

【事件等级】{severity}

【图谱事实】
{kg_context}

【规程原文】
{rag_context}"""

        obj = _extract_json(last_text)
        if obj is not None:
            try:
                md, warns = _render_markdown(obj, event_profile)
                if attempt == 2:
                    logging.warning("[json] 第 1 次输出解析失败，重试成功")
                for w in warns:
                    logging.warning("[json] 渲染警告：%s", w)
                return md
            except Exception as e:
                render_error = e
                logging.warning("[json] **渲染失败**（attempt=%d；JSON 合法，渲染器抛异常 → 代码缺陷）：%s",
                                attempt, e)
                logging.warning("[json] %s", traceback.format_exc())
                continue                      # 不再走下面那句"不是合法 JSON"

        logging.warning("[json] 第 %d 次输出不是合法 JSON（len=%d）", attempt, len(last_text))

    if render_error is not None:
        logging.warning("[json] 渲染器两次均抛异常（**代码缺陷，不是模型问题**）：%s", render_error)
        return (f"⚠️ **方案渲染失败（代码缺陷，非模型问题）**：{render_error}\n\n"
                f"以下为模型原始输出（**JSON 原文，未经渲染**，内容未丢）：\n\n{last_text}")

    logging.warning("[json] 两次均未产出合法 JSON，降级返回模型原始输出（内容未丢，未经结构化渲染）")
    return last_text
