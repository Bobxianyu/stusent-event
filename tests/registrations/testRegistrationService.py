"""报名的额度、窗口、容量、FIFO、递补和原子性测试。"""

import threading

import pytest

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
  ERROR_VALIDATION,
  STATUS_CANCELLED,
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
)
from campusApp.registrations.RegistrationRepository import RegistrationRepository
from registrationTestKit import (
  NOW,
  FakeClock,
  buildService,
  makeActivity,
  makeRegistration,
  makeStudent,
  seed,
)


OPEN_AT = NOW - 600
CLOSE_AT = NOW + 3_600
START_AT = NOW + 7_200


def prepare(capacity: int = 2, students: int = 2, current: int = NOW):
  """准备一个正在报名的活动与若干学生。"""
  store, service, clock, repository = buildService(clock=FakeClock(current))
  seed(
    store,
    students=[makeStudent(index) for index in range(1, students + 1)],
    activities=[makeActivity(1, capacity=capacity)],
  )
  return store, service, clock


def occupancy(studentId: int, count: int, firstActivityId: int = 2):
  """为一名学生构造 count 条占用额度的正式报名，返回活动与报名元组。"""
  activities = []
  registrations = []
  for index in range(count):
    activityId = firstActivityId + index
    activities.append(makeActivity(activityId, capacity=10))
    registrations.append(
      makeRegistration(index + 1, studentId, activityId, STATUS_CONFIRMED)
    )
  return tuple(activities), tuple(registrations)


def readAll(store):
  """读取一次只读快照，便于断言状态未被修改。"""
  return store.runRead(lambda state: state)


def testFirstApplicantIsConfirmedWithRemainingSeats():
  """名额未满时第一个申请人正式报名，剩余名额递减。"""
  _, service, _ = prepare(capacity=2)

  result = service.registerStudent(1, 1)

  assert result.ok
  assert result.data.registration.registrationId == 1
  assert result.data.registration.status == STATUS_CONFIRMED
  assert result.data.registration.joinedAt == NOW
  assert result.data.registration.cancelledAt is None
  assert result.data.remainingSeats == 1


def testApplicantBecomesWaitlistedWhenCapacityIsFull():
  """正式名额已满时后续申请人进入候补，剩余名额为 0。"""
  _, service, _ = prepare(capacity=1)

  first = service.registerStudent(1, 1)
  second = service.registerStudent(2, 1)

  assert first.data.registration.status == STATUS_CONFIRMED
  assert second.ok
  assert second.data.registration.registrationId == 2
  assert second.data.registration.status == STATUS_WAITLISTED
  assert second.data.remainingSeats == 0


@pytest.mark.parametrize(
  ("delta", "expectedOk"),
  [(-1, False), (0, True), (3_599, True), (3_600, False), (3_601, False)],
)
def testRegistrationWindowBoundary(delta, expectedOk):
  """报名窗口左闭右开：开始前 1 秒拒绝，恰好开始和截止前 1 秒允许，恰好截止拒绝。"""
  activity = makeActivity(1, capacity=5, openAt=NOW, closeAt=NOW + 3_600, startAt=NOW + 7_200)
  store, service, clock, _ = buildService(clock=FakeClock(NOW + delta))
  seed(store, students=[makeStudent(1)], activities=[activity])

  result = service.registerStudent(1, 1)

  assert result.ok is expectedOk
  if not expectedOk:
    assert result.error.code == ERROR_ACTIVITY_NOT_OPEN
    assert readAll(store).registrations == {}


def testClosedActivityRejectsNewRegistration():
  """手动关闭报名后即使仍在窗口内也不能提交。"""
  activity = makeActivity(1, capacity=5, isClosed=True)
  store, service, clock, _ = buildService()
  seed(store, students=[makeStudent(1)], activities=[activity])

  result = service.registerStudent(1, 1)

  assert result.ok is False
  assert result.error.code == ERROR_ACTIVITY_NOT_OPEN


