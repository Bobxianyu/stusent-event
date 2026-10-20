"""学生录入、查询与资料修改页面。"""

import re
import tkinter as tk
from tkinter import messagebox, ttk

from campusApp.students.StudentService import StudentService


STUDENT_COLUMNS = ("编号", "学号", "姓名", "年级")
GRADE_PATTERN = re.compile(r"[0-9]+")


class StudentView(ttk.Frame):
  """仅通过学生服务读取和修改学生资料。"""

  def __init__(self, parent: tk.Misc, studentService: StudentService):
    """绑定学生服务并初始化页面控件。"""
    super().__init__(parent, padding=12)
    self._service = studentService
    self.studentNoVar = tk.StringVar()
    self.nameVar = tk.StringVar()
    self.gradeVar = tk.StringVar()
    self.updateNameVar = tk.StringVar()
    self.updateGradeVar = tk.StringVar()
    self._buildForm()
    self._buildList()
    self.refresh()

  def _buildForm(self) -> None:
    """创建学生录入表单。"""
    form = ttk.LabelFrame(self, text="新增学生", padding=10)
    form.pack(fill="x")
    fields = (
      ("学号（10 位数字）", self.studentNoVar),
      ("姓名", self.nameVar),
      ("年级（1～4）", self.gradeVar),
    )
    for index, (label, variable) in enumerate(fields):
      ttk.Label(form, text=label).grid(row=0, column=index, sticky="w", padx=4)
      ttk.Entry(form, textvariable=variable, width=28).grid(row=1, column=index, sticky="ew", padx=4)
      form.columnconfigure(index, weight=1)
    ttk.Button(form, text="新增学生", command=self.createStudent).grid(row=1, column=len(fields), padx=8)

  def _buildList(self) -> None:
    """创建学生列表与选中学生的修改区域。"""
    toolbar = ttk.Frame(self)
    toolbar.pack(fill="x", pady=(12, 5))
    ttk.Label(toolbar, text="修改选中学生：").pack(side="left")
    ttk.Entry(toolbar, textvariable=self.updateNameVar, width=20).pack(side="left", padx=3)
    ttk.Entry(toolbar, textvariable=self.updateGradeVar, width=8).pack(side="left", padx=3)
    ttk.Button(toolbar, text="保存姓名与年级", command=self.updateStudent).pack(side="left", padx=3)
    ttk.Button(toolbar, text="刷新列表", command=self.refresh).pack(side="left", padx=3)

    table = ttk.Frame(self)
    table.pack(fill="both", expand=True)
    self.studentList = ttk.Treeview(table, columns=STUDENT_COLUMNS, show="headings", height=14)
    for column in STUDENT_COLUMNS:
      self.studentList.heading(column, text=column)
      self.studentList.column(column, width=160)
    self.studentList.pack(side="left", fill="both", expand=True)
    self.studentList.bind("<<TreeviewSelect>>", self._onSelect)
    scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.studentList.yview)
    scrollbar.pack(side="right", fill="y")
    self.studentList.configure(yscrollcommand=scrollbar.set)

  def createStudent(self) -> None:
    """解析年级并创建学生；失败时展示中文提示。"""
    grade = self._parseGrade(self.gradeVar.get())
    if grade is None:
      return
    result = self._service.createStudent(self.studentNoVar.get(), self.nameVar.get(), grade)
    if self._showResult(result, "学生创建成功"):
      self.refresh()

  def updateStudent(self) -> None:
    """修改选中学生的姓名和年级。"""
    selected = self.studentList.selection()
    if not selected:
      messagebox.showerror("操作失败", "请先选择一名学生")
      return
    grade = self._parseGrade(self.updateGradeVar.get())
    if grade is None:
      return
    result = self._service.updateStudent(int(selected[0]), self.updateNameVar.get(), grade)
    if self._showResult(result, "学生资料已更新"):
      self.refresh()

  def refresh(self) -> None:
    """重新加载学生列表，保留仍存在的选择。"""
    result = self._service.listStudents()
    if not result.ok:
      messagebox.showerror("读取失败", result.error.message)
      return
    selected = self.studentList.selection()
    self.studentList.delete(*self.studentList.get_children())
    for student in result.data:
      self.studentList.insert(
        "", "end", iid=str(student.studentId),
        values=(student.studentId, student.studentNo, student.name, student.grade),
      )
    if selected and self.studentList.exists(selected[0]):
      self.studentList.selection_set(selected[0])

  def _onSelect(self, _event: object) -> None:
    """选中列表项时填充修改表单。"""
    selected = self.studentList.selection()
    if not selected:
      return
    values = self.studentList.item(selected[0], "values")
    self.updateNameVar.set(values[2])
    self.updateGradeVar.set(values[3])

  @staticmethod
  def _parseGrade(text: str) -> int | None:
    """只接收 ASCII 十进制年级，具体范围由服务校验。"""
    if GRADE_PATTERN.fullmatch(text.strip()) is None:
      messagebox.showerror("输入错误", "年级必须是整数")
      return None
    return int(text.strip())

  @staticmethod
  def _showResult(result: object, successMessage: str) -> bool:
    """统一展示服务操作结果。"""
    if not result.ok:
      messagebox.showerror("操作失败", result.error.message)
      return False
    messagebox.showinfo("操作成功", successMessage)
    return True
