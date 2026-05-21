from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import os, json
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from langchain_core.tools import tool
import subprocess
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
client = ZhipuAI(api_key=os.getenv("API_KEY"))

@tool
def calculate(expression: str) -> str:
    """计算数学表达式"""
    try:
        return str(eval(expression))
    except:
        return "计算失败"

tools_map = {"calculate": calculate}

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            }
        }
    }
]

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

@app.post("/chat")
def chat(req: ChatRequest):
    messages = [{"role": "system", "content": "你是一个数学助手"}]
    messages += req.history
    messages.append({"role": "user", "content": req.message})

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
            {"id": tool_call.id, "type": "function", "function": {"name": func_name, "arguments": tool_call.function.arguments}}
        ]})
        messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})

        final = client.chat.completions.create(model="glm-4-flash", messages=messages)
        reply = final.choices[0].message.content
    else:
        reply = msg.content

    messages.append({"role": "assistant", "content": reply})

    return {
        "reply": reply,
        "history": messages[1:]  # 去掉system message
    }