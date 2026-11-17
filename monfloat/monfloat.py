# MonFloat: lightweight TrafficMonitor-style desktop gadget (WinForms via pythonnet)
#   rows: CPU load+temp | GPU load+temp | RAM | net up/down
#   data: LibreHardwareMonitorLib.dll (real MSR/EC sensors via PawnIO) + psutil
import clr
import ctypes
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE, "monfloat.json")
DLL_DIR = os.path.join(BASE, "lib")  # self-contained: LibreHardwareMonitorLib + runtime dlls
TASK_NAME = "MonFloat"

clr.AddReference(os.path.join(DLL_DIR, "LibreHardwareMonitorLib.dll"))
from LibreHardwareMonitor.Hardware import Computer  # noqa: E402

clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
import System.Windows.Forms as Win  # noqa: E402
from System.Drawing import Color, Font, FontStyle, Point, SystemIcons  # noqa: E402

import psutil  # noqa: E402

DEFAULT_CFG = {
    "interval_ms": 1000,
    "alpha": 0.88,
    "font_size": 9,
    "x": 40, "y": 40,
    "topmost": True,
    "dark": True,
}
THEME = {
    True:  {"bg": (24, 24, 30), "fg": (225, 225, 232), "hot": (255, 120, 120)},
    False: {"bg": (246, 246, 248), "fg": (30, 30, 38), "hot": (192, 40, 56)},
}
FONT_NAME = "Microsoft YaHei UI"


def fmt_rate(v):
    v = float(v)
    for unit in ("B", "K", "M", "G"):
        if v < 1024:
            return ("%4.1f" % v if v < 100 else "%4.0f" % v) + unit
        v /= 1024.0
    return " ----"


def mark(text, on):
    return ("● " if on else "    ") + text


class _PdhValue(ctypes.Structure):
    _fields_ = [("CStatus", ctypes.c_uint32), ("pad", ctypes.c_uint32),
                ("doubleValue", ctypes.c_double)]


class PdhCpu:
    """CPU utilization matching Task Manager (frequency-normalized % Utility)."""

    PATH = u"\\Processor Information(_Total)\\% Processor Utility"
    PDH_FMT_DOUBLE = 0x00000200

    def __init__(self):
        self._pdh = ctypes.WinDLL("pdh")
        self.q = ctypes.c_void_p()
        self.c = ctypes.c_void_p()
        if self._pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.q)) != 0:
            raise OSError("PdhOpenQueryW failed")
        r = self._pdh.PdhAddEnglishCounterW(
            self.q, self.PATH, 0, ctypes.byref(self.c))
        if r != 0:
            self._pdh.PdhCloseQuery(self.q)
            raise OSError("PdhAddEnglishCounterW failed: %d" % r)
        self._pdh.PdhCollectQueryData(self.q)  # prime first sample

    def get(self):
        if self._pdh.PdhCollectQueryData(self.q) != 0:
            raise OSError("PdhCollectQueryData failed")
        v = _PdhValue()
        r = self._pdh.PdhGetFormattedCounterValue(
            self.c, self.PDH_FMT_DOUBLE, None, ctypes.byref(v))
        if r != 0 or v.CStatus != 0:
            raise OSError("PdhGetFormattedCounterValue failed: %d/%d"
                          % (r, v.CStatus))
        return min(v.doubleValue, 100.0)


HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_MINIMIZEBOX = 0x00020000
SW_SHOWNOACTIVATE = 4

# dedicated handles so get_last_error works (windll does not capture errors)
_u32 = ctypes.WinDLL("user32", use_last_error=True)


# ---------- autostart (opt-in via scheduled task) ----------
def autostart_installed():
    # task file check avoids spawning schtasks at menu build time
    return os.path.exists(os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                       "System32", "Tasks", TASK_NAME))


CREATE_NO_WINDOW = 0x08000000


