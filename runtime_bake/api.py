import json
import os
import re

import bpy

from ..runtime_core.constants import (
    BAKE_JOB_TYPE,
    FlowExecutionError,
    GN_LAST_BAKE_STATE_PROP,
    GN_PACKED_CACHE_STATE_PROP,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
)
from ..runtime_core.module_loading import bind_partial_export
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
    _apply_current_geometry_bake_temporary_override as _apply_current_geometry_bake_temporary_override_impl,
    _apply_geometry_bake_entry_settings as _apply_geometry_bake_entry_settings_impl,
    _apply_geometry_bake_runtime_disk_directory as _apply_geometry_bake_runtime_disk_directory_impl,
    _apply_geometry_bake_settings_for_run as _apply_geometry_bake_settings_for_run_impl,
    _apply_temporary_geometry_bake_settings as _apply_temporary_geometry_bake_settings_impl,
    _build_geometry_bake_release_task_ref as _build_geometry_bake_release_task_ref_impl,
    _call_operator_with_override as _call_operator_with_override_impl,
    _capture_geometry_bake_entry_settings as _capture_geometry_bake_entry_settings_impl,
    _clear_geometry_bake_recorded_cache_state as _clear_geometry_bake_recorded_cache_state_impl,
    _clear_geometry_bake_last_bake_state as _clear_geometry_bake_last_bake_state_impl,
    _clear_geometry_bake_tracked_packed_cache_state as _clear_geometry_bake_tracked_packed_cache_state_impl,
    _compose_bake_override as _compose_bake_override_impl,
    _ensure_background_geometry_task_supported as _ensure_background_geometry_task_supported_impl,
    _ensure_operator_finished as _ensure_operator_finished_impl,
    _find_geometry_bake_entry_for_task as _find_geometry_bake_entry_for_task_impl,
    _geometry_bake_cached_frame_from_filename as _geometry_bake_cached_frame_from_filename_impl,
    _geometry_bake_cached_frame_range_from_candidate_root as _geometry_bake_cached_frame_range_from_candidate_root_impl,
    _geometry_bake_cache_status_from_node as _geometry_bake_cache_status_from_node_impl,
    _geometry_bake_disk_cache_exists as _geometry_bake_disk_cache_exists_impl,
    _geometry_bake_disk_cache_frame_range as _geometry_bake_disk_cache_frame_range_impl,
    _geometry_bake_default_disk_cache_root_dir as _geometry_bake_default_disk_cache_root_dir_impl,
    _geometry_bake_default_disk_cache_root_dir_relpath as _geometry_bake_default_disk_cache_root_dir_relpath_impl,
    _geometry_bake_disk_cache_root_dir as _geometry_bake_disk_cache_root_dir_impl,
    _geometry_bake_entry_cached_frame_range as _geometry_bake_entry_cached_frame_range_impl,
    _geometry_bake_entry_has_cached_data as _geometry_bake_entry_has_cached_data_impl,
    _geometry_bake_has_existing_cache as _geometry_bake_has_existing_cache_impl,
    _geometry_bake_has_existing_cache_for_current_entry as _geometry_bake_has_existing_cache_for_current_entry_impl,
    _geometry_bake_keep_overridden_settings_on_success as _geometry_bake_keep_overridden_settings_on_success_impl,
    _get_geometry_bake_last_bake_state as _get_geometry_bake_last_bake_state_impl,
    _get_geometry_bake_tracked_packed_cache_status as _get_geometry_bake_tracked_packed_cache_status_impl,
    _invoke_geometry_nodes_bake_task as _invoke_geometry_nodes_bake_task_impl,
    _invoke_physics_bake_all_task as _invoke_physics_bake_all_task_impl,
    _invoke_physics_bake_task as _invoke_physics_bake_task_impl,
    _invoke_render_task as _invoke_render_task_impl,
    _iter_geometry_bake_disk_cache_candidate_roots as _iter_geometry_bake_disk_cache_candidate_roots_impl,
    _normalize_geometry_bake_modifier_directory_for_task as _normalize_geometry_bake_modifier_directory_for_task_impl,
    _physics_bake_all_has_pending_work as _physics_bake_all_has_pending_work_impl,
    _physics_bake_cache_status_from_node as _physics_bake_cache_status_from_node_impl,
    _physics_task_has_existing_cache as _physics_task_has_existing_cache_impl,
    _point_cache_frame_range as _point_cache_frame_range_impl,
    _point_cache_has_existing_cache as _point_cache_has_existing_cache_impl,
    _read_geometry_bake_last_bake_state as _read_geometry_bake_last_bake_state_impl,
    _read_geometry_bake_tracked_packed_cache_state as _read_geometry_bake_tracked_packed_cache_state_impl,
    _refresh_geometry_bake_cache_state_after_completion as _refresh_geometry_bake_cache_state_after_completion_impl,
    _resolve_geometry_task_effective_bake_target as _resolve_geometry_task_effective_bake_target_impl,
    _resolve_geometry_task_source_node as _resolve_geometry_task_source_node_impl,
    _restore_geometry_bake_entry_settings as _restore_geometry_bake_entry_settings_impl,
    _restore_waiting_bake_cleanup as _restore_waiting_bake_cleanup_impl,
    _run_geometry_bake_free_operators as _run_geometry_bake_free_operators_impl,
    _schedule_geometry_bake_cache_refresh as _schedule_geometry_bake_cache_refresh_impl,
    _start_geometry_nodes_bake_task as _start_geometry_nodes_bake_task_impl,
    _start_named_operator as _start_named_operator_impl,
    _start_physics_bake_all_task as _start_physics_bake_all_task_impl,
    _start_physics_bake_task as _start_physics_bake_task_impl,
    _task_operator_result_is_skipped as _task_operator_result_is_skipped_impl,
    _write_geometry_bake_last_bake_state as _write_geometry_bake_last_bake_state_impl,
    _write_geometry_bake_tracked_packed_cache_state as _write_geometry_bake_tracked_packed_cache_state_impl,
)


