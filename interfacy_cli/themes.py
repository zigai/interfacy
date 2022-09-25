from stdl.str_u import FG

from interfacy_cli.param_helpstring import HelpStringTheme

PLAIN = HelpStringTheme(type_clr=FG.WHITE, default_clr=FG.WHITE, sep=" = ", simplify_type=False)

DEFAULT = HelpStringTheme(
    type_clr=FG.GREEN, default_clr=FG.LIGHT_BLUE, sep=" = ", simplify_type=True, clear_metavar=True
)

OLD = HelpStringTheme(
    type_clr=FG.LIGHT_YELLOW,
    default_clr=FG.LIGHT_BLUE,
    sep=", default: ",
    simplify_type=False,
)
