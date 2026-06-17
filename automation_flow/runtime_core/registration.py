import bpy


def safe_unregister_class(cls):
    candidates = []
    existing = getattr(bpy.types, cls.__name__, None)
    if existing is not None:
        candidates.append(existing)
    if cls not in candidates:
        candidates.append(cls)

    seen = set()
    for candidate in candidates:
        key = id(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            bpy.utils.unregister_class(candidate)
            return True
        except Exception:
            continue
    return False


def safe_register_class(cls):
    try:
        bpy.utils.register_class(cls)
        return cls
    except ValueError as exc:
        if "already registered" not in str(exc):
            raise
    safe_unregister_class(cls)
    bpy.utils.register_class(cls)
    return cls

