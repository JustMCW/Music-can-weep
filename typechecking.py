"""Type checkings, these function are extremely good at removing typing errors"""

from typing import (
    Optional,
    TypeVar,
    Type,
    Any,
)

T = TypeVar("T")
OBJECT_TYPE = TypeVar("OBJECT_TYPE", bound=Any)

def ensure_exist(
    obj: Optional[OBJECT_TYPE], *,
    error : Exception|type[Exception]|None = None,
) -> OBJECT_TYPE:
    """
    Converts an optional object to a non-optional, 
    useful for removing optionals when you know it cannot be None.
    Raises user selected error or `RuntimeError` if the value is None.
    """
    if obj is not None:
        return obj
    
    if error:
        raise error
    raise RuntimeError(f"Object does not exist.")

def ensure_type(obj: Any, expect_type: Type[T]) -> T:
    """
    Narrow the type of an object.
    Raises `TypeError` if the object type does not match.
    """
    if isinstance(obj, expect_type):
        return obj

    raise TypeError(
        f"Expected type `{expect_type.__name__}`, got `{type(obj).__name__}` => `{obj}`"
    )

def ensure_type_optional(obj: Any, expect_type: Type[T]) -> Optional[T]:
    """
    Narrow the type of an object, but None also is considered that type.
    Raises `TypeError` if the object type does not match.
    """
    if obj is None:
        return obj
    return ensure_type(obj, expect_type)

