"""QueryService 单元测试：普通边界 + 健壮边界 + 异常 + 一致读。"""
import pytest

from tests.queries.conftest import (
  makeStudent,
  makeActivity,
  makeReg,
  makeSeconds,
  seed,
)
from campusApp.core.constants import (
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
  STATUS_CANCELLED,
)
from campusApp.queries.QueryService import QueryService


# ---------- 个人报名历史：实体与参数 ----------

def testListPersonalStudentNotFound(queryService, queryStore):
  r = queryService.listPersonalRegistrations(999, 1, 10)
  assert r.ok is False
  assert r.error.code == "STUDENT_NOT_FOUND"


# 页码：普通边界 1/2/5000/9999/10000，健壮边界 0/10001
@pytest.mark.parametrize("page", [1, 2, 5000, 9999, 10000])
def testListPersonalPageNormalBoundary(queryService, queryStore, page):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])
  r = queryService.listPersonalRegistrations(1, page, 10)
  assert r.ok is True
  assert r.data.page == page
  assert r.data.items == []
  assert r.data.total == 0


@pytest.mark.parametrize("page", [0, -1, 10001])
def testListPersonalPageRobustBoundary(queryService, queryStore, page):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])
  r = queryService.listPersonalRegistrations(1, page, 10)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"
  assert r.error.field == "page"


# 每页条数：普通边界 1/2/50/99/100，健壮边界 0/101
@pytest.mark.parametrize("pageSize", [1, 2, 50, 99, 100])
def testListPersonalPageSizeNormalBoundary(queryService, queryStore, pageSize):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])
  r = queryService.listPersonalRegistrations(1, 1, pageSize)
  assert r.ok is True
  assert r.data.pageSize == pageSize


@pytest.mark.parametrize("pageSize", [0, -1, 101])
def testListPersonalPageSizeRobustBoundary(queryService, queryStore, pageSize):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])
  r = queryService.listPersonalRegistrations(1, 1, pageSize)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"
  assert r.error.field == "pageSize"


@pytest.mark.parametrize("badId", [0, -1, True, 1.5, "1", None])
def testListPersonalInvalidStudentId(queryService, queryStore, badId):
  r = queryService.listPersonalRegistrations(badId, 1, 10)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"
  assert r.error.field == "studentId"


def testListPersonalBoolPageRejected(queryService, queryStore):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])
  for field, args in (
    ("page", (1, True, 10)),
    ("pageSize", (1, 1, True)),
  ):
    r = queryService.listPersonalRegistrations(*args)
    assert r.ok is False
    assert r.error.code == "VALIDATION_ERROR"


# ---------- 个人报名历史：结果正确性 ----------

def testListPersonalTotalAndOrder(queryService, queryStore):
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1), makeActivity(2), makeActivity(3)],
    [
      makeReg(3, 1, 3, STATUS_CONFIRMED),
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 1, 2, STATUS_CANCELLED, cancelledAt=100),
    ],
  )
  r = queryService.listPersonalRegistrations(1, 1, 10)
  assert r.ok is True
  assert r.data.total == 3
  assert [x.registrationId for x in r.data.items] == [1, 2, 3]


def testListPersonalOnlyOwnRows(queryService, queryStore):
  seed(
    queryStore,
    [
      makeStudent(1, "2024010001", "张三"),
      makeStudent(2, "2024010002", "李四"),
    ],
    [makeActivity(1)],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 2, 1, STATUS_WAITLISTED),
    ],
  )
  r = queryService.listPersonalRegistrations(1, 1, 10)
  assert r.data.total == 1
  assert r.data.items[0].studentId == 1


def testListPersonalRowCarriesCurrentProfile(queryService, queryStore):
  # 学生改名后，历史报名查询显示当前姓名（8.1 需求）。
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, title="迎新晚会")],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  row = queryService.listPersonalRegistrations(1, 1, 10).data.items[0]
  assert row.studentNo == "2024010001"
  assert row.studentName == "张三"
  assert row.activityTitle == "迎新晚会"
  assert row.status == STATUS_CONFIRMED
  assert row.cancelledAt is None


