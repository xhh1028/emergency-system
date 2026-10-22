import json
import re

def load_role_mapping(path="online/role_mapping.json"):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def assign_tasks_to_roles(plan_text):
    """把完整方案按角色分类"""
    role_map = load_role_mapping()
    
    # 初始化4个角色的任务清单
    role_tasks = {role: [] for role in role_map.keys()}
    
    # 用正则从方案里提取所有 "执行岗位：XXX" 的行
    # 匹配格式：- **步骤N**：...\n  - 执行岗位：XXX
    step_pattern = r'\*\*步骤(\d+)\*\*[：:](.*?)(?=\*\*步骤|\Z)'
    steps = re.findall(step_pattern, plan_text, re.DOTALL)
    
    for step_num, step_content in steps:
        # 提取执行岗位
        role_match = re.search(r'执行岗位[：:]\s*(.+)', step_content)
        if not role_match:
            continue
        role_str = role_match.group(1).strip()
        
        # 找到这个岗位属于哪个角色
        for role, roles_list in role_map.items():
            for r in roles_list:
                if r in role_str:
                    action_match = re.search(r'\*\*步骤\d+\*\*[：:](.+?)(?=\n\s*-|\Z)', step_content, re.DOTALL)
                    action = action_match.group(1).strip() if action_match else step_content[:100]
                    
                    role_tasks[role].append({
                        "step_number": int(step_num),
                        "role_detail": role_str,
                        "action": action,
                        "full_content": step_content.strip()
                    })
                    break
    
    return role_tasks