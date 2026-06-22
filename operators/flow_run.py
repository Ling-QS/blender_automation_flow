import time

import bpy
from bpy.app.handlers import persistent

from ..runtime_runner.core import FlowRunner
from ..runtime_runner.core.active import get_active_runner, set_active_runner
from .editor_utils import _tag_flow_node_editor_redraw

_RESUME_RUNNER_TIMER_ACTIVE = False
_AUTO_FOLLOW_PENDING_STARTS = {}
_AUTO_FOLLOW_TIMER_ACTIVE = False
_AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE = False
_AUTO_FOLLOW_TIMER_GENERATION = 0
_AUTO_FOLLOW_PLAYBACK_TIMER_GENERATION = 0
_AUTO_FOLLOW_PLAYBACK_TIMER_ENABLED = False
_AUTO_FOLLOW_SUSPEND_DEPTH = 0
_AUTO_FOLLOW_IGNORE_UNTIL = 0.0
_AUTO_FOLLOW_LAST_PLAY_STATE = None
_AUTO_FOLLOW_SCENE_UPDATE_STATE = {}
_AUTO_FOLLOW_SCENE_UPDATE_END_PENDING = {}
_AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE = ""
_AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE = ""
_AUTO_FOLLOW_START_CACHE = {
    "entries": (),
    "dirty": True,
    "initialized": False,
    "expires_at": 0.0,
}
_AUTO_FOLLOW_SCENE_EDGE_GUARD = {}
_AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD = {}
_AUTO_FOLLOW_RECENT_OVERLAY = {
    "entries": [],
}
def _set_active_runner(runner):
    set_active_runner(runner)


def _get_active_runner():
    return get_active_runner()


def _suspend_auto_follow_notifications():
    global _AUTO_FOLLOW_SUSPEND_DEPTH
    _AUTO_FOLLOW_SUSPEND_DEPTH += 1


def _resume_auto_follow_notifications():
    global _AUTO_FOLLOW_SUSPEND_DEPTH
    _AUTO_FOLLOW_SUSPEND_DEPTH = max(0, int(_AUTO_FOLLOW_SUSPEND_DEPTH) - 1)


def _runner_tick_step_budget(runner):
    if runner is not None and bool(getattr(runner, "auto_follow", False)):
        return None
    return 1


def _scene_flow_settings(scene):
    return getattr(scene, "af_flow_settings", None) if scene is not None else None


def _is_animation_playing():
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return False
    for window in getattr(wm, "windows", []):
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        if bool(getattr(screen, "is_animation_playing", False)):
            return True
    return False


def _arm_auto_follow_cooldown(seconds=0.35):
    global _AUTO_FOLLOW_IGNORE_UNTIL
    _AUTO_FOLLOW_IGNORE_UNTIL = max(
        float(_AUTO_FOLLOW_IGNORE_UNTIL),
        float(time.monotonic()) + max(0.0, float(seconds)),
    )


def _auto_follow_queue_interval():
    if _is_animation_playing():
        return 0.01
    return 0.02


def _mark_auto_follow_start_cache_dirty():
    _AUTO_FOLLOW_START_CACHE["entries"] = ()
    _AUTO_FOLLOW_START_CACHE["dirty"] = True
    _AUTO_FOLLOW_START_CACHE["initialized"] = False
    _AUTO_FOLLOW_START_CACHE["expires_at"] = 0.0


def _auto_follow_start_cache_ttl_seconds():
    if _is_animation_playing():
        return 0.5
    return 0.25


def _cache_recent_auto_follow_overlay(runner):
    global _AUTO_FOLLOW_RECENT_OVERLAY
    if runner is None or not bool(getattr(runner, "auto_follow", False)):
        return
    recent_refs_fn = getattr(runner, "auto_follow_recent_step_refs", None)
    recent_refs = recent_refs_fn() if callable(recent_refs_fn) else []
    if not recent_refs:
        return
    expiry = float(getattr(runner, "_auto_follow_recent_step_expiry", 0.0) or 0.0)
    if expiry <= float(time.monotonic()):
        return
    root_tree_name = str(getattr(getattr(runner, "node_tree", None), "name", "") or "")
    run_id = str(getattr(runner, "run_id", "") or "")
    existing_entries = list(dict(_AUTO_FOLLOW_RECENT_OVERLAY or {}).get("entries", []) or [])
    now = float(time.monotonic())
    filtered_entries = []
    for entry in existing_entries:
        if not isinstance(entry, dict):
            continue
        if float(entry.get("expiry", 0.0) or 0.0) <= now:
            continue
        if run_id and str(entry.get("run_id", "") or "") == run_id:
            continue
        filtered_entries.append(entry)
    filtered_entries.append(
        {
            "root_tree_name": root_tree_name,
            "run_id": run_id,
            "step_refs": [dict(item) for item in recent_refs if isinstance(item, dict)],
            "expiry": expiry,
        }
    )
    _AUTO_FOLLOW_RECENT_OVERLAY = {
        "entries": filtered_entries,
    }


def _arm_post_run_depsgraph_guard(scene, callback_budget=2):
    if scene is None or _is_animation_playing():
        return
    scene_name = str(getattr(scene, "name", "") or "")
    if not scene_name:
        return
    _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD[scene_name] = {
        "frame": int(getattr(scene, "frame_current", 0) or 0),
        "subframe": float(getattr(scene, "frame_subframe", 0.0) or 0.0),
        "time": float(time.monotonic()),
        "remaining_callbacks": max(0, int(callback_budget)),
    }

