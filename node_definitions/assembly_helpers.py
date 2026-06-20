import bpy


GROUP_NODE_EXPORTS = (
    "_tag_all_af_node_editor_redraw",
    "_iter_group_interface_sockets",
    "_group_interface_socket_type",
    "_is_custom_group_socket_type",
    "_sanitize_group_node_socket_specs",
    "_build_group_node_socket_specs",
    "_group_node_expected_socket_signature",
    "_group_node_current_socket_signature",
    "_group_node_socket_signatures_match",
    "_group_node_identifier_key",
    "_decode_group_node_identifiers",
    "_encode_group_node_identifiers",
    "_copy_socket_default_value",
    "_describe_socket_reference",
    "_resolve_socket_reference",
    "_capture_dynamic_socket_state",
    "_socket_types_are_numeric_compatible",
    "_socket_types_are_string_compatible",
    "_restore_dynamic_socket_state",
    "_capture_group_socket_state",
    "_restore_group_socket_state",
    "_sync_visible_node_editor_sockets",
    "_sync_group_node_sockets",
    "_replace_group_node_instance",
    "_hard_sync_group_node",
    "_iter_group_nodes_referencing_tree",
    "_sync_group_nodes_referencing_tree",
    "_group_tree_poll",
    "_group_tree_updated",
)

PROPERTY_DATA_HELPER_EXPORTS = (
    "_OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS",
    "_apply_property_data_socket_visibility",
    "_draw_modifier_property_assignment_fields",
    "_draw_object_display_property_assignment_fields",
    "_draw_object_transform_property_assignment_fields",
    "_draw_property_data_input_socket",
    "_draw_rotation_value_inputs",
    "_initialize_object_transform_property_input_defaults",
    "_modifier_property_definition_from_node",
    "_object_display_property_definition_from_node",
    "_object_transform_property_definition_from_node",
    "_persist_property_data_manual_hidden_keys",
    "_property_data_field_specs",
    "_property_data_input_specs",
    "_property_data_output_specs",
    "_property_data_socket_key",
    "_property_data_update_socket_layout",
    "_refresh_property_data_socket_visibility",
    "_resolve_property_data_manual_hidden_keys",
    "_sync_object_transform_property_data_sockets",
    "_sync_property_data_node_sockets",
)

TASK_NODE_HELPER_EXPORTS = (
    "_socket_signature",
    "_is_physics_bake_settings_socket",
    "_is_task_plan_socket",
    "_default_task_plan_socket_name",
    "_new_property_package_bake_asset_id",
    "_iter_run_task_plan_real_inputs",
    "_sync_run_task_plan_inputs",
    "_sync_run_task_plan_sockets",
    "_remove_last_run_task_plan_input",
    "_add_run_task_plan_input",
    "_sync_physics_bake_task_inputs",
    "_sync_bake_target_sockets",
    "_sync_physics_bake_target_sockets",
    "_sync_evaluate_task_dependencies_sockets",
    "_ensure_named_socket",
    "_find_named_socket",
    "_ensure_render_target_input_sockets",
    "_sync_render_target_sockets",
    "_sync_task_step_sockets",
    "_sync_task_output_sockets",
    "_sync_branch_end_sockets",
    "_sync_run_background_task_plan_sockets",
)

DYNAMIC_SOCKET_HELPER_EXPORTS = (
    "_valid_socket_links",
    "_find_single_from_input_socket",
    "_is_property_assignment_socket",
    "_is_index_switch_value_socket",
    "_index_switch_socket_idname_for_mode",
    "_switch_socket_idname_for_mode",
    "_sample_object_index_socket_idname_for_mode",
    "_sample_object_index_output_key_for_mode",
    "_context_reduce_socket_idname_for_type",
    "_context_reduce_output_key_for_type",
    "_default_index_switch_socket_name",
    "_default_property_assignment_socket_name",
    "_iter_create_property_package_assignment_inputs",
    "_iter_index_switch_real_inputs",
    "_sync_index_switch_sockets",
    "_remove_last_index_switch_input",
    "_add_index_switch_input",
    "_sync_create_property_package_assignment_inputs",
    "_sync_property_assignment_dynamic_inputs",
    "_remove_last_create_property_package_assignment_input",
    "_add_create_property_package_assignment_input",
    "_sync_create_property_package_sockets",
    "_sync_apply_object_properties_sockets",
)

EDITOR_CONTEXT_EXPORTS = (
    "_context_node_editor_path_items",
    "_context_node_editor_space",
    "_group_path_from_path_items",
    "_path_item_node_tree",
    "_resolve_group_path_node",
    "_root_tree_from_path_items",
    "_space_matches_node_tree",
    "_space_path_items",
    "_ui_group_path",
    "_ui_root_tree",
    "_ui_runner_for_node",
)

PAIR_HELPER_EXPORTS = (
    "_PAIR_NODE_SYNC_GUARD",
    "_START_NODE_ACTIVE_SYNC_GUARD",
    "_assign_inferred_pair_ids",
    "_assign_pair_metadata",
    "_candidate_pair_location",
    "_clear_pair_metadata",
    "_create_missing_pair_node",
    "_has_selected_pending_pair_cohort",
    "_initialize_start_node",
    "_is_pair_managed_node",
    "_iter_start_nodes",
    "_materialize_selected_pending_pair",
    "_normalize_duplicate_pair_ids",
    "_node_flow_input_source",
    "_node_flow_output_target",
    "_node_layout_width",
    "_node_pointer_key",
    "_pair_auto_create_allowed",
    "_pair_counterpart",
    "_pair_counterpart_type",
    "_pair_default_location_delta",
    "_pair_duplicate_offset",
    "_pair_end_input_socket_name",
    "_pair_is_end",
    "_pair_is_start",
    "_pair_kind",
    "_pair_node_info",
    "_pair_reference_delta",
    "_pair_role",
    "_pair_sequence",
    "_pair_sequence_forward",
    "_pair_sequence_reverse",
    "_pair_start_output_socket_name",
    "_relink_pair_flow",
    "_remove_orphaned_pair_nodes",
    "_selected_pending_pair_cohort",
    "_set_pair_duplicate_offset",
    "_start_node_active_updated",
    "_start_node_auto_order_updated",
    "_start_node_auto_follow_updated",
    "_sync_active_start_nodes",
    "_sync_paired_flow_nodes",
)

