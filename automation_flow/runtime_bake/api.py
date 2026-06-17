import json
import os
import re

import bpy

from ..runtime_core.constants import (
    BAKE_JOB_TYPE,
    FlowExecutionError,
    GN_PACKED_CACHE_STATE_PROP,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
)
from ..runtime_state.cache import (
    _capture_scene_frame_state,
    _operator_result_tokens,
    _restore_scene_frame_state,
    _tag_all_node_editor_redraw,
)
from ..runtime_task_ref import (
    _require_payload_object_ref,
    _resolve_bake_target,
    _resolve_physics_task_target,
)
from ..runtime_task_target import (
    _apply_geometry_bake_entry_settings as _apply_geometry_bake_entry_settings_impl,
    _apply_geometry_bake_settings_for_run as _apply_geometry_bake_settings_for_run_impl,
    _apply_temporary_geometry_bake_settings as _apply_temporary_geometry_bake_settings_impl,
    _call_operator_with_override as _call_operator_with_override_impl,
    _clear_geometry_bake_tracked_packed_cache_state as _clear_geometry_bake_tracked_packed_cache_state_impl,
    _capture_geometry_bake_entry_settings as _capture_geometry_bake_entry_settings_impl,
    _compose_bake_override as _compose_bake_override_impl,
    _ensure_background_geometry_task_supported as _ensure_background_geometry_task_supported_impl,
    _ensure_operator_finished as _ensure_operator_finished_impl,
    _find_geometry_bake_entry_for_task as _find_geometry_bake_entry_for_task_impl,
    _geometry_bake_cached_frame_from_filename as _geometry_bake_cached_frame_from_filename_impl,
    _geometry_bake_cached_frame_range_from_candidate_root as _geometry_bake_cached_frame_range_from_candidate_root_impl,
    _geometry_bake_cache_status_from_node as _geometry_bake_cache_status_from_node_impl,
    _geometry_bake_disk_cache_exists as _geometry_bake_disk_cache_exists_impl,
    _geometry_bake_disk_cache_frame_range as _geometry_bake_disk_cache_frame_range_impl,
    _geometry_bake_disk_cache_root_dir as _geometry_bake_disk_cache_root_dir_impl,
    _geometry_bake_entry_cached_frame_range as _geometry_bake_entry_cached_frame_range_impl,
    _geometry_bake_entry_has_cached_data as _geometry_bake_entry_has_cached_data_impl,
    _geometry_bake_has_existing_cache as _geometry_bake_has_existing_cache_impl,
    _geometry_bake_has_existing_cache_for_current_entry as _geometry_bake_has_existing_cache_for_current_entry_impl,
    _geometry_bake_keep_overridden_settings_on_success as _geometry_bake_keep_overridden_settings_on_success_impl,
    _get_geometry_bake_tracked_packed_cache_status as _get_geometry_bake_tracked_packed_cache_status_impl,
    _invoke_geometry_nodes_bake_task as _invoke_geometry_nodes_bake_task_impl,
    _invoke_physics_bake_all_task as _invoke_physics_bake_all_task_impl,
    _invoke_physics_bake_task as _invoke_physics_bake_task_impl,
    _invoke_render_task as _invoke_render_task_impl,
    _iter_geometry_bake_disk_cache_candidate_roots as _iter_geometry_bake_disk_cache_candidate_roots_impl,
    _physics_bake_all_has_pending_work as _physics_bake_all_has_pending_work_impl,
    _physics_bake_cache_status_from_node as _physics_bake_cache_status_from_node_impl,
    _physics_task_has_existing_cache as _physics_task_has_existing_cache_impl,
    _point_cache_frame_range as _point_cache_frame_range_impl,
    _point_cache_has_existing_cache as _point_cache_has_existing_cache_impl,
    _read_geometry_bake_tracked_packed_cache_state as _read_geometry_bake_tracked_packed_cache_state_impl,
    _refresh_geometry_bake_cache_state_after_completion as _refresh_geometry_bake_cache_state_after_completion_impl,
    _resolve_geometry_task_effective_bake_target as _resolve_geometry_task_effective_bake_target_impl,
    _resolve_geometry_task_source_node as _resolve_geometry_task_source_node_impl,
    _restore_geometry_bake_entry_settings as _restore_geometry_bake_entry_settings_impl,
    _restore_waiting_bake_cleanup as _restore_waiting_bake_cleanup_impl,
    _schedule_geometry_bake_cache_refresh as _schedule_geometry_bake_cache_refresh_impl,
    _start_geometry_nodes_bake_task as _start_geometry_nodes_bake_task_impl,
    _start_named_operator as _start_named_operator_impl,
    _start_physics_bake_all_task as _start_physics_bake_all_task_impl,
    _start_physics_bake_task as _start_physics_bake_task_impl,
    _task_operator_result_is_skipped as _task_operator_result_is_skipped_impl,
    _write_geometry_bake_tracked_packed_cache_state as _write_geometry_bake_tracked_packed_cache_state_impl,
)