def _consume_post_run_depsgraph_guard(scene, depsgraph=None):
    del depsgraph
    if scene is None or _is_animation_playing():
        return False
    scene_name = str(getattr(scene, "name", "") or "")
    if not scene_name:
        return False
    guard = _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD.get(scene_name)
    if not isinstance(guard, dict):
        return False
    guard_age = float(time.monotonic()) - float(guard.get("time", 0.0) or 0.0)
    if guard_age < 0.0:
        guard_age = 0.0
    if guard_age > 0.03:
        _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD.pop(scene_name, None)
        return False
    current_frame = int(getattr(scene, "frame_current", 0) or 0)
    current_subframe = float(getattr(scene, "frame_subframe", 0.0) or 0.0)
    if current_frame != int(guard.get("frame", current_frame)):
        _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD.pop(scene_name, None)
        return False
    if abs(current_subframe - float(guard.get("subframe", current_subframe) or 0.0)) > 1e-6:
        _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD.pop(scene_name, None)
        return False
    remaining_callbacks = int(guard.get("remaining_callbacks", 0) or 0)
    if remaining_callbacks <= 0:
        _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD.pop(scene_name, None)
        return False
    remaining_callbacks -= 1
    if remaining_callbacks <= 0:
        _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD.pop(scene_name, None)
    else:
        guard["remaining_callbacks"] = remaining_callbacks
        _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD[scene_name] = guard
    return True


def get_recent_auto_follow_overlay_step_refs(root_tree_name=""):
    overlay = dict(_AUTO_FOLLOW_RECENT_OVERLAY or {})
    overlay_entries = list(overlay.get("entries", []) or [])
    if not overlay_entries:
        return []
    expected_root_tree_name = str(root_tree_name or "")
    now = float(time.monotonic())
    step_refs = []
    filtered_entries = []
    for entry in overlay_entries:
        if not isinstance(entry, dict):
            continue
        if float(entry.get("expiry", 0.0) or 0.0) <= now:
            continue
        filtered_entries.append(entry)
        if expected_root_tree_name and str(entry.get("root_tree_name", "") or "") != expected_root_tree_name:
            continue
        step_refs.extend(dict(item) for item in entry.get("step_refs", []) if isinstance(item, dict))
    if filtered_entries != overlay_entries:
        _AUTO_FOLLOW_RECENT_OVERLAY["entries"] = filtered_entries
    return step_refs


def _auto_follow_runner_interval_seconds(scene=None, default_poll_ms=200):
    del scene, default_poll_ms
    return 0.01


def _auto_follow_debounce_seconds(scene=None, default_debounce_ms=300):
    if _is_animation_playing():
        return 0.0
    settings = _scene_flow_settings(scene)
    debounce_ms = int(getattr(settings, "auto_follow_debounce_ms", default_debounce_ms) or default_debounce_ms) if settings is not None else int(default_debounce_ms)
    return max(0.05, debounce_ms / 1000.0)


def _auto_follow_entry_key(scene_name, tree_name, start_node_name):
    return f"{str(scene_name or '')}::{str(tree_name or '')}::{str(start_node_name or '')}"


def _start_runner(node_tree, scene, start_node_name="", ui_context=None, auto_follow=False):
    if not bool(auto_follow):
        _AUTO_FOLLOW_PENDING_STARTS.clear()
    runner = FlowRunner(
        node_tree,
        scene,
        ui_context=dict(ui_context or {}),
        start_node_name=str(start_node_name or ""),
        auto_follow=bool(auto_follow),
    )
    runner.start()
    _set_active_runner(runner)
    _tag_flow_node_editor_redraw(getattr(node_tree, "name", None))
    return runner


def _start_subflow_runner(node_tree, scene, subflow_start_name="", ui_context=None):
    runner = FlowRunner(
        node_tree,
        scene,
        ui_context=dict(ui_context or {}),
        start_node_name="",
        auto_follow=False,
    )
    runner.start_subflow(str(subflow_start_name or ""))
    _set_active_runner(runner)
    _tag_flow_node_editor_redraw(getattr(node_tree, "name", None))
    return runner


def _start_branch_runner(node_tree, scene, branch_start_name="", ui_context=None):
    runner = FlowRunner(
        node_tree,
        scene,
        ui_context=dict(ui_context or {}),
        start_node_name="",
        auto_follow=False,
    )
    runner.start_branch(str(branch_start_name or ""))
    _set_active_runner(runner)
    _tag_flow_node_editor_redraw(getattr(node_tree, "name", None))
    return runner


def _tag_viewport_redraw():
    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _finish_active_runner_for_timer():
    runner = _get_active_runner()
    tree_name = runner.node_tree.name if runner is not None else None
    is_auto_follow = bool(getattr(runner, "auto_follow", False)) if runner is not None else False
    _cache_recent_auto_follow_overlay(runner)
    if runner is not None and is_auto_follow:
        _arm_post_run_depsgraph_guard(getattr(runner, "scene", None))
    _set_active_runner(None)
    _tag_flow_node_editor_redraw(tree_name)
    if not is_auto_follow:
        _tag_viewport_redraw()


def _runner_timer_interval(runner):
    if runner is None:
        return None
    scene = getattr(runner, "scene", None)
    return _auto_follow_runner_interval_seconds(scene=scene, default_poll_ms=200) if bool(getattr(runner, "auto_follow", False)) else max(0.05, int(getattr(getattr(scene, "af_flow_settings", None), "poll_interval_ms", 200) or 200) / 1000.0)


