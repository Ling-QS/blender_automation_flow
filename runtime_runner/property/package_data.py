from ...node_system.socket_aliases import (
    ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    ADD_PROPERTY_PACKAGE_SOCKET_NAME,
    BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    BASE_PROPERTY_PACKAGE_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)
from ...runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
)
from ...runtime_property.definitions import (
    _clone_property_assignment,
    _clone_property_definition,
    _iter_property_assignment_entries,
    _iter_property_definition_entries,
    _merge_property_assignments,
    _matches_modifier_filters,
    _merge_property_definitions,
    _modifier_filter_settings_from_metadata,
    _validate_property_assignment,
    _property_definition_has_content,
    _validate_property_definition,
)
from ...runtime_property.api import (
    _clone_property_package,
    _filter_property_package,
    _merge_property_packages,
    _property_package_has_property_content,
    _property_package_item_count,
    _property_package_to_definition,
    _property_package_to_object_list,
    _validate_property_package,
)
from ...runtime_math.values import _identity_rotation_payload


class RuntimePropertyPackageDataMixin:
    def _evaluate_property_package_data_node(self, node, node_type):
        if node_type == "AFNodeModifierPropertyData":
            property_definition = self._modifier_property_definition_from_node(node)
            output_mode = str(getattr(node, "output_mode", "ASSIGNMENT") or "ASSIGNMENT")
            if output_mode == "CONTEXT":
                modifier = self._current_property_context_modifier()
                settings = _modifier_filter_settings_from_metadata(property_definition.get("metadata", {}))
                if modifier is not None and not _matches_modifier_filters(
                    modifier,
                    str(settings["modifier_type_filter"]),
                    str(settings["modifier_name_filter"]),
                    str(settings["modifier_name_match_mode"]),
                ):
                    modifier = None
                if modifier is not None and bool(settings["filter_by_context"]) and not bool(
                    settings.get("context_filter_passed", True)
                ):
                    modifier = None
                self._set_output_socket_value(
                    node,
                    "Name",
                    str(getattr(modifier, "name", "") or "") if modifier is not None else "",
                )
                self._set_output_socket_value(
                    node,
                    "Show Viewport",
                    bool(getattr(modifier, "show_viewport", False)) if modifier is not None else False,
                )
                self._set_output_socket_value(
                    node,
                    "Show Render",
                    bool(getattr(modifier, "show_render", False)) if modifier is not None else False,
                )
                self._set_output_socket_value(
                    node,
                    "Show In Edit Mode",
                    bool(getattr(modifier, "show_in_editmode", False)) if modifier is not None else False,
                )
            else:
                property_assignment = self._modifier_property_assignment_from_node(node)
                self._set_output(node, "property_assignment", property_assignment)
            self._set_output(
                node,
                "report",
                {
                    "definition_kind": str(property_definition["definition_kind"]),
                    "output_mode": output_mode,
                    "field_count": int(property_definition.get("metadata", {}).get("count", 0)),
                },
            )
            return True

        if node_type == "AFNodeObjectDisplayPropertyData":
            property_definition = self._object_display_property_definition_from_node(node)
            output_mode = str(getattr(node, "output_mode", "ASSIGNMENT") or "ASSIGNMENT")
            if output_mode == "CONTEXT":
                context_object = self._current_property_context_object()
                self._set_output_socket_value(
                    node,
                    "Hide Viewport",
                    bool(getattr(context_object, "hide_viewport", False)) if context_object is not None else False,
                )
                self._set_output_socket_value(
                    node,
                    "Hide Render",
                    bool(getattr(context_object, "hide_render", False)) if context_object is not None else False,
                )
                self._set_output_socket_value(
                    node,
                    "Show In Front",
                    bool(getattr(context_object, "show_in_front", False)) if context_object is not None else False,
                )
                self._set_output_socket_value(
                    node,
                    "Show Name",
                    bool(getattr(context_object, "show_name", False)) if context_object is not None else False,
                )
                self._set_output_socket_value(
                    node,
                    "Show Axis",
                    bool(getattr(context_object, "show_axis", False)) if context_object is not None else False,
                )
                self._set_output_socket_value(
                    node,
                    "Display Type",
                    str(getattr(context_object, "display_type", "TEXTURED") or "TEXTURED")
                    if context_object is not None
                    else "TEXTURED",
                )
            else:
                property_assignment = self._object_display_property_assignment_from_node(node)
                self._set_output(node, "property_assignment", property_assignment)
            self._set_output(
                node,
                "report",
                {
                    "definition_kind": str(property_definition["definition_kind"]),
                    "output_mode": output_mode,
                    "field_count": int(property_definition.get("metadata", {}).get("count", 0)),
                },
            )
            return True

        if node_type == "AFNodeObjectTransformPropertyData":
            property_definition = self._object_transform_property_definition_from_node(node)
            output_mode = str(getattr(node, "output_mode", "ASSIGNMENT") or "ASSIGNMENT")
            if output_mode == "CONTEXT":
                context_object = self._current_property_context_object()
                location_value = (
                    tuple(float(component) for component in getattr(context_object, "location", (0.0, 0.0, 0.0)))
                    if context_object is not None
                    else (0.0, 0.0, 0.0)
                )
                self._set_output_socket_value(node, "Location", location_value)
                rotation_value = (
                    self._capture_object_rotation_value(context_object)
                    if context_object is not None
                    else _identity_rotation_payload()
                )
                self._set_output_socket_value(node, "Rotation", rotation_value)
                scale_value = (
                    tuple(float(component) for component in getattr(context_object, "scale", (1.0, 1.0, 1.0)))
                    if context_object is not None
                    else (1.0, 1.0, 1.0)
                )
                self._set_output_socket_value(node, "Scale", scale_value)
                self._set_output_socket_value(
                    node,
                    "Rotation Mode",
                    str(getattr(context_object, "rotation_mode", "XYZ") or "XYZ")
                    if context_object is not None
                    else "XYZ",
                )
            else:
                property_assignment = self._object_transform_property_assignment_from_node(node)
                self._set_output(node, "property_assignment", property_assignment)
            self._set_output(
                node,
                "report",
                {
                    "definition_kind": str(property_definition["definition_kind"]),
                    "output_mode": output_mode,
                    "field_count": int(property_definition.get("metadata", {}).get("count", 0)),
                },
            )
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

        if node_type == "AFNodeSampleObjectIndex":
            sampled_value = self._sample_object_index_value(node)
            self._set_output_socket_value(node, "Value", sampled_value)
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
            if (
                object_list is None
                and property_definition is None
                and str(getattr(node, "filter_mode", "KEEP_MATCHED") or "KEEP_MATCHED") != "REMOVE_MATCHED"
            ):
                raise FlowExecutionError(
                    "AF_E011",
                    "Object List or Property Definition input must be linked",
                    node.name,
                )
            stats = {
                "input_count": _property_package_item_count(package),
                "input_entry_count": int(dict(package.get("metadata", {}) or {}).get("entry_count", 0) or 0),
                "object_match_count": 0,
                "definition_match_count": 0,
                "removed_missing_modifier_count": 0,
            }
            object_filter_active = object_list is not None
            object_names = (
                [str(item.get("name", "") or "") for item in object_list.get("items", [])]
                if object_list is not None
                else []
            )
            definition_filter_active = property_definition is not None and _property_definition_has_content(
                property_definition,
                node.name,
            )
            filtered_package = _filter_property_package(
                package,
                [int(item["id"]) for item in object_list.get("items", [])] if object_list is not None else [],
                node.filter_mode,
                property_definition=property_definition,
                object_filter_active=object_filter_active,
                object_names=object_names,
                remove_missing_modifiers=bool(getattr(node, "remove_missing_modifiers", False)),
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
                    "object_filter_count": int(object_list.get("count", 0)) if object_list is not None else 0,
                    "object_name_count": int(len([name for name in object_names if str(name).strip()])),
                    "definition_filter_active": bool(definition_filter_active),
                    "object_match_count": int(stats["object_match_count"]),
                    "definition_match_count": int(stats["definition_match_count"]),
                    "removed_missing_modifier_count": int(stats["removed_missing_modifier_count"]),
                    "filter_mode": str(getattr(node, "filter_mode", "KEEP_MATCHED") or "KEEP_MATCHED"),
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
