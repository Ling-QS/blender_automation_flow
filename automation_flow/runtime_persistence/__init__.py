import importlib

reload_checkpoint = importlib.import_module(f"{__name__}.reload_checkpoint")
serialization = importlib.import_module(f"{__name__}.serialization")

for _module in (reload_checkpoint, serialization):
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
    if name == "reload_checkpoint":
        return reload_checkpoint
    if name == "serialization":
        return serialization
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
