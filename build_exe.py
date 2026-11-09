import pythonnet
import sys
import os
import threading
import time
import base64  # 🚀 新增：用于解码前端传来的 Excel 二进制数据
import struct
import math
import json
import subprocess
import shutil
import tempfile
import webbrowser
from urllib.parse import unquote_to_bytes
from update_service import UpdateManager

# ---------------------------------------------------------------- 启动环境

APP_NAME = 'Perovskite Engine'
APP_DIR = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'PerovskiteEngine')
LOG_DIR = os.path.join(APP_DIR, 'logs')
STARTUP_LOG = os.environ.get('PEROVSKITE_STARTUP_TRACE') or os.path.join(LOG_DIR, 'startup.log')
RUNTIME_CACHE = os.path.join(APP_DIR, 'dotnet-runtime.txt')

# netfx 优先：Windows 10/11 自带 .NET Framework 4.8，不依赖 hostfxr，
# 在实验室电脑上比 coreclr 更稳，启动路径也更短。
DOTNET_RUNTIMES = ('netfx', 'coreclr')

window = None
_log_prepared = False


def log_startup(stage, detail=''):
    """把启动过程写入日志文件；任何失败都不影响启动。"""
    global _log_prepared
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if not _log_prepared:
            _log_prepared = True
            if os.path.exists(STARTUP_LOG) and os.path.getsize(STARTUP_LOG) > 256 * 1024:
                os.replace(STARTUP_LOG, STARTUP_LOG + '.1')
        try:
            import psutil
            elapsed = time.time() - psutil.Process().create_time()
        except Exception:
            elapsed = time.perf_counter()
        line = f'{elapsed:8.3f}s  {stage}'
        if detail:
            line += f'  |  {detail}'
        with open(STARTUP_LOG, 'a', encoding='utf-8') as startup_log:
            startup_log.write(line + '\n')
    except OSError:
        pass


def _runtime_preference():
    """优先尝试的 .NET 运行时：环境变量 > 上次成功记录 > 默认 netfx。"""
    requested = (os.environ.get('PEROVSKITE_DOTNET_RUNTIME') or '').strip().lower()
    if requested in DOTNET_RUNTIMES:
        return requested, '环境变量'
    try:
        with open(RUNTIME_CACHE, 'r', encoding='utf-8') as cache_file:
            cached = cache_file.read().strip().lower()
        if cached in DOTNET_RUNTIMES:
            return cached, '上次成功记录'
    except OSError:
        pass
    return DOTNET_RUNTIMES[0], '默认'


def _remember_runtime(runtime):
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(RUNTIME_CACHE, 'w', encoding='utf-8') as cache_file:
            cache_file.write(runtime)
    except OSError:
        pass


def _activate_dotnet_runtime():
    """在导入 clr / pywebview 之前确定并启动 .NET 运行时。

    运行时只在 pythonnet.load() 这一层选定；绝不在 CLR 半初始化后再切换。
    """
    preferred, source = _runtime_preference()
    attempts = [preferred] + [runtime for runtime in DOTNET_RUNTIMES if runtime != preferred]
    log_startup('选择 .NET 运行时', '首选 {0}（{1}），尝试顺序 {2}'.format(preferred, source, attempts))
    failures = []
    for runtime in attempts:
        try:
            pythonnet.load(runtime)
            _remember_runtime(runtime)
            log_startup('.NET 运行时已启动', runtime)
            return runtime
        except Exception as error:  # noqa: BLE001
            failures.append('{0}: {1}: {2}'.format(runtime, type(error).__name__, error))
            log_startup('.NET 运行时启动失败', failures[-1])
    raise RuntimeError('；'.join(failures))


def check_webview2_runtime():
    """检测已安装的 WebView2 运行时版本，未安装返回 None。"""
    try:
        import winreg
    except ImportError:
        return None
    client = r'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root, client) as key:
                version, _ = winreg.QueryValueEx(key, 'pv')
            if version and version != '0.0.0.0':
                return str(version)
        except OSError:
            continue
    return None


def window_geometry():
    """窗口尺寸用逻辑像素（1366×768），由 Windows 按系统缩放放大。

    注意：不要在这里手动乘以缩放比例。实测（125% 缩放，WebView2 156）把进程声明为
    DPI 感知再放大窗口后，WebView2 会把物理像素当成 DIP 又放大一次，右侧工具栏反而
    被裁掉。保持 DPI 不感知、窗口逻辑尺寸固定，才是当前 pywebview 下正确的组合。
    """
    return 1366, 768


