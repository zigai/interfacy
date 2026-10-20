# Lazy Commands

Register a command by import path to import its module only when the command line selects it.

```python
parser = Interfacy(print_result=True)
parser.add_command("app.reports:export")
parser.add_group("app.admin:create_group")
parser.add_command("tools/sync.py:Sync", name="sync")
parser.run()
```

A target is `"module:object"` or `"path.py:object"`. `add_group()` also accepts a function that returns a `CommandGroup`.

`--help` and unknown commands import no targets. `app admin --help` imports only `app.admin`.

The name and description are read from the target's source:

- a function or class: its name and docstring
- a `CommandGroup(...)` call, or the one a factory function returns: its literal `name`, `description`, and `aliases`

If a value is not a string literal, registration fails. Pass `name=` or `description=` instead. Finding a dotted module imports its parent packages, so keep their `__init__.py` files light.

An import error is raised only when its command runs. `build_parser_schema()` and `build_parser()` import every target, which makes a test that loads all commands a one-liner:

```python
def test_commands_import() -> None:
    build_cli().build_parser_schema()
```
