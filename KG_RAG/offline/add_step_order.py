import json
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "@Lz2430747005"
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def main():
    # 1. 读取parsed_records.jsonl（含有step字段的结构化数据）
    with open("output/parsed_records.jsonl", "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"共读取 {len(records)} 条记录")

    # 2. 按 parent_section（章节）分组，组内按 step 排序
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in records:
        section = r.get("parent_section") or "未知章节"
        # 只保留有明确step号的记录
        if r.get("step"):
            try:
                step_num = int(r["step"])
                grouped[section].append((step_num, r))
            except (ValueError, TypeError):
                continue

    # 3. 为每个章节内的相邻步骤建立 NEXT_STEP 关系
    total_links = 0
    skipped_steps = 0   # 被前缀过滤器跳过的步骤数（可观测性，便于核对过滤效果）
    with driver.session() as session:
        for section, steps in grouped.items():
            # 按步骤号排序
            steps.sort(key=lambda x: x[0])
            
            # 关键改动：同一章节内，步骤号相同时只保留第一条
            unique_steps = []
            seen = set()
            for step_num, record in steps:
                if step_num not in seen:
                    unique_steps.append((step_num, record))
                    seen.add(step_num)

            # 过滤：动作文本过于相似（前缀相同）的跳过
            filtered_steps = []
            for step_num, record in unique_steps:
                action = record["action_text"]
                # 如果和前一条动作的前10个字相同，视为同一表格的子问题，跳过
                if filtered_steps:
                    prev_action = filtered_steps[-1][1]["action_text"]
                    if action[:10] == prev_action[:10]:
                        skipped_steps += 1
                        continue
                filtered_steps.append((step_num, record))

            # 对过滤后的步骤建立 NEXT_STEP 关系
            for i in range(len(filtered_steps) - 1):
                step_curr = filtered_steps[i][1]
                step_next = filtered_steps[i+1][1]
                
                action_curr = step_curr["action_text"]
                action_next = step_next["action_text"]
                
                session.run("""
                    MERGE (a1:Action {name: $action1})
                    MERGE (a2:Action {name: $action2})
                    MERGE (a1)-[r:NEXT_STEP {
                        section: $section,
                        step_from: $step_from,
                        step_to: $step_to
                    }]->(a2)
                """, 
                    action1=action_curr, 
                    action2=action_next,
                    section=section,
                    step_from=step_curr["step"],
                    step_to=step_next["step"]
                )
                total_links += 1

    print(f"✅ 共建立 {total_links} 条 NEXT_STEP 关系")
    print(f"（前缀过滤器跳过了 {skipped_steps} 个步骤）")
    driver.close()

if __name__ == "__main__":
    main()