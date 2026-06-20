import importlib


api = importlib.import_module(f"{__name__}.api")

for _name in getattr(api, "__all__", ()):
    globals()[_name] = getattr(api, _name)

__all__ = sorted(
    _name
    for _name in globals()
    if _name.startswith("_") and not _name.startswith("__")
)


def __getattr__(name):
    if name == "api":
        return api
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
