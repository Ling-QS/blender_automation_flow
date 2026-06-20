import copy

from ..runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_ASSIGNMENT_KIND_COMPOSITE,
    PROPERTY_ASSIGNMENT_KIND_MODIFIER,
    PROPERTY_DEFINITION_KIND_COMPOSITE,
    PROPERTY_DEFINITION_KIND_MODIFIER,
    PROPERTY_SCOPE_KIND_MIXED,
    PROPERTY_SOURCE_CURRENT,
    PROPERTY_SOURCE_VALUE,
)


def _metadata_bool(metadata, key, default=False):
    value = dict(metadata or {}).get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _modifier_filter_settings_from_metadata(metadata):
    metadata = dict(metadata or {})
    raw_modifier_filter = str(metadata.get("modifier_type_filter", "ALL") or "ALL")
    raw_name_filter = str(metadata.get("modifier_name_filter", "") or "").strip()
    has_type_flag = "filter_by_type" in metadata
    has_name_flag = "filter_by_name" in metadata
    filter_by_type = _metadata_bool(metadata, "filter_by_type", raw_modifier_filter != "ALL") if has_type_flag else raw_modifier_filter != "ALL"
    filter_by_name = _metadata_bool(metadata, "filter_by_name", bool(raw_name_filter)) if has_name_flag else bool(raw_name_filter)
    return {
        "filter_by_type": bool(filter_by_type),
        "filter_by_name": bool(filter_by_name),
        "filter_by_context": _metadata_bool(metadata, "filter_by_context", False),
        "modifier_type_filter": raw_modifier_filter if filter_by_type else "ALL",
        "modifier_name_filter": raw_name_filter if filter_by_name else "",
        "modifier_name_match_mode": str(metadata.get("modifier_name_match_mode", "EXACT") or "EXACT"),
        "context_filter_passed": _metadata_bool(metadata, "context_filter_passed", True),
    }


def _modifier_filter_settings_from_node(node, name_filter_text=""):
    filter_by_type = bool(getattr(node, "filter_by_type", False))
    filter_by_name = bool(getattr(node, "filter_by_name", False))
    filter_by_context = bool(getattr(node, "filter_by_context", False))
    return {
        "filter_by_type": filter_by_type,
        "filter_by_name": filter_by_name,
        "filter_by_context": filter_by_context,
        "modifier_type_filter": str(getattr(node, "modifier_type_filter", "ALL") or "ALL") if filter_by_type else "ALL",
        "modifier_name_filter": str(name_filter_text or "").strip() if filter_by_name else "",
        "modifier_name_match_mode": str(getattr(node, "modifier_name_match_mode", "EXACT") or "EXACT"),
    }


def _matches_modifier_filter(modifier, modifier_filter):
    if modifier_filter == "ALL":
        return True
    if modifier_filter == "GEOMETRY_NODES":
        return modifier.type == "NODES"
    return True


def _matches_modifier_name_filter(modifier, modifier_name_filter="", match_mode="EXACT"):
    filter_text = str(modifier_name_filter or "").strip()
    if not filter_text:
        return True
    modifier_name = str(getattr(modifier, "name", "") or "")
    mode = str(match_mode or "EXACT")
    if mode == "CONTAINS":
        return filter_text in modifier_name
    if mode == "STARTS_WITH":
        return modifier_name.startswith(filter_text)
    return modifier_name == filter_text


def _matches_modifier_filters(modifier, modifier_filter="ALL", modifier_name_filter="", modifier_name_match_mode="EXACT"):
    return _matches_modifier_filter(modifier, modifier_filter) and _matches_modifier_name_filter(
        modifier,
        modifier_name_filter,
        modifier_name_match_mode,
    )


def _make_property_definition(definition_kind, scope_kind, source_node, properties, metadata=None):
    safe_properties = copy.deepcopy(properties or {})
    safe_metadata = copy.deepcopy(metadata or {})
    safe_metadata.setdefault("count", len([key for key, enabled in safe_properties.items() if enabled]))
    return {
        "definition_kind": str(definition_kind),
        "scope_kind": str(scope_kind),
        "source_node": str(source_node or ""),
        "properties": safe_properties,
        "metadata": safe_metadata,
    }


