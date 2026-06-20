_ACTIVE_RUNNER = None


def get_active_runner():
    return _ACTIVE_RUNNER


def set_active_runner(runner):
    global _ACTIVE_RUNNER
    _ACTIVE_RUNNER = runner

