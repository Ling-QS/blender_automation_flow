import os
import uuid

import bpy

from ...runtime_core.constants import FlowExecutionError
from ...runtime_state.cache import _operator_result_tokens


class RuntimeBackgroundProcessCleanupMixin:
    def _save_temporary_background_blend_copy(self, node, temp_dir):
        current_blend_path = str(getattr(bpy.data, "filepath", "") or "")
        has_saved_source = bool(current_blend_path) and os.path.exists(current_blend_path)
        if has_saved_source:
            source_dir = os.path.dirname(current_blend_path)
            source_stem = os.path.splitext(os.path.basename(current_blend_path))[0] or "automation_flow"
            temp_blend_path = os.path.join(source_dir, f"{source_stem}.af_bg_{uuid.uuid4().hex[:8]}.blend")
        else:
            temp_blend_path = os.path.join(temp_dir, f"automation_flow_background_{uuid.uuid4().hex[:8]}.blend")

        save_kwargs = {
            "filepath": temp_blend_path,
            "check_existing": False,
            "copy": True,
            "compress": False,
        }
        try:
            context_override = {key: value for key, value in self.ui_context.items() if value is not None}
            if context_override:
                with bpy.context.temp_override(**context_override):
                    result = bpy.ops.wm.save_as_mainfile(**save_kwargs)
            else:
                result = bpy.ops.wm.save_as_mainfile(**save_kwargs)
        except Exception as exc:
            raise FlowExecutionError("AF_E005", f"Failed to save temporary background .blend copy: {exc}", node.name)

        if "FINISHED" not in _operator_result_tokens(result):
            raise FlowExecutionError("AF_E005", "Failed to save temporary background .blend copy", node.name)
        if not os.path.exists(temp_blend_path):
            raise FlowExecutionError("AF_E005", "Temporary background .blend copy was not created", node.name)
        return temp_blend_path

    def _cleanup_background_task_plan_blend_copy(self, state, keep_artifacts=False):
        if not isinstance(state, dict):
            return
        blend_copy_path = str(state.get("blend_copy_path", "") or "")
        if keep_artifacts:
            return
        if blend_copy_path and os.path.exists(blend_copy_path):
            try:
                os.remove(blend_copy_path)
            except Exception:
                pass

    def _cleanup_background_process(self, task_id, keep_artifacts=False):
        entry = self.background_processes.pop(str(task_id), None)
        if entry is None:
            return
        stdout_handle = entry.get("stdout_handle")
        if stdout_handle is not None:
            try:
                stdout_handle.close()
            except Exception:
                pass
        if keep_artifacts:
            return
