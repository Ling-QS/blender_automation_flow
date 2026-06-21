import uuid
import math

from mathutils import Vector

from ...runtime_state.cache import (
    _property_package_bake_action_has_cached_data,
    _property_package_bake_cache_status_from_node,
    _clear_stored_property_package,
    _fallback_group_instance_stored_property_package,
    _find_property_package_bake_action_for_node,
    _has_stored_property_package,
    _is_bake_job_running,
    _read_reload_resume_checkpoint,
    _read_stored_property_package_direct,
    _reload_resume_checkpoint_path,
    _remove_reload_resume_checkpoint,
    _summarize_property_package,
    _write_reload_resume_checkpoint,
)
from ...runtime_property.definitions import (
    _clone_property_definition,
    _is_composite_property_assignment,
    _is_composite_property_definition,
    _iter_property_assignment_entries,
    _iter_property_definition_entries,
    _matches_modifier_filters,
    _merge_property_definitions,
    _modifier_filter_settings_from_metadata,
    _property_definition_has_content,
    _validate_property_definition,
)
from ...runtime_property.api import (
    _build_allowed_object_identity_filter,
    _is_composite_property_package,
    _iter_property_package_entries,
    _property_package_item_matches_allowed_objects,
    _property_package_item_count,
    _property_package_to_definition,
    _property_role_label,
    _property_scope_label,
    _validate_property_package,
)
from ...runtime_bake import (
    _apply_geometry_bake_entry_settings,
    _apply_temporary_geometry_bake_settings,
    _call_operator_with_override,
    _clear_geometry_bake_tracked_packed_cache_state,
    _ensure_background_geometry_task_supported,
    _find_geometry_bake_entry_for_task,
    _geometry_bake_cache_status_from_node,
    _invoke_geometry_nodes_bake_task,
    _invoke_physics_bake_all_task,
    _invoke_physics_bake_task,
    _physics_bake_cache_status_from_node,
    _restore_geometry_bake_entry_settings,
    _restore_waiting_bake_cleanup,
)
from ...runtime_task_ref import (
    _build_property_package_bake_task_ref_fallback,
    _ensure_object_persistent_uuid,
    _obj_item,
    _object_list_from_task_ref,
    _resolve_bake_target,
    _resolve_physics_task_target,
    _stored_property_package_key_for_node,
)
from ..property_package_bake import RuntimePropertyPackageBakeExecutionMixin, RuntimePropertyPackageBakeRecordMixin
from ..background_process import RuntimeBackgroundProcessHelpersMixin
from ..data_runtime import (
    RuntimeContextSamplingMixin,
    RuntimeDisplayMixin,
    RuntimeIdentityMixin,
    RuntimeLinksMixin,
    RuntimeMathDataMixin,
    RuntimeMutedDataMixin,
)
from ..flow import (
    RuntimeFlowControlMixin,
    RuntimeFlowStructureMixin,
    RuntimeLinearFlowMixin,
)
from ..runner_state import (
    RuntimeActionPrecheckMixin,
    RuntimeLifecycleMixin,
    RuntimeReloadStateMixin,
    RuntimeWaitReloadMixin,
)
from ..io import RuntimeInputsMixin, RuntimeOutputResolutionMixin, RuntimeOutputsMixin
from ..node_runtime import RuntimeNodeExecutionMixin, RuntimeNodePrecheckMixin, RuntimeNodeUtilsMixin
from ..object_runtime import RuntimeObjectActionsMixin
from ..property import (
    RuntimePropertyApplyMixin,
    RuntimePropertyContextMixin,
    RuntimePropertyDataMixin,
    RuntimePropertyPackageActionsMixin,
    RuntimePropertyPackageDataMixin,
    RuntimeStoredPackageMixin,
)
from ..scene import RuntimeSceneActionsMixin, RuntimeSceneDataMixin, RuntimeSceneLookupMixin
from ..task import RuntimeTaskActionNodesMixin, RuntimeTaskExecutionMixin, RuntimeTaskHandleMixin, RuntimeTaskPlanMixin
from ..task_ref import RuntimeTaskRefDataMixin, RuntimeTaskRefsMixin
from ...runtime_core.constants import (
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_WAITING,
    STATUS_RELOADING,
    STATUS_SUCCESS,
    STATUS_FAILED,
    STATUS_CANCELLED,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    FLOW_WAIT,
    FLOW_YIELD,
    FlowExecutionError,
)
from ...runtime_flow.helpers import (
    _find_single_from_input_socket,
    _find_single_to_output_socket,
    _first_output_node,
    _scan_repeat_pairs,
    _socket_specific_output_key,
)
from ...runtime_scene.objects import (
    _collect_constraint_pointer_references,
    _collect_depsgraph_dependency_objects,
    _collect_direct_depsgraph_dependency_objects,
    _collect_direct_static_dependency_objects,
    _collect_direct_task_dependency_objects,
    _collect_explicit_physics_collision_filter_ids,
    _collect_explicit_physics_collision_objects,
    _collect_modifier_pointer_references,
    _collect_objects_from_node_group,
    _collect_render_enabled_scene_objects,
    _collect_static_task_dependency_objects,
    _collect_task_dependency_objects,
    _get_physics_collision_collection,
    _iter_collection_objects,
    _iter_physics_collision_collection_objects,
    _iter_scene_objects,
    _link_object_to_collection_safe,
    _object_has_collision_modifier,
    _remove_unused_object_data,
    _socket_default_pointer,
    _unlink_object_from_collection_safe,
)
from .node_sets import (
    AUTO_FOLLOW_UNSUPPORTED_NODE_TYPES,
    BRANCH_UNSUPPORTED_NODE_TYPES,
    DATA_NODE_TYPES,
    SUBFLOW_UNSUPPORTED_NODE_TYPES,
    TASK_PLAN_STEP_TYPES,
)


