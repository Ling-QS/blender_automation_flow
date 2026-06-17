from pathlib import Path

import bpy

GROUP_ASSET_TASK_ISOLATION = "TASK_ISOLATION"
GROUP_ASSET_BLEND_FILENAME = "group_assets.blend"
GROUP_ASSET_TREE_NAME_TASK_ISOLATION = "任务隔离"


def _addon_assets_dir():
    return Path(__file__).resolve().parent.parent / "assets"


def _group_asset_blend_path():
    return _addon_assets_dir() / GROUP_ASSET_BLEND_FILENAME


def _group_asset_tree_name(asset_id):
    if str(asset_id or "") == GROUP_ASSET_TASK_ISOLATION:
        return GROUP_ASSET_TREE_NAME_TASK_ISOLATION
    return ""


def _append_group_asset_tree(blend_path, tree_name):
    if not blend_path.exists():
        return None
    try:
        with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
            if tree_name not in data_from.node_groups:
                return None
            data_to.node_groups = [tree_name]
    except Exception:
        return None

    for node_tree in reversed(list(getattr(bpy.data, "node_groups", []))):
        if getattr(node_tree, "name", "") == tree_name and getattr(node_tree, "bl_idname", "") == "AFNodeTreeType":
            node_tree.use_fake_user = True
            return node_tree
    return None


def _ensure_group_asset_tree(asset_id):
    tree_name = _group_asset_tree_name(asset_id)
    if not tree_name:
        return None
    existing = bpy.data.node_groups.get(tree_name)
    if existing is not None and getattr(existing, "bl_idname", "") == "AFNodeTreeType":
        return existing
    return _append_group_asset_tree(_group_asset_blend_path(), tree_name)
