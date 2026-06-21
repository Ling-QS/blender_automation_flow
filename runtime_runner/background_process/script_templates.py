import textwrap


def _automation_flow_loader_function_text(module_imports):
    import_lines = [
        f"    {alias} = importlib.import_module(package_name + '.{module_path}')"
        for alias, module_path in module_imports
    ]
    return_names = ", ".join(["module", *[alias for alias, _module_path in module_imports]])
    lines = [
        "def _load_automation_flow(package_dir):",
        "    package_path = pathlib.Path(package_dir)",
        '    init_path = package_path / "__init__.py"',
        "    if not init_path.exists():",
        '        raise RuntimeError(f"Automation Flow package not found: {init_path}")',
        '    package_name = "automation_flow_background_exec"',
        "    spec = importlib.util.spec_from_file_location(",
        "        package_name,",
        "        init_path,",
        "        submodule_search_locations=[str(package_path)],",
        "    )",
        "    if spec is None or spec.loader is None:",
        '        raise RuntimeError("Failed to load Automation Flow package spec")',
        "    module = importlib.util.module_from_spec(spec)",
        "    sys.modules[package_name] = module",
        "    spec.loader.exec_module(module)",
        "    module.register()",
        *import_lines,
        f"    return {return_names}",
    ]
    return "\n".join(lines)