DISPLAY_HELPER_EXPORTS = (
    "_DISPLAY_HELPERS",
    "_use_chinese_ui",
    "_status_value_display_label",
    "_camera_object_poll",
    "_set_node_color",
    "_enum_property_label",
    "_enum_identifier_label",
    "_hide_auxiliary_output_socket",
    "_hide_default_auxiliary_outputs",
    "_draw_compact_property_source",
    "_set_default_node_width",
)

SOCKET_REBUILD_EXPORTS = (
    "_SOCKET_REBUILD_HELPERS",
    "_rebuild_sockets",
)

INPUT_NODE_CLASS_NAMES = (
    "AFNodePlaybackState",
    "AFNodeSceneTime",
    "AFNodeFloatInput",
    "AFNodeBooleanInput",
    "AFNodeVectorInput",
    "AFNodeIntegerInput",
    "AFNodeStringInput",
    "AFNodeInputRotation",
    "AFNodeStatusInput",
)

OBJECT_NODE_CLASS_NAMES = (
    "AFNodeCollectionList",
    "AFNodeCollectionExpand",
    "AFNodeObjectList",
    "AFNodeSceneObjectList",
    "AFNodeObjectInfo",
    "AFNodeCreateCollection",
    "AFNodeAddToCollection",
    "AFNodeCreateObject",
    "AFNodeDuplicateObject",
    "AFNodeDeleteObject",
)

PREVIEW_NODE_CLASS_NAMES = ("AFNodePreviewData",)
PREVIEW_NODE_EXPORTS = PREVIEW_NODE_CLASS_NAMES + (
    ("_normalized_preview_context", "normalized_preview_context"),
    ("_schedule_preview_data_ui_refresh", "schedule_preview_data_ui_refresh"),
)

CONTEXT_GEOMETRY_NODE_CLASS_NAMES = (
    "AFNodePropertyContext",
    "AFNodeSampleObjectIndex",
    "AFNodeReduceContextValue",
    "AFNodeReadGeometryAttribute",
)
CONTEXT_GEOMETRY_NODE_EXPORTS = (
    "_sync_property_context_sockets",
    "_sync_sample_object_index_sockets",
    "_sync_context_reduce_value_sockets",
    "_sync_geometry_attribute_node_sockets",
    *CONTEXT_GEOMETRY_NODE_CLASS_NAMES,
)

PROPERTY_DATA_NODE_CLASS_NAMES = (
    "AFNodeModifierPropertyData",
    "AFNodeObjectDisplayPropertyData",
    "AFNodeObjectTransformPropertyData",
)

MATH_NODE_CLASS_NAMES = (
    "AFNodeMath",
    "AFNodeIntegerMath",
    "AFNodeBooleanMath",
    "AFNodeVectorMath",
    "AFNodeMix",
    "AFNodeSwitch",
    "AFNodeIndexSwitch",
    "AFNodeCompare",
    "AFNodeStringCompare",
    "AFNodeConvertValue",
    "AFNodeClamp",
    "AFNodeMapRange",
    "AFNodeCombineVector",
    "AFNodeSeparateVector",
    "AFNodeVectorRotate",
    "AFNodeEulerToRotation",
    "AFNodeQuaternionToRotation",
    "AFNodeAxisAngleToRotation",
    "AFNodeInvertRotation",
    "AFNodeRotateRotation",
    "AFNodeRotationToEuler",
    "AFNodeRotationToQuaternion",
    "AFNodeRotationToAxisAngle",
    "AFNodeAxesToRotation",
    "AFNodeAlignRotationToVector",
    "AFNodeCombineMatrix",
    "AFNodeSeparateMatrix",
    "AFNodeMatrixMultiply",
    "AFNodeInvertMatrix",
    "AFNodeTransposeMatrix",
    "AFNodeMatrixDeterminant",
    "AFNodeCombineTransform",
    "AFNodeSeparateTransform",
    "AFNodeTransformPoint",
    "AFNodeTransformDirection",
    "AFNodeProjectPoint",
    "AFNodeSmoothstep",
    "AFNodeRandomValue",
)

PROPERTY_PACKAGE_NODE_CLASS_NAMES = (
    "AFNodeParsePropertyPackage",
    "AFNodeMergePropertyAssignments",
    "AFNodeFilterPropertyPackage",
    "AFNodeMergePropertyPackages",
    "AFNodeCreatePropertyPackage",
    "AFNodeStorePropertyPackage",
    "AFNodeApplyObjectProperties",
    "AFNodeApplyPropertyPackage",
    "AFNodeRecordPropertyPackage",
)

FLOW_NODE_CLASS_NAMES = (
    "AFNodeGroup",
    "AFNodeStart",
    "AFNodeFlowToggle",
    "AFNodeRepeatStart",
    "AFNodeRepeatEnd",
    "AFNodeSubflowStart",
    "AFNodeSubflowJoin",
    "AFNodeBranchStart",
    "AFNodeBranchEnd",
    "AFNodeEnd",
    "AFNodeTaskStart",
    "AFNodeTaskOutput",
)

