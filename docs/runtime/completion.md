# Completion

Interfacy can install shell completion support through `argcomplete` for the argparse backend.

Install the optional dependency:

```console
$ python -m pip install argcomplete
```

Or install Interfacy with the full extra:

```console
$ python -m pip install "interfacy[full]"
```

Enable completion on the parser:

```python
from interfacy import Interfacy

Interfacy(tab_completion=True).run(main)
```

## What gets completed

Interfacy exposes completion metadata for:

- command names
- command aliases
- option flags
- `Literal` choices
- `Enum` choices

```python
from typing import Literal


def deploy(environment: Literal["dev", "staging", "prod"]) -> None:
    ...
```

The environment values can be offered by the shell completion layer.

## CLI entrypoint

The `interfacy` entrypoint can also enable completion through configuration.

```toml
[behavior]
tab_completion = true
```

See {doc}`../cli/config` for configuration files.

## Missing argcomplete

If completion is enabled but `argcomplete` is not installed, Interfacy warns and continues. Your command still runs normally; only completion is unavailable.
