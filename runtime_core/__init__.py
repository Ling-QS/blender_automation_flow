import importlib

constants = importlib.import_module(f"{__name__}.constants")
registration = importlib.import_module(f"{__name__}.registration")

for _module in (constants, registration):
    for _name in dir(_module):
        if not _name.startswith("__"):
            globals()[_name] = getattr(_module, _name)

__all__ = sorted(
    _name
    for _name in globals()
    if not _name.startswith("__")
)


def __getattr__(name):
    if name == "api":
        return importlib.import_module(f"{__name__}.api")
    if name == "constants":
        return constants
    if name == "registration":
        return registration
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
