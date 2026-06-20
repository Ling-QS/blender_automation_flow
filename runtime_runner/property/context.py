import copy

from ...runtime_core.constants import (
    PROPERTY_ASSIGNMENT_KIND_MODIFIER,
    PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
    PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
    PROPERTY_DEFINITION_KIND_MODIFIER,
    PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
    PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    PROPERTY_SOURCE_CURRENT,
    PROPERTY_SOURCE_VALUE,
)
from ...runtime_property.definitions import (
    _iter_property_assignment_entries,
    _modifier_filter_settings_from_metadata,
    _property_assignment_structure_key,
    _property_assignment_to_definition_payload,
    _validate_property_assignment,
    _validate_property_definition,
)


class RuntimePropertyContextMixin:
    def _current_property_context_item(self):
        context = getattr(self, "current_property_context", None)
        if not isinstance(context, dict):
            return None
        return context.get("object_item")

    def _current_property_context_items(self):
        context = getattr(self, "current_property_context", None)
        if not isinstance(context, dict):
            return []
        items = context.get("object_items")
        if not isinstance(items, list):
            return []
        return items

    def _current_property_context_object(self):
        context = getattr(self, "current_property_context", None)
        if not isinstance(context, dict):
            return None
        return context.get("object_ref")

    def _current_property_context_modifier(self):
        context = getattr(self, "current_property_context", None)
        if not isinstance(context, dict):
            return None
        return context.get("modifier_ref")

    def _make_object_property_context(self, obj_item, obj, index, count, object_items=None, copy_payload=True):
        return {
            "object_item": (dict(obj_item or {}) if copy_payload else (obj_item if isinstance(obj_item, dict) else dict(obj_item or {}))),
            "object_items": (list(object_items or []) if copy_payload else (object_items if isinstance(object_items, list) else list(object_items or []))),
            "object_ref": obj,
            "object_index": int(index),
            "object_count": int(count),
            "component_kind": PROPERTY_PACKAGE_SCOPE_OBJECT,
            "component_index": 0,
            "component_count": 1,
            "modifier_ref": None,
            "modifier_name": "",
            "modifier_type": "",
        }

    def _make_modifier_property_context(self, obj_item, obj, object_index, object_count, modifier, component_index, component_count, object_items=None, copy_payload=True):
        return {
            "object_item": (dict(obj_item or {}) if copy_payload else (obj_item if isinstance(obj_item, dict) else dict(obj_item or {}))),
            "object_items": (list(object_items or []) if copy_payload else (object_items if isinstance(object_items, list) else list(object_items or []))),
            "object_ref": obj,
            "object_index": int(object_index),
            "object_count": int(object_count),
            "component_kind": PROPERTY_PACKAGE_SCOPE_MODIFIER,
            "component_index": int(component_index),
            "component_count": int(component_count),
            "modifier_ref": modifier,
            "modifier_name": str(getattr(modifier, "name", "") or ""),
            "modifier_type": str(getattr(modifier, "type", "") or ""),
        }

    def _set_output_socket_value(self, node, socket_name, value):
        socket = getattr(node, "outputs", {}).get(socket_name) if hasattr(getattr(node, "outputs", None), "get") else None
        if socket is None:
            return
        for key in self._socket_output_keys(socket):
            self._set_output(node, key, copy.deepcopy(value))

    def _resolve_property_assignment_entry_for_source(self, source_node, source_socket, expected_assignment, node_name):
        property_assignment = self._get_output_from_source(source_node, source_socket, "property_assignment")
        if property_assignment is None:
            return expected_assignment
        expected_signature = _property_assignment_structure_key(expected_assignment)
        for entry in _iter_property_assignment_entries(
            property_assignment,
            node_name,
            allow_kinds={
                PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            },
        ):
            if _property_assignment_structure_key(entry) == expected_signature:
                return entry
        return expected_assignment

    def _property_assignment_to_definition(self, property_assignment, node_name):
        property_definition = _property_assignment_to_definition_payload(property_assignment, node_name)
        return _validate_property_definition(
            property_definition,
            node_name,
            allow_kinds={
                PROPERTY_DEFINITION_KIND_MODIFIER,
                PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
                PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
            },
        )

    def _compile_property_assignment_plan(self, property_assignment, node_name):
        property_assignment = _validate_property_assignment(
            property_assignment,
            node_name,
            allow_kinds={
                PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            },
        )
        signature = _property_assignment_structure_key(property_assignment)
        assignment_kind = str(property_assignment.get("assignment_kind", "") or "")
        properties_map = {
            str(key): bool(enabled)
            for key, enabled in dict(property_assignment.get("properties", {}) or {}).items()
        }
        sources_map = {
            str(key): str(source or PROPERTY_SOURCE_VALUE)
            for key, source in dict(property_assignment.get("sources", {}) or {}).items()
        }
        cached = self._property_assignment_plan_cache.get(signature)
        if cached is None:
            enabled_properties = tuple(key for key, enabled in properties_map.items() if bool(enabled))
            package_role = PROPERTY_PACKAGE_ROLE_SNAPSHOT
            if any(str(sources_map.get(key, PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE) != PROPERTY_SOURCE_CURRENT for key in enabled_properties):
                package_role = PROPERTY_PACKAGE_ROLE_TARGET
            settings = _modifier_filter_settings_from_metadata(property_assignment.get("metadata", {}))
            cached = {
                "signature": signature,
                "assignment_kind": assignment_kind,
                "properties_map": properties_map,
                "sources_map": sources_map,
                "enabled_properties": enabled_properties,
                "package_role": package_role,
                "modifier_filter": str(settings["modifier_type_filter"]),
                "modifier_name_filter": str(settings["modifier_name_filter"]),
                "modifier_name_match_mode": str(settings["modifier_name_match_mode"]),
                "filter_by_type": bool(settings["filter_by_type"]),
                "filter_by_name": bool(settings["filter_by_name"]),
                "filter_by_context": bool(settings["filter_by_context"]),
            }
            self._property_assignment_plan_cache[signature] = cached
        return {
            **cached,
            "context_filter_passed": bool(
                _modifier_filter_settings_from_metadata(property_assignment.get("metadata", {})).get("context_filter_passed", True)
            ),
            "values_map": dict(property_assignment.get("values", {}) or {}),
        }


__all__ = ["RuntimePropertyContextMixin"]