def _make_property_assignment(assignment_kind, scope_kind, source_node, properties, sources, values, metadata=None):
    safe_properties = copy.deepcopy(properties or {})
    safe_sources = copy.deepcopy(sources or {})
    safe_values = copy.deepcopy(values or {})
    safe_metadata = copy.deepcopy(metadata or {})
    safe_metadata.setdefault("count", len([key for key, enabled in safe_properties.items() if enabled]))
    return {
        "assignment_kind": str(assignment_kind),
        "scope_kind": str(scope_kind),
        "source_node": str(source_node or ""),
        "properties": safe_properties,
        "sources": safe_sources,
        "values": safe_values,
        "metadata": safe_metadata,
    }


def _make_composite_property_definition(source_node, entries, metadata=None):
    safe_entries = [_clone_property_definition(entry) for entry in (entries or [])]
    safe_metadata = copy.deepcopy(metadata or {})
    safe_metadata.setdefault("entry_count", len(safe_entries))
    safe_metadata.setdefault("count", len(safe_entries))
    return {
        "definition_kind": PROPERTY_DEFINITION_KIND_COMPOSITE,
        "scope_kind": PROPERTY_SCOPE_KIND_MIXED,
        "source_node": str(source_node or ""),
        "entries": safe_entries,
        "metadata": safe_metadata,
    }


def _make_composite_property_assignment(source_node, entries, metadata=None):
    safe_entries = [_clone_property_assignment(entry) for entry in (entries or [])]
    safe_metadata = copy.deepcopy(metadata or {})
    safe_metadata.setdefault("entry_count", len(safe_entries))
    safe_metadata.setdefault("count", len(safe_entries))
    return {
        "assignment_kind": PROPERTY_ASSIGNMENT_KIND_COMPOSITE,
        "scope_kind": PROPERTY_SCOPE_KIND_MIXED,
        "source_node": str(source_node or ""),
        "entries": safe_entries,
        "metadata": safe_metadata,
    }


def _clone_property_definition(property_definition):
    return copy.deepcopy(property_definition)


def _clone_property_assignment(property_assignment):
    return copy.deepcopy(property_assignment)


def _is_composite_property_definition(property_definition):
    return isinstance(property_definition, dict) and str(property_definition.get("definition_kind", "") or "") == PROPERTY_DEFINITION_KIND_COMPOSITE


def _is_composite_property_assignment(property_assignment):
    return isinstance(property_assignment, dict) and str(property_assignment.get("assignment_kind", "") or "") == PROPERTY_ASSIGNMENT_KIND_COMPOSITE


def _make_empty_property_definition(source_node=""):
    return _make_composite_property_definition(source_node, [], metadata={"entry_count": 0, "count": 0})


def _property_definition_signature(property_definition):
    definition_kind = str(property_definition.get("definition_kind", "") or "")
    scope_kind = str(property_definition.get("scope_kind", "") or "")
    metadata = dict(property_definition.get("metadata", {}) or {})
    if definition_kind == PROPERTY_DEFINITION_KIND_MODIFIER:
        settings = _modifier_filter_settings_from_metadata(metadata)
        return (
            definition_kind,
            scope_kind,
            bool(settings["filter_by_type"]),
            bool(settings["filter_by_name"]),
            bool(settings["filter_by_context"]),
            str(settings["modifier_type_filter"]),
            str(settings["modifier_name_filter"]),
            str(settings["modifier_name_match_mode"]),
        )
    return (definition_kind, scope_kind, "")


def _property_assignment_signature(property_assignment):
    assignment_kind = str(property_assignment.get("assignment_kind", "") or "")
    scope_kind = str(property_assignment.get("scope_kind", "") or "")
    metadata = dict(property_assignment.get("metadata", {}) or {})
    if assignment_kind == PROPERTY_ASSIGNMENT_KIND_MODIFIER:
        settings = _modifier_filter_settings_from_metadata(metadata)
        return (
            assignment_kind,
            scope_kind,
            bool(settings["filter_by_type"]),
            bool(settings["filter_by_name"]),
            bool(settings["filter_by_context"]),
            str(settings["modifier_type_filter"]),
            str(settings["modifier_name_filter"]),
            str(settings["modifier_name_match_mode"]),
        )
    return (assignment_kind, scope_kind, "")


