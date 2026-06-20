import bpy
from bpy.app.translations import pgettext_iface as iface_


def _zh(text):
    return text.encode("ascii").decode("unicode_escape")


_AF_ZH_LABELS = {
    "Property Definition": _zh("\\u5c5e\\u6027\\u5b9a\\u4e49"),
    "Property Assignment": _zh("\\u5c5e\\u6027\\u8d4b\\u503c"),
    "Property Package": _zh("\\u5c5e\\u6027\\u5305"),
    "Prop Def": _zh("\\u5c5e\\u6027\\u5b9a\\u4e49"),
    "Prop Assign": _zh("\\u5c5e\\u6027\\u8d4b\\u503c"),
    "Prop Pack": _zh("\\u5c5e\\u6027\\u5305"),
    "Prop Pack Bake Target": _zh("\\u5c5e\\u6027\\u5305\\u70d8\\u7119\\u76ee\\u6807"),
    "Definition": _zh("\\u5c5e\\u6027\\u5b9a\\u4e49"),
    "Assignment": _zh("\\u8d4b\\u503c"),
    "Package": _zh("\\u6253\\u5305"),
    "Base Property Definition": _zh("\\u57fa\\u7840\\u5c5e\\u6027\\u5b9a\\u4e49"),
    "Add Property Definition": _zh("\\u65b0\\u589e\\u5c5e\\u6027\\u5b9a\\u4e49"),
    "Base Property Assignment": _zh("\\u57fa\\u7840\\u5c5e\\u6027\\u8d4b\\u503c"),
    "Add Property Assignment": _zh("\\u65b0\\u589e\\u5c5e\\u6027\\u8d4b\\u503c"),
    "Base Property Package": _zh("\\u57fa\\u7840\\u5c5e\\u6027\\u5305"),
    "Add Property Package": _zh("\\u65b0\\u589e\\u5c5e\\u6027\\u5305"),
    "Target": _zh("\\u76ee\\u6807"),
    "Settings": _zh("\\u8bbe\\u7f6e"),
    "Status": _zh("\\u72b6\\u6001"),
    "Current": _zh("\\u5f53\\u524d"),
    "Expired": _zh("\\u5df2\\u8fc7\\u671f"),
    "Last Bake": _zh("\\u4e0a\\u6b21\\u70d8\\u7119"),
    "Last Frames": _zh("\\u4e0a\\u6b21\\u5e27\\u8303\\u56f4"),
    "Last Path": _zh("\\u4e0a\\u6b21\\u8def\\u5f84"),
    "Ready": _zh("\\u5c31\\u7eea"),
    "Done": _zh("\\u5b8c\\u6210"),
    "Skipped": _zh("\\u5df2\\u8df3\\u8fc7"),
    "Invalid": _zh("\\u65e0\\u6548"),
    "Failed": _zh("\\u5931\\u8d25"),
    "Warning": _zh("\\u8b66\\u544a"),
    "Cancelled": _zh("\\u5df2\\u53d6\\u6d88"),
    "Running": _zh("\\u8fd0\\u884c\\u4e2d"),
    "Waiting": _zh("\\u7b49\\u5f85\\u4e2d"),
    "Idle": _zh("\\u7a7a\\u95f2"),
    "Precheck": _zh("\\u9884\\u68c0"),
    "Reloading": _zh("\\u91cd\\u8f7d\\u4e2d"),
    "Success": _zh("\\u6210\\u529f"),
    "Snapshot": _zh("\\u5feb\\u7167"),
    "Object": _zh("\\u7269\\u4f53"),
    "Modifier": _zh("\\u4fee\\u6539\\u5668"),
    "GN Bake": _zh("GN \\u70d8\\u7119"),
    "Property Package Bake Target": _zh("\\u5c5e\\u6027\\u5305\\u70d8\\u7119\\u76ee\\u6807"),
    "Physics Bake": _zh("\\u7269\\u7406\\u70d8\\u7119"),
    "Mixed": _zh("\\u6df7\\u5408"),
    "Output": _zh("\\u8f93\\u51fa"),
    "Stored": _zh("\\u5df2\\u5b58\\u50a8"),
    "Output Stored": _zh("\\u4ec5\\u8f93\\u51fa\\u5df2\\u5b58\\u50a8"),
    "Empty": _zh("\\u7a7a"),
    "Objects Only": _zh("\\u4ec5\\u7269\\u4f53"),
    "No Properties": _zh("\\u65e0\\u5c5e\\u6027"),
    "Disk": _zh("\\u78c1\\u76d8"),
    "Disk Cache": _zh("\\u78c1\\u76d8\\u7f13\\u5b58"),
    "Task Plan": _zh("\\u4efb\\u52a1\\u8ba1\\u5212"),
    "Context": _zh("\\u4e0a\\u4e0b\\u6587"),
    "Enabled": _zh("\\u5df2\\u542f\\u7528"),
}

