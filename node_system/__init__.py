from ..runtime_core.module_exports import resolve_module_export
from . import config, editor_context, sockets, tree

_SUBMODULES = (config, editor_context, sockets, tree)

__all__ = [
    "config",
    "editor_context",
    "sockets",
    "tree",
]


def __getattr__(name):
    if name in __all__:
        return globals()[name]
    return resolve_module_export(_SUBMODULES, name, __name__)
