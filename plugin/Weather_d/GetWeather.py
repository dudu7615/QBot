from modules.Logger import logger
from modules.HttpSender import client
from plugin.Weather_d.SqlCache import Cache, WeatherType
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import asyncio

ROOT = Path(__file__).parent
with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
    _config = yaml.safe_load(f)
    key: str = _config["privKey"]
_lastCheck = datetime.now()

async def getTodayWeather(cityName: str) -> str:
    global _lastCheck

    cache = Cache.getByPath(cityName)
    if cache:
        return cache.detal

    for _ in range(3):
        try:
            pramas = {
                "key": key,
                "location": cityName,
                "language": "zh-Hans",
                "unit": "c"
            }

            # 防止请求过快
            while datetime.now() - _lastCheck < timedelta(seconds=1.05):
                await asyncio.sleep(1)
            _lastCheck = datetime.now()

            response = await client.get(f"https://api.seniverse.com/v3/weather/now.json",
                                        params=pramas, timeout=5)
            if response.status_code == 200:
                resp = response.json()
                detal = (f"城市: {resp['results'][0]['location']['path']}\n"
                         f"天气: {resp['results'][0]['now']['text']} {resp['results'][0]['now']['temperature']}℃\n")
                Cache.addCache(cityName, detal, WeatherType.today)
                return detal
        except Exception as e:
            logger.warning(f"尝试获取天气信息失败: {e}")
            await asyncio.sleep(1)
    logger.error(f"获取天气信息失败: {cityName}")
    return "获取天气信息失败"