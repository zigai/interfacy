# Schema API

## Parser schema

```{eval-rst}
.. autodata:: interfacy.schema.nodes.CommandType
```

```{eval-rst}
.. autoclass:: interfacy.schema.nodes.ArgumentKind
   :members:
```

```{eval-rst}
.. autoclass:: interfacy.schema.nodes.ValueShape
   :members:
```

```{eval-rst}
.. autoclass:: interfacy.declarations.params.BooleanMode
   :members:
```

```{eval-rst}
.. autoclass:: interfacy.schema.nodes.BooleanBehavior
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.ExecutableFlag
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.schema.nodes.Argument
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.schema.nodes.Command
   :members: description, epilog
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.schema.nodes.ParserSchema
   :members: description, epilog, is_multi_command, get_command, canonical_names
   :exclude-members: __init__, __new__
```

## Pipe input

```{eval-rst}
.. autodata:: interfacy.declarations.pipes.PipePriority
```

```{eval-rst}
.. autoclass:: interfacy.declarations.pipes.PipeTargets
   :members: targeted_parameters
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autodata:: interfacy.declarations.pipes.TargetsInput
```

```{eval-rst}
.. autofunction:: interfacy.declarations.pipes.build_pipe_targets_config
```