TASK_NODE_CLASS_NAMES = (
    "AFNodeResolveTaskRef",
    "AFNodeBakeTask",
    "AFNodePropertyPackageBakeTarget",
    "AFNodeTaskStep",
    "AFNodePhysicsBakeSettings",
    "AFNodePhysicsBakeTask",
    "AFNodeEvaluateTaskDependencies",
    "AFNodeRunTaskPlan",
    "AFNodeRunBackgroundTaskPlan",
    "AFNodeSetActiveCamera",
    "AFNodeRenderTarget",
    "AFNodeRenderTask",
    "AFNodeWaitForTask",
    "AFNodeDelayWait",
    "AFNodeReloadAfterTask",
)

INPUT_NODE_EXPORTS = INPUT_NODE_CLASS_NAMES
OBJECT_NODE_EXPORTS = OBJECT_NODE_CLASS_NAMES
MATH_NODE_EXPORTS = MATH_NODE_CLASS_NAMES
PROPERTY_DATA_NODE_EXPORTS = PROPERTY_DATA_NODE_CLASS_NAMES
PROPERTY_PACKAGE_NODE_EXPORTS = PROPERTY_PACKAGE_NODE_CLASS_NAMES
FLOW_NODE_EXPORTS = FLOW_NODE_CLASS_NAMES
TASK_NODE_EXPORTS = TASK_NODE_CLASS_NAMES


def preview_context_for_builder(context):
    if getattr(context, "space_data", None) is not None or getattr(context, "scene", None) is not None:
        return context
    return bpy.context


def bind_exports(module_globals, source, names):
    for item in names:
        if isinstance(item, tuple):
            target_name, source_name = item
        else:
            target_name = item
            source_name = item
        module_globals[target_name] = source[source_name]


def bind_built_exports(module_globals, builder, names, **builder_kwargs):
    bind_exports(module_globals, builder(**builder_kwargs), names)


def bind_module_exports(module_globals, module, names):
    bind_exports(module_globals, vars(module), names)


def bind_nodes_module_exports(module_globals, node_module_exports):
    bind_exports(module_globals, node_module_exports["display_helper_exports"], DISPLAY_HELPER_EXPORTS)
    bind_exports(module_globals, node_module_exports["socket_rebuild_exports"], SOCKET_REBUILD_EXPORTS)
    bind_support_helper_exports(module_globals, node_module_exports["support_helper_exports"])


def build_support_helper_exports(
    *,
    build_group_node_helpers,
    build_task_node_helpers,
    build_dynamic_socket_helpers,
    build_property_data_helpers,
    AFNodeTree,
    GROUP_NODE_INPUT_IDENTIFIERS_KEY,
    GROUP_NODE_OUTPUT_IDENTIFIERS_KEY,
    GROUP_SUPPORTED_SOCKET_IDNAMES,
    NUMERIC_COMPATIBLE_SOCKET_IDNAMES,
    PHYSICS_BAKE_TASK_INPUT_PREFIX,
    PHYSICS_BAKE_TASK_SOCKET_IDNAME,
    PHYSICS_BAKE_TASK_VIRTUAL_LABEL,
    RUN_TASK_PLAN_INPUT_PREFIX,
    RUN_TASK_PLAN_VIRTUAL_LABEL,
    TASK_STEP_INPUT_SPECS,
    TASK_STEP_OUTPUT_SPECS,
    iface_,
    CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE,
    CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE,
    INDEX_SWITCH_SOCKET_IDNAME_BY_MODE,
    INDEX_SWITCH_VIRTUAL_LABEL,
    PROPERTY_ASSIGNMENT_INPUT_PREFIX,
    PROPERTY_ASSIGNMENT_VIRTUAL_LABEL,
    SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE,
    SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE,
    SWITCH_SOCKET_IDNAME_BY_MODE,
    CUSTOM_MENU_SOCKET_IDNAMES,
    PROPERTY_DATA_FIELD_SPECS,
    PROPERTY_SOURCE_VALUE,
    _draw_compact_property_source,
    _hide_default_auxiliary_outputs,
    _rebuild_sockets,
):
    group_helpers = build_group_node_helpers(
        AFNodeTree=AFNodeTree,
        GROUP_NODE_INPUT_IDENTIFIERS_KEY=GROUP_NODE_INPUT_IDENTIFIERS_KEY,
        GROUP_NODE_OUTPUT_IDENTIFIERS_KEY=GROUP_NODE_OUTPUT_IDENTIFIERS_KEY,
        GROUP_SUPPORTED_SOCKET_IDNAMES=GROUP_SUPPORTED_SOCKET_IDNAMES,
        NUMERIC_COMPATIBLE_SOCKET_IDNAMES=NUMERIC_COMPATIBLE_SOCKET_IDNAMES,
        _rebuild_sockets=_rebuild_sockets,
    )
    task_helpers = build_task_node_helpers(
        PHYSICS_BAKE_TASK_INPUT_PREFIX=PHYSICS_BAKE_TASK_INPUT_PREFIX,
        PHYSICS_BAKE_TASK_SOCKET_IDNAME=PHYSICS_BAKE_TASK_SOCKET_IDNAME,
        PHYSICS_BAKE_TASK_VIRTUAL_LABEL=PHYSICS_BAKE_TASK_VIRTUAL_LABEL,
        RUN_TASK_PLAN_INPUT_PREFIX=RUN_TASK_PLAN_INPUT_PREFIX,
        RUN_TASK_PLAN_VIRTUAL_LABEL=RUN_TASK_PLAN_VIRTUAL_LABEL,
        TASK_STEP_INPUT_SPECS=TASK_STEP_INPUT_SPECS,
        TASK_STEP_OUTPUT_SPECS=TASK_STEP_OUTPUT_SPECS,
        iface_=iface_,
        _hide_default_auxiliary_outputs=_hide_default_auxiliary_outputs,
        _rebuild_sockets=_rebuild_sockets,
    )
    dynamic_socket_helpers = build_dynamic_socket_helpers(
        CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE=CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE,
        CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE=CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE,
        INDEX_SWITCH_SOCKET_IDNAME_BY_MODE=INDEX_SWITCH_SOCKET_IDNAME_BY_MODE,
        INDEX_SWITCH_VIRTUAL_LABEL=INDEX_SWITCH_VIRTUAL_LABEL,
        PROPERTY_ASSIGNMENT_INPUT_PREFIX=PROPERTY_ASSIGNMENT_INPUT_PREFIX,
        PROPERTY_ASSIGNMENT_VIRTUAL_LABEL=PROPERTY_ASSIGNMENT_VIRTUAL_LABEL,
        SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE=SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE,
        SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE=SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE,
        SWITCH_SOCKET_IDNAME_BY_MODE=SWITCH_SOCKET_IDNAME_BY_MODE,
        _rebuild_sockets=_rebuild_sockets,
    )
    property_data_helpers = build_property_data_helpers(
        CUSTOM_MENU_SOCKET_IDNAMES=CUSTOM_MENU_SOCKET_IDNAMES,
        PROPERTY_DATA_FIELD_SPECS=PROPERTY_DATA_FIELD_SPECS,
        PROPERTY_SOURCE_VALUE=PROPERTY_SOURCE_VALUE,
        _draw_compact_property_source=_draw_compact_property_source,
        _find_single_from_input_socket=dynamic_socket_helpers["_find_single_from_input_socket"],
        _rebuild_sockets=_rebuild_sockets,
        _socket_signature=lambda socket: task_helpers["_socket_signature"](socket),
    )
    return {
        "group_helpers": group_helpers,
        "task_helpers": task_helpers,
        "dynamic_socket_helpers": dynamic_socket_helpers,
        "property_data_helpers": property_data_helpers,
    }


