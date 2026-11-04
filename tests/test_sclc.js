const fs = require('fs');
const assert = require('assert');
const html = fs.readFileSync('src/index.html', 'utf8');

assert(html.includes('>SCLC 分析</label>'), 'left navigation must include SCLC analysis');
assert(/id="file-8"\s+multiple/.test(html), 'SCLC input must accept multiple files');
assert(html.includes('id="sclc-area" value="0.07065"'), 'SCLC area must use the requested default');
assert(html.includes("Math.abs(current)/area"), 'SCLC current density must use absolute current and device area');
assert(html.includes("settings.polarity==='positive'?row.rawVoltage>0:row.rawVoltage<0"), 'SCLC must filter the selected voltage polarity');
assert(html.includes("type:'log'"), 'SCLC axes must use logarithmic scales');
assert(html.includes('id="sclc-smooth" checked'), 'SCLC must offer enabled-by-default smoothing');
assert(html.includes('function smoothSCLC(values)'), 'SCLC smoothing must preserve a testable implementation');
assert(html.includes("smoothedCurrentDensity=Math.abs(smoothed[index])/settings.area"), 'SCLC must smooth signed current before taking its absolute value');
assert(html.includes("save_excel_python('SCLC_Data.xlsx'"), 'SCLC converted data must export to Excel');
assert(html.includes("exportPlot('plot-8','SCLC_Plot',format"), 'SCLC plot must export through the shared PNG/SVG path');
console.log('SCLC UI checks passed');
