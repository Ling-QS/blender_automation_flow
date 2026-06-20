from ...runtime_core.constants import FlowExecutionError
from ...runtime_flow.helpers import (
    _find_single_from_input_socket,
    _is_branch_end_node,
    _is_branch_start_node,
    _is_repeat_end_node,
    _is_repeat_start_node,
    _is_subflow_join_node,
    _is_subflow_start_node,
    _scan_repeat_pairs,
)


class RuntimeFlowStructureMixin:
    def _is_repeat_start_node(self, node):
        return _is_repeat_start_node(node)

    def _is_repeat_end_node(self, node):
        return _is_repeat_end_node(node)

    def _is_subflow_start_node(self, node):
        return _is_subflow_start_node(node)

    def _is_subflow_join_node(self, node):
        return _is_subflow_join_node(node)

    def _is_branch_start_node(self, node):
        return _is_branch_start_node(node)

    def _is_branch_end_node(self, node):
        return _is_branch_end_node(node)

    def _entry_group_path(self, entry):
        return list(entry.get("group_path", []))

    def _entry_node(self, entry):
        return entry["node"]

    def _compile_repeat_metadata(self, entries, owner_node_name, entry_cost_fn):
        scan_result = _scan_repeat_pairs(entries, self._entry_node)
        if not scan_result["ok"]:
            raise FlowExecutionError(scan_result["code"], scan_result["message"], scan_result["node_name"] or owner_node_name)

        repeat_pairs = {}
        for pair in scan_result["pairs"]:
            start_index = int(pair["start_index"])
            end_index = int(pair["end_index"])
            start_entry = entries[start_index]
            previous_group_path = list(self.current_group_path)
            self.current_group_path = self._entry_group_path(start_entry)
            try:
                repeat_count = max(0, int(self._input_int(self._entry_node(start_entry), "Count", 1)))
            finally:
                self.current_group_path = previous_group_path

            body_step_count = 0
            for body_index in range(start_index + 1, end_index):
                body_step_count += int(entry_cost_fn(entries[body_index]))

            repeat_pairs[start_index] = {
                "start_index": int(start_index),
                "end_index": int(end_index),
                "count": int(repeat_count),
                "body_step_count": int(body_step_count),
            }
            repeat_pairs[end_index] = {
                "start_index": int(start_index),
                "end_index": int(end_index),
            }

        total_steps = 0
        index = 0
        while index < len(entries):
            node = self._entry_node(entries[index])
            if self._is_repeat_start_node(node):
                repeat_info = repeat_pairs.get(index)
                if repeat_info is None:
                    raise FlowExecutionError("AF_E009", "Repeat Start is missing compiled repeat metadata", node.name)
                total_steps += int(repeat_info["body_step_count"]) * int(repeat_info["count"])
                index = int(repeat_info["end_index"]) + 1
                continue
            if self._is_repeat_end_node(node):
                index += 1
                continue
            total_steps += int(entry_cost_fn(entries[index]))
            index += 1

        return repeat_pairs, total_steps

    def _compile_subflow_step_refs(self, join_node, owner_node_name, group_path=None):
        inputs = getattr(join_node, "inputs", None)
        get_input = getattr(inputs, "get", lambda _name: None)
        subflow_input = get_input("Subflow")
        if subflow_input is None:
            subflow_input = get_input("Subflow In")
        if subflow_input is None:
            raise FlowExecutionError("AF_E009", "Subflow Join is missing Subflow", owner_node_name)

        reverse_step_refs = []
        visited = {self._node_identity(join_node)}
        current, _current_socket = _find_single_from_input_socket(subflow_input)

        while current is not None:
            current_key = self._node_identity(current)
            if current_key in visited:
                raise FlowExecutionError("AF_E009", "Subflow branch has a loop", current.name)
            visited.add(current_key)

            if self._is_subflow_start_node(current):
                break

            if getattr(current, "mute", False):
                if "Flow In" not in current.inputs:
                    raise FlowExecutionError("AF_E009", "Muted subflow node is missing Flow In", current.name)
                current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])
                continue

            current_type = str(getattr(current, "bl_idname", "") or "")
            if current_type in self.SUBFLOW_UNSUPPORTED_NODE_TYPES:
                raise FlowExecutionError("AF_E020", f"Subflow does not support '{current.bl_label}'", current.name)

            if "Flow In" not in current.inputs:
                raise FlowExecutionError("AF_E009", "Subflow node is missing Flow In", current.name)

            reverse_step_refs.append(self._make_step_ref(current, group_path))
            current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])

        if current is None or not self._is_subflow_start_node(current):
            raise FlowExecutionError("AF_E009", "Subflow Join cannot reach Subflow Start", join_node.name)

        reverse_step_refs.reverse()
        step_count = 0
        for step_ref in reverse_step_refs:
            step_node = self._resolve_step_ref(step_ref, owner_node_name)
            step_count += int(self._flow_node_step_cost(step_node))
        return {
            "step_refs": reverse_step_refs,
            "step_count": int(step_count),
            "start_node_name": str(getattr(current, "name", "") or ""),
        }

    def _compile_subflow_metadata(self, entries, owner_node_name):
        subflow_plans = {}
        total_steps = 0
        for index, entry in enumerate(entries):
            node = self._entry_node(entry)
            if not self._is_subflow_join_node(node):
                continue
            plan = self._compile_subflow_step_refs(node, owner_node_name, entry.get("group_path", []))
            plan["join_index"] = int(index)
            plan["join_node_name"] = str(getattr(node, "name", "") or "")
            subflow_plans[index] = plan
            total_steps += int(plan["step_count"])
        return subflow_plans, total_steps

    def _find_branch_end_for_start(self, start_node):
        if start_node is None:
            return None
        pair_id = str(getattr(start_node, "af_pair_id", "") or "").strip()
        if not pair_id:
            return None
        node_tree = getattr(start_node, "id_data", None)
        for candidate in getattr(node_tree, "nodes", []):
            if not self._is_branch_end_node(candidate):
                continue
            if str(getattr(candidate, "af_pair_id", "") or "").strip() == pair_id:
                return candidate
        return None

    def _find_branch_start_for_end(self, end_node):
        if end_node is None:
            return None
        pair_id = str(getattr(end_node, "af_pair_id", "") or "").strip()
        if not pair_id:
            return None
        node_tree = getattr(end_node, "id_data", None)
        for candidate in getattr(node_tree, "nodes", []):
            if not self._is_branch_start_node(candidate):
                continue
            if str(getattr(candidate, "af_pair_id", "") or "").strip() == pair_id:
                return candidate
        return None

    def _compile_branch_step_refs(self, end_node, owner_node_name, group_path=None):
        branch_input = getattr(getattr(end_node, "inputs", None), "get", lambda _name: None)("Branch Flow")
        if branch_input is None:
            raise FlowExecutionError("AF_E009", "Branch End is missing Branch Flow", owner_node_name)

        reverse_step_refs = []
        visited = {self._node_identity(end_node)}
        current, _current_socket = _find_single_from_input_socket(branch_input)

        while current is not None:
            current_key = self._node_identity(current)
            if current_key in visited:
                raise FlowExecutionError("AF_E009", "Branch flow has a loop", current.name)
            visited.add(current_key)

            if self._is_branch_start_node(current):
                break

            if getattr(current, "mute", False):
                if "Flow In" not in current.inputs:
                    raise FlowExecutionError("AF_E009", "Muted branch node is missing Flow In", current.name)
                current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])
                continue

            current_type = str(getattr(current, "bl_idname", "") or "")
            if current_type in self.BRANCH_UNSUPPORTED_NODE_TYPES:
                raise FlowExecutionError("AF_E020", f"Branch does not support '{current.bl_label}'", current.name)

            if "Flow In" not in current.inputs:
                raise FlowExecutionError("AF_E009", "Branch node is missing Flow In", current.name)

            reverse_step_refs.append(self._make_step_ref(current, group_path))
            current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])

        if current is None or not self._is_branch_start_node(current):
            raise FlowExecutionError("AF_E009", "Branch End cannot reach Branch Start", end_node.name)

        reverse_step_refs.reverse()
        step_count = 0
        for step_ref in reverse_step_refs:
            step_node = self._resolve_step_ref(step_ref, owner_node_name)
            step_count += int(self._flow_node_step_cost(step_node))
        return {
            "step_refs": reverse_step_refs,
            "step_count": int(step_count),
            "start_node_name": str(getattr(current, "name", "") or ""),
            "end_node_name": str(getattr(end_node, "name", "") or ""),
            "end_ref": self._make_step_ref(end_node, group_path),
        }

    def _compile_branch_metadata(self, entries, owner_node_name):
        branch_plans = {}
        total_steps = 0
        for index, entry in enumerate(entries):
            node = self._entry_node(entry)
            if not self._is_branch_start_node(node):
                continue
            end_node = self._find_branch_end_for_start(node)
            if end_node is None:
                raise FlowExecutionError("AF_E009", "Branch Start has no matching Branch End", node.name)
            plan = self._compile_branch_step_refs(end_node, owner_node_name)
            if str(plan.get("start_node_name", "") or "") != str(getattr(node, "name", "") or ""):
                raise FlowExecutionError("AF_E009", "Branch End cannot reach matching Branch Start", end_node.name)
            plan["start_index"] = int(index)
            branch_plans[index] = plan
            total_steps += int(plan["step_count"])
        return branch_plans, total_steps

    def _compile_task_plan_branch_metadata(self, step_entries, owner_node_name):
        branch_plans = {}
        total_steps = 0
        for index, entry in enumerate(step_entries):
            node = self._entry_node(entry)
            if not self._is_branch_start_node(node):
                continue
            end_node = self._find_branch_end_for_start(node)
            if end_node is None:
                raise FlowExecutionError("AF_E009", "Branch Start has no matching Branch End", node.name)
            plan = self._compile_branch_step_refs(end_node, owner_node_name, entry.get("group_path", []))
            plan["start_index"] = int(index)
            branch_plans[int(index)] = plan
            total_steps += int(plan["step_count"])
        return branch_plans, total_steps


__all__ = ["RuntimeFlowStructureMixin"]
