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

    def _normalize_step_refs(self, step_refs):
        normalized = []
        for step_ref in list(step_refs or []):
            if not isinstance(step_ref, dict):
                continue
            normalized_ref = {
                "tree_name": str(step_ref.get("tree_name", "") or ""),
                "node_name": str(step_ref.get("node_name", "") or ""),
            }
            group_path = []
            for item in list(step_ref.get("group_path", []) or []):
                if not isinstance(item, dict):
                    continue
                group_path.append(
                    {
                        "tree_name": str(item.get("tree_name", "") or ""),
                        "node_name": str(item.get("node_name", "") or ""),
                    }
                )
            if group_path:
                normalized_ref["group_path"] = group_path
            normalized.append(normalized_ref)
        return normalized

    def _normalize_repeat_pairs(self, repeat_pairs):
        normalized = {}
        for key, value in dict(repeat_pairs or {}).items():
            try:
                index = int(key)
            except Exception:
                continue
            if not isinstance(value, dict):
                continue
            record = dict(value)
            for field_name in ("start_index", "end_index", "count", "body_step_count", "iteration"):
                if field_name not in record:
                    continue
                try:
                    record[field_name] = int(record.get(field_name, 0) or 0)
                except Exception:
                    record[field_name] = 0
            normalized[index] = record
        return normalized

    def _normalize_indexed_local_plans(self, plans):
        normalized = {}
        for key, value in dict(plans or {}).items():
            try:
                index = int(key)
            except Exception:
                continue
            if not isinstance(value, dict):
                continue
            normalized[index] = self._normalize_local_segment_plan(value)
        return normalized

    def _normalize_local_segment_plan(self, plan):
        if not isinstance(plan, dict):
            return {}
        normalized = dict(plan)
        normalized["step_refs"] = self._normalize_step_refs(plan.get("step_refs", []))
        normalized["repeat_pairs"] = self._normalize_repeat_pairs(plan.get("repeat_pairs", {}))
        normalized["subflow_plans"] = self._normalize_indexed_local_plans(plan.get("subflow_plans", {}))
        normalized["branch_plans"] = self._normalize_indexed_local_plans(plan.get("branch_plans", {}))
        if isinstance(plan.get("end_ref"), dict):
            end_refs = self._normalize_step_refs([plan.get("end_ref")])
            normalized["end_ref"] = end_refs[0] if end_refs else {}
        for field_name in ("step_count", "join_index", "start_index"):
            if field_name not in normalized:
                continue
            try:
                normalized[field_name] = int(normalized.get(field_name, 0) or 0)
            except Exception:
                normalized[field_name] = 0
        for field_name in ("start_node_name", "join_node_name", "end_node_name"):
            if field_name in normalized:
                normalized[field_name] = str(normalized.get(field_name, "") or "")
        return normalized

    def _iter_local_plan_step_refs_recursive(self, plan):
        normalized_plan = self._normalize_local_segment_plan(plan)
        step_refs = list(normalized_plan.get("step_refs", []) or [])
        subflow_plans = dict(normalized_plan.get("subflow_plans", {}) or {})
        branch_plans = dict(normalized_plan.get("branch_plans", {}) or {})
        for index, step_ref in enumerate(step_refs):
            yield dict(step_ref)
            nested_subflow = subflow_plans.get(index)
            if isinstance(nested_subflow, dict):
                yield from self._iter_local_plan_step_refs_recursive(nested_subflow)
            nested_branch = branch_plans.get(index)
            if isinstance(nested_branch, dict):
                yield from self._iter_local_plan_step_refs_recursive(nested_branch)

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

    def _resolve_step_entries(self, step_refs, owner_node_name):
        step_entries = []
        for step_ref in self._normalize_step_refs(step_refs):
            step_entries.append(
                {
                    "node": self._resolve_step_ref(step_ref, owner_node_name),
                    "group_path": list(step_ref.get("group_path", [])),
                }
            )
        return step_entries

    def _compile_local_segment_plan(self, step_refs, owner_node_name, entry_cost_fn):
        normalized_step_refs = self._normalize_step_refs(step_refs)
        step_entries = self._resolve_step_entries(normalized_step_refs, owner_node_name)
        repeat_pairs, step_count = self._compile_repeat_metadata(step_entries, owner_node_name, entry_cost_fn)
        subflow_plans, subflow_step_count = self._compile_subflow_metadata(
            step_entries,
            owner_node_name,
            entry_cost_fn=entry_cost_fn,
        )
        branch_plans, branch_step_count = self._compile_branch_metadata(
            step_entries,
            owner_node_name,
            entry_cost_fn=entry_cost_fn,
        )
        return {
            "step_refs": normalized_step_refs,
            "repeat_pairs": repeat_pairs,
            "subflow_plans": subflow_plans,
            "branch_plans": branch_plans,
            "step_count": int(step_count) + int(subflow_step_count) + int(branch_step_count),
        }

    def _find_subflow_start_for_join(self, join_node):
        if join_node is None:
            return None
        pair_id = str(getattr(join_node, "af_pair_id", "") or "").strip()
        if not pair_id:
            return None
        node_tree = getattr(join_node, "id_data", None)
        for candidate in getattr(node_tree, "nodes", []):
            if not self._is_subflow_start_node(candidate):
                continue
            if str(getattr(candidate, "af_pair_id", "") or "").strip() == pair_id:
                return candidate
        return None

    def _compile_subflow_step_refs(self, join_node, owner_node_name, group_path=None, entry_cost_fn=None):
        inputs = getattr(join_node, "inputs", None)
        get_input = getattr(inputs, "get", lambda _name: None)
        subflow_input = get_input("Subflow")
        if subflow_input is None:
            subflow_input = get_input("Subflow In")
        if subflow_input is None:
            raise FlowExecutionError("AF_E009", "Subflow Join is missing Subflow", owner_node_name)
        start_node = self._find_subflow_start_for_join(join_node)
        if start_node is None:
            raise FlowExecutionError("AF_E009", "Subflow Join cannot find its matching Subflow Start", join_node.name)

        reverse_step_refs = []
        visited = {self._node_identity(join_node)}
        current, _current_socket = _find_single_from_input_socket(subflow_input)
        start_node_key = self._node_identity(start_node)

        while current is not None:
            current_key = self._node_identity(current)
            if current_key in visited:
                raise FlowExecutionError("AF_E009", "Subflow branch has a loop", current.name)
            visited.add(current_key)

            if current_key == start_node_key:
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

        if current is None or self._node_identity(current) != start_node_key:
            raise FlowExecutionError("AF_E009", "Subflow Join cannot reach Subflow Start", join_node.name)

        reverse_step_refs.reverse()
        plan = self._compile_local_segment_plan(
            reverse_step_refs,
            owner_node_name,
            entry_cost_fn
            if callable(entry_cost_fn)
            else (lambda entry: self._flow_node_step_cost(self._entry_node(entry))),
        )
        plan["start_node_name"] = str(getattr(start_node, "name", "") or "")
        return plan

    def _compile_subflow_metadata(self, entries, owner_node_name, entry_cost_fn=None):
        subflow_plans = {}
        total_steps = 0
        for index, entry in enumerate(entries):
            node = self._entry_node(entry)
            if not self._is_subflow_join_node(node):
                continue
            plan = self._compile_subflow_step_refs(
                node,
                owner_node_name,
                entry.get("group_path", []),
                entry_cost_fn=entry_cost_fn,
            )
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

    def _compile_branch_step_refs(self, end_node, owner_node_name, group_path=None, entry_cost_fn=None):
        branch_input = getattr(getattr(end_node, "inputs", None), "get", lambda _name: None)("Branch Flow")
        if branch_input is None:
            raise FlowExecutionError("AF_E009", "Branch End is missing Branch Flow", owner_node_name)
        start_node = self._find_branch_start_for_end(end_node)
        if start_node is None:
            raise FlowExecutionError("AF_E009", "Branch End cannot find its matching Branch Start", end_node.name)

        reverse_step_refs = []
        visited = {self._node_identity(end_node)}
        current, _current_socket = _find_single_from_input_socket(branch_input)
        start_node_key = self._node_identity(start_node)

        while current is not None:
            current_key = self._node_identity(current)
            if current_key in visited:
                raise FlowExecutionError("AF_E009", "Branch flow has a loop", current.name)
            visited.add(current_key)

            if current_key == start_node_key:
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

        if current is None or self._node_identity(current) != start_node_key:
            raise FlowExecutionError("AF_E009", "Branch End cannot reach Branch Start", end_node.name)

        reverse_step_refs.reverse()
        plan = self._compile_local_segment_plan(
            reverse_step_refs,
            owner_node_name,
            entry_cost_fn
            if callable(entry_cost_fn)
            else (lambda entry: self._flow_node_step_cost(self._entry_node(entry))),
        )
        plan["start_node_name"] = str(getattr(start_node, "name", "") or "")
        plan["end_node_name"] = str(getattr(end_node, "name", "") or "")
        plan["end_ref"] = self._make_step_ref(end_node, group_path)
        return plan

    def _compile_branch_metadata(self, entries, owner_node_name, entry_cost_fn=None):
        branch_plans = {}
        total_steps = 0
        for index, entry in enumerate(entries):
            node = self._entry_node(entry)
            if not self._is_branch_start_node(node):
                continue
            end_node = self._find_branch_end_for_start(node)
            if end_node is None:
                raise FlowExecutionError("AF_E009", "Branch Start has no matching Branch End", node.name)
            plan = self._compile_branch_step_refs(
                end_node,
                owner_node_name,
                entry.get("group_path", []),
                entry_cost_fn=entry_cost_fn,
            )
            if str(plan.get("start_node_name", "") or "") != str(getattr(node, "name", "") or ""):
                raise FlowExecutionError("AF_E009", "Branch End cannot reach matching Branch Start", end_node.name)
            plan["start_index"] = int(index)
            branch_plans[index] = plan
            total_steps += int(plan["step_count"])
        return branch_plans, total_steps

    def _compile_task_plan_branch_metadata(self, step_entries, owner_node_name):
        return self._compile_branch_metadata(step_entries, owner_node_name, entry_cost_fn=self._task_plan_step_cost)


__all__ = ["RuntimeFlowStructureMixin"]
