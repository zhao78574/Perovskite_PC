const assert = require('assert'), fs = require('fs');

// 启动优化回归测试：前端依赖必须本地化，NumPy/SciPy 不得在模块顶层导入。
const html = fs.readFileSync('src/index.html', 'utf8');
assert(!/https:\/\/cdn\./.test(html), '前端脚本不能从 CDN 加载');
assert(html.includes('src="vendor/plotly-2.27.0.min.js"'), 'Plotly 必须从 src/vendor 加载');
assert(html.includes('src="vendor/xlsx.full.min.js"'), 'SheetJS 必须从 src/vendor 加载');
['plotly-2.27.0.min.js', 'xlsx.full.min.js'].forEach((name) =>
    assert(fs.existsSync('src/vendor/' + name), '缺少本地依赖 ' + name));

const backend = fs.readFileSync('build_exe.py', 'utf8');
const moduleLevel = backend.split('class BackendAPI')[0];
assert(!/^from trpl_fit import/m.test(moduleLevel), 'trpl_fit 不能在模块顶层导入');
assert(!/^from ups_fit import/m.test(moduleLevel), 'ups_fit 不能在模块顶层导入');
assert(backend.includes('from trpl_fit import fit_trpl'), '按需导入后仍需能调用 fit_trpl');
assert(backend.includes('from ups_fit import fit_ups_sample'), '按需导入后仍需能调用 fit_ups_sample');
assert(backend.includes('url=html_path'), '页面需以 url 方式加载，vendor 相对路径才可解析');

const spec = fs.readFileSync('packaging/perovskite-engine.spec', 'utf8');
assert(spec.includes("'../src/vendor', 'src/vendor'"), '打包时必须带上 src/vendor');
