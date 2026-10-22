import json
import os
import time
from openai import OpenAI

# ========== 请在这里填入你的 API Key ==========
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com"
)

def normalize_batch(entities_batch):
    prompt = f"""你是轨道交通知识图谱专家。请对以下实体列表进行标准化和同义词合并。
原则：
1. 合并指代同一事物的实体（如'列车司机'和'司机'合并为'司机'）。
2. 保留最规范、最完整的标准名称。
3. 如果实体本身已经标准或无需合并，保持原样。
输出严格的JSON格式，key是原始实体，value是标准化后的实体名，不要输出任何其他解释。

实体列表：
{json.dumps(entities_batch, ensure_ascii=False)}
"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={'type': 'json_object'},
        temperature=0.1
    )
    return json.loads(response.choices[0].message.content)

def main():
    input_path = "output/all_entities.txt"
    output_path = "output/alias_map.json"
    
    # 读取之前解析出的实体列表
    with open(input_path, "r", encoding="utf-8") as f:
        all_entities = [line.strip() for line in f if line.strip()]
    
    alias_map = {}
    batch_size = 50  # 每批50个，防止超长报错
    
    print(f"共 {len(all_entities)} 个实体，将分 {(len(all_entities)-1)//batch_size + 1} 批处理")
    
    for i in range(0, len(all_entities), batch_size):
        batch = all_entities[i:i+batch_size]
        print(f"正在处理第 {i+1} ~ {i+len(batch)} 个实体...")
        try:
            result = normalize_batch(batch)
            alias_map.update(result)
        except Exception as e:
            print(f"批次出错: {e}，等待5秒重试...")
            time.sleep(5)
            try:
                result = normalize_batch(batch)
                alias_map.update(result)
            except Exception as e2:
                print(f"重试依然失败: {e2}，跳过该批次")
        
        time.sleep(1)  # 避免请求过快被限流
        
    # 保存归一化映射表
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alias_map, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 归一化完成！共处理 {len(alias_map)} 个实体映射，保存至 {output_path}")

if __name__ == "__main__":
    main()
