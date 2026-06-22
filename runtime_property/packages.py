import copy


def _property_scope_label(scope_kind, property_package_scope_object, property_package_scope_modifier):
    labels = {
        property_package_scope_object: "Object",
        property_package_scope_modifier: "Modifier",
        "PHYSICS_BAKE": "Physics Bake",
        "GN_BAKE": "GN Bake",
        "MIXED": "Mixed",
    }
    return labels.get(str(scope_kind or ""), str(scope_kind or "Package").title())


def _property_role_label(package_role, property_package_role_snapshot, property_package_role_target, property_package_role_settings, property_package_role_composite):
    labels = {
        property_package_role_snapshot: "Snapshot",
        property_package_role_target: "Target",
        property_package_role_settings: "Settings",
        property_package_role_composite: "Composite",
    }
    return labels.get(str(package_role or ""), str(package_role or "Package").title())


def _summarize_property_package(
    property_package,
    *,
    property_definition_kind_composite,
    property_package_role_composite,
    property_package_role_settings,
    property_package_item_count,
    property_package_has_property_content,
    property_scope_label,
    property_role_label,
):
    if not isinstance(property_package, dict):
        return {
            "package_role": "",
            "scope_kind": "",
            "definition_kind": "",
            "item_count": 0,
            "object_count": 0,
            "entry_count": 0,
            "has_properties": False,
            "title": "Empty",
            "detail": "Empty",
        }

    package_role = str(property_package.get("package_role", "") or "")
    scope_kind = str(property_package.get("scope_kind", "") or "")
    metadata = dict(property_package.get("metadata", {}) or {})
    definition_kind = str(metadata.get("definition_kind", "") or "")
    item_count = int(metadata.get("count", property_package_item_count(property_package)) or 0)
    object_count = int(metadata.get("object_count", 0) or 0)
    entry_count = int(metadata.get("entry_count", 0) or 0)
    has_properties = property_package_has_property_content(property_package, str(property_package.get("source_node", "") or ""))

    if item_count <= 0 and object_count <= 0 and entry_count <= 0:
        title = "Empty"
    elif not has_properties:
        title = "Objects Only"
    elif package_role == property_package_role_composite:
        title = "Composite"
    elif package_role == property_package_role_settings:
        title = f"{property_scope_label(scope_kind)} Settings"
    else:
        title = f"{property_scope_label(scope_kind)} {property_role_label(package_role)}".strip()

    detail_parts = [title]
    if entry_count > 0:
        detail_parts.append(f"{entry_count} entries")
    if item_count > 0:
        detail_parts.append(f"{item_count} items")
    if object_count > 0:
        detail_parts.append(f"{object_count} objs")
    if not has_properties and object_count > 0:
        detail_parts.append("No Properties")
    if definition_kind and definition_kind != property_definition_kind_composite and title == "Composite":
        detail_parts.append(definition_kind.title())

    return {
        "package_role": package_role,
        "scope_kind": scope_kind,
        "definition_kind": definition_kind,
        "item_count": item_count,
        "object_count": object_count,
        "entry_count": entry_count,
        "has_properties": bool(has_properties),
        "title": title,
        "detail": " | ".join(detail_parts) if detail_parts else "Empty",
    }


def _make_property_package_item(
    object_ref,
    target_kind,
    component_path,
    component_name,
    component_type,
    properties,
    metadata=None,
    ensure_object_persistent_uuid=None,
):
    return {
        "target_kind": str(target_kind),
        "object_id": int(object_ref.session_uid),
        "object_name": str(object_ref.name),
        "object_uuid": ensure_object_persistent_uuid(object_ref),
        "component_path": str(component_path),
        "component_name": str(component_name),
        "component_type": str(component_type),
        "properties": copy.deepcopy(properties or {}),
        "metadata": copy.deepcopy(metadata or {}),
    }


