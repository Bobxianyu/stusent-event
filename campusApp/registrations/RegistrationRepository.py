"""报名集合的读写操作。"""

from dataclasses import replace

from campusApp.core.constants import STATUS_CANCELLED, STATUS_CONFIRMED, STATUS_WAITLISTED
from campusApp.core.contracts import Registration, StoreDraft, StoreSnapshot


class RegistrationRepository:
  """只访问共享状态中的报名集合，不创建独立存储。"""

  def findById(self, state: StoreSnapshot | StoreDraft, registrationId: int) -> Registration | None:
    """按编号读取报名记录；不存在时返回 None。"""
    return state.registrations.get(registrationId)

  def hasUncancelled(
    self,
    state: StoreSnapshot | StoreDraft,
    studentId: int,
    activityId: int,
  ) -> bool:
    """判断同一学生对同一活动是否已有未取消的记录。"""
    for registration in state.registrations.values():
      if registration.studentId != studentId or registration.activityId != activityId:
        continue
      if registration.status != STATUS_CANCELLED:
        return True
    return False

  def countActiveForStudent(
    self,
    state: StoreSnapshot | StoreDraft,
    studentId: int,
    now: int,
  ) -> int:
    """统计学生当前占用的有效报名数，以活动结束时间晚于 now 为准。"""
    count = 0
    for registration in state.registrations.values():
      if registration.studentId != studentId or registration.status == STATUS_CANCELLED:
        continue
      activity = state.activities.get(registration.activityId)
      if activity is not None and activity.endAt > now:
        count += 1
    return count

  def countConfirmed(self, state: StoreSnapshot | StoreDraft, activityId: int) -> int:
    """统计活动当前的正式报名人数。"""
    return sum(
      1
      for registration in state.registrations.values()
      if registration.activityId == activityId and registration.status == STATUS_CONFIRMED
    )

  def insert(
    self,
    state: StoreDraft,
    studentId: int,
    activityId: int,
    status: str,
    joinedAt: int,
  ) -> Registration:
    """使用草稿中的下一编号新增报名记录，并返回不可变实体。"""
    registrationId = state.nextRegistrationId
    registration = Registration(registrationId, studentId, activityId, status, joinedAt, None)
    state.registrations[registrationId] = registration
    state.nextRegistrationId = registrationId + 1
    return registration

  def cancel(
    self,
    state: StoreDraft,
    registrationId: int,
    cancelledAt: int,
  ) -> Registration:
    """把记录标记为已取消并写入取消时间；要求调用方已确认记录存在。"""
    registration = replace(
      state.registrations[registrationId],
      status=STATUS_CANCELLED,
      cancelledAt=cancelledAt,
    )
    state.registrations[registrationId] = registration
    return registration

  def confirm(self, state: StoreDraft, registrationId: int) -> Registration:
    """把候补记录转为正式报名；要求调用方已确认记录存在且处于候补状态。"""
    registration = replace(state.registrations[registrationId], status=STATUS_CONFIRMED)
    state.registrations[registrationId] = registration
    return registration

  def findFirstWaitlisted(
    self,
    state: StoreSnapshot | StoreDraft,
    activityId: int,
  ) -> Registration | None:
    """按报名编号升序返回活动最早的候补记录；没有候补时返回 None。"""
    candidates = [
      registration
      for registration in state.registrations.values()
      if registration.activityId == activityId and registration.status == STATUS_WAITLISTED
    ]
    if not candidates:
      return None
    return min(candidates, key=lambda registration: registration.registrationId)
