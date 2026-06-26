import bpy
import blf
import time
from bpy.app.translations import pgettext_iface as iface_

from ..i18n import af_iface
from ..runtime_bake import (
    _geometry_bake_cache_status_from_node,
    _physics_bake_cache_status_from_node,
    _read_geometry_bake_last_bake_state,
)
from ..runtime_runner.core import FlowRunner
from ..runtime_runner.core.active import get_active_runner
from ..runtime_state.cache import (
    _property_package_bake_cache_status_from_node,
    _fallback_group_instance_stored_property_package,
    _read_stored_property_package_direct,
    _summarize_property_package,
)
from .preferences import _ui_pref_enabled
from .overlay_context import (
    _iter_visible_nodes,
    _node_editor_group_path,
    _node_editor_group_path_labels,
    _node_editor_root_tree,
    _node_editor_zoom_factor,
    _ui_scale_factor,
)
from .overlay_drawing import (
    _draw_pixel_rounded_rect,
    _node_bounds,
)
from .sidebar import _runtime_status_label


_STORE_CHIP_FONT_ID = 0
_CHIP_STATE_CACHE = {}
_CHIP_STATE_CACHE_LAST_PRUNE = 0.0
_CHIP_CACHE_TTL_SEC = 0.12
_CHIP_CACHE_PRUNE_INTERVAL_SEC = 1.0
_CHIP_CACHE_MAX_ITEMS = 1024


def _active_runner():
    return get_active_runner()


def _cache_pointer_token(value):
    if value is None:
        return 0
    try:
        return int(value.as_pointer())
    except Exception:
        return id(value)


def _group_path_cache_key(group_path):
    return tuple(
        (
            str(item.get("tree_name", "") or ""),
            str(item.get("node_name", "") or ""),
        )
        for item in list(group_path or [])
        if isinstance(item, dict)
    )


def _prune_chip_state_cache(now=None):
    global _CHIP_STATE_CACHE_LAST_PRUNE
    now = float(time.monotonic() if now is None else now)
    if (
        len(_CHIP_STATE_CACHE) < _CHIP_CACHE_MAX_ITEMS
        and (now - _CHIP_STATE_CACHE_LAST_PRUNE) < _CHIP_CACHE_PRUNE_INTERVAL_SEC
    ):
        return
    expired_keys = [
        key
        for key, entry in list(_CHIP_STATE_CACHE.items())
        if float(entry[0]) <= now
    ]
    for key in expired_keys:
        _CHIP_STATE_CACHE.pop(key, None)
    if len(_CHIP_STATE_CACHE) > _CHIP_CACHE_MAX_ITEMS:
        _CHIP_STATE_CACHE.clear()
    _CHIP_STATE_CACHE_LAST_PRUNE = now


def _chip_cached_value(cache_key, compute_fn, ttl=_CHIP_CACHE_TTL_SEC):
    now = time.monotonic()
    _prune_chip_state_cache(now)
    cached = _CHIP_STATE_CACHE.get(cache_key)
    if cached is not None and float(cached[0]) > now:
        return cached[1]
    value = compute_fn()
    _CHIP_STATE_CACHE[cache_key] = (now + float(ttl), value)
    return value
def _store_chip_palette(store_mode, has_package):
    if not has_package:
        if store_mode == "OUTPUT_ONLY":
            return (0.42, 0.16, 0.14, 0.78), (0.68, 0.28, 0.24, 0.88), (1.0, 0.92, 0.90, 1.0)
        return (0.22, 0.22, 0.22, 0.78), (0.44, 0.44, 0.44, 0.88), (0.90, 0.90, 0.90, 1.0)
    if store_mode == "OUTPUT_ONLY":
        return (0.46, 0.31, 0.12, 0.78), (0.72, 0.49, 0.20, 0.88), (1.0, 0.97, 0.90, 1.0)
    return (0.11, 0.41, 0.34, 0.78), (0.22, 0.68, 0.54, 0.88), (0.92, 1.0, 0.97, 1.0)


def _error_chip_palette():
    return (0.46, 0.14, 0.12, 0.82), (0.82, 0.26, 0.22, 0.94), (1.0, 0.94, 0.92, 1.0)


def _localized_summary_title(summary):
    if not isinstance(summary, dict):
        return ""
    title = str(summary.get("title", "") or "").strip()
    if not title:
        return ""
    localized = af_iface(title)
    if localized != title:
        return localized
    for suffix in ("Settings", "Snapshot", "Target"):
        suffix_token = f" {suffix}"
        if not title.endswith(suffix_token):
            continue
        prefix = title[: -len(suffix_token)].strip()
        if prefix:
            return f"{af_iface(prefix)} {af_iface(suffix)}"
    return localized


