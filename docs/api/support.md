# Support Types


## Naming

```{eval-rst}
.. autoclass:: interfacy.naming.AbbreviationGenerator
   :members:
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.naming.DefaultAbbreviationGenerator
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.naming.NoAbbreviations
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autodata:: interfacy.naming.FlagStyle
```

```{eval-rst}
.. autodata:: interfacy.naming.TranslationMode
```

```{eval-rst}
.. autoclass:: interfacy.naming.FlagStrategy
   :members:
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.naming.DefaultFlagStrategy
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.naming.CommandNameRegistry
   :exclude-members: __init__, __new__
```

## Group Metadata

```{eval-rst}
.. autodata:: interfacy.declarations.settings.AbbreviationScope
```

```{eval-rst}
.. autoclass:: interfacy.declarations.groups.CommandEntry
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.declarations.groups.SubgroupEntry
   :exclude-members: __init__, __new__
```

## Backend Types

The low-level `ArgumentParser` also accepts `help_position` so manual argparse
setups can use the same help-description column control as `Interfacy`.

```{eval-rst}
.. autoclass:: interfacy.backends.argparse.parser.ArgumentParser
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.backends.click.commands.InterfacyClickCommand
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.backends.click.commands.InterfacyClickGroup
   :exclude-members: __init__, __new__
```
