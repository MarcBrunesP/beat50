"""Errors the app can show in the user's language.

Each one carries a `code` that picks the translated message and the `params` to fill it in. Its plain
text (str) is the English message, used by the command line.
"""


class BeatcrateError(RuntimeError):
    def __init__(self, code, message, **params):
        super().__init__(message)
        self.code = code
        self.params = params
