import copy

import bpy

from ..runtime_core.module_loading import bind_partial_export
from ..runtime_core.constants import (
    FlowExecutionError,
    OBJECT_PERSISTENT_UUID_PROP,
    PROPERTY_DEFINITION_KIND_COMPOSITE,
    PROPERTY_DEFINITION_KIND_MODIFIER,
    PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
    PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
    PROPERTY_PACKAGE_ROLE_COMPOSITE,
    PROPERTY_PACKAGE_ROLE_SETTINGS,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    PROPERTY_PACKAGE_SCOPE_PHYSICS_BAKE,
    PROPERTY_SCOPE_KIND_MIXED,
)
from ..runtime_refs.objects import (
    _property_package_to_object_list as _property_package_to_object_list_impl,
)
from .definitions import (
    _clone_property_definition,
    _iter_property_definition_entries,
    _make_empty_property_definition,
    _merge_property_definitions,
    _normalize_property_definition_entries,
    _property_definition_has_content,
    _property_definition_matching_fields,
    _property_package_signature,
    _sanitize_reusable_property_definition,
    _validate_property_definition,
)
from .packages import (
    _build_modifier_snapshot_property_package as _build_modifier_snapshot_property_package_impl,
    _build_modifier_target_property_package as _build_modifier_target_property_package_impl,
    _build_object_display_snapshot_property_package as _build_object_display_snapshot_property_package_impl,
    _build_object_display_target_property_package as _build_object_display_target_property_package_impl,
    _build_object_transform_snapshot_property_package as _build_object_transform_snapshot_property_package_impl,
    _build_object_transform_target_property_package as _build_object_transform_target_property_package_impl,
    _build_physics_property_package as _build_physics_property_package_impl,
    _clone_property_package as _clone_property_package_impl,
    _is_composite_property_package as _is_composite_property_package_impl,
    _iter_property_package_entries as _iter_property_package_entries_impl,
    _make_composite_property_package as _make_composite_property_package_impl,
    _make_property_package as _make_property_package_impl,
    _make_property_package_item as _make_property_package_item_impl,
    _merge_property_packages as _merge_property_packages_impl,
    _merge_single_property_packages as _merge_single_property_packages_impl,
    _normalize_filtered_leaf_property_package as _normalize_filtered_leaf_property_package_impl,
    _physics_property_package_to_settings_payloads as _physics_property_package_to_settings_payloads_impl,
    _property_package_has_property_content as _property_package_has_property_content_impl,
    _property_package_item_count as _property_package_item_count_impl,
    _property_package_keep_objects_only as _property_package_keep_objects_only_impl,
    _property_package_to_definition as _property_package_to_definition_impl,
    _property_role_label as _property_role_label_impl,
    _property_scope_label as _property_scope_label_impl,
    _prune_redundant_object_only_package_entries as _prune_redundant_object_only_package_entries_impl,
    _summarize_property_package as _summarize_property_package_impl,
    _validate_property_package as _validate_property_package_impl,
)
from ..runtime_refs.objects import (
    _build_allowed_object_identity_filter as _build_allowed_object_identity_filter_impl,
    _dedup_obj_items as _dedup_obj_items_impl,
    _find_object_by_item as _find_object_by_item_impl,
    _normalize_object_item_reference as _normalize_object_item_reference_impl,
    _object_reference_identity as _object_reference_identity_impl,
    _property_package_item_matches_allowed_objects as _property_package_item_matches_allowed_objects_impl,
    _property_package_object_identity as _property_package_object_identity_impl,
)
from ..runtime_persistence.serialization import _ensure_object_persistent_uuid as _ensure_object_persistent_uuid_impl
from ..runtime_task_ref.helpers import _require_payload_object_ref as _require_payload_object_ref_impl


_ensure_object_persistent_uuid = bind_partial_export(
    _ensure_object_persistent_uuid_impl,
    object_persistent_uuid_prop=OBJECT_PERSISTENT_UUID_PROP,
)


_find_object_by_item = bind_partial_export(
    _find_object_by_item_impl,
    object_persistent_uuid_prop=OBJECT_PERSISTENT_UUID_PROP,
)