def _clip_text_to_width(font_id, text, max_width, ellipsis="..."):
    text = str(text or "")
    if max_width <= 0.0:
        return ""
    if not text:
        return text
    if blf.dimensions(font_id, text)[0] <= max_width:
        return text

    ellipsis_width = blf.dimensions(font_id, ellipsis)[0]
    if ellipsis_width >= max_width:
        return ellipsis

    available_width = max_width - ellipsis_width
    clipped = text
    while clipped and blf.dimensions(font_id, clipped)[0] > available_width:
        clipped = clipped[:-1]
    return f"{clipped}{ellipsis}" if clipped else ellipsis


def _text_dimensions_cached(font_id, text, cache):
    key = (int(font_id), str(text or ""))
    size = cache.get(key)
    if size is None:
        size = tuple(float(value) for value in blf.dimensions(font_id, str(text or "")))
        cache[key] = size
    return size


def _clip_text_to_width_cached(font_id, text, max_width, dimensions_cache, clip_cache, ellipsis="..."):
    text = str(text or "")
    rounded_width = round(float(max_width), 3)
    key = (int(font_id), text, rounded_width, str(ellipsis or ""))
    clipped = clip_cache.get(key)
    if clipped is not None:
        return clipped
    if rounded_width <= 0.0:
        clip_cache[key] = ""
        return ""
    if not text:
        clip_cache[key] = text
        return text
    text_width = _text_dimensions_cached(font_id, text, dimensions_cache)[0]
    if text_width <= rounded_width:
        clip_cache[key] = text
        return text
    ellipsis_width = _text_dimensions_cached(font_id, ellipsis, dimensions_cache)[0]
    if ellipsis_width >= rounded_width:
        clip_cache[key] = ellipsis
        return ellipsis
    available_width = rounded_width - ellipsis_width
    clipped = text
    while clipped and _text_dimensions_cached(font_id, clipped, dimensions_cache)[0] > available_width:
        clipped = clipped[:-1]
    clipped = f"{clipped}{ellipsis}" if clipped else ellipsis
    clip_cache[key] = clipped
    return clipped


def _draw_top_status_chip_for_node(
    node,
    chip_text,
    palette,
    chip_scale,
    region,
    view2d,
    dimensions_cache,
    clip_cache,
    *,
    right_text="",
    right_text_color=None,
):
    if node is None or not chip_text:
        return
    fill_color, outline_color, text_color = palette
    _text_width, text_height = _text_dimensions_cached(_STORE_CHIP_FONT_ID, chip_text, dimensions_cache)
    x1, y1, x2, _y2 = _node_bounds(node, pad=0.0)
    left_anchor = view2d.view_to_region(x1, y1, clip=False)
    right_anchor = view2d.view_to_region(x2, y1, clip=False)
    if left_anchor is None or right_anchor is None:
        return
    node_left_x, node_top_y = float(left_anchor[0]), float(left_anchor[1])
    node_right_x = float(right_anchor[0])
    hidden_chip_offset_y = (4.0 * chip_scale) if bool(getattr(node, "hide", False)) else 0.0
    chip_anchor_top_y = float(node_top_y) + hidden_chip_offset_y
    pad_x = 10.0 * chip_scale
    pad_y = 4.0 * chip_scale
    side_margin = 8.0 * _ui_scale_factor()
    chip_left = node_left_x + side_margin
    chip_right = node_right_x - side_margin
    chip_width = chip_right - chip_left
    chip_height = max(22.0 * chip_scale, float(text_height) + (pad_y * 2.0) + (3.0 * chip_scale))
    intrusion_y = max(6.0, 6.0 * chip_scale)
    chip_bottom = chip_anchor_top_y - intrusion_y
    chip_top = chip_bottom + chip_height
    right_text = str(right_text or "").strip()
    right_text_width = 0.0
    right_gap_x = 0.0
    if right_text:
        right_text_width = _text_dimensions_cached(_STORE_CHIP_FONT_ID, right_text, dimensions_cache)[0]
        right_gap_x = max(6.0, 6.0 * chip_scale)
    text_max_width = max(0.0, chip_width - (pad_x * 2.0) - right_text_width - right_gap_x)
    clipped_chip_text = _clip_text_to_width_cached(
        _STORE_CHIP_FONT_ID,
        chip_text,
        text_max_width,
        dimensions_cache,
        clip_cache,
    )
    _draw_pixel_rounded_rect(
        chip_left,
        chip_bottom,
        chip_right,
        chip_top,
        fill_color,
        outline_color=outline_color,
        line_width=1.0,
        radius=max(3.0 * chip_scale, 5.0),
    )
    blf.color(_STORE_CHIP_FONT_ID, *text_color)
    blf.position(_STORE_CHIP_FONT_ID, chip_left + pad_x, chip_anchor_top_y + pad_y + (1.0 * chip_scale), 0)
    blf.draw(_STORE_CHIP_FONT_ID, clipped_chip_text)
    if right_text:
        clipped_right_text = _clip_text_to_width_cached(
            _STORE_CHIP_FONT_ID,
            right_text,
            max(0.0, chip_width - (pad_x * 2.0)),
            dimensions_cache,
            clip_cache,
        )
        clipped_right_width = _text_dimensions_cached(_STORE_CHIP_FONT_ID, clipped_right_text, dimensions_cache)[0]
        right_draw_x = chip_right - pad_x - clipped_right_width
        blf.color(_STORE_CHIP_FONT_ID, *(right_text_color or (1.0, 0.94, 0.68, 1.0)))
        blf.position(_STORE_CHIP_FONT_ID, right_draw_x, chip_anchor_top_y + pad_y + (1.0 * chip_scale), 0)
        blf.draw(_STORE_CHIP_FONT_ID, clipped_right_text)


