# Help

The help package contains the layout, color, and formatting objects used to
control how Interfacy renders CLI help.

## Base Types

The base help classes are configuration-heavy. For these objects, the constructor
signature is the useful part of the API; inherited rendering methods are
documented once on `HelpLayout` instead of repeated on every preset.

### `HelpLayout`

Base layout configuration object used by the help system. Its constructor
parameters define the available formatting knobs.

Grouped command listings can be tuned with ``command_indent`` for the global
command-row indentation and ``command_group_spacing`` for the number of blank
lines inserted between help-group sections.

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.format_argument
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.format_description
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.format_parameter
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.format_usage_metavar
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_command_description
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_commands_ljust
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_help_for_class
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_help_for_multiple_commands
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_help_for_parameter
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_parser_command_usage_suffix
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_primary_boolean_flag_for_argument
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.get_subcommand_usage_token
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.is_argument_boolean
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.keep_help_default_slot_for_arguments
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.order_class_methods_for_help
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.order_commands_for_help
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.order_option_arguments_for_help
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.prepare_default_field_width_for_arguments
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.prepare_default_field_width_for_params
```

```{eval-rst}
.. automethod:: interfacy.help.layout.HelpLayout.should_render_description_before_usage
```

- `InterfacyColors`
- `InterfacyLayout`

## Layouts

- `StandardLayout`
- `ArgparseLayout`
- `Aligned`
- `AlignedTyped`
- `Modern`
- `ClapLayout`

## Color Themes

- `NoColor`
- `Aurora`
- `ClapColors`

## Help Sorting

```{eval-rst}
.. autodata:: interfacy.schema.sorting.HelpOptionSortRule
```

```{eval-rst}
.. autodata:: interfacy.schema.sorting.HELP_OPTION_SORT_RULE_VALUES
```

```{eval-rst}
.. autodata:: interfacy.schema.sorting.DEFAULT_HELP_OPTION_SORT_RULES
```

```{eval-rst}
.. autofunction:: interfacy.schema.sorting.normalize_sort_rule_name
```

```{eval-rst}
.. autofunction:: interfacy.schema.sorting.resolve_sort_rules
```

```{eval-rst}
.. autofunction:: interfacy.schema.sorting.resolve_help_option_sort_rules
```

```{eval-rst}
.. autofunction:: interfacy.schema.sorting.default_help_option_sort_rules
```

```{eval-rst}
.. autodata:: interfacy.schema.sorting.HelpSubcommandSortRule
```

```{eval-rst}
.. autodata:: interfacy.schema.sorting.HELP_SUBCOMMAND_SORT_RULE_VALUES
```

```{eval-rst}
.. autodata:: interfacy.schema.sorting.DEFAULT_HELP_SUBCOMMAND_SORT_RULES
```

```{eval-rst}
.. autofunction:: interfacy.schema.sorting.resolve_help_subcommand_sort_rules
```

```{eval-rst}
.. autofunction:: interfacy.schema.sorting.default_help_subcommand_sort_rules
```

## Type Formatting

```{eval-rst}
.. autoclass:: interfacy.help.formatting.TypeHelpFormatter
   :members: format
   :exclude-members: __init__, __new__
   :show-inheritance:
```

```{eval-rst}
.. autofunction:: interfacy.help.formatting.format_type_for_help
```

## Rendering

### `SchemaHelpRenderer`

Turns schema objects into final help text using a selected layout.

```{eval-rst}
.. automethod:: interfacy.help.renderer.SchemaHelpRenderer.render_parser_help
```

```{eval-rst}
.. automethod:: interfacy.help.renderer.SchemaHelpRenderer.render_command_help
```

```{eval-rst}
.. autofunction:: interfacy.help.renderer.has_grouped_commands
```

```{eval-rst}
.. autofunction:: interfacy.help.renderer.command_has_grouped_subcommands
```
