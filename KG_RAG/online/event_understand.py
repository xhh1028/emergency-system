# -*- coding: utf-8 -*-
import json
import os
import traceback

_SCENE_KEYS_CACHE = None


def _load_scene_keys():
    """读取**受控场景键**（只读 scene_chapter_map.json；缺失/损坏 → []，不崩）。

    仅供 prompt 里列词表用——让模型从现成的键里**选**，而不是自创词面。
    """
    global _SCENE_KEYS_CACHE
    if _SCENE_KEYS_CACHE is not None:
        return _SCENE_KEYS_CACHE
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "scene_chapter_map.json"),
                 os.path.join("online", "scene_chapter_map.json"),
                 "scene_chapter_map.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except OSError:
            continue
        except (ValueError, TypeError):
            _SCENE_KEYS_CACHE = []
            return _SCENE_KEYS_CACHE
        _SCENE_KEYS_CACHE = [k for k in (data or {}) if not str(k).startswith("_")]
        return _SCENE_KEYS_CACHE
    _SCENE_KEYS_CACHE = []
    return _SCENE_KEYS_CACHE


def understand_event(user_description, llm_client):
    """把用户的现场描述解析成结构化事件画像（支持复合事件 + 国标4等级）"""

    scene_block = "、".join(_load_scene_keys()) or "（场景词表加载失败，`scene_key` 请留空数组）"

    prompt = f"""你是轨道交通应急事件分析专家。请从用户描述中提取结构化信息。
严格输出JSON，格式：
{{
  "primary_event": {{
    "event_type": "主事件类型（**照实描述本次事件**，如'高架桥下仓库起火波及线路声屏障'；不要套用场景词表里的键）",
    "scene_category": "场景分类（站内/站外/列车/隧道/车辆段/露天段）",
    "severity_level": "事故等级（必须从下面4个国家标准等级中选一个）",
    "severity_reason": "判定依据。**有量化数据**时写清命中的国标档位；**无量化数据**时必须写明这是**保守初判**（依据同类事件的极端危险性），并注明**非国标量化判定**"
  }},
  "scene_key": ["从下面【场景词表】里**原样**选 1~3 个最贴切的键；选不出就写 []，不得自创、不得改写"],
  "secondary_events": [
    {{
      "event_type": "次生事件类型（如大客流、乘客被困、隧道水淹、通信中断等）",
      "trigger": "由什么触发（如'主事件导致'、'同时发生'）"
    }}
  ],
  "environmental_factors": ["环境诱因（天气/地质/时段等**外部条件**，如'暴雨红色预警'、'轨面湿滑'、'能见度低'、'早高峰'）；没有就写 []"],
  "potential_risks": ["**尚未发生但可能发生**的风险（如'二次脱轨'、'踩踏'、'触电'、'追尾'、'气体爆炸'）；没有就写 []"],
  "location": "发生位置",
  "involved_devices": ["涉及设备"],
  "involved_roles": ["涉及岗位"],
  "key_facts": ["关键事实点"],
  "matched_chapter": "最匹配的章节编号"
}}

【场景词表（`scene_key` 必须从这里**原样**取键，不得改写或自创；检索层按它定位规程）】
{scene_block}
- 选键看**事件的性质**，不要只看字面：如"高架桥下仓库起火波及线路"→`站外失火`；
  "隧道内边墙明火"→`隧道火灾`；"车站发现可疑爆炸物"→`恐吓事件`；"乘客心脏骤停"→`乘客突发疾病`。
- 允许同时选多个（复合事件）；**选不出贴切的就写 []**，硬凑比留空更糟。
- 注意区分：`event_type` **照实描述本次事件**（保留细节、可自由用词）；
  `scene_key` **必须原样用词表里的键**。两者不要互相替代，也不要为了对齐 key 而把 `event_type` 写笼统。

【事故等级判定标准（国标4选1，不得自创）】
依据《国家城市轨道交通运营突发事件应急预案》**7.2**（四维度：死亡人数 / 重伤人数 / 直接经济损失 / 连续中断行车）。
（注：伤亡人数与经济损失的四档门槛与《生产安全事故报告和调查处理条例》（国务院令第493号）**一致**；
  但 **493号令没有"连续中断行车"这个维度**——那是 7.2 特有的判据；
  且 7.2 的一般档经济损失带 **50 万元下限**，493号令没有。本表以 7.2 为准。）

1. 特别重大事故：
   - 死亡≥30人
   - 或重伤≥100人
   - 或直接经济损失≥1亿元
   （**7.2 此档不含"连续中断行车"维度** —— 中断再长也不会单独构成特别重大）

2. 重大事故：
   - 死亡10~29人
   - 或重伤50~99人
   - 或直接经济损失5000万~1亿元
   - 或连续中断行车24小时以上

3. 较大事故：
   - 死亡3~9人
   - 或重伤10~49人
   - 或直接经济损失1000万~5000万元
   - 或连续中断行车6小时以上24小时以下

4. 一般事故：
   - 死亡<3人
   - 或重伤<10人
   - 或直接经济损失50万元以上1000万元以下
   - 或连续中断行车2小时以上6小时以下

【判定规则】
1. 优先按"死亡人数"判定；无死亡按"重伤人数"；无伤亡按"直接经济损失"；无损失按"中断行车时间"。
2. **若用户描述中没有明确数据**（四项量化指标均缺失）→ 本判定**只能是"保守初判"**，
   依据是**同类事件的极端危险性**（**不得**使用"按可能后果推断""基于定性风险评估"
   这类**主观措辞**）：
   - 多人被困且环境持续恶化（如水位上涨、火势蔓延、氧气减少）→ 至少"较大事故"
   - 涉及隧道、地下空间、密闭空间的人员被困 → 至少"较大事故"
   - 已出现人员身体不适或受伤迹象（如"有人晕倒"、"有人受伤"）→ 至少"一般事故"
   - 需要紧急疏散大量人员（≥50人）→ 至少"较大事故"
   - 仅设备故障、无人员受影响 → "一般事故"
   ⚠️ **上述结论是"保守推断，非国家标准量化判定"** —— 用途是**确定响应规模与处置力度**，
   **不得**在 `severity_reason` 里写成"符合 7.2 第X档"。
   `severity_reason` 应写成："**保守初判**：依据同类事件的极端危险性（…），**非国标量化判定**"。
3. 事故等级必须从上面4个国家标准等级中选一个，
   不允许写"一类延误"、"二类延误"、"三级"、"紧急"、"严重"等非国标等级。

【复合事件识别】
1. primary_event 只写一个，是最核心、最先发生的事件。
2. secondary_events 写所有由主事件引发或同时发生的事件：
   - 火灾引发大客流 → 次生事件：大客流
   - 列车迫停引发乘客被困 → 次生事件：乘客被困
   - 暴雨引发隧道积水 → 次生事件：隧道水淹
   - 脱轨引发接触轨损坏 → 次生事件：设备故障
3. 如果只有一个事件，secondary_events 返回空数组 []。

【环境诱因 / 潜在风险（v8.25 新增，混合场景必需）】
- `environmental_factors` 收**外部条件**——天气、地质、时段、周边环境。
  它们是**放大器**：同样一起设备故障，暴雨天与晴天的处置完全不同。
  例："早高峰暴雨天气列车撞击异物" → `["暴雨", "轨面湿滑", "早高峰客流"]`
- `potential_risks` 收**尚未发生、但由本次事件推演出来的**风险（不是已经发生的事）。
  例：列车脱轨 → `["二次脱轨", "接触轨带电伤人", "后续列车追尾"]`
- **两者都不与 `secondary_events` 混用**：`secondary_events` 是**已经发生**的次生事件，
  `potential_risks` 是**还没发生**的推演风险。宁可分开写，不要合并。
- 没有就写 `[]`，**不要硬凑**。

【场景分类参考】
- 站内：车站公共区、设备房、站厅、站台
- 站外：站前广场、邻近建筑
- 列车：列车车厢内
- 隧道：区间隧道内
- 车辆段：车辆段/停车场
- 露天段：地面段/高架段

用户描述：{user_description}

只输出JSON，不要解释。"""

    try:
        response = llm_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是轨道交通应急事件分析专家，只输出JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={'type': 'json_object'}
        )
        result = json.loads(response.choices[0].message.content)

        # 兼容：如果模型返回旧结构，自动转成新结构
        if "primary_event" not in result and "event_type" in result:
            result = {
                "primary_event": {
                    "event_type": result.get("event_type", ""),
                    "scene_category": result.get("scene_category", ""),
                    "severity_level": result.get("severity_level", "一般事故"),
                    "severity_reason": result.get("severity_reason", "")
                },
                "secondary_events": [],
                "environmental_factors": result.get("environmental_factors", []),
                "potential_risks": result.get("potential_risks", []),
                "location": result.get("location", ""),
                "involved_devices": result.get("involved_devices", []),
                "involved_roles": result.get("involved_roles", []),
                "key_facts": result.get("key_facts", []),
                "matched_chapter": result.get("matched_chapter", "")
            }

        # 兼容：把旧等级映射成国标等级（防止大模型没改过来）
        LEVEL_MAP = {
            "一类延误": "一般事故",
            "二类延误": "一般事故",
            "三类延误": "一般事故",
            "轻伤事故": "一般事故",
            "险性事故": "较大事故",
            "大事故": "较大事故",
            "紧急": "较大事故",
            "严重": "较大事故",
        }
        primary = result.get("primary_event", {})
        old_level = primary.get("severity_level", "")
        if old_level in LEVEL_MAP:
            primary["severity_level"] = LEVEL_MAP[old_level]
            primary["severity_reason"] = (
                primary.get("severity_reason", "") +
                f"（原判定为'{old_level}'，已映射为国标'较大事故/一般事故'）"
            )
            result["primary_event"] = primary

        # v8.25：补齐可能缺失的列表字段 —— 下游按**固定键**读取（尤其「混合场景」判定
        # 依赖 `environmental_factors`/`potential_risks`），缺失会让提示**静默失效**。
        for _k in ("secondary_events", "environmental_factors", "potential_risks",
                   "involved_devices", "involved_roles", "key_facts"):
            _v = result.get(_k)
            if not isinstance(_v, list):
                result[_k] = [] if _v in (None, "") else [_v]

        return result

    except Exception as e:
        print(f"⚠️ 事件理解失败：{e}")
        traceback.print_exc()
        return {
            "primary_event": {
                "event_type": user_description,
                "scene_category": "未知",
                "severity_level": "一般事故",
                "severity_reason": "解析失败，使用默认等级"
            },
            "secondary_events": [],
            "environmental_factors": [],
            "potential_risks": [],
            "location": "未识别",
            "involved_devices": [],
            "involved_roles": [],
            "key_facts": [user_description],
            "matched_chapter": ""
        }