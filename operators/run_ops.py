import bpy

from .editor_utils import _get_active_flow_tree, _tag_flow_node_editor_redraw
from .group_helpers import _is_group_editing_context
from .flow_run import (
    _arm_auto_follow_cooldown,
    _capture_runtime_ui_context,
    _consume_pending_reload_resume,
    _get_active_runner,
    _has_pending_reload_resume,
    _perform_reload_resume,
    _resume_auto_follow_notifications,
    _runner_tick_step_budget,
    _set_active_runner,
    _start_branch_runner,
    _start_runner,
    _start_subflow_runner,
    _suspend_auto_follow_notifications,
)


def _merge_runner_ui_context(runtime_context, runner):
    merged = dict(runtime_context or {})
    existing = dict(getattr(runner, "ui_context", {}) or {}) if runner is not None else {}
    if "playback_state" in existing and "playback_state" not in merged:
        merged["playback_state"] = dict(existing.get("playback_state") or {})
    if "trigger_state" in existing and "trigger_state" not in merged:
        merged["trigger_state"] = dict(existing.get("trigger_state") or {})
    return merged


def _manual_trigger_ui_context(context):
    payload = _capture_runtime_ui_context(context)
    payload["trigger_state"] = {
        "manual": True,
        "scene_updating": False,
        "on_scene_update_start": False,
        "on_scene_update_end": False,
        "object_interaction_mode": "",
        "viewport_shading_mode": "",
    }
    return payload


