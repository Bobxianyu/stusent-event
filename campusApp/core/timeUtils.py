"""北京时间与 Unix 秒的转换。"""

import re
import time
from datetime import datetime, timedelta, timezone

from campusApp.core.constants import (
  DATE_FORMAT,
  DATE_PATTERN,
  DATE_TIME_FORMAT,
  DATE_TIME_PATTERN,
  ERROR_VALIDATION,
  MAX_REPORT_DAYS,
  MAX_SUPPORTED_YEAR,
  MIN_REPORT_DAYS,
  MIN_SUPPORTED_YEAR,
  UTC_OFFSET_HOURS,
)
from campusApp.core.contracts import DomainError
from campusApp.core.validation import requireInteger


BEIJING_TIMEZONE = timezone(timedelta(hours=UTC_OFFSET_HOURS))
MIN_TIMESTAMP = int(datetime(MIN_SUPPORTED_YEAR, 1, 1, tzinfo=BEIJING_TIMEZONE).timestamp())
MAX_TIMESTAMP = int(datetime(MAX_SUPPORTED_YEAR + 1, 1, 1, tzinfo=BEIJING_TIMEZONE).timestamp())


def validateTimestamp(value: object, field: str, allowUpperBound: bool = False) -> None:
  """校验业务支持的 Unix 秒范围；允许排他终点时包含上界。"""
  if type(value) is not int:
    raise DomainError(ERROR_VALIDATION, f"{field}必须是整数时间戳", field)
  if value < MIN_TIMESTAMP or value > MAX_TIMESTAMP or (value == MAX_TIMESTAMP and not allowUpperBound):
    raise DomainError(ERROR_VALIDATION, f"{field}超出支持的时间范围", field)


def parseDateTime(text: str, field: str) -> int:
  """将严格格式的北京时间转换为 Unix 秒；非法日期抛业务异常。"""
  if type(text) is not str or re.fullmatch(DATE_TIME_PATTERN, text) is None:
    raise DomainError(ERROR_VALIDATION, f"{field}格式必须为年-月-日 时:分:秒", field)
  try:
    timestamp = int(datetime.strptime(text, DATE_TIME_FORMAT).replace(tzinfo=BEIJING_TIMEZONE).timestamp())
  except ValueError as error:
    raise DomainError(ERROR_VALIDATION, f"{field}不是有效日期时间", field) from error
  validateTimestamp(timestamp, field)
  return timestamp


def formatDateTime(timestamp: int) -> str:
  """将 Unix 秒格式化为北京时间；范围外抛业务异常。"""
  validateTimestamp(timestamp, "时间", allowUpperBound=True)
  return datetime.fromtimestamp(timestamp, BEIJING_TIMEZONE).strftime(DATE_TIME_FORMAT)


def getDateRange(startDate: str, days: int) -> tuple[int, int]:
  """返回北京时间左闭右开的日期区间；非法输入抛业务异常。"""
  requireInteger(days, MIN_REPORT_DAYS, MAX_REPORT_DAYS, "days")
  if type(startDate) is not str or re.fullmatch(DATE_PATTERN, startDate) is None:
    raise DomainError(ERROR_VALIDATION, "startDate 格式必须为年-月-日", "startDate")
  try:
    start = datetime.strptime(startDate, DATE_FORMAT).replace(tzinfo=BEIJING_TIMEZONE)
    end = start + timedelta(days=days)
  except (ValueError, OverflowError) as error:
    raise DomainError(ERROR_VALIDATION, "startDate 不是有效日期范围", "startDate") from error
  fromAt, toAt = int(start.timestamp()), int(end.timestamp())
  validateTimestamp(fromAt, "startDate")
  validateTimestamp(toAt, "days", allowUpperBound=True)
  return fromAt, toAt


class SystemClock:
  """生产环境使用的系统时钟。"""

  def now(self) -> int:
    """返回当前 Unix 秒。"""
    return int(time.time())
