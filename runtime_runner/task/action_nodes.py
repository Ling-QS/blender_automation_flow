import copy

from ...runtime_core.constants import FLOW_OK, FLOW_WAIT, TASK_PLAN_KIND, FlowExecutionError
from ...runtime_flow.helpers import _find_single_from_input_socket


class RuntimeTaskActionNodesMixin:
    def _execute_task_action_node(self, node):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeRunBackgroundTaskPlan":
            return self._execute_run_background_task_plan_node(node)
        if node_type == "AFNodeTaskStep":
            return self._execute_task_step_node(node)
        return None

    def _execute_run_background_task_plan_node(self, node):
        if _find_single_from_input_socket(node.inputs["Task Plan"])[0] is None:
            handle = self._create_skipped_background_plan_handle(node, "Task Plan input is not linked")
            self.log("INFO", f"BACKGROUND_TASK_PLAN_SKIPPED [{node.name}] no task plan linked", node.name)
            self._set_output(node, "task_handle", copy.deepcopy(handle))
            self._set_output(node, "status", handle["status"])
            self._set_output(
                node,
                "report",
                {
                    "task_id": str(handle["task_id"]),
                    "plan_uid": str(handle.get("plan_uid", "")),
                    "step_count": int(handle.get("step_count", 0)),
                    "status": str(handle.get("status", "")),
                    "skipped": True,
                    "simulated": False,
                    "flow_test": False,
                    "dry_run": False,
                    "reason": "Task Plan input is not linked",
                },
            )
            return FLOW_OK, handle["task_id"]

        task_plan = self._get_linked_output(node, "Task Plan", "task_plan")
        if task_plan is None or str(task_plan.get("plan_kind", "")) != TASK_PLAN_KIND:
            raise FlowExecutionError("AF_E011", "Task Plan input is not linked to a valid Task Plan", node.name)
        handle = self._start_background_task_plan(node, task_plan)
        if self._task_handle_is_skipped(handle):
            self.log("INFO", f"BACKGROUND_TASK_PLAN_SKIPPED [{node.name}] precheck", node.name)
        display_status = self._task_handle_display_status(handle, default=str(handle.get("status", "DONE")))
        self._set_output(node, "task_handle", copy.deepcopy(handle))
        self._set_output(node, "status", display_status)
        self._set_output(
            node,
            "report",
            {
                "task_id": str(handle["task_id"]),
                "plan_uid": str(handle.get("plan_uid", "")),
                "step_count": int(handle.get("step_count", 0)),
                "status": display_status,
                "skipped": bool(handle.get("skipped", False)),
                "simulated": bool(handle.get("simulated", False)),
                "flow_test": bool(handle.get("flow_test", False)),
                "dry_run": bool(dict(handle.get("report") or {}).get("dry_run", False)),
                "prechecked": bool(dict(handle.get("report") or {}).get("prechecked", False)),
            },
        )
        return FLOW_OK, handle["task_id"]

    def _execute_task_step_node(self, node):
        task_ref = self._get_linked_output(node, "Task Ref", "task_ref")
        if task_ref is None:
            raise FlowExecutionError("AF_E011", "Task Ref not found", node.name)
        object_list = self._object_list_from_task_ref(task_ref, "NAME_ASC", self.scene)
        wait_result = self._poll_bake_wait(node)
        if wait_result is not None:
            return wait_result
        start_result = self._start_task_ref_async(node, task_ref, object_list)
        task_handle = start_result["task_handle"]
        display_status = self._task_handle_display_status(task_handle)
        self._set_output(node, "status", display_status)
        report = {
            "task_id": task_handle["task_id"],
            "task_kind": task_handle["task_kind"],
            "target_count": object_list["count"],
            "status": display_status,
        }
        report.update(dict(task_handle.get("report") or {}))
        if bool(task_handle.get("skipped", False)):
            report["skipped"] = True
        self._set_output(node, "report", report)
        if start_result["finished"]:
            return FLOW_OK, task_handle["task_id"]
        return FLOW_WAIT, None


__all__ = ["RuntimeTaskActionNodesMixin"]
