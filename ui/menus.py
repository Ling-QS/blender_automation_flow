import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..i18n import af_iface
from .menu_config import (
    FLOW_MENU_PAIRED_NODES,
    FLOW_MENU_REGULAR_NODES,
    FLOW_PROCESS_MENU_LABEL,
    FLOW_STRUCTURES_MENU_LABEL,
    GROUP_ASSET_MENU_ENTRIES,
    GROUP_ASSET_MENU_TITLE,
    NODE_MENU_GROUPS,
    NODE_MENU_SECTIONS,
    PROPERTY_CONTEXT_DATA_MENU_NODES,
    PROPERTY_PACKAGE_MENU_NODES,
)


def _add_nodes_group_menu_idname(title):
    sanitized = "".join(ch for ch in str(title or "") if ch.isalnum())
    return f"AF_MT_add_nodes_{sanitized.lower()}"


def _add_nodes_group_menu_class_name(title):
    sanitized = "".join(ch for ch in str(title or "") if ch.isalnum())
    return f"AF_MT_AddNodes_{sanitized}"


def _add_nodes_section_menu_idname(title):
    sanitized = "".join(ch for ch in str(title or "") if ch.isalnum())
    return f"AF_MT_add_nodes_section_{sanitized.lower()}"


def _add_nodes_section_menu_class_name(title):
    sanitized = "".join(ch for ch in str(title or "") if ch.isalnum())
    return f"AF_MT_AddNodesSection_{sanitized}"


def _draw_add_node_entries(layout, node_types):
    from ..nodes import PAIR_NODE_TYPE_MAP

    for node_type, label in node_types:
        if node_type in PAIR_NODE_TYPE_MAP:
            op = layout.operator("af.add_paired_flow_node", text=af_iface(label, compact=True))
            op.node_type = node_type
        else:
            op = layout.operator("node.add_node", text=af_iface(label, compact=True))
            op.type = node_type
            op.use_transform = True


def _make_add_nodes_group_menu(title, node_types):
    def draw(self, context):
        del context
        _draw_add_node_entries(self.layout, node_types)

    return type(
        _add_nodes_group_menu_class_name(title),
        (bpy.types.Menu,),
        {
            "bl_idname": _add_nodes_group_menu_idname(title),
            "bl_label": title,
            "draw": draw,
        },
    )


ADD_NODE_GROUP_MENUS = tuple(_make_add_nodes_group_menu(title, node_types) for title, node_types in NODE_MENU_GROUPS)


def _make_add_nodes_section_menu(title, group_titles):
    def draw(self, context):
        del context
        layout = self.layout
        for group_title in group_titles:
            if str(group_title or "") == GROUP_ASSET_MENU_TITLE:
                layout.menu(AF_MT_AddGroupAssets.bl_idname, text=iface_(GROUP_ASSET_MENU_TITLE))
            else:
                layout.menu(_add_nodes_group_menu_idname(group_title), text=iface_(group_title))

    return type(
        _add_nodes_section_menu_class_name(title),
        (bpy.types.Menu,),
        {
            "bl_idname": _add_nodes_section_menu_idname(title),
            "bl_label": title,
            "draw": draw,
        },
    )


ADD_NODE_SECTION_MENUS = tuple(_make_add_nodes_section_menu(title, group_titles) for title, group_titles in NODE_MENU_SECTIONS)


class AF_MT_AddFlowNodes(bpy.types.Menu):
    bl_idname = "AF_MT_add_flow_nodes"
    bl_label = "Flow"
    bl_translation_context = "*"

    def draw(self, context):
        del context
        layout = self.layout
        layout.menu(AF_MT_AddFlowRegularNodes.bl_idname, text=iface_(FLOW_PROCESS_MENU_LABEL))
        layout.menu(AF_MT_AddFlowPairedNodes.bl_idname, text=iface_(FLOW_STRUCTURES_MENU_LABEL))


class AF_MT_AddPropertyNodes(bpy.types.Menu):
    bl_idname = "AF_MT_add_property_nodes"
    bl_label = "Property"

    def draw(self, context):
        del context
        layout = self.layout
        layout.menu(AF_MT_AddPropertyContextNodes.bl_idname, text=iface_("Context & Data"))
        layout.menu(AF_MT_AddPropertyPackageNodes.bl_idname, text=iface_("Prop Pack Ops"))


class AF_MT_AddFlowRegularNodes(bpy.types.Menu):
    bl_idname = "AF_MT_add_flow_regular_nodes"
    bl_label = FLOW_PROCESS_MENU_LABEL
    bl_translation_context = "*"

    def draw(self, context):
        del context
        _draw_add_node_entries(self.layout, FLOW_MENU_REGULAR_NODES)


class AF_MT_AddFlowPairedNodes(bpy.types.Menu):
    bl_idname = "AF_MT_add_flow_paired_nodes"
    bl_label = FLOW_STRUCTURES_MENU_LABEL
    bl_translation_context = "*"

    def draw(self, context):
        del context
        _draw_add_node_entries(self.layout, FLOW_MENU_PAIRED_NODES)


