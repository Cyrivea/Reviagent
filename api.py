from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import os, json
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from langchain_core.tools import tool
import subprocess
from fastapi.middleware.cors import CORSMiddleware
from rag import add_document, search
from fastapi import FastAPI, UploadFile, File
import tempfile
from rag import add_document, search
from datetime import datetime
import pytz

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
client = ZhipuAI(api_key=os.getenv("API_KEY"))

from fastapi.responses import FileResponse

@app.get("/")
def index():
    return FileResponse("index.html")
@app.get("/logo.png")
def logo():
    return FileResponse("logo.png")

from fastapi.responses import FileResponse

@app.get("/")
def index():
    return FileResponse("index.html")

@app.get("/logo.png")
def logo():
    return FileResponse("logo.png")


@app.get("/CascadiaMono.ttf")
def font():
    return FileResponse("CascadiaMono.ttf") 

@tool
def calculate(expression: str) -> str:
    """计算数学表达式"""
    try:
        return str(eval(expression))
    except:
        return "计算失败"

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
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前最新的北京时间（包含日期、具体时间以及星期几），当用户询问时间、日期或今天星期几时调用。",
            "parameters": {
                "type": "object",
                "properties": {} # 注册无需参数
            }
        }
    }
]

@tool
def get_current_time() -> str:
    """获取当前最新的北京时间以及全球主要城市（纽约、伦敦、东京、柏林）的精准当地时间"""
    try:
        # 定义需要展示的时区字典
        regions = {
            "中国 (北京)": "Asia/Shanghai",
            "美国 (纽约)": "America/New_York",
            "英国 (伦敦)": "Europe/London",
            "日本 (东京)": "Asia/Tokyo",
            "德国 (柏林)": "Europe/Berlin"
        }
        
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        result_lines = ["当前全球主要时刻对照："]
        
        for name, tz_str in regions.items():
            tz = pytz.timezone(tz_str)
            now = datetime.now(tz)
            time_str = now.strftime(f"%Y-%m-%d %H:%M:%S {weekdays[now.weekday()]}")
            result_lines.append(f"- **{name}**：{time_str}")
            
        return "\n".join(result_lines)
    except Exception as e:
        return f"获取全球时间失败: {str(e)}"   

tools_map = {
    "calculate": calculate,
    "get_current_time": get_current_time  # 注册新工具
}

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

@app.post("/chat")
def chat(req: ChatRequest):
    docs = search(req.message)
    context = "\n".join(docs) if docs else ""
    system_prompt = """你是Reviagent，用户的私人AI助手。
    用户信息：
    - 姓名：王翊帆，英文名Cyrivea
    - 身份：西安工业大学软件工程大一学生
    - 目标：成为AI应用开发/Agent工程师，未来去杭州或上海
    - 技术栈：Python、FastAPI、LangChain、Agent开发

    注意：当你需要知道现在的精确时间或日期时，请务必调用 get_current_time 工具。
    """
    if context:
        system_prompt += f"\n\n参考以下资料回答问题：\n{context}"
        system_prompt += "\n- 格式要求：请务必使用 Markdown 格式输出。在回答时，要善于使用小标题、加粗、粗体列表（如 1. **标题**：内容）来分点阐述，保证结构清晰、易于阅读。"
    messages = [{"role": "system", "content": system_prompt}]
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
        "history": messages[1:]  
    }
    