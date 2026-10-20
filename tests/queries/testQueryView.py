"""QueryView 界面冒烟测试。

目的不是替代人工截图，而是把「界面取到的值是否正确」这类可自动化的缺陷钉住：
下拉框按文本定位实体、刷新后保留选择、无结果与错误的提示文案。
运行环境没有图形显示时自动跳过。
"""
import pytest

tk = pytest.importorskip("tkinter")
ttk = pytest.importorskip("tkinter.ttk")

from campusApp.core.contracts import success, failure  # noqa: E402
from campusApp.core.timeUtils import MAX_TIMESTAMP  # noqa: E402
from campusApp.core.constants import STATUS_CONFIRMED, STATUS_WAITLISTED  # noqa: E402
from campusApp.queries.QueryRepository import QueryRepository  # noqa: E402
from campusApp.queries.QueryService import QueryService  # noqa: E402
from campusApp.queries.QueryView import QueryView, UNKNOWN_TIME_TEXT  # noqa: E402

from tests.queries.conftest import (  # noqa: E402
  FixedClock,
  makeActivity,
  makeReg,
  makeStudent,
  makeSeconds,
  seed,
)


class FakeStudentService:
  def __init__(self, students=None, fail=False):
    self.students = list(students or [])
    self.fail = fail

  def listStudents(self):
    if self.fail:
      return failure("INTERNAL_ERROR", "模拟学生列表故障")
    return success(list(self.students))


class FakeActivityService:
  def __init__(self, activities=None, fail=False):
    self.activities = list(activities or [])
    self.fail = fail

  def listActivities(self):
    if self.fail:
      return failure("INTERNAL_ERROR", "模拟活动列表故障")
    return success(list(self.activities))


@pytest.fixture(scope="module")
def tkRoot():
  # 一个进程只创建一次 Tk 根窗口：反复创建/销毁会触发
  # invalid command name "tcl_findLibrary" 的 Tk 拆卸竞态。
  try:
    root = tk.Tk()
  except tk.TclError as exc:  # pragma: no cover - 无显示环境
    pytest.skip("当前环境没有可用的图形显示：%s" % exc)
  root.withdraw()
  yield root
  root.destroy()


@pytest.fixture
def viewHost(tkRoot):
  # 每个用例一个独立容器，用例结束即销毁，避免控件互相干扰。
  frame = ttk.Frame(tkRoot)
  yield frame
  frame.destroy()


def buildView(parent, queryStore, students, activities, studentFail=False,
        activityFail=False, clockNow=0):
  service = QueryService(queryStore, QueryRepository(), FixedClock(clockNow))
  return QueryView(
    parent,
    FakeStudentService(students, fail=studentFail),
    FakeActivityService(activities, fail=activityFail),
    service,
  ), service


def testViewBuildsAndListsOptions(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三"),
        makeStudent(2, "2024010002", "李四")]
  activities = [makeActivity(1, title="迎新晚会")]
  view, _ = buildView(viewHost, queryStore, students, activities)

  assert list(view.personalStudent["values"]) == [
    "2024010001 - 张三", "2024010002 - 李四"
  ]
  assert list(view.activityActivity["values"]) == ["1 - 迎新晚会"]
  assert view.personalStudent.get() == "2024010001 - 张三"
  assert view.optionHint.get() == ""


def testSelectionResolvesEntityNotIndex(viewHost, queryStore):
  # 顺序变化后，界面必须按当前文本定位实体，不能沿用旧索引。
  students = [makeStudent(1, "2024010001", "张三"),
        makeStudent(2, "2024010002", "李四")]
  view, _ = buildView(viewHost, queryStore, students, [])
  view.personalStudent.set("2024010002 - 李四")
  assert view._resolveStudentId(view.personalStudent) == 2

  # 反过来把学生列表换序后刷新，仍然指向李四。
  view.studentService.students = list(reversed(students))
  view.refresh()
  assert view.personalStudent.get() == "2024010002 - 李四"
  assert view._resolveStudentId(view.personalStudent) == 2


def testRefreshKeepsSelectionWhenStillPresent(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三"),
        makeStudent(2, "2024010002", "李四")]
  view, _ = buildView(viewHost, queryStore, students, [])
  view.personalStudent.set("2024010002 - 李四")
  view.refresh()
  assert view.personalStudent.get() == "2024010002 - 李四"


def testRefreshClearsVanishedSelection(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三"),
        makeStudent(2, "2024010002", "李四")]
  view, _ = buildView(viewHost, queryStore, students, [])
  view.personalStudent.set("2024010002 - 李四")
  view.studentService.students = [students[0]]
  view.refresh()
  assert view.personalStudent.get() == "2024010001 - 张三"


def testRefreshSurfacesOptionErrors(viewHost, queryStore):
  view, _ = buildView(
    viewHost, queryStore, [], [], studentFail=True, activityFail=True
  )
  hint = view.optionHint.get()
  assert "学生列表加载失败" in hint
  assert "活动列表加载失败" in hint
  assert view.personalStudent.get() == ""


