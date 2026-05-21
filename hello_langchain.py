from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from typing import List, Optional, Any
from zhipuai import ZhipuAI
import os
from dotenv import load_dotenv

load_dotenv()

class ZhipuChatModel(BaseChatModel):
    api_key: str
    model: str = "glm-4-flash"

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        client = ZhipuAI(api_key=self.api_key)
        zhipu_messages = [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content} for m in messages]
        response = client.chat.completions.create(model=self.model, messages=zhipu_messages)
        content = response.choices[0].message.content
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    @property
    def _llm_type(self) -> str:
        return "zhipu"

llm = ZhipuChatModel(api_key=os.getenv("API_KEY"))
response = llm.invoke([HumanMessage(content="你好，用一句话介绍一下你自己")])
print(response.content)

from langchain_core.prompts import ChatPromptTemplate

from langchain_core.chat_history import InMemoryChatMessageHistory

history = InMemoryChatMessageHistory()

if __name__ == "__main__":
    while True:
        user_input = input("聊一聊：")
        if user_input == "quit":
            break
    
        history.add_user_message(user_input)
        response = llm.invoke(history.messages)
        history.add_ai_message(response.content)
    
        print(f"AI:{response.content}")