def bind_support_helper_exports(module_globals, helper_exports):
    bind_exports(module_globals, helper_exports["group_helpers"], GROUP_NODE_EXPORTS)
    bind_exports(module_globals, helper_exports["task_helpers"], TASK_NODE_HELPER_EXPORTS)
    bind_exports(module_globals, helper_exports["dynamic_socket_helpers"], DYNAMIC_SOCKET_HELPER_EXPORTS)
    bind_exports(module_globals, helper_exports["property_data_helpers"], PROPERTY_DATA_HELPER_EXPORTS)


def build_base_node_class(*, AFNodeTree):
    class AFBaseNode:
        @classmethod
        def poll(cls, ntree):
            return ntree.bl_idname == AFNodeTree.bl_idname

    return AFBaseNode


def build_display_helper_exports(
    *,
    build_display_helpers,
    PROPERTY_SOURCE_CURRENT,
    PROPERTY_SOURCE_VALUE,
):
    display_helpers = build_display_helpers(
        PROPERTY_SOURCE_CURRENT=PROPERTY_SOURCE_CURRENT,
        PROPERTY_SOURCE_VALUE=PROPERTY_SOURCE_VALUE,
    )
    return {
        "_DISPLAY_HELPERS": display_helpers,
        "_use_chinese_ui": display_helpers["_use_chinese_ui"],
        "_status_value_display_label": display_helpers["_status_value_display_label"],
        "_camera_object_poll": display_helpers["_camera_object_poll"],
        "_set_node_color": display_helpers["_set_node_color"],
        "_enum_property_label": display_helpers["_enum_property_label"],
        "_enum_identifier_label": display_helpers["_enum_identifier_label"],
        "_hide_auxiliary_output_socket": display_helpers["_hide_auxiliary_output_socket"],
        "_hide_default_auxiliary_outputs": display_helpers["_hide_default_auxiliary_outputs"],
        "_draw_compact_property_source": display_helpers["_draw_compact_property_source"],
        "_set_default_node_width": display_helpers["_set_default_node_width"],
    }


def build_socket_rebuild_exports(
    *,
    build_socket_rebuild_helpers,
    _capture_dynamic_socket_state,
    _restore_dynamic_socket_state,
):
    socket_rebuild_helpers = build_socket_rebuild_helpers(
        _capture_dynamic_socket_state=_capture_dynamic_socket_state,
        _restore_dynamic_socket_state=_restore_dynamic_socket_state,
    )
    return {
        "_SOCKET_REBUILD_HELPERS": socket_rebuild_helpers,
        "_rebuild_sockets": socket_rebuild_helpers["_rebuild_sockets"],
    }


def build_registered_class_names(
    *,
    flow_names,
    input_names,
    task_names,
    object_names,
    property_package_names,
    math_names,
    preview_names,
    context_geometry_names,
    property_data_names,
):
    return (
        flow_names[:2]
        + input_names[:2]
        + flow_names[2:]
        + task_names[:1]
        + object_names
        + task_names[1:6]
        + property_package_names[:4]
        + task_names[6:7]
        + input_names[2:]
        + math_names
        + preview_names
        + task_names[7:9]
        + context_geometry_names
        + property_data_names
        + property_package_names[4:]
        + task_names[9:]
    )


