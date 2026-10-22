# -*- coding: utf-8 -*-
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(BASE_DIR, "offline", "historical_cases.json")
OUTPUT = os.path.join(BASE_DIR, "offline", "historical_cases_clean.json")

# ==================== 要删除的案例 ====================
DELETE_IDS = {
    "case_058",  # 研究论文，无处置动作
    "case_060",  # 与case_003重复（郑州7·20）
    "case_061",  # 与case_016重复（广州8号线受电弓）
    "case_072",  # 与case_001重复（北京昌平线追尾）
    "case_080",  # 与case_002重复（上海10号线追尾）
    "case_082",  # 与case_024重复（上海9号线持刀伤人）
}

# ==================== severity_level 修正 ====================
SEVERITY_FIX = {
    "case_007": "一般事故",   # 原"大事故"（1人死亡，应为一般事故）
    "case_014": "较大事故",   # 原"险性事故"（列车冲突脱轨）
    "case_015": "较大事故",   # 原"特别重大事故"（损失1831万，应为较大事故）
    "case_025": "较大事故",   # 原"大事故"（1死2伤）
    "case_026": "较大事故",   # 原"大事故"（1死3伤）
    "case_027": "较大事故",   # 原"大事故"（1死1伤）
    "case_028": "一般事故",   # 原"大事故"（无伤亡）
    "case_047": "较大事故",   # 原"大事故"（中断2小时+）
}

def main():
    print(f"读取文件：{INPUT}")
    with open(INPUT, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    print(f"原始案例数：{len(cases)}\n")

    cleaned = []
    deleted_count = 0
    fixed_count = 0

    for case in cases:
        cid = case.get("case_id", "")

        # 1. 删除
        if cid in DELETE_IDS:
            print(f"  ❌ 删除 {cid} — {case.get('event_type', '')}")
            deleted_count += 1
            continue

        # 2. 修正 severity_level
        if cid in SEVERITY_FIX:
            old = case.get("severity_level", "")
            new = SEVERITY_FIX[cid]
            case["severity_level"] = new
            print(f"  ✏️  修正 {cid} — {old} → {new}")
            fixed_count += 1

        cleaned.append(case)

    # 3. 输出到新文件
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ 处理完成")
    print(f"   删除：{deleted_count} 个案例")
    print(f"   修正：{fixed_count} 个案例的 severity_level")
    print(f"   最终：{len(cleaned)} 个案例")
    print(f"   输出：{OUTPUT}")
    print(f"{'='*50}")
    print(f"\n下一步：")
    print(f"   1. 把 historical_cases_clean.json 重命名为 historical_cases.json")
    print(f"   2. 运行 python offline\\build_cases.py 重新入库")

if __name__ == "__main__":
    main()