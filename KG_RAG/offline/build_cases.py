# -*- coding: utf-8 -*-
import json
import os
from FlagEmbedding import FlagModel
import chromadb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
CASE_FILE = os.path.join(BASE_DIR, "offline", "historical_cases.json")
EMBED_MODEL_DIR = os.path.join(BASE_DIR, "models", "bge-base-zh-v1.5")


def to_str(v):
    if isinstance(v, list):
        return " || ".join(str(x) for x in v if x)
    return str(v) if v else ""


def main():
    print("正在加载 BGE 模型...")
    model = FlagModel(
        EMBED_MODEL_DIR,
        query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：",
        use_fp16=False,
    )
    print("模型加载完成")

    print(f"正在读取案例文件：{CASE_FILE}")
    with open(CASE_FILE, 'r', encoding='utf-8') as f:
        cases = json.load(f)
    print(f"共读取 {len(cases)} 个案例")

    print("正在连接 Chroma...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection("historical_cases")
        print("已删除旧的 historical_cases collection")
    except Exception:
        pass

    collection = client.create_collection(
        name="historical_cases",
        metadata={"hnsw:space": "cosine"}
    )

    for i, case in enumerate(cases):
        text = " ".join([
            str(case.get("event_type", "")),
            str(case.get("event_category", "")),
            str(case.get("event_subcategory", "")),
            str(case.get("scene_category", "")),
            str(case.get("description", "")),
        ])
        vec = model.encode(text).tolist()

        collection.add(
            ids=[case.get("case_id", f"case_{i:03d}")],
            embeddings=[vec],
            documents=[str(case.get("description", ""))],
            metadatas=[{
                "event_category": to_str(case.get("event_category", "")),
                "event_subcategory": to_str(case.get("event_subcategory", "")),
                "event_type": to_str(case.get("event_type", "")),
                "scene_category": to_str(case.get("scene_category", "")),
                "severity_level": to_str(case.get("severity_level", "")),
                "actions_taken": to_str(case.get("actions_taken", "")),
                "outcome": to_str(case.get("outcome", "")),
                "lessons_learned": to_str(case.get("lessons_learned", "")),
                "deviation": to_str(case.get("deviation", "")),
                "source": to_str(case.get("source", "")),
            }]
        )

        if (i + 1) % 10 == 0:
            print(f"已处理 {i+1}/{len(cases)}")

    print(f"\n✅ 已入库 {len(cases)} 个案例")


if __name__ == "__main__":
    main()