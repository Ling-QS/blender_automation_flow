from ...runtime_core.constants import FlowExecutionError
from ...runtime_property.api import _build_physics_property_package
from ...runtime_persistence.serialization import _copy_runtime_state_value


class RuntimeTaskRefDataMixin:
    def _evaluate_task_ref_data_node(self, node, node_type):
        if node_type == "AFNodeTaskOutput":
            task_plan = self._compile_task_plan(node, list(self.current_group_path))
            self._set_output(node, "task_plan", task_plan)
            self._set_output(node, "report", {"step_count": int(task_plan["step_count"])})
            return True

        if node_type == "AFNodeStart":
            start_ref = {
                "tree_name": getattr(getattr(node, "id_data", None), "name", self.node_tree.name),
                "start_node_name": str(getattr(node, "name", "") or ""),
            }
            self._set_output(node, "start_ref", start_ref)
            self._set_output(node, "report", {"start_node_name": str(start_ref["start_node_name"])})
            return True

        if node_type == "AFNodeResolveTaskRef":
            task_ref = self._get_linked_output(node, "Task Ref", "task_ref")
            object_list, frame_start, frame_end, status_value, report = self._resolve_task_ref_status_payload(
                node,
                task_ref,
            )
            self._set_output(node, "object_list", object_list)
            self._set_output(node, "frame_start", int(frame_start))
            self._set_output(node, "frame_end", int(frame_end))
            self._set_output(node, "status", status_value)
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodeGroup":
            task_plan = self._compile_group_task_plan(node)
            self._set_output(node, "task_plan", task_plan)
            report_value = None
            for output_socket in getattr(node, "outputs", []):
                socket_keys = list(self._socket_output_keys(output_socket))
                if not socket_keys:
                    continue
                if "task_plan" in socket_keys:
                    continue
                for socket_key in socket_keys:
                    resolved_value = self._get_output_from_source(
                        node,
                        output_socket,
                        socket_key,
                        list(self.current_group_path),
                    )
                    if resolved_value is None:
                        continue
                    self._set_output(node, socket_key, _copy_runtime_state_value(resolved_value))
                    if socket_key == "report":
                        report_value = resolved_value
            if isinstance(report_value, dict):
                merged_report = dict(report_value)
                merged_report.setdefault("step_count", int(task_plan["step_count"]))
                self._set_output(node, "report", merged_report)
            elif report_value is None:
                self._set_output(node, "report", {"step_count": int(task_plan["step_count"])})
            return True

        if node_type == "AFNodeBakeTask":
            try:
                task_ref = self._build_geometry_task_ref(node)
            except FlowExecutionError as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            except Exception as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            self._set_output(node, "task_ref", task_ref)
            object_list = self._object_list_from_task_ref(task_ref, "NAME_ASC", self.scene)
            self._set_output(node, "object_list", object_list)
            report = dict(task_ref.get("report") or {})
            report.update(
                {
                    "task_uid": task_ref["task_uid"],
                    "object_count": int(object_list.get("count", 0)),
                }
            )
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodeAutoFlowBakeTarget":
            try:
                task_ref = self._build_auto_flow_bake_task_ref(node)
            except FlowExecutionError as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            except Exception as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            self._set_output(node, "task_ref", task_ref)
            report = dict(task_ref.get("report") or {})
            report.update(
                {
                    "task_uid": task_ref["task_uid"],
                    "start_node_name": str(task_ref.get("start_node_name", "") or ""),
                    "frame_start": int(
                        task_ref.get("frame_start", getattr(self.scene, "frame_start", 1))
                        or getattr(self.scene, "frame_start", 1)
                    ),
                    "frame_end": int(
                        task_ref.get(
                            "frame_end",
                            getattr(self.scene, "frame_end", getattr(self.scene, "frame_start", 1)),
                        )
                        or getattr(self.scene, "frame_end", getattr(self.scene, "frame_start", 1))
                    ),
                    "bake_asset_id": str(task_ref.get("bake_asset_id", "") or ""),
                    "action_name": str(task_ref.get("action_name", "") or ""),
                    "object_count": int(len(list(task_ref.get("predicted_object_items", []) or []))),
                    "object_scope_mode": str(task_ref.get("object_scope_mode", "STATIC") or "STATIC"),
                }
            )
            self._set_output(node, "report", report)
            return True

        if node_type in {"AFNodeRenderTarget", "AFNodeRenderTask"}:
            try:
                task_ref = self._build_render_task_ref(node)
            except FlowExecutionError as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            except Exception as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            self._set_output(node, "task_ref", task_ref)
            render_objects = self._object_list_from_task_ref(task_ref, "NAME_ASC", self.scene)
            self._set_output(node, "object_list", render_objects)
            report = dict(task_ref.get("report") or {})
            report.update(
                {
                    "task_uid": task_ref["task_uid"],
                    "scene": task_ref["scene_name"],
                    "mode": task_ref["render_mode"],
                    "object_count": render_objects["count"],
                }
            )
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodePhysicsBakeSettings":
            payload = self._build_physics_settings_payload(node)
            property_package = _build_physics_property_package(node.name, payload)
            self._set_output(node, "property_package", property_package)
            self._set_output(
                node,
                "report",
                {
                    "object": payload["object_name"],
                    "modifier": payload["modifier_name"],
                    "frame_start": payload["frame_start"],
                    "frame_end": payload["frame_end"],
                },
            )
            return True

        if node_type == "AFNodePhysicsBakeTask":
            try:
                task_ref = self._build_physics_bake_all_task_ref(node)
            except FlowExecutionError as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            except Exception as exc:
                task_ref = self._make_invalid_task_ref_payload(node, exc)
            self._set_output(node, "task_ref", task_ref)
            object_list = self._object_list_from_task_ref(task_ref, "NAME_ASC", self.scene)
            self._set_output(node, "object_list", object_list)
            report = dict(task_ref.get("report") or {})
            report.update(
                {
                    "task_uid": task_ref["task_uid"],
                    "task_count": len(list(task_ref.get("tasks", []) or [])),
                    "object_count": object_list["count"],
                    "scene_frame_start": int(
                        task_ref.get("scene_frame_start", getattr(self.scene, "frame_start", 1))
                        or getattr(self.scene, "frame_start", 1)
                    ),
                    "scene_frame_end": int(
                        task_ref.get(
                            "scene_frame_end",
                            getattr(self.scene, "frame_end", getattr(self.scene, "frame_start", 1)),
                        )
                        or getattr(self.scene, "frame_end", getattr(self.scene, "frame_start", 1))
                    ),
                }
            )
            self._set_output(node, "report", report)
            return True

        return False


__all__ = ["RuntimeTaskRefDataMixin"]
