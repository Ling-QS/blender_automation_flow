import bpy

from ...node_system.socket_aliases import PROPERTY_PACKAGE_SOCKET_NAME
from ...runtime_core.constants import TASK_PLAN_KIND
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_task_ref.refs import _invalid_task_ref_issue


class RuntimeActionPrecheckMixin:
    def _precheck_action_node(self, node):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type in {
            "AFNodeCreateCollection",
            "AFNodeAddToCollection",
            "AFNodeCreateObject",
            "AFNodeDuplicateObject",
            "AFNodeDeleteObject",
        }:
            return self._precheck_object_action_node(node, node_type)
        if node_type in {"AFNodeSetActiveCamera", "AFNodeRenderTarget", "AFNodeRenderTask"}:
            return self._precheck_scene_action_node(node, node_type)
        if node_type in {"AFNodeTaskStep", "AFNodeRunBackgroundTaskPlan"}:
            return self._precheck_task_action_node(node, node_type)
        if node_type in {"AFNodeWaitForTask", "AFNodeReloadAfterTask"}:
            return self._precheck_wait_reload_node(node, node_type)
        if node_type in {
            "AFNodeStorePropertyPackage",
            "AFNodeApplyObjectProperties",
            "AFNodeApplyPropertyPackage",
            "AFNodeRecordPropertyPackage",
        }:
            return self._precheck_property_package_action_node(node, node_type)
        return None

    def _precheck_object_action_node(self, node, node_type):
        issues = []
        if node_type == "AFNodeCreateCollection":
            if not str(getattr(node, "collection_name", "") or "").strip():
                issues.append(self._make_issue("AF_E011", "Collection Name is empty", node.name))
        elif node_type == "AFNodeAddToCollection":
            if _find_single_from_input_socket(node.inputs["Object List"])[0] is None:
                issues.append(self._make_issue("AF_E011", "Object List input is not linked", node.name))
            if _find_single_from_input_socket(node.inputs["Collection List"])[0] is None and getattr(node, "target_collection", None) is None:
                issues.append(self._make_issue("AF_E011", "Collection List input is not linked", node.name))
        elif node_type == "AFNodeCreateObject":
            if not str(getattr(node, "object_name", "") or "").strip():
                issues.append(self._make_issue("AF_E011", "Object Name is empty", node.name))
        elif node_type == "AFNodeDuplicateObject":
            if _find_single_from_input_socket(node.inputs["Object List"])[0] is None:
                issues.append(self._make_issue("AF_E011", "Object List input is not linked", node.name))
        elif node_type == "AFNodeDeleteObject":
            if _find_single_from_input_socket(node.inputs["Object List"])[0] is None:
                issues.append(self._make_issue("AF_E011", "Object List input is not linked", node.name))
        return issues

    def _precheck_scene_action_node(self, node, node_type):
        issues = []
        if node_type == "AFNodeSetActiveCamera":
            scene = node.target_scene if node.target_scene is not None else self.scene
            camera = node.camera_object
            if scene is None:
                issues.append(self._make_issue("AF_E001", "Target scene is missing", node.name))
            if camera is None:
                issues.append(self._make_issue("AF_E001", "Camera object is not set", node.name))
            elif getattr(camera, "type", "") != "CAMERA":
                issues.append(self._make_issue("AF_E020", "Camera object must be a Camera", node.name))
            return issues

        render_scene = node.target_scene if node.target_scene is not None else self.scene
        if render_scene is None:
            issues.append(self._make_issue("AF_E001", "Target scene is missing", node.name))
        elif getattr(render_scene, "camera", None) is None:
            issues.append(self._make_issue("AF_E001", "Target scene has no active camera", node.name))
        frame_start = self._input_int(node, "Frame Start", int(node.frame_start))
        frame_end = self._input_int(node, "Frame End", int(node.frame_end))
        if node.render_mode == "ANIMATION" and int(frame_end) < int(frame_start):
            issues.append(self._make_issue("AF_E020", "Frame End cannot be less than Frame Start", node.name))
        return issues

    def _precheck_task_action_node(self, node, node_type):
        issues = []
        if node_type == "AFNodeTaskStep":
            if _find_single_from_input_socket(node.inputs["Task Ref"])[0] is None:
                issues.append(self._make_issue("AF_E011", "Task Ref input is not linked", node.name))
                return issues
            task_ref = self._get_linked_output(node, "Task Ref", "task_ref")
            if task_ref is None:
                issues.append(self._make_issue("AF_E011", "Task Ref not found", node.name))
                return issues
            invalid_issue = _invalid_task_ref_issue(task_ref)
            if invalid_issue is not None:
                issues.append(
                    self._make_issue(
                        str(invalid_issue.get("code", "AF_E011") or "AF_E011"),
                        str(invalid_issue.get("message", "Task Ref is invalid") or "Task Ref is invalid"),
                        str(invalid_issue.get("node_name", "") or node.name),
                    )
                )
            return issues

        if _find_single_from_input_socket(node.inputs["Task Plan"])[0] is not None:
            task_plan = self._get_linked_output(node, "Task Plan", "task_plan")
            if task_plan is None or str(task_plan.get("plan_kind", "")) != TASK_PLAN_KIND:
                issues.append(self._make_issue("AF_E011", "Task Plan input is not linked to a valid Task Plan", node.name))
            else:
                issues.extend(self._validate_background_task_plan(node, task_plan))
        return issues

    def _precheck_wait_reload_node(self, node, node_type):
        issues = []
        if node_type == "AFNodeWaitForTask":
            if node.delay_seconds < 0:
                issues.append(self._make_issue("AF_E020", "Delay seconds cannot be negative", node.name))
            return issues

        if _find_single_from_input_socket(node.inputs["Task Handle"])[0] is None:
            issues.append(self._make_issue("AF_E011", "Task Handle input is not linked", node.name))
        if not str(getattr(bpy.data, "filepath", "") or "").strip():
            issues.append(self._make_issue("AF_E005", "Current .blend must be saved before reload", node.name))
        return issues

    def _precheck_property_package_action_node(self, node, node_type):
        issues = []
        if node_type == "AFNodeStorePropertyPackage":
            if str(getattr(node, "store_mode", "STORE_AND_OUTPUT")) == "STORE_AND_OUTPUT":
                package_socket = self._input_socket(node, PROPERTY_PACKAGE_SOCKET_NAME)
                if package_socket is None or _find_single_from_input_socket(package_socket)[0] is None:
                    issues.append(self._make_issue("AF_E011", "Property Package input is not linked", node.name))
            elif self._read_stored_property_package(node) is None:
                issues.append(self._make_issue("AF_E011", "No stored Property Package is available", node.name))
        elif node_type == "AFNodeApplyObjectProperties":
            if _find_single_from_input_socket(node.inputs["Object List"])[0] is None:
                issues.append(self._make_issue("AF_E011", "Object List input is not linked", node.name))
            apply_mode = str(getattr(node, "apply_mode", "PACKAGE") or "PACKAGE")
            if apply_mode == "ASSIGNMENT":
                if not any(
                    _find_single_from_input_socket(socket)[0] is not None
                    for socket in getattr(node, "inputs", [])
                    if str(getattr(socket, "bl_idname", "") or "") == "AFSocketPropertyAssignment"
                    and not bool(getattr(socket, "af_is_virtual", False))
                ):
                    issues.append(self._make_issue("AF_E011", "Property Assignment inputs are not linked", node.name))
            else:
                package_socket = self._input_socket(node, PROPERTY_PACKAGE_SOCKET_NAME)
                if package_socket is None or _find_single_from_input_socket(package_socket)[0] is None:
                    issues.append(self._make_issue("AF_E011", "Property Package input is not linked", node.name))
        elif node_type in {"AFNodeApplyPropertyPackage", "AFNodeRecordPropertyPackage"}:
            package_socket = self._input_socket(node, PROPERTY_PACKAGE_SOCKET_NAME)
            if package_socket is None or _find_single_from_input_socket(package_socket)[0] is None:
                issues.append(self._make_issue("AF_E011", "Property Package input is not linked", node.name))
        return issues


__all__ = ["RuntimeActionPrecheckMixin"]