_normalize_object_item_reference = bind_partial_export(
    _normalize_object_item_reference_impl,
    object_reference_identity=lambda object_id, object_name, object_uuid="", object_resolver=None: _object_reference_identity(
        object_id,
        object_name,
        object_uuid=object_uuid,
        object_resolver=object_resolver,
    ),
)


_dedup_obj_items = bind_partial_export(
    _dedup_obj_items_impl,
    normalize_object_item_reference=_normalize_object_item_reference,
)


_require_payload_object_ref = bind_partial_export(
    _require_payload_object_ref_impl,
    flow_execution_error_cls=FlowExecutionError,
)


def _component_path_for_modifier(obj, modifier_name):
    return f"{obj.name}/{modifier_name}"


def _component_path_for_object(obj):
    return f"{obj.name}/OBJECT"


_property_scope_label = bind_partial_export(
    _property_scope_label_impl,
    property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
    property_package_scope_modifier=PROPERTY_PACKAGE_SCOPE_MODIFIER,
)


_property_role_label = bind_partial_export(
    _property_role_label_impl,
    property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
    property_package_role_settings=PROPERTY_PACKAGE_ROLE_SETTINGS,
    property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
)


_summarize_property_package = bind_partial_export(
    _summarize_property_package_impl,
    property_definition_kind_composite=PROPERTY_DEFINITION_KIND_COMPOSITE,
    property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
    property_package_role_settings=PROPERTY_PACKAGE_ROLE_SETTINGS,
    property_package_item_count=lambda package: _property_package_item_count(package),
    property_package_has_property_content=lambda package, node_name: _property_package_has_property_content(package, node_name),
    property_scope_label=lambda scope_kind: _property_scope_label(scope_kind),
    property_role_label=lambda package_role: _property_role_label(package_role),
)


_make_property_package_item = bind_partial_export(
    _make_property_package_item_impl,
    ensure_object_persistent_uuid=_ensure_object_persistent_uuid,
)


_make_property_package = _make_property_package_impl


_clone_property_package = _clone_property_package_impl


_make_composite_property_package = bind_partial_export(
    _make_composite_property_package_impl,
    clone_property_package=_clone_property_package,
    property_package_item_count=lambda package: _property_package_item_count(package),
    property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
    property_scope_kind_mixed=PROPERTY_SCOPE_KIND_MIXED,
)


_is_composite_property_package = bind_partial_export(
    _is_composite_property_package_impl,
    property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
)


_property_package_item_count = bind_partial_export(
    _property_package_item_count_impl,
    is_composite_property_package=_is_composite_property_package,
)


_validate_property_package = bind_partial_export(
    _validate_property_package_impl,
    flow_execution_error_cls=FlowExecutionError,
    property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
)


