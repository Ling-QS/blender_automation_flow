import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..i18n import af_iface, af_status_label
from ..runtime_runner.core.active import get_active_runner
from .overlay_context import _node_editor_root_tree


_RUNTIME_STATUS_LABELS = {
    "IDLE": "Idle",
    "PRECHECK": "Precheck",
    "RUNNING": "Running",
    "WAITING": "Waiting",
    "RELOADING": "Reloading",
    "SUCCESS": "Success",
    "FAILED": "Failed",
    "CANCELLED": "Cancelled",
    "READY": "Ready",
    "DONE": "Done",
    "SKIPPED": "Skipped",
    "INVALID": "Invalid",
}


def _active_runner():
    return get_active_runner()


def _draw_physics_bake_path_button(self, context):
    obj = getattr(context, "object", None)
    if obj is None:
        return
    modifier = None
    for attr_name in ("cloth", "soft_body", "dynamic_paint"):
        modifier = getattr(context, attr_name, None)
        if modifier is not None:
            break
    if modifier is None:
        modifier = getattr(getattr(obj, "modifiers", None), "active", None)
    if modifier is None:
        return
    modifier_type = str(getattr(modifier, "type", "") or "")
    if modifier_type not in {"CLOTH", "SOFT_BODY", "DYNAMIC_PAINT"}:
        return
    if modifier_type == "DYNAMIC_PAINT" and getattr(modifier, "canvas_settings", None) is None:
        return
    layout = self.layout
    layout.separator()
    row = layout.row(align=True)
    op = row.operator("af.copy_physics_bake_task_path", text=iface_("Copy Physics Bake Path"), icon="COPYDOWN")
    op.object_name = obj.name
    op.modifier_name = modifier.name


def _is_group_editing(space):
    return space is not None and len(getattr(space, "path", [])) > 1


def _runtime_status_label(status):
    return af_status_label(status, fallback=status or "-")


class AF_MT_StatusValueMenu(bpy.types.Menu):
    bl_label = "Status"
    bl_idname = "AF_MT_status_value_menu"

    def draw(self, context):
        layout = self.layout
        node = getattr(context, "af_status_node", None)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeStatusInput":
            node = getattr(context, "active_node", None)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeStatusInput":
            return
        node_tree_name = str(getattr(getattr(node, "id_data", None), "name", "") or "")
        node_name = str(getattr(node, "name", "") or "")
        try:
            from ..nodes import STATUS_VALUE_ITEMS, _status_value_display_label
        except Exception:
            STATUS_VALUE_ITEMS = ()

            def _status_value_display_label(identifier):
                return str(identifier or "")

        for item in STATUS_VALUE_ITEMS:
            identifier = item[0] if len(item) > 0 else ""
            op = layout.operator("af.set_status_input_value", text=_status_value_display_label(identifier))
            op.node_tree_name = node_tree_name
            op.node_name = node_name
            op.status_value = str(identifier or "")


