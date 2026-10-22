import json
import os
from neo4j import GraphDatabase

# ========== 请修改这里的密码 ==========
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "@Lz2430747005"  # 👈 把这个换成你 Neo4j 里实际设置的密码！
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def load_data():
    with open("output/alias_map.json", "r", encoding="utf-8") as f:
        alias_map = json.load(f)
    
    records = []
    with open("output/parsed_records.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return alias_map, records

def build_graph():
    alias_map, records = load_data()
    
    # 先建约束和索引
    with driver.session() as session:
        session.run("CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE")
        session.run("CREATE INDEX role_name_index IF NOT EXISTS FOR (n:Role) ON (n.name)")
        session.run("CREATE INDEX action_name_index IF NOT EXISTS FOR (n:Action) ON (n.name)")
        print("✅ Neo4j 约束和索引建立完成")

    count = 0
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        with driver.session() as session:
            for record in batch:
                role = alias_map.get(record["role"], record["role"])
                action = record["action_text"]
                condition = record.get("condition", "无")
                
                raw_entities = record.get("entities", [])
                std_entities = [e if e.isdigit() else alias_map.get(e, e) for e in raw_entities]
                
                session.run("""
                    MERGE (r:Role {name: $role})
                    MERGE (a:Action {name: $action})
                    MERGE (c:Condition {name: $condition})
                    MERGE (r)-[:EXECUTES]->(a)
                    MERGE (a)-[:REQUIRES]->(c)
                """, role=role, action=action, condition=condition)
                
                for ent in std_entities:
                    if ent != role and ent != action:
                        session.run("""
                            MERGE (e:Entity {name: $ent})
                            WITH e
                            MATCH (a:Action {name: $action})
                            MERGE (a)-[:INVOLVES]->(e)
                        """, ent=ent, action=action)
        
        count += len(batch)
        print(f"已处理 {count} / {len(records)} 条记录...")

    print(f"✅ 成功写入 {count} 条记录到 Neo4j！")
    driver.close()

if __name__ == "__main__":
    build_graph()