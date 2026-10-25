"""Persistence errors. Messages never contain SQL or connection details."""


class PersistenceError(RuntimeError):
    """A database write/read for stored results failed."""


class SessionNotFoundError(LookupError):
    pass


class ReferenceMismatchError(ValueError):
    pass
