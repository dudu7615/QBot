"""心知天气查询与本地缓存。"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from modules.Logger import logger
from plugin.Weather_d.SqlCache import Cache, WeatherType

ROOT: Path = Path(__file__).parent
CONFIG_FILE: Path = ROOT / "config.yaml"

WEATHER_NOW_URL: str = "https://api.seniverse.com/v3/weather/now.json"
WEATHER_DAILY_URL: str = "https://api.seniverse.com/v3/weather/daily.json"
_REQUEST_TIMEOUT: float = 5.0
_MIN_INTERVAL_SECONDS: float = 1.05
_MAX_ATTEMPTS: int = 3


class WeatherConfig(BaseModel):
    """心知天气配置。

    Attributes:
        pubKey: 公钥，仅用于控制台展示，运行时可缺省。
        privKey: 私钥（请求用）。
    """

    pubKey: str = ""
    privKey: str


def _load_config() -> WeatherConfig:
    """读取并校验天气插件配置。

    Returns:
        校验后的配置对象。

    Raises:
        SystemExit: 文件缺失或内容不合法。
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            raw: object = yaml.safe_load(file)
    except FileNotFoundError:
        logger.error(f"配置文件不存在: {CONFIG_FILE}")
        raise SystemExit(1)

    try:
        return WeatherConfig.model_validate(raw)
    except ValidationError as exc:
        logger.error(f"天气插件配置不合法: {CONFIG_FILE}\n{exc}")
        raise SystemExit(1)


_config: WeatherConfig = _load_config()
_last_request_at: datetime = datetime.now()
_request_lock: asyncio.Lock = asyncio.Lock()
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """返回模块级复用的 AsyncClient。"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)
    return _client


async def close() -> None:
    """关闭共享的 HTTP 客户端（进程退出时调用）。"""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def _throttle() -> None:
    """限制两次上游请求的最小间隔，避免触发心知天气的频率限制。"""
    global _last_request_at
    async with _request_lock:
        elapsed: float = (datetime.now() - _last_request_at).total_seconds()
        if elapsed < _MIN_INTERVAL_SECONDS:
            await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        _last_request_at = datetime.now()


async def _request_json(url: str, params: dict[str, str]) -> dict[str, object] | None:
    """请求天气接口并返回 JSON。

    Args:
        url: 接口地址。
        params: 查询参数（key 会自动补上）。

    Returns:
        JSON 字典；失败时返回 None。
    """
    query: dict[str, str] = {"key": _config.privKey, **params}

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await _throttle()
        try:
            response: httpx.Response = await _get_client().get(url, params=query)
            if response.is_success:
                payload: object = response.json()
                if isinstance(payload, dict):
                    return payload
                logger.warning(f"天气接口返回格式异常: {payload!r}"[:200])
            else:
                logger.warning(
                    f"天气接口返回 {response.status_code}: {response.text[:200]}"
                )
        except Exception as exc:
            logger.warning(f"请求天气接口失败（第 {attempt} 次）: {exc}")

    return None


def _first_result(payload: dict[str, object]) -> dict[str, object] | None:
    """取出响应中的第一条 results。"""
    results: object = payload.get("results")
    if not isinstance(results, list) or not results:
        return None
    first: object = results[0]
    return first if isinstance(first, dict) else None


async def getTodayWeather(cityName: str) -> str:
    """查询实时天气。

    Args:
        cityName: 城市名。

    Returns:
        格式化的天气文本；失败时返回提示语。
    """
    cache: Cache | None = Cache.getByPath(cityName, WeatherType.today)
    if cache:
        return cache.detal

    payload: dict[str, object] | None = await _request_json(
        WEATHER_NOW_URL,
        {"location": cityName, "language": "zh-Hans", "unit": "c"},
    )
    result: dict[str, object] | None = _first_result(payload) if payload else None
    if result is None:
        logger.error(f"获取天气信息失败: {cityName}")
        return "获取天气信息失败"

    location: object = result.get("location")
    now: object = result.get("now")
    if not isinstance(location, dict) or not isinstance(now, dict):
        logger.error(f"天气响应结构异常: {payload}")
        return "获取天气信息失败"

    detail: str = (
        f"城市: {location.get('path', cityName)}\n"
        f"天气: {now.get('text', '')} {now.get('temperature', '')}℃\n"
    )
    Cache.addCache(cityName, detail, WeatherType.today)
    return detail


async def getFutureWeather(cityName: str) -> str:
    """查询未来几天天气预报。

    Args:
        cityName: 城市名。

    Returns:
        格式化的预报文本；失败时返回提示语。
    """
    cache: Cache | None = Cache.getByPath(cityName, WeatherType.future)
    if cache:
        return cache.detal

    payload: dict[str, object] | None = await _request_json(
        WEATHER_DAILY_URL,
        {
            "location": cityName,
            "language": "zh-Hans",
            "unit": "c",
            "start": "0",
            "days": "4",
        },
    )
    result: dict[str, object] | None = _first_result(payload) if payload else None
    if result is None:
        logger.error(f"获取天气预报失败: {cityName}")
        return "获取天气信息失败"

    location: object = result.get("location")
    daily: object = result.get("daily")
    if not isinstance(location, dict) or not isinstance(daily, list):
        logger.error(f"天气预报响应结构异常: {payload}")
        return "获取天气信息失败"

    lines: list[str] = [f"城市: {location.get('path', cityName)}"]
    for day in daily:
        if not isinstance(day, dict):
            continue
        lines.append(
            f"{day.get('date', '')}: \n"
            f"{day.get('text_day', '')} {day.get('low', '')}~{day.get('high', '')}℃\n"
            f"{day.get('wind_direction', '')}, {day.get('wind_speed', '')}m/s, "
            f"{day.get('wind_scale', '')}级\n"
            f"降雨: {day.get('rainfall', '')}\n"
        )

    detail: str = "\n".join(lines)
    Cache.addCache(cityName, detail, WeatherType.future)
    return detail
