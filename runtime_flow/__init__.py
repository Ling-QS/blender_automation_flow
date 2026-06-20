import importlib

helpers = importlib.import_module(f"{__name__}.helpers")

for _name in dir(helpers):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(helpers, _name)

__all__ = sorted(
    _name
    for _name in globals()
    if _name.startswith("_") and not _name.startswith("__")
)


def __getattr__(name):
    if name == "api":
        return importlib.import_module(f"{__name__}.api")
    if name == "helpers":
        return helpers
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
