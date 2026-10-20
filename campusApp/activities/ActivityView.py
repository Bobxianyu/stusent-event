"""活动管理的 Tkinter 页面。"""

import re
import tkinter as tk
from tkinter import messagebox, ttk

from campusApp.activities.ActivityService import ActivityService
from campusApp.core.constants import ERROR_VALIDATION
from campusApp.core.contracts import DomainError, Result
from campusApp.core.timeUtils import formatDateTime, parseDateTime


FIELD_LABELS = (
  ("活动名称", "titleVar"),
  ("活动容量", "capacityVar"),
  ("时长（分钟）", "durationVar"),
  ("报名开始", "openAtVar"),
  ("报名截止", "closeAtVar"),
  ("活动开始", "startAtVar"),
)
LIST_COLUMNS = ("编号", "名称", "容量", "时长", "报名开始", "报名截止", "活动开始", "活动结束", "阶段")
TIME_HINT = "时间格式：年-月-日 时:分:秒，使用北京时间"


class ActivityView(ttk.Frame):
  """活动创建、列表查询、名称修改和关闭报名页面。"""

  def __init__(self, parent: tk.Misc, activityService: ActivityService):
    """绑定服务并初始化控件；不访问共享存储。"""
    super().__init__(parent, padding=12)
    self._service = activityService
    self.titleVar = tk.StringVar()
    self.capacityVar = tk.StringVar()
    self.durationVar = tk.StringVar()
    self.openAtVar = tk.StringVar()
    self.closeAtVar = tk.StringVar()
    self.startAtVar = tk.StringVar()
    self.renameVar = tk.StringVar()
    self._buildForm()
    self._buildList()
    self.refresh()

  def _buildForm(self) -> None:
    """创建新活动输入框和操作按钮。"""
    form = ttk.LabelFrame(self, text="创建活动", padding=10)
    form.pack(fill="x")
    for index, (label, variableName) in enumerate(FIELD_LABELS):
      row, column = divmod(index, 3)
      ttk.Label(form, text=label).grid(row=row * 2, column=column, sticky="w", padx=4)
      entry = ttk.Entry(form, textvariable=getattr(self, variableName), width=27)
      entry.grid(row=row * 2 + 1, column=column, sticky="ew", padx=4, pady=(0, 7))
      form.columnconfigure(column, weight=1)
    ttk.Label(form, text=TIME_HINT).grid(row=4, column=0, columnspan=3, sticky="w", padx=4)
    ttk.Button(form, text="创建活动", command=self.createActivity).grid(row=5, column=0, sticky="w", padx=4, pady=8)

  def _buildList(self) -> None:
    """创建活动列表与选中项操作区。"""
    toolbar = ttk.Frame(self)
    toolbar.pack(fill="x", pady=(12, 5))
    ttk.Label(toolbar, text="选中活动后修改名称：").pack(side="left")
    ttk.Entry(toolbar, textvariable=self.renameVar, width=24).pack(side="left", padx=(0, 6))
    ttk.Button(toolbar, text="修改名称", command=self.updateActivityTitle).pack(side="left", padx=3)
    ttk.Button(toolbar, text="关闭报名", command=self.closeRegistration).pack(side="left", padx=3)
    ttk.Button(toolbar, text="刷新列表", command=self.refresh).pack(side="left", padx=3)

    table = ttk.Frame(self)
    table.pack(fill="both", expand=True)
    self.activityList = ttk.Treeview(table, columns=LIST_COLUMNS, show="headings", height=12)
    for column in LIST_COLUMNS:
      self.activityList.heading(column, text=column)
      timeColumns = {"报名开始", "报名截止", "活动开始", "活动结束"}
      self.activityList.column(column, width=158 if column in timeColumns else 90)
    self.activityList.column("名称", width=190)
    self.activityList.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.activityList.yview)
    scrollbar.pack(side="right", fill="y")
    self.activityList.configure(yscrollcommand=scrollbar.set)

  def createActivity(self) -> None:
    """转换页面输入并调用创建服务，成功后刷新本页。"""
    try:
      capacity = self._parsePositiveInteger(self.capacityVar.get(), "活动容量")
      duration = self._parsePositiveInteger(self.durationVar.get(), "时长")
      openAt = parseDateTime(self.openAtVar.get(), "报名开始")
      closeAt = parseDateTime(self.closeAtVar.get(), "报名截止")
      startAt = parseDateTime(self.startAtVar.get(), "活动开始")
    except DomainError as error:
      messagebox.showerror("输入错误", error.error.message)
      return
    result = self._service.createActivity(self.titleVar.get(), capacity, duration, openAt, closeAt, startAt)
    if self._showResult(result, "活动创建成功"):
      self.refresh()

  def updateActivityTitle(self) -> None:
    """仅修改选中活动名称，容量和时间保持原值。"""
    activityId = self._selectedActivityId()
    if activityId is None:
      return
    result = self._service.updateActivityTitle(activityId, self.renameVar.get())
    if self._showResult(result, "活动名称已更新"):
      self.refresh()

  def closeRegistration(self) -> None:
    """关闭选中活动的新报名入口。"""
    activityId = self._selectedActivityId()
    if activityId is None:
      return
    result = self._service.closeRegistration(activityId)
    if self._showResult(result, "活动报名已关闭"):
      self.refresh()

  def refresh(self) -> None:
    """重新读取活动并根据当前时间更新阶段。"""
    result = self._service.listActivities()
    if not result.ok:
      messagebox.showerror("读取失败", result.error.message)
      return
    selected = self.activityList.selection()
    self.activityList.delete(*self.activityList.get_children())
    for activity in result.data:
      values = (
        activity.activityId,
        activity.title,
        activity.capacity,
        activity.durationMinutes,
        formatDateTime(activity.openAt),
        formatDateTime(activity.closeAt),
        formatDateTime(activity.startAt),
        formatDateTime(activity.endAt),
        self._service.describePhase(activity),
      )
      self.activityList.insert("", "end", iid=str(activity.activityId), values=values)
    if selected and self.activityList.exists(selected[0]):
      self.activityList.selection_set(selected[0])

  def _selectedActivityId(self) -> int | None:
    """读取当前列表选择；未选择时给出中文提示。"""
    selected = self.activityList.selection()
    if not selected:
      messagebox.showerror("操作失败", "请先选择一个活动")
      return None
    return int(selected[0])

  @staticmethod
  def _parsePositiveInteger(value: str, label: str) -> int:
    """仅接受 ASCII 十进制整数，具体边界由 Service 检查。"""
    if re.fullmatch(r"[0-9]+", value.strip()) is None:
      raise DomainError(ERROR_VALIDATION, f"{label}必须是整数")
    return int(value.strip())

  @staticmethod
  def _showResult(result: Result, successMessage: str) -> bool:
    """统一显示操作结果，返回是否成功。"""
    if not result.ok:
      messagebox.showerror("操作失败", result.error.message)
      return False
    messagebox.showinfo("操作成功", successMessage)
    return True