def background_task_plan_script_text():
    loader_block = _automation_flow_loader_function_text(
        [
            ("runtime_runner", "runtime_runner"),
            ("runtime_constants", "runtime_core.constants"),
        ]
    )
    template = """
import bpy
import importlib
import importlib.util
import json
import os
import pathlib
import sys
import time
import traceback


def _write_status(path, payload):
    temp_path = path + ".tmp"
    serializer = getattr(globals().get("runtime"), "_serialize_runtime_state_value", None)
    if serializer is not None:
        payload = serializer(payload)
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True)
    os.replace(temp_path, path)


__LOADER_BLOCK__


def _normalize_repeat_pairs(task_plan):
    pairs = {}
    for key, value in dict(task_plan.get("repeat_pairs", {}) or {}).items():
        try:
            cursor = int(key)
        except Exception:
            continue
        if not isinstance(value, dict):
            continue
        pairs[cursor] = dict(value)
    return pairs


def _normalize_indexed_plan_dict(task_plan, key_name):
    plans = {}
    source = dict(task_plan.get(key_name, {}) or {})
    for key, value in source.items():
        try:
            cursor = int(key)
        except Exception:
            continue
        if not isinstance(value, dict):
            continue
        plans[cursor] = dict(value)
    return plans


def _make_entry(task_plan, title):
    step_refs = list(task_plan.get("step_refs", []))
    step_count = int(task_plan.get("step_count", len(step_refs)))
    return {
        "socket": None,
        "socket_index": 1,
        "title": str(title or "Background Task Plan"),
        "enabled": True,
        "task_plan": dict(task_plan),
        "step_refs": step_refs,
        "step_count": step_count,
        "repeat_pairs": _normalize_repeat_pairs(task_plan),
        "subflow_plans": _normalize_indexed_plan_dict(task_plan, "subflow_plans"),
        "branch_plans": _normalize_indexed_plan_dict(task_plan, "branch_plans"),
        "cursor": 0,
        "completed_step_count": 0,
        "status": "PENDING",
        "step_started": False,
        "repeat_states": {},
        "runtime_status_override": "",
        "from_node": None,
        "from_socket": None,
        "enabled_index": 1,
        "enabled_total": 1,
    }


def _current_entry(runner):
    state = getattr(runner, "current_task_plan", None)
    if not isinstance(state, dict):
        return None
    entries = state.get("entries", [])
    cursor = int(state.get("cursor", 0))
    if cursor < 0 or cursor >= len(entries):
        return None
    return entries[cursor]


def _snapshot_current_step(runner, launcher_node):
    entry = _current_entry(runner)
    if entry is None:
        return None
    step_refs = entry.get("step_refs", [])
    cursor = int(entry.get("cursor", 0))
    if cursor < 0 or cursor >= len(step_refs):
        return None
    step_ref = dict(step_refs[cursor])
    step_node = runner._resolve_step_ref(step_ref, launcher_node.name)
    return {
        "step_ref": step_ref,
        "node_name": step_node.name,
        "tree_name": getattr(getattr(step_node, "id_data", None), "name", ""),
        "group_path": list(step_ref.get("group_path", [])),
        "completed_step_count": int(entry.get("completed_step_count", 0)),
        "step_count": int(entry.get("step_count", 0)),
    }


def _step_key(snapshot):
    if not isinstance(snapshot, dict):
        return ""
    step_ref = snapshot.get("step_ref", {})
    group_path = step_ref.get("group_path", [])
    return json.dumps(
        {
            "tree_name": step_ref.get("tree_name", ""),
            "node_name": step_ref.get("node_name", ""),
            "group_path": group_path,
        },
        ensure_ascii=True,
        sort_keys=True,
    )


def _append_event(events, event_type, snapshot=None, payload=None, wait_type=""):
    event = {
        "type": str(event_type),
        "step_ref": {},
        "node_name": "",
        "tree_name": "",
        "group_path": [],
        "wait_type": str(wait_type or ""),
    }
    if isinstance(snapshot, dict):
        event["step_ref"] = dict(snapshot.get("step_ref", {}))
        event["node_name"] = str(snapshot.get("node_name", "") or "")
        event["tree_name"] = str(snapshot.get("tree_name", "") or "")
        event["group_path"] = list(snapshot.get("group_path", []))
    if payload is not None:
        event["payload"] = payload
    events.append(event)


def _property_package_bake_reports(runtime_constants, runner):
    if runtime_constants is None or runner is None:
        return []
    property_package_bake_kind = getattr(runtime_constants, "TASK_KIND_PROPERTY_PACKAGE_BAKE", "PROPERTY_PACKAGE_BAKE")
    reports = []
    for task_handle in getattr(runner, "tasks", {}).values():
        if not isinstance(task_handle, dict):
            continue
        if str(task_handle.get("task_kind", "")) != property_package_bake_kind:
            continue
        report = dict(task_handle.get("report", {}) or {})
        if not report:
            continue
        report.setdefault("task_kind", property_package_bake_kind)
        report["skipped"] = bool(task_handle.get("skipped", False) or report.get("skipped", False))
        reports.append(report)
    return reports


def _status_payload(runner, launcher_node, task_plan, events, state_name, final_report=None, error_payload=None):
    snapshot = None
    entry = None
    if runner is not None and launcher_node is not None:
        snapshot = _snapshot_current_step(runner, launcher_node)
        entry = _current_entry(runner)
    completed_step_count = int(entry.get("completed_step_count", 0)) if entry is not None else int(task_plan.get("step_count", 0))
    if state_name == "DONE":
        completed_step_count = int(task_plan.get("step_count", completed_step_count))
    if runner is not None:
        current_wait = getattr(runner, "current_wait", None) or {}
    else:
        current_wait = {}
    report = dict(final_report or {})
    if not report:
        report = {
            "step_count": int(task_plan.get("step_count", 0)),
            "completed_step_count": int(completed_step_count),
        }
    payload = {
        "state": str(state_name),
        "step_count": int(task_plan.get("step_count", 0)),
        "completed_step_count": int(completed_step_count),
        "current_step_name": str(snapshot.get("node_name", "") if snapshot else ""),
        "current_step_tree_name": str(snapshot.get("tree_name", "") if snapshot else ""),
        "current_step_group_path": list(snapshot.get("group_path", []) if snapshot else []),
        "current_wait_type": str(current_wait.get("wait_type", "") or ""),
        "events": list(events),
        "report": report,
    }
    if error_payload is not None:
        payload["error"] = dict(error_payload)
    return payload


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
status_path, package_dir, launcher_ref_json, task_plan_json, poll_interval_ms = args[:5]
final_payload = {}
try:
    _module, runtime_runner, runtime_constants = _load_automation_flow(package_dir)
    launcher_ref = json.loads(launcher_ref_json)
    task_plan = json.loads(task_plan_json)
    tree_name = str(launcher_ref.get("tree_name", "") or "")
    node_name = str(launcher_ref.get("node_name", "") or "")
    node_tree = bpy.data.node_groups.get(tree_name)
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        raise RuntimeError(f"Background task tree '{tree_name}' not found")
    launcher_node = node_tree.nodes.get(node_name)
    if launcher_node is None:
        raise RuntimeError(f"Background task launcher '{node_name}' not found")
    scene = bpy.context.scene or (bpy.data.scenes[0] if bpy.data.scenes else None)
    if scene is None:
        raise RuntimeError("No scene available for background task execution")
    runner = runtime_runner.FlowRunner(node_tree, scene)
    runner._external_process_execution = True
    runner.current_task_plan = {
        "run_node_name": launcher_node.name,
        "entries": [_make_entry(task_plan, launcher_node.name)],
        "cursor": 0,
        "linked_count": 1,
        "enabled_count": 1,
        "completed_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "failure_policy": "STOP_ON_FAILURE",
        "first_failure": None,
        "active_entry_index": -1,
    }
    events = []
    started_step_key = ""
    waiting_step_key = ""
    waiting_type = ""
    poll_seconds = max(0.05, int(poll_interval_ms) / 1000.0)
    _write_status(
        status_path,
        _status_payload(runner, launcher_node, task_plan, events, "RUNNING"),
    )
    while True:
        snapshot_before = _snapshot_current_step(runner, launcher_node)
        current_step_key = _step_key(snapshot_before)
        if current_step_key and current_step_key != started_step_key:
            _append_event(events, "STEP_STARTED", snapshot_before)
            started_step_key = current_step_key
            waiting_step_key = ""
            waiting_type = ""
        result, payload = runner._execute_task_plan(launcher_node)
        if result == runtime_constants.FLOW_WAIT:
            wait_info = getattr(runner, "current_wait", None) or {}
            current_wait_type = str(wait_info.get("wait_type", "") or "")
            if current_step_key and (current_step_key != waiting_step_key or current_wait_type != waiting_type):
                _append_event(events, "STEP_WAITING", snapshot_before, wait_type=current_wait_type)
                waiting_step_key = current_step_key
                waiting_type = current_wait_type
            _write_status(
                status_path,
                _status_payload(runner, launcher_node, task_plan, events, "WAITING"),
            )
            time.sleep(poll_seconds)
            continue
        if snapshot_before is not None:
            _append_event(events, "STEP_DONE", snapshot_before, payload=payload)
        waiting_step_key = ""
        waiting_type = ""
        if result == runtime_constants.FLOW_YIELD:
            _write_status(
                status_path,
                _status_payload(runner, launcher_node, task_plan, events, "RUNNING"),
            )
            continue
        final_report = runner._get_output(launcher_node, "report") or {}
        try:
            if any(
                bool(task_handle.get("skipped", False)) or bool(dict(task_handle.get("report") or {}).get("skipped", False))
                for task_handle in getattr(runner, "tasks", {}).values()
                if isinstance(task_handle, dict)
            ):
                final_report = dict(final_report or {})
                final_report["skipped"] = True
        except Exception:
            pass
        property_package_bake_reports = _property_package_bake_reports(runtime_constants, runner)
        if property_package_bake_reports:
            final_report = dict(final_report or {})
            final_report["property_package_bake_reports"] = property_package_bake_reports
            save_result = bpy.ops.wm.save_mainfile(filepath=str(getattr(bpy.data, 'filepath', '') or ''), check_existing=False, compress=False)
            if "FINISHED" not in {str(token) for token in save_result}:
                raise RuntimeError("Failed to save background task plan result blend")
        final_payload = _status_payload(runner, launcher_node, task_plan, events, "DONE", final_report=final_report)
        final_payload["success"] = True
        final_payload["report"] = dict(final_report)
        final_payload["skipped"] = bool(dict(final_report).get("skipped", False))
        _write_status(status_path, final_payload)
        break
except Exception as exc:
    error_payload = {
        "error_code": str(getattr(exc, "code", "AF_E005")),
        "error_message": str(getattr(exc, "message", str(exc))),
        "node_name": str(getattr(exc, "node_name", "") or ""),
        "traceback": traceback.format_exc(),
    }
    fallback_plan = {}
    try:
        fallback_plan = json.loads(task_plan_json)
    except Exception:
        fallback_plan = {"step_count": 0}
    try:
        fallback_launcher = launcher_node
    except Exception:
        fallback_launcher = None
    try:
        fallback_runner = runner
    except Exception:
        fallback_runner = None
    final_payload = _status_payload(
        fallback_runner,
        fallback_launcher,
        fallback_plan,
        locals().get("events", []),
        "FAILED",
        error_payload=error_payload,
    )
    final_payload["success"] = False
    final_payload.update(error_payload)
    _write_status(status_path, final_payload)
"""
    return textwrap.dedent(template).replace("__LOADER_BLOCK__", loader_block).lstrip()


__all__ = [
    "background_task_plan_script_text",
]
