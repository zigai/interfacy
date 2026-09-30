from __future__ import annotations

from typing import ClassVar, Final

from typing_extensions import Self


class UnsetType:
    __slots__ = ()

    _instance: ClassVar[UnsetType | None] = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"


class ModelDefaultUnsetType:
    """Marker for an expanded model parameter that declares no default instance."""

    __slots__ = ()

    _instance: ClassVar[ModelDefaultUnsetType | None] = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __repr__(self) -> str:
        return "MODEL_DEFAULT_UNSET"


UNSET: Final = UnsetType()
MODEL_DEFAULT_UNSET: Final = ModelDefaultUnsetType()


__all__ = [
    "MODEL_DEFAULT_UNSET",
    "UNSET",
    "ModelDefaultUnsetType",
    "UnsetType",
]
