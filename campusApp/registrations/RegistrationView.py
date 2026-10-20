"""报名与取消的 Tkinter 页面。

本页只负责输入转换、调用服务并展示结果；不直接读取共享存储，也不创建正式运行所需的 Store。
报名历史通过模块四的只读查询接口取得；查询模块尚未接入时，本页只停用历史区，报名与取消仍可正常使用。
"""

import tkinter as tk
from tkinter import messagebox, ttk

from campusApp.core.constants import (
  STATUS_CANCELLED,
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
)
from campusApp.core.timeUtils import formatDateTime


HISTORY_COLUMNS = ("编号", "活动", "状态", "报名时间", "取消时间", "活动开始", "活动结束")
STATUS_LABELS = {
  STATUS_CONFIRMED: "正式报名",
  STATUS_WAITLISTED: "候补",
  STATUS_CANCELLED: "已取消",
}
DEFAULT_PAGE_SIZE = 20
EMPTY_STUDENT_TEXT = "（暂无学生，请先在学生管理页录入）"
QUERY_PENDING_TEXT = "查询模块尚未接入，报名历史暂不可用；报名与取消不受影响。"


class RegistrationView(ttk.Frame):
  """报名提交、取消和报名历史页面。"""

  def __init__(
    self,
    parent: tk.Misc,
    studentService: object,
    activityService: object,
    registrationService: object,
    queryService: object | None = None,
  ):
    """绑定四个服务并初始化控件；查询服务缺省时只停用历史区。"""
    super().__init__(parent, padding=12)
    self._studentService = studentService
    self._activityService = activityService
    self._registrationService = registrationService
    self._queryService = queryService
    self.studentVar = tk.StringVar()
    self.activityVar = tk.StringVar()
    self.statusVar = tk.StringVar(value="请选择学生和活动后提交报名")
    self._students: list = []
    self._activities: list = []
    self._page = 1
    self._buildApplyArea()
    self._buildHistoryArea()
    self.refresh()

  def _buildApplyArea(self) -> None:
    """创建学生、活动选择和报名按钮。"""
    area = ttk.LabelFrame(self, text="报名申请", padding=10)
    area.pack(fill="x")
    ttk.Label(area, text="学生").grid(row=0, column=0, sticky="w", padx=4)
    self.studentBox = ttk.Combobox(area, textvariable=self.studentVar, state="readonly", width=30)
    self.studentBox.grid(row=0, column=1, sticky="ew", padx=4)
    self.studentBox.bind("<<ComboboxSelected>>", lambda _event: self._loadHistory())
    ttk.Label(area, text="活动").grid(row=0, column=2, sticky="w", padx=4)
    self.activityBox = ttk.Combobox(area, textvariable=self.activityVar, state="readonly", width=40)
    self.activityBox.grid(row=0, column=3, sticky="ew", padx=4)
    ttk.Button(area, text="提交报名", command=self.submitRegistration).grid(row=0, column=4, padx=6)
    ttk.Button(area, text="刷新", command=self.refresh).grid(row=0, column=5, padx=2)
    area.columnconfigure(1, weight=1)
    area.columnconfigure(3, weight=2)
    ttk.Label(area, textvariable=self.statusVar, foreground="#1a5fb4").grid(
      row=1,
      column=0,
      columnspan=6,
      sticky="w",
      padx=4,
      pady=(8, 0),
    )

  def _buildHistoryArea(self) -> None:
    """创建报名历史表格和取消按钮。"""
    area = ttk.LabelFrame(self, text="报名历史", padding=10)
    area.pack(fill="both", expand=True, pady=(12, 0))
    toolbar = ttk.Frame(area)
    toolbar.pack(fill="x", pady=(0, 6))
    ttk.Button(toolbar, text="取消选中报名", command=self.cancelSelectedRegistration).pack(side="left")
    ttk.Button(toolbar, text="刷新历史", command=self._loadHistory).pack(side="left", padx=4)
    self.pageLabel = ttk.Label(toolbar, text="")
    self.pageLabel.pack(side="right")
    table = ttk.Frame(area)
    table.pack(fill="both", expand=True)
    self.historyList = ttk.Treeview(table, columns=HISTORY_COLUMNS, show="headings", height=12)
    for column in HISTORY_COLUMNS:
      self.historyList.heading(column, text=column)
      self.historyList.column(column, width=150 if "时间" in column else 90)
    self.historyList.column("活动", width=220)
    self.historyList.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.historyList.yview)
    scrollbar.pack(side="right", fill="y")
    self.historyList.configure(yscrollcommand=scrollbar.set)

  def refresh(self) -> None:
    """重新加载学生、活动和当前学生的报名历史。"""
    self._loadStudents()
    self._loadActivities()
    self._loadHistory()

  def submitRegistration(self) -> None:
    """把当前选择提交给报名服务，并显示正式、候补或失败结果。"""
    studentId = self._selectedStudentId()
    activityId = self._selectedActivityId()
    if studentId is None or activityId is None:
      return
    result = self._registrationService.registerStudent(studentId, activityId)
    if not result.ok:
      messagebox.showerror("报名失败", result.error.message)
      self.statusVar.set(f"报名失败：{result.error.message}")
      return
    registration = result.data.registration
    label = STATUS_LABELS.get(registration.status, registration.status)
    self.statusVar.set(
      f"报名编号 {registration.registrationId}：{label}，剩余名额 {result.data.remainingSeats}"
    )
    messagebox.showinfo("报名成功", f"{label}，剩余名额 {result.data.remainingSeats}")
    self._loadActivities()
    self._loadHistory()

  def cancelSelectedRegistration(self) -> None:
    """取消当前学生在表格中选中的报名，并提示是否发生递补。"""
    studentId = self._selectedStudentId()
    if studentId is None:
      return
    selected = self.historyList.selection()
    if not selected:
      messagebox.showerror("操作失败", "请先在报名历史中选中一条记录")
      return
    registrationId = int(selected[0])
    result = self._registrationService.cancelRegistration(studentId, registrationId)
    if not result.ok:
      messagebox.showerror("取消失败", result.error.message)
      self.statusVar.set(f"取消失败：{result.error.message}")
      return
    promotedId = result.data.promotedRegistrationId
    message = f"报名编号 {registrationId} 已取消"
    if promotedId is not None:
      message = f"{message}，候补编号 {promotedId} 已递补为正式报名"
    self.statusVar.set(message)
    messagebox.showinfo("取消成功", message)
    self._loadActivities()
    self._loadHistory()

  def _loadStudents(self) -> None:
    """读取学生列表并填入下拉框。"""
    result = self._studentService.listStudents()
    if not result.ok:
      self._students = []
      self.studentBox.configure(values=[EMPTY_STUDENT_TEXT])
      messagebox.showerror("读取失败", result.error.message)
      return
    self._students = list(result.data)
    self.studentBox.configure(
      values=[f"{student.studentNo} {student.name}" for student in self._students]
    )

  def _loadActivities(self) -> None:
    """读取活动列表并填入下拉框，同时显示剩余名额。"""
    result = self._activityService.listActivities()
    if not result.ok:
      self._activities = []
      self.activityBox.configure(values=[EMPTY_STUDENT_TEXT])
      messagebox.showerror("读取失败", result.error.message)
      return
    self._activities = list(result.data)
    self.activityBox.configure(
      values=[f"{activity.title}（容量 {activity.capacity}）" for activity in self._activities]
    )

  def _loadHistory(self) -> None:
    """调用查询模块的只读接口显示当前学生的报名历史。"""
    self.historyList.delete(*self.historyList.get_children())
    if self._queryService is None:
      self.pageLabel.configure(text=QUERY_PENDING_TEXT)
      return
    studentId = self._selectedStudentId(quiet=True)
    if studentId is None:
      self.pageLabel.configure(text="请先选择学生")
      return
    result = self._queryService.listPersonalRegistrations(studentId, self._page, DEFAULT_PAGE_SIZE)
    if not result.ok:
      messagebox.showerror("读取失败", result.error.message)
      return
    page = result.data
    for row in page.items:
      self.historyList.insert(
        "",
        "end",
        iid=str(row.registrationId),
        values=(
          row.registrationId,
          row.activityTitle,
          STATUS_LABELS.get(row.status, row.status),
          formatDateTime(row.joinedAt),
          formatDateTime(row.cancelledAt) if row.cancelledAt is not None else "",
          formatDateTime(row.startAt),
          formatDateTime(row.endAt),
        ),
      )
    self.pageLabel.configure(text=f"第 {page.page} 页，共 {page.total} 条")

  def _selectedStudentId(self, quiet: bool = False) -> int | None:
    """返回下拉框当前选中的学生编号；未选择时按需提示。"""
    index = self.studentBox.current()
    if index < 0 or index >= len(self._students):
      if not quiet:
        messagebox.showerror("操作失败", "请先选择学生")
      return None
    return self._students[index].studentId

  def _selectedActivityId(self) -> int | None:
    """返回下拉框当前选中的活动编号；未选择时提示。"""
    index = self.activityBox.current()
    if index < 0 or index >= len(self._activities):
      messagebox.showerror("操作失败", "请先选择活动")
      return None
    return self._activities[index].activityId