class FlowRunner(
    RuntimeActionPrecheckMixin,
    RuntimeDisplayMixin,
    RuntimeOutputsMixin,
    RuntimeOutputResolutionMixin,
    RuntimeBackgroundProcessHelpersMixin,
    RuntimeMathDataMixin,
    RuntimeMutedDataMixin,
    RuntimeObjectActionsMixin,
    RuntimePropertyPackageActionsMixin,
    RuntimeSceneActionsMixin,
    RuntimeSceneDataMixin,
    RuntimeLinksMixin,
    RuntimeInputsMixin,
    RuntimeContextSamplingMixin,
    RuntimePropertyContextMixin,
    RuntimeIdentityMixin,
    RuntimeSceneLookupMixin,
    RuntimePropertyDataMixin,
    RuntimePropertyPackageDataMixin,
    RuntimePropertyApplyMixin,
    RuntimeStoredPackageMixin,
    RuntimePropertyPackageBakeRecordMixin,
    RuntimePropertyPackageBakeExecutionMixin,
    RuntimeFlowStructureMixin,
    RuntimeFlowControlMixin,
    RuntimeLinearFlowMixin,
    RuntimeLifecycleMixin,
    RuntimeNodePrecheckMixin,
    RuntimeNodeExecutionMixin,
    RuntimeNodeUtilsMixin,
    RuntimeTaskHandleMixin,
    RuntimeTaskExecutionMixin,
    RuntimeTaskActionNodesMixin,
    RuntimeTaskRefDataMixin,
    RuntimeTaskPlanMixin,
    RuntimeTaskRefsMixin,
    RuntimeWaitReloadMixin,
    RuntimeReloadStateMixin,
):
    DATA_NODE_TYPES = DATA_NODE_TYPES
    TASK_PLAN_STEP_TYPES = TASK_PLAN_STEP_TYPES
    AUTO_FOLLOW_UNSUPPORTED_NODE_TYPES = AUTO_FOLLOW_UNSUPPORTED_NODE_TYPES
    SUBFLOW_UNSUPPORTED_NODE_TYPES = SUBFLOW_UNSUPPORTED_NODE_TYPES
    BRANCH_UNSUPPORTED_NODE_TYPES = BRANCH_UNSUPPORTED_NODE_TYPES

    def __init__(self, node_tree, scene, ui_context=None, start_node_name="", auto_follow=False):
        self.node_tree = node_tree
        self.scene = scene
        self.settings = scene.af_flow_settings
        self.ui_context = dict(ui_context or {})
        self.start_node_name = str(start_node_name or "").strip()
        self.auto_follow = bool(auto_follow)
        self.property_package_bake_context = None
        self.run_id = str(uuid.uuid4())
        self.status = STATUS_IDLE
        self.nodes_in_order = []
        self.node_group_paths_in_order = []
        self.cursor = 0
        self.vars = {}
        self.last_snapshot_package = None
        self.tasks = {}
        self.current_wait = None
        self.current_task_plan = None
        self.background_task_plans = {}
        self.background_processes = {}
        self.current_group_path = []
        self.current_property_context = None
        self.stop_requested = False
        self.data_eval_stack = set()
        self.completed_step_count = 0
        self.flow_repeat_pairs = {}
        self.flow_repeat_states = {}
        self.flow_subflow_plans = {}
        self.flow_branch_plans = {}
        self.pending_branch_failure = None
        self.isolated_subflow_join_keys = set()
        self.isolated_branch_start_keys = set()
        self._active_waiting_node_key = None
        self._geometry_attribute_cache = {}
        self._object_lookup_cache = {}
        self._property_context_dependency_cache = {}
        self._runtime_matrix_cache = {}
        self._runtime_rotation_cache = {}
        self._property_assignment_plan_cache = {}
        self._auto_follow_tick_step_refs = []
        self._auto_follow_tick_step_keys = set()
        self._auto_follow_recent_step_refs = []
        self._auto_follow_recent_step_expiry = 0.0
        self._task_plan_input_overrides = {}
        self._status_report_cache_payload = None
        self._status_report_cache_dirty = False
        self._flow_toggle_cache_payload = None
        self._flow_toggle_cache_dirty = False

    def _evaluate_data_node(self, node):
        node_identity = self._node_identity(node)
        if node_identity in self.data_eval_stack:
            raise FlowExecutionError("AF_E019", f"Data node cycle detected at '{node.name}'", node.name)
        self.data_eval_stack.add(node_identity)
        try:
            node_type = node.bl_idname
            if getattr(node, "mute", False):
                self._evaluate_muted_data_node(node)
                return
            if self._evaluate_scene_data_node(node, node_type):
                return
            if self._evaluate_property_package_data_node(node, node_type):
                return
            if self._evaluate_task_ref_data_node(node, node_type):
                return

            if self._evaluate_math_data_node(node, node_type):
                return

            raise FlowExecutionError("AF_E009", f"Unsupported data node type: {node_type}", node.name)
        finally:
            self.data_eval_stack.discard(node_identity)

    def tick(self, max_immediate_steps=1):
        self._begin_auto_follow_tick_highlight()
        immediate_budget = None
        try:
            if max_immediate_steps is not None:
                parsed_budget = int(max_immediate_steps)
                if parsed_budget > 0:
                    immediate_budget = parsed_budget
        except Exception:
            immediate_budget = 1
        processed_immediate_steps = 0
        self._tick_background_task_plans()
        while True:
            if self.stop_requested:
                if self.current_wait is not None and self.current_wait.get("wait_type") == "bake_task":
                    if _is_bake_job_running():
                        self._commit_auto_follow_tick_highlight()
                        return False
                    _restore_waiting_bake_cleanup(self.current_wait, bake_completed=True)
                    self.current_wait = None
                self._commit_auto_follow_tick_highlight()
                return self._flow_finished(STATUS_CANCELLED, "RUN_CANCELLED")
            if self.cursor >= len(self.nodes_in_order):
                if self._has_pending_background_task_plans():
                    if any(str(state["handle"].get("status", "")) == "WAITING" for state in self.background_task_plans.values()):
                        self.set_status(STATUS_WAITING)
                    else:
                        self.set_status(STATUS_RUNNING)
                    self._commit_auto_follow_tick_highlight()
                    return False
                failed_background_handles = [handle for handle in self.tasks.values() if bool(handle.get("is_background_plan")) and str(handle.get("status", "")) == "FAILED"]
                if failed_background_handles:
                    self._commit_auto_follow_tick_highlight()
                    return self._flow_finished(STATUS_FAILED, "RUN_FAILED")
                self._commit_auto_follow_tick_highlight()
                return self._flow_finished(STATUS_SUCCESS, "RUN_SUCCESS")

            node = self.nodes_in_order[self.cursor]
            active_group_path = self._flow_group_path_at(self.cursor)
            is_task_plan_runner = node.bl_idname == "AFNodeRunTaskPlan"
            waiting_node_key = (self.cursor, self._node_identity(node)) if not is_task_plan_runner else None
            should_log_start = not is_task_plan_runner and self._active_waiting_node_key != waiting_node_key
            if not is_task_plan_runner:
                self.current_group_path = list(active_group_path)
                self._set_current_node(node)
                if should_log_start:
                    self.log("INFO", "NODE_EXEC_STARTED", node.name)
            try:
                result, payload = self._execute_node(node)
            except FlowExecutionError as exc:
                current_tree_name = str(
                    getattr(exc, "node_tree_name", "") or self.settings.runtime_tree_name or self.node_tree.name
                )
                self.log("ERROR", f"{exc.code}: {exc.message}", exc.node_name or node.name, current_tree_name)
                if self.current_task_plan is not None:
                    active_index = int(self.current_task_plan.get("active_entry_index", -1))
                    if 0 <= active_index < len(self.current_task_plan.get("entries", [])):
                        active_entry = self.current_task_plan["entries"][active_index]
                        if self._handoff_task_plan_failure_to_branch(node, active_entry, exc, {"group_path": list(getattr(exc, "group_path", None) or self.current_group_path)}):
                            self._commit_auto_follow_tick_highlight()
                            return False
                if self._handoff_failure_to_branch(node, exc, current_tree_name):
                    self._commit_auto_follow_tick_highlight()
                    return False
                self._mark_node_failed(
                    exc.node_name or node.name,
                    current_tree_name,
                    getattr(exc, "group_path", None),
                )
                self._auto_restore()
                self._commit_auto_follow_tick_highlight()
                return self._flow_finished(STATUS_FAILED, "RUN_FAILED")
            except Exception as exc:
                current_tree_name = str(self.settings.runtime_tree_name or self.node_tree.name)
                self.log("ERROR", f"AF_E999: {exc}", node.name, current_tree_name)
                self._mark_node_failed(node.name, current_tree_name)
                self._auto_restore()
                self._commit_auto_follow_tick_highlight()
                return self._flow_finished(STATUS_FAILED, "RUN_FAILED")

            control_payload = payload if isinstance(payload, dict) and payload.get("__af_runtime_control__") else None
            if not is_task_plan_runner:
                self._record_auto_follow_tick_node(node, group_path=active_group_path)
            if result == FLOW_WAIT:
                if not is_task_plan_runner:
                    if should_log_start:
                        self.log("INFO", "NODE_WAITING", node.name)
                    self._active_waiting_node_key = waiting_node_key
                self._commit_auto_follow_tick_highlight()
                return False

            self._active_waiting_node_key = None

            if result == FLOW_YIELD:
                self._commit_auto_follow_tick_highlight()
                return False

            if not is_task_plan_runner:
                payload_for_log = control_payload.get("log_payload") if control_payload is not None else payload
                if payload_for_log is not None:
                    self.log("INFO", f"NODE_EXEC_DONE ({payload_for_log})", node.name)
                else:
                    self.log("INFO", "NODE_EXEC_DONE", node.name)
                self._mark_node_finished(node, count_step=bool(control_payload.get("count_step", True)) if control_payload is not None else True)
            self._execute_post_node_flow_triggers(
                node,
                control_payload=control_payload,
                group_path=active_group_path,
            )
            if control_payload is not None and "cursor_override" in control_payload:
                self.cursor = int(control_payload["cursor_override"])
            else:
                self.cursor += 1
            reload_request = control_payload.get("reload_request") if control_payload is not None else None
            if reload_request is not None:
                try:
                    task_handle = dict(reload_request.get("task_handle") or {})
                    prepared_request = self._prepare_reload_after_task(node, task_handle, self.cursor)
                    from ... import operators as operators_module

                    schedule_reload_fn = getattr(operators_module, "schedule_reload_resume", None)
                    if schedule_reload_fn is None:
                        raise FlowExecutionError("AF_E005", "Reload scheduler is unavailable", node.name)
                    schedule_reload_fn(prepared_request)
                    self.settings.current_node_name = ""
                    self.set_status(STATUS_RELOADING)
                    self.log("INFO", f"RELOAD_NODE_TRIGGERED [{node.name}] {str(prepared_request.get('task_id', '') or '').strip()}".rstrip(), node.name)
                    self._commit_auto_follow_tick_highlight()
                    return True
                except FlowExecutionError as exc:
                    current_tree_name = str(
                        getattr(exc, "node_tree_name", "") or self.settings.runtime_tree_name or self.node_tree.name
                    )
                    self.log("ERROR", f"{exc.code}: {exc.message}", exc.node_name or node.name, current_tree_name)
                    self._mark_node_failed(
                        exc.node_name or node.name,
                        current_tree_name,
                        getattr(exc, "group_path", None),
                    )
                    self._commit_auto_follow_tick_highlight()
                    return self._flow_finished(STATUS_FAILED, "RUN_FAILED")
                except Exception as exc:
                    current_tree_name = str(self.settings.runtime_tree_name or self.node_tree.name)
                    self.log("ERROR", f"AF_E999: {exc}", node.name, current_tree_name)
                    self._mark_node_failed(node.name, current_tree_name)
                    self._commit_auto_follow_tick_highlight()
                    return self._flow_finished(STATUS_FAILED, "RUN_FAILED")

            processed_immediate_steps += 1
            if immediate_budget is not None and processed_immediate_steps >= immediate_budget:
                self._commit_auto_follow_tick_highlight()
                return False


__all__ = ["FlowRunner"]
