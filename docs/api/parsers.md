# Parsers

The parser classes are the main programmatic entry points for Interfacy. Use
`Argparser` for the standard argparse-backed flow, or `ClickParser` when you
want Click integration.

## Argparser

`Argparser` and `ClickParser` both accept a parser-level `help_position`
keyword argument. Use it to push the help-description column further right
without having to build a custom `HelpLayout` first.

```{eval-rst}
.. autoclass:: interfacy.Argparser
   :members:
   :exclude-members: __init__
   :show-inheritance:
```

## ClickParser

For Click-backed parsers, `help_position` preserves the native Click-style help
layout while changing the column where option and command descriptions begin.

```{eval-rst}
.. autoclass:: interfacy.ClickParser
   :members:
   :exclude-members: __init__
   :show-inheritance:
```
