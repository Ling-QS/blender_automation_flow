import os
import time

import bpy
from bpy.app.handlers import persistent

from ..runtime_core.constants import RELOAD_RESUME_CONTINUE_DELAY_SECONDS
from ..runtime_runner.core import FlowRunner
from ..runtime_runner.core.active import set_active_runner
from ..runtime_state.cache import (
    _read_reload_resume_checkpoint,
    _remove_reload_resume_checkpoint,
)
from .editor_utils import _tag_flow_node_editor_redraw

_PENDING_RELOAD_RESUME = None
_RESUME_RUNNER_TIMER_ACTIVE_RESET_CALLBACK = None
_RUNNER_RESUME_TIMER_CALLBACK = None
_UI_CONTEXT_CALLBACK = None
_SET_ACTIVE_RUNNER_CALLBACK = None


def configure_reload_resume_callbacks(
    *,
    reset_resume_timer_state=None,
    ensure_resume_runner_timer=None,
    capture_runtime_ui_context=None,
    set_active_runner=None,
):
    global _RESUME_RUNNER_TIMER_ACTIVE_RESET_CALLBACK, _RUNNER_RESUME_TIMER_CALLBACK, _UI_CONTEXT_CALLBACK, _SET_ACTIVE_RUNNER_CALLBACK
    _RESUME_RUNNER_TIMER_ACTIVE_RESET_CALLBACK = reset_resume_timer_state
    _RUNNER_RESUME_TIMER_CALLBACK = ensure_resume_runner_timer
    _UI_CONTEXT_CALLBACK = capture_runtime_ui_context
    _SET_ACTIVE_RUNNER_CALLBACK = set_active_runner


def _reset_resume_timer_state():
    if callable(_RESUME_RUNNER_TIMER_ACTIVE_RESET_CALLBACK):
        _RESUME_RUNNER_TIMER_ACTIVE_RESET_CALLBACK()


def _ensure_resume_runner_timer_callback():
    if callable(_RUNNER_RESUME_TIMER_CALLBACK):
        _RUNNER_RESUME_TIMER_CALLBACK()


def _capture_runtime_ui_context(context):
    if callable(_UI_CONTEXT_CALLBACK):
        return _UI_CONTEXT_CALLBACK(context)
    snapshot = {}
    for key in ("window", "screen", "area", "region", "space_data", "view_layer"):
        value = getattr(context, key, None)
        if value is not None:
            snapshot[key] = value
    return snapshot


def _set_active_runner(runner):
    if callable(_SET_ACTIVE_RUNNER_CALLBACK):
        _SET_ACTIVE_RUNNER_CALLBACK(runner)
        return
    set_active_runner(runner)


def schedule_reload_resume(request):
    global _PENDING_RELOAD_RESUME
    if not isinstance(request, dict):
        return
    _PENDING_RELOAD_RESUME = dict(request)


def _has_pending_reload_resume():
    return isinstance(_PENDING_RELOAD_RESUME, dict) and bool(_PENDING_RELOAD_RESUME)


def _peek_pending_reload_resume():
    return dict(_PENDING_RELOAD_RESUME or {})


def _consume_pending_reload_resume():
    global _PENDING_RELOAD_RESUME
    payload = dict(_PENDING_RELOAD_RESUME or {})
    _PENDING_RELOAD_RESUME = None
    return payload


def _log_reload_resume_error(message, request_payload=None):
    scene = bpy.context.scene
    logs = getattr(scene, "af_flow_logs", None) if scene is not None else None
    if logs is None:
        return
    item = logs.add()
    item.level = "ERROR"
    item.node_tree_name = str((request_payload or {}).get("tree_name", "") or "")
    item.node_name = str((request_payload or {}).get("node_name", "") or "")
    item.message = str(message)
    item.timestamp = time.strftime("%H:%M:%S")


def _perform_reload_resume(context):
    request_payload = _peek_pending_reload_resume()
    filepath = str(request_payload.get("filepath", "") or "").strip()
    if not filepath:
        return False
    try:
        current_filepath = str(getattr(bpy.data, "filepath", "") or "").strip()
        override = {
            key: value
            for key in ("window", "screen", "area", "region")
            for value in (getattr(context, key, None),)
            if value is not None
        }
        if current_filepath and os.path.normcase(os.path.normpath(current_filepath)) == os.path.normcase(os.path.normpath(filepath)):
            if override:
                with context.temp_override(**override):
                    result = bpy.ops.wm.revert_mainfile()
            else:
                result = bpy.ops.wm.revert_mainfile()
        else:
            if override:
                with context.temp_override(**override):
                    result = bpy.ops.wm.open_mainfile(filepath=filepath, load_ui=False)
            else:
                result = bpy.ops.wm.open_mainfile(filepath=filepath, load_ui=False)
        tokens = {str(item) for item in result} if isinstance(result, (set, list, tuple)) else {str(result)}
        if "FINISHED" not in tokens:
            raise RuntimeError(f"reload operator returned {sorted(tokens)}")
        return True
    except Exception as exc:
        _log_reload_resume_error(f"AF_E005: Reload failed: {exc}", request_payload)
        print(f"Automation Flow reload failed: {exc}")
        return False


