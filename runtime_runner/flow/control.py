from ...runtime_core.constants import FLOW_OK, FLOW_WAIT, FLOW_YIELD, FlowExecutionError
from ...runtime_flow.helpers import _flow_trigger_output_nodes


class RuntimeFlowControlMixin:
    def _execute_attached_flow_triggers(self, source_node, output_name="Flow Out", group_path=None):
        if source_node is None:
            return 0
        trigger_nodes = _flow_trigger_output_nodes(source_node, output_name)
        if not trigger_nodes:
            return 0

        active_group_path = list(self.current_group_path if group_path is None else group_path)
        previous_group_path = list(self.current_group_path)
        triggered_count = 0
        try:
            for trigger_node in trigger_nodes:
                self.current_group_path = list(active_group_path)
                _result, payload = self._execute_flow_toggle(trigger_node)
                payload_for_log = payload
                if payload_for_log is not None:
                    self.log(
                        "INFO",
                        f"FLOW_TRIGGER_DONE [{source_node.name}] ({payload_for_log})",
                        trigger_node.name,
                        getattr(getattr(trigger_node, "id_data", None), "name", self.node_tree.name),
                    )
                else:
                    self.log(
                        "INFO",
                        f"FLOW_TRIGGER_DONE [{source_node.name}]",
                        trigger_node.name,
                        getattr(getattr(trigger_node, "id_data", None), "name", self.node_tree.name),
                    )
                triggered_count += 1
        finally:
            self.current_group_path = previous_group_path
        return triggered_count

    def _runtime_control_payload(self, cursor_override, count_step=False, log_payload=None, **extra):
        payload = {
            "__af_runtime_control__": True,
            "cursor_override": int(cursor_override),
            "count_step": bool(count_step),
            "log_payload": log_payload,
        }
        payload.update(dict(extra or {}))
        return payload

    def _execute_flow_repeat_start(self, node):
        repeat_info = self.flow_repeat_pairs.get(self.cursor)
        if repeat_info is None:
            raise FlowExecutionError("AF_E009", "Repeat Start is missing compiled repeat metadata", node.name)

        repeat_count = int(repeat_info["count"])
        if repeat_count <= 0:
            self._set_output(node, "int_value", 0)
            self.log("INFO", f"REPEAT_SKIPPED [{node.name}] count=0", node.name)
            return FLOW_OK, self._runtime_control_payload(repeat_info["end_index"] + 1, count_step=False, log_payload="SKIPPED")

        repeat_state = self.flow_repeat_states.get(self.cursor)
        if repeat_state is None:
            repeat_state = {
                "iteration": 0,
                "count": repeat_count,
                "end_index": int(repeat_info["end_index"]),
            }
            self.flow_repeat_states[self.cursor] = repeat_state
        self._invalidate_data_node_outputs()
        self._set_output(node, "int_value", int(repeat_state["iteration"]))
        self._set_output(node, "report", {"index": int(repeat_state["iteration"])})
        self.log("INFO", f"REPEAT_ITERATION [{node.name}] {int(repeat_state['iteration']) + 1}/{repeat_count}", node.name)
        return FLOW_OK, self._runtime_control_payload(self.cursor + 1, count_step=False, log_payload=f"{int(repeat_state['iteration']) + 1}/{repeat_count}")

    def _execute_flow_toggle(self, node):
        previous_value = bool(self._read_flow_toggle_state(node))
        toggled_value = not previous_value
        if not self._is_dry_run_mode() and not self._is_flow_test_mode():
            self._write_flow_toggle_state(node, toggled_value)
        self._set_output(node, "bool_value", toggled_value)
        self._set_output(
            node,
            "report",
            {
                "previous": previous_value,
                "current": toggled_value,
                "persisted": not self._is_dry_run_mode() and not self._is_flow_test_mode(),
            },
        )
        return FLOW_OK, toggled_value

    def _execute_flow_repeat_end(self, node):
        repeat_info = self.flow_repeat_pairs.get(self.cursor)
        if repeat_info is None:
            raise FlowExecutionError("AF_E009", "Repeat End is missing compiled repeat metadata", node.name)

        start_index = int(repeat_info["start_index"])
        repeat_state = self.flow_repeat_states.get(start_index)
        if repeat_state is None:
            return FLOW_OK, self._runtime_control_payload(self.cursor + 1, count_step=False)

        next_iteration = int(repeat_state["iteration"]) + 1
        if next_iteration < int(repeat_state["count"]):
            repeat_state["iteration"] = next_iteration
            return FLOW_OK, self._runtime_control_payload(start_index, count_step=False, log_payload=f"LOOP {next_iteration + 1}/{int(repeat_state['count'])}")

        self.flow_repeat_states.pop(start_index, None)
        start_node = self.nodes_in_order[start_index] if 0 <= start_index < len(self.nodes_in_order) else node
        self.log("INFO", f"REPEAT_DONE [{start_node.name}] {int(repeat_state['count'])} iteration(s)", start_node.name)
        return FLOW_OK, self._runtime_control_payload(self.cursor + 1, count_step=False, log_payload="DONE")

    def _execute_flow_subflow_join(self, node):
        subflow_plan = self.flow_subflow_plans.get(self.cursor)
        if subflow_plan is None:
            raise FlowExecutionError("AF_E009", "Subflow Join is missing compiled subflow metadata", node.name)

        force_trigger = self._node_identity(node) in self.isolated_subflow_join_keys
        trigger = True if force_trigger else bool(self._input_bool(node, "Trigger", False))
        if not trigger:
            report = {
                "triggered": False,
                "executed_step_count": 0,
                "step_count": int(subflow_plan.get("step_count", 0)),
                "skipped": True,
                "isolated": False,
            }
            self._set_output(node, "report", report)
            self.current_group_path = []
            self._set_current_node(node)
            self.log("INFO", f"SUBFLOW_SKIPPED [{node.name}]", node.name)
            return FLOW_OK, "SKIPPED"

        step_refs = list(subflow_plan.get("step_refs", []) or [])
        executed_steps = 0
        self.log("INFO", f"SUBFLOW_STARTED [{node.name}] {len(step_refs)} step(s)", node.name)
        for step_ref in step_refs:
            step_node = self._resolve_step_ref(step_ref, node.name)
            step_tree_name = getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name)
            self.current_group_path = list(step_ref.get("group_path", []))
            self._set_current_node(step_node)
            self.log("INFO", f"SUBFLOW_STEP_STARTED [{node.name}]", step_node.name, step_tree_name)
            result, payload = self._execute_node(step_node)
            if result == FLOW_WAIT:
                raise FlowExecutionError("AF_E020", "Subflow does not support waiting nodes", step_node.name, step_tree_name, step_ref.get("group_path", []))
            if result == FLOW_YIELD:
                raise FlowExecutionError("AF_E020", "Subflow does not support yielding nodes", step_node.name, step_tree_name, step_ref.get("group_path", []))
            control_payload = payload if isinstance(payload, dict) and payload.get("__af_runtime_control__") else None
            if control_payload is not None:
                raise FlowExecutionError("AF_E020", "Subflow does not support nested flow control nodes", step_node.name, step_tree_name, step_ref.get("group_path", []))
            payload_for_log = payload
            if payload_for_log is not None:
                self.log("INFO", f"SUBFLOW_STEP_DONE [{node.name}] ({payload_for_log})", step_node.name, step_tree_name)
            else:
                self.log("INFO", f"SUBFLOW_STEP_DONE [{node.name}]", step_node.name, step_tree_name)
            self._mark_node_finished(step_node)
            self._execute_attached_flow_triggers(step_node, group_path=step_ref.get("group_path", []))
            executed_steps += 1

        report = {
            "triggered": True,
            "executed_step_count": int(executed_steps),
            "step_count": int(subflow_plan.get("step_count", executed_steps)),
            "skipped": False,
            "isolated": bool(force_trigger),
        }
        self._set_output(node, "report", report)
        self.current_group_path = []
        self._set_current_node(node)
        self.log("INFO", f"SUBFLOW_DONE [{node.name}] {executed_steps} step(s)", node.name)
        return FLOW_OK, executed_steps

    def _execute_flow_branch_start(self, node):
        branch_plan = self.flow_branch_plans.get(self.cursor)
        if branch_plan is None:
            raise FlowExecutionError("AF_E009", "Branch Start is missing compiled branch metadata", node.name)

        force_trigger = self._node_identity(node) in self.isolated_branch_start_keys
        pending_failure = dict(self.pending_branch_failure or {}) if isinstance(self.pending_branch_failure, dict) else None
        trigger = True if force_trigger else bool(self._input_bool(node, "Trigger", False))
        if not trigger and pending_failure is not None:
            raise FlowExecutionError(
                str(pending_failure.get("code", "AF_E010") or "AF_E010"),
                str(pending_failure.get("message", "Unhandled branch failure") or "Unhandled branch failure"),
                str(pending_failure.get("node_name", node.name) or node.name),
                str(pending_failure.get("node_tree_name", self.node_tree.name) or self.node_tree.name),
                pending_failure.get("group_path", []),
            )
        if not trigger:
            return FLOW_OK, self._runtime_control_payload(
                self.cursor + 1,
                count_step=False,
                branch_triggered=False,
                executed_steps=0,
            )

        step_refs = list(branch_plan.get("step_refs", []) or [])
        executed_steps = 0
        self.pending_branch_failure = None
        if pending_failure is not None:
            self.log("INFO", f"BRANCH_HANDLING_FAILURE [{node.name}] {pending_failure.get('code', 'AF_E010')}", node.name)
        else:
            self.log("INFO", f"BRANCH_STARTED [{node.name}]", node.name)
        for step_ref in step_refs:
            step_node = self._resolve_step_ref(step_ref, node.name)
            step_tree_name = getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name)
            self.current_group_path = list(step_ref.get("group_path", []))
            self._set_current_node(step_node)
            self.log("INFO", f"BRANCH_STEP_STARTED [{node.name}]", step_node.name, step_tree_name)
            result, payload = self._execute_node(step_node)
            if result == FLOW_WAIT:
                raise FlowExecutionError("AF_E020", "Branch does not support waiting nodes", step_node.name, step_tree_name, step_ref.get("group_path", []))
            if result == FLOW_YIELD:
                raise FlowExecutionError("AF_E020", "Branch does not support yielding nodes", step_node.name, step_tree_name, step_ref.get("group_path", []))
            control_payload = payload if isinstance(payload, dict) and payload.get("__af_runtime_control__") else None
            if control_payload is not None:
                raise FlowExecutionError("AF_E020", "Branch does not support nested flow control nodes", step_node.name, step_tree_name, step_ref.get("group_path", []))
            payload_for_log = payload
            if payload_for_log is not None:
                self.log("INFO", f"BRANCH_STEP_DONE [{node.name}] ({payload_for_log})", step_node.name, step_tree_name)
            else:
                self.log("INFO", f"BRANCH_STEP_DONE [{node.name}]", step_node.name, step_tree_name)
            self._mark_node_finished(step_node)
            self._execute_attached_flow_triggers(step_node, group_path=step_ref.get("group_path", []))
            executed_steps += 1

        self.current_group_path = []
        self._set_current_node(node)
        self.log("INFO", f"BRANCH_DONE [{node.name}] {executed_steps} step(s)", node.name)
        branch_status_override = ""
        end_node = None
        end_ref = dict(branch_plan.get("end_ref", {}) or {})
        if end_ref:
            try:
                end_node = self._resolve_step_ref(end_ref, node.name)
            except Exception:
                end_node = None
        if end_node is None:
            end_node_name = str(branch_plan.get("end_node_name", "") or "")
            if end_node_name:
                end_node = getattr(self.node_tree, "nodes", None).get(end_node_name) if getattr(self.node_tree, "nodes", None) is not None else None
        if end_node is not None and str(getattr(end_node, "bl_idname", "") or "") == "AFNodeBranchEnd":
            try:
                previous_group_path = list(self.current_group_path)
                try:
                    self.current_group_path = list(end_ref.get("group_path", [])) if end_ref else []
                    branch_status_override = self._normalize_task_plan_final_status(
                        str(self._input_string(end_node, "Status", "") or "").strip()
                    )
                finally:
                    self.current_group_path = previous_group_path
            except Exception:
                branch_status_override = ""
        return FLOW_OK, self._runtime_control_payload(
            len(self.nodes_in_order),
            count_step=False,
            log_payload="BRANCHED",
            branch_triggered=True,
            executed_steps=int(executed_steps),
            branch_status_override=branch_status_override,
        )


__all__ = ["RuntimeFlowControlMixin"]
