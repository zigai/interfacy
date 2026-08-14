import enum
from dataclasses import dataclass
from typing import Literal


class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


ColorLiteral = Literal["RED", "GREEN", "BLUE"]


@dataclass
class Address:
    """Mailing address data for a user.

    Args:
        city: City name.
        zip: Postal or ZIP code.
    """

    city: str
    zip: int


@dataclass
class UserWithAddress:
    """User profile information for the CLI.

    Args:
        name: Display name.
        age: Age in years.
        address: Optional mailing address details.
    """

    name: str
    age: int
    address: Address | None = None


def greet_with_address(user: UserWithAddress) -> str:
    if user.address is None:
        return f"Hello {user.name}, age {user.age}"

    return f"Hello {user.name}, age {user.age} from {user.address.city} {user.address.zip}"


@dataclass
class Level3:
    leaf: str


@dataclass
class Level2:
    level3: Level3


@dataclass
class Level1:
    level2: Level2


def uses_levels(level1: Level1) -> str:
    return level1.level2.level3.leaf


class PlainUser:
    """Plain class user model.

    Args:
        name: Display name.
        age: Age in years.
    """

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age


def greet_plain(user: PlainUser) -> str:
    return f"Hello {user.name}, age {user.age}"


def maybe_plain(user: PlainUser | None = None) -> PlainUser | None:
    return user


PLAIN_DEFAULT_USER = PlainUser(name="Tess", age=40)


def greet_plain_default(user: PlainUser = PLAIN_DEFAULT_USER) -> str:
    return f"Hello {user.name}, age {user.age}"


class PlainAddress:
    """Plain class address model.

    Args:
        city: City name.
        zip: Postal or ZIP code.
    """

    def __init__(self, city: str, zip: int) -> None:
        self.city = city
        self.zip = zip


class PlainUserWithAddress:
    """Plain class user model with address.

    Args:
        name: Display name.
        age: Age in years.
        address: Mailing address details.
    """

    def __init__(self, name: str, age: int, address: PlainAddress) -> None:
        self.name = name
        self.age = age
        self.address = address


def greet_plain_with_address(user: PlainUserWithAddress) -> str:
    return f"Hello {user.name}, age {user.age} from {user.address.city} {user.address.zip}"
