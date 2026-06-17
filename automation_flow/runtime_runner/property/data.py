import copy
import uuid

import bpy
from mathutils import Vector

from ...runtime_core.constants import (
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
    OBJECT_PERSISTENT_UUID_PROP,
)
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_persistence.serialization import _ensure_object_persistent_uuid as _ensure_object_persistent_uuid_impl
from ...runtime_property.definitions import (
    _clone_property_assignment,
    _clone_property_definition,
    _iter_property_assignment_entries,
    _make_composite_property_definition,
    _matches_modifier_filters,
    _normalize_property_definition_entries,
    _property_assignment_signature,
    _validate_property_assignment,
    _validate_property_definition,
)
from ...runtime_property.packages import (
    _build_modifier_snapshot_property_package as _build_modifier_snapshot_property_package_impl,
    _build_modifier_target_property_package as _build_modifier_target_property_package_impl,
    _build_object_display_snapshot_property_package as _build_object_display_snapshot_property_package_impl,
    _build_object_display_target_property_package as _build_object_display_target_property_package_impl,
    _build_object_transform_snapshot_property_package as _build_object_transform_snapshot_property_package_impl,
    _build_object_transform_target_property_package as _build_object_transform_target_property_package_impl,
    _clone_property_package,
    _property_package_item_count,
    _make_composite_property_package as _make_composite_property_package_impl,
    _make_property_package as _make_property_package_impl,
    _make_property_package_item as _make_property_package_item_impl,
)
from ...runtime_property.definitions import (
    _make_property_assignment,
    _make_property_definition,
    _modifier_filter_settings_from_node,
)


