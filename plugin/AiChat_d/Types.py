from typing import TypedDict


class ApiJson_Messages(TypedDict):
    role: str  # system, user, assistant, tool
    content: str


class ApiJson(TypedDict):
    model: str  # glm-4.5-flash
    messages: list[ApiJson_Messages]
    temperature: float  # 1
    max_tokens: int  # 65536
    stream: bool  # False
    thinking: dict[str, str]  # {"type": "enabled"|"disabled"}
    do_sample: bool  # True
    top_p: float  # 0.95


class ReplyJson_Choices_Message(ApiJson_Messages): ...


class ReplyJson_Choices(TypedDict):
    index: int
    message: ReplyJson_Choices_Message
    finish_reason: str


class ReplyJson(TypedDict):
    id: str
    object: str
    created: int
    model: str
    choices: list[ReplyJson_Choices]
    usage: dict[str, int]

    time: str
    role: str
    content: str
