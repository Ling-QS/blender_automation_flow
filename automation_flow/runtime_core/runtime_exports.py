import importlib


_BASE_PACKAGE = __name__.rsplit(".", 2)[0]
_GROUP_MODULE_PATHS = {
    "bake": f"{_BASE_PACKAGE}.runtime_bake.api",
    "constants": f"{_BASE_PACKAGE}.runtime_core.constants",
    "flow": f"{_BASE_PACKAGE}.runtime_flow.helpers",
    "property": f"{_BASE_PACKAGE}.runtime_property",
    "scene": f"{_BASE_PACKAGE}.runtime_scene.objects",
    "state": f"{_BASE_PACKAGE}.runtime_state.cache",
    "task_ref": f"{_BASE_PACKAGE}.runtime_task_ref.api",
}

_GROUP_EXPORTS = {
    "bake": (
        "_apply_geometry_bake_entry_settings",
        "_apply_temporary_geometry_bake_settings",
        "_call_operator_with_override",
        "_clear_geometry_bake_tracked_packed_cache_state",
        "_ensure_background_geometry_task_supported",
        "_find_geometry_bake_entry_for_task",
        "_geometry_bake_cache_status_from_node",
        "_invoke_geometry_nodes_bake_task",
        "_invoke_physics_bake_all_task",
        "_invoke_physics_bake_task",
        "_physics_bake_cache_status_from_node",
        "_restore_geometry_bake_entry_settings",
        "_restore_waiting_bake_cleanup",
    ),
    "constants": (
        "FLOW_WAIT",
        "FLOW_YIELD",
        "PROPERTY_PACKAGE_ROLE_SNAPSHOT",
        "PROPERTY_PACKAGE_SCOPE_MODIFIER",
        "STATUS_CANCELLED",
        "STATUS_FAILED",
        "STATUS_IDLE",
        "STATUS_RELOADING",
        "STATUS_RUNNING",
        "STATUS_SUCCESS",
        "STATUS_WAITING",
        "TASK_KIND_GEOMETRY",
        "TASK_KIND_PHYSICS",
        "FlowExecutionError",
    ),
    "flow": (
        "_find_single_from_input_socket",
        "_find_single_to_output_socket",
        "_first_output_node",
        "_scan_repeat_pairs",
        "_socket_specific_output_key",
    ),
    "property": (
        "_build_allowed_object_identity_filter",
        "_clone_property_definition",
        "_is_composite_property_assignment",
        "_is_composite_property_definition",
        "_is_composite_property_package",
        "_iter_property_assignment_entries",
        "_iter_property_definition_entries",
        "_iter_property_package_entries",
        "_matches_modifier_filters",
        "_merge_property_definitions",
        "_modifier_filter_settings_from_metadata",
        "_property_definition_has_content",
        "_property_package_item_matches_allowed_objects",
        "_property_package_item_count",
        "_property_package_to_definition",
        "_property_role_label",
        "_property_scope_label",
        "_validate_property_definition",
        "_validate_property_package",
    ),
    "scene": (
        "_collect_constraint_pointer_references",
        "_collect_depsgraph_dependency_objects",
        "_collect_direct_depsgraph_dependency_objects",
        "_collect_direct_static_dependency_objects",
        "_collect_direct_task_dependency_objects",
        "_collect_explicit_physics_collision_filter_ids",
        "_collect_explicit_physics_collision_objects",
        "_collect_modifier_pointer_references",
        "_collect_objects_from_node_group",
        "_collect_render_enabled_scene_objects",
        "_collect_static_task_dependency_objects",
        "_collect_task_dependency_objects",
        "_get_physics_collision_collection",
        "_iter_collection_objects",
        "_iter_physics_collision_collection_objects",
        "_iter_scene_objects",
        "_link_object_to_collection_safe",
        "_object_has_collision_modifier",
        "_remove_unused_object_data",
        "_socket_default_pointer",
        "_unlink_object_from_collection_safe",
    ),
    "state": (
        "_auto_flow_bake_action_has_cached_data",
        "_auto_flow_bake_cache_status_from_node",
        "_clear_stored_property_package",
        "_fallback_group_instance_stored_property_package",
        "_find_auto_flow_bake_action_for_node",
        "_has_stored_property_package",
        "_is_bake_job_running",
        "_read_reload_resume_checkpoint",
        "_read_stored_property_package_direct",
        "_reload_resume_checkpoint_path",
        "_remove_reload_resume_checkpoint",
        "_summarize_property_package",
        "_write_reload_resume_checkpoint",
    ),
    "task_ref": (
        "_build_auto_flow_bake_task_ref_fallback",
        "_ensure_object_persistent_uuid",
        "_obj_item",
        "_object_list_from_task_ref",
        "_resolve_bake_target",
        "_resolve_physics_task_target",
        "_stored_property_package_key_for_node",
    ),
}

_MODULE_CACHE = {}
_EXPORT_TO_MODULE_PATH = {
    name: _GROUP_MODULE_PATHS[group_name]
    for group_name, names in _GROUP_EXPORTS.items()
    for name in names
}

STABLE_EXPORTS = tuple(_GROUP_EXPORTS["constants"])
LEGACY_EXPORTS = tuple(
    name
    for group_name, names in _GROUP_EXPORTS.items()
    if group_name != "constants"
    for name in names
)
ALL_EXPORTS = tuple(dict.fromkeys(STABLE_EXPORTS + LEGACY_EXPORTS))
EXPORT_GROUPS = {
    "stable": STABLE_EXPORTS,
    "legacy": LEGACY_EXPORTS,
    **{group_name: tuple(names) for group_name, names in _GROUP_EXPORTS.items()},
}


def has_runtime_export(name):
    return name in _EXPORT_TO_MODULE_PATH


def resolve_runtime_export(name):
    module_path = _EXPORT_TO_MODULE_PATH.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = _MODULE_CACHE.get(module_path)
    if module is None:
        module = importlib.import_module(module_path)
        _MODULE_CACHE[module_path] = module
    return getattr(module, name)


__all__ = [
    "ALL_EXPORTS",
    "EXPORT_GROUPS",
    "LEGACY_EXPORTS",
    "STABLE_EXPORTS",
    "has_runtime_export",
    "resolve_runtime_export",
]
