"""查询与统计模块：只读 Service。"""
from __future__ import annotations

import logging

from campusApp.core.contracts import (
  Result,
  Page,
  DomainError,
  RegistrationRow,
  ActivityStats,
  OverviewStats,
  success,
  failure,
)
from campusApp.core.constants import (
  ERROR_ACTIVITY_NOT_FOUND,
  ERROR_INTERNAL,
  ERROR_STUDENT_NOT_FOUND,
  ERROR_VALIDATION,
  MAX_PAGE,
  MAX_PAGE_SIZE,
  MIN_PAGE,
  MIN_PAGE_SIZE,
  PERCENT_BASE,
  STATUS_CANCELLED,
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
)
from campusApp.core.validation import requireId, requireInteger
from campusApp.core.timeUtils import getDateRange
from campusApp.queries.QueryRepository import QueryRepository


VALID_STATUSES = {STATUS_CONFIRMED, STATUS_WAITLISTED, STATUS_CANCELLED}
LOGGER = logging.getLogger(__name__)


class QueryService:
  def __init__(self, store, repository: QueryRepository, clock) -> None:
    self.store = store
    self.repository = repository
    self.clock = clock

  # ---------- 1. 个人报名历史 ----------

  def listPersonalRegistrations(
    self, studentId: int, page: int, pageSize: int
  ) -> Result[Page[RegistrationRow]]:
    try:
      sid = requireId(studentId, "studentId")
      p = requireInteger(page, MIN_PAGE, MAX_PAGE, "page")
      ps = requireInteger(pageSize, MIN_PAGE_SIZE, MAX_PAGE_SIZE, "pageSize")
      resultPage = self.store.runRead(
        lambda state: self._doListPersonal(state, sid, p, ps)
      )
      return success(resultPage)
    except DomainError as e:
      return failure(e.error.code, e.error.message, e.error.field)
    except Exception:
      LOGGER.exception("查询个人报名记录时发生内部错误")
      return failure(ERROR_INTERNAL, "查询个人报名记录时发生内部错误")

  def _doListPersonal(self, state, studentId: int, page: int, pageSize: int) -> Page:
    if not self.repository.studentExists(state, studentId):
      raise DomainError(ERROR_STUDENT_NOT_FOUND, "学生不存在", "studentId")
    total = self.repository.countPersonal(state, studentId)
    offset = (page - MIN_PAGE) * pageSize
    items = self.repository.selectPersonal(state, studentId, offset, pageSize)
    return Page(items=items, total=total, page=page, pageSize=pageSize)

  # ---------- 2. 活动报名名单 ----------

  def listActivityRegistrations(
    self,
    activityId: int,
    status: str | None,
    page: int,
    pageSize: int,
  ) -> Result[Page[RegistrationRow]]:
    try:
      aid = requireId(activityId, "activityId")
      self._validateStatus(status)
      p = requireInteger(page, MIN_PAGE, MAX_PAGE, "page")
      ps = requireInteger(pageSize, MIN_PAGE_SIZE, MAX_PAGE_SIZE, "pageSize")
      resultPage = self.store.runRead(
        lambda state: self._doListActivity(state, aid, status, p, ps)
      )
      return success(resultPage)
    except DomainError as e:
      return failure(e.error.code, e.error.message, e.error.field)
    except Exception:
      LOGGER.exception("查询活动报名名单时发生内部错误")
      return failure(ERROR_INTERNAL, "查询活动报名名单时发生内部错误")

  def _doListActivity(
    self, state, activityId: int, status: str | None, page: int, pageSize: int
  ) -> Page:
    if not self.repository.activityExists(state, activityId):
      raise DomainError(ERROR_ACTIVITY_NOT_FOUND, "活动不存在", "activityId")
    total = self.repository.countActivity(state, activityId, status)
    offset = (page - MIN_PAGE) * pageSize
    items = self.repository.selectActivity(
      state, activityId, status, offset, pageSize
    )
    return Page(items=items, total=total, page=page, pageSize=pageSize)

  @staticmethod
  def _validateStatus(status) -> None:
    if status is None:
      return
    if not isinstance(status, str):
      raise DomainError(
        ERROR_VALIDATION, "报名状态必须是字符串或为空", "status"
      )
    if status not in VALID_STATUSES:
      raise DomainError(
        ERROR_VALIDATION,
        "报名状态只能是 STATUS_CONFIRMED、STATUS_WAITLISTED、STATUS_CANCELLED 或为空",
        "status",
      )

  # ---------- 3. 活动统计 ----------

  def getActivityStats(self, activityId: int) -> Result[ActivityStats]:
    try:
      aid = requireId(activityId, "activityId")
      stats = self.store.runRead(
        lambda state: self._doGetActivityStats(state, aid)
      )
      return success(stats)
    except DomainError as e:
      return failure(e.error.code, e.error.message, e.error.field)
    except Exception:
      LOGGER.exception("统计活动时发生内部错误")
      return failure(ERROR_INTERNAL, "统计活动时发生内部错误")

  def _doGetActivityStats(self, state, activityId: int) -> ActivityStats:
    activity = self.repository.findActivityById(state, activityId)
    if activity is None:
      raise DomainError(ERROR_ACTIVITY_NOT_FOUND, "活动不存在", "activityId")
    counts = self.repository.countByStatus(state, activityId)
    remainingSeats = activity.capacity - counts["confirmed"]
    occupancyPercent = round(
      counts["confirmed"] / activity.capacity * PERCENT_BASE, 2
    )
    return ActivityStats(
      activityId=activityId,
      capacity=activity.capacity,
      confirmedCount=counts["confirmed"],
      waitlistedCount=counts["waitlisted"],
      cancelledCount=counts["cancelled"],
      remainingSeats=remainingSeats,
      occupancyPercent=occupancyPercent,
    )

  # ---------- 4. 总览统计 ----------

  def getOverviewStats(self, startDate: str, days: int) -> Result[OverviewStats]:
    try:
      fromAt, toAt = getDateRange(startDate, days)
      stats = self.store.runRead(
        lambda state: self.repository.summarizeByStartRange(
          state, fromAt, toAt
        )
      )
      return success(stats)
    except DomainError as e:
      return failure(e.error.code, e.error.message, e.error.field)
    except Exception:
      LOGGER.exception("总览统计时发生内部错误")
      return failure(ERROR_INTERNAL, "总览统计时发生内部错误")
