import json
import os

def parse_line(line):
    """解析单行数据，返回结构化字典"""
    parts = line.strip().split('\t')
    
    # 如果不足9列，说明这行有问题，跳过
    if len(parts) < 9:
        return None
    
    # 前8列直接取值
    record_id = parts[0].strip()
    role = parts[1].strip()
    action_text = parts[2].strip()
    condition = parts[3].strip()
    doc_name = parts[4].strip()
    parent_section = parts[5].strip()
    page = parts[6].strip()
    version = parts[7].strip()
    remark = parts[8].strip()
    
    # 解析第9列的【备注】
    entities = []
    logic_relation = ""
    condition_detail = ""
    step = ""
    modal = ""
    boundary = ""
    parent_item = ""
    
    if "【备注：" in remark:
        # 去掉【备注：和结尾的】
        inner = remark.replace("【备注：", "").rstrip("】")
        # 按中文分号拆成一条条
        items = inner.split("；")
        for item in items:
            item = item.strip()
            if item.startswith("实体="):
                entities = [e.strip() for e in item.replace("实体=", "").split("、") if e.strip()]
            elif item.startswith("逻辑关系="):
                logic_relation = item.replace("逻辑关系=", "").strip()
            elif item.startswith("条件="):
                condition_detail = item.replace("条件=", "").strip()
            elif item.startswith("步骤="):
                step = item.replace("步骤=", "").strip()
            elif item.startswith("模态="):
                modal = item.replace("模态=", "").strip()
            elif item.startswith("边界冲突="):
                boundary = item.replace("边界冲突=", "").strip()
            elif item.startswith("父条目="):
                parent_item = item.replace("父条目=", "").strip()
    
    return {
        "record_id": record_id,
        "role": role,
        "action_text": action_text,
        "condition": condition,
        "doc_name": doc_name,
        "parent_section": parent_section,
        "page": page,
        "version": version,
        "entities": entities,
        "logic_relation": logic_relation,
        "condition_detail": condition_detail,
        "step": step,
        "modal": modal,
        "boundary": boundary,
        "parent_item": parent_item,
        "raw_text": line.strip()
    }


def main():
    input_path = r"short_data\short_sentence.txt"
    output_jsonl = "output/parsed_records.jsonl"
    output_entities = "output/all_entities.txt"
    
    # 确保输出目录存在
    os.makedirs("output", exist_ok=True)
    
    # 读取所有行
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = [line for line in f if line.strip()]
    
    print(f"📄 共读取到 {len(lines)} 行数据")
    
    parsed_records = []
    all_entities = set()
    failed_lines = []
    
    for idx, line in enumerate(lines):
        result = parse_line(line)
        if result is None:
            failed_lines.append((idx+1, line.strip()[:50]))
            continue
        parsed_records.append(result)
        # 收集所有实体（去重）
        for ent in result["entities"]:
            all_entities.add(ent)
    
    # 写入JSONL（每条一行）
    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for record in parsed_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    # 写入所有去重后的实体列表
    with open(output_entities, 'w', encoding='utf-8') as f:
        for ent in sorted(all_entities):
            f.write(ent + '\n')
    
    # 打印统计信息
    print(f"✅ 成功解析 {len(parsed_records)} 条记录")
    print(f"✅ 提取到 {len(all_entities)} 个不重复实体")
    print(f"✅ 解析结果保存至: {output_jsonl}")
    print(f"✅ 实体列表保存至: {output_entities}")
    
    if failed_lines:
        print(f"\n⚠️ 有 {len(failed_lines)} 行解析失败:")
        for line_no, content in failed_lines[:5]:
            print(f"   第{line_no}行: {content}...")


if __name__ == "__main__":
    main()