from ...runtime_core.module_loading import bind_local_package_exports, resolve_local_package_export

_MODULE_SPECS = (
    ("property_package_bake", "property_package_bake"),
    ("common", "common"),
    ("data", "data"),
    ("refs", "refs"),
    ("status", "status"),
)

bind_local_package_exports(globals(), __package__, _MODULE_SPECS)


def __getattr__(name):
    return resolve_local_package_export(globals(), name, __name__)
