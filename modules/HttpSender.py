import httpx
from datetime import datetime
from modules import AutoAuth, Urls, Config, Types
from modules.Logger import logger
from typing import Union

client = httpx.AsyncClient(timeout=10.0)

token: AutoAuth.AccessToken = AutoAuth.AccessToken("", datetime(1970, 1, 1))


async def sendText2Person(
    message: str, recievedMessage: Types.MessageData, to: str
) -> None:
    global token
    url = Urls.sendMessage2Person.format(to)
    if token.expires_in < datetime.now():
        for _ in range(5):
            token_ = await AutoAuth.getAccessToken(
                Config.config["appId"], Config.config["clientSecret"]
            )
            if token_:
                break
        else:
            logger.error("Failed to get access token")
            return
        token = token_

    headers = {"Authorization": f"QQBot {token}", "Content-Type": "application/json"}
    data: dict[str, Union[str, int]] = {
        "content": message,
        "msg_type": 0,
        "msg_id": recievedMessage["d"]["id"],
        "event_id": recievedMessage["id"],
    }
    resq = None
    for _ in range(3):
        resq_ = await client.post(url, json=data, headers=headers)
        if resq_.status_code == 200:
            resq = resq_
            break
    else:
        if resq is not None:
            logger.error(f"发送消息失败: {resq.status_code} - {resq.text["message"]}")
        else:
            logger.error("发送消息失败: 无法建立连接")
        return

    logger.info(f"发送消息成功: {resq.json()}")