def _iter_auto_follow_start_nodes():
    now = float(time.monotonic())
    cache = _AUTO_FOLLOW_START_CACHE
    if bool(cache.get("initialized", False)) and not bool(cache.get("dirty", True)) and now < float(cache.get("expires_at", 0.0) or 0.0):
        resolved_entries = []
        cached_entries = tuple(cache.get("entries", ()) or ())
        for tree_name, start_node_name in cached_entries:
            node_tree = bpy.data.node_groups.get(str(tree_name or ""))
            if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
                _mark_auto_follow_start_cache_dirty()
                resolved_entries = []
                break
            start_node = node_tree.nodes.get(str(start_node_name or ""))
            if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeStart":
                _mark_auto_follow_start_cache_dirty()
                resolved_entries = []
                break
            if not bool(getattr(start_node, "auto_follow_enabled", False)):
                _mark_auto_follow_start_cache_dirty()
                resolved_entries = []
                break
            resolved_entries.append((node_tree, start_node))
        if resolved_entries or not cached_entries:
            for resolved_entry in resolved_entries:
                yield resolved_entry
            return

    cached_entries = []
    for node_tree in getattr(bpy.data, "node_groups", []):
        if getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            continue
        for node in getattr(node_tree, "nodes", []):
            if getattr(node, "bl_idname", "") != "AFNodeStart":
                continue
            if not bool(getattr(node, "auto_follow_enabled", False)):
                continue
            cached_entries.append((str(getattr(node_tree, "name", "") or ""), str(getattr(node, "name", "") or "")))
            yield node_tree, node
    _AUTO_FOLLOW_START_CACHE["entries"] = tuple(cached_entries)
    _AUTO_FOLLOW_START_CACHE["dirty"] = False
    _AUTO_FOLLOW_START_CACHE["initialized"] = True
    _AUTO_FOLLOW_START_CACHE["expires_at"] = now + float(_auto_follow_start_cache_ttl_seconds())


def _playback_state_payload(playing=False, on_play=False, on_pause=False):
    return {
        "playing": bool(playing),
        "on_play": bool(on_play),
        "on_pause": bool(on_pause),
    }


def _trigger_state_payload(
    *,
    manual=False,
    scene_updating=False,
    on_scene_update_start=False,
    on_scene_update_end=False,
    object_interaction_mode="",
    viewport_shading_mode="",
):
    return {
        "manual": bool(manual),
        "scene_updating": bool(scene_updating),
        "on_scene_update_start": bool(on_scene_update_start),
        "on_scene_update_end": bool(on_scene_update_end),
        "object_interaction_mode": str(object_interaction_mode or ""),
        "viewport_shading_mode": str(viewport_shading_mode or ""),
    }


def _merge_playback_state_payload(base_payload, extra_payload):
    base = dict(base_payload or {})
    extra = dict(extra_payload or {})
    return {
        "playing": bool(extra.get("playing", base.get("playing", False))),
        "on_play": bool(base.get("on_play", False)) or bool(extra.get("on_play", False)),
        "on_pause": bool(base.get("on_pause", False)) or bool(extra.get("on_pause", False)),
    }


def _merge_trigger_state_payload(base_payload, extra_payload):
    base = dict(base_payload or {})
    extra = dict(extra_payload or {})
    merged_object_interaction_mode = str(base.get("object_interaction_mode", "") or "")
    extra_object_interaction_mode = str(extra.get("object_interaction_mode", "") or "")
    if extra_object_interaction_mode:
        merged_object_interaction_mode = extra_object_interaction_mode
    merged_viewport_shading_mode = str(base.get("viewport_shading_mode", "") or "")
    extra_viewport_shading_mode = str(extra.get("viewport_shading_mode", "") or "")
    if extra_viewport_shading_mode:
        merged_viewport_shading_mode = extra_viewport_shading_mode
    return {
        "manual": bool(base.get("manual", False)) or bool(extra.get("manual", False)),
        "scene_updating": bool(base.get("scene_updating", False)) or bool(extra.get("scene_updating", False)),
        "on_scene_update_start": bool(base.get("on_scene_update_start", False)) or bool(extra.get("on_scene_update_start", False)),
        "on_scene_update_end": bool(base.get("on_scene_update_end", False)) or bool(extra.get("on_scene_update_end", False)),
        "object_interaction_mode": merged_object_interaction_mode,
        "viewport_shading_mode": merged_viewport_shading_mode,
    }


def _playback_edge_signature(playback_state):
    payload = dict(playback_state or {})
    if bool(payload.get("on_play", False)):
        return "ON_PLAY"
    if bool(payload.get("on_pause", False)):
        return "ON_PAUSE"
    return ""


def _consume_scene_playback_edge(scene, playback_state, now=None):
    payload = dict(playback_state or {})
    edge_signature = _playback_edge_signature(payload)
    if not edge_signature or scene is None:
        return payload

    if now is None:
        now = time.monotonic()
    scene_name = str(getattr(scene, "name", "") or "")
    if not scene_name:
        return payload
    guard = _AUTO_FOLLOW_SCENE_EDGE_GUARD.get(scene_name)
    if isinstance(guard, dict):
        guard_age = float(now) - float(guard.get("time", 0.0) or 0.0)
        if guard_age < 0.0:
            guard_age = 0.0
        if (
            guard_age <= 0.35
            and str(guard.get("signature", "") or "") == edge_signature
            and bool(guard.get("playing", False)) == bool(payload.get("playing", False))
        ):
            payload["on_play"] = False
            payload["on_pause"] = False
            return payload
    _AUTO_FOLLOW_SCENE_EDGE_GUARD[scene_name] = {
        "signature": edge_signature,
        "playing": bool(payload.get("playing", False)),
        "time": float(now),
    }
    return payload


def _scene_update_state(scene_name):
    state = _AUTO_FOLLOW_SCENE_UPDATE_STATE.get(scene_name)
    if not isinstance(state, dict):
        state = {
            "burst_active": False,
            "last_dirty_at": 0.0,
        }
    return state


