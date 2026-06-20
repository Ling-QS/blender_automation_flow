import bpy


def _tag_flow_node_editor_redraw(tree_name=None):
    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != "NODE_EDITOR":
                continue
            if tree_name is None:
                area.tag_redraw()
                continue
            for space in area.spaces:
                if space.type != "NODE_EDITOR":
                    continue
                node_tree = getattr(space, "edit_tree", None)
                if node_tree is not None and node_tree.name == tree_name:
                    area.tag_redraw()
                    break


def _select_active_node(node_tree, node):
    if node_tree is None or node is None:
        return
    for other in getattr(node_tree, "nodes", []):
        other.select = False
    node.select = True
    node_tree.nodes.active = node


def _invoke_node_translate_attach():
    try:
        return bpy.ops.node.translate_attach_remove_on_cancel("INVOKE_DEFAULT")
    except Exception:
        pass
    try:
        return bpy.ops.transform.translate("INVOKE_DEFAULT")
    except Exception:
        return {"FINISHED"}


def _get_active_flow_tree(context):
    space = context.space_data
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        return None
    tree = getattr(space, "edit_tree", None)
    if tree is None:
        return None
    if tree.bl_idname != "AFNodeTreeType":
        return None
    return tree


def _node_editor_cursor_location(context, fallback=(0.0, 0.0)):
    space = getattr(context, "space_data", None)
    if space is not None:
        cursor_location = getattr(space, "cursor_location", None)
        if cursor_location is not None:
            try:
                return cursor_location.copy()
            except Exception:
                try:
                    return (float(cursor_location[0]), float(cursor_location[1]))
                except Exception:
                    pass

    region = getattr(context, "region", None)
    view2d = getattr(region, "view2d", None) if region is not None else None
    if region is not None and view2d is not None:
        try:
            center_x = int(region.width * 0.5)
            center_y = int(region.height * 0.5)
            return view2d.region_to_view(center_x, center_y)
        except Exception:
            pass

    return fallback


def _set_node_editor_cursor_from_event(context, event):
    if event is None:
        return False
    space = getattr(context, "space_data", None)
    area = getattr(context, "area", None)
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        return False
    if area is None or getattr(area, "type", "") != "NODE_EDITOR":
        return False

    candidate_regions = []
    context_region = getattr(context, "region", None)
    if context_region is not None and getattr(context_region, "type", "") == "WINDOW":
        candidate_regions.append(context_region)
    for region in getattr(area, "regions", []):
        if getattr(region, "type", "") != "WINDOW":
            continue
        if region in candidate_regions:
            continue
        candidate_regions.append(region)

    for region in candidate_regions:
        try:
            if region is context_region:
                mouse_x = int(event.mouse_region_x)
                mouse_y = int(event.mouse_region_y)
            else:
                mouse_x = int(event.mouse_x - region.x)
                mouse_y = int(event.mouse_y - region.y)
                if mouse_x < 0 or mouse_y < 0 or mouse_x > int(region.width) or mouse_y > int(region.height):
                    continue
            if hasattr(space, "cursor_location_from_region"):
                space.cursor_location_from_region(mouse_x, mouse_y)
            else:
                view2d = getattr(region, "view2d", None)
                if view2d is None:
                    continue
                space.cursor_location = view2d.region_to_view(mouse_x, mouse_y)
            return True
        except Exception:
            continue
    return False