_STATUS_IDENTIFIER_LABELS = {
    "READY": "Ready",
    "DONE": "Done",
    "SKIPPED": "Skipped",
    "INVALID": "Invalid",
    "FAILED": "Failed",
    "WARNING": "Warning",
    "CANCELLED": "Cancelled",
    "RUNNING": "Running",
    "WAITING": "Waiting",
    "IDLE": "Idle",
    "PRECHECK": "Precheck",
    "RELOADING": "Reloading",
    "SUCCESS": "Success",
}

_COMPOUND_SUFFIXES = ("Settings", "Snapshot", "Target")

_AF_COMPACT_EN_LABELS = {
    "Property Definition": "Prop Def",
    "Property Assignment": "Prop Assign",
    "Property Package": "Prop Pack",
    "Property Package Bake Target": "Prop Pack Bake Target",
    "Base Property Definition": "Base Prop Def",
    "Add Property Definition": "Add Prop Def",
    "Base Property Assignment": "Base Prop Assign",
    "Add Property Assignment": "Add Prop Assign",
    "Base Property Package": "Base Prop Pack",
    "Add Property Package": "Add Prop Pack",
}

_AF_COMPACT_EN_PREFIXES = (
    ("Property Definition ", "Prop Def "),
    ("Property Assignment ", "Prop Assign "),
    ("Property Package ", "Prop Pack "),
)


def _use_chinese_ui():
    try:
        preferences = getattr(bpy.context, "preferences", None)
        view = getattr(preferences, "view", None)
        language = str(getattr(view, "language", "") or "")
    except Exception:
        language = ""
    return language.startswith("zh")


def af_label(text):
    raw_text = str(text or "")
    if not raw_text or not _use_chinese_ui():
        return raw_text
    localized = _AF_ZH_LABELS.get(raw_text)
    if localized is not None:
        return localized
    for suffix in _COMPOUND_SUFFIXES:
        suffix_token = f" {suffix}"
        if not raw_text.endswith(suffix_token):
            continue
        prefix = raw_text[: -len(suffix_token)].strip()
        if prefix:
            return f"{af_iface(prefix)} {af_iface(suffix)}"
    return raw_text


def af_compact_label(text):
    raw_text = str(text or "")
    if not raw_text:
        return raw_text
    if _use_chinese_ui():
        return af_label(raw_text)
    compact = _AF_COMPACT_EN_LABELS.get(raw_text)
    if compact is not None:
        return compact
    for full_prefix, compact_prefix in _AF_COMPACT_EN_PREFIXES:
        if raw_text.startswith(full_prefix):
            return f"{compact_prefix}{raw_text[len(full_prefix):]}"
    return raw_text


def af_iface(text, *, compact=False):
    raw_text = str(text or "")
    if not raw_text:
        return raw_text
    localized = af_compact_label(raw_text) if compact else af_label(raw_text)
    if localized != raw_text:
        return localized
    return iface_(raw_text)


def af_status_label(identifier, fallback="-"):
    status_key = str(identifier or "").strip().upper()
    if not status_key:
        return str(fallback or "-")
    label = _STATUS_IDENTIFIER_LABELS.get(status_key, status_key)
    return af_iface(label)


__all__ = [
    "af_compact_label",
    "af_iface",
    "af_label",
    "af_status_label",
]