_ensure_operator_finished = bind_partial_export(
    _ensure_operator_finished_impl,
    flow_execution_error_cls=FlowExecutionError,
)


_find_geometry_bake_entry_for_task = bind_partial_export(
    _find_geometry_bake_entry_for_task_impl,
    flow_execution_error_cls=FlowExecutionError,
    require_payload_object_ref=_require_payload_object_ref,
)


_resolve_geometry_task_effective_bake_target = bind_partial_export(
    _resolve_geometry_task_effective_bake_target_impl,
    find_geometry_bake_entry_for_task=lambda task_ref, error_context: _find_geometry_bake_entry_for_task(
        task_ref,
        error_context,
    ),
)


_ensure_background_geometry_task_supported = bind_partial_export(
    _ensure_background_geometry_task_supported_impl,
    flow_execution_error_cls=FlowExecutionError,
    resolve_geometry_task_effective_bake_target=lambda task_ref: _resolve_geometry_task_effective_bake_target(task_ref),
)


_capture_geometry_bake_entry_settings = _capture_geometry_bake_entry_settings_impl


_build_geometry_bake_release_task_ref = bind_partial_export(
    _build_geometry_bake_release_task_ref_impl,
    get_geometry_bake_last_bake_state=lambda task_ref: _get_geometry_bake_last_bake_state(task_ref),
    get_geometry_bake_tracked_packed_cache_status=lambda task_ref: _get_geometry_bake_tracked_packed_cache_status(task_ref),
)


_apply_geometry_bake_entry_settings = _apply_geometry_bake_entry_settings_impl


def _apply_geometry_bake_runtime_disk_directory(bake_entry, task_ref, *, resolve_default_directory=None):
    if resolve_default_directory is None:
        object_ref = _require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "geometry bake"))
        modifier = object_ref.modifiers.get(task_ref["modifier_name"])
        if modifier is None:
            raise FlowExecutionError(
                "AF_E017",
                f"Modifier '{task_ref['modifier_name']}' missing while resolving runtime GN disk cache directory",
                str(task_ref.get("source_node", "") or "geometry bake"),
            )
        resolve_default_directory = lambda current_task_ref: _geometry_bake_default_disk_cache_root_dir_relpath(
            current_task_ref,
            modifier,
        )
    return _apply_geometry_bake_runtime_disk_directory_impl(
        bake_entry,
        task_ref,
        resolve_default_directory=resolve_default_directory,
    )


_restore_geometry_bake_entry_settings = _restore_geometry_bake_entry_settings_impl


_resolve_geometry_task_source_node = _resolve_geometry_task_source_node_impl


_read_geometry_bake_tracked_packed_cache_state = bind_partial_export(
    _read_geometry_bake_tracked_packed_cache_state_impl,
    gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
    json_module=json,
)


