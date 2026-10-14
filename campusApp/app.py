"""共享内存与四个固定页签的启动入口。"""

import importlib
import importlib.util
import logging
import tkinter as tk
from tkinter import ttk

from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.timeUtils import SystemClock


WINDOW_TITLE = "校园活动报名系统"
WINDOW_SIZE = "1180x650"
ACTIVITY_VIEW_MODULE = "campusApp.activities.ActivityView"
ACTIVITY_REPOSITORY_MODULE = "campusApp.activities.ActivityRepository"
ACTIVITY_SERVICE_MODULE = "campusApp.activities.ActivityService"
TAB_NAMES = ("学生管理", "活动管理", "报名与取消", "查询统计")
PENDING_MESSAGE = "本模块尚未接入，请先使用活动管理页。"


def buildApp() -> tk.Tk:
  """创建单一根窗口和共享 Store，返回尚未进入事件循环的窗口。"""
  root = tk.Tk()
  root.title(WINDOW_TITLE)
  root.geometry(WINDOW_SIZE)
  notebook = ttk.Notebook(root)
  notebook.pack(fill="both", expand=True)

  store = MemoryStore()
  clock = SystemClock()
  pages: list[ttk.Frame] = []
  for name in TAB_NAMES:
    if name == "活动管理" and importlib.util.find_spec("campusApp.activities") is not None:
      if importlib.util.find_spec(ACTIVITY_VIEW_MODULE) is not None:
        repositoryClass = importlib.import_module(ACTIVITY_REPOSITORY_MODULE).ActivityRepository
        serviceClass = importlib.import_module(ACTIVITY_SERVICE_MODULE).ActivityService
        viewClass = importlib.import_module(ACTIVITY_VIEW_MODULE).ActivityView
        page = viewClass(notebook, serviceClass(store, repositoryClass(), clock))
      else:
        page = _buildPendingPage(notebook)
    else:
      page = _buildPendingPage(notebook)
    notebook.add(page, text=name)
    pages.append(page)

  def refreshSelected(_event: object) -> None:
    """切换页签时刷新当前模块，不重建 Store。"""
    selectedIndex = notebook.index(notebook.select())
    refresh = getattr(pages[selectedIndex], "refresh", None)
    if callable(refresh):
      refresh()

  notebook.bind("<<NotebookTabChanged>>", refreshSelected)
  return root


def _buildPendingPage(parent: ttk.Notebook) -> ttk.Frame:
  """创建尚待其他组员接入的页签。"""
  page = ttk.Frame(parent, padding=24)
  ttk.Label(page, text=PENDING_MESSAGE).pack(anchor="w")
  return page


def main() -> None:
  """设置中文日志格式并启动桌面事件循环。"""
  logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
  )
  buildApp().mainloop()


if __name__ == "__main__":
  main()
