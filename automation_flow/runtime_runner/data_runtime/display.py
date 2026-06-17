import copy
import json
import time


class RuntimeDisplayMixin:
    def log(self, level, message, node_name="", node_tree_name=None):
        item = self.scene.af_flow_logs.add()
        item.level = level
        item.node_tree_name = str(node_tree_name or self.node_tree.name)
        item.node_name = node_name
        item.message = message
        item.timestamp = time.strftime("%H:%M:%S")
        max_entries = max(10, self.settings.max_log_entries)
        while len(self.scene.af_flow_logs) > max_entries:
            self.scene.af_flow_logs.remove(0)

    def set_status(self, status):
        self.status = status
        self.settings.runtime_status = status

    def _reset_runtime_display_state(self):
        self.settings.runtime_tree_name = self.node_tree.name
        self.settings.current_node_name = ""
        self.settings.last_finished_node_name = ""
        self.settings.error_node_name = ""
        self.settings.error_group_path_json = ""
        self._clear_plan_progress()
        self.settings.current_step_index = 0
        self.settings.total_step_count = 0
        self.completed_step_count = 0
        self.flow_repeat_states.clear()
        self._active_waiting_node_key = None
        self._auto_follow_tick_step_refs = []
        self._auto_follow_tick_step_keys = set()
        self._auto_follow_recent_step_refs = []
        self._auto_follow_recent_step_expiry = 0.0

    def _begin_auto_follow_tick_highlight(self):
        if not self.auto_follow:
            return
        self._auto_follow_tick_step_refs = []
        self._auto_follow_tick_step_keys = set()

    def _record_auto_follow_tick_node(self, node, group_path=None):
        if not self.auto_follow or node is None:
            return
        active_group_path = list(self.current_group_path if group_path is None else group_path)
        step_ref = self._make_step_ref(node, active_group_path)
        step_key = (
            str(step_ref.get("tree_name", "") or ""),
            str(step_ref.get("node_name", "") or ""),
            self._group_path_key(step_ref.get("group_path", []) or []),
        )
        if step_key in self._auto_follow_tick_step_keys:
            return
        self._auto_follow_tick_step_keys.add(step_key)
        self._auto_follow_tick_step_refs.append(step_ref)

    def _commit_auto_follow_tick_highlight(self, hold_seconds=0.18):
        if not self.auto_follow:
            return
        if self._auto_follow_tick_step_refs:
            self._auto_follow_recent_step_refs = [copy.deepcopy(item) for item in self._auto_follow_tick_step_refs]
            self._auto_follow_recent_step_expiry = float(time.monotonic()) + max(0.0, float(hold_seconds))
        self._auto_follow_tick_step_refs = []
        self._auto_follow_tick_step_keys = set()

    def auto_follow_recent_step_refs(self):
        if not self.auto_follow:
            return []
        if float(self._auto_follow_recent_step_expiry) <= float(time.monotonic()):
            return []
        return [copy.deepcopy(item) for item in self._auto_follow_recent_step_refs]

    def _set_current_node(self, node, step_index=None):
        node_tree = getattr(node, "id_data", None)
        self.settings.runtime_tree_name = getattr(node_tree, "name", self.node_tree.name) if node is not None else self.node_tree.name
        self.settings.current_node_name = node.name if node is not None else ""
        if node is None:
            self.settings.current_step_index = min(self.completed_step_count, self.settings.total_step_count)
            return
        if step_index is None:
            step_index = self.completed_step_count + 1
        if self.settings.total_step_count > 0:
            step_index = min(int(step_index), int(self.settings.total_step_count))
        self.settings.current_step_index = max(0, int(step_index))

    def _mark_node_finished(self, node, count_step=True):
        node_tree = getattr(node, "id_data", None)
        self.settings.runtime_tree_name = getattr(node_tree, "name", self.node_tree.name) if node is not None else self.node_tree.name
        self.settings.last_finished_node_name = node.name if node is not None else ""
        if count_step:
            self.completed_step_count += 1
            if self.settings.total_step_count > 0:
                self.completed_step_count = min(self.completed_step_count, int(self.settings.total_step_count))
            self.settings.current_step_index = self.completed_step_count

    def _mark_node_failed(self, node_name, node_tree_name=None, group_path=None):
        fallback_tree_name = str(self.settings.runtime_tree_name or self.node_tree.name)
        self.settings.runtime_tree_name = str(node_tree_name or fallback_tree_name)
        self.settings.error_node_name = str(node_name or "")
        try:
            active_group_path = list(self.current_group_path if group_path is None else group_path)
            self.settings.error_group_path_json = json.dumps(active_group_path, ensure_ascii=True)
        except Exception:
            self.settings.error_group_path_json = ""
        self.settings.current_node_name = ""


__all__ = ["RuntimeDisplayMixin"]
