import bpy
from ..node_system.socket_aliases import (
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)
from .editor_utils import _tag_flow_node_editor_redraw
from .group_helpers import _group_interface_context, _unique_interface_name

GROUP_INTERFACE_SOCKET_TYPE_ITEMS = (
    ("AFSocketFlow", "Flow", "SORTTIME"),
    ("AFSocketCollectionList", "Collection List", "OUTLINER_COLLECTION"),
    ("AFSocketString", "String", "SORTALPHA"),
    ("AFSocketObjectList", "Object List", "OUTLINER_OB_GROUP_INSTANCE"),
    ("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME, "NODE_COMPOSITING"),
    ("AFSocketPropertyDefinition", PROPERTY_DEFINITION_SOCKET_NAME, "PREFERENCES"),
    ("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_SOCKET_NAME, "SETTINGS"),
    ("AFSocketTaskRef", "Task Ref", "PLAY"),
    ("AFSocketTaskPlan", "Task Plan", "PLAY"),
    ("AFSocketTaskHandle", "Task Handle", "DECORATE_OVERRIDE"),
    ("NodeSocketBool", "Boolean", "CHECKBOX_HLT"),
    ("NodeSocketFloat", "Float", "RNDCURVE"),
    ("NodeSocketInt", "Integer", "SORTBYEXT"),
    ("NodeSocketVector", "Vector", "EMPTY_AXIS"),
    ("NodeSocketRotation", "Rotation", "DRIVER_ROTATIONAL_DIFFERENCE"),
    ("NodeSocketMatrix", "Matrix", "SNAP_VOLUME"),
    ("AFSocketDisplayType", "Display Type", "DOWNARROW_HLT"),
    ("AFSocketObjectInteractionMode", "Object Interaction Mode", "DOWNARROW_HLT"),
    ("AFSocketRotationMode", "Rotation Mode", "DOWNARROW_HLT"),
    ("AFSocketViewportShadingMode", "Viewport Shading Mode", "DOWNARROW_HLT"),
    ("AFSocketReport", "Report", "TEXT"),
)

GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE = {
    socket_type: label for socket_type, label, _icon in GROUP_INTERFACE_SOCKET_TYPE_ITEMS
}

_GROUP_INTERFACE_SOCKET_TYPE_ALIASES = {
    "AFSocketString": "NodeSocketString",
}

for socket_type, label in tuple(GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE.items()):
    resolved_socket_type = str(_GROUP_INTERFACE_SOCKET_TYPE_ALIASES.get(socket_type, socket_type) or socket_type)
    GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE.setdefault(resolved_socket_type, label)


def _resolved_group_interface_socket_type(socket_type):
    socket_type = str(socket_type or "").strip()
    return str(_GROUP_INTERFACE_SOCKET_TYPE_ALIASES.get(socket_type, socket_type) or socket_type)


def _group_interface_socket_default_name(socket_type):
    return str(GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE.get(str(socket_type or ""), "Socket") or "Socket")


class AF_OT_AddGroupInterfaceSocket(bpy.types.Operator):
    bl_idname = "af.add_group_interface_socket"
    bl_label = "Add Group Interface Socket"
    bl_description = "Add a filtered Group Interface socket type from the plugin panel"
    bl_options = {"REGISTER", "UNDO"}

    in_out: bpy.props.EnumProperty(
        name="Direction",
        items=(
            ("INPUT", "Input", "Add an input interface socket"),
            ("OUTPUT", "Output", "Add an output interface socket"),
        ),
        default="INPUT",
    )
    socket_type: bpy.props.StringProperty(name="Socket Type", default="")

    def execute(self, context):
        tree, interface = _group_interface_context(context)
        if tree is None or interface is None:
            self.report({"ERROR"}, "Open an Automation Flow group in the Node Editor first")
            return {"CANCELLED"}

        socket_type = str(self.socket_type or "").strip()
        in_out = str(self.in_out or "INPUT").strip().upper()
        if socket_type not in GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE:
            self.report({"ERROR"}, "Unsupported Group Interface socket type")
            return {"CANCELLED"}
        if in_out not in {"INPUT", "OUTPUT"}:
            self.report({"ERROR"}, "Unsupported Group Interface direction")
            return {"CANCELLED"}

        used_names = {
            str(getattr(item, "name", "") or "")
            for item in getattr(interface, "items_tree", [])
            if getattr(item, "item_type", "") == "SOCKET"
        }
        base_name = _group_interface_socket_default_name(socket_type)
        socket_name = _unique_interface_name(base_name, used_names)

        try:
            item = interface.new_socket(
                socket_name,
                socket_type=_resolved_group_interface_socket_type(socket_type),
                in_out=in_out,
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to add Group Interface socket: {exc}")
            return {"CANCELLED"}

        try:
            for index, candidate in enumerate(interface.items_tree):
                if candidate == item:
                    interface.active_index = index
                    break
        except Exception:
            pass

        try:
            from ..node_system.tree import _queue_group_tree_sync

            _queue_group_tree_sync(tree)
        except Exception:
            pass
        try:
            _tag_flow_node_editor_redraw(tree.name)
        except Exception:
            pass
        return {"FINISHED"}


class AF_OT_SetGroupInterfaceSocketType(bpy.types.Operator):
    bl_idname = "af.set_group_interface_socket_type"
    bl_label = "Set Group Interface Socket Type"
    bl_description = "Set the active Group Interface socket type using the filtered plugin panel list"
    bl_options = {"REGISTER", "UNDO"}

    socket_type: bpy.props.StringProperty(name="Socket Type", default="")

    def execute(self, context):
        tree, interface = _group_interface_context(context)
        active_item = getattr(interface, "active", None) if interface is not None else None
        if tree is None or interface is None or active_item is None:
            self.report({"ERROR"}, "No active Group Interface socket")
            return {"CANCELLED"}
        if getattr(active_item, "item_type", "") != "SOCKET":
            self.report({"ERROR"}, "Active Group Interface item is not a socket")
            return {"CANCELLED"}

        socket_type = str(self.socket_type or "").strip()
        if socket_type not in GROUP_INTERFACE_SOCKET_LABEL_BY_TYPE:
            self.report({"ERROR"}, "Unsupported Group Interface socket type")
            return {"CANCELLED"}

        try:
            active_item.socket_type = _resolved_group_interface_socket_type(socket_type)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to set Group Interface socket type: {exc}")
            return {"CANCELLED"}

        try:
            from ..node_system.tree import _queue_group_tree_sync

            _queue_group_tree_sync(tree)
        except Exception:
            pass
        try:
            _tag_flow_node_editor_redraw(tree.name)
        except Exception:
            pass
        return {"FINISHED"}


class AF_OT_RemoveActiveGroupInterfaceItem(bpy.types.Operator):
    bl_idname = "af.remove_active_group_interface_item"
    bl_label = "Remove Active Group Interface Item"
    bl_description = "Remove only the active Group Interface item from the plugin panel"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        space = getattr(context, "space_data", None)
        if space is None or getattr(space, "type", "") != "NODE_EDITOR":
            self.report({"ERROR"}, "Open a Node Editor first")
            return {"CANCELLED"}

        tree = getattr(space, "edit_tree", None)
        interface = getattr(tree, "interface", None) if tree is not None else None
        active_item = getattr(interface, "active", None) if interface is not None else None
        if tree is None or interface is None or active_item is None:
            self.report({"ERROR"}, "No active interface item")
            return {"CANCELLED"}

        try:
            for item in interface.items_tree:
                try:
                    item.select = (item == active_item)
                except Exception:
                    continue

            if getattr(active_item, "item_type", "") == "PANEL":
                children = getattr(active_item, "interface_items", [])
                if len(children) > 0:
                    first_child = children[0]
                    if isinstance(first_child, bpy.types.NodeTreeInterfaceSocket) and bool(getattr(first_child, "is_panel_toggle", False)):
                        interface.remove(first_child)

            interface.remove(active_item)
            interface.active_index = min(int(getattr(interface, "active_index", 0)), len(interface.items_tree) - 1)

            new_active = getattr(interface, "active", None)
            if isinstance(new_active, bpy.types.NodeTreeInterfaceSocket) and bool(getattr(new_active, "is_panel_toggle", False)):
                interface.active_index = int(getattr(new_active.parent, "index", interface.active_index))
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to remove active interface item: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


GROUP_INTERFACE_OPERATOR_CLASSES = (
    AF_OT_AddGroupInterfaceSocket,
    AF_OT_SetGroupInterfaceSocketType,
    AF_OT_RemoveActiveGroupInterfaceItem,
)
