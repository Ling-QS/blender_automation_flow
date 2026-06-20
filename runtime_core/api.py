from .module_loading import bind_package_api_exports, load_local_submodules

_package_exports = bind_package_api_exports(
    globals(),
    __package__,
    name_filter=lambda name: name not in {"importlib", "constants", "registration"},
)
load_local_submodules(
    globals(),
    __package__,
    (
        ("constants", "constants"),
        ("registration", "registration"),
    ),
)

__all__ = [
    "constants",
    "registration",
]
__all__.extend(_package_exports)
