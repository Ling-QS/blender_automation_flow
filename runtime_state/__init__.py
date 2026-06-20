import importlib


cache = importlib.import_module(f"{__name__}.cache")

for _name in dir(cache):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(cache, _name)

__all__ = sorted(
    _name
    for _name in globals()
    if _name.startswith("_") and not _name.startswith("__")
)


def __getattr__(name):
    if name == "cache":
        return cache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
