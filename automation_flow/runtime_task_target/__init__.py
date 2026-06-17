import importlib

from .bake_lifecycle import (
    _refresh_geometry_bake_cache_state_after_completion,
    _restore_waiting_bake_cleanup,
    _schedule_geometry_bake_cache_refresh,
    _task_operator_result_is_skipped,
)
from .cache import (
    _geometry_bake_cache_status_from_node,
    _geometry_bake_cached_frame_from_filename,
    _geometry_bake_cached_frame_range_from_candidate_root,
    _geometry_bake_disk_cache_exists,
    _geometry_bake_disk_cache_frame_range,
    _geometry_bake_disk_cache_root_dir,
    _geometry_bake_entry_cached_frame_range,
    _geometry_bake_entry_has_cached_data,
    _geometry_bake_has_existing_cache,
    _geometry_bake_has_existing_cache_for_current_entry,
    _iter_geometry_bake_disk_cache_candidate_roots,
    _physics_bake_all_has_pending_work,
    _physics_bake_cache_status_from_node,
    _physics_task_has_existing_cache,
    _point_cache_frame_range,
    _point_cache_has_existing_cache,
)
from .geometry_execution import (
    _ensure_background_geometry_task_supported,
    _find_geometry_bake_entry_for_task,
    _invoke_geometry_nodes_bake_task,
    _resolve_geometry_task_effective_bake_target,
    _start_geometry_nodes_bake_task,
)
from .geometry_state import (
    _apply_geometry_bake_entry_settings,
    _apply_geometry_bake_settings_for_run,
    _apply_temporary_geometry_bake_settings,
    _capture_geometry_bake_entry_settings,
    _clear_geometry_bake_tracked_packed_cache_state,
    _geometry_bake_keep_overridden_settings_on_success,
    _get_geometry_bake_tracked_packed_cache_status,
    _read_geometry_bake_tracked_packed_cache_state,
    _resolve_geometry_task_source_node,
    _restore_geometry_bake_entry_settings,
    _write_geometry_bake_tracked_packed_cache_state,
)
from .resolution import (
    _call_operator_with_override,
    _compose_bake_override,
    _ensure_operator_finished,
    _resolve_bake_entry,
    _resolve_bake_target,
    _resolve_physics_batch_task_target,
    _resolve_physics_task_target,
    _split_bake_task_path,
    _split_physics_task_path,
    _start_named_operator,
)
from .scene_execution import (
    _invoke_physics_bake_all_task,
    _invoke_physics_bake_task,
    _invoke_render_task,
    _start_physics_bake_all_task,
    _start_physics_bake_task,
)


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]


def __getattr__(name):
    if name == "api":
        return importlib.import_module(f"{__name__}.api")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