def _resume_flow_from_checkpoint_payload(checkpoint):
    if not isinstance(checkpoint, dict):
        return False
    tree_name = str(checkpoint.get("tree_name", "") or "")
    node_tree = bpy.data.node_groups.get(tree_name)
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        raise RuntimeError(f"Automation Flow tree '{tree_name}' not found for reload resume")
    scene_name = str(checkpoint.get("scene_name", "") or "")
    scene = bpy.data.scenes.get(scene_name) if scene_name else None
    if scene is None:
        scene = bpy.context.scene or (bpy.data.scenes[0] if bpy.data.scenes else None)
    if scene is None:
        raise RuntimeError("No scene available for reload resume")
    runner = FlowRunner(
        node_tree,
        scene,
        ui_context=_capture_runtime_ui_context(bpy.context),
        start_node_name=str(checkpoint.get("start_node_name", "") or ""),
    )
    runner.resume(checkpoint)
    _set_active_runner(runner)
    _tag_flow_node_editor_redraw(node_tree.name)
    if not _invoke_resume_flow_modal():
        _ensure_resume_runner_timer_callback()
    return True


def _invoke_resume_flow_modal():
    window_manager = getattr(bpy.context, "window_manager", None)
    if window_manager is None:
        return False
    for window in getattr(window_manager, "windows", []):
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        area = next((candidate for candidate in getattr(screen, "areas", []) if getattr(candidate, "type", "") == "NODE_EDITOR"), None)
        region = None
        if area is not None:
            region = next((candidate for candidate in getattr(area, "regions", []) if getattr(candidate, "type", "") == "WINDOW"), None)
        override = {"window": window, "screen": screen}
        if area is not None:
            override["area"] = area
        if region is not None:
            override["region"] = region
        try:
            with bpy.context.temp_override(**override):
                result = bpy.ops.af.resume_flow_modal()
        except Exception:
            continue
        tokens = {str(item) for item in result} if isinstance(result, (set, list, tuple)) else {str(result)}
        if "RUNNING_MODAL" in tokens or "FINISHED" in tokens:
            return True
    return False


@persistent
def _resume_flow_after_load(_dummy):
    current_filepath = str(getattr(bpy.data, "filepath", "") or "").strip()
    if not current_filepath:
        return
    try:
        checkpoint = _read_reload_resume_checkpoint(current_filepath)
    except Exception as exc:
        print(f"Automation Flow resume checkpoint read failed: {exc}")
        return
    if not isinstance(checkpoint, dict) or str(checkpoint.get("kind", "") or "") != "AF_RELOAD_RESUME":
        return

    def _timer(checkpoint_payload=checkpoint, checkpoint_filepath=current_filepath):
        try:
            _resume_flow_from_checkpoint_payload(checkpoint_payload)
        except Exception as exc:
            _remove_reload_resume_checkpoint(checkpoint_filepath)
            scene_name = str(checkpoint_payload.get("scene_name", "") or "")
            scene = bpy.data.scenes.get(scene_name) if scene_name else (bpy.context.scene or None)
            settings = getattr(scene, "af_flow_settings", None) if scene is not None else None
            logs = getattr(scene, "af_flow_logs", None) if scene is not None else None
            if settings is not None:
                settings.runtime_status = "FAILED"
            if logs is not None:
                item = logs.add()
                item.level = "ERROR"
                item.node_tree_name = str(checkpoint_payload.get("tree_name", "") or "")
                item.node_name = str(checkpoint_payload.get("reload_node_name", "") or "")
                item.message = f"AF_E005: Reload resume failed: {exc}"
                item.timestamp = "00:00:00"
            print(f"Automation Flow reload resume failed: {exc}")
            return None
        _remove_reload_resume_checkpoint(checkpoint_filepath)
        return None

    delay_seconds = float(RELOAD_RESUME_CONTINUE_DELAY_SECONDS or 0.3)
    bpy.app.timers.register(_timer, first_interval=max(0.05, delay_seconds))


def _remove_resume_flow_after_load_handlers():
    handlers = getattr(bpy.app.handlers, "load_post", None)
    if handlers is None:
        return
    target_name = getattr(_resume_flow_after_load, "__name__", "_resume_flow_after_load")
    removable = [handler for handler in list(handlers) if getattr(handler, "__name__", "") == target_name]
    for handler in removable:
        try:
            handlers.remove(handler)
        except Exception:
            pass


def clear_pending_reload_resume():
    global _PENDING_RELOAD_RESUME
    _PENDING_RELOAD_RESUME = None
    _reset_resume_timer_state()

