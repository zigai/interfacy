# Layouts

A layout controls how help output is rendered.

```python
from interfacy import Interfacy
from interfacy.help import ClapLayout

Interfacy(help_layout=ClapLayout()).run(main)
```

The command behavior does not change. Only the help presentation changes.

## Built-in layouts

- `InterfacyLayout`
- `StandardLayout`
- `ArgparseLayout`
- `Aligned`
- `AlignedTyped`
- `Modern`
- `ClapLayout`

```python
from interfacy.help import Aligned, Modern, StandardLayout

Interfacy(help_layout=Aligned()).run(main)
Interfacy(help_layout=Modern()).run(main)
Interfacy(help_layout=StandardLayout()).run(main)
```

## Layout settings

Layouts expose formatting options as constructor keyword arguments.

```python
from interfacy.help import Aligned

layout = Aligned(
    help_position=32,
    command_indent=4,
    command_group_spacing=1,
)

Interfacy(help_layout=layout).run(main)
```

Common settings include:

- `help_position` for the description column
- `command_indent` for command rows
- `command_group_spacing` for grouped command sections
- `help_option_sort_default` for option order
- `help_subcommand_sort_default` for command order

## Parser-level override

`Interfacy(help_position=...)` can override the layout's help column for one parser.

```python
Interfacy(
    help_layout=Aligned(),
    help_position=36,
).run(main)
```

This sets one column width without creating a custom layout subclass.

## Rendering behavior

Schema-backed argparse and Click commands use the same help renderer. Layout measurements are
scoped to each render, so one layout instance can be reused across commands without carrying
column widths or terminal dimensions from an earlier help screen. An explicit backend terminal
width takes precedence over the process terminal size.

Manually constructed schema-less `ArgumentParser` objects continue to use native argparse help
formatting with the selected adaptive layout settings.

Custom layouts should use the documented `HelpLayout` methods and constructor fields as extension
points. Private row, measurement, wrapping, and template helpers are implementation details.

## API reference

See {doc}`../api/help` for the full layout API.
