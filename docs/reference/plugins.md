# Plugins

This page lists the public plugin API.

For a guide-style introduction, see {doc}`../backends/plugins`.

## Base class

```{eval-rst}
.. autoclass:: interfacy.plugins.InterfacyPlugin
   :members:
   :exclude-members: __init__, __new__
```

## Contexts

```{eval-rst}
.. autoclass:: interfacy.plugins.ConfigureContext
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.plugins.BeforeParseContext
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.plugins.SchemaTransformContext
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.plugins.AfterParseContext
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.plugins.HelpHookContext
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.plugins.ExecuteContext
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.plugins.ParseFailureContext
   :members:
   :exclude-members: __init__, __new__
```

## Help content

```{eval-rst}
.. autoclass:: interfacy.help.HelpContext
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.help.HelpContent
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.help.HelpSection
   :members:
   :exclude-members: __init__, __new__
```


## Backend-native context

```{eval-rst}
.. autoclass:: interfacy.plugins.BackendPlugin
   :members:
   :exclude-members: __init__, __new__

.. autoclass:: interfacy.plugins.BackendPluginContext
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
