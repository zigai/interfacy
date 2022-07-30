from interfacy.cli.helpstr_theme import HelpStringTheme
from stdl.str_util import Color

PLAIN = HelpStringTheme(type=Color.WHITE, default=Color.WHITE, sep=" = ", slice_typename=False)

DEFAULT = HelpStringTheme(
    type=Color.GREEN,
    default=Color.LIGHT_BLUE,
    sep=" = ",
    slice_typename=True,
)

OLD = HelpStringTheme(
    type=Color.LIGHT_YELLOW,
    default=Color.LIGHT_BLUE,
    sep=", default: ",
    slice_typename=False,
)