@pytest.mark.parametrize("existing", [0, 1, 2])
def testAllowsUpToThreeActiveRegistrations(existing):
  """个人已有 0、1、2 条有效报名时仍可申请新活动。"""
  extraActivities, registrations = occupancy(1, existing)
  store, service, clock, _ = buildService()
  seed(
    store,
    students=[makeStudent(1)],
    activities=(makeActivity(1, capacity=10), *extraActivities),
    registrations=registrations,
  )

  result = service.registerStudent(1, 1)

  assert result.ok
  assert result.data.registration.status == STATUS_CONFIRMED


def testRejectsFourthActiveRegistration():
  """个人已有 3 条有效报名时第 4 条被拒绝且不写入记录。"""
  extraActivities, registrations = occupancy(1, 3)
  store, service, clock, _ = buildService()
  seed(
    store,
    students=[makeStudent(1)],
    activities=(makeActivity(1, capacity=10), *extraActivities),
    registrations=registrations,
  )

  result = service.registerStudent(1, 1)

  assert result.ok is False
  assert result.error.code == ERROR_ACTIVE_LIMIT_REACHED
  assert len(readAll(store).registrations) == 3


@pytest.mark.parametrize(("startOffset", "expectedOk"), [(-1_800, False), (-3_600, True)])
def testQuotaDependsOnActivityEndTime(startOffset, expectedOk):
  """活动结束前 1 秒仍占额度，恰好结束时（endAt 等于 now）不再占用。"""
  activities = [
    makeActivity(2, capacity=10),
    makeActivity(3, capacity=10),
    makeActivity(4, capacity=10, openAt=NOW - 7_200, closeAt=NOW - 5_400,
                 startAt=NOW + startOffset),
  ]
  registrations = [
    makeRegistration(1, 1, 2, STATUS_CONFIRMED),
    makeRegistration(2, 1, 3, STATUS_CONFIRMED),
    makeRegistration(3, 1, 4, STATUS_CONFIRMED),
  ]
  store, service, clock, _ = buildService()
  seed(
    store,
    students=[makeStudent(1)],
    activities=(makeActivity(1, capacity=10), *activities),
    registrations=registrations,
  )

  result = service.registerStudent(1, 1)

  assert result.ok is expectedOk
  if not expectedOk:
    assert result.error.code == ERROR_ACTIVE_LIMIT_REACHED


def testCancelledRegistrationDoesNotOccupyQuota():
  """已取消的记录不占用个人额度。"""
  extraActivities, registrations = occupancy(1, 2)
  cancelled = makeRegistration(3, 1, 4, STATUS_CANCELLED, cancelledAt=NOW - 60)
  store, service, clock, _ = buildService()
  seed(
    store,
    students=[makeStudent(1)],
    activities=(makeActivity(1, capacity=10), *extraActivities, makeActivity(4, capacity=10)),
    registrations=(*registrations, cancelled),
  )

  result = service.registerStudent(1, 1)

  assert result.ok
  assert result.data.registration.registrationId == 4


def testDuplicateUncancelledRegistrationRejected():
  """同一学生对同一活动只能有一条未取消记录。"""
  _, service, _ = prepare(capacity=5)

  service.registerStudent(1, 1)
  result = service.registerStudent(1, 1)

  assert result.ok is False
  assert result.error.code == ERROR_DUPLICATE_REGISTRATION


def testReapplyAfterCancelJoinsWaitlistTail():
  """取消后重新申请生成新记录，并排在候补队尾。"""
  _, service, _ = prepare(capacity=1, students=3)
  service.registerStudent(1, 1)
  service.registerStudent(2, 1)
  cancelled = service.cancelRegistration(1, 1)
  assert cancelled.data.promotedRegistrationId == 2

  result = service.registerStudent(1, 1)

  assert result.ok
  assert result.data.registration.registrationId == 3
  assert result.data.registration.status == STATUS_WAITLISTED


@pytest.mark.parametrize(("delta", "expectedOk"), [(-1, True), (0, False), (1, False)])
def testCancelBeforeStartBoundary(delta, expectedOk):
  """活动开始前 1 秒可取消，恰好开始及之后不可取消。"""
  store, service, clock, _ = buildService(clock=FakeClock(START_AT + delta))
  seed(
    store,
    students=[makeStudent(1)],
    activities=[makeActivity(1, capacity=5)],
    registrations=[makeRegistration(1, 1, 1, STATUS_CONFIRMED)],
  )

  result = service.cancelRegistration(1, 1)

  assert result.ok is expectedOk
  if not expectedOk:
    assert result.error.code == ERROR_CANCELLATION_CLOSED
    assert readAll(store).registrations[1].status == STATUS_CONFIRMED