def build_node_build_exports(namespace):
    ns = namespace
    return (
        (
            ns["build_input_node_classes"],
            INPUT_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                STATUS_VALUE_ITEMS=ns["STATUS_VALUE_ITEMS"],
                SCENE_TIME_OUTPUT_SOCKET_SPECS=ns["SCENE_TIME_OUTPUT_SOCKET_SPECS"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _set_node_color=ns["_set_node_color"],
                _status_value_display_label=ns["_status_value_display_label"],
            ),
        ),
        (
            ns["build_object_node_classes"],
            OBJECT_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                COLLECTION_LINK_MODE_ITEMS=ns["COLLECTION_LINK_MODE_ITEMS"],
                CREATE_OBJECT_TYPE_ITEMS=ns["CREATE_OBJECT_TYPE_ITEMS"],
                DUPLICATE_DATA_MODE_ITEMS=ns["DUPLICATE_DATA_MODE_ITEMS"],
                LIGHT_TYPE_ITEMS=ns["LIGHT_TYPE_ITEMS"],
                MISSING_POLICY_ITEMS=ns["MISSING_POLICY_ITEMS"],
                OBJECT_TYPE_FILTER_ITEMS=ns["OBJECT_TYPE_FILTER_ITEMS"],
                SORT_MODE_ITEMS=ns["SORT_MODE_ITEMS"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _set_default_node_width=ns["_set_default_node_width"],
                _set_node_color=ns["_set_node_color"],
            ),
        ),
        (
            ns["build_preview_node_classes"],
            PREVIEW_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                OBJECT_DISPLAY_TYPE_ITEMS=ns["OBJECT_DISPLAY_TYPE_ITEMS"],
                OBJECT_ROTATION_MODE_ITEMS=ns["OBJECT_ROTATION_MODE_ITEMS"],
                PREVIEW_DATA_MODE_BY_SOCKET_IDNAME=ns["PREVIEW_DATA_MODE_BY_SOCKET_IDNAME"],
                PREVIEW_DATA_MODE_ITEMS=ns["PREVIEW_DATA_MODE_ITEMS"],
                PREVIEW_DATA_MODE_SPECS=ns["PREVIEW_DATA_MODE_SPECS"],
                PREVIEW_DATA_VIRTUAL_LABEL=ns["PREVIEW_DATA_VIRTUAL_LABEL"],
                PREVIEW_PROPERTY_DEFINITION_VIEW_MODE_ITEMS=ns["PREVIEW_PROPERTY_DEFINITION_VIEW_MODE_ITEMS"],
                PREVIEW_PROPERTY_PACKAGE_VIEW_MODE_ITEMS=ns["PREVIEW_PROPERTY_PACKAGE_VIEW_MODE_ITEMS"],
                PREVIEW_TASK_PLAN_VIEW_MODE_ITEMS=ns["PREVIEW_TASK_PLAN_VIEW_MODE_ITEMS"],
                _enum_identifier_label=ns["_enum_identifier_label"],
                _find_single_from_input_socket=ns["_find_single_from_input_socket"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _is_composite_property_assignment=ns["_is_composite_property_assignment"],
                _is_composite_property_definition=ns["_is_composite_property_definition"],
                _is_composite_property_package=ns["_is_composite_property_package"],
                _modifier_filter_settings_from_metadata=ns["_modifier_filter_settings_from_metadata"],
                _normalized_preview_context=ns["preview_context_for_builder"],
                _property_definition_has_content=ns["_property_definition_has_content"],
                _property_role_label=ns["_property_role_label"],
                _property_scope_label=ns["_property_scope_label"],
                _rebuild_sockets=ns["_rebuild_sockets"],
                _set_default_node_width=ns["_set_default_node_width"],
                _summarize_property_package=ns["_summarize_property_package"],
                _ui_runner_for_node=ns["_ui_runner_for_node"],
            ),
        ),
        (
            ns["build_context_geometry_node_classes"],
            CONTEXT_GEOMETRY_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                CONTEXT_REDUCE_OPERATION_ITEMS=ns["CONTEXT_REDUCE_OPERATION_ITEMS"],
                CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE=ns["CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE"],
                CONTEXT_REDUCE_VALUE_TYPE_ITEMS=ns["CONTEXT_REDUCE_VALUE_TYPE_ITEMS"],
                CONTEXT_REDUCE_VECTOR_MODE_ITEMS=ns["CONTEXT_REDUCE_VECTOR_MODE_ITEMS"],
                GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE=ns["GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE"],
                GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS=ns["GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS"],
                SAMPLE_OBJECT_INDEX_MODE_ITEMS=ns["SAMPLE_OBJECT_INDEX_MODE_ITEMS"],
                SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE=ns["SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _rebuild_sockets=ns["_rebuild_sockets"],
                _set_default_node_width=ns["_set_default_node_width"],
                _set_node_color=ns["_set_node_color"],
                _socket_signature=ns["_socket_signature"],
            ),
        ),
        (
            ns["build_property_data_node_classes"],
            PROPERTY_DATA_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                MODIFIER_NAME_MATCH_MODE_ITEMS=ns["MODIFIER_NAME_MATCH_MODE_ITEMS"],
                MODIFIER_TYPE_FILTER_ITEMS=ns["MODIFIER_TYPE_FILTER_ITEMS"],
                OBJECT_DISPLAY_TYPE_ITEMS=ns["OBJECT_DISPLAY_TYPE_ITEMS"],
                OBJECT_ROTATION_MODE_ITEMS=ns["OBJECT_ROTATION_MODE_ITEMS"],
                PROPERTY_DATA_OUTPUT_MODE_ITEMS=ns["PROPERTY_DATA_OUTPUT_MODE_ITEMS"],
                PROPERTY_VALUE_SOURCE_ITEMS=ns["PROPERTY_VALUE_SOURCE_ITEMS"],
                _OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS=ns["_OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS"],
                _apply_property_data_socket_visibility=ns["_apply_property_data_socket_visibility"],
                _draw_modifier_property_assignment_fields=ns["_draw_modifier_property_assignment_fields"],
                _draw_object_display_property_assignment_fields=ns["_draw_object_display_property_assignment_fields"],
                _draw_object_transform_property_assignment_fields=ns["_draw_object_transform_property_assignment_fields"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _initialize_object_transform_property_input_defaults=ns["_initialize_object_transform_property_input_defaults"],
                _persist_property_data_manual_hidden_keys=ns["_persist_property_data_manual_hidden_keys"],
                _property_data_output_specs=ns["_property_data_output_specs"],
                _property_data_update_socket_layout=ns["_property_data_update_socket_layout"],
                _refresh_property_data_socket_visibility=ns["_refresh_property_data_socket_visibility"],
                _resolve_property_data_manual_hidden_keys=ns["_resolve_property_data_manual_hidden_keys"],
                _set_default_node_width=ns["_set_default_node_width"],
                _sync_object_transform_property_data_sockets=ns["_sync_object_transform_property_data_sockets"],
                _sync_property_data_node_sockets=ns["_sync_property_data_node_sockets"],
            ),
        ),
        (
            ns["build_math_node_classes"],
            MATH_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                BOOLEAN_MATH_OPERATION_ITEMS=ns["BOOLEAN_MATH_OPERATION_ITEMS"],
                COMPARE_MODE_ITEMS=ns["COMPARE_MODE_ITEMS"],
                COMPARE_OPERATION_ITEMS=ns["COMPARE_OPERATION_ITEMS"],
                COMPARE_VECTOR_MODE_ITEMS=ns["COMPARE_VECTOR_MODE_ITEMS"],
                CONVERSION_MODE_ITEMS=ns["CONVERSION_MODE_ITEMS"],
                CONVERSION_SOCKET_MAP=ns["CONVERSION_SOCKET_MAP"],
                FLOAT_MATH_OPERATION_ITEMS=ns["FLOAT_MATH_OPERATION_ITEMS"],
                INDEX_SWITCH_MODE_ITEMS=ns["INDEX_SWITCH_MODE_ITEMS"],
                INTEGER_MATH_OPERATION_ITEMS=ns["INTEGER_MATH_OPERATION_ITEMS"],
                MIX_MODE_ITEMS=ns["MIX_MODE_ITEMS"],
                RANDOM_TYPE_ITEMS=ns["RANDOM_TYPE_ITEMS"],
                ROTATION_AXIS_ITEMS=ns["ROTATION_AXIS_ITEMS"],
                ROTATION_PIVOT_AXIS_ITEMS=ns["ROTATION_PIVOT_AXIS_ITEMS"],
                ROTATION_SPACE_ITEMS=ns["ROTATION_SPACE_ITEMS"],
                STRING_COMPARE_OPERATION_ITEMS=ns["STRING_COMPARE_OPERATION_ITEMS"],
                SWITCH_MODE_ITEMS=ns["SWITCH_MODE_ITEMS"],
                VECTOR_BOOL_MODE_ITEMS=ns["VECTOR_BOOL_MODE_ITEMS"],
                VECTOR_COMPONENT_MODE_ITEMS=ns["VECTOR_COMPONENT_MODE_ITEMS"],
                VECTOR_MATH_OPERATION_ITEMS=ns["VECTOR_MATH_OPERATION_ITEMS"],
                _enum_property_label=ns["_enum_property_label"],
                _rebuild_sockets=ns["_rebuild_sockets"],
                _set_default_node_width=ns["_set_default_node_width"],
                _set_node_color=ns["_set_node_color"],
                _switch_socket_idname_for_mode=ns["_switch_socket_idname_for_mode"],
                _sync_index_switch_sockets=ns["_sync_index_switch_sockets"],
            ),
        ),
        (
            ns["build_property_package_node_classes"],
            PROPERTY_PACKAGE_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                APPLY_OBJECT_PROPERTIES_MODE_ITEMS=ns["APPLY_OBJECT_PROPERTIES_MODE_ITEMS"],
                MISSING_POLICY_ITEMS=ns["MISSING_POLICY_ITEMS"],
                PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS=ns["PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS"],
                PROPERTY_PACKAGE_FILTER_MODE_ITEMS=ns["PROPERTY_PACKAGE_FILTER_MODE_ITEMS"],
                PROPERTY_PACKAGE_STORE_MODE_ITEMS=ns["PROPERTY_PACKAGE_STORE_MODE_ITEMS"],
                SORT_MODE_ITEMS=ns["SORT_MODE_ITEMS"],
                _has_stored_property_package=ns["_has_stored_property_package"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _normalized_preview_context=ns["preview_context_for_builder"],
                _set_node_color=ns["_set_node_color"],
                _sync_apply_object_properties_sockets=ns["_sync_apply_object_properties_sockets"],
                _sync_create_property_package_sockets=ns["_sync_create_property_package_sockets"],
                _ui_runner_for_node=ns["_ui_runner_for_node"],
            ),
        ),
        (
            ns["build_flow_node_classes"],
            FLOW_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                _group_tree_poll=ns["_group_tree_poll"],
                _group_tree_updated=ns["_group_tree_updated"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _initialize_start_node=ns["_initialize_start_node"],
                _start_node_active_updated=ns["_start_node_active_updated"],
                _start_node_auto_order_updated=ns["_start_node_auto_order_updated"],
                _start_node_auto_follow_updated=ns["_start_node_auto_follow_updated"],
                _sync_group_node_sockets=ns["_sync_group_node_sockets"],
                _ui_runner_for_node=ns["_ui_runner_for_node"],
            ),
        ),
        (
            ns["build_task_node_classes"],
            TASK_NODE_EXPORTS,
            dict(
                AFBaseNode=ns["AFBaseNode"],
                BAKE_TASK_BAKE_MODE_ITEMS=ns["BAKE_TASK_BAKE_MODE_ITEMS"],
                BAKE_TASK_BAKE_TARGET_ITEMS=ns["BAKE_TASK_BAKE_TARGET_ITEMS"],
                DEPENDENCY_SCOPE_ITEMS=ns["DEPENDENCY_SCOPE_ITEMS"],
                DEPENDENCY_STRATEGY_ITEMS=ns["DEPENDENCY_STRATEGY_ITEMS"],
                RENDER_MODE_ITEMS=ns["RENDER_MODE_ITEMS"],
                RUN_TASK_PLAN_FAILURE_POLICY_ITEMS=ns["RUN_TASK_PLAN_FAILURE_POLICY_ITEMS"],
                _camera_object_poll=ns["_camera_object_poll"],
                _hide_default_auxiliary_outputs=ns["_hide_default_auxiliary_outputs"],
                _new_property_package_bake_asset_id=ns["_new_property_package_bake_asset_id"],
                _set_default_node_width=ns["_set_default_node_width"],
                _set_node_color=ns["_set_node_color"],
                _sync_bake_target_sockets=ns["_sync_bake_target_sockets"],
                _sync_evaluate_task_dependencies_sockets=ns["_sync_evaluate_task_dependencies_sockets"],
                _sync_physics_bake_target_sockets=ns["_sync_physics_bake_target_sockets"],
                _sync_render_target_sockets=ns["_sync_render_target_sockets"],
                _sync_run_background_task_plan_sockets=ns["_sync_run_background_task_plan_sockets"],
                _sync_run_task_plan_sockets=ns["_sync_run_task_plan_sockets"],
                _sync_task_step_sockets=ns["_sync_task_step_sockets"],
                iface_=ns["iface_"],
            ),
        ),
    )