def testListPersonalIncludesCancelledAndEnded(queryService, queryStore):
  # 个人历史包含已取消、已结束活动，不做时间过滤。
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [
      makeActivity(1, startAt=1000, endAt=2000),
      makeActivity(2, startAt=3000, endAt=4000),
    ],
    [
      makeReg(1, 1, 1, STATUS_CANCELLED, cancelledAt=900),
      makeReg(2, 1, 2, STATUS_CONFIRMED),
    ],
  )
  r = queryService.listPersonalRegistrations(1, 1, 10)
  assert r.data.total == 2
  assert [x.status for x in r.data.items] == [STATUS_CANCELLED, STATUS_CONFIRMED]


def testListPersonalBeyondLast(queryService, queryStore):
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  r = queryService.listPersonalRegistrations(1, 2, 10)
  assert r.ok is True
  assert r.data.total == 1
  assert r.data.items == []


def testListPersonalLastPagePartial(queryService, queryStore):
  # 5 条记录、每页 2 条：第 3 页应为 1 条，total 始终为 5。
  regs = [makeReg(i, 1, i, STATUS_CONFIRMED) for i in range(1, 6)]
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(i) for i in range(1, 6)],
    regs,
  )
  r = queryService.listPersonalRegistrations(1, 3, 2)
  assert r.ok is True
  assert r.data.total == 5
  assert len(r.data.items) == 1
  assert r.data.items[0].registrationId == 5


def testListPersonalPaginationNoOverlap(queryService, queryStore):
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(i) for i in range(1, 5)],
    [makeReg(i, 1, i, STATUS_CONFIRMED) for i in range(1, 5)],
  )
  first = queryService.listPersonalRegistrations(1, 1, 2).data.items
  second = queryService.listPersonalRegistrations(1, 2, 2).data.items
  firstIds = [x.registrationId for x in first]
  secondIds = [x.registrationId for x in second]
  assert firstIds == [1, 2]
  assert secondIds == [3, 4]
  assert set(firstIds).isdisjoint(secondIds)


# ---------- 活动报名名单 ----------

def testListActivityNotFound(queryService, queryStore):
  r = queryService.listActivityRegistrations(999, None, 1, 10)
  assert r.ok is False
  assert r.error.code == "ACTIVITY_NOT_FOUND"


@pytest.mark.parametrize("badStatus", ["", "UNKNOWN", 123, 0, True, ["STATUS_CONFIRMED"]])
def testListActivityInvalidStatus(queryService, queryStore, badStatus):
  seed(queryStore, [], [makeActivity(1)], [])
  r = queryService.listActivityRegistrations(1, badStatus, 1, 10)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"
  assert r.error.field == "status"


def testListActivityStatusFilter(queryService, queryStore):
  seed(
    queryStore,
    [
      makeStudent(1, "2024010001", "张三"),
      makeStudent(2, "2024010002", "李四"),
    ],
    [makeActivity(1, capacity=1)],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 2, 1, STATUS_WAITLISTED),
      makeReg(3, 1, 1, STATUS_CANCELLED, cancelledAt=100),
    ],
  )
  assert queryService.listActivityRegistrations(1, None, 1, 10).data.total == 3
  assert queryService.listActivityRegistrations(1, STATUS_CONFIRMED, 1, 10).data.total == 1
  assert queryService.listActivityRegistrations(1, STATUS_WAITLISTED, 1, 10).data.total == 1
  assert queryService.listActivityRegistrations(1, STATUS_CANCELLED, 1, 10).data.total == 1