def _make_property_package(package_role, scope_kind, source_node, items, metadata=None):
    safe_items = copy.deepcopy(items or [])
    safe_metadata = copy.deepcopy(metadata or {})
    safe_metadata.setdefault("count", len(safe_items))
    safe_metadata.setdefault("object_count", len({int(item["object_id"]) for item in safe_items}))
    return {
        "package_role": str(package_role),
        "scope_kind": str(scope_kind),
        "source_node": str(source_node or ""),
        "items": safe_items,
        "metadata": safe_metadata,
    }


def _clone_property_package(package):
    return copy.deepcopy(package)


def _make_composite_property_package(
    source_node,
    entries,
    metadata=None,
    *,
    clone_property_package,
    property_package_item_count,
    property_package_role_composite,
    property_scope_kind_mixed,
):
    safe_entries = [clone_property_package(entry) for entry in (entries or [])]
    safe_metadata = copy.deepcopy(metadata or {})
    safe_metadata.setdefault("entry_count", len(safe_entries))
    safe_metadata.setdefault("count", sum(property_package_item_count(entry) for entry in safe_entries))
    safe_metadata.setdefault(
        "object_count",
        len(
            {
                int(item["object_id"])
                for entry in safe_entries
                for item in entry.get("items", [])
                if isinstance(item, dict) and "object_id" in item
            }
        ),
    )
    return {
        "package_role": property_package_role_composite,
        "scope_kind": property_scope_kind_mixed,
        "source_node": str(source_node or ""),
        "entries": safe_entries,
        "metadata": safe_metadata,
    }


def _is_composite_property_package(package, property_package_role_composite):
    return isinstance(package, dict) and str(package.get("package_role", "") or "") == property_package_role_composite


def _property_package_item_count(package, is_composite_property_package):
    if is_composite_property_package(package):
        return sum(_property_package_item_count(entry, is_composite_property_package) for entry in package.get("entries", []))
    return len(package.get("items", []))


def _validate_property_package(
    package,
    node_name,
    allow_roles=None,
    allow_scopes=None,
    *,
    flow_execution_error_cls,
    property_package_role_composite,
):
    if not isinstance(package, dict):
        raise flow_execution_error_cls("AF_E011", "Property Package payload is invalid", node_name)
    package_role = str(package.get("package_role", "") or "")
    if not package_role:
        raise flow_execution_error_cls("AF_E011", "Property Package role is missing", node_name)
    scope_kind = str(package.get("scope_kind", "") or "")
    if not scope_kind:
        raise flow_execution_error_cls("AF_E011", "Property Package scope is missing", node_name)
    if package_role == property_package_role_composite:
        entries = package.get("entries")
        if not isinstance(entries, list):
            raise flow_execution_error_cls("AF_E011", "Composite Property Package is missing entries", node_name)
        if allow_roles is not None and property_package_role_composite not in set(allow_roles):
            allowed_roles = set(allow_roles)
            for entry in entries:
                _validate_property_package(
                    entry,
                    node_name,
                    allow_roles=allowed_roles,
                    allow_scopes=allow_scopes,
                    flow_execution_error_cls=flow_execution_error_cls,
                    property_package_role_composite=property_package_role_composite,
                )
        return package

    if "items" not in package or not isinstance(package["items"], list):
        raise flow_execution_error_cls("AF_E011", "Property Package is missing items", node_name)
    if allow_roles is not None and package_role not in set(allow_roles):
        raise flow_execution_error_cls("AF_E011", f"Property Package role '{package_role}' is not supported", node_name)
    if allow_scopes is not None and scope_kind not in set(allow_scopes):
        raise flow_execution_error_cls("AF_E011", f"Property Package scope '{scope_kind}' is not supported", node_name)
    return package


