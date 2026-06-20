from ..runtime_core.constants import (
    FlowExecutionError,
    OBJECT_PERSISTENT_UUID_PROP,
    PHYSICS_BATCH_SUPPORTED_MODIFIER_TYPES,
    PHYSICS_SUPPORTED_MODIFIER_TYPES,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    STORED_PROPERTY_PACKAGE_PROP_PREFIX,
    TASK_KIND_PROPERTY_PACKAGE_BAKE,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_KIND_RENDER,
)
from ..runtime_core.module_loading import bind_partial_export
from ..runtime_flow.helpers import _find_single_from_input_socket, _first_output_node
from ..runtime_property.api import (
    _iter_property_package_entries,
    _object_reference_identity,
)
from ..runtime_refs.objects import (
    _dedup_obj_items as _dedup_obj_items_impl,
    _find_object_by_item as _find_object_by_item_impl,
    _find_object_by_name as _find_object_by_name_impl,
    _normalize_object_item_reference as _normalize_object_item_reference_impl,
    _obj_item as _obj_item_impl,
    _object_list_from_task_ref as _object_list_from_task_ref_impl,
    _stored_property_package_key_for_node as _stored_property_package_key_for_node_impl,
    _stored_property_package_key_for_tree_node as _stored_property_package_key_for_tree_node_impl,
)
from ..runtime_persistence.serialization import (
    _copy_runtime_state_value,
    _copy_task_ref_payload,
    _ensure_object_persistent_uuid as _ensure_object_persistent_uuid_impl,
)
from ..runtime_task_target import (
    _resolve_bake_entry,
    _resolve_bake_target as _resolve_bake_target_impl,
    _resolve_physics_batch_task_target as _resolve_physics_batch_task_target_impl,
    _resolve_physics_task_target as _resolve_physics_task_target_impl,
    _split_bake_task_path as _split_bake_task_path_impl,
    _split_physics_task_path as _split_physics_task_path_impl,
)
from .helpers import (
    _build_property_package_bake_task_ref_fallback as _build_property_package_bake_task_ref_fallback_impl,
    _collect_predicted_items_from_property_package as _collect_predicted_items_from_property_package_impl,
    _frame_range_from_task_ref as _frame_range_from_task_ref_impl,
    _make_property_package_bake_task_ref_payload as _make_property_package_bake_task_ref_payload_impl,
    _manual_predict_property_package_bake_targets as _manual_predict_property_package_bake_targets_impl,
    _precheck_failure_message as _precheck_failure_message_impl,
    _predict_property_package_bake_targets_resilient as _predict_property_package_bake_targets_resilient_impl,
    _rehydrate_property_package_bake_predicted_items as _rehydrate_property_package_bake_predicted_items_impl,
    _require_payload_object_ref as _require_payload_object_ref_impl,
)
from .refs import (
    _invalid_task_ref_issue as _invalid_task_ref_issue_impl,
    _raise_if_invalid_task_ref as _raise_if_invalid_task_ref_impl,
    _rehydrate_task_ref_object_references as _rehydrate_task_ref_object_references_impl,
    _validate_task_ref_object_targets as _validate_task_ref_object_targets_impl,
)


def _make_issue(code, message, node_name, level="ERROR"):
    return {
        "code": code,
        "message": message,
        "node_name": node_name,
        "level": level,
    }


_ensure_object_persistent_uuid = bind_partial_export(
    _ensure_object_persistent_uuid_impl,
    object_persistent_uuid_prop=OBJECT_PERSISTENT_UUID_PROP,
)


_obj_item = bind_partial_export(
    _obj_item_impl,
    ensure_object_persistent_uuid=_ensure_object_persistent_uuid,
)


_stored_property_package_key_for_tree_node = bind_partial_export(
    _stored_property_package_key_for_tree_node_impl,
    stored_property_package_prop_prefix=STORED_PROPERTY_PACKAGE_PROP_PREFIX,
)


_stored_property_package_key_for_node = bind_partial_export(
    _stored_property_package_key_for_node_impl,
    stored_property_package_prop_prefix=STORED_PROPERTY_PACKAGE_PROP_PREFIX,
)


_normalize_object_item_reference = bind_partial_export(
    _normalize_object_item_reference_impl,
    object_reference_identity=_object_reference_identity,
)


_dedup_obj_items = bind_partial_export(
    _dedup_obj_items_impl,
    normalize_object_item_reference=_normalize_object_item_reference,
)


_find_object_by_item = bind_partial_export(
    _find_object_by_item_impl,
    object_persistent_uuid_prop=OBJECT_PERSISTENT_UUID_PROP,
)


_find_object_by_name = _find_object_by_name_impl


_object_list_from_task_ref = bind_partial_export(
    _object_list_from_task_ref_impl,
    rehydrate_task_ref_object_references=lambda task_ref, object_resolver=None, scene=None: _rehydrate_task_ref_object_references(
        task_ref,
        object_resolver=object_resolver,
        scene=scene,
    ),
    rehydrate_property_package_bake_predicted_items=lambda task_ref, scene: _rehydrate_property_package_bake_predicted_items(
        task_ref,
        scene,
    ),
    copy_runtime_state_value=_copy_runtime_state_value,
    dedup_obj_items=_dedup_obj_items,
    obj_item=_obj_item,
    ensure_object_persistent_uuid=_ensure_object_persistent_uuid,
    task_kind_geometry=TASK_KIND_GEOMETRY,
    task_kind_render=TASK_KIND_RENDER,
    task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
    task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
)


