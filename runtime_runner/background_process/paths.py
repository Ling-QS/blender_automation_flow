import os


def _automation_flow_package_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


__all__ = ["_automation_flow_package_dir"]
