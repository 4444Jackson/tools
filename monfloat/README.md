# MonFloat

TrafficMonitor 风格的轻量桌面悬浮窗：CPU 占用率+真实温度、GPU 占用率/温度、内存、网络上下行。单文件 Python 脚本（~450 行），`lib/` 内置 LibreHardwareMonitorLib 及其运行库，自包含可整体拷走。

## 数据来源（全部真实值，无估算）

| 行 | 指标 | 来源 |
|---|---|---|
| CPU | 占用率 | PDH `\Processor Information(_Total)\% Processor Utility`（与任务管理器同源，频率归一化；psutil 经典差分在降频 CPU 上会低估 3-4 倍） |
| CPU | 温度 | LibreHardwareMonitorLib（PawnIO 读 MSR，如 Core Average） |
| GPU | 占用率/温度 | LHM（AMD/NVIDIA/Intel 均支持；部分独显无温度传感器则显示 `--`，不造假） |
| 风扇 | 转速 | LHM（自动探测：机器上存在会转的风扇传感器才显示该行；本机 SuperIO 不解码联想 EC，无数据则整行隐藏） |
| 内存/网络 | 占用/速率 | psutil |

## 运行要求

- Windows 10/11，管理员权限（PawnIO 需要令牌，bat 会自动弹 UAC）
- Python 3.9+，装 `pythonnet` 和 `psutil`（`pip install pythonnet psutil`）
- **PawnIO 驱动已安装**（系统级驱动，装一次即可：<https://pawnio.ataman.dev/>）。本目录不包含驱动本体，只依赖它
- 双击 `monfloat.bat` 启动；bat 自动发现 PATH 里的 pythonw，找不到时回退到脚本内写死的路径（可按需修改）

## 交互

左键拖动 · 双击切置顶 · 右键菜单（刷新频率 0.5/1/2/5 秒、不透明度、字号、置顶、**开机自启**、深浅主题、重置位置、退出）。

**任务栏托盘图标（总开关）**：常驻通知区。左键单击 = 显示/隐藏浮窗（隐藏时停止全部轮询，零开销）；右键菜单 = 显示/隐藏浮窗、开机自启开关、退出。

## 开机自启（可选）

右键菜单勾选「开机自启」即注册一个登录触发的计划任务（管理员权限运行，读取传感器需要）；再点一次即删除任务。不想自启就什么都不用做，无任何后台残留。

## 已知实现要点（换机器调试时有用）

- 置顶：Windows「显示桌面」(Win+D) 会剥掉所有窗口的 TOPMOST 位，本程序每秒检测并经 .NET `TopMost` 属性 toggle 补回；窗口不可最小化（`MinimizeBox=False`），Win+D 本身会跳过它
- 原生 `ctypes` 直调 `SetWindowPos` 在部分环境（火绒/Hooks）恒返回 err=1400，因此置顶写操作走 .NET 属性路径而非裸 API
- `MinimizeBox=False` 是 Win+D 不隐藏的关键（Win+D 只最小化可最小化窗口，TrafficMonitor 同理）

## 免责声明

仅供学习与个人设备监控使用。作者不对使用本工具造成的任何问题负责。第三方组件（LibreHardwareMonitorLib 等）遵循其各自开源许可证。