_frame_range_from_task_ref = bind_partial_export(
    _frame_range_from_task_ref_impl,
    task_kind_render=TASK_KIND_RENDER,
    task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
    task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
    task_kind_geometry=TASK_KIND_GEOMETRY,
)


_make_property_package_bake_task_ref_payload = bind_partial_export(
    _make_property_package_bake_task_ref_payload_impl,
    task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
    dedup_obj_items=_dedup_obj_items,
)


_build_property_package_bake_task_ref_fallback = bind_partial_export(
    _build_property_package_bake_task_ref_fallback_impl,
    flow_execution_error_cls=FlowExecutionError,
    make_property_package_bake_task_ref_payload=_make_property_package_bake_task_ref_payload,
)


_collect_predicted_items_from_property_package = bind_partial_export(
    _collect_predicted_items_from_property_package_impl,
    iter_property_package_entries=_iter_property_package_entries,
    property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
    property_package_scope_modifier=PROPERTY_PACKAGE_SCOPE_MODIFIER,
    property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
)


def _manual_predict_property_package_bake_targets(
    start_tree,
    start_node_name,
    scene,
    owner_node_name,
):
    from ..runtime_runner.core import FlowRunner

    return _manual_predict_property_package_bake_targets_impl(
        start_tree,
        start_node_name,
        scene,
        owner_node_name,
        flow_runner_cls=FlowRunner,
        find_single_from_input_socket=_find_single_from_input_socket,
        first_output_node=_first_output_node,
        collect_predicted_items_from_property_package=_collect_predicted_items_from_property_package,
        dedup_obj_items=_dedup_obj_items,
    )


def _predict_property_package_bake_targets_resilient(
    start_tree,
    start_node_name,
    scene,
    owner_node_name,
):
    from ..runtime_runner.core import FlowRunner

    return _predict_property_package_bake_targets_resilient_impl(
        start_tree,
        start_node_name,
        scene,
        owner_node_name,
        flow_runner_cls=FlowRunner,
        manual_predict_property_package_bake_targets=_manual_predict_property_package_bake_targets,
    )


_rehydrate_property_package_bake_predicted_items = bind_partial_export(
    _rehydrate_property_package_bake_predicted_items_impl,
    predict_property_package_bake_targets_resilient=_predict_property_package_bake_targets_resilient,
)


_rehydrate_task_ref_object_references = bind_partial_export(
    _rehydrate_task_ref_object_references_impl,
    task_kind_geometry=TASK_KIND_GEOMETRY,
    task_kind_physics=TASK_KIND_PHYSICS,
    task_kind_render=TASK_KIND_RENDER,
    task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
    task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
    copy_task_ref_payload=_copy_task_ref_payload,
    copy_runtime_state_value=_copy_runtime_state_value,
    ensure_object_persistent_uuid=_ensure_object_persistent_uuid,
    find_object_by_item=_find_object_by_item,
    dedup_obj_items=_dedup_obj_items,
)


_validate_task_ref_object_targets = bind_partial_export(
    _validate_task_ref_object_targets_impl,
    flow_execution_error_cls=FlowExecutionError,
    task_kind_geometry=TASK_KIND_GEOMETRY,
    task_kind_physics=TASK_KIND_PHYSICS,
    task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
)


_split_bake_task_path = bind_partial_export(
    _split_bake_task_path_impl,
    flow_execution_error_cls=FlowExecutionError,
)


_resolve_bake_target = bind_partial_export(
    _resolve_bake_target_impl,
    flow_execution_error_cls=FlowExecutionError,
    split_bake_task_path=_split_bake_task_path,
    resolve_bake_entry=_resolve_bake_entry,
)


_split_physics_task_path = bind_partial_export(
    _split_physics_task_path_impl,
    flow_execution_error_cls=FlowExecutionError,
)


_resolve_physics_task_target = bind_partial_export(
    _resolve_physics_task_target_impl,
    flow_execution_error_cls=FlowExecutionError,
    split_physics_task_path=_split_physics_task_path,
    physics_supported_modifier_types=PHYSICS_SUPPORTED_MODIFIER_TYPES,
)


_resolve_physics_batch_task_target = bind_partial_export(
    _resolve_physics_batch_task_target_impl,
    flow_execution_error_cls=FlowExecutionError,
    resolve_physics_task_target=_resolve_physics_task_target,
    physics_batch_supported_modifier_types=PHYSICS_BATCH_SUPPORTED_MODIFIER_TYPES,
)


_require_payload_object_ref = bind_partial_export(
    _require_payload_object_ref_impl,
    flow_execution_error_cls=FlowExecutionError,
)


_precheck_failure_message = _precheck_failure_message_impl


_invalid_task_ref_issue = _invalid_task_ref_issue_impl


_raise_if_invalid_task_ref = bind_partial_export(
    _raise_if_invalid_task_ref_impl,
    flow_execution_error_cls=FlowExecutionError,
)


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
