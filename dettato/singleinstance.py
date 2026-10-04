import ctypes
import time
from ctypes import wintypes

_MUTEX_NAME = "Dettato_SingleInstance_Mutex"
_EXIT_EVENT_NAME = "Dettato_Exit_Event"
_SHOW_EVENT_NAME = "Dettato_Show_Event"
_ERROR_ALREADY_EXISTS = 183
_EVENT_MODIFY_STATE = 0x0002
_INFINITE = 0xFFFFFFFF
_ASFW_ANY = 0xFFFFFFFF

_kernel32 = ctypes.windll.kernel32
_user32 = ctypes.windll.user32
_user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
_user32.AllowSetForegroundWindow.restype = wintypes.BOOL
_kernel32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.OpenEventW.restype = wintypes.HANDLE
_kernel32.SetEvent.argtypes = [wintypes.HANDLE]
_kernel32.SetEvent.restype = wintypes.BOOL
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


def acquire_single_instance_lock() -> bool:
    """Claim a named mutex; returns False if another instance already holds it.

    Without this, launching the app twice (e.g. the Start Menu shortcut
    plus a leftover manual/legacy launch) registers the same global
    hotkey twice, so one keypress starts/stops two independent
    recordings fighting over the same microphone. The handle is
    intentionally never closed: it must live for the whole process
    lifetime, and Windows releases it automatically on exit.
    """
    handle = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if ctypes.GetLastError() == _ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return False
    return True


def acquire_single_instance_lock_waiting(timeout: float) -> bool:
    """Like acquire_single_instance_lock, retrying while a previous
    instance finishes shutting down (used by "Riavvia")."""
    deadline = time.monotonic() + timeout
    while True:
        if acquire_single_instance_lock():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.25)


def create_exit_event() -> int:
    """Create the named event a separate `--stop` invocation can signal."""
    return _kernel32.CreateEventW(None, True, False, _EXIT_EVENT_NAME)


def create_show_event() -> int:
    """Create the auto-reset event a second launch signals to bring up
    the running instance's window instead of starting a duplicate."""
    return _kernel32.CreateEventW(None, False, False, _SHOW_EVENT_NAME)


def wait_for_event(handle: int) -> None:
    """Block until an event from create_*_event() is signalled."""
    _kernel32.WaitForSingleObject(handle, _INFINITE)


def signal_exit_event() -> bool:
    """Ask a running instance to exit. Returns False if none is running."""
    return _signal(_EXIT_EVENT_NAME)


def signal_show_event() -> bool:
    """Ask a running instance to show its window. False if none is running.

    This process was just launched by the user (icon click), so Windows
    lets it take the foreground; hand that right to the running instance,
    otherwise its window would open behind whatever has focus.
    """
    _user32.AllowSetForegroundWindow(_ASFW_ANY)
    return _signal(_SHOW_EVENT_NAME)


def _signal(name: str) -> bool:
    handle = _kernel32.OpenEventW(_EVENT_MODIFY_STATE, False, name)
    if not handle:
        return False
    try:
        _kernel32.SetEvent(handle)
    finally:
        _kernel32.CloseHandle(handle)
    return True
