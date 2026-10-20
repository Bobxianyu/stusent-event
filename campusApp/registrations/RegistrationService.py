"""报名、取消、候补与自动递补的业务逻辑。"""

import logging
from typing import Callable, TypeVar

from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.constants import (
  ERROR_ACTIVITY_NOT_FOUND,
  ERROR_ACTIVITY_NOT_OPEN,
  ERROR_ACTIVE_LIMIT_REACHED,
  ERROR_CANCELLATION_CLOSED,
  ERROR_DUPLICATE_REGISTRATION,
  ERROR_INTERNAL,
  ERROR_REGISTRATION_ALREADY_CANCELLED,
  ERROR_REGISTRATION_NOT_FOUND,
  ERROR_REGISTRATION_NOT_OWNED,
  ERROR_STUDENT_NOT_FOUND,
  MAX_ACTIVE_REGISTRATIONS,
  STATUS_CANCELLED,
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
)
from campusApp.core.contracts import (
  ActivityReader,
  CancellationReceipt,
  Clock,
  DomainError,
  Registration,
  RegistrationReceipt,
  Result,
  StudentReader,
  failure,
  success,
)
from campusApp.core.validation import requireId
from campusApp.registrations.RegistrationRepository import RegistrationRepository


T = TypeVar("T")
LOGGER = logging.getLogger(__name__)


class RegistrationService:
  """报名与取消的公开业务接口。"""

  def __init__(
    self,
    store: MemoryStore,
    repository: RegistrationRepository,
    studentReader: StudentReader,
    activityReader: ActivityReader,
    clock: Clock,
  ):
    """注入共享存储、报名仓储、跨模块读取协议和时钟。"""
    self._store = store
    self._repository = repository
    self._studentReader = studentReader
    self._activityReader = activityReader
    self._clock = clock

  def registerStudent(self, studentId: int, activityId: int) -> Result[RegistrationReceipt]:
    """为学生申请名额；容量已满时自动进入候补。"""
    def action() -> RegistrationReceipt:
      validStudentId = requireId(studentId, "studentId")
      validActivityId = requireId(activityId, "activityId")

      def write(state) -> RegistrationReceipt:
        now = self._clock.now()
        if self._studentReader.findById(state, validStudentId) is None:
          raise DomainError(ERROR_STUDENT_NOT_FOUND, "学生不存在", "studentId")
        activity = self._activityReader.findById(state, validActivityId)
        if activity is None:
          raise DomainError(ERROR_ACTIVITY_NOT_FOUND, "活动不存在", "activityId")
        self._assertRegistrationOpen(activity, now)
        if self._repository.hasUncancelled(state, validStudentId, validActivityId):
          raise DomainError(
            ERROR_DUPLICATE_REGISTRATION,
            "已存在未取消的报名，请勿重复报名",
            "activityId",
          )
        activeCount = self._repository.countActiveForStudent(state, validStudentId, now)
        if activeCount >= MAX_ACTIVE_REGISTRATIONS:
          raise DomainError(
            ERROR_ACTIVE_LIMIT_REACHED,
            f"有效报名最多为 {MAX_ACTIVE_REGISTRATIONS} 条",
            "studentId",
          )
        confirmedCount = self._repository.countConfirmed(state, validActivityId)
        status = STATUS_CONFIRMED if confirmedCount < activity.capacity else STATUS_WAITLISTED
        registration = self._repository.insert(
          state,
          validStudentId,
          validActivityId,
          status,
          now,
        )
        remainingSeats = activity.capacity - self._repository.countConfirmed(
          state,
          validActivityId,
        )
        return RegistrationReceipt(registration, remainingSeats)

      return self._store.runWrite(write)

    return self._runAction(action, "提交报名")

  def cancelRegistration(self, studentId: int, registrationId: int) -> Result[CancellationReceipt]:
    """取消本人报名；取消正式名额时自动递补最早的候补。"""
    def action() -> CancellationReceipt:
      validStudentId = requireId(studentId, "studentId")
      validRegistrationId = requireId(registrationId, "registrationId")

      def write(state) -> CancellationReceipt:
        now = self._clock.now()
        registration = self._repository.findById(state, validRegistrationId)
        if registration is None:
          raise DomainError(ERROR_REGISTRATION_NOT_FOUND, "报名记录不存在", "registrationId")
        if registration.studentId != validStudentId:
          raise DomainError(ERROR_REGISTRATION_NOT_OWNED, "只能取消本人的报名", "registrationId")
        if registration.status == STATUS_CANCELLED:
          raise DomainError(
            ERROR_REGISTRATION_ALREADY_CANCELLED,
            "该报名已取消",
            "registrationId",
          )
        activity = self._activityReader.findById(state, registration.activityId)
        if activity is None:
          raise DomainError(ERROR_ACTIVITY_NOT_FOUND, "活动不存在", "activityId")
        if now >= activity.startAt:
          raise DomainError(ERROR_CANCELLATION_CLOSED, "活动已开始，不能取消", "registrationId")
        cancelled = self._repository.cancel(state, validRegistrationId, now)
        promotedId = self._promoteFirstWaitlisted(state, registration)
        return CancellationReceipt(cancelled, promotedId)

      return self._store.runWrite(write)

    return self._runAction(action, "取消报名")

  @staticmethod
  def describeStatus(registration: Registration) -> str:
    """返回报名状态的中文说明，供界面显示使用。"""
    if registration.status == STATUS_CONFIRMED:
      return "正式报名"
    if registration.status == STATUS_WAITLISTED:
      return "候补"
    if registration.status == STATUS_CANCELLED:
      return "已取消"
    return registration.status

  @staticmethod
  def _assertRegistrationOpen(activity, now: int) -> None:
    """按手动关闭标记和报名窗口判断是否还能提交新报名。"""
    if activity.isClosed:
      raise DomainError(ERROR_ACTIVITY_NOT_OPEN, "活动已关闭报名", "activityId")
    if now < activity.openAt:
      raise DomainError(ERROR_ACTIVITY_NOT_OPEN, "报名尚未开始", "activityId")
    if now >= activity.closeAt:
      raise DomainError(ERROR_ACTIVITY_NOT_OPEN, "报名已截止", "activityId")

  def _promoteFirstWaitlisted(self, state, registration: Registration) -> int | None:
    """取消正式名额后把最早的候补转为正式，返回被递补的记录编号。"""
    if registration.status != STATUS_CONFIRMED:
      return None
    candidate = self._repository.findFirstWaitlisted(state, registration.activityId)
    if candidate is None:
      return None
    self._repository.confirm(state, candidate.registrationId)
    return candidate.registrationId

  @staticmethod
  def _runAction(action: Callable[[], T], operation: str) -> Result[T]:
    """捕获业务和内部异常，统一生成中文 Result。"""
    try:
      return success(action())
    except DomainError as error:
      return failure(error.error.code, error.error.message, error.error.field)
    except Exception:
      LOGGER.exception("报名模块执行%s失败", operation)
      return failure(ERROR_INTERNAL, f"{operation}失败，请查看日志")
