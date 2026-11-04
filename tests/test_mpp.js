const fs = require('fs');
const assert = require('assert');
const html = fs.readFileSync('src/index.html', 'utf8');

assert(html.includes('>MPP 绘图</label>'), 'left navigation must include MPP plotting');
assert(/id="file-6"\s+multiple/.test(html), 'MPP input must accept multiple files');
assert(html.includes("rows.map(row=>row[1]*1000)"), 'MPP current must convert A to mA');
assert(html.includes("Plotly.newPlot('plot-6', traces"), 'MPP curves must render together');
assert(html.includes('id="mpp-data-table"'), 'raw MPP data must be visible');
assert(html.includes('id="mpp-y-mode"'), 'MPP y-axis must switch between current and PCE');
assert(html.includes("title:pceMode?'PCE (%)':'Current (mA)'"), 'MPP plot must label the selected y-axis');
assert(html.includes("save_excel_python('MPP_Converted_Data.xlsx'"), 'converted MPP data must export to Excel');
assert(html.includes('Math.abs(currentMa) / settings.area'), 'PCE conversion must use absolute current and device area');
assert(html.includes('id="mpp-smooth"'), 'MPP controls must include a smoothing toggle');
assert(html.includes('function smoothMPPSeries(values)'), 'MPP smoothing must preserve a testable implementation');
assert(html.includes('index<start?average(index,0,start,25):average(index,start,values.length,100)'), 'MPP smoothing must independently smooth startup and stable regions');
assert(html.includes("['smoothing_enabled',smoothing?'yes':'no']"), 'MPP export must record whether smoothing was enabled');
console.log('MPP UI checks passed');
