import json
import os


def _reload_resume_checkpoint_path(blend_filepath):
    filepath = str(blend_filepath or "").strip()
    if not filepath:
        return ""
    return f"{filepath}.af_reload_resume.json"


def _write_reload_resume_checkpoint(filepath, payload, serialize_runtime_state_value):
    checkpoint_path = _reload_resume_checkpoint_path(filepath)
    if not checkpoint_path:
        return ""
    temp_path = f"{checkpoint_path}.tmp"
    serialized_payload = serialize_runtime_state_value(payload)
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(serialized_payload, handle, ensure_ascii=True, indent=2)
    os.replace(temp_path, checkpoint_path)
    return checkpoint_path


def _read_reload_resume_checkpoint(filepath, deserialize_runtime_state_value):
    checkpoint_path = _reload_resume_checkpoint_path(filepath)
    if not checkpoint_path or not os.path.exists(checkpoint_path):
        return None
    with open(checkpoint_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return deserialize_runtime_state_value(payload)


def _remove_reload_resume_checkpoint(filepath):
    checkpoint_path = _reload_resume_checkpoint_path(filepath)
    if not checkpoint_path or not os.path.exists(checkpoint_path):
        return False
    try:
        os.remove(checkpoint_path)
        return True
    except Exception:
        return False

