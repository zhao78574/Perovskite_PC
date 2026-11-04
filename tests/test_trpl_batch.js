const fs = require('fs');
const assert = require('assert');
const html = fs.readFileSync('src/index.html', 'utf8');

assert(/id="file-4"\s+multiple/.test(html), 'TRPL input must accept multiple files');
assert(html.includes("trplResults.push({name:file.name, raw, model, status:'success'"), 'successful batch results must be retained');
assert(html.includes("XLSX.utils.book_append_sheet(workbook,XLSX.utils.aoa_to_sheet(summary),'Summary')"), 'batch export must include Summary');
assert(html.includes("safeSheetName(item.name,used)"), 'sample sheets must use safe unique names');
assert(html.includes("'模型','τavg','y0'"), 'τavg must appear before y0 in the summary table');
assert(html.includes('<option value="expdec2" selected>'), 'ExpDec2 must be the default model');
assert(html.includes('<option value="expdec3">'), 'ExpDec3 must be selectable');
console.log('TRPL batch UI checks passed');
