import bpy


def _resolve_bake_entry(modifier, bake_node_name):
    bakes = getattr(modifier, "bakes", None)
    if bakes is None:
        return None
    for bake_entry in bakes:
        node_ref = getattr(bake_entry, "node", None)
        if node_ref and node_ref.name == bake_node_name:
            return bake_entry
    return None


def _split_bake_task_path(task_path, node_name, *, flow_execution_error_cls):
    raw = str(task_path or "").strip()
    if not raw:
        raise flow_execution_error_cls("AF_E021", "Bake task path is empty", node_name)
    parts = [p.strip() for p in raw.split("/", 2)]
    if len(parts) != 3 or not all(parts):
        raise flow_execution_error_cls("AF_E021", "Bake task path must be 'ObjectName/ModifierName/BakeNodeName'", node_name)
    return parts[0], parts[1], parts[2]


def _resolve_bake_target(task_path, node_name, *, flow_execution_error_cls, split_bake_task_path, resolve_bake_entry):
    object_name, modifier_name, bake_node_name = split_bake_task_path(task_path, node_name)
    object_ref = bpy.data.objects.get(object_name)
    if object_ref is None:
        raise flow_execution_error_cls("AF_E002", f"Target object '{object_name}' is missing", node_name)

    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        raise flow_execution_error_cls("AF_E003", f"Modifier '{modifier_name}' not found on '{object_name}'", node_name)
    if modifier.type != "NODES":
        raise flow_execution_error_cls("AF_E003", f"Modifier '{modifier_name}' on '{object_name}' is not a Geometry Nodes modifier", node_name)

    node_group = getattr(modifier, "node_group", None)
    if node_group is None:
        raise flow_execution_error_cls("AF_E004", "Geometry Nodes node group is missing", node_name)

    bake_node = node_group.nodes.get(bake_node_name)
    if bake_node is None:
        raise flow_execution_error_cls("AF_E004", f"Bake node '{bake_node_name}' not found in node group '{node_group.name}'", node_name)

    bake_entry = resolve_bake_entry(modifier, bake_node.name)
    if bake_entry is None:
        raise flow_execution_error_cls("AF_E004", f"Bake entry for node '{bake_node.name}' not found on modifier '{modifier.name}'", node_name)
    return object_ref, modifier, bake_node, bake_entry


def _split_physics_task_path(task_path, node_name, *, flow_execution_error_cls):
    raw = str(task_path or "").strip()
    if not raw:
        raise flow_execution_error_cls("AF_E021", "Physics task path is empty", node_name)
    parts = [p.strip() for p in raw.split("/", 1)]
    if len(parts) != 2 or not all(parts):
        raise flow_execution_error_cls("AF_E021", "Physics task path must be 'ObjectName/ModifierName'", node_name)
    return parts[0], parts[1]


def _resolve_physics_task_target(
    task_path,
    node_name,
    *,
    flow_execution_error_cls,
    split_physics_task_path,
    physics_supported_modifier_types,
):
    object_name, modifier_name = split_physics_task_path(task_path, node_name)
    object_ref = bpy.data.objects.get(object_name)
    if object_ref is None:
        raise flow_execution_error_cls("AF_E002", f"Target object '{object_name}' is missing", node_name)

    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        raise flow_execution_error_cls("AF_E003", f"Modifier '{modifier_name}' not found on '{object_name}'", node_name)

    if modifier.type not in physics_supported_modifier_types:
        supported = ", ".join(physics_supported_modifier_types.values())
        raise flow_execution_error_cls(
            "AF_E003",
            f"Modifier '{modifier_name}' on '{object_name}' is not a supported physics modifier ({supported})",
            node_name,
        )
    if modifier.type == "DYNAMIC_PAINT" and getattr(modifier, "canvas_settings", None) is None:
        raise flow_execution_error_cls("AF_E004", f"Dynamic Paint modifier '{modifier_name}' on '{object_name}' is not set as Canvas", node_name)
    return object_ref, modifier


def _resolve_physics_batch_task_target(
    task_path,
    node_name,
    *,
    flow_execution_error_cls,
    resolve_physics_task_target,
    physics_batch_supported_modifier_types,
):
    object_ref, modifier = resolve_physics_task_target(
        task_path,
        node_name,
    )
    if modifier.type not in physics_batch_supported_modifier_types:
        supported = ", ".join(physics_batch_supported_modifier_types.values())
        raise flow_execution_error_cls(
            "AF_E003",
            f"Modifier '{modifier.name}' on '{object_ref.name}' is not supported in Physics Bake Task ({supported})",
            node_name,
        )
    return object_ref, modifier


def _ensure_operator_finished(result, error_code, operator_label, node_name, *, flow_execution_error_cls):
    tokens = set(result) if isinstance(result, (set, tuple, list)) else {str(result)}
    if "FINISHED" in tokens:
        return result
    if "CANCELLED" in tokens:
        raise flow_execution_error_cls(error_code, f"{operator_label} was cancelled", node_name)
    joined = ", ".join(sorted(tokens))
    raise flow_execution_error_cls(error_code, f"{operator_label} returned unexpected result: {joined}", node_name)


def _compose_bake_override(base_override, ui_context=None):
    override = {}
    if ui_context:
        for key in ("window", "screen", "area", "region", "space_data"):
            value = ui_context.get(key)
            if value is not None:
                override[key] = value
    override.update({key: value for key, value in base_override.items() if value is not None})
    return override


def _call_operator_with_override(operator, override, payload=None, invoke_async=False, *, operator_result_tokens):
    payload = dict(payload or {})
    with bpy.context.temp_override(**override):
        if not operator.poll():
            return None, {"POLL_FAILED"}
        if invoke_async:
            result = operator("INVOKE_DEFAULT", **payload)
        else:
            result = operator(**payload)
    return result, operator_result_tokens(result)


def _start_named_operator(
    operator_paths,
    override,
    payload,
    source_node,
    invoke_async=False,
    *,
    flow_execution_error_cls,
    call_operator_with_override,
):
    last_error = None
    for op_path in operator_paths:
        namespace, name = op_path.split(".")
        group = getattr(bpy.ops, namespace, None)
        if group is None or not hasattr(group, name):
            continue
        operator = getattr(group, name)
        try:
            result, tokens = call_operator_with_override(operator, override, payload, invoke_async=invoke_async)
        except Exception as exc:
            last_error = exc
            continue
        if "POLL_FAILED" in tokens:
            last_error = flow_execution_error_cls("AF_E005", f"Operator poll failed: {op_path}", source_node)
            continue
        if "CANCELLED" in tokens:
            last_error = flow_execution_error_cls("AF_E005", f"Operator cancelled: {op_path}", source_node)
            continue
        return op_path, result, tokens
    if last_error is None:
        raise flow_execution_error_cls("AF_E005", "No supported bake operator found", source_node)
    if isinstance(last_error, flow_execution_error_cls):
        raise last_error
    raise flow_execution_error_cls("AF_E005", f"Bake operator failed: {last_error}", source_node)


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