def _draw_output_row_status_chip(node, output_row_index, chip_text, palette, chip_scale, view2d, dimensions_cache, clip_cache):
    if node is None or not chip_text:
        return
    fill_color, outline_color, text_color = palette
    text_width, text_height = _text_dimensions_cached(_STORE_CHIP_FONT_ID, chip_text, dimensions_cache)
    _x1, _y1, x2, _y2 = _node_bounds(node, pad=0.0)
    pad_x = 8.0 * chip_scale
    pad_y = 3.0 * chip_scale
    intrusion_x = max(12.0, 14.0 * chip_scale)
    chip_width = intrusion_x + float(text_width) + (pad_x * 2.0)
    chip_height = max(16.0 * chip_scale, float(text_height) + (pad_y * 2.0))
    row_center_view_y = _output_socket_center_view_y(node, output_row_index)
    anchor = view2d.view_to_region(float(x2), row_center_view_y, clip=False)
    if anchor is None:
        return
    node_right_x, row_center_y = float(anchor[0]), float(anchor[1])
    row_center_y += 3.0 * chip_scale
    chip_left = node_right_x - intrusion_x
    chip_bottom = row_center_y - (chip_height * 0.5)
    chip_top = chip_bottom + chip_height
    clipped_chip_text = _clip_text_to_width_cached(
        _STORE_CHIP_FONT_ID,
        chip_text,
        max(0.0, chip_width - intrusion_x - (pad_x * 2.0)),
        dimensions_cache,
        clip_cache,
    )

    _draw_pixel_rounded_rect(
        chip_left,
        chip_bottom,
        chip_left + chip_width,
        chip_top,
        fill_color,
        outline_color=outline_color,
        line_width=1.0,
        radius=max(2.5 * chip_scale, 4.0),
    )
    blf.color(_STORE_CHIP_FONT_ID, *text_color)
    text_gap_x = 3.0 * chip_scale
    clipped_width, clipped_height = _text_dimensions_cached(_STORE_CHIP_FONT_ID, clipped_chip_text, dimensions_cache)
    text_vertical_nudge_y = 1.5 * chip_scale
    text_y = row_center_y - (float(clipped_height) * 0.5) + text_vertical_nudge_y
    blf.position(_STORE_CHIP_FONT_ID, node_right_x + pad_x + text_gap_x, text_y, 0)
    blf.draw(_STORE_CHIP_FONT_ID, clipped_chip_text)