def _iter_property_package_entries(
    package,
    node_name,
    allow_roles=None,
    allow_scopes=None,
    *,
    validate_property_package,
    is_composite_property_package,
    clone_property_package,
    flow_execution_error_cls,
):
    package = validate_property_package(package, node_name)
    if is_composite_property_package(package):
        entries = package.get("entries")
        if not isinstance(entries, list):
            raise flow_execution_error_cls("AF_E011", "Composite Property Package is missing entries", node_name)
        flattened = []
        for entry in entries:
            flattened.extend(
                _iter_property_package_entries(
                    entry,
                    node_name,
                    allow_roles=allow_roles,
                    allow_scopes=allow_scopes,
                    validate_property_package=validate_property_package,
                    is_composite_property_package=is_composite_property_package,
                    clone_property_package=clone_property_package,
                    flow_execution_error_cls=flow_execution_error_cls,
                )
            )
        return flattened

    package_role = str(package.get("package_role", "") or "")
    scope_kind = str(package.get("scope_kind", "") or "")
    if allow_roles is not None and package_role not in set(allow_roles):
        raise flow_execution_error_cls("AF_E011", f"Property Package role '{package_role}' is not supported", node_name)
    if allow_scopes is not None and scope_kind not in set(allow_scopes):
        raise flow_execution_error_cls("AF_E011", f"Property Package scope '{scope_kind}' is not supported", node_name)
    return [clone_property_package(package)]


def _property_package_to_definition(
    package,
    node_name,
    *,
    validate_property_package,
    is_composite_property_package,
    iter_property_definition_entries,
    normalize_property_definition_entries,
    make_empty_property_definition,
    clone_property_definition,
    sanitize_reusable_property_definition,
    validate_property_definition,
):
    package = validate_property_package(package, node_name)
    if is_composite_property_package(package):
        definitions = []
        for entry in package.get("entries", []):
            entry_definition = _property_package_to_definition(
                entry,
                node_name,
                validate_property_package=validate_property_package,
                is_composite_property_package=is_composite_property_package,
                iter_property_definition_entries=iter_property_definition_entries,
                normalize_property_definition_entries=normalize_property_definition_entries,
                make_empty_property_definition=make_empty_property_definition,
                clone_property_definition=clone_property_definition,
                sanitize_reusable_property_definition=sanitize_reusable_property_definition,
                validate_property_definition=validate_property_definition,
            )
            definitions.extend(iter_property_definition_entries(entry_definition, node_name))
        return normalize_property_definition_entries(node_name, definitions)
    property_definition = package.get("metadata", {}).get("property_definition")
    if property_definition is None:
        return make_empty_property_definition(node_name)
    return sanitize_reusable_property_definition(
        clone_property_definition(validate_property_definition(property_definition, node_name)),
        node_name,
    )


def _property_package_has_property_content(
    package,
    node_name,
    *,
    validate_property_package,
    is_composite_property_package,
    property_definition_has_content,
):
    package = validate_property_package(package, node_name)
    if is_composite_property_package(package):
        return any(
            _property_package_has_property_content(
                entry,
                node_name,
                validate_property_package=validate_property_package,
                is_composite_property_package=is_composite_property_package,
                property_definition_has_content=property_definition_has_content,
            )
            for entry in package.get("entries", [])
        )
    property_definition = package.get("metadata", {}).get("property_definition")
    if property_definition is not None:
        return property_definition_has_content(property_definition, node_name)
    for item in package.get("items", []):
        if dict(item.get("properties", {}) or {}):
            return True
    return False


