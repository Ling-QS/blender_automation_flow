import importlib

from ..runtime_core.module_loading import bind_module_exports


api = importlib.import_module(f"{__name__}.api")
_api_exports = bind_module_exports(globals(), api)

__all__ = sorted(
    name
    for name in _api_exports
    if name.startswith("_") and not name.startswith("__")
)


def __getattr__(name):
    if name == "api":
        return api
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
