from dataclasses import dataclass
from datetime import datetime, timedelta
from httpx import AsyncClient
from modules.Logger import logger
from modules import Urls


@dataclass
class AccessToken:
    access_token: str
    expires_in: datetime


async def getAccessToken(appId: str, appSecret: str, client: AsyncClient) -> AccessToken | None:
    url = Urls.getAppAccessToken
    headers = {"Content-Type": "application/json"}
    data = {"appId": appId, "clientSecret": appSecret}
    response = await client.post(url, headers=headers, json=data)
    if response.status_code == 200:
        resp_json = response.json()
        logger.info(f"获取AccessToken成功: {response.json()["access_token"]}")
        return AccessToken(
            access_token=resp_json.get("access_token"),
            expires_in=datetime.now()
            + timedelta(
                seconds=int(resp_json.get("expires_in")) - 30
            ),  # -30 to keep it usable and reget on time
        )
    else:
        logger.warning(f"获取AccessToken失败: {response.status_code} - {response.text}")
        return None
