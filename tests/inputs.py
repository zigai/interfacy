def pow(base: int, exponent: int = 2) -> int:
    """
    Raise base to the power of exponent.

    Args:
        base (int): The base number.
        exponent (int, optional): The power to which the base is raised.

    Returns:
        int: Result of base raised to exponent.
    """
    return base**exponent


class Math:
    """
    A simple math class.

    Args:
        rounding (int, optional): The number of decimal places to round to.

    """

    def __init__(self, rounding: int = 6) -> None:
        self.rounding = rounding

    def _round(self, value: float | int) -> float | int:
        return round(value, self.rounding)

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


def func_with_bool_arg(value: bool):
    return value


def func_with_bool_default_true(value: bool = True):
    return value


def func_with_bool_default_false(value: bool = False):
    return value