def testCancelAfterCloseStillPromotesWaitlist():
  """报名截止后、活动开始前仍可取消并递补。"""
  store, service, clock, _ = buildService(clock=FakeClock(CLOSE_AT + 1))
  seed(
    store,
    students=[makeStudent(1), makeStudent(2)],
    activities=[makeActivity(1, capacity=1)],
    registrations=[
      makeRegistration(1, 1, 1, STATUS_CONFIRMED),
      makeRegistration(2, 2, 1, STATUS_WAITLISTED),
    ],
  )

  result = service.cancelRegistration(1, 1)

  assert result.ok
  assert result.data.promotedRegistrationId == 2
  state = readAll(store)
  assert state.registrations[1].status == STATUS_CANCELLED
  assert state.registrations[2].status == STATUS_CONFIRMED


def testCancelConfirmedPromotesEarliestWaitlisted():
  """取消正式报名按编号升序递补最早的一条候补。"""
  store, service, _ = prepare(capacity=1, students=3)
  service.registerStudent(1, 1)
  service.registerStudent(2, 1)
  service.registerStudent(3, 1)

  result = service.cancelRegistration(1, 1)

  assert result.ok
  assert result.data.registration.status == STATUS_CANCELLED
  assert result.data.registration.cancelledAt == NOW
  assert result.data.promotedRegistrationId == 2
  state = readAll(store)
  assert state.registrations[2].status == STATUS_CONFIRMED
  assert state.registrations[3].status == STATUS_WAITLISTED


def testCancelWaitlistedDoesNotPromote():
  """取消候补不会触发其他人递补。"""
  store, service, _ = prepare(capacity=1, students=2)
  service.registerStudent(1, 1)
  service.registerStudent(2, 1)

  result = service.cancelRegistration(2, 2)

  assert result.ok
  assert result.data.promotedRegistrationId is None
  state = readAll(store)
  assert state.registrations[1].status == STATUS_CONFIRMED
  assert state.registrations[2].status == STATUS_CANCELLED


def testPromotedStudentKeepsThreeActiveRegistrations():
  """候补者已有 3 条有效报名时仍能递补为正式，不因额度被跳过。"""
  extraActivities, registrations = occupancy(2, 3, firstActivityId=2)
  store, service, clock, _ = buildService()
  seed(
    store,
    students=[makeStudent(1), makeStudent(2)],
    activities=(makeActivity(1, capacity=1), *extraActivities),
    registrations=(
      makeRegistration(10, 1, 1, STATUS_CONFIRMED),
      makeRegistration(11, 2, 1, STATUS_WAITLISTED),
      *registrations,
    ),
  )

  result = service.cancelRegistration(1, 10)

  assert result.ok
  assert result.data.promotedRegistrationId == 11
  assert readAll(store).registrations[11].status == STATUS_CONFIRMED


def testCancelUnknownRegistration():
  """取消不存在的记录时返回登记不存在。"""
  _, service, _ = prepare()

  result = service.cancelRegistration(1, 99)

  assert result.ok is False
  assert result.error.code == ERROR_REGISTRATION_NOT_FOUND


def testCancelOtherStudentRegistration():
  """不能取消他人的报名。"""
  _, service, _ = prepare(capacity=5)
  service.registerStudent(1, 1)

  result = service.cancelRegistration(2, 1)

  assert result.ok is False
  assert result.error.code == ERROR_REGISTRATION_NOT_OWNED


def testCancelTwiceRejected():
  """同一记录重复取消返回已取消。"""
  _, service, _ = prepare(capacity=5)
  service.registerStudent(1, 1)
  service.cancelRegistration(1, 1)

  result = service.cancelRegistration(1, 1)

  assert result.ok is False
  assert result.error.code == ERROR_REGISTRATION_ALREADY_CANCELLED


