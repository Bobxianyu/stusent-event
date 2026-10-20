"""QueryRepository 单元测试。"""
import pytest

from tests.queries.conftest import (
  makeStudent,
  makeActivity,
  makeReg,
  seed,
)
from campusApp.queries.QueryRepository import QueryRepository
from campusApp.core.constants import (
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
  STATUS_CANCELLED,
)


@pytest.fixture
def repo():
  return QueryRepository()


def testStudentExists(repo, queryStore):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])
  snap = queryStore.runRead(lambda s: s)
  assert repo.studentExists(snap, 1) is True
  assert repo.studentExists(snap, 99) is False


def testActivityExists(repo, queryStore):
  seed(queryStore, [], [makeActivity(1)], [])
  snap = queryStore.runRead(lambda s: s)
  assert repo.activityExists(snap, 1) is True
  assert repo.activityExists(snap, 99) is False


def testFindActivityById(repo, queryStore):
  seed(queryStore, [], [makeActivity(1, title="讲座")], [])
  snap = queryStore.runRead(lambda s: s)
  assert repo.findActivityById(snap, 1).title == "讲座"
  assert repo.findActivityById(snap, 99) is None


def testCountByStatus(repo, queryStore):
  # 合法前置：同一学生同一活动最多一条未取消记录，
  # 故用“取消后再报名”产生两条历史（1 条取消 + 1 条正式），并补一个候补学生。
  seed(
    queryStore,
    [
      makeStudent(1, "2024010001", "张三"),
      makeStudent(2, "2024010002", "李四"),
    ],
    [makeActivity(1)],
    [
      makeReg(1, 1, 1, STATUS_CANCELLED, cancelledAt=100),
      makeReg(2, 1, 1, STATUS_CONFIRMED),
      makeReg(3, 2, 1, STATUS_WAITLISTED),
    ],
  )
  snap = queryStore.runRead(lambda s: s)
  counts = repo.countByStatus(snap, 1)
  assert counts == {"confirmed": 1, "waitlisted": 1, "cancelled": 1}


def testCountByStatusIgnoresOtherActivities(repo, queryStore):
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1), makeActivity(2)],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 1, 2, STATUS_CONFIRMED),
    ],
  )
  snap = queryStore.runRead(lambda s: s)
  assert repo.countByStatus(snap, 1) == {
    "confirmed": 1, "waitlisted": 0, "cancelled": 0
  }


def testSummarizeStartRangeBoundaryExcluded(repo, queryStore):
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [
      makeActivity(1, startAt=1000, endAt=2000),
      makeActivity(2, startAt=2000, endAt=3000),
    ],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 1, 2, STATUS_CONFIRMED),
    ],
  )
  snap = queryStore.runRead(lambda s: s)
  stats = repo.summarizeByStartRange(snap, 1000, 2000)
  assert stats.activityCount == 1
  assert stats.confirmedCount == 1
  assert stats.distinctParticipantCount == 1


def testBuildRowsSkipsDanglingReference(repo, queryStore):
  # 防御分支：仓储遇到悬空引用（学生被删 / 活动被删）时跳过该行，不抛异常。
  from campusApp.core.contracts import RegistrationRow  # noqa: F401
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )

  class DanglingState:
    students = {1: makeStudent(1, "2024010001", "张三")}
    activities = {}
    registrations = {1: makeReg(1, 1, 1, STATUS_CONFIRMED)}

  rows = repo._buildRows(DanglingState, lambda reg: True)
  assert rows == []


def testSummarizeRejectsUnknownStatus(repo, queryStore):
  # 不合法状态必须显式失败，不能静默跳过（回归用例）。
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  snap = queryStore.runRead(lambda s: s)

  class BrokenReg:
    activityId = 1
    studentId = 1
    status = "UNKNOWN"

  class BrokenState:
    students = snap.students
    activities = snap.activities
    registrations = {1: BrokenReg()}

  with pytest.raises(ValueError):
    repo.summarizeByStartRange(BrokenState, 0, 10 ** 10)
