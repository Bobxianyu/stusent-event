"""共享内存与四个固定页签的启动入口。"""

import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from campusApp.activities.ActivityRepository import ActivityRepository
from campusApp.activities.ActivityService import ActivityService
from campusApp.activities.ActivityView import ActivityView
from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.contracts import Clock
from campusApp.core.timeUtils import SystemClock
from campusApp.queries.QueryRepository import QueryRepository
from campusApp.queries.QueryService import QueryService
from campusApp.queries.QueryView import QueryView
from campusApp.registrations.RegistrationRepository import RegistrationRepository
from campusApp.registrations.RegistrationService import RegistrationService
from campusApp.registrations.RegistrationView import RegistrationView
from campusApp.students.StudentRepository import StudentRepository
from campusApp.students.StudentService import StudentService
from campusApp.students.StudentView import StudentView


WINDOW_TITLE = "校园活动报名系统"
WINDOW_SIZE = "1180x650"
TAB_NAMES = ("学生管理", "活动管理", "报名与取消", "查询统计")


@dataclass(frozen=True)
class AppServices:
  """一个应用实例共用的存储和四个业务服务。"""

  store: MemoryStore
  studentService: StudentService
  activityService: ActivityService
  registrationService: RegistrationService
  queryService: QueryService


def buildServices(clock: Clock | None = None) -> AppServices:
  """创建唯一共享存储并按仓储、服务的依赖顺序组装。"""
  store = MemoryStore()
  appClock = clock if clock is not None else SystemClock()
  studentRepository = StudentRepository()
  activityRepository = ActivityRepository()
  registrationRepository = RegistrationRepository()
  queryRepository = QueryRepository()
  studentService = StudentService(store, studentRepository, appClock)
  activityService = ActivityService(store, activityRepository, appClock)
  registrationService = RegistrationService(
    store, registrationRepository, studentRepository, activityRepository, appClock
  )
  queryService = QueryService(store, queryRepository, appClock)
  return AppServices(store, studentService, activityService, registrationService, queryService)


def buildApp(clock: Clock | None = None) -> tk.Tk:
  """创建单一根窗口和共享 Store；可注入时钟供联调复现。"""
  root = tk.Tk()
  root.title(WINDOW_TITLE)
  root.geometry(WINDOW_SIZE)
  notebook = ttk.Notebook(root)
  notebook.pack(fill="both", expand=True)

  services = buildServices(clock)
  pages: list[ttk.Frame] = [
    StudentView(notebook, services.studentService),
    ActivityView(notebook, services.activityService),
    RegistrationView(
      notebook,
      services.studentService,
      services.activityService,
      services.registrationService,
      services.queryService,
    ),
    QueryView(notebook, services.studentService, services.activityService, services.queryService),
  ]
  for name, page in zip(TAB_NAMES, pages):
    notebook.add(page, text=name)

  def refreshSelected(_event: object) -> None:
    """切换页签时刷新当前模块，不重建 Store。"""
    selectedIndex = notebook.index(notebook.select())
    refresh = getattr(pages[selectedIndex], "refresh", None)
    if callable(refresh):
      refresh()

  notebook.bind("<<NotebookTabChanged>>", refreshSelected)
  return root


def main() -> None:
  """设置中文日志格式并启动桌面事件循环。"""
  logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
  )
  buildApp().mainloop()


if __name__ == "__main__":
  main()
