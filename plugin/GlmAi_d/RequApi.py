from modules.HttpSender import client
from modules.Logger import logger
from plugin.GlmAi_d.Types import ApiJson, ApiJson_Messages
from plugin.GlmAi_d.Config import config

url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


async def RequApi(messages: str, openId: str) -> str:
    payloda: ApiJson = {
        "model": "glm-4.5-flash",
        "messages": [{"role": "user", "content": messages}],
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
    logger.info(f"请求数据: {payloda}")
    response = await client.post(url, headers=headers, json=payloda, timeout=60)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return "请求错误"
