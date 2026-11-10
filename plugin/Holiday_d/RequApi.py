from datetime import date, datetime
from typing import Any

import httpx
from sqlmodel import Session, delete

from modules.Logger import logger
from plugin.Holiday_d.SqlCache import Cache, _engine

HOLIDAY_YEAR_URL = "https://timor.tech/api/holiday/year"
_REQUEST_TIMEOUT = 10.0
_MAX_ATTEMPTS = 3


def _fetch_year(year: int) -> list[tuple[str, datetime, bool]]:
    """拉取指定年份的假期数据。

    Args:
        year: 年份。

    Returns:
        (假期名, 日期, 是否为假期) 列表。

    Raises:
        RuntimeError: 重试后仍无法获取数据。
    """
    last_error: str = ""
    for _ in range(_MAX_ATTEMPTS):
        try:
            response: httpx.Response = httpx.get(
                HOLIDAY_YEAR_URL,
                params={"year": year},
                timeout=_REQUEST_TIMEOUT,
            )
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                continue

            payload: dict[str, Any] = response.json()
            if payload.get("code") != 0:
                last_error = f"code={payload.get('code')}"
                continue

            holidays: dict[str, Any] = payload.get("holiday") or {}
            records: list[tuple[str, datetime, bool]] = []
            for item in holidays.values():
                records.append(
                    (
                        str(item["name"]),
                        datetime.strptime(str(item["date"]), "%Y-%m-%d"),
                        bool(item["holiday"]),
                    )
                )
            return records
        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(f"获取 {year} 年节假日信息失败: {last_error}")


def refresh_cache(year: int | None = None) -> bool:
    """刷新指定年份的假期缓存。

    先清空该年份的旧数据再整体写入，避免累积重复行。

    Args:
        year: 年份，默认当前年份。

    Returns:
        是否刷新成功。
    """
    target_year: int = year if year is not None else date.today().year

    try:
        records: list[tuple[str, datetime, bool]] = _fetch_year(target_year)
    except RuntimeError as exc:
        logger.error(str(exc))
        return False

    year_start: datetime = datetime(target_year, 1, 1)
    year_end: datetime = datetime(target_year + 1, 1, 1)
    with Session(_engine) as session:
        session.exec(
            delete(Cache)
            .where(Cache.date >= year_start)  # type: ignore[arg-type]
            .where(Cache.date < year_end)  # type: ignore[arg-type]
        )
        for name, day, is_holiday in records:
            session.add(Cache(name=name, date=day, isHoliday=is_holiday))
        session.commit()

    logger.info(f"获取节假日信息成功: {target_year} 年共 {len(records)} 条")
    return True


def ensure_cache_fresh() -> None:
    """确保持久化缓存覆盖当前年份。

    缓存缺失或未覆盖当前年份时触发一次刷新。
    """
    today: date = date.today()
    cached: datetime | None = Cache.getCachedYear()
    if cached is None or cached.year != today.year:
        refresh_cache(today.year)
