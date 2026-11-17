# FnLockEC: toggle Lenovo Fn Lock via AcpiVpc.sys control device \\.\EnergyDrv
# IOCTL 0x831020E8 (METHOD_BUFFERED): 1-byte input.
#   input 0x02 -> driver evaluates ACPI HALS, returns 4-byte status DWORD (bit 10 = Fn Lock)
#   other byte -> driver evaluates ACPI SALS with that byte as command (0xE = lock on, 0xF = off)
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes, c_ubyte, byref

TASK_NAME = "FnLockEC_Hotkey"
BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE, "fnlock.json")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.DeviceIoControl.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPCVOID, wintypes.DWORD,
    wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3

IOCTL_VPC_EVAL = 0x831020E8
OP_HALS_READ = 0x02
SALS_FNLOCK_ON = 0x0E
SALS_FNLOCK_OFF = 0x0F
FNLOCK_BIT = 10


def open_device():
    h = kernel32.CreateFileW(
        "\\\\.\\EnergyDrv",
        GENERIC_READ | GENERIC_WRITE,
        0, None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE or h is None:
        raise OSError("CreateFile(\\\\.\\EnergyDrv) failed, winerr=%d" % ctypes.get_last_error())
    return h


def eval_byte(handle, op, out_len=16):
    inbuf = (c_ubyte * 1)(op)
    outbuf = (c_ubyte * out_len)()
    ret_len = wintypes.DWORD(0)
    ok = kernel32.DeviceIoControl(
        handle, wintypes.DWORD(IOCTL_VPC_EVAL),
        byref(inbuf), 1,
        outbuf, out_len,
        byref(ret_len), None)
    if not ok:
        raise OSError("DeviceIoControl(0x%08X op=0x%02X) failed, winerr=%d"
                      % (IOCTL_VPC_EVAL, op, ctypes.get_last_error()))
    return bytes(outbuf[:min(ret_len.value, out_len)])


def read_hals(handle):
    out = eval_byte(handle, OP_HALS_READ)
    hals = int.from_bytes(out[:4], "little")
    print("HALS = 0x%08X (fnlock bit10 = %d)" % (hals, (hals >> FNLOCK_BIT) & 1))
    return (hals >> FNLOCK_BIT) & 1


def write_sals(handle, cmd):
    eval_byte(handle, cmd)
    print("SALS cmd=0x%02X sent" % cmd)


def toggle():
    h = open_device()
    try:
        cur = (int.from_bytes(eval_byte(h, OP_HALS_READ)[:4], "little") >> FNLOCK_BIT) & 1
        write_sals(h, SALS_FNLOCK_ON if cur == 0 else SALS_FNLOCK_OFF)
        new = (int.from_bytes(eval_byte(h, OP_HALS_READ)[:4], "little") >> FNLOCK_BIT) & 1
        return new
    finally:
        kernel32.CloseHandle(h)


# ---------- global hotkey (opt-in) ----------
MOD_MAP = {"ctrl": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
VK_MAP = {  # keys that are not simple ASCII
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "esc": 0x1B, "space": 0x20, "tab": 0x09, "enter": 0x0D, "backspace": 0x08,
    "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdn": 0x22,
    "ins": 0x2D, "del": 0x2E, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
}
DEFAULT_HOTKEY = "ctrl+alt+f12"


def load_hotkey():
    """None = not set yet (no fnlock.json)."""
    try:
        return json.load(open(CFG_PATH, encoding="utf-8")).get("hotkey")
    except Exception:
        return None


def parse_hotkey(spec):
    """'ctrl+alt+f12' -> (mod_flags, vk). Raises ValueError on bad spec."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    mods, vk = 0, None
    for p in parts:
        if p in MOD_MAP:
            mods |= MOD_MAP[p]
        else:
            if vk is not None:
                raise ValueError("two non-modifier keys: %s" % spec)
            if len(p) == 1 and p in "abcdefghijklmnopqrstuvwxyz0123456789":
                vk = ord(p.upper())
            elif p in VK_MAP:
                vk = VK_MAP[p]
            else:
                raise ValueError("unknown key: %s" % p)
    if vk is None or mods == 0:
        raise ValueError("need 1+ modifiers and 1 normal key: %s" % spec)
    return mods, vk


def listen():
    """Resident global-hotkey listener; toggles Fn Lock on each press."""
    spec = load_hotkey()
    if not spec:
        print("hotkey not set; run hotkey-set first")
        return 1
    mods, vk = parse_hotkey(spec)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    # atom-based id so concurrent instances stay unique per key combo
    hid = mods | (vk << 16)
    if not u32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
        print("hotkey %s is taken by another app, listener exits" % spec)
        return 0
    msg = wintypes.MSG()
    print("FnLockEC hotkey listener running: %s" % spec)
    while u32.GetMessageW(byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            toggle()
    u32.UnregisterHotKey(None, hid)
    return 0


def _pyw():
    """pythonw.exe next to the running interpreter, if it exists."""
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return pyw if os.path.exists(pyw) else exe


def hotkey_install():
    """Register a logon scheduled task running the hidden listener."""
    spec = load_hotkey()
    if not spec:
        print("hotkey not set; run hotkey-set first (fnlock.bat [3])")
        return 1
    parse_hotkey(spec)  # fail fast on bad config
    tr = '"%s" "%s" listen' % (_pyw(), os.path.join(BASE, "FnLockEC.py"))
    r = subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME,
         "/tr", tr, "/sc", "onlogon", "/rl", "HIGHEST", "/f"],
        capture_output=True, text=True)
    ok = r.returncode == 0
    print(("installed: Fn Lock hotkey %s (task %s, logon, elevated)\n"
           "edit fnlock.json to change the key, then reinstall"
           % (spec, TASK_NAME)) if ok else "install failed:\n%s%s" % (r.stdout, r.stderr))
    return 0 if ok else 1


def hotkey_uninstall():
    r = subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
                       capture_output=True, text=True)
    ok = r.returncode == 0
    print(("uninstalled: listener task removed, nothing resident anymore")
          if ok else "not installed (or delete failed):\n%s%s" % (r.stdout, r.stderr))
    return 0 if ok else 1


VK_REV = {v: k for k, v in VK_MAP.items()}
VK_REV.update({i + 65: chr(ord("a") + i) for i in range(26)})
VK_REV.update({i + 48: str(i) for i in range(10)})
# modifier virtual keys (generic + left/right pairs)
VK_MOD = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C}


def vk_to_name(vk):
    if vk in VK_REV:
        return VK_REV[vk]
    if 0x70 <= vk <= 0x87:  # F1-F24
        return "f%d" % (vk - 0x6F)
    return None  # unmappable: reject


def hotkey_set():
    """Interactive: user presses the desired combo, it becomes the hotkey."""
    u32 = ctypes.WinDLL("user32")
    print("在 10 秒内按下你想要的组合键（需含 Ctrl/Alt/Shift/Win 至少一个修饰键）...")
    deadline = time.time() + 10
    spec = None
    while time.time() < deadline and spec is None:
        pressed = [vk for vk in range(0x08, 0x100)
                   if u32.GetAsyncKeyState(vk) & 0x8000]
        keys = [vk for vk in pressed if vk not in VK_MOD]
        if pressed and keys:
            vk = keys[0]
            name = vk_to_name(vk)
            if name is None:
                print("  不支持该键 (vk=0x%02X)，换一个组合" % vk)
                time.sleep(1)
                continue
            mods = 0
            if u32.GetKeyState(0x11) & 0x8000: mods |= MOD_MAP["ctrl"]
            if u32.GetKeyState(0x12) & 0x8000: mods |= MOD_MAP["alt"]
            if u32.GetKeyState(0x10) & 0x8000: mods |= MOD_MAP["shift"]
            if (u32.GetKeyState(0x5B) | u32.GetKeyState(0x5C)) & 0x8000:
                mods |= MOD_MAP["win"]
            if not mods:
                print("  需要至少一个 Ctrl/Alt/Shift/Win 修饰键，重按")
                time.sleep(1)
                continue
            parts = [m for m in ("ctrl", "alt", "shift", "win") if mods & MOD_MAP[m]]
            spec = "+".join(parts + [name])
        time.sleep(0.03)
    if spec is None:
        print("超时未捕捉到组合键，未修改。")
        return 1
    json.dump({"hotkey": spec}, open(CFG_PATH, "w", encoding="utf-8"))
    print("已保存热键: %s" % spec)
    if autostart_installed_query():
        print("监听已注册，正在用新热键重建...")
        return hotkey_install()
    print("（监听尚未注册，运行 hotkey-install 后生效）")
    return 0


def autostart_installed_query():
    return os.path.exists(os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                       "System32", "Tasks", TASK_NAME))


def hotkey_status():
    spec = load_hotkey()
    if autostart_installed_query():
        print("INSTALLED (key=%s)" % spec)
    else:
        print("NOT INSTALLED (key=%s)" % spec)


def hotkey_toggle():
    """Reverse-op: uninstall if installed; otherwise set key (if unset) and install."""
    if autostart_installed_query():
        return hotkey_uninstall()
    if not load_hotkey():
        if hotkey_set() != 0:
            return 1
    return hotkey_install()


def batstatus():
    """Two-line state for fnlock.bat header. No '|' or cmd metachars:
    lines are echoed unescaped by the bat."""
    h = open_device()
    try:
        cur = (int.from_bytes(eval_byte(h, OP_HALS_READ)[:4], "little") >> FNLOCK_BIT) & 1
    finally:
        kernel32.CloseHandle(h)
    print("on = F1-F12 作为标准功能键" if cur
          else "off = 多媒体键优先（按 Fn 才得到 F1-F12）")
    spec = load_hotkey()
    if not spec:
        print("未设快捷键")
    elif autostart_installed_query():
        print("已注册 %s" % spec)
    else:
        print("未注册 %s" % spec)


def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    if cmd == "listen":
        return listen()
    if cmd == "hotkey-install":
        return hotkey_install()
    if cmd == "hotkey-uninstall":
        return hotkey_uninstall()
    if cmd == "hotkey-status":
        hotkey_status()
        return 0
    if cmd == "hotkey-set":
        return hotkey_set()
    if cmd == "hotkey-toggle":
        return hotkey_toggle()
    if cmd == "batstatus":
        batstatus()
        return 0
    h = open_device()
    print("device \\\\.\\EnergyDrv opened")
    try:
        if cmd == "status":
            read_hals(h)
        elif cmd in ("on", "lock"):
            write_sals(h, SALS_FNLOCK_ON)
            read_hals(h)
        elif cmd in ("off", "unlock"):
            write_sals(h, SALS_FNLOCK_OFF)
            read_hals(h)
        elif cmd == "toggle":
            cur = read_hals(h)
            write_sals(h, SALS_FNLOCK_ON if cur == 0 else SALS_FNLOCK_OFF)
            read_hals(h)
        else:
            print("usage: FnLockEC.py [status|on|off|toggle|batstatus|listen|"
                  "hotkey-install|hotkey-uninstall|hotkey-status|hotkey-set]")
            return 1
    finally:
        kernel32.CloseHandle(h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
