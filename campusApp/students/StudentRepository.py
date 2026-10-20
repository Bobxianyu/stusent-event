"""共享内存中的学生集合读写。"""

from dataclasses import replace

from campusApp.core.contracts import StoreDraft, StoreSnapshot, Student


class StudentRepository:
  """只访问传入状态中的学生集合，并实现学生读取协议。"""

  def findById(self, state: StoreSnapshot | StoreDraft, studentId: int) -> Student | None:
    """按学生编号查找；不存在时返回 None。"""
    return state.students.get(studentId)

  def existsByStudentNo(self, state: StoreSnapshot | StoreDraft, studentNo: str) -> bool:
    """检查学号是否已被占用。"""
    return any(student.studentNo == studentNo for student in state.students.values())

  def listAll(self, state: StoreSnapshot | StoreDraft) -> list[Student]:
    """按学生编号升序返回列表。"""
    return sorted(state.students.values(), key=lambda student: student.studentId)

  def insert(self, state: StoreDraft, studentNo: str, name: str, grade: int, createdAt: int) -> Student:
    """分配下一个学生编号并写入新实体。"""
    studentId = state.nextStudentId
    student = Student(studentId, studentNo, name, grade, createdAt)
    state.students[studentId] = student
    state.nextStudentId = studentId + 1
    return student

  def updateProfile(self, state: StoreDraft, studentId: int, name: str, grade: int) -> Student:
    """只修改姓名和年级，保留身份字段。"""
    student = replace(state.students[studentId], name=name, grade=grade)
    state.students[studentId] = student
    return student
