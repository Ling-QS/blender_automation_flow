import importlib

objects = importlib.import_module(f"{__name__}.objects")

for _name in dir(objects):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(objects, _name)

__all__ = sorted(
    _name
    for _name in globals()
    if _name.startswith("_") and not _name.startswith("__")
)


def __getattr__(name):
    if name == "api":
        return importlib.import_module(f"{__name__}.api")
    if name == "objects":
        return objects
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
