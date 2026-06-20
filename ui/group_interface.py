import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..i18n import af_iface
from ..operators import GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE, GROUP_INTERFACE_SOCKET_TYPE_ITEMS


def _is_group_editing(space):
    return space is not None and len(getattr(space, "path", [])) > 1


def _active_group_interface_item(tree):
    if tree is None:
        return None
    interface = getattr(tree, "interface", None)
    if interface is None:
        return None
    return getattr(interface, "active", None)


def _group_interface_socket_type_label(socket_type):
    socket_type = str(socket_type or "")
    label = str(GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE.get(socket_type, socket_type or iface_("Socket")))
    return af_iface(label)


def _draw_group_interface_item_details(layout, item):
    if item is None:
        layout.label(text=iface_("No interface item selected"))
        return

    layout.use_property_split = True
    layout.use_property_decorate = False
    col = layout.column(align=True)
    col.prop(item, "name", text=iface_("Name"))
    if hasattr(item, "description"):
        col.prop(item, "description", text=iface_("Description"))

    item_type = str(getattr(item, "item_type", "") or "")
    if item_type == "PANEL":
        col.label(text=f"{iface_('Items')}: {len(getattr(item, 'interface_items', []))}")
        return

    socket_type_prop = item.bl_rna.properties.get("socket_type")
    if socket_type_prop is not None and not socket_type_prop.is_readonly:
        row = col.row(align=True)
        row.label(text=iface_("Type"))
        row.menu(
            "AF_MT_group_interface_socket_type",
            text=_group_interface_socket_type_label(getattr(item, "socket_type", "")),
        )
    if bool(getattr(item, "is_panel_toggle", False)):
        col.label(text=iface_("Panel Toggle"))


class AF_MT_GroupInterfaceAddInputSocket(bpy.types.Menu):
    bl_label = "Add Input Socket"
    bl_idname = "AF_MT_group_interface_add_input_socket"

    def draw(self, context):
        del context
        layout = self.layout
        for socket_type, label, icon in GROUP_INTERFACE_SOCKET_TYPE_ITEMS:
            op = layout.operator("af.add_group_interface_socket", text=af_iface(label), icon=icon)
            op.in_out = "INPUT"
            op.socket_type = socket_type


class AF_MT_GroupInterfaceAddOutputSocket(bpy.types.Menu):
    bl_label = "Add Output Socket"
    bl_idname = "AF_MT_group_interface_add_output_socket"

    def draw(self, context):
        del context
        layout = self.layout
        for socket_type, label, icon in GROUP_INTERFACE_SOCKET_TYPE_ITEMS:
            op = layout.operator("af.add_group_interface_socket", text=af_iface(label), icon=icon)
            op.in_out = "OUTPUT"
            op.socket_type = socket_type


class AF_MT_GroupInterfaceAddItem(bpy.types.Menu):
    bl_label = "Add Group Interface Item"
    bl_idname = "AF_MT_group_interface_add_item"

    def draw(self, context):
        layout = self.layout
        layout.menu("AF_MT_group_interface_add_input_socket", text=iface_("Input Socket"), icon="IMPORT")
        layout.menu("AF_MT_group_interface_add_output_socket", text=iface_("Output Socket"), icon="EXPORT")
        layout.separator()
        panel_op = layout.operator("node.interface_item_new", text=iface_("Panel"), icon="FILE_FOLDER")
        panel_op.item_type = "PANEL"


class AF_MT_GroupInterfaceSocketType(bpy.types.Menu):
    bl_label = "Group Interface Socket Type"
    bl_idname = "AF_MT_group_interface_socket_type"

    def draw(self, context):
        del context
        layout = self.layout
        for socket_type, label, icon in GROUP_INTERFACE_SOCKET_TYPE_ITEMS:
            op = layout.operator("af.set_group_interface_socket_type", text=af_iface(label), icon=icon)
            op.socket_type = socket_type


class AF_UL_GroupInterfaceItems(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        del context, data, icon, active_data, active_propname, index, flt_flag
        item_type = str(getattr(item, "item_type", "") or "")
        if item_type == "PANEL":
            layout.label(text=str(getattr(item, "name", iface_("Panel"))), icon="FILE_FOLDER")
            return
        if bool(getattr(item, "is_panel_toggle", False)):
            icon_name = "CHECKBOX_HLT"
        else:
            icon_name = "IMPORT" if str(getattr(item, "in_out", "") or "") == "INPUT" else "EXPORT"
        direction = iface_("Input") if str(getattr(item, "in_out", "") or "") == "INPUT" else iface_("Output")
        split = layout.split(factor=0.82, align=True)
        socket_name = str(getattr(item, "name", iface_("Socket")))
        split.label(text=af_iface(socket_name), icon=icon_name, translate=False)
        split.label(text=direction, translate=False)


class AF_PT_GroupInterfacePanel(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "AF"
    bl_label = "Group Interface"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if not (space and space.type == "NODE_EDITOR" and getattr(space, "tree_type", "") == "AFNodeTreeType"):
            return False
        if not _is_group_editing(space):
            return False
        tree = getattr(space, "edit_tree", None)
        return tree is not None and bool(getattr(tree, "bl_use_group_interface", False))

    def draw(self, context):
        layout = self.layout
        space = context.space_data
        tree = getattr(space, "edit_tree", None)
        interface = getattr(tree, "interface", None) if tree is not None else None
        active_item = _active_group_interface_item(tree)

        row = layout.row()
        row.template_list(
            "AF_UL_GroupInterfaceItems",
            "",
            interface,
            "items_tree",
            interface,
            "active_index",
            rows=6,
        )
        col = row.column(align=True)
        col.menu("AF_MT_group_interface_add_item", icon="ADD", text="")
        remove_col = col.column(align=True)
        remove_col.enabled = active_item is not None
        remove_col.operator("af.remove_active_group_interface_item", icon="REMOVE", text="")
        specials_col = col.column(align=True)
        specials_col.enabled = active_item is not None
        specials_col.menu("NODE_MT_node_tree_interface_context_menu", icon="DOWNARROW_HLT", text="")

        layout.separator()
        _draw_group_interface_item_details(layout, active_item)


GROUP_INTERFACE_CLASSES = (
    AF_MT_GroupInterfaceAddInputSocket,
    AF_MT_GroupInterfaceAddOutputSocket,
    AF_MT_GroupInterfaceAddItem,
    AF_MT_GroupInterfaceSocketType,
    AF_UL_GroupInterfaceItems,
    AF_PT_GroupInterfacePanel,
)
