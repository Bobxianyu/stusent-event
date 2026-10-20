"""活动管理的边界、异常和状态测试。"""

from dataclasses import dataclass

import pytest

from campusApp.activities.ActivityRepository import ActivityRepository
from campusApp.activities.ActivityService import ActivityService
from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.constants import ERROR_ACTIVITY_NOT_FOUND, ERROR_INTERNAL, ERROR_VALIDATION
from campusApp.core.timeUtils import parseDateTime


FIXED_NOW = parseDateTime("2027-03-01 00:00:00", "now")
OPEN_AT = FIXED_NOW - 60
CLOSE_AT = FIXED_NOW + 3_600
START_AT = FIXED_NOW + 7_200


@dataclass
class FixedClock:
  """固定时间，避免用例依赖执行当天。"""

  current: int = FIXED_NOW

  def now(self):
    """返回固定 Unix 秒。"""
    return self.current


def makeService(repository=None, current=FIXED_NOW):
  """为每个用例准备独立内存。"""
  store = MemoryStore()
  activityRepository = repository or ActivityRepository()
  service = ActivityService(store, activityRepository, FixedClock(current))
  return store, service, activityRepository


def createActivity(service, **overrides):
  """用合法默认值创建活动，允许覆盖一个待测输入。"""
  values = {
    "title": " 校园音乐会 ",
    "capacity": 50,
    "durationMinutes": 120,
    "openAt": OPEN_AT,
    "closeAt": CLOSE_AT,
    "startAt": START_AT,
  }
  values.update(overrides)
  return service.createActivity(**values)


@pytest.mark.parametrize("capacity", [1, 2, 50, 99, 100])
def testCapacityNormalBoundary(capacity):
  """容量有效边界和正常值均可创建。"""
  _, service, _ = makeService()

  result = createActivity(service, capacity=capacity)

  assert result.ok
  assert result.data.capacity == capacity
  assert result.data.title == "校园音乐会"
  assert result.data.endAt == START_AT + 120 * 60


@pytest.mark.parametrize("capacity", [0, 101, True, 1.5, "3"])
def testCapacityRobustBoundary(capacity):
  """超出范围或类型错误的容量被拒绝。"""
  store, service, _ = makeService()

  result = createActivity(service, capacity=capacity)

  assert not result.ok
  assert result.error.code == ERROR_VALIDATION
  assert len(store.runRead(lambda state: state.activities)) == 0


@pytest.mark.parametrize("durationMinutes", [30, 31, 120, 239, 240])
def testDurationNormalBoundary(durationMinutes):
  """时长有效边界和正常值均可创建。"""
  _, service, _ = makeService()

  result = createActivity(service, durationMinutes=durationMinutes)

  assert result.ok
  assert result.data.endAt == START_AT + durationMinutes * 60


@pytest.mark.parametrize("durationMinutes", [29, 241, False, 30.0, "30"])
def testDurationRobustBoundary(durationMinutes):
  """时长超界和非整数输入被拒绝。"""
  _, service, _ = makeService()

  result = createActivity(service, durationMinutes=durationMinutes)

  assert not result.ok
  assert result.error.code == ERROR_VALIDATION


@pytest.mark.parametrize("title", ["甲", "甲" * 41, "   ", None])
def testTitleRobustBoundary(title):
  """名称长度和类型不合规时不创建活动。"""
  _, service, _ = makeService()

  result = createActivity(service, title=title)

  assert not result.ok
  assert result.error.code == ERROR_VALIDATION


@pytest.mark.parametrize("title", ["甲乙", "甲" * 40])
def testTitleNormalBoundary(title):
  """名称最小和最大长度均可接受。"""
  _, service, _ = makeService()

  assert createActivity(service, title=title).ok


def testTimeOrderAndInclusiveClosingAtStart():
  """报名截止可等于开始；其他时间逆序均失败。"""
  _, service, _ = makeService()

  assert createActivity(service, closeAt=START_AT).ok
  assert createActivity(service, closeAt=OPEN_AT).error.code == ERROR_VALIDATION
  assert createActivity(service, closeAt=START_AT + 1).error.code == ERROR_VALIDATION