def _mark_scene_update_activity(scene, now=None):
    if scene is None:
        return _trigger_state_payload()
    if now is None:
        now = time.monotonic()
    scene_name = str(getattr(scene, "name", "") or "")
    if not scene_name:
        return _trigger_state_payload()
    state = _scene_update_state(scene_name)
    on_start = not bool(state.get("burst_active", False))
    state["burst_active"] = True
    state["last_dirty_at"] = float(now)
    _AUTO_FOLLOW_SCENE_UPDATE_STATE[scene_name] = state
    _AUTO_FOLLOW_SCENE_UPDATE_END_PENDING.pop(scene_name, None)
    return _trigger_state_payload(
        scene_updating=True,
        on_scene_update_start=on_start,
    )


def _scene_update_end_due_scenes(now=None):
    if now is None:
        now = time.monotonic()
    due = []
    for scene_name, state in list(_AUTO_FOLLOW_SCENE_UPDATE_STATE.items()):
        if not isinstance(state, dict) or not bool(state.get("burst_active", False)):
            continue
        scene = bpy.data.scenes.get(str(scene_name or ""))
        if scene is None or _scene_flow_settings(scene) is None:
            _AUTO_FOLLOW_SCENE_UPDATE_STATE.pop(scene_name, None)
            _AUTO_FOLLOW_SCENE_UPDATE_END_PENDING.pop(scene_name, None)
            continue
        last_dirty_at = float(state.get("last_dirty_at", 0.0) or 0.0)
        debounce_seconds = _auto_follow_debounce_seconds(scene=scene, default_debounce_ms=300)
        if float(now) < last_dirty_at + debounce_seconds:
            continue
        if bool(_AUTO_FOLLOW_SCENE_UPDATE_END_PENDING.get(scene_name, False)):
            continue
        _AUTO_FOLLOW_SCENE_UPDATE_END_PENDING[scene_name] = True
        due.append(scene)
    return due


def _consume_scene_update_end(scene):
    if scene is None:
        return None
    scene_name = str(getattr(scene, "name", "") or "")
    if not scene_name:
        return None
    state = _scene_update_state(scene_name)
    if not bool(state.get("burst_active", False)):
        return None
    state["burst_active"] = False
    _AUTO_FOLLOW_SCENE_UPDATE_STATE[scene_name] = state
    _AUTO_FOLLOW_SCENE_UPDATE_END_PENDING.pop(scene_name, None)
    return _trigger_state_payload(
        on_scene_update_end=True,
    )


def _normalize_object_interaction_mode(raw_mode):
    mode = str(raw_mode or "").strip().upper()
    if mode.startswith("EDIT"):
        return "EDIT"
    if mode == "PAINT_WEIGHT":
        return "WEIGHT_PAINT"
    if mode == "PAINT_VERTEX":
        return "VERTEX_PAINT"
    if mode == "PAINT_TEXTURE":
        return "TEXTURE_PAINT"
    if mode in {"OBJECT", "SCULPT", "POSE", "WEIGHT_PAINT", "VERTEX_PAINT", "TEXTURE_PAINT"}:
        return mode
    return ""


def _active_object_interaction_mode():
    normalized = _normalize_object_interaction_mode(getattr(bpy.context, "mode", ""))
    if normalized:
        return normalized
    view_layer = getattr(bpy.context, "view_layer", None)
    objects = getattr(view_layer, "objects", None) if view_layer is not None else None
    active_object = getattr(objects, "active", None) if objects is not None else None
    return _normalize_object_interaction_mode(getattr(active_object, "mode", ""))


def _active_viewport_shading_mode():
    area = getattr(bpy.context, "area", None)
    space_data = getattr(bpy.context, "space_data", None)
    if getattr(area, "type", "") == "VIEW_3D" and getattr(space_data, "type", "") == "VIEW_3D":
        shading = getattr(space_data, "shading", None)
        return str(getattr(shading, "type", "") or "")
    window = getattr(bpy.context, "window", None)
    screen = getattr(window, "screen", None) if window is not None else None
    if screen is not None:
        for candidate_area in getattr(screen, "areas", []):
            if getattr(candidate_area, "type", "") != "VIEW_3D":
                continue
            for candidate_space in getattr(candidate_area, "spaces", []):
                if getattr(candidate_space, "type", "") != "VIEW_3D":
                    continue
                shading = getattr(candidate_space, "shading", None)
                return str(getattr(shading, "type", "") or "")
    return ""


def _active_auto_follow_scene():
    window = getattr(bpy.context, "window", None)
    scene = getattr(window, "scene", None) if window is not None else None
    if scene is not None and _scene_flow_settings(scene) is not None:
        return scene
    scene = getattr(bpy.context, "scene", None)
    if scene is not None and _scene_flow_settings(scene) is not None:
        return scene
    return None


def _prime_interaction_trigger_state():
    global _AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE, _AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE
    _AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE = _active_object_interaction_mode()
    _AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE = _active_viewport_shading_mode()


