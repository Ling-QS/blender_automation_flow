import copy
import time

from ...runtime_core.constants import (
    FLOW_OK,
    FLOW_WAIT,
    STATUS_RUNNING,
    STATUS_WAITING,
    FlowExecutionError,
)


class RuntimeWaitReloadMixin:
    def _execute_wait_reload_node(self, node, dry_run=False, flow_test=False):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeWaitForTask":
            return self._execute_wait_for_task_node(node)
        if node_type == "AFNodeDelayWait":
            return self._execute_delay_wait_node(node)
        if node_type == "AFNodeReloadAfterTask":
            return self._execute_reload_after_task_node(node, dry_run=dry_run, flow_test=flow_test)
        return None

    def _execute_wait_for_task_node(self, node):
        task_handle_payload = self._get_linked_output(node, "Task Handle", "task_handle")
        if task_handle_payload is None:
            raise FlowExecutionError("AF_E011", "Task Handle input is not linked", node.name)
        live_handle = self._resolve_live_task_handle(task_handle_payload)
        if live_handle is None:
            raise FlowExecutionError("AF_E011", "Task Handle input is invalid", node.name)
        task_id = str(live_handle.get("task_id", "") or "")
        status = str(live_handle.get("status", "PENDING") or "PENDING")
        if status == "FAILED":
            report = dict(live_handle.get("report") or {})
            raise FlowExecutionError(
                str(report.get("error_code", "AF_E010")),
                str(report.get("error_message", "Background Task Plan failed")),
                str(report.get("node_name", node.name) or node.name),
            )
        if task_id and task_id in self.background_task_plans:
            self.set_status(STATUS_WAITING)
            self._set_output(node, "status", status)
            report = {"task_id": task_id, "status": status}
            report.update(dict(live_handle.get("report") or {}))
            self._set_output(node, "report", report)
            return FLOW_WAIT, None
        self.set_status(STATUS_RUNNING)
        self._set_output(node, "status", status)
        report = {"task_id": task_id, "status": status}
        report.update(dict(live_handle.get("report") or {}))
        report["skipped"] = bool(self._task_handle_is_skipped(live_handle))
        self._set_output(node, "report", report)
        return FLOW_OK, task_id or status

    def _execute_delay_wait_node(self, node):
        delay = max(0.0, float(node.delay_seconds))
        interval_ms = node.poll_interval_ms if node.poll_interval_ms > 0 else self.settings.poll_interval_ms
        interval_ms = max(50, interval_ms)

        if self.current_wait is None:
            self.current_wait = {
                "wait_type": "delay",
                "node_name": node.name,
                "started_at": time.monotonic(),
                "delay_seconds": delay,
                "poll_interval_ms": interval_ms,
                "next_poll_at": time.monotonic(),
            }
            self.set_status(STATUS_WAITING)
        wait = self.current_wait
        delay_result = self._poll_delay_wait_state(wait)
        if delay_result is None:
            raise FlowExecutionError("AF_E009", "Delay wait state is invalid", node.name)
        if delay_result["finished"]:
            self.current_wait = None
            self.set_status(STATUS_RUNNING)
            return FLOW_OK, "DONE"
        return FLOW_WAIT, None

    def _execute_reload_after_task_node(self, node, dry_run=False, flow_test=False):
        task_handle_payload = self._get_linked_output(node, "Task Handle", "task_handle")
        if task_handle_payload is None:
            raise FlowExecutionError("AF_E011", "Task Handle input is not linked", node.name)
        live_handle = self._resolve_live_task_handle(task_handle_payload)
        if live_handle is None:
            raise FlowExecutionError("AF_E011", "Task Handle input is invalid", node.name)
        task_id = str(live_handle.get("task_id", "") or "")
        status = str(live_handle.get("status", "PENDING") or "PENDING")
        report = {"task_id": task_id, "status": status}
        report.update(dict(live_handle.get("report") or {}))
        report["skipped"] = bool(self._task_handle_is_skipped(live_handle))
        if status == "FAILED":
            raise FlowExecutionError(
                str(report.get("error_code", "AF_E010")),
                str(report.get("error_message", "Background Task Plan failed")),
                str(report.get("node_name", node.name) or node.name),
            )
        if bool(self._task_handle_is_skipped(live_handle)):
            report["reload_skipped"] = True
            self._set_output(node, "status", "SKIPPED")
            self._set_output(node, "report", report)
            self.set_status(STATUS_RUNNING)
            return FLOW_OK, "SKIPPED"
        self._set_output(node, "status", status)
        self._set_output(node, "report", report)
        if status != "DONE":
            self.set_status(STATUS_WAITING)
            return FLOW_WAIT, None
        if bool(live_handle.get("simulated", False)) or bool(report.get("simulated", False)):
            report["reload_skipped"] = True
            report["simulated"] = True
            if bool(live_handle.get("flow_test", False)) or bool(report.get("flow_test", False)) or flow_test:
                report["flow_test"] = True
            if dry_run or bool(report.get("dry_run", False)):
                report["dry_run"] = True
            self._set_output(node, "report", report)
            self.set_status(STATUS_RUNNING)
            return FLOW_OK, "SIMULATED"
        return FLOW_OK, self._runtime_control_payload(
            self.cursor + 1,
            count_step=True,
            log_payload=task_id or "RELOAD",
            reload_request={"task_handle": copy.deepcopy(live_handle)},
        )


__all__ = ["RuntimeWaitReloadMixin"]