def testPersonalQueryShowsNoResultHint(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三")]
  seed(queryStore, students, [], [])
  view, _ = buildView(viewHost, queryStore, students, [])
  view._onQueryPersonal()
  assert view.personalResult.get() == "该学生暂无报名记录"
  assert view.personalTree.get_children() == ()


def testFormatTimeFallbackForOutOfRange(viewHost, queryStore):
  # 回归用例（缺陷 D-8）：真实 formatDateTime 会校验业务时间范围，
  # 越界时间戳不能让整个查询页抛异常，必须显示占位符。
  view, _ = buildView(viewHost, queryStore, [], [])
  assert view._formatTime(None) == ""
  assert view._formatTime(0) == UNKNOWN_TIME_TEXT
  assert view._formatTime(1024) == UNKNOWN_TIME_TEXT
  assert view._formatTime(MAX_TIMESTAMP) == "2100-01-01 00:00:00"
  assert view._formatTime(MAX_TIMESTAMP + 1) == UNKNOWN_TIME_TEXT
  assert view._formatTime(makeSeconds("2025-01-02", 9)) == "2025-01-02 09:00:00"


def testOutOfRangeTimestampRendersPlaceholder(viewHost, queryStore):
  # 端到端：一条 joinedAt 越界的历史记录仍能正常渲染成一行。
  students = [makeStudent(1, "2024010001", "张三")]
  activities = [makeActivity(1, title="迎新晚会")]
  seed(queryStore, students, activities,
       [makeReg(1, 1, 1, STATUS_CONFIRMED, joinedAt=0)])
  view, _ = buildView(viewHost, queryStore, students, activities)
  view._onQueryPersonal()
  rows = view.personalTree.get_children()
  assert len(rows) == 1
  assert view.personalTree.item(rows[0], "values")[3] == UNKNOWN_TIME_TEXT


def testPersonalQueryFillsTree(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三")]
  activities = [makeActivity(1, title="迎新晚会",
                startAt=makeSeconds("2025-01-02", 9),
                endAt=makeSeconds("2025-01-02", 10))]
  seed(queryStore, students, activities, [makeReg(1, 1, 1, STATUS_CONFIRMED)])
  view, _ = buildView(viewHost, queryStore, students, activities, clockNow=0)
  view._onQueryPersonal()

  assert "共 1 条" in view.personalResult.get()
  rows = view.personalTree.get_children()
  assert len(rows) == 1
  values = view.personalTree.item(rows[0], "values")
  assert values[1] == "迎新晚会"
  assert values[2] == "正式报名"
  assert values[4] == ""


def testPersonalQueryShowsServiceError(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三")]
  view, _ = buildView(viewHost, queryStore, students, [])
  view.personalPage.set("0")
  view._onQueryPersonal()
  assert view.personalResult.get().startswith("错误：")
  assert view.personalTree.get_children() == ()


def testPersonalQueryRejectsNonIntegerPaging(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三")]
  view, _ = buildView(viewHost, queryStore, students, [])
  view.personalPage.set("abc")
  view._onQueryPersonal()
  assert view.personalResult.get() == "页码或每页必须是整数"


def testPersonalQueryWithoutStudent(viewHost, queryStore):
  view, _ = buildView(viewHost, queryStore, [], [])
  view._onQueryPersonal()
  assert view.personalResult.get() == "请先选择学生"


def testActivityQueryStatusFilter(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三"),
        makeStudent(2, "2024010002", "李四")]
  activities = [makeActivity(1, capacity=1)]
  seed(queryStore, students, activities, [
    makeReg(1, 1, 1, STATUS_CONFIRMED),
    makeReg(2, 2, 1, STATUS_WAITLISTED),
  ])
  view, _ = buildView(viewHost, queryStore, students, activities)

  view.activityStatus.set("候补")
  view._onQueryActivity()
  rows = view.activityTree.get_children()
  assert len(rows) == 1
  assert view.activityTree.item(rows[0], "values")[2] == "李四"

  view.activityStatus.set("全部")
  view._onQueryActivity()
  assert len(view.activityTree.get_children()) == 2


def testActivityQueryNoResultHint(viewHost, queryStore):
  activities = [makeActivity(1)]
  seed(queryStore, [], activities, [])
  view, _ = buildView(viewHost, queryStore, [], activities)
  view._onQueryActivity()
  assert view.activityResult.get() == "该活动暂无符合条件的报名记录"


def testStatsQueryFormatsResult(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三")]
  activities = [makeActivity(1, capacity=4)]
  seed(queryStore, students, activities, [makeReg(1, 1, 1, STATUS_CONFIRMED)])
  view, _ = buildView(viewHost, queryStore, students, activities)
  view._onQueryStats()
  text = view.statsResult.get()
  assert "容量：4" in text
  assert "正式报名：1" in text
  assert "占用率：25.00%" in text


def testOverviewQueryNoActivityHint(viewHost, queryStore):
  view, _ = buildView(viewHost, queryStore, [], [])
  view.overviewDate.set("2025-01-01")
  view.overviewDays.set("30")
  view._onQueryOverview()
  assert view.overviewResult.get() == "该时间范围内没有活动"


def testOverviewQueryInvalidDays(viewHost, queryStore):
  view, _ = buildView(viewHost, queryStore, [], [])
  view.overviewDays.set("abc")
  view._onQueryOverview()
  assert view.overviewResult.get() == "天数必须是整数"


def testOverviewQueryFormatsResult(viewHost, queryStore):
  students = [makeStudent(1, "2024010001", "张三")]
  day = makeSeconds("2025-05-01", 9)
  activities = [makeActivity(1, startAt=day, endAt=day + 3600)]
  seed(queryStore, students, activities, [makeReg(1, 1, 1, STATUS_CONFIRMED)])
  view, _ = buildView(viewHost, queryStore, students, activities)
  view.overviewDate.set("2025-05-01")
  view.overviewDays.set("1")
  view._onQueryOverview()
  text = view.overviewResult.get()
  assert "活动数量：1" in text
  assert "去重参与学生数：1" in text
