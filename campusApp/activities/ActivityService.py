"""活动输入校验、状态判断和业务操作。"""

import logging
from typing import Callable, TypeVar

from campusApp.activities.ActivityRepository import ActivityRepository
from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.constants import (
  ERROR_ACTIVITY_NOT_FOUND,
  ERROR_INTERNAL,
  ERROR_VALIDATION,
  MAX_CAPACITY,
  MAX_DURATION_MINUTES,
  MAX_TITLE_LENGTH,
  MIN_CAPACITY,
  MIN_DURATION_MINUTES,
  MIN_TITLE_LENGTH,
  SECONDS_PER_MINUTE,
)
from campusApp.core.contracts import Activity, Clock, DomainError, Result, failure, success
from campusApp.core.timeUtils import validateTimestamp
from campusApp.core.validation import requireId, requireInteger, requireText


T = TypeVar("T")
LOGGER = logging.getLogger(__name__)


class ActivityService:
  """活动管理的公开业务接口。"""

  def __init__(self, store: MemoryStore, repository: ActivityRepository, clock: Clock):
    """注入唯一共享存储、活动仓储和时钟。"""
    self._store = store
    self._repository = repository
    self._clock = clock

  def createActivity(
    self,
    title: str,
    capacity: int,
    durationMinutes: int,
    openAt: int,
    closeAt: int,
    startAt: int,
  ) -> Result[Activity]:
    """创建未来活动；参数不合法时返回错误且不占用编号。"""
    def action() -> Activity:
      normalizedTitle = requireText(title, MIN_TITLE_LENGTH, MAX_TITLE_LENGTH, "title")
      validCapacity = requireInteger(capacity, MIN_CAPACITY, MAX_CAPACITY, "capacity")
      validDuration = requireInteger(
        durationMinutes,
        MIN_DURATION_MINUTES,
        MAX_DURATION_MINUTES,
        "durationMinutes",
      )
      validateTimestamp(openAt, "openAt")
      validateTimestamp(closeAt, "closeAt")
      validateTimestamp(startAt, "startAt")
      if not openAt < closeAt <= startAt:
        raise DomainError(ERROR_VALIDATION, "报名开始、截止和活动开始时间顺序无效", "closeAt")

      def write(state):
        now = self._clock.now()
        if startAt <= now:
          raise DomainError(ERROR_VALIDATION, "活动开始时间必须晚于当前时间", "startAt")
        endAt = startAt + validDuration * SECONDS_PER_MINUTE
        validateTimestamp(endAt, "endAt", allowUpperBound=True)
        return self._repository.insert(
          state,
          normalizedTitle,
          validCapacity,
          validDuration,
          openAt,
          closeAt,
          startAt,
          endAt,
          False,
          now,
        )

      return self._store.runWrite(write)

    return self._runAction(action, "创建活动")

  def updateActivityTitle(self, activityId: int, title: str) -> Result[Activity]:
    """修改活动名称；其他字段保持不变。"""
    def action() -> Activity:
      validId = requireId(activityId, "activityId")
      normalizedTitle = requireText(title, MIN_TITLE_LENGTH, MAX_TITLE_LENGTH, "title")

      def write(state):
        if self._repository.findById(state, validId) is None:
          raise DomainError(ERROR_ACTIVITY_NOT_FOUND, "活动不存在", "activityId")
        return self._repository.updateTitle(state, validId, normalizedTitle)

      return self._store.runWrite(write)

    return self._runAction(action, "修改活动名称")

  def closeRegistration(self, activityId: int) -> Result[Activity]:
    """关闭活动的新报名；重复关闭仍返回成功。"""
    def action() -> Activity:
      validId = requireId(activityId, "activityId")

      def write(state):
        activity = self._repository.findById(state, validId)
        if activity is None:
          raise DomainError(ERROR_ACTIVITY_NOT_FOUND, "活动不存在", "activityId")
        if activity.isClosed:
          return activity
        return self._repository.setClosed(state, validId)

      return self._store.runWrite(write)

    return self._runAction(action, "关闭报名")

  def getActivity(self, activityId: int) -> Result[Activity]:
    """按编号查询活动。"""
    def action() -> Activity:
      validId = requireId(activityId, "activityId")

      def read(state):
        activity = self._repository.findById(state, validId)
        if activity is None:
          raise DomainError(ERROR_ACTIVITY_NOT_FOUND, "活动不存在", "activityId")
        return activity

      return self._store.runRead(read)

    return self._runAction(action, "查询活动")

  def listActivities(self) -> Result[list[Activity]]:
    """返回按开始时间和编号排序的活动列表。"""
    return self._runAction(lambda: self._store.runRead(self._repository.listAll), "查询活动列表")

  def describePhase(self, activity: Activity) -> str:
    """按当前时间显示活动阶段；仅供本模块界面使用。"""
    now = self._clock.now()
    if now >= activity.endAt:
      return "已结束"
    if now >= activity.startAt:
      return "进行中"
    if activity.isClosed or now >= activity.closeAt:
      return "报名关闭"
    if now < activity.openAt:
      return "未开放"
    return "报名中"

  @staticmethod
  def _runAction(action: Callable[[], T], operation: str) -> Result[T]:
    """捕获业务和内部异常，统一生成中文 Result。"""
    try:
      return success(action())
    except DomainError as error:
      return failure(error.error.code, error.error.message, error.error.field)
    except Exception:
      LOGGER.exception("活动管理模块执行%s失败", operation)
      return failure(ERROR_INTERNAL, f"{operation}失败，请查看日志")
