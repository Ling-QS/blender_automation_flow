from ..runtime_core.module_loading import bind_local_package_exports, resolve_local_package_export

_MODULE_SPECS = (
    ("assembly_helpers", "assembly_helpers"),
    ("context_geometry_nodes", "context_geometry_nodes"),
    ("display_helpers", "display_helpers"),
    ("dynamic_socket_helpers", "dynamic_socket_helpers"),
    ("flow_nodes", "flow_nodes"),
    ("group_node_helpers", "group_node_helpers"),
    ("input_nodes", "input_nodes"),
    ("math_nodes", "math_nodes"),
    ("object_nodes", "object_nodes"),
    ("property_data_helpers", "property_data_helpers"),
    ("property_data_nodes", "property_data_nodes"),
    ("property_package_nodes", "property_package_nodes"),
    ("preview_nodes", "preview_nodes"),
    ("socket_rebuild_helpers", "socket_rebuild_helpers"),
    ("task_helpers", "task_helpers"),
    ("task_nodes", "task_nodes"),
)

bind_local_package_exports(globals(), __package__, _MODULE_SPECS)


def __getattr__(name):
    return resolve_local_package_export(globals(), name, __name__)
