from ...runtime_flow.helpers import _socket_specific_output_key
from ...runtime_core.constants import FlowExecutionError
from ...runtime_math.values import _identity_rotation_payload
from ...runtime_scene.objects import (
    _collect_direct_task_dependency_objects,
    _collect_task_dependency_objects,
    _iter_collection_objects,
    _iter_scene_objects,
)
from ...runtime_task_ref import (
    _dedup_obj_items,
    _find_object_by_item,
    _obj_item,
)


class RuntimeSceneDataMixin:
    def _evaluate_scene_data_node(self, node, node_type):
        if node_type == "AFNodeCollectionList":
            base = []
            if node.target_collection is not None:
                base.append({"id": int(node.target_collection.session_uid), "name": node.target_collection.name})
            add_payload = self._get_linked_output(node, "Add Collections", "collection_list")
            if add_payload:
                base.extend(add_payload.get("items", []))
            remove_payload = self._get_linked_output(node, "Remove Collections", "collection_list")
            remove_ids = {int(item["id"]) for item in (remove_payload.get("items", []) if remove_payload else [])}
            merged = {}
            for item in base:
                merged[int(item["id"])] = {"id": int(item["id"]), "name": item["name"]}
            for rid in remove_ids:
                merged.pop(rid, None)
            items = sorted(merged.values(), key=lambda x: x["name"])
            payload = {"items": items, "count": len(items)}
            self._set_output(node, "collection_list", payload)
            self._set_output(node, "report", {"count": len(items)})
            return True

        if node_type == "AFNodeCollectionExpand":
            collections = []
            linked_payload = self._get_linked_output(node, "Collection List", "collection_list")
            if linked_payload:
                collections.extend(self._resolve_collection_items(linked_payload))
            elif node.target_collection is not None:
                collections.append(node.target_collection)

            obj_items = []
            for collection in collections:
                objects = _iter_collection_objects(
                    collection,
                    recursive=node.recursive_collections,
                    include_hidden=node.include_hidden_objects,
                    object_type_filter=node.object_type_filter,
                )
                obj_items.extend(_obj_item(obj) for obj in objects)
            deduped = _dedup_obj_items(obj_items, node.sort_mode)
            payload = {"items": deduped, "count": len(deduped), "sort_mode": node.sort_mode}
            self._set_output(node, "object_list", payload)
            self._set_output(node, "report", {"count": len(deduped)})
            if len(deduped) == 0:
                self.log("WARN", "AF_E012: Collection Expand produced an empty object list", node.name)
            return True

        if node_type == "AFNodeObjectList":
            items = []
            base_payload = self._get_linked_output(node, "Base Objects", "object_list")
            add_payload = self._get_linked_output(node, "Add Objects", "object_list")
            remove_payload = self._get_linked_output(node, "Remove Objects", "object_list")
            if base_payload:
                items.extend(base_payload.get("items", []))
            if add_payload:
                items.extend(add_payload.get("items", []))

            dedup = {int(item["id"]): {"id": int(item["id"]), "name": item["name"]} for item in items}
            remove_ids = {int(item["id"]) for item in (remove_payload.get("items", []) if remove_payload else [])}
            for rid in remove_ids:
                dedup.pop(rid, None)
            final_items = list(dedup.values())
            final_items.sort(key=lambda x: x["name"], reverse=(node.sort_mode == "NAME_DESC"))
            payload = {"items": final_items, "count": len(final_items), "sort_mode": node.sort_mode}
            self._set_output(node, "object_list", payload)
            self._set_output(node, "report", {"count": len(final_items)})
            if len(final_items) == 0:
                self.log("WARN", "AF_E012: Object List result is empty", node.name)
            return True

        if node_type == "AFNodePlaybackState":
            playback_state = self._playback_state_snapshot()
            self._set_output_socket_value(node, "Playing", bool(playback_state.get("playing", False)))
            self._set_output_socket_value(node, "On Play", bool(playback_state.get("on_play", False)))
            self._set_output_socket_value(node, "On Pause", bool(playback_state.get("on_pause", False)))
            self._set_output(
                node,
                "report",
                {
                    "playing": bool(playback_state.get("playing", False)),
                    "on_play": bool(playback_state.get("on_play", False)),
                    "on_pause": bool(playback_state.get("on_pause", False)),
                },
            )
            return True

        if node_type == "AFNodeSceneObjectList":
            scene_ref = node.target_scene if node.target_scene is not None else self.scene
            objects = _iter_scene_objects(
                scene_ref,
                recursive=node.recursive_collections,
                include_hidden=node.include_hidden_objects,
                object_type_filter=node.object_type_filter,
            )
            obj_items = [_obj_item(obj) for obj in objects]
            deduped = _dedup_obj_items(obj_items, node.sort_mode)
            payload = {"items": deduped, "count": len(deduped), "sort_mode": node.sort_mode}
            self._set_output(node, "object_list", payload)
            self._set_output(node, "report", {"count": len(deduped), "scene": scene_ref.name if scene_ref else ""})
            if len(deduped) == 0:
                self.log("WARN", "AF_E012: Scene Object List produced an empty object list", node.name)
            return True

        if node_type == "AFNodeObjectInfo":
            target_object = getattr(node, "target_object", None)
            object_items = [_obj_item(target_object)] if target_object is not None else []
            payload = {"items": object_items, "count": len(object_items), "sort_mode": "NAME_ASC"}
            self._set_output(node, "object_list", payload)
            self._set_output_socket_value(
                node,
                "Location",
                tuple(float(component) for component in getattr(target_object, "location", (0.0, 0.0, 0.0)))
                if target_object is not None
                else (0.0, 0.0, 0.0),
            )
            self._set_output_socket_value(
                node,
                "Rotation",
                self._capture_object_rotation_value(target_object)
                if target_object is not None
                else _identity_rotation_payload(),
            )
            self._set_output_socket_value(
                node,
                "Scale",
                tuple(float(component) for component in getattr(target_object, "scale", (1.0, 1.0, 1.0)))
                if target_object is not None
                else (1.0, 1.0, 1.0),
            )
            self._set_output(
                node,
                "report",
                {
                    "count": int(payload["count"]),
                    "has_object": bool(target_object is not None),
                    "object_name": str(getattr(target_object, "name", "") or ""),
                },
            )
            return True

        if node_type == "AFNodeSceneTime":
            scene = getattr(self, "scene", None)
            frame = 0.0
            seconds = 0.0
            if scene is not None:
                frame = float(getattr(scene, "frame_current", 0)) + float(getattr(scene, "frame_subframe", 0.0))
                render = getattr(scene, "render", None)
                fps = float(getattr(render, "fps", 24.0) or 24.0) if render is not None else 24.0
                fps_base = float(getattr(render, "fps_base", 1.0) or 1.0) if render is not None else 1.0
                effective_fps = fps / fps_base if abs(fps_base) > 1e-8 else fps
                if abs(effective_fps) > 1e-8:
                    seconds = frame / effective_fps
            seconds_socket = getattr(getattr(node, "outputs", None), "get", lambda _name: None)("Seconds")
            frame_socket = getattr(getattr(node, "outputs", None), "get", lambda _name: None)("Frame")
            seconds_key = _socket_specific_output_key(seconds_socket)
            frame_key = _socket_specific_output_key(frame_socket)
            if seconds_key:
                self._set_output(node, seconds_key, float(seconds))
            if frame_key:
                self._set_output(node, frame_key, float(frame))
            return True

        if node_type == "AFNodeEvaluateTaskDependencies":
            input_payload = self._get_linked_output(node, "Object List", "object_list")
            if input_payload is None:
                raise FlowExecutionError("AF_E011", "Object List input is not linked", node.name)

            task_objects = []
            seen_ids = set()
            for obj_item in input_payload.get("items", []):
                obj = _find_object_by_item(obj_item)
                if obj is None:
                    continue
                obj_id = int(obj.session_uid)
                if obj_id in seen_ids:
                    continue
                seen_ids.add(obj_id)
                task_objects.append(obj)

            obj_items = []
            for task_object in task_objects:
                if node.dependency_scope == "FULL_CLOSURE":
                    deps = _collect_task_dependency_objects(task_object, node.dependency_strategy)
                else:
                    deps = _collect_direct_task_dependency_objects(task_object, node.dependency_strategy)
                obj_items.extend(_obj_item(obj) for obj in deps)
                if node.include_self:
                    obj_items.append(_obj_item(task_object))

            source_task_ref = input_payload.get("_source_task_ref") if isinstance(input_payload, dict) else None
            procedural_dep_objects = self._collect_property_package_bake_read_geometry_dependency_objects(source_task_ref)
            for procedural_obj in procedural_dep_objects:
                if procedural_obj is None:
                    continue
                if node.dependency_scope == "FULL_CLOSURE":
                    deps = _collect_task_dependency_objects(procedural_obj, node.dependency_strategy)
                    obj_items.extend(_obj_item(obj) for obj in deps)
                else:
                    obj_items.append(_obj_item(procedural_obj))

            if not node.include_self and task_objects:
                task_ids = {int(task_object.session_uid) for task_object in task_objects}
                obj_items = [item for item in obj_items if int(item["id"]) not in task_ids]

            final_items = _dedup_obj_items(obj_items, "NAME_ASC")
            payload = {"items": final_items, "count": len(final_items), "sort_mode": "NAME_ASC"}
            self._set_output(node, "object_list", payload)
            self._set_output(
                node,
                "report",
                {
                    "input_object_count": len(task_objects),
                    "dependency_object_count": len(
                        _dedup_obj_items(
                            [
                                item
                                for item in obj_items
                                if int(item["id"]) not in {int(task_object.session_uid) for task_object in task_objects}
                            ],
                            "NAME_ASC",
                        )
                    ),
                    "count": len(final_items),
                    "output_object_count": len(final_items),
                },
            )
            if len(final_items) == 0:
                self.log("WARN", "AF_E012: Dependency object list is empty", node.name)
            return True

        return False


__all__ = ["RuntimeSceneDataMixin"]
