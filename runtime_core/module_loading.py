import importlib
from functools import partial, update_wrapper

from .module_exports import resolve_module_export


def bind_module_exports(namespace, module, *, export_names=None):
    export_names = tuple(getattr(module, "__all__", ()) if export_names is None else export_names)
    for name in export_names:
        namespace[name] = getattr(module, name)
    return export_names


def bind_partial_export(func, /, *args, **kwargs):
    wrapped = partial(func, *args, **kwargs)
    update_wrapper(wrapped, func)
    return wrapped


def bind_package_api_exports(namespace, package_name, *, name_filter=None):
    package_module = importlib.import_module(package_name)
    export_names = tuple(getattr(package_module, "__all__", ()))
    if callable(name_filter):
        export_names = tuple(name for name in export_names if bool(name_filter(name)))
    for name in export_names:
        namespace[name] = getattr(package_module, name)
    return export_names


def load_local_submodules(namespace, package_name, module_specs):
    loaded = {}
    for alias, relative_module_name in module_specs:
        existing = namespace.get(alias)
        if existing is None:
            module = importlib.import_module(f"{package_name}.{relative_module_name}")
        else:
            module = importlib.reload(existing)
        namespace[alias] = module
        loaded[alias] = module
    return loaded


def bind_local_package_exports(namespace, package_name, module_specs):
    loaded = load_local_submodules(namespace, package_name, module_specs)
    namespace["_EXPORT_MODULES"] = tuple(loaded[alias] for alias, _relative_module_name in module_specs)
    namespace["__all__"] = [alias for alias, _relative_module_name in module_specs]
    return loaded


def resolve_local_package_export(namespace, name, package_name):
    public_names = namespace.get("__all__", ())
    if name in public_names:
        return namespace[name]
    return resolve_module_export(namespace.get("_EXPORT_MODULES", ()), name, package_name)


__all__ = [
    "bind_module_exports",
    "bind_partial_export",
    "bind_package_api_exports",
    "bind_local_package_exports",
    "load_local_submodules",
    "resolve_local_package_export",
]
