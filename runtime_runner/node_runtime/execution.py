from ...runtime_core.constants import FLOW_OK, FlowExecutionError


class RuntimeNodeExecutionMixin:
    def _execute_node(self, node):
        dry_run = self._is_dry_run_mode()
        flow_test = self._is_flow_test_mode()
        node_type = node.bl_idname
        self._geometry_attribute_cache.clear()

        if node_type in {"AFNodeStart", "AFNodeEnd", "AFNodeTaskStart", "AFNodeSubflowStart"}:
            return FLOW_OK, None
        if node_type == "AFNodeRepeatStart":
            return self._execute_flow_repeat_start(node)
        if node_type == "AFNodeRepeatEnd":
            return self._execute_flow_repeat_end(node)
        if node_type == "AFNodeFlowToggle":
            return self._execute_flow_toggle(node)
        if node_type == "AFNodeSubflowJoin":
            return self._execute_flow_subflow_join(node)
        if node_type == "AFNodeBranchStart":
            return self._execute_flow_branch_start(node)
        if node_type == "AFNodeBranchEnd":
            status_value = str(self._input_string(node, "Status", "") or "").strip().upper()
            if status_value:
                self._set_output(node, "status", status_value)
                self._set_output(node, "report", {"status": status_value})
            return FLOW_OK, status_value or None

        if getattr(node, "mute", False):
            if "status" in {key for output in node.outputs for key in self._socket_output_keys(output)}:
                self._set_output(node, "status", "MUTED")
            self._set_output(node, "report", {"muted": True})
            return FLOW_OK, "MUTED"

        property_package_action_result = self._execute_property_package_action_node(node, dry_run=dry_run)
        if property_package_action_result is not None:
            return property_package_action_result

        object_action_result = self._execute_object_action_node(node, dry_run=dry_run)
        if object_action_result is not None:
            return object_action_result

        scene_action_result = self._execute_scene_action_node(node, dry_run=dry_run, flow_test=flow_test)
        if scene_action_result is not None:
            return scene_action_result

        task_action_result = self._execute_task_action_node(node)
        if task_action_result is not None:
            return task_action_result

        if node_type == "AFNodeRunTaskPlan":
            return self._execute_task_plan(node)

        wait_reload_result = self._execute_wait_reload_node(node, dry_run=dry_run, flow_test=flow_test)
        if wait_reload_result is not None:
            return wait_reload_result

        raise FlowExecutionError("AF_E009", f"Unsupported node type: {node_type}", node.name)

    def _handoff_failure_to_branch(self, node, exc, current_tree_name):
        next_index = int(self.cursor) + 1
        if next_index >= len(self.nodes_in_order):
            return False
        branch_node = self.nodes_in_order[next_index]
        if not self._is_branch_start_node(branch_node):
            return False
        if self.pending_branch_failure is not None:
            return False

        self._set_output(node, "status", "FAILED")
        self._set_output(
            node,
            "report",
            {
                "status": "FAILED",
                "error_code": str(getattr(exc, "code", "AF_E010") or "AF_E010"),
                "error_message": str(getattr(exc, "message", "Flow failed") or "Flow failed"),
                "node_name": str(getattr(exc, "node_name", "") or node.name),
                "tree_name": str(current_tree_name or self.node_tree.name),
            },
        )
        self._mark_node_failed(
            exc.node_name or node.name,
            current_tree_name,
            getattr(exc, "group_path", None),
        )
        self.pending_branch_failure = {
            "code": str(getattr(exc, "code", "AF_E010") or "AF_E010"),
            "message": str(getattr(exc, "message", "Flow failed") or "Flow failed"),
            "node_name": str(getattr(exc, "node_name", "") or node.name),
            "node_tree_name": str(current_tree_name or self.node_tree.name),
            "group_path": list(getattr(exc, "group_path", None) or []),
        }
        self.current_group_path = []
        self.cursor = next_index
        self._active_waiting_node_key = None
        self.log("INFO", f"BRANCH_ARMED [{branch_node.name}] after {str(getattr(exc, 'node_name', '') or node.name)}", branch_node.name)
        return True


__all__ = ["RuntimeNodeExecutionMixin"]
