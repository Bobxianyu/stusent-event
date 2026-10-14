"""Service 复用的输入校验。"""

from campusApp.core.constants import ERROR_VALIDATION, INITIAL_ID
from campusApp.core.contracts import DomainError


def requireInteger(value: object, minValue: int, maxValue: int | None, field: str) -> int:
  """校验整数类型和范围；失败时抛中文业务异常。"""
  if type(value) is not int:
    raise DomainError(ERROR_VALIDATION, f"{field}必须是整数", field)
  if value < minValue or (maxValue is not None and value > maxValue):
    raise DomainError(ERROR_VALIDATION, f"{field}超出允许范围", field)
  return value


def requireId(value: object, field: str) -> int:
  """校验正整数实体编号；失败时抛中文业务异常。"""
  return requireInteger(value, INITIAL_ID, None, field)


def requireText(
  value: object,
  minLength: int,
  maxLength: int,
  field: str,
  stripWhitespace: bool = True,
) -> str:
  """校验文本长度，并按要求去掉首尾空白；失败时抛业务异常。"""
  if type(value) is not str:
    raise DomainError(ERROR_VALIDATION, f"{field}必须是文本", field)
  normalized = value.strip() if stripWhitespace else value
  if len(normalized) < minLength or len(normalized) > maxLength:
    raise DomainError(ERROR_VALIDATION, f"{field}长度超出允许范围", field)
  return normalized
