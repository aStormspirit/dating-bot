"""Граф реплики: персонаж, проверка роли и один повтор через Abliteration."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from vk_bot.agent.prompt import system_prompt
from vk_bot.chat.session import _Session
from vk_bot.config import ABLIT_API_KEY, ABLIT_BASE_URL, ABLIT_MODEL, ABLIT_TIMEOUT

_CONTEXT_LIMIT = 24
_NUDGE = (
    "Ответь только следующей репликой персонажа. "
    "Не отказывайся от взрослого флирта между людьми 18+ и не говори, что ты модель."
)
_BREAKS_ROLE = (
    "as an ai",
    "language model",
    "i'm an ai",
    "i am an ai",
    "я языковая модель",
    "я нейросеть",
    "я искусственный интеллект",
    "как ии",
    "как искусственный интеллект",
)


class PersonaState(TypedDict):
    messages: list[BaseMessage]
    reply: str | None
    attempt: int
    broke_role: bool


def breaks_role(text: str) -> bool:
    """Модель вышла из персонажа и заговорила как ассистент."""
    low = text.lower()
    return any(marker in low for marker in _BREAKS_ROLE)


def history_messages(state: _Session) -> list[BaseMessage]:
    """Системная роль и последние реплики сессии, без своего хранилища графа."""
    assert state.persona is not None
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt(state))]
    for item in state.history[-_CONTEXT_LIMIT:]:
        content = item["content"]
        if item["role"] == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages


_model: ChatOpenAI | None = None
_graph = None


def _chat_model() -> ChatOpenAI:
    """Один клиент Abliteration на процесс. Размышление выключено, чтобы ответ пришёл сразу."""
    global _model
    if _model is None:
        _model = ChatOpenAI(
            model=ABLIT_MODEL,
            api_key=ABLIT_API_KEY,
            base_url=ABLIT_BASE_URL,
            temperature=0.9,
            max_tokens=80,
            timeout=ABLIT_TIMEOUT,
            max_retries=0,
            use_responses_api=False,
            reasoning_effort="none",
        )
    return _model


def _message_text(message: AIMessage) -> str:
    """Достаёт текст из строки или из списка частей ответа."""
    content = message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or ""
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


async def _speak(messages: list[BaseMessage]) -> tuple[str | None, bool]:
    """Просит модель ответить. Второй флаг — реплика сломала роль и её нельзя отдавать."""
    response = await _chat_model().ainvoke(messages)
    text = _message_text(response)
    if not text:
        return None, False
    if breaks_role(text):
        return None, True
    return text, False


async def persona(state: PersonaState) -> dict:
    """Первая реплика персонажа. Плохой ответ в историю графа не кладётся."""
    reply, broke = await _speak(state["messages"])
    return {"reply": reply, "broke_role": broke, "attempt": state["attempt"] + 1}


def check_role(state: PersonaState) -> Literal["nudge", "__end__"]:
    """Один повтор, если модель вышла из роли. Иначе реплика уже готова."""
    if state["broke_role"] and state["attempt"] < 2:
        return "nudge"
    return END


async def nudge(state: PersonaState) -> dict:
    """Добавляет уточнение к тем же сообщениям, без отбракованной реплики."""
    return {
        "messages": [*state["messages"], SystemMessage(content=_NUDGE)],
        "broke_role": False,
    }


async def retry(state: PersonaState) -> dict:
    """Вторая и последняя попытка после уточнения."""
    reply, broke = await _speak(state["messages"])
    return {"reply": reply, "broke_role": broke, "attempt": state["attempt"] + 1}


def get_graph():
    """Собирает граф один раз: персонаж, проверка роли, повтор, конец."""
    global _graph
    if _graph is None:
        graph = StateGraph(PersonaState)
        graph.add_node("persona", persona)
        graph.add_node("nudge", nudge)
        graph.add_node("retry", retry)
        graph.add_edge(START, "persona")
        graph.add_conditional_edges("persona", check_role, {"nudge": "nudge", END: END})
        graph.add_edge("nudge", "retry")
        graph.add_edge("retry", END)
        _graph = graph.compile()
    return _graph