def _ensure_operator_finished(result, error_code, operator_label, node_name):
    return _ensure_operator_finished_impl(
        result,
        error_code,
        operator_label,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
    )


def _find_geometry_bake_entry_for_task(task_ref, error_context):
    return _find_geometry_bake_entry_for_task_impl(
        task_ref,
        error_context,
        flow_execution_error_cls=FlowExecutionError,
        require_payload_object_ref=_require_payload_object_ref,
    )


def _resolve_geometry_task_effective_bake_target(task_ref):
    return _resolve_geometry_task_effective_bake_target_impl(
        task_ref,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
    )


def _ensure_background_geometry_task_supported(task_ref, node_name):
    return _ensure_background_geometry_task_supported_impl(
        task_ref,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
        resolve_geometry_task_effective_bake_target=_resolve_geometry_task_effective_bake_target,
    )


def _capture_geometry_bake_entry_settings(bake_entry):
    return _capture_geometry_bake_entry_settings_impl(bake_entry)


def _apply_geometry_bake_entry_settings(bake_entry, task_ref):
    return _apply_geometry_bake_entry_settings_impl(bake_entry, task_ref)


def _restore_geometry_bake_entry_settings(bake_entry, state):
    return _restore_geometry_bake_entry_settings_impl(bake_entry, state)


def _resolve_geometry_task_source_node(task_ref):
    return _resolve_geometry_task_source_node_impl(task_ref)


def _read_geometry_bake_tracked_packed_cache_state(node):
    return _read_geometry_bake_tracked_packed_cache_state_impl(
        node,
        gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
        json_module=json,
    )


def _write_geometry_bake_tracked_packed_cache_state(task_ref, frame_range=None):
    return _write_geometry_bake_tracked_packed_cache_state_impl(
        task_ref,
        frame_range=frame_range,
        resolve_geometry_task_source_node=_resolve_geometry_task_source_node,
        gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
        json_module=json,
    )


def _clear_geometry_bake_tracked_packed_cache_state(task_ref):
    return _clear_geometry_bake_tracked_packed_cache_state_impl(
        task_ref,
        resolve_geometry_task_source_node=_resolve_geometry_task_source_node,
        gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
    )


def _get_geometry_bake_tracked_packed_cache_status(task_ref):
    return _get_geometry_bake_tracked_packed_cache_status_impl(
        task_ref,
        resolve_geometry_task_source_node=_resolve_geometry_task_source_node,
        read_geometry_bake_tracked_packed_cache_state=_read_geometry_bake_tracked_packed_cache_state,
    )


def _geometry_bake_entry_has_cached_data(bake_entry):
    return _geometry_bake_entry_has_cached_data_impl(bake_entry)


def _geometry_bake_disk_cache_root_dir(task_ref, bake_entry=None):
    return _geometry_bake_disk_cache_root_dir_impl(
        task_ref,
        bake_entry=bake_entry,
        bpy_module=bpy,
        require_payload_object_ref=_require_payload_object_ref,
    )


def _iter_geometry_bake_disk_cache_candidate_roots(task_ref, bake_entry=None):
    return _iter_geometry_bake_disk_cache_candidate_roots_impl(
        task_ref,
        bake_entry=bake_entry,
        geometry_bake_disk_cache_root_dir=_geometry_bake_disk_cache_root_dir,
    )


