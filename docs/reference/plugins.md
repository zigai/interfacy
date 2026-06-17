# Plugins

This page lists the public plugin API.

For a guide-style introduction, see {doc}`../backends/plugins`.

## Base class

```{eval-rst}
.. autoclass:: interfacy.plugins.InterfacyPlugin
   :members:
   :exclude-members: __init__, __new__
```

## Context

```{eval-rst}
.. autoclass:: interfacy.plugins.PluginContext
   :members:
   :exclude-members: __init__, __new__
```

## Parse failure

```{eval-rst}
.. autoclass:: interfacy.plugins.ParseFailureKind
   :members:
```

```{eval-rst}
.. autoclass:: interfacy.plugins.ArgumentRef
   :members:
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.plugins.ParseFailure
   :members:
   :exclude-members: __init__, __new__
```

## Recovery actions

```{eval-rst}
.. autoclass:: interfacy.plugins.ProvideArgumentValues
   :members:
   :exclude-members: __init__, __new__
```

```{eval-rst}
.. autoclass:: interfacy.plugins.AbortRecovery
   :members:
   :exclude-members: __init__, __new__
```
