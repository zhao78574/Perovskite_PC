const assert = require('assert');
const fs = require('fs');

// 1.3.1 回归：启动必须在导入 pywebview 之前选定 .NET 运行时，失败要能给出中文提示；
// 顶栏在窄窗口 / 高缩放下必须换行，不能把右侧按钮挤出窗口。

const backend = fs.readFileSync('build_exe.py', 'utf8');
const html = fs.readFileSync('src/index.html', 'utf8');

assert(backend.includes("DOTNET_RUNTIMES = ('netfx', 'coreclr')"), '必须同时支持 netfx 与 coreclr');
assert(backend.includes('def _activate_dotnet_runtime()'), '必须有明确的运行时选择函数');
assert(backend.includes('pythonnet.load(runtime)'), '必须通过 pythonnet.load 选定运行时');
assert(backend.includes('RUNTIME_CACHE'), '成功运行时必须缓存，避免每次试探');
assert(backend.includes('def check_webview2_runtime()'), '必须检查 WebView2 运行时');
assert(backend.includes('def window_geometry()'), '窗口尺寸必须集中在一处定义');
assert(backend.includes('return 1366, 768'), '窗口保持逻辑像素，避免 WebView2 二次放大裁切');
assert(backend.includes('MessageBoxW'), '启动失败必须弹出系统消息框');
assert(backend.includes('无法启动'), '错误提示必须是中文说明');
assert(backend.includes('STARTUP_LOG'), '启动过程必须落盘到日志文件');

const runtimeCall = backend.indexOf('_activate_dotnet_runtime()');
const webviewImport = backend.indexOf('import webview  # noqa: E402');
assert(runtimeCall > -1 && webviewImport > runtimeCall, '导入 pywebview 必须晚于运行时选择');

assert(/\.topbar\s*\{[^}]*flex-wrap:\s*wrap/.test(html), '顶栏必须允许换行');
assert(/\.top-actions\s*\{[^}]*flex-wrap:\s*wrap/.test(html), '操作按钮组必须允许换行');
assert(/\.top-actions\s*\{[^}]*min-width:\s*0/.test(html), '操作按钮组不能被压缩溢出');

console.log('Startup runtime and DPI checks passed');
