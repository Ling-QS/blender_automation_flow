import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..node_system.socket_aliases import (
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)


def _zh_ui():
    try:
        language = str(getattr(getattr(bpy.context, "preferences", None), "view", None).language or "")
    except Exception:
        language = ""
    return language.startswith("zh")


def build_property_package_node_classes(
    *,
    AFBaseNode,
    APPLY_OBJECT_PROPERTIES_MODE_ITEMS,
    MISSING_POLICY_ITEMS,
    PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS,
    PROPERTY_PACKAGE_FILTER_MODE_ITEMS,
    PROPERTY_PACKAGE_STORE_MODE_ITEMS,
    SORT_MODE_ITEMS,
    _has_stored_property_package,
    _hide_default_auxiliary_outputs,
    _normalized_preview_context,
    _set_node_color,
    _sync_apply_object_properties_sockets,
    _sync_create_property_package_sockets,
    _ui_runner_for_node,
):
    class AFNodeParsePropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeParsePropertyPackage"
        bl_label = "Parse Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Parse Prop Pack")

        sort_mode: bpy.props.EnumProperty(name="Sort Mode", items=SORT_MODE_ITEMS, default="NAME_ASC")

        def init(self, context):
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketPropertyDefinition", PROPERTY_DEFINITION_SOCKET_NAME)
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "sort_mode", text="")

    class AFNodeMergePropertyAssignments(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMergePropertyAssignments"
        bl_label = "Merge Property Assignments"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Merge Prop Assigns")

        conflict_policy: bpy.props.EnumProperty(
            name="Conflict Policy",
            items=PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS,
            default="LAST_WINS",
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketPropertyAssignment", "Base Prop Assign")
            self.inputs.new("AFSocketPropertyAssignment", "Add Prop Assign")
            self.outputs.new("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "conflict_policy", text="")

    class AFNodeFilterPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeFilterPropertyPackage"
        bl_label = "Filter Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Filter Prop Pack")

        filter_mode: bpy.props.EnumProperty(
            name="Filter Mode",
            items=PROPERTY_PACKAGE_FILTER_MODE_ITEMS,
            default="KEEP_MATCHED",
        )
        remove_missing_modifiers: bpy.props.BoolProperty(
            name="Remove Missing Modifiers",
            default=False,
        )

        def init(self, context):
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.inputs.new("AFSocketObjectList", "Object List")
            self.inputs.new("AFSocketPropertyDefinition", PROPERTY_DEFINITION_SOCKET_NAME)
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "filter_mode", text="")
            layout.prop(self, "remove_missing_modifiers")

    class AFNodeMergePropertyPackages(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMergePropertyPackages"
        bl_label = "Merge Property Packages"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Merge Prop Packs")

        conflict_policy: bpy.props.EnumProperty(
            name="Conflict Policy",
            items=PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS,
            default="LAST_WINS",
        )

        def init(self, context):
            self.inputs.new("AFSocketPropertyPackage", "Base Prop Pack")
            self.inputs.new("AFSocketPropertyPackage", "Add Prop Pack")
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "conflict_policy", text="")

    class AFNodeCreatePropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCreatePropertyPackage"
        bl_label = "Create Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Create Prop Pack")

        def init(self, context):
            del context
            self.inputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            self._sync_sockets()
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context

        def _sync_sockets(self):
            _sync_create_property_package_sockets(self)

        def update(self):
            self._sync_sockets()

    class AFNodeStorePropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeStorePropertyPackage"
        bl_label = "Store Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Store Prop Pack")

        store_mode: bpy.props.EnumProperty(
            name="Mode",
            items=PROPERTY_PACKAGE_STORE_MODE_ITEMS,
            default="STORE_AND_OUTPUT",
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            owner = None
            has_stored_package = False
            try:
                preview_context = _normalized_preview_context(context)
                runner = _ui_runner_for_node(self, preview_context)
                owner = runner._stored_property_package_owner(self) if runner is not None else None
            except Exception:
                owner = None
            try:
                has_stored_package = bool(_has_stored_property_package(self, owner=owner))
            except Exception:
                has_stored_package = bool(_has_stored_property_package(self))
            row = layout.row(align=True)
            store_op = row.operator("af.run_store_property_package_node", text="", icon="PLAY")
            if store_op is not None:
                store_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                store_op.node_name = self.name
            row.prop(self, "store_mode", expand=True)
            clear_row = row.row(align=True)
            clear_row.enabled = has_stored_package
            clear_op = clear_row.operator("af.clear_stored_property_package", text="", icon="TRASH")
            if clear_op is not None:
                clear_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                clear_op.node_name = self.name

    class AFNodeApplyObjectProperties(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeApplyObjectProperties"
        bl_label = "Apply Object Properties"
        bl_icon = "BLANK1"

        def draw_label(self):
            if _zh_ui():
                return iface_("Apply Object Properties")
            return iface_("Apply Properties")

        apply_mode: bpy.props.EnumProperty(
            name="Mode",
            items=APPLY_OBJECT_PROPERTIES_MODE_ITEMS,
            default="PACKAGE",
            update=lambda self, context: self._sync_sockets(),
        )
        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketObjectList", "Object List")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketReport", "Report")
            self._sync_sockets()
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "apply_mode", expand=True)
            layout.prop(self, "missing_policy", text="")

        def _sync_sockets(self):
            _sync_apply_object_properties_sockets(self)

        def update(self):
            self._sync_sockets()

    class AFNodeApplyPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeApplyPropertyPackage"
        bl_label = "Apply Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Apply Prop Pack")

        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            apply_op = layout.operator("af.run_apply_property_package_node", text=iface_("Apply"), icon="PLAY")
            if apply_op is not None:
                apply_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                apply_op.node_name = self.name
            layout.prop(self, "missing_policy", text="")

    class AFNodeRecordPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRecordPropertyPackage"
        bl_label = "Record Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Record Prop Pack")

        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "missing_policy", text="")

    return {
        "AFNodeParsePropertyPackage": AFNodeParsePropertyPackage,
        "AFNodeMergePropertyAssignments": AFNodeMergePropertyAssignments,
        "AFNodeFilterPropertyPackage": AFNodeFilterPropertyPackage,
        "AFNodeMergePropertyPackages": AFNodeMergePropertyPackages,
        "AFNodeCreatePropertyPackage": AFNodeCreatePropertyPackage,
        "AFNodeStorePropertyPackage": AFNodeStorePropertyPackage,
        "AFNodeApplyObjectProperties": AFNodeApplyObjectProperties,
        "AFNodeApplyPropertyPackage": AFNodeApplyPropertyPackage,
        "AFNodeRecordPropertyPackage": AFNodeRecordPropertyPackage,
    }
