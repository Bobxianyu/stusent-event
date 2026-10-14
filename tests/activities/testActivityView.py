"""活动页的输入转换与列表刷新测试。"""

import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import messagebox, ttk

import pytest

from campusApp.activities.ActivityRepository import ActivityRepository
from campusApp.activities.ActivityService import ActivityService
from campusApp.activities.ActivityView import ActivityView
from campusApp.app import buildApp
from campusApp.core.MemoryStore import MemoryStore


BEIJING_TIMEZONE = timezone(timedelta(hours=8))
FIXED_NOW = int(datetime(2026, 10, 14, 8, tzinfo=BEIJING_TIMEZONE).timestamp())


class FixedClock:
  """测试使用的固定时钟。"""

  def now(self) -> int:
    """返回固定 Unix 秒。"""
    return FIXED_NOW


@pytest.fixture
def activityView(monkeypatch):
  """创建隐藏窗口，避免测试弹出消息框。"""
  try:
    root = tk.Tk()
  except tk.TclError as error:
    pytest.skip(f"Tk 环境不可用：{error}")
  root.withdraw()
  monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
  monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
  service = ActivityService(MemoryStore(), ActivityRepository(), FixedClock())
  view = ActivityView(root, service)
  try:
    yield view, service
  finally:
    root.destroy()


def testCreateRefreshRenameAndClose(activityView):
  """界面创建、修改、关闭后均展示最新活动。"""
  view, service = activityView
  view.titleVar.set("读书分享会")
  view.capacityVar.set("20")
  view.durationVar.set("60")
  view.openAtVar.set("2026-10-14 09:00:00")
  view.closeAtVar.set("2026-10-14 10:00:00")
  view.startAtVar.set("2026-10-14 11:00:00")

  view.createActivity()
  assert len(view.activityList.get_children()) == 1
  activityId = service.listActivities().data[0].activityId
  view.activityList.selection_set(str(activityId))
  view.renameVar.set("新读书分享会")
  view.updateActivityTitle()
  assert service.getActivity(activityId).data.title == "新读书分享会"

  view.activityList.selection_set(str(activityId))
  view.closeRegistration()
  assert service.getActivity(activityId).data.isClosed is True
  assert view.activityList.item(str(activityId), "values")[-1] == "报名关闭"


def testInvalidInputKeepsListEmpty(activityView):
  """输入不合法时不创建活动，界面仍可刷新。"""
  view, service = activityView
  view.titleVar.set("无效活动")
  view.capacityVar.set("人数")
  view.durationVar.set("60")
  view.openAtVar.set("2026-10-14 09:00:00")
  view.closeAtVar.set("2026-10-14 10:00:00")
  view.startAtVar.set("2026-10-14 11:00:00")

  view.createActivity()
  view.refresh()
  assert service.listActivities().data == []
  assert view.activityList.get_children() == ()


def testActivityPageMountedInApp():
  """完整启动时活动页是可操作的真实 View。"""
  try:
    root = buildApp()
  except tk.TclError as error:
    pytest.skip(f"Tk 环境不可用：{error}")
  root.withdraw()
  try:
    notebook = next(child for child in root.winfo_children() if isinstance(child, ttk.Notebook))
    page = notebook.nametowidget(notebook.tabs()[1])
    assert isinstance(page, ActivityView)
  finally:
    root.destroy()