def _property_package_keep_objects_only(
    package,
    *,
    object_resolver=None,
    validate_property_package,
    iter_property_package_entries,
    property_package_object_identity,
    component_path_for_object,
    make_property_package,
    make_empty_property_definition,
    property_package_scope_object,
    property_package_role_target,
    property_package_role_composite,
):
    package = validate_property_package(package, str(package.get("source_node", "") or "Filter"))
    object_items = []
    seen_keys = set()
    for entry in iter_property_package_entries(package, str(package.get("source_node", "") or "Filter")):
        for item in list(entry.get("items", [])):
            object_id = int(item.get("object_id", 0) or 0)
            dedup_key, obj, resolved_object_id, resolved_object_name, resolved_object_uuid = property_package_object_identity(
                item,
                object_resolver=object_resolver,
            )
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            component_name = resolved_object_name or "Object"
            component_type = str(getattr(obj, "type", "") or "OBJECT")
            component_path = component_path_for_object(obj) if obj is not None else f"{component_name}/OBJECT"
            object_items.append(
                {
                    "target_kind": property_package_scope_object,
                    "object_id": int(resolved_object_id or object_id),
                    "object_name": component_name,
                    "object_uuid": str(resolved_object_uuid or ""),
                    "component_path": component_path,
                    "component_name": component_name,
                    "component_type": component_type,
                    "properties": {},
                    "metadata": {},
                }
            )
    package_role = str(package.get("package_role", "") or property_package_role_target)
    if package_role == property_package_role_composite:
        package_role = property_package_role_target
    return make_property_package(
        package_role=package_role,
        scope_kind=property_package_scope_object,
        source_node=str(package.get("source_node", "") or ""),
        items=object_items,
        metadata={
            "count": len(object_items),
            "object_count": len(object_items),
            "entry_count": 0,
            "property_definition": make_empty_property_definition(str(package.get("source_node", "") or "")),
        },
    )


def _prune_redundant_object_only_package_entries(
    package,
    *,
    object_resolver=None,
    node_name="",
    is_composite_property_package=None,
    iter_property_package_entries=None,
    clone_property_package=None,
    property_package_has_property_content=None,
    property_package_object_identity=None,
    make_empty_property_definition=None,
    make_composite_property_package=None,
    property_package_to_definition=None,
):
    if not is_composite_property_package(package):
        return package
    owner_name = node_name or str(package.get("source_node", "") or "Filter")

    flattened_entries = [
        clone_property_package(entry)
        for entry in iter_property_package_entries(package, owner_name)
    ]
    if not flattened_entries:
        return package

    covered_object_keys = set()
    for entry in flattened_entries:
        if not property_package_has_property_content(entry, owner_name):
            continue
        for item in list(entry.get("items", [])):
            item_key, _obj, _resolved_object_id, _resolved_object_name, _resolved_object_uuid = property_package_object_identity(
                item,
                object_resolver=object_resolver,
            )
            covered_object_keys.add(item_key)

    if not covered_object_keys:
        return package

    retained_entries = []
    for entry in flattened_entries:
        if property_package_has_property_content(entry, owner_name):
            retained_entries.append(entry)
            continue
        retained_items = []
        for item in list(entry.get("items", [])):
            item_key, _obj, _resolved_object_id, _resolved_object_name, _resolved_object_uuid = property_package_object_identity(
                item,
                object_resolver=object_resolver,
            )
            if item_key in covered_object_keys:
                continue
            retained_items.append(copy.deepcopy(item))
        if not retained_items:
            continue
        retained_entry = clone_property_package(entry)
        retained_entry["items"] = retained_items
        retained_entry["metadata"] = copy.deepcopy(dict(retained_entry.get("metadata", {}) or {}))
        retained_entry["metadata"]["count"] = len(retained_items)
        retained_entry["metadata"]["object_count"] = len({int(item.get("object_id", 0) or 0) for item in retained_items})
        retained_entry["metadata"]["property_definition"] = make_empty_property_definition(owner_name)
        retained_entries.append(retained_entry)

    if not retained_entries:
        return make_composite_property_package(
            str(package.get("source_node", "") or ""),
            [],
            metadata={"property_definition": make_empty_property_definition(owner_name)},
        )
    if len(retained_entries) == len(flattened_entries):
        return package
    result = make_composite_property_package(
        str(package.get("source_node", "") or ""),
        retained_entries,
        metadata={},
    )
    result["metadata"] = copy.deepcopy(dict(result.get("metadata", {}) or {}))
    result["metadata"]["property_definition"] = property_package_to_definition(result, owner_name)
    return result


