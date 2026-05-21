from langchain_core.tools import tool
import os, json
from dotenv import load_dotenv
from zhipuai import ZhipuAI

load_dotenv()
client = ZhipuAI(api_key=os.getenv("API_KEY"))

@tool
def calculate(expression: str) -> str:
    """计算数学表达式"""
    try:
        return str(eval(expression))
    except:
        return "计算失败"
    
import subprocess

@tool
def run_python(code: str) -> str:
    """执行Python代码，返回输出结果"""
    print(f"\n--- AI想执行以下代码 ---\n{code}\n------------------------")
    confirm = input("确认执行？(y/n): ")
    if confirm != "y":
        return "用户取消了执行"
    
    result = subprocess.run(
        ["python3", "-c", code],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return result.stdout
    else:
        return f"错误：{result.stderr}"
    

tools_map = {"calculate": calculate, "run_python": run_python}

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式，比如 '1234*5678'",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"]
            }
        }
    },

    {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "执行Python代码并返回结果，适合需要编程解决的问题",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的Python代码"}
            },
            "required": ["code"]
            }
        }
    }
]

messages = [{"role": "system", "content": "你是用户的私人数学助手"}]
print("AI：我是你的私人数学工具")

while True:
    user_input = input("追问：")
    if user_input == "quit":
        break

    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=messages,
        tools=tools_schema
    )

    msg = response.choices[0].message

    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        func_name = tool_call.function.name
        func_args = json.loads(tool_call.function.arguments)
        result = tools_map[func_name].invoke(func_args)

        messages.append({"role": "assistant", "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": func_name,
                    "arguments": tool_call.function.arguments
                }
            }
        ]})
        messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})

        final = client.chat.completions.create(
            model="glm-4-flash",
            messages=messages
        )
        reply = final.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
    else:
        reply = msg.content
        messages.append({"role": "assistant", "content": reply})

    print(f"AI：{reply}")