class AF_MT_AddPropertyContextNodes(bpy.types.Menu):
    bl_idname = "AF_MT_add_property_context_nodes"
    bl_label = "Context & Data"

    def draw(self, context):
        del context
        _draw_add_node_entries(self.layout, PROPERTY_CONTEXT_DATA_MENU_NODES)


class AF_MT_AddPropertyPackageNodes(bpy.types.Menu):
    bl_idname = "AF_MT_add_property_package_nodes"
    bl_label = "Prop Pack Ops"

    def draw(self, context):
        del context
        _draw_add_node_entries(self.layout, PROPERTY_PACKAGE_MENU_NODES)


class AF_MT_AddNodes(bpy.types.Menu):
    bl_idname = "AF_MT_add_nodes"
    bl_label = "Automation Flow"

    def draw(self, context):
        del context
        layout = self.layout
        layout.menu(AF_MT_AddFlowNodes.bl_idname, text=iface_("Flow"))
        layout.menu(_add_nodes_section_menu_idname("Task"), text=iface_("Task"))
        layout.menu(AF_MT_AddPropertyNodes.bl_idname, text=iface_("Property"))
        layout.menu(_add_nodes_section_menu_idname("Scene"), text=iface_("Scene"))
        layout.menu(_add_nodes_group_menu_idname("Inputs"), text=iface_("Inputs"))
        layout.menu(_add_nodes_section_menu_idname("Math"), text=iface_("Math"))
        layout.menu(AF_MT_AddGroupAssets.bl_idname, text=iface_(GROUP_ASSET_MENU_TITLE))


class AF_MT_AddGroupAssets(bpy.types.Menu):
    bl_idname = "AF_MT_add_group_assets"
    bl_label = GROUP_ASSET_MENU_TITLE

    def draw(self, context):
        del context
        layout = self.layout
        for label, asset_id in GROUP_ASSET_MENU_ENTRIES:
            operator = layout.operator("af.add_group_asset_node", text=iface_(label), icon="NODETREE")
            operator.asset_id = asset_id


def _draw_add_menu(self, context):
    space = context.space_data
    if space is None or getattr(space, "tree_type", "") != "AFNodeTreeType":
        return
    self.layout.separator()
    self.layout.menu(AF_MT_AddFlowNodes.bl_idname, text=iface_("Flow"))
    self.layout.menu(_add_nodes_section_menu_idname("Task"), text=iface_("Task"))
    self.layout.menu(AF_MT_AddPropertyNodes.bl_idname, text=iface_("Property"))
    self.layout.menu(_add_nodes_section_menu_idname("Scene"), text=iface_("Scene"))
    self.layout.menu(_add_nodes_group_menu_idname("Inputs"), text=iface_("Inputs"))
    self.layout.menu(_add_nodes_section_menu_idname("Math"), text=iface_("Math"))
    self.layout.menu(AF_MT_AddGroupAssets.bl_idname, text=iface_(GROUP_ASSET_MENU_TITLE))


def _draw_node_context_menu(self, context):
    from ..operators import find_bake_task_paths_for_node

    space = context.space_data
    active_node = getattr(context, "active_node", None)
    is_flow_tree = space is not None and getattr(space, "tree_type", "") == "AFNodeTreeType"
    if is_flow_tree:
        tree = getattr(space, "edit_tree", None)
        selected = [node for node in getattr(tree, "nodes", []) if getattr(node, "select", False)] if tree is not None else []
        if selected:
            self.layout.separator()
            self.layout.operator("af.create_group_from_selection", text=iface_("Create Group From Selection"), icon="NODETREE")
        if active_node is not None and getattr(active_node, "bl_idname", "") == "AFNodeGroup" and getattr(active_node, "group_tree", None) is not None:
            self.layout.operator("af.edit_group", text=iface_("Enter Group"), icon="NODETREE")
        if len(getattr(space, "path", [])) > 1:
            self.layout.operator("af.exit_group", text=iface_("Exit Group"), icon="LOOP_BACK")
        if active_node is not None and getattr(active_node, "bl_idname", "") in {
            "AFNodeModifierPropertyData",
            "AFNodeObjectDisplayPropertyData",
            "AFNodeObjectTransformPropertyData",
        }:
            self.layout.separator()
            self.layout.operator("af.hide_disabled_property_data_sockets", text=iface_("Hide Disabled Field Sockets"), icon="HIDE_OFF")

    paths = find_bake_task_paths_for_node(context)
    if not paths:
        return
    self.layout.separator()
    if len(paths) == 1:
        op = self.layout.operator("af.copy_bake_task_path", text=iface_("Copy Bake Task Path"))
        op.task_path = paths[0]
        return
    self.layout.label(text=iface_("Copy Bake Task Path"))
    for task_path in paths:
        op = self.layout.operator("af.copy_bake_task_path", text=task_path)
        op.task_path = task_path

MENU_CLASSES = (
    AF_MT_AddFlowNodes,
    AF_MT_AddFlowRegularNodes,
    AF_MT_AddFlowPairedNodes,
    AF_MT_AddPropertyNodes,
    AF_MT_AddPropertyContextNodes,
    AF_MT_AddPropertyPackageNodes,
    *ADD_NODE_GROUP_MENUS,
    *ADD_NODE_SECTION_MENUS,
    AF_MT_AddGroupAssets,
    AF_MT_AddNodes,
)