def _normalize_filtered_leaf_property_package(
    package,
    node_name,
    *,
    validate_property_package,
    is_composite_property_package,
    clone_property_package,
    clone_property_definition,
    validate_property_definition,
    property_package_to_definition,
    make_empty_property_definition,
    make_composite_property_package,
):
    package = validate_property_package(package, node_name)
    if is_composite_property_package(package):
        return package
    items = list(package.get("items", []))
    if not items:
        return package

    base_definition = package.get("metadata", {}).get("property_definition")
    if base_definition is None:
        return package
    base_definition = clone_property_definition(validate_property_definition(base_definition, node_name))

    grouped = {}
    ordered = []
    for item in items:
        property_keys = tuple(sorted(str(key) for key in dict(item.get("properties", {}) or {}).keys()))
        if property_keys not in grouped:
            grouped[property_keys] = []
            ordered.append(property_keys)
        grouped[property_keys].append(copy.deepcopy(item))

    if len(grouped) <= 1:
        normalized = clone_property_package(package)
        normalized["items"] = [copy.deepcopy(item) for item in items]
        normalized["metadata"] = copy.deepcopy(dict(normalized.get("metadata", {}) or {}))
        normalized["metadata"]["count"] = len(items)
        normalized["metadata"]["object_count"] = len({int(item.get("object_id", 0) or 0) for item in items})
        normalized["metadata"]["property_definition"] = property_package_to_definition(normalized, node_name)
        return normalized

    normalized_entries = []
    for property_keys in ordered:
        entry_items = grouped[property_keys]
        entry = clone_property_package(package)
        entry["items"] = entry_items
        entry["metadata"] = copy.deepcopy(dict(entry.get("metadata", {}) or {}))
        entry["metadata"]["count"] = len(entry_items)
        entry["metadata"]["object_count"] = len({int(item.get("object_id", 0) or 0) for item in entry_items})
        entry_definition = clone_property_definition(base_definition)
        entry_definition["properties"] = {
            key: bool(key in property_keys)
            for key, enabled in dict(base_definition.get("properties", {}) or {}).items()
            if bool(enabled) and key in property_keys
        }
        entry_definition["metadata"] = copy.deepcopy(dict(entry_definition.get("metadata", {}) or {}))
        entry_definition["metadata"]["count"] = len(entry_definition["properties"])
        entry["metadata"]["property_definition"] = (
            entry_definition if entry_definition["properties"] else make_empty_property_definition(node_name)
        )
        normalized_entries.append(entry)

    result = make_composite_property_package(
        str(package.get("source_node", "") or ""),
        normalized_entries,
        metadata={},
    )
    result["metadata"] = copy.deepcopy(dict(result.get("metadata", {}) or {}))
    result["metadata"]["property_definition"] = property_package_to_definition(result, node_name)
    return result