def build_nodes_module_exports(namespace):
    ns = namespace
    display_helper_exports = build_display_helper_exports(
        build_display_helpers=ns["build_display_helpers"],
        PROPERTY_SOURCE_CURRENT=ns["PROPERTY_SOURCE_CURRENT"],
        PROPERTY_SOURCE_VALUE=ns["PROPERTY_SOURCE_VALUE"],
    )
    socket_rebuild_exports = build_socket_rebuild_exports(
        build_socket_rebuild_helpers=ns["build_socket_rebuild_helpers"],
        _capture_dynamic_socket_state=lambda node, direction, include_default_values=True: ns[
            "_capture_dynamic_socket_state"
        ](
            node,
            direction,
            include_default_values=include_default_values,
        ),
        _restore_dynamic_socket_state=lambda node, direction, state, socket_specs, restore_default_values=True: ns[
            "_restore_dynamic_socket_state"
        ](
            node,
            direction,
            state,
            socket_specs,
            restore_default_values=restore_default_values,
        ),
    )
    support_helper_exports = build_support_helper_exports(
        build_group_node_helpers=ns["build_group_node_helpers"],
        build_task_node_helpers=ns["build_task_node_helpers"],
        build_dynamic_socket_helpers=ns["build_dynamic_socket_helpers"],
        build_property_data_helpers=ns["build_property_data_helpers"],
        AFNodeTree=ns["AFNodeTree"],
        GROUP_NODE_INPUT_IDENTIFIERS_KEY=ns["GROUP_NODE_INPUT_IDENTIFIERS_KEY"],
        GROUP_NODE_OUTPUT_IDENTIFIERS_KEY=ns["GROUP_NODE_OUTPUT_IDENTIFIERS_KEY"],
        GROUP_SUPPORTED_SOCKET_IDNAMES=ns["GROUP_SUPPORTED_SOCKET_IDNAMES"],
        NUMERIC_COMPATIBLE_SOCKET_IDNAMES=ns["NUMERIC_COMPATIBLE_SOCKET_IDNAMES"],
        PHYSICS_BAKE_TASK_INPUT_PREFIX=ns["PHYSICS_BAKE_TASK_INPUT_PREFIX"],
        PHYSICS_BAKE_TASK_SOCKET_IDNAME=ns["PHYSICS_BAKE_TASK_SOCKET_IDNAME"],
        PHYSICS_BAKE_TASK_VIRTUAL_LABEL=ns["PHYSICS_BAKE_TASK_VIRTUAL_LABEL"],
        RUN_TASK_PLAN_INPUT_PREFIX=ns["RUN_TASK_PLAN_INPUT_PREFIX"],
        RUN_TASK_PLAN_VIRTUAL_LABEL=ns["RUN_TASK_PLAN_VIRTUAL_LABEL"],
        TASK_STEP_INPUT_SPECS=ns["TASK_STEP_INPUT_SPECS"],
        TASK_STEP_OUTPUT_SPECS=ns["TASK_STEP_OUTPUT_SPECS"],
        iface_=ns["iface_"],
        CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE=ns["CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE"],
        CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE=ns["CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE"],
        INDEX_SWITCH_SOCKET_IDNAME_BY_MODE=ns["INDEX_SWITCH_SOCKET_IDNAME_BY_MODE"],
        INDEX_SWITCH_VIRTUAL_LABEL=ns["INDEX_SWITCH_VIRTUAL_LABEL"],
        PROPERTY_ASSIGNMENT_INPUT_PREFIX=ns["PROPERTY_ASSIGNMENT_INPUT_PREFIX"],
        PROPERTY_ASSIGNMENT_VIRTUAL_LABEL=ns["PROPERTY_ASSIGNMENT_VIRTUAL_LABEL"],
        SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE=ns["SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE"],
        SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE=ns["SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE"],
        SWITCH_SOCKET_IDNAME_BY_MODE=ns["SWITCH_SOCKET_IDNAME_BY_MODE"],
        CUSTOM_MENU_SOCKET_IDNAMES=ns["CUSTOM_MENU_SOCKET_IDNAMES"],
        PROPERTY_DATA_FIELD_SPECS=ns["PROPERTY_DATA_FIELD_SPECS"],
        PROPERTY_SOURCE_VALUE=ns["PROPERTY_SOURCE_VALUE"],
        _draw_compact_property_source=display_helper_exports["_draw_compact_property_source"],
        _hide_default_auxiliary_outputs=display_helper_exports["_hide_default_auxiliary_outputs"],
        _rebuild_sockets=socket_rebuild_exports["_rebuild_sockets"],
    )
    return {
        "display_helper_exports": display_helper_exports,
        "socket_rebuild_exports": socket_rebuild_exports,
        "support_helper_exports": support_helper_exports,
        "registered_class_names": build_registered_class_names(
            flow_names=ns["FLOW_NODE_CLASS_NAMES"],
            input_names=ns["INPUT_NODE_CLASS_NAMES"],
            task_names=ns["TASK_NODE_CLASS_NAMES"],
            object_names=ns["OBJECT_NODE_CLASS_NAMES"],
            property_package_names=ns["PROPERTY_PACKAGE_NODE_CLASS_NAMES"],
            math_names=ns["MATH_NODE_CLASS_NAMES"],
            preview_names=ns["PREVIEW_NODE_CLASS_NAMES"],
            context_geometry_names=ns["CONTEXT_GEOMETRY_NODE_CLASS_NAMES"],
            property_data_names=ns["PROPERTY_DATA_NODE_CLASS_NAMES"],
        ),
    }


