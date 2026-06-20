def resolve_module_export(modules, name, package_name):
    if not isinstance(modules, (tuple, list)):
        modules = (modules,)
    for module in modules:
        try:
            return getattr(module, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {package_name!r} has no attribute {name!r}")


__all__ = ["resolve_module_export"]
