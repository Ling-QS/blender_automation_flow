from ...runtime_core.constants import FlowExecutionError


class RuntimeNodeUtilsMixin:
    def clear_logs(self):
        self.scene.af_flow_logs.clear()

    def preview_flow_output(self, node, output_key):
        if node is None:
            return None
        node_type = str(getattr(node, "bl_idname", "") or "")
        previous_group_path = list(self.current_group_path)
        if node_type == "AFNodeFlowToggle" and output_key == "bool_value":
            return self._get_output(node, output_key, previous_group_path)
        if node_type in self.DATA_NODE_TYPES:
            previous_preview_read_only = bool(getattr(self, "_preview_data_node_read_only", False))
            try:
                self._preview_data_node_read_only = True
                self._evaluate_data_node(node)
            except FlowExecutionError:
                return None
            finally:
                self._preview_data_node_read_only = previous_preview_read_only
            return self._get_output(node, output_key, previous_group_path)
        if node_type in {"AFNodeStart", "AFNodeEnd", "AFNodeTaskStart", "AFNodeRepeatStart", "AFNodeRepeatEnd"}:
            return None
        previous_run_mode = str(getattr(self.settings, "run_mode", "NORMAL") or "NORMAL")
        try:
            self.settings.run_mode = "DRY_RUN"
            self._execute_node(node)
        except FlowExecutionError:
            return None
        finally:
            self.settings.run_mode = previous_run_mode
            self.current_group_path = previous_group_path
        return self._get_output(node, output_key, previous_group_path)

    def _invoke_render_task_for_scene_actions(self, task_ref, fallback_scene, node_name):
        return self._invoke_render_task(task_ref, fallback_scene, node_name)

    def _set_scalar_vector_outputs(self, node, float_value=None, bool_value=None, vector_value=None, int_value=None):
        if float_value is not None:
            self._set_output(node, "float_value", float(float_value))
        if bool_value is not None:
            self._set_output(node, "bool_value", bool(bool_value))
        if vector_value is not None:
            self._set_output(node, "vector_value", (float(vector_value[0]), float(vector_value[1]), float(vector_value[2])))
        if int_value is not None:
            self._set_output(node, "int_value", int(int_value))


__all__ = ["RuntimeNodeUtilsMixin"]
