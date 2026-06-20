import bpy

from ..runtime_core.registration import safe_register_class, safe_unregister_class
from . import assembly, menus, overlays, panels, preferences


class AFFlowSettings(bpy.types.PropertyGroup):
    run_mode: bpy.props.EnumProperty(
        name="Run Mode",
        items=(
            ("NORMAL", "Execute", "Execute real operations"),
            ("DRY_RUN", "Dry Run", "Validate and log only"),
            ("FLOW_TEST", "Flow Test", "Run non-task flow operations while simulating tasks"),
        ),
        default="NORMAL",
    )
    auto_restore_on_error: bpy.props.BoolProperty(name="Auto Restore On Error", default=True)
    fail_on_warning: bpy.props.BoolProperty(name="Fail On Warning", default=False)
    default_timeout_sec: bpy.props.FloatProperty(name="Default Timeout (sec)", default=0.0, min=0.0)
    poll_interval_ms: bpy.props.IntProperty(name="Poll Interval (ms)", default=200, min=50, max=10000)
    auto_follow_debounce_ms: bpy.props.IntProperty(name="Auto Follow Debounce (ms)", default=300, min=50, max=10000)
    max_log_entries: bpy.props.IntProperty(name="Max Log Entries", default=2000, min=10, max=100000)
    runtime_status: bpy.props.StringProperty(name="Runtime Status", default="IDLE")
    runtime_tree_name: bpy.props.StringProperty(name="Runtime Tree", default="")
    current_node_name: bpy.props.StringProperty(name="Current Node", default="")
    last_finished_node_name: bpy.props.StringProperty(name="Last Finished Node", default="")
    error_node_name: bpy.props.StringProperty(name="Error Node", default="")
    error_group_path_json: bpy.props.StringProperty(name="Error Group Path", default="")
    current_plan_title: bpy.props.StringProperty(name="Current Plan", default="")
    current_plan_index: bpy.props.IntProperty(name="Current Plan Index", default=0, min=0)
    total_plan_count: bpy.props.IntProperty(name="Total Plan Count", default=0, min=0)
    current_plan_step_index: bpy.props.IntProperty(name="Current Plan Step", default=0, min=0)
    current_plan_step_count: bpy.props.IntProperty(name="Current Plan Step Count", default=0, min=0)
    current_step_index: bpy.props.IntProperty(name="Current Step", default=0, min=0)
    total_step_count: bpy.props.IntProperty(name="Total Steps", default=0, min=0)


class AFFlowLogItem(bpy.types.PropertyGroup):
    timestamp: bpy.props.StringProperty(name="Time")
    level: bpy.props.StringProperty(name="Level")
    node_tree_name: bpy.props.StringProperty(name="Tree")
    node_name: bpy.props.StringProperty(name="Node")
    message: bpy.props.StringProperty(name="Message")

assembly.initialize_default_ui_module(
    globals(),
    flow_settings_cls=AFFlowSettings,
    flow_log_item_cls=AFFlowLogItem,
)


def register():
    assembly.register_ui_classes(CLASSES, safe_register_class)
    assembly.attach_scene_runtime_properties(
        flow_settings_cls=AFFlowSettings,
        flow_log_item_cls=AFFlowLogItem,
    )
    assembly.reset_all_scene_runtime_state()
    assembly.register_ui_hooks(overlays=overlays, menus=menus, panels=panels)


def unregister():
    assembly.unregister_ui_hooks(overlays=overlays, menus=menus, panels=panels)
    assembly.detach_scene_runtime_properties()
    assembly.unregister_ui_classes(CLASSES, safe_unregister_class)


def __getattr__(name):
    return assembly.resolve_ui_module_export(globals(), name)


__all__ = list(assembly.UI_MODULE_EXPORTS)
