import sys

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

_RUNTIME_PROPERTY_DEFINITION_EXPORTS = (
    "_is_composite_property_assignment",
    "_is_composite_property_definition",
    "_modifier_filter_settings_from_metadata",
    "_property_definition_has_content",
)

_RUNTIME_PROPERTY_API_EXPORTS = (
    "_is_composite_property_package",
    "_property_role_label",
    "_property_scope_label",
    "_summarize_property_package",
)

_RUNTIME_STATE_CACHE_EXPORTS = ("_has_stored_property_package",)

_NODE_SYSTEM_CONFIG_EXPORTS = (
    "BOOLEAN_MATH_OPERATION_ITEMS",
    "COMPARE_MODE_ITEMS",
    "COMPARE_OPERATION_ITEMS",
    "COMPARE_VECTOR_MODE_ITEMS",
    "CONVERSION_MODE_ITEMS",
    "CONVERSION_SOCKET_MAP",
    "CUSTOM_MENU_SOCKET_IDNAMES",
    "CUSTOM_NUMERIC_SOCKET_IDNAMES",
    "FLOAT_MATH_OPERATION_ITEMS",
    "GROUP_NODE_INPUT_IDENTIFIERS_KEY",
    "GROUP_NODE_OUTPUT_IDENTIFIERS_KEY",
    "GROUP_RESERVED_SOCKET_TYPES",
    "GROUP_SUPPORTED_SOCKET_IDNAMES",
    "INDEX_SWITCH_MODE_ITEMS",
    "INDEX_SWITCH_SOCKET_IDNAME_BY_MODE",
    "INDEX_SWITCH_VIRTUAL_LABEL",
    "INTEGER_MATH_OPERATION_ITEMS",
    "MIX_MODE_ITEMS",
    "MAP_RANGE_MODE_ITEMS",
    "NUMERIC_COMPATIBLE_SOCKET_IDNAMES",
    "OBJECT_DISPLAY_TYPE_ITEMS",
    "OBJECT_INTERACTION_MODE_ITEMS",
    "OBJECT_ROTATION_MODE_ITEMS",
    "PAIR_KIND_END_INPUT_SOCKET",
    "PAIR_KIND_END_TYPE",
    "PAIR_KIND_START_OUTPUT_SOCKET",
    "PAIR_KIND_START_TYPE",
    "PAIR_NODE_FALLBACK_WIDTH",
    "PAIR_NODE_HORIZONTAL_OFFSET",
    "PAIR_NODE_PLACEMENT_GAP",
    "PAIR_NODE_TYPE_MAP",
    "PHYSICS_BAKE_TASK_INPUT_PREFIX",
    "PHYSICS_BAKE_TASK_SOCKET_IDNAME",
    "PHYSICS_BAKE_TASK_VIRTUAL_LABEL",
    "PROPERTY_ASSIGNMENT_INPUT_PREFIX",
    "PROPERTY_ASSIGNMENT_VIRTUAL_LABEL",
    "PROPERTY_DATA_FIELD_SPECS",
    "PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS",
    "PROPERTY_PACKAGE_FILTER_MODE_ITEMS",
    "RANDOM_TYPE_ITEMS",
    "RENDER_MODE_ITEMS",
    "ROTATION_AXIS_ITEMS",
    "ROTATION_PIVOT_AXIS_ITEMS",
    "ROTATION_SPACE_ITEMS",
    "RUN_TASK_PLAN_FAILURE_POLICY_ITEMS",
    "RUN_TASK_PLAN_INPUT_PREFIX",
    "RUN_TASK_PLAN_VIRTUAL_LABEL",
    "SORT_MODE_ITEMS",
    "STATUS_VALUE_ITEMS",
    "STRING_COMPARE_OPERATION_ITEMS",
    "SWITCH_MODE_ITEMS",
    "SWITCH_SOCKET_IDNAME_BY_MODE",
    "TASK_STEP_INPUT_SPECS",
    "TASK_STEP_OUTPUT_SPECS",
    "VECTOR_BOOL_MODE_ITEMS",
    "VECTOR_COMPONENT_MODE_ITEMS",
    "VECTOR_MATH_OPERATION_ITEMS",
    "VIEWPORT_SHADING_MODE_ITEMS",
)

