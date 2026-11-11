"""AiChat 使用到的 OpenAI 兼容接口数据结构。"""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """一条对话消息。

    Attributes:
        role: system / user / assistant / tool。
        content: 消息文本。
    """

    role: str
    content: str


class ThinkingConfig(BaseModel):
    """是否启用思考模式。"""

    type: str = "disabled"


class ChatRequest(BaseModel):
    """对话请求体（OpenAI 兼容）。"""

    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = 0.7
    top_p: float = 0.7
    max_tokens: int = 2048
    do_sample: bool = True
    thinking: ThinkingConfig = Field(default_factory=ThinkingConfig)


class ChatChoiceMessage(BaseModel):
    """回复中的单条消息。"""

    role: str
    content: str


class ChatChoice(BaseModel):
    """回复中的一个候选。"""

    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str = ""


class ChatResponse(BaseModel):
    """对话响应体，只保留用到的字段。"""

    id: str = ""
    model: str = ""
    choices: list[ChatChoice] = Field(default_factory=list)
