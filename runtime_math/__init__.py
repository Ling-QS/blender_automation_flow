import importlib

values = importlib.import_module(f"{__name__}.values")

for _name in dir(values):
    if not _name.startswith("__"):
        globals()[_name] = getattr(values, _name)

__all__ = sorted(
    _name
    for _name in globals()
    if not _name.startswith("__")
)


def __getattr__(name):
    if name == "api":
        return importlib.import_module(f"{__name__}.api")
    if name == "values":
        return values
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