class RuntimePropertyDataMixin:
    def _property_data_component_path_for_modifier(self, obj, modifier_name):
        return f"{obj.name}/{modifier_name}"

    def _property_data_component_path_for_object(self, obj):
        return f"{obj.name}/OBJECT"

    def _property_data_make_property_package_item(
        self,
        object_ref,
        target_kind,
        component_path,
        component_name,
        component_type,
        properties,
        metadata=None,
    ):
        return _make_property_package_item_impl(
            object_ref,
            target_kind,
            component_path,
            component_name,
            component_type,
            properties,
            metadata=metadata,
            ensure_object_persistent_uuid=lambda obj: _ensure_object_persistent_uuid_impl(obj, OBJECT_PERSISTENT_UUID_PROP),
        )

    def _property_data_make_property_package(self, package_role, scope_kind, source_node, items, metadata=None):
        return _make_property_package_impl(package_role, scope_kind, source_node, items, metadata=metadata)

    def _property_data_make_composite_property_package(self, source_node, entries, metadata=None):
        return _make_composite_property_package_impl(
            source_node,
            entries,
            metadata=metadata,
            clone_property_package=_clone_property_package,
            property_package_item_count=lambda package: _property_package_item_count(
                package,
                lambda value: bool(isinstance(value, dict) and str(value.get("package_role", "") or "") == PROPERTY_PACKAGE_ROLE_COMPOSITE),
            ),
            property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
            property_scope_kind_mixed=PROPERTY_SCOPE_KIND_MIXED,
        )

    def _property_data_build_modifier_snapshot_property_package(self, source_node, snapshot_id, snapshot_items):
        return _build_modifier_snapshot_property_package_impl(
            source_node,
            snapshot_id,
            snapshot_items,
            bpy_module=bpy,
            find_object_by_item=self._find_object_by_item_cached,
            make_property_package_item=self._property_data_make_property_package_item,
            make_property_package=self._property_data_make_property_package,
            component_path_for_modifier=self._property_data_component_path_for_modifier,
            property_package_scope_modifier=PROPERTY_PACKAGE_SCOPE_MODIFIER,
            property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
        )

    def _property_data_build_modifier_target_property_package(self, source_node, property_definition, items):
        return _build_modifier_target_property_package_impl(
            source_node,
            property_definition,
            items,
            validate_property_definition=_validate_property_definition,
            make_property_package=self._property_data_make_property_package,
            clone_property_definition=_clone_property_definition,
            property_definition_kind_modifier=PROPERTY_DEFINITION_KIND_MODIFIER,
            property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
            property_package_scope_modifier=PROPERTY_PACKAGE_SCOPE_MODIFIER,
        )

    def _property_data_build_object_display_snapshot_property_package(self, source_node, snapshot_id, snapshot_items):
        return _build_object_display_snapshot_property_package_impl(
            source_node,
            snapshot_id,
            snapshot_items,
            bpy_module=bpy,
            find_object_by_item=self._find_object_by_item_cached,
            make_property_package_item=self._property_data_make_property_package_item,
            make_property_package=self._property_data_make_property_package,
            component_path_for_object=self._property_data_component_path_for_object,
            property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
            property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
        )

    def _property_data_build_object_display_target_property_package(self, source_node, property_definition, items):
        return _build_object_display_target_property_package_impl(
            source_node,
            property_definition,
            items,
            validate_property_definition=_validate_property_definition,
            make_property_package=self._property_data_make_property_package,
            clone_property_definition=_clone_property_definition,
            property_definition_kind_object_display=PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
            property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
            property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
        )

    def _property_data_build_object_transform_snapshot_property_package(self, source_node, snapshot_id, snapshot_items):
        return _build_object_transform_snapshot_property_package_impl(
            source_node,
            snapshot_id,
            snapshot_items,
            bpy_module=bpy,
            find_object_by_item=self._find_object_by_item_cached,
            make_property_package_item=self._property_data_make_property_package_item,
            make_property_package=self._property_data_make_property_package,
            component_path_for_object=self._property_data_component_path_for_object,
            property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
            property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
        )

    def _property_data_build_object_transform_target_property_package(self, source_node, property_definition, items):
        return _build_object_transform_target_property_package_impl(
            source_node,
            property_definition,
            items,
            validate_property_definition=_validate_property_definition,
            make_property_package=self._property_data_make_property_package,
            clone_property_definition=_clone_property_definition,
            property_definition_kind_object_transform=PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
            property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
            property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
        )

    def _vector_prop_matches(self, current_value, target_value):
        try:
            current_components = tuple(float(component) for component in current_value[:3])
        except Exception:
            current_components = tuple(float(component) for component in Vector(current_value))
        target_components = tuple(float(component) for component in list(target_value)[:3])
        return current_components == target_components

    def _rotation_payload_matches_object(self, obj, rotation_payload):
        if not isinstance(rotation_payload, dict):
            return False
        target_mode = str(rotation_payload.get("mode", getattr(obj, "rotation_mode", "XYZ")) or getattr(obj, "rotation_mode", "XYZ"))
        if str(getattr(obj, "rotation_mode", "XYZ") or "XYZ") != target_mode:
            return False
        target_values = [float(value) for value in list(rotation_payload.get("value", []))]
        if target_mode == "QUATERNION":
            current_values = [float(value) for value in getattr(obj, "rotation_quaternion", (1.0, 0.0, 0.0, 0.0))]
            return current_values[:4] == target_values[:4]
        if target_mode == "AXIS_ANGLE":
            current_values = [float(value) for value in getattr(obj, "rotation_axis_angle", (0.0, 0.0, 0.0, 1.0))]
            return current_values[:4] == target_values[:4]
        current_values = [float(value) for value in getattr(obj, "rotation_euler", (0.0, 0.0, 0.0))]
        return current_values[:3] == target_values[:3]

    def _modifier_property_definition_from_node(self, node):
        modifier_name_filter = str(self._input_string_forgiving(node, "Name", "") or "").strip()
        settings = _modifier_filter_settings_from_node(node, modifier_name_filter)
        if bool(settings["filter_by_context"]):
            context_filter_passed = bool(self._input_bool(node, "Context", True))
        else:
            context_filter_passed = True
        properties = {
            "show_viewport": bool(getattr(node, "capture_show_viewport", False)),
            "show_render": bool(getattr(node, "capture_show_render", False)),
            "show_in_editmode": bool(getattr(node, "capture_show_in_editmode", False)),
        }
        return _make_property_definition(
            definition_kind=PROPERTY_DEFINITION_KIND_MODIFIER,
            scope_kind=PROPERTY_PACKAGE_SCOPE_MODIFIER,
            source_node=node.name,
            properties=properties,
            metadata={
                "filter_by_type": bool(settings["filter_by_type"]),
                "filter_by_name": bool(settings["filter_by_name"]),
                "filter_by_context": bool(settings["filter_by_context"]),
                "modifier_type_filter": str(settings["modifier_type_filter"]),
                "modifier_name_filter": str(settings["modifier_name_filter"]),
                "modifier_name_match_mode": str(settings["modifier_name_match_mode"]),
                "context_filter_passed": bool(context_filter_passed),
            },
        )

    def _object_display_property_definition_from_node(self, node):
        properties = {
            "hide_viewport": bool(getattr(node, "capture_hide_viewport", False)),
            "hide_render": bool(getattr(node, "capture_hide_render", False)),
            "show_in_front": bool(getattr(node, "capture_show_in_front", False)),
            "show_name": bool(getattr(node, "capture_show_name", False)),
            "show_axis": bool(getattr(node, "capture_show_axis", False)),
            "display_type": bool(getattr(node, "capture_display_type", False)),
        }
        return _make_property_definition(
            definition_kind=PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
            scope_kind=PROPERTY_PACKAGE_SCOPE_OBJECT,
            source_node=node.name,
            properties=properties,
            metadata={},
        )

    def _capture_object_rotation_value(self, obj, rotation_mode=None):
        resolved_mode = str(rotation_mode or getattr(obj, "rotation_mode", "XYZ") or "XYZ")
        if resolved_mode == "QUATERNION":
            return {
                "mode": resolved_mode,
                "value": [float(value) for value in getattr(obj, "rotation_quaternion", (1.0, 0.0, 0.0, 0.0))],
            }
        if resolved_mode == "AXIS_ANGLE":
            return {
                "mode": resolved_mode,
                "value": [float(value) for value in getattr(obj, "rotation_axis_angle", (0.0, 0.0, 0.0, 1.0))],
            }
        return {
            "mode": resolved_mode,
            "value": [float(value) for value in getattr(obj, "rotation_euler", (0.0, 0.0, 0.0))],
        }

    def _apply_object_rotation_value(self, obj, rotation_payload, dry_run=False):
        if not isinstance(rotation_payload, dict):
            return
        rotation_mode = str(rotation_payload.get("mode", getattr(obj, "rotation_mode", "XYZ")) or getattr(obj, "rotation_mode", "XYZ"))
        rotation_values = list(rotation_payload.get("value", []))
        if not dry_run:
            obj.rotation_mode = rotation_mode
            if rotation_mode == "QUATERNION" and len(rotation_values) >= 4:
                obj.rotation_quaternion = rotation_values[:4]
            elif rotation_mode == "AXIS_ANGLE" and len(rotation_values) >= 4:
                obj.rotation_axis_angle = rotation_values[:4]
            elif len(rotation_values) >= 3:
                obj.rotation_euler = rotation_values[:3]

    def _object_transform_property_definition_from_node(self, node):
        properties = {
            "location": bool(getattr(node, "capture_location", False)),
            "rotation": bool(getattr(node, "capture_rotation", False)),
            "scale": bool(getattr(node, "capture_scale", False)),
            "rotation_mode": bool(getattr(node, "capture_rotation_mode", False)),
        }
        return _make_property_definition(
            definition_kind=PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
            scope_kind=PROPERTY_PACKAGE_SCOPE_OBJECT,
            source_node=node.name,
            properties=properties,
            metadata={},
        )

    def _object_transform_property_assignment_from_node(self, node):
        properties = {
            "location": bool(getattr(node, "capture_location", False)),
            "rotation": bool(getattr(node, "capture_rotation", False)),
            "scale": bool(getattr(node, "capture_scale", False)),
            "rotation_mode": bool(getattr(node, "capture_rotation_mode", False)),
        }
        sources = {
            "location": str(getattr(node, "source_location", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "rotation": str(getattr(node, "source_rotation", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "scale": str(getattr(node, "source_scale", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "rotation_mode": str(getattr(node, "source_rotation_mode", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
        }
        values = {}
        if bool(properties["location"]) and sources["location"] == PROPERTY_SOURCE_VALUE:
            values["location"] = [float(value) for value in self._input_vector(node, "Location", getattr(node, "target_location", (0.0, 0.0, 0.0)))]
        if bool(properties["rotation"]) and sources["rotation"] == PROPERTY_SOURCE_VALUE:
            linked_rotation = self._get_linked_output(node, "Rotation", "rotation_value")
            if linked_rotation is not None:
                values["rotation"] = copy.deepcopy(linked_rotation)
            else:
                rotation_mode = self._input_rotation_mode(node, "Rotation Mode", getattr(node, "target_rotation_mode", "XYZ"))
                if rotation_mode == "QUATERNION":
                    rotation_value = [float(value) for value in getattr(node, "target_rotation_quaternion", (1.0, 0.0, 0.0, 0.0))]
                elif rotation_mode == "AXIS_ANGLE":
                    rotation_value = [float(value) for value in getattr(node, "target_rotation_axis_angle", (0.0, 0.0, 0.0, 1.0))]
                else:
                    rotation_value = [float(value) for value in getattr(node, "target_rotation_euler", (0.0, 0.0, 0.0))]
                values["rotation"] = {"mode": rotation_mode, "value": rotation_value}
        if bool(properties["scale"]) and sources["scale"] == PROPERTY_SOURCE_VALUE:
            linked_scale = self._get_linked_output(node, "Scale", "vector_value")
            if linked_scale is not None:
                values["scale"] = [float(value) for value in linked_scale]
            else:
                values["scale"] = [float(value) for value in getattr(node, "target_scale", (1.0, 1.0, 1.0))]
        if bool(properties["rotation_mode"]) and sources["rotation_mode"] == PROPERTY_SOURCE_VALUE:
            values["rotation_mode"] = self._input_rotation_mode(node, "Rotation Mode", getattr(node, "target_rotation_mode", "XYZ"))
        return _make_property_assignment(
            assignment_kind=PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM,
            scope_kind=PROPERTY_PACKAGE_SCOPE_OBJECT,
            source_node=node.name,
            properties=properties,
            sources=sources,
            values=values,
            metadata={},
        )

    def _modifier_property_assignment_from_node(self, node):
        modifier_name_filter = str(self._input_string_forgiving(node, "Name", "") or "").strip()
        settings = _modifier_filter_settings_from_node(node, modifier_name_filter)
        if bool(settings["filter_by_context"]):
            context_filter_passed = bool(self._input_bool(node, "Context", True))
        else:
            context_filter_passed = True
        properties = {
            "show_viewport": bool(getattr(node, "capture_show_viewport", False)),
            "show_render": bool(getattr(node, "capture_show_render", False)),
            "show_in_editmode": bool(getattr(node, "capture_show_in_editmode", False)),
        }
        sources = {
            "show_viewport": str(getattr(node, "source_show_viewport", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "show_render": str(getattr(node, "source_show_render", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "show_in_editmode": str(getattr(node, "source_show_in_editmode", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
        }
        values = {}
        if bool(properties["show_viewport"]) and sources["show_viewport"] == PROPERTY_SOURCE_VALUE:
            values["show_viewport"] = bool(self._input_bool(node, "Show Viewport", False))
        if bool(properties["show_render"]) and sources["show_render"] == PROPERTY_SOURCE_VALUE:
            values["show_render"] = bool(self._input_bool(node, "Show Render", False))
        if bool(properties["show_in_editmode"]) and sources["show_in_editmode"] == PROPERTY_SOURCE_VALUE:
            values["show_in_editmode"] = bool(self._input_bool(node, "Show In Edit Mode", False))
        return _make_property_assignment(
            assignment_kind=PROPERTY_ASSIGNMENT_KIND_MODIFIER,
            scope_kind=PROPERTY_PACKAGE_SCOPE_MODIFIER,
            source_node=node.name,
            properties=properties,
            sources=sources,
            values=values,
            metadata={
                "filter_by_type": bool(settings["filter_by_type"]),
                "filter_by_name": bool(settings["filter_by_name"]),
                "filter_by_context": bool(settings["filter_by_context"]),
                "modifier_type_filter": str(settings["modifier_type_filter"]),
                "modifier_name_filter": str(settings["modifier_name_filter"]),
                "modifier_name_match_mode": str(settings["modifier_name_match_mode"]),
                "context_filter_passed": bool(context_filter_passed),
            },
        )

    def _object_display_property_assignment_from_node(self, node):
        properties = {
            "hide_viewport": bool(getattr(node, "capture_hide_viewport", False)),
            "hide_render": bool(getattr(node, "capture_hide_render", False)),
            "show_in_front": bool(getattr(node, "capture_show_in_front", False)),
            "show_name": bool(getattr(node, "capture_show_name", False)),
            "show_axis": bool(getattr(node, "capture_show_axis", False)),
            "display_type": bool(getattr(node, "capture_display_type", False)),
        }
        sources = {
            "hide_viewport": str(getattr(node, "source_hide_viewport", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "hide_render": str(getattr(node, "source_hide_render", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "show_in_front": str(getattr(node, "source_show_in_front", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "show_name": str(getattr(node, "source_show_name", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "show_axis": str(getattr(node, "source_show_axis", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
            "display_type": str(getattr(node, "source_display_type", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE),
        }
        values = {}
        if bool(properties["hide_viewport"]) and sources["hide_viewport"] == PROPERTY_SOURCE_VALUE:
            values["hide_viewport"] = bool(self._input_bool(node, "Hide Viewport", False))
        if bool(properties["hide_render"]) and sources["hide_render"] == PROPERTY_SOURCE_VALUE:
            values["hide_render"] = bool(self._input_bool(node, "Hide Render", False))
        if bool(properties["show_in_front"]) and sources["show_in_front"] == PROPERTY_SOURCE_VALUE:
            values["show_in_front"] = bool(self._input_bool(node, "Show In Front", False))
        if bool(properties["show_name"]) and sources["show_name"] == PROPERTY_SOURCE_VALUE:
            values["show_name"] = bool(self._input_bool(node, "Show Name", False))
        if bool(properties["show_axis"]) and sources["show_axis"] == PROPERTY_SOURCE_VALUE:
            values["show_axis"] = bool(self._input_bool(node, "Show Axis", False))
        if bool(properties["display_type"]) and sources["display_type"] == PROPERTY_SOURCE_VALUE:
            values["display_type"] = self._input_display_type(node, "Display Type", getattr(node, "target_display_type", "TEXTURED"))
        return _make_property_assignment(
            assignment_kind=PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY,
            scope_kind=PROPERTY_PACKAGE_SCOPE_OBJECT,
            source_node=node.name,
            properties=properties,
            sources=sources,
            values=values,
            metadata={},
        )

    def _collect_property_assignment_items_for_object(self, node, property_assignment, obj, obj_item, source_node=None, source_socket=None):
        property_assignment = _validate_property_assignment(
            property_assignment,
            node.name,
            allow_kinds={PROPERTY_ASSIGNMENT_KIND_MODIFIER, PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY, PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM},
        )
        plan = self._compile_property_assignment_plan(property_assignment, node.name)
        assignment_kind = str(plan["assignment_kind"])
        properties_map = dict(plan["properties_map"])
        sources_map = dict(plan["sources_map"])
        values_map = dict(plan["values_map"])
        package_role = str(plan["package_role"])

        items = []
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
            for component_index, modifier in enumerate(matching_modifiers):
                evaluated_assignment = property_assignment
                if source_node is not None and source_socket is not None:
                    self.current_property_context = self._make_modifier_property_context(
                        obj_item,
                        obj,
                        int(base_context.get("object_index", 0) if isinstance(base_context, dict) else 0),
                        int(base_context.get("object_count", 0) if isinstance(base_context, dict) else 0),
                        modifier,
                        component_index,
                        len(matching_modifiers),
                        list(base_context.get("object_items", [])) if isinstance(base_context, dict) else None,
                    )
                    evaluated_assignment = self._resolve_property_assignment_entry_for_source(source_node, source_socket, property_assignment, node.name)

                evaluated_plan = self._compile_property_assignment_plan(evaluated_assignment, node.name)
                if bool(evaluated_plan.get("filter_by_context", False)) and not bool(evaluated_plan.get("context_filter_passed", True)):
                    continue
                evaluated_properties_map = dict(evaluated_plan["properties_map"])
                evaluated_sources_map = dict(evaluated_plan["sources_map"])
                evaluated_values_map = dict(evaluated_plan["values_map"])
                item_properties = {}
                if bool(evaluated_properties_map.get("show_viewport", False)) and hasattr(modifier, "show_viewport"):
                    source = str(evaluated_sources_map.get("show_viewport", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                    item_properties["show_viewport"] = bool(modifier.show_viewport) if source == PROPERTY_SOURCE_CURRENT else bool(evaluated_values_map["show_viewport"])
                if bool(evaluated_properties_map.get("show_render", False)) and hasattr(modifier, "show_render"):
                    source = str(evaluated_sources_map.get("show_render", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                    item_properties["show_render"] = bool(modifier.show_render) if source == PROPERTY_SOURCE_CURRENT else bool(evaluated_values_map["show_render"])
                if bool(evaluated_properties_map.get("show_in_editmode", False)) and hasattr(modifier, "show_in_editmode"):
                    source = str(evaluated_sources_map.get("show_in_editmode", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                    item_properties["show_in_editmode"] = bool(modifier.show_in_editmode) if source == PROPERTY_SOURCE_CURRENT else bool(evaluated_values_map["show_in_editmode"])
                if not item_properties:
                    continue
                items.append(
                    self._property_data_make_property_package_item(
                        object_ref=obj,
                        target_kind=PROPERTY_PACKAGE_SCOPE_MODIFIER,
                        component_path=self._property_data_component_path_for_modifier(obj, modifier.name),
                        component_name=modifier.name,
                        component_type=str(getattr(modifier, "type", "") or "UNKNOWN"),
                        properties=item_properties,
                        metadata={},
                    )
                )
            self.current_property_context = base_context
            return {"package_role": package_role, "items": items}

        if assignment_kind == PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM:
            item_properties = {}
            if bool(properties_map.get("location", False)) and hasattr(obj, "location"):
                source = str(sources_map.get("location", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                item_properties["location"] = [float(value) for value in obj.location] if source == PROPERTY_SOURCE_CURRENT else copy.deepcopy(values_map["location"])
            if bool(properties_map.get("rotation", False)):
                source = str(sources_map.get("rotation", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                item_properties["rotation"] = self._capture_object_rotation_value(obj) if source == PROPERTY_SOURCE_CURRENT else copy.deepcopy(values_map["rotation"])
            if bool(properties_map.get("scale", False)) and hasattr(obj, "scale"):
                source = str(sources_map.get("scale", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                item_properties["scale"] = [float(value) for value in obj.scale] if source == PROPERTY_SOURCE_CURRENT else copy.deepcopy(values_map["scale"])
            if bool(properties_map.get("rotation_mode", False)) and hasattr(obj, "rotation_mode"):
                source = str(sources_map.get("rotation_mode", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
                item_properties["rotation_mode"] = str(getattr(obj, "rotation_mode", "XYZ") or "XYZ") if source == PROPERTY_SOURCE_CURRENT else str(values_map["rotation_mode"])
            if not item_properties:
                return {"package_role": package_role, "items": []}
            items.append(
                self._property_data_make_property_package_item(
                    object_ref=obj,
                    target_kind=PROPERTY_PACKAGE_SCOPE_OBJECT,
                    component_path=self._property_data_component_path_for_object(obj),
                    component_name=obj.name,
                    component_type=str(getattr(obj, "type", "") or "OBJECT"),
                    properties=item_properties,
                    metadata={},
                )
            )
            return {"package_role": package_role, "items": items}

        item_properties = {}
        if bool(properties_map.get("hide_viewport", False)) and hasattr(obj, "hide_viewport"):
            source = str(sources_map.get("hide_viewport", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
            item_properties["hide_viewport"] = bool(obj.hide_viewport) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["hide_viewport"])
        if bool(properties_map.get("hide_render", False)) and hasattr(obj, "hide_render"):
            source = str(sources_map.get("hide_render", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
            item_properties["hide_render"] = bool(obj.hide_render) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["hide_render"])
        if bool(properties_map.get("show_in_front", False)) and hasattr(obj, "show_in_front"):
            source = str(sources_map.get("show_in_front", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
            item_properties["show_in_front"] = bool(obj.show_in_front) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["show_in_front"])
        if bool(properties_map.get("show_name", False)) and hasattr(obj, "show_name"):
            source = str(sources_map.get("show_name", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
            item_properties["show_name"] = bool(obj.show_name) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["show_name"])
        if bool(properties_map.get("show_axis", False)) and hasattr(obj, "show_axis"):
            source = str(sources_map.get("show_axis", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
            item_properties["show_axis"] = bool(obj.show_axis) if source == PROPERTY_SOURCE_CURRENT else bool(values_map["show_axis"])
        if bool(properties_map.get("display_type", False)) and hasattr(obj, "display_type"):
            source = str(sources_map.get("display_type", PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
            item_properties["display_type"] = str(obj.display_type) if source == PROPERTY_SOURCE_CURRENT else str(values_map["display_type"])
        if not item_properties:
            return {"package_role": package_role, "items": []}
        items.append(
            self._property_data_make_property_package_item(
                object_ref=obj,
                target_kind=PROPERTY_PACKAGE_SCOPE_OBJECT,
                component_path=self._property_data_component_path_for_object(obj),
                component_name=obj.name,
                component_type=str(getattr(obj, "type", "") or "OBJECT"),
                properties=item_properties,
                metadata={},
            )
        )
        return {"package_role": package_role, "items": items}

    def _build_package_from_assignment_items(self, node, property_assignment, package_role, items):
        property_definition = self._property_assignment_to_definition(property_assignment, node.name)
        assignment_kind = str(property_assignment.get("assignment_kind", "") or "")
        if assignment_kind == PROPERTY_ASSIGNMENT_KIND_MODIFIER:
            if package_role == PROPERTY_PACKAGE_ROLE_SNAPSHOT:
                package = self._property_data_build_modifier_snapshot_property_package(
                    node.name,
                    str(uuid.uuid4()),
                    [
                        {
                            "object_id": int(item["object_id"]),
                            "object_name": item["object_name"],
                            "modifier_name": item["component_name"],
                            "props": item["properties"],
                        }
                        for item in items
                    ],
                )
            else:
                package = self._property_data_build_modifier_target_property_package(node.name, property_definition, items)
            package["metadata"] = copy.deepcopy(package.get("metadata", {}))
            package["metadata"]["definition_kind"] = PROPERTY_DEFINITION_KIND_MODIFIER
            package["metadata"]["property_definition"] = copy.deepcopy(property_definition)
            return package
        if assignment_kind == PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM:
            if package_role == PROPERTY_PACKAGE_ROLE_SNAPSHOT:
                package = self._property_data_build_object_transform_snapshot_property_package(
                    node.name,
                    str(uuid.uuid4()),
                    [
                        {
                            "object_id": int(item["object_id"]),
                            "object_name": item["object_name"],
                            "props": item["properties"],
                        }
                        for item in items
                    ],
                )
            else:
                package = self._property_data_build_object_transform_target_property_package(node.name, property_definition, items)
            package["metadata"] = copy.deepcopy(package.get("metadata", {}))
            package["metadata"]["definition_kind"] = PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM
            package["metadata"]["property_definition"] = copy.deepcopy(property_definition)
            return package
        if package_role == PROPERTY_PACKAGE_ROLE_SNAPSHOT:
            package = self._property_data_build_object_display_snapshot_property_package(
                node.name,
                str(uuid.uuid4()),
                [
                    {
                        "object_id": int(item["object_id"]),
                        "object_name": item["object_name"],
                        "props": item["properties"],
                    }
                    for item in items
                ],
            )
        else:
            package = self._property_data_build_object_display_target_property_package(node.name, property_definition, items)
        package["metadata"] = copy.deepcopy(package.get("metadata", {}))
        package["metadata"]["definition_kind"] = PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY
        package["metadata"]["property_definition"] = copy.deepcopy(property_definition)
        return package

    def _build_property_package_from_assignments(self, node, object_list_payload):
        linked_sources = []
        for socket in getattr(node, "inputs", []):
            if str(getattr(socket, "bl_idname", "") or "") != "AFSocketPropertyAssignment" or bool(getattr(socket, "af_is_virtual", False)):
                continue
            from_node, from_socket = _find_single_from_input_socket(socket)
            if from_node is None:
                continue
            linked_sources.append((from_node, from_socket))
        if not linked_sources:
            object_items = list((object_list_payload or {}).get("items", []))
            package_items = []
            for obj_item in object_items:
                object_name = str(obj_item.get("name", "") or "")
                object_id = int(obj_item.get("id", 0) or 0)
                obj = self._find_object_by_item_cached(obj_item) if object_name or object_id else None
                component_name = str(getattr(obj, "name", "") or object_name)
                if not component_name:
                    continue
                package_items.append(
                    {
                        "target_kind": PROPERTY_PACKAGE_SCOPE_OBJECT,
                        "object_id": int(getattr(obj, "session_uid", object_id) if obj is not None else object_id),
                        "object_name": component_name,
                        "component_path": self._property_data_component_path_for_object(obj) if obj is not None else f"{component_name}/OBJECT",
                        "component_name": component_name,
                        "component_type": str(getattr(obj, "type", "") or "OBJECT"),
                        "properties": {},
                        "metadata": {},
                    }
                )
            return self._property_data_make_property_package(
                package_role=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
                scope_kind=PROPERTY_PACKAGE_SCOPE_OBJECT,
                source_node=node.name,
                items=package_items,
            )

        aggregates = {}
        previous_context = dict(self.current_property_context or {}) if isinstance(self.current_property_context, dict) else self.current_property_context
        try:
            object_items = list(object_list_payload.get("items", []))
            object_count = len(object_items)
            for index, obj_item in enumerate(object_items):
                obj = self._find_object_by_item_cached(obj_item)
                if obj is None:
                    continue
                self.current_property_context = self._make_object_property_context(obj_item, obj, index, object_count, object_items, copy_payload=False)
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
                        item_payload = self._collect_property_assignment_items_for_object(
                            node,
                            entry,
                            obj,
                            obj_item,
                            source_node=from_node,
                            source_socket=from_socket,
                        )
                        if not item_payload["items"]:
                            continue
                        aggregate_key = (_property_assignment_signature(entry), str(item_payload["package_role"]))
                        aggregate = aggregates.get(aggregate_key)
                        if aggregate is None:
                            aggregates[aggregate_key] = {
                                "assignment": _clone_property_assignment(entry),
                                "package_role": str(item_payload["package_role"]),
                                "items": list(item_payload["items"]),
                            }
                        else:
                            aggregate["items"].extend(list(item_payload["items"]))
        finally:
            self.current_property_context = previous_context

        packages = []
        definitions = []
        for aggregate in aggregates.values():
            packages.append(
                self._build_package_from_assignment_items(
                    node,
                    aggregate["assignment"],
                    aggregate["package_role"],
                    aggregate["items"],
                )
            )
            definitions.append(self._property_assignment_to_definition(aggregate["assignment"], node.name))
        if not packages:
            return self._property_data_make_composite_property_package(
                node.name,
                [],
                metadata={"property_definition": _make_composite_property_definition(node.name, [])},
            )
        if len(packages) == 1:
            return packages[0]
        return self._property_data_make_composite_property_package(
            node.name,
            packages,
            metadata={"property_definition": _normalize_property_definition_entries(node.name, definitions)},
        )


__all__ = ["RuntimePropertyDataMixin"]
