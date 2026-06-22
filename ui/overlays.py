import math
import time
from ctypes import POINTER, Structure, c_char, c_float

import bpy
import blf
from bpy.app.translations import pgettext_iface as iface_

from ..node_system.sockets import is_flow_socket
from ..node_system.tree import is_resolved_flow_socket, node_tree_runtime_revision
from ..runtime_core.constants import FLOW_SIDE_HOOK_NODE_TYPES
from ..runtime_flow.helpers import _find_single_from_input_socket, _first_output_node, _valid_socket_links
from ..runtime_runner.core import FlowRunner
from ..runtime_runner.core.active import get_active_runner
from .preferences import _ui_pref_enabled
from .overlay_context import (
    _iter_visible_nodes,
    _load_serialized_group_path,
    _node_editor_group_path,
    _node_editor_root_tree,
    _node_editor_zoom_factor,
    _path_item_node_tree,
    _resolve_group_path_node,
    _resolve_visible_path_target_node_name,
    _group_path_from_path_items,
    _ui_scale_factor,
)
from .overlay_drawing import (
    _clip_text_to_width,
    _draw_dashed_polyline,
    _draw_outline_bounds,
    _draw_pixel_rounded_rect,
    _draw_polyline_strip,
    _draw_polygon,
    _draw_region_polygon,
    _draw_top_rounded_pixel_rect,
    _node_bounds,
    _rounded_polygon_points,
    batch_for_shader,
    gpu,
)
from .overlay_pairs import (
    _annotate_overlay_pair_nesting,
    _append_overlay_entry_with_style,
    _collect_branch_overlay_pairs,
    _collect_control_overlay_pairs,
    _collect_execution_overlay_pairs,
    _collect_repeat_overlay_pairs,
    _collect_subflow_overlay_pairs,
    _collect_task_overlay_pairs,
    _overlay_pair_hull,
    _overlay_pair_palette,
    _overlay_pulse_state,
)


_FLOW_REPEAT_OVERLAY_HANDLER = None
_FLOW_STATUS_OVERLAY_HANDLER = None
_STORE_CHIP_FONT_ID = 0
_FLOW_TOGGLE_LINK_COLOR = (0.02, 0.02, 0.02, 0.75)
_FLOW_TOGGLE_SOCKET_RUNTIME_OFFSET = 456 if bpy.app.version >= (5, 1, 0) else 520
# Blender 5.2 added an identifier_ustr field ahead of bNodeSocketRuntime.location.
# Keep reading the exact runtime location, but jump to the correct byte offset for
# each supported layout instead of mirroring every preceding C++ field.
_FLOW_SOCKET_RUNTIME_LOCATION_OFFSET = 32 if bpy.app.version >= (5, 2, 0) else 24
_FLOW_SOCKET_MARKER_FILL_COLOR = (0.10, 0.42, 0.98, 1.00)
_FLOW_SOCKET_MARKER_OUTLINE_COLOR = (0.08, 0.10, 0.16, 0.92)
_FLOW_SOCKET_LINK_UNDERLAY_COLOR = (0.34, 0.74, 1.00, 0.60)
_FLOW_SOCKET_VIEWPORT_MARGIN = 96.0
_OVERLAY_PAIR_CACHE = {}
_FLOW_UNDERLAY_LINK_CACHE = {}
_QUICK_RUN_NODE_TYPES = {
    "AFNodeStorePropertyPackage",
    "AFNodeApplyObjectProperties",
    "AFNodeApplyPropertyPackage",
    "AFNodeRecordPropertyPackage",
}

_FLOW_STATUS_COLORS = {
    "RUNNING": (1.00, 0.66, 0.20, 1.00),
    "ERROR": (0.95, 0.24, 0.20, 1.00),
    "AUTO_TICK": (0.22, 0.76, 0.90, 1.00),
    "BACKGROUND": (0.18, 0.78, 0.90, 1.00),
    "BACKGROUND_STEP": (0.14, 0.88, 0.62, 1.00),
}


def _active_runner():
    return get_active_runner()


def _cache_pointer_token(data):
    if data is None:
        return 0
    return int(data.as_pointer()) if hasattr(data, "as_pointer") else id(data)


