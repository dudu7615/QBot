import httpx
from modules.Logger import logger
from plugin.AiChat_d.Types import ApiJson, ApiJson_Messages
from plugin.AiChat_d.Config import config
from plugin.AiChat_d.History import PersonHistory

client: httpx.AsyncClient = httpx.AsyncClient(timeout=60.0)

url = config["url"]


async def RequApi(messages: str, openId: str) -> str:
    logger.debug(f"RequApi called with openId: {openId}, messages: {messages}")
    history = PersonHistory(openId)

    payloda: ApiJson = {
        "model": config["model"],
        "messages": history.getHistory() + [{"role": "user", "content": messages}],
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.7,
        "max_tokens": 2048,
        "do_sample": True,
        "thinking": {"type": "disabled"},
    }

    headers = {
        "Authorization": f"Bearer {config['apiKey']}",
        # "Content-Type": "application/json",
    }
    logger.info(f"请求Glm openid: {openId}, 请求内容: {messages}")
    history.addHistory(
        ApiJson_Messages(
            role="user",
            content=messages,
        )
    )

    for _ in range(3):
        try:
            response = await client.post(url, headers=headers, json=payloda, timeout=60)
            if response.status_code == 200:
                aiReply = response.json()["choices"][0]["message"]["content"]
                history.addHistory(
                    ApiJson_Messages(
                        role="assistant",
                        content=aiReply,
                    )
                )
                logger.info(f"Glm: openid: {openId}, 回复内容: {aiReply}")
                return aiReply

        except Exception as e:
            logger.error(f"Glm 接口请求异常: {e}")

    return "抱歉，Glm接口请求失败，请稍后再试。"
