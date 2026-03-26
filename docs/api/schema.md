# Schema

## Parser Schema

```{eval-rst}
.. autodata:: interfacy.schema.schema.CommandType
```

```{eval-rst}
.. autoclass:: interfacy.schema.schema.ArgumentKind
   :members:
```

```{eval-rst}
.. autoclass:: interfacy.schema.schema.ValueShape
   :members:
```

```{eval-rst}
.. autoclass:: interfacy.schema.schema.BooleanBehavior
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.schema.schema.Argument
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.schema.schema.Command
   :members: description, epilog
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.schema.schema.ParserSchema
   :members: description, epilog, is_multi_command, get_command, canonical_names
   :exclude-members: __init__, __new__
```

## Pipe Input

```{eval-rst}
.. autodata:: interfacy.pipe.PipePriority
```

```{eval-rst}
.. autoclass:: interfacy.pipe.PipeTargets
   :members: targeted_parameters
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autodata:: interfacy.pipe.TargetsInput
```

```{eval-rst}
.. autofunction:: interfacy.pipe.build_pipe_targets_config
```
