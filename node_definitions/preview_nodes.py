import bpy

from ..i18n import af_iface
from ..node_system.socket_aliases import (
    PROPERTY_PACKAGE_SOCKET_NAME,
    find_node_input_socket,
)


def build_preview_node_classes(
    *,
    AFBaseNode,
    OBJECT_DISPLAY_TYPE_ITEMS,
    OBJECT_INTERACTION_MODE_ITEMS,
    OBJECT_ROTATION_MODE_ITEMS,
    PREVIEW_DATA_MODE_BY_SOCKET_IDNAME,
    PREVIEW_DATA_MODE_ITEMS,
    PREVIEW_DATA_MODE_SPECS,
    PREVIEW_DATA_VIRTUAL_LABEL,
    PREVIEW_PROPERTY_DEFINITION_VIEW_MODE_ITEMS,
    PREVIEW_PROPERTY_PACKAGE_VIEW_MODE_ITEMS,
    PREVIEW_TASK_PLAN_VIEW_MODE_ITEMS,
    VIEWPORT_SHADING_MODE_ITEMS,
    _enum_identifier_label,
    _find_single_from_input_socket,
    _hide_default_auxiliary_outputs,
    _is_composite_property_assignment,
    _is_composite_property_definition,
    _is_composite_property_package,
    _modifier_filter_settings_from_metadata,
    _normalized_preview_context,
    _property_definition_has_content,
    _property_role_label,
    _property_scope_label,
    _set_default_node_width,
    _summarize_property_package,
    _sync_node_sockets_in_place,
    _ui_runner_for_node,
):
    def _preview_mode_spec(mode):
        return PREVIEW_DATA_MODE_SPECS.get(str(mode or "OBJECT_LIST"), PREVIEW_DATA_MODE_SPECS["OBJECT_LIST"])

    def _preview_mode_from_socket_idname(socket_idname):
        return PREVIEW_DATA_MODE_BY_SOCKET_IDNAME.get(str(socket_idname or ""))

    def _preview_input_socket(node):
        return node.inputs[0] if len(node.inputs) == 1 else None

    def _preview_input_source(node):
        input_socket = _preview_input_socket(node)
        if input_socket is None:
            return None, None
        return _find_single_from_input_socket(input_socket)

    def _preview_source_mode(node):
        input_socket = _preview_input_socket(node)
        source_node, source_socket = _preview_input_source(node)
        if (
            input_socket is not None
            and bool(getattr(input_socket, "af_is_virtual", False))
            and source_socket is None
        ):
            return None
        if source_socket is not None:
            return _preview_mode_from_socket_idname(getattr(source_socket, "bl_idname", ""))
        return _preview_mode_from_socket_idname(getattr(input_socket, "bl_idname", "")) if input_socket is not None else None

    def _preview_mode_label(node):
        mode = _preview_source_mode(node)
        if not mode:
            return "Auto"
        _socket_id, socket_name, _output_key = _preview_mode_spec(mode)
        return socket_name

    def _preview_effective_mode(node):
        source_mode = _preview_source_mode(node)
        if source_mode:
            return source_mode
        return str(getattr(node, "preview_mode", "OBJECT_LIST") or "OBJECT_LIST")

    def _sync_preview_data_sockets(node):
        node_tree = getattr(node, "id_data", None)
        upstream_socket = None
        did_rebuild = False
        input_socket = _preview_input_socket(node)
        current_mode = str(getattr(node, "preview_mode", "OBJECT_LIST") or "OBJECT_LIST")
        current_is_virtual = bool(getattr(input_socket, "af_is_virtual", False)) if input_socket is not None else True
        if input_socket is not None:
            _upstream_node, upstream_socket = _find_single_from_input_socket(input_socket)

        resolved_mode = _preview_mode_from_socket_idname(getattr(upstream_socket, "bl_idname", "")) if upstream_socket is not None else None
        if resolved_mode and current_mode != resolved_mode:
            node.preview_mode = resolved_mode

        effective_mode = resolved_mode
        if effective_mode is None and input_socket is not None and not current_is_virtual:
            effective_mode = current_mode

        target_name = _preview_mode_spec(effective_mode)[1] if effective_mode else PREVIEW_DATA_VIRTUAL_LABEL
        needs_repair = (
            len(node.inputs) != 1
            or str(getattr(node.inputs[0], "bl_idname", "") or "") != "AFSocketPreviewData"
            or len(node.outputs) != 0
        )
        if needs_repair:
            _sync_node_sockets_in_place(node, (("AFSocketPreviewData", target_name),), ())
            did_rebuild = True
        elif str(getattr(node.inputs[0], "name", "") or "") != target_name:
            try:
                node.inputs[0].name = target_name
            except Exception:
                pass

        input_socket = _preview_input_socket(node)
        if input_socket is None:
            return
        input_socket.af_is_virtual = effective_mode is None
        if str(getattr(input_socket, "name", "") or "") != target_name:
            input_socket.name = target_name
        if did_rebuild and upstream_socket is not None and not bool(getattr(input_socket, "is_linked", False)) and node_tree is not None:
            try:
                node_tree.links.new(upstream_socket, input_socket)
            except Exception:
                pass

    def _preview_output_payload(runner, source_node, source_socket, output_key, group_path=None):
        resolved_group_path = list(group_path or [])
        try:
            payload = runner._get_output_from_source(source_node, source_socket, output_key, resolved_group_path)
            if payload is not None:
                return payload
        except Exception:
            pass

        previous_group_path = list(getattr(runner, "current_group_path", []))
        try:
            runner.current_group_path = list(resolved_group_path)
            payload = runner.preview_flow_output(source_node, output_key)
            if payload is not None:
                return payload
        except Exception:
            pass
        finally:
            runner.current_group_path = previous_group_path

        try:
            return runner._get_output_from_source(source_node, source_socket, output_key, resolved_group_path)
        except Exception:
            return None

    def _preview_store_payload_direct(runner, source_node, group_path=None):
        if source_node is None or getattr(source_node, "bl_idname", "") != "AFNodeStorePropertyPackage":
            return None, None

        preview_resolver = getattr(runner, "_preview_store_property_package_outputs", None)
        if preview_resolver is not None:
            try:
                return preview_resolver(source_node, group_path)
            except Exception:
                pass

        try:
            store_mode = str(getattr(source_node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT")
            if store_mode == "OUTPUT_ONLY":
                property_package = runner._read_stored_property_package(source_node)
            else:
                package_input = find_node_input_socket(source_node, PROPERTY_PACKAGE_SOCKET_NAME)
                upstream_node, upstream_socket = _find_single_from_input_socket(package_input)
                property_package = None
                if upstream_node is not None:
                    property_package = _preview_output_payload(
                        runner,
                        upstream_node,
                        upstream_socket,
                        "property_package",
                        group_path,
                    )
            if property_package is None:
                return None, None
            report = {
                "package_role": str(property_package.get("package_role", "")),
                "scope_kind": str(property_package.get("scope_kind", "")),
                "count": int(len(list(property_package.get("items", [])))) if "entries" not in property_package else int(dict(property_package.get("metadata", {}) or {}).get("count", 0)),
                "mode": str(getattr(source_node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT"),
                "dry_run": True,
            }
            return property_package, report
        except Exception:
            return None, None

    def _preview_fallback_runner(node, source_node, context):
        try:
            from ..runtime_runner.core import FlowRunner
        except Exception:
            return None

        scene = getattr(context, "scene", None) or getattr(bpy.context, "scene", None)
        root_tree = getattr(source_node, "id_data", None) if source_node is not None else None
        if root_tree is None:
            root_tree = getattr(node, "id_data", None)
        if scene is None or root_tree is None:
            return None
        try:
            runner = FlowRunner(root_tree, scene)
            runner.current_group_path = []
            return runner
        except Exception:
            return None

    def _preview_seed_property_context_from_object_list(runner, object_list):
        if runner is None or not isinstance(object_list, dict):
            return False
        object_items = [dict(item or {}) for item in list(object_list.get("items", [])) if isinstance(item, dict) and item]
        if not object_items:
            return False
        object_count = len(object_items)
        for index, obj_item in enumerate(object_items):
            try:
                obj = runner._find_object_by_item_cached(obj_item)
            except Exception:
                obj = None
            if obj is None:
                continue
            try:
                runner.current_property_context = runner._make_object_property_context(
                    obj_item,
                    obj,
                    index,
                    object_count,
                    object_items,
                    copy_payload=False,
                )
                return True
            except Exception:
                continue
        return False

    def _preview_object_list_from_downstream_context(runner, producer_node, group_path=None, visited=None, depth=0):
        if runner is None or producer_node is None or depth > 8:
            return None
        node_tree = getattr(producer_node, "id_data", None)
        if node_tree is None:
            return None

        if visited is None:
            visited = set()
        visit_key = (
            getattr(node_tree, "name", ""),
            str(getattr(producer_node, "name", "") or ""),
            tuple(
                (
                    str(item.get("tree_name", "") or ""),
                    str(item.get("node_name", "") or ""),
                )
                for item in list(group_path or [])
                if isinstance(item, dict)
            ),
        )
        if visit_key in visited:
            return None
        visited.add(visit_key)

        for link in getattr(node_tree, "links", []):
            try:
                if not bool(getattr(link, "is_valid", True)):
                    continue
                if getattr(link, "from_node", None) != producer_node:
                    continue
            except Exception:
                continue

            consumer_node = getattr(link, "to_node", None)
            if consumer_node is None:
                continue

            object_list_socket = find_node_input_socket(consumer_node, "Object List")
            if object_list_socket is not None:
                upstream_node, upstream_socket = _find_single_from_input_socket(object_list_socket)
                if upstream_node is not None and upstream_socket is not None:
                    try:
                        object_list = runner._get_output_from_source(
                            upstream_node,
                            upstream_socket,
                            "object_list",
                            list(group_path or []),
                        )
                    except Exception:
                        object_list = None
                    if isinstance(object_list, dict) and list(object_list.get("items", [])):
                        return object_list

            object_list = _preview_object_list_from_downstream_context(
                runner,
                consumer_node,
                group_path=group_path,
                visited=visited,
                depth=depth + 1,
            )
            if isinstance(object_list, dict) and list(object_list.get("items", [])):
                return object_list
        return None

    def _seed_preview_property_context(runner, source_node, source_socket, group_path=None):
        if runner is None or source_node is None:
            return False
        existing_context = getattr(runner, "current_property_context", None)
        if isinstance(existing_context, dict) and existing_context:
            return True

        previous_group_path = list(getattr(runner, "current_group_path", []))
        depends_on_context = False
        try:
            runner.current_group_path = list(group_path or [])
            source_depends_fn = getattr(runner, "_source_depends_on_property_context", None)
            node_depends_fn = getattr(runner, "_data_node_depends_on_property_context", None)
            if callable(source_depends_fn) and source_socket is not None:
                depends_on_context = bool(source_depends_fn(source_node, source_socket, set()))
            elif callable(node_depends_fn):
                depends_on_context = bool(node_depends_fn(source_node))
        except Exception:
            depends_on_context = False
        finally:
            runner.current_group_path = previous_group_path

        if not depends_on_context:
            return False

        candidate_specs = [(source_node, list(group_path or []))]
        resolve_step_ref = getattr(runner, "_resolve_step_ref", None)
        if callable(resolve_step_ref):
            group_path_items = list(group_path or [])
            for index in range(len(group_path_items) - 1, -1, -1):
                step_ref = group_path_items[index]
                try:
                    candidate_node = resolve_step_ref(step_ref, str(getattr(source_node, "name", "") or "Preview Data"))
                except Exception:
                    candidate_node = None
                if candidate_node is None:
                    continue
                candidate_specs.append((candidate_node, group_path_items[:index]))

        seen_candidates = set()
        for candidate_node, candidate_group_path in candidate_specs:
            candidate_tree = getattr(getattr(candidate_node, "id_data", None), "name", "")
            candidate_key = (
                candidate_tree,
                str(getattr(candidate_node, "name", "") or ""),
                tuple(
                    (
                        str(item.get("tree_name", "") or ""),
                        str(item.get("node_name", "") or ""),
                    )
                    for item in list(candidate_group_path or [])
                    if isinstance(item, dict)
                ),
            )
            if candidate_key in seen_candidates:
                continue
            seen_candidates.add(candidate_key)

            object_list = _preview_object_list_from_downstream_context(
                runner,
                candidate_node,
                group_path=candidate_group_path,
            )
            if _preview_seed_property_context_from_object_list(runner, object_list):
                return True
        return False

    def _preview_task_ref_payload_direct(runner, source_node):
        if runner is None or source_node is None:
            return None
        node_type = str(getattr(source_node, "bl_idname", "") or "")
        try:
            if node_type == "AFNodePropertyPackageBakeTarget":
                from ..runtime_task_ref import _build_property_package_bake_task_ref_fallback

                payload = _build_property_package_bake_task_ref_fallback(runner, source_node)
                if payload is not None:
                    return payload
                fallback_runner = _preview_fallback_runner(source_node, source_node, bpy.context)
                if fallback_runner is not None and fallback_runner is not runner:
                    return _build_property_package_bake_task_ref_fallback(fallback_runner, source_node)
                return None
            if node_type == "AFNodeBakeTask":
                return runner._build_geometry_task_ref(source_node)
            if node_type in {"AFNodeRenderTarget", "AFNodeRenderTask"}:
                return runner._build_render_task_ref(source_node)
            if node_type == "AFNodePhysicsBakeTask":
                return runner._build_physics_bake_all_task_ref(source_node)
        except Exception:
            return None
        return None

    def _preview_geometry_task_ref_payload_with_last_bake(payload, source_node):
        if source_node is None or getattr(source_node, "bl_idname", "") != "AFNodeBakeTask":
            return payload
        if not isinstance(payload, dict):
            return payload
        try:
            from ..runtime_bake import _read_geometry_bake_last_bake_state
        except Exception:
            return payload
        try:
            last_bake_state = _read_geometry_bake_last_bake_state(source_node)
        except Exception:
            last_bake_state = None
        if not isinstance(last_bake_state, dict):
            return payload
        preview_payload = dict(payload)
        preview_payload["last_bake_state"] = dict(last_bake_state)
        return preview_payload

    def _preview_input_payload(node, context):
        context = _normalized_preview_context(context)
        effective_mode = _preview_effective_mode(node)
        _socket_id, socket_name, output_key = _preview_mode_spec(effective_mode)
        source_node, source_socket = _preview_input_source(node)
        if source_node is None:
            try:
                _sync_preview_data_sockets(node)
                source_node, source_socket = _preview_input_source(node)
                effective_mode = _preview_effective_mode(node)
                _socket_id, socket_name, output_key = _preview_mode_spec(effective_mode)
            except Exception:
                pass
        if source_node is None:
            return None
        runner = _ui_runner_for_node(node, context)
        if runner is None and context is not bpy.context:
            context = bpy.context
            runner = _ui_runner_for_node(node, context)
        if runner is None:
            runner = _preview_fallback_runner(node, source_node, context)
        if runner is None:
            return None

        resolved_group_path = list(getattr(runner, "current_group_path", []))
        trace_output_source = getattr(runner, "_trace_output_source", None)
        if trace_output_source is not None:
            try:
                resolved_node, resolved_socket, resolved_group_path = trace_output_source(source_node, source_socket, resolved_group_path, output_key)
                source_node = resolved_node or source_node
                source_socket = resolved_socket or source_socket
            except Exception:
                resolved_group_path = list(getattr(runner, "current_group_path", []))

        try:
            _seed_preview_property_context(runner, source_node, source_socket, resolved_group_path)
        except Exception:
            pass

        if getattr(source_node, "bl_idname", "") == "AFNodeStorePropertyPackage":
            try:
                property_package, report = _preview_store_payload_direct(runner, source_node, resolved_group_path)
                if output_key == "property_package" and property_package is not None:
                    return property_package
                if output_key == "report" and report is not None:
                    return report
            except Exception:
                pass

        payload = _preview_output_payload(runner, source_node, source_socket, output_key, resolved_group_path)
        if payload is not None:
            if output_key == "task_ref":
                payload = _preview_geometry_task_ref_payload_with_last_bake(payload, source_node)
            return payload

        if output_key == "task_ref":
            payload = _preview_task_ref_payload_direct(runner, source_node)
            if payload is not None:
                payload = _preview_geometry_task_ref_payload_with_last_bake(payload, source_node)
                return payload
        return None

    def _preview_property_package_item_line(item, prefix=""):
        component_path = str(item.get("component_path", "") or item.get("object_name", "") or "Item")
        properties = dict(item.get("properties", {}) or {})
        prop_pairs = ", ".join(
            f"{key}={_format_preview_value(value)}" for key, value in list(properties.items())
        )
        line = f"{component_path} -> {prop_pairs}" if prop_pairs else component_path
        return f"{prefix}{line}" if prefix else line

    def _collect_preview_property_package_leaf_items(property_package, path_parts=None, out_items=None):
        if out_items is None:
            out_items = []
        if path_parts is None:
            path_parts = []

        is_composite = bool(_is_composite_property_package(property_package))
        if is_composite:
            for index, entry in enumerate(list(property_package.get("entries", [])), 1):
                _collect_preview_property_package_leaf_items(entry, [*path_parts, str(index)], out_items)
            return out_items

        entry_label = ".".join(path_parts)
        for item in list(property_package.get("items", [])):
            out_items.append((entry_label, item))
        return out_items

    def _preview_property_package_view_mode(node, property_package):
        view_mode = str(getattr(node, "preview_property_package_view_mode", "ENTRIES") or "ENTRIES")
        if view_mode not in {"SUMMARY", "ENTRIES", "ITEMS"}:
            view_mode = "ENTRIES"
        if view_mode == "ENTRIES":
            is_composite = bool(_is_composite_property_package(property_package))
            return "ENTRIES" if is_composite else "ITEMS"
        return view_mode

    def _localized_property_package_summary_detail(summary):
        if not isinstance(summary, dict):
            return "Empty"
        title = str(summary.get("title", "") or "")
        detail = str(summary.get("detail", "") or "")
        if detail:
            return detail
        if title:
            return title
        return "Empty"

    def _preview_property_package_lines(node, property_package, max_items):
        summary = _summarize_property_package(property_package)
        lines = [_localized_property_package_summary_detail(summary)]
        view_mode = _preview_property_package_view_mode(node, property_package)

        if view_mode == "SUMMARY":
            package_role = str(summary.get("package_role", "") or "")
            scope_kind = str(summary.get("scope_kind", "") or "")
            source_node = str(property_package.get("source_node", "") or "")
            extra_lines = []
            if package_role:
                extra_lines.append(f"Role: {_property_role_label(package_role)}")
            if scope_kind:
                extra_lines.append(f"Scope: {_property_scope_label(scope_kind)}")
            if source_node:
                extra_lines.append(f"Source: {source_node}")
            lines.extend(extra_lines[:max_items])
            return tuple(lines)

        if view_mode == "ENTRIES":
            entries = list(property_package.get("entries", []))
            for index, entry in enumerate(entries[:max_items], 1):
                entry_summary = _summarize_property_package(entry)
                lines.append(f"[{index}] {entry_summary['detail']}")
            if len(entries) > max_items:
                lines.append("...")
            return tuple(lines)

        flattened_items = _collect_preview_property_package_leaf_items(property_package)
        for entry_label, item in flattened_items[:max_items]:
            prefix = f"[{entry_label}] " if entry_label else ""
            lines.append(_preview_property_package_item_line(item, prefix=prefix))
        if len(flattened_items) > max_items:
            lines.append("...")
        return tuple(lines)

    def _preview_property_definition_view_mode(node, property_definition):
        view_mode = str(getattr(node, "preview_property_definition_view_mode", "ENTRIES") or "ENTRIES")
        if view_mode not in {"SUMMARY", "ENTRIES", "FIELDS"}:
            view_mode = "ENTRIES"
        if view_mode == "ENTRIES":
            is_composite = bool(_is_composite_property_definition(property_definition))
            return "ENTRIES" if is_composite else "FIELDS"
        return view_mode

    def _preview_property_definition_entry_summary(entry):
        definition_kind = str(entry.get("definition_kind", "") or "")
        scope_kind = str(entry.get("scope_kind", "") or "")
        enabled_fields = [str(key) for key, enabled in dict(entry.get("properties", {}) or {}).items() if bool(enabled)]
        kind_label = definition_kind.title() if definition_kind else af_iface("Prop Def")
        scope_label = _property_scope_label(scope_kind) if scope_kind else ""
        detail = f"{len(enabled_fields)} field(s)"
        metadata = dict(entry.get("metadata", {}) or {})
        modifier_settings = _modifier_filter_settings_from_metadata(metadata)
        modifier_filter = str(modifier_settings.get("modifier_type_filter", "") or "")
        if bool(modifier_settings.get("filter_by_type", False)) and modifier_filter and modifier_filter != "ALL":
            detail = f"{detail}, {modifier_filter}"
        modifier_name_filter = str(modifier_settings.get("modifier_name_filter", "") or "").strip()
        if bool(modifier_settings.get("filter_by_name", False)) and modifier_name_filter:
            match_mode = str(modifier_settings.get("modifier_name_match_mode", "EXACT") or "EXACT")
            detail = f"{detail}, {match_mode} '{modifier_name_filter}'"
        if bool(modifier_settings.get("filter_by_context", False)):
            detail = f"{detail}, Context"
        return f"{kind_label} / {scope_label} - {detail}" if scope_label else f"{kind_label} - {detail}"

    def _collect_preview_property_definition_fields(property_definition, path_parts=None, out_items=None):
        if out_items is None:
            out_items = []
        if path_parts is None:
            path_parts = []

        is_composite = bool(_is_composite_property_definition(property_definition))
        if is_composite:
            for index, entry in enumerate(list(property_definition.get("entries", [])), 1):
                _collect_preview_property_definition_fields(entry, [*path_parts, str(index)], out_items)
            return out_items

        entry_label = ".".join(path_parts)
        for key, enabled in dict(property_definition.get("properties", {}) or {}).items():
            if not bool(enabled):
                continue
            out_items.append((entry_label, str(key)))
        return out_items

    def _preview_property_definition_lines(node, property_definition, max_items):
        if not bool(_property_definition_has_content(property_definition, "Preview")):
            return ("No Properties",)

        definition_kind = str(property_definition.get("definition_kind", "") or "")
        scope_kind = str(property_definition.get("scope_kind", "") or "")
        metadata = dict(property_definition.get("metadata", {}) or {})
        lines = [definition_kind.title() if definition_kind else af_iface("Prop Def")]
        view_mode = _preview_property_definition_view_mode(node, property_definition)

        if view_mode == "SUMMARY":
            extra_lines = []
            if scope_kind:
                extra_lines.append(f"Scope: {_property_scope_label(scope_kind)}")
            source_node = str(property_definition.get("source_node", "") or "")
            if source_node:
                extra_lines.append(f"Source: {source_node}")
            modifier_settings = _modifier_filter_settings_from_metadata(metadata)
            modifier_filter = str(modifier_settings.get("modifier_type_filter", "") or "")
            if bool(modifier_settings.get("filter_by_type", False)) and modifier_filter and modifier_filter != "ALL":
                extra_lines.append(f"Modifier Filter: {modifier_filter}")
            modifier_name_filter = str(modifier_settings.get("modifier_name_filter", "") or "").strip()
            if bool(modifier_settings.get("filter_by_name", False)) and modifier_name_filter:
                match_mode = str(modifier_settings.get("modifier_name_match_mode", "EXACT") or "EXACT")
                extra_lines.append(f"Name: {match_mode} '{modifier_name_filter}'")
            if bool(modifier_settings.get("filter_by_context", False)):
                extra_lines.append("Context Filter: Enabled")
            count_value = int(metadata.get("count", 0) or 0)
            if count_value:
                extra_lines.append(f"Fields: {count_value}")
            lines.extend(extra_lines[:max_items])
            return tuple(lines)

        if view_mode == "ENTRIES":
            entries = list(property_definition.get("entries", []))
            for index, entry in enumerate(entries[:max_items], 1):
                lines.append(f"[{index}] {_preview_property_definition_entry_summary(entry)}")
            if len(entries) > max_items:
                lines.append("...")
            return tuple(lines)

        flattened_fields = _collect_preview_property_definition_fields(property_definition)
        for entry_label, field_name in flattened_fields[:max_items]:
            prefix = f"[{entry_label}] " if entry_label else ""
            lines.append(f"{prefix}{field_name}")
        if len(flattened_fields) > max_items:
            lines.append("...")
        return tuple(lines)

    def _format_preview_value(value):
        if isinstance(value, float):
            formatted = f"{value:.4f}".rstrip("0").rstrip(".")
            if formatted in {"", "-0"}:
                return "0"
            return formatted
        if isinstance(value, (list, tuple)):
            if all(isinstance(component, (int, float)) for component in value):
                return "(" + ", ".join(str(_format_preview_value(component)) for component in value) + ")"
            return str(tuple(value))
        if isinstance(value, dict):
            if bool(value.get("__af_rotation__")):
                quaternion = tuple(value.get("quaternion", ()))
                quaternion_text = _format_preview_value(quaternion)
                return f"Quat {quaternion_text}" if quaternion else "Quat"
            if bool(value.get("__af_matrix__")):
                rows = list(value.get("rows", []))
                if rows:
                    row_text = _format_preview_value(tuple(rows[0]))
                    return f"Matrix[{row_text}]"
                return "Matrix"
            mode = str(value.get("mode", "") or "")
            payload = value.get("value")
            if isinstance(payload, (list, tuple)):
                payload_text = _format_preview_value(tuple(payload))
                return f"{mode}: {payload_text}" if mode else payload_text
            return str(value)
        return str(value)

    def _preview_property_assignment_entry_summary(entry):
        assignment_kind = str(entry.get("assignment_kind", "") or "")
        scope_kind = str(entry.get("scope_kind", "") or "")
        properties = dict(entry.get("properties", {}) or {})
        enabled_count = len([key for key, enabled in properties.items() if bool(enabled)])
        kind_label = assignment_kind.title() if assignment_kind else af_iface("Prop Assign")
        scope_label = _property_scope_label(scope_kind) if scope_kind else ""
        detail = f"{enabled_count} field(s)"
        metadata = dict(entry.get("metadata", {}) or {})
        modifier_settings = _modifier_filter_settings_from_metadata(metadata)
        modifier_filter = str(modifier_settings.get("modifier_type_filter", "") or "")
        if bool(modifier_settings.get("filter_by_type", False)) and modifier_filter and modifier_filter != "ALL":
            detail = f"{detail}, {modifier_filter}"
        modifier_name_filter = str(modifier_settings.get("modifier_name_filter", "") or "").strip()
        if bool(modifier_settings.get("filter_by_name", False)) and modifier_name_filter:
            match_mode = str(modifier_settings.get("modifier_name_match_mode", "EXACT") or "EXACT")
            detail = f"{detail}, {match_mode} '{modifier_name_filter}'"
        if bool(modifier_settings.get("filter_by_context", False)):
            detail = f"{detail}, Context"
        return f"{kind_label} / {scope_label} - {detail}" if scope_label else f"{kind_label} - {detail}"

    def _collect_preview_property_assignment_values(property_assignment, path_parts=None, out_items=None):
        if out_items is None:
            out_items = []
        if path_parts is None:
            path_parts = []
        is_composite = bool(_is_composite_property_assignment(property_assignment))
        if is_composite:
            for index, entry in enumerate(list(property_assignment.get("entries", [])), 1):
                _collect_preview_property_assignment_values(entry, [*path_parts, str(index)], out_items)
            return out_items
        entry_label = ".".join(path_parts)
        properties = dict(property_assignment.get("properties", {}) or {})
        sources = dict(property_assignment.get("sources", {}) or {})
        values = dict(property_assignment.get("values", {}) or {})
        for key, enabled in properties.items():
            if not bool(enabled):
                continue
            out_items.append((entry_label, str(key), str(sources.get(key, "VALUE") or "VALUE"), values.get(key)))
        return out_items

    def _preview_property_assignment_lines(node, property_assignment, max_items):
        assignment_kind = str(property_assignment.get("assignment_kind", "") or "")
        scope_kind = str(property_assignment.get("scope_kind", "") or "")
        metadata = dict(property_assignment.get("metadata", {}) or {})
        lines = [assignment_kind.title() if assignment_kind else af_iface("Prop Assign")]
        is_composite = bool(_is_composite_property_assignment(property_assignment))

        extra_lines = []
        if scope_kind:
            extra_lines.append(f"Scope: {_property_scope_label(scope_kind)}")
        source_node = str(property_assignment.get("source_node", "") or "")
        if source_node:
            extra_lines.append(f"Source: {source_node}")
        modifier_settings = _modifier_filter_settings_from_metadata(metadata)
        modifier_filter = str(modifier_settings.get("modifier_type_filter", "") or "")
        if bool(modifier_settings.get("filter_by_type", False)) and modifier_filter and modifier_filter != "ALL":
            extra_lines.append(f"Modifier Filter: {modifier_filter}")
        modifier_name_filter = str(modifier_settings.get("modifier_name_filter", "") or "").strip()
        if bool(modifier_settings.get("filter_by_name", False)) and modifier_name_filter:
            match_mode = str(modifier_settings.get("modifier_name_match_mode", "EXACT") or "EXACT")
            extra_lines.append(f"Name: {match_mode} '{modifier_name_filter}'")
        if bool(modifier_settings.get("filter_by_context", False)):
            extra_lines.append("Context Filter: Enabled")
        count_value = int(metadata.get("count", 0) or 0)
        if count_value:
            extra_lines.append(f"Fields: {count_value}")
        lines.extend(extra_lines[:max_items])
        if len(lines) - 1 >= max_items:
            return tuple(lines)

        if is_composite:
            entries = list(property_assignment.get("entries", []))
            remaining = max(0, max_items - len(lines) + 1)
            for index, entry in enumerate(entries[:remaining], 1):
                lines.append(f"[{index}] {_preview_property_assignment_entry_summary(entry)}")
            if len(entries) > remaining:
                lines.append("...")
            return tuple(lines)

        remaining = max(0, max_items - len(lines) + 1)
        flattened_values = _collect_preview_property_assignment_values(property_assignment)
        for entry_label, key, source, value in flattened_values[:remaining]:
            prefix = f"[{entry_label}] " if entry_label else ""
            if source == "CURRENT":
                lines.append(f"{prefix}{key}=Current")
            else:
                lines.append(f"{prefix}{key}={_format_preview_value(value)}")
        if len(flattened_values) > remaining:
            lines.append("...")
        return tuple(lines)

    def _preview_task_plan_step_node(step_ref):
        tree_name = str(step_ref.get("tree_name", "") or "")
        node_name = str(step_ref.get("node_name", "") or "")
        if not tree_name or not node_name:
            return None
        node_tree = bpy.data.node_groups.get(tree_name)
        if node_tree is None:
            return None
        return getattr(node_tree, "nodes", {}).get(node_name) if hasattr(getattr(node_tree, "nodes", None), "get") else None

    def _preview_task_plan_step_type_label(step_ref):
        step_node = _preview_task_plan_step_node(step_ref)
        if step_node is None:
            return str(step_ref.get("node_name", "") or "")
        if getattr(step_node, "bl_idname", "") == "AFNodeGroup":
            group_tree = getattr(step_node, "group_tree", None)
            if group_tree is not None and str(getattr(group_tree, "name", "") or "").strip():
                return str(group_tree.name)
        return str(getattr(step_node, "bl_label", "") or getattr(step_node, "name", "") or "Step")

    def _preview_task_plan_path_label(step_ref):
        node_name = str(step_ref.get("node_name", "") or "")
        type_label = _preview_task_plan_step_type_label(step_ref)
        if not node_name or node_name == type_label:
            return type_label
        return f"{type_label} ({node_name})"

    def _preview_task_plan_lines(node, task_plan, max_items):
        view_mode = str(getattr(node, "preview_task_plan_view_mode", "STEPS") or "STEPS")
        if view_mode not in {"SUMMARY", "STEPS", "STRUCTURE"}:
            view_mode = "STEPS"

        step_refs = list(task_plan.get("step_refs", []) or [])
        step_names = [str(step_ref.get("node_name", "") or "") for step_ref in step_refs] or [str(name) for name in list(task_plan.get("step_names", []) or [])]
        repeat_pair_count = len(dict(task_plan.get("repeat_pairs", {}) or {})) // 2
        repeat_pairs = dict(task_plan.get("repeat_pairs", {}) or {})
        lines = [f"Steps: {int(task_plan.get('step_count', len(step_names)))}"]

        if view_mode == "SUMMARY":
            output_node = str(task_plan.get("output_node", "") or "")
            output_tree_name = str(task_plan.get("output_tree_name", "") or "")
            if output_tree_name:
                lines.append(f"Group Tree: {output_tree_name}")
            if output_node:
                lines.append(f"Output: {output_node}")
            if repeat_pair_count:
                lines.append(f"Repeat Start: {repeat_pair_count}")
            return tuple(lines[: max_items + 1])

        display_steps = step_refs if step_refs else [{"node_name": name, "group_path": []} for name in step_names]
        for index, step_ref in enumerate(display_steps[:max_items], 1):
            step_type_label = _preview_task_plan_step_type_label(step_ref)
            if view_mode == "STRUCTURE":
                group_nodes = [
                    _preview_task_plan_path_label(item)
                    for item in list(step_ref.get("group_path", []) or [])
                    if str(item.get("node_name", "") or "")
                ]
                node_label = _preview_task_plan_path_label(step_ref)
                label = " / ".join([*group_nodes, node_label]) if group_nodes else node_label
            else:
                label = step_type_label
            repeat_info = repeat_pairs.get(index - 1)
            if repeat_info is not None and "count" in repeat_info:
                label = f"{label} [x{int(repeat_info['count'])}]"
            lines.append(f"[{index}] {label}")
        if len(display_steps) > max_items:
            lines.append("...")
        return tuple(lines)

    def _preview_lines_for_payload(node, context):
        payload = _preview_input_payload(node, context)
        if payload is None:
            return ("No linked data",)

        mode = _preview_effective_mode(node)
        max_items = max(1, int(getattr(node, "preview_line_count", 4)))

        if mode == "OBJECT_LIST":
            items = list(payload.get("items", []))
            lines = [f"Count: {int(payload.get('count', len(items)))}"]
            for item in items[:max_items]:
                lines.append(str(item.get("name", "")))
            if len(items) > max_items:
                lines.append("...")
            return tuple(lines)

        if mode == "OBJECT":
            if isinstance(payload, dict):
                if "items" in payload:
                    items = list(payload.get("items", []))
                    first_item = items[0] if items else {}
                    object_name = str(first_item.get("name", "") or "")
                    object_id = first_item.get("id")
                    lines = [object_name or "Object"]
                    if object_id is not None:
                        lines.append(f"ID: {object_id}")
                    if int(payload.get("count", len(items))) > 1:
                        lines.append(f"Count: {int(payload.get('count', len(items)))}")
                    return tuple(lines[: max_items + 1])
                object_name = str(payload.get("name", "") or "")
                object_id = payload.get("id")
                lines = [object_name or "Object"]
                if object_id is not None:
                    lines.append(f"ID: {object_id}")
                return tuple(lines[: max_items + 1])
            return (str(payload),)

        if mode == "STRING":
            text_value = "" if payload is None else str(payload)
            lines = text_value.splitlines() if text_value else [""]
            if len(lines) > max_items:
                return tuple([*lines[:max_items], "..."])
            return tuple(lines)

        if mode == "BOOLEAN":
            return (f"Value: {bool(payload)}",)

        if mode == "INTEGER":
            return (f"Value: {int(payload)}",)

        if mode == "FLOAT":
            return (f"Value: {_format_preview_value(float(payload))}",)

        if mode == "VECTOR":
            vector_value = tuple(payload or ())
            if len(vector_value) >= 3:
                return (
                    "Vector",
                    f"X: {_format_preview_value(float(vector_value[0]))}",
                    f"Y: {_format_preview_value(float(vector_value[1]))}",
                    f"Z: {_format_preview_value(float(vector_value[2]))}",
                )
            return (f"Value: {_format_preview_value(vector_value)}",)

        if mode == "ROTATION":
            if isinstance(payload, dict) and bool(payload.get("__af_rotation__")):
                quaternion = tuple(payload.get("quaternion", ()))
                if len(quaternion) >= 4:
                    return (
                        "Rotation",
                        f"W: {_format_preview_value(float(quaternion[0]))}",
                        f"X: {_format_preview_value(float(quaternion[1]))}",
                        f"Y: {_format_preview_value(float(quaternion[2]))}",
                        f"Z: {_format_preview_value(float(quaternion[3]))}",
                    )
            return (f"Value: {_format_preview_value(payload)}",)

        if mode == "MATRIX":
            if isinstance(payload, dict) and bool(payload.get("__af_matrix__")):
                rows = list(payload.get("rows", []))
                lines = ["Matrix"]
                for row in rows[:max_items]:
                    row_values = [str(_format_preview_value(float(component))) for component in list(row)[:4]]
                    lines.append("[ " + ", ".join(row_values) + " ]")
                if len(rows) > max_items:
                    lines.append("...")
                return tuple(lines)
            return (f"Value: {_format_preview_value(payload)}",)

        if mode == "DISPLAY_TYPE":
            return (f"Value: {_enum_identifier_label(OBJECT_DISPLAY_TYPE_ITEMS, payload)}",)

        if mode == "OBJECT_INTERACTION_MODE":
            return (f"Value: {_enum_identifier_label(OBJECT_INTERACTION_MODE_ITEMS, payload)}",)

        if mode == "ROTATION_MODE":
            return (f"Value: {_enum_identifier_label(OBJECT_ROTATION_MODE_ITEMS, payload)}",)

        if mode == "VIEWPORT_SHADING_MODE":
            return (f"Value: {_enum_identifier_label(VIEWPORT_SHADING_MODE_ITEMS, payload)}",)

        if mode == "PROPERTY_DEFINITION":
            return _preview_property_definition_lines(node, payload, max_items)

        if mode == "PROPERTY_ASSIGNMENT":
            return _preview_property_assignment_lines(node, payload, max_items)

        if mode == "PROPERTY_PACKAGE":
            return _preview_property_package_lines(node, payload, max_items)

        if mode == "TASK_REF":
            report_payload = dict(payload.get("report", {}) or {}) if isinstance(payload, dict) else {}
            task_kind = str(payload.get("task_kind", report_payload.get("task_kind", "TASK")) or "TASK")
            status_value = str(payload.get("status", report_payload.get("status", "")) or "").strip()
            lines = [task_kind.title()]
            if status_value:
                lines.append(af_iface("Status") + f": {status_value}")
            source_task_kind = str(payload.get("_source_task_kind", "") or "").strip()
            if source_task_kind and source_task_kind != task_kind:
                lines.append("Source" + f": {source_task_kind.title()}")
            object_ref = payload.get("object_ref")
            if object_ref is not None:
                lines.append(str(getattr(object_ref, "name", "")))
            scene_ref = payload.get("scene_ref")
            if scene_ref is not None:
                scene_name = str(getattr(scene_ref, "name", "") or "")
                if scene_name:
                    lines.append("Scene" + f": {scene_name}")
            predicted_items = list(payload.get("predicted_object_items", []) or [])
            if predicted_items:
                object_names = [str(item.get("name", "") or "") for item in predicted_items if str(item.get("name", "") or "")]
                if object_names:
                    lines.append("Objects" + f": {', '.join(object_names[:max_items])}")
                    if len(object_names) > max_items:
                        lines.append("...")
            else:
                object_count = payload.get("object_count", report_payload.get("object_count", None))
                if object_count is not None:
                    lines.append("Object Count" + f": {object_count}")
            action_name = str(payload.get("action_name", "") or "").strip()
            if action_name:
                lines.append("Action" + f": {action_name}")
            cache_kind = ""
            if bool(payload.get("cache_packed", report_payload.get("cache_packed", False))):
                cache_kind = "Packed"
            elif bool(payload.get("cache_on_disk", report_payload.get("cache_on_disk", False))):
                cache_kind = "Disk"
            elif bool(payload.get("has_cache", report_payload.get("has_cache", False))):
                cache_kind = "Cached"
            if cache_kind:
                lines.append("Cache" + f": {cache_kind}")
            cache_frame_start = payload.get("cache_frame_start", report_payload.get("cache_frame_start", None))
            cache_frame_end = payload.get("cache_frame_end", report_payload.get("cache_frame_end", None))
            if cache_frame_start is not None or cache_frame_end is not None:
                lines.append(f"Cache Frames: {cache_frame_start if cache_frame_start is not None else '?'} - {cache_frame_end if cache_frame_end is not None else '?'}")
            frame_start = payload.get("frame_start", report_payload.get("frame_start", None))
            frame_end = payload.get("frame_end", report_payload.get("frame_end", None))
            if frame_start is not None or frame_end is not None:
                lines.append(f"Frames: {frame_start if frame_start is not None else '?'} - {frame_end if frame_end is not None else '?'}")
            record_node_name = str(payload.get("record_node_name", "") or "").strip()
            if record_node_name:
                lines.append("Record" + f": {record_node_name}")
            start_node_name = str(payload.get("start_node_name", "") or "").strip()
            if start_node_name:
                lines.append("Start" + f": {start_node_name}")
            source_tree_name = str(payload.get("source_tree_name", "") or "").strip()
            if source_tree_name:
                lines.append("Tree" + f": {source_tree_name}")
            prediction_reason = str(payload.get("prediction_reason", "") or "").strip()
            if prediction_reason:
                lines.append("Prediction" + f": {prediction_reason}")
            last_bake_state = dict(payload.get("last_bake_state", {}) or {}) if isinstance(payload, dict) else {}
            if last_bake_state:
                last_bake_target = str(last_bake_state.get("bake_target", "") or "").strip().upper()
                if last_bake_target == "DISK":
                    last_bake_label = af_iface("Disk")
                elif last_bake_target == "PACKED":
                    last_bake_label = af_iface("Packed")
                elif last_bake_target:
                    last_bake_label = last_bake_target.title()
                else:
                    last_bake_label = af_iface("Done")
                lines.append(af_iface("Last Bake") + f": {last_bake_label}")
                last_frame_start = last_bake_state.get("frame_start", None)
                last_frame_end = last_bake_state.get("frame_end", None)
                if last_frame_start is not None or last_frame_end is not None:
                    lines.append(
                        af_iface("Last Frames")
                        + f": {last_frame_start if last_frame_start is not None else '?'} - {last_frame_end if last_frame_end is not None else '?'}"
                    )
                if bool(last_bake_state.get("use_custom_path", False)):
                    last_directory = str(last_bake_state.get("directory", "") or "").strip()
                    if last_directory:
                        lines.append(af_iface("Last Path") + f": {last_directory}")
            return tuple(lines)

        if mode == "TASK_PLAN":
            return _preview_task_plan_lines(node, payload, max_items)

        if mode == "TASK_HANDLE":
            report_payload = dict(payload.get("report", {}) or {}) if isinstance(payload, dict) else {}
            task_kind = str(payload.get("task_kind", report_payload.get("task_kind", "TASK")) or "TASK")
            status_value = str(payload.get("status", report_payload.get("status", "INVALID")) or "INVALID").strip()
            lines = [task_kind.title()]
            if status_value:
                lines.append(af_iface("Status") + f": {status_value}")
            task_id = str(payload.get("task_id", "") or "").strip()
            if task_id:
                lines.append("Task ID" + f": {task_id}")
            node_name = str(payload.get("node_name", "") or "").strip()
            if node_name:
                lines.append("Node" + f": {node_name}")
            if bool(payload.get("skipped", False) or report_payload.get("skipped", False)):
                lines.append("Skipped: True")
            if bool(payload.get("simulated", False) or report_payload.get("simulated", False)):
                lines.append("Simulated: True")
            if bool(payload.get("flow_test", False) or report_payload.get("flow_test", False)):
                lines.append("Flow Test: True")
            step_count = payload.get("step_count", report_payload.get("step_count", None))
            if step_count is not None:
                lines.append("Steps" + f": {step_count}")
            frame_start = report_payload.get("frame_start", None)
            frame_end = report_payload.get("frame_end", None)
            if frame_start is not None or frame_end is not None:
                lines.append(
                    "Frames"
                    + f": {frame_start if frame_start is not None else '?'} - {frame_end if frame_end is not None else '?'}"
                )
            error_message = str(report_payload.get("error_message", "") or "").strip()
            if error_message:
                lines.append("Error" + f": {error_message}")
            if len(lines) > max_items + 1:
                return tuple([*lines[: max_items + 1], "..."])
            return tuple(lines)

        if mode == "REPORT":
            if isinstance(payload, dict):
                lines = []
                for key, value in list(dict(payload or {}).items())[: max_items + 1]:
                    lines.append(f"{key}: {value}")
                return tuple(lines or ("Report",))
            text_value = "" if payload is None else str(payload)
            lines = text_value.splitlines() if text_value else ["Report"]
            if len(lines) > max_items:
                return tuple([*lines[:max_items], "..."])
            return tuple(lines)

        return ("Unsupported",)

    class AFNodePreviewData(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodePreviewData"
        bl_label = "Preview Data"
        bl_icon = "BLANK1"

        preview_mode: bpy.props.EnumProperty(
            name="Mode",
            items=PREVIEW_DATA_MODE_ITEMS,
            default="OBJECT_LIST",
            update=lambda self, context: _sync_preview_data_sockets(self),
        )
        preview_property_package_view_mode: bpy.props.EnumProperty(
            name="Prop Pack View",
            items=PREVIEW_PROPERTY_PACKAGE_VIEW_MODE_ITEMS,
            default="ENTRIES",
        )
        preview_property_definition_view_mode: bpy.props.EnumProperty(
            name="Prop Def View",
            items=PREVIEW_PROPERTY_DEFINITION_VIEW_MODE_ITEMS,
            default="ENTRIES",
        )
        preview_task_plan_view_mode: bpy.props.EnumProperty(
            name="Task Plan View",
            items=PREVIEW_TASK_PLAN_VIEW_MODE_ITEMS,
            default="STEPS",
        )
        preview_line_count: bpy.props.IntProperty(name="Max Lines", default=8, min=1, max=128)

        def init(self, context):
            del context
            _sync_preview_data_sockets(self)
            _set_default_node_width(self, multiplier=2.0)

        def update(self):
            _sync_preview_data_sockets(self)

        def draw_buttons(self, context, layout):
            preview_context = _normalized_preview_context(context)
            try:
                _sync_preview_data_sockets(self)
            except Exception:
                pass
            effective_mode = _preview_effective_mode(self)
            header = layout.row(align=True)
            header.label(text=_preview_mode_label(self))
            header.prop(self, "preview_line_count", text="Max Lines")
            if effective_mode == "PROPERTY_PACKAGE":
                layout.prop(self, "preview_property_package_view_mode", expand=True)
            elif effective_mode == "PROPERTY_DEFINITION":
                layout.prop(self, "preview_property_definition_view_mode", expand=True)
            elif effective_mode == "TASK_PLAN":
                layout.prop(self, "preview_task_plan_view_mode", expand=True)
            box = layout.box()
            for line in _preview_lines_for_payload(self, preview_context):
                box.label(text=str(line), translate=False)

    def refresh_preview_data_nodes_ui():
        for node_tree in bpy.data.node_groups:
            if getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
                continue
            touched = False
            for node in getattr(node_tree, "nodes", []):
                if getattr(node, "bl_idname", "") != "AFNodePreviewData":
                    continue
                try:
                    _sync_preview_data_sockets(node)
                    touched = True
                except Exception:
                    continue
            if touched:
                try:
                    node_tree.interface_update(bpy.context)
                except Exception:
                    pass
                try:
                    node_tree.update_tag()
                except Exception:
                    pass

    def schedule_preview_data_ui_refresh():
        def _timer():
            try:
                refresh_preview_data_nodes_ui()
            except Exception:
                pass
            return None

        try:
            bpy.app.timers.register(_timer, first_interval=0.1)
        except Exception:
            pass

    return {
        "AFNodePreviewData": AFNodePreviewData,
        "normalized_preview_context": _normalized_preview_context,
        "schedule_preview_data_ui_refresh": schedule_preview_data_ui_refresh,
    }