def _property_assignment_structure_key(property_assignment):
    assignment_kind = str(property_assignment.get("assignment_kind", "") or "")
    scope_kind = str(property_assignment.get("scope_kind", "") or "")
    metadata = dict(property_assignment.get("metadata", {}) or {})
    properties = tuple(
        sorted(
            (str(key), bool(value))
            for key, value in dict(property_assignment.get("properties", {}) or {}).items()
        )
    )
    sources = tuple(
        sorted(
            (str(key), str(value or PROPERTY_SOURCE_VALUE))
            for key, value in dict(property_assignment.get("sources", {}) or {}).items()
        )
    )
    if assignment_kind == PROPERTY_ASSIGNMENT_KIND_MODIFIER:
        settings = _modifier_filter_settings_from_metadata(metadata)
        return (
            assignment_kind,
            scope_kind,
            bool(settings["filter_by_type"]),
            bool(settings["filter_by_name"]),
            bool(settings["filter_by_context"]),
            str(settings["modifier_type_filter"]),
            str(settings["modifier_name_filter"]),
            str(settings["modifier_name_match_mode"]),
            properties,
            sources,
        )
    return (
        assignment_kind,
        scope_kind,
        "",
        properties,
        sources,
    )


def _property_package_signature(package):
    package_role = str(package.get("package_role", "") or "")
    scope_kind = str(package.get("scope_kind", "") or "")
    property_definition = dict(package.get("metadata", {}).get("property_definition", {}) or {})
    return (package_role, scope_kind, _property_definition_signature(property_definition) if property_definition else ("", "", ""))


def _iter_property_definition_entries(property_definition, node_name, allow_kinds=None):
    property_definition = _validate_property_definition(property_definition, node_name)
    if _is_composite_property_definition(property_definition):
        entries = property_definition.get("entries")
        if not isinstance(entries, list):
            raise FlowExecutionError("AF_E011", "Composite Property Definition is missing entries", node_name)
        flattened = []
        for entry in entries:
            flattened.extend(_iter_property_definition_entries(entry, node_name, allow_kinds=allow_kinds))
        return flattened

    definition_kind = str(property_definition.get("definition_kind", "") or "")
    if allow_kinds is not None and definition_kind not in set(allow_kinds):
        raise FlowExecutionError("AF_E011", f"Property Definition kind '{definition_kind}' is not supported", node_name)
    return [_clone_property_definition(property_definition)]


def _iter_property_assignment_entries(property_assignment, node_name, allow_kinds=None):
    property_assignment = _validate_property_assignment(property_assignment, node_name)
    if _is_composite_property_assignment(property_assignment):
        entries = property_assignment.get("entries")
        if not isinstance(entries, list):
            raise FlowExecutionError("AF_E011", "Composite Property Assignment is missing entries", node_name)
        flattened = []
        for entry in entries:
            flattened.extend(_iter_property_assignment_entries(entry, node_name, allow_kinds=allow_kinds))
        return flattened

    assignment_kind = str(property_assignment.get("assignment_kind", "") or "")
    if allow_kinds is not None and assignment_kind not in set(allow_kinds):
        raise FlowExecutionError("AF_E011", f"Property Assignment kind '{assignment_kind}' is not supported", node_name)
    return [_clone_property_assignment(property_assignment)]


