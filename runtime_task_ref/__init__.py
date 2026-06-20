import importlib


helpers = importlib.import_module(f"{__name__}.helpers")
refs = importlib.import_module(f"{__name__}.refs")

for _module in (helpers, refs):
    for _name in getattr(_module, "__all__", ()):
        globals()[_name] = getattr(_module, _name)

_MODULE_CACHE = {
    "helpers": helpers,
    "refs": refs,
}


def _load_module(module_name):
    module = _MODULE_CACHE.get(module_name)
    if module is None:
        module = importlib.import_module(f"{__name__}.{module_name}")
        _MODULE_CACHE[module_name] = module
        globals()[module_name] = module
        for export_name in getattr(module, "__all__", ()):
            globals()[export_name] = getattr(module, export_name)
    return module


__all__ = sorted(name for name in globals() if name.startswith("_") and not name.startswith("__"))


def __getattr__(name):
    if name == "api":
        return _load_module("api")
    if name == "helpers":
        return helpers
    if name == "refs":
        return refs
    for module_name in ("helpers", "refs", "api"):
        module = _load_module(module_name)
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            if name.startswith("_") and not name.startswith("__") and name not in __all__:
                __all__.append(name)
                __all__.sort()
            return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