def testListActivityFilterConsistentWithItems(queryService, queryStore):
  # 过滤条件与计数必须使用同一条件，total 与 items 数量一致。
  seed(
    queryStore,
    [makeStudent(i, "20240100%02d" % i, "学生%d" % i) for i in range(1, 4)],
    [makeActivity(1)],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 2, 1, STATUS_CONFIRMED),
      makeReg(3, 3, 1, STATUS_WAITLISTED),
    ],
  )
  page = queryService.listActivityRegistrations(1, STATUS_CONFIRMED, 1, 10).data
  assert page.total == 2
  assert len(page.items) == 2
  assert all(row.status == STATUS_CONFIRMED for row in page.items)


def testListActivityEmptyResultIsSuccess(queryService, queryStore):
  # 活动存在但没有记录：成功 + 空列表（8.3）。
  seed(queryStore, [], [makeActivity(1)], [])
  r = queryService.listActivityRegistrations(1, None, 1, 10)
  assert r.ok is True
  assert r.data.total == 0
  assert r.data.items == []


@pytest.mark.parametrize("page,pageSize", [(0, 10), (10001, 10), (1, 0), (1, 101)])
def testListActivityPagingValidation(queryService, queryStore, page, pageSize):
  seed(queryStore, [], [makeActivity(1)], [])
  r = queryService.listActivityRegistrations(1, None, page, pageSize)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


def testListActivityInvalidEntityId(queryService, queryStore):
  r = queryService.listActivityRegistrations(0, None, 1, 10)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


# ---------- 活动统计 ----------

def testGetActivityStatsNotFound(queryService, queryStore):
  r = queryService.getActivityStats(999)
  assert r.ok is False
  assert r.error.code == "ACTIVITY_NOT_FOUND"


def testGetActivityStatsCounts(queryService, queryStore):
  # 合法前置：张三先取消再正式报名（两条历史），李四正式，王五候补。
  seed(
    queryStore,
    [
      makeStudent(1, "2024010001", "张三"),
      makeStudent(2, "2024010002", "李四"),
      makeStudent(3, "2024010003", "王五"),
    ],
    [makeActivity(1, capacity=4)],
    [
      makeReg(1, 1, 1, STATUS_CANCELLED, cancelledAt=100),
      makeReg(2, 1, 1, STATUS_CONFIRMED),
      makeReg(3, 2, 1, STATUS_CONFIRMED),
      makeReg(4, 3, 1, STATUS_WAITLISTED),
    ],
  )
  r = queryService.getActivityStats(1)
  assert r.ok is True
  s = r.data
  assert s.capacity == 4
  assert s.confirmedCount == 2
  assert s.waitlistedCount == 1
  assert s.cancelledCount == 1
  assert s.remainingSeats == 2
  assert s.occupancyPercent == 50.0


def testGetActivityStatsEmptyActivity(queryService, queryStore):
  # 空活动：全部计数 0、剩余等于容量、占用率 0.0（不能除零）。
  seed(queryStore, [], [makeActivity(1, capacity=7)], [])
  s = queryService.getActivityStats(1).data
  assert s.confirmedCount == 0
  assert s.waitlistedCount == 0
  assert s.cancelledCount == 0
  assert s.remainingSeats == 7
  assert s.occupancyPercent == 0.0


def testGetActivityStatsFullActivity(queryService, queryStore):
  # 满员：容量 2，两名正式报名者（张三有一条取消历史），另有候补一人。
  seed(
    queryStore,
    [
      makeStudent(1, "2024010001", "张三"),
      makeStudent(2, "2024010002", "李四"),
      makeStudent(3, "2024010003", "王五"),
    ],
    [makeActivity(1, capacity=2)],
    [
      makeReg(1, 1, 1, STATUS_CANCELLED, cancelledAt=10),
      makeReg(2, 1, 1, STATUS_CONFIRMED),
      makeReg(3, 2, 1, STATUS_CONFIRMED),
      makeReg(4, 3, 1, STATUS_WAITLISTED),
    ],
  )
  s = queryService.getActivityStats(1).data
  assert s.confirmedCount == 2
  assert s.cancelledCount == 1
  assert s.waitlistedCount == 1
  assert s.remainingSeats == 0
  assert s.occupancyPercent == 100.0


