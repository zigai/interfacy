class HelpStringTheme:

    def __init__(self, type: str, default: str, sep: str, slice_typename: bool) -> None:
        self.type = type
        self.default = default
        self.sep = sep
        self.slice_typename = slice_typename

    @property
    def dict(self):
        return {
            "type": self.type,
            "default": self.default,
            "sep": self.sep,
            "slice_typename": self.slice_typename,
        }