def testUnknownStudentAndActivity():
  """学生或活动不存在时分别返回对应错误。"""
  _, service, _ = prepare(capacity=5)

  missingStudent = service.registerStudent(99, 1)
  missingActivity = service.registerStudent(1, 99)

  assert missingStudent.error.code == ERROR_STUDENT_NOT_FOUND
  assert missingActivity.error.code == ERROR_ACTIVITY_NOT_FOUND


@pytest.mark.parametrize("value", [0, -1, "1", 1.5, True, None])
def testInvalidStudentIdRejected(value):
  """非法学生编号在写入前被拒绝。"""
  _, service, _ = prepare(capacity=5)

  result = service.registerStudent(value, 1)

  assert result.ok is False
  assert result.error.code == ERROR_VALIDATION


@pytest.mark.parametrize("value", [0, -1, "1", 2.0, False])
def testInvalidActivityIdRejected(value):
  """非法活动编号在写入前被拒绝。"""
  _, service, _ = prepare(capacity=5)

  result = service.registerStudent(1, value)

  assert result.ok is False
  assert result.error.code == ERROR_VALIDATION


def testFailedRegistrationDoesNotConsumeRegistrationId():
  """失败的申请不消耗报名编号。"""
  store, service, _ = prepare(capacity=5)
  service.registerStudent(1, 1)
  failed = service.registerStudent(1, 1)
  assert failed.ok is False

  result = service.registerStudent(2, 1)

  assert result.ok
  assert result.data.registration.registrationId == 2


def testFailureBetweenCancelAndPromoteDiscardsDraft():
  """取消后再递补前的异常必须整份丢弃草稿，共享状态保持不变。"""
  class ExplodingRepository(RegistrationRepository):
    """在递补时抛异常的仓储替身。"""

    def confirm(self, state, registrationId):
      """模拟递补阶段的内部错误。"""
      raise RuntimeError("模拟递补失败")

  store, service, clock, _ = buildService(repository=ExplodingRepository())
  seed(
    store,
    students=[makeStudent(1), makeStudent(2)],
    activities=[makeActivity(1, capacity=1)],
    registrations=[
      makeRegistration(1, 1, 1, STATUS_CONFIRMED),
      makeRegistration(2, 2, 1, STATUS_WAITLISTED),
    ],
  )

  result = service.cancelRegistration(1, 1)

  assert result.ok is False
  assert result.error.code == ERROR_INTERNAL
  state = readAll(store)
  assert state.registrations[1].status == STATUS_CONFIRMED
  assert state.registrations[1].cancelledAt is None
  assert state.registrations[2].status == STATUS_WAITLISTED


def testLastSeatRaceKeepsExactlyOneConfirmed():
  """两个线程争抢最后一个名额时恰好一条正式、一条候补。"""
  store, service, _ = prepare(capacity=1, students=2)
  barrier = threading.Barrier(2)
  results = []
  lock = threading.Lock()

  def apply(studentId: int) -> None:
    """等待同步点后提交报名，并记录结果。"""
    barrier.wait()
    outcome = service.registerStudent(studentId, 1)
    with lock:
      results.append(outcome)

  threads = [threading.Thread(target=apply, args=(studentId,)) for studentId in (1, 2)]
  for thread in threads:
    thread.start()
  for thread in threads:
    thread.join()

  assert len(results) == 2
  assert all(outcome.ok for outcome in results)
  statuses = sorted(outcome.data.registration.status for outcome in results)
  assert statuses == [STATUS_CONFIRMED, STATUS_WAITLISTED]
  state = readAll(store)
  confirmed = [item for item in state.registrations.values() if item.status == STATUS_CONFIRMED]
  assert len(confirmed) == 1


@pytest.mark.parametrize(
  ("status", "expected"),
  [(STATUS_CONFIRMED, "正式报名"), (STATUS_WAITLISTED, "候补"), (STATUS_CANCELLED, "已取消")],
)
def testDescribeStatusLabels(status, expected):
  """报名状态映射为界面使用的中文说明。"""
  _, service, _ = prepare()

  registration = makeRegistration(1, 1, 1, status, cancelledAt=NOW if status == STATUS_CANCELLED else None)

  assert service.describeStatus(registration) == expected
