import copy

from ...node_system.socket_aliases import (
    ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    ADD_PROPERTY_PACKAGE_SOCKET_NAME,
    BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    BASE_PROPERTY_PACKAGE_SOCKET_NAME,
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)
from ...runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_ASSIGNMENT_KIND_MODIFIER,
    PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
    PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
    PROPERTY_DEFINITION_KIND_MODIFIER,
    PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
    PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
    PROPERTY_PACKAGE_ROLE_COMPOSITE,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    PROPERTY_SOURCE_CURRENT,
    PROPERTY_SOURCE_VALUE,
)
from ...node_system.config import PROPERTY_DATA_FIELD_SPECS
from ...runtime_property.definitions import (
    _clone_property_assignment,
    _iter_property_assignment_entries,
    _make_empty_property_assignment,
    _make_empty_property_definition,
    _make_property_assignment,
    _merge_property_assignments,
    _matches_modifier_filters,
    _merge_property_definitions,
    _modifier_filter_settings_from_metadata,
    _normalize_property_assignment_entries,
    _property_definition_matching_fields,
    _validate_property_assignment,
    _property_definition_has_content,
    _validate_property_definition,
)
from ...runtime_property.api import (
    _clone_property_package,
    _filter_property_package,
    _iter_property_package_entries,
    _make_composite_property_package,
    _merge_property_packages,
    _normalize_filtered_leaf_property_package,
    _property_package_has_property_content,
    _property_package_item_count,
    _property_package_to_definition,
    _property_package_to_object_list,
    _validate_property_package,
)
from ...runtime_math.values import _identity_rotation_payload
from ...runtime_refs.objects import _property_package_object_identity
from ...runtime_scene.objects import _object_reference_identity


_PROPERTY_DATA_CONTEXT_DEFINITION_BY_NODE_TYPE = {
    "AFNodeModifierPropertyData": (PROPERTY_DEFINITION_KIND_MODIFIER, PROPERTY_PACKAGE_SCOPE_MODIFIER),
    "AFNodeObjectDisplayPropertyData": (PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY, PROPERTY_PACKAGE_SCOPE_OBJECT),
    "AFNodeObjectTransformPropertyData": (PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM, PROPERTY_PACKAGE_SCOPE_OBJECT),
}

_PROPERTY_DATA_CONTEXT_FIELD_DEFAULTS = {
    "display_type": "TEXTURED",
    "location": (0.0, 0.0, 0.0),
    "rotation_mode": "XYZ",
    "scale": (1.0, 1.0, 1.0),
}


