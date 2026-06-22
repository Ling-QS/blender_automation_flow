import bpy

from ...runtime_core.constants import (
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_BAKE_ASSET_ID,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_END,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_START,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_NODE_NAME,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_START_NODE_NAME,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_START_TREE_NAME,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_TASK_KIND,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_TREE_NAME,
    FlowExecutionError,
    OBJECT_PERSISTENT_UUID_PROP,
    PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
    PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
    PROPERTY_PACKAGE_ROLE_COMPOSITE,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    PROPERTY_SCOPE_KIND_MIXED,
    TASK_KIND_PROPERTY_PACKAGE_BAKE,
)
from ...runtime_refs.objects import _obj_item
from ...runtime_property.definitions import (
    _clone_property_definition,
    _iter_property_definition_entries,
    _make_empty_property_definition,
    _normalize_property_definition_entries,
    _sanitize_reusable_property_definition,
    _validate_property_definition,
)
from ...runtime_property.packages import (
    _clone_property_package,
    _is_composite_property_package,
    _iter_property_package_entries,
    _property_package_to_definition,
    _validate_property_package,
)
from ...runtime_persistence.serialization import _ensure_object_persistent_uuid
from ...runtime_state.cache import (
    _property_package_bake_action_name_from_task_ref,
    _property_package_bake_slot_display_name,
    _find_property_package_bake_action_by_identifier,
)


