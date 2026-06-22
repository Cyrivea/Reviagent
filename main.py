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
from fastapi.responses import StreamingResponse
import asyncio
from ddgs import DDGS
from fastapi.responses import FileResponse
import json
PROFILE_FILE = "data/user_profile.json"



def load_profile() -> str:
    try:
        with open(PROFILE_FILE, "r") as f:
            data = json.load(f)
            return data.get("profile", "")
    except:
        return ""

def save_profile(profile: str):
    with open(PROFILE_FILE, "w") as f:
        json.dump({"profile": profile}, f, ensure_ascii=False)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
client = ZhipuAI(api_key=os.getenv("API_KEY"))



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

@tool
def search_web(query: str) -> str:
    """搜索网络获取实时信息，适合查询新闻、天气、最新事件等"""
    news_keywords = ['新闻', '动态', '最新', '今天', '事件', '发生', '价格', 
                     '天气', '股价', '近况', '怎么样', '情况', '破产', '裁员', 
                     '融资', '倒闭', '收购', '上市']
    is_news = any(kw in query for kw in news_keywords)
    
    try:
        with DDGS(timeout=5) as ddgs:
            if is_news:
                print(f"🚀 [Reviagent] 正在尝试高时效新闻搜索: {query}")
                results = list(ddgs.news(query, max_results=5, timelimit='w'))
            else:
                results = list(ddgs.text(query, max_results=5, timelimit='m'))
                
            if results:
                return "\n".join([f"{r['title']}: {r['body']}" for r in results])
    
    except Exception as e:
        if is_news:
            print(f"⚠️ [Reviagent] 新闻网络超时，立刻切换 24小时 网页检索兜底...")
            try:
                with DDGS(timeout=5) as ddgs:
                    results = list(ddgs.text(f"{query} 最新新闻", max_results=5, timelimit='d'))
                if results:
                    return "\n".join([f"{r['title']}: {r['body']}" for r in results])
            except:
                pass
        
        import traceback
        traceback.print_exc()
        return f"搜索失败，网络连接超时，请稍后重试。"
        
    return "没有找到相关结果"

@tool
def get_current_time() -> str:
    """获取当前最新的北京时间以及全球主要城市（纽约、伦敦、东京、柏林）的精准当地时间"""
    try:
       
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
                "properties": {} 
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索网络获取实时信息，适合查询新闻、天气、最新事件等",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    }
]


tools_map = {
    "calculate": calculate,
    "get_current_time": get_current_time,
    "search_web": search_web  
}

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

@app.post("/chat")
async def chat(req: ChatRequest):  # 【异步改造】加上 async
    try:
        docs = await asyncio.to_thread(search, req.message, n_results=3)
        context = "\n".join(docs) if docs else ""
    except:
        context = ""

    profile = load_profile()
    profile_section = f"\n用户信息：\n{profile}" if profile else ""

    system_prompt = f"""你是Reviagent，用户的私人AI助手，说话像claude一样简洁明了，不要有情绪。{profile_section}

工具使用规则：
- 涉及实时信息、新闻、天气、最新事件时，必须调用search_web工具
- 涉及数学计算时，调用calculate工具
- 用户追问或质疑某个事实时，必须重新调用search_web验证，不能依赖上下文记忆
- 如果搜索结果包含非中文内容，回答时自动翻译成中文
"""
    if context:
        system_prompt += f"\n\n参考以下资料回答问题：\n{context}"
        system_prompt += "\n- 格式要求：请务必使用 Markdown 格式输出。在回答时，要善于使用小标题、加粗、粗体列表（如 1. **标题**：内容）来分点阐述，保证结构清晰、易于阅读。"

    messages = [{"role": "system", "content": system_prompt}]
    messages += req.history
    messages.append({"role": "user", "content": req.message})

    async def stream_generator():
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=messages,
            tools=tools_schema
        )

        msg = response.choices[0].message
        func_name = None

        if msg.tool_calls:
            tool_call = msg.tool_calls[0]
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            yield f"data: {json.dumps({'type': 'tool', 'tool_name': func_name}, ensure_ascii=False)}\n\n"
            
            
            result = tools_map[func_name].invoke(func_args)

            messages.append({"role": "assistant", "tool_calls": [
                {"id": tool_call.id, "type": "function", "function": {"name": func_name, "arguments": tool_call.function.arguments}}
            ]})
            messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})

            final_stream = await asyncio.to_thread(
                client.chat.completions.create,
                model="glm-4-flash",
                messages=messages,
                stream=True  
            )
        
        
        else:
            final_stream = [{ "choices": [{ "delta": { "content": msg.content } }] }]

        
        reply = ""
        
        for chunk in final_stream:
            
            if isinstance(chunk, dict):
                content = chunk["choices"][0]["delta"].get("content", "")
            else:
                delta = chunk.choices[0].delta
                content = delta.content if hasattr(delta, 'content') and delta.content else ""
            
            if content:
                reply += content
                yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"


        messages.append({"role": "assistant", "content": reply})


        clean_history = []
        for m in messages:
            if m.get("role") in ["user", "assistant"] and m.get("content"):
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    continue  
                clean_history.append({"role": m["role"], "content": m["content"]})


        yield f"data: {json.dumps({'type': 'done', 'history': clean_history, 'tool_used': func_name}, ensure_ascii=False)}\n\n"
   
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

class ProfileRequest(BaseModel):
    profile: str

@app.post("/profile")
def set_profile(req: ProfileRequest):
    save_profile(req.profile)
    return {"status": "success", "message": "个人信息已更新"}

@app.get("/profile")
def get_profile():
    return {"profile": load_profile()}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """【补齐功能】完美对齐前端📎按钮，实现端到端文件上传 RAG 录入"""
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        chunks_count = await asyncio.to_thread(add_document, tmp_path, file.filename)
        
        os.unlink(tmp_path)
        return {"status": "success", "message": f"成功导入文档: {file.filename}（共分切成 {chunks_count} 块）"}
    except Exception as e:
        return {"status": "error", "message": f"导入失败: {str(e)}"}