def _underlay_signature_value(value):
    if isinstance(value, dict):
        return tuple(
            sorted(
                (str(key), _underlay_signature_value(item_value))
                for key, item_value in value.items()
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_underlay_signature_value(item) for item in value)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return round(float(value), 6)
    if value is None:
        return ""
    return str(value)


def _background_task_overlay_entries(context, node_tree, runner):
    if runner is None:
        return []
    root_tree = _node_editor_root_tree(context, node_tree)
    if root_tree is None or getattr(runner, "node_tree", None) != root_tree:
        return []

    entries = []
    slots = {}
    for _task_id, state in sorted(getattr(runner, "background_task_plans", {}).items()):
        handle = state.get("handle", {})
        status = str(handle.get("status", state.get("status", "")) or "")
        if status in {"DONE", "FAILED", "CANCELLED"}:
            continue

        launcher_target_name = _resolve_visible_path_target_node_name(
            node_tree,
            str(getattr(root_tree, "name", "") or ""),
            str(state.get("node_name", "") or ""),
            [],
        )
        launcher_node = node_tree.nodes.get(launcher_target_name) if launcher_target_name else None
        _append_overlay_entry_with_style(
            entries,
            slots,
            launcher_node,
            _FLOW_STATUS_COLORS["BACKGROUND"],
            2.6,
            "BACKGROUND_PULSE",
        )

        current_step_name = str(state.get("current_step_name", "") or "")
        current_step_tree_name = str(state.get("current_step_tree_name", "") or "")
        current_step_group_path = list(state.get("current_step_group_path", []) or [])
        if not current_step_name or not current_step_tree_name:
            continue
        step_target_name = _resolve_visible_path_target_node_name(
            node_tree,
            current_step_tree_name,
            current_step_name,
            current_step_group_path,
        )
        step_node = node_tree.nodes.get(step_target_name) if step_target_name else None
        _append_overlay_entry_with_style(
            entries,
            slots,
            step_node,
            _FLOW_STATUS_COLORS["BACKGROUND_STEP"],
            2.2,
            "BACKGROUND_STEP_PULSE",
        )

    return entries


def _get_overlay_targets(context):
    space = getattr(context, "space_data", None)
    region = getattr(context, "region", None)
    scene = getattr(context, "scene", None)
    if space is None or region is None or scene is None:
        return []
    if space.type != "NODE_EDITOR" or getattr(space, "tree_type", "") != "AFNodeTreeType":
        return []
    node_tree = getattr(space, "edit_tree", None)
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return []

    settings = scene.af_flow_settings
    entries = []
    runner = _active_runner()
    slots = {}

    for entry in _background_task_overlay_entries(context, node_tree, runner):
        _append_overlay_entry_with_style(entries, slots, entry[0], entry[1], entry[2], entry[3] if len(entry) > 3 else "STATIC")

    root_tree = _node_editor_root_tree(context, node_tree)

    recent_step_refs = []
    if runner is not None and bool(getattr(runner, "auto_follow", False)) and getattr(runner, "node_tree", None) == root_tree:
        recent_step_refs_fn = getattr(runner, "auto_follow_recent_step_refs", None)
        recent_step_refs = recent_step_refs_fn() if callable(recent_step_refs_fn) else []
    try:
        from .. import operators as operators_module

        get_recent_overlay_refs = getattr(operators_module, "get_recent_auto_follow_overlay_step_refs", None)
        if callable(get_recent_overlay_refs):
            overlay_step_refs = get_recent_overlay_refs(getattr(root_tree, "name", ""))
            if overlay_step_refs:
                if recent_step_refs:
                    recent_step_refs = list(recent_step_refs) + list(overlay_step_refs)
                else:
                    recent_step_refs = list(overlay_step_refs)
    except Exception:
        pass

    if recent_step_refs:
        seen_auto_refs = set()
        for step_ref in recent_step_refs:
            if not isinstance(step_ref, dict):
                continue
            auto_ref_key = (
                str(step_ref.get("tree_name", "") or ""),
                str(step_ref.get("node_name", "") or ""),
                tuple(str(item) for item in list(step_ref.get("group_path", []) or [])),
            )
            if auto_ref_key in seen_auto_refs:
                continue
            seen_auto_refs.add(auto_ref_key)
            highlight_node_name = _resolve_visible_path_target_node_name(
                node_tree,
                str(step_ref.get("tree_name", "") or ""),
                str(step_ref.get("node_name", "") or ""),
                list(step_ref.get("group_path", []) or []),
            )
            node = node_tree.nodes.get(highlight_node_name) if highlight_node_name else None
            _append_overlay_entry_with_style(entries, slots, node, _FLOW_STATUS_COLORS["AUTO_TICK"], 2.1, "AUTO_TICK")
    elif runner is not None and runner.node_tree == node_tree:
        highlight_node_name = str(settings.current_node_name or "")
        if getattr(runner, "current_group_path", None):
            root_step_ref = runner.current_group_path[0]
            highlight_node_name = str(root_step_ref.get("node_name", "") or "")
        node = node_tree.nodes.get(highlight_node_name) if highlight_node_name else None
        _append_overlay_entry_with_style(entries, slots, node, _FLOW_STATUS_COLORS["RUNNING"], 3.0, "RUNNING")

    if settings.error_node_name and settings.runtime_status == "FAILED":
        error_group_path = _load_serialized_group_path(getattr(settings, "error_group_path_json", ""))
        highlight_node_name = _resolve_visible_path_target_node_name(
            node_tree,
            str(settings.runtime_tree_name or ""),
            str(settings.error_node_name or ""),
            error_group_path,
        )
        node = node_tree.nodes.get(highlight_node_name) if highlight_node_name else None
        _append_overlay_entry_with_style(entries, slots, node, _FLOW_STATUS_COLORS["ERROR"], 4.0, "ERROR")

    return entries
def _draw_node_outline(node, color, line_width):
    _draw_outline_bounds(_node_bounds(node, pad=4.0), color, line_width)


def _overlay_pair_node_signature(node):
    if node is None:
        return ()
    node_pointer = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
    node_location = getattr(node, "location_absolute", None)
    if node_location is None:
        node_location = getattr(node, "location", None)
    location_x = float(getattr(node_location, "x", 0.0) or 0.0)
    location_y = float(getattr(node_location, "y", 0.0) or 0.0)
    dimensions = getattr(node, "dimensions", None)
    dimension_x = float(getattr(dimensions, "x", 0.0) or 0.0)
    dimension_y = float(getattr(dimensions, "y", 0.0) or 0.0)
    return (
        node_pointer,
        str(getattr(node, "name", "") or ""),
        str(getattr(node, "bl_idname", "") or ""),
        str(getattr(node, "af_pair_id", "") or ""),
        bool(getattr(node, "hide", False)),
        bool(getattr(node, "mute", False)),
        round(location_x, 3),
        round(location_y, 3),
        round(float(getattr(node, "width", 0.0) or 0.0), 3),
        round(float(getattr(node, "height", 0.0) or 0.0), 3),
        round(dimension_x, 3),
        round(dimension_y, 3),
    )


def _overlay_pair_link_signature(link):
    if link is None:
        return ()
    from_node = getattr(link, "from_node", None)
    to_node = getattr(link, "to_node", None)
    from_socket = getattr(link, "from_socket", None)
    to_socket = getattr(link, "to_socket", None)
    return (
        int(from_node.as_pointer()) if hasattr(from_node, "as_pointer") else id(from_node),
        int(to_node.as_pointer()) if hasattr(to_node, "as_pointer") else id(to_node),
        str(getattr(from_socket, "name", "") or ""),
        str(getattr(to_socket, "name", "") or ""),
        bool(getattr(link, "is_valid", True)),
    )


def _overlay_pair_tree_signature(node_tree):
    node_signatures = sorted(
        _overlay_pair_node_signature(node)
        for node in getattr(node_tree, "nodes", [])
    )
    link_signatures = sorted(
        _overlay_pair_link_signature(link)
        for link in getattr(node_tree, "links", [])
    )
    return (
        str(getattr(node_tree, "name", "") or ""),
        len(node_signatures),
        len(link_signatures),
        tuple(node_signatures),
        tuple(link_signatures),
    )


def _cached_overlay_pair_draw_items(node_tree):
    if node_tree is None:
        return ()
    cache_key = int(node_tree.as_pointer()) if hasattr(node_tree, "as_pointer") else id(node_tree)
    signature = _overlay_pair_tree_signature(node_tree)
    cached = _OVERLAY_PAIR_CACHE.get(cache_key)
    if cached is not None and cached.get("signature") == signature:
        return cached.get("draw_items", ())

    # Reuse one completed control-pair snapshot so execution/task overlays and
    # control overlays resolve the same nested node coverage.
    control_pairs = _collect_control_overlay_pairs(node_tree)
    overlay_pairs = []
    overlay_pairs.extend(_collect_execution_overlay_pairs(node_tree, control_pairs=control_pairs))
    overlay_pairs.extend(_collect_task_overlay_pairs(node_tree, control_pairs=control_pairs))
    overlay_pairs.extend(_collect_repeat_overlay_pairs(node_tree))
    overlay_pairs.extend(_collect_subflow_overlay_pairs(node_tree, control_pairs=control_pairs))
    overlay_pairs.extend(_collect_branch_overlay_pairs(node_tree, control_pairs=control_pairs))
    overlay_pairs = _annotate_overlay_pair_nesting(overlay_pairs)

    hull_cache = {}
    draw_items = []
    for pair in sorted(overlay_pairs, key=lambda item: (int(item.get("depth", 0)), str(item.get("kind", "")))):
        hull = _overlay_pair_hull(pair, cache=hull_cache)
        if not hull:
            continue
        draw_items.append(
            {
                "kind": str(pair.get("kind", "REPEAT")),
                "hull": tuple(hull),
            }
        )

    draw_items = tuple(draw_items)
    _OVERLAY_PAIR_CACHE[cache_key] = {
        "signature": signature,
        "draw_items": draw_items,
    }
    if len(_OVERLAY_PAIR_CACHE) > 16:
        stale_keys = [key for key in _OVERLAY_PAIR_CACHE.keys() if key != cache_key]
        for stale_key in stale_keys[:-8]:
            _OVERLAY_PAIR_CACHE.pop(stale_key, None)
    return draw_items


def _status_overlay_palette(color):
    red, green, blue = float(color[0]), float(color[1]), float(color[2])
    fill_color = (red, green, blue, 0.20)
    outline_color = (red, green, blue, 0.82)
    return fill_color, outline_color


def _theme_node_editor_color(attr_name, fallback):
    try:
        theme = getattr(getattr(bpy.context, "preferences", None), "themes", None)
        node_editor = getattr(theme[0], "node_editor", None) if theme else None
        color = getattr(node_editor, attr_name, None) if node_editor is not None else None
        if color is not None:
            return (float(color[0]), float(color[1]), float(color[2]), 1.0)
    except Exception:
        pass
    return fallback


def _custom_math_header_palette(node):
    node_type = str(getattr(node, "bl_idname", "") or "")
    mode = str(getattr(node, "mode", "") or "")
    default_converter_fill = (0.1412, 0.3843, 0.5137, 1.0)
    default_vector_fill = (0.2353, 0.2353, 0.5137, 1.0)
    default_flow_fill = (0.25, 0.33, 0.44, 1.0)
    default_task_fill = (0.4745, 0.2745, 0.1137, 1.0)
    default_analysis_fill = (0.1137, 0.4471, 0.3686, 1.0)
    default_package_fill = (0.18, 0.46, 0.34, 1.0)

    flow_types = {
        "AFNodeStart",
        "AFNodeFlowToggle",
        "AFNodeTaskStatusOverride",
        "AFNodeRepeatStart",
        "AFNodeRepeatEnd",
        "AFNodeSubflowStart",
        "AFNodeSubflowJoin",
        "AFNodeBranchStart",
        "AFNodeBranchEnd",
        "AFNodeEnd",
        "AFNodeWaitForTask",
        "AFNodeDelayWait",
        "AFNodeReloadAfterTask",
    }
    task_types = {
        "AFNodeTaskStart",
        "AFNodeTaskOutput",
        "AFNodeBakeTask",
        "AFNodePropertyPackageBakeTarget",
        "AFNodeTaskStep",
        "AFNodePhysicsBakeSettings",
        "AFNodePhysicsBakeTask",
        "AFNodeSetActiveCamera",
        "AFNodeRenderTarget",
        "AFNodeRenderTask",
        "AFNodeRunTaskPlan",
        "AFNodeRunBackgroundTaskPlan",
    }
    analysis_types = {
        "AFNodeResolveTaskRef",
        "AFNodeEvaluateTaskDependencies",
    }
    package_types = {
        "AFNodeSetGeometryAttribute",
        "AFNodePublishGeometryAttribute",
        "AFNodeCreatePropertyPackage",
        "AFNodeRefreshPropertyPackage",
        "AFNodeStorePropertyPackage",
        "AFNodeReadPropertyPackage",
        "AFNodeApplyObjectProperties",
        "AFNodeApplyPropertyPackage",
        "AFNodeRecordPropertyPackage",
        "AFNodeParsePropertyPackage",
        "AFNodeFilterPropertyPackage",
        "AFNodeMergePropertyPackages",
    }
    vector_types = {
        "AFNodeVectorMath",
        "AFNodeCombineVector",
        "AFNodeSeparateVector",
        "AFNodeVectorRotate",
    }
    converter_types = {
        "AFNodeMath",
        "AFNodeIntegerMath",
        "AFNodeBooleanMath",
        "AFNodeMix",
        "AFNodeSwitch",
        "AFNodeIndexSwitch",
        "AFNodeCompare",
        "AFNodeStringCompare",
        "AFNodeConvertValue",
        "AFNodeClamp",
        "AFNodeMapRange",
        "AFNodeSmoothstep",
        "AFNodeRandomValue",
    }

    theme_attr = "converter_node"
    fallback_fill = default_converter_fill
    if node_type in flow_types:
        theme_attr = "attribute_node"
        fallback_fill = default_flow_fill
    elif node_type in task_types:
        theme_attr = "texture_node"
        fallback_fill = default_task_fill
    elif node_type in analysis_types:
        theme_attr = "geometry_node"
        fallback_fill = default_analysis_fill
    elif node_type in package_types:
        theme_attr = "geometry_node"
        fallback_fill = default_package_fill
    elif node_type in vector_types:
        theme_attr = "vector_node"
        fallback_fill = default_vector_fill
    elif node_type in {"AFNodeMix", "AFNodeSwitch", "AFNodeIndexSwitch", "AFNodeCompare"} and mode == "VECTOR":
        theme_attr = "vector_node"
        fallback_fill = default_vector_fill
    elif node_type in converter_types:
        theme_attr = "converter_node"
        fallback_fill = default_converter_fill

    fill = _theme_node_editor_color(theme_attr, fallback_fill)
    outline = tuple(min(1.0, channel + 0.10) for channel in fill[:3]) + (1.0,)
    text = (0.96, 0.97, 0.98, 1.0)
    return fill, outline, text


def _draw_node_highlight_fill(node, color, line_width, style="STATIC"):
    if gpu is None or batch_for_shader is None:
        return
    region = getattr(bpy.context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return

    x1, y1, x2, y2 = _node_bounds(node, pad=0.0)
    top_left = view2d.view_to_region(float(x1), float(y1), clip=False)
    bottom_right = view2d.view_to_region(float(x2), float(y2), clip=False)
    if top_left is None or bottom_right is None:
        return

    left = min(float(top_left[0]), float(bottom_right[0]))
    right = max(float(top_left[0]), float(bottom_right[0]))
    bottom = min(float(top_left[1]), float(bottom_right[1]))
    top = max(float(top_left[1]), float(bottom_right[1]))

    scale = _ui_scale_factor() * _node_editor_zoom_factor(region, view2d)
    pulse = _overlay_pulse_state(style)
    pad_x = 10.0 * scale * float(pulse.get("pad_scale", 1.0))
    pad_y = 8.0 * scale * float(pulse.get("pad_scale", 1.0))
    fill_color, outline_color = _status_overlay_palette(color)
    alpha_scale = float(pulse.get("alpha_scale", 1.0))
    fill_color = (fill_color[0], fill_color[1], fill_color[2], min(1.0, fill_color[3] * alpha_scale))
    outline_color = (outline_color[0], outline_color[1], outline_color[2], min(1.0, outline_color[3] * alpha_scale))
    _draw_pixel_rounded_rect(
        left - pad_x,
        bottom - pad_y,
        right + pad_x,
        top + pad_y,
        fill_color,
        outline_color=outline_color,
        line_width=max(1.25, float(line_width) * 0.55 * float(pulse.get("line_scale", 1.0))),
        radius=max(4.0 * scale, 6.0),
    )


def _custom_header_title(node):
    custom_label = str(getattr(node, "label", "") or "").strip()
    if custom_label:
        return custom_label
    draw_label_fn = getattr(node, "draw_label", None)
    if callable(draw_label_fn):
        try:
            dynamic_label = str(draw_label_fn() or "").strip()
        except Exception:
            dynamic_label = ""
        if dynamic_label:
            return dynamic_label
    bl_label = str(getattr(node, "bl_label", "") or "").strip()
    if bl_label:
        return iface_(bl_label)
    return ""


def _custom_header_region_layout(node, region, view2d, scale):
    x1, y1, x2, _y2 = _node_bounds(node, pad=0.0)
    top_left = view2d.view_to_region(float(x1), float(y1), clip=False)
    top_right = view2d.view_to_region(float(x2), float(y1), clip=False)
    if top_left is None or top_right is None:
        return None

    left = min(float(top_left[0]), float(top_right[0]))
    right = max(float(top_left[0]), float(top_right[0]))
    top = max(float(top_left[1]), float(top_right[1]))
    is_collapsed = bool(getattr(node, "hide", False))
    max_socket_count = max(_visible_socket_count(getattr(node, "inputs", [])), _visible_socket_count(getattr(node, "outputs", [])))
    if is_collapsed:
        hidden_offset_y = _collapsed_custom_header_offset_y(scale, max_socket_count)
        header_height = _collapsed_custom_header_height(scale, max_socket_count)
        top -= hidden_offset_y
    else:
        header_height = 20.0 * scale
    bottom = top - header_height
    header_overdraw_top = 1.25 * scale
    header_overdraw_right = 1.25 * scale
    return {
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
        "draw_top": top + header_overdraw_top,
        "draw_right": right + header_overdraw_right,
        "header_height": header_height,
        "center_y": bottom + (header_height * 0.5),
        "is_collapsed": is_collapsed,
    }


def _custom_header_text_y(center_y, text_height, scale):
    return float(center_y) - (float(text_height) * 0.5) + (2.5 * float(scale))


def _draw_disclosure_triangle(center_x, center_y, size, collapsed, color):
    half_size = max(2.0, float(size) * 0.5)
    if collapsed:
        points = [
            (center_x - (half_size * 0.45), center_y + half_size),
            (center_x - (half_size * 0.45), center_y - half_size),
            (center_x + (half_size * 0.75), center_y),
        ]
    else:
        points = [
            (center_x - half_size, center_y + (half_size * 0.45)),
            (center_x + half_size, center_y + (half_size * 0.45)),
            (center_x, center_y - (half_size * 0.75)),
        ]
    _draw_region_polygon(points, fill_color=color, outline_color=None, line_width=1.0)


def _draw_play_triangle(center_x, center_y, size, color, corner_radius=0.0, corner_segments=5):
    half_size = max(2.0, float(size) * 0.5)
    points = [
        (center_x - (half_size * 0.55), center_y + half_size),
        (center_x - (half_size * 0.55), center_y - half_size),
        (center_x + (half_size * 0.80), center_y),
    ]
    if float(corner_radius) > 0.0:
        points = _rounded_polygon_points(points, float(corner_radius), segments=max(3, int(corner_segments)))
    _draw_region_polygon(points, fill_color=color, outline_color=None, line_width=1.0)


def _quick_run_button_layout(node, region=None, view2d=None):
    if node is None or str(getattr(node, "bl_idname", "") or "") not in _QUICK_RUN_NODE_TYPES:
        return None
    region = region if region is not None else getattr(bpy.context, "region", None)
    view2d = view2d if view2d is not None else (getattr(region, "view2d", None) if region is not None else None)
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return None
    scale = _ui_scale_factor() * _node_editor_zoom_factor(region, view2d)
    header_layout = _custom_header_region_layout(node, region, view2d, scale)
    if header_layout is None:
        return None
    button_height = max(20.0, 25.0 * scale)
    button_width = max(button_height + (7.0 * scale), 30.0 * scale)
    attach_inset = max(8.0, 9.0 * scale)
    button_right = float(header_layout["left"]) + attach_inset
    button_left = button_right - button_width
    center_y = float(header_layout["center_y"]) - (25.0 * scale)
    button_bottom = center_y - (button_height * 0.5)
    button_top = button_bottom + button_height
    return {
        "left": button_left,
        "right": button_right,
        "bottom": button_bottom,
        "top": button_top,
        "center_x": button_left + (button_width * 0.5),
        "center_y": center_y,
        "scale": scale,
    }


def _draw_quick_run_buttons(node_tree):
    region = getattr(bpy.context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return

    fill_color = (0.4, 0.4, 0.4, 0.6)
    outline_color = (0.7, 0.7, 0.7, 0.8)
    icon_color = (1.0, 1.0, 1.0, 0.96)
    for node in _iter_visible_nodes(node_tree, region=region, view2d=view2d, margin=120.0):
        layout = _quick_run_button_layout(node, region=region, view2d=view2d)
        if layout is None:
            continue
        scale = float(layout["scale"])
        _draw_pixel_rounded_rect(
            layout["left"],
            layout["bottom"],
            layout["right"],
            layout["top"],
            fill_color,
            outline_color=outline_color,
            line_width=max(0.5, 0.55 * scale),
            radius=max(4.5, 4.8 * scale),
        )
        _draw_play_triangle(
            layout["center_x"] - (5.0 * scale),
            layout["center_y"],
            max(12.0, 14.0 * scale),
            icon_color,
            corner_radius=max(1.0, 1.0 * scale),
            corner_segments=6,
        )


def _visible_socket_count(sockets):
    return sum(1 for socket in sockets if not bool(getattr(socket, "hide", False)))


def _visible_input_sockets(node):
    return [
        socket
        for socket in getattr(node, "inputs", [])
        if not bool(getattr(socket, "hide", False))
    ]


def _visible_output_sockets(node):
    return [
        socket
        for socket in getattr(node, "outputs", [])
        if not bool(getattr(socket, "hide", False))
    ]


def _socket_runtime_region_center(socket, view2d):
    if socket is None or view2d is None:
        return None
    if not bool(getattr(socket, "enabled", True)):
        return None
    try:
        socket_struct = _BNodeSocket.from_address(socket.as_pointer())
        if not socket_struct.runtime:
            return None
        runtime = socket_struct.runtime.contents
        region_point = view2d.view_to_region(float(runtime.location[0]), float(runtime.location[1]) + 0.5, clip=False)
    except Exception:
        return None
    if region_point is None:
        return None
    center_x = float(region_point[0])
    center_y = float(region_point[1])
    if not math.isfinite(center_x) or not math.isfinite(center_y):
        return None
    return (center_x, center_y)


def _flow_socket_marker_region_points(center_x, center_y, scale):
    center_x = float(center_x)
    center_y = float(center_y)
    scale = max(0.5, float(scale))
    half_height = max(5.0, 7.0 * scale)
    half_width = max(5.0, 7.0 * scale)
    raw_points = [
        (center_x - half_width, center_y),
        (center_x, center_y + half_height),
        (center_x + half_width, center_y),
        (center_x, center_y - half_height),
    ]
    return _rounded_polygon_points(raw_points, radius=max(0.5, 0.6 * scale), segments=3)


def _draw_flow_socket_marker(center_x, center_y, scale):
    points = _flow_socket_marker_region_points(center_x, center_y, scale)
    _draw_region_polygon(
        points,
        fill_color=_FLOW_SOCKET_MARKER_FILL_COLOR,
        outline_color=_FLOW_SOCKET_MARKER_OUTLINE_COLOR,
        line_width=max(1.0, 1.2 * float(scale)),
    )


class _BNodeSocketRuntime(Structure):
    _fields_ = [
        ("pad", c_char * _FLOW_SOCKET_RUNTIME_LOCATION_OFFSET),
        ("location", c_float * 2),
    ]


class _BNodeSocket(Structure):
    _fields_ = [
        ("pad", c_char * _FLOW_TOGGLE_SOCKET_RUNTIME_OFFSET),
        ("runtime", POINTER(_BNodeSocketRuntime)),
    ]


def _flow_toggle_link_curving_factor():
    try:
        curving = float(getattr(bpy.context.preferences.themes[0].node_editor, "noodle_curving", 0.0))
    except Exception:
        curving = 0.0
    return max(0.0, curving / 10.0)


def _flow_toggle_link_handle_offset(x1, y1, x2, y2, curving_factor):
    dx = abs(float(x2) - float(x1))
    dy = abs(float(y2) - float(y1))
    if dx <= 1e-6:
        return 0.0
    slope = dy / dx
    raw_curving = curving_factor * 10.0
    clamp_factor = min(1.0, slope * (4.5 - (0.25 * raw_curving)))
    return raw_curving * 0.1 * dx * clamp_factor


def _flow_toggle_link_runtime_region_points(link, view2d, curving_factor):
    from_socket = getattr(link, "from_socket", None)
    to_socket = getattr(link, "to_socket", None)
    if from_socket is None or to_socket is None:
        return None
    if not bool(getattr(from_socket, "enabled", False)) or not bool(getattr(to_socket, "enabled", False)):
        return None
    try:
        from_struct = _BNodeSocket.from_address(from_socket.as_pointer())
        to_struct = _BNodeSocket.from_address(to_socket.as_pointer())
        if not from_struct.runtime or not to_struct.runtime:
            return None
        from_runtime = from_struct.runtime.contents
        to_runtime = to_struct.runtime.contents
        x1, y1 = float(from_runtime.location[0]), float(from_runtime.location[1]) + 0.5
        x2, y2 = float(to_runtime.location[0]), float(to_runtime.location[1]) + 0.5
    except Exception:
        return None

    handle = _flow_toggle_link_handle_offset(x1, y1, x2, y2, curving_factor)
    p0 = (x1, y1)
    p1 = (x1 + handle, y1)
    p2 = (x2 - handle, y2)
    p3 = (x2, y2)

    start_region = view2d.view_to_region(p0[0], p0[1], clip=False)
    end_region = view2d.view_to_region(p3[0], p3[1], clip=False)
    if start_region is None or end_region is None:
        return None

    approx = abs(float(end_region[0]) - float(start_region[0])) + abs(float(end_region[1]) - float(start_region[1]))
    sample_count = max(8, min(80, int(approx * 0.055)))
    points = []
    for step in range(sample_count + 1):
        factor = step / float(max(1, sample_count))
        inverse = 1.0 - factor
        point_x = (
            (inverse ** 3) * p0[0]
            + 3.0 * (inverse ** 2) * factor * p1[0]
            + 3.0 * inverse * (factor ** 2) * p2[0]
            + (factor ** 3) * p3[0]
        )
        point_y = (
            (inverse ** 3) * p0[1]
            + 3.0 * (inverse ** 2) * factor * p1[1]
            + 3.0 * inverse * (factor ** 2) * p2[1]
            + (factor ** 3) * p3[1]
        )
        region_point = view2d.view_to_region(point_x, point_y, clip=False)
        if region_point is None:
            return None
        rx = float(region_point[0])
        ry = float(region_point[1])
        if not math.isfinite(rx) or not math.isfinite(ry):
            return None
        points.append((rx, ry))
    return points


def _is_flow_side_hook_trigger_link(link):
    to_node = getattr(link, "to_node", None)
    to_socket = getattr(link, "to_socket", None)
    from_socket = getattr(link, "from_socket", None)
    if to_node is None or to_socket is None or from_socket is None:
        return False
    if str(getattr(to_node, "bl_idname", "") or "") not in FLOW_SIDE_HOOK_NODE_TYPES:
        return False
    try:
        flow_side_hook_inputs = getattr(to_node, "inputs", None)
        first_input = flow_side_hook_inputs[0] if flow_side_hook_inputs and len(flow_side_hook_inputs) > 0 else None
    except Exception:
        first_input = None
    if first_input is not None and to_socket == first_input and is_flow_socket(to_socket):
        return True
    socket_identifier = str(getattr(to_socket, "identifier", "") or "")
    if socket_identifier == "Trigger":
        return True
    return str(getattr(to_socket, "name", "") or "") == "Trigger"


def _trim_polyline_region_points(region_points, trim_start=0.0, trim_end=0.0):
    if len(region_points) < 2:
        return list(region_points)

    trim_start = max(0.0, float(trim_start))
    trim_end = max(0.0, float(trim_end))
    if trim_start <= 1e-6 and trim_end <= 1e-6:
        return list(region_points)

    segment_lengths = []
    total_length = 0.0
    for start_point, end_point in zip(region_points[:-1], region_points[1:]):
        x1, y1 = float(start_point[0]), float(start_point[1])
        x2, y2 = float(end_point[0]), float(end_point[1])
        segment_length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        segment_lengths.append(segment_length)
        total_length += segment_length

    if total_length <= (trim_start + trim_end) + 1e-6:
        return None

    start_target = trim_start
    end_target = total_length - trim_end
    accumulated = 0.0
    trimmed_points = []

    for index, (start_point, end_point) in enumerate(zip(region_points[:-1], region_points[1:])):
        segment_length = segment_lengths[index]
        if segment_length <= 1e-6:
            accumulated += segment_length
            continue

        segment_start = accumulated
        segment_end = accumulated + segment_length
        accumulated = segment_end

        if segment_end <= start_target:
            continue
        if segment_start >= end_target:
            break

        x1, y1 = float(start_point[0]), float(start_point[1])
        x2, y2 = float(end_point[0]), float(end_point[1])
        direction_x = (x2 - x1) / segment_length
        direction_y = (y2 - y1) / segment_length
        local_start = max(0.0, start_target - segment_start)
        local_end = min(segment_length, end_target - segment_start)
        if local_end <= local_start + 1e-6:
            continue

        trimmed_start = (
            x1 + (direction_x * local_start),
            y1 + (direction_y * local_start),
        )
        trimmed_end = (
            x1 + (direction_x * local_end),
            y1 + (direction_y * local_end),
        )
        if not trimmed_points:
            trimmed_points.append(trimmed_start)
        elif (
            abs(trimmed_points[-1][0] - trimmed_start[0]) > 1e-6
            or abs(trimmed_points[-1][1] - trimmed_start[1]) > 1e-6
        ):
            trimmed_points.append(trimmed_start)
        trimmed_points.append(trimmed_end)

    return trimmed_points if len(trimmed_points) >= 2 else None


def _flow_toggle_trigger_links(node_tree):
    for link in getattr(node_tree, "links", []):
        if not _is_flow_side_hook_trigger_link(link):
            continue
        to_socket = getattr(link, "to_socket", None)
        from_socket = getattr(link, "from_socket", None)
        if bool(getattr(to_socket, "hide", False)) or bool(getattr(from_socket, "hide", False)):
            continue
        if not bool(getattr(link, "is_valid", True)):
            continue
        yield link


def _draw_flow_toggle_trigger_links(node_tree):
    region = getattr(bpy.context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return

    scale = _ui_scale_factor() * _node_editor_zoom_factor(region, view2d)
    dash_length = max(3.0, 10.0 * scale)
    gap_length = dash_length * 0.4
    line_width = max(1.2, 1.6 * scale) * 2.8
    endpoint_trim = max(5.0, 7.0 * scale)
    viewport_margin = 96.0
    curving_factor = _flow_toggle_link_curving_factor()

    for link in _flow_toggle_trigger_links(node_tree):
        link_points = _flow_toggle_link_runtime_region_points(link, view2d, curving_factor)
        if not link_points or len(link_points) < 2:
            continue
        link_points = _trim_polyline_region_points(
            link_points,
            trim_start=endpoint_trim,
            trim_end=endpoint_trim,
        )
        if not link_points or len(link_points) < 2:
            continue
        start_x, start_y = link_points[0]
        end_x, end_y = link_points[-1]
        min_x = min(start_x, end_x)
        max_x = max(start_x, end_x)
        min_y = min(start_y, end_y)
        max_y = max(start_y, end_y)
        if (
            max_x < -viewport_margin
            or min_x > float(region.width) + viewport_margin
            or max_y < -viewport_margin
            or min_y > float(region.height) + viewport_margin
        ):
            continue
        _draw_dashed_polyline(
            link_points,
            _FLOW_TOGGLE_LINK_COLOR,
            line_width=line_width,
            dash_length=dash_length,
            gap_length=gap_length,
        )


def _socket_identity(socket):
    if socket is None:
        return None
    node = getattr(socket, "node", None)
    if node is None:
        return None
    try:
        node_key = int(node.as_pointer())
    except Exception:
        node_key = str(getattr(node, "name", "") or "")
    return (
        node_key,
        bool(getattr(socket, "is_output", False)),
        str(getattr(socket, "identifier", "") or getattr(socket, "name", "") or ""),
    )


def _flow_link_identity(link):
    return (
        _socket_identity(getattr(link, "from_socket", None)),
        _socket_identity(getattr(link, "to_socket", None)),
    )


def _is_flow_underlay_candidate_link(link):
    from_node = getattr(link, "from_node", None)
    to_node = getattr(link, "to_node", None)
    from_socket = getattr(link, "from_socket", None)
    to_socket = getattr(link, "to_socket", None)
    if from_node is None or to_node is None or from_socket is None or to_socket is None:
        return False
    if bool(getattr(from_socket, "hide", False)) or bool(getattr(to_socket, "hide", False)):
        return False
    if not bool(getattr(link, "is_valid", True)):
        return False
    if _is_flow_side_hook_trigger_link(link):
        return False
    if not is_resolved_flow_socket(from_node, from_socket):
        return False
    if not is_resolved_flow_socket(to_node, to_socket):
        return False
    return True


def _flow_input_socket(node, preferred_name="Flow In"):
    inputs = getattr(node, "inputs", None)
    get_input = getattr(inputs, "get", lambda _name: None)
    preferred_socket = get_input(preferred_name) if preferred_name else None
    if preferred_socket is not None and is_flow_socket(preferred_socket):
        return preferred_socket
    flow_inputs = [socket for socket in list(inputs or []) if is_flow_socket(socket)]
    if len(flow_inputs) == 1:
        return flow_inputs[0]
    return preferred_socket if preferred_socket is not None and is_flow_socket(preferred_socket) else None


def _flow_output_socket(node, preferred_name="Flow Out"):
    outputs = getattr(node, "outputs", None)
    get_output = getattr(outputs, "get", lambda _name: None)
    preferred_socket = get_output(preferred_name) if preferred_name else None
    if preferred_socket is not None and is_flow_socket(preferred_socket):
        return preferred_socket
    flow_outputs = [socket for socket in list(outputs or []) if is_flow_socket(socket)]
    if len(flow_outputs) == 1:
        return flow_outputs[0]
    return preferred_socket if preferred_socket is not None and is_flow_socket(preferred_socket) else None


def _flow_output_path_links_to_target(output_socket, target_socket, visited_reroutes=None):
    if output_socket is None or target_socket is None:
        return []

    target_identity = _socket_identity(target_socket)
    if target_identity is None:
        return []

    visited = set(visited_reroutes or ())
    for link in _valid_socket_links(output_socket):
        if not _is_flow_underlay_candidate_link(link):
            continue
        to_node = getattr(link, "to_node", None)
        to_socket = getattr(link, "to_socket", None)
        if _socket_identity(to_socket) == target_identity:
            return [link]
        if to_node is None or str(getattr(to_node, "bl_idname", "") or "") != "NodeReroute":
            continue
        reroute_key = int(to_node.as_pointer()) if hasattr(to_node, "as_pointer") else id(to_node)
        if reroute_key in visited:
            continue
        reroute_outputs = getattr(to_node, "outputs", None)
        reroute_output_socket = reroute_outputs[0] if reroute_outputs and len(reroute_outputs) > 0 else None
        nested_path = _flow_output_path_links_to_target(
            reroute_output_socket,
            target_socket,
            visited | {reroute_key},
        )
        if nested_path:
            return [link] + list(nested_path)
    return []


def _add_flow_underlay_links(path_links, ordered_links, seen_links):
    for link in list(path_links or []):
        link_key = _flow_link_identity(link)
        if link_key in seen_links:
            continue
        seen_links.add(link_key)
        ordered_links.append(link)


def _extend_underlay_links_to_step_ref(
    runner,
    source_node,
    output_name,
    target_step_ref,
    preferred_input_name,
    owner_node_name,
    ordered_links,
    seen_links,
):
    if source_node is None or not isinstance(target_step_ref, dict):
        return False
    output_socket = _flow_output_socket(source_node, output_name)
    if output_socket is None:
        return False
    try:
        target_node = runner._resolve_step_ref(target_step_ref, owner_node_name)
    except Exception:
        return False
    target_socket = _flow_input_socket(target_node, preferred_input_name)
    if target_socket is None:
        return False
    path_links = _flow_output_path_links_to_target(output_socket, target_socket)
    if not path_links:
        return False
    _add_flow_underlay_links(path_links, ordered_links, seen_links)
    return True


def _collect_visible_linear_flow_entries(runner, start_node, stop_node_types, group_path):
    entries = []
    current = start_node
    active_group_path = [
        dict(item)
        for item in list(group_path or [])
        if isinstance(item, dict)
    ]
    visited = set()

    while current is not None:
        current_identity = runner._flow_entry_identity(current, active_group_path)
        if current_identity in visited:
            raise RuntimeError("Visible flow segment has a loop")
        visited.add(current_identity)
        entries.append(
            {
                "node": current,
                "group_path": [dict(item) for item in active_group_path],
            }
        )
        if str(getattr(current, "bl_idname", "") or "") in set(stop_node_types or ()):
            break
        current = _first_output_node(current, "Flow Out")

    return entries


def _find_visible_task_start_for_output(task_output_node):
    if task_output_node is None or str(getattr(task_output_node, "bl_idname", "") or "") != "AFNodeTaskOutput":
        return None
    inputs = getattr(task_output_node, "inputs", None)
    flow_input = getattr(inputs, "get", lambda _name: None)("Flow In")
    if flow_input is None:
        return None

    current, _current_socket = _find_single_from_input_socket(flow_input)
    visited = {int(task_output_node.as_pointer()) if hasattr(task_output_node, "as_pointer") else id(task_output_node)}
    while current is not None:
        current_key = int(current.as_pointer()) if hasattr(current, "as_pointer") else id(current)
        if current_key in visited:
            return None
        visited.add(current_key)
        if str(getattr(current, "bl_idname", "") or "") == "AFNodeTaskStart":
            return current
        current_inputs = getattr(current, "inputs", None)
        current_flow_input = getattr(current_inputs, "get", lambda _name: None)("Flow In")
        if current_flow_input is None:
            return None
        current, _current_socket = _find_single_from_input_socket(current_flow_input)
    return None


def _select_visible_task_plan_nodes(runner, node_tree):
    task_outputs = list(runner._find_task_group_nodes(node_tree, "AFNodeTaskOutput"))
    linked_task_outputs = []
    for node in task_outputs:
        flow_input = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Flow In")
        if bool(getattr(flow_input, "links", None)):
            linked_task_outputs.append(node)
    if linked_task_outputs:
        task_outputs = linked_task_outputs

    task_starts = list(runner._find_task_group_nodes(node_tree, "AFNodeTaskStart"))
    linked_task_starts = []
    for node in task_starts:
        flow_output = getattr(getattr(node, "outputs", None), "get", lambda _name: None)("Flow Out")
        if bool(getattr(flow_output, "links", None)):
            linked_task_starts.append(node)
    if linked_task_starts:
        task_starts = linked_task_starts
    return task_starts, task_outputs


def _build_task_underlay_context_from_output(runner, node_tree, task_output_node, group_path):
    if runner is None or node_tree is None or task_output_node is None:
        return None
    if getattr(task_output_node, "id_data", None) != node_tree:
        return None
    if str(getattr(task_output_node, "bl_idname", "") or "") != "AFNodeTaskOutput":
        return None

    task_start_node = _find_visible_task_start_for_output(task_output_node)
    if task_start_node is None or getattr(task_start_node, "id_data", None) != node_tree:
        return None

    entries = _collect_visible_linear_flow_entries(
        runner,
        task_start_node,
        {"AFNodeTaskOutput"},
        group_path,
    )
    if not entries or entries[-1].get("node") != task_output_node:
        return None

    owner_node_name = str(getattr(task_output_node, "name", "") or getattr(node_tree, "name", "") or "Task Underlay")
    return _build_underlay_context_from_entries(
        runner,
        entries,
        owner_node_name,
        entry_anchor=None,
        mode="TASK",
    )


def _collect_active_task_underlay_contexts_from_plan(
    runner,
    node_tree,
    plan,
    owner_node_name,
    contexts,
    seen_outputs,
):
    normalized_plan = runner._normalize_local_segment_plan(plan)
    step_refs = list(normalized_plan.get("step_refs", []) or [])
    if not step_refs:
        return

    step_nodes = [runner._resolve_step_ref(step_ref, owner_node_name) for step_ref in step_refs]
    branch_plans = dict(normalized_plan.get("branch_plans", {}) or {})
    subflow_plans = dict(normalized_plan.get("subflow_plans", {}) or {})

    for index, step_node in enumerate(step_nodes):
        step_ref = step_refs[index]
        group_path = list(step_ref.get("group_path", []) or [])
        node_type = str(getattr(step_node, "bl_idname", "") or "")

        if node_type == "AFNodeRunTaskPlan":
            entries, _linked_count, _enabled_count = runner._collect_run_task_plan_entries(step_node)
            for entry in entries:
                if not bool(entry.get("enabled", False)):
                    continue
                source_node = entry.get("from_node")
                if source_node is None:
                    continue
                if getattr(source_node, "id_data", None) != node_tree:
                    continue
                if str(getattr(source_node, "bl_idname", "") or "") != "AFNodeTaskOutput":
                    continue
                source_key = int(source_node.as_pointer()) if hasattr(source_node, "as_pointer") else id(source_node)
                if source_key in seen_outputs:
                    continue
                context_data = _build_task_underlay_context_from_output(runner, node_tree, source_node, group_path)
                if context_data is None:
                    continue
                seen_outputs.add(source_key)
                contexts.append(context_data)

        if node_type == "AFNodeBranchStart":
            trigger_state = _evaluate_underlay_trigger_state(runner, step_node, group_path)
            branch_plan = branch_plans.get(index)
            if trigger_state is not False and isinstance(branch_plan, dict):
                _collect_active_task_underlay_contexts_from_plan(
                    runner,
                    node_tree,
                    branch_plan,
                    str(getattr(step_node, "name", "") or owner_node_name),
                    contexts,
                    seen_outputs,
                )
            if trigger_state is True:
                break
            continue

        if node_type == "AFNodeSubflowJoin":
            trigger_state = _evaluate_underlay_trigger_state(runner, step_node, group_path)
            subflow_plan = subflow_plans.get(index)
            if trigger_state is not False and isinstance(subflow_plan, dict):
                _collect_active_task_underlay_contexts_from_plan(
                    runner,
                    node_tree,
                    subflow_plan,
                    str(getattr(step_node, "name", "") or owner_node_name),
                    contexts,
                    seen_outputs,
                )


def _append_underlay_links_from_context(context_data, ordered_links, seen_links):
    if not isinstance(context_data, dict):
        return False
    runner = context_data.get("runner")
    plan = context_data.get("plan")
    owner_node_name = str(context_data.get("owner_node_name", "") or "")
    entry_anchor = context_data.get("entry_anchor")
    if runner is None or not isinstance(plan, dict):
        return False

    step_refs = list(runner._normalize_local_segment_plan(plan).get("step_refs", []) or [])
    if entry_anchor is not None and step_refs:
        _extend_underlay_links_to_step_ref(
            runner,
            entry_anchor.get("node"),
            entry_anchor.get("output_name", "Flow Out"),
            step_refs[0],
            "Flow In",
            owner_node_name,
            ordered_links,
            seen_links,
        )
    _collect_plan_active_underlay_links(
        runner,
        plan,
        owner_node_name,
        ordered_links,
        seen_links,
    )
    return bool(ordered_links)


def _build_underlay_context_from_entries(runner, entries, owner_node_name, *, entry_anchor=None, mode="FLOW"):
    if runner is None or not entries:
        return None
    step_refs = [
        runner._make_step_ref(entry["node"], entry.get("group_path", []))
        for entry in entries
    ]
    plan = runner._compile_local_segment_plan(step_refs, owner_node_name, lambda _entry: 0)
    return {
        "runner": runner,
        "plan": plan,
        "owner_node_name": str(owner_node_name or "Underlay"),
        "entry_anchor": dict(entry_anchor) if isinstance(entry_anchor, dict) else None,
        "mode": str(mode or "FLOW"),
    }


def _select_visible_flow_group_sockets(runner, node_tree, node_type, socket_collection_name):
    matches = list(runner._find_group_flow_socket_nodes(node_tree, node_type, socket_collection_name))
    linked_matches = [
        (node, socket)
        for node, socket in matches
        if bool(getattr(socket, "links", None))
    ]
    return linked_matches or matches


def _current_underlay_playback_state():
    try:
        from ..operators import flow_run as flow_run_module

        return {
            "playing": bool(getattr(flow_run_module, "_is_animation_playing", lambda: False)()),
            "on_play": False,
            "on_pause": False,
        }
    except Exception:
        return {
            "playing": False,
            "on_play": False,
            "on_pause": False,
        }


def _root_underlay_playback_ui_context():
    return {"playback_state": _current_underlay_playback_state()}


def _make_root_underlay_start_context(start_node_name, ui_context=None, auto_follow=False):
    start_name = str(start_node_name or "").strip()
    if not start_name:
        return None
    return {
        "start_node_name": start_name,
        "ui_context": dict(ui_context or {}),
        "auto_follow": bool(auto_follow),
    }


def _pending_auto_follow_underlay_contexts(root_tree, scene):
    if root_tree is None or scene is None:
        return []
    try:
        from ..operators import flow_run as flow_run_module
    except Exception:
        return []

    pending_entries = []
    pending_map = getattr(flow_run_module, "_AUTO_FOLLOW_PENDING_STARTS", None)
    if not isinstance(pending_map, dict):
        return []

    root_tree_name = str(getattr(root_tree, "name", "") or "")
    scene_name = str(getattr(scene, "name", "") or "")
    for key, entry in list(pending_map.items()):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("tree_name", "") or "") != root_tree_name:
            continue
        if str(entry.get("scene_name", "") or "") != scene_name:
            continue
        start_node_name = str(entry.get("start_node_name", "") or "").strip()
        start_node = root_tree.nodes.get(start_node_name) if start_node_name else None
        if start_node is None or str(getattr(start_node, "bl_idname", "") or "") != "AFNodeStart":
            continue
        if not bool(getattr(start_node, "auto_follow_enabled", False)):
            continue
        pending_entries.append(
            (
                int(getattr(start_node, "auto_order", entry.get("auto_order", 0)) or 0),
                float(entry.get("first_dirty_at", entry.get("last_dirty_at", 0.0)) or 0.0),
                str(key or ""),
                start_node_name,
                dict(entry.get("playback_state") or {}),
            )
        )

    if not pending_entries:
        return []

    pending_entries.sort(key=lambda item: (item[1], item[0], item[2]))
    contexts = []
    for _auto_order, _dirty_at, _entry_key, start_node_name, playback_state in pending_entries:
        context = _make_root_underlay_start_context(
            start_node_name,
            ui_context={"playback_state": playback_state},
            auto_follow=True,
        )
        if context is not None:
            contexts.append(context)
    return contexts


def _dedupe_root_underlay_start_contexts(start_contexts):
    contexts = []
    seen_start_names = set()
    for context in list(start_contexts or []):
        if not isinstance(context, dict):
            continue
        start_node_name = str(context.get("start_node_name", "") or "").strip()
        if not start_node_name or start_node_name in seen_start_names:
            continue
        seen_start_names.add(start_node_name)
        normalized = _make_root_underlay_start_context(
            start_node_name,
            ui_context=context.get("ui_context", {}),
            auto_follow=context.get("auto_follow", False),
        )
        if normalized is not None:
            contexts.append(normalized)
    return contexts


def _root_underlay_start_contexts(root_tree, scene):
    if root_tree is None:
        return []

    contexts = []
    active_runner = _active_runner()
    if (
        active_runner is not None
        and getattr(active_runner, "node_tree", None) == root_tree
        and (scene is None or getattr(active_runner, "scene", None) == scene)
    ):
        start_node_name = str(getattr(active_runner, "start_node_name", "") or "").strip()
        start_node = root_tree.nodes.get(start_node_name) if start_node_name else None
        if start_node is not None and str(getattr(start_node, "bl_idname", "") or "") == "AFNodeStart":
            context = _make_root_underlay_start_context(
                start_node_name,
                ui_context=getattr(active_runner, "ui_context", {}) or {},
                auto_follow=getattr(active_runner, "auto_follow", False),
            )
            if context is not None:
                contexts.append(context)

    contexts.extend(_pending_auto_follow_underlay_contexts(root_tree, scene))

    start_nodes = [
        node
        for node in getattr(root_tree, "nodes", [])
        if str(getattr(node, "bl_idname", "") or "") == "AFNodeStart"
    ]
    playback_ui_context = _root_underlay_playback_ui_context()

    manual_start_nodes = [
        node
        for node in start_nodes
        if bool(getattr(node, "is_active_start", False))
    ]
    for node in sorted(manual_start_nodes, key=lambda item: str(getattr(item, "name", "") or "")):
        context = _make_root_underlay_start_context(
            getattr(node, "name", ""),
            ui_context=playback_ui_context,
            auto_follow=False,
        )
        if context is not None:
            contexts.append(context)

    auto_follow_start_nodes = [
        node
        for node in start_nodes
        if bool(getattr(node, "auto_follow_enabled", False))
    ]
    for node in sorted(
        auto_follow_start_nodes,
        key=lambda item: (
            int(getattr(item, "auto_order", 0) or 0),
            str(getattr(item, "name", "") or ""),
        ),
    ):
        context = _make_root_underlay_start_context(
            getattr(node, "name", ""),
            ui_context=playback_ui_context,
            auto_follow=True,
        )
        if context is not None:
            contexts.append(context)

    # A Start without manual-enable or auto-follow is not treated as an effective
    # root underlay entry when multiple Starts exist. Otherwise the overlay would
    # drift away from actual run selection and expand back toward "draw everything".
    # We only accept that kind of Start as a final fallback when the tree has
    # exactly one Start and no explicit effective Start contexts were found.
    if not contexts and len(start_nodes) == 1:
        context = _make_root_underlay_start_context(
            getattr(start_nodes[0], "name", ""),
            ui_context=playback_ui_context,
            auto_follow=False,
        )
        if context is not None:
            contexts.append(context)

    return _dedupe_root_underlay_start_contexts(contexts)


def _root_underlay_contexts_signature(root_tree, scene):
    return tuple(
        (
            str(context.get("start_node_name", "") or ""),
            bool(context.get("auto_follow", False)),
            _underlay_signature_value(context.get("ui_context", {})),
        )
        for context in _root_underlay_start_contexts(root_tree, scene)
    )


def _visible_underlay_context_signature(node_tree, root_tree, scene):
    return (
        _cache_pointer_token(node_tree),
        int(node_tree_runtime_revision(node_tree)),
        _cache_pointer_token(root_tree),
        int(node_tree_runtime_revision(root_tree)),
        _cache_pointer_token(scene),
        int(getattr(scene, "frame_current", 0) or 0) if scene is not None else 0,
        round(float(getattr(scene, "frame_subframe", 0.0) or 0.0), 6) if scene is not None else 0.0,
        _underlay_signature_value(_node_editor_group_path(bpy.context)),
    )


def _build_root_underlay_contexts(root_tree, scene):
    context_items = []
    for start_context in _root_underlay_start_contexts(root_tree, scene):
        runner_kwargs = {
            "ui_context": dict(start_context.get("ui_context", {}) or {}),
            "start_node_name": str(start_context.get("start_node_name", "") or ""),
            "auto_follow": bool(start_context.get("auto_follow", False)),
        }
        runner = FlowRunner(root_tree, scene, **runner_kwargs)
        start_node_name = str(runner_kwargs.get("start_node_name", "") or "")
        start_node = root_tree.nodes.get(start_node_name) if start_node_name else None
        if start_node is None or str(getattr(start_node, "bl_idname", "") or "") != "AFNodeStart":
            continue
        try:
            entries = _collect_visible_linear_flow_entries(runner, start_node, {"AFNodeEnd"}, [])
        except Exception:
            continue
        if not entries or str(getattr(entries[-1].get("node"), "bl_idname", "") or "") != "AFNodeEnd":
            continue
        owner_node_name = str(getattr(entries[0].get("node"), "name", "") or getattr(root_tree, "name", "") or "Underlay")
        try:
            context_data = _build_underlay_context_from_entries(
                runner,
                entries,
                owner_node_name,
                entry_anchor=None,
                mode="FLOW_ROOT",
            )
        except Exception:
            continue
        if context_data is not None:
            context_items.append(context_data)
    return context_items


def _build_visible_underlay_context(node_tree):
    context = bpy.context
    scene = getattr(context, "scene", None)
    if scene is None or node_tree is None:
        return None

    root_tree = _node_editor_root_tree(context, node_tree)
    if root_tree is None:
        return None
    if node_tree == root_tree:
        return None

    runner = FlowRunner(root_tree, scene)
    group_path = _node_editor_group_path(context)
    runner.current_group_path = list(group_path)

    flow_group_inputs = _select_visible_flow_group_sockets(runner, node_tree, "NodeGroupInput", "outputs")
    flow_group_outputs = _select_visible_flow_group_sockets(runner, node_tree, "NodeGroupOutput", "inputs")
    if len(flow_group_inputs) == 1 and len(flow_group_outputs) == 1:
        flow_input_node, flow_input_socket = flow_group_inputs[0]
        expected_group_output, _output_socket = flow_group_outputs[0]
        start_node = _first_output_node(flow_input_node, flow_input_socket.name)
        if start_node is None:
            return None
        entries = _collect_visible_linear_flow_entries(
            runner,
            start_node,
            {"NodeGroupOutput"},
            group_path,
        )
        if not entries or entries[-1].get("node") != expected_group_output:
            return None
        owner_node_name = str(getattr(entries[0].get("node"), "name", "") or getattr(node_tree, "name", "") or "Underlay")
        return _build_underlay_context_from_entries(
            runner,
            entries,
            owner_node_name,
            entry_anchor={
                "node": flow_input_node,
                "output_name": str(getattr(flow_input_socket, "name", "") or ""),
            },
            mode="FLOW_GROUP",
        )

    task_starts, task_outputs = _select_visible_task_plan_nodes(runner, node_tree)
    if len(task_starts) != 1 or len(task_outputs) != 1:
        return None
    task_context = _build_task_underlay_context_from_output(runner, node_tree, task_outputs[0], group_path)
    if task_context is None:
        return None
    task_context["mode"] = "TASK_GROUP"
    return task_context


def _evaluate_underlay_trigger_state(runner, node, group_path):
    if runner is None or node is None:
        return None
    previous_group_path = list(getattr(runner, "current_group_path", []))
    try:
        runner.current_group_path = [
            dict(item)
            for item in list(group_path or [])
            if isinstance(item, dict)
        ]
        return bool(runner._input_bool(node, "Trigger", False))
    except Exception:
        return None
    finally:
        runner.current_group_path = previous_group_path


def _collect_branch_underlay_links(runner, branch_start_node, branch_plan, ordered_links, seen_links):
    normalized_plan = runner._normalize_local_segment_plan(branch_plan)
    step_refs = list(normalized_plan.get("step_refs", []) or [])
    end_ref = normalized_plan.get("end_ref") if isinstance(normalized_plan.get("end_ref"), dict) else None
    if step_refs:
        first_target_ref = step_refs[0]
        preferred_input_name = "Flow In"
    else:
        first_target_ref = end_ref
        preferred_input_name = "Branch Flow"
    if first_target_ref is not None:
        _extend_underlay_links_to_step_ref(
            runner,
            branch_start_node,
            "Branch Flow",
            first_target_ref,
            preferred_input_name,
            str(getattr(branch_start_node, "name", "") or "Branch Start"),
            ordered_links,
            seen_links,
        )
    _collect_plan_active_underlay_links(
        runner,
        normalized_plan,
        str(getattr(branch_start_node, "name", "") or "Branch Start"),
        ordered_links,
        seen_links,
        exit_step_ref=end_ref,
        exit_input_name="Branch Flow",
    )


def _collect_subflow_underlay_links(runner, join_node, join_step_ref, subflow_plan, ordered_links, seen_links):
    normalized_plan = runner._normalize_local_segment_plan(subflow_plan)
    start_node = runner._find_subflow_start_for_join(join_node)
    if start_node is None:
        return
    step_refs = list(normalized_plan.get("step_refs", []) or [])
    if step_refs:
        first_target_ref = step_refs[0]
        preferred_input_name = "Flow In"
    else:
        first_target_ref = join_step_ref
        preferred_input_name = "Subflow"
    if first_target_ref is not None:
        _extend_underlay_links_to_step_ref(
            runner,
            start_node,
            "Subflow",
            first_target_ref,
            preferred_input_name,
            str(getattr(join_node, "name", "") or "Subflow Join"),
            ordered_links,
            seen_links,
        )
    _collect_plan_active_underlay_links(
        runner,
        normalized_plan,
        str(getattr(join_node, "name", "") or "Subflow Join"),
        ordered_links,
        seen_links,
        exit_step_ref=join_step_ref,
        exit_input_name="Subflow",
    )


def _collect_plan_active_underlay_links(
    runner,
    plan,
    owner_node_name,
    ordered_links,
    seen_links,
    *,
    exit_step_ref=None,
    exit_input_name="Flow In",
):
    normalized_plan = runner._normalize_local_segment_plan(plan)
    step_refs = list(normalized_plan.get("step_refs", []) or [])
    if not step_refs:
        return

    step_nodes = [runner._resolve_step_ref(step_ref, owner_node_name) for step_ref in step_refs]
    branch_plans = dict(normalized_plan.get("branch_plans", {}) or {})
    subflow_plans = dict(normalized_plan.get("subflow_plans", {}) or {})

    for index, step_node in enumerate(step_nodes):
        step_ref = step_refs[index]
        group_path = list(step_ref.get("group_path", []) or [])
        next_step_ref = step_refs[index + 1] if index + 1 < len(step_refs) else exit_step_ref
        preferred_input_name = "Flow In" if index + 1 < len(step_refs) else exit_input_name
        node_type = str(getattr(step_node, "bl_idname", "") or "")

        if node_type == "AFNodeBranchStart":
            trigger_state = _evaluate_underlay_trigger_state(runner, step_node, group_path)
            branch_plan = branch_plans.get(index)
            if trigger_state is not False and isinstance(branch_plan, dict):
                _collect_branch_underlay_links(runner, step_node, branch_plan, ordered_links, seen_links)
            if trigger_state is True:
                break
            if next_step_ref is not None:
                _extend_underlay_links_to_step_ref(
                    runner,
                    step_node,
                    "Flow Out",
                    next_step_ref,
                    preferred_input_name,
                    owner_node_name,
                    ordered_links,
                    seen_links,
                )
            continue

        if node_type == "AFNodeSubflowJoin":
            trigger_state = _evaluate_underlay_trigger_state(runner, step_node, group_path)
            subflow_plan = subflow_plans.get(index)
            if trigger_state is not False and isinstance(subflow_plan, dict):
                _collect_subflow_underlay_links(
                    runner,
                    step_node,
                    step_ref,
                    subflow_plan,
                    ordered_links,
                    seen_links,
                )
            if next_step_ref is not None:
                _extend_underlay_links_to_step_ref(
                    runner,
                    step_node,
                    "Flow Out",
                    next_step_ref,
                    preferred_input_name,
                    owner_node_name,
                    ordered_links,
                    seen_links,
                )
            continue

        if next_step_ref is None:
            continue
        _extend_underlay_links_to_step_ref(
            runner,
            step_node,
            "Flow Out",
            next_step_ref,
            preferred_input_name,
            owner_node_name,
            ordered_links,
            seen_links,
        )


def _collect_active_flow_links_from_context_items(context_items, node_tree, root_tree):
    ordered_links = []
    seen_links = set()
    task_seen_outputs = set()
    for context_data in list(context_items or []):
        if not isinstance(context_data, dict):
            continue
        runner = context_data.get("runner")
        plan = context_data.get("plan")
        owner_node_name = str(context_data.get("owner_node_name", "") or "")
        _append_underlay_links_from_context(context_data, ordered_links, seen_links)
        if node_tree != root_tree or runner is None or not isinstance(plan, dict):
            continue
        task_contexts = []
        _collect_active_task_underlay_contexts_from_plan(
            runner,
            node_tree,
            plan,
            owner_node_name,
            task_contexts,
            task_seen_outputs,
        )
        for task_context in task_contexts:
            _append_underlay_links_from_context(task_context, ordered_links, seen_links)
    return ordered_links


def _active_flow_underlay_links(node_tree):
    if node_tree is None:
        return ()
    scene = getattr(bpy.context, "scene", None)
    root_tree = _node_editor_root_tree(bpy.context, node_tree)
    if node_tree == root_tree and root_tree is not None:
        cache_signature = (
            "ROOT",
            _cache_pointer_token(root_tree),
            int(node_tree_runtime_revision(root_tree)),
            _cache_pointer_token(scene),
            int(getattr(scene, "frame_current", 0) or 0) if scene is not None else 0,
            round(float(getattr(scene, "frame_subframe", 0.0) or 0.0), 6) if scene is not None else 0.0,
            _root_underlay_contexts_signature(root_tree, scene),
        )
    else:
        cache_signature = (
            "VISIBLE",
            _visible_underlay_context_signature(node_tree, root_tree, scene),
        )

    cache_key = _cache_pointer_token(node_tree)
    cached = _FLOW_UNDERLAY_LINK_CACHE.get(cache_key)
    if cached is not None and cached.get("signature") == cache_signature:
        return cached.get("links", ())

    context_items = []
    try:
        if node_tree == root_tree and root_tree is not None:
            context_items = _build_root_underlay_contexts(root_tree, scene)
        else:
            context_data = _build_visible_underlay_context(node_tree)
            if context_data is not None:
                context_items = [context_data]
    except Exception:
        context_items = []

    try:
        active_links = _collect_active_flow_links_from_context_items(context_items, node_tree, root_tree)
    except Exception:
        active_links = []
    active_links = tuple(active_links or ())
    _FLOW_UNDERLAY_LINK_CACHE[cache_key] = {
        "signature": cache_signature,
        "links": active_links,
    }
    if len(_FLOW_UNDERLAY_LINK_CACHE) > 16:
        stale_keys = [key for key in _FLOW_UNDERLAY_LINK_CACHE.keys() if key != cache_key]
        for stale_key in stale_keys[:-8]:
            _FLOW_UNDERLAY_LINK_CACHE.pop(stale_key, None)
    return active_links


def _flow_link_runtime_region_points(link, view2d, curving_factor, region):
    link_points = _flow_toggle_link_runtime_region_points(link, view2d, curving_factor)
    if not link_points or len(link_points) < 2:
        return None
    min_x = min(point[0] for point in link_points)
    max_x = max(point[0] for point in link_points)
    min_y = min(point[1] for point in link_points)
    max_y = max(point[1] for point in link_points)
    if (
        max_x < -_FLOW_SOCKET_VIEWPORT_MARGIN
        or min_x > float(region.width) + _FLOW_SOCKET_VIEWPORT_MARGIN
        or max_y < -_FLOW_SOCKET_VIEWPORT_MARGIN
        or min_y > float(region.height) + _FLOW_SOCKET_VIEWPORT_MARGIN
    ):
        return None
    return link_points


def _draw_flow_link_underlays(node_tree):
    region = getattr(bpy.context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return

    scale = _ui_scale_factor() * _node_editor_zoom_factor(region, view2d)
    line_width = max(1.2, 1.75 * scale) * 6.0
    curving_factor = _flow_toggle_link_curving_factor()

    for link in _active_flow_underlay_links(node_tree):
        link_points = _flow_link_runtime_region_points(link, view2d, curving_factor, region)
        if link_points is None:
            continue
        _draw_polyline_strip(
            link_points,
            _FLOW_SOCKET_LINK_UNDERLAY_COLOR,
            line_width=line_width,
        )


def _draw_flow_socket_endpoint_markers(node_tree):
    region = getattr(bpy.context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return

    scale = _ui_scale_factor() * _node_editor_zoom_factor(region, view2d)
    for node in _iter_visible_nodes(node_tree, region=region, view2d=view2d, margin=120.0):
        if str(getattr(node, "bl_idname", "") or "") == "NodeReroute":
            continue

        for socket in _visible_input_sockets(node):
            if not is_flow_socket(socket):
                continue
            center = _socket_runtime_region_center(socket, view2d)
            if center is None:
                continue
            _draw_flow_socket_marker(center[0], center[1], scale)

        for socket in _visible_output_sockets(node):
            if not is_flow_socket(socket):
                continue
            center = _socket_runtime_region_center(socket, view2d)
            if center is None:
                continue
            _draw_flow_socket_marker(center[0], center[1], scale)


def _custom_header_node_types():
    return {
        "AFNodeStart",
        "AFNodeFlowToggle",
        "AFNodeTaskStatusOverride",
        "AFNodeRepeatStart",
        "AFNodeRepeatEnd",
        "AFNodeSubflowStart",
        "AFNodeSubflowJoin",
        "AFNodeBranchStart",
        "AFNodeBranchEnd",
        "AFNodeEnd",
        "AFNodeWaitForTask",
        "AFNodeDelayWait",
        "AFNodeReloadAfterTask",
        "AFNodeTaskStart",
        "AFNodeTaskOutput",
        "AFNodeResolveTaskRef",
        "AFNodeBakeTask",
        "AFNodePropertyPackageBakeTarget",
        "AFNodeTaskStep",
        "AFNodePhysicsBakeSettings",
        "AFNodePhysicsBakeTask",
        "AFNodeEvaluateTaskDependencies",
        "AFNodeRunTaskPlan",
        "AFNodeRunBackgroundTaskPlan",
        "AFNodeSetGeometryAttribute",
        "AFNodePublishGeometryAttribute",
        "AFNodeCreatePropertyPackage",
        "AFNodeRefreshPropertyPackage",
        "AFNodeStorePropertyPackage",
        "AFNodeReadPropertyPackage",
        "AFNodeApplyObjectProperties",
        "AFNodeApplyPropertyPackage",
        "AFNodeRecordPropertyPackage",
        "AFNodeParsePropertyPackage",
        "AFNodeFilterPropertyPackage",
        "AFNodeMergePropertyPackages",
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
        "AFNodeSmoothstep",
        "AFNodeRandomValue",
        "AFNodeSetActiveCamera",
        "AFNodeRenderTarget",
        "AFNodeRenderTask",
    }


def _collapsed_custom_header_offset_y(scale, max_socket_count):
    extra_socket_count = max(0, int(max_socket_count) - 2)
    return  (-3.5 - 5.0 * extra_socket_count) * scale


def _collapsed_custom_header_height(scale, max_socket_count):
    extra_socket_count = max(0, int(max_socket_count) - 2)
    return (27.0 + 10.0 * extra_socket_count) * scale


def _draw_custom_math_header(node_tree):
    region = getattr(bpy.context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return

    scale = _ui_scale_factor() * _node_editor_zoom_factor(region, view2d)
    header_node_types = _custom_header_node_types()
    blf.size(_STORE_CHIP_FONT_ID, max(1, int(round(11 * scale))))
    for node in _iter_visible_nodes(node_tree, region=region, view2d=view2d, margin=120.0):
        if getattr(node, "bl_idname", "") not in header_node_types:
            continue
        fill_color, outline_color, text_color = _custom_math_header_palette(node)
        header_layout = _custom_header_region_layout(node, region, view2d, scale)
        if header_layout is None:
            continue
        left = float(header_layout["left"])
        right = float(header_layout["right"])
        bottom = float(header_layout["bottom"])
        draw_top = float(header_layout["draw_top"])
        draw_right = float(header_layout["draw_right"])
        center_y = float(header_layout["center_y"])
        header_height = float(header_layout["header_height"])

        if bool(header_layout["is_collapsed"]):
            _draw_pixel_rounded_rect(
                left,
                bottom,
                draw_right,
                draw_top,
                fill_color,
                outline_color=outline_color,
                line_width=max(0.75, 0.8 * scale),
                radius=3.0 * scale,
            )
        else:
            _draw_top_rounded_pixel_rect(
                left,
                bottom,
                draw_right,
                draw_top,
                fill_color,
                outline_color=outline_color,
                line_width=max(0.75, 0.8 * scale),
                radius=3.0 * scale,
            )

        triangle_size = max(6.0, 7.0 * scale)
        triangle_center_x = left + (12.0 * scale)
        triangle_center_y = center_y
        _draw_disclosure_triangle(
            triangle_center_x,
            triangle_center_y,
            triangle_size,
            bool(getattr(node, "hide", False)),
            text_color,
        )

        title = _custom_header_title(node)
        text_max_width = max(0.0, (right - left) - (30.0 * scale))
        clipped_title = _clip_text_to_width(_STORE_CHIP_FONT_ID, title, text_max_width)
        _title_width, title_height = blf.dimensions(_STORE_CHIP_FONT_ID, clipped_title)
        blf.color(_STORE_CHIP_FONT_ID, *text_color)
        text_x = left + (22.0 * scale)
        text_y = _custom_header_text_y(center_y, title_height, scale)
        blf.position(_STORE_CHIP_FONT_ID, text_x, text_y, 0)
        blf.draw(_STORE_CHIP_FONT_ID, clipped_title)

def _draw_repeat_overlay():
    if gpu is None or batch_for_shader is None:
        return
    try:
        space = getattr(bpy.context, "space_data", None)
        node_tree = getattr(space, "edit_tree", None) if space is not None else None
        if node_tree is not None and getattr(node_tree, "bl_idname", "") == "AFNodeTreeType":
            if _ui_pref_enabled("show_custom_flow_links", True):
                _draw_flow_link_underlays(node_tree)
            if _ui_pref_enabled("show_flow_zone_overlays", True):
                for draw_item in _cached_overlay_pair_draw_items(node_tree):
                    hull = draw_item.get("hull", ())
                    if hull:
                        fill_color, outline_color = _overlay_pair_palette(draw_item.get("kind", "REPEAT"))
                        overlay_radius = max(
                            4.0,
                            5.5 * _ui_scale_factor() * _node_editor_zoom_factor(),
                        )
                        _draw_polygon(
                            hull,
                            fill_color=fill_color,
                            outline_color=outline_color,
                            line_width=1.5,
                            radius=overlay_radius,
                        )
            if _ui_pref_enabled("show_runtime_node_highlights", True):
                for node, color, line_width, style in _get_overlay_targets(bpy.context):
                    _draw_node_highlight_fill(node, color, line_width, style=style)
            _draw_quick_run_buttons(node_tree)
            if _ui_pref_enabled("show_property_status_chips", True):
                from .chips import _draw_property_package_backdrop_tags

                _draw_property_package_backdrop_tags(node_tree)
    except Exception:
        return


def _draw_status_overlay():
    if gpu is None or batch_for_shader is None:
        return
    try:
        space = getattr(bpy.context, "space_data", None)
        node_tree = getattr(space, "edit_tree", None) if space is not None else None
        if node_tree is not None and getattr(node_tree, "bl_idname", "") == "AFNodeTreeType":
            if _ui_pref_enabled("show_flow_toggle_trigger_links", True):
                _draw_flow_toggle_trigger_links(node_tree)
            if _ui_pref_enabled("show_custom_node_headers", True):
                _draw_custom_math_header(node_tree)
            if _ui_pref_enabled("show_custom_flow_sockets", True):
                _draw_flow_socket_endpoint_markers(node_tree)
            from .chips import _draw_group_path_chip, _draw_run_mode_chip

            run_chip_bottom = _draw_run_mode_chip(getattr(bpy.context, "scene", None))
            group_chip_top = (float(run_chip_bottom) - (8.0 * _ui_scale_factor())) if run_chip_bottom is not None else None
            _draw_group_path_chip(top_y=group_chip_top)
    except Exception:
        return


def register_flow_overlay_handler():
    global _FLOW_REPEAT_OVERLAY_HANDLER, _FLOW_STATUS_OVERLAY_HANDLER
    if _FLOW_REPEAT_OVERLAY_HANDLER is None:
        _FLOW_REPEAT_OVERLAY_HANDLER = bpy.types.SpaceNodeEditor.draw_handler_add(
            _draw_repeat_overlay,
            (),
            "WINDOW",
            "BACKDROP",
        )
    if _FLOW_STATUS_OVERLAY_HANDLER is not None:
        return
    _FLOW_STATUS_OVERLAY_HANDLER = bpy.types.SpaceNodeEditor.draw_handler_add(
        _draw_status_overlay,
        (),
        "WINDOW",
        "POST_PIXEL",
    )


def unregister_flow_overlay_handler():
    global _FLOW_REPEAT_OVERLAY_HANDLER, _FLOW_STATUS_OVERLAY_HANDLER
    if _FLOW_REPEAT_OVERLAY_HANDLER is not None:
        try:
            bpy.types.SpaceNodeEditor.draw_handler_remove(_FLOW_REPEAT_OVERLAY_HANDLER, "WINDOW")
        except Exception:
            pass
        _FLOW_REPEAT_OVERLAY_HANDLER = None
    if _FLOW_STATUS_OVERLAY_HANDLER is not None:
        try:
            bpy.types.SpaceNodeEditor.draw_handler_remove(_FLOW_STATUS_OVERLAY_HANDLER, "WINDOW")
        except Exception:
            pass
        _FLOW_STATUS_OVERLAY_HANDLER = None
