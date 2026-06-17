# Colors

Color themes style help output without changing command behavior.

```python
from interfacy import Interfacy
from interfacy.appearance import Modern
from interfacy.appearance.colors import Aurora

Interfacy(
    help_layout=Modern(style=Aurora()),
).run(main)
```

## Built-in themes

- `NoColor`
- `Aurora`
- `ClapColors`

```python
from interfacy.appearance import ClapLayout
from interfacy.appearance.colors import ClapColors, NoColor

Interfacy(help_layout=ClapLayout(style=ClapColors())).run(main)
Interfacy(help_colors=NoColor()).run(main)
```

`help_colors=` applies a theme to the selected layout.

## Custom colors

Color themes are configuration objects. You can override individual fields.

```python
from stdl.st import TextStyle
from interfacy.appearance.colors import Aurora

colors = Aurora(
    flag_long=TextStyle(color="light_green", style="bold"),
    default=TextStyle(color="yellow"),
)
```

Custom colors affect terminal output, CI logs, and copied bug reports.

## Disable colors

```python
from interfacy.appearance.colors import NoColor

Interfacy(help_colors=NoColor()).run(main)
```

You can also use the independent argparse wrapper with `color=False` when you need plain output from a manual parser.
