"""
Stub para emergentintegrations (não disponível no PyPI)
Substituir por OpenAI ou outro provedor LLM em produção.
"""

from typing import Any, List, Optional


class UserMessage:
    def __init__(self, content: str = "", **kwargs):
        self.content = content or kwargs.get("text", "")


class SystemMessage:
    def __init__(self, content: str):
        self.content = content


class LlmChat:
    def __init__(
        self,
        provider: Any = None,
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
        system_message: Optional[str] = None,
    ):
        self.provider = provider or ("openai", "gpt-4")
        self.model = self.provider[1] if isinstance(self.provider, tuple) else "gpt-4"
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message

    def with_model(self, *args, **kwargs) -> "LlmChat":
        if args:
            provider = args[0]
            return LlmChat(provider, self.api_key, self.session_id, self.system_message)
        return self

    async def send_message(self, msg: UserMessage) -> str:
        return "AI stub: Configure OpenAI API key para usar agentes IA."

    async def chat(self, messages: List[Any]) -> str:
        return "AI stub: Configure OpenAI API key para usar agentes IA."

    async def stream(self, messages: List[Any]):
        yield "AI stub: Configure OpenAI API key para usar agentes IA."

    def text(self, content: str) -> UserMessage:
        return UserMessage(content=content)