def build_registered_classes(module_globals, registered_class_names):
    return tuple(module_globals[name] for name in registered_class_names)


def initialize_nodes_module(
    module_globals,
    *,
    editor_context_module,
    pair_helpers_module,
    AFNodeTree,
):
    bind_module_exports(module_globals, editor_context_module, EDITOR_CONTEXT_EXPORTS)
    bind_module_exports(module_globals, pair_helpers_module, PAIR_HELPER_EXPORTS)

    node_module_exports = build_nodes_module_exports(module_globals)
    bind_nodes_module_exports(module_globals, node_module_exports)
    module_globals["NODE_MODULE_EXPORTS"] = node_module_exports

    module_globals["AFBaseNode"] = build_base_node_class(AFNodeTree=AFNodeTree)

    for builder, exports, kwargs in build_node_build_exports(module_globals):
        bind_built_exports(module_globals, builder, exports, **kwargs)

    classes = build_registered_classes(module_globals, node_module_exports["registered_class_names"])
    module_globals["CLASSES"] = classes
    return {
        "NODE_MODULE_EXPORTS": node_module_exports,
        "AFBaseNode": module_globals["AFBaseNode"],
        "CLASSES": classes,
    }


def register_classes(classes, safe_register_class, after_register=None):
    for cls in classes:
        safe_register_class(cls)
    if after_register is not None:
        after_register()