_read_geometry_bake_last_bake_state = bind_partial_export(
    _read_geometry_bake_last_bake_state_impl,
    gn_last_bake_state_prop=GN_LAST_BAKE_STATE_PROP,
    json_module=json,
)


_write_geometry_bake_tracked_packed_cache_state = bind_partial_export(
    _write_geometry_bake_tracked_packed_cache_state_impl,
    resolve_geometry_task_source_node=lambda task_ref: _resolve_geometry_task_source_node(task_ref),
    gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
    json_module=json,
)


_write_geometry_bake_last_bake_state = bind_partial_export(
    _write_geometry_bake_last_bake_state_impl,
    resolve_geometry_task_source_node=lambda task_ref: _resolve_geometry_task_source_node(task_ref),
    resolve_geometry_task_effective_bake_target=lambda task_ref: _resolve_geometry_task_effective_bake_target(task_ref),
    gn_last_bake_state_prop=GN_LAST_BAKE_STATE_PROP,
    json_module=json,
)


_clear_geometry_bake_tracked_packed_cache_state = bind_partial_export(
    _clear_geometry_bake_tracked_packed_cache_state_impl,
    resolve_geometry_task_source_node=lambda task_ref: _resolve_geometry_task_source_node(task_ref),
    gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
)


_clear_geometry_bake_last_bake_state = bind_partial_export(
    _clear_geometry_bake_last_bake_state_impl,
    resolve_geometry_task_source_node=lambda task_ref: _resolve_geometry_task_source_node(task_ref),
    gn_last_bake_state_prop=GN_LAST_BAKE_STATE_PROP,
)


_get_geometry_bake_tracked_packed_cache_status = bind_partial_export(
    _get_geometry_bake_tracked_packed_cache_status_impl,
    resolve_geometry_task_source_node=lambda task_ref: _resolve_geometry_task_source_node(task_ref),
    read_geometry_bake_tracked_packed_cache_state=lambda node: _read_geometry_bake_tracked_packed_cache_state(node),
)


_get_geometry_bake_last_bake_state = bind_partial_export(
    _get_geometry_bake_last_bake_state_impl,
    resolve_geometry_task_source_node=lambda task_ref: _resolve_geometry_task_source_node(task_ref),
    read_geometry_bake_last_bake_state=lambda node: _read_geometry_bake_last_bake_state(node),
)


_geometry_bake_entry_has_cached_data = _geometry_bake_entry_has_cached_data_impl


_geometry_bake_disk_cache_root_dir = bind_partial_export(
    _geometry_bake_disk_cache_root_dir_impl,
    bpy_module=bpy,
    require_payload_object_ref=_require_payload_object_ref,
)


_geometry_bake_default_disk_cache_root_dir = bind_partial_export(
    _geometry_bake_default_disk_cache_root_dir_impl,
    bpy_module=bpy,
)


_geometry_bake_default_disk_cache_root_dir_relpath = bind_partial_export(
    _geometry_bake_default_disk_cache_root_dir_relpath_impl,
    bpy_module=bpy,
)


_iter_geometry_bake_disk_cache_candidate_roots = bind_partial_export(
    _iter_geometry_bake_disk_cache_candidate_roots_impl,
    geometry_bake_disk_cache_root_dir=lambda task_ref, bake_entry=None: _geometry_bake_disk_cache_root_dir(
        task_ref,
        bake_entry=bake_entry,
    ),
)


_geometry_bake_cached_frame_from_filename = _geometry_bake_cached_frame_from_filename_impl


_geometry_bake_cached_frame_range_from_candidate_root = _geometry_bake_cached_frame_range_from_candidate_root_impl


_geometry_bake_disk_cache_frame_range = _geometry_bake_disk_cache_frame_range_impl


_geometry_bake_entry_cached_frame_range = _geometry_bake_entry_cached_frame_range_impl


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
        geometry_bake_disk_cache_exists=lambda task_ref, bake_entry=None: _geometry_bake_disk_cache_exists(
            task_ref,
            bake_entry=bake_entry,
        ),
    )


def _refresh_geometry_bake_cache_state_after_completion(task_ref, scene=None):
    return _refresh_geometry_bake_cache_state_after_completion_impl(
        task_ref,
        scene=scene if scene is not None else getattr(bpy.context, "scene", None),
        find_geometry_bake_entry_for_task=lambda current_task_ref, error_context: _find_geometry_bake_entry_for_task(
            current_task_ref,
            error_context,
        ),
        geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
        geometry_bake_entry_cached_frame_range=_geometry_bake_entry_cached_frame_range,
        resolve_geometry_task_effective_bake_target=lambda current_task_ref: _resolve_geometry_task_effective_bake_target(
            current_task_ref
        ),
        tag_all_node_editor_redraw=_tag_all_node_editor_redraw,
    )