def _is_admin():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def autostart_set(on):
    """Create or delete the logon task. Requires elevation (RL HIGHEST)."""
    if not _is_admin():
        raise OSError("当前进程没有管理员权限（schtasks /rl HIGHEST 必须提权）。"
                      "\n请用 monfloat.bat 重新启动（它会自动弹 UAC）。")
    if on:
        exe = sys.executable
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pyw):
            exe = pyw
        tr = '"%s" "%s"' % (exe, os.path.join(BASE, "monfloat.py"))
        r = subprocess.run(["schtasks", "/create", "/tn", TASK_NAME, "/tr", tr,
                            "/sc", "onlogon", "/rl", "HIGHEST", "/f"],
                           capture_output=True, text=True,
                           creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0 or not autostart_installed():
            raise OSError("schtasks create failed (rc=%s):\n%s%s"
                          % (r.returncode, r.stdout, r.stderr))
    else:
        subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
                       capture_output=True, text=True,
                       creationflags=CREATE_NO_WINDOW)


class MonFloat:
    def __init__(self):
        self.cfg = dict(DEFAULT_CFG)
        try:
            self.cfg.update(json.load(open(CFG_PATH, encoding="utf-8")))
        except Exception:
            pass
        self._save()

        self.comp = Computer()
        self.comp.IsCpuEnabled = True
        self.comp.IsGpuEnabled = True
        self.comp.IsMotherboardEnabled = True   # fans usually live here
        self.comp.IsSuperIOEnabled = True
        self.comp.IsMemoryEnabled = False
        self.comp.IsStorageEnabled = False
        self.comp.IsNetworkEnabled = False
        self.comp.IsControllerEnabled = False
        self.comp.IsPsuEnabled = False
        self.comp.Open()
        self.sensors = self._index_sensors()
        self.fans = self._index_fans()
        self._fan_shown = False

        self._net = psutil.net_io_counters()
        self._net_t = time.time()
        psutil.cpu_percent(interval=None)  # prime first diff
        self._tick_cnt = 0
        try:
            self._pdh_cpu = PdhCpu()
        except Exception:
            self._pdh_cpu = None  # fall back to psutil classic diff

        self._build_form()

    # ---------- hardware ----------
    def _index_sensors(self):
        idx = {}
        for hw in self.comp.Hardware:
            hw.Update()
            htype = str(hw.HardwareType)
            for s in hw.Sensors:
                stype = str(s.SensorType)
                name = s.Name
                if htype == "Cpu":
                    if name == "Core Average" and stype == "Temperature":
                        idx["cpu_temp"] = s
                if htype in ("GpuAmd", "GpuNvidia", "GpuIntel"):
                    if stype == "Temperature" and "GPU Core" in name:
                        idx.setdefault("gpu_temp", s)
                    if stype == "Load" and name in ("GPU Core", "D3D 3D"):
                        idx.setdefault("gpu_load_" + htype, s)
        return idx

    def _index_fans(self):
        """Fan (RPM) sensors. Some GPUs expose a bogus always-0 sensor on
        fanless cards, so a row is only shown once a sensor reads > 1 RPM."""
        fans = []
        for hw in self.comp.Hardware:
            hw.Update()
            for s in hw.Sensors:
                if str(s.SensorType) == "Fan":
                    fans.append(s)
        return fans

    # ---------- UI ----------
    def _col(self, key):
        rgb = THEME[self.cfg["dark"]][key]
        return Color.FromArgb(rgb[0], rgb[1], rgb[2])

    def _build_form(self):
        self.form = Win.Form()
        f = self.form
        f.FormBorderStyle = getattr(Win.FormBorderStyle, "None")
        # not minimizable => Win+D "show desktop" skips this window
        # (this is how TrafficMonitor survives Win+D without any message handling)
        f.MinimizeBox = False
        f.MaximizeBox = False
        f.TopMost = self.cfg["topmost"]
        f.Opacity = self.cfg["alpha"]
        f.StartPosition = Win.FormStartPosition.Manual
        f.Location = Point(self.cfg["x"], self.cfg["y"])
        f.BackColor = self._col("bg")
        f.ShowInTaskbar = False
        f.Text = "MonFloat"
        f.AutoSize = True
        f.AutoSizeMode = Win.AutoSizeMode.GrowAndShrink
        f.Padding = Win.Padding(0)

        fs = self.cfg["font_size"]
        self.font_n = Font(FONT_NAME, fs)

        self.panel = Win.FlowLayoutPanel()
        self.panel.FlowDirection = Win.FlowDirection.TopDown
        self.panel.WrapContents = False
        self.panel.AutoSize = True
        self.panel.AutoSizeMode = Win.AutoSizeMode.GrowAndShrink
        self.panel.BackColor = self._col("bg")
        self.panel.Padding = Win.Padding(2)
        self.panel.Margin = Win.Padding(0)
        f.Controls.Add(self.panel)

        self.rows = {}
        for key, text in (("cpu", "CPU"), ("gpu", "GPU"), ("fan", "风扇"),
                          ("mem", "内存"), ("net", "网络")):
            lab = Win.Label()
            lab.Text = text
            lab.AutoSize = True
            lab.Font = self.font_n
            lab.ForeColor = self._col("hot") if key == "cpu" else self._col("fg")
            lab.BackColor = self._col("bg")
            lab.Margin = Win.Padding(0)
            lab.Padding = Win.Padding(0)
            lab.Visible = key != "fan"  # fan row appears only when data exists
            self.panel.Controls.Add(lab)
            self.rows[key] = lab

        # events
        f.MouseDown += self._drag_start
        f.MouseMove += self._drag_move
        f.MouseUp += self._drag_end
        f.MouseClick += self._click_route
        self.panel.MouseDown += self._drag_start
        self.panel.MouseMove += self._drag_move
        self.panel.MouseUp += self._drag_end
        self.panel.MouseClick += self._click_route
        for lab in self.rows.values():
            lab.MouseDown += self._drag_start
            lab.MouseMove += self._drag_move
            lab.MouseUp += self._drag_end
            lab.MouseClick += self._click_route
        f.Shown += self._on_shown
        f.FormClosing += self._on_close

        # tray icon: master switch (show/hide window, autostart, exit)
        self.tray = Win.NotifyIcon()
        self.tray.Icon = SystemIcons.Information
        self.tray.Text = "MonFloat"
        self.tray.Visible = True
        self.tray.MouseClick += self._tray_click  # builds fresh menu per click

        self.timer = Win.Timer()
        self.timer.Interval = self.cfg["interval_ms"]
        self.timer.Tick += self._tick

    def _apply_theme(self):
        self.form.BackColor = self._col("bg")
        self.panel.BackColor = self._col("bg")
        for key, lab in self.rows.items():
            lab.BackColor = self._col("bg")
            lab.ForeColor = self._col("hot") if key == "cpu" else self._col("fg")

    def _apply_font(self):
        self.font_n = Font(FONT_NAME, self.cfg["font_size"])
        for lab in self.rows.values():
            lab.Font = self.font_n

    # ---------- interaction ----------
    def _click_route(self, sender, e):
        if e.Button == Win.MouseButtons.Right:
            self._menu()

    def _drag_start(self, sender, e):
        if e.Button == Win.MouseButtons.Left:
            self._dx = Win.Cursor.Position.X - self.form.Location.X
            self._dy = Win.Cursor.Position.Y - self.form.Location.Y

    def _drag_move(self, sender, e):
        if e.Button == Win.MouseButtons.Left and hasattr(self, "_dx"):
            self.form.Location = Point(Win.Cursor.Position.X - self._dx,
                                       Win.Cursor.Position.Y - self._dy)

    def _drag_end(self, sender, e):
        if e.Button == Win.MouseButtons.Left and hasattr(self, "_dx"):
            self.cfg["x"] = self.form.Location.X
            self.cfg["y"] = self.form.Location.Y
            self._save()

    # ---------- menu ----------
    def _build_menu(self, tray=False):
        m = Win.ContextMenuStrip()

        sub_i = Win.ToolStripMenuItem("刷新频率")
        for ms, lbl in ((500, "0.5 秒"), (1000, "1 秒"), (2000, "2 秒"), (5000, "5 秒")):
            item = Win.ToolStripMenuItem(mark(lbl, self.cfg["interval_ms"] == ms))
            item.Click += self._mk_set("interval_ms", ms)
            sub_i.DropDownItems.Add(item)
        m.Items.Add(sub_i)

        sub_a = Win.ToolStripMenuItem("不透明度")
        for a in (1.0, 0.88, 0.7, 0.5):
            item = Win.ToolStripMenuItem(mark("%d%%" % int(a * 100), abs(self.cfg["alpha"] - a) < 0.01))
            item.Click += self._mk_alpha(a)
            sub_a.DropDownItems.Add(item)
        m.Items.Add(sub_a)

        sub_f = Win.ToolStripMenuItem("字体大小")
        for fs in (8, 9, 10, 12):
            item = Win.ToolStripMenuItem(mark(str(fs), self.cfg["font_size"] == fs))
            item.Click += self._mk_font(fs)
            sub_f.DropDownItems.Add(item)
        m.Items.Add(sub_f)

        m.Items.Add(Win.ToolStripSeparator())
        top = Win.ToolStripMenuItem(mark("窗口置顶", self.cfg["topmost"]))
        top.Click += self._top_fn
        m.Items.Add(top)
        auto = Win.ToolStripMenuItem(mark("开机自启", autostart_installed()))
        auto.Click += self._autostart_fn
        m.Items.Add(auto)
        theme = Win.ToolStripMenuItem("切换深浅主题")
        theme.Click += self._theme_fn
        m.Items.Add(theme)
        reset = Win.ToolStripMenuItem("重置位置")
        reset.Click += self._reset_fn
        m.Items.Add(reset)

        m.Items.Add(Win.ToolStripSeparator())
        if tray:  # master switch: show/hide the floating window
            vis = Win.ToolStripMenuItem("隐藏浮窗" if self.form.Visible else "显示浮窗")
            vis.Click += self._vis_fn
            m.Items.Add(vis)
        quit_ = Win.ToolStripMenuItem("退出")
        quit_.Click += self._quit_fn
        m.Items.Add(quit_)
        return m

    def _menu(self):
        self._build_menu(tray=False).Show(Win.Cursor.Position)

    # ---------- menu handlers ----------
    def _mk_set(self, key, value):
        def fn(sender, e):
            self.cfg[key] = value
            self._save()
        return fn

    def _mk_alpha(self, v):
        def fn(sender, e):
            self.cfg["alpha"] = v
            self.form.Opacity = v
            self._save()
        return fn

    def _mk_font(self, v):
        def fn(sender, e):
            self.cfg["font_size"] = v
            self._apply_font()
            self._save()
        return fn

    def _top_fn(self, sender, e):
        self.cfg["topmost"] = not self.cfg["topmost"]
        self.form.TopMost = self.cfg["topmost"]
        self._save()

    def _theme_fn(self, sender, e):
        self.cfg["dark"] = not self.cfg["dark"]
        self._apply_theme()
        self._save()

    def _reset_fn(self, sender, e):
        self.form.Location = Point(40, 40)
        self.cfg["x"], self.cfg["y"] = 40, 40
        self._save()

    def _autostart_fn(self, sender, e):
        try:
            on = not autostart_installed()
            autostart_set(on)
            self.tray.BalloonTipTitle = "MonFloat"
            self.tray.BalloonTipText = "开机自启已开启" if on else "开机自启已关闭"
            self.tray.ShowBalloonTip(2000)
        except OSError as ex:
            ctypes.windll.user32.MessageBoxW(
                0, str(ex), "MonFloat 开机自启设置失败", 0x10)

    def _vis_fn(self, sender, e):
        self.form.Visible = not self.form.Visible
        if self.form.Visible:
            self.timer.Start()  # refresh timer also drives topmost re-assert
        else:
            self.timer.Stop()   # hidden: zero polling overhead

    def _tray_click(self, sender, e):
        if e.Button == Win.MouseButtons.Left:  # single left click toggles
            self._vis_fn(sender, e)
        elif e.Button == Win.MouseButtons.Right:
            # rebuild every time so toggle marks (置顶/自启) always current
            self._build_menu(tray=True).Show(Win.Cursor.Position)

    def _quit_fn(self, sender, e):
        self.tray.Visible = False
        self.tray.Dispose()
        self.form.Close()

    def _on_shown(self, sender, e):
        # WS_EX_TOOLWINDOW (Alt-Tab hidden) comes from ShowInTaskbar=False;
        # non-minimizable (Win+D skip) comes from MinimizeBox=False.
        self.timer.Start()

    def _on_close(self, sender, e):
        self.timer.Stop()
        try:
            self.comp.Close()
        finally:
            self._save()

    # ---------- data loop ----------
    def _tick(self, sender, e):
        try:
            self._tick_cnt += 1
            if self.cfg["topmost"]:
                self._reassert_topmost()

            for hw in self.comp.Hardware:
                hw.Update()

            cpu_t = self.sensors["cpu_temp"].Value if "cpu_temp" in self.sensors else None

            cpu_l = None
            if self._pdh_cpu is not None:
                try:
                    cpu_l = self._pdh_cpu.get()
                except Exception:
                    cpu_l = None
            if cpu_l is None:
                cpu_l = psutil.cpu_percent(interval=None)

            gpu_loads = [s.Value for k, s in self.sensors.items()
                         if k.startswith("gpu_load") and s.Value is not None]
            gpu_t = None
            if "gpu_temp" in self.sensors:
                v = self.sensors["gpu_temp"].Value
                if v is not None and v > 1:
                    gpu_t = v

            self.rows["cpu"].Text = ("CPU  %3.0f%%  %5.1f°C" % (cpu_l, cpu_t)
                                     if cpu_t is not None else "CPU  %3.0f%%   --" % cpu_l)

            if gpu_loads:
                self.rows["gpu"].Text = "GPU  %3.0f%%  %s" % (
                    max(gpu_loads), ("%4.1f°C" % gpu_t) if gpu_t is not None else "--")
            else:
                self.rows["gpu"].Text = "GPU   --   --"

            mem = psutil.virtual_memory()
            self.rows["mem"].Text = "内存  %3.0f%%  %4.1fG" % (mem.percent, mem.used / (1024 ** 3))

            rpm = 0
            for s in self.fans:
                v = s.Value
                if v is not None and v > rpm:
                    rpm = v
            if rpm > 1:
                self._fan_shown = True
                self.rows["fan"].Visible = True
                self.rows["fan"].Text = "风扇  %4.0f RPM" % rpm
            elif not self._fan_shown:
                self.rows["fan"].Visible = False
            else:  # was shown before: keep the row, 0 RPM is real (fan stopped)
                self.rows["fan"].Text = "风扇  %4.0f RPM" % rpm

            now = psutil.net_io_counters()
            dt = time.time() - self._net_t
            if dt > 0.2:
                up = (now.bytes_sent - self._net.bytes_sent) / dt
                down = (now.bytes_recv - self._net.bytes_recv) / dt
                self._net, self._net_t = now, time.time()
                self.rows["net"].Text = "网络 ↑%s ↓%s" % (fmt_rate(up), fmt_rate(down))
        except Exception:
            pass

    def _reassert_topmost(self):
        """Re-apply topmost when something stripped it (Win+D removes
        WS_EX_TOPMOST from every window). Raw ctypes SetWindowPos is broken
        in this environment (err 1400 even on valid handles), so the actual
        call goes through the .NET TopMost property toggle, which works."""
        hwnd = self.form.Handle.ToInt64()
        if _u32.IsIconic(hwnd):  # Win+D hit us despite everything: restore
            _u32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        ex = _u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if not ex & WS_EX_TOPMOST:
            self.form.TopMost = False
            self.form.TopMost = True
            ex = _u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if self._tick_cnt <= 10:
            line = ("tick %d ex=0x%X topmost=%s\n"
                    % (self._tick_cnt, ex, bool(ex & WS_EX_TOPMOST)))
            with open(os.path.join(os.path.dirname(CFG_PATH),
                                   "topmost_debug.log"), "a",
                      encoding="utf-8") as fh:
                fh.write(line)

    def _save(self):
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=1)

    def run(self):
        Win.Application.Run(self.form)


if __name__ == "__main__":
    try:
        app = MonFloat()
        app.run()
    except Exception as ex:
        # pythonw has no console: surface the error in a message box
        import traceback
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "MonFloat 启动失败:\n\n%s\n\n%s" % (ex, traceback.format_exc()[-800:]),
            "MonFloat 错误", 0x10)
