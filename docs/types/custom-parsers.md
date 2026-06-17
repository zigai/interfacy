# Custom Parsers

Register a custom parser when an annotation needs domain-specific conversion.

A parser receives one raw CLI string and returns the Python value passed to your command.

```python
from dataclasses import dataclass
from interfacy import Interfacy


@dataclass(frozen=True)
class Port:
    value: int


def parse_port(raw: str) -> Port:
    port = int(raw)
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return Port(port)


def serve(port: Port) -> str:
    return f"serving on {port.value}"


parser = Interfacy(print_result=True)
parser.add_type_parser(Port, parse_port)
parser.run(serve)
```

```console
$ python app.py 8080
serving on 8080
```

## Registry access

`add_type_parser()` is the usual API. If you need lower-level control, the active `StrToTypeParser` registry is available through `parser.type_parser`.

```python
parser = Interfacy()
parser.add_type_parser(Port, parse_port)
```

## Parser errors

Raise `ValueError` or another clear exception from the parser when input is invalid. Interfacy reports the parsing failure through the active backend.

```python
def parse_percent(raw: str) -> float:
    value = float(raw.rstrip("%"))
    if not 0 <= value <= 100:
        raise ValueError("percent must be between 0 and 100")
    return value / 100
```

## Custom parser vs model expansion

A registered parser for a class means “parse this value as a scalar.” That takes precedence over model expansion.

With a custom parser, the CLI accepts one scalar value:

```console
$ python app.py 127.0.0.1:8000
```

With model expansion, the CLI accepts structured flags:

```console
$ python app.py --server.host 127.0.0.1 --server.port 8000
```