def show_startup_error(message):
    """启动失败时弹中文说明；此时 GUI 框架可能不可用，直接用系统消息框。"""
    log_startup('启动失败', message.replace('\n', ' | '))
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME + ' 启动失败', 0x10)
    except Exception:
        pass


_DOTNET_RUNTIME = None
_DOTNET_ERROR = None
try:
    _DOTNET_RUNTIME = _activate_dotnet_runtime()
    import webview  # noqa: E402  运行时选定后才导入；导入即初始化 WinForms / WebView2
except Exception as _startup_error:  # noqa: BLE001
    webview = None
    _DOTNET_ERROR = _startup_error

# 注意：这里不要导入 trpl_fit / ups_fit，否则每次启动都会连带加载 NumPy、SciPy。
# 拟合用的库改为在 BackendAPI.fit_*_python 里按需导入。


def unique_path(path):
    stem, extension = os.path.splitext(path)
    candidate = path
    suffix = 1
    while os.path.exists(candidate):
        candidate = f"{stem} ({suffix}){extension}"
        suffix += 1
    return candidate


def write_failure_report(output_dir, failures):
    if not failures:
        return None
    report_path = unique_path(os.path.join(output_dir, 'BIN转换失败记录.txt'))
    with open(report_path, 'w', encoding='utf-8-sig') as report_file:
        report_file.write(f'失败文件数: {len(failures)}\n\n')
        report_file.write('\n'.join(failures))
    return report_path


def read_chi_lsv(source_path):
    with open(source_path, 'rb') as source_file:
        payload = source_file.read()
    if len(payload) < 1457 or payload[8:11] != b'LSV':
        raise ValueError('不是受支持的 CHI LSV 文件')
    start, target, step = (struct.unpack_from('<f', payload, offset)[0] for offset in (853, 857, 885))
    step = abs(step)
    if not step:
        raise ValueError('扫描步长无效')
    points = round(abs(start - target) / step)
    data_offset = len(payload) - points * 4
    if points <= 0 or data_offset != 1453:
        raise ValueError('CHI LSV 数据区结构不匹配')
    direction = 1 if target >= start else -1
    current = [value[0] for value in struct.iter_unpack('<f', payload[data_offset:])]
    voltage = [start + direction * step * index for index in range(points)]
    return {"voltage": voltage, "current": current, "start": start, "end": voltage[-1], "step": direction * step}


def convert_chi_bin_file(source_path, output_path):
    data = read_chi_lsv(source_path)
    decimals = max(0, int(-math.floor(math.log10(abs(data['step'])))))
    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write(f"Source: {source_path}\n")
        output_file.write('Technique: Linear Sweep Voltammetry (LSV)\n')
        output_file.write(f"Points: {len(data['voltage'])}\n")
        output_file.write(f"Potential start (V): {data['start']:.{decimals}f}\n")
        output_file.write(f"Potential end (V): {data['end']:.{decimals}f}\n")
        output_file.write(f"Potential step (V): {data['step']:.{decimals}f}\n\n")
        output_file.write('Potential (V)\tCurrent (A)\n')
        for voltage, current in zip(data['voltage'], data['current']):
            output_file.write(f'{voltage:.{decimals}f}\t{current:.9e}\n')
    return True

def get_resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def get_app_path(filename):
    """Locate files installed beside the main executable."""
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


def mark_update_healthy():
    marker = os.path.join(APP_DIR, 'update-pending.json')
    try:
        if os.path.isfile(marker):
            with open(marker, 'r', encoding='utf-8') as marker_file:
                payload = json.load(marker_file)
            payload['status'] = 'healthy'
            payload['pid'] = os.getpid()
            with open(marker, 'w', encoding='utf-8') as marker_file:
                json.dump(payload, marker_file, ensure_ascii=False)
    except (OSError, ValueError):
        pass

def trace_startup(stage, detail=''):
    """兼容旧调用：启动追踪统一写入启动日志。"""
    log_startup(stage, detail)


def close_splash():
    time.sleep(0.5)
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

