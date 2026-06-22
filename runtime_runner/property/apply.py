import uuid

from ...runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_ASSIGNMENT_KIND_MODIFIER,
    PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
    PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
    PROPERTY_DEFINITION_KIND_MODIFIER,
    PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
    PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
    PROPERTY_PACKAGE_ROLE_COMPOSITE,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    PROPERTY_SCOPE_KIND_MIXED,
    PROPERTY_SOURCE_CURRENT,
    PROPERTY_SOURCE_VALUE,
)
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_refs.objects import (
    _build_allowed_object_identity_filter,
    _property_package_item_matches_allowed_objects,
    _property_package_object_identity,
)
from ...runtime_property.definitions import (
    _iter_property_assignment_entries,
    _iter_property_definition_entries,
    _matches_modifier_filters,
    _modifier_filter_settings_from_node,
    _property_definition_signature,
    _validate_property_assignment,
    _validate_property_definition,
)
from ...runtime_scene.objects import _object_reference_identity


class RuntimePropertyApplyMixin:
    def _property_apply_allowed_object_filter(self, object_items):
        return _build_allowed_object_identity_filter(
            object_items,
            object_resolver=self._find_object_by_item_cached,
            object_reference_identity=_object_reference_identity,
        )

    def _property_apply_item_matches_allowed_objects(self, item, allowed_filter):
        return _property_package_item_matches_allowed_objects(
            item,
            allowed_filter,
            object_resolver=self._find_object_by_item_cached,
            property_package_object_identity=lambda payload, object_resolver=None: _property_package_object_identity(
                payload,
                object_resolver=object_resolver,
                object_reference_identity=_object_reference_identity,
            ),
        )

    def _property_package_apply_is_lenient(self, node):
        return str(getattr(node, "bl_idname", "") or "") == "AFNodeApplyObjectProperties"

    def _handle_property_package_missing_object(self, node, object_name):
        if self._property_package_apply_is_lenient(node):
            return False
        if str(getattr(node, "missing_policy", "WARN_AND_SKIP") or "WARN_AND_SKIP") == "FAIL":
            raise FlowExecutionError("AF_E008", f"Object '{object_name}' missing", node.name)
        self.log("WARN", f"Object '{object_name}' missing, skipping", node.name)
        return False

    def _handle_property_package_missing_modifier(self, node, object_name, modifier_name):
        if self._property_package_apply_is_lenient(node):
            return False
        if str(getattr(node, "missing_policy", "WARN_AND_SKIP") or "WARN_AND_SKIP") == "FAIL":
            raise FlowExecutionError("AF_E008", f"Modifier '{modifier_name}' missing on '{object_name}'", node.name)
        self.log("WARN", f"Modifier '{modifier_name}' missing on '{object_name}', skipping", node.name)
        return False

    def _apply_property_assignment_entry_direct(self, node, property_assignment, obj, obj_item, source_node=None, source_socket=None, dry_run=False):
        property_assignment = _validate_property_assignment(
            property_assignment,
            node.name,
            allow_kinds={
                PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            },
        )
        plan = self._compile_property_assignment_plan(property_assignment, node.name)
        assignment_kind = str(plan["assignment_kind"])
        package_role = str(plan["package_role"])
        applied_count = 0
        applied_scope_kinds = []

        if assignment_kind == PROPERTY_ASSIGNMENT_KIND_MODIFIER:
            modifier_filter = str(plan["modifier_filter"])
            modifier_name_filter = str(plan.get("modifier_name_filter", "") or "")
            modifier_name_match_mode = str(plan.get("modifier_name_match_mode", "EXACT") or "EXACT")
            matching_modifiers = [
                modifier
                for modifier in getattr(obj, "modifiers", [])
                if _matches_modifier_filters(modifier, modifier_filter, modifier_name_filter, modifier_name_match_mode)
            ]
            base_context = dict(self.current_property_context or {}) if isinstance(self.current_property_context, dict) else self.current_property_context
            object_index = int(base_context.get("object_index", 0) if isinstance(base_context, dict) else 0)
            object_count = int(base_context.get("object_count", 0) if isinstance(base_context, dict) else 0)
            object_items = base_context.get("object_items", []) if isinstance(base_context, dict) else []
            try:
                for component_index, modifier in enumerate(matching_modifiers):
                    evaluated_plan = plan
                    if source_node is not None and source_socket is not None:
                        self.current_property_context = self._make_modifier_property_context(
                            obj_item,
                            obj,
                            object_index,
                            object_count,
                            modifier,
                            component_index,
                            len(matching_modifiers),
                            object_items,
                            copy_payload=False,
                        )
                        evaluated_assignment = self._resolve_property_assignment_entry_for_source(
                            source_node,
                            source_socket,
                            property_assignment,
                            node.name,
                        )
                        evaluated_plan = self._compile_property_assignment_plan(evaluated_assignment, node.name)
                    if bool(evaluated_plan.get("filter_by_context", False)) and not bool(evaluated_plan.get("context_filter_passed", True)):
                        continue
                    evaluated_properties_map = dict(evaluated_plan["properties_map"])
                    evaluated_sources_map = dict(evaluated_plan["sources_map"])
                    evaluated_values_map = dict(evaluated_plan["values_map"])
                    changed = False
                    if bool(evaluated_properties_map.get("show_viewport", False)) and hasattr(modifier, "show_viewport"):
                        source = str(evaluated_sources_map.get("show_viewport", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                        target_value = bool(modifier.show_viewport) if source == PROPERTY_SOURCE_CURRENT else bool(evaluated_values_map["show_viewport"])
                        if bool(getattr(modifier, "show_viewport", False)) != target_value:
                            changed = True
                            if not dry_run:
                                modifier.show_viewport = target_value
                    if bool(evaluated_properties_map.get("show_render", False)) and hasattr(modifier, "show_render"):
                        source = str(evaluated_sources_map.get("show_render", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                        target_value = bool(modifier.show_render) if source == PROPERTY_SOURCE_CURRENT else bool(evaluated_values_map["show_render"])
                        if bool(getattr(modifier, "show_render", False)) != target_value:
                            changed = True
                            if not dry_run:
                                modifier.show_render = target_value
                    if bool(evaluated_properties_map.get("show_in_editmode", False)) and hasattr(modifier, "show_in_editmode"):
                        source = str(evaluated_sources_map.get("show_in_editmode", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                        target_value = bool(modifier.show_in_editmode) if source == PROPERTY_SOURCE_CURRENT else bool(evaluated_values_map["show_in_editmode"])
                        if bool(getattr(modifier, "show_in_editmode", False)) != target_value:
                            changed = True
                            if not dry_run:
                                modifier.show_in_editmode = target_value
                    if changed:
                        applied_count += 1
                        applied_scope_kinds.append(PROPERTY_PACKAGE_SCOPE_MODIFIER)
            finally:
                self.current_property_context = base_context
            return {
                "package_role": package_role,
                "applied_count": int(applied_count),
                "scope_kinds": applied_scope_kinds,
            }

        properties_map = dict(plan["properties_map"])
        sources_map = dict(plan["sources_map"])
        values_map = dict(plan["values_map"])
        changed = False
        if assignment_kind == PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM:
            if bool(properties_map.get("location", False)) and hasattr(obj, "location"):
                source = str(sources_map.get("location", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = [float(value) for value in obj.location] if source == PROPERTY_SOURCE_CURRENT else values_map["location"]
                if not self._vector_prop_matches(obj.location, target_value):
                    changed = True
                    if not dry_run:
                        obj.location = list(target_value)[:3]
            if bool(properties_map.get("rotation_mode", False)) and hasattr(obj, "rotation_mode"):
                source = str(sources_map.get("rotation_mode", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_mode = str(getattr(obj, "rotation_mode", "XYZ") or "XYZ") if source == PROPERTY_SOURCE_CURRENT else str(values_map["rotation_mode"])
                if str(getattr(obj, "rotation_mode", "") or "") != target_mode:
                    changed = True
                    if not dry_run:
                        obj.rotation_mode = target_mode
            if bool(properties_map.get("rotation", False)):
                source = str(sources_map.get("rotation", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_rotation = self._capture_object_rotation_value(obj) if source == PROPERTY_SOURCE_CURRENT else values_map["rotation"]
                if not self._rotation_payload_matches_object(obj, target_rotation):
                    changed = True
                    self._apply_object_rotation_value(obj, target_rotation, dry_run=dry_run)
            if bool(properties_map.get("scale", False)) and hasattr(obj, "scale"):
                source = str(sources_map.get("scale", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = [float(value) for value in obj.scale] if source == PROPERTY_SOURCE_CURRENT else values_map["scale"]
                if not self._vector_prop_matches(obj.scale, target_value):
                    changed = True
                    if not dry_run:
                        obj.scale = list(target_value)[:3]
        else:
            if bool(properties_map.get("hide_viewport", False)) and hasattr(obj, "hide_viewport"):
                source = str(sources_map.get("hide_viewport", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = bool(obj.hide_viewport) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["hide_viewport"])
                if bool(getattr(obj, "hide_viewport", False)) != target_value:
                    changed = True
                    if not dry_run:
                        obj.hide_viewport = target_value
            if bool(properties_map.get("hide_render", False)) and hasattr(obj, "hide_render"):
                source = str(sources_map.get("hide_render", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = bool(obj.hide_render) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["hide_render"])
                if bool(getattr(obj, "hide_render", False)) != target_value:
                    changed = True
                    if not dry_run:
                        obj.hide_render = target_value
            if bool(properties_map.get("show_in_front", False)) and hasattr(obj, "show_in_front"):
                source = str(sources_map.get("show_in_front", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = bool(obj.show_in_front) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["show_in_front"])
                if bool(getattr(obj, "show_in_front", False)) != target_value:
                    changed = True
                    if not dry_run:
                        obj.show_in_front = target_value
            if bool(properties_map.get("show_name", False)) and hasattr(obj, "show_name"):
                source = str(sources_map.get("show_name", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = bool(obj.show_name) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["show_name"])
                if bool(getattr(obj, "show_name", False)) != target_value:
                    changed = True
                    if not dry_run:
                        obj.show_name = target_value
            if bool(properties_map.get("show_axis", False)) and hasattr(obj, "show_axis"):
                source = str(sources_map.get("show_axis", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = bool(obj.show_axis) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["show_axis"])
                if bool(getattr(obj, "show_axis", False)) != target_value:
                    changed = True
                    if not dry_run:
                        obj.show_axis = target_value
            if bool(properties_map.get("display_type", False)) and hasattr(obj, "display_type"):
                source = str(sources_map.get("display_type", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                target_value = str(obj.display_type) if source == PROPERTY_SOURCE_CURRENT else str(values_map["display_type"])
                if str(getattr(obj, "display_type", "") or "") != target_value:
                    changed = True
                    if not dry_run:
                        obj.display_type = target_value

        return {
            "package_role": package_role,
            "applied_count": 1 if changed else 0,
            "scope_kinds": ([PROPERTY_PACKAGE_SCOPE_OBJECT] if changed else []),
        }

    def _apply_object_properties_from_assignments_direct(self, node, object_list_payload, dry_run=False):
        linked_sources = []
        for socket in getattr(node, "inputs", []):
            if str(getattr(socket, "bl_idname", "") or "") != "AFSocketPropertyAssignment" or bool(getattr(socket, "af_is_virtual", False)):
                continue
            from_node, from_socket = _find_single_from_input_socket(socket)
            if from_node is None:
                continue
            linked_sources.append((from_node, from_socket))

        if not linked_sources:
            return {
                "package_role": "",
                "scope_kind": "",
                "count": 0,
                "no_properties": True,
                "direct_apply": True,
            }

        applied_count = 0
        package_roles = []
        scope_kinds = []
        previous_context = dict(self.current_property_context or {}) if isinstance(self.current_property_context, dict) else self.current_property_context
        try:
            object_items = list((object_list_payload or {}).get("items", []))
            object_count = len(object_items)
            for index, obj_item in enumerate(object_items):
                obj = self._find_object_by_item_cached(obj_item)
                if obj is None:
                    continue
                self.current_property_context = self._make_object_property_context(
                    obj_item,
                    obj,
                    index,
                    object_count,
                    object_items,
                    copy_payload=False,
                )
                for from_node, from_socket in linked_sources:
                    property_assignment = self._get_output_from_source(from_node, from_socket, "property_assignment")
                    if property_assignment is None:
                        continue
                    entries = _iter_property_assignment_entries(
                        property_assignment,
                        node.name,
                        allow_kinds={
                            PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                            PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                            PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
                        },
                    )
                    for entry in entries:
                        apply_result = self._apply_property_assignment_entry_direct(
                            node,
                            entry,
                            obj,
                            obj_item,
                            source_node=from_node,
                            source_socket=from_socket,
                            dry_run=dry_run,
                        )
                        package_roles.append(str(apply_result.get("package_role", "") or ""))
                        applied_count += int(apply_result.get("applied_count", 0) or 0)
                        scope_kinds.extend(list(apply_result.get("scope_kinds", []) or []))
        finally:
            self.current_property_context = previous_context

        return {
            "package_role": (
                PROPERTY_PACKAGE_ROLE_COMPOSITE
                if len({role for role in package_roles if role}) > 1
                else next((role for role in package_roles if role), "")
            ),
            "scope_kind": (
                PROPERTY_SCOPE_KIND_MIXED
                if len({kind for kind in scope_kinds if kind}) > 1
                else next((kind for kind in scope_kinds if kind), "")
            ),
            "count": int(applied_count),
            "no_properties": bool(applied_count == 0),
            "direct_apply": True,
        }

    def _apply_single_property_package(self, node, property_definition, property_package, object_list_payload, dry_run=False):
        property_definition = _validate_property_definition(
            property_definition,
            node.name,
            allow_kinds={PROPERTY_DEFINITION_KIND_MODIFIER, PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY, PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM},
        )
        definition_kind = str(property_definition.get("definition_kind", "") or "")
        allowed_scopes = (
            {PROPERTY_PACKAGE_SCOPE_MODIFIER}
            if definition_kind == PROPERTY_DEFINITION_KIND_MODIFIER
            else {PROPERTY_PACKAGE_SCOPE_OBJECT}
        )
        package = self._validate_property_package(
            property_package,
            node.name,
            allow_roles={PROPERTY_PACKAGE_ROLE_SNAPSHOT, PROPERTY_PACKAGE_ROLE_TARGET},
            allow_scopes=allowed_scopes,
        )
        selected_properties = tuple(
            property_name
            for property_name, enabled in dict(property_definition.get("properties", {})).items()
            if bool(enabled)
        )
        if definition_kind == PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY:
            allowed_object_filter = self._property_apply_allowed_object_filter((object_list_payload or {}).get("items", []))
            applied_count = 0
            matched_item_count = 0
            missing_object_count = 0
            for item in package.get("items", []):
                if not self._property_apply_item_matches_allowed_objects(item, allowed_object_filter):
                    continue
                matched_item_count += 1
                obj = self._find_object_by_item_cached({"id": item["object_id"], "name": item["object_name"]})
                if obj is None:
                    missing_object_count += 1
                    self._handle_property_package_missing_object(node, str(item["object_name"]))
                    continue
                props = dict(item.get("properties", {}))
                changed = False
                if "hide_viewport" in selected_properties and "hide_viewport" in props and hasattr(obj, "hide_viewport"):
                    target_value = bool(props["hide_viewport"])
                    if bool(getattr(obj, "hide_viewport", False)) != target_value:
                        changed = True
                        if not dry_run:
                            obj.hide_viewport = target_value
                if "hide_render" in selected_properties and "hide_render" in props and hasattr(obj, "hide_render"):
                    target_value = bool(props["hide_render"])
                    if bool(getattr(obj, "hide_render", False)) != target_value:
                        changed = True
                        if not dry_run:
                            obj.hide_render = target_value
                if "show_in_front" in selected_properties and "show_in_front" in props and hasattr(obj, "show_in_front"):
                    target_value = bool(props["show_in_front"])
                    if bool(getattr(obj, "show_in_front", False)) != target_value:
                        changed = True
                        if not dry_run:
                            obj.show_in_front = target_value
                if "show_name" in selected_properties and "show_name" in props and hasattr(obj, "show_name"):
                    target_value = bool(props["show_name"])
                    if bool(getattr(obj, "show_name", False)) != target_value:
                        changed = True
                        if not dry_run:
                            obj.show_name = target_value
                if "show_axis" in selected_properties and "show_axis" in props and hasattr(obj, "show_axis"):
                    target_value = bool(props["show_axis"])
                    if bool(getattr(obj, "show_axis", False)) != target_value:
                        changed = True
                        if not dry_run:
                            obj.show_axis = target_value
                if "display_type" in selected_properties and "display_type" in props and hasattr(obj, "display_type"):
                    target_value = str(props["display_type"])
                    if str(getattr(obj, "display_type", "") or "") != target_value:
                        changed = True
                        if not dry_run:
                            obj.display_type = target_value
                if changed:
                    applied_count += 1
            return {
                "package_role": str(package.get("package_role", "")),
                "scope_kind": str(package.get("scope_kind", "")),
                "count": applied_count,
                "matched_item_count": matched_item_count,
                "missing_object_count": missing_object_count,
                "missing_component_count": 0,
            }

        if definition_kind == PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM:
            allowed_object_filter = self._property_apply_allowed_object_filter((object_list_payload or {}).get("items", []))
            applied_count = 0
            matched_item_count = 0
            missing_object_count = 0
            for item in package.get("items", []):
                if not self._property_apply_item_matches_allowed_objects(item, allowed_object_filter):
                    continue
                matched_item_count += 1
                obj = self._find_object_by_item_cached({"id": item["object_id"], "name": item["object_name"]})
                if obj is None:
                    missing_object_count += 1
                    self._handle_property_package_missing_object(node, str(item["object_name"]))
                    continue
                props = dict(item.get("properties", {}))
                changed = False
                if "location" in selected_properties and "location" in props and hasattr(obj, "location"):
                    if not self._vector_prop_matches(obj.location, props["location"]):
                        changed = True
                        if not dry_run:
                            obj.location = list(props["location"])[:3]
                if "rotation_mode" in selected_properties and "rotation_mode" in props and hasattr(obj, "rotation_mode"):
                    target_mode = str(props["rotation_mode"])
                    if str(getattr(obj, "rotation_mode", "") or "") != target_mode:
                        changed = True
                        if not dry_run:
                            obj.rotation_mode = target_mode
                if "rotation" in selected_properties and "rotation" in props:
                    if not self._rotation_payload_matches_object(obj, props["rotation"]):
                        changed = True
                        self._apply_object_rotation_value(obj, props["rotation"], dry_run=dry_run)
                if "scale" in selected_properties and "scale" in props and hasattr(obj, "scale"):
                    if not self._vector_prop_matches(obj.scale, props["scale"]):
                        changed = True
                        if not dry_run:
                            obj.scale = list(props["scale"])[:3]
                if changed:
                    applied_count += 1
            return {
                "package_role": str(package.get("package_role", "")),
                "scope_kind": str(package.get("scope_kind", "")),
                "count": applied_count,
                "matched_item_count": matched_item_count,
                "missing_object_count": missing_object_count,
                "missing_component_count": 0,
            }

        allowed_object_filter = self._property_apply_allowed_object_filter((object_list_payload or {}).get("items", []))
        applied_count = 0
        matched_item_count = 0
        missing_object_count = 0
        missing_component_count = 0
        for item in package.get("items", []):
            if not self._property_apply_item_matches_allowed_objects(item, allowed_object_filter):
                continue
            matched_item_count += 1
            obj = self._find_object_by_item_cached({"id": item["object_id"], "name": item["object_name"]})
            if obj is None:
                missing_object_count += 1
                self._handle_property_package_missing_object(node, str(item["object_name"]))
                continue
            modifier_name = str(item.get("component_name", "") or "")
            modifier = obj.modifiers.get(modifier_name)
            if modifier is None:
                missing_component_count += 1
                self._handle_property_package_missing_modifier(node, str(obj.name), modifier_name)
                continue
            props = dict(item.get("properties", {}))
            changed = False
            if "show_viewport" in selected_properties and "show_viewport" in props and hasattr(modifier, "show_viewport"):
                target_value = bool(props["show_viewport"])
                if bool(getattr(modifier, "show_viewport", False)) != target_value:
                    changed = True
                    if not dry_run:
                        modifier.show_viewport = target_value
            if "show_render" in selected_properties and "show_render" in props and hasattr(modifier, "show_render"):
                target_value = bool(props["show_render"])
                if bool(getattr(modifier, "show_render", False)) != target_value:
                    changed = True
                    if not dry_run:
                        modifier.show_render = target_value
            if "show_in_editmode" in selected_properties and "show_in_editmode" in props and hasattr(modifier, "show_in_editmode"):
                target_value = bool(props["show_in_editmode"])
                if bool(getattr(modifier, "show_in_editmode", False)) != target_value:
                    changed = True
                    if not dry_run:
                        modifier.show_in_editmode = target_value
            if changed:
                applied_count += 1
        return {
            "package_role": str(package.get("package_role", "")),
            "scope_kind": str(package.get("scope_kind", "")),
            "count": applied_count,
            "matched_item_count": matched_item_count,
            "missing_object_count": missing_object_count,
            "missing_component_count": missing_component_count,
        }

    def _apply_property_package(self, node, property_definition, property_package, object_list_payload, dry_run=False):
        definition_entries = _iter_property_definition_entries(
            property_definition,
            node.name,
            allow_kinds={PROPERTY_DEFINITION_KIND_MODIFIER, PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY, PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM},
        )
        if not definition_entries:
            return {
                "package_role": str(property_package.get("package_role", "")),
                "scope_kind": str(property_package.get("scope_kind", "")),
                "count": 0,
                "no_properties": True,
            }
        package_entries = self._iter_property_package_entries_for_actions(
            property_package,
            node.name,
            allow_roles={PROPERTY_PACKAGE_ROLE_SNAPSHOT, PROPERTY_PACKAGE_ROLE_TARGET},
            allow_scopes={PROPERTY_PACKAGE_SCOPE_MODIFIER, PROPERTY_PACKAGE_SCOPE_OBJECT},
        )
        definition_map = {_property_definition_signature(entry): entry for entry in definition_entries}
        total_count = 0
        matched_item_count = 0
        missing_object_count = 0
        missing_component_count = 0
        package_roles = []
        scope_kinds = []
        for entry in package_entries:
            package_definition = self._property_package_to_definition_for_actions(entry, node.name)
            match = definition_map.get(_property_definition_signature(package_definition))
            if match is None:
                continue
            entry_report = self._apply_single_property_package(node, match, entry, object_list_payload, dry_run=dry_run)
            total_count += int(entry_report.get("count", 0))
            matched_item_count += int(entry_report.get("matched_item_count", 0) or 0)
            missing_object_count += int(entry_report.get("missing_object_count", 0) or 0)
            missing_component_count += int(entry_report.get("missing_component_count", 0) or 0)
            package_roles.append(str(entry_report.get("package_role", "")))
            scope_kinds.append(str(entry_report.get("scope_kind", "")))
        return {
            "package_role": (
                PROPERTY_PACKAGE_ROLE_COMPOSITE
                if len(set(package_roles)) > 1
                else (package_roles[0] if package_roles else str(property_package.get("package_role", "")))
            ),
            "scope_kind": (
                PROPERTY_SCOPE_KIND_MIXED
                if len(set(scope_kinds)) > 1
                else (scope_kinds[0] if scope_kinds else str(property_package.get("scope_kind", "")))
            ),
            "count": total_count,
            "matched_item_count": matched_item_count,
            "missing_object_count": missing_object_count,
            "missing_component_count": missing_component_count,
            "no_properties": False,
        }

    def _collect_snapshot(self, node, object_list_payload):
        snapshot_id = str(uuid.uuid4())
        items = []
        modifier_name_filter = str(self._input_string_forgiving(node, "Name", "") or "").strip()
        settings = _modifier_filter_settings_from_node(node, modifier_name_filter)
        object_items = list(object_list_payload.get("items", []))
        object_count = len(object_items)
        for object_index, obj_item in enumerate(object_items):
            obj = self._find_object_by_item_cached(obj_item)
            if obj is None:
                continue
            matching_modifiers = [
                modifier
                for modifier in getattr(obj, "modifiers", [])
                if _matches_modifier_filters(
                    modifier,
                    str(settings["modifier_type_filter"]),
                    str(settings["modifier_name_filter"]),
                    str(settings["modifier_name_match_mode"]),
                )
            ]
            for component_index, modifier in enumerate(matching_modifiers):
                if bool(settings["filter_by_context"]):
                    previous_context = self.current_property_context
                    try:
                        self.current_property_context = self._make_modifier_property_context(
                            obj_item,
                            obj,
                            object_index,
                            object_count,
                            modifier,
                            component_index,
                            len(matching_modifiers),
                            object_items,
                            copy_payload=False,
                        )
                        if not bool(self._input_bool(node, "Context", True)):
                            continue
                    finally:
                        self.current_property_context = previous_context
                props = {}
                if node.capture_show_viewport:
                    props["show_viewport"] = bool(modifier.show_viewport)
                if node.capture_show_render and hasattr(modifier, "show_render"):
                    props["show_render"] = bool(modifier.show_render)
                if node.capture_show_in_editmode and hasattr(modifier, "show_in_editmode"):
                    props["show_in_editmode"] = bool(modifier.show_in_editmode)
                items.append(
                    {
                        "object_id": int(obj.session_uid),
                        "object_name": obj.name,
                        "modifier_name": modifier.name,
                        "props": props,
                    }
                )
        return self._property_data_build_modifier_snapshot_property_package(node.name, snapshot_id, items)

    def _restore_property_package(self, node, property_package, filter_object_ids=None):
        package = self._validate_property_package(
            property_package,
            node.name,
            allow_roles={PROPERTY_PACKAGE_ROLE_SNAPSHOT},
            allow_scopes={PROPERTY_PACKAGE_SCOPE_MODIFIER},
        )
        allowed_object_filter = None
        if filter_object_ids is not None:
            allowed_object_filter = {
                "identity_keys": set(),
                "object_ids": {int(item_id) for item_id in list(filter_object_ids or [])},
                "object_names": set(),
            }
        for item in package.get("items", []):
            if not self._property_apply_item_matches_allowed_objects(item, allowed_object_filter):
                continue
            obj = self._find_object_by_item_cached({"id": item["object_id"], "name": item["object_name"]})
            if obj is None:
                if node.missing_policy == "FAIL":
                    raise FlowExecutionError("AF_E008", f"Object '{item['object_name']}' missing", node.name)
                self.log("WARN", f"Object '{item['object_name']}' missing, skipping", node.name)
                continue
            modifier_name = str(item.get("component_name", ""))
            modifier = obj.modifiers.get(modifier_name)
            if modifier is None:
                if node.missing_policy == "FAIL":
                    raise FlowExecutionError("AF_E008", f"Modifier '{modifier_name}' missing on '{obj.name}'", node.name)
                self.log("WARN", f"Modifier '{modifier_name}' missing on '{obj.name}', skipping", node.name)
                continue
            props = dict(item.get("properties", {}))
            if node.restore_show_viewport and "show_viewport" in props:
                modifier.show_viewport = bool(props["show_viewport"])
            if node.restore_show_render and "show_render" in props and hasattr(modifier, "show_render"):
                modifier.show_render = bool(props["show_render"])
            if node.restore_show_in_editmode and "show_in_editmode" in props and hasattr(modifier, "show_in_editmode"):
                modifier.show_in_editmode = bool(props["show_in_editmode"])

    def _auto_restore(self):
        if not self.settings.auto_restore_on_error:
            return
        property_package = self.last_snapshot_package
        if property_package is None:
            return
        self.log("INFO", "AUTO_RESTORE_STARTED")
        dummy_node = type("DummyNode", (), {"name": "AutoRestore", "missing_policy": "WARN_AND_SKIP", "restore_show_viewport": True, "restore_show_render": True, "restore_show_in_editmode": True})()
        try:
            self._restore_property_package(dummy_node, property_package)
        except Exception as exc:
            self.log("WARN", f"Auto-restore warning: {exc}")
        self.log("INFO", "AUTO_RESTORE_DONE")


__all__ = ["RuntimePropertyApplyMixin"]
