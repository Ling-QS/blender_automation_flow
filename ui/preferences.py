import bpy
from bpy.app.translations import pgettext_iface as iface_


_ADDON_IDNAME = __package__.rsplit(".", 1)[0]


def _addon_preferences(context=None):
    preferences = getattr(context, "preferences", None) if context is not None else getattr(bpy.context, "preferences", None)
    addons = getattr(preferences, "addons", None) if preferences is not None else None
    addon = addons.get(_ADDON_IDNAME) if addons is not None else None
    return getattr(addon, "preferences", None) if addon is not None else None


def _ui_pref_enabled(name, default=True, context=None):
    prefs = _addon_preferences(context=context)
    if prefs is None:
        return bool(default)
    return bool(getattr(prefs, name, default))


class AFAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = _ADDON_IDNAME

    show_flow_zone_overlays: bpy.props.BoolProperty(
        name="Flow Zone Overlays",
        description="Draw hull overlays for repeat, task, subflow, and branch structures",
        default=True,
    )
    show_runtime_node_highlights: bpy.props.BoolProperty(
        name="Runtime Node Highlights",
        description="Highlight currently running and background task nodes",
        default=True,
    )
    show_custom_flow_sockets: bpy.props.BoolProperty(
        name="Custom Flow Sockets",
        description="Draw custom markers for Automation Flow socket endpoints",
        default=True,
    )
    show_custom_flow_links: bpy.props.BoolProperty(
        name="Custom Flow Links",
        description="Draw the active Automation Flow link underlay",
        default=True,
    )
    show_custom_node_headers: bpy.props.BoolProperty(
        name="Custom Node Headers",
        description="Draw custom title bars for supported nodes",
        default=True,
    )
    show_flow_toggle_trigger_links: bpy.props.BoolProperty(
        name="Flow Toggle Trigger Links",
        description="Draw dashed trigger links for FlowToggle nodes",
        default=True,
    )
    show_property_status_chips: bpy.props.BoolProperty(
        name="Property Status Chips",
        description="Draw bake, property package, and group output status chips",
        default=True,
    )
    show_bake_status_chips: bpy.props.BoolProperty(
        name="Bake Status Chips",
        description="Draw cache state chips for GN Bake, Physics Bake, and Property Package Bake nodes",
        default=True,
    )
    show_stored_package_chips: bpy.props.BoolProperty(
        name="Stored Package Chips",
        description="Draw stored package chips for Store Property Package nodes",
        default=True,
    )
    show_group_output_package_chips: bpy.props.BoolProperty(
        name="Group Output Package Chips",
        description="Draw property package chips on group output sockets",
        default=True,
    )
    show_run_mode_chip: bpy.props.BoolProperty(
        name="Run Mode Chip",
        description="Draw the run mode and runtime status chip in the node editor",
        default=True,
    )

    def draw(self, _context):
        layout = self.layout
        box = layout.box()
        box.label(text=iface_("Custom UI"))
        col = box.column(align=True)
        col.prop(self, "show_flow_zone_overlays")
        col.prop(self, "show_runtime_node_highlights")
        col.prop(self, "show_custom_flow_sockets")
        col.prop(self, "show_custom_flow_links")
        col.prop(self, "show_custom_node_headers")
        col.prop(self, "show_flow_toggle_trigger_links")
        col.prop(self, "show_property_status_chips")
        chip_col = col.column(align=True)
        chip_col.enabled = bool(self.show_property_status_chips)
        chip_col.prop(self, "show_bake_status_chips")
        chip_col.prop(self, "show_stored_package_chips")
        chip_col.prop(self, "show_group_output_package_chips")
        col.prop(self, "show_run_mode_chip")


__all__ = [
    "AFAddonPreferences",
    "_addon_preferences",
    "_ui_pref_enabled",
]
