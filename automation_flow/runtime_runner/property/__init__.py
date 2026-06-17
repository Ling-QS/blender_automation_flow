from ...runtime_core.module_loading import bind_local_package_exports, resolve_local_package_export

_MODULE_SPECS = (
    ("apply", "apply"),
    ("context", "context"),
    ("data", "data"),
    ("package_actions", "package_actions"),
    ("package_data", "package_data"),
    ("stored_package", "stored_package"),
)

bind_local_package_exports(globals(), __package__, _MODULE_SPECS)


def __getattr__(name):
    return resolve_local_package_export(globals(), name, __name__)
