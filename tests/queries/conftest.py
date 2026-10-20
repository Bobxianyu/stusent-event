"""查询与统计模块专用夹具。夹具名与 tests/conftest.py 不重名。

造数原则：一律生成满足公共约束的合法前置状态。
同一学生同一活动最多一条未取消记录（STATUS_CONFIRMED / STATUS_WAITLISTED），
历史取消记录可以有多条——因此混合状态场景用「多学生 + 取消后再报名」表达，
不用非法内存状态绕过约束。
"""
import pytest

from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.contracts import (
  Student,
  Activity,
  Registration,
)
from campusApp.core.constants import (
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
  STATUS_CANCELLED,
  SECONDS_PER_MINUTE,
)
from campusApp.queries.QueryRepository import QueryRepository
from campusApp.queries.QueryService import QueryService


class FixedClock:
  """固定时钟：测试通过它控制 Service 看到的当前时间。"""

  def __init__(self, now: int = 0):
    self._now = now

  def now(self) -> int:
    return self._now

  def set(self, now: int) -> None:
    self._now = now


def makeStudent(sid, no, name, grade=1):
  return Student(
    studentId=sid, studentNo=no, name=name, grade=grade, createdAt=0
  )


def makeActivity(
  aid, title="活动", capacity=10,
  openAt=0, closeAt=500, startAt=1000, endAt=2000,
  durationMinutes=60, isClosed=False,
):
  return Activity(
    activityId=aid, title=title, capacity=capacity,
    durationMinutes=durationMinutes,
    openAt=openAt, closeAt=closeAt, startAt=startAt, endAt=endAt,
    isClosed=isClosed, createdAt=0,
  )


def makeReg(rid, sid, aid, status, cancelledAt=None, joinedAt=0):
  return Registration(
    registrationId=rid, studentId=sid, activityId=aid,
    status=status, joinedAt=joinedAt, cancelledAt=cancelledAt,
  )


@pytest.fixture
def queryStore():
  return MemoryStore()


@pytest.fixture
def queryClock():
  return FixedClock(0)


@pytest.fixture
def queryService(queryStore, queryClock):
  return QueryService(queryStore, QueryRepository(), queryClock)


def seed(queryStore, students, activities, registrations):
  """把三类合法实体一次性写入独立 MemoryStore，并同步编号计数器。"""
  def write(state):
    for s in students:
      state.students[s.studentId] = s
    for a in activities:
      state.activities[a.activityId] = a
    for r in registrations:
      state.registrations[r.registrationId] = r
    state.nextStudentId = max([s.studentId for s in students] or [0]) + 1
    state.nextActivityId = max([a.activityId for a in activities] or [0]) + 1
    state.nextRegistrationId = max(
      [r.registrationId for r in registrations] or [0]
    ) + 1
  queryStore.runWrite(write)


def makeSeconds(dateText: str, hour: int = 0) -> int:
  """把北京时间日期转成当天指定小时的 Unix 秒，供统计区间用例使用。"""
  from campusApp.core.timeUtils import parseDateTime
  return parseDateTime("%s %02d:00:00" % (dateText, hour), "startAt")


__all__ = [
  "FixedClock",
  "makeStudent",
  "makeActivity",
  "makeReg",
  "makeSeconds",
  "seed",
  "STATUS_CONFIRMED",
  "STATUS_WAITLISTED",
  "STATUS_CANCELLED",
  "SECONDS_PER_MINUTE",
]