def _poll_interaction_trigger_state_once():
    global _AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE, _AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE
    current_object_mode = _active_object_interaction_mode()
    current_viewport_shading = _active_viewport_shading_mode()
    target_scene = _active_auto_follow_scene()

    last_object_mode = str(_AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE or "")
    if current_object_mode != last_object_mode:
        if current_object_mode and target_scene is not None:
            trigger_state = _trigger_state_payload(object_interaction_mode=current_object_mode)
            _handle_auto_follow_scene_trigger(
                target_scene,
                prefer_immediate=True,
                trigger_state=trigger_state,
                ignore_debounce=True,
            )
        _AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE = current_object_mode

    last_viewport_shading = str(_AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE or "")
    if current_viewport_shading != last_viewport_shading:
        if current_viewport_shading and target_scene is not None:
            trigger_state = _trigger_state_payload(viewport_shading_mode=current_viewport_shading)
            _handle_auto_follow_scene_trigger(
                target_scene,
                prefer_immediate=True,
                trigger_state=trigger_state,
                ignore_debounce=True,
            )
        _AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE = current_viewport_shading

    for scene in _scene_update_end_due_scenes():
        trigger_state = _consume_scene_update_end(scene)
        if trigger_state is None:
            continue
        _handle_auto_follow_scene_trigger(
            scene,
            prefer_immediate=True,
            trigger_state=trigger_state,
            ignore_debounce=True,
        )


def _queue_auto_follow_for_scene(scene, playback_state=None, trigger_state=None, ignore_debounce=False):
    if scene is None:
        return
    if _scene_flow_settings(scene) is None:
        return
    now = time.monotonic()
    scene_name = str(getattr(scene, "name", "") or "")
    queued_playback_state = _merge_playback_state_payload(
        _playback_state_payload(playing=_is_animation_playing()),
        playback_state,
    )
    queued_playback_state = _consume_scene_playback_edge(scene, queued_playback_state, now=now)
    queued_trigger_state = _merge_trigger_state_payload(
        _trigger_state_payload(),
        trigger_state,
    )
    for node_tree, node in _iter_auto_follow_start_nodes():
        key = _auto_follow_entry_key(scene_name, getattr(node_tree, "name", ""), getattr(node, "name", ""))
        existing = _AUTO_FOLLOW_PENDING_STARTS.get(key)
        first_dirty_at = float(existing.get("first_dirty_at", now)) if isinstance(existing, dict) else float(now)
        merged_playback_state = _merge_playback_state_payload(
            existing.get("playback_state") if isinstance(existing, dict) else None,
            queued_playback_state,
        )
        merged_trigger_state = _merge_trigger_state_payload(
            existing.get("trigger_state") if isinstance(existing, dict) else None,
            queued_trigger_state,
        )
        _AUTO_FOLLOW_PENDING_STARTS[key] = {
            "scene_name": scene_name,
            "tree_name": str(getattr(node_tree, "name", "") or ""),
            "start_node_name": str(getattr(node, "name", "") or ""),
            "auto_order": int(getattr(node, "auto_order", 0) or 0),
            "first_dirty_at": float(first_dirty_at),
            "last_dirty_at": float(now),
            "playback_state": merged_playback_state,
            "trigger_state": merged_trigger_state,
            "ignore_debounce": (
                bool(ignore_debounce)
                or (bool(existing.get("ignore_debounce", False)) if isinstance(existing, dict) else False)
            ),
        }


def _log_auto_follow_start_error(scene, tree_name, start_node_name, exc):
    logs = getattr(scene, "af_flow_logs", None) if scene is not None else None
    if logs is None:
        return
    item = logs.add()
    item.level = "ERROR"
    item.node_tree_name = str(tree_name or "")
    item.node_name = str(start_node_name or "")
    item.message = f"AUTO_FOLLOW_FAILED: {exc}"
    item.timestamp = time.strftime("%H:%M:%S")
    settings = _scene_flow_settings(scene)
    max_entries = max(10, int(getattr(settings, "max_log_entries", 2000) or 2000)) if settings is not None else 2000
    while len(logs) > max_entries:
        logs.remove(0)


def _ensure_auto_follow_timer():
    global _AUTO_FOLLOW_TIMER_ACTIVE, _AUTO_FOLLOW_TIMER_GENERATION
    if _AUTO_FOLLOW_TIMER_ACTIVE:
        return
    _AUTO_FOLLOW_TIMER_GENERATION += 1
    timer_generation = int(_AUTO_FOLLOW_TIMER_GENERATION)

    def _timer():
        global _AUTO_FOLLOW_TIMER_ACTIVE
        if timer_generation != int(_AUTO_FOLLOW_TIMER_GENERATION):
            return None
        interval = _process_auto_follow_queue_once()
        if interval is None:
            _AUTO_FOLLOW_TIMER_ACTIVE = False
            return None
        return interval

    _AUTO_FOLLOW_TIMER_ACTIVE = True
    bpy.app.timers.register(_timer, first_interval=_auto_follow_queue_interval())


def _iter_auto_follow_window_scenes():
    yielded = set()
    wm = getattr(bpy.context, "window_manager", None)
    if wm is not None:
        for window in getattr(wm, "windows", []):
            scene = getattr(window, "scene", None)
            if scene is None or _scene_flow_settings(scene) is None:
                continue
            scene_key = int(scene.as_pointer()) if hasattr(scene, "as_pointer") else id(scene)
            if scene_key in yielded:
                continue
            yielded.add(scene_key)
            yield scene
    if yielded:
        return
    scene = getattr(bpy.context, "scene", None)
    if scene is None or _scene_flow_settings(scene) is None:
        return
    yield scene


def _prime_auto_follow_playback_state():
    global _AUTO_FOLLOW_LAST_PLAY_STATE
    _AUTO_FOLLOW_LAST_PLAY_STATE = bool(_is_animation_playing())


