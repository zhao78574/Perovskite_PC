const fs = require('fs');
const assert = require('assert');
const html = fs.readFileSync('src/index.html', 'utf8');

assert(html.includes('>EIS 绘图</label>'), 'left navigation must include EIS plotting');
assert(/id="file-5"\s+multiple/.test(html), 'EIS input must accept multiple files');
assert(html.includes("mode:'lines+markers'"), 'Nyquist plot must use connected points');
assert(html.includes("y:item.zImag.map(value=>-value)"), 'Nyquist plot must show negative imaginary impedance');
assert(html.includes('Math.abs(zReal[zReal.length-1]-zReal[0])'), 'impedance delta must use the first and last Z-real values');
assert(html.includes("XLSX.utils.book_append_sheet(workbook,XLSX.utils.aoa_to_sheet(summary),'Summary')"), 'EIS export must include summary sheet');
assert(html.includes('id="eis-data-table"'), 'raw EIS data must be visible');
console.log('EIS UI checks passed');
