from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_flow.helpers import _make_issue
from ...runtime_core.constants import FlowExecutionError
from ...node_system.socket_aliases import (
    ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
    find_node_input_socket,
)
from ...runtime_task_ref.refs import _invalid_task_ref_issue


class RuntimeNodePrecheckMixin:
    def _precheck_local_segment_plan(self, plan, owner_node_name):
        issues = []
        normalized_plan = self._normalize_local_segment_plan(plan)
        for step_ref in list(normalized_plan.get("step_refs", []) or []):
            try:
                step_node = self._resolve_step_ref(step_ref, owner_node_name)
            except FlowExecutionError as exc:
                issues.append(_make_issue(exc.code, exc.message, exc.node_name or owner_node_name))
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(step_ref.get("group_path", []))
            try:
                issues.extend(self._precheck_node(step_node))
            finally:
                self.current_group_path = previous_group_path
        return issues

    def _precheck_node(self, node):
        issues = []
        node_type = node.bl_idname
        if getattr(node, "mute", False) and node_type not in {"AFNodeStart", "AFNodeEnd", "AFNodeTaskStart"}:
            return issues
        if self.auto_follow and node_type in self.AUTO_FOLLOW_UNSUPPORTED_NODE_TYPES:
            issues.append(
                _make_issue(
                    "AF_E020",
                    "Auto Follow only supports lightweight foreground execution flows",
                    node.name,
                )
            )
            return issues
        if node_type == "AFNodeSubflowJoin":
            try:
                plan = self._compile_subflow_step_refs(node, node.name)
                issues.extend(self._precheck_local_segment_plan(plan, node.name))
            except FlowExecutionError as exc:
                issues.append(_make_issue(exc.code, exc.message, exc.node_name or node.name))
            return issues
        if node_type == "AFNodeBranchStart":
            end_node = self._find_branch_end_for_start(node)
            if end_node is None:
                issues.append(_make_issue("AF_E009", "Branch Start has no matching Branch End", node.name))
                return issues
            try:
                plan = self._compile_branch_step_refs(end_node, node.name)
                if str(plan.get("start_node_name", "") or "") != str(getattr(node, "name", "") or ""):
                    issues.append(_make_issue("AF_E009", "Branch End cannot reach matching Branch Start", end_node.name))
                else:
                    issues.extend(self._precheck_local_segment_plan(plan, node.name))
            except FlowExecutionError as exc:
                issues.append(_make_issue(exc.code, exc.message, exc.node_name or node.name))
            return issues
        if node_type == "AFNodeBranchEnd":
            start_node = self._find_branch_start_for_end(node)
            if start_node is None:
                issues.append(_make_issue("AF_E009", "Branch End has no matching Branch Start", node.name))
                return issues
            try:
                plan = self._compile_branch_step_refs(node, node.name)
                if str(plan.get("start_node_name", "") or "") != str(getattr(start_node, "name", "") or ""):
                    issues.append(_make_issue("AF_E009", "Branch End cannot reach matching Branch Start", node.name))
                else:
                    issues.extend(self._precheck_local_segment_plan(plan, node.name))
            except FlowExecutionError as exc:
                issues.append(_make_issue(exc.code, exc.message, exc.node_name or node.name))
            return issues
        action_issues = self._precheck_action_node(node)
        if action_issues is not None:
            return action_issues
        if node_type == "AFNodeBakeTask":
            if not str(node.bake_task_path).strip():
                issues.append(_make_issue("AF_E021", "Bake task path is empty", node.name))
                return issues
            try:
                self._split_bake_task_path(node.bake_task_path, node.name)
            except FlowExecutionError as exc:
                issues.append(_make_issue(exc.code, exc.message, node.name))
                return issues
            frame_start = self._input_int(node, "Frame Start", 1)
            frame_end = self._input_int(node, "Frame End", 250)
            if bool(node.apply_settings_on_run) and node.use_custom_simulation_frame_range and int(frame_end) < int(frame_start):
                issues.append(_make_issue("AF_E020", "Frame End cannot be less than Frame Start", node.name))
            if node.use_custom_path and not str(node.directory).strip():
                effective_target = str(getattr(node, "bake_target", "") or "")
                try:
                    task_ref = self._build_geometry_task_ref(node)
                    effective_target = str(self._resolve_geometry_task_effective_bake_target(task_ref) or effective_target)
                except Exception:
                    pass
                if effective_target == "DISK":
                    issues.append(_make_issue("AF_E020", "Custom path enabled but directory is empty", node.name))
        elif node_type == "AFNodePhysicsBakeSettings":
            if not str(node.physics_task_path).strip():
                issues.append(_make_issue("AF_E021", "Bake task path is empty", node.name))
                return issues
            try:
                self._resolve_physics_batch_task_target(node.physics_task_path, node.name)
            except FlowExecutionError as exc:
                issues.append(_make_issue(exc.code, exc.message, node.name))
                return issues
            frame_start = self._input_int(node, "Frame Start", int(self.scene.frame_start))
            frame_end = self._input_int(node, "Frame End", int(self.scene.frame_end))
            if bool(node.override_settings) and int(frame_end) < int(frame_start):
                issues.append(_make_issue("AF_E020", "Frame End cannot be less than Frame Start", node.name))
        elif node_type == "AFNodePhysicsBakeTask":
            try:
                task_ref = self._build_physics_bake_all_task_ref(node)
            except FlowExecutionError as exc:
                issues.append(_make_issue(exc.code, exc.message, node.name))
                return issues
            if bool(getattr(node, "override_frame_range", False)):
                frame_start = self._input_int(node, "Frame Start", int(self.scene.frame_start))
                frame_end = self._input_int(node, "Frame End", int(self.scene.frame_end))
                if int(frame_end) < int(frame_start):
                    issues.append(_make_issue("AF_E020", "Frame End cannot be less than Frame Start", node.name))
            if int(task_ref["scene_frame_end"]) < int(task_ref["scene_frame_start"]):
                issues.append(_make_issue("AF_E020", "Scene Frame End cannot be less than Scene Frame Start", node.name))
        elif node_type == "AFNodeEvaluateTaskDependencies":
            if _find_single_from_input_socket(node.inputs["Object List"])[0] is None:
                issues.append(_make_issue("AF_E011", "Object List input is not linked", node.name))
        elif node_type == "AFNodeModifierPropertyData":
            property_definition = self._modifier_property_definition_from_node(node)
            if int(property_definition.get("metadata", {}).get("count", 0)) <= 0:
                issues.append(_make_issue("AF_E020", "Property Definition has no enabled fields", node.name))
        elif node_type == "AFNodeObjectDisplayPropertyData":
            property_definition = self._object_display_property_definition_from_node(node)
            if int(property_definition.get("metadata", {}).get("count", 0)) <= 0:
                issues.append(_make_issue("AF_E020", "Property Definition has no enabled fields", node.name))
        elif node_type == "AFNodeObjectTransformPropertyData":
            property_definition = self._object_transform_property_definition_from_node(node)
            if int(property_definition.get("metadata", {}).get("count", 0)) <= 0:
                issues.append(_make_issue("AF_E020", "Property Definition has no enabled fields", node.name))
        elif node_type == "AFNodeReadGeometryAttribute":
            if _find_single_from_input_socket(node.inputs["Object List"])[0] is None and getattr(node, "target_object", None) is None:
                issues.append(_make_issue("AF_E011", "Object List input is not linked", node.name))
            attribute_name = str(getattr(node, "attribute_name", "") or "").strip()
            if not attribute_name:
                issues.append(_make_issue("AF_E011", "Attribute Name is empty", node.name))
            target_object = getattr(node, "target_object", None)
            if target_object is not None and getattr(target_object, "type", "") != "MESH":
                issues.append(_make_issue("AF_E020", "Geometry Attribute source object must be a Mesh", node.name))
        elif node_type == "AFNodeMergePropertyAssignments":
            base_socket = find_node_input_socket(node, BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME)
            add_socket = find_node_input_socket(node, ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME)
            base_linked = _find_single_from_input_socket(base_socket)[0] is not None if base_socket is not None else False
            add_linked = _find_single_from_input_socket(add_socket)[0] is not None if add_socket is not None else False
            if not base_linked and not add_linked:
                issues.append(_make_issue("AF_E011", "Property Assignment inputs are not linked", node.name))
        elif node_type == "AFNodeCreatePropertyPackage":
            if _find_single_from_input_socket(node.inputs["Object List"])[0] is None:
                issues.append(_make_issue("AF_E011", "Object List input is not linked", node.name))
        elif node_type == "AFNodePropertyPackageBakeTarget":
            if _find_single_from_input_socket(node.inputs["Task Ref"])[0] is None:
                issues.append(_make_issue("AF_E011", "Task Ref input is not linked", node.name))
                return issues
            task_ref = self._get_linked_output(node, "Task Ref", "task_ref")
            if task_ref is None:
                issues.append(_make_issue("AF_E011", "Task Ref not found", node.name))
                return issues
            invalid_issue = _invalid_task_ref_issue(task_ref)
            if invalid_issue is not None:
                issues.append(
                    _make_issue(
                        str(invalid_issue.get("code", "AF_E011") or "AF_E011"),
                        str(invalid_issue.get("message", "Task Ref is invalid") or "Task Ref is invalid"),
                        str(invalid_issue.get("node_name", "") or node.name),
                    )
                )
            elif str(dict(task_ref or {}).get("task_kind", "") or "") != "PROPERTY_PACKAGE_BAKE":
                issues.append(_make_issue("AF_E011", "Task Ref is not a Property Package task reference", node.name))
            frame_start = self._input_int(node, "Frame Start", int(getattr(self.scene, "frame_start", 1)))
            frame_end = self._input_int(node, "Frame End", int(getattr(self.scene, "frame_end", frame_start)))
            if int(frame_end) < int(frame_start):
                issues.append(_make_issue("AF_E020", "Frame End cannot be less than Frame Start", node.name))
        elif node_type == "AFNodeResolveTaskRef":
            if _find_single_from_input_socket(node.inputs["Task Ref"])[0] is None:
                issues.append(_make_issue("AF_E011", "Task Ref input is not linked", node.name))
        elif node_type == "AFNodeRunTaskPlan":
            entries, linked_count, _enabled_count = self._collect_run_task_plan_entries(node)
            if linked_count == 0:
                return issues
            for entry in entries:
                if not entry["enabled"]:
                    continue
                task_plan = entry.get("task_plan")
                if task_plan is None:
                    issues.append(_make_issue("AF_E011", f"{entry['title']} is not linked to a valid Task Plan", node.name))
                    continue
                issues.extend(self._precheck_local_segment_plan(task_plan, node.name))
        elif node_type == "AFNodeGroup":
            if getattr(node, "group_tree", None) is None:
                issues.append(_make_issue("AF_E030", "Group tree is missing", node.name))
        elif node_type == "AFNodeFilterPropertyPackage":
            package_socket = self._input_socket(node, PROPERTY_PACKAGE_SOCKET_NAME)
            if package_socket is None or _find_single_from_input_socket(package_socket)[0] is None:
                issues.append(_make_issue("AF_E011", "Property Package input is not linked", node.name))
            has_object_list = _find_single_from_input_socket(node.inputs["Object List"])[0] is not None
            definition_socket = self._input_socket(node, PROPERTY_DEFINITION_SOCKET_NAME)
            has_definition = definition_socket is not None and _find_single_from_input_socket(definition_socket)[0] is not None
            filter_mode = str(getattr(node, "filter_mode", "KEEP_MATCHED") or "KEEP_MATCHED")
            if not has_object_list and not has_definition and filter_mode != "REMOVE_MATCHED":
                issues.append(_make_issue("AF_E011", "Object List or Property Definition input must be linked", node.name))
        return issues


__all__ = ["RuntimeNodePrecheckMixin"]