def testGetActivityStatsOccupancyRounding(queryService, queryStore):
  # 1/3 = 33.333...% → 保留两位小数 33.33；2/3 → 66.67。
  seed(
    queryStore,
    [makeStudent(i, "20240100%02d" % i, "学生%d" % i) for i in range(1, 4)],
    [makeActivity(1, capacity=3)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  assert queryService.getActivityStats(1).data.occupancyPercent == 33.33
  seed(
    queryStore,
    [makeStudent(i, "20240100%02d" % i, "学生%d" % i) for i in range(1, 4)],
    [makeActivity(1, capacity=3)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED), makeReg(2, 2, 1, STATUS_CONFIRMED)],
  )
  assert queryService.getActivityStats(1).data.occupancyPercent == 66.67


def testGetActivityStatsMinimumCapacity(queryService, queryStore):
  # 容量下边界 1：无报名时占用率 0.0，1 人时 100.0。
  seed(queryStore, [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, capacity=1)], [])
  assert queryService.getActivityStats(1).data.occupancyPercent == 0.0
  seed(queryStore, [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, capacity=1)], [makeReg(1, 1, 1, STATUS_CONFIRMED)])
  assert queryService.getActivityStats(1).data.occupancyPercent == 100.0


def testGetActivityStatsWaitlistDoesNotOccupySeat(queryService, queryStore):
  # 候补不计入已占名额（8.3 明确口径）。
  seed(
    queryStore,
    [makeStudent(i, "20240100%02d" % i, "学生%d" % i) for i in range(1, 4)],
    [makeActivity(1, capacity=2)],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 2, 1, STATUS_CONFIRMED),
      makeReg(3, 3, 1, STATUS_WAITLISTED),
    ],
  )
  s = queryService.getActivityStats(1).data
  assert s.confirmedCount == 2
  assert s.waitlistedCount == 1
  assert s.remainingSeats == 0
  assert s.occupancyPercent == 100.0


@pytest.mark.parametrize("badId", [0, -1, None, "1", 2.5])
def testGetActivityStatsInvalidId(queryService, queryStore, badId):
  r = queryService.getActivityStats(badId)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


def testGetActivityStatsDoesNotMutateStore(queryService, queryStore):
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  before = queryStore.runRead(
    lambda s: (len(s.students), len(s.activities), len(s.registrations))
  )
  queryService.getActivityStats(1)
  after = queryStore.runRead(
    lambda s: (len(s.students), len(s.activities), len(s.registrations))
  )
  assert before == after


# ---------- 总览统计：天数边界 ----------

@pytest.mark.parametrize("days", [1, 2, 180, 364, 365])
def testGetOverviewDaysNormalBoundary(queryService, queryStore, days):
  r = queryService.getOverviewStats("2025-01-01", days)
  assert r.ok is True
  assert r.data.activityCount == 0


@pytest.mark.parametrize("days", [0, -1, 366])
def testGetOverviewDaysRobustBoundary(queryService, queryStore, days):
  r = queryService.getOverviewStats("2025-01-01", days)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"
  assert r.error.field == "days"


@pytest.mark.parametrize("days", [True, 1.5, "30", None])
def testGetOverviewDaysMustBeInteger(queryService, queryStore, days):
  r = queryService.getOverviewStats("2025-01-01", days)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


# ---------- 总览统计：日期合法性 ----------

@pytest.mark.parametrize(
  "badDate",
  ["", "2025-1-1", "2025/01/01", "2025-13-01", "2025-02-30", "20250101",
  "2025-01-01 00:00:00", "abc"],
)
def testGetOverviewInvalidDate(queryService, queryStore, badDate):
  r = queryService.getOverviewStats(badDate, 30)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"
  assert r.error.field == "startDate"