class AF_PT_MainPanel(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "AF"
    bl_label = "Flow Runner"
    bl_order = 10

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.type == "NODE_EDITOR" and getattr(space, "tree_type", "") == "AFNodeTreeType"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.af_flow_settings
        space = context.space_data
        tree = getattr(space, "edit_tree", None) if space is not None else None
        active_node = getattr(context, "active_node", None)
        is_group_editing = _is_group_editing(space)
        root_tree = _node_editor_root_tree(context, tree)
        active_runner = _active_runner()
        if active_runner is not None and getattr(active_runner, "node_tree", None) != root_tree:
            active_runner = None

        row = layout.row(align=True)
        run_row = row.row(align=True)
        run_row.enabled = not is_group_editing
        run_row.operator("af.run_flow", text=iface_("Run Automation Flow"), icon="PLAY")
        row.operator("af.stop_flow", text=iface_("Stop Automation Flow"), icon="CANCEL")
        if is_group_editing:
            layout.label(text=iface_("Exit the current group before running the flow"), icon="ERROR")

        status_row = layout.row(align=True)
        status_row.label(text=f"{af_iface('Status')}:", translate=False)
        status_row.label(text=_runtime_status_label(settings.runtime_status), translate=False)
        if settings.total_plan_count > 0:
            plan_label = f"{iface_('Plan')} {settings.current_plan_index} / {settings.total_plan_count}"
            if settings.current_plan_title:
                plan_label += f" - {settings.current_plan_title}"
            layout.label(text=plan_label)
        if settings.current_plan_step_count > 0:
            layout.label(text=f"{iface_('Step')} {settings.current_plan_step_index} / {settings.current_plan_step_count}")
        if settings.total_step_count > 0:
            layout.label(text=f"{iface_('Total Steps')} {settings.current_step_index} / {settings.total_step_count}")
        if settings.current_node_name:
            row = layout.row(align=True)
            row.label(text=f"{af_iface('Current')}: {settings.current_node_name}", translate=False)
            op = row.operator("af.focus_node", text="", icon="VIEWZOOM", emboss=False)
            op.node_tree_name = settings.runtime_tree_name
            op.node_name = settings.current_node_name
        elif settings.runtime_status in {"RUNNING", "WAITING", "PRECHECK"}:
            layout.label(text=iface_("Current: Preparing"))
        if settings.last_finished_node_name:
            row = layout.row(align=True)
            row.label(text=f"{iface_('Last Finished')}: {settings.last_finished_node_name}")
            op = row.operator("af.focus_node", text="", icon="VIEWZOOM", emboss=False)
            op.node_tree_name = settings.runtime_tree_name
            op.node_name = settings.last_finished_node_name
        if settings.error_node_name:
            row = layout.row(align=True)
            row.alert = True
            row.label(text=f"{iface_('Error')}: {settings.error_node_name}")
            op = row.operator("af.focus_node", text="", icon="VIEWZOOM", emboss=False)
            op.node_tree_name = settings.runtime_tree_name
            op.node_name = settings.error_node_name
        if active_runner is not None and getattr(active_runner, "background_task_plans", None):
            bg_box = layout.box()
            bg_box.label(text=iface_("Background Tasks"))
            for task_id, state in sorted(active_runner.background_task_plans.items()):
                handle = state.get("handle", {})
                row = bg_box.row(align=True)
                row.label(text=f"{task_id}: {iface_(_runtime_status_label(str(handle.get('status', ''))))}")
                step_count = int(handle.get("step_count", 0) or 0)
                if step_count > 0:
                    bg_box.label(text=active_runner._background_task_plan_step_label(state))
                current_step_name = str(state.get("current_step_name", "") or "")
                if current_step_name:
                    bg_box.label(text=f"{iface_('Current')}: {current_step_name}")
                current_wait_type = str(state.get("current_wait_type", "") or "")
                if current_wait_type:
                    bg_box.label(text=f"{iface_('Status')}: {iface_('Waiting')} ({current_wait_type})")
        layout.prop(settings, "run_mode")
        layout.prop(settings, "auto_restore_on_error")
        layout.prop(settings, "fail_on_warning")
        layout.prop(settings, "default_timeout_sec")
        layout.prop(settings, "poll_interval_ms")
        layout.prop(settings, "auto_follow_debounce_ms")
        layout.prop(settings, "max_log_entries")

        layout.separator()
        group_box = layout.box()
        group_box.label(text=iface_("Groups"))
        if tree is not None:
            group_box.label(text=f"{iface_('Editing')}: {tree.name}")
        row = group_box.row(align=True)
        row.operator("af.create_group_from_selection", text=iface_("Create Group From Selection"), icon="NODETREE")
        if is_group_editing:
            group_box.label(text=iface_("Double-click blank space to exit"), icon="MOUSE_LMB")
        elif active_node is not None and getattr(active_node, "bl_idname", "") == "AFNodeGroup" and getattr(active_node, "group_tree", None) is not None:
            group_box.label(text=iface_("Double-click the group node to enter"), icon="MOUSE_LMB")

        layout.separator()
        layout.operator("af.create_flow_tree", text=iface_("Create Automation Flow Tree"), icon="NODETREE")
        layout.operator("af.clear_logs", text=iface_("Clear Flow Logs"), icon="TRASH")


class AF_PT_LogPanel(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "AF"
    bl_label = "Logs"
    bl_parent_id = "AF_PT_MainPanel"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.type == "NODE_EDITOR" and getattr(space, "tree_type", "") == "AFNodeTreeType"

    def draw(self, context):
        layout = self.layout
        logs = context.scene.af_flow_logs

        if not logs:
            layout.label(text=iface_("No logs yet"))
            return

        col = layout.column(align=True)
        max_view = 30
        start = max(0, len(logs) - max_view)
        for i in range(len(logs) - 1, start - 1, -1):
            item = logs[i]
            line = f"[{item.timestamp}] {item.level}"
            if item.node_name:
                line += f" {item.node_name}"
            row = col.row(align=True)
            row.label(text=line, icon="INFO" if item.level != "ERROR" else "ERROR")
            if item.node_tree_name and item.node_name:
                op = row.operator("af.focus_node", text="", icon="VIEWZOOM", emboss=False)
                op.node_tree_name = item.node_tree_name
                op.node_name = item.node_name
            col.label(text=item.message)


_PHYSICS_BAKE_PATH_PANEL_IDS = (
    "PHYSICS_PT_cloth_cache",
    "PHYSICS_PT_softbody_cache",
    "PHYSICS_PT_dp_cache",
)


def _register_physics_bake_panel_hooks():
    for panel_id in _PHYSICS_BAKE_PATH_PANEL_IDS:
        panel = getattr(bpy.types, panel_id, None)
        if panel is None:
            continue
        try:
            panel.remove(_draw_physics_bake_path_button)
        except (AttributeError, ValueError):
            pass
        panel.append(_draw_physics_bake_path_button)


def _unregister_physics_bake_panel_hooks():
    for panel_id in _PHYSICS_BAKE_PATH_PANEL_IDS:
        panel = getattr(bpy.types, panel_id, None)
        if panel is None:
            continue
        try:
            panel.remove(_draw_physics_bake_path_button)
        except (AttributeError, ValueError):
            pass


SIDEBAR_CLASSES = (
    AF_MT_StatusValueMenu,
    AF_PT_MainPanel,
    AF_PT_LogPanel,
)
