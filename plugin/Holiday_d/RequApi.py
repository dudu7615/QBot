from datetime import date, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, StrictInt
from sqlmodel import Session, delete

from modules.Logger import logger
from plugin.Holiday_d.SqlCache import Cache, _engine

HOLIDAY_YEAR_URL = "https://timor.tech/api/holiday/year"
_REQUEST_TIMEOUT = 10.0
_MAX_ATTEMPTS = 3


class HolidayEntry(BaseModel):
    """接口返回的单条假期记录。

    Attributes:
        name: 假期名称。
        date: 日期（YYYY-MM-DD）。
        holiday: 是否为假期；False 表示调休补班。
    """

    model_config = ConfigDict(strict=True)

    name: str
    date: date
    holiday: bool


class HolidayYearResponse(BaseModel):
    """``/api/holiday/year`` 的响应体。

    Attributes:
        code: 业务状态码，0 表示成功。
        holiday: 日期字符串到假期记录的映射。
    """

    model_config = ConfigDict(strict=True)

    code: StrictInt
    holiday: dict[str, HolidayEntry] = Field(default_factory=dict)


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
            # 接口的年份在路径里，不是查询参数
            response: httpx.Response = httpx.get(
                f"{HOLIDAY_YEAR_URL}/{year}/",
                timeout=_REQUEST_TIMEOUT,
            )
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                continue

            parsed: HolidayYearResponse = HolidayYearResponse.model_validate_json(
                response.content
            )
            if parsed.code != 0:
                last_error = f"code={parsed.code}"
                continue

            records = [
                (
                    entry.name,
                    datetime(entry.date.year, entry.date.month, entry.date.day),
                    entry.holiday,
                )
                for entry in parsed.holiday.values()
            ]
            # 接口可能忽略年份参数而返回当前年数据，写入前必须核对
            if any(day.year != year for _, day, _ in records):
                last_error = "响应年份与请求年份不一致"
                continue
            return records
        except (ValidationError, ValueError) as exc:
            last_error = f"响应结构异常: {exc}"
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

    if not records:
        # 空数据不代表「这一年没有假期」，保留已有缓存而不是整体替换成空
        logger.error(f"{target_year} 年节假日数据为空，保留现有缓存")
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


def ensure_cache_fresh() -> bool:
    """确保持久化缓存覆盖当前年份。

    缓存缺失或未覆盖当前年份时触发一次刷新。

    Returns:
        缓存已覆盖当前年份时为 True；刷新失败时返回 False，
        调用方应据此决定是否在下次请求时重试。
    """
    today: date = date.today()
    cached: datetime | None = Cache.getCachedYear()
    if cached is not None and cached.year == today.year:
        return True
    return refresh_cache(today.year)
