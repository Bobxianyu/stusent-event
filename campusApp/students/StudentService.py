"""学生资料校验与原子写入。"""

import logging
import re
from typing import Callable, TypeVar

from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.constants import (
  ERROR_INTERNAL,
  ERROR_STUDENT_NOT_FOUND,
  ERROR_STUDENT_NO_EXISTS,
  ERROR_VALIDATION,
  MAX_GRADE,
  MAX_NAME_LENGTH,
  MIN_GRADE,
  MIN_NAME_LENGTH,
  STUDENT_NO_LENGTH,
)
from campusApp.core.contracts import Clock, DomainError, Result, Student, failure, success
from campusApp.core.validation import requireId, requireInteger, requireText
from campusApp.students.StudentRepository import StudentRepository


T = TypeVar("T")
LOGGER = logging.getLogger(__name__)
STUDENT_NO_PATTERN = re.compile(rf"[0-9]{{{STUDENT_NO_LENGTH}}}")


class StudentService:
  """学生创建、资料修改及查询的公开接口。"""

  def __init__(self, store: MemoryStore, repository: StudentRepository, clock: Clock):
    """注入唯一共享存储、学生仓储及时间来源。"""
    self._store = store
    self._repository = repository
    self._clock = clock

  def createStudent(self, studentNo: str, name: str, grade: int) -> Result[Student]:
    """创建学生；校验失败或学号重复时不消耗编号。"""
    def action() -> Student:
      validStudentNo = self._requireStudentNo(studentNo)
      validName = requireText(name, MIN_NAME_LENGTH, MAX_NAME_LENGTH, "name")
      validGrade = requireInteger(grade, MIN_GRADE, MAX_GRADE, "grade")

      def write(state) -> Student:
        # 重复检查与编号分配处于同一写事务，防止并发创建相同学号。
        if self._repository.existsByStudentNo(state, validStudentNo):
          raise DomainError(ERROR_STUDENT_NO_EXISTS, "学号已存在", "studentNo")
        return self._repository.insert(state, validStudentNo, validName, validGrade, self._clock.now())

      return self._store.runWrite(write)

    return self._runAction(action, "创建学生")

  def updateStudent(self, studentId: int, name: str, grade: int) -> Result[Student]:
    """只修改学生姓名和年级。"""
    def action() -> Student:
      validId = requireId(studentId, "studentId")
      validName = requireText(name, MIN_NAME_LENGTH, MAX_NAME_LENGTH, "name")
      validGrade = requireInteger(grade, MIN_GRADE, MAX_GRADE, "grade")

      def write(state) -> Student:
        if self._repository.findById(state, validId) is None:
          raise DomainError(ERROR_STUDENT_NOT_FOUND, "学生不存在", "studentId")
        return self._repository.updateProfile(state, validId, validName, validGrade)

      return self._store.runWrite(write)

    return self._runAction(action, "修改学生")

  def getStudent(self, studentId: int) -> Result[Student]:
    """按编号查询学生。"""
    def action() -> Student:
      validId = requireId(studentId, "studentId")

      def read(state) -> Student:
        student = self._repository.findById(state, validId)
        if student is None:
          raise DomainError(ERROR_STUDENT_NOT_FOUND, "学生不存在", "studentId")
        return student

      return self._store.runRead(read)

    return self._runAction(action, "查询学生")

  def listStudents(self) -> Result[list[Student]]:
    """返回按学生编号升序排列的列表。"""
    return self._runAction(lambda: self._store.runRead(self._repository.listAll), "查询学生列表")

  @staticmethod
  def _requireStudentNo(value: object) -> str:
    """校验固定长度的 ASCII 数字学号，保留前导零。"""
    if type(value) is not str or STUDENT_NO_PATTERN.fullmatch(value) is None:
      raise DomainError(ERROR_VALIDATION, "学号必须是 10 位 ASCII 数字", "studentNo")
    return value

  @staticmethod
  def _runAction(action: Callable[[], T], operation: str) -> Result[T]:
    """把业务错误转换为 Result，并记录非预期异常堆栈。"""
    try:
      return success(action())
    except DomainError as error:
      return failure(error.error.code, error.error.message, error.error.field)
    except Exception:
      LOGGER.exception("学生模块执行%s失败", operation)
      return failure(ERROR_INTERNAL, f"{operation}失败，请查看日志")
