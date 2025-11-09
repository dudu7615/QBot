from modules.HttpSender import client
from modules.Logger import logger
from plugin.GlmAi_d.Types import ApiJson, ApiJson_Messages
from plugin.GlmAi_d.Config import config
from plugin.GlmAi_d.History import PersonHistory

url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


async def RequApi(messages: str, openId: str) -> str:
    history = PersonHistory(openId)

    payloda: ApiJson = {
            "model": "GLM-4-Flash-250414",
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
                aiReply =  response.json()["choices"][0]["message"]["content"]
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