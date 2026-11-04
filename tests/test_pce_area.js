const fs = require('fs');
const assert = require('assert');
const html = fs.readFileSync('src/index.html', 'utf8');

assert(html.includes('onchange="applyPCEAreaToAll()"'), 'global area must explicitly update every J-V file');
assert(/id="pce-abs"(?![^>]*\schecked)[^>]*>/.test(html), 'absolute-current calculation must be off by default');
assert(html.includes("pceSeries.forEach(item=>item.area=area)"), 'global area must overwrite all per-file areas');
assert(html.includes('function updatePCEArea(index, value)'), 'each J-V file must expose an independent area update');
assert(html.includes('item.area = area; calculatePCESeries(item);'), 'a row edit must recalculate only the selected file');
assert(html.includes("item.i.map(value=>(doAbs?Math.abs(value):value)*1000/item.area)"), 'plot current density must use each file area');
assert(html.includes('"面积 (cm²)": area'), 'PCE results and CSV export must include the effective area');
assert((html.match(/if\(!\(area>0\)\)/g) || []).length >= 3, 'import, global, and per-file area values must reject non-positive or invalid input');
assert(html.includes('pceSeries = []; pceDataCache = [];'), 'clearing J-V data must clear per-file areas');
assert(html.includes('class="sort-header"'), 'every J-V result header must expose a sort button');
assert(html.includes("pceSort.direction==='asc'?'▲':'▼'"), 'active headers must show ascending or descending direction');
assert(html.includes('onclick=\'sortPCETable('), 'clicking a header must sort the J-V result table');
assert(html.includes('updatePCEArea(${index},this.value)'), 'sorted rows must retain their original editable area index');

const compareSource = html.match(/function comparePCEValues\([\s\S]*?\n}/)[0];
eval(compareSource);
assert(comparePCEValues('2.txt', '10.txt', '文件名') < 0, 'filename sorting must use natural numeric order');
assert(comparePCEValues('1.1620', '1.1680', 'Voc (V)') < 0, 'photovoltaic metrics must sort numerically');

const interpolateSource = html.match(/function interpolateAtZero\([\s\S]*?\n}/)[0];
const getPceSource = html.match(/function getPceFromLists\([\s\S]*?\n}/)[0];
eval(interpolateSource + '\n' + getPceSource);
const first = getPceFromLists([0, 0.5, 1], [0.002, 0.001, 0], 'first.txt', true, 0.1);
const second = getPceFromLists([0, 0.5, 1], [0.002, 0.001, 0], 'second.txt', true, 0.2);
assert.strictEqual(Number(first['Jsc (mA/cm²)']), 20, 'first file must use its own area');
assert.strictEqual(Number(second['Jsc (mA/cm²)']), 10, 'second file must use its own area');
assert.strictEqual(Number(first['PCE (%)']), Number(second['PCE (%)']) * 2, 'PCE must scale with each file area');
assert.strictEqual(first['面积 (cm²)'], 0.1, 'exported result must retain the first file area');
assert.strictEqual(second['面积 (cm²)'], 0.2, 'exported result must retain the second file area');

const reference = getPceFromLists([-0.1, 0.1, 0.5, 0.9, 1.1], [0.0022, 0.0018, 0.0018, 0.0002, -0.0002], 'reference.txt', false, 0.1);
assert.strictEqual(Number(reference['Jsc (mA/cm²)']), 20, 'Jsc must be linearly interpolated at V=0');
assert.strictEqual(Number(reference['Voc (V)']), 1, 'Voc must be linearly interpolated at I=0');
assert.strictEqual(Number(reference['FF']), 0.45, 'FF must use interpolated Voc and Jsc');
assert.strictEqual(Number(reference['PCE (%)']), 9, 'PCE must match the hand-calculated reference result');
console.log('J-V per-file area checks passed');
