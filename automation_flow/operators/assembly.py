import bpy


_GROUP_NAV_KEYMAP_ITEMS = []


def build_operator_classes(
    *,
    run_ops,
    status_ops,
    dynamic_inputs,
    misc_ops,
    node_add_ops,
    group_navigation,
    bake_ops,
    property_ops,
    group_interface,
):
    return (
        *run_ops.RUN_OPERATOR_CLASSES,
        status_ops.AF_OT_SetStatusInputValue,
        *dynamic_inputs.DYNAMIC_INPUT_OPERATOR_CLASSES,
        *misc_ops.MISC_OPERATOR_CLASSES,
        *node_add_ops.NODE_ADD_OPERATOR_CLASSES,
        *group_navigation.GROUP_NAVIGATION_OPERATOR_CLASSES,
        *bake_ops.BAKE_OPERATOR_CLASSES,
        *property_ops.PROPERTY_OPERATOR_CLASSES,
        *group_interface.GROUP_INTERFACE_OPERATOR_CLASSES,
    )


def register_group_navigation_keymaps():
    unregister_group_navigation_keymaps()
    window_manager = getattr(bpy.context, "window_manager", None)
    keyconfigs = getattr(window_manager, "keyconfigs", None) if window_manager is not None else None
    addon_keyconfig = getattr(keyconfigs, "addon", None) if keyconfigs is not None else None
    if addon_keyconfig is None:
        return

    keymap = addon_keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    keymap_item = keymap.keymap_items.new(
        "af.group_double_click_navigate",
        "LEFTMOUSE",
        "DOUBLE_CLICK",
        head=True,
    )
    _GROUP_NAV_KEYMAP_ITEMS.append((keymap, keymap_item))


def unregister_group_navigation_keymaps():
    while _GROUP_NAV_KEYMAP_ITEMS:
        keymap, keymap_item = _GROUP_NAV_KEYMAP_ITEMS.pop()
        try:
            keymap.keymap_items.remove(keymap_item)
        except Exception:
            pass


def register_operator_classes(classes, safe_register_class):
    for cls in classes:
        safe_register_class(cls)


def unregister_operator_classes(classes, safe_unregister_class):
    for cls in reversed(classes):
        safe_unregister_class(cls)


__all__ = [
    "build_operator_classes",
    "register_group_navigation_keymaps",
    "register_operator_classes",
    "unregister_group_navigation_keymaps",
    "unregister_operator_classes",
]
