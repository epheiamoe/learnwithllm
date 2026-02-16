import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 需要修复的部分 - while 循环体内的代码需要缩进
# 找到 generate() 函数中的 try: while iteration < max_iterations: 部分

old_pattern = '''        try:
            while iteration < max_iterations:
            iteration += 1
            tool_calls_dict = {}

            # 调用LLM获取回复
            for chunk in llm_service.chat_completion(
                current_messages, stream=True, tools=tools
            ):'''

new_pattern = '''        try:
            while iteration < max_iterations:
                iteration += 1
                tool_calls_dict = {}

                # 调用LLM获取回复
                for chunk in llm_service.chat_completion(
                    current_messages, stream=True, tools=tools
                ):'''

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)
    print("Fixed first indentation")
else:
    print("Pattern 1 not found")

# 修复其他缩进问题 - 需要将 while 循环内的所有代码缩进一级
# 但这是一个复杂的任务，让我采用不同的方法

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
