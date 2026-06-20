from ...runtime_core.module_loading import bind_local_package_exports, resolve_local_package_export

_MODULE_SPECS = (
    ("active", "active"),
    ("flow_runner", "flow_runner"),
)

bind_local_package_exports(globals(), __package__, _MODULE_SPECS)


def __getattr__(name):
    return resolve_local_package_export(globals(), name, __name__)