def _merge_single_property_packages(
    base_package,
    add_package,
    conflict_policy,
    node_name,
    *,
    flow_execution_error_cls,
    clone_property_package,
    clone_property_definition,
    merge_property_definitions,
):
    if str(base_package.get("package_role", "")) != str(add_package.get("package_role", "")):
        raise flow_execution_error_cls("AF_E020", "Cannot merge Property Packages with different package roles", node_name)
    if str(base_package.get("scope_kind", "")) != str(add_package.get("scope_kind", "")):
        raise flow_execution_error_cls("AF_E020", "Cannot merge Property Packages with different scope kinds", node_name)

    result = clone_property_package(base_package)
    item_map = {}
    order = []
    for item in result.get("items", []):
        key = str(item["component_path"])
        item_map[key] = item
        order.append(key)

    for add_item in add_package.get("items", []):
        key = str(add_item["component_path"])
        add_props = copy.deepcopy(add_item.get("properties", {}))
        existing = item_map.get(key)
        if existing is None:
            item_map[key] = copy.deepcopy(add_item)
            order.append(key)
            continue

        existing_props = existing.setdefault("properties", {})
        for prop_key, prop_value in add_props.items():
            if prop_key in existing_props and existing_props[prop_key] != prop_value:
                if conflict_policy == "ERROR":
                    raise flow_execution_error_cls("AF_E020", f"Property conflict at '{key}/{prop_key}'", node_name)
                if conflict_policy == "FIRST_WINS":
                    continue
            existing_props[prop_key] = prop_value
        existing_metadata = existing.setdefault("metadata", {})
        add_metadata = add_item.get("metadata", {})
        if conflict_policy != "FIRST_WINS":
            existing_metadata.update(copy.deepcopy(add_metadata))

    result["items"] = [item_map[key] for key in order]
    result["metadata"] = copy.deepcopy(result.get("metadata", {}))
    base_definition = result["metadata"].get("property_definition")
    add_definition = add_package.get("metadata", {}).get("property_definition")
    if base_definition is not None and add_definition is not None:
        result["metadata"]["property_definition"] = merge_property_definitions(base_definition, add_definition, node_name)
    elif add_definition is not None:
        result["metadata"]["property_definition"] = clone_property_definition(add_definition)
    result["metadata"]["count"] = len(result["items"])
    result["metadata"]["object_count"] = len({int(item["object_id"]) for item in result["items"]})
    return result


def _merge_property_packages(
    base_package,
    add_package,
    conflict_policy,
    node_name,
    *,
    validate_property_package,
    iter_property_package_entries,
    property_package_signature,
    clone_property_package,
    make_composite_property_package,
    normalize_property_definition_entries,
    property_package_to_definition,
    merge_single_property_packages,
):
    validate_property_package(base_package, node_name)
    validate_property_package(add_package, node_name)
    grouped = {}
    ordered = []
    for entry in iter_property_package_entries(base_package, node_name):
        signature = property_package_signature(entry)
        grouped[signature] = clone_property_package(entry)
        ordered.append(signature)
    for entry in iter_property_package_entries(add_package, node_name):
        signature = property_package_signature(entry)
        if signature not in grouped:
            grouped[signature] = clone_property_package(entry)
            ordered.append(signature)
            continue
        grouped[signature] = merge_single_property_packages(grouped[signature], entry, conflict_policy, node_name)
    merged_entries = [grouped[signature] for signature in ordered]
    if len(merged_entries) == 1:
        return merged_entries[0]
    return make_composite_property_package(
        node_name,
        merged_entries,
        metadata={
            "property_definition": normalize_property_definition_entries(
                node_name,
                [property_package_to_definition(entry, node_name) for entry in merged_entries],
            )
        },
    )


def _build_modifier_snapshot_property_package(
    source_node,
    snapshot_id,
    snapshot_items,
    *,
    bpy_module,
    find_object_by_item,
    make_property_package_item,
    make_property_package,
    component_path_for_modifier,
    property_package_scope_modifier,
    property_package_role_snapshot,
):
    package_items = []
    for item in snapshot_items:
        object_ref = bpy_module.data.objects.get(item["object_name"])
        if object_ref is None:
            object_ref = find_object_by_item({"id": item["object_id"], "name": item["object_name"]})
        if object_ref is None:
            continue
        modifier_name = str(item["modifier_name"])
        modifier = object_ref.modifiers.get(modifier_name)
        component_type = modifier.type if modifier is not None else "UNKNOWN"
        package_items.append(
            make_property_package_item(
                object_ref=object_ref,
                target_kind=property_package_scope_modifier,
                component_path=component_path_for_modifier(object_ref, modifier_name),
                component_name=modifier_name,
                component_type=component_type,
                properties=item.get("props", {}),
                metadata={"snapshot_id": str(snapshot_id)},
            )
        )
    package_metadata = {"snapshot_id": str(snapshot_id)}
    return make_property_package(
        package_role=property_package_role_snapshot,
        scope_kind=property_package_scope_modifier,
        source_node=source_node,
        items=package_items,
        metadata=package_metadata,
    )


