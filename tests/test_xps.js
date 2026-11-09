const assert = require('assert'), fs = require('fs'), vm = require('vm');

const html = fs.readFileSync('src/index.html', 'utf8');
assert(html.includes('value="10"') && html.includes('id="plot-10"'), 'XPS mode must be present');
assert(html.includes('autorange:\'reversed\''), 'XPS binding-energy axis must be reversed');
const start = html.indexOf('function xpsCellText');
const end = html.indexOf('async function processXPS');
assert(start >= 0 && end > start, 'XPS parser block must exist');
const context = vm.createContext({console});
vm.runInContext(`${html.slice(start, end)}; this.detectXPSColumns=detectXPSColumns; this.buildXPSResult=buildXPSResult;`, context);

function rowsWithData(headers, count = 30) {
    return [
        ['Avantage export', null, null, null, null, null],
        headers,
        ['eV / counts', 'eV', 'counts/s', 'counts/s', 'counts/s', 'counts/s'],
        ...Array.from({length: count}, (_, index) => {
            const energy = 540 - index;
            const raw = 100 + (index === 8 ? 80 : 0) + (index === 20 ? 50 : 0);
            return [null, energy, raw, 20, raw - 20, raw - 20];
        }),
    ];
}

const o1s = rowsWithData(['Metadata', 'Binding Energy', 'O 1s Experimental', 'O 1s Background', 'O 1s Envelope', 'O 1s Peak 1']);
o1s[4][2] = null;
o1s[5][2] = 'not-a-number';
const oDetected = context.detectXPSColumns(o1s);
assert.strictEqual(oDetected.x, 1, 'O 1s must detect binding energy by semantic header');
assert.strictEqual(oDetected.y, 2, 'O 1s must detect the experimental column');
assert(oDetected.components.some(column => column.role === 'background'));
assert(oDetected.components.some(column => column.role === 'envelope'));
const oResult = context.buildXPSResult('O1s.xlsx', 'O 1s', o1s, oDetected);
assert.strictEqual(oResult.energy.length, 28, 'blank and text rows must be skipped without blank plots');
assert(oResult.background && oResult.envelope, 'optional fitted series must be retained');

const i3d = rowsWithData(['I 3d Envelope', 'Binding Energy (eV)', 'I 3d Background', 'I 3d Scan A', 'I 3d Peak 1', 'I 3d Peak 2']);
 i3d.slice(3).forEach(row => { const raw=row[2]; row[0]=raw-20; row[2]=20; row[3]=raw; row[4]=raw-20; row[5]=raw-20; });
const iDetected = context.detectXPSColumns(i3d);
assert.strictEqual(iDetected.x, 1, 'I 3d energy must survive reordered columns');
assert.strictEqual(iDetected.y, 3, 'I 3d raw intensity must not be inferred from position');
const iResult = context.buildXPSResult('I3d.xlsx', 'I 3d', i3d, iDetected);
assert.strictEqual(iResult.components.length, 2, 'multiple fitted peaks must remain separate components');

const bare = rowsWithData(['Metadata', 'Binding Energy', 'C 1s Experimental', null, null, null]);
bare.forEach(row => { row[3] = null; row[4] = null; row[5] = null; });
const bareDetected = context.detectXPSColumns(bare);
const bareResult = context.buildXPSResult('C1s.xlsx', 'C 1s', bare, bareDetected);
assert.strictEqual(bareResult.background, null, 'missing background must stay absent');
assert.strictEqual(bareResult.envelope, null, 'missing envelope must stay absent');
assert.strictEqual(bareResult.components.length, 0, 'no fitting components may be fabricated');

console.log('XPS parser tests passed');