_UI_NODE_CONSTANT_EXPORTS = (
    "APPLY_OBJECT_PROPERTIES_MODE_ITEMS",
    "BAKE_TASK_BAKE_MODE_ITEMS",
    "BAKE_TASK_BAKE_TARGET_ITEMS",
    "COLLECTION_LINK_MODE_ITEMS",
    "CONTEXT_REDUCE_OPERATION_ITEMS",
    "CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE",
    "CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE",
    "CONTEXT_REDUCE_VALUE_TYPE_ITEMS",
    "CONTEXT_REDUCE_VECTOR_MODE_ITEMS",
    "CREATE_OBJECT_TYPE_ITEMS",
    "DEPENDENCY_SCOPE_ITEMS",
    "DEPENDENCY_STRATEGY_ITEMS",
    "DUPLICATE_DATA_MODE_ITEMS",
    "GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE",
    "GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS",
    "LIGHT_TYPE_ITEMS",
    "MISSING_POLICY_ITEMS",
    "MODIFIER_NAME_MATCH_MODE_ITEMS",
    "MODIFIER_TYPE_FILTER_ITEMS",
    "OBJECT_TYPE_FILTER_ITEMS",
    "PREVIEW_DATA_MODE_BY_SOCKET_IDNAME",
    "PREVIEW_DATA_MODE_ITEMS",
    "PREVIEW_DATA_MODE_SPECS",
    "PREVIEW_DATA_VIRTUAL_LABEL",
    "PREVIEW_PROPERTY_DEFINITION_VIEW_MODE_ITEMS",
    "PREVIEW_PROPERTY_PACKAGE_VIEW_MODE_ITEMS",
    "PREVIEW_TASK_PLAN_VIEW_MODE_ITEMS",
    "PROPERTY_DATA_OUTPUT_MODE_ITEMS",
    "REFRESH_PROPERTY_PACKAGE_RANGE_MODE_ITEMS",
    "PROPERTY_PACKAGE_STORE_MODE_ITEMS",
    "PROPERTY_SOURCE_CURRENT",
    "PROPERTY_SOURCE_VALUE",
    "PROPERTY_VALUE_SOURCE_ITEMS",
    "SAMPLE_OBJECT_INDEX_MODE_ITEMS",
    "SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE",
    "SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE",
    "SCENE_TIME_OUTPUT_SOCKET_SPECS",
)

_NODES_MODULE_PACKAGE_EXPORTS = (
    "CONTEXT_GEOMETRY_NODE_CLASS_NAMES",
    "CONTEXT_GEOMETRY_NODE_EXPORTS",
    "EDITOR_CONTEXT_EXPORTS",
    "FLOW_NODE_CLASS_NAMES",
    "FLOW_NODE_EXPORTS",
    "INPUT_NODE_CLASS_NAMES",
    "INPUT_NODE_EXPORTS",
    "MATH_NODE_CLASS_NAMES",
    "MATH_NODE_EXPORTS",
    "OBJECT_NODE_CLASS_NAMES",
    "OBJECT_NODE_EXPORTS",
    "PAIR_HELPER_EXPORTS",
    "PREVIEW_NODE_CLASS_NAMES",
    "PREVIEW_NODE_EXPORTS",
    "PROPERTY_DATA_NODE_CLASS_NAMES",
    "PROPERTY_DATA_NODE_EXPORTS",
    "PROPERTY_PACKAGE_NODE_CLASS_NAMES",
    "PROPERTY_PACKAGE_NODE_EXPORTS",
    "TASK_NODE_CLASS_NAMES",
    "TASK_NODE_EXPORTS",
    "build_context_geometry_node_classes",
    "build_display_helpers",
    "build_dynamic_socket_helpers",
    "build_flow_node_classes",
    "build_group_node_helpers",
    "build_input_node_classes",
    "build_math_node_classes",
    "build_object_node_classes",
    "build_preview_node_classes",
    "build_property_data_helpers",
    "build_property_data_node_classes",
    "build_property_package_node_classes",
    "build_socket_rebuild_helpers",
    "build_task_node_helpers",
    "build_task_node_classes",
    "preview_context_for_builder",
    "register_classes",
    "unregister_classes",
)


def _bind_named_exports(target_namespace, source_module, export_names):
    for export_name in export_names:
        target_namespace[export_name] = getattr(source_module, export_name)


def initialize_default_nodes_module(module_globals):
    from ..node_system import config as node_system_config_module
    from ..node_system import editor_context as editor_context_module
    from ..node_system import pair_helpers as pair_helpers_module
    from ..node_system.tree import AFNodeTree
    from ..runtime_property import api as runtime_property_api_module
    from ..runtime_property import definitions as runtime_property_definitions_module
    from ..runtime_state import cache as runtime_state_cache_module
    from ..ui import node_constants as ui_node_constants_module

    package_module = sys.modules[__name__]

    _bind_named_exports(module_globals, runtime_property_definitions_module, _RUNTIME_PROPERTY_DEFINITION_EXPORTS)
    _bind_named_exports(module_globals, runtime_property_api_module, _RUNTIME_PROPERTY_API_EXPORTS)
    _bind_named_exports(module_globals, runtime_state_cache_module, _RUNTIME_STATE_CACHE_EXPORTS)
    _bind_named_exports(module_globals, node_system_config_module, _NODE_SYSTEM_CONFIG_EXPORTS)
    _bind_named_exports(module_globals, ui_node_constants_module, _UI_NODE_CONSTANT_EXPORTS)
    _bind_named_exports(module_globals, package_module, _NODES_MODULE_PACKAGE_EXPORTS)
    module_globals["AFNodeTree"] = AFNodeTree

    return globals()["assembly_helpers"].initialize_nodes_module(
        module_globals,
        editor_context_module=editor_context_module,
        pair_helpers_module=pair_helpers_module,
        AFNodeTree=AFNodeTree,
    )


def __getattr__(name):
    return resolve_local_package_export(globals(), name, __name__)


__all__.append("initialize_default_nodes_module")
