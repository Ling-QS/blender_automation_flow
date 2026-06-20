import bpy

from ...runtime_core.constants import FLOW_OK, FlowExecutionError
from ...runtime_scene.objects import (
    _link_object_to_collection_safe,
    _obj_item,
    _remove_unused_object_data,
    _unlink_object_from_collection_safe,
)


class RuntimeObjectActionsMixin:
    def _execute_object_action_node(self, node, dry_run=False):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeCreateCollection":
            return self._execute_create_collection_node(node, dry_run=dry_run)
        if node_type == "AFNodeAddToCollection":
            return self._execute_add_to_collection_node(node, dry_run=dry_run)
        if node_type == "AFNodeCreateObject":
            return self._execute_create_object_node(node, dry_run=dry_run)
        if node_type == "AFNodeDuplicateObject":
            return self._execute_duplicate_object_node(node, dry_run=dry_run)
        if node_type == "AFNodeDeleteObject":
            return self._execute_delete_object_node(node, dry_run=dry_run)
        return None

    def _execute_create_collection_node(self, node, dry_run=False):
        collection_name = str(getattr(node, "collection_name", "") or "").strip()
        if not collection_name:
            raise FlowExecutionError("AF_E011", "Collection Name is empty", node.name)
        parent_collections = self._resolve_target_collections(node, "Parent Collections", "parent_collection", default_scene_root=True)
        parent_collection = parent_collections[0] if parent_collections else getattr(self.scene, "collection", None)
        existing = bpy.data.collections.get(collection_name) if bool(getattr(node, "reuse_existing", True)) else None
        collection = existing
        created = False
        if collection is None and not dry_run:
            collection = bpy.data.collections.new(collection_name)
            created = True
        if collection is not None and parent_collection is not None and not dry_run:
            try:
                if collection.name not in getattr(parent_collection.children, "keys", lambda: [])():
                    parent_collection.children.link(collection)
            except Exception:
                if collection not in list(parent_collection.children):
                    parent_collection.children.link(collection)
        payload_items = [{"id": int(collection.session_uid), "name": collection.name}] if collection is not None else []
        payload = {"items": payload_items, "count": len(payload_items)}
        self._set_output(node, "collection_list", payload)
        report = {
            "count": len(payload_items),
            "collection_name": collection.name if collection is not None else collection_name,
            "created": bool(created),
            "reused": bool(existing is not None),
            "parent_collection": str(getattr(parent_collection, "name", "") or ""),
            "dry_run": bool(dry_run),
        }
        self._set_output(node, "report", report)
        return FLOW_OK, report["collection_name"]

    def _execute_add_to_collection_node(self, node, dry_run=False):
        object_list = self._get_linked_output(node, "Object List", "object_list")
        if object_list is None:
            raise FlowExecutionError("AF_E011", "Object List input is not linked", node.name)
        target_collections = self._resolve_target_collections(node, "Collection List", "target_collection", default_scene_root=False)
        if not target_collections:
            raise FlowExecutionError("AF_E011", "Collection List input is not linked", node.name)
        link_mode = str(getattr(node, "link_mode", "LINK_ONLY") or "LINK_ONLY")
        linked_count = 0
        unlinked_count = 0
        output_items = []
        target_ids = {int(getattr(collection, "session_uid", 0) or 0) for collection in target_collections}
        for obj_item in list(object_list.get("items", [])):
            obj = self._find_object_by_item(obj_item)
            if obj is None:
                self._handle_missing_object_action(node, str(obj_item.get("name", "") or ""), "adding to collections")
                continue
            output_items.append(_obj_item(obj))
            if dry_run:
                continue
            for collection in target_collections:
                if _link_object_to_collection_safe(obj, collection):
                    linked_count += 1
            if link_mode == "MOVE_TO_ONLY":
                for collection in list(getattr(obj, "users_collection", ())):
                    collection_id = int(getattr(collection, "session_uid", 0) or 0)
                    if collection_id in target_ids:
                        continue
                    if _unlink_object_from_collection_safe(obj, collection):
                        unlinked_count += 1
        payload = {
            "items": self._dedup_obj_items(output_items, str(object_list.get("sort_mode", "NAME_ASC") or "NAME_ASC")),
            "count": len({int(item["id"]) for item in output_items}),
            "sort_mode": str(object_list.get("sort_mode", "NAME_ASC") or "NAME_ASC"),
        }
        self._set_output(node, "object_list", payload)
        report = {
            "count": int(payload["count"]),
            "collection_count": len(target_collections),
            "linked_count": int(linked_count),
            "unlinked_count": int(unlinked_count),
            "mode": link_mode,
            "dry_run": bool(dry_run),
        }
        self._set_output(node, "report", report)
        return FLOW_OK, report["count"]

    def _execute_create_object_node(self, node, dry_run=False):
        object_name = str(getattr(node, "object_name", "") or "").strip()
        if not object_name:
            raise FlowExecutionError("AF_E011", "Object Name is empty", node.name)
        object_type = str(getattr(node, "object_type", "EMPTY") or "EMPTY")
        target_collections = self._resolve_target_collections(node, "Collection List", "target_collection", default_scene_root=True)
        if not target_collections:
            raise FlowExecutionError("AF_E001", "Target collection is missing", node.name)
        created_object = None
        if not dry_run:
            object_data = None
            if object_type == "MESH":
                object_data = bpy.data.meshes.new(object_name)
            elif object_type == "CAMERA":
                object_data = bpy.data.cameras.new(object_name)
            elif object_type == "LIGHT":
                object_data = bpy.data.lights.new(object_name, type=str(getattr(node, "light_type", "POINT") or "POINT"))
            created_object = bpy.data.objects.new(object_name, object_data)
            for collection in target_collections:
                _link_object_to_collection_safe(created_object, collection)
        payload_items = [_obj_item(created_object)] if created_object is not None else []
        payload = {"items": payload_items, "count": len(payload_items), "sort_mode": "NAME_ASC"}
        self._set_output(node, "object_list", payload)
        report = {
            "count": len(payload_items),
            "object_name": str(getattr(created_object, "name", "") or object_name),
            "object_type": object_type,
            "collection_count": len(target_collections),
            "dry_run": bool(dry_run),
        }
        if object_type == "LIGHT":
            report["light_type"] = str(getattr(node, "light_type", "POINT") or "POINT")
        self._set_output(node, "report", report)
        return FLOW_OK, report["object_name"]

    def _execute_duplicate_object_node(self, node, dry_run=False):
        object_list = self._get_linked_output(node, "Object List", "object_list")
        if object_list is None:
            raise FlowExecutionError("AF_E011", "Object List input is not linked", node.name)
        explicit_target_collections = self._resolve_target_collections(node, "Collection List", "target_collection", default_scene_root=False)
        data_mode = str(getattr(node, "data_mode", "LINKED_DATA") or "LINKED_DATA")
        name_suffix = str(getattr(node, "name_suffix", "") or "")
        duplicate_copies = max(0, int(self._input_int(node, "Count", 1)))
        output_items = []
        duplicate_count = 0
        for obj_item in list(object_list.get("items", [])):
            obj = self._find_object_by_item(obj_item)
            if obj is None:
                self._handle_missing_object_action(node, str(obj_item.get("name", "") or ""), "duplicating")
                continue
            if duplicate_copies <= 0:
                continue
            if dry_run:
                duplicate_count += duplicate_copies
                continue
            for _duplicate_index in range(duplicate_copies):
                duplicate_object = obj.copy()
                if data_mode == "SINGLE_USER_DATA" and getattr(obj, "data", None) is not None:
                    try:
                        duplicate_object.data = obj.data.copy()
                    except Exception:
                        pass
                if name_suffix:
                    duplicate_object.name = f"{obj.name}{name_suffix}"
                    if data_mode == "SINGLE_USER_DATA" and getattr(duplicate_object, "data", None) is not None:
                        try:
                            duplicate_object.data.name = f"{getattr(obj.data, 'name', duplicate_object.data.name)}{name_suffix}"
                        except Exception:
                            pass
                target_collections = list(explicit_target_collections)
                if not target_collections:
                    target_collections = list(getattr(obj, "users_collection", ()))
                if not target_collections and self.scene is not None and getattr(self.scene, "collection", None) is not None:
                    target_collections = [self.scene.collection]
                for collection in target_collections:
                    _link_object_to_collection_safe(duplicate_object, collection)
                output_items.append(_obj_item(duplicate_object))
                duplicate_count += 1
        payload = {"items": self._dedup_obj_items(output_items, "NAME_ASC"), "count": len(output_items), "sort_mode": "NAME_ASC"}
        self._set_output(node, "object_list", payload)
        report = {
            "count": int(duplicate_count),
            "copies_per_object": int(duplicate_copies),
            "data_mode": data_mode,
            "dry_run": bool(dry_run),
            "collection_override_count": len(explicit_target_collections),
        }
        self._set_output(node, "report", report)
        return FLOW_OK, report["count"]

    def _execute_delete_object_node(self, node, dry_run=False):
        object_list = self._get_linked_output(node, "Object List", "object_list")
        if object_list is None:
            raise FlowExecutionError("AF_E011", "Object List input is not linked", node.name)
        deleted_count = 0
        removed_data_count = 0
        for obj_item in list(object_list.get("items", [])):
            obj = self._find_object_by_item(obj_item)
            if obj is None:
                self._handle_missing_object_action(node, str(obj_item.get("name", "") or ""), "deleting")
                continue
            if dry_run:
                deleted_count += 1
                continue
            object_data = getattr(obj, "data", None)
            bpy.data.objects.remove(obj, do_unlink=True)
            deleted_count += 1
            if bool(getattr(node, "delete_data_if_orphaned", False)) and _remove_unused_object_data(object_data):
                removed_data_count += 1
        report = {
            "count": int(deleted_count),
            "removed_data_count": int(removed_data_count),
            "dry_run": bool(dry_run),
        }
        self._set_output(node, "report", report)
        return FLOW_OK, report["count"]


__all__ = ["RuntimeObjectActionsMixin"]