class BackendAPI:
    def __init__(self):
        self._rename_plan = []
        self._last_rename = []
        self._updates = UpdateManager()

    def ui_ready(self, frontend_ms=None):
        """前端脚本执行完毕时回调，仅在开启启动追踪时写日志。"""
        trace_startup(f'ui ready (frontend {frontend_ms} ms)')
        return True

    def open_feedback_email(self, subject='', body=''):
        """打开默认邮件客户端，避免在软件中保存邮箱凭据。"""
        from urllib.parse import quote

        recipient = 'zhao78574@163.com'
        mailto = 'mailto:{0}?subject={1}&body={2}'.format(
            recipient, quote(str(subject)), quote(str(body))
        )
        try:
            if sys.platform == 'win32':
                subprocess.run(
                    ['clip'],
                    input=f'{subject}\n\n{body}',
                    text=True,
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return {
                    'status': 'manual',
                    'message': f'反馈模板已复制，请粘贴到邮件中发送至 {recipient}。',
                }
            else:
                webbrowser.open(mailto)
            return {'status': 'success'}
        except Exception as error:  # noqa: BLE001
            return {'status': 'error', 'message': str(error)}

    def check_update_python(self, current_version):
        self._updates.check_async(str(current_version))
        return {"status": "started"}

    def update_status_python(self):
        return self._updates.state()

    def download_update_python(self):
        self._updates.download_async()
        return {"status": "started"}

    def launch_update_python(self, has_unsaved=False, task_running=False):
        if has_unsaved or task_running:
            return {"status": "blocked", "message": "请先导出结果并等待科研任务完成。"}
        state = self._updates.state()
        installer = state.get("installer")
        if state.get("status") != "ready" or not installer or not os.path.isfile(installer):
            return {"status": "error", "message": "更新包尚未完成验证。"}
        updater = get_app_path('Updater.exe')
        if not os.path.isfile(updater):
            return {"status": "error", "message": "缺少 Updater.exe，请重新安装软件。"}
        try:
            release = state.get('release') or {}
            os.makedirs(APP_DIR, exist_ok=True)
            marker = os.path.join(APP_DIR, 'update-pending.json')
            with open(marker, 'w', encoding='utf-8') as marker_file:
                json.dump({'status': 'pending', 'version': release.get('version')}, marker_file)
            with tempfile.NamedTemporaryFile(prefix='PerovskiteEngine-Updater-', suffix='.exe', delete=False) as updater_file:
                updater_copy = updater_file.name
            shutil.copy2(updater, updater_copy)
            subprocess.Popen([
                updater_copy, installer, '--pid', str(os.getpid()),
                '--sha256', str(release.get('sha256', '')),
                '--publisher', str(release.get('publisher', '')),
                '--certificate-sha256', str(release.get('certificate_sha256', '')),
                '--health-marker', marker,
            ], close_fds=True)
        except OSError as error:
            return {"status": "error", "message": f"无法启动更新程序：{error}"}
        return {"status": "success"}

    def fit_trpl_python(self, x_values, y_values, model="expdec2"):
        try:
            from trpl_fit import fit_trpl  # 第一次拟合时才加载 NumPy / SciPy
            return {"status": "success", "result": fit_trpl(x_values, y_values, model)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def fit_ups_python(self, cutoff_x, cutoff_y, onset_x, onset_y, cutoff_window=None, onset_window=None, smooth_window=None, smooth_order=None):
        try:
            from ups_fit import fit_ups_sample  # 第一次拟合时才加载 NumPy / SciPy
            options = {}
            if smooth_window is not None:
                options['smooth_window'] = int(smooth_window)  # 0 表示关闭平滑
            if smooth_order is not None:
                options['smooth_order'] = int(smooth_order)
            result = fit_ups_sample(cutoff_x, cutoff_y, onset_x, onset_y, cutoff_window, onset_window, **options)
            return {"status": "success", "result": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def preview_rename_python(self, rename_type, prefix):
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return {"status": "cancelled"}
        folder_path = result[0]
        try:
            operations = []
            if rename_type == "1":
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        operations.append((file_path, os.path.join(folder_path, prefix + filename)))
            elif rename_type == "2":
                for item in os.listdir(folder_path):
                    sub_path = os.path.join(folder_path, item)
                    if os.path.isdir(sub_path):
                        for filename in os.listdir(sub_path):
                            file_path = os.path.join(sub_path, filename)
                            if os.path.isfile(file_path):
                                operations.append((file_path, os.path.join(sub_path, item + "-" + filename)))
            else:
                return {"status": "error", "message": "未知的重命名方式"}

            targets = [target for _, target in operations]
            duplicate_targets = {target for target in targets if targets.count(target) > 1}
            conflicts = [target for target in targets if os.path.exists(target) or target in duplicate_targets]
            self._rename_plan = [] if conflicts else operations
            return {
                "status": "success",
                "folder": folder_path,
                "operations": [{"old": os.path.basename(source), "new": os.path.basename(target)} for source, target in operations],
                "conflicts": [os.path.basename(path) for path in dict.fromkeys(conflicts)],
            }
        except Exception as e:
            self._rename_plan = []
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _apply_rename_operations(operations):
        completed = []
        try:
            for source, target in operations:
                if not os.path.isfile(source):
                    raise FileNotFoundError(f"源文件不存在：{source}")
                if os.path.exists(target):
                    raise FileExistsError(f"目标文件已存在：{target}")
                os.rename(source, target)
                completed.append((source, target))
        except Exception:
            for source, target in reversed(completed):
                if os.path.exists(target) and not os.path.exists(source):
                    os.rename(target, source)
            raise
        return completed

    def execute_rename_python(self):
        if not self._rename_plan:
            return {"status": "error", "message": "没有可执行的重命名预览，请重新选择文件夹"}
        try:
            completed = self._apply_rename_operations(self._rename_plan)
            self._last_rename = completed
            self._rename_plan = []
            return {"status": "success", "count": len(completed)}
        except Exception as e:
            self._rename_plan = []
            return {"status": "error", "message": str(e)}

    def undo_rename_python(self):
        if not self._last_rename:
            return {"status": "error", "message": "没有可撤销的重命名操作"}
        reverse_operations = [(target, source) for source, target in reversed(self._last_rename)]
        try:
            completed = self._apply_rename_operations(reverse_operations)
            self._last_rename = []
            return {"status": "success", "count": len(completed)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # 🚀 核心新增：调用原生“另存为”保存 Excel
    def save_excel_python(self, default_name, base64_data):
        result = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=default_name,
            file_types=('Excel Files (*.xlsx)', 'All files (*.*)')
        )
        if result:
            try:
                # 把前端传来的 base64 数据解码成二进制并写入文件
                with open(result[0], 'wb') as f:
                    f.write(base64.b64decode(base64_data))
                return "success"
            except Exception as e:
                return f"error:{str(e)}"
        return "cancelled"

    def save_png_python(self, default_name, base64_data):
        result = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=default_name,
            file_types=('PNG Images (*.png)', 'All files (*.*)')
        )
        if not result:
            return "cancelled"
        try:
            payload = base64_data.split(',', 1)[-1]
            with open(result[0], 'wb') as output_file:
                output_file.write(base64.b64decode(payload))
            return "success"
        except Exception as e:
            return f"error:{str(e)}"

    def save_plot_python(self, default_name, data_url):
        extension = os.path.splitext(default_name)[1].lower()
        if extension not in ('.png', '.svg'):
            return "error:仅支持 PNG 或 SVG 绘图文件"
        label = 'PNG Images (*.png)' if extension == '.png' else 'SVG Images (*.svg)'
        result = window.create_file_dialog(webview.SAVE_DIALOG, save_filename=default_name, file_types=(label, 'All files (*.*)'))
        if not result:
            return "cancelled"
        try:
            header, payload = data_url.split(',', 1)
            content = base64.b64decode(payload) if ';base64' in header else unquote_to_bytes(payload)
            with open(result[0], 'wb') as output_file:
                output_file.write(content)
            return "success"
        except Exception as e:
            return f"error:{str(e)}"

    # 🚀 核心新增：调用原生“另存为”保存 CSV
    def save_csv_python(self, default_name, csv_content):
        result = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=default_name,
            file_types=('CSV Files (*.csv)', 'All files (*.*)')
        )
        if result:
            try:
                with open(result[0], 'w', encoding='utf-8-sig') as f:
                    f.write(csv_content)
                return "success"
            except Exception as e:
                return f"error:{str(e)}"
        return "cancelled"

    def save_settings_python(self, settings):
        result = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename='Perovskite_Workstation_Settings.json',
            file_types=('JSON Files (*.json)', 'All files (*.*)')
        )
        if not result:
            return "cancelled"
        try:
            with open(result[0], 'w', encoding='utf-8') as output_file:
                json.dump(settings, output_file, ensure_ascii=False, indent=2)
            return "success"
        except Exception as e:
            return f"error:{str(e)}"

    def load_settings_python(self):
        result = window.create_file_dialog(webview.OPEN_DIALOG, file_types=('JSON Files (*.json)', 'All files (*.*)'))
        if not result:
            return {"status": "cancelled"}
        try:
            if os.path.getsize(result[0]) > 1024 * 1024:
                raise ValueError('配置文件不能超过 1 MB')
            with open(result[0], 'r', encoding='utf-8-sig') as input_file:
                settings = json.load(input_file)
            if not isinstance(settings, dict) or settings.get('format') != 'perovskite-workstation-settings':
                raise ValueError('不是受支持的 Perovskite Workstation 配置文件')
            return {"status": "success", "settings": settings}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def save_text_files_python(self, files, failures=None):
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return "cancelled"
        try:
            output_dir = result[0]
            saved = 0
            for item in files:
                filename = os.path.basename(str(item.get('name', '')))
                if not filename.lower().endswith('.txt'):
                    continue
                output_path = unique_path(os.path.join(output_dir, filename))
                with open(output_path, 'w', encoding='utf-8') as output_file:
                    output_file.write(str(item.get('content', '')))
                saved += 1
            write_failure_report(output_dir, [f'{name}\t无法识别为受支持的 CHI LSV 文件' for name in (failures or [])])
            return f"success:{saved}"
        except Exception as e:
            return f"error:{str(e)}"

    def convert_bin_folders_python(self):
        source_dirs = window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=True)
        if not source_dirs:
            return {"status": "cancelled"}
        output_result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not output_result:
            return {"status": "cancelled"}
        converted = 0
        failures = []
        multiple_roots = len(source_dirs) > 1
        try:
            for source_dir in source_dirs:
                root_output = os.path.join(output_result[0], os.path.basename(os.path.normpath(source_dir))) if multiple_roots else output_result[0]
                for current_dir, _, filenames in os.walk(source_dir):
                    relative_dir = os.path.relpath(current_dir, source_dir)
                    target_dir = root_output if relative_dir == '.' else os.path.join(root_output, relative_dir)
                    bin_files = [name for name in filenames if name.lower().endswith('.bin')]
                    if bin_files:
                        os.makedirs(target_dir, exist_ok=True)
                    for filename in bin_files:
                        output_path = unique_path(os.path.join(target_dir, os.path.splitext(filename)[0] + '.txt'))
                        source_path = os.path.join(current_dir, filename)
                        try:
                            converted += bool(convert_chi_bin_file(source_path, output_path))
                        except Exception as error:
                            failures.append(f'{os.path.relpath(source_path, source_dir)}\t{error}')
            write_failure_report(output_result[0], failures)
            return {"status": "success", "converted": converted, "failed": len(failures)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def main():
    global window
    if _DOTNET_ERROR is not None or webview is None:
        raise _DOTNET_ERROR if _DOTNET_ERROR is not None else RuntimeError('pywebview 未能加载')
    mark_update_healthy()

    width, height = window_geometry()
    webview2 = check_webview2_runtime()
    log_startup(
        '准备创建窗口',
        '窗口 {0}x{1}，WebView2 {2}'.format(width, height, webview2 or '未检测到')
    )
    if not webview2:
        log_startup('警告', '未检测到 WebView2 运行时，窗口可能无法显示')

    html_path = get_resource_path(os.path.join('src', 'index.html'))
    api = BackendAPI()
    window = webview.create_window(
        title='Perovskite Engine',
        url=html_path,
        width=width,
        height=height,
        min_size=(1024, 600),
        js_api=api,
        text_select=True,
        confirm_close=True
    )
    log_startup('窗口已创建，进入 webview.start()', '{0}x{1}'.format(width, height))
    threading.Thread(target=close_splash, daemon=True).start()
    webview.start()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # noqa: BLE001
        detail = str(error)
        if webview is None:
            message = (
                APP_NAME + ' 无法启动：未能加载 .NET / WebView2 运行环境。\n\n'
                '技术信息：' + detail + '\n\n'
                '处理建议：\n'
                '1. 确认系统已启用 .NET Framework 4.8（Windows 10/11 默认自带）\n'
                '2. 确认已安装 Microsoft Edge WebView2 运行时（常青版即可）\n'
                '3. 仍无法启动时，把下面这个日志文件发给开发者：\n'
                + STARTUP_LOG
            )
        else:
            message = (
                APP_NAME + ' 启动失败：' + type(error).__name__ + ': ' + detail + '\n\n'
                '详细日志：' + STARTUP_LOG
            )
        show_startup_error(message)
        sys.exit(1)
