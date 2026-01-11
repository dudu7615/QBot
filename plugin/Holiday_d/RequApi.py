from plugin.Holiday_d.SqlCache import Cache
from modules.HttpSender import httpx
from modules.Logger import logger
from datetime import datetime

def updataCache():
    url = "https://timor.tech/api/holiday/year"
    for _ in range(3):
        try:
            resp = httpx.get(url, timeout=10)
            if resp.status_code == 200:
                reply = resp.json()
                if reply["code"] == 0:
                    for _, holiday in reply["holiday"].items():
                        Cache.addCache(holiday["name"], datetime.strptime(holiday["date"], "%Y-%m-%d"), holiday["holiday"])
                    logger.info("获取节假日信息成功")
                    return
        except Exception as e:
            logger.warning(f"尝试获取节假日信息失败，错误信息：{e}")
            continue
    logger.error("获取节假日信息失败，请检查网络连接")
    return None

def checkAndUpdata():
    cachedYear = Cache.getCachedYear()
    if cachedYear is None or cachedYear.year != datetime.now().year:
        updataCache()
   