@pytest.mark.parametrize("badDate", [20250101, None, ["2025-01-01"]])
def testGetOverviewDateMustBeString(queryService, queryStore, badDate):
  r = queryService.getOverviewStats(badDate, 30)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


def testGetOverviewLeapDay(queryService, queryStore):
  # 2024 是闰年，2 月 29 日合法；往后 1 天命中 3 月 1 日的活动。
  feb28 = makeSeconds("2024-02-28")
  leap = makeSeconds("2024-02-29")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, startAt=leap, endAt=leap + 3600)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  assert queryService.getOverviewStats("2024-02-29", 1).data.activityCount == 1
  assert queryService.getOverviewStats("2024-02-28", 1).data.activityCount == 0
  assert queryService.getOverviewStats("2024-02-28", 2).data.activityCount == 1
  del feb28


@pytest.mark.parametrize("nonLeapDay", ["2023-02-29", "2025-02-29"])
def testGetOverviewNonLeapFeb29(queryService, queryStore, nonLeapDay):
  r = queryService.getOverviewStats(nonLeapDay, 1)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


def testGetOverviewCrossMonth(queryService, queryStore):
  jan31 = makeSeconds("2025-01-31")
  feb01 = makeSeconds("2025-02-01")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [
      makeActivity(1, startAt=jan31, endAt=jan31 + 3600),
      makeActivity(2, startAt=feb01, endAt=feb01 + 3600),
    ],
    [makeReg(1, 1, 1, STATUS_CONFIRMED), makeReg(2, 1, 2, STATUS_CONFIRMED)],
  )
  assert queryService.getOverviewStats("2025-01-31", 1).data.activityCount == 1
  assert queryService.getOverviewStats("2025-01-31", 2).data.activityCount == 2


def testGetOverviewCrossYear(queryService, queryStore):
  dec31 = makeSeconds("2025-12-31")
  jan01 = makeSeconds("2026-01-01")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [
      makeActivity(1, startAt=dec31, endAt=dec31 + 3600),
      makeActivity(2, startAt=jan01, endAt=jan01 + 3600),
    ],
    [makeReg(1, 1, 1, STATUS_CONFIRMED), makeReg(2, 1, 2, STATUS_CONFIRMED)],
  )
  assert queryService.getOverviewStats("2025-12-31", 1).data.activityCount == 1
  assert queryService.getOverviewStats("2025-12-31", 2).data.activityCount == 2


# ---------- 总览统计：区间包含 / 排除 ----------

def testGetOverviewStartBoundaryIncluded(queryService, queryStore):
  day = makeSeconds("2025-03-10")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, startAt=day, endAt=day + 3600)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  assert queryService.getOverviewStats("2025-03-10", 1).data.activityCount == 1


def testGetOverviewEndBoundaryExcluded(queryService, queryStore):
  # 区间 [startDate, startDate+days)：恰好落在终点那一秒的活动被排除。
  day = makeSeconds("2025-03-10")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, startAt=day + 86400, endAt=day + 86400 + 3600)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  assert queryService.getOverviewStats("2025-03-10", 1).data.activityCount == 0
  assert queryService.getOverviewStats("2025-03-10", 2).data.activityCount == 1


def testGetOverviewEndsAtUpperBound(queryService, queryStore):
  # 统计终点恰好等于 2100-01-01 00:00:00 允许；活动刚好在那之前开始则计入。
  dec31 = makeSeconds("2099-12-31", hour=23)
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, startAt=dec31, endAt=dec31 + 3600)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  r = queryService.getOverviewStats("2099-12-31", 1)
  assert r.ok is True
  assert r.data.activityCount == 1


def testGetOverviewExceedsUpperBound(queryService, queryStore):
  # 2099-12-31 + 365 天越过 2100-01-01 上界 → VALIDATION_ERROR。
  r = queryService.getOverviewStats("2099-12-31", 365)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("badYear", ["1999-12-31", "2100-01-01"])
