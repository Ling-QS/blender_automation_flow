import bpy


def reset_scene_runtime_state(scene):
    settings = getattr(scene, "af_flow_settings", None) if scene is not None else None
    if settings is None:
        return
    settings.runtime_status = "IDLE"
    settings.runtime_tree_name = ""
    settings.current_node_name = ""
    settings.last_finished_node_name = ""
    settings.error_node_name = ""
    settings.error_group_path_json = ""
    settings.current_plan_title = ""
    settings.current_plan_index = 0
    settings.total_plan_count = 0
    settings.current_plan_step_index = 0
    settings.current_plan_step_count = 0
    settings.current_step_index = 0
    settings.total_step_count = 0


def build_ui_classes(*, preferences, flow_settings_cls, flow_log_item_cls, menus, panels):
    return (
        preferences.AFAddonPreferences,
        flow_settings_cls,
        flow_log_item_cls,
        *menus.MENU_CLASSES,
        *panels.PANEL_CLASSES,
    )


def register_ui_classes(classes, safe_register_class):
    for cls in classes:
        safe_register_class(cls)


def unregister_ui_classes(classes, safe_unregister_class):
    for cls in reversed(classes):
        safe_unregister_class(cls)


def attach_scene_runtime_properties(*, flow_settings_cls, flow_log_item_cls):
    if hasattr(bpy.types.Scene, "af_flow_settings"):
        del bpy.types.Scene.af_flow_settings
    if hasattr(bpy.types.Scene, "af_flow_logs"):
        del bpy.types.Scene.af_flow_logs
    bpy.types.Scene.af_flow_settings = bpy.props.PointerProperty(type=flow_settings_cls)
    bpy.types.Scene.af_flow_logs = bpy.props.CollectionProperty(type=flow_log_item_cls)


def detach_scene_runtime_properties():
    if hasattr(bpy.types.Scene, "af_flow_logs"):
        del bpy.types.Scene.af_flow_logs
    if hasattr(bpy.types.Scene, "af_flow_settings"):
        del bpy.types.Scene.af_flow_settings


def reset_all_scene_runtime_state():
    for scene in getattr(bpy.data, "scenes", []):
        reset_scene_runtime_state(scene)


def register_ui_hooks(*, overlays, menus, panels):
    overlays.register_flow_overlay_handler()
    try:
        bpy.types.NODE_MT_add.remove(menus._draw_add_menu)
    except (AttributeError, ValueError):
        pass
    bpy.types.NODE_MT_add.append(menus._draw_add_menu)
    try:
        bpy.types.NODE_MT_context_menu.remove(menus._draw_node_context_menu)
    except (AttributeError, ValueError):
        pass
    bpy.types.NODE_MT_context_menu.append(menus._draw_node_context_menu)
    panels._register_physics_bake_panel_hooks()


def unregister_ui_hooks(*, overlays, menus, panels):
    panels._unregister_physics_bake_panel_hooks()
    overlays.unregister_flow_overlay_handler()
    try:
        bpy.types.NODE_MT_context_menu.remove(menus._draw_node_context_menu)
    except (AttributeError, ValueError):
        pass
    try:
        bpy.types.NODE_MT_add.remove(menus._draw_add_menu)
    except (AttributeError, ValueError):
        pass


__all__ = [
    "attach_scene_runtime_properties",
    "build_ui_classes",
    "detach_scene_runtime_properties",
    "register_ui_classes",
    "register_ui_hooks",
    "reset_all_scene_runtime_state",
    "reset_scene_runtime_state",
    "unregister_ui_classes",
    "unregister_ui_hooks",
]
