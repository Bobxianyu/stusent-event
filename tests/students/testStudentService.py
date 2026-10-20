"""学生服务的正常、边界和异常用例。"""

import pytest

from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.constants import ERROR_STUDENT_NOT_FOUND, ERROR_STUDENT_NO_EXISTS, ERROR_VALIDATION
from campusApp.students.StudentRepository import StudentRepository
from campusApp.students.StudentService import StudentService


class FixedClock:
  """返回固定秒数的测试时钟。"""

  def now(self) -> int:
    """提供固定创建时间。"""
    return 1_800_000_000


@pytest.fixture
def studentService():
  """为每个用例创建独立的内存存储。"""
  store = MemoryStore()
  repository = StudentRepository()
  return StudentService(store, repository, FixedClock()), store, repository


def testCreateAndReadStudent(studentService):
  """学号保留前导零，姓名去空白，列表按编号排序。"""
  service, store, repository = studentService
  created = service.createStudent("0000000001", "  张三  ", 1)
  assert created.ok
  assert (created.data.studentId, created.data.studentNo, created.data.name) == (1, "0000000001", "张三")
  assert service.getStudent(1).data == created.data
  assert service.listStudents().data == [created.data]
  assert store.runRead(lambda state: repository.findById(state, 1)) == created.data


@pytest.mark.parametrize("name", ["李四", "测试甲", "测试学生甲乙丙丁戊己庚辛", "测试学生名字长一点", "甲" * 20])
def testAcceptedNameLengths(studentService, name):
  """覆盖姓名的短、中、长合法边界。"""
  service, _, _ = studentService
  assert service.createStudent("0000000001", name, 2).ok


@pytest.mark.parametrize("grade", [1, 2, 3, 4])
def testAcceptedGrades(studentService, grade):
  """覆盖所有合法年级。"""
  service, _, _ = studentService
  assert service.createStudent("0000000001", "张三", grade).ok


@pytest.mark.parametrize("studentNo", [
  "123456789", "12345678901", "１２３４５６７８９０", "123456789a", " 1234567890", 1234567890,
])
def testInvalidStudentNumber(studentService, studentNo):
  """拒绝长度、字符集、空白或类型不合法的学号。"""
  service, _, _ = studentService
  result = service.createStudent(studentNo, "张三", 2)
  assert result.ok is False
  assert result.error.code == ERROR_VALIDATION


@pytest.mark.parametrize("name", ["甲", "甲" * 21, "  ", None])
def testInvalidName(studentService, name):
  """拒绝不合法姓名。"""
  service, _, _ = studentService
  assert service.createStudent("0000000001", name, 2).error.code == ERROR_VALIDATION


@pytest.mark.parametrize("grade", [0, 5, True, 2.0, "2"])
def testInvalidGrade(studentService, grade):
  """拒绝越界或非整数年级。"""
  service, _, _ = studentService
  assert service.createStudent("0000000001", "张三", grade).error.code == ERROR_VALIDATION


def testDuplicateNumberDoesNotConsumeId(studentService):
  """重名允许，重复学号拒绝且不会占用学生编号。"""
  service, _, _ = studentService
  first = service.createStudent("0000000001", "张三", 2)
  duplicate = service.createStudent("0000000001", "李四", 3)
  second = service.createStudent("0000000002", "张三", 4)
  assert first.ok and second.ok
  assert duplicate.error.code == ERROR_STUDENT_NO_EXISTS
  assert second.data.studentId == 2


def testUpdateKeepsIdentityAndHistory(studentService):
  """修改姓名和年级时保持主键、学号与创建时间。"""
  service, _, _ = studentService
  before = service.createStudent("0000000001", "张三", 2).data
  after = service.updateStudent(before.studentId, "  李四  ", 4).data
  assert (after.studentId, after.studentNo, after.createdAt) == (
    before.studentId, before.studentNo, before.createdAt
  )
  assert (after.name, after.grade) == ("李四", 4)


def testFailedUpdateAndMissingStudent(studentService):
  """失败的修改不改变旧数据，缺失编号返回明确错误。"""
  service, _, _ = studentService
  before = service.createStudent("0000000001", "张三", 2).data
  assert service.updateStudent(1, "甲", 3).error.code == ERROR_VALIDATION
  assert service.updateStudent(99, "李四", 3).error.code == ERROR_STUDENT_NOT_FOUND
  assert service.getStudent(99).error.code == ERROR_STUDENT_NOT_FOUND
  assert service.getStudent(1).data == before


def testInvalidIdAndListOrder(studentService):
  """编号类型非法时失败，列表以创建编号升序返回。"""
  service, _, _ = studentService
  for suffix in (3, 1, 2):
    assert service.createStudent(f"{suffix:010d}", "张三", 2).ok
  assert [student.studentId for student in service.listStudents().data] == [1, 2, 3]
  assert service.getStudent(True).error.code == ERROR_VALIDATION
