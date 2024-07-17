import sys

from stdl import fs


def read_stdin() -> str | None:
    """
    Read input from stdin (piped input) in a cross-platform manner.

    Returns:
        str: The content read from stdin.
    """
    if sys.stdin.isatty():
        return None
    return sys.stdin.read().strip()


if __name__ == "__main__":
    input_data = read_stdin()
    if input_data:
        print("Received input:")
        print(input_data)
    else:
        print("No input received.")