def _poll_auto_follow_playback_state_once(current_state=None):
    global _AUTO_FOLLOW_LAST_PLAY_STATE
    current_state = bool(_is_animation_playing()) if current_state is None else bool(current_state)
    last_state = _AUTO_FOLLOW_LAST_PLAY_STATE
    if last_state is None:
        _AUTO_FOLLOW_LAST_PLAY_STATE = current_state
        return
    if current_state == bool(last_state):
        return
    if current_state and not bool(last_state):
        # Preserve the pending play edge for the first frame-change callback.
        return
    if (not current_state) and bool(last_state):
        playback_state = _playback_state_payload(
            playing=current_state,
            on_play=False,
            on_pause=True,
        )
        for scene in _iter_auto_follow_window_scenes():
            _handle_auto_follow_scene_trigger(
                scene,
                prefer_immediate=True,
                playback_state=playback_state,
                ignore_debounce=True,
            )
    _AUTO_FOLLOW_LAST_PLAY_STATE = current_state


def _ensure_auto_follow_playback_timer():
    global _AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE, _AUTO_FOLLOW_PLAYBACK_TIMER_GENERATION
    if _AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE or not _AUTO_FOLLOW_PLAYBACK_TIMER_ENABLED:
        return
    _AUTO_FOLLOW_PLAYBACK_TIMER_GENERATION += 1
    timer_generation = int(_AUTO_FOLLOW_PLAYBACK_TIMER_GENERATION)

    def _timer():
        global _AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE
        if timer_generation != int(_AUTO_FOLLOW_PLAYBACK_TIMER_GENERATION):
            return None
        if not _AUTO_FOLLOW_PLAYBACK_TIMER_ENABLED:
            _AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE = False
            return None

        current_state = bool(_is_animation_playing())
        _poll_auto_follow_playback_state_once(current_state=current_state)
        _poll_interaction_trigger_state_once()
        return 0.05 if current_state else 0.1

    _AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE = True
    bpy.app.timers.register(_timer, first_interval=0.05)


def _tick_active_auto_follow_runner_once():
    runner = _get_active_runner()
    if runner is None:
        return False
    try:
        _suspend_auto_follow_notifications()
        try:
            finished = runner.tick(max_immediate_steps=_runner_tick_step_budget(runner))
        finally:
            _resume_auto_follow_notifications()
    except Exception:
        _finish_active_runner_for_timer()
        raise
    if not bool(getattr(runner, "auto_follow", False)):
        _tag_flow_node_editor_redraw(getattr(getattr(runner, "node_tree", None), "name", None))
        _tag_viewport_redraw()
    if finished:
        _finish_active_runner_for_timer()
        return True
    _ensure_resume_runner_timer()
    return True


def _run_auto_follow_queue_now(ignore_debounce=False, max_handoffs=16):
    handoffs = 0
    ran_any = False
    while _AUTO_FOLLOW_PENDING_STARTS and _get_active_runner() is None and handoffs < max(1, int(max_handoffs)) and not _has_pending_reload_resume():
        _process_auto_follow_queue_once(ignore_debounce=bool(ignore_debounce))
        runner = _get_active_runner()
        if runner is None:
            if _AUTO_FOLLOW_PENDING_STARTS:
                _ensure_auto_follow_timer()
            return ran_any
        ran_any = True
        handoffs += 1
        _tick_active_auto_follow_runner_once()
        if _get_active_runner() is not None:
            return True
    if _AUTO_FOLLOW_PENDING_STARTS and _get_active_runner() is None:
        _ensure_auto_follow_timer()
    return ran_any


def _handoff_ready_auto_follow_queue(max_handoffs=16):
    return _run_auto_follow_queue_now(ignore_debounce=False, max_handoffs=max_handoffs)


def _try_run_auto_follow_immediately(scene, ignore_debounce=False):
    if scene is None:
        return False
    return _run_auto_follow_queue_now(ignore_debounce=bool(ignore_debounce))


def _process_auto_follow_queue_once(ignore_debounce=False):
    if not _AUTO_FOLLOW_PENDING_STARTS:
        return None
    if _get_active_runner() is not None or _has_pending_reload_resume():
        return _auto_follow_queue_interval()

    now = time.monotonic()
    ready_entries = []
    next_delay = None
    for key, entry in list(_AUTO_FOLLOW_PENDING_STARTS.items()):
        scene = bpy.data.scenes.get(str(entry.get("scene_name", "") or ""))
        node_tree = bpy.data.node_groups.get(str(entry.get("tree_name", "") or ""))
        start_node_name = str(entry.get("start_node_name", "") or "")
        if scene is None or _scene_flow_settings(scene) is None or node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            _AUTO_FOLLOW_PENDING_STARTS.pop(key, None)
            continue
        start_node = node_tree.nodes.get(start_node_name)
        if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeStart":
            _AUTO_FOLLOW_PENDING_STARTS.pop(key, None)
            continue
        if not bool(getattr(start_node, "auto_follow_enabled", False)):
            _AUTO_FOLLOW_PENDING_STARTS.pop(key, None)
            continue
        auto_order = int(getattr(start_node, "auto_order", entry.get("auto_order", 0)) or 0)
        entry["auto_order"] = auto_order
        first_dirty_at = float(entry.get("first_dirty_at", entry.get("last_dirty_at", now)))
        if bool(ignore_debounce) or bool(entry.get("ignore_debounce", False)):
            ready_at = float(first_dirty_at)
        else:
            debounce_seconds = _auto_follow_debounce_seconds(scene=scene, default_debounce_ms=300)
            ready_at = first_dirty_at + debounce_seconds
        if now >= ready_at:
            ready_entries.append((auto_order, first_dirty_at, key, scene, node_tree, start_node_name))
        else:
            remaining = max(0.01 if _is_animation_playing() else 0.05, ready_at - now)
            next_delay = remaining if next_delay is None else min(next_delay, remaining)

    if not ready_entries:
        if not _AUTO_FOLLOW_PENDING_STARTS:
            return None
        return next_delay if next_delay is not None else _auto_follow_queue_interval()

    # Keep older dirty batches ahead of newer ones so a lower-priority flow
    # cannot starve other pending auto flows simply by retriggering first.
    # Order is only used to sort within the same dirty wave.
    ready_entries.sort(key=lambda item: (item[1], item[0], item[2]))
    _auto_order, _dirty_at, key, scene, node_tree, start_node_name = ready_entries[0]
    entry = dict(_AUTO_FOLLOW_PENDING_STARTS.get(key) or {})
    playback_state = dict(entry.get("playback_state") or {})
    trigger_state = dict(entry.get("trigger_state") or {})
    try:
        _start_runner(
            node_tree,
            scene,
            start_node_name=start_node_name,
            ui_context={
                "playback_state": playback_state,
                "trigger_state": trigger_state,
            },
            auto_follow=True,
        )
        _ensure_resume_runner_timer()
    except Exception as exc:
        _log_auto_follow_start_error(scene, getattr(node_tree, "name", ""), start_node_name, exc)
    finally:
        _AUTO_FOLLOW_PENDING_STARTS.pop(key, None)
    return _auto_follow_queue_interval()


