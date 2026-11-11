"""心知天气查询与本地缓存。"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, ValidationError

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


class WeatherLocation(BaseModel):
    """查询到的城市信息。"""

    name: str = ""
    path: str = ""


class WeatherNow(BaseModel):
    """实时天气。"""

    text: str = ""
    temperature: str = ""


class WeatherDay(BaseModel):
    """单日预报。"""

    date: str = ""
    text_day: str = ""
    low: str = ""
    high: str = ""
    wind_direction: str = ""
    wind_speed: str = ""
    wind_scale: str = ""
    rainfall: str = ""


class WeatherNowResult(BaseModel):
    """``now.json`` 的单条结果。"""

    location: WeatherLocation
    now: WeatherNow


class WeatherDailyResult(BaseModel):
    """``daily.json`` 的单条结果。"""

    location: WeatherLocation
    daily: list[WeatherDay] = Field(default_factory=list)


class WeatherNowResponse(BaseModel):
    """``now.json`` 响应体。"""

    results: list[WeatherNowResult] = Field(default_factory=list)


class WeatherDailyResponse(BaseModel):
    """``daily.json`` 响应体。"""

    results: list[WeatherDailyResult] = Field(default_factory=list)


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


async def _request_bytes(url: str, params: dict[str, str]) -> bytes | None:
    """请求天气接口并返回响应体。

    Args:
        url: 接口地址。
        params: 查询参数（key 会自动补上）。

    Returns:
        响应体字节；失败时返回 None。
    """
    query: dict[str, str] = {"key": _config.privKey, **params}

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await _throttle()
        try:
            response: httpx.Response = await _get_client().get(url, params=query)
            if response.is_success:
                return response.content
            logger.warning(
                f"天气接口返回 {response.status_code}: {response.text[:200]}"
            )
        except Exception as exc:
            logger.warning(f"请求天气接口失败（第 {attempt} 次）: {exc}")

    return None


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

    payload: bytes | None = await _request_bytes(
        WEATHER_NOW_URL,
        {"location": cityName, "language": "zh-Hans", "unit": "c"},
    )
    if payload is None:
        logger.error(f"获取天气信息失败: {cityName}")
        return "获取天气信息失败"

    try:
        parsed = WeatherNowResponse.model_validate_json(payload)
    except ValidationError as exc:
        logger.error(f"实时天气响应结构异常: {exc}")
        return "获取天气信息失败"

    if not parsed.results:
        logger.error(f"实时天气响应没有结果: {cityName}")
        return "获取天气信息失败"

    result: WeatherNowResult = parsed.results[0]
    detail: str = (
        f"城市: {result.location.path or cityName}\n"
        f"天气: {result.now.text} {result.now.temperature}℃\n"
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

    payload: bytes | None = await _request_bytes(
        WEATHER_DAILY_URL,
        {
            "location": cityName,
            "language": "zh-Hans",
            "unit": "c",
            "start": "0",
            "days": "4",
        },
    )
    if payload is None:
        logger.error(f"获取天气预报失败: {cityName}")
        return "获取天气信息失败"

    try:
        parsed = WeatherDailyResponse.model_validate_json(payload)
    except ValidationError as exc:
        logger.error(f"天气预报响应结构异常: {exc}")
        return "获取天气信息失败"

    if not parsed.results:
        logger.error(f"天气预报响应没有结果: {cityName}")
        return "获取天气信息失败"

    forecast: WeatherDailyResult = parsed.results[0]
    lines: list[str] = [f"城市: {forecast.location.path or cityName}"]
    for day in forecast.daily:
        lines.append(
            f"{day.date}: \n"
            f"{day.text_day} {day.low}~{day.high}℃\n"
            f"{day.wind_direction}, {day.wind_speed}m/s, "
            f"{day.wind_scale}级\n"
            f"降雨: {day.rainfall}\n"
        )

    detail: str = "\n".join(lines)
    Cache.addCache(cityName, detail, WeatherType.future)
    return detail
