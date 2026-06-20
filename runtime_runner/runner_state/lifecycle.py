import copy

from ...runtime_core.constants import (
    STATUS_FAILED,
    STATUS_PRECHECK,
    STATUS_RUNNING,
    FlowExecutionError,
)
from ...runtime_flow.helpers import _make_issue
from ...runtime_task_ref.helpers import _precheck_failure_message


class RuntimeLifecycleMixin:
    def _reset_run_state_for_start(self):
        self.clear_logs()
        self.vars.clear()
        self._geometry_attribute_cache.clear()
        self._object_lookup_cache.clear()
        self._property_assignment_plan_cache.clear()
        self.last_snapshot_package = None
        self.tasks.clear()
        self.current_wait = None
        self.current_task_plan = None
        self.flow_subflow_plans.clear()
        self.flow_branch_plans.clear()
        self.isolated_subflow_join_keys.clear()
        self.isolated_branch_start_keys.clear()
        self.pending_branch_failure = None
        self.current_group_path = []
        self.stop_requested = False
        self.cursor = 0
        self.data_eval_stack.clear()
        self._reset_runtime_display_state()

    def _report_precheck_issues(self, issues, fallback_node_name=""):
        if not issues:
            return
        error_count = len([issue for issue in issues if issue["level"] == "ERROR"])
        warn_count = len([issue for issue in issues if issue["level"] == "WARN"])
        self.log("ERROR", f"PRECHECK_REPORT: {error_count} error(s), {warn_count} warning(s)")
        for issue in issues:
            self.log(issue["level"], f"{issue['code']}: {issue['message']}", issue["node_name"])
        raise FlowExecutionError(
            "AF_E010",
            _precheck_failure_message(issues),
            issues[0]["node_name"] if issues else fallback_node_name,
        )

    def _handle_start_flow_exception(self, exc):
        self._mark_node_failed(
            exc.node_name,
            getattr(exc, "node_tree_name", "") or None,
            getattr(exc, "group_path", None),
        )
        self.set_status(STATUS_FAILED)
        raise

    def precheck(self):
        self.set_status(STATUS_PRECHECK)
        self.log("INFO", "PRECHECK_STARTED")
        self._compile_linear_flow()
        issues = []
        for node in self.nodes_in_order:
            issues.extend(self._precheck_node(node))
        self._report_precheck_issues(issues)
        self.log("INFO", "PRECHECK_PASSED")

    def start(self):
        self._reset_run_state_for_start()
        run_flags = [f"mode={self.settings.run_mode}"]
        if self.auto_follow:
            run_flags.append("auto_follow=1")
        self.log("INFO", f"RUN_STARTED ({self.run_id}) {' '.join(run_flags)}")
        try:
            self.precheck()
            self.set_status(STATUS_RUNNING)
        except FlowExecutionError as exc:
            self._handle_start_flow_exception(exc)
        except Exception:
            self.set_status(STATUS_FAILED)
            raise

    def start_subflow(self, subflow_start_node_name):
        self._reset_run_state_for_start()
        run_flags = [f"mode={self.settings.run_mode}", f"subflow={str(subflow_start_node_name or '').strip()}"]
        if self.auto_follow:
            run_flags.append("auto_follow=1")
        self.log("INFO", f"RUN_STARTED ({self.run_id}) {' '.join(run_flags)}")

        start_node_name = str(subflow_start_node_name or "").strip()
        start_node = self.node_tree.nodes.get(start_node_name) if start_node_name else None
        if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeSubflowStart":
            self.set_status(STATUS_FAILED)
            raise FlowExecutionError("AF_E011", "Subflow Start node not found", start_node_name)

        pair_id = str(getattr(start_node, "af_pair_id", "") or "").strip()
        join_node = None
        if pair_id:
            for candidate in getattr(self.node_tree, "nodes", []):
                if getattr(candidate, "bl_idname", "") != "AFNodeSubflowJoin":
                    continue
                if str(getattr(candidate, "af_pair_id", "") or "").strip() == pair_id:
                    join_node = candidate
                    break
        if join_node is None:
            self.set_status(STATUS_FAILED)
            raise FlowExecutionError("AF_E011", "Subflow Join node not found", start_node.name)

        try:
            self.set_status(STATUS_PRECHECK)
            self.log("INFO", "PRECHECK_STARTED")
            self.nodes_in_order = [join_node]
            self.flow_branch_plans.clear()
            self.pending_branch_failure = None
            subflow_plan = self._compile_subflow_step_refs(join_node, join_node.name)
            subflow_plan["join_index"] = 0
            subflow_plan["join_node_name"] = str(getattr(join_node, "name", "") or "")
            self.flow_subflow_plans[0] = subflow_plan
            self.isolated_subflow_join_keys.add(self._node_identity(join_node))

            issues = list(self._precheck_node(join_node))
            for step_ref in list(subflow_plan.get("step_refs", []) or []):
                try:
                    step_node = self._resolve_step_ref(step_ref, join_node.name)
                except FlowExecutionError as exc:
                    issues.append(_make_issue(exc.code, exc.message, exc.node_name or join_node.name))
                    continue
                previous_group_path = list(self.current_group_path)
                self.current_group_path = list(step_ref.get("group_path", []))
                try:
                    issues.extend(self._precheck_node(step_node))
                finally:
                    self.current_group_path = previous_group_path

            self._report_precheck_issues(issues, join_node.name)
            self.log("INFO", "PRECHECK_PASSED")
            self.set_status(STATUS_RUNNING)
        except FlowExecutionError as exc:
            self._handle_start_flow_exception(exc)
        except Exception:
            self.set_status(STATUS_FAILED)
            raise

    def start_branch(self, branch_start_node_name):
        self._reset_run_state_for_start()
        run_flags = [f"mode={self.settings.run_mode}", f"branch={str(branch_start_node_name or '').strip()}"]
        if self.auto_follow:
            run_flags.append("auto_follow=1")
        self.log("INFO", f"RUN_STARTED ({self.run_id}) {' '.join(run_flags)}")

        start_node_name = str(branch_start_node_name or "").strip()
        start_node = self.node_tree.nodes.get(start_node_name) if start_node_name else None
        if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeBranchStart":
            self.set_status(STATUS_FAILED)
            raise FlowExecutionError("AF_E011", "Branch Start node not found", start_node_name)

        end_node = self._find_branch_end_for_start(start_node)
        if end_node is None:
            self.set_status(STATUS_FAILED)
            raise FlowExecutionError("AF_E011", "Branch End node not found", start_node.name)

        try:
            self.set_status(STATUS_PRECHECK)
            self.log("INFO", "PRECHECK_STARTED")
            self.nodes_in_order = [start_node]
            self.flow_subflow_plans.clear()
            self.pending_branch_failure = None
            branch_plan = self._compile_branch_step_refs(end_node, start_node.name)
            branch_plan["start_index"] = 0
            branch_plan["end_node_name"] = str(getattr(end_node, "name", "") or "")
            branch_plan["end_ref"] = self._make_step_ref(end_node)
            self.flow_branch_plans[0] = branch_plan
            self.isolated_branch_start_keys.add(self._node_identity(start_node))

            issues = list(self._precheck_node(start_node))
            issues.extend(self._precheck_node(end_node))
            for step_ref in list(branch_plan.get("step_refs", []) or []):
                try:
                    step_node = self._resolve_step_ref(step_ref, start_node.name)
                except FlowExecutionError as exc:
                    issues.append(_make_issue(exc.code, exc.message, exc.node_name or start_node.name))
                    continue
                previous_group_path = list(self.current_group_path)
                self.current_group_path = list(step_ref.get("group_path", []))
                try:
                    issues.extend(self._precheck_node(step_node))
                finally:
                    self.current_group_path = previous_group_path

            self._report_precheck_issues(issues, start_node.name)
            self.log("INFO", "PRECHECK_PASSED")
            self.set_status(STATUS_RUNNING)
        except FlowExecutionError as exc:
            self._handle_start_flow_exception(exc)
        except Exception:
            self.set_status(STATUS_FAILED)
            raise

    def resume(self, checkpoint):
        if not isinstance(checkpoint, dict):
            raise FlowExecutionError("AF_E009", "Reload resume checkpoint is invalid")
        self.run_id = str(checkpoint.get("run_id", self.run_id) or self.run_id)
        self.precheck()
        self.vars = dict(checkpoint.get("vars", {}) or {})
        self._invalidate_data_node_outputs()
        self.last_snapshot_package = copy.deepcopy(checkpoint.get("last_snapshot_package"))
        self.tasks = dict(checkpoint.get("tasks", {}) or {})
        self.current_wait = None
        self.current_task_plan = None
        self.background_task_plans.clear()
        self.background_processes.clear()
        self.flow_repeat_states = dict(checkpoint.get("flow_repeat_states", {}) or {})
        self.current_group_path = []
        self.stop_requested = False
        self.data_eval_stack.clear()
        self.completed_step_count = max(0, int(checkpoint.get("completed_step_count", 0) or 0))
        cursor = max(0, int(checkpoint.get("cursor", 0) or 0))
        self.cursor = min(cursor, len(self.nodes_in_order))
        self.settings.error_node_name = ""
        self.settings.error_group_path_json = ""
        self.settings.last_finished_node_name = str(checkpoint.get("reload_node_name", "") or self.settings.last_finished_node_name)
        self.settings.runtime_tree_name = self.node_tree.name
        self.settings.current_node_name = ""
        self.settings.current_step_index = min(self.completed_step_count, int(self.settings.total_step_count))
        for entry in checkpoint.get("background_task_plans", []):
            self._restore_background_task_plan_checkpoint(entry)
        self.log("INFO", f"RUN_RESUMED ({self.run_id})")
        self.set_status(STATUS_RUNNING)

    def request_stop(self):
        self.stop_requested = True


__all__ = ["RuntimeLifecycleMixin"]
