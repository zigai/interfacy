from abc import ABC, abstractmethod


class Math:
    """
    A simple math class.

    Args:
        rounding (int, optional): The number of decimal places to round to.

    """

    def __init__(self, rounding: int = 6) -> None:
        self.rounding = rounding

    def pow(self, base: int, exponent: int = 2) -> float:
        """
        Raise base to the power of exponent.

        Args:
            base (int): The base number.
            exponent (int, optional): The power to which the base is raised.

        Returns:
            float: Result of base raised to exponent.
        """
        return self._round(base**exponent)

    def add(self, a: int, b: int) -> float:
        """
        Add two numbers.

        Args:
            a (int): First number.
            b (int): Second number.

        Returns:
            float: Sum of a and b.
        """
        return self._round(a + b)

    def subtract(self, a: int, b: int) -> float:
        """
        Subtract two numbers.

        Args:
            a (int): First number.
            b (int): Second number.

        Returns:
            float: Difference of a and b.
        """
        return self._round(a - b)

    def _round(self, value: float | int) -> float | int:
        return round(value, self.rounding)


class TextTools:
    """String utilities with a configurable prefix."""

    def __init__(self, prefix: str = "hi-") -> None:
        self.prefix = prefix

    def join(self, a: str, b: str, sep: str = " ") -> str:
        return f"{a}{sep}{b}"

    def prefix_text(self, text: str) -> str:
        return f"{self.prefix}{text}"

    @staticmethod
    def repeat(text: str, times: int = 2) -> str:
        return text * times

    @classmethod
    def tool_name(cls) -> str:
        return cls.__name__

    @property
    def label(self) -> str:
        return f"prefix-{self.prefix}"

    def _helper(self, text: str) -> str:
        return text.strip()


class Empty:
    """No public methods."""

    def __init__(self, value: int) -> None:
        self.value = value

    def _private(self) -> int:
        return self.value


class BaseOperation:
    """For inheritance tests."""

    def execute(self, x: int) -> int:
        return x + 1

    def describe(self) -> str:
        return "base"


class DerivedOperation(BaseOperation):
    """Overrides execute, adds extra."""

    def execute(self, x: int) -> int:
        return x * 2

    def extra(self) -> str:
        return "extra"


class AbstractProcessor(ABC):
    """Abstract processor for testing."""

    @abstractmethod
    def process(self, data: str) -> str: ...

    @abstractmethod
    def validate(self, data: str) -> bool: ...


class ConcreteProcessor(AbstractProcessor):
    """Concrete implementation of abstract class."""

    def process(self, data: str) -> str:
        return data.upper()

    def validate(self, data: str) -> bool:
        return bool(data)


class Container:
    """Container management commands."""

    def __init__(self, format: str = "table") -> None:
        self.format = format

    def run(self, image: str) -> str:
        return f"Running {image} with format {self.format}"

    def stop(self, name: str) -> str:
        return f"Stopped {name}"


class Database:
    """Database connection for testing instances."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def query(self, sql: str) -> str:
        return f"Query on {self.host}:{self.port}: {sql}"

    def ping(self) -> str:
        return f"Pong from {self.host}:{self.port}"


class TextCollector:
    """Class fixture for testing positional + varargs method execution."""

    def collect(self, head: str, *tail: str) -> tuple[str, tuple[str, ...]]:
        return head, tail

    def collect_with_mode(
        self,
        head: str,
        *tail: str,
        mode: str = "default",
    ) -> tuple[str, tuple[str, ...], str]:
        return head, tail, mode

    def collect_with_options(
        self,
        head: str,
        *tail: str,
        **options: dict[str, str],
    ) -> tuple[str, tuple[str, ...], dict[str, str]]:
        return head, tail, options