_schedule_geometry_bake_cache_refresh = bind_partial_export(
    _schedule_geometry_bake_cache_refresh_impl,
    refresh_geometry_bake_cache_state_after_completion=lambda task_ref, scene=None: _refresh_geometry_bake_cache_state_after_completion(
        task_ref,
        scene=scene,
    ),
    find_geometry_bake_entry_for_task=lambda task_ref, error_context: _find_geometry_bake_entry_for_task(
        task_ref,
        error_context,
    ),
    geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
    geometry_bake_disk_cache_exists=lambda task_ref, bake_entry=None: _geometry_bake_disk_cache_exists(
        task_ref,
        bake_entry=bake_entry,
    ),
    tag_all_node_editor_redraw=_tag_all_node_editor_redraw,
)


_geometry_bake_disk_cache_exists = bind_partial_export(
    _geometry_bake_disk_cache_exists_impl,
    geometry_bake_disk_cache_candidate_roots=lambda task_ref, bake_entry=None: _iter_geometry_bake_disk_cache_candidate_roots(
        task_ref,
        bake_entry=bake_entry,
    ),
)


_geometry_bake_has_existing_cache = bind_partial_export(
    _geometry_bake_has_existing_cache_impl,
    geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
    get_geometry_bake_tracked_packed_cache_status=lambda task_ref: _get_geometry_bake_tracked_packed_cache_status(task_ref),
    geometry_bake_disk_cache_exists=lambda task_ref, bake_entry=None: _geometry_bake_disk_cache_exists(
        task_ref,
        bake_entry=bake_entry,
    ),
)


_geometry_bake_has_existing_cache_for_current_entry = bind_partial_export(
    _geometry_bake_has_existing_cache_for_current_entry_impl,
    geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
    get_geometry_bake_tracked_packed_cache_status=lambda task_ref: _get_geometry_bake_tracked_packed_cache_status(task_ref),
    geometry_bake_disk_cache_exists=lambda task_ref, bake_entry=None: _geometry_bake_disk_cache_exists(
        task_ref,
        bake_entry=bake_entry,
    ),
)


_point_cache_has_existing_cache = bind_partial_export(
    _point_cache_has_existing_cache_impl,
    bpy_module=bpy,
    os_module=os,
    re_module=re,
)


_point_cache_frame_range = bind_partial_export(
    _point_cache_frame_range_impl,
    point_cache_has_existing_cache=_point_cache_has_existing_cache,
)


_physics_bake_cache_status_from_node = bind_partial_export(
    _physics_bake_cache_status_from_node_impl,
    flow_execution_error_cls=FlowExecutionError,
    resolve_physics_task_target=_resolve_physics_task_target,
    point_cache_frame_range=_point_cache_frame_range,
)


_physics_task_has_existing_cache = bind_partial_export(
    _physics_task_has_existing_cache_impl,
    point_cache_has_existing_cache=_point_cache_has_existing_cache,
)


_physics_bake_all_has_pending_work = bind_partial_export(
    _physics_bake_all_has_pending_work_impl,
    physics_task_has_existing_cache=_physics_task_has_existing_cache,
)


_task_operator_result_is_skipped = _task_operator_result_is_skipped_impl


def _apply_temporary_geometry_bake_settings(task_ref):
    object_ref = _require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "geometry bake"))
    modifier = object_ref.modifiers.get(task_ref["modifier_name"])
    if modifier is None:
        raise FlowExecutionError(
            "AF_E017",
            f"Modifier '{task_ref['modifier_name']}' missing while resolving temporary GN bake settings",
            str(task_ref.get("source_node", "") or "geometry bake"),
        )
    return _apply_temporary_geometry_bake_settings_impl(
        task_ref,
        apply_full_settings=True,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        capture_geometry_bake_entry_settings=_capture_geometry_bake_entry_settings,
        apply_geometry_bake_entry_settings=_apply_geometry_bake_entry_settings,
        apply_geometry_bake_runtime_disk_directory=_apply_geometry_bake_runtime_disk_directory,
        resolve_default_directory=lambda current_task_ref: _geometry_bake_default_disk_cache_root_dir_relpath_impl(
            current_task_ref,
            modifier,
            bpy_module=bpy,
        ),
    )


