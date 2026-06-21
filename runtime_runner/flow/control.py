from ...runtime_core.constants import FLOW_OK, FLOW_WAIT, FLOW_YIELD, FlowExecutionError
from ...runtime_flow.helpers import _flow_trigger_output_nodes


class RuntimeFlowControlMixin:
    def _execute_flow_side_hook(self, node):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeFlowToggle":
            return self._execute_flow_toggle(node)
        if node_type == "AFNodeTaskStatusOverride":
            return self._execute_task_status_override(node)
        raise FlowExecutionError("AF_E009", f"Unsupported flow side-hook type: {node_type}", getattr(node, "name", ""))

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
                _result, payload = self._execute_flow_side_hook(trigger_node)
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

    def _flow_trigger_output_names_after_node(self, node, control_payload=None):
        if node is None:
            return ("Flow Out",)
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeBranchStart":
            if isinstance(control_payload, dict) and bool(control_payload.get("branch_triggered", False)):
                return ()
            return ("Flow Out",)
        return ("Flow Out",)

    def _execute_post_node_flow_triggers(self, node, control_payload=None, group_path=None):
        triggered_count = 0
        for output_name in self._flow_trigger_output_names_after_node(node, control_payload):
            triggered_count += int(
                self._execute_attached_flow_triggers(
                    node,
                    output_name=output_name,
                    group_path=group_path,
                )
            )
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

    def _execute_local_flow_segment(self, owner_node, segment_plan, segment_label):
        normalized_plan = self._normalize_local_segment_plan(segment_plan)
        step_refs = list(normalized_plan.get("step_refs", []) or [])
        local_nodes = [self._resolve_step_ref(step_ref, owner_node.name) for step_ref in step_refs]
        previous_nodes_in_order = self.nodes_in_order
        previous_group_paths_in_order = getattr(self, "node_group_paths_in_order", [])
        previous_cursor = int(self.cursor)
        previous_group_path = list(self.current_group_path)
        previous_repeat_pairs = self.flow_repeat_pairs
        previous_repeat_states = self.flow_repeat_states
        previous_subflow_plans = self.flow_subflow_plans
        previous_branch_plans = self.flow_branch_plans
        previous_pending_branch_failure = self.pending_branch_failure
        executed_steps = 0
        self.nodes_in_order = list(local_nodes)
        self.node_group_paths_in_order = [
            [dict(item) for item in list(step_ref.get("group_path", []) or []) if isinstance(item, dict)]
            for step_ref in step_refs
        ]
        self.cursor = 0
        self.flow_repeat_pairs = self._normalize_repeat_pairs(normalized_plan.get("repeat_pairs", {}))
        self.flow_repeat_states = {}
        self.flow_subflow_plans = self._normalize_indexed_local_plans(normalized_plan.get("subflow_plans", {}))
        self.flow_branch_plans = self._normalize_indexed_local_plans(normalized_plan.get("branch_plans", {}))
        try:
            while self.cursor < len(self.nodes_in_order):
                step_node = self.nodes_in_order[self.cursor]
                step_ref = step_refs[self.cursor]
                step_tree_name = getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name)
                self.current_group_path = list(step_ref.get("group_path", []))
                self._set_current_node(step_node)
                self.log("INFO", f"{segment_label}_STEP_STARTED [{owner_node.name}]", step_node.name, step_tree_name)
                completed_before_step = int(self.completed_step_count)
                try:
                    result, payload = self._execute_node(step_node)
                except FlowExecutionError as exc:
                    if self._handoff_failure_to_branch(step_node, exc, step_tree_name):
                        continue
                    raise
                except Exception as exc:
                    wrapped = FlowExecutionError(
                        "AF_E999",
                        str(exc),
                        step_node.name,
                        step_tree_name,
                        step_ref.get("group_path", []),
                    )
                    if self._handoff_failure_to_branch(step_node, wrapped, step_tree_name):
                        continue
                    raise wrapped

                if result == FLOW_WAIT:
                    raise FlowExecutionError(
                        "AF_E020",
                        f"{segment_label.title()} does not support waiting nodes",
                        step_node.name,
                        step_tree_name,
                        step_ref.get("group_path", []),
                    )
                if result == FLOW_YIELD:
                    raise FlowExecutionError(
                        "AF_E020",
                        f"{segment_label.title()} does not support yielding nodes",
                        step_node.name,
                        step_tree_name,
                        step_ref.get("group_path", []),
                    )

                control_payload = payload if isinstance(payload, dict) and payload.get("__af_runtime_control__") else None
                self._record_auto_follow_tick_node(step_node, group_path=step_ref.get("group_path", []))
                payload_for_log = control_payload.get("log_payload") if control_payload is not None else payload
                if payload_for_log is not None:
                    self.log("INFO", f"{segment_label}_STEP_DONE [{owner_node.name}] ({payload_for_log})", step_node.name, step_tree_name)
                else:
                    self.log("INFO", f"{segment_label}_STEP_DONE [{owner_node.name}]", step_node.name, step_tree_name)
                self._mark_node_finished(
                    step_node,
                    count_step=bool(control_payload.get("count_step", True)) if control_payload is not None else True,
                )
                self._execute_post_node_flow_triggers(
                    step_node,
                    control_payload=control_payload,
                    group_path=step_ref.get("group_path", []),
                )
                executed_steps += max(0, int(self.completed_step_count) - completed_before_step)
                if control_payload is not None and "cursor_override" in control_payload:
                    self.cursor = int(control_payload["cursor_override"])
                else:
                    self.cursor += 1
        finally:
            self.pending_branch_failure = previous_pending_branch_failure
            self.flow_branch_plans = previous_branch_plans
            self.flow_subflow_plans = previous_subflow_plans
            self.flow_repeat_states = previous_repeat_states
            self.flow_repeat_pairs = previous_repeat_pairs
            self.current_group_path = previous_group_path
            self.cursor = previous_cursor
            self.node_group_paths_in_order = previous_group_paths_in_order
            self.nodes_in_order = previous_nodes_in_order
        return executed_steps

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

    def _execute_task_status_override(self, node):
        status_value = str(self._input_string(node, "Status", "") or "")
        normalized_status = self._normalize_task_plan_final_status(status_value)
        applied = bool(self._write_task_plan_runtime_status_override(normalized_status))
        if applied:
            return FLOW_OK, normalized_status or "CLEARED"
        return FLOW_OK, "NOOP"

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
        subflow_plan = self._normalize_local_segment_plan(self.flow_subflow_plans.get(self.cursor, {}))
        if not subflow_plan:
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

        start_node = self._find_subflow_start_for_join(node)
        if start_node is not None:
            self._execute_attached_flow_triggers(
                start_node,
                output_name="Subflow",
                group_path=list(self.current_group_path),
            )

        step_refs = list(subflow_plan.get("step_refs", []) or [])
        self.log("INFO", f"SUBFLOW_STARTED [{node.name}] {int(subflow_plan.get('step_count', len(step_refs)))} step(s)", node.name)
        executed_steps = self._execute_local_flow_segment(node, subflow_plan, "SUBFLOW")

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
        branch_plan = self._normalize_local_segment_plan(self.flow_branch_plans.get(self.cursor, {}))
        if not branch_plan:
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
        self.pending_branch_failure = None
        if pending_failure is not None:
            self.log("INFO", f"BRANCH_HANDLING_FAILURE [{node.name}] {pending_failure.get('code', 'AF_E010')}", node.name)
        else:
            self.log("INFO", f"BRANCH_STARTED [{node.name}]", node.name)
        self._execute_attached_flow_triggers(
            node,
            output_name="Branch Flow",
            group_path=list(self.current_group_path),
        )
        executed_steps = self._execute_local_flow_segment(node, branch_plan, "BRANCH")

        self.current_group_path = []
        self._set_current_node(node)
        self.log("INFO", f"BRANCH_DONE [{node.name}] {executed_steps} step(s)", node.name)
        return FLOW_OK, self._runtime_control_payload(
            len(self.nodes_in_order),
            count_step=False,
            log_payload="BRANCHED",
            branch_triggered=True,
            executed_steps=int(executed_steps),
        )


__all__ = ["RuntimeFlowControlMixin"]
