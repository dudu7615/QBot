from dataclasses import dataclass
from datetime import datetime, timedelta
from modules.HttpSender import client
from modules.Logger import logger
from modules import Urls


@dataclass
class AccessToken:
    access_token: str
    expires_in: datetime


async def getAccessToken(appId: str, appSecret: str) -> AccessToken | None:
    url = Urls.getAppAccessToken
    headers = {"Content-Type": "application/json"}
    data = {"appId": appId, "clientSecret": appSecret}
    response = await client.post(url, headers=headers, json=data)
    if response.status_code == 200:
        logger.info(f"获取AccessToken成功: {response.json()}")
        resp_json = response.json()
        return AccessToken(
            access_token=resp_json.get("accessToken"),
            expires_in=datetime.now() + timedelta(seconds=resp_json.get("expiresIn")-30),  # -30 to keep it usable and reget on time
        )
    else:
        logger.error(f"获取AccessToken失败: {response.status_code} - {response.text}")
        return None