def _ensure_resume_runner_timer():
    global _RESUME_RUNNER_TIMER_ACTIVE
    if _RESUME_RUNNER_TIMER_ACTIVE:
        return

    def _timer():
        global _RESUME_RUNNER_TIMER_ACTIVE
        runner = _get_active_runner()
        if runner is None:
            _RESUME_RUNNER_TIMER_ACTIVE = False
            return None
        was_auto_follow = bool(getattr(runner, "auto_follow", False))
        try:
            _suspend_auto_follow_notifications()
            try:
                finished = runner.tick(max_immediate_steps=_runner_tick_step_budget(runner))
            finally:
                _resume_auto_follow_notifications()
        except Exception:
            _finish_active_runner_for_timer()
            _RESUME_RUNNER_TIMER_ACTIVE = False
            raise
        if not bool(getattr(runner, "auto_follow", False)):
            _tag_flow_node_editor_redraw(getattr(getattr(runner, "node_tree", None), "name", None))
            _tag_viewport_redraw()
        if finished:
            _finish_active_runner_for_timer()
            _RESUME_RUNNER_TIMER_ACTIVE = False
            if was_auto_follow and _AUTO_FOLLOW_PENDING_STARTS:
                _run_auto_follow_queue_now()
            return None
        return _runner_timer_interval(runner)

    _RESUME_RUNNER_TIMER_ACTIVE = True
    first_interval = _runner_timer_interval(_get_active_runner())
    if first_interval is None:
        first_interval = 0.01 if _is_animation_playing() else 0.02
    bpy.app.timers.register(_timer, first_interval=max(0.001, float(first_interval)))


from .flow_reload import (
    clear_pending_reload_resume,
    configure_reload_resume_callbacks,
    schedule_reload_resume,
    _consume_pending_reload_resume,
    _has_pending_reload_resume,
    _perform_reload_resume,
    _remove_resume_flow_after_load_handlers,
    _resume_flow_after_load,
    _resume_flow_from_checkpoint_payload,
)

def _capture_runtime_ui_context(context):
    snapshot = {}
    for key in ("window", "screen", "area", "region", "space_data", "view_layer"):
        value = getattr(context, key, None)
        if value is not None:
            snapshot[key] = value
    return snapshot


def _reset_resume_runner_timer_state():
    global _RESUME_RUNNER_TIMER_ACTIVE
    _RESUME_RUNNER_TIMER_ACTIVE = False


configure_reload_resume_callbacks(
    reset_resume_timer_state=_reset_resume_runner_timer_state,
    ensure_resume_runner_timer=_ensure_resume_runner_timer,
    capture_runtime_ui_context=_capture_runtime_ui_context,
    set_active_runner=_set_active_runner,
)


def _clear_auto_follow_state():
    global _AUTO_FOLLOW_TIMER_ACTIVE, _AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE, _AUTO_FOLLOW_TIMER_GENERATION, _AUTO_FOLLOW_PLAYBACK_TIMER_GENERATION, _AUTO_FOLLOW_SUSPEND_DEPTH, _AUTO_FOLLOW_IGNORE_UNTIL, _AUTO_FOLLOW_LAST_PLAY_STATE, _AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE, _AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE
    _AUTO_FOLLOW_PENDING_STARTS.clear()
    _mark_auto_follow_start_cache_dirty()
    _AUTO_FOLLOW_SCENE_EDGE_GUARD.clear()
    _AUTO_FOLLOW_POST_RUN_DEPSGRAPH_GUARD.clear()
    _AUTO_FOLLOW_SCENE_UPDATE_STATE.clear()
    _AUTO_FOLLOW_SCENE_UPDATE_END_PENDING.clear()
    _AUTO_FOLLOW_TIMER_ACTIVE = False
    _AUTO_FOLLOW_PLAYBACK_TIMER_ACTIVE = False
    _AUTO_FOLLOW_TIMER_GENERATION += 1
    _AUTO_FOLLOW_PLAYBACK_TIMER_GENERATION += 1
    _AUTO_FOLLOW_SUSPEND_DEPTH = 0
    _AUTO_FOLLOW_IGNORE_UNTIL = 0.0
    _AUTO_FOLLOW_LAST_PLAY_STATE = None
    _AUTO_FOLLOW_LAST_OBJECT_INTERACTION_MODE = ""
    _AUTO_FOLLOW_LAST_VIEWPORT_SHADING_MODE = ""