class AF_OT_RunFlow(bpy.types.Operator):
    bl_idname = "af.run_flow"
    bl_label = "Run Automation Flow"
    bl_description = "Execute active Automation Flow node tree"
    bl_options = {"REGISTER"}

    _timer = None

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        runner = _get_active_runner()
        if runner is None:
            self._finish(context)
            return {"CANCELLED"}

        runner.ui_context = _merge_runner_ui_context(_capture_runtime_ui_context(context), runner)
        _suspend_auto_follow_notifications()
        try:
            finished = runner.tick(max_immediate_steps=_runner_tick_step_budget(runner))
        finally:
            _resume_auto_follow_notifications()
        _tag_flow_node_editor_redraw(runner.node_tree.name)
        if finished:
            should_reload = str(getattr(runner, "status", "") or "") == "RELOADING" and _has_pending_reload_resume()
            self._finish(context)
            if should_reload:
                if _perform_reload_resume(context):
                    _consume_pending_reload_resume()
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if _get_active_runner() is not None:
            self.report({"WARNING"}, "A flow is already running")
            return {"CANCELLED"}

        if _is_group_editing_context(context):
            self.report({"ERROR"}, "Exit the current group before running the flow")
            return {"CANCELLED"}

        tree = _get_active_flow_tree(context)
        if tree is None:
            self.report({"ERROR"}, "Open an Automation Flow node tree first")
            return {"CANCELLED"}

        try:
            _start_runner(tree, context.scene, ui_context=_manual_trigger_ui_context(context))
        except Exception as exc:
            _tag_flow_node_editor_redraw(tree.name)
            self.report({"ERROR"}, f"Failed to start flow: {exc}")
            return {"CANCELLED"}

        wm = context.window_manager
        self._timer = wm.event_timer_add(max(0.05, context.scene.af_flow_settings.poll_interval_ms / 1000.0), window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        runner = _get_active_runner()
        tree_name = runner.node_tree.name if runner is not None else ""
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        _arm_auto_follow_cooldown()
        _set_active_runner(None)
        _tag_flow_node_editor_redraw(tree_name or None)


class AF_OT_ResumeFlowModal(bpy.types.Operator):
    bl_idname = "af.resume_flow_modal"
    bl_label = "Resume Automation Flow"
    bl_description = "Resume an already restored Automation Flow runner in the UI"
    bl_options = {"INTERNAL"}

    _timer = None

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        runner = _get_active_runner()
        if runner is None:
            self._finish(context)
            return {"CANCELLED"}

        runner.ui_context = _merge_runner_ui_context(_capture_runtime_ui_context(context), runner)
        _suspend_auto_follow_notifications()
        try:
            finished = runner.tick(max_immediate_steps=_runner_tick_step_budget(runner))
        finally:
            _resume_auto_follow_notifications()
        _tag_flow_node_editor_redraw(runner.node_tree.name)
        if finished:
            should_reload = str(getattr(runner, "status", "") or "") == "RELOADING" and _has_pending_reload_resume()
            self._finish(context)
            if should_reload:
                if _perform_reload_resume(context):
                    _consume_pending_reload_resume()
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        runner = _get_active_runner()
        if runner is None:
            return {"CANCELLED"}
        window = getattr(context, "window", None)
        window_manager = getattr(context, "window_manager", None)
        if window is None or window_manager is None:
            return {"CANCELLED"}
        scene = getattr(runner, "scene", None) or getattr(context, "scene", None)
        poll_ms = int(getattr(getattr(scene, "af_flow_settings", None), "poll_interval_ms", 200) or 200)
        self._timer = window_manager.event_timer_add(max(0.05, poll_ms / 1000.0), window=window)
        window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        runner = _get_active_runner()
        tree_name = runner.node_tree.name if runner is not None else ""
        window_manager = getattr(context, "window_manager", None)
        if self._timer is not None and window_manager is not None:
            window_manager.event_timer_remove(self._timer)
            self._timer = None
        _arm_auto_follow_cooldown()
        _set_active_runner(None)
        _tag_flow_node_editor_redraw(tree_name or None)


class AF_OT_RunStartNode(bpy.types.Operator):
    bl_idname = "af.run_start_node"
    bl_label = "Run Start Node"
    bl_description = "Run this Start flow once without changing the default enabled Start"
    bl_options = {"REGISTER"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    start_node_name: bpy.props.StringProperty(name="Start Node Name", default="")
    run_mode_override: bpy.props.EnumProperty(
        name="Run Mode Override",
        items=(
            ("NORMAL", "Execute", "Execute real operations"),
            ("DRY_RUN", "Dry Run", "Validate and log only"),
            ("FLOW_TEST", "Flow Test", "Run non-task flow operations while simulating tasks"),
        ),
        default="NORMAL",
    )

    _timer = None
    _previous_run_mode = None

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        runner = _get_active_runner()
        if runner is None:
            self._finish(context)
            return {"CANCELLED"}

        runner.ui_context = _merge_runner_ui_context(_capture_runtime_ui_context(context), runner)
        _suspend_auto_follow_notifications()
        try:
            finished = runner.tick(max_immediate_steps=_runner_tick_step_budget(runner))
        finally:
            _resume_auto_follow_notifications()
        _tag_flow_node_editor_redraw(runner.node_tree.name)
        if finished:
            should_reload = str(getattr(runner, "status", "") or "") == "RELOADING" and _has_pending_reload_resume()
            self._finish(context)
            if should_reload:
                if _perform_reload_resume(context):
                    _consume_pending_reload_resume()
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if _get_active_runner() is not None:
            self.report({"WARNING"}, "A flow is already running")
            return {"CANCELLED"}

        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        start_node = node_tree.nodes.get(self.start_node_name)
        if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeStart":
            self.report({"ERROR"}, "Start node not found")
            return {"CANCELLED"}

        self._previous_run_mode = None
        override_mode = str(getattr(self, "run_mode_override", "NORMAL") or "NORMAL")
        if override_mode in {"NORMAL", "DRY_RUN", "FLOW_TEST"}:
            settings = getattr(context.scene, "af_flow_settings", None)
            if settings is not None:
                self._previous_run_mode = str(getattr(settings, "run_mode", "NORMAL") or "NORMAL")
                settings.run_mode = override_mode

        try:
            _start_runner(
                node_tree,
                context.scene,
                ui_context=_manual_trigger_ui_context(context),
                start_node_name=self.start_node_name,
            )
        except Exception as exc:
            if self._previous_run_mode is not None:
                try:
                    context.scene.af_flow_settings.run_mode = self._previous_run_mode
                except Exception:
                    pass
                self._previous_run_mode = None
            _tag_flow_node_editor_redraw(node_tree.name)
            self.report({"ERROR"}, f"Failed to start flow: {exc}")
            return {"CANCELLED"}

        wm = context.window_manager
        self._timer = wm.event_timer_add(max(0.05, context.scene.af_flow_settings.poll_interval_ms / 1000.0), window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        runner = _get_active_runner()
        tree_name = runner.node_tree.name if runner is not None else ""
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        _arm_auto_follow_cooldown()
        _set_active_runner(None)
        if self._previous_run_mode is not None:
            try:
                context.scene.af_flow_settings.run_mode = self._previous_run_mode
            except Exception:
                pass
            self._previous_run_mode = None
        _tag_flow_node_editor_redraw(tree_name or None)


class AF_OT_RunSubflowStart(bpy.types.Operator):
    bl_idname = "af.run_subflow_start"
    bl_label = "Run Subflow Start"
    bl_description = "Run this Subflow once without executing the outer main flow"
    bl_options = {"REGISTER"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    subflow_start_name: bpy.props.StringProperty(name="Subflow Start Name", default="")
    run_mode_override: bpy.props.EnumProperty(
        name="Run Mode Override",
        items=(
            ("NORMAL", "Execute", "Execute real operations"),
            ("DRY_RUN", "Dry Run", "Validate and log only"),
            ("FLOW_TEST", "Flow Test", "Run non-task flow operations while simulating tasks"),
        ),
        default="NORMAL",
    )

    _timer = None
    _previous_run_mode = None

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        runner = _get_active_runner()
        if runner is None:
            self._finish(context)
            return {"CANCELLED"}

        runner.ui_context = _merge_runner_ui_context(_capture_runtime_ui_context(context), runner)
        _suspend_auto_follow_notifications()
        try:
            finished = runner.tick(max_immediate_steps=_runner_tick_step_budget(runner))
        finally:
            _resume_auto_follow_notifications()
        _tag_flow_node_editor_redraw(runner.node_tree.name)
        if finished:
            should_reload = str(getattr(runner, "status", "") or "") == "RELOADING" and _has_pending_reload_resume()
            self._finish(context)
            if should_reload:
                if _perform_reload_resume(context):
                    _consume_pending_reload_resume()
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if _get_active_runner() is not None:
            self.report({"WARNING"}, "A flow is already running")
            return {"CANCELLED"}

        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        subflow_start = node_tree.nodes.get(self.subflow_start_name)
        if subflow_start is None or getattr(subflow_start, "bl_idname", "") != "AFNodeSubflowStart":
            self.report({"ERROR"}, "Subflow Start node not found")
            return {"CANCELLED"}

        self._previous_run_mode = None
        override_mode = str(getattr(self, "run_mode_override", "NORMAL") or "NORMAL")
        if override_mode in {"NORMAL", "DRY_RUN", "FLOW_TEST"}:
            settings = getattr(context.scene, "af_flow_settings", None)
            if settings is not None:
                self._previous_run_mode = str(getattr(settings, "run_mode", "NORMAL") or "NORMAL")
                settings.run_mode = override_mode

        try:
            _start_subflow_runner(
                node_tree,
                context.scene,
                subflow_start_name=self.subflow_start_name,
                ui_context=_manual_trigger_ui_context(context),
            )
        except Exception as exc:
            if self._previous_run_mode is not None:
                try:
                    context.scene.af_flow_settings.run_mode = self._previous_run_mode
                except Exception:
                    pass
                self._previous_run_mode = None
            _tag_flow_node_editor_redraw(node_tree.name)
            self.report({"ERROR"}, f"Failed to start subflow: {exc}")
            return {"CANCELLED"}

        wm = context.window_manager
        self._timer = wm.event_timer_add(max(0.05, context.scene.af_flow_settings.poll_interval_ms / 1000.0), window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        runner = _get_active_runner()
        tree_name = runner.node_tree.name if runner is not None else ""
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        _arm_auto_follow_cooldown()
        _set_active_runner(None)
        if self._previous_run_mode is not None:
            try:
                context.scene.af_flow_settings.run_mode = self._previous_run_mode
            except Exception:
                pass
            self._previous_run_mode = None
        _tag_flow_node_editor_redraw(tree_name or None)


class AF_OT_RunBranchStart(bpy.types.Operator):
    bl_idname = "af.run_branch_start"
    bl_label = "Run Branch Start"
    bl_description = "Run this Branch once without executing the outer main flow"
    bl_options = {"REGISTER"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    branch_start_name: bpy.props.StringProperty(name="Branch Start Name", default="")
    run_mode_override: bpy.props.EnumProperty(
        name="Run Mode Override",
        items=(
            ("NORMAL", "Execute", "Execute real operations"),
            ("DRY_RUN", "Dry Run", "Validate and log only"),
            ("FLOW_TEST", "Flow Test", "Run non-task flow operations while simulating tasks"),
        ),
        default="NORMAL",
    )

    _timer = None
    _previous_run_mode = None

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        runner = _get_active_runner()
        if runner is None:
            self._finish(context)
            return {"CANCELLED"}

        runner.ui_context = _merge_runner_ui_context(_capture_runtime_ui_context(context), runner)
        _suspend_auto_follow_notifications()
        try:
            finished = runner.tick(max_immediate_steps=_runner_tick_step_budget(runner))
        finally:
            _resume_auto_follow_notifications()
        _tag_flow_node_editor_redraw(runner.node_tree.name)
        if finished:
            should_reload = str(getattr(runner, "status", "") or "") == "RELOADING" and _has_pending_reload_resume()
            self._finish(context)
            if should_reload:
                if _perform_reload_resume(context):
                    _consume_pending_reload_resume()
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if _get_active_runner() is not None:
            self.report({"WARNING"}, "A flow is already running")
            return {"CANCELLED"}

        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        branch_start = node_tree.nodes.get(self.branch_start_name)
        if branch_start is None or getattr(branch_start, "bl_idname", "") != "AFNodeBranchStart":
            self.report({"ERROR"}, "Branch Start node not found")
            return {"CANCELLED"}

        self._previous_run_mode = None
        override_mode = str(getattr(self, "run_mode_override", "NORMAL") or "NORMAL")
        if override_mode in {"NORMAL", "DRY_RUN", "FLOW_TEST"}:
            settings = getattr(context.scene, "af_flow_settings", None)
            if settings is not None:
                self._previous_run_mode = str(getattr(settings, "run_mode", "NORMAL") or "NORMAL")
                settings.run_mode = override_mode

        try:
            _start_branch_runner(
                node_tree,
                context.scene,
                branch_start_name=self.branch_start_name,
                ui_context=_manual_trigger_ui_context(context),
            )
        except Exception as exc:
            if self._previous_run_mode is not None:
                try:
                    context.scene.af_flow_settings.run_mode = self._previous_run_mode
                except Exception:
                    pass
                self._previous_run_mode = None
            _tag_flow_node_editor_redraw(node_tree.name)
            self.report({"ERROR"}, f"Failed to start branch: {exc}")
            return {"CANCELLED"}

        wm = context.window_manager
        self._timer = wm.event_timer_add(max(0.05, context.scene.af_flow_settings.poll_interval_ms / 1000.0), window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        runner = _get_active_runner()
        tree_name = runner.node_tree.name if runner is not None else ""
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        _arm_auto_follow_cooldown()
        _set_active_runner(None)
        if self._previous_run_mode is not None:
            try:
                context.scene.af_flow_settings.run_mode = self._previous_run_mode
            except Exception:
                pass
            self._previous_run_mode = None
        _tag_flow_node_editor_redraw(tree_name or None)

RUN_OPERATOR_CLASSES = (
    AF_OT_RunFlow,
    AF_OT_ResumeFlowModal,
    AF_OT_RunStartNode,
    AF_OT_RunSubflowStart,
    AF_OT_RunBranchStart,
)
