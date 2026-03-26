# Support Types

## Parser Base

```{eval-rst}
.. autoclass:: interfacy.core.InterfacyParser
   :exclude-members: __init__, __new__
```

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
.. autodata:: interfacy.group.AbbreviationScope
```

```{eval-rst}
.. autoclass:: interfacy.group.CommandEntry
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.group.SubgroupEntry
   :exclude-members: __init__, __new__
```

## Backend Types

```{eval-rst}
.. autoclass:: interfacy.argparse_backend.argument_parser.ArgumentParser
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.click_backend.commands.InterfacyClickCommand
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.click_backend.commands.InterfacyClickGroup
   :exclude-members: __init__, __new__
```
