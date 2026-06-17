import importlib

_package_module = importlib.import_module(__package__)
for _name in getattr(_package_module, "__all__", ()):
    globals()[_name] = getattr(_package_module, _name)

objects = importlib.import_module(f"{__package__}.objects")

__all__ = [
    name
    for name in globals()
    if (name.startswith("_") and not name.startswith("__")) or name == "objects"
]