_iter_property_package_entries = bind_partial_export(
    _iter_property_package_entries_impl,
    validate_property_package=lambda package, node_name, allow_roles=None, allow_scopes=None: _validate_property_package(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    is_composite_property_package=lambda package: _is_composite_property_package(package),
    clone_property_package=_clone_property_package,
    flow_execution_error_cls=FlowExecutionError,
)


_property_package_to_object_list = bind_partial_export(
    _property_package_to_object_list_impl,
    is_composite_property_package=lambda package: _is_composite_property_package(package),
    dedup_obj_items=lambda items, sort_mode, object_resolver=None: _dedup_obj_items(
        items,
        sort_mode,
        object_resolver=object_resolver,
    ),
)


_property_package_to_definition = bind_partial_export(
    _property_package_to_definition_impl,
    validate_property_package=lambda package, node_name, allow_roles=None, allow_scopes=None: _validate_property_package(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    is_composite_property_package=lambda package: _is_composite_property_package(package),
    iter_property_definition_entries=_iter_property_definition_entries,
    normalize_property_definition_entries=_normalize_property_definition_entries,
    make_empty_property_definition=_make_empty_property_definition,
    clone_property_definition=_clone_property_definition,
    sanitize_reusable_property_definition=_sanitize_reusable_property_definition,
    validate_property_definition=_validate_property_definition,
)


_property_package_has_property_content = bind_partial_export(
    _property_package_has_property_content_impl,
    validate_property_package=lambda package, node_name, allow_roles=None, allow_scopes=None: _validate_property_package(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    is_composite_property_package=lambda package: _is_composite_property_package(package),
    property_definition_has_content=_property_definition_has_content,
)


_object_reference_identity = bind_partial_export(
    _object_reference_identity_impl,
    find_object_by_item=lambda item: _find_object_by_item(item),
    ensure_object_persistent_uuid=lambda obj: _ensure_object_persistent_uuid(obj),
)


_property_package_object_identity = bind_partial_export(
    _property_package_object_identity_impl,
    object_reference_identity=lambda object_id, object_name, object_uuid="", object_resolver=None: _object_reference_identity(
        object_id,
        object_name,
        object_uuid=object_uuid,
        object_resolver=object_resolver,
    ),
)


_build_allowed_object_identity_filter = bind_partial_export(
    _build_allowed_object_identity_filter_impl,
    object_reference_identity=lambda object_id, object_name, object_uuid="", object_resolver=None: _object_reference_identity(
        object_id,
        object_name,
        object_uuid=object_uuid,
        object_resolver=object_resolver,
    ),
)


_property_package_item_matches_allowed_objects = bind_partial_export(
    _property_package_item_matches_allowed_objects_impl,
    property_package_object_identity=lambda item, object_resolver=None: _property_package_object_identity(
        item,
        object_resolver=object_resolver,
    ),
)


_property_package_keep_objects_only = bind_partial_export(
    _property_package_keep_objects_only_impl,
    validate_property_package=lambda package, node_name, allow_roles=None, allow_scopes=None: _validate_property_package(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    iter_property_package_entries=lambda package, node_name, allow_roles=None, allow_scopes=None: _iter_property_package_entries(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    property_package_object_identity=lambda item, object_resolver=None: _property_package_object_identity(
        item,
        object_resolver=object_resolver,
    ),
    component_path_for_object=_component_path_for_object,
    make_property_package=_make_property_package,
    make_empty_property_definition=_make_empty_property_definition,
    property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
    property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
    property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
)


_prune_redundant_object_only_package_entries = bind_partial_export(
    _prune_redundant_object_only_package_entries_impl,
    is_composite_property_package=lambda package: _is_composite_property_package(package),
    iter_property_package_entries=lambda package, node_name, allow_roles=None, allow_scopes=None: _iter_property_package_entries(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    clone_property_package=_clone_property_package,
    property_package_has_property_content=lambda package, node_name: _property_package_has_property_content(package, node_name),
    property_package_object_identity=lambda item, object_resolver=None: _property_package_object_identity(
        item,
        object_resolver=object_resolver,
    ),
    make_empty_property_definition=_make_empty_property_definition,
    make_composite_property_package=lambda source_node, entries, metadata=None: _make_composite_property_package(
        source_node,
        entries,
        metadata=metadata,
    ),
    property_package_to_definition=lambda package, node_name: _property_package_to_definition(package, node_name),
)


_normalize_filtered_leaf_property_package = bind_partial_export(
    _normalize_filtered_leaf_property_package_impl,
    validate_property_package=lambda package, node_name, allow_roles=None, allow_scopes=None: _validate_property_package(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    is_composite_property_package=lambda package: _is_composite_property_package(package),
    clone_property_package=_clone_property_package,
    clone_property_definition=_clone_property_definition,
    validate_property_definition=_validate_property_definition,
    property_package_to_definition=lambda package, node_name: _property_package_to_definition(package, node_name),
    make_empty_property_definition=_make_empty_property_definition,
    make_composite_property_package=lambda source_node, entries, metadata=None: _make_composite_property_package(
        source_node,
        entries,
        metadata=metadata,
    ),
)


def _filter_property_package(
    package,
    object_ids,
    filter_mode,
    property_definition=None,
    object_filter_active=False,
    object_names=None,
    object_resolver=None,
    node_name="",
    stats=None,
):
    if _is_composite_property_package(package):
        filtered_entries = []
        for entry in package.get("entries", []):
            filtered_entry = _filter_property_package(
                entry,
                object_ids,
                filter_mode,
                property_definition=property_definition,
                object_filter_active=object_filter_active,
                object_names=object_names,
                object_resolver=object_resolver,
                node_name=node_name,
                stats=stats,
            )
            if _property_package_item_count(filtered_entry) <= 0:
                continue
            filtered_entries.append(filtered_entry)
        result = _make_composite_property_package(
            package.get("source_node", ""),
            filtered_entries,
            metadata={},
        )
        result = _prune_redundant_object_only_package_entries(
            result,
            object_resolver=object_resolver,
            node_name=node_name or str(package.get("source_node", "") or "Filter"),
        )
        result["metadata"] = copy.deepcopy(dict(result.get("metadata", {}) or {}))
        result["metadata"]["property_definition"] = _property_package_to_definition(
            result,
            node_name or str(package.get("source_node", "") or "Filter"),
        )
        if not _property_package_has_property_content(result, node_name or str(package.get("source_node", "") or "Filter")):
            return _property_package_keep_objects_only(result, object_resolver=object_resolver)
        return result
    keep = filter_mode == "KEEP_MATCHED"
    filtered_items = []
    object_only_candidates = []
    allowed_ids = {int(item_id) for item_id in object_ids}
    allowed_names = {
        str(object_name).strip()
        for object_name in list(object_names or [])
        if str(object_name).strip()
    }
    package_definition = _property_package_to_definition(package, node_name or str(package.get("source_node", "") or "Filter"))
    definition_filter_active = property_definition is not None and _property_definition_has_content(property_definition, node_name or "Filter")
    matching_definition_fields = set()
    if definition_filter_active:
        matching_definition_fields = _property_definition_matching_fields(package_definition, property_definition, node_name or "Filter")
    definition_match = bool(matching_definition_fields)
    if stats is not None and definition_match:
        stats["definition_match_count"] = int(stats.get("definition_match_count", 0)) + 1
    if keep and definition_filter_active and not definition_match:
        filtered_items = []
        for item in package.get("items", []):
            item_object_id = int(item.get("object_id", 0) or 0)
            item_object_name = str(item.get("object_name", "") or "").strip()
            matched_object = True
            if object_filter_active:
                matched_object = bool(
                    item_object_id in allowed_ids
                    or (item_object_name and item_object_name in allowed_names)
                )
                if stats is not None and matched_object:
                    stats["object_match_count"] = int(stats.get("object_match_count", 0)) + 1
            if matched_object:
                filtered_items.append(copy.deepcopy(item))
        filtered_leaf = _clone_property_package(package)
        filtered_leaf["items"] = filtered_items
        filtered_leaf["metadata"] = copy.deepcopy(dict(filtered_leaf.get("metadata", {}) or {}))
        filtered_leaf["metadata"]["count"] = len(filtered_items)
        filtered_leaf["metadata"]["object_count"] = len({int(item["object_id"]) for item in filtered_items})
        if len(filtered_items) <= 0:
            filtered_leaf["metadata"]["property_definition"] = _make_empty_property_definition(
                node_name or str(package.get("source_node", "") or "Filter")
            )
        return filtered_leaf
    if keep and object_filter_active and not definition_filter_active:
        for item in package.get("items", []):
            item_object_id = int(item.get("object_id", 0) or 0)
            item_object_name = str(item.get("object_name", "") or "").strip()
            matched_object = bool(
                item_object_id in allowed_ids
                or (item_object_name and item_object_name in allowed_names)
            )
            if stats is not None and matched_object:
                stats["object_match_count"] = int(stats.get("object_match_count", 0)) + 1
        filtered_items = []
        for item in package.get("items", []):
            item_object_id = int(item.get("object_id", 0) or 0)
            item_object_name = str(item.get("object_name", "") or "").strip()
            if item_object_id in allowed_ids or (item_object_name and item_object_name in allowed_names):
                filtered_items.append(copy.deepcopy(item))
        filtered_leaf = _clone_property_package(package)
        filtered_leaf["items"] = filtered_items
        filtered_leaf["metadata"] = copy.deepcopy(dict(filtered_leaf.get("metadata", {}) or {}))
        filtered_leaf["metadata"]["count"] = len(filtered_items)
        filtered_leaf["metadata"]["object_count"] = len({int(item["object_id"]) for item in filtered_items})
        if len(filtered_items) <= 0:
            filtered_leaf["metadata"]["property_definition"] = _make_empty_property_definition(
                node_name or str(package.get("source_node", "") or "Filter")
            )
        return filtered_leaf
    if not object_filter_active and not definition_filter_active and not keep:
        result = _clone_property_package(package)
        result["metadata"] = copy.deepcopy(result.get("metadata", {}))
        result["metadata"]["count"] = len(result.get("items", []))
        result["metadata"]["object_count"] = len({int(item["object_id"]) for item in result.get("items", [])})
        if len(result.get("items", [])) <= 0:
            result["metadata"]["property_definition"] = _make_empty_property_definition(
                node_name or str(package.get("source_node", "") or "Filter")
            )
        return result
    for item in package.get("items", []):
        matched_object = False
        if object_filter_active:
            item_object_id = int(item.get("object_id", 0) or 0)
            item_object_name = str(item.get("object_name", "") or "").strip()
            if item_object_id in allowed_ids:
                matched_object = True
            elif item_object_name and item_object_name in allowed_names:
                matched_object = True
        if stats is not None and object_filter_active and matched_object:
            stats["object_match_count"] = int(stats.get("object_match_count", 0)) + 1
        copied_item = copy.deepcopy(item)
        if keep:
            keep_item = True
            if object_filter_active:
                keep_item = keep_item and matched_object
            if definition_filter_active:
                keep_item = keep_item and definition_match
            if not keep_item:
                continue
            copied_item["properties"] = {
                str(key): copy.deepcopy(value)
                for key, value in dict(copied_item.get("properties", {}) or {}).items()
                if str(key) in matching_definition_fields
            }
            if not copied_item["properties"]:
                object_only_candidates.append(copy.deepcopy(copied_item))
                continue
        else:
            if object_filter_active and definition_filter_active:
                if matched_object:
                    continue
                if definition_match:
                    copied_item["properties"] = {
                        str(key): copy.deepcopy(value)
                        for key, value in dict(copied_item.get("properties", {}) or {}).items()
                        if str(key) not in matching_definition_fields
                    }
                    if not copied_item["properties"]:
                        object_only_candidates.append(copy.deepcopy(copied_item))
                        continue
            elif object_filter_active:
                if matched_object:
                    continue
            elif definition_filter_active:
                if definition_match:
                    copied_item["properties"] = {
                        str(key): copy.deepcopy(value)
                        for key, value in dict(copied_item.get("properties", {}) or {}).items()
                        if str(key) not in matching_definition_fields
                    }
                    if not copied_item["properties"]:
                        object_only_candidates.append(copy.deepcopy(copied_item))
                        continue
        filtered_items.append(copied_item)
    if not filtered_items and object_only_candidates:
        objects_only_package = _clone_property_package(package)
        objects_only_package["items"] = object_only_candidates
        objects_only_package["metadata"] = copy.deepcopy(dict(objects_only_package.get("metadata", {}) or {}))
        objects_only_package["metadata"]["count"] = len(object_only_candidates)
        objects_only_package["metadata"]["object_count"] = len({int(item["object_id"]) for item in object_only_candidates})
        return _property_package_keep_objects_only(objects_only_package, object_resolver=object_resolver)
    if filtered_items and not any(dict(item.get("properties", {}) or {}) for item in filtered_items):
        objects_only_package = _clone_property_package(package)
        objects_only_package["items"] = filtered_items
        objects_only_package["metadata"] = copy.deepcopy(dict(objects_only_package.get("metadata", {}) or {}))
        objects_only_package["metadata"]["count"] = len(filtered_items)
        objects_only_package["metadata"]["object_count"] = len({int(item["object_id"]) for item in filtered_items})
        return _property_package_keep_objects_only(objects_only_package, object_resolver=object_resolver)
    result = _clone_property_package(package)
    result["items"] = filtered_items
    result["metadata"] = copy.deepcopy(result.get("metadata", {}))
    result["metadata"]["count"] = len(filtered_items)
    result["metadata"]["object_count"] = len({int(item["object_id"]) for item in filtered_items})
    if definition_filter_active and filtered_items:
        trimmed_definition = _clone_property_definition(package_definition)
        if keep:
            trimmed_definition["properties"] = {
                key: bool(str(key) in matching_definition_fields)
                for key, enabled in dict(package_definition.get("properties", {}) or {}).items()
                if bool(enabled) and str(key) in matching_definition_fields
            }
        else:
            trimmed_definition["properties"] = {
                key: bool(str(key) not in matching_definition_fields)
                for key, enabled in dict(package_definition.get("properties", {}) or {}).items()
                if bool(enabled) and str(key) not in matching_definition_fields
            }
        trimmed_definition["metadata"] = copy.deepcopy(dict(trimmed_definition.get("metadata", {}) or {}))
        trimmed_definition["metadata"]["count"] = len(trimmed_definition["properties"])
        result["metadata"]["property_definition"] = (
            trimmed_definition if trimmed_definition["properties"] else _make_empty_property_definition(
                node_name or str(package.get("source_node", "") or "Filter")
            )
        )
    if len(filtered_items) <= 0:
        result["metadata"]["property_definition"] = _make_empty_property_definition(
            node_name or str(package.get("source_node", "") or "Filter")
        )
    else:
        result = _normalize_filtered_leaf_property_package(
            result,
            node_name or str(package.get("source_node", "") or "Filter"),
        )
    if object_only_candidates:
        objects_only_package = _clone_property_package(package)
        objects_only_package["items"] = object_only_candidates
        objects_only_package["metadata"] = copy.deepcopy(dict(objects_only_package.get("metadata", {}) or {}))
        objects_only_package["metadata"]["count"] = len(object_only_candidates)
        objects_only_package["metadata"]["object_count"] = len({int(item["object_id"]) for item in object_only_candidates})
        objects_only_entry = _property_package_keep_objects_only(objects_only_package, object_resolver=object_resolver)
        combined_result = _make_composite_property_package(
            str(package.get("source_node", "") or ""),
            [result, objects_only_entry],
            metadata={},
        )
        combined_result["metadata"] = copy.deepcopy(dict(combined_result.get("metadata", {}) or {}))
        combined_result["metadata"]["property_definition"] = _property_package_to_definition(
            combined_result,
            node_name or str(package.get("source_node", "") or "Filter"),
        )
        return combined_result
    return result


_merge_single_property_packages = bind_partial_export(
    _merge_single_property_packages_impl,
    flow_execution_error_cls=FlowExecutionError,
    clone_property_package=_clone_property_package,
    clone_property_definition=_clone_property_definition,
    merge_property_definitions=_merge_property_definitions,
)


_merge_property_packages = bind_partial_export(
    _merge_property_packages_impl,
    validate_property_package=lambda package, node_name, allow_roles=None, allow_scopes=None: _validate_property_package(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    iter_property_package_entries=lambda package, node_name, allow_roles=None, allow_scopes=None: _iter_property_package_entries(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    property_package_signature=_property_package_signature,
    clone_property_package=_clone_property_package,
    make_composite_property_package=lambda source_node, entries, metadata=None: _make_composite_property_package(
        source_node,
        entries,
        metadata=metadata,
    ),
    normalize_property_definition_entries=_normalize_property_definition_entries,
    property_package_to_definition=lambda package, node_name: _property_package_to_definition(package, node_name),
    merge_single_property_packages=lambda base_package, add_package, conflict_policy, node_name: _merge_single_property_packages(
        base_package,
        add_package,
        conflict_policy,
        node_name,
    ),
)


_build_modifier_snapshot_property_package = bind_partial_export(
    _build_modifier_snapshot_property_package_impl,
    bpy_module=bpy,
    find_object_by_item=lambda item: _find_object_by_item(item),
    make_property_package_item=lambda object_ref, target_kind, component_path, component_name, component_type, properties, metadata=None: _make_property_package_item(
        object_ref,
        target_kind,
        component_path,
        component_name,
        component_type,
        properties,
        metadata=metadata,
    ),
    make_property_package=_make_property_package,
    component_path_for_modifier=_component_path_for_modifier,
    property_package_scope_modifier=PROPERTY_PACKAGE_SCOPE_MODIFIER,
    property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
)


_build_modifier_target_property_package = bind_partial_export(
    _build_modifier_target_property_package_impl,
    validate_property_definition=_validate_property_definition,
    make_property_package=_make_property_package,
    clone_property_definition=_clone_property_definition,
    property_definition_kind_modifier=PROPERTY_DEFINITION_KIND_MODIFIER,
    property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
    property_package_scope_modifier=PROPERTY_PACKAGE_SCOPE_MODIFIER,
)


_build_object_display_snapshot_property_package = bind_partial_export(
    _build_object_display_snapshot_property_package_impl,
    bpy_module=bpy,
    find_object_by_item=lambda item: _find_object_by_item(item),
    make_property_package_item=lambda object_ref, target_kind, component_path, component_name, component_type, properties, metadata=None: _make_property_package_item(
        object_ref,
        target_kind,
        component_path,
        component_name,
        component_type,
        properties,
        metadata=metadata,
    ),
    make_property_package=_make_property_package,
    component_path_for_object=_component_path_for_object,
    property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
    property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
)


_build_object_display_target_property_package = bind_partial_export(
    _build_object_display_target_property_package_impl,
    validate_property_definition=_validate_property_definition,
    make_property_package=_make_property_package,
    clone_property_definition=_clone_property_definition,
    property_definition_kind_object_display=PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY,
    property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
    property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
)


_build_object_transform_snapshot_property_package = bind_partial_export(
    _build_object_transform_snapshot_property_package_impl,
    bpy_module=bpy,
    find_object_by_item=lambda item: _find_object_by_item(item),
    make_property_package_item=lambda object_ref, target_kind, component_path, component_name, component_type, properties, metadata=None: _make_property_package_item(
        object_ref,
        target_kind,
        component_path,
        component_name,
        component_type,
        properties,
        metadata=metadata,
    ),
    make_property_package=_make_property_package,
    component_path_for_object=_component_path_for_object,
    property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
    property_package_role_snapshot=PROPERTY_PACKAGE_ROLE_SNAPSHOT,
)


_build_object_transform_target_property_package = bind_partial_export(
    _build_object_transform_target_property_package_impl,
    validate_property_definition=_validate_property_definition,
    make_property_package=_make_property_package,
    clone_property_definition=_clone_property_definition,
    property_definition_kind_object_transform=PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM,
    property_package_role_target=PROPERTY_PACKAGE_ROLE_TARGET,
    property_package_scope_object=PROPERTY_PACKAGE_SCOPE_OBJECT,
)


_build_physics_property_package = bind_partial_export(
    _build_physics_property_package_impl,
    require_payload_object_ref=lambda payload, node_name, object_name_key="object_name": _require_payload_object_ref(
        payload,
        node_name,
        object_name_key=object_name_key,
    ),
    make_property_package_item=lambda object_ref, target_kind, component_path, component_name, component_type, properties, metadata=None: _make_property_package_item(
        object_ref,
        target_kind,
        component_path,
        component_name,
        component_type,
        properties,
        metadata=metadata,
    ),
    make_property_package=_make_property_package,
    component_path_for_modifier=_component_path_for_modifier,
    property_package_scope_physics_bake=PROPERTY_PACKAGE_SCOPE_PHYSICS_BAKE,
    property_package_role_settings=PROPERTY_PACKAGE_ROLE_SETTINGS,
)


_physics_property_package_to_settings_payloads = bind_partial_export(
    _physics_property_package_to_settings_payloads_impl,
    validate_property_package=lambda package, node_name, allow_roles=None, allow_scopes=None: _validate_property_package(
        package,
        node_name,
        allow_roles=allow_roles,
        allow_scopes=allow_scopes,
    ),
    find_object_by_item=lambda item: _find_object_by_item(item),
    component_path_for_modifier=_component_path_for_modifier,
    ensure_object_persistent_uuid=lambda obj: _ensure_object_persistent_uuid(obj),
    flow_execution_error_cls=FlowExecutionError,
    property_package_role_settings=PROPERTY_PACKAGE_ROLE_SETTINGS,
    property_package_scope_physics_bake=PROPERTY_PACKAGE_SCOPE_PHYSICS_BAKE,
)


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
