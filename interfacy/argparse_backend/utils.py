from argparse import Namespace
from typing import Any


def namespace_to_dict(namespace: Namespace) -> dict[str, Any]:
    result = {}
    for key, value in vars(namespace).items():
        if isinstance(value, Namespace):
            result[key] = namespace_to_dict(value)
        else:
            result[key] = value
    return result
