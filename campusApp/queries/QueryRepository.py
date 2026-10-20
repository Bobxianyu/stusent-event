"""鏌ヨ涓庣粺璁℃ā鍧楋細鍙鍐呭瓨浠撳偍銆?

鍙鍙?StoreSnapshot锛岀粷涓嶄慨鏀瑰叡浜唴瀛橈紱渚?QueryService 鍦?runRead 鍥炶皟涓娇鐢ㄣ€?
"""
from __future__ import annotations

from campusApp.core.contracts import (
  RegistrationRow,
  OverviewStats,
)
from campusApp.core.constants import (
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
  STATUS_CANCELLED,
)


class QueryRepository:
  """鏌ヨ涓庣粺璁℃ā鍧楃殑鍙浠撳偍銆?

  鎵€鏈夋柟娉曚粎璇诲彇浼犲叆鐨?state锛屼笉鎸佹湁 Store 寮曠敤锛屼笉鍋氬啓鎿嶄綔銆?
  """

  def __init__(self) -> None:
    pass

  # ---------- 瀛︾敓 / 娲诲姩 ----------

  def studentExists(self, state, studentId: int) -> bool:
    return studentId in state.students

  def activityExists(self, state, activityId: int) -> bool:
    return activityId in state.activities

  def findActivityById(self, state, activityId: int):
    return state.activities.get(activityId)

  # ---------- 涓汉鎶ュ悕鍘嗗彶 ----------

  def countPersonal(self, state, studentId: int) -> int:
    return sum(
      1
      for reg in state.registrations.values()
      if reg.studentId == studentId
    )

  def selectPersonal(
    self, state, studentId: int, offset: int, pageSize: int
  ) -> list[RegistrationRow]:
    rows = self._buildRows(state, lambda reg: reg.studentId == studentId)
    return rows[offset : offset + pageSize]

  # ---------- 娲诲姩鎶ュ悕鍚嶅崟 ----------

  def countActivity(
    self, state, activityId: int, status: str | None
  ) -> int:
    return sum(
      1
      for reg in state.registrations.values()
      if reg.activityId == activityId
      and (status is None or reg.status == status)
    )

  def selectActivity(
    self, state, activityId: int, status: str | None,
    offset: int, pageSize: int,
  ) -> list[RegistrationRow]:
    rows = self._buildRows(
      state,
      lambda reg: reg.activityId == activityId
      and (status is None or reg.status == status),
    )
    return rows[offset : offset + pageSize]

  # ---------- 娲诲姩缁熻 ----------

  def countByStatus(self, state, activityId: int) -> dict:
    counts = {STATUS_CONFIRMED: 0, STATUS_WAITLISTED: 0, STATUS_CANCELLED: 0}
    for reg in state.registrations.values():
      if reg.activityId != activityId:
        continue
      if reg.status in counts:
        counts[reg.status] += 1
    return {
      "confirmed": counts[STATUS_CONFIRMED],
      "waitlisted": counts[STATUS_WAITLISTED],
      "cancelled": counts[STATUS_CANCELLED],
    }

  # ---------- 鎬昏缁熻 ----------

  def summarizeByStartRange(
    self, state, fromAt: int, toAt: int
  ) -> OverviewStats:
    activityIds = {
      aid
      for aid, act in state.activities.items()
      if fromAt <= act.startAt < toAt
    }

    confirmedCount = 0
    waitlistedCount = 0
    cancelledCount = 0
    distinctStudents: set[int] = set()
    knownStatuses = (STATUS_CONFIRMED, STATUS_WAITLISTED, STATUS_CANCELLED)

    for reg in state.registrations.values():
      if reg.activityId not in activityIds:
        continue
      # 鐘舵€佸繀椤讳弗鏍间笁鍒嗭細鍑虹幇鏈煡瀛楃涓茶鏄庡唴閮ㄧ姸鎬佸凡鎹熷潖锛岀洿鎺ユ姏鍑轰氦鐢?
      # Service 杞?INTERNAL_ERROR锛屼笉鑳介潤榛樿烦杩囧鑷存€绘暟鎮勬倓鍙樺皯銆?
      if reg.status not in knownStatuses:
        raise ValueError("鎶ュ悕鐘舵€侀潪娉曪細%r" % (reg.status,))
      if reg.status == STATUS_CONFIRMED:
        confirmedCount += 1
        distinctStudents.add(reg.studentId)
      elif reg.status == STATUS_WAITLISTED:
        waitlistedCount += 1
      else:
        cancelledCount += 1

    return OverviewStats(
      activityCount=len(activityIds),
      confirmedCount=confirmedCount,
      waitlistedCount=waitlistedCount,
      cancelledCount=cancelledCount,
      distinctParticipantCount=len(distinctStudents),
    )

  # ---------- 鍐呴儴宸ュ叿 ----------

  def _buildRows(self, state, filterFn) -> list[RegistrationRow]:
    rows: list[RegistrationRow] = []
    for reg in state.registrations.values():
      if not filterFn(reg):
        continue
      student = state.students.get(reg.studentId)
      activity = state.activities.get(reg.activityId)
      if student is None or activity is None:
        continue
      rows.append(
        RegistrationRow(
          registrationId=reg.registrationId,
          studentId=reg.studentId,
          studentNo=student.studentNo,
          studentName=student.name,
          activityId=reg.activityId,
          activityTitle=activity.title,
          status=reg.status,
          joinedAt=reg.joinedAt,
          cancelledAt=reg.cancelledAt,
          startAt=activity.startAt,
          endAt=activity.endAt,
        )
      )
    rows.sort(key=lambda r: r.registrationId)
    return rows
