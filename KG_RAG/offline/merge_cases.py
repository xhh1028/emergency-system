# -*- coding: utf-8 -*-
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_FILE = os.path.join(BASE_DIR, "offline", "historical_cases.json")          # 原50个
NEW_FILE = os.path.join(BASE_DIR, "offline", "historical_cases_new.json")       # 新增25个
OUTPUT_FILE = os.path.join(BASE_DIR, "offline", "historical_cases_merged.json")

# 逐条映射（按案例内容判断）
# 格式：{原case_id: "国标等级"}
SEVERITY_MAP = {
    "case_001": "重大事故",   # 11人死亡
    "case_002": "一般事故",   # 无伤亡
    "case_003": "一般事故",   # 无伤亡
    "case_004": "较大事故",   # 6人死亡
    "case_005": "较大事故",   # 无伤亡，损失3836万
    "case_006": "一般事故",   # 无伤亡
    "case_007": "较大事故",   # 6人死亡
    "case_008": "一般事故",   # 研究案例
    "case_009": "较大事故",   # 1死+28伤
    "case_010": "重大事故",   # 14人死亡
    "case_011": "一般事故",   # 4轻伤
    "case_012": "较大事故",   # 4死1轻伤
    "case_013": "一般事故",   # 14人不适，无死亡
    "case_014": "一般事故",   # 无伤亡
    "case_015": "一般事故",   # 无伤亡
    "case_016": "一般事故",   # 无伤亡
    "case_017": "一般事故",   # 无伤亡
    "case_018": "一般事故",   # 1人死亡
    "case_019": "一般事故",   # 无伤亡
    "case_020": "一般事故",   # 无伤亡
    "case_021": "一般事故",   # 无伤亡
    "case_022": "重大事故",   # 102人骨折（重伤口径≥100）
    "case_023": "一般事故",   # 无伤亡
    "case_024": "一般事故",   # 停运1小时<2小时
    "case_025": "一般事故",   # 无伤亡
}

def main():
    with open(MAIN_FILE, 'r', encoding='utf-8') as f:
        main_cases = json.load(f)
    with open(NEW_FILE, 'r', encoding='utf-8') as f:
        new_cases = json.load(f)

    print(f"原案例：{len(main_cases)} 个")
    print(f"新增案例：{len(new_cases)} 个")

    start_num = len(main_cases) + 1
    converted = []
    for i, case in enumerate(new_cases):
        new_case = dict(case)
        old_id = case.get("case_id", f"case_{i+1:03d}")
        new_id = f"case_{start_num + i:03d}"

        # 映射等级，同时保留原始等级
        new_case["case_id"] = new_id
        new_case["original_level"] = case.get("severity_level", "")
        new_case["severity_level"] = SEVERITY_MAP.get(old_id, "一般事故")

        converted.append(new_case)

    merged = main_cases + converted
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"✅ 合并完成！共 {len(merged)} 个案例")
    print(f"   输出：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()