def testGetOverviewDateOutOfRange(queryService, queryStore, badYear):
  r = queryService.getOverviewStats(badYear, 1)
  assert r.ok is False
  assert r.error.code == "VALIDATION_ERROR"


# ---------- 总览统计：计数口径 ----------

def testGetOverviewCountsByStartRange(queryService, queryStore):
  seed(
    queryStore,
    [
      makeStudent(1, "2024010001", "张三"),
      makeStudent(2, "2024010002", "李四"),
    ],
    [
      makeActivity(1, startAt=1_735_689_600, endAt=1_735_693_200),
      makeActivity(2, startAt=1_735_776_000, endAt=1_735_779_600),
    ],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 2, 1, STATUS_WAITLISTED),
      makeReg(3, 1, 2, STATUS_CONFIRMED),
    ],
  )
  r = queryService.getOverviewStats("2025-01-01", 1)
  assert r.ok is True
  s = r.data
  assert s.activityCount == 1
  assert s.confirmedCount == 1
  assert s.waitlistedCount == 1
  assert s.distinctParticipantCount == 1


def testGetOverviewDistinctParticipantDedup(queryService, queryStore):
  # 同一学生正式参加两个活动只计一人；候补学生不计入 distinct。
  day = makeSeconds("2025-05-01")
  seed(
    queryStore,
    [
      makeStudent(1, "2024010001", "张三"),
      makeStudent(2, "2024010002", "李四"),
      makeStudent(3, "2024010003", "王五"),
    ],
    [
      makeActivity(1, startAt=day, endAt=day + 3600),
      makeActivity(2, startAt=day + 7200, endAt=day + 10800),
    ],
    [
      makeReg(1, 1, 1, STATUS_CONFIRMED),
      makeReg(2, 1, 2, STATUS_CONFIRMED),
      makeReg(3, 2, 1, STATUS_WAITLISTED),
      makeReg(4, 3, 2, STATUS_CANCELLED, cancelledAt=day),
    ],
  )
  s = queryService.getOverviewStats("2025-05-01", 1).data
  assert s.activityCount == 2
  assert s.confirmedCount == 2
  assert s.waitlistedCount == 1
  assert s.cancelledCount == 1
  assert s.distinctParticipantCount == 1


def testGetOverviewIncludesRegistrationBeforeRange(queryService, queryStore):
  # 活动在区间内开始，但报名时间早于区间开始 → 仍计入当前状态。
  day = makeSeconds("2025-06-01")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, startAt=day, endAt=day + 3600)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED, joinedAt=day - 86400 * 30)],
  )
  s = queryService.getOverviewStats("2025-06-01", 1).data
  assert s.confirmedCount == 1
  assert s.distinctParticipantCount == 1


def testGetOverviewIgnoresOutOfRangeActivities(queryService, queryStore):
  # 区间外活动的报名不计入总览。
  day = makeSeconds("2025-07-01")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [
      makeActivity(1, startAt=day, endAt=day + 3600),
      makeActivity(2, startAt=day + 86400 * 10, endAt=day + 86400 * 10 + 3600),
    ],
    [makeReg(1, 1, 1, STATUS_CONFIRMED), makeReg(2, 1, 2, STATUS_CONFIRMED)],
  )
  s = queryService.getOverviewStats("2025-07-01", 1).data
  assert s.activityCount == 1
  assert s.confirmedCount == 1


def testGetOverviewEmptyStore(queryService, queryStore):
  s = queryService.getOverviewStats("2025-01-01", 30).data
  assert s.activityCount == 0
  assert s.confirmedCount == 0
  assert s.waitlistedCount == 0
  assert s.cancelledCount == 0
  assert s.distinctParticipantCount == 0