def _build_modifier_target_property_package(
    source_node,
    property_definition,
    items,
    *,
    validate_property_definition,
    make_property_package,
    clone_property_definition,
    property_definition_kind_modifier,
    property_package_role_target,
    property_package_scope_modifier,
):
    property_definition = validate_property_definition(
        property_definition,
        source_node,
        allow_kinds={property_definition_kind_modifier},
    )
    return make_property_package(
        package_role=property_package_role_target,
        scope_kind=property_package_scope_modifier,
        source_node=source_node,
        items=items,
        metadata={
            "definition_kind": property_definition_kind_modifier,
            "property_definition": clone_property_definition(property_definition),
        },
    )


def _build_object_display_snapshot_property_package(
    source_node,
    snapshot_id,
    snapshot_items,
    *,
    bpy_module,
    find_object_by_item,
    make_property_package_item,
    make_property_package,
    component_path_for_object,
    property_package_scope_object,
    property_package_role_snapshot,
):
    package_items = []
    for item in snapshot_items:
        object_ref = bpy_module.data.objects.get(item["object_name"])
        if object_ref is None:
            object_ref = find_object_by_item({"id": item["object_id"], "name": item["object_name"]})
        if object_ref is None:
            continue
        package_items.append(
            make_property_package_item(
                object_ref=object_ref,
                target_kind=property_package_scope_object,
                component_path=component_path_for_object(object_ref),
                component_name=object_ref.name,
                component_type=str(getattr(object_ref, "type", "") or "OBJECT"),
                properties=item.get("props", {}),
                metadata={"snapshot_id": str(snapshot_id)},
            )
        )
    package_metadata = {"snapshot_id": str(snapshot_id)}
    return make_property_package(
        package_role=property_package_role_snapshot,
        scope_kind=property_package_scope_object,
        source_node=source_node,
        items=package_items,
        metadata=package_metadata,
    )


def _build_object_display_target_property_package(
    source_node,
    property_definition,
    items,
    *,
    validate_property_definition,
    make_property_package,
    clone_property_definition,
    property_definition_kind_object_display,
    property_package_role_target,
    property_package_scope_object,
):
    property_definition = validate_property_definition(
        property_definition,
        source_node,
        allow_kinds={property_definition_kind_object_display},
    )
    return make_property_package(
        package_role=property_package_role_target,
        scope_kind=property_package_scope_object,
        source_node=source_node,
        items=items,
        metadata={
            "definition_kind": property_definition_kind_object_display,
            "property_definition": clone_property_definition(property_definition),
        },
    )


def _build_object_transform_snapshot_property_package(
    source_node,
    snapshot_id,
    snapshot_items,
    *,
    bpy_module,
    find_object_by_item,
    make_property_package_item,
    make_property_package,
    component_path_for_object,
    property_package_scope_object,
    property_package_role_snapshot,
):
    package_items = []
    for item in snapshot_items:
        object_ref = bpy_module.data.objects.get(item["object_name"])
        if object_ref is None:
            object_ref = find_object_by_item({"id": item["object_id"], "name": item["object_name"]})
        if object_ref is None:
            continue
        package_items.append(
            make_property_package_item(
                object_ref=object_ref,
                target_kind=property_package_scope_object,
                component_path=component_path_for_object(object_ref),
                component_name=object_ref.name,
                component_type=str(getattr(object_ref, "type", "") or "OBJECT"),
                properties=item.get("props", {}),
                metadata={"snapshot_id": str(snapshot_id)},
            )
        )
    return make_property_package(
        package_role=property_package_role_snapshot,
        scope_kind=property_package_scope_object,
        source_node=source_node,
        items=package_items,
        metadata={"snapshot_id": str(snapshot_id)},
    )


