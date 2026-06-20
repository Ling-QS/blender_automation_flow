import importlib

from .module_exports import resolve_module_export


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
    "bind_local_package_exports",
    "load_local_submodules",
    "resolve_local_package_export",
]
