"""北京时间解析和日期边界测试。"""

import pytest

from campusApp.core.contracts import DomainError
from campusApp.core.timeUtils import (
  MAX_TIMESTAMP,
  MIN_TIMESTAMP,
  formatDateTime,
  getDateRange,
  parseDateTime,
  validateTimestamp,
)


def testParseAndFormatRoundTrip():
  """有效北京时间可往返转换。"""
  value = parseDateTime("2026-10-14 09:30:00", "开始时间")
  assert formatDateTime(value) == "2026-10-14 09:30:00"


@pytest.mark.parametrize("value", ["2026/10/14 09:30:00", "2026-02-30 09:30:00", 123])
def testParseRejectsInvalidInput(value):
  """格式、日期及类型无效时返回业务错误。"""
  with pytest.raises(DomainError):
    parseDateTime(value, "开始时间")


def testTimestampUpperBoundOnlyForEnd():
  """上界只对排他结束时间开放。"""
  validateTimestamp(MIN_TIMESTAMP, "开始时间")
  validateTimestamp(MAX_TIMESTAMP, "结束时间", allowUpperBound=True)
  with pytest.raises(DomainError):
    validateTimestamp(MAX_TIMESTAMP, "开始时间")
  with pytest.raises(DomainError):
    validateTimestamp(False, "开始时间")


@pytest.mark.parametrize("startDate,days", [
  ("2026-02-30", 1),
  ("2026/10/14", 1),
  ("2026-10-14", 0),
  ("2099-12-31", 2),
])
def testDateRangeRejectsInvalidInput(startDate, days):
  """日期格式、范围和天数均须合法。"""
  with pytest.raises(DomainError):
    getDateRange(startDate, days)


def testDateRangeUsesBeijingMidnight():
  """日期窗口按北京时间零点计算。"""
  startAt, endAt = getDateRange("2026-10-14", 1)
  assert formatDateTime(startAt) == "2026-10-14 00:00:00"
  assert formatDateTime(endAt) == "2026-10-15 00:00:00"
