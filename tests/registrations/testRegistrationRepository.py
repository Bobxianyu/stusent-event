"""报名仓储的读取、统计和写入行为测试。"""

from campusApp.core.constants import STATUS_CANCELLED, STATUS_CONFIRMED, STATUS_WAITLISTED
from registrationTestKit import (
  NOW,
  buildService,
  makeActivity,
  makeRegistration,
  makeStudent,
  seed,
)


def readState(store):
  """读取一次只读快照。"""
  return store.runRead(lambda state: state)


def prepareRepository():
  """准备学生与三个活动：1 号进行中，2 号已结束。"""
  store, service, clock, repository = buildService()
  seed(
    store,
    students=[makeStudent(1), makeStudent(2), makeStudent(3), makeStudent(4)],
    activities=[
      makeActivity(1, capacity=5),
      makeActivity(2, capacity=5, openAt=NOW - 14_400, closeAt=NOW - 10_800, startAt=NOW - 7_200),
      makeActivity(3, capacity=5),
    ],
  )
  return store, repository


def testFindByIdReturnsNoneWhenMissing():
  """编号不存在时返回 None。"""
  store, repository = prepareRepository()

  assert readState(store) is not None
  assert repository.findById(readState(store), 99) is None


def testHasUncancelledIgnoresCancelledRecords():
  """已取消的记录不算未取消报名。"""
  store, repository = prepareRepository()
  seed(
    store,
    students=[makeStudent(1)],
    registrations=[
      makeRegistration(1, 1, 1, STATUS_CANCELLED, cancelledAt=NOW - 30),
    ],
  )

  assert repository.hasUncancelled(readState(store), 1, 1) is False


def testHasUncancelledDetectsWaitlisted():
  """候补同样属于未取消记录。"""
  store, repository = prepareRepository()
  seed(store, registrations=[makeRegistration(1, 1, 1, STATUS_WAITLISTED)])

  assert repository.hasUncancelled(readState(store), 1, 1) is True


def testCountActiveForStudentSkipsCancelledAndFinished():
  """只统计未取消且活动尚未结束的报名。"""
  store, repository = prepareRepository()
  seed(
    store,
    registrations=[
      makeRegistration(1, 1, 1, STATUS_CONFIRMED),
      makeRegistration(2, 1, 2, STATUS_CONFIRMED),
      makeRegistration(3, 1, 3, STATUS_CANCELLED, cancelledAt=NOW - 60),
    ],
  )

  assert repository.countActiveForStudent(readState(store), 1, NOW) == 1


def testCountActiveIsZeroAtExactEnd():
  """活动恰好结束时不再占用额度。"""
  store, repository = prepareRepository()
  seed(store, registrations=[makeRegistration(1, 1, 2, STATUS_CONFIRMED)])
  activity = readState(store).activities[2]

  assert repository.countActiveForStudent(readState(store), 1, activity.endAt) == 0
  assert repository.countActiveForStudent(readState(store), 1, activity.endAt - 1) == 1


def testCountConfirmedIgnoresWaitlistedAndCancelled():
  """正式人数只统计 CONFIRMED 状态。"""
  store, repository = prepareRepository()
  seed(
    store,
    registrations=[
      makeRegistration(1, 1, 1, STATUS_CONFIRMED),
      makeRegistration(2, 2, 1, STATUS_CONFIRMED),
      makeRegistration(3, 3, 1, STATUS_WAITLISTED),
      makeRegistration(4, 4, 1, STATUS_CANCELLED, cancelledAt=NOW - 10),
    ],
  )

  assert repository.countConfirmed(readState(store), 1) == 2


def testFindFirstWaitlistedReturnsLowestId():
  """候补按编号升序，返回最小的一条。"""
  store, repository = prepareRepository()
  seed(
    store,
    registrations=[
      makeRegistration(9, 2, 1, STATUS_WAITLISTED),
      makeRegistration(4, 3, 1, STATUS_WAITLISTED),
      makeRegistration(6, 4, 1, STATUS_CONFIRMED),
    ],
  )

  candidate = repository.findFirstWaitlisted(readState(store), 1)

  assert candidate is not None
  assert candidate.registrationId == 4


def testFindFirstWaitlistedReturnsNoneWhenEmpty():
  """没有候补时返回 None。"""
  store, repository = prepareRepository()

  assert repository.findFirstWaitlisted(readState(store), 1) is None


def testInsertUsesNextRegistrationIdAndBumpsCounter():
  """新增记录使用草稿中的下一个编号并使计数器加一。"""
  store, repository = prepareRepository()

  registration = store.runWrite(
    lambda state: repository.insert(state, 1, 1, STATUS_CONFIRMED, NOW)
  )

  assert registration.registrationId == 1
  assert registration.cancelledAt is None
  state = readState(store)
  assert state.registrations[1] is registration

  second = store.runWrite(
    lambda draft: repository.insert(draft, 2, 1, STATUS_WAITLISTED, NOW)
  )

  assert second.registrationId == 2


def testCancelSetsStatusAndCancelledAt():
  """取消记录同时写入状态和取消时间，并保留原报名时间。"""
  store, repository = prepareRepository()
  seed(store, registrations=[makeRegistration(1, 1, 1, STATUS_CONFIRMED)])

  cancelled = store.runWrite(lambda state: repository.cancel(state, 1, NOW + 5))

  assert cancelled.status == STATUS_CANCELLED
  assert cancelled.cancelledAt == NOW + 5
  assert cancelled.joinedAt == NOW


def testConfirmKeepsJoinTimeAndClearsNothingElse():
  """候补转正式只改变状态。"""
  store, repository = prepareRepository()
  seed(store, registrations=[makeRegistration(1, 1, 1, STATUS_WAITLISTED)])

  confirmed = store.runWrite(lambda state: repository.confirm(state, 1))

  assert confirmed.status == STATUS_CONFIRMED
  assert confirmed.joinedAt == NOW
  assert confirmed.cancelledAt is None
