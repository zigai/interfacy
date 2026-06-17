# Sorting

Interfacy can sort option rows and subcommand rows in help output.

The command behavior does not change. Sorting only affects help.

## Option sorting

Pass `help_option_sort` to the parser or to one command.

```python
from interfacy import Interfacy

Interfacy(
    help_option_sort=["required_first", "short_first", "alphabetical"],
).run(main)
```

Available option rules are:

- `required_first`
- `short_first`
- `value_first`
- `bool_last`
- `no_default_first`
- `choices_first`
- `name_length`
- `alias_count`
- `alphabetical`

Rules are applied in order. Later rules break ties from earlier rules.

## Subcommand sorting

Pass `help_subcommand_sort` to control command rows.

```python
Interfacy(
    help_subcommand_sort=["alphabetical"],
).run(build, clean, test)
```

Available subcommand rules are:

- `insert_order`
- `alphabetical`
- `name_length_asc`
- `name_length_desc`

The default is insertion order.

## Per-command sorting

A command can override the parser default.

```python
parser = Interfacy(help_subcommand_sort=["alphabetical"])
parser.add_command(Admin, help_subcommand_sort=["insert_order"])
parser.run()
```

This gives one command group a manual row order while the parser keeps its default.

## Layout defaults

Layouts can define default sort rules. Explicit parser settings win over layout defaults.

```python
from interfacy.appearance import Modern

layout = Modern(help_option_sort_default=["required_first", "alphabetical"])
Interfacy(help_layout=layout).run(main)
```