@persistent
def _reset_auto_follow_after_load(_dummy):
    _clear_auto_follow_state()
    _prime_auto_follow_playback_state()
    _prime_interaction_trigger_state()
    if _AUTO_FOLLOW_PLAYBACK_TIMER_ENABLED:
        _ensure_auto_follow_playback_timer()


@persistent
def _auto_follow_depsgraph_post(scene, _depsgraph):
    global _AUTO_FOLLOW_LAST_PLAY_STATE
    current_play_state = bool(_is_animation_playing())
    if current_play_state:
        # `On Play` belongs to the first frame-change callback. If a depsgraph
        # update arrives first while playback is starting, do not consume the
        # transition here or the pulse can be lost.
        return
    if _consume_post_run_depsgraph_guard(scene, _depsgraph):
        return
    just_paused = bool(_AUTO_FOLLOW_LAST_PLAY_STATE)
    _AUTO_FOLLOW_LAST_PLAY_STATE = False
    trigger_state = _mark_scene_update_activity(scene)
    playback_state = _playback_state_payload(
        playing=False,
        on_play=False,
        on_pause=just_paused,
    )
    _handle_auto_follow_scene_trigger(
        scene,
        prefer_immediate=True,
        playback_state=playback_state,
        trigger_state=trigger_state,
        ignore_debounce=True,
    )


def _handle_auto_follow_scene_trigger(scene, prefer_immediate=False, playback_state=None, trigger_state=None, ignore_debounce=False):
    if _AUTO_FOLLOW_SUSPEND_DEPTH > 0:
        return
    if float(time.monotonic()) < float(_AUTO_FOLLOW_IGNORE_UNTIL):
        return
    if scene is None or _scene_flow_settings(scene) is None:
        return
    _queue_auto_follow_for_scene(
        scene,
        playback_state=playback_state,
        trigger_state=trigger_state,
        ignore_debounce=bool(ignore_debounce),
    )
    if bool(prefer_immediate) and _run_auto_follow_queue_now(ignore_debounce=bool(ignore_debounce)):
        return
    if _AUTO_FOLLOW_PENDING_STARTS:
        _ensure_auto_follow_timer()


@persistent
def _auto_follow_frame_change_post(scene, _depsgraph=None):
    global _AUTO_FOLLOW_LAST_PLAY_STATE
    current_play_state = bool(_is_animation_playing())
    if _AUTO_FOLLOW_LAST_PLAY_STATE is None:
        _AUTO_FOLLOW_LAST_PLAY_STATE = current_play_state
    if not current_play_state:
        return
    on_play = bool(_AUTO_FOLLOW_LAST_PLAY_STATE is False)
    _AUTO_FOLLOW_LAST_PLAY_STATE = True
    if on_play:
        _AUTO_FOLLOW_SCENE_UPDATE_STATE.clear()
        _AUTO_FOLLOW_SCENE_UPDATE_END_PENDING.clear()
    _handle_auto_follow_scene_trigger(
        scene,
        prefer_immediate=True,
        playback_state=_playback_state_payload(
            playing=True,
            on_play=on_play,
            on_pause=False,
        ),
        trigger_state=_trigger_state_payload(),
        ignore_debounce=True,
    )


def _remove_auto_follow_handlers():
    depsgraph_handlers = getattr(bpy.app.handlers, "depsgraph_update_post", None)
    if depsgraph_handlers is not None:
        target_name = getattr(_auto_follow_depsgraph_post, "__name__", "_auto_follow_depsgraph_post")
        removable = [handler for handler in list(depsgraph_handlers) if getattr(handler, "__name__", "") == target_name]
        for handler in removable:
            try:
                depsgraph_handlers.remove(handler)
            except Exception:
                pass
    frame_change_handlers = getattr(bpy.app.handlers, "frame_change_post", None)
    if frame_change_handlers is not None:
        target_name = getattr(_auto_follow_frame_change_post, "__name__", "_auto_follow_frame_change_post")
        removable = [handler for handler in list(frame_change_handlers) if getattr(handler, "__name__", "") == target_name]
        for handler in removable:
            try:
                frame_change_handlers.remove(handler)
            except Exception:
                pass
    load_handlers = getattr(bpy.app.handlers, "load_post", None)
    if load_handlers is not None:
        target_name = getattr(_reset_auto_follow_after_load, "__name__", "_reset_auto_follow_after_load")
        removable = [handler for handler in list(load_handlers) if getattr(handler, "__name__", "") == target_name]
        for handler in removable:
            try:
                load_handlers.remove(handler)
            except Exception:
                pass


def set_auto_follow_playback_timer_enabled(enabled):
    global _AUTO_FOLLOW_PLAYBACK_TIMER_ENABLED
    _AUTO_FOLLOW_PLAYBACK_TIMER_ENABLED = bool(enabled)
    if _AUTO_FOLLOW_PLAYBACK_TIMER_ENABLED:
        _prime_auto_follow_playback_state()
        _prime_interaction_trigger_state()
        _ensure_auto_follow_playback_timer()


def register_handlers():
    _remove_resume_flow_after_load_handlers()
    _remove_auto_follow_handlers()
    bpy.app.handlers.load_post.append(_resume_flow_after_load)
    bpy.app.handlers.load_post.append(_reset_auto_follow_after_load)
    bpy.app.handlers.depsgraph_update_post.append(_auto_follow_depsgraph_post)
    bpy.app.handlers.frame_change_post.append(_auto_follow_frame_change_post)
    set_auto_follow_playback_timer_enabled(True)


def unregister_handlers():
    set_auto_follow_playback_timer_enabled(False)
    clear_pending_reload_resume()
    _clear_auto_follow_state()
    _remove_resume_flow_after_load_handlers()
    _remove_auto_follow_handlers()