def testGetOverviewUnknownStatusFailsLoudly(queryService, queryStore):
  # 回归用例：仓储遇到未知状态必须失败，Service 需转为 INTERNAL_ERROR。
  day = makeSeconds("2025-08-01")
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1, startAt=day, endAt=day + 3600)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )

  def corrupt(state):
    state.registrations[1] = makeReg(1, 1, 1, "UNKNOWN")

  class _State:
    students = queryStore.runRead(lambda s: s.students)
    activities = queryStore.runRead(lambda s: s.activities)
    registrations = {1: makeReg(1, 1, 1, "UNKNOWN")}

  from campusApp.queries.QueryRepository import QueryRepository

  repo = QueryRepository()
  with pytest.raises(ValueError):
    repo.summarizeByStartRange(_State, 0, 10 ** 12)
  del corrupt


# ---------- 一致读 ----------

def testPageSnapshotConsistentUnderLaterWrite(queryService, queryStore):
  # 分页 total 与 items 取自同一只读快照；后续写入不影响已取快照。
  seed(
    queryStore,
    [makeStudent(1, "2024010001", "张三")],
    [makeActivity(1), makeActivity(2)],
    [makeReg(1, 1, 1, STATUS_CONFIRMED)],
  )
  page = queryService.listPersonalRegistrations(1, 1, 10).data
  assert page.total == 1

  def addMore(state):
    state.activities[2] = makeActivity(2)
    from campusApp.core.contracts import Registration
    state.registrations[2] = Registration(
      registrationId=2, studentId=1, activityId=2,
      status=STATUS_CONFIRMED, joinedAt=0, cancelledAt=None,
    )
    state.nextRegistrationId = 3
    state.nextActivityId = 3

  queryStore.runWrite(addMore)
  assert len(page.items) == 1
  fresh = queryService.listPersonalRegistrations(1, 1, 10).data
  assert fresh.total == 2


def testSnapshotIsReadOnly(queryService, queryStore):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])

  def attempt(state):
    try:
      state.students[99] = makeStudent(99, "2024010099", "越权")
      return "written"
    except TypeError:
      return "blocked"

  assert queryStore.runRead(attempt) == "blocked"
  assert queryService.listPersonalRegistrations(99, 1, 10).error.code == (
    "STUDENT_NOT_FOUND"
  )


# ---------- 非预期异常的兜底转换 ----------

class _BrokenRepository:
  """模拟仓储内部故障：任何读取都抛非业务异常，Service 必须转 INTERNAL_ERROR。"""

  def __getattr__(self, name):
    def boom(*args, **kwargs):
      raise RuntimeError("模拟内部故障：%s" % name)
    return boom


@pytest.fixture
def brokenService(queryStore, queryClock):
  return QueryService(queryStore, _BrokenRepository(), queryClock)


def testListPersonalInternalError(brokenService, queryStore):
  seed(queryStore, [makeStudent(1, "2024010001", "张三")], [], [])
  r = brokenService.listPersonalRegistrations(1, 1, 10)
  assert r.ok is False
  assert r.error.code == "INTERNAL_ERROR"
  assert r.error.message == "查询个人报名记录时发生内部错误"
  assert r.data is None


def testListActivityInternalError(brokenService, queryStore):
  seed(queryStore, [], [makeActivity(1)], [])
  r = brokenService.listActivityRegistrations(1, None, 1, 10)
  assert r.ok is False
  assert r.error.code == "INTERNAL_ERROR"
  assert r.error.message == "查询活动报名名单时发生内部错误"
  assert r.data is None


def testGetActivityStatsInternalError(brokenService, queryStore):
  seed(queryStore, [], [makeActivity(1)], [])
  r = brokenService.getActivityStats(1)
  assert r.ok is False
  assert r.error.code == "INTERNAL_ERROR"
  assert r.error.message == "统计活动时发生内部错误"
  assert r.data is None


def testGetOverviewInternalError(brokenService, queryStore):
  seed(queryStore, [], [], [])
  r = brokenService.getOverviewStats("2025-01-01", 30)
  assert r.ok is False
  assert r.error.code == "INTERNAL_ERROR"
  assert r.error.message == "总览统计时发生内部错误"
  assert r.data is None