def _geometry_bake_cached_frame_from_filename(filename):
    return _geometry_bake_cached_frame_from_filename_impl(filename)


def _geometry_bake_cached_frame_range_from_candidate_root(candidate_root):
    return _geometry_bake_cached_frame_range_from_candidate_root_impl(candidate_root)


def _geometry_bake_disk_cache_frame_range(task_ref, bake_entry=None):
    return _geometry_bake_disk_cache_frame_range_impl(task_ref, bake_entry=bake_entry)


def _geometry_bake_entry_cached_frame_range(bake_entry):
    return _geometry_bake_entry_cached_frame_range_impl(bake_entry)


def _geometry_bake_cache_status_from_node(node):
    from ..runtime_runner.core import FlowRunner

    return _geometry_bake_cache_status_from_node_impl(
        node,
        bpy_module=bpy,
        flow_execution_error_cls=FlowExecutionError,
        resolve_bake_target=_resolve_bake_target,
        build_geometry_task_ref=lambda runner_tree, scene, bake_node: FlowRunner(runner_tree, scene)._build_geometry_task_ref(bake_node),
        geometry_bake_disk_cache_frame_range=_geometry_bake_disk_cache_frame_range,
        geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
        geometry_bake_entry_cached_frame_range=_geometry_bake_entry_cached_frame_range,
        get_geometry_bake_tracked_packed_cache_status=_get_geometry_bake_tracked_packed_cache_status,
        geometry_bake_disk_cache_exists=_geometry_bake_disk_cache_exists,
    )


def _refresh_geometry_bake_cache_state_after_completion(task_ref, scene=None):
    return _refresh_geometry_bake_cache_state_after_completion_impl(
        task_ref,
        scene=scene if scene is not None else getattr(bpy.context, "scene", None),
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
        geometry_bake_entry_cached_frame_range=_geometry_bake_entry_cached_frame_range,
        resolve_geometry_task_effective_bake_target=_resolve_geometry_task_effective_bake_target,
        tag_all_node_editor_redraw=_tag_all_node_editor_redraw,
    )


def _schedule_geometry_bake_cache_refresh(task_ref, scene=None, retries=24, interval=0.12):
    return _schedule_geometry_bake_cache_refresh_impl(
        task_ref,
        scene=scene,
        retries=retries,
        interval=interval,
        refresh_geometry_bake_cache_state_after_completion=_refresh_geometry_bake_cache_state_after_completion,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
        geometry_bake_disk_cache_exists=_geometry_bake_disk_cache_exists,
        tag_all_node_editor_redraw=_tag_all_node_editor_redraw,
    )


def _geometry_bake_disk_cache_exists(task_ref, bake_entry=None):
    return _geometry_bake_disk_cache_exists_impl(
        task_ref,
        bake_entry=bake_entry,
        geometry_bake_disk_cache_candidate_roots=_iter_geometry_bake_disk_cache_candidate_roots,
    )


def _geometry_bake_has_existing_cache(task_ref, scene, bake_entry):
    return _geometry_bake_has_existing_cache_impl(
        task_ref,
        scene,
        bake_entry,
        geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
        get_geometry_bake_tracked_packed_cache_status=_get_geometry_bake_tracked_packed_cache_status,
        geometry_bake_disk_cache_exists=_geometry_bake_disk_cache_exists,
    )


def _geometry_bake_has_existing_cache_for_current_entry(task_ref, scene, bake_entry):
    return _geometry_bake_has_existing_cache_for_current_entry_impl(
        task_ref,
        scene,
        bake_entry,
        geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
        geometry_bake_disk_cache_exists=_geometry_bake_disk_cache_exists,
    )


def _point_cache_has_existing_cache(point_cache):
    return _point_cache_has_existing_cache_impl(
        point_cache,
        bpy_module=bpy,
        os_module=os,
        re_module=re,
    )


def _point_cache_frame_range(point_cache):
    return _point_cache_frame_range_impl(
        point_cache,
        point_cache_has_existing_cache=_point_cache_has_existing_cache,
    )