def _store_chip_text(node, summary):
    store_mode = str(getattr(node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT")
    if summary is None or summary.get("title", "Empty") == "Empty":
        return f"{af_iface('Output')} - {af_iface('Empty')}" if store_mode == "OUTPUT_ONLY" else af_iface("Empty")
    prefix = af_iface("Output") if store_mode == "OUTPUT_ONLY" else af_iface("Stored")
    return f"{prefix} - {_localized_summary_title(summary)}"


def _group_output_chip_text_and_palette(source_node, package, summary):
    has_package = bool(package is not None and summary is not None and summary.get("title", "Empty") != "Empty")
    if source_node is not None and getattr(source_node, "bl_idname", "") == "AFNodeStorePropertyPackage":
        store_mode = str(getattr(source_node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT")
        if not has_package:
            chip_text = af_iface("Empty")
        else:
            chip_text = af_iface("Output") if store_mode == "OUTPUT_ONLY" else af_iface("Stored")
        return chip_text, _store_chip_palette(store_mode, has_package)
    if not has_package:
        return af_iface("Empty"), _store_chip_palette("STORE_AND_OUTPUT", False)
    return af_iface("Ready"), _store_chip_palette("STORE_AND_OUTPUT", True)


def _resolve_group_output_property_package_chip(runner, group_node, output_socket, group_path):
    if runner is None or group_node is None or output_socket is None:
        return None

    previous_group_path = list(getattr(runner, "current_group_path", []))
    try:
        runner.current_group_path = list(group_path or [])
        source_node, _source_socket, resolved_group_path = runner._trace_output_source(
            group_node,
            output_socket,
            list(group_path or []),
            "property_package",
        )
        resolved_group_path = list(resolved_group_path or [])
        runner.current_group_path = list(resolved_group_path)
        if source_node is not None and getattr(source_node, "bl_idname", "") == "AFNodeStorePropertyPackage":
            package = runner._read_stored_property_package(source_node)
        else:
            package = runner._get_output_from_source(group_node, output_socket, "property_package", list(group_path or []))
    except Exception:
        return None
    finally:
        runner.current_group_path = previous_group_path

    summary = _summarize_property_package(package)
    chip_text, palette = _group_output_chip_text_and_palette(source_node, package, summary)
    return {
        "text": chip_text,
        "palette": palette,
        "summary": summary,
        "source_node": source_node,
        "has_package": bool(package is not None and summary.get("title", "Empty") != "Empty"),
    }


def _cached_bake_chip_status(kind, node):
    cache_key = ("bake_status", str(kind or ""), _cache_pointer_token(node))
    if kind == "geometry":
        compute_fn = lambda: _geometry_bake_cache_status_from_node(node)
    elif kind == "physics":
        compute_fn = lambda: _physics_bake_cache_status_from_node(node)
    else:
        compute_fn = lambda: _property_package_bake_cache_status_from_node(node)
    return _chip_cached_value(cache_key, compute_fn)


def _geometry_bake_local_unlinked_input_int(node, socket_name):
    socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)(socket_name)
    if socket is None or bool(getattr(socket, "is_linked", False)):
        return None
    try:
        return int(getattr(socket, "default_value", 0))
    except Exception:
        return None


def _geometry_bake_current_node_settings_state(node):
    use_custom_path = bool(getattr(node, "use_custom_path", False))
    use_custom_range = bool(getattr(node, "use_custom_simulation_frame_range", False))
    frame_start_local = _geometry_bake_local_unlinked_input_int(node, "Frame Start") if use_custom_range else None
    frame_end_local = _geometry_bake_local_unlinked_input_int(node, "Frame End") if use_custom_range else None
    return {
        "task_path": str(getattr(node, "bake_task_path", "") or "").strip(),
        "bake_mode": str(getattr(node, "bake_mode", "") or "").strip().upper(),
        "bake_target": str(getattr(node, "bake_target", "") or "").strip().upper(),
        "use_custom_path": bool(use_custom_path),
        "directory": str(getattr(node, "directory", "") or "").strip() if use_custom_path else "",
        "use_custom_simulation_frame_range": bool(use_custom_range),
        "frame_start_local": int(frame_start_local) if frame_start_local is not None else None,
        "frame_end_local": int(frame_end_local) if frame_end_local is not None else None,
    }


def _geometry_bake_normalize_settings_state(raw_state):
    if not isinstance(raw_state, dict):
        return None
    use_custom_path = bool(raw_state.get("use_custom_path", False))
    use_custom_range = bool(raw_state.get("use_custom_simulation_frame_range", False))
    return {
        "task_path": str(raw_state.get("task_path", "") or "").strip(),
        "bake_mode": str(raw_state.get("bake_mode", "") or "").strip().upper(),
        "bake_target": str(raw_state.get("bake_target", "") or "").strip().upper(),
        "use_custom_path": bool(use_custom_path),
        "directory": str(raw_state.get("directory", "") or "").strip() if use_custom_path else "",
        "use_custom_simulation_frame_range": bool(use_custom_range),
        "frame_start_local": (
            int(raw_state.get("frame_start_local", raw_state.get("frame_start", 0)) or 0)
            if use_custom_range and raw_state.get("frame_start_local", raw_state.get("frame_start")) is not None
            else None
        ),
        "frame_end_local": (
            int(raw_state.get("frame_end_local", raw_state.get("frame_end", 0)) or 0)
            if use_custom_range and raw_state.get("frame_end_local", raw_state.get("frame_end")) is not None
            else None
        ),
    }


def _geometry_bake_node_is_expired(node, runner):
    del runner
    if node is None or getattr(node, "bl_idname", "") != "AFNodeBakeTask":
        return False
    last_bake_state = _read_geometry_bake_last_bake_state(node)
    if not isinstance(last_bake_state, dict):
        return False
    current_settings_state = _geometry_bake_current_node_settings_state(node)
    stored_settings_state = _geometry_bake_normalize_settings_state(last_bake_state.get("node_settings_state"))
    if stored_settings_state is not None:
        return current_settings_state != stored_settings_state
    current_task_path = str(getattr(node, "bake_task_path", "") or "").strip()
    last_task_path = str(last_bake_state.get("task_path", "") or "").strip()
    if current_task_path != last_task_path:
        return True
    current_bake_mode = str(getattr(node, "bake_mode", "") or "").strip().upper()
    last_bake_mode = str(last_bake_state.get("bake_mode", "") or "").strip().upper()
    if current_bake_mode != last_bake_mode:
        return True
    current_bake_target = str(getattr(node, "bake_target", "") or "").strip().upper()
    last_bake_target = str(
        last_bake_state.get("node_bake_target", last_bake_state.get("bake_target", "")) or ""
    ).strip().upper()
    if current_bake_target != last_bake_target:
        return True
    current_use_custom_path = bool(getattr(node, "use_custom_path", False))
    last_use_custom_path = bool(last_bake_state.get("use_custom_path", False))
    if current_use_custom_path != last_use_custom_path:
        return True
    if current_use_custom_path:
        current_directory = str(getattr(node, "directory", "") or "").strip()
        last_directory = str(last_bake_state.get("directory", "") or "").strip()
        if current_directory != last_directory:
            return True
    current_use_custom_range = bool(getattr(node, "use_custom_simulation_frame_range", False))
    last_use_custom_range = bool(last_bake_state.get("use_custom_simulation_frame_range", False))
    if current_use_custom_range != last_use_custom_range:
        return True
    if current_use_custom_range and last_use_custom_range:
        current_frame_start = _geometry_bake_local_unlinked_input_int(node, "Frame Start")
        current_frame_end = _geometry_bake_local_unlinked_input_int(node, "Frame End")
        if current_frame_start is not None and current_frame_start != int(last_bake_state.get("frame_start", current_frame_start) or current_frame_start):
            return True
        if current_frame_end is not None and current_frame_end != int(last_bake_state.get("frame_end", current_frame_end) or current_frame_end):
            return True
    return False


def _cached_geometry_bake_chip_data(runner, node, root_tree, group_path):
    cache_key = (
        "geometry_bake_chip",
        _cache_pointer_token(root_tree),
        _group_path_cache_key(group_path),
        _cache_pointer_token(node),
        str(getattr(node, "bake_task_path", "") or ""),
        str(getattr(node, "bake_mode", "") or ""),
        str(getattr(node, "bake_target", "") or ""),
        bool(getattr(node, "use_custom_path", False)),
        str(getattr(node, "directory", "") or ""),
        bool(getattr(node, "use_custom_simulation_frame_range", False)),
        _geometry_bake_local_unlinked_input_int(node, "Frame Start"),
        _geometry_bake_local_unlinked_input_int(node, "Frame End"),
    )

    def _compute():
        cache_status = _geometry_bake_cache_status_from_node(node)
        if cache_status is None:
            return None
        return {
            "cache_status": cache_status,
            "expired": bool(_geometry_bake_node_is_expired(node, runner)),
        }

    return _chip_cached_value(cache_key, _compute)


def _cached_store_package_chip_data(runner, node, root_tree, group_path):
    cache_key = (
        "store_package_chip",
        _cache_pointer_token(root_tree),
        _group_path_cache_key(group_path),
        _cache_pointer_token(node),
        str(getattr(node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT"),
    )

    def _compute():
        store_mode = str(getattr(node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT")
        package = None
        try:
            if runner is not None:
                package = runner._read_stored_property_package(node)
        except Exception:
            package = None
        if package is None:
            package = _read_stored_property_package_direct(node)
        if package is None and not group_path:
            package = _fallback_group_instance_stored_property_package(node)
        summary = _summarize_property_package(package)
        return {
            "chip_text": _store_chip_text(node, summary),
            "palette": _store_chip_palette(store_mode, package is not None),
        }

    return _chip_cached_value(cache_key, _compute)


def _resolve_read_property_package_chip_target(node):
    if node is None or getattr(node, "bl_idname", "") != "AFNodeReadPropertyPackage":
        return None
    node_tree = getattr(node, "id_data", None)
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None

    target_store_id = str(getattr(node, "target_store_id", "") or "").strip()
    if target_store_id == "0":
        target_store_id = ""
    target_store_node_name = str(getattr(node, "target_store_node_name", "") or "").strip()

    if target_store_id:
        for candidate in getattr(node_tree, "nodes", []):
            if str(getattr(candidate, "bl_idname", "") or "") != "AFNodeStorePropertyPackage":
                continue
            if str(getattr(candidate, "store_asset_id", "") or "").strip() == target_store_id:
                return candidate

    if target_store_node_name:
        candidate = getattr(node_tree, "nodes", {}).get(target_store_node_name)
        if candidate is not None and str(getattr(candidate, "bl_idname", "") or "") == "AFNodeStorePropertyPackage":
            return candidate
    return None


def _cached_read_package_chip_data(runner, node, root_tree, group_path):
    target_store_node = _resolve_read_property_package_chip_target(node)
    if target_store_node is None:
        return None
    return _cached_store_package_chip_data(runner, target_store_node, root_tree, group_path)


def _cached_group_output_chip_data(runner, group_node, output_socket, root_tree, group_path):
    cache_key = (
        "group_output_chip",
        _cache_pointer_token(root_tree),
        _group_path_cache_key(group_path),
        _cache_pointer_token(group_node),
        str(getattr(output_socket, "identifier", "") or ""),
        str(getattr(output_socket, "name", "") or ""),
    )
    return _chip_cached_value(
        cache_key,
        lambda: _resolve_group_output_property_package_chip(runner, group_node, output_socket, group_path),
    )


def _visible_output_sockets(node):
    return [
        socket
        for socket in getattr(node, "outputs", [])
        if not bool(getattr(socket, "hide", False))
    ]


def _output_socket_center_view_y(node, row_index):
    ui_scale = _ui_scale_factor()
    _x1, y1, _x2, _y2 = _node_bounds(node, pad=0.0)
    socket_row_top_offset = 37.0 * ui_scale
    socket_row_step = 22.5 * ui_scale
    return float(y1) - socket_row_top_offset - (float(row_index) * socket_row_step)


def _gn_bake_chip_text(cache_status):
    if not isinstance(cache_status, dict):
        return ""
    if bool(cache_status.get("invalid", False)):
        return iface_("Invalid Target")
    source = str(cache_status.get("source", "") or "")
    if source == "DISK":
        baked_label = af_iface("Disk")
    elif source == "ACTION":
        baked_label = iface_("Recorded")
    elif source == "PACKED_TRACKED":
        baked_label = iface_("Packed")
    elif source == "MEMORY":
        baked_label = iface_("Memory")
    else:
        baked_label = iface_("Baked")
    frame_range = cache_status.get("frame_range")
    if isinstance(frame_range, (list, tuple)) and len(frame_range) >= 2:
        frame_start = int(frame_range[0])
        frame_end = int(frame_range[1])
        return f"{baked_label} {frame_start} - {frame_end}"
    if bool(cache_status.get("has_cache", False)):
        return baked_label
    return iface_("Empty Cache")


def _draw_property_package_backdrop_tags(node_tree):
    if not _ui_pref_enabled("show_property_status_chips", True):
        return
    draw_bake_status_chips = _ui_pref_enabled("show_bake_status_chips", True)
    draw_stored_package_chips = _ui_pref_enabled("show_stored_package_chips", True)
    draw_group_output_package_chips = _ui_pref_enabled("show_group_output_package_chips", True)
    if not (draw_bake_status_chips or draw_stored_package_chips or draw_group_output_package_chips):
        return
    region = getattr(bpy.context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return

    ui_scale = _ui_scale_factor()
    zoom_factor = _node_editor_zoom_factor(region, view2d)
    chip_scale = ui_scale * zoom_factor
    visible_nodes = list(_iter_visible_nodes(node_tree, region=region, view2d=view2d, margin=96.0))
    if not visible_nodes:
        return
    visible_node_types = {str(getattr(node, "bl_idname", "") or "") for node in visible_nodes}
    has_visible_store_nodes = draw_stored_package_chips and (
        "AFNodeStorePropertyPackage" in visible_node_types
        or "AFNodeReadPropertyPackage" in visible_node_types
    )
    has_visible_group_nodes = draw_group_output_package_chips and "AFNodeGroup" in visible_node_types
    need_runner_context = bool(has_visible_store_nodes or has_visible_group_nodes)
    root_tree = _node_editor_root_tree(bpy.context, node_tree) if need_runner_context else None
    group_path = _node_editor_group_path(bpy.context) if need_runner_context else []
    active_runner = _active_runner() if need_runner_context else None
    runner = None
    if active_runner is not None and getattr(active_runner, "node_tree", None) == root_tree:
        runner = active_runner
    elif has_visible_group_nodes or (has_visible_store_nodes and bool(group_path)):
        scene = getattr(bpy.context, "scene", None)
        runner = FlowRunner(root_tree, scene) if scene is not None and root_tree is not None else None

    previous_group_path = list(getattr(runner, "current_group_path", [])) if runner is not None else []
    if runner is not None:
        runner.current_group_path = list(group_path)

    blf.size(_STORE_CHIP_FONT_ID, max(1, int(round(11 * chip_scale))))
    dimensions_cache = {}
    clip_cache = {}
    try:
        for node in visible_nodes:
            try:
                node_type = str(getattr(node, "bl_idname", "") or "")
                if draw_bake_status_chips and node_type == "AFNodeBakeTask":
                    try:
                        chip_data = _cached_geometry_bake_chip_data(runner, node, root_tree, group_path)
                    except Exception:
                        chip_data = None
                    if isinstance(chip_data, dict):
                        cache_status = chip_data.get("cache_status")
                        chip_text = _gn_bake_chip_text(cache_status)
                        if chip_text:
                            palette = _error_chip_palette() if bool(cache_status.get("invalid", False)) else _store_chip_palette("STORE_AND_OUTPUT", bool(cache_status.get("has_cache", False)))
                            right_text = ""
                            right_text_color = None
                            if not bool(cache_status.get("invalid", False)) and bool(chip_data.get("expired", False)):
                                right_text = af_iface("Expired")
                                right_text_color = (1.0, 0.92, 0.66, 1.0)
                            _draw_top_status_chip_for_node(
                                node,
                                chip_text,
                                palette,
                                chip_scale,
                                region,
                                view2d,
                                dimensions_cache,
                                clip_cache,
                                right_text=right_text,
                                right_text_color=right_text_color,
                            )
                    continue

                if draw_bake_status_chips and node_type == "AFNodePhysicsBakeSettings":
                    try:
                        cache_status = _cached_bake_chip_status("physics", node)
                    except Exception:
                        cache_status = None
                    if cache_status is not None:
                        chip_text = _gn_bake_chip_text(cache_status)
                        if chip_text:
                            palette = _error_chip_palette() if bool(cache_status.get("invalid", False)) else _store_chip_palette("STORE_AND_OUTPUT", bool(cache_status.get("has_cache", False)))
                            _draw_top_status_chip_for_node(node, chip_text, palette, chip_scale, region, view2d, dimensions_cache, clip_cache)
                    continue

                if draw_bake_status_chips and node_type == "AFNodePropertyPackageBakeTarget":
                    try:
                        cache_status = _cached_bake_chip_status("property_package_bake", node)
                    except Exception:
                        cache_status = None
                    if cache_status is not None:
                        chip_text = _gn_bake_chip_text(cache_status)
                        if chip_text:
                            palette = _error_chip_palette() if bool(cache_status.get("invalid", False)) else _store_chip_palette("STORE_AND_OUTPUT", bool(cache_status.get("has_cache", False)))
                            _draw_top_status_chip_for_node(node, chip_text, palette, chip_scale, region, view2d, dimensions_cache, clip_cache)
                    continue

                if draw_stored_package_chips and node_type == "AFNodeStorePropertyPackage":
                    try:
                        chip_data = _cached_store_package_chip_data(runner, node, root_tree, group_path)
                    except Exception:
                        chip_data = None
                    if not isinstance(chip_data, dict):
                        continue
                    chip_text = str(chip_data.get("chip_text", "") or "")
                    palette = chip_data.get("palette", _store_chip_palette("STORE_AND_OUTPUT", False))
                    _draw_top_status_chip_for_node(node, chip_text, palette, chip_scale, region, view2d, dimensions_cache, clip_cache)
                    continue

                if draw_stored_package_chips and node_type == "AFNodeReadPropertyPackage":
                    try:
                        chip_data = _cached_read_package_chip_data(runner, node, root_tree, group_path)
                    except Exception:
                        chip_data = None
                    if not isinstance(chip_data, dict):
                        continue
                    chip_text = str(chip_data.get("chip_text", "") or "")
                    palette = chip_data.get("palette", _store_chip_palette("STORE_AND_OUTPUT", False))
                    _draw_top_status_chip_for_node(node, chip_text, palette, chip_scale, region, view2d, dimensions_cache, clip_cache)
                    continue

                if draw_group_output_package_chips and node_type == "AFNodeGroup" and runner is not None and not bool(getattr(node, "hide", False)):
                    property_outputs = [
                        (row_index, socket)
                        for row_index, socket in enumerate(_visible_output_sockets(node))
                        if str(getattr(socket, "bl_idname", "") or "") == "AFSocketPropertyPackage"
                    ]
                    if not property_outputs:
                        continue
                    for output_row_index, output_socket in property_outputs:
                        chip_info = _cached_group_output_chip_data(
                            runner,
                            node,
                            output_socket,
                            root_tree,
                            group_path,
                        )
                        if chip_info is None:
                            continue
                        chip_text = str(chip_info.get("text", "") or "")
                        palette = chip_info["palette"]
                        _draw_output_row_status_chip(
                            node,
                            output_row_index,
                            chip_text,
                            palette,
                            chip_scale,
                            view2d,
                            dimensions_cache,
                            clip_cache,
                        )
            except Exception:
                continue
    finally:
        if runner is not None:
            runner.current_group_path = previous_group_path


def _draw_run_mode_chip(scene):
    chip_spec = _run_mode_chip_spec(scene)
    if chip_spec is None:
        return None
    return _draw_top_left_overlay_chip(
        chip_spec["text"],
        chip_spec["fill_color"],
        chip_spec["outline_color"],
        chip_spec["text_color"],
    )


def _run_mode_chip_spec(scene):
    if not _ui_pref_enabled("show_run_mode_chip", True):
        return None
    if scene is None:
        return None
    settings = getattr(scene, "af_flow_settings", None)
    if settings is None:
        return None
    run_mode = str(getattr(settings, "run_mode", "NORMAL") or "NORMAL")
    runtime_status = str(getattr(settings, "runtime_status", "IDLE") or "IDLE")
    active_statuses = {"PRECHECK", "RUNNING", "WAITING", "RELOADING"}
    show_active_status = runtime_status in active_statuses
    show_mode_chip = run_mode in {"DRY_RUN", "FLOW_TEST"}
    if not show_active_status and not show_mode_chip:
        return None

    status_label = af_iface(_runtime_status_label(runtime_status)) if show_active_status else ""
    if run_mode == "FLOW_TEST":
        chip_text = f"{af_iface('Flow Test')} - {status_label}" if show_active_status else af_iface("Flow Test")
        fill_color = (0.12, 0.28, 0.34, 0.92)
        outline_color = (0.44, 0.82, 0.90, 0.98)
        text_color = (0.94, 0.99, 1.0, 1.0)
    elif run_mode == "DRY_RUN":
        chip_text = f"{af_iface('Dry Run')} - {status_label}" if show_active_status else af_iface("Dry Run")
        fill_color = (0.46, 0.31, 0.12, 0.92)
        outline_color = (0.78, 0.54, 0.22, 0.98)
        text_color = (1.0, 0.97, 0.90, 1.0)
    elif runtime_status == "PRECHECK":
        chip_text = status_label
        fill_color = (0.16, 0.25, 0.38, 0.92)
        outline_color = (0.40, 0.60, 0.90, 0.98)
        text_color = (0.94, 0.97, 1.0, 1.0)
    elif runtime_status == "WAITING":
        chip_text = status_label
        fill_color = (0.14, 0.30, 0.38, 0.92)
        outline_color = (0.34, 0.72, 0.88, 0.98)
        text_color = (0.92, 0.99, 1.0, 1.0)
    elif runtime_status == "RELOADING":
        chip_text = status_label
        fill_color = (0.20, 0.32, 0.18, 0.92)
        outline_color = (0.52, 0.82, 0.42, 0.98)
        text_color = (0.95, 1.0, 0.92, 1.0)
    else:
        chip_text = status_label
        fill_color = (0.16, 0.33, 0.20, 0.92)
        outline_color = (0.42, 0.82, 0.54, 0.98)
        text_color = (0.94, 1.0, 0.95, 1.0)

    return {
        "text": chip_text,
        "fill_color": fill_color,
        "outline_color": outline_color,
        "text_color": text_color,
    }


def _draw_top_left_overlay_chip(
    chip_text,
    fill_color,
    outline_color,
    text_color,
    *,
    top_y=None,
    font_size=12.0,
):
    region = getattr(bpy.context, "region", None)
    if region is None or getattr(region, "type", "") != "WINDOW":
        return None

    ui_scale = _ui_scale_factor()
    chip_scale = ui_scale
    chip_text = str(chip_text or "").strip()
    if not chip_text:
        return None
    blf.size(_STORE_CHIP_FONT_ID, max(1, int(round(float(font_size) * chip_scale))))
    max_text_width = max(64.0, float(region.width) - (24.0 * chip_scale))
    clipped_text = _clip_text_to_width(_STORE_CHIP_FONT_ID, chip_text, max_text_width)
    text_width, text_height = blf.dimensions(_STORE_CHIP_FONT_ID, clipped_text)
    pad_x = 11.0 * chip_scale
    pad_y = 5.0 * chip_scale
    chip_width = float(text_width) + (pad_x * 2.0)
    chip_height = max(22.0 * chip_scale, float(text_height) + (pad_y * 2.0))
    margin_x = 12.0 * chip_scale
    margin_y = 12.0 * chip_scale
    chip_left = margin_x
    chip_top = float(top_y) if top_y is not None else float(region.height) - margin_y
    chip_bottom = chip_top - chip_height

    _draw_pixel_rounded_rect(
        chip_left,
        chip_bottom,
        chip_left + chip_width,
        chip_top,
        fill_color,
        outline_color=outline_color,
        line_width=1.0,
        radius=max(4.0 * chip_scale, 6.0),
    )
    blf.color(_STORE_CHIP_FONT_ID, *text_color)
    blf.position(_STORE_CHIP_FONT_ID, chip_left + pad_x, chip_bottom + pad_y + chip_scale, 0)
    blf.draw(_STORE_CHIP_FONT_ID, clipped_text)
    return chip_bottom


def _draw_group_path_chip(*, top_y=None):
    labels = _node_editor_group_path_labels(bpy.context)
    if not labels:
        return None
    chip_text = " / ".join(str(label or "").strip() for label in labels if str(label or "").strip())
    if not chip_text:
        return None
    return _draw_top_left_overlay_chip(
        chip_text,
        (0.14, 0.18, 0.24, 0.90),
        (0.42, 0.52, 0.66, 0.98),
        (0.95, 0.97, 1.0, 1.0),
        top_y=top_y,
        font_size=11.0,
    )