def _apply_temporary_geometry_bake_runtime_directory(task_ref):
    object_ref = _require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "geometry bake"))
    modifier = object_ref.modifiers.get(task_ref["modifier_name"])
    if modifier is None:
        raise FlowExecutionError(
            "AF_E017",
            f"Modifier '{task_ref['modifier_name']}' missing while resolving temporary GN disk directory",
            str(task_ref.get("source_node", "") or "geometry bake"),
        )
    return _apply_temporary_geometry_bake_settings_impl(
        task_ref,
        apply_full_settings=False,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        capture_geometry_bake_entry_settings=_capture_geometry_bake_entry_settings,
        apply_geometry_bake_entry_settings=_apply_geometry_bake_entry_settings,
        apply_geometry_bake_runtime_disk_directory=_apply_geometry_bake_runtime_disk_directory,
        resolve_default_directory=lambda current_task_ref: _geometry_bake_default_disk_cache_root_dir_relpath_impl(
            current_task_ref,
            modifier,
            bpy_module=bpy,
        ),
    )


_apply_current_geometry_bake_temporary_override = bind_partial_export(
    _apply_current_geometry_bake_temporary_override_impl,
    apply_temporary_geometry_bake_settings=_apply_temporary_geometry_bake_settings,
    apply_temporary_geometry_bake_runtime_directory=_apply_temporary_geometry_bake_runtime_directory,
)


def _apply_geometry_bake_settings_for_run(task_ref):
    object_ref = _require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "geometry bake"))
    modifier = object_ref.modifiers.get(task_ref["modifier_name"])
    if modifier is None:
        raise FlowExecutionError(
            "AF_E017",
            f"Modifier '{task_ref['modifier_name']}' missing while applying GN bake run settings",
            str(task_ref.get("source_node", "") or "geometry bake"),
        )
    return _apply_geometry_bake_settings_for_run_impl(
        task_ref,
        find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
        apply_geometry_bake_entry_settings=_apply_geometry_bake_entry_settings,
        apply_geometry_bake_runtime_disk_directory=_apply_geometry_bake_runtime_disk_directory,
        resolve_default_directory=lambda current_task_ref: _geometry_bake_default_disk_cache_root_dir_relpath_impl(
            current_task_ref,
            modifier,
            bpy_module=bpy,
        ),
    )


_geometry_bake_keep_overridden_settings_on_success = _geometry_bake_keep_overridden_settings_on_success_impl


_clear_geometry_bake_recorded_cache_state = bind_partial_export(
    _clear_geometry_bake_recorded_cache_state_impl,
    clear_geometry_bake_tracked_packed_cache_state=lambda task_ref: _clear_geometry_bake_tracked_packed_cache_state(task_ref),
    clear_geometry_bake_last_bake_state=lambda task_ref: _clear_geometry_bake_last_bake_state(task_ref),
)


_normalize_geometry_bake_modifier_directory_for_task = bind_partial_export(
    _normalize_geometry_bake_modifier_directory_for_task_impl,
    bpy_module=bpy,
    require_payload_object_ref=_require_payload_object_ref,
)


_compose_bake_override = _compose_bake_override_impl


_call_operator_with_override = bind_partial_export(
    _call_operator_with_override_impl,
    operator_result_tokens=_operator_result_tokens,
)


_run_geometry_bake_free_operators = bind_partial_export(
    _run_geometry_bake_free_operators_impl,
    bpy_module=bpy,
    call_operator_with_override=_call_operator_with_override,
)


_start_named_operator = bind_partial_export(
    _start_named_operator_impl,
    flow_execution_error_cls=FlowExecutionError,
    call_operator_with_override=_call_operator_with_override,
)


_restore_waiting_bake_cleanup = bind_partial_export(
    _restore_waiting_bake_cleanup_impl,
    task_kind_geometry=TASK_KIND_GEOMETRY,
    task_kind_physics=TASK_KIND_PHYSICS,
    task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
    restore_geometry_bake_entry_settings=_restore_geometry_bake_entry_settings,
    restore_scene_frame_state=_restore_scene_frame_state,
)