def unregister_classes(classes, safe_unregister_class):
    for cls in reversed(classes):
        safe_unregister_class(cls)


__all__ = [
    "DYNAMIC_SOCKET_HELPER_EXPORTS",
    "DISPLAY_HELPER_EXPORTS",
    "EDITOR_CONTEXT_EXPORTS",
    "FLOW_NODE_EXPORTS",
    "GROUP_NODE_EXPORTS",
    "PAIR_HELPER_EXPORTS",
    "CONTEXT_GEOMETRY_NODE_CLASS_NAMES",
    "CONTEXT_GEOMETRY_NODE_EXPORTS",
    "INPUT_NODE_EXPORTS",
    "FLOW_NODE_CLASS_NAMES",
    "INPUT_NODE_CLASS_NAMES",
    "MATH_NODE_EXPORTS",
    "MATH_NODE_CLASS_NAMES",
    "OBJECT_NODE_EXPORTS",
    "OBJECT_NODE_CLASS_NAMES",
    "PREVIEW_NODE_CLASS_NAMES",
    "PREVIEW_NODE_EXPORTS",
    "PROPERTY_DATA_HELPER_EXPORTS",
    "PROPERTY_DATA_NODE_CLASS_NAMES",
    "PROPERTY_DATA_NODE_EXPORTS",
    "PROPERTY_PACKAGE_NODE_CLASS_NAMES",
    "PROPERTY_PACKAGE_NODE_EXPORTS",
    "SOCKET_REBUILD_EXPORTS",
    "TASK_NODE_EXPORTS",
    "TASK_NODE_HELPER_EXPORTS",
    "TASK_NODE_CLASS_NAMES",
    "bind_exports",
    "bind_built_exports",
    "bind_module_exports",
    "bind_nodes_module_exports",
    "build_registered_class_names",
    "build_node_build_exports",
    "build_nodes_module_exports",
    "build_registered_classes",
    "build_base_node_class",
    "initialize_nodes_module",
    "build_display_helper_exports",
    "build_socket_rebuild_exports",
    "build_support_helper_exports",
    "bind_support_helper_exports",
    "register_classes",
    "unregister_classes",
    "preview_context_for_builder",
]
