import uuid

from ...runtime_core.constants import (
    FlowExecutionError,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_KIND_RENDER,
)
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_scene.objects import _collect_render_enabled_scene_objects
from .property_package_bake import RuntimeTaskRefPropertyPackageBakeMixin
from .common import RuntimeTaskRefCommonMixin
from .status import RuntimeTaskRefStatusMixin


class RuntimeTaskRefsMixin(
    RuntimeTaskRefCommonMixin,
    RuntimeTaskRefStatusMixin,
    RuntimeTaskRefPropertyPackageBakeMixin,
):
    def _build_geometry_task_ref(self, node):
        object_ref, modifier, bake_node, bake_entry = self._resolve_bake_target(node.bake_task_path, node.name)
        frame_start = self._input_int(node, "Frame Start", 1)
        frame_end = self._input_int(node, "Frame End", 250)
        task_ref = {
            "task_kind": TASK_KIND_GEOMETRY,
            "task_uid": str(uuid.uuid4()),
            "source_node": node.name,
            "source_tree_name": getattr(getattr(node, "id_data", None), "name", self.node_tree.name),
            "task_path": str(node.bake_task_path),
            "object_ref": object_ref,
            "object_name": object_ref.name,
            "session_uid": int(object_ref.session_uid),
            "object_uuid": self._ensure_object_persistent_uuid(object_ref),
            "modifier_name": modifier.name,
            "bake_node_name": bake_node.name,
            "bake_id": int(bake_entry.bake_id),
            "bake_mode": node.bake_mode,
            "bake_target": node.bake_target,
            "use_custom_path": bool(node.use_custom_path),
            "directory": str(node.directory or ""),
            "use_custom_simulation_frame_range": bool(node.use_custom_simulation_frame_range),
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
            "apply_settings_on_run": bool(node.apply_settings_on_run),
            "free_before_bake": bool(node.free_before_bake),
        }
        return self._embed_task_ref_status_payload(node, task_ref)

    def _build_render_task_ref(self, node):
        target_scene = node.target_scene if node.target_scene is not None else self.scene
        frame = self._input_int(node, "Frame", int(node.frame))
        frame_start = self._input_int(node, "Frame Start", int(node.frame_start))
        frame_end = self._input_int(node, "Frame End", int(node.frame_end))
        render_object_items = _collect_render_enabled_scene_objects(target_scene)
        task_ref = {
            "task_kind": TASK_KIND_RENDER,
            "task_uid": str(uuid.uuid4()),
            "source_node": node.name,
            "scene_ref": target_scene,
            "scene_name": getattr(target_scene, "name", ""),
            "render_mode": str(node.render_mode),
            "frame": int(frame),
            "override_frame_range": True,
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
            "write_still": bool(node.write_still),
            "use_viewport": bool(node.use_viewport),
            "render_object_items": render_object_items,
        }
        return self._embed_task_ref_status_payload(node, task_ref)

    def _build_physics_settings_payload(self, node):
        object_ref, modifier = self._resolve_physics_batch_task_target(node.physics_task_path, node.name)
        frame_start = self._input_int(node, "Frame Start", int(self.scene.frame_start))
        frame_end = self._input_int(node, "Frame End", int(self.scene.frame_end))
        return {
            "source_node": node.name,
            "task_path": str(node.physics_task_path),
            "object_ref": object_ref,
            "object_name": object_ref.name,
            "session_uid": int(object_ref.session_uid),
            "object_uuid": self._ensure_object_persistent_uuid(object_ref),
            "modifier_name": modifier.name,
            "physics_type": modifier.type,
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
            "override_settings": bool(node.override_settings),
            "free_before_bake": bool(node.free_before_bake),
            "disk_cache": bool(getattr(node, "disk_cache", False)),
        }

    def _collect_physics_settings_payloads(self, node):
        payloads = []
        seen_by_path = {}
        linked_count = 0
        for socket in node.inputs:
            if getattr(socket, "bl_idname", "") != "AFSocketPropertyPackage":
                continue
            from_node, _from_socket = _find_single_from_input_socket(socket)
            if from_node is None:
                continue
            linked_count += 1
            package = self._get_output(from_node, "property_package", normalize=False)
            if package is None and from_node.bl_idname in self.DATA_NODE_TYPES:
                self._evaluate_data_node(from_node)
                package = self._get_output(from_node, "property_package", normalize=False)
            if package is None:
                raise FlowExecutionError(
                    "AF_E011",
                    f"{socket.name or 'Settings'} is not linked to Physics Bake Settings",
                    node.name,
                )
            for payload in self._physics_property_package_to_settings_payloads(package, node.name):
                path = str(payload["task_path"])
                existing = seen_by_path.get(path)
                if existing is None:
                    seen_by_path[path] = payload
                    payloads.append(payload)
                    continue
                same_settings = (
                    int(existing["frame_start"]) == int(payload["frame_start"])
                    and int(existing["frame_end"]) == int(payload["frame_end"])
                    and bool(existing.get("override_settings", True)) == bool(payload.get("override_settings", True))
                    and bool(existing["free_before_bake"]) == bool(payload["free_before_bake"])
                    and bool(existing.get("disk_cache", False)) == bool(payload.get("disk_cache", False))
                    and str(existing["physics_type"]) == str(payload["physics_type"])
                )
                if same_settings:
                    self.log("WARN", f"Duplicate Physics Bake Settings ignored: {path}", node.name)
                    continue
                raise FlowExecutionError("AF_E020", f"Conflicting Physics Bake Settings for '{path}'", node.name)
        if linked_count == 0:
            raise FlowExecutionError("AF_E011", "Physics Bake Task has no linked Physics Bake Settings inputs", node.name)
        return payloads

    def _build_physics_bake_all_task_ref(self, node):
        payloads = self._collect_physics_settings_payloads(node)
        if bool(getattr(node, "free_before_bake", False)):
            payloads = [
                {
                    **item,
                    "free_before_bake": True,
                }
                for item in payloads
            ]
        if bool(getattr(node, "disk_cache", False)):
            payloads = [
                {
                    **item,
                    "disk_cache": True,
                }
                for item in payloads
            ]
        if bool(getattr(node, "override_frame_range", False)):
            unified_frame_start = self._input_int(node, "Frame Start", int(self.scene.frame_start))
            unified_frame_end = self._input_int(node, "Frame End", int(self.scene.frame_end))
            payloads = [
                {
                    **item,
                    "frame_start": int(unified_frame_start),
                    "frame_end": int(unified_frame_end),
                }
                for item in payloads
            ]
        override_payloads = [item for item in payloads if bool(item.get("override_settings", True))]
        scene_frame_start = (
            min(int(item["frame_start"]) for item in override_payloads)
            if override_payloads
            else int(self.scene.frame_start)
        )
        scene_frame_end = (
            max(int(item["frame_end"]) for item in override_payloads)
            if override_payloads
            else int(self.scene.frame_end)
        )
        target_object_ids = sorted({int(item["session_uid"]) for item in payloads})
        task_ref = {
            "task_kind": TASK_KIND_PHYSICS_BAKE_ALL,
            "task_uid": str(uuid.uuid4()),
            "source_node": node.name,
            "tasks": payloads,
            "task_paths": [str(item["task_path"]) for item in payloads],
            "target_object_ids": target_object_ids,
            "override_settings": bool(override_payloads),
            "scene_frame_start": int(scene_frame_start),
            "scene_frame_end": int(scene_frame_end),
        }
        return self._embed_task_ref_status_payload(node, task_ref)


__all__ = ["RuntimeTaskRefsMixin"]