def testStartAtNowRejectedWithoutConsumingId():
  """活动必须在未来开始，失败时编号不消耗。"""
  store, service, _ = makeService()

  result = createActivity(service, closeAt=FIXED_NOW, startAt=FIXED_NOW)

  assert result.error.code == ERROR_VALIDATION
  assert store.runWrite(lambda state: state.nextActivityId) == 1


def testTimeRangeUpperBound():
  """结束恰好达到时间上界合法，超过时拒绝。"""
  upperStart = parseDateTime("2099-12-31 23:30:00", "startAt")
  _, service, _ = makeService()

  accepted = createActivity(service, openAt=upperStart - 60, closeAt=upperStart, startAt=upperStart,
                            durationMinutes=30)
  rejected = createActivity(service, openAt=upperStart - 60, closeAt=upperStart, startAt=upperStart + 60,
                            durationMinutes=30)

  assert accepted.ok
  assert rejected.error.code == ERROR_VALIDATION


def testRenameKeepsCapacityAndTime():
  """改名只更新名称，不改变其他配置。"""
  _, service, _ = makeService()
  original = createActivity(service).data

  renamed = service.updateActivityTitle(original.activityId, " 新活动名称 ")

  assert renamed.ok
  assert renamed.data.title == "新活动名称"
  assert renamed.data.capacity == original.capacity
  assert renamed.data.startAt == original.startAt
  assert service.getActivity(original.activityId).data == renamed.data


def testCloseRegistrationIsIdempotent():
  """重复关闭报名返回同一活动。"""
  _, service, _ = makeService()
  activityId = createActivity(service).data.activityId

  first = service.closeRegistration(activityId)
  second = service.closeRegistration(activityId)

  assert first.ok and second.ok
  assert first.data == second.data
  assert first.data.isClosed is True


def testListActivitiesUsesStableOrder():
  """列表先按活动开始时间，再按编号排序。"""
  _, service, _ = makeService()
  later = createActivity(service, title="较晚活动").data
  earlier = createActivity(service, title="较早活动", closeAt=FIXED_NOW + 1_000,
                           startAt=FIXED_NOW + 2_000).data
  same = createActivity(service, title="同时间活动").data

  assert [item.activityId for item in service.listActivities().data] == [earlier.activityId, later.activityId,
                                                                         same.activityId]


def testMissingActivityAndInvalidId():
  """不存在活动和非法编号返回各自错误。"""
  _, service, _ = makeService()

  assert service.getActivity(1).error.code == ERROR_ACTIVITY_NOT_FOUND
  assert service.updateActivityTitle(1, "有效名称").error.code == ERROR_ACTIVITY_NOT_FOUND
  assert service.closeRegistration(1).error.code == ERROR_ACTIVITY_NOT_FOUND
  assert service.getActivity(True).error.code == ERROR_VALIDATION


def testReaderSeesCurrentDraft():
  """仓储读取器可以使用外部模块的同一写入草稿。"""
  store, service, repository = makeService()
  activityId = createActivity(service).data.activityId

  assert store.runWrite(lambda state: repository.findById(state, activityId)).activityId == activityId


def testRepositoryFailureDiscardsDraft():
  """仓储写入后报错时不发布活动，也不消耗编号。"""
  class FailingRepository(ActivityRepository):
    """在写入草稿后模拟意外失败。"""

    def insert(self, *args, **kwargs):
      """调用原写入后抛出异常。"""
      super().insert(*args, **kwargs)
      raise RuntimeError("模拟写入失败")

  store, service, _ = makeService(repository=FailingRepository())

  result = createActivity(service)

  assert result.error.code == ERROR_INTERNAL
  assert len(store.runRead(lambda state: state.activities)) == 0
  assert store.runWrite(lambda state: state.nextActivityId) == 1
