from ..runtime_core.constants import (
    AUTO_FLOW_BAKE_ACTION_NAME_PREFIX,
    FlowExecutionError,
    OBJECT_PERSISTENT_UUID_PROP,
    PHYSICS_BATCH_SUPPORTED_MODIFIER_TYPES,
    PHYSICS_SUPPORTED_MODIFIER_TYPES,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    STORED_PROPERTY_PACKAGE_PROP_PREFIX,
    TASK_KIND_AUTO_FLOW_BAKE,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_KIND_RENDER,
)
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
from ..runtime_state.cache import _auto_flow_bake_action_name_from_task_ref
from ..runtime_task_target import (
    _resolve_bake_entry,
    _resolve_bake_target as _resolve_bake_target_impl,
    _resolve_physics_batch_task_target as _resolve_physics_batch_task_target_impl,
    _resolve_physics_task_target as _resolve_physics_task_target_impl,
    _split_bake_task_path as _split_bake_task_path_impl,
    _split_physics_task_path as _split_physics_task_path_impl,
)
from .helpers import (
    _build_auto_flow_bake_task_ref_fallback as _build_auto_flow_bake_task_ref_fallback_impl,
    _collect_predicted_items_from_property_package as _collect_predicted_items_from_property_package_impl,
    _frame_range_from_task_ref as _frame_range_from_task_ref_impl,
    _make_auto_flow_bake_task_ref_payload as _make_auto_flow_bake_task_ref_payload_impl,
    _manual_predict_auto_flow_bake_targets as _manual_predict_auto_flow_bake_targets_impl,
    _precheck_failure_message as _precheck_failure_message_impl,
    _predict_auto_flow_bake_targets_resilient as _predict_auto_flow_bake_targets_resilient_impl,
    _rehydrate_auto_flow_bake_predicted_items as _rehydrate_auto_flow_bake_predicted_items_impl,
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


def _ensure_object_persistent_uuid(obj):
    return _ensure_object_persistent_uuid_impl(obj, OBJECT_PERSISTENT_UUID_PROP)


def _obj_item(obj):
    return _obj_item_impl(obj, _ensure_object_persistent_uuid)


def _stored_property_package_key_for_tree_node(tree_name, node_name):
    return _stored_property_package_key_for_tree_node_impl(
        tree_name,
        node_name,
        STORED_PROPERTY_PACKAGE_PROP_PREFIX,
    )


def _stored_property_package_key_for_node(node):
    return _stored_property_package_key_for_node_impl(
        node,
        STORED_PROPERTY_PACKAGE_PROP_PREFIX,
    )


def _normalize_object_item_reference(item, object_resolver=None):
    return _normalize_object_item_reference_impl(
        item,
        object_resolver=object_resolver,
        object_reference_identity=_object_reference_identity,
    )


def _dedup_obj_items(items, sort_mode, object_resolver=None):
    return _dedup_obj_items_impl(
        items,
        sort_mode,
        object_resolver=object_resolver,
        normalize_object_item_reference=_normalize_object_item_reference,
    )


def _find_object_by_item(item):
    return _find_object_by_item_impl(item, OBJECT_PERSISTENT_UUID_PROP)


def _find_object_by_name(name):
    return _find_object_by_name_impl(name)


def _object_list_from_task_ref(
    task_ref,
    sort_mode="NAME_ASC",
    scene=None,
):
    return _object_list_from_task_ref_impl(
        task_ref,
        sort_mode=sort_mode,
        scene=scene,
        rehydrate_task_ref_object_references=_rehydrate_task_ref_object_references,
        rehydrate_auto_flow_bake_predicted_items=_rehydrate_auto_flow_bake_predicted_items,
        copy_runtime_state_value=_copy_runtime_state_value,
        dedup_obj_items=_dedup_obj_items,
        obj_item=_obj_item,
        ensure_object_persistent_uuid=_ensure_object_persistent_uuid,
        task_kind_geometry=TASK_KIND_GEOMETRY,
        task_kind_render=TASK_KIND_RENDER,
        task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
        task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
    )


def _frame_range_from_task_ref(task_ref, scene):
    return _frame_range_from_task_ref_impl(
        task_ref,
        scene,
        task_kind_render=TASK_KIND_RENDER,
        task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
        task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        task_kind_geometry=TASK_KIND_GEOMETRY,
    )


def _make_auto_flow_bake_task_ref_payload(
    node,
    owner_tree_name,
    start_tree_name,
    start_node_name,
    frame_start,
    frame_end,
    bake_asset_id,
    action_name,
    predicted_targets,
    preview_degraded=False,
):
    return _make_auto_flow_bake_task_ref_payload_impl(
        node,
        owner_tree_name,
        start_tree_name,
        start_node_name,
        frame_start,
        frame_end,
        bake_asset_id,
        action_name,
        predicted_targets,
        preview_degraded=preview_degraded,
        task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
        dedup_obj_items=_dedup_obj_items,
    )


def _build_auto_flow_bake_task_ref_fallback(runner, node):
    return _build_auto_flow_bake_task_ref_fallback_impl(
        runner,
        node,
        flow_execution_error_cls=FlowExecutionError,
        predict_auto_flow_bake_targets_resilient=_predict_auto_flow_bake_targets_resilient,
        auto_flow_bake_action_name_from_task_ref=_auto_flow_bake_action_name_from_task_ref,
        auto_flow_bake_action_name_prefix=AUTO_FLOW_BAKE_ACTION_NAME_PREFIX,
        make_auto_flow_bake_task_ref_payload=_make_auto_flow_bake_task_ref_payload,
    )


def _collect_predicted_items_from_property_package(
    property_package,
    owner_node_name,
    predicted_by_id,
    predicted_component_paths,
):
    return _collect_predicted_items_from_property_package_impl(
        property_package,
        owner_node_name,
        predicted_by_id,
        predicted_component_paths,
        iter_property_package_entries=_iter_property_package_entries,
        property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
        property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
        property_package_scope_modifier=PROPERTY_PACKAGE_SCOPE_MODIFIER,
        property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
    )


def _manual_predict_auto_flow_bake_targets(
    start_tree,
    start_node_name,
    scene,
    owner_node_name,
):
    from ..runtime_runner.core import FlowRunner

    return _manual_predict_auto_flow_bake_targets_impl(
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


def _predict_auto_flow_bake_targets_resilient(
    start_tree,
    start_node_name,
    scene,
    owner_node_name,
):
    from ..runtime_runner.core import FlowRunner

    return _predict_auto_flow_bake_targets_resilient_impl(
        start_tree,
        start_node_name,
        scene,
        owner_node_name,
        flow_runner_cls=FlowRunner,
        manual_predict_auto_flow_bake_targets=_manual_predict_auto_flow_bake_targets,
    )


def _rehydrate_auto_flow_bake_predicted_items(task_ref, scene):
    return _rehydrate_auto_flow_bake_predicted_items_impl(
        task_ref,
        scene,
        predict_auto_flow_bake_targets_resilient=_predict_auto_flow_bake_targets_resilient,
    )


def _rehydrate_task_ref_object_references(
    task_ref,
    object_resolver=None,
    scene=None,
):
    return _rehydrate_task_ref_object_references_impl(
        task_ref,
        task_kind_geometry=TASK_KIND_GEOMETRY,
        task_kind_physics=TASK_KIND_PHYSICS,
        task_kind_render=TASK_KIND_RENDER,
        task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
        task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        copy_task_ref_payload=_copy_task_ref_payload,
        copy_runtime_state_value=_copy_runtime_state_value,
        ensure_object_persistent_uuid=_ensure_object_persistent_uuid,
        find_object_by_item=_find_object_by_item,
        dedup_obj_items=_dedup_obj_items,
        scene=scene,
        object_resolver=object_resolver,
    )


def _validate_task_ref_object_targets(task_ref, node_name):
    return _validate_task_ref_object_targets_impl(
        task_ref,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
        task_kind_geometry=TASK_KIND_GEOMETRY,
        task_kind_physics=TASK_KIND_PHYSICS,
        task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
    )


def _split_bake_task_path(task_path, node_name):
    return _split_bake_task_path_impl(
        task_path,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
    )


def _resolve_bake_target(task_path, node_name):
    return _resolve_bake_target_impl(
        task_path,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
        split_bake_task_path=_split_bake_task_path,
        resolve_bake_entry=_resolve_bake_entry,
    )


def _split_physics_task_path(task_path, node_name):
    return _split_physics_task_path_impl(
        task_path,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
    )


def _resolve_physics_task_target(task_path, node_name):
    return _resolve_physics_task_target_impl(
        task_path,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
        split_physics_task_path=_split_physics_task_path,
        physics_supported_modifier_types=PHYSICS_SUPPORTED_MODIFIER_TYPES,
    )


def _resolve_physics_batch_task_target(task_path, node_name):
    return _resolve_physics_batch_task_target_impl(
        task_path,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
        resolve_physics_task_target=_resolve_physics_task_target,
        physics_batch_supported_modifier_types=PHYSICS_BATCH_SUPPORTED_MODIFIER_TYPES,
    )


def _require_payload_object_ref(payload, node_name, object_name_key="object_name"):
    return _require_payload_object_ref_impl(
        payload,
        node_name,
        object_name_key=object_name_key,
        flow_execution_error_cls=FlowExecutionError,
    )


def _precheck_failure_message(issues):
    return _precheck_failure_message_impl(issues)


def _invalid_task_ref_issue(task_ref):
    return _invalid_task_ref_issue_impl(task_ref)


def _raise_if_invalid_task_ref(task_ref, fallback_node_name):
    return _raise_if_invalid_task_ref_impl(
        task_ref,
        fallback_node_name,
        flow_execution_error_cls=FlowExecutionError,
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
