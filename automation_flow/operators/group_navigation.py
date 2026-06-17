import bpy

from .editor_utils import _get_active_flow_tree
from .group_helpers import (
    _enter_group_node,
    _exit_current_group,
    _find_node_under_cursor,
    _get_active_group_node,
    _make_group_nav_target,
    _select_node_under_cursor,
)


class AF_OT_EditGroup(bpy.types.Operator):
    bl_idname = "af.edit_group"
    bl_label = "Edit Group"
    bl_description = "Enter the selected AF group for editing"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _get_active_group_node(context) is not None

    def execute(self, context):
        group_node = _get_active_group_node(context)
        if group_node is None:
            return {"CANCELLED"}
        return _enter_group_node(context, group_node, reporter=self)


class AF_OT_ExitGroup(bpy.types.Operator):
    bl_idname = "af.exit_group"
    bl_label = "Exit Group"
    bl_description = "Return to the parent AF tree"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or getattr(space, "type", "") != "NODE_EDITOR":
            return False
        return len(getattr(space, "path", [])) > 1

    def execute(self, context):
        return _exit_current_group(context, reporter=self)


class AF_OT_GroupDoubleClickNavigate(bpy.types.Operator):
    bl_idname = "af.group_double_click_navigate"
    bl_label = "Navigate AF Group"
    bl_description = "Double-click a group node to enter it, or double-click empty group space to exit"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return _get_active_flow_tree(context) is not None

    def invoke(self, context, event):
        hit_node = _select_node_under_cursor(context, event)
        group_hit_node = None
        if (
            hit_node is not None
            and getattr(hit_node, "bl_idname", "") == "AFNodeGroup"
            and getattr(hit_node, "group_tree", None) is not None
        ):
            group_hit_node = hit_node
        elif hit_node is None:
            group_hit_node = _find_node_under_cursor(context, event, groups_only=True)
            hit_node = group_hit_node if group_hit_node is not None else _find_node_under_cursor(context, event)
        target = _make_group_nav_target(context, group_hit_node if group_hit_node is not None else hit_node)

        if target == "BLANK":
            return _exit_current_group(context, reporter=self)

        if target == "GROUP":
            target_node = hit_node
        else:
            return {"CANCELLED"} if hit_node is not None else {"PASS_THROUGH"}

        if target_node is not None and getattr(target_node, "bl_idname", "") != "AFNodeGroup":
            return {"PASS_THROUGH"}

        if target_node is not None and getattr(target_node, "group_tree", None) is None:
            return {"PASS_THROUGH"}

        if target_node is None:
            return {"PASS_THROUGH"}

        node_tree = getattr(target_node, "id_data", None)
        if node_tree is not None:
            node_tree.nodes.active = target_node
        target_node.select = True
        return _enter_group_node(context, target_node, reporter=self)


GROUP_NAVIGATION_OPERATOR_CLASSES = (
    AF_OT_EditGroup,
    AF_OT_ExitGroup,
    AF_OT_GroupDoubleClickNavigate,
)
