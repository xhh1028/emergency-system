# -*- coding: utf-8 -*-
import os
import json
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
OUTPUT = os.path.join(BASE_DIR, "output", "new_docs_chunks.jsonl")


def extract_pdf_text(pdf_path):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    text = "\n".join([page.get_text() for page in doc])
    doc.close()
    return text


def extract_docx_text(docx_path):
    from docx import Document
    doc = Document(docx_path)
    parts = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    return "\n".join(parts)


def split_by_structure(text, doc_name):
    """按文档结构切分：优先按章/节/条款切，保留标题"""
    
    chunks = []
    
    # 判断文档类型，采用不同策略
    # 策略1：按"第X条"切（管理办法类）
    if re.search(r'第[一二三四五六七八九十百零\d]+条', text):
        # 按"第X条"切
        pattern = r'(第[一二三四五六七八九十百零\d]+条)'
        parts = re.split(pattern, text)
        # 合并：标题 + 内容
        current_title = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if re.match(r'^第[一二三四五六七八九十百零\d]+条$', part):
                current_title = part
            else:
                if len(part) > 30:
                    chunks.append({
                        "text": f"{current_title}\n{part}".strip(),
                        "section": current_title or "未分类"
                    })
                    current_title = ""
    
    # 策略2：按"一、二、三、"或"1. 2. 3." 切（应急预案类）
    elif re.search(r'^[一二三四五六七八九十]+、', text, re.MULTILINE):
        pattern = r'(^[一二三四五六七八九十]+、[^\n]*)'
        parts = re.split(pattern, text, flags=re.MULTILINE)
        current_title = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if re.match(r'^[一二三四五六七八九十]+、', part) and len(part) < 50:
                current_title = part
            else:
                if len(part) > 30:
                    chunks.append({
                        "text": f"{current_title}\n{part}".strip(),
                        "section": current_title or "未分类"
                    })
                    current_title = ""
    
    # 策略3：按"数字.数字"节切（标准/规范类）
    elif re.search(r'^\d+\.\d+\s', text, re.MULTILINE):
        pattern = r'(^\d+\.\d+\s+[^\n]{0,80})'
        parts = re.split(pattern, text, flags=re.MULTILINE)
        current_title = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if re.match(r'^\d+\.\d+\s', part) and len(part) < 100:
                current_title = part
            else:
                if len(part) > 30:
                    chunks.append({
                        "text": f"{current_title}\n{part}".strip(),
                        "section": current_title or "未分类"
                    })
                    current_title = ""
    
    # 策略4：兜底，按空行/段落切
    else:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if len(p.strip()) > 50]
        for i, para in enumerate(paragraphs):
            chunks.append({
                "text": para,
                "section": f"第{i+1}段"
            })
    
    # 过滤太短的切片
    chunks = [c for c in chunks if len(c["text"]) > 50]
    
    # 如果切片太长（>1500字），按400字再切一次
    final_chunks = []
    for chunk in chunks:
        if len(chunk["text"]) <= 1500:
            final_chunks.append(chunk)
        else:
            # 按400字切
            text = chunk["text"]
            for i in range(0, len(text), 400):
                sub = text[i:i+400]
                if len(sub) > 50:
                    final_chunks.append({
                        "text": sub,
                        "section": chunk["section"] + f" 第{i//400+1}段"
                    })
    
    # 加上元数据
    return [
        {
            "text": c["text"],
            "source_file": f"{doc_name}_chunks.jsonl",
            "section": c["section"],
            "doc_name": doc_name,
            "version": "2024"
        }
        for c in final_chunks
    ]


def main():
    os.makedirs(os.path.join(BASE_DIR, "output"), exist_ok=True)
    
    if not os.path.exists(DOCS_DIR):
        print(f"❌ docs 文件夹不存在：{DOCS_DIR}")
        return
    
    all_files = os.listdir(DOCS_DIR)
    print(f"共发现 {len(all_files)} 个文件\n")
    
    all_chunks = []
    
    for filename in all_files:
        filepath = os.path.join(DOCS_DIR, filename)
        
        if not (filename.endswith(".pdf") or filename.endswith(".docx")):
            print(f"⏭️  跳过（格式不支持）：{filename}")
            continue
        
        doc_name = os.path.splitext(filename)[0]
        print(f"正在处理：{filename}")
        
        try:
            if filename.endswith(".pdf"):
                text = extract_pdf_text(filepath)
            else:
                text = extract_docx_text(filepath)
            
            if len(text.strip()) < 100:
                print(f"  ⚠️ 提取文字不足100字，跳过")
                continue
            
            chunks = split_by_structure(text, doc_name)
            all_chunks.extend(chunks)
            print(f"  ✅ 生成 {len(chunks)} 条切片（共 {len(text)} 字）")
        
        except Exception as e:
            print(f"  ❌ 处理失败：{e}")
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
    
    print(f"\n{'='*50}")
    print(f"✅ 全部完成！共 {len(all_chunks)} 条切片")
    print(f"   输出：{OUTPUT}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()