def _physics_bake_cache_status_from_node(node):
    return _physics_bake_cache_status_from_node_impl(
        node,
        flow_execution_error_cls=FlowExecutionError,
        resolve_physics_task_target=_resolve_physics_task_target,
        point_cache_frame_range=_point_cache_frame_range,
    )


def _physics_task_has_existing_cache(task_ref):
    return _physics_task_has_existing_cache_impl(
        task_ref,
        point_cache_has_existing_cache=_point_cache_has_existing_cache,
    )


def _physics_bake_all_has_pending_work(task_ref):
    return _physics_bake_all_has_pending_work_impl(
        task_ref,
        physics_task_has_existing_cache=_physics_task_has_existing_cache,
    )


def _task_operator_result_is_skipped(result):
    return _task_operator_result_is_skipped_impl(result)


def _apply_temporary_geometry_bake_settings(task_ref):
    return _apply_temporary_geometry_bake_settings_impl(
        task_ref,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        capture_geometry_bake_entry_settings=_capture_geometry_bake_entry_settings,
        apply_geometry_bake_entry_settings=_apply_geometry_bake_entry_settings,
    )


def _apply_geometry_bake_settings_for_run(task_ref):
    return _apply_geometry_bake_settings_for_run_impl(
        task_ref,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        apply_geometry_bake_entry_settings=_apply_geometry_bake_entry_settings,
    )


def _geometry_bake_keep_overridden_settings_on_success(task_ref):
    return _geometry_bake_keep_overridden_settings_on_success_impl(task_ref)


def _compose_bake_override(base_override, ui_context=None):
    return _compose_bake_override_impl(base_override, ui_context=ui_context)


def _call_operator_with_override(operator, override, payload=None, invoke_async=False):
    return _call_operator_with_override_impl(
        operator,
        override,
        payload=payload,
        invoke_async=invoke_async,
        operator_result_tokens=_operator_result_tokens,
    )


def _start_named_operator(operator_paths, override, payload, source_node, invoke_async=False):
    return _start_named_operator_impl(
        operator_paths,
        override,
        payload,
        source_node,
        invoke_async=invoke_async,
        flow_execution_error_cls=FlowExecutionError,
        call_operator_with_override=_call_operator_with_override,
    )


def _restore_waiting_bake_cleanup(wait_state, bake_completed):
    return _restore_waiting_bake_cleanup_impl(
        wait_state,
        bake_completed,
        task_kind_geometry=TASK_KIND_GEOMETRY,
        task_kind_physics=TASK_KIND_PHYSICS,
        task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        restore_geometry_bake_entry_settings=_restore_geometry_bake_entry_settings,
        restore_scene_frame_state=_restore_scene_frame_state,
    )


def _start_geometry_nodes_bake_task(task_ref, scene, ui_context=None):
    return _start_geometry_nodes_bake_task_impl(
        task_ref,
        scene,
        ui_context=ui_context,
        bpy_module=bpy,
        require_payload_object_ref=_require_payload_object_ref,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        compose_bake_override=_compose_bake_override,
        capture_scene_frame_state=_capture_scene_frame_state,
        geometry_bake_has_existing_cache_for_current_entry=_geometry_bake_has_existing_cache_for_current_entry,
        geometry_bake_has_existing_cache=_geometry_bake_has_existing_cache,
        apply_temporary_geometry_bake_settings=_apply_temporary_geometry_bake_settings,
        clear_geometry_bake_tracked_packed_cache_state=_clear_geometry_bake_tracked_packed_cache_state,
        call_operator_with_override=_call_operator_with_override,
        start_named_operator=_start_named_operator,
        restore_waiting_bake_cleanup=_restore_waiting_bake_cleanup,
        bake_job_type=BAKE_JOB_TYPE,
        task_kind_geometry=TASK_KIND_GEOMETRY,
    )


def _start_physics_bake_task(task_ref, scene, ui_context=None):
    return _start_physics_bake_task_impl(
        task_ref,
        scene,
        ui_context=ui_context,
        bpy_module=bpy,
        flow_execution_error_cls=FlowExecutionError,
        require_payload_object_ref=_require_payload_object_ref,
        capture_scene_frame_state=_capture_scene_frame_state,
        physics_task_has_existing_cache=_physics_task_has_existing_cache,
        compose_bake_override=_compose_bake_override,
        start_named_operator=_start_named_operator,
        restore_waiting_bake_cleanup=_restore_waiting_bake_cleanup,
        bake_job_type=BAKE_JOB_TYPE,
        task_kind_physics=TASK_KIND_PHYSICS,
    )


def _start_physics_bake_all_task(task_ref, scene, ui_context=None):
    return _start_physics_bake_all_task_impl(
        task_ref,
        scene,
        ui_context=ui_context,
        bpy_module=bpy,
        flow_execution_error_cls=FlowExecutionError,
        require_payload_object_ref=_require_payload_object_ref,
        capture_scene_frame_state=_capture_scene_frame_state,
        physics_bake_all_has_pending_work=_physics_bake_all_has_pending_work,
        compose_bake_override=_compose_bake_override,
        start_named_operator=_start_named_operator,
        restore_waiting_bake_cleanup=_restore_waiting_bake_cleanup,
        bake_job_type=BAKE_JOB_TYPE,
        task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
    )


def _invoke_geometry_nodes_bake_task(task_ref, scene):
    return _invoke_geometry_nodes_bake_task_impl(
        task_ref,
        scene,
        bpy_module=bpy,
        require_payload_object_ref=_require_payload_object_ref,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        capture_scene_frame_state=_capture_scene_frame_state,
        geometry_bake_has_existing_cache_for_current_entry=_geometry_bake_has_existing_cache_for_current_entry,
        geometry_bake_has_existing_cache=_geometry_bake_has_existing_cache,
        apply_temporary_geometry_bake_settings=_apply_temporary_geometry_bake_settings,
        clear_geometry_bake_tracked_packed_cache_state=_clear_geometry_bake_tracked_packed_cache_state,
        call_operator_with_override=_call_operator_with_override,
        start_named_operator=_start_named_operator,
        refresh_geometry_bake_cache_state_after_completion=_refresh_geometry_bake_cache_state_after_completion,
        resolve_geometry_task_effective_bake_target=_resolve_geometry_task_effective_bake_target,
        write_geometry_bake_tracked_packed_cache_state=_write_geometry_bake_tracked_packed_cache_state,
        ensure_operator_finished=_ensure_operator_finished,
        restore_geometry_bake_entry_settings=_restore_geometry_bake_entry_settings,
        restore_scene_frame_state=_restore_scene_frame_state,
    )


def _invoke_physics_bake_task(task_ref, scene):
    return _invoke_physics_bake_task_impl(
        task_ref,
        scene,
        bpy_module=bpy,
        flow_execution_error_cls=FlowExecutionError,
        require_payload_object_ref=_require_payload_object_ref,
        capture_scene_frame_state=_capture_scene_frame_state,
        physics_task_has_existing_cache=_physics_task_has_existing_cache,
        start_named_operator=_start_named_operator,
        ensure_operator_finished=_ensure_operator_finished,
        restore_scene_frame_state=_restore_scene_frame_state,
    )


def _invoke_physics_bake_all_task(task_ref, scene):
    return _invoke_physics_bake_all_task_impl(
        task_ref,
        scene,
        bpy_module=bpy,
        flow_execution_error_cls=FlowExecutionError,
        require_payload_object_ref=_require_payload_object_ref,
        capture_scene_frame_state=_capture_scene_frame_state,
        physics_bake_all_has_pending_work=_physics_bake_all_has_pending_work,
        start_named_operator=_start_named_operator,
        ensure_operator_finished=_ensure_operator_finished,
        restore_scene_frame_state=_restore_scene_frame_state,
    )


def _invoke_render_task(task_ref, fallback_scene, node_name):
    return _invoke_render_task_impl(
        task_ref,
        fallback_scene,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
        capture_scene_frame_state=_capture_scene_frame_state,
        start_named_operator=_start_named_operator,
        ensure_operator_finished=_ensure_operator_finished,
        restore_scene_frame_state=_restore_scene_frame_state,
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
