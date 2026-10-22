import json
import os
import re
import glob
from FlagEmbedding import FlagModel
import chromadb

# 用仓库里那份本地权重，与 online/main.py 的 load_encoder() 同一目录：
# 建库与查询必须用同一个模型，否则向量不在同一空间里。
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "models", "bge-base-zh-v1.5")


# 步骤号允许小数与字母后缀：AIEP10 等文档把流程图节点写成 "2.1"，只认整数会漏掉
# 全库 565 个 procedure_step 里的 99 个（实测：整数正则覆盖 466，放宽后 565）。
STEP_IN_TITLE_RE = re.compile(r"-步骤(\d[\d.]*[a-z]?)$")
STEP_IN_CONTENT_RE = re.compile(r"步骤：(\d[\d.]*[a-z]?)[；;]")


def step_of(chunk):
    """步骤号（字符串），取不到则空串。

    procedure_step 切片没有 step 字段，但号在两个地方带着：title 结尾
    「…-步骤9」或 content 前缀「步骤：9；行动：…」。online/main.py 的
    search_rag_full 用它排序并标注 "[步骤N]"，所以要写进 metadata。
    非步骤切片返回 ""（Chroma 不接受 None；空串在查询侧为假值，不会误标）。
    查询侧用 .isdigit() 判断，非整数号（"2.1"）会排到最后，不会崩。
    """
    m = STEP_IN_TITLE_RE.search(chunk.get("title") or "")
    if not m:
        m = STEP_IN_CONTENT_RE.match(chunk.get("content") or "")
    return m.group(1) if m else ""


def main():
    # 1. 加载本地 BGE 模型
    print("正在加载本地 BGE 模型...")
    model = FlagModel(
        MODEL_DIR,
        query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：",
        use_fp16=False,   # 与 online/main.py 的 load_encoder() 对齐（CPU 上 fp16 无意义）
    )
    print("✅ 模型加载完成！")

    # 2. 初始化本地 Chroma 向量库
    client = chromadb.PersistentClient(path="chroma_db")
    try:
        client.delete_collection("emergency_rag")
    except:
        pass
    collection = client.create_collection(
        name="emergency_rag",
        metadata={"hnsw:space": "cosine"}
    )

    # 3. 遍历 04_jsonl 文件夹下所有的 jsonl 文件
    jsonl_folder = r"long_data\JSON"  # 👈 改成这样，注意前面的 r 不要漏
    all_files = glob.glob(os.path.join(jsonl_folder, "*.jsonl"))

    if not all_files:
        print(f"❌ 在 {jsonl_folder} 里没找到 jsonl 文件，请检查文件夹位置！")
        return

    print(f"共找到 {len(all_files)} 个切片文件，开始向量化...")

    count = 0
    for file_path in all_files:
        file_name = os.path.basename(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                chunk = json.loads(line)

                text = chunk.get("text") or chunk.get("content") or ""
                if not text.strip():
                    continue

                chunk_id = chunk.get("chunk_id") or chunk.get("id") or f"{file_name}_{count}"

                vector = model.encode(text).tolist()
                collection.add(
                    ids=[str(chunk_id)],
                    embeddings=[vector],
                    documents=[text],
                    metadatas=[{
                        "source_file": file_name,
                        "section": chunk.get("section", ""),
                        "doc_name": chunk.get("doc_name", file_name),
                        "version": chunk.get("version", ""),
                        "step": step_of(chunk),
                    }]
                )

                count += 1
                if count % 200 == 0:
                    print(f"已处理 {count} 条...")

    print(f"✅ RAG向量库构建完成！共存入 {count} 条切片，文件夹：chroma_db")

if __name__ == "__main__":
    main()