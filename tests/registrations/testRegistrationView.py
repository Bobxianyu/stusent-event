"""报名页的下拉加载、提交和取消流程测试。"""

import tkinter as tk
from tkinter import messagebox

import pytest

from campusApp.core.constants import ERROR_VALIDATION
from campusApp.core.contracts import Page, RegistrationRow, failure, success
from campusApp.registrations.RegistrationView import QUERY_PENDING_TEXT, RegistrationView
from registrationTestKit import (
  NOW,
  buildService,
  makeActivity,
  makeStudent,
  seed,
)


class StubStudentService:
  """返回预置学生列表的学生服务替身，可切换为失败场景。"""

  def __init__(self, students, ok: bool = True):
    """保存要返回的学生列表和成功标记。"""
    self._students = students
    self._ok = ok

  def listStudents(self):
    """返回预置学生或一个中文失败结果。"""
    if not self._ok:
      return failure(ERROR_VALIDATION, "读取学生失败")
    return success(self._students)


class StubActivityService:
  """返回预置活动列表的活动服务替身。"""

  def __init__(self, activities):
    """保存要返回的活动列表。"""
    self._activities = activities

  def listActivities(self):
    """返回预置活动列表。"""
    return success(self._activities)


class LiveQueryService:
  """直接读取共享存储的只读查询替身，模拟模块四的分页结果。"""

  def __init__(self, store):
    """绑定要读取的共享存储。"""
    self._store = store

  def listPersonalRegistrations(self, studentId: int, page: int, pageSize: int):
    """按学生编号拼装报名历史行并分页返回。"""
    def read(state):
      """在只读快照中关联活动、拼出 RegistrationRow。"""
      items = []
      for registration in sorted(state.registrations.values(), key=lambda item: item.registrationId):
        if registration.studentId != studentId:
          continue
        activity = state.activities.get(registration.activityId)
        items.append(
          RegistrationRow(
            registration.registrationId,
            registration.studentId,
            f"2023{registration.studentId:06d}",
            f"学生{registration.studentId}",
            registration.activityId,
            activity.title if activity is not None else "",
            registration.status,
            registration.joinedAt,
            registration.cancelledAt,
            activity.startAt if activity is not None else NOW,
            activity.endAt if activity is not None else NOW,
          )
        )
      return Page(items, len(items), page, pageSize)

    return success(self._store.runRead(read))


@pytest.fixture
def viewEnv(monkeypatch):
  """创建隐藏窗口和三个替身服务，避免测试弹窗。"""
  try:
    root = tk.Tk()
  except tk.TclError as error:
    pytest.skip(f"Tk 环境不可用：{error}")
  root.withdraw()
  monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
  monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
  store, service, clock, repository = buildService()
  students = [makeStudent(1), makeStudent(2)]
  activities = [makeActivity(1, capacity=1)]
  seed(store, students=students, activities=activities)
  view = RegistrationView(
    root,
    StubStudentService(students),
    StubActivityService(activities),
    service,
    LiveQueryService(store),
  )
  try:
    yield view, service, store, students, activities
  finally:
    root.destroy()


def testComboboxesAreFilledOnStartup(viewEnv):
  """启动后学生和活动下拉框都有可选项。"""
  view, service, store, students, activities = viewEnv

  assert len(view._students) == 2
  assert view.studentBox.cget("values")[0] == "2023000001 学生1"
  assert "容量 1" in view.activityBox.cget("values")[0]


def testSubmitRegistrationShowsConfirmedAndRefreshesHistory(viewEnv):
  """选中学生和活动后提交，界面提示正式报名并刷新历史。"""
  view, service, store, students, activities = viewEnv
  view.studentBox.current(0)
  view.activityBox.current(0)

  view.submitRegistration()

  assert "正式报名" in view.statusVar.get()
  assert "剩余名额 0" in view.statusVar.get()
  rows = view.historyList.get_children()
  assert len(rows) == 1
  assert view.historyList.item(rows[0], "values")[2] == "正式报名"


def testSecondStudentBecomesWaitlistedInView(viewEnv):
  """容量为 1 时第二名学生在界面显示候补。"""
  view, service, store, students, activities = viewEnv
  service.registerStudent(1, 1)
  view.studentBox.current(1)
  view.activityBox.current(0)

  view.submitRegistration()

  assert "候补" in view.statusVar.get()
  statuses = [view.historyList.item(row, "values")[2] for row in view.historyList.get_children()]
  assert "候补" in statuses


def testCancelSelectedRegistrationReportsPromotion(viewEnv):
  """取消选中记录后界面提示递补编号。"""
  view, service, store, students, activities = viewEnv
  service.registerStudent(1, 1)
  service.registerStudent(2, 1)
  view.studentBox.current(0)
  view._loadHistory()
  registrationId = view.historyList.get_children()[0]
  view.historyList.selection_set(registrationId)

  view.cancelSelectedRegistration()

  assert "已取消" in view.statusVar.get()
  assert "递补" in view.statusVar.get()
  assert view.historyList.item(registrationId, "values")[2] == "已取消"


def testMissingQueryServiceKeepsApplyUsable(monkeypatch):
  """查询模块未接入时只停用历史区，报名照常可用。"""
  try:
    root = tk.Tk()
  except tk.TclError as error:
    pytest.skip(f"Tk 环境不可用：{error}")
  root.withdraw()
  monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
  monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
  store, service, clock, repository = buildService()
  students = [makeStudent(1)]
  activities = [makeActivity(1, capacity=1)]
  seed(store, students=students, activities=activities)
  view = RegistrationView(
    root,
    StubStudentService(students),
    StubActivityService(activities),
    service,
  )
  try:
    assert view.pageLabel.cget("text") == QUERY_PENDING_TEXT
    view.studentBox.current(0)
    view.activityBox.current(0)
    view.submitRegistration()
    assert "正式报名" in view.statusVar.get()
    assert len(store.runRead(lambda state: state).registrations) == 1
  finally:
    root.destroy()


def testSubmitWithoutSelectionShowsError(viewEnv):
  """未选择学生或活动时不提交，只提示。"""
  view, service, store, students, activities = viewEnv

  view.submitRegistration()

  assert store.runRead(lambda state: state).registrations == {}
