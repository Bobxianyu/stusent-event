"""四模块共用内存的真实业务流程。"""

import tkinter as tk
from tkinter import messagebox, ttk

import pytest

from campusApp.app import buildApp, buildServices
from campusApp.core.constants import STATUS_CANCELLED, STATUS_CONFIRMED, STATUS_WAITLISTED
from campusApp.core.timeUtils import parseDateTime


NOW = parseDateTime("2026-10-20 09:00:00", "当前时间")
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60


class FixedClock:
  """让联调场景使用固定时刻。"""

  def now(self) -> int:
    """返回固定 Unix 秒。"""
    return NOW


def testRegistrationWaitlistCancellationAndQueriesShareOneStore():
  """建学生、建活动、报名、候补、取消和统计使用同一份状态。"""
  services = buildServices(clock=FixedClock())
  firstStudent = services.studentService.createStudent("0000000001", "张三", 2).data
  secondStudent = services.studentService.createStudent("0000000002", "李四", 3).data
  activity = services.activityService.createActivity(
    "读书分享会", 1, 60,
    NOW - SECONDS_PER_MINUTE,
    NOW + 30 * SECONDS_PER_MINUTE,
    NOW + SECONDS_PER_HOUR,
  ).data

  first = services.registrationService.registerStudent(firstStudent.studentId, activity.activityId).data
  second = services.registrationService.registerStudent(secondStudent.studentId, activity.activityId).data
  assert first.registration.status == STATUS_CONFIRMED
  assert second.registration.status == STATUS_WAITLISTED
  assert services.queryService.getActivityStats(activity.activityId).data.waitlistedCount == 1

  cancelled = services.registrationService.cancelRegistration(
    firstStudent.studentId, first.registration.registrationId
  ).data
  assert cancelled.registration.status == STATUS_CANCELLED
  assert cancelled.promotedRegistrationId == second.registration.registrationId

  updated = services.studentService.updateStudent(secondStudent.studentId, "王五", 4).data
  history = services.queryService.listPersonalRegistrations(updated.studentId, 1, 10).data
  assert history.items[0].studentName == "王五"
  assert history.items[0].status == STATUS_CONFIRMED
  stats = services.queryService.getActivityStats(activity.activityId).data
  assert (stats.confirmedCount, stats.waitlistedCount, stats.cancelledCount) == (1, 0, 1)
  overview = services.queryService.getOverviewStats("2026-10-20", 1).data
  assert (overview.activityCount, overview.distinctParticipantCount) == (1, 1)


def testViewsShareStudentAndActivityData(monkeypatch):
  """学生页和活动页写入后，报名页能读取同一份数据。"""
  monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
  monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
  try:
    root = buildApp(clock=FixedClock())
  except tk.TclError as error:
    pytest.skip(f"Tk 环境不可用：{error}")
  root.withdraw()
  try:
    notebook = next(child for child in root.winfo_children() if isinstance(child, ttk.Notebook))
    studentView = notebook.nametowidget(notebook.tabs()[0])
    activityView = notebook.nametowidget(notebook.tabs()[1])
    registrationView = notebook.nametowidget(notebook.tabs()[2])
    queryView = notebook.nametowidget(notebook.tabs()[3])
    studentView.studentNoVar.set("0000000001")
    studentView.nameVar.set("张三")
    studentView.gradeVar.set("2")
    studentView.createStudent()
    activityView.titleVar.set("读书分享会")
    activityView.capacityVar.set("1")
    activityView.durationVar.set("60")
    activityView.openAtVar.set("2026-10-20 08:59:00")
    activityView.closeAtVar.set("2026-10-20 09:30:00")
    activityView.startAtVar.set("2026-10-20 10:00:00")
    activityView.createActivity()
    registrationView.refresh()
    assert len(registrationView.studentBox["values"]) == 1
    assert len(registrationView.activityBox["values"]) == 1
    registrationView.studentBox.current(0)
    registrationView.activityBox.current(0)
    registrationView.submitRegistration()
    assert "正式报名" in registrationView.statusVar.get()
    assert len(registrationView.historyList.get_children()) == 1
    queryView.refresh()
    queryView._onQueryPersonal()
    assert len(queryView.personalTree.get_children()) == 1
  finally:
    root.destroy()
