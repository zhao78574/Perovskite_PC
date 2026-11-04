const assert = require('assert');
const fs = require('fs');
const html = fs.readFileSync('src/index.html', 'utf8');
const backend = fs.readFileSync('build_exe.py', 'utf8');
const fit = fs.readFileSync('ups_fit.py', 'utf8');

// 平滑控件：默认对齐 Origin 的 Savitzky-Golay / 2 阶 / 7 点
assert(html.includes('id="ups-smooth"'), 'UPS 配对区必须有平滑开关');
assert(html.includes('id="ups-smooth-order"'), 'UPS 必须有多项式阶数输入');
assert(html.includes('id="ups-smooth-window"'), 'UPS 必须有窗口点数输入');
assert(/id="ups-smooth-order"[^>]*value="2"/.test(html), '多项式阶数默认应为 2');
assert(/id="ups-smooth-window"[^>]*value="7"/.test(html), '窗口点数默认应为 7');
assert(html.includes('Savitzky-Golay'), '界面需要标明所用手法');

// 参数校验与重新拟合
assert(html.includes('function upsSmoothingSettings('), '需要统一的平滑参数校验入口');
assert(html.includes('% 2 === 0'), '窗口点数必须校验为奇数');
assert(html.includes('function applyUPSSmoothing('), '修改参数后应能触发重新拟合');

// 平滑参数必须真的传给后端
assert(
    /fit_ups_python\([^)]*smoothing\.window,smoothing\.order\)/.test(html),
    '平滑参数必须传给后端的 fit_ups_python'
);
assert(backend.includes('def fit_ups_python(self, cutoff_x, cutoff_y, onset_x, onset_y, cutoff_window=None, onset_window=None, smooth_window=None, smooth_order=None)'), '后端桥接函数必须接收平滑参数');
assert(backend.includes("options['smooth_window'] = int(smooth_window)"), '后端需把平滑参数透传给拟合函数');

// 平滑发生在归一化之前，且保留原始强度
assert(fit.includes('def savgol('), 'ups_fit 需要 Savitzky-Golay 实现');
assert(fit.indexOf('cutoff_y = savgol(') < fit.indexOf('cutoff_baseline = _mean_in_range'), '平滑必须早于基线与拟合计算');
assert(fit.includes('"intensity_raw"'), '导出与绘图需要保留原始强度');
assert(html.includes('"intensity_raw"') || html.includes('intensity_raw'), '前端不应丢弃原始强度');

console.log('ups smoothing wiring ok');
