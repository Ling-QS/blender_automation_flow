import copy
import os
import time

import bpy

from ...runtime_core.constants import (
    FlowExecutionError,
    RELOAD_RESUME_CHECKPOINT_VERSION,
    STATUS_SUCCESS,
)
from ...runtime_persistence.reload_checkpoint import _write_reload_resume_checkpoint
from ...runtime_persistence.serialization import _serialize_runtime_state_value
from ...runtime_state.cache import _operator_result_tokens


class RuntimeReloadStateMixin:
    def _background_task_plan_checkpoint_entries(self):
        entries = []
        for task_id, state in sorted(self.background_task_plans.items()):
            if not isinstance(state, dict):
                continue
            handle = dict(state.get("handle") or {})
            wait_state = dict(state.get("wait_state") or {})
            wait_state.pop("task_handle", None)
            entries.append(
                {
                    "task_id": str(task_id),
                    "handle": copy.deepcopy(handle),
                    "wait_state": copy.deepcopy(wait_state),
                    "node_name": str(state.get("node_name", "") or ""),
                    "status": str(state.get("status", "") or ""),
                    "plan_uid": str(state.get("plan_uid", "") or ""),
                    "step_count": int(state.get("step_count", 0) or 0),
                    "completed_step_count": int(state.get("completed_step_count", 0) or 0),
                    "current_step_name": str(state.get("current_step_name", "") or ""),
                    "current_step_tree_name": str(state.get("current_step_tree_name", "") or ""),
                    "current_step_group_path": copy.deepcopy(list(state.get("current_step_group_path", []) or [])),
                    "current_wait_type": str(state.get("current_wait_type", "") or ""),
                    "event_cursor": int(state.get("event_cursor", 0) or 0),
                    "blend_copy_path": str(state.get("blend_copy_path", "") or ""),
                }
            )
        return entries

    def _build_reload_resume_checkpoint(self, node, next_cursor):
        blend_filepath = str(getattr(bpy.data, "filepath", "") or "").strip()
        if not blend_filepath:
            raise FlowExecutionError("AF_E005", "Current .blend must be saved before reload", node.name)
        if not os.path.exists(blend_filepath):
            raise FlowExecutionError("AF_E005", "Current .blend path is unavailable for reload", node.name)
        return {
            "checkpoint_version": int(RELOAD_RESUME_CHECKPOINT_VERSION),
            "kind": "AF_RELOAD_RESUME",
            "tree_name": str(self.node_tree.name),
            "scene_name": str(getattr(self.scene, "name", "") or ""),
            "start_node_name": str(self.start_node_name or ""),
            "run_id": str(self.run_id),
            "cursor": int(next_cursor),
            "completed_step_count": int(self.completed_step_count),
            "flow_repeat_states": copy.deepcopy(self.flow_repeat_states),
            "vars": dict(self.vars),
            "tasks": dict(self.tasks),
            "last_snapshot_package": copy.deepcopy(self.last_snapshot_package),
            "background_task_plans": self._background_task_plan_checkpoint_entries(),
            "reload_node_name": str(getattr(node, "name", "") or ""),
        }

    def _save_mainfile_before_reload(self, node):
        filepath = str(getattr(bpy.data, "filepath", "") or "").strip()
        if not filepath:
            raise FlowExecutionError("AF_E005", "Current .blend must be saved before reload", node.name)
        save_kwargs = {"filepath": filepath, "check_existing": False}
        self.log("INFO", "RELOAD_NODE_SAVE_STARTED", node.name)
        try:
            context_override = {key: value for key, value in self.ui_context.items() if value is not None}
            if context_override:
                with bpy.context.temp_override(**context_override):
                    result = bpy.ops.wm.save_mainfile(**save_kwargs)
            else:
                result = bpy.ops.wm.save_mainfile(**save_kwargs)
        except Exception as exc:
            raise FlowExecutionError("AF_E005", f"Failed to save current .blend before reload: {exc}", node.name)
        if "FINISHED" not in _operator_result_tokens(result):
            raise FlowExecutionError("AF_E005", "Failed to save current .blend before reload", node.name)
        self.log("INFO", "RELOAD_NODE_SAVE_DONE", node.name)
        return filepath

    def _prepare_reload_after_task(self, node, task_handle, next_cursor):
        blend_filepath = self._save_mainfile_before_reload(node)
        checkpoint_payload = self._build_reload_resume_checkpoint(node, next_cursor)
        checkpoint_path = _write_reload_resume_checkpoint(
            blend_filepath,
            checkpoint_payload,
            _serialize_runtime_state_value,
        )
        if not checkpoint_path:
            raise FlowExecutionError("AF_E005", "Failed to write reload resume checkpoint", node.name)
        return {
            "filepath": blend_filepath,
            "task_id": str(task_handle.get("task_id", "") or ""),
            "node_name": str(node.name),
            "tree_name": str(getattr(getattr(node, "id_data", None), "name", self.node_tree.name) or self.node_tree.name),
        }

    def _restore_background_task_plan_checkpoint(self, entry):
        if not isinstance(entry, dict):
            return
        handle = dict(entry.get("handle") or {})
        task_id = str(handle.get("task_id", entry.get("task_id", "")) or "")
        if not task_id:
            return
        self.tasks[task_id] = handle
        wait_state = dict(entry.get("wait_state") or {})
        if wait_state:
            wait_state["task_handle"] = handle
            wait_state["wait_type"] = "external_process"
            wait_state["next_poll_at"] = time.monotonic()
        state = {
            "handle": handle,
            "wait_state": wait_state if wait_state else None,
            "node_name": str(entry.get("node_name", handle.get("node_name", "")) or ""),
            "status": str(entry.get("status", handle.get("status", "RUNNING")) or "RUNNING"),
            "plan_uid": str(entry.get("plan_uid", handle.get("plan_uid", "")) or ""),
            "step_count": int(entry.get("step_count", handle.get("step_count", 0)) or 0),
            "completed_step_count": int(entry.get("completed_step_count", 0) or 0),
            "current_step_name": str(entry.get("current_step_name", "") or ""),
            "current_step_tree_name": str(entry.get("current_step_tree_name", "") or ""),
            "current_step_group_path": copy.deepcopy(list(entry.get("current_step_group_path", []) or [])),
            "current_wait_type": str(entry.get("current_wait_type", "") or ""),
            "event_cursor": int(entry.get("event_cursor", 0) or 0),
            "blend_copy_path": str(entry.get("blend_copy_path", "") or ""),
        }
        self.background_task_plans[task_id] = state
        self.background_processes[task_id] = {
            "process": None,
            "status_path": str(wait_state.get("status_path", "") or "") if wait_state else "",
            "script_path": "",
            "log_path": str(wait_state.get("log_path", "") or "") if wait_state else "",
            "temp_dir": "",
            "blend_copy_path": str(state.get("blend_copy_path", "") or ""),
            "task_kind": "TASK_PLAN",
        }
        self._push_background_task_plan_outputs(state)

    def _flow_finished(self, status, message):
        self._flush_flow_toggle_cache()
        self._flush_status_report_cache()
        self.set_status(status)
        self.settings.current_node_name = ""
        self.log("INFO" if status == STATUS_SUCCESS else "ERROR", message)
        return True


__all__ = ["RuntimeReloadStateMixin"]
