class TransientError(Exception):
    """A temporary problem (timeout, server error). Worth retrying."""


class ToolError(Exception):
    """A permanent problem with a clear code the agent can react to."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
