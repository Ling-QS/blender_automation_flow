import bpy
import sys
import types

from ..runtime_core.module_exports import resolve_module_export


_GROUP_NAV_KEYMAP_ITEMS = []
_QUICK_RUN_KEYMAP_ITEMS = []

_OPERATOR_MODULE_EXPORT_NAMES = (
    "bake_helpers",
    "bake_ops",
    "dynamic_inputs",
    "flow_reload",
    "flow_run",
    "group_interface",
    "group_navigation",
    "misc_ops",
    "node_add_ops",
    "property_ops",
    "run_ops",
    "status_ops",
)
OPERATOR_MODULE_EXPORTS = (
    "bake_helpers",
    "bake_ops",
    "assembly",
    "dynamic_inputs",
    "flow_reload",
    "flow_run",
    "group_interface",
    "group_navigation",
    "misc_ops",
    "node_add_ops",
    "property_ops",
    "run_ops",
    "status_ops",
    "CLASSES",
    "register",
    "unregister",
)

_FLOW_RUN_PROXY_NAMES = {
    "_AUTO_FOLLOW_LAST_PLAY_STATE",
    "_is_animation_playing",
}


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

    quick_run_keymap = addon_keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    quick_run_item = quick_run_keymap.keymap_items.new(
        "af.quick_run_node_overlay_click",
        "LEFTMOUSE",
        "PRESS",
        head=True,
    )
    _QUICK_RUN_KEYMAP_ITEMS.append((quick_run_keymap, quick_run_item))


def unregister_group_navigation_keymaps():
    while _QUICK_RUN_KEYMAP_ITEMS:
        keymap, keymap_item = _QUICK_RUN_KEYMAP_ITEMS.pop()
        try:
            keymap.keymap_items.remove(keymap_item)
        except Exception:
            pass
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


def build_default_operator_classes(*, module_globals):
    return build_operator_classes(
        run_ops=module_globals["run_ops"],
        status_ops=module_globals["status_ops"],
        dynamic_inputs=module_globals["dynamic_inputs"],
        misc_ops=module_globals["misc_ops"],
        node_add_ops=module_globals["node_add_ops"],
        group_navigation=module_globals["group_navigation"],
        bake_ops=module_globals["bake_ops"],
        property_ops=module_globals["property_ops"],
        group_interface=module_globals["group_interface"],
    )


def initialize_default_operators_module(module_globals):
    module_globals["CLASSES"] = build_default_operator_classes(module_globals=module_globals)
    return {"CLASSES": module_globals["CLASSES"]}


def install_operator_module_proxy(module_globals):
    operator_export_modules = tuple(module_globals[name] for name in _OPERATOR_MODULE_EXPORT_NAMES)
    flow_run_module = module_globals["flow_run"]
    module_name = module_globals["__name__"]

    class _OperatorsModule(types.ModuleType):
        def __getattribute__(self, name):
            if name in _FLOW_RUN_PROXY_NAMES:
                return getattr(flow_run_module, name)
            return types.ModuleType.__getattribute__(self, name)

        def __getattr__(self, name):
            return resolve_module_export(operator_export_modules, name, module_name)

        def __setattr__(self, name, value):
            if name in _FLOW_RUN_PROXY_NAMES:
                setattr(flow_run_module, name, value)
            types.ModuleType.__setattr__(self, name, value)

    sys.modules[module_name].__class__ = _OperatorsModule


__all__ = [
    "OPERATOR_MODULE_EXPORTS",
    "build_operator_classes",
    "build_default_operator_classes",
    "initialize_default_operators_module",
    "install_operator_module_proxy",
    "register_group_navigation_keymaps",
    "register_operator_classes",
    "unregister_group_navigation_keymaps",
    "unregister_operator_classes",
]