def _build_object_transform_target_property_package(
    source_node,
    property_definition,
    items,
    *,
    validate_property_definition,
    make_property_package,
    clone_property_definition,
    property_definition_kind_object_transform,
    property_package_role_target,
    property_package_scope_object,
):
    property_definition = validate_property_definition(
        property_definition,
        source_node,
        allow_kinds={property_definition_kind_object_transform},
    )
    return make_property_package(
        package_role=property_package_role_target,
        scope_kind=property_package_scope_object,
        source_node=source_node,
        items=items,
        metadata={
            "definition_kind": property_definition_kind_object_transform,
            "property_definition": clone_property_definition(property_definition),
        },
    )


def _build_physics_property_package(
    source_node,
    payload,
    *,
    require_payload_object_ref,
    make_property_package_item,
    make_property_package,
    component_path_for_modifier,
    property_package_scope_physics_bake,
    property_package_role_settings,
):
    object_ref = require_payload_object_ref(payload, source_node)
    modifier_name = str(payload["modifier_name"])
    properties = {
        "frame_start": int(payload["frame_start"]),
        "frame_end": int(payload["frame_end"]),
        "override_settings": bool(payload["override_settings"]),
        "free_before_bake": bool(payload["free_before_bake"]),
        "disk_cache": bool(payload.get("disk_cache", False)),
    }
    item = make_property_package_item(
        object_ref=object_ref,
        target_kind=property_package_scope_physics_bake,
        component_path=component_path_for_modifier(object_ref, modifier_name),
        component_name=modifier_name,
        component_type=str(payload["physics_type"]),
        properties=properties,
        metadata={"task_path": str(payload["task_path"])},
    )
    return make_property_package(
        package_role=property_package_role_settings,
        scope_kind=property_package_scope_physics_bake,
        source_node=source_node,
        items=[item],
        metadata={"task_path": str(payload["task_path"])},
    )


def _physics_property_package_to_settings_payloads(
    package,
    node_name,
    *,
    validate_property_package,
    find_object_by_item,
    component_path_for_modifier,
    ensure_object_persistent_uuid,
    flow_execution_error_cls,
    property_package_role_settings,
    property_package_scope_physics_bake,
):
    validate_property_package(
        package,
        node_name,
        allow_roles={property_package_role_settings},
        allow_scopes={property_package_scope_physics_bake},
    )
    payloads = []
    for item in package.get("items", []):
        object_ref = find_object_by_item(
            {
                "id": item["object_id"],
                "name": item["object_name"],
                "uuid": item.get("object_uuid", ""),
            }
        )
        if object_ref is None:
            raise flow_execution_error_cls("AF_E002", f"Target object '{item['object_name']}' is missing", node_name)
        modifier_name = str(item.get("component_name", "") or "")
        modifier = object_ref.modifiers.get(modifier_name)
        if modifier is None:
            raise flow_execution_error_cls("AF_E003", f"Modifier '{modifier_name}' not found on '{object_ref.name}'", node_name)
        payloads.append(
            {
                "source_node": package.get("source_node", node_name),
                "task_path": str(item.get("metadata", {}).get("task_path", component_path_for_modifier(object_ref, modifier_name))),
                "object_ref": object_ref,
                "object_name": object_ref.name,
                "session_uid": int(object_ref.session_uid),
                "object_uuid": ensure_object_persistent_uuid(object_ref),
                "modifier_name": modifier.name,
                "physics_type": str(item.get("component_type", modifier.type)),
                "frame_start": int(item.get("properties", {}).get("frame_start", 1)),
                "frame_end": int(item.get("properties", {}).get("frame_end", 250)),
                "override_settings": bool(item.get("properties", {}).get("override_settings", True)),
                "free_before_bake": bool(item.get("properties", {}).get("free_before_bake", False)),
                "disk_cache": bool(item.get("properties", {}).get("disk_cache", False)),
            }
        )
    return payloads