class RuntimePropertyPackageDataMixin:
    def _make_empty_composite_property_package(self, source_node):
        return _make_composite_property_package(
            source_node,
            [],
            metadata={
                "entry_count": 0,
                "count": 0,
                "object_count": 0,
                "property_definition": _make_empty_property_definition(source_node),
            },
        )

    def _property_data_context_field_specs(self, node):
        node_type = str(getattr(node, "bl_idname", "") or "")
        return tuple(
            dict(spec or {})
            for spec in PROPERTY_DATA_FIELD_SPECS.get(node_type, ())
            if bool(dict(spec or {}).get("supports_context", False))
        )

    def _property_data_context_default_value(self, field_key):
        field_key = str(field_key or "")
        if field_key == "rotation":
            return _identity_rotation_payload()
        if field_key in _PROPERTY_DATA_CONTEXT_FIELD_DEFAULTS:
            return copy.deepcopy(_PROPERTY_DATA_CONTEXT_FIELD_DEFAULTS[field_key])
        return False if field_key.startswith("show_") or field_key.startswith("hide_") else 0.0

    def _property_package_item_matches_context_item(self, item, scope_kind, context_item, *, modifier_name=""):
        if not isinstance(context_item, dict) or not context_item:
            return False
        context_identity, _context_object, _context_object_id, _context_object_name, _context_object_uuid = _object_reference_identity(
            int(context_item.get("id", 0) or 0),
            str(context_item.get("name", "") or ""),
            str(context_item.get("uuid", "") or context_item.get("object_uuid", "") or ""),
            object_resolver=self._find_object_by_item_cached,
        )
        item_identity, _item_object, _item_object_id, _item_object_name, _item_object_uuid = _property_package_object_identity(
            dict(item or {}),
            object_resolver=self._find_object_by_item_cached,
            object_reference_identity=lambda object_id, object_name, object_uuid="", object_resolver=None: _object_reference_identity(
                object_id,
                object_name,
                object_uuid=object_uuid,
                object_resolver=object_resolver,
            ),
        )
        if context_identity != item_identity:
            return False
        if str(scope_kind or "") != PROPERTY_PACKAGE_SCOPE_MODIFIER:
            return True
        return bool(modifier_name) and str(dict(item or {}).get("component_name", "") or "") == str(modifier_name or "")

    def _property_data_context_report(self, *, context_source, has_context, matched_item, matched_field_count):
        return {
            "context_source": str(context_source or "LIVE"),
            "has_context": bool(has_context),
            "matched_item": bool(matched_item),
            "matched_field_count": int(matched_field_count),
        }

    def _property_data_modifier_context(self, node, property_definition):
        modifier = self._current_property_context_modifier()
        context_object = self._current_property_context_object()
        settings = _modifier_filter_settings_from_metadata(dict(property_definition or {}).get("metadata", {}))
        if modifier is not None and not _matches_modifier_filters(
            modifier,
            str(settings["modifier_type_filter"]),
            str(settings["modifier_name_filter"]),
            str(settings["modifier_name_match_mode"]),
        ):
            modifier = None
        if modifier is not None and bool(getattr(node, "filter_by_context", False)) and not bool(
            self._input_bool(node, "Context", True)
        ):
            modifier = None
        return {
            "modifier": modifier,
            "context_object": context_object,
            "has_context": bool(modifier is not None and context_object is not None),
        }

    def _property_data_live_field_value(self, node_type, field_key, *, context_object=None, modifier=None):
        field_key = str(field_key or "")
        if node_type == "AFNodeModifierPropertyData":
            if modifier is None:
                return self._property_data_context_default_value(field_key)
            if field_key == "show_viewport":
                return bool(getattr(modifier, "show_viewport", False))
            if field_key == "show_render":
                return bool(getattr(modifier, "show_render", False))
            if field_key == "show_in_editmode":
                return bool(getattr(modifier, "show_in_editmode", False))
            return self._property_data_context_default_value(field_key)

        if node_type == "AFNodeObjectDisplayPropertyData":
            if context_object is None:
                return self._property_data_context_default_value(field_key)
            if field_key == "hide_viewport":
                return bool(getattr(context_object, "hide_viewport", False))
            if field_key == "hide_render":
                return bool(getattr(context_object, "hide_render", False))
            if field_key == "show_in_front":
                return bool(getattr(context_object, "show_in_front", False))
            if field_key == "show_name":
                return bool(getattr(context_object, "show_name", False))
            if field_key == "show_axis":
                return bool(getattr(context_object, "show_axis", False))
            if field_key == "display_type":
                return str(getattr(context_object, "display_type", "TEXTURED") or "TEXTURED")
            return self._property_data_context_default_value(field_key)

        if node_type == "AFNodeObjectTransformPropertyData":
            if context_object is None:
                return self._property_data_context_default_value(field_key)
            if field_key == "location":
                return tuple(float(component) for component in getattr(context_object, "location", (0.0, 0.0, 0.0)))
            if field_key == "rotation":
                return self._capture_object_rotation_value(context_object)
            if field_key == "scale":
                return tuple(float(component) for component in getattr(context_object, "scale", (1.0, 1.0, 1.0)))
            if field_key == "rotation_mode":
                return str(getattr(context_object, "rotation_mode", "XYZ") or "XYZ")
            return self._property_data_context_default_value(field_key)

        return self._property_data_context_default_value(field_key)

    def _property_data_live_context_values(self, node, property_definition):
        node_type = str(getattr(node, "bl_idname", "") or "")
        context_field_specs = self._property_data_context_field_specs(node)
        field_values = {
            str(spec.get("key", "") or ""): self._property_data_context_default_value(spec.get("key", ""))
            for spec in context_field_specs
        }
        context_object = self._current_property_context_object()
        modifier = None
        component_name = ""
        if node_type == "AFNodeModifierPropertyData":
            modifier_context = self._property_data_modifier_context(node, property_definition)
            modifier = modifier_context["modifier"]
            context_object = modifier_context["context_object"]
            has_context = bool(modifier_context["has_context"])
            if has_context and modifier is not None:
                component_name = str(getattr(modifier, "name", "") or "")
        else:
            has_context = bool(context_object is not None)
        report = self._property_data_context_report(
            context_source="LIVE",
            has_context=has_context,
            matched_item=has_context,
            matched_field_count=len(context_field_specs) if has_context else 0,
        )
        if not has_context:
            return field_values, "", report

        for spec in context_field_specs:
            field_key = str(spec.get("key", "") or "")
            field_values[field_key] = self._property_data_live_field_value(
                node_type,
                field_key,
                context_object=context_object,
                modifier=modifier,
            )
        return field_values, component_name, report

    def _property_data_assignment_entry_matches_context(self, node, property_assignment_entry, *, modifier=None):
        node_type = str(getattr(node, "bl_idname", "") or "")
        expected = _PROPERTY_DATA_CONTEXT_DEFINITION_BY_NODE_TYPE.get(node_type)
        if expected is None:
            return False
        expected_kind, expected_scope = expected
        if (
            str(dict(property_assignment_entry or {}).get("assignment_kind", "") or "") != str(expected_kind)
            or str(dict(property_assignment_entry or {}).get("scope_kind", "") or "") != str(expected_scope)
        ):
            return False
        if str(expected_kind) != PROPERTY_ASSIGNMENT_KIND_MODIFIER:
            return True
        if modifier is None:
            return False
        settings = _modifier_filter_settings_from_metadata(dict(property_assignment_entry or {}).get("metadata", {}))
        if not _matches_modifier_filters(
            modifier,
            str(settings["modifier_type_filter"]),
            str(settings["modifier_name_filter"]),
            str(settings["modifier_name_match_mode"]),
        ):
            return False
        if bool(settings["filter_by_context"]) and not bool(settings["context_filter_passed"]):
            return False
        return True

    def _property_data_assignment_context_values(self, node, property_assignment, property_definition):
        node_type = str(getattr(node, "bl_idname", "") or "")
        context_field_specs = self._property_data_context_field_specs(node)
        field_values = {
            str(spec.get("key", "") or ""): self._property_data_context_default_value(spec.get("key", ""))
            for spec in context_field_specs
        }
        context_object = self._current_property_context_object()
        modifier = None
        if node_type == "AFNodeModifierPropertyData":
            modifier_context = self._property_data_modifier_context(node, property_definition)
            modifier = modifier_context["modifier"]
            context_object = modifier_context["context_object"]
            has_context = bool(modifier_context["has_context"])
        else:
            has_context = bool(context_object is not None)
        report = self._property_data_context_report(
            context_source="ASSIGNMENT",
            has_context=has_context,
            matched_item=False,
            matched_field_count=0,
        )
        if not has_context:
            return field_values, "", report

        matched_fields = set()
        matched_component_name = ""
        validated_assignment = _validate_property_assignment(
            property_assignment,
            node.name,
            allow_kinds={
                PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            },
        )
        for entry in _iter_property_assignment_entries(
            validated_assignment,
            node.name,
            allow_kinds={
                PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            },
        ):
            if not self._property_data_assignment_entry_matches_context(node, entry, modifier=modifier):
                continue
            properties = dict(entry.get("properties", {}) or {})
            sources = dict(entry.get("sources", {}) or {})
            values = dict(entry.get("values", {}) or {})
            entry_matched_field = False
            for spec in context_field_specs:
                field_key = str(spec.get("key", "") or "")
                if not bool(properties.get(field_key, False)):
                    continue
                source = str(sources.get(field_key, PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                if source == PROPERTY_SOURCE_CURRENT:
                    resolved_value = self._property_data_live_field_value(
                        node_type,
                        field_key,
                        context_object=context_object,
                        modifier=modifier,
                    )
                elif field_key in values:
                    resolved_value = copy.deepcopy(values.get(field_key))
                else:
                    continue
                field_values[field_key] = copy.deepcopy(resolved_value)
                matched_fields.add(field_key)
                entry_matched_field = True
            if entry_matched_field:
                report["matched_item"] = True
                if node_type == "AFNodeModifierPropertyData" and modifier is not None:
                    matched_component_name = str(getattr(modifier, "name", "") or "")
        report["matched_field_count"] = len(matched_fields)
        if not bool(report["matched_item"]):
            matched_component_name = ""
        return field_values, matched_component_name, report

    def _property_data_connected_assignment(self, node):
        assignment_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)(PROPERTY_ASSIGNMENT_SOCKET_NAME)
        if assignment_socket is None or not bool(getattr(assignment_socket, "is_linked", False)):
            return False, None
        property_assignment = self._get_linked_output(node, PROPERTY_ASSIGNMENT_SOCKET_NAME, "property_assignment")
        if property_assignment is None:
            property_assignment = _make_empty_property_assignment(node.name)
        return True, property_assignment

    def _property_data_connected_package(self, node):
        package_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)(PROPERTY_PACKAGE_SOCKET_NAME)
        if package_socket is None or not bool(getattr(package_socket, "is_linked", False)):
            return False, None
        property_package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
        if property_package is None:
            property_package = self._make_empty_composite_property_package(node.name)
        return True, property_package

    def _resolve_property_package_assignments_for_context(self, node, property_package):
        report = self._property_data_context_report(
            context_source="PACKAGE",
            has_context=False,
            matched_item=False,
            matched_field_count=0,
        )
        context_item = self._current_property_context_item()
        context_object = self._current_property_context_object()
        modifier = self._current_property_context_modifier()
        has_context = bool(context_object is not None and isinstance(context_item, dict) and context_item)
        report["has_context"] = has_context
        if not has_context:
            return _make_empty_property_assignment(node.name), report

        modifier_name = str(getattr(modifier, "name", "") or "") if modifier is not None else ""
        package = _validate_property_package(property_package, node.name)
        assignment_entries = []
        matched_fields = set()
        supported_entry_types = {
            (PROPERTY_ASSIGNMENT_KIND_MODIFIER, PROPERTY_PACKAGE_SCOPE_MODIFIER),
            (PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY, PROPERTY_PACKAGE_SCOPE_OBJECT),
            (PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM, PROPERTY_PACKAGE_SCOPE_OBJECT),
        }
        for entry in _iter_property_package_entries(package, node.name):
            entry_definition = _property_package_to_definition(entry, node.name)
            assignment_kind = str(dict(entry_definition or {}).get("definition_kind", "") or "")
            scope_kind = str(dict(entry_definition or {}).get("scope_kind", "") or "")
            if (assignment_kind, scope_kind) not in supported_entry_types:
                continue
            for item in list(entry.get("items", [])):
                if not self._property_package_item_matches_context_item(
                    item,
                    scope_kind,
                    context_item,
                    modifier_name=modifier_name,
                ):
                    continue
                properties = dict(item.get("properties", {}) or {})
                if not properties:
                    continue
                entry_properties = {}
                entry_sources = {}
                entry_values = {}
                for key, value in properties.items():
                    field_key = str(key or "")
                    if not field_key:
                        continue
                    entry_properties[field_key] = True
                    entry_sources[field_key] = PROPERTY_SOURCE_VALUE
                    entry_values[field_key] = copy.deepcopy(value)
                    matched_fields.add(field_key)
                if not entry_properties:
                    continue
                report["matched_item"] = True
                assignment_entries.append(
                    _make_property_assignment(
                        assignment_kind=assignment_kind,
                        scope_kind=scope_kind,
                        source_node=node.name,
                        properties=entry_properties,
                        sources=entry_sources,
                        values=entry_values,
                        metadata={},
                    )
                )
        report["matched_field_count"] = len(matched_fields)
        if not assignment_entries:
            return _make_empty_property_assignment(node.name), report
        return _normalize_property_assignment_entries(node.name, assignment_entries, conflict_policy="LAST_WINS"), report

    def _sample_context_data_modifier_for_assignment_entry(self, context_object, property_assignment_entry):
        if context_object is None:
            return None
        if str(dict(property_assignment_entry or {}).get("assignment_kind", "") or "") != PROPERTY_ASSIGNMENT_KIND_MODIFIER:
            return None
        settings = _modifier_filter_settings_from_metadata(dict(property_assignment_entry or {}).get("metadata", {}))
        if bool(settings["filter_by_context"]) and not bool(settings["context_filter_passed"]):
            return None
        if not bool(settings["filter_by_type"]) and not bool(settings["filter_by_name"]):
            return None
        for modifier in list(getattr(context_object, "modifiers", []) or []):
            if _matches_modifier_filters(
                modifier,
                str(settings["modifier_type_filter"]),
                str(settings["modifier_name_filter"]),
                str(settings["modifier_name_match_mode"]),
            ):
                return modifier
        return None

    def _sample_context_data_live_assignment_value(self, property_assignment_entry, field_key, *, context_object=None, modifier=None):
        assignment_kind = str(dict(property_assignment_entry or {}).get("assignment_kind", "") or "")
        if assignment_kind == PROPERTY_ASSIGNMENT_KIND_MODIFIER:
            node_type = "AFNodeModifierPropertyData"
        elif assignment_kind == PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY:
            node_type = "AFNodeObjectDisplayPropertyData"
        elif assignment_kind == PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM:
            node_type = "AFNodeObjectTransformPropertyData"
        else:
            return self._property_data_context_default_value(field_key)
        return self._property_data_live_field_value(
            node_type,
            field_key,
            context_object=context_object,
            modifier=modifier,
        )

    def _sample_context_data_explicit_property_assignment(self, node, property_assignment):
        if property_assignment is None:
            return _make_empty_property_assignment(node.name)
        context_object = self._current_property_context_object()
        validated_assignment = _validate_property_assignment(
            property_assignment,
            node.name,
            allow_kinds={
                PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            },
        )
        resolved_entries = []
        for entry in _iter_property_assignment_entries(
            validated_assignment,
            node.name,
            allow_kinds={
                PROPERTY_ASSIGNMENT_KIND_MODIFIER,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
                PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            },
        ):
            properties = {
                str(key): bool(enabled)
                for key, enabled in dict(entry.get("properties", {}) or {}).items()
            }
            sources = {
                str(key): str(source or PROPERTY_SOURCE_VALUE)
                for key, source in dict(entry.get("sources", {}) or {}).items()
            }
            values = dict(entry.get("values", {}) or {})
            resolved_values = {}
            resolved_sources = {}
            resolved_modifier = self._sample_context_data_modifier_for_assignment_entry(context_object, entry)
            for field_key, enabled in properties.items():
                if not bool(enabled):
                    continue
                source = str(sources.get(field_key, PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                resolved_sources[field_key] = PROPERTY_SOURCE_VALUE
                if source == PROPERTY_SOURCE_CURRENT:
                    resolved_values[field_key] = copy.deepcopy(
                        self._sample_context_data_live_assignment_value(
                            entry,
                            field_key,
                            context_object=context_object,
                            modifier=resolved_modifier,
                        )
                    )
                elif field_key in values:
                    resolved_values[field_key] = copy.deepcopy(values.get(field_key))
                else:
                    resolved_values[field_key] = copy.deepcopy(self._property_data_context_default_value(field_key))
            resolved_entries.append(
                _make_property_assignment(
                    assignment_kind=str(entry.get("assignment_kind", "") or ""),
                    scope_kind=str(entry.get("scope_kind", "") or ""),
                    source_node=str(entry.get("source_node", "") or node.name),
                    properties=properties,
                    sources=resolved_sources,
                    values=resolved_values,
                    metadata=copy.deepcopy(dict(entry.get("metadata", {}) or {})),
                )
            )
        if not resolved_entries:
            return _make_empty_property_assignment(node.name)
        return _normalize_property_assignment_entries(node.name, resolved_entries, conflict_policy="LAST_WINS")

    def _refresh_property_package_current_values(self, node, property_package, object_list=None, property_definition=None):
        package = _validate_property_package(property_package, node.name)
        selection = self._refresh_property_package_selection_context(node, object_list, property_definition)
        if not bool(selection["refresh_values"]) and not bool(selection["prune_items"]):
            raise FlowExecutionError("AF_E020", "Enable Refresh Values or Prune Items", node.name)
        stats = {
            "refreshed_item_count": 0,
            "removed_item_count": 0,
            "removed_field_count": 0,
            "missing_object_count": 0,
            "missing_component_count": 0,
            "selection_fallback": str(selection["selection_fallback"]),
        }
        refreshed_package = self._refresh_property_package_entry_current_values(node, package, selection, stats)
        return refreshed_package, stats

    def _refresh_property_package_selection_context(self, node, object_list=None, property_definition=None):
        validated_definition = None
        if property_definition is not None:
            validated_definition = _validate_property_definition(property_definition, node.name)
        definition_filter_active = validated_definition is not None and _property_definition_has_content(
            validated_definition,
            node.name,
        )
        object_items = list(dict(object_list or {}).get("items", []) or []) if isinstance(object_list, dict) else []
        object_filter_active = self._has_effective_output_content("object_list", object_list, node)
        allowed_ids = set()
        allowed_names = set()
        for item in object_items:
            if not isinstance(item, dict):
                continue
            try:
                allowed_ids.add(int(item.get("id", 0) or 0))
            except Exception:
                pass
            object_name = str(item.get("name", "") or "").strip()
            if object_name:
                allowed_names.add(object_name)
        selection_fallback = "FULL_PACKAGE" if not object_filter_active and not definition_filter_active else ""
        return {
            "range_mode": str(getattr(node, "range_mode", "IN_SCOPE") or "IN_SCOPE"),
            "refresh_values": bool(getattr(node, "refresh_values", True)),
            "prune_items": bool(getattr(node, "prune_items", False)),
            "object_filter_active": bool(object_filter_active),
            "allowed_ids": allowed_ids,
            "allowed_names": allowed_names,
            "definition_filter_active": bool(definition_filter_active),
            "property_definition": validated_definition,
            "selection_fallback": selection_fallback,
        }

    def _refresh_property_package_entry_current_values(self, node, package, selection, stats):
        refreshed_package = _clone_property_package(package)
        if str(refreshed_package.get("package_role", "") or "") == PROPERTY_PACKAGE_ROLE_COMPOSITE:
            refreshed_entries = [
                self._refresh_property_package_entry_current_values(node, entry, selection, stats)
                for entry in list(refreshed_package.get("entries", []))
            ]
            refreshed_entries = [
                entry
                for entry in refreshed_entries
                if isinstance(entry, dict) and _property_package_item_count(entry) > 0
            ]
            refreshed_package["entries"] = refreshed_entries
            refreshed_package["metadata"] = self._refreshed_property_package_metadata(
                node,
                refreshed_package,
                items=None,
                entries=refreshed_entries,
            )
            return refreshed_package
        return self._refresh_leaf_property_package(node, refreshed_package, selection, stats)

    def _refreshed_property_package_metadata(self, node, package, *, items=None, entries=None):
        metadata = copy.deepcopy(dict(package.get("metadata", {}) or {}))
        if entries is not None:
            metadata["entry_count"] = len(entries)
            metadata["count"] = sum(_property_package_item_count(entry) for entry in entries)
            metadata["object_count"] = len(self._property_package_object_ids(entries=entries))
            metadata["property_definition"] = _property_package_to_definition(package, node.name)
            return metadata
        item_list = list(items or [])
        metadata["entry_count"] = 0
        metadata["count"] = len(item_list)
        metadata["object_count"] = len(
            {
                int(item.get("object_id", 0) or 0)
                for item in item_list
                if isinstance(item, dict)
            }
        )
        metadata["property_definition"] = (
            _make_empty_property_definition(node.name)
            if not item_list
            else metadata.get("property_definition")
        )
        return metadata

    def _property_package_object_ids(self, *, entries=None):
        object_ids = set()
        for entry in list(entries or []):
            if str(entry.get("package_role", "") or "") == PROPERTY_PACKAGE_ROLE_COMPOSITE:
                object_ids.update(self._property_package_object_ids(entries=list(entry.get("entries", []))))
                continue
            object_ids.update(
                int(item.get("object_id", 0) or 0)
                for item in list(entry.get("items", []))
                if isinstance(item, dict)
            )
        return object_ids

    def _refresh_leaf_property_package(self, node, package, selection, stats):
        refreshed_package = _clone_property_package(package)
        scope_kind = str(refreshed_package.get("scope_kind", "") or "")
        package_definition = None
        matching_definition_fields = set()
        if bool(selection["definition_filter_active"]):
            package_definition = _property_package_to_definition(refreshed_package, node.name)
            matching_definition_fields = _property_definition_matching_fields(
                package_definition,
                selection["property_definition"],
                node.name,
            )
        if scope_kind not in {PROPERTY_PACKAGE_SCOPE_OBJECT, PROPERTY_PACKAGE_SCOPE_MODIFIER}:
            if self._leaf_package_has_selected_fields(refreshed_package, selection, matching_definition_fields):
                self.log(
                    "WARN",
                    f"Refresh Property Package does not support scope '{scope_kind}', keeping previous values",
                    node.name,
                )
            return refreshed_package

        refreshed_items = []
        for item in list(refreshed_package.get("items", [])):
            next_item, keep_item = self._refresh_property_package_item_current_values(
                node,
                scope_kind,
                item,
                selection,
                matching_definition_fields,
                stats,
            )
            if keep_item:
                refreshed_items.append(next_item)
        refreshed_package["items"] = refreshed_items
        refreshed_package["metadata"] = copy.deepcopy(dict(refreshed_package.get("metadata", {}) or {}))
        refreshed_package["metadata"]["count"] = len(refreshed_items)
        refreshed_package["metadata"]["object_count"] = len(
            {
                int(item.get("object_id", 0) or 0)
                for item in refreshed_items
                if isinstance(item, dict)
            }
        )
        if not refreshed_items:
            refreshed_package["metadata"]["property_definition"] = _make_empty_property_definition(node.name)
            return refreshed_package
        return _normalize_filtered_leaf_property_package(refreshed_package, node.name)

    def _leaf_package_has_selected_fields(self, package, selection, matching_definition_fields):
        for item in list(package.get("items", [])):
            properties = dict(item.get("properties", {}) or {})
            if not properties:
                continue
            matched_object = self._refresh_item_matches_object_selector(item, selection)
            selected_fields = self._selected_refresh_fields(
                properties,
                matched_object,
                matching_definition_fields,
                selection,
            )
            if selected_fields:
                return True
        return False

    def _refresh_item_matches_object_selector(self, item, selection):
        if not bool(selection["object_filter_active"]):
            return True
        object_id = int(dict(item or {}).get("object_id", 0) or 0)
        object_name = str(dict(item or {}).get("object_name", "") or "").strip()
        return bool(
            object_id in set(selection["allowed_ids"])
            or (object_name and object_name in set(selection["allowed_names"]))
        )

    def _selected_refresh_fields(self, properties, matched_object, matching_definition_fields, selection):
        property_keys = {str(key) for key in dict(properties or {}).keys()}
        if not property_keys:
            return set()
        if str(selection["selection_fallback"] or "") == "FULL_PACKAGE":
            return set(property_keys)

        object_filter_active = bool(selection["object_filter_active"])
        definition_filter_active = bool(selection["definition_filter_active"])
        if object_filter_active and definition_filter_active:
            in_scope_fields = set(property_keys).intersection(set(matching_definition_fields)) if matched_object else set()
        elif object_filter_active:
            in_scope_fields = set(property_keys) if matched_object else set()
        elif definition_filter_active:
            in_scope_fields = set(property_keys).intersection(set(matching_definition_fields))
        else:
            in_scope_fields = set(property_keys)

        if str(selection["range_mode"] or "IN_SCOPE") == "OUT_OF_SCOPE":
            return set(property_keys).difference(in_scope_fields)
        return in_scope_fields

    def _prune_selected_fields(self, properties, selected_fields):
        removed_fields = {
            str(key)
            for key in set(selected_fields or set())
            if str(key) in dict(properties or {})
        }
        next_properties = copy.deepcopy(dict(properties or {}))
        for key in removed_fields:
            next_properties.pop(key, None)
        return next_properties, removed_fields

    def _capture_object_scope_property_value(self, obj, key):
        if key == "hide_viewport" and hasattr(obj, "hide_viewport"):
            return True, bool(getattr(obj, "hide_viewport", False))
        if key == "hide_render" and hasattr(obj, "hide_render"):
            return True, bool(getattr(obj, "hide_render", False))
        if key == "show_in_front" and hasattr(obj, "show_in_front"):
            return True, bool(getattr(obj, "show_in_front", False))
        if key == "show_name" and hasattr(obj, "show_name"):
            return True, bool(getattr(obj, "show_name", False))
        if key == "show_axis" and hasattr(obj, "show_axis"):
            return True, bool(getattr(obj, "show_axis", False))
        if key == "display_type" and hasattr(obj, "display_type"):
            return True, str(getattr(obj, "display_type", "") or "")
        if key == "location" and hasattr(obj, "location"):
            return True, [float(value) for value in getattr(obj, "location", (0.0, 0.0, 0.0))]
        if key == "rotation":
            return True, self._capture_object_rotation_value(obj)
        if key == "scale" and hasattr(obj, "scale"):
            return True, [float(value) for value in getattr(obj, "scale", (1.0, 1.0, 1.0))]
        if key == "rotation_mode" and hasattr(obj, "rotation_mode"):
            return True, str(getattr(obj, "rotation_mode", "XYZ") or "XYZ")
        return False, None

    def _capture_modifier_scope_property_value(self, modifier, key):
        if key == "show_viewport" and hasattr(modifier, "show_viewport"):
            return True, bool(getattr(modifier, "show_viewport", False))
        if key == "show_render" and hasattr(modifier, "show_render"):
            return True, bool(getattr(modifier, "show_render", False))
        if key == "show_in_editmode" and hasattr(modifier, "show_in_editmode"):
            return True, bool(getattr(modifier, "show_in_editmode", False))
        return False, None

    def _refresh_property_package_item_current_values(self, node, scope_kind, item, selection, matching_definition_fields, stats):
        refreshed_item = copy.deepcopy(dict(item or {}))
        existing_properties = dict(refreshed_item.get("properties", {}) or {})
        if not existing_properties:
            return refreshed_item, True

        matched_object = self._refresh_item_matches_object_selector(refreshed_item, selection)
        selected_fields = self._selected_refresh_fields(
            existing_properties,
            matched_object,
            matching_definition_fields,
            selection,
        )
        if not selected_fields:
            return refreshed_item, True

        object_item = {
            "id": int(refreshed_item.get("object_id", 0) or 0),
            "name": str(refreshed_item.get("object_name", "") or ""),
            "uuid": str(refreshed_item.get("object_uuid", "") or ""),
        }
        obj = self._find_object_by_item_cached(object_item)
        if obj is None:
            stats["missing_object_count"] += 1
            if bool(selection["prune_items"]):
                next_properties, removed_fields = self._prune_selected_fields(existing_properties, selected_fields)
                stats["removed_field_count"] += len(removed_fields)
                refreshed_item["properties"] = next_properties
                if not next_properties:
                    stats["removed_item_count"] += 1
                    return refreshed_item, False
            return refreshed_item, True

        target_value_reader = self._capture_object_scope_property_value
        target_ref = obj
        if scope_kind == PROPERTY_PACKAGE_SCOPE_MODIFIER:
            modifier_name = str(refreshed_item.get("component_name", "") or "")
            modifier = getattr(obj, "modifiers", None).get(modifier_name) if getattr(obj, "modifiers", None) is not None else None
            if modifier is None:
                stats["missing_component_count"] += 1
                if bool(selection["prune_items"]):
                    next_properties, removed_fields = self._prune_selected_fields(existing_properties, selected_fields)
                    stats["removed_field_count"] += len(removed_fields)
                    refreshed_item["properties"] = next_properties
                    if not next_properties:
                        stats["removed_item_count"] += 1
                        return refreshed_item, False
                return refreshed_item, True
            target_ref = modifier
            target_value_reader = self._capture_modifier_scope_property_value

        next_properties = copy.deepcopy(existing_properties)
        if bool(selection["prune_items"]):
            unsupported_fields = set()
            for key in set(selected_fields):
                supported, _value = target_value_reader(target_ref, str(key))
                if not supported:
                    unsupported_fields.add(str(key))
            if unsupported_fields:
                next_properties, removed_fields = self._prune_selected_fields(next_properties, unsupported_fields)
                stats["removed_field_count"] += len(removed_fields)
                if not next_properties:
                    refreshed_item["properties"] = next_properties
                    stats["removed_item_count"] += 1
                    return refreshed_item, False

        refreshed_key_count = 0
        if bool(selection["refresh_values"]):
            for key in sorted(set(selected_fields).intersection(set(next_properties.keys()))):
                supported, value = target_value_reader(target_ref, str(key))
                if not supported:
                    continue
                next_properties[str(key)] = value
                refreshed_key_count += 1
        refreshed_item["properties"] = next_properties
        if refreshed_key_count > 0:
            stats["refreshed_item_count"] += 1
        return refreshed_item, True

    def _refresh_object_scope_property_values(self, obj, properties):
        refreshed_properties = copy.deepcopy(dict(properties or {}))
        refreshed_key_count = 0
        for key in list(refreshed_properties.keys()):
            if key == "hide_viewport" and hasattr(obj, "hide_viewport"):
                refreshed_properties[key] = bool(getattr(obj, "hide_viewport", False))
                refreshed_key_count += 1
            elif key == "hide_render" and hasattr(obj, "hide_render"):
                refreshed_properties[key] = bool(getattr(obj, "hide_render", False))
                refreshed_key_count += 1
            elif key == "show_in_front" and hasattr(obj, "show_in_front"):
                refreshed_properties[key] = bool(getattr(obj, "show_in_front", False))
                refreshed_key_count += 1
            elif key == "show_name" and hasattr(obj, "show_name"):
                refreshed_properties[key] = bool(getattr(obj, "show_name", False))
                refreshed_key_count += 1
            elif key == "show_axis" and hasattr(obj, "show_axis"):
                refreshed_properties[key] = bool(getattr(obj, "show_axis", False))
                refreshed_key_count += 1
            elif key == "display_type" and hasattr(obj, "display_type"):
                refreshed_properties[key] = str(getattr(obj, "display_type", "") or "")
                refreshed_key_count += 1
            elif key == "location" and hasattr(obj, "location"):
                refreshed_properties[key] = [float(value) for value in getattr(obj, "location", (0.0, 0.0, 0.0))]
                refreshed_key_count += 1
            elif key == "rotation":
                refreshed_properties[key] = self._capture_object_rotation_value(obj)
                refreshed_key_count += 1
            elif key == "scale" and hasattr(obj, "scale"):
                refreshed_properties[key] = [float(value) for value in getattr(obj, "scale", (1.0, 1.0, 1.0))]
                refreshed_key_count += 1
            elif key == "rotation_mode" and hasattr(obj, "rotation_mode"):
                refreshed_properties[key] = str(getattr(obj, "rotation_mode", "XYZ") or "XYZ")
                refreshed_key_count += 1
        return refreshed_properties, refreshed_key_count

    def _refresh_modifier_scope_property_values(self, modifier, properties):
        refreshed_properties = copy.deepcopy(dict(properties or {}))
        refreshed_key_count = 0
        for key in list(refreshed_properties.keys()):
            if key == "show_viewport" and hasattr(modifier, "show_viewport"):
                refreshed_properties[key] = bool(getattr(modifier, "show_viewport", False))
                refreshed_key_count += 1
            elif key == "show_render" and hasattr(modifier, "show_render"):
                refreshed_properties[key] = bool(getattr(modifier, "show_render", False))
                refreshed_key_count += 1
            elif key == "show_in_editmode" and hasattr(modifier, "show_in_editmode"):
                refreshed_properties[key] = bool(getattr(modifier, "show_in_editmode", False))
                refreshed_key_count += 1
        return refreshed_properties, refreshed_key_count

    def _evaluate_property_package_data_node(self, node, node_type):
        if node_type == "AFNodeReadPropertyPackage":
            target_store_node = self._resolve_read_property_package_target(node)
            stored_package = self._read_stored_property_package_slot(target_store_node)
            has_stored_package = stored_package is not None
            property_package = (
                _clone_property_package(stored_package)
                if has_stored_package
                else self._make_empty_composite_property_package(node.name)
            )
            item_count = int(_property_package_item_count(property_package))
            entry_count = int(dict(property_package.get("metadata", {}) or {}).get("entry_count", 0) or 0)
            empty = bool(item_count <= 0 and entry_count <= 0)
            self._set_output(node, "property_package", property_package)
            self._set_output(
                node,
                "report",
                {
                    "package_role": str(property_package.get("package_role", "") or ""),
                    "scope_kind": str(property_package.get("scope_kind", "") or ""),
                    "entry_count": entry_count,
                    "item_count": item_count,
                    "has_stored_package": bool(has_stored_package),
                    "empty": empty,
                    "target_store_node_name": str(getattr(target_store_node, "name", "") or ""),
                },
            )
            return True

        if node_type == "AFNodeExtractPropertyAssignments":
            package_connected, property_package = self._property_data_connected_package(node)
            if not package_connected:
                property_package = self._make_empty_composite_property_package(node.name)
            property_assignment, report = self._resolve_property_package_assignments_for_context(node, property_package)
            self._set_output(node, "property_assignment", property_assignment)
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodeModifierPropertyData":
            property_definition = self._modifier_property_definition_from_node(node)
            output_mode = str(getattr(node, "output_mode", "ASSIGNMENT") or "ASSIGNMENT")
            report = {
                "definition_kind": str(property_definition["definition_kind"]),
                "output_mode": output_mode,
                "field_count": int(property_definition.get("metadata", {}).get("count", 0)),
            }
            if output_mode == "CONTEXT":
                assignment_connected, property_assignment = self._property_data_connected_assignment(node)
                if assignment_connected:
                    field_values, component_name, context_report = self._property_data_assignment_context_values(
                        node,
                        property_assignment,
                        property_definition,
                    )
                else:
                    field_values, component_name, context_report = self._property_data_live_context_values(
                        node,
                        property_definition,
                    )
                self._set_output_socket_value(node, "Name", str(component_name or ""))
                self._set_output_socket_value(node, "Show Viewport", bool(field_values.get("show_viewport", False)))
                self._set_output_socket_value(node, "Show Render", bool(field_values.get("show_render", False)))
                self._set_output_socket_value(node, "Show In Edit Mode", bool(field_values.get("show_in_editmode", False)))
                report.update(context_report)
            else:
                property_assignment = self._modifier_property_assignment_from_node(node)
                self._set_output(node, "property_assignment", property_assignment)
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodeObjectDisplayPropertyData":
            property_definition = self._object_display_property_definition_from_node(node)
            output_mode = str(getattr(node, "output_mode", "ASSIGNMENT") or "ASSIGNMENT")
            report = {
                "definition_kind": str(property_definition["definition_kind"]),
                "output_mode": output_mode,
                "field_count": int(property_definition.get("metadata", {}).get("count", 0)),
            }
            if output_mode == "CONTEXT":
                assignment_connected, property_assignment = self._property_data_connected_assignment(node)
                if assignment_connected:
                    field_values, _component_name, context_report = self._property_data_assignment_context_values(
                        node,
                        property_assignment,
                        property_definition,
                    )
                else:
                    field_values, _component_name, context_report = self._property_data_live_context_values(
                        node,
                        property_definition,
                    )
                self._set_output_socket_value(node, "Hide Viewport", bool(field_values.get("hide_viewport", False)))
                self._set_output_socket_value(node, "Hide Render", bool(field_values.get("hide_render", False)))
                self._set_output_socket_value(node, "Show In Front", bool(field_values.get("show_in_front", False)))
                self._set_output_socket_value(node, "Show Name", bool(field_values.get("show_name", False)))
                self._set_output_socket_value(node, "Show Axis", bool(field_values.get("show_axis", False)))
                self._set_output_socket_value(
                    node,
                    "Display Type",
                    str(field_values.get("display_type", "TEXTURED") or "TEXTURED"),
                )
                report.update(context_report)
            else:
                property_assignment = self._object_display_property_assignment_from_node(node)
                self._set_output(node, "property_assignment", property_assignment)
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodeObjectTransformPropertyData":
            property_definition = self._object_transform_property_definition_from_node(node)
            output_mode = str(getattr(node, "output_mode", "ASSIGNMENT") or "ASSIGNMENT")
            report = {
                "definition_kind": str(property_definition["definition_kind"]),
                "output_mode": output_mode,
                "field_count": int(property_definition.get("metadata", {}).get("count", 0)),
            }
            if output_mode == "CONTEXT":
                assignment_connected, property_assignment = self._property_data_connected_assignment(node)
                if assignment_connected:
                    field_values, _component_name, context_report = self._property_data_assignment_context_values(
                        node,
                        property_assignment,
                        property_definition,
                    )
                else:
                    field_values, _component_name, context_report = self._property_data_live_context_values(
                        node,
                        property_definition,
                    )
                self._set_output_socket_value(
                    node,
                    "Location",
                    tuple(float(component) for component in field_values.get("location", (0.0, 0.0, 0.0))),
                )
                self._set_output_socket_value(
                    node,
                    "Rotation",
                    copy.deepcopy(field_values.get("rotation", _identity_rotation_payload())),
                )
                self._set_output_socket_value(
                    node,
                    "Scale",
                    tuple(float(component) for component in field_values.get("scale", (1.0, 1.0, 1.0))),
                )
                self._set_output_socket_value(
                    node,
                    "Rotation Mode",
                    str(field_values.get("rotation_mode", "XYZ") or "XYZ"),
                )
                report.update(context_report)
            else:
                property_assignment = self._object_transform_property_assignment_from_node(node)
                self._set_output(node, "property_assignment", property_assignment)
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodePropertyContext":
            context = dict(self.current_property_context or {})
            selected_item, selected_index = self._context_selected_object_item(node)
            context_object = context.get("object_ref") if isinstance(context, dict) else None
            context_items = [dict(selected_item)] if isinstance(selected_item, dict) and selected_item else []
            self._set_output(
                node,
                "object_list",
                {
                    "items": context_items,
                    "count": len(context_items),
                    "sort_mode": "CONTEXT",
                },
            )
            self._set_output_socket_value(node, "Object Index", selected_index)
            self._set_output_socket_value(node, "Object Count", int(context.get("object_count", 0)))
            self._set_output_socket_value(node, "Component Index", int(context.get("component_index", 0)))
            self._set_output_socket_value(node, "Component Count", int(context.get("component_count", 0)))
            self._set_output_socket_value(
                node,
                "Is Modifier",
                str(context.get("component_kind", "") or "") == PROPERTY_PACKAGE_SCOPE_MODIFIER,
            )
            self._set_output(
                node,
                "report",
                {
                    "has_object": bool(context_object is not None),
                    "object_count": int(context.get("object_count", 0)),
                    "component_count": int(context.get("component_count", 0)),
                    "selected_index": selected_index,
                    "is_modifier": str(context.get("component_kind", "") or "")
                    == PROPERTY_PACKAGE_SCOPE_MODIFIER,
                },
            )
            return True

        if node_type == "AFNodeSampleContextData":
            output_values, report = self._sample_context_data_outputs(node)
            for socket_name, value in dict(output_values or {}).items():
                self._set_output_socket_value(node, socket_name, value)
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodeReduceContextValue":
            reduced_value, matched_object_payload, matched_index, report = self._reduce_context_value(node)
            self._set_output_socket_value(node, "Value", reduced_value)
            self._set_output(node, "object_list", matched_object_payload)
            self._set_output_socket_value(node, "Object", matched_object_payload)
            self._set_output_socket_value(node, "Object Index", int(matched_index))
            self._set_output(node, "report", report)
            return True

        if node_type == "AFNodeReadGeometryAttribute":
            source_object, source_item, source_count = self._geometry_attribute_source_object(node)
            attribute_name = str(getattr(node, "attribute_name", "") or "").strip()
            element_index = self._input_int(node, "Element Index", 0)
            value_payload = self._read_geometry_attribute_value(node, source_object, attribute_name, element_index)
            runtime_type = str(value_payload.get("runtime_type", "") or "")
            output_mode, output_value = self._coerce_geometry_attribute_output(node, value_payload)
            if output_mode == "BOOLEAN":
                self._set_scalar_vector_outputs(node, bool_value=bool(output_value))
            elif output_mode == "INTEGER":
                self._set_scalar_vector_outputs(node, int_value=int(output_value))
            elif output_mode == "VECTOR":
                self._set_scalar_vector_outputs(node, vector_value=tuple(output_value or (0.0, 0.0, 0.0)))
            elif output_mode == "ROTATION":
                self._set_output(node, "rotation_value", output_value)
            elif output_mode == "MATRIX":
                self._set_output(node, "matrix_value", output_value)
            else:
                self._set_scalar_vector_outputs(node, float_value=float(output_value))
            self._set_output(
                node,
                "report",
                {
                    "attribute_name": attribute_name,
                    "runtime_type": runtime_type,
                    "output_type": output_mode,
                    "element_index": int(element_index),
                    "element_count": int(value_payload.get("element_count", 0)),
                    "object_name": str(getattr(source_object, "name", "") or (source_item or {}).get("name", "")),
                    "source_count": int(source_count),
                    "domain": str(value_payload.get("domain", "") or ""),
                    "data_type": str(value_payload.get("data_type", "") or ""),
                },
            )
            return True

        if node_type == "AFNodeMergePropertyAssignments":
            base_assignment = self._get_linked_output(node, BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME, "property_assignment")
            add_assignment = self._get_linked_output(node, ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME, "property_assignment")
            if base_assignment is None and add_assignment is None:
                raise FlowExecutionError("AF_E011", "No Property Assignment input is linked", node.name)
            if base_assignment is None:
                merged_assignment = _clone_property_assignment(_validate_property_assignment(add_assignment, node.name))
            elif add_assignment is None:
                merged_assignment = _clone_property_assignment(_validate_property_assignment(base_assignment, node.name))
            else:
                merged_assignment = _merge_property_assignments(
                    base_assignment,
                    add_assignment,
                    str(getattr(node, "conflict_policy", "LAST_WINS") or "LAST_WINS"),
                    node.name,
                )
            self._set_output(node, "property_assignment", merged_assignment)
            entry_count = len(_iter_property_assignment_entries(merged_assignment, node.name))
            self._set_output(
                node,
                "report",
                {
                    "assignment_kind": str(merged_assignment.get("assignment_kind", "")),
                    "entry_count": entry_count,
                },
            )
            return True

        if node_type == "AFNodeCreatePropertyPackage":
            object_list = self._get_linked_output(node, "Object List", "object_list")
            if object_list is None:
                raise FlowExecutionError("AF_E011", "Object List input is not linked", node.name)
            property_package = self._build_property_package_from_assignments(node, object_list)
            has_properties = _property_package_has_property_content(property_package, node.name)
            property_definition = _property_package_to_definition(property_package, node.name)
            self._set_output(node, "property_package", property_package)
            self._set_output(
                node,
                "report",
                {
                    "package_role": str(property_package["package_role"]),
                    "scope_kind": str(property_package["scope_kind"]),
                    "definition_kind": "" if not has_properties else str(property_definition.get("definition_kind", "")),
                    "count": _property_package_item_count(property_package),
                    "object_count": int(object_list.get("count", 0)),
                    "has_properties": bool(has_properties),
                },
            )
            return True

        if node_type == "AFNodeRefreshPropertyPackage":
            package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
            if package is None:
                raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
            object_list = self._get_linked_output(node, "Object List", "object_list")
            property_definition = self._get_linked_output(node, PROPERTY_DEFINITION_SOCKET_NAME, "property_definition")
            refreshed_package, stats = self._refresh_property_package_current_values(
                node,
                package,
                object_list=object_list,
                property_definition=property_definition,
            )
            self._set_output(node, "property_package", refreshed_package)
            self._set_output(
                node,
                "report",
                {
                    "package_role": str(refreshed_package.get("package_role", "") or ""),
                    "scope_kind": str(refreshed_package.get("scope_kind", "") or ""),
                    "entry_count": int(dict(refreshed_package.get("metadata", {}) or {}).get("entry_count", 0) or 0),
                    "item_count": int(_property_package_item_count(refreshed_package)),
                    "range_mode": str(getattr(node, "range_mode", "IN_SCOPE") or "IN_SCOPE"),
                    "selection_fallback": str(stats["selection_fallback"]),
                    "refresh_values_enabled": bool(getattr(node, "refresh_values", True)),
                    "prune_items_enabled": bool(getattr(node, "prune_items", False)),
                    "refreshed_item_count": int(stats["refreshed_item_count"]),
                    "removed_item_count": int(stats["removed_item_count"]),
                    "removed_field_count": int(stats["removed_field_count"]),
                    "missing_object_count": int(stats["missing_object_count"]),
                    "missing_component_count": int(stats["missing_component_count"]),
                },
            )
            return True

        if node_type == "AFNodeParsePropertyPackage":
            package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
            if package is None:
                raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
            _validate_property_package(package, node.name)
            property_definition = _property_package_to_definition(package, node.name)
            payload = _property_package_to_object_list(package, node.sort_mode)
            has_properties = _property_definition_has_content(property_definition, node.name)
            self._set_output(node, "property_definition", property_definition)
            self._set_output(node, "object_list", payload)
            self._set_output(
                node,
                "report",
                {
                    "package_role": str(package["package_role"]),
                    "scope_kind": str(package["scope_kind"]),
                    "definition_kind": "" if not has_properties else str(property_definition["definition_kind"]),
                    "object_count": payload["count"],
                    "has_properties": bool(has_properties),
                },
            )
            return True

        if node_type == "AFNodeFilterPropertyPackage":
            package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
            if package is None:
                raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
            _validate_property_package(package, node.name)
            object_list = self._get_linked_output(node, "Object List", "object_list")
            property_definition = self._get_linked_output(node, PROPERTY_DEFINITION_SOCKET_NAME, "property_definition")
            has_effective_object_filter = self._has_effective_output_content("object_list", object_list, node)
            has_effective_definition_filter = self._has_effective_output_content("property_definition", property_definition, node)
            filter_mode = str(getattr(node, "filter_mode", "KEEP_MATCHED") or "KEEP_MATCHED")
            stats = {
                "input_count": _property_package_item_count(package),
                "input_entry_count": int(dict(package.get("metadata", {}) or {}).get("entry_count", 0) or 0),
                "object_match_count": 0,
                "definition_match_count": 0,
            }
            object_filter_active = bool(has_effective_object_filter)
            object_names = (
                [str(item.get("name", "") or "") for item in object_list.get("items", [])]
                if object_filter_active
                else []
            )
            definition_filter_active = bool(has_effective_definition_filter)
            empty_due_to_no_effective_filter = (
                filter_mode == "KEEP_MATCHED"
                and not object_filter_active
                and not definition_filter_active
            )
            if empty_due_to_no_effective_filter:
                filtered_package = self._make_empty_composite_property_package(node.name)
            else:
                filtered_package = _filter_property_package(
                    package,
                    [int(item["id"]) for item in object_list.get("items", [])] if object_filter_active else [],
                    filter_mode,
                    property_definition=property_definition,
                    object_filter_active=object_filter_active,
                    object_names=object_names,
                    object_resolver=self._find_object_by_item_cached,
                    node_name=node.name,
                    stats=stats,
                )
            self._set_output(node, "property_package", filtered_package)
            self._set_output(
                node,
                "report",
                {
                    "package_role": str(filtered_package["package_role"]),
                    "scope_kind": str(filtered_package["scope_kind"]),
                    "count": _property_package_item_count(filtered_package),
                    "entry_count": int(dict(filtered_package.get("metadata", {}) or {}).get("entry_count", 0) or 0),
                    "input_count": int(stats["input_count"]),
                    "input_entry_count": int(stats["input_entry_count"]),
                    "object_filter_active": bool(object_filter_active),
                    "object_filter_count": int(object_list.get("count", 0)) if object_filter_active else 0,
                    "object_name_count": int(len([name for name in object_names if str(name).strip()])),
                    "definition_filter_active": bool(definition_filter_active),
                    "object_match_count": int(stats["object_match_count"]),
                    "definition_match_count": int(stats["definition_match_count"]),
                    "filter_mode": filter_mode,
                    "empty_due_to_no_effective_filter": bool(empty_due_to_no_effective_filter),
                },
            )
            return True

        if node_type == "AFNodeMergePropertyPackages":
            base_package = self._get_linked_output(node, BASE_PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
            add_package = self._get_linked_output(node, ADD_PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
            if base_package is None and add_package is None:
                raise FlowExecutionError("AF_E011", "No Property Package input is linked", node.name)
            if base_package is None:
                merged_package = _clone_property_package(_validate_property_package(add_package, node.name))
            elif add_package is None:
                merged_package = _clone_property_package(_validate_property_package(base_package, node.name))
            else:
                merged_package = _merge_property_packages(base_package, add_package, node.conflict_policy, node.name)
            self._set_output(node, "property_package", merged_package)
            self._set_output(
                node,
                "report",
                {
                    "package_role": str(merged_package["package_role"]),
                    "scope_kind": str(merged_package["scope_kind"]),
                    "count": _property_package_item_count(merged_package),
                },
            )
            return True

        return False


__all__ = ["RuntimePropertyPackageDataMixin"]