class RuntimePropertyPackageBakeRecordMixin:
    def _collect_af_tree_hierarchy(self, root_tree):
        collected = []
        pending = [root_tree]
        seen = set()
        while pending:
            node_tree = pending.pop()
            if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
                continue
            tree_name = str(getattr(node_tree, "name", "") or "")
            if not tree_name or tree_name in seen:
                continue
            seen.add(tree_name)
            collected.append(node_tree)
            for node in getattr(node_tree, "nodes", []):
                if getattr(node, "bl_idname", "") != "AFNodeGroup":
                    continue
                group_tree = getattr(node, "group_tree", None)
                if group_tree is not None and getattr(group_tree, "bl_idname", "") == "AFNodeTreeType":
                    pending.append(group_tree)
        return collected

    def _property_package_bake_record_obj_item(self, obj):
        return _obj_item(obj, lambda object_ref: _ensure_object_persistent_uuid(object_ref, OBJECT_PERSISTENT_UUID_PROP))

    def _iter_property_package_entries_for_record(self, property_package, node_name):
        return _iter_property_package_entries(
            property_package,
            node_name,
            allow_roles={PROPERTY_PACKAGE_ROLE_SNAPSHOT, PROPERTY_PACKAGE_ROLE_TARGET},
            allow_scopes={PROPERTY_PACKAGE_SCOPE_MODIFIER, PROPERTY_PACKAGE_SCOPE_OBJECT},
            validate_property_package=lambda package, owner_name: _validate_property_package(
                package,
                owner_name,
                allow_roles=None,
                allow_scopes=None,
                flow_execution_error_cls=FlowExecutionError,
                property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
            ),
            is_composite_property_package=lambda package: _is_composite_property_package(package, PROPERTY_PACKAGE_ROLE_COMPOSITE),
            clone_property_package=_clone_property_package,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _find_property_package_bake_action(self, bake_asset_id, action_name):
        return _find_property_package_bake_action_by_identifier(bake_asset_id, action_name)

    def _clear_property_package_bake_action_contents(self, action):
        if action is None:
            return
        try:
            while len(action.layers) > 0:
                action.layers.remove(action.layers[0])
        except Exception:
            pass
        try:
            while len(action.slots) > 0:
                action.slots.remove(action.slots[0])
        except Exception:
            pass

    def _ensure_property_package_bake_action_layer(self, action):
        if action is None:
            return None
        layer = action.layers[0] if len(action.layers) > 0 else action.layers.new("Property Package Bake")
        if len(layer.strips) == 0:
            layer.strips.new(type="KEYFRAME")
        return layer

    def _tag_property_package_bake_action(self, action, task_ref):
        if action is None:
            return
        action.name = str(task_ref.get("action_name", action.name) or action.name)
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_TASK_KIND] = TASK_KIND_PROPERTY_PACKAGE_BAKE
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_BAKE_ASSET_ID] = str(task_ref.get("bake_asset_id", "") or "")
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_TREE_NAME] = str(task_ref.get("source_tree_name", "") or "")
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_NODE_NAME] = str(task_ref.get("source_node", "") or "")
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_START_TREE_NAME] = str(task_ref.get("start_tree_name", "") or "")
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_START_NODE_NAME] = str(task_ref.get("start_node_name", "") or "")
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_START] = int(task_ref.get("frame_start", 1) or 1)
        action[PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_END] = int(task_ref.get("frame_end", action.get(PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_START, 1)) or action.get(PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_START, 1))

    def _ensure_property_package_bake_action(self, task_ref, clear_existing=False):
        action_name = _property_package_bake_action_name_from_task_ref(task_ref)
        bake_asset_id = str(task_ref.get("bake_asset_id", "") or "").strip()
        action = self._find_property_package_bake_action(bake_asset_id, action_name)
        if action is None:
            action = bpy.data.actions.new(action_name)
        elif clear_existing:
            self._clear_property_package_bake_action_contents(action)
        self._tag_property_package_bake_action(action, {**dict(task_ref), "action_name": action_name})
        self._ensure_property_package_bake_action_layer(action)
        return action

    def _ensure_property_package_bake_action_slot(self, action, obj):
        if action is None or obj is None:
            return None
        expected_identifier = f"OB{_property_package_bake_slot_display_name(obj)}"
        for slot in action.slots:
            if str(getattr(slot, "identifier", "") or "") == expected_identifier:
                return slot
        return action.slots.new("OBJECT", _property_package_bake_slot_display_name(obj))

    def _ensure_property_package_bake_binding(self, obj, action):
        if obj is None or action is None:
            return None
        self._ensure_property_package_bake_action_layer(action)
        anim_data = obj.animation_data_create()
        slot = self._ensure_property_package_bake_action_slot(action, obj)
        anim_data.action = action
        try:
            anim_data.action_slot = slot
        except Exception:
            pass
        return slot

    def _keyframe_insert_safe(self, target, data_path, frame, node):
        try:
            return bool(target.keyframe_insert(data_path=data_path, frame=float(frame)))
        except Exception as exc:
            self.log("WARN", f"Keyframe insert failed for '{data_path}': {exc}", node.name)
            return False

    def _rotation_data_path_for_object(self, obj):
        mode = str(getattr(obj, "rotation_mode", "XYZ") or "XYZ") if obj is not None else "XYZ"
        if mode == "QUATERNION":
            return "rotation_quaternion"
        if mode == "AXIS_ANGLE":
            return "rotation_axis_angle"
        return "rotation_euler"

    def _record_property_package_current_frame(self, node, property_package, frame):
        bake_context = self.property_package_bake_context if isinstance(self.property_package_bake_context, dict) else None
        shared_action = bake_context.get("shared_action") if isinstance(bake_context, dict) else None
        package_entries = self._iter_property_package_entries_for_record(property_package, node.name)
        key_insert_count = 0
        touched_ids = set()
        package_roles = []
        scope_kinds = []

        for entry in package_entries:
            package_roles.append(str(entry.get("package_role", "")))
            scope_kind = str(entry.get("scope_kind", "") or "")
            scope_kinds.append(scope_kind)
            items = list(entry.get("items", []))
            if scope_kind == PROPERTY_PACKAGE_SCOPE_OBJECT:
                definition = self._property_package_to_definition_for_record(entry, node.name)
                definition_kind = str(definition.get("definition_kind", "") or "")
                selected_properties = {
                    str(property_name)
                    for property_name, enabled in dict(definition.get("properties", {}) or {}).items()
                    if bool(enabled)
                }
                for item in items:
                    obj = self._find_object_by_item_cached({"id": int(item["object_id"]), "name": str(item["object_name"])})
                    if obj is None:
                        self._handle_missing_object_action(node, str(item.get("object_name", "") or ""), "recording property package")
                        continue
                    if shared_action is not None:
                        self._ensure_property_package_bake_binding(obj, shared_action)
                    touched_ids.add(int(item["object_id"]))
                    if bake_context is not None:
                        bake_context.setdefault("touched_object_items", {})[int(item["object_id"])] = self._property_package_bake_record_obj_item(obj)
                        component_path = str(item.get("component_path", "") or "").strip()
                        if component_path:
                            bake_context.setdefault("touched_component_paths", set()).add(component_path)
                    props = dict(item.get("properties", {}) or {})
                    if definition_kind == PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY:
                        display_keys = (
                            "hide_viewport",
                            "hide_render",
                            "show_in_front",
                            "show_name",
                            "show_axis",
                            "display_type",
                        )
                        for key in display_keys:
                            if key not in selected_properties or key not in props or not hasattr(obj, key):
                                continue
                            setattr(obj, key, props[key])
                            if self._keyframe_insert_safe(obj, key, frame, node):
                                key_insert_count += 1
                    elif definition_kind == PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM:
                        if "location" in selected_properties and "location" in props and hasattr(obj, "location"):
                            obj.location = list(props["location"])[:3]
                            if self._keyframe_insert_safe(obj, "location", frame, node):
                                key_insert_count += 1
                        if "rotation_mode" in selected_properties and "rotation_mode" in props and hasattr(obj, "rotation_mode"):
                            obj.rotation_mode = str(props["rotation_mode"])
                            if self._keyframe_insert_safe(obj, "rotation_mode", frame, node):
                                key_insert_count += 1
                        if "rotation" in selected_properties and "rotation" in props:
                            self._apply_object_rotation_value(obj, props["rotation"], dry_run=False)
                            if self._keyframe_insert_safe(obj, self._rotation_data_path_for_object(obj), frame, node):
                                key_insert_count += 1
                        if "scale" in selected_properties and "scale" in props and hasattr(obj, "scale"):
                            obj.scale = list(props["scale"])[:3]
                            if self._keyframe_insert_safe(obj, "scale", frame, node):
                                key_insert_count += 1
            elif scope_kind == PROPERTY_PACKAGE_SCOPE_MODIFIER:
                definition = self._property_package_to_definition_for_record(entry, node.name)
                selected_properties = {
                    str(property_name)
                    for property_name, enabled in dict(definition.get("properties", {}) or {}).items()
                    if bool(enabled)
                }
                for item in items:
                    obj = self._find_object_by_item_cached({"id": int(item["object_id"]), "name": str(item["object_name"])})
                    if obj is None:
                        self._handle_missing_object_action(node, str(item.get("object_name", "") or ""), "recording property package")
                        continue
                    if shared_action is not None:
                        self._ensure_property_package_bake_binding(obj, shared_action)
                    touched_ids.add(int(item["object_id"]))
                    if bake_context is not None:
                        bake_context.setdefault("touched_object_items", {})[int(item["object_id"])] = self._property_package_bake_record_obj_item(obj)
                        component_path = str(item.get("component_path", "") or "").strip()
                        if component_path:
                            bake_context.setdefault("touched_component_paths", set()).add(component_path)
                    modifier = getattr(obj, "modifiers", None).get(str(item.get("component_name", "") or "")) if getattr(obj, "modifiers", None) is not None else None
                    if modifier is None:
                        if str(getattr(node, "missing_policy", "WARN_AND_SKIP") or "WARN_AND_SKIP") == "FAIL":
                            raise FlowExecutionError("AF_E008", f"Modifier '{str(item.get('component_name', '') or '')}' missing on '{obj.name}'", node.name)
                        self.log("WARN", f"Modifier '{str(item.get('component_name', '') or '')}' missing on '{obj.name}', skipping", node.name)
                        continue
                    props = dict(item.get("properties", {}) or {})
                    for key in ("show_viewport", "show_render", "show_in_editmode"):
                        if key not in selected_properties or key not in props or not hasattr(modifier, key):
                            continue
                        setattr(modifier, key, bool(props[key]))
                        if self._keyframe_insert_safe(modifier, key, frame, node):
                            key_insert_count += 1

        return {
            "package_role": (
                PROPERTY_PACKAGE_ROLE_COMPOSITE
                if len({role for role in package_roles if role}) > 1
                else next((role for role in package_roles if role), str(property_package.get("package_role", "")))
            ),
            "scope_kind": (
                PROPERTY_SCOPE_KIND_MIXED
                if len({kind for kind in scope_kinds if kind}) > 1
                else next((kind for kind in scope_kinds if kind), str(property_package.get("scope_kind", "")))
            ),
            "count": int(key_insert_count),
            "object_count": int(len(touched_ids)),
            "frame": int(frame),
            "recorded": True,
            "action_name": str(getattr(shared_action, "name", "") or ""),
        }

    def _property_package_to_definition_for_record(self, entry, node_name):
        return _property_package_to_definition(
            entry,
            node_name,
            validate_property_package=lambda package, owner_name: _validate_property_package(
                package,
                owner_name,
                flow_execution_error_cls=FlowExecutionError,
                property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
            ),
            is_composite_property_package=lambda package: _is_composite_property_package(package, PROPERTY_PACKAGE_ROLE_COMPOSITE),
            iter_property_definition_entries=_iter_property_definition_entries,
            normalize_property_definition_entries=_normalize_property_definition_entries,
            make_empty_property_definition=_make_empty_property_definition,
            clone_property_definition=_clone_property_definition,
            sanitize_reusable_property_definition=_sanitize_reusable_property_definition,
            validate_property_definition=_validate_property_definition,
        )


__all__ = ["RuntimePropertyPackageBakeRecordMixin"]
