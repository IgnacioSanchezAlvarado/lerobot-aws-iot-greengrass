"""
Utility decorators for motor bus operations.
"""


def check_if_connected(func):
    """
    Decorator: ensures bus is connected before operation.

    Raises:
        RuntimeError: If bus is not connected
    """

    def wrapper(self, *args, **kwargs):
        if not self.is_connected:
            raise RuntimeError("Motor bus is not connected. Call connect() first.")
        return func(self, *args, **kwargs)

    return wrapper


def check_if_not_connected(func):
    """
    Decorator: ensures bus is NOT connected (for setup operations).

    Raises:
        RuntimeError: If bus is already connected
    """

    def wrapper(self, *args, **kwargs):
        if self.is_connected:
            raise RuntimeError("Motor bus is already connected.")
        return func(self, *args, **kwargs)

    return wrapper
