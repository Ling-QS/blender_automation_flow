import copy
import os
import tempfile
import time
import uuid

import bpy

from ...runtime_core.constants import (
    FLOW_OK,
    FLOW_WAIT,
    FLOW_YIELD,
    FlowExecutionError,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_PLAN_KIND,
    _enrich_flow_error_context,
)
from ...runtime_flow.helpers import (
    _find_single_from_input_socket,
    _is_run_task_plan_socket,
    _make_issue as _make_issue_impl,
    _task_plan_socket_title,
)
from ...runtime_persistence.serialization import _copy_task_plan_payload
from ...runtime_task_ref.helpers import _require_payload_object_ref as _require_payload_object_ref_impl
from ...runtime_task_ref.refs import _invalid_task_ref_issue
from ...runtime_task_target import (
    _apply_geometry_bake_entry_settings,
    _apply_geometry_bake_runtime_disk_directory,
    _capture_geometry_bake_entry_settings,
    _ensure_background_geometry_task_supported,
    _find_geometry_bake_entry_for_task,
    _geometry_bake_default_disk_cache_root_dir_relpath,
    _resolve_geometry_task_effective_bake_target,
    _restore_geometry_bake_entry_settings,
)


class RuntimeTaskPlanMixin:
    def _validate_background_task_ref_support(self, task_ref, step_node_name):
        task_kind = str(task_ref.get("task_kind", TASK_KIND_GEOMETRY) or TASK_KIND_GEOMETRY)
        if task_kind in {TASK_KIND_PHYSICS, TASK_KIND_PHYSICS_BAKE_ALL}:
            raise FlowExecutionError(
                "AF_E020",
                "Background Task Plan does not currently support Physics Bake tasks",
                step_node_name,
            )
        if task_kind == TASK_KIND_GEOMETRY:
            self._validate_background_geometry_task_support(task_ref, step_node_name)

    def _ensure_background_task_plan_supported(self, launcher_node, task_plan):
        for step_ref in task_plan.get("step_refs", []):
            step_node = self._resolve_step_ref(step_ref, launcher_node.name)
            if str(getattr(step_node, "bl_idname", "") or "") != "AFNodeTaskStep":
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(step_ref.get("group_path", []))
            try:
                task_ref = self._get_linked_output(step_node, "Task Ref", "task_ref")
                if task_ref is None:
                    raise FlowExecutionError("AF_E011", "Task Ref not found", step_node.name)
                invalid_issue = _invalid_task_ref_issue(task_ref)
                if invalid_issue is not None:
                    raise FlowExecutionError(
                        str(invalid_issue.get("code", "AF_E011") or "AF_E011"),
                        str(invalid_issue.get("message", "Task Ref is invalid") or "Task Ref is invalid"),
                        str(invalid_issue.get("node_name", "") or step_node.name),
                    )
                self._validate_background_task_ref_support(task_ref, step_node.name)
            finally:
                self.current_group_path = previous_group_path

    def _resolve_geometry_task_source_node(self, task_ref):
        if not isinstance(task_ref, dict):
            return None
        tree_name = str(task_ref.get("source_tree_name", "") or "").strip()
        node_name = str(task_ref.get("source_node", "") or "").strip()
        if not tree_name or not node_name:
            return None
        node_tree = bpy.data.node_groups.get(tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            return None
        node = node_tree.nodes.get(node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeBakeTask":
            return None
        return node

    def _restore_background_task_plan_geometry_bake_settings(self, restore_records):
        for record in reversed(list(restore_records or [])):
            if not isinstance(record, dict):
                continue
            kind = str(record.get("kind", "") or "")
            if kind == "bake_entry_state":
                bake_entry = record.get("bake_entry")
                state = record.get("state")
                if bake_entry is None or not isinstance(state, dict):
                    continue
                try:
                    _restore_geometry_bake_entry_settings(bake_entry, state)
                except Exception:
                    continue

    def _resolve_background_task_plan_geometry_bake_entry_directory(self, task_ref, step_node_name):
        object_ref = self._require_payload_object_ref(
            task_ref,
            str(task_ref.get("source_node", "") or step_node_name or "geometry bake"),
        )
        modifier = object_ref.modifiers.get(task_ref["modifier_name"])
        if modifier is None:
            raise FlowExecutionError(
                "AF_E017",
                f"Modifier '{task_ref['modifier_name']}' missing while resolving background geometry bake entry directory",
                step_node_name,
            )
        directory = str(task_ref.get("directory", "") or "").strip()
        if bool(task_ref.get("use_custom_path", False)) and directory:
            return directory
        return _geometry_bake_default_disk_cache_root_dir_relpath(task_ref, modifier, bpy_module=bpy)

    def _persist_background_task_plan_geometry_bake_entry_bindings(self, launcher_node, task_plan):
        persisted_count = 0
        for step_ref in list(task_plan.get("step_refs", []) or []):
            try:
                step_node = self._resolve_step_ref(step_ref, launcher_node.name)
            except FlowExecutionError:
                continue
            if str(getattr(step_node, "bl_idname", "") or "") != "AFNodeTaskStep":
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(step_ref.get("group_path", []))
            try:
                task_ref = self._get_linked_output(step_node, "Task Ref", "task_ref")
                if task_ref is None:
                    continue
                task_ref = self._rehydrate_task_ref_payload(task_ref, scene=self.scene)
                task_ref = self._raise_invalid_task_ref_issue(task_ref, step_node.name)
                task_ref = self._validate_task_ref_targets(task_ref, step_node.name)
                if str(task_ref.get("task_kind", "") or "") != TASK_KIND_GEOMETRY:
                    continue
                effective_target = self._resolve_task_plan_geometry_bake_target(task_ref)
                if effective_target != "DISK":
                    continue
                persisted_directory = self._resolve_background_task_plan_geometry_bake_entry_directory(task_ref, step_node.name)
                if not persisted_directory:
                    continue
                try:
                    bake_entry = self._find_geometry_bake_entry_for_task(
                        task_ref,
                        "persisting background geometry bake entry bindings",
                    )
                except FlowExecutionError:
                    bake_entry = None
                if bake_entry is not None:
                    try:
                        bake_entry.bake_target = "DISK"
                        if hasattr(bake_entry, "use_custom_path"):
                            bake_entry.use_custom_path = True
                        if hasattr(bake_entry, "directory"):
                            bake_entry.directory = persisted_directory
                    except Exception:
                        pass
                persisted_count += 1
            finally:
                self.current_group_path = previous_group_path
        return persisted_count

    def _record_background_task_plan_geometry_bake_last_states(self, launcher_node, task_plan):
        recorded_count = 0
        deferred_refresh_count = 0
        for step_ref in list(task_plan.get("step_refs", []) or []):
            try:
                step_node = self._resolve_step_ref(step_ref, launcher_node.name)
            except FlowExecutionError:
                continue
            if str(getattr(step_node, "bl_idname", "") or "") != "AFNodeTaskStep":
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(step_ref.get("group_path", []))
            try:
                task_ref = self._get_linked_output(step_node, "Task Ref", "task_ref")
                if task_ref is None:
                    continue
                task_ref = self._rehydrate_task_ref_payload(task_ref, scene=self.scene)
                task_ref = self._raise_invalid_task_ref_issue(task_ref, step_node.name)
                task_ref = self._validate_task_ref_targets(task_ref, step_node.name)
                if str(task_ref.get("task_kind", "") or "") != TASK_KIND_GEOMETRY:
                    continue
                frame_range = self._refresh_geometry_bake_cache_state_after_completion(task_ref, self.scene)
                self._write_geometry_bake_last_bake_state(task_ref, frame_range=frame_range)
                self._clear_geometry_bake_tracked_packed_cache_state(task_ref)
                should_schedule_refresh = False
                try:
                    bake_entry = self._find_geometry_bake_entry_for_task(
                        task_ref,
                        "recording background geometry bake last state",
                    )
                    has_immediate_cache = bool(
                        self._geometry_bake_entry_has_cached_data(bake_entry)
                        or self._geometry_bake_disk_cache_exists(task_ref, bake_entry=bake_entry)
                    )
                    should_schedule_refresh = not has_immediate_cache
                except Exception:
                    should_schedule_refresh = True
                if should_schedule_refresh:
                    self._schedule_geometry_bake_cache_refresh(task_ref, self.scene)
                    deferred_refresh_count += 1
                recorded_count += 1
            finally:
                self.current_group_path = previous_group_path
        return {
            "recorded": int(recorded_count),
            "deferred_refresh_scheduled": int(deferred_refresh_count),
        }

    def _register_background_task_plan_physics_cache_bindings(self, launcher_node, task_plan):
        registered = 0
        attempted = 0
        backed_up_cache_files = 0
        restored_cache_files = 0
        cache_files_changed_during_registration = False
        mainfile_reload_required = False
        mainfile_reload_reason = ""
        reasons = []
        errors = []
        for step_ref in list(task_plan.get("step_refs", []) or []):
            try:
                step_node = self._resolve_step_ref(step_ref, launcher_node.name)
            except FlowExecutionError:
                continue
            if str(getattr(step_node, "bl_idname", "") or "") != "AFNodeTaskStep":
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(step_ref.get("group_path", []))
            try:
                task_ref = self._get_linked_output(step_node, "Task Ref", "task_ref")
                if task_ref is None:
                    continue
                task_ref = self._rehydrate_task_ref_payload(task_ref, scene=self.scene)
                task_ref = self._raise_invalid_task_ref_issue(task_ref, step_node.name)
                task_ref = self._validate_task_ref_targets(task_ref, step_node.name)
                task_kind = str(task_ref.get("task_kind", "") or "")
                if task_kind == TASK_KIND_PHYSICS_BAKE_ALL:
                    report = self._register_returned_physics_bake_all_disk_cache(
                        task_ref,
                        scene=self.scene,
                        ui_context=self.ui_context,
                    )
                elif task_kind == TASK_KIND_PHYSICS:
                    report = self._register_returned_physics_disk_cache(
                        task_ref,
                        scene=self.scene,
                        ui_context=self.ui_context,
                    )
                else:
                    continue
                registered += int(report.get("registered", 0) or 0)
                attempted += int(report.get("attempted", 0) or 0)
                backed_up_cache_files += int(report.get("backed_up_cache_files", 0) or 0)
                restored_cache_files += int(report.get("restored_cache_files", 0) or 0)
                if bool(report.get("cache_files_changed_during_registration", False)):
                    cache_files_changed_during_registration = True
                if bool(report.get("mainfile_reload_required", False)):
                    mainfile_reload_required = True
                    if not mainfile_reload_reason:
                        mainfile_reload_reason = str(
                            report.get("mainfile_reload_reason", "") or "physics_disk_cache_runtime_metadata"
                        )
                reason = str(report.get("reason", "") or "").strip()
                if reason and reason not in reasons:
                    reasons.append(reason)
                error = str(report.get("error", "") or "").strip()
                if error and error not in errors:
                    errors.append(error)
            finally:
                self.current_group_path = previous_group_path
        merged_report = {
            "registered": int(registered),
            "attempted": int(attempted),
            "backed_up_cache_files": int(backed_up_cache_files),
            "restored_cache_files": int(restored_cache_files),
            "cache_files_changed_during_registration": bool(cache_files_changed_during_registration),
            "mainfile_reload_required": bool(mainfile_reload_required),
        }
        if mainfile_reload_reason:
            merged_report["mainfile_reload_reason"] = str(mainfile_reload_reason)
        if reasons:
            merged_report["reason"] = "; ".join(reasons)
        if errors:
            merged_report["error"] = "; ".join(errors)
        return merged_report

    def _make_issue(self, code, message, node_name, level="ERROR"):
        return _make_issue_impl(code, message, node_name, level=level)

    def _require_payload_object_ref(self, payload, node_name, object_name_key="object_name"):
        return _require_payload_object_ref_impl(
            payload,
            node_name,
            object_name_key=object_name_key,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _find_geometry_bake_entry_for_task(self, task_ref, error_context):
        return _find_geometry_bake_entry_for_task(
            task_ref,
            error_context,
            flow_execution_error_cls=FlowExecutionError,
            require_payload_object_ref=self._require_payload_object_ref,
        )

    def _ensure_background_geometry_task_supported(self, task_ref, node_name):
        return _ensure_background_geometry_task_supported(
            task_ref,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
            resolve_geometry_task_effective_bake_target=self._resolve_task_plan_geometry_bake_target,
        )

    def _resolve_task_plan_geometry_bake_target(self, task_ref):
        return _resolve_geometry_task_effective_bake_target(
            task_ref,
            find_geometry_bake_entry_for_task=self._find_geometry_bake_entry_for_task,
        )

    def _validate_background_geometry_task_support(self, task_ref, node_name):
        return self._ensure_background_geometry_task_supported(task_ref, node_name)

    def _compile_task_segment(self, sink_node, flow_input_name, start_node_types, group_path=None):
        if flow_input_name not in sink_node.inputs:
            raise FlowExecutionError("AF_E009", f"Task segment sink is missing '{flow_input_name}'", sink_node.name)

        reverse_step_refs = []
        visited = {self._node_identity(sink_node)}
        current, _current_socket = _find_single_from_input_socket(sink_node.inputs[flow_input_name])

        while current is not None:
            current_key = self._node_identity(current)
            if current_key in visited:
                raise FlowExecutionError("AF_E009", "Task plan flow has a loop", current.name)
            visited.add(current_key)

            if current.bl_idname in start_node_types:
                break

            if getattr(current, "mute", False):
                if "Flow In" not in current.inputs:
                    raise FlowExecutionError("AF_E009", "Muted task plan step is missing Flow In", current.name)
                current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])
                continue

            if current.bl_idname == "AFNodeGroup":
                nested_steps = self._compile_group_task_step_refs(current, group_path)
                reverse_step_refs.extend(reversed(nested_steps))
                if "Flow In" not in current.inputs:
                    raise FlowExecutionError("AF_E009", "Grouped task step is missing Flow In", current.name)
                current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])
                continue

            if current.bl_idname not in self.TASK_PLAN_STEP_TYPES:
                raise FlowExecutionError("AF_E009", f"Unsupported task plan node type '{current.bl_idname}'", current.name)

            reverse_step_refs.append(self._make_step_ref(current, group_path))
            if "Flow In" not in current.inputs:
                raise FlowExecutionError("AF_E009", "Task plan step is missing Flow In", current.name)
            current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])

        if current is None or current.bl_idname not in start_node_types:
            expected = " / ".join(sorted(start_node_types))
            raise FlowExecutionError("AF_E009", f"Task segment cannot reach expected start node ({expected})", sink_node.name)

        reverse_step_refs.reverse()
        return reverse_step_refs

    def _compile_group_task_step_refs(self, group_node, parent_group_path=None):
        group_tree = getattr(group_node, "group_tree", None)
        if group_tree is None or getattr(group_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E009", "Group tree is missing", group_node.name)
        group_path = list(parent_group_path or [])
        group_path.append(self._make_step_ref(group_node))

        flow_group_outputs = self._find_group_flow_socket_nodes(group_tree, "NodeGroupOutput", "inputs")
        linked_flow_group_outputs = [
            (node, socket)
            for node, socket in flow_group_outputs
            if bool(getattr(socket, "links", None))
        ]
        if linked_flow_group_outputs:
            flow_group_outputs = linked_flow_group_outputs
        flow_group_inputs = self._find_group_flow_socket_nodes(group_tree, "NodeGroupInput", "outputs")
        linked_flow_group_inputs = [
            (node, socket)
            for node, socket in flow_group_inputs
            if bool(getattr(socket, "links", None))
        ]
        if linked_flow_group_inputs:
            flow_group_inputs = linked_flow_group_inputs
        if len(flow_group_outputs) == 1 and len(flow_group_inputs) == 1:
            group_output, flow_socket = flow_group_outputs[0]
            try:
                return self._compile_task_segment(group_output, flow_socket.name, {"NodeGroupInput"}, group_path)
            except FlowExecutionError as exc:
                _enrich_flow_error_context(
                    exc,
                    group_output,
                    getattr(getattr(group_output, "id_data", None), "name", self.node_tree.name),
                    group_path,
                )
                pass

        task_outputs = self._find_task_group_nodes(group_tree, "AFNodeTaskOutput")
        task_starts = self._find_task_group_nodes(group_tree, "AFNodeTaskStart")
        if task_outputs or task_starts:
            if len(task_outputs) != 1 or len(task_starts) != 1:
                raise FlowExecutionError("AF_E009", "Reusable task groups must contain exactly one Task Start and one Task Output", group_node.name)
            task_plan = self._compile_task_plan(task_outputs[0], group_path)
            return list(task_plan.get("step_refs", []))

        raise FlowExecutionError("AF_E009", "Grouped task steps require a valid Flow path or reusable task path", group_node.name)

    def _compile_group_task_plan(self, group_node):
        group_tree = getattr(group_node, "group_tree", None)
        if group_tree is None or getattr(group_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E009", "Group tree is missing", group_node.name)
        task_outputs = self._find_task_group_nodes(group_tree, "AFNodeTaskOutput")
        task_starts = self._find_task_group_nodes(group_tree, "AFNodeTaskStart")
        if len(task_outputs) != 1 or len(task_starts) != 1:
            raise FlowExecutionError("AF_E009", "Task Plan group must contain exactly one Task Start and one Task Output", group_node.name)
        return self._compile_task_plan(task_outputs[0], [self._make_step_ref(group_node)])

    def _compile_task_plan(self, output_node, group_path=None):
        if getattr(output_node, "bl_idname", "") != "AFNodeTaskOutput":
            raise FlowExecutionError("AF_E009", "Task Plan must be compiled from a Task Output node", output_node.name)

        try:
            step_refs = self._compile_task_segment(output_node, "Flow In", {"AFNodeTaskStart"}, group_path)
        except FlowExecutionError as exc:
            raise _enrich_flow_error_context(
                exc,
                output_node,
                getattr(getattr(output_node, "id_data", None), "name", self.node_tree.name),
                group_path,
            )
        step_entries = []
        for step_ref in step_refs:
            step_entries.append(
                {
                    "node": self._resolve_step_ref(step_ref, output_node.name),
                    "group_path": list(step_ref.get("group_path", [])),
                }
            )
        try:
            repeat_pairs, step_count = self._compile_repeat_metadata(step_entries, output_node.name, self._task_plan_step_cost)
        except FlowExecutionError as exc:
            raise _enrich_flow_error_context(
                exc,
                output_node,
                getattr(getattr(output_node, "id_data", None), "name", self.node_tree.name),
                group_path,
            )
        try:
            subflow_plans, subflow_step_count = self._compile_subflow_metadata(
                step_entries,
                output_node.name,
                entry_cost_fn=self._task_plan_step_cost,
            )
        except FlowExecutionError as exc:
            raise _enrich_flow_error_context(
                exc,
                output_node,
                getattr(getattr(output_node, "id_data", None), "name", self.node_tree.name),
                group_path,
            )
        try:
            branch_plans, branch_step_count = self._compile_task_plan_branch_metadata(step_entries, output_node.name)
        except FlowExecutionError as exc:
            raise _enrich_flow_error_context(
                exc,
                output_node,
                getattr(getattr(output_node, "id_data", None), "name", self.node_tree.name),
                group_path,
            )
        return {
            "plan_kind": TASK_PLAN_KIND,
            "plan_uid": str(uuid.uuid4()),
            "output_node": output_node.name,
            "output_tree_name": getattr(getattr(output_node, "id_data", None), "name", self.node_tree.name),
            "output_ref": self._make_step_ref(output_node, group_path),
            "step_refs": list(step_refs),
            "step_names": [str(step_ref["node_name"]) for step_ref in step_refs],
            "step_count": int(step_count) + int(subflow_step_count) + int(branch_step_count),
            "repeat_pairs": repeat_pairs,
            "subflow_plans": subflow_plans,
            "branch_plans": branch_plans,
        }

    def _flow_node_step_cost(self, node):
        if (
            self._is_repeat_start_node(node)
            or self._is_repeat_end_node(node)
            or self._is_subflow_start_node(node)
            or self._is_branch_start_node(node)
            or self._is_branch_end_node(node)
        ):
            return 0
        if getattr(node, "mute", False) and node.bl_idname not in {"AFNodeStart", "AFNodeEnd"}:
            return 0
        if node.bl_idname == "AFNodeRunTaskPlan":
            entries, linked_count, _enabled_count = self._collect_run_task_plan_entries(node)
            if linked_count == 0:
                return 0
            total_steps = 0
            for entry in entries:
                if not entry["enabled"]:
                    continue
                task_plan = entry.get("task_plan")
                if task_plan is None:
                    raise FlowExecutionError("AF_E011", f"{entry['title']} is not linked to a valid Task Plan", node.name)
                total_steps += int(entry.get("step_count", len(task_plan.get("step_names", []))))
            return total_steps
        return 1

    def _task_plan_step_cost(self, entry):
        node = self._entry_node(entry)
        if self._is_repeat_start_node(node) or self._is_repeat_end_node(node) or self._is_branch_start_node(node) or self._is_branch_end_node(node):
            return 0
        return 1

    def _iter_run_task_plan_sockets(self, node):
        return [socket for socket in getattr(node, "inputs", []) if _is_run_task_plan_socket(socket)]

    def _task_plan_override_key(self, node, socket):
        return (
            str(getattr(getattr(node, "id_data", None), "name", "") or ""),
            str(getattr(node, "name", "") or ""),
            str(getattr(socket, "identifier", "") or getattr(socket, "name", "") or ""),
        )

    def _collect_run_task_plan_entries(self, node):
        entries = []
        linked_count = 0
        enabled_count = 0
        for socket_index, socket in enumerate(self._iter_run_task_plan_sockets(node), 1):
            from_node, from_socket = _find_single_from_input_socket(socket)
            task_plan_override = None
            if from_node is None:
                task_plan_override = self._task_plan_input_overrides.get(self._task_plan_override_key(node, socket))
            if from_node is None and task_plan_override is None:
                continue
            linked_count += 1
            enabled = bool(getattr(socket, "af_enabled", True))
            title = _task_plan_socket_title(socket, socket_index)
            entry = {
                "socket": socket,
                "socket_index": socket_index,
                "title": title,
                "enabled": enabled,
                "task_plan": None,
                "step_refs": [],
                "step_count": 0,
                "repeat_pairs": {},
                "subflow_plans": {},
                "branch_plans": {},
                "cursor": 0,
                "completed_step_count": 0,
                "status": "PENDING",
                "step_started": False,
                "repeat_states": {},
                "runtime_status_override": "",
                "from_node": from_node,
                "from_socket": from_socket,
                "enabled_index": 0,
            }
            if enabled:
                enabled_count += 1
                entry["enabled_index"] = enabled_count
                if task_plan_override is not None:
                    task_plan = copy.deepcopy(task_plan_override)
                else:
                    task_plan = self._get_output_from_source(from_node, from_socket, "task_plan")
                entry["task_plan"] = task_plan
                if isinstance(task_plan, dict):
                    step_refs = task_plan.get("step_refs")
                    if not step_refs:
                        step_refs = [{"tree_name": self.node_tree.name, "node_name": step_name} for step_name in task_plan.get("step_names", [])]
                    entry["step_refs"] = self._normalize_step_refs(step_refs)
                    entry["step_count"] = int(task_plan.get("step_count", len(step_refs)))
                    entry["repeat_pairs"] = self._normalize_repeat_pairs(task_plan.get("repeat_pairs", {}))
                    entry["subflow_plans"] = self._normalize_indexed_local_plans(task_plan.get("subflow_plans", {}))
                    entry["branch_plans"] = self._normalize_indexed_local_plans(task_plan.get("branch_plans", {}))
            entries.append(entry)

        for entry in entries:
            entry["enabled_total"] = enabled_count
        return entries, linked_count, enabled_count

    def _task_plan_entry_label(self, entry):
        if int(entry.get("enabled_index", 0)) > 0 and int(entry.get("enabled_total", 0)) > 0:
            return f"Plan {entry['enabled_index']}/{entry['enabled_total']} - {entry['title']}"
        return str(entry.get("title", "Task Plan"))

    def _normalize_task_plan_final_status(self, status_value):
        status_text = str(status_value or "").strip().upper()
        return status_text

    def _active_task_plan_entry(self):
        state = self.current_task_plan
        if not isinstance(state, dict):
            return None
        entries = list(state.get("entries", []) or [])
        if not entries:
            return None
        try:
            active_index = int(state.get("active_entry_index", state.get("cursor", 0)) or 0)
        except Exception:
            active_index = 0
        if active_index < 0 or active_index >= len(entries):
            return None
        entry = entries[active_index]
        return entry if isinstance(entry, dict) else None

    def _write_task_plan_runtime_status_override(self, status_value):
        entry = self._active_task_plan_entry()
        if not isinstance(entry, dict):
            return False
        entry["runtime_status_override"] = self._normalize_task_plan_final_status(status_value)
        return True

    def _classify_task_plan_final_status(self, status_value):
        normalized = self._normalize_task_plan_final_status(status_value)
        if normalized in {"FAILED", "ERROR", "CANCELLED"}:
            return "FAILED"
        if normalized == "SKIPPED":
            return "SKIPPED"
        return "DONE"

    def _resolve_task_plan_status_override(self, run_node, entry):
        runtime_status_override = self._normalize_task_plan_final_status(entry.get("runtime_status_override", ""))
        if runtime_status_override:
            return runtime_status_override
        task_plan = entry.get("task_plan")
        if not isinstance(task_plan, dict):
            return ""
        output_ref = dict(task_plan.get("output_ref", {}) or {})
        if not output_ref:
            return ""
        try:
            output_node = self._resolve_step_ref(output_ref, run_node.name)
        except Exception:
            return ""
        if output_node is None or str(getattr(output_node, "bl_idname", "") or "") != "AFNodeTaskOutput":
            return ""
        previous_group_path = list(self.current_group_path)
        self.current_group_path = list(output_ref.get("group_path", []))
        try:
            return str(self._input_string(output_node, "Status", "") or "").strip()
        finally:
            self.current_group_path = previous_group_path

    def _predict_task_plan_status(self, run_node, task_plan):
        if not isinstance(task_plan, dict) or str(task_plan.get("plan_kind", "")) != TASK_PLAN_KIND:
            return "INVALID", {"status": "INVALID", "reason": "invalid_task_plan"}
        predictor_runner = self.__class__(
            self.node_tree,
            self.scene,
            ui_context=dict(self.ui_context or {}),
            start_node_name=str(getattr(self, "start_node_name", "") or ""),
            auto_follow=False,
        )
        try:
            previous_run_mode = str(getattr(predictor_runner.settings, "run_mode", "NORMAL") or "NORMAL")
            predictor_runner.settings.run_mode = "FLOW_TEST"
            predictor_runner.vars.clear()
            predictor_runner.tasks.clear()
            predictor_runner.current_wait = None
            predictor_runner.current_task_plan = None
            predictor_runner.flow_repeat_states.clear()
            predictor_runner.flow_subflow_plans.clear()
            predictor_runner.flow_branch_plans.clear()
            predictor_runner.pending_branch_failure = None
            predictor_runner.current_group_path = []
            predictor_runner._geometry_attribute_cache.clear()
            predictor_runner._object_lookup_cache.clear()
            predictor_runner._property_assignment_plan_cache.clear()
            predictor_run_node = getattr(getattr(predictor_runner.node_tree, "nodes", None), "get", lambda _name: None)(str(getattr(run_node, "name", "") or ""))
            if predictor_run_node is None or str(getattr(predictor_run_node, "bl_idname", "") or "") != str(getattr(run_node, "bl_idname", "") or ""):
                return "INVALID", {"status": "INVALID", "reason": "predictor_run_node_missing"}
            task_plan_sockets = predictor_runner._iter_run_task_plan_sockets(predictor_run_node)
            if not task_plan_sockets:
                return "INVALID", {"status": "INVALID", "reason": "predictor_task_plan_socket_missing"}
            predictor_runner._task_plan_input_overrides[
                predictor_runner._task_plan_override_key(predictor_run_node, task_plan_sockets[0])
            ] = _copy_task_plan_payload(task_plan)
            result, payload = predictor_runner._execute_task_plan(predictor_run_node)
            while result == FLOW_YIELD:
                result, payload = predictor_runner._execute_task_plan(predictor_run_node)
            if result == FLOW_WAIT:
                return "INVALID", {
                    "status": "INVALID",
                    "reason": "task_plan_wait_not_supported",
                }
            status_value = str(predictor_runner._get_output(predictor_run_node, "status") or "DONE").strip().upper() or "DONE"
            report = dict(predictor_runner._get_output(predictor_run_node, "report") or {})
            report["status"] = status_value
            if status_value == "SKIPPED":
                report["skipped"] = True
            return status_value, report
        except FlowExecutionError as exc:
            return "FAILED", {
                "status": "FAILED",
                "error_code": str(exc.code or "AF_E010"),
                "error_message": str(exc.message or "Task Plan failed"),
                "node_name": str(exc.node_name or getattr(run_node, "name", "")),
            }
        except Exception as exc:
            return "FAILED", {
                "status": "FAILED",
                "error_code": "AF_E999",
                "error_message": str(exc),
                "node_name": str(getattr(run_node, "name", "")),
            }
        finally:
            try:
                predictor_runner.settings.run_mode = previous_run_mode
            except Exception:
                pass
            predictor_runner._task_plan_input_overrides.clear()

    def _clear_plan_progress(self):
        self.settings.current_plan_title = ""
        self.settings.current_plan_index = 0
        self.settings.total_plan_count = 0
        self.settings.current_plan_step_index = 0
        self.settings.current_plan_step_count = 0

    def _set_plan_progress(self, entry, step_index=0, step_count=0):
        self.settings.current_plan_title = str(entry.get("title", "") or "")
        self.settings.current_plan_index = int(entry.get("enabled_index", 0))
        self.settings.total_plan_count = int(entry.get("enabled_total", 0))
        self.settings.current_plan_step_index = int(step_index)
        self.settings.current_plan_step_count = int(step_count)

    def _task_plan_state_report(self, state):
        entries = list(state.get("entries", []) or [])
        report = {
            "plan_count": int(state.get("linked_count", 0)),
            "enabled_plan_count": int(state.get("enabled_count", 0)),
            "skipped_plan_count": int(state.get("skipped_count", 0)),
            "completed_plan_count": int(state.get("completed_count", 0)),
            "failed_plan_count": int(state.get("failed_count", 0)),
            "failure_policy": str(state.get("failure_policy", "")),
            "step_count": sum(int(entry.get("step_count", 0)) for entry in entries if entry.get("enabled")),
        }
        if int(state.get("failed_count", 0)) > 0:
            report["status"] = "FAILED"
        elif int(state.get("completed_count", 0)) == 0 and int(state.get("skipped_count", 0)) > 0:
            report["status"] = "SKIPPED"
        else:
            report["status"] = "DONE"
        return report

    def _set_task_plan_outputs(self, run_node, state):
        report = self._task_plan_state_report(state)
        previous_group_path = list(self.current_group_path)
        self.current_group_path = []
        try:
            self._set_output(run_node, "report", report)
            self._set_output(run_node, "status", str(report.get("status", "DONE") or "DONE"))
        finally:
            self.current_group_path = previous_group_path
        return report

    def _background_task_plan_step_label(self, state):
        handle = state.get("handle", {})
        step_count = max(0, int(handle.get("step_count", state.get("step_count", 0)) or 0))
        if step_count <= 0:
            return "Step 0/0"
        completed = max(0, int(state.get("completed_step_count", 0) or 0))
        status = str(handle.get("status", state.get("status", "")) or "")
        current_index = min(step_count, completed if status == "DONE" else (completed + 1))
        current_index = max(1, current_index)
        return f"Step {current_index}/{step_count}"

    def _background_task_plan_step_tree_name(self, step_node):
        return getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name)

    def _background_task_plan_launcher_node(self, state):
        if not isinstance(state, dict):
            return None
        launcher_node = state.get("launcher_node")
        if launcher_node is not None:
            return launcher_node
        launcher_ref = state.get("launcher_ref")
        node_name = str(state.get("node_name", "") or "").strip()
        if not isinstance(launcher_ref, dict):
            if not node_name:
                return None
            launcher_ref = {
                "tree_name": str(getattr(self.node_tree, "name", "") or ""),
                "node_name": node_name,
            }
            state["launcher_ref"] = copy.deepcopy(launcher_ref)
        try:
            launcher_node = self._resolve_step_ref(launcher_ref, node_name or "Background Task Plan")
        except FlowExecutionError:
            return None
        state["launcher_node"] = launcher_node
        return launcher_node

    def _push_background_task_plan_outputs(self, state):
        if not isinstance(state, dict):
            return
        handle = state.get("handle")
        launcher_node = self._background_task_plan_launcher_node(state)
        if not isinstance(handle, dict) or launcher_node is None:
            return
        report = dict(handle.get("report") or {})
        report.update(
            {
                "plan_uid": str(handle.get("plan_uid", report.get("plan_uid", "")) or ""),
                "step_count": int(handle.get("step_count", report.get("step_count", 0)) or 0),
                "completed_step_count": int(state.get("completed_step_count", report.get("completed_step_count", 0)) or 0),
                "status": str(handle.get("status", state.get("status", "")) or ""),
                "current_step_name": str(state.get("current_step_name", "") or ""),
                "current_step_tree_name": str(state.get("current_step_tree_name", "") or ""),
                "current_step_group_path": copy.deepcopy(list(state.get("current_step_group_path", []) or [])),
                "current_wait_type": str(state.get("current_wait_type", "") or ""),
                "launcher_node_name": str(state.get("node_name", "") or ""),
                "blend_copy_path": str(report.get("blend_copy_path", state.get("blend_copy_path", "")) or ""),
            }
        )
        if "log_path" not in report and state.get("wait_state") is not None:
            wait_state = state.get("wait_state") or {}
            report["log_path"] = str(wait_state.get("log_path", "") or "")
        handle["report"] = report
        previous_group_path = list(self.current_group_path)
        self.current_group_path = []
        try:
            self._set_output(launcher_node, "task_handle", copy.deepcopy(handle))
            self._set_output(launcher_node, "status", str(handle.get("status", "")))
            self._set_output(launcher_node, "report", copy.deepcopy(report))
        finally:
            self.current_group_path = previous_group_path

    def _log_background_task_step_started(self, state, step_node):
        self.log(
            "INFO",
            f"BACKGROUND_TASK_STEP_STARTED [{state['node_name']}] {self._background_task_plan_step_label(state)}",
            step_node.name,
            self._background_task_plan_step_tree_name(step_node),
        )

    def _log_background_task_step_waiting(self, state, step_node):
        wait_state = state.get("wait_state") or {}
        wait_type = str(wait_state.get("wait_type", "") or "")
        message = f"BACKGROUND_TASK_STEP_WAITING [{state['node_name']}] {self._background_task_plan_step_label(state)}"
        if wait_type:
            message += f" ({wait_type})"
        self.log("INFO", message, step_node.name, self._background_task_plan_step_tree_name(step_node))

    def _log_background_task_step_done(self, state, step_node, payload=None):
        message = f"BACKGROUND_TASK_STEP_DONE [{state['node_name']}] {self._background_task_plan_step_label(state)}"
        if payload is not None:
            message += f" ({payload})"
        self.log("INFO", message, step_node.name, self._background_task_plan_step_tree_name(step_node))

    def _apply_background_task_plan_status_payload(self, state, status_payload):
        if not isinstance(state, dict) or not isinstance(status_payload, dict):
            return
        handle = state.get("handle") or {}
        report = dict(handle.get("report") or {})
        report.update(dict(status_payload.get("report", {}) or {}))
        payload_state = str(status_payload.get("state", "") or "")
        if payload_state:
            state["status"] = payload_state
            handle["status"] = "WAITING" if payload_state == "WAITING" else ("DONE" if payload_state == "DONE" else ("FAILED" if payload_state == "FAILED" else "RUNNING"))
        state["completed_step_count"] = int(status_payload.get("completed_step_count", state.get("completed_step_count", 0)) or 0)
        state["current_step_name"] = str(status_payload.get("current_step_name", state.get("current_step_name", "")) or "")
        state["current_step_tree_name"] = str(status_payload.get("current_step_tree_name", state.get("current_step_tree_name", "")) or "")
        state["current_step_group_path"] = copy.deepcopy(list(status_payload.get("current_step_group_path", state.get("current_step_group_path", [])) or []))
        state["current_wait_type"] = str(status_payload.get("current_wait_type", state.get("current_wait_type", "")) or "")
        handle["report"] = report

        events = status_payload.get("events", [])
        if not isinstance(events, list):
            return
        event_cursor = int(state.get("event_cursor", 0) or 0)
        new_events = events[event_cursor:]
        for event in new_events:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type", "") or "")
            step_ref = event.get("step_ref", {})
            if not isinstance(step_ref, dict):
                continue
            try:
                step_node = self._resolve_step_ref(step_ref, state.get("node_name", "Background Task Plan"))
            except Exception:
                continue
            if event_type == "STEP_STARTED":
                self._log_background_task_step_started(state, step_node)
            elif event_type == "STEP_WAITING":
                state["current_wait_type"] = str(event.get("wait_type", state.get("current_wait_type", "")) or "")
                self._log_background_task_step_waiting(state, step_node)
            elif event_type == "STEP_DONE":
                self._log_background_task_step_done(state, step_node, event.get("payload"))
        state["event_cursor"] = len(events)

    def _validate_background_task_plan(self, launcher_node, task_plan):
        issues = []
        for step_ref in task_plan.get("step_refs", []):
            try:
                step_node = self._resolve_step_ref(step_ref, launcher_node.name)
            except FlowExecutionError as exc:
                issues.append(self._make_issue(exc.code, exc.message, launcher_node.name))
                continue
            if str(getattr(step_node, "bl_idname", "") or "") != "AFNodeTaskStep":
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(step_ref.get("group_path", []))
            try:
                task_ref = self._get_linked_output(step_node, "Task Ref", "task_ref")
                if task_ref is None:
                    issues.append(self._make_issue("AF_E011", "Task Ref not found", step_node.name))
                    continue
                invalid_issue = _invalid_task_ref_issue(task_ref)
                if invalid_issue is not None:
                    issues.append(
                        self._make_issue(
                            str(invalid_issue.get("code", "AF_E011") or "AF_E011"),
                            str(invalid_issue.get("message", "Task Ref is invalid") or "Task Ref is invalid"),
                            str(invalid_issue.get("node_name", "") or step_node.name),
                        )
                    )
                    continue
                try:
                    self._validate_background_task_ref_support(task_ref, step_node.name)
                except FlowExecutionError as exc:
                    issues.append(self._make_issue(exc.code, exc.message, step_node.name))
            finally:
                self.current_group_path = previous_group_path
        return issues

    def _import_background_task_plan_property_package_bake_results(self, state, status_payload):
        if not isinstance(state, dict) or not isinstance(status_payload, dict):
            return []
        handle = state.get("handle") or {}
        plan_report = dict(handle.get("report") or {})
        payload_report = dict(status_payload.get("report", {}) or {})
        property_package_bake_reports = list(payload_report.get("property_package_bake_reports", []) or [])
        if not property_package_bake_reports:
            return []

        blend_copy_path = str(state.get("blend_copy_path", "") or "")
        imported_reports = []
        for item in property_package_bake_reports:
            if not isinstance(item, dict):
                continue
            imported_report = self._import_background_property_package_bake_result(
                handle,
                {"report": dict(item), "success": True, "skipped": bool(item.get("skipped", False))},
                blend_copy_path,
            )
            imported_reports.append(imported_report)
        if imported_reports:
            plan_report["property_package_bake_reports"] = copy.deepcopy(imported_reports)
            plan_report["imported_property_package_bake_count"] = len(imported_reports)
            plan_report["imported_result"] = True
            handle["report"] = plan_report
        return imported_reports

    def _capture_background_task_plan_tree_users(self, launcher_node, task_plan):
        tree_names = set()
        launcher_tree = getattr(launcher_node, "id_data", None)
        if launcher_tree is not None and getattr(launcher_tree, "bl_idname", "") == "AFNodeTreeType":
            tree_names.add(str(getattr(launcher_tree, "name", "") or ""))
        for step_ref in task_plan.get("step_refs", []):
            if not isinstance(step_ref, dict):
                continue
            tree_name = str(step_ref.get("tree_name", "") or "")
            if tree_name:
                tree_names.add(tree_name)
            for group_item in step_ref.get("group_path", []):
                if not isinstance(group_item, dict):
                    continue
                group_tree_name = str(group_item.get("tree_name", "") or "")
                if group_tree_name:
                    tree_names.add(group_tree_name)
        records = []
        for tree_name in tree_names:
            node_tree = bpy.data.node_groups.get(tree_name)
            if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
                continue
            records.append((node_tree, bool(getattr(node_tree, "use_fake_user", False))))
            node_tree.use_fake_user = True
        return records

    def _restore_background_task_plan_tree_users(self, records):
        for node_tree, original_use_fake_user in records:
            try:
                node_tree.use_fake_user = bool(original_use_fake_user)
            except Exception:
                pass

    def _prepare_background_task_plan_geometry_bake_settings(self, launcher_node, task_plan):
        applied_count = 0
        prepared_disk_directory_count = 0
        restore_records = []
        for step_ref in list(task_plan.get("step_refs", []) or []):
            try:
                step_node = self._resolve_step_ref(step_ref, launcher_node.name)
            except FlowExecutionError:
                continue
            if str(getattr(step_node, "bl_idname", "") or "") != "AFNodeTaskStep":
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(step_ref.get("group_path", []))
            try:
                task_ref = self._get_linked_output(step_node, "Task Ref", "task_ref")
                if task_ref is None:
                    continue
                task_ref = self._rehydrate_task_ref_payload(task_ref, scene=self.scene)
                task_ref = self._raise_invalid_task_ref_issue(task_ref, step_node.name)
                task_ref = self._validate_task_ref_targets(task_ref, step_node.name)
                if str(task_ref.get("task_kind", "") or "") != TASK_KIND_GEOMETRY:
                    continue
                bake_entry = self._find_geometry_bake_entry_for_task(task_ref, "preparing background geometry bake settings")
                restore_records.append(
                    {
                        "kind": "bake_entry_state",
                        "bake_entry": bake_entry,
                        "state": _capture_geometry_bake_entry_settings(bake_entry),
                    }
                )
                if bool(task_ref.get("apply_settings_on_run", False)):
                    _apply_geometry_bake_entry_settings(bake_entry, task_ref)
                    applied_count += 1
                if _apply_geometry_bake_runtime_disk_directory(
                    bake_entry,
                    task_ref,
                    resolve_default_directory=lambda current_task_ref: self._resolve_background_task_plan_geometry_bake_entry_directory(
                        current_task_ref,
                        step_node.name,
                    ),
                ):
                    prepared_disk_directory_count += 1
            finally:
                self.current_group_path = previous_group_path
        return applied_count, prepared_disk_directory_count, restore_records

    def _start_background_task_plan(self, node, task_plan):
        self._ensure_background_task_plan_supported(node, task_plan)
        predicted_status, predicted_report = self._predict_task_plan_status(node, task_plan)
        predicted_status = self._normalize_task_plan_final_status(predicted_status)
        if predicted_status == "SKIPPED":
            handle = self._create_skipped_background_plan_handle(
                node,
                str(dict(predicted_report or {}).get("reason", "") or "Task Plan precheck resolved to SKIPPED"),
            )
            merged_report = dict(handle.get("report") or {})
            merged_report.update(dict(predicted_report or {}))
            merged_report["status"] = "SKIPPED"
            merged_report["skipped"] = True
            merged_report["external_process"] = False
            merged_report["prechecked"] = True
            handle["report"] = merged_report
            handle["status"] = "SKIPPED"
            handle["skipped"] = True
            return handle
        if predicted_status == "FAILED":
            raise FlowExecutionError(
                str(dict(predicted_report or {}).get("error_code", "AF_E010") or "AF_E010"),
                str(dict(predicted_report or {}).get("error_message", "Task Plan precheck failed") or "Task Plan precheck failed"),
                str(dict(predicted_report or {}).get("node_name", node.name) or node.name),
            )
        if predicted_status == "INVALID":
            raise FlowExecutionError(
                "AF_E011",
                str(dict(predicted_report or {}).get("reason", "Task Plan precheck resolved to INVALID") or "Task Plan precheck resolved to INVALID"),
                node.name,
            )
        handle = self._create_background_plan_handle(node, task_plan)
        if self._is_task_simulation_mode():
            self._mark_task_handle_simulated(
                handle,
                extra_report={
                    "plan_uid": str(task_plan.get("plan_uid", "")),
                    "step_count": int(task_plan.get("step_count", 0)),
                    "completed_step_count": int(task_plan.get("step_count", 0)),
                    "status": "DONE",
                    "external_process": False,
                    "blend_copy_path": "",
                    "prechecked": True,
                },
            )
            if self._is_flow_test_mode():
                self.log("INFO", f"FLOW_TEST_BACKGROUND_TASK_PLAN [{node.name}] simulated", node.name)
            else:
                self.log("INFO", f"DRY_RUN_BACKGROUND_TASK_PLAN [{node.name}] simulated", node.name)
            return handle
        prepared_geometry_bake_settings, prepared_geometry_bake_directories, geometry_bake_restore_records = self._prepare_background_task_plan_geometry_bake_settings(node, task_plan)
        if prepared_geometry_bake_settings > 0:
            self.log(
                "INFO",
                f"BACKGROUND_TASK_PLAN_PREPARED_GN_BAKE_SETTINGS [{node.name}] {prepared_geometry_bake_settings} target(s)",
                node.name,
            )
        if prepared_geometry_bake_directories > 0:
            self.log(
                "INFO",
                f"BACKGROUND_TASK_PLAN_PREPARED_GN_BAKE_DIRS [{node.name}] {prepared_geometry_bake_directories} target(s)",
                node.name,
            )
        temp_dir = tempfile.mkdtemp(prefix="af_bg_task_")
        blend_copy_path = ""
        tree_user_records = self._capture_background_task_plan_tree_users(node, task_plan)
        try:
            if not self._is_dry_run_mode():
                blend_copy_path = self._save_temporary_background_blend_copy(node, temp_dir)
        finally:
            self._restore_background_task_plan_geometry_bake_settings(geometry_bake_restore_records)
            self._restore_background_task_plan_tree_users(tree_user_records)
        start_result = self._start_external_background_task_plan_process(node, task_plan, handle, blend_copy_path, temp_dir)
        state = {
            "handle": handle,
            "launcher_node": node,
            "node_name": node.name,
            "task_plan": _copy_task_plan_payload(task_plan),
            "completed_step_count": 0,
            "wait_state": start_result.get("wait_state"),
            "status": str(handle.get("status", "RUNNING")),
            "failure": None,
            "temp_dir": temp_dir,
            "blend_copy_path": blend_copy_path,
            "current_step_name": "",
            "current_step_tree_name": "",
            "current_step_group_path": [],
            "current_wait_type": "",
            "event_cursor": 0,
            "prepared_geometry_bake_settings": int(prepared_geometry_bake_settings),
            "prepared_geometry_bake_directories": int(prepared_geometry_bake_directories),
        }
        self.background_task_plans[handle["task_id"]] = state
        self._push_background_task_plan_outputs(state)
        self.log("INFO", f"BACKGROUND_TASK_PLAN_STARTED [{node.name}] {int(task_plan.get('step_count', 0))} step(s)", node.name)
        return handle

    def _tick_background_task_plan(self, state):
        handle = state["handle"]
        task_id = str(handle["task_id"])
        wait_state = state.get("wait_state")
        if wait_state is None:
            if str(handle.get("status", "")) == "DONE":
                self.background_task_plans.pop(task_id, None)
                return
            raise FlowExecutionError("AF_E005", "Background task plan lost its external process state", state["node_name"])

        poll_result = self._poll_external_process_wait_state(wait_state)
        if poll_result is None:
            return

        status_payload = poll_result.get("status_payload")
        if isinstance(status_payload, dict) and status_payload:
            self._apply_background_task_plan_status_payload(state, status_payload)

        if not poll_result["finished"]:
            self._push_background_task_plan_outputs(state)
            return

        state["wait_state"] = None
        if bool(poll_result.get("failed", False)):
            report = dict(handle.get("report") or {})
            raise FlowExecutionError(
                str(report.get("error_code", "AF_E005")),
                str(report.get("error_message", "Background task plan failed")),
                str(report.get("node_name", state["node_name"])) or state["node_name"],
            )

        try:
            imported_reports = self._import_background_task_plan_property_package_bake_results(state, status_payload or {})
        except FlowExecutionError as exc:
            handle["status"] = "FAILED"
            handle["finished_at"] = time.monotonic()
            handle["report"] = {
                "error_code": exc.code,
                "error_message": exc.message,
                "node_name": exc.node_name,
                "blend_copy_path": str(state.get("blend_copy_path", "") or ""),
            }
            state["status"] = "FAILED"
            state["failure"] = exc
            state["current_step_group_path"] = []
            state["current_wait_type"] = ""
            self._push_background_task_plan_outputs(state)
            self._cleanup_background_task_plan_blend_copy(state, keep_artifacts=True)
            self.background_task_plans.pop(task_id, None)
            self.log("ERROR", f"BACKGROUND_TASK_PLAN_FAILED [{state['node_name']}] {exc.code}: {exc.message}", exc.node_name or state["node_name"])
            return

        handle["status"] = "DONE"
        handle["finished_at"] = time.monotonic()
        state["status"] = "DONE"
        state["current_step_name"] = ""
        state["current_step_tree_name"] = ""
        state["current_step_group_path"] = []
        state["current_wait_type"] = ""
        if imported_reports:
            state["imported_property_package_bake_count"] = len(imported_reports)
        launcher_node = self._background_task_plan_launcher_node(state)
        task_plan = state.get("task_plan")
        post_import_skip_reasons = []
        if launcher_node is None:
            post_import_skip_reasons.append("launcher_node_missing")
        if not isinstance(task_plan, dict) or str(task_plan.get("plan_kind", "")) != TASK_PLAN_KIND:
            post_import_skip_reasons.append("task_plan_missing")

        persisted_geometry_bake_entry_bindings = 0
        geometry_bake_last_state_report = {}
        physics_cache_registration = {}
        if not post_import_skip_reasons:
            cache_handoff_report = self._handoff_background_blend_cache(str(state.get("blend_copy_path", "") or ""))
            if cache_handoff_report:
                merged_report = dict(handle.get("report") or {})
                merged_report.update(cache_handoff_report)
                handle["report"] = merged_report
        if not post_import_skip_reasons:
            persisted_geometry_bake_entry_bindings = self._persist_background_task_plan_geometry_bake_entry_bindings(
                launcher_node,
                task_plan,
            )
            if persisted_geometry_bake_entry_bindings > 0:
                merged_report = dict(handle.get("report") or {})
                merged_report["geometry_bake_entry_bindings_persisted"] = int(persisted_geometry_bake_entry_bindings)
                handle["report"] = merged_report
            geometry_bake_last_state_report = self._record_background_task_plan_geometry_bake_last_states(
                launcher_node,
                task_plan,
            )
            if int(geometry_bake_last_state_report.get("recorded", 0) or 0) > 0:
                merged_report = dict(handle.get("report") or {})
                merged_report["geometry_bake_last_state_recorded"] = int(
                    geometry_bake_last_state_report.get("recorded", 0) or 0
                )
                if int(geometry_bake_last_state_report.get("deferred_refresh_scheduled", 0) or 0) > 0:
                    merged_report["geometry_bake_last_state_deferred_refresh_scheduled"] = int(
                        geometry_bake_last_state_report.get("deferred_refresh_scheduled", 0) or 0
                    )
                handle["report"] = merged_report
            physics_cache_registration = self._register_background_task_plan_physics_cache_bindings(
                launcher_node,
                task_plan,
            )
            if int(physics_cache_registration.get("attempted", 0) or 0) > 0:
                merged_report = dict(handle.get("report") or {})
                merged_report["physics_cache_registered"] = int(physics_cache_registration.get("registered", 0) or 0)
                merged_report["physics_cache_registration_attempted"] = int(physics_cache_registration.get("attempted", 0) or 0)
                merged_report["physics_cache_backed_up_files"] = int(physics_cache_registration.get("backed_up_cache_files", 0) or 0)
                merged_report["physics_cache_restored_files"] = int(physics_cache_registration.get("restored_cache_files", 0) or 0)
                merged_report["physics_cache_files_changed_during_registration"] = bool(
                    physics_cache_registration.get("cache_files_changed_during_registration", False)
                )
                if bool(physics_cache_registration.get("mainfile_reload_required", False)):
                    merged_report["mainfile_reload_required"] = True
                    merged_report["mainfile_reload_reason"] = str(
                        physics_cache_registration.get("mainfile_reload_reason", "") or "physics_disk_cache_runtime_metadata"
                    )
                handle["report"] = merged_report
        else:
            merged_report = dict(handle.get("report") or {})
            merged_report["background_post_import_skipped"] = True
            merged_report["background_post_import_skip_reasons"] = list(post_import_skip_reasons)
            handle["report"] = merged_report
        should_save_imported_state = (
            persisted_geometry_bake_entry_bindings > 0
            or int(geometry_bake_last_state_report.get("recorded", 0) or 0) > 0
            or int(physics_cache_registration.get("registered", 0) or 0) > 0
        )
        if should_save_imported_state:
            save_report = self._save_current_mainfile_after_background_import(state["node_name"])
            merged_report = dict(handle.get("report") or {})
            if persisted_geometry_bake_entry_bindings > 0:
                merged_report["geometry_bake_entry_bindings_saved"] = bool(save_report.get("saved", False))
                if str(save_report.get("filepath", "") or "").strip():
                    merged_report["geometry_bake_entry_bindings_blend_path"] = str(save_report.get("filepath", "") or "")
                if not bool(save_report.get("saved", False)):
                    merged_report["geometry_bake_entry_bindings_save_reason"] = str(
                        save_report.get("reason", "save_failed") or "save_failed"
                    )
                    if str(save_report.get("error", "") or "").strip():
                        merged_report["geometry_bake_entry_bindings_save_error"] = str(save_report.get("error", "") or "")
            if int(geometry_bake_last_state_report.get("recorded", 0) or 0) > 0:
                merged_report["geometry_bake_last_state_saved"] = bool(save_report.get("saved", False))
                if str(save_report.get("filepath", "") or "").strip():
                    merged_report["geometry_bake_last_state_blend_path"] = str(save_report.get("filepath", "") or "")
                if not bool(save_report.get("saved", False)):
                    merged_report["geometry_bake_last_state_save_reason"] = str(
                        save_report.get("reason", "save_failed") or "save_failed"
                    )
                    if str(save_report.get("error", "") or "").strip():
                        merged_report["geometry_bake_last_state_save_error"] = str(save_report.get("error", "") or "")
            if int(physics_cache_registration.get("registered", 0) or 0) > 0:
                merged_report["physics_cache_registration_saved"] = bool(save_report.get("saved", False))
                if str(save_report.get("filepath", "") or "").strip():
                    merged_report["physics_cache_registration_blend_path"] = str(save_report.get("filepath", "") or "")
                if not bool(save_report.get("saved", False)):
                    merged_report["physics_cache_registration_save_reason"] = str(
                        save_report.get("reason", "save_failed") or "save_failed"
                    )
                    if str(save_report.get("error", "") or "").strip():
                        merged_report["physics_cache_registration_save_error"] = str(save_report.get("error", "") or "")
            handle["report"] = merged_report
        self._push_background_task_plan_outputs(state)
        self._cleanup_background_task_plan_blend_copy(state, keep_artifacts=False)
        self.background_task_plans.pop(task_id, None)
        self.log("INFO", f"BACKGROUND_TASK_PLAN_DONE [{state['node_name']}] {int(state.get('completed_step_count', 0))} step(s)", state["node_name"])

    def _tick_background_task_plans(self):
        if not self.background_task_plans:
            return
        previous_group_path = list(self.current_group_path)
        for task_id in list(self.background_task_plans.keys()):
            state = self.background_task_plans.get(task_id)
            if state is None:
                continue
            try:
                self._tick_background_task_plan(state)
            except FlowExecutionError as exc:
                handle = state["handle"]
                handle["status"] = "FAILED"
                handle["finished_at"] = time.monotonic()
                handle["report"] = {
                    "error_code": exc.code,
                    "error_message": exc.message,
                    "node_name": exc.node_name,
                    "blend_copy_path": str(state.get("blend_copy_path", "") or ""),
                }
                state["status"] = "FAILED"
                state["failure"] = exc
                state["current_step_group_path"] = []
                state["current_wait_type"] = ""
                self._push_background_task_plan_outputs(state)
                self._cleanup_background_task_plan_blend_copy(state, keep_artifacts=True)
                self.background_task_plans.pop(task_id, None)
                self.log("ERROR", f"BACKGROUND_TASK_PLAN_FAILED [{state['node_name']}] {exc.code}: {exc.message}", exc.node_name or state["node_name"])
            finally:
                self.current_group_path = list(previous_group_path)

    def _has_pending_background_task_plans(self):
        return bool(self.background_task_plans)

    def _handle_task_plan_repeat_control(self, run_node, entry, step_node, step_ref):
        del run_node
        cursor = int(entry["cursor"])
        repeat_pairs = entry.get("repeat_pairs", {})

        if self._is_repeat_start_node(step_node):
            repeat_info = repeat_pairs.get(cursor)
            if repeat_info is None:
                raise FlowExecutionError("AF_E009", "Repeat Start is missing compiled repeat metadata", step_node.name)
            repeat_count = int(repeat_info["count"])
            if repeat_count <= 0:
                self._set_output(step_node, "int_value", 0)
                entry["cursor"] = int(repeat_info["end_index"]) + 1
                self.log(
                    "INFO",
                    f"TASK_REPEAT_SKIPPED [{self._task_plan_entry_label(entry)}] count=0",
                    step_node.name,
                    getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
                )
                return True

            repeat_state = entry.setdefault("repeat_states", {}).get(cursor)
            if repeat_state is None:
                repeat_state = {
                    "iteration": 0,
                    "count": repeat_count,
                    "end_index": int(repeat_info["end_index"]),
                }
                entry["repeat_states"][cursor] = repeat_state
            self.current_group_path = list(step_ref.get("group_path", []))
            self._invalidate_data_node_outputs()
            self._set_output(step_node, "int_value", int(repeat_state["iteration"]))
            self._set_output(step_node, "report", {"index": int(repeat_state["iteration"])})
            self.log(
                "INFO",
                f"TASK_REPEAT_ITERATION [{self._task_plan_entry_label(entry)}] {int(repeat_state['iteration']) + 1}/{repeat_count}",
                step_node.name,
                getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
            )
            entry["cursor"] += 1
            return True

        if self._is_repeat_end_node(step_node):
            repeat_info = repeat_pairs.get(cursor)
            if repeat_info is None:
                raise FlowExecutionError("AF_E009", "Repeat End is missing compiled repeat metadata", step_node.name)
            start_index = int(repeat_info["start_index"])
            repeat_state = entry.setdefault("repeat_states", {}).get(start_index)
            if repeat_state is None:
                entry["cursor"] += 1
                return True
            next_iteration = int(repeat_state["iteration"]) + 1
            if next_iteration < int(repeat_state["count"]):
                repeat_state["iteration"] = next_iteration
                entry["cursor"] = start_index
                return True
            entry["repeat_states"].pop(start_index, None)
            self.log(
                "INFO",
                f"TASK_REPEAT_DONE [{self._task_plan_entry_label(entry)}] {int(repeat_state['count'])} iteration(s)",
                step_node.name,
                getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
            )
            entry["cursor"] += 1
            return True

        return False

    def _execute_task_plan_subflow_join(self, run_node, entry, step_node, step_ref):
        del run_node
        current_tree_name = getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name)
        previous_group_path = list(self.current_group_path)
        previous_flow_subflow_plans = self.flow_subflow_plans
        previous_cursor = int(self.cursor)
        self.current_group_path = list(step_ref.get("group_path", []))
        self.flow_subflow_plans = self._normalize_indexed_local_plans(entry.get("subflow_plans", {}))
        self.cursor = int(entry.get("cursor", 0))
        try:
            result, payload = self._execute_flow_subflow_join(step_node)
        except FlowExecutionError as exc:
            raise _enrich_flow_error_context(exc, step_node, current_tree_name, step_ref.get("group_path", []))
        finally:
            self.cursor = previous_cursor
            self.flow_subflow_plans = previous_flow_subflow_plans
            self.current_group_path = previous_group_path
        executed_steps = int(payload) if isinstance(payload, int) else 0
        return FLOW_OK, {
            "__af_runtime_control__": True,
            "count_step": False,
            "task_plan_completed_step_delta": 1 + max(0, executed_steps),
            "log_payload": payload,
        }

    def _execute_task_plan_branch_start(self, run_node, entry, step_node, step_ref):
        del run_node
        current_tree_name = getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name)
        previous_group_path = list(self.current_group_path)
        previous_pending_failure = copy.deepcopy(self.pending_branch_failure)
        previous_flow_branch_plans = self.flow_branch_plans
        previous_cursor = int(self.cursor)
        self.current_group_path = list(step_ref.get("group_path", []))
        entry_failure = entry.get("branch_failure")
        self.pending_branch_failure = copy.deepcopy(entry_failure) if isinstance(entry_failure, dict) else None
        self.flow_branch_plans = self._normalize_indexed_local_plans(entry.get("branch_plans", {}))
        self.cursor = int(entry.get("cursor", 0))
        try:
            result, payload = self._execute_flow_branch_start(step_node)
        except FlowExecutionError as exc:
            raise _enrich_flow_error_context(exc, step_node, current_tree_name, step_ref.get("group_path", []))
        finally:
            entry["branch_failure"] = copy.deepcopy(self.pending_branch_failure) if isinstance(self.pending_branch_failure, dict) else None
            self.cursor = previous_cursor
            self.flow_branch_plans = previous_flow_branch_plans
            self.pending_branch_failure = previous_pending_failure
            self.current_group_path = previous_group_path
        control_payload = payload if isinstance(payload, dict) and payload.get("__af_runtime_control__") else None
        if control_payload is None:
            return result, payload
        branch_triggered = bool(control_payload.get("branch_triggered", False))
        executed_steps = max(0, int(control_payload.get("executed_steps", 0) or 0))
        wrapped_payload = {
            "__af_runtime_control__": True,
            "count_step": False,
            "task_plan_completed_step_delta": executed_steps,
        }
        log_payload = control_payload.get("log_payload")
        if log_payload is not None:
            wrapped_payload["log_payload"] = log_payload
        if branch_triggered:
            wrapped_payload["task_plan_cursor_override"] = len(entry.get("step_refs", []))
        return FLOW_OK, wrapped_payload

    def _execute_task_plan(self, run_node):
        if self.current_task_plan is None or self.current_task_plan.get("run_node_name") != run_node.name:
            entries, linked_count, enabled_count = self._collect_run_task_plan_entries(run_node)
            if linked_count == 0:
                report = {
                    "plan_count": 0,
                    "enabled_plan_count": 0,
                    "skipped_plan_count": 0,
                    "completed_plan_count": 0,
                    "failed_plan_count": 0,
                    "failure_policy": str(getattr(run_node, "failure_policy", "STOP_ON_FAILURE")),
                    "step_count": 0,
                    "skipped": True,
                }
                self._set_output(run_node, "report", report)
                self._set_output(run_node, "status", "SKIPPED")
                self.log("INFO", f"TASK_PLAN_SKIPPED [{run_node.name}] no linked Task Plan inputs", run_node.name)
                self._clear_plan_progress()
                return FLOW_OK, "SKIPPED"
            for entry in entries:
                if not entry["enabled"]:
                    continue
                task_plan = entry.get("task_plan")
                if task_plan is None or str(task_plan.get("plan_kind", "")) != TASK_PLAN_KIND:
                    raise FlowExecutionError("AF_E011", f"{entry['title']} is not linked to a valid Task Plan", run_node.name)
            self.current_task_plan = {
                "run_node_name": run_node.name,
                "entries": entries,
                "cursor": 0,
                "linked_count": linked_count,
                "enabled_count": enabled_count,
                "completed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "failure_policy": str(getattr(run_node, "failure_policy", "STOP_ON_FAILURE")),
                "first_failure": None,
                "active_entry_index": -1,
            }

        state = self.current_task_plan
        entries = state["entries"]

        while state["cursor"] < len(entries):
            entry = entries[state["cursor"]]
            if not entry["enabled"]:
                if entry["status"] != "SKIPPED":
                    entry["status"] = "SKIPPED"
                    state["skipped_count"] += 1
                    self.log("INFO", f"TASK_PLAN_SKIPPED [{run_node.name}] {entry['title']}")
                state["cursor"] += 1
                continue

            state["active_entry_index"] = int(state["cursor"])

            next_step_index = entry["completed_step_count"] + 1 if int(entry["step_count"]) > int(entry["completed_step_count"]) else int(entry["step_count"])
            self._set_plan_progress(entry, next_step_index, entry["step_count"])

            if entry["status"] == "PENDING":
                entry["status"] = "RUNNING"
                self.log("INFO", f"TASK_PLAN_STARTED [{run_node.name}] {self._task_plan_entry_label(entry)} ({entry['step_count']} step(s))")

            if entry["cursor"] < len(entry["step_refs"]):
                step_ref = entry["step_refs"][entry["cursor"]]
                step_node = self._resolve_step_ref(step_ref, run_node.name)
                self.current_group_path = list(step_ref.get("group_path", []))
                if self._handle_task_plan_repeat_control(run_node, entry, step_node, step_ref):
                    if entry["cursor"] < len(entry["step_refs"]):
                        self._set_output(run_node, "status", "RUNNING")
                        return FLOW_YIELD, None
                    continue
                self._set_current_node(step_node)
                if not entry["step_started"]:
                    self.log(
                        "INFO",
                        f"TASK_STEP_STARTED [{self._task_plan_entry_label(entry)}]",
                        step_node.name,
                        getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
                    )
                    entry["step_started"] = True
                try:
                    if self._is_subflow_join_node(step_node):
                        result, payload = self._execute_task_plan_subflow_join(run_node, entry, step_node, step_ref)
                    elif self._is_branch_start_node(step_node):
                        result, payload = self._execute_task_plan_branch_start(run_node, entry, step_node, step_ref)
                    else:
                        result, payload = self._execute_node(step_node)
                except FlowExecutionError as exc:
                    _enrich_flow_error_context(
                        exc,
                        step_node,
                        getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
                        step_ref.get("group_path", []),
                    )
                    if self._handoff_task_plan_failure_to_branch(step_node, entry, exc, step_ref):
                        self._set_output(run_node, "status", "RUNNING")
                        return FLOW_YIELD, None
                    entry["status"] = "FAILED"
                    entry["step_started"] = False
                    state["failed_count"] += 1
                    if state["first_failure"] is None:
                        state["first_failure"] = exc
                    self.log("ERROR", f"TASK_PLAN_FAILED [{self._task_plan_entry_label(entry)}] {exc.code}: {exc.message}", exc.node_name or run_node.name)
                    if state["failure_policy"] == "STOP_ON_FAILURE":
                        self._set_task_plan_outputs(run_node, state)
                        self.current_task_plan = None
                        self._clear_plan_progress()
                        raise
                    state["cursor"] += 1
                    continue
                except Exception as exc:
                    wrapped = FlowExecutionError(
                        "AF_E999",
                        str(exc),
                        step_node.name,
                        getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
                        step_ref.get("group_path", []),
                    )
                    entry["status"] = "FAILED"
                    entry["step_started"] = False
                    state["failed_count"] += 1
                    if state["first_failure"] is None:
                        state["first_failure"] = wrapped
                    if self._handoff_task_plan_failure_to_branch(step_node, entry, wrapped, step_ref):
                        state["failed_count"] = max(0, int(state["failed_count"]) - 1)
                        if state["first_failure"] is wrapped:
                            state["first_failure"] = None
                        self._set_output(run_node, "status", "RUNNING")
                        return FLOW_YIELD, None
                    self.log("ERROR", f"TASK_PLAN_FAILED [{self._task_plan_entry_label(entry)}] AF_E999: {exc}", step_node.name)
                    if state["failure_policy"] == "STOP_ON_FAILURE":
                        self._set_task_plan_outputs(run_node, state)
                        self.current_task_plan = None
                        self._clear_plan_progress()
                        raise wrapped
                    state["cursor"] += 1
                    continue

                if result == FLOW_WAIT:
                    self._set_output(run_node, "status", "WAITING")
                    return FLOW_WAIT, None
                if result == FLOW_YIELD:
                    self._set_output(run_node, "status", "RUNNING")
                    return FLOW_YIELD, None
                control_payload = payload if isinstance(payload, dict) and payload.get("__af_runtime_control__") else None
                payload_for_log = control_payload.get("log_payload") if control_payload is not None else payload
                if payload_for_log is not None:
                    self.log(
                        "INFO",
                        f"TASK_STEP_DONE [{self._task_plan_entry_label(entry)}] ({payload_for_log})",
                        step_node.name,
                        getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
                    )
                else:
                    self.log(
                        "INFO",
                        f"TASK_STEP_DONE [{self._task_plan_entry_label(entry)}]",
                        step_node.name,
                        getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name),
                    )
                self._mark_node_finished(step_node, count_step=bool(control_payload.get("count_step", True)) if control_payload is not None else True)
                self._execute_post_node_flow_triggers(
                    step_node,
                    control_payload=control_payload,
                    group_path=step_ref.get("group_path", []),
                )
                entry["cursor"] += 1
                if control_payload is not None and "task_plan_cursor_override" in control_payload:
                    entry["cursor"] = int(control_payload["task_plan_cursor_override"])
                if control_payload is not None:
                    entry["completed_step_count"] += max(0, int(control_payload.get("task_plan_completed_step_delta", 0) or 0))
                else:
                    entry["completed_step_count"] += 1
                entry["branch_failure"] = None
                entry["step_started"] = False
                next_step_index = entry["completed_step_count"] + 1 if int(entry["step_count"]) > int(entry["completed_step_count"]) else int(entry["step_count"])
                self._set_plan_progress(entry, next_step_index, entry["step_count"])
                if entry["cursor"] < len(entry["step_refs"]):
                    self._set_output(run_node, "status", "RUNNING")
                    return FLOW_YIELD, None

            override_status = self._normalize_task_plan_final_status(self._resolve_task_plan_status_override(run_node, entry))
            final_status = override_status or "DONE"
            final_class = self._classify_task_plan_final_status(final_status)
            entry["status"] = final_status
            entry["branch_failure"] = None
            self.current_group_path = []

            if final_class == "FAILED":
                state["failed_count"] += 1
                failure = FlowExecutionError("AF_E010", f"Task Plan finished with status {final_status}", run_node.name)
                if state["first_failure"] is None:
                    state["first_failure"] = failure
                self.log("ERROR", f"TASK_PLAN_FAILED [{self._task_plan_entry_label(entry)}] status={final_status}", run_node.name)
                if state["failure_policy"] == "STOP_ON_FAILURE":
                    self._set_task_plan_outputs(run_node, state)
                    self.current_task_plan = None
                    self._clear_plan_progress()
                    raise failure
                state["cursor"] += 1
                if state["cursor"] < len(entries):
                    self._set_output(run_node, "status", "RUNNING")
                    return FLOW_YIELD, None
                continue

            if final_class == "SKIPPED":
                state["skipped_count"] += 1
                self.log("INFO", f"TASK_PLAN_SKIPPED [{run_node.name}] {self._task_plan_entry_label(entry)}")
            else:
                state["completed_count"] += 1
                self.log("INFO", f"TASK_PLAN_DONE [{run_node.name}] {self._task_plan_entry_label(entry)} ({entry['step_count']} step(s))")

            state["cursor"] += 1
            if state["cursor"] < len(entries):
                self._set_output(run_node, "status", "RUNNING")
                return FLOW_YIELD, None

        report = self._task_plan_state_report(state)
        self.current_task_plan = None
        self._clear_plan_progress()
        self._set_task_plan_outputs(run_node, {"entries": entries, **state})
        if state["failed_count"] > 0:
            first_failure = state["first_failure"] or FlowExecutionError("AF_E010", "Task Plan queue failed", run_node.name)
            raise FlowExecutionError("AF_E010", f"Task Plan queue failed with {state['failed_count']} failed plan(s)", first_failure.node_name or run_node.name)
        return FLOW_OK, report["completed_plan_count"]

    def _handoff_task_plan_failure_to_branch(self, step_node, entry, exc, step_ref):
        if self.current_task_plan is None:
            return False
        state = self.current_task_plan
        if int(state.get("active_entry_index", -1)) != int(state["cursor"]):
            return False
        if self._is_branch_start_node(step_node):
            return False

        next_cursor = int(entry.get("cursor", 0)) + 1
        if next_cursor >= len(entry.get("step_refs", [])):
            return False
        next_step_ref = entry["step_refs"][next_cursor]
        next_step_node = self._resolve_step_ref(next_step_ref, state.get("run_node_name", step_node.name))
        if not self._is_branch_start_node(next_step_node):
            return False

        entry["branch_failure"] = {
            "code": str(getattr(exc, "code", "AF_E010") or "AF_E010"),
            "message": str(getattr(exc, "message", "Flow failed") or "Flow failed"),
            "node_name": str(getattr(exc, "node_name", "") or step_node.name),
            "node_tree_name": str(getattr(exc, "node_tree_name", "") or getattr(getattr(step_node, "id_data", None), "name", self.node_tree.name)),
            "group_path": list(getattr(exc, "group_path", None) or step_ref.get("group_path", [])),
        }
        entry["cursor"] = next_cursor
        entry["step_started"] = False
        previous_group_path = list(self.current_group_path)
        try:
            self.current_group_path = list(step_ref.get("group_path", []))
            self._set_output(step_node, "status", "FAILED")
            self._set_output(
                step_node,
                "report",
                {
                    "status": "FAILED",
                    "error_code": str(getattr(exc, "code", "AF_E010") or "AF_E010"),
                    "error_message": str(getattr(exc, "message", "Flow failed") or "Flow failed"),
                    "node_name": str(getattr(exc, "node_name", "") or step_node.name),
                },
            )
        finally:
            self.current_group_path = previous_group_path
        self.log(
            "INFO",
            f"TASK_BRANCH_ARMED [{self._task_plan_entry_label(entry)}] after {str(getattr(exc, 'node_name', '') or step_node.name)}",
            next_step_node.name,
            getattr(getattr(next_step_node, "id_data", None), "name", self.node_tree.name),
        )
        return True


__all__ = ["RuntimeTaskPlanMixin"]