def _normalize_property_definition_entries(source_node, entries):
    flattened_entries = []
    for entry in entries or []:
        flattened_entries.extend(_iter_property_definition_entries(entry, source_node))
    if not flattened_entries:
        return _make_empty_property_definition(source_node)

    merged_map = {}
    ordered_keys = []
    for entry in flattened_entries:
        signature = _property_definition_signature(entry)
        existing = merged_map.get(signature)
        if existing is None:
            merged_map[signature] = _clone_property_definition(entry)
            ordered_keys.append(signature)
            continue
        existing_props = existing.setdefault("properties", {})
        for prop_key, enabled in dict(entry.get("properties", {}) or {}).items():
            existing_props[str(prop_key)] = bool(existing_props.get(str(prop_key), False) or bool(enabled))
        if signature[0] == PROPERTY_DEFINITION_KIND_MODIFIER:
            current_settings = _modifier_filter_settings_from_metadata(existing.get("metadata", {}))
            new_settings = _modifier_filter_settings_from_metadata(entry.get("metadata", {}))
            if bool(current_settings["filter_by_type"]) != bool(new_settings["filter_by_type"]) or str(current_settings["modifier_type_filter"]) != str(new_settings["modifier_type_filter"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Definitions with different Modifier Filter values", source_node)
            if bool(current_settings["filter_by_name"]) != bool(new_settings["filter_by_name"]) or str(current_settings["modifier_name_filter"]) != str(new_settings["modifier_name_filter"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Definitions with different Modifier Name values", source_node)
            if str(current_settings["modifier_name_match_mode"]) != str(new_settings["modifier_name_match_mode"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Definitions with different Name Match values", source_node)
            if bool(current_settings["filter_by_context"]) != bool(new_settings["filter_by_context"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Definitions with different Context Filter values", source_node)
        existing_metadata = existing.setdefault("metadata", {})
        entry_metadata = dict(entry.get("metadata", {}) or {})
        entry_metadata["count"] = len([key for key, enabled in existing_props.items() if bool(enabled)])
        existing_metadata.update(copy.deepcopy(entry_metadata))
    normalized = [merged_map[key] for key in ordered_keys]
    if len(normalized) == 1:
        return normalized[0]
    return _make_composite_property_definition(source_node, normalized)


def _normalize_property_assignment_entries(source_node, entries, conflict_policy="LAST_WINS"):
    merged_map = {}
    ordered_keys = []
    for entry in entries:
        signature = _property_assignment_signature(entry)
        existing = merged_map.get(signature)
        if existing is None:
            merged_map[signature] = _clone_property_assignment(entry)
            ordered_keys.append(signature)
            continue
        existing_properties = existing.setdefault("properties", {})
        for prop_key, enabled in dict(entry.get("properties", {}) or {}).items():
            existing_properties[str(prop_key)] = bool(existing_properties.get(str(prop_key), False) or bool(enabled))
        existing_sources = existing.setdefault("sources", {})
        existing_values = existing.setdefault("values", {})
        for prop_key, source in dict(entry.get("sources", {}) or {}).items():
            key = str(prop_key)
            new_source = str(source or PROPERTY_SOURCE_VALUE)
            old_source = str(existing_sources.get(key, new_source) or new_source)
            if key in existing_sources and old_source != new_source and conflict_policy == "ERROR":
                raise FlowExecutionError("AF_E020", f"Property Assignment source conflict at '{signature[0]}/{key}'", source_node)
            if key in existing_sources and old_source != new_source and conflict_policy == "FIRST_WINS":
                continue
            existing_sources[key] = new_source
        for value_key, value in dict(entry.get("values", {}) or {}).items():
            if value_key in existing_values and existing_values[value_key] != value:
                if conflict_policy == "ERROR":
                    raise FlowExecutionError("AF_E020", f"Property Assignment conflict at '{signature[0]}/{value_key}'", source_node)
                if conflict_policy == "FIRST_WINS":
                    continue
            existing_values[str(value_key)] = copy.deepcopy(value)
        if signature[0] == PROPERTY_ASSIGNMENT_KIND_MODIFIER:
            current_settings = _modifier_filter_settings_from_metadata(existing.get("metadata", {}))
            new_settings = _modifier_filter_settings_from_metadata(entry.get("metadata", {}))
            if bool(current_settings["filter_by_type"]) != bool(new_settings["filter_by_type"]) or str(current_settings["modifier_type_filter"]) != str(new_settings["modifier_type_filter"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Assignments with different Modifier Filter values", source_node)
            if bool(current_settings["filter_by_name"]) != bool(new_settings["filter_by_name"]) or str(current_settings["modifier_name_filter"]) != str(new_settings["modifier_name_filter"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Assignments with different Modifier Name values", source_node)
            if str(current_settings["modifier_name_match_mode"]) != str(new_settings["modifier_name_match_mode"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Assignments with different Name Match values", source_node)
            if bool(current_settings["filter_by_context"]) != bool(new_settings["filter_by_context"]):
                raise FlowExecutionError("AF_E020", "Cannot merge Modifier Property Assignments with different Context Filter values", source_node)
        existing_metadata = existing.setdefault("metadata", {})
        entry_metadata = dict(entry.get("metadata", {}) or {})
        entry_metadata["count"] = len([key for key, enabled in existing_properties.items() if bool(enabled)])
        existing_metadata.update(copy.deepcopy(entry_metadata))
    normalized = [merged_map[key] for key in ordered_keys]
    if len(normalized) == 1:
        return normalized[0]
    return _make_composite_property_assignment(source_node, normalized)


def _merge_property_definitions(base_definition, add_definition, node_name):
    entries = _iter_property_definition_entries(base_definition, node_name)
    entries.extend(_iter_property_definition_entries(add_definition, node_name))
    return _normalize_property_definition_entries(node_name, entries)


def _merge_property_assignments(base_assignment, add_assignment, conflict_policy, node_name):
    entries = _iter_property_assignment_entries(base_assignment, node_name)
    entries.extend(_iter_property_assignment_entries(add_assignment, node_name))
    return _normalize_property_assignment_entries(node_name, entries, conflict_policy=conflict_policy)


def _validate_property_definition(property_definition, node_name, allow_kinds=None):
    if not isinstance(property_definition, dict):
        raise FlowExecutionError("AF_E011", "Property Definition payload is invalid", node_name)
    definition_kind = str(property_definition.get("definition_kind", "") or "")
    if not definition_kind:
        raise FlowExecutionError("AF_E011", "Property Definition kind is missing", node_name)
    if definition_kind == PROPERTY_DEFINITION_KIND_COMPOSITE:
        entries = property_definition.get("entries")
        if not isinstance(entries, list):
            raise FlowExecutionError("AF_E011", "Composite Property Definition is missing entries", node_name)
        if allow_kinds is not None and PROPERTY_DEFINITION_KIND_COMPOSITE not in set(allow_kinds):
            allowed = set(allow_kinds)
            for entry in entries:
                _validate_property_definition(entry, node_name, allow_kinds=allowed)
        return property_definition

    properties = property_definition.get("properties")
    if not isinstance(properties, dict):
        raise FlowExecutionError("AF_E011", "Property Definition is missing properties", node_name)
    if allow_kinds is not None and definition_kind not in set(allow_kinds):
        raise FlowExecutionError("AF_E011", f"Property Definition kind '{definition_kind}' is not supported", node_name)
    return property_definition


def _validate_property_assignment(property_assignment, node_name, allow_kinds=None):
    if not isinstance(property_assignment, dict):
        raise FlowExecutionError("AF_E011", "Property Assignment payload is invalid", node_name)
    assignment_kind = str(property_assignment.get("assignment_kind", "") or "")
    if not assignment_kind:
        raise FlowExecutionError("AF_E011", "Property Assignment kind is missing", node_name)
    if assignment_kind == PROPERTY_ASSIGNMENT_KIND_COMPOSITE:
        entries = property_assignment.get("entries")
        if not isinstance(entries, list):
            raise FlowExecutionError("AF_E011", "Composite Property Assignment is missing entries", node_name)
        if allow_kinds is not None and PROPERTY_ASSIGNMENT_KIND_COMPOSITE not in set(allow_kinds):
            allowed = set(allow_kinds)
            for entry in entries:
                _validate_property_assignment(entry, node_name, allow_kinds=allowed)
        return property_assignment

    properties = property_assignment.get("properties")
    sources = property_assignment.get("sources")
    values = property_assignment.get("values")
    if not isinstance(properties, dict):
        raise FlowExecutionError("AF_E011", "Property Assignment is missing properties", node_name)
    if not isinstance(sources, dict):
        raise FlowExecutionError("AF_E011", "Property Assignment is missing sources", node_name)
    if not isinstance(values, dict):
        raise FlowExecutionError("AF_E011", "Property Assignment is missing values", node_name)
    if allow_kinds is not None and assignment_kind not in set(allow_kinds):
        raise FlowExecutionError("AF_E011", f"Property Assignment kind '{assignment_kind}' is not supported", node_name)
    return property_assignment


def _property_definition_has_content(property_definition, node_name):
    return len(_iter_property_definition_entries(property_definition, node_name)) > 0


def _property_definition_to_assignment(property_definition, node_name, source_mode=PROPERTY_SOURCE_CURRENT):
    property_definition = _validate_property_definition(property_definition, node_name)
    if _is_composite_property_definition(property_definition):
        converted_entries = [
            _property_definition_to_assignment(entry, node_name, source_mode=source_mode)
            for entry in list(property_definition.get("entries", []))
        ]
        return _make_composite_property_assignment(
            str(property_definition.get("source_node", "") or node_name),
            converted_entries,
            metadata=copy.deepcopy(dict(property_definition.get("metadata", {}) or {})),
        )
    properties = {
        str(key): bool(enabled)
        for key, enabled in dict(property_definition.get("properties", {}) or {}).items()
    }
    sources = {
        str(key): str(source_mode or PROPERTY_SOURCE_CURRENT)
        for key, enabled in properties.items()
        if bool(enabled)
    }
    return _make_property_assignment(
        assignment_kind=str(property_definition.get("definition_kind", "") or ""),
        scope_kind=str(property_definition.get("scope_kind", "") or ""),
        source_node=str(property_definition.get("source_node", "") or ""),
        properties=properties,
        sources=sources,
        values={},
        metadata=copy.deepcopy(dict(property_definition.get("metadata", {}) or {})),
    )


def _property_assignment_to_definition_payload(property_assignment, node_name):
    property_assignment = _validate_property_assignment(property_assignment, node_name)
    if _is_composite_property_assignment(property_assignment):
        converted_entries = [
            _property_assignment_to_definition_payload(entry, node_name)
            for entry in list(property_assignment.get("entries", []))
        ]
        return _make_composite_property_definition(
            str(property_assignment.get("source_node", "") or node_name),
            converted_entries,
            metadata=copy.deepcopy(dict(property_assignment.get("metadata", {}) or {})),
        )
    return _make_property_definition(
        definition_kind=str(property_assignment.get("assignment_kind", "") or ""),
        scope_kind=str(property_assignment.get("scope_kind", "") or ""),
        source_node=str(property_assignment.get("source_node", "") or ""),
        properties={
            str(key): bool(enabled)
            for key, enabled in dict(property_assignment.get("properties", {}) or {}).items()
        },
        metadata=copy.deepcopy(dict(property_assignment.get("metadata", {}) or {})),
    )


def _property_definition_matches_filter(target_definition, filter_definition, node_name):
    target_definition = _validate_property_definition(target_definition, node_name)
    filter_definition = _validate_property_definition(filter_definition, node_name)
    if _is_composite_property_definition(target_definition) or _is_composite_property_definition(filter_definition):
        return False
    if str(target_definition.get("definition_kind", "") or "") != str(filter_definition.get("definition_kind", "") or ""):
        return False
    if str(target_definition.get("scope_kind", "") or "") != str(filter_definition.get("scope_kind", "") or ""):
        return False
    filter_properties = {
        str(key)
        for key, enabled in dict(filter_definition.get("properties", {}) or {}).items()
        if bool(enabled)
    }
    target_properties = {
        str(key)
        for key, enabled in dict(target_definition.get("properties", {}) or {}).items()
        if bool(enabled)
    }
    return filter_properties.issubset(target_properties)


def _property_definition_matching_fields(target_definition, filter_definition, node_name):
    target_definition = _validate_property_definition(target_definition, node_name)
    filter_definition = _validate_property_definition(filter_definition, node_name)
    if _is_composite_property_definition(target_definition):
        return set()
    target_kind = str(target_definition.get("definition_kind", "") or "")
    target_scope = str(target_definition.get("scope_kind", "") or "")
    target_fields = {
        str(key)
        for key, enabled in dict(target_definition.get("properties", {}) or {}).items()
        if bool(enabled)
    }
    matched_fields = set()
    for filter_entry in _iter_property_definition_entries(filter_definition, node_name):
        if str(filter_entry.get("definition_kind", "") or "") != target_kind:
            continue
        if str(filter_entry.get("scope_kind", "") or "") != target_scope:
            continue
        filter_fields = {
            str(key)
            for key, enabled in dict(filter_entry.get("properties", {}) or {}).items()
            if bool(enabled)
        }
        matched_fields.update(target_fields.intersection(filter_fields))
    return matched_fields