_start_geometry_nodes_bake_task = bind_partial_export(
    _start_geometry_nodes_bake_task_impl,
    bpy_module=bpy,
    require_payload_object_ref=_require_payload_object_ref,
    find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
    compose_bake_override=_compose_bake_override,
    capture_scene_frame_state=_capture_scene_frame_state,
    geometry_bake_has_existing_cache_for_current_entry=_geometry_bake_has_existing_cache_for_current_entry,
    geometry_bake_has_existing_cache=_geometry_bake_has_existing_cache,
    apply_temporary_geometry_bake_settings=_apply_temporary_geometry_bake_settings,
    apply_current_geometry_bake_temporary_override=_apply_current_geometry_bake_temporary_override,
    build_geometry_bake_release_task_ref=_build_geometry_bake_release_task_ref,
    normalize_geometry_bake_modifier_directory_for_task=_normalize_geometry_bake_modifier_directory_for_task,
    clear_geometry_bake_recorded_cache_state=_clear_geometry_bake_recorded_cache_state,
    call_operator_with_override=_call_operator_with_override,
    start_named_operator=_start_named_operator,
    restore_waiting_bake_cleanup=_restore_waiting_bake_cleanup,
    bake_job_type=BAKE_JOB_TYPE,
    task_kind_geometry=TASK_KIND_GEOMETRY,
)


_start_physics_bake_task = bind_partial_export(
    _start_physics_bake_task_impl,
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


_start_physics_bake_all_task = bind_partial_export(
    _start_physics_bake_all_task_impl,
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


_invoke_geometry_nodes_bake_task = bind_partial_export(
    _invoke_geometry_nodes_bake_task_impl,
    bpy_module=bpy,
    require_payload_object_ref=_require_payload_object_ref,
    find_geometry_bake_entry_for_task=_find_geometry_bake_entry_for_task,
    capture_scene_frame_state=_capture_scene_frame_state,
    geometry_bake_has_existing_cache_for_current_entry=_geometry_bake_has_existing_cache_for_current_entry,
    geometry_bake_has_existing_cache=_geometry_bake_has_existing_cache,
    apply_temporary_geometry_bake_settings=_apply_temporary_geometry_bake_settings,
    apply_current_geometry_bake_temporary_override=_apply_current_geometry_bake_temporary_override,
    build_geometry_bake_release_task_ref=_build_geometry_bake_release_task_ref,
    normalize_geometry_bake_modifier_directory_for_task=_normalize_geometry_bake_modifier_directory_for_task,
    clear_geometry_bake_recorded_cache_state=_clear_geometry_bake_recorded_cache_state,
    call_operator_with_override=_call_operator_with_override,
    start_named_operator=_start_named_operator,
    refresh_geometry_bake_cache_state_after_completion=_refresh_geometry_bake_cache_state_after_completion,
    schedule_geometry_bake_cache_refresh=_schedule_geometry_bake_cache_refresh,
    resolve_geometry_task_effective_bake_target=_resolve_geometry_task_effective_bake_target,
    geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data,
    geometry_bake_disk_cache_exists=_geometry_bake_disk_cache_exists,
    clear_geometry_bake_tracked_packed_cache_state=_clear_geometry_bake_tracked_packed_cache_state,
    write_geometry_bake_tracked_packed_cache_state=_write_geometry_bake_tracked_packed_cache_state,
    write_geometry_bake_last_bake_state=_write_geometry_bake_last_bake_state,
    ensure_operator_finished=_ensure_operator_finished,
    restore_geometry_bake_entry_settings=_restore_geometry_bake_entry_settings,
    restore_scene_frame_state=_restore_scene_frame_state,
)


_invoke_physics_bake_task = bind_partial_export(
    _invoke_physics_bake_task_impl,
    bpy_module=bpy,
    flow_execution_error_cls=FlowExecutionError,
    require_payload_object_ref=_require_payload_object_ref,
    capture_scene_frame_state=_capture_scene_frame_state,
    physics_task_has_existing_cache=_physics_task_has_existing_cache,
    start_named_operator=_start_named_operator,
    ensure_operator_finished=_ensure_operator_finished,
    restore_scene_frame_state=_restore_scene_frame_state,
)


_invoke_physics_bake_all_task = bind_partial_export(
    _invoke_physics_bake_all_task_impl,
    bpy_module=bpy,
    flow_execution_error_cls=FlowExecutionError,
    require_payload_object_ref=_require_payload_object_ref,
    capture_scene_frame_state=_capture_scene_frame_state,
    physics_bake_all_has_pending_work=_physics_bake_all_has_pending_work,
    start_named_operator=_start_named_operator,
    ensure_operator_finished=_ensure_operator_finished,
    restore_scene_frame_state=_restore_scene_frame_state,
)


_invoke_render_task = bind_partial_export(
    _invoke_render_task_impl,
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
