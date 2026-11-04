const assert = require('assert');
const fs = require('fs');

// 外观设置回归：设置入口、主题 token、持久化、图表跟随主题。
const html = fs.readFileSync('src/index.html', 'utf8');

assert(html.includes('id="appearance-theme"'), '必须有一层独立的外观主题样式');
assert(html.includes('onclick="openSettings()"'), '顶栏必须有设置入口');
assert(html.includes('id="settings-dialog"'), '设置必须用对话框呈现');
assert(html.includes('id="appearance-mode"'), '外观需要浅色/深色/跟随系统三档');
assert(html.includes('data-mode="system"'), '必须支持跟随系统');
assert(html.includes('id="appearance-accent"'), '必须提供强调色选择');
['ocean', 'teal', 'graphite', 'indigo', 'sand'].forEach((accent) => {
    assert(html.includes(`data-accent="${accent}"`), `缺少强调色 ${accent}`);
});

assert(html.includes("perovskite-workstation-appearance-v1"), '外观设置必须持久化');
assert(html.includes('prefers-color-scheme'), '跟随系统需要读取系统偏好');
assert(html.includes('--t-accent'), '强调色必须以 CSS 变量驱动');
assert(html.includes('--t-data'), '图表主色必须跟随强调色');
assert(html.includes('html[data-mode="dark"]'), '必须有深色主题变量');
assert(html.includes('function seriesFor('), '图表色序必须按主题生成');
assert(html.includes('Plotly[name] = function'), '必须包装 Plotly 渲染以注入主题');
assert(html.includes('colorway'), '切换主题时必须更新图表色序');
assert(html.includes('window.resetAppearance'), '必须提供恢复默认');
assert(html.includes('showModal'), '设置对话框应使用原生 dialog');

// 默认外观不应改变现有观感
assert(html.includes('--t-bg:#f5f5f7'), '浅色默认背景必须与现有界面一致');
assert(html.includes('--t-accent:#087ef1'), '默认强调色应为现有的海蓝');

// 品牌与设置入口位置（1.4.1）：新标识是几何 P，设置从按钮行移到侧栏底部常驻。
assert(html.includes('class="brand-mark"') && html.includes('stroke="currentColor"'), '品牌标必须使用可跟随主题的描边标识');
assert(!html.includes('<div class="brand-mark">PW</div>'), '旧的 PW 方块占位标必须移除');
assert(html.includes('class="sidebar-settings"'), '设置入口必须在侧栏底部常驻');
assert(!html.includes('class="toolbar-btn" onclick="openSettings()"'), '设置不应再占用顶部操作行');
assert(html.includes('class="sidebar-scroll"'), '侧栏内容需要独立滚动区，避免遮住设置入口');

console.log('Appearance settings checks passed');