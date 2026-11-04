const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

// Behavioral checks for the UPS linked cutoff/onset editing model.
// The real application script is loaded into a VM with a small DOM/Plotly stub.

const html = fs.readFileSync('src/index.html', 'utf8');

assert(!html.includes('energyShift'), 'the old single energyShift state must be removed');
assert(html.includes('cutoffShift') && html.includes('onsetShift'), 'per-sample cutoff/onset shifts must exist');
assert(html.includes('data-ups-curve="cutoff"') && html.includes('data-ups-curve="onset"'), 'per-sample Ecutoff/Eonset inputs must exist');
assert(html.includes('updateUPSCurveShift'), 'cutoff/onset inputs must use the shifted-curve editor');
assert(html.includes('step="0.01"'), 'numeric editors must use 0.01 eV steps');
assert(!html.includes('可调'), 'there must be no adjustable badge');
assert(!html.includes('prompt('), 'there must be no prompt dialog');

function escapeText(value) {
    return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function makeElement(id) {
    const handlers = {};
    const element = {
        id,
        _text: '',
        _html: undefined,
        value: '',
        style: { setProperty(name, value) { this[name] = value; } },
        checked: false,
        type: 'number',
        classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
        dataset: {},
        addEventListener() {},
        removeEventListener() {},
        removeAllListeners() { for (const key of Object.keys(handlers)) delete handlers[key]; },
        on(name, callback) { handlers[name] = callback; },
        emit(name, event) { if (handlers[name]) return handlers[name](event); },
        showModal() {},
        close() {},
        click() {},
        prepend() {},
        appendChild() {},
        querySelector() { return null; },
        querySelectorAll() { return []; }
    };
    Object.defineProperty(element, 'textContent', {
        get() { return this._text; },
        set(value) { this._text = String(value); this._html = undefined; }
    });
    Object.defineProperty(element, 'innerHTML', {
        get() { return this._html === undefined ? escapeText(this._text) : this._html; },
        set(value) { this._html = String(value); }
    });
    return element;
}

const elements = new Map();
const getElementById = id => {
    if (!elements.has(id)) elements.set(id, makeElement(id));
    return elements.get(id);
};
const documentStub = {
    getElementById,
    querySelector(selector) {
        if (selector.includes('rename_type')) return { value: '1' };
        if (selector.includes('mode')) return { value: '7' };
        return null;
    },
    querySelectorAll() { return []; },
    createElement(tag) { return makeElement(tag); },
    addEventListener() {},
    body: makeElement('body')
};

const plotlyCalls = [];
const Plotly = {
    react(id, traces, layout, config) { plotlyCalls.push({ id, traces, layout, config }); },
    newPlot(id, traces, layout, config) { plotlyCalls.push({ id, traces, layout, config }); },
    toImage: async () => 'data'
};
const XLSX = {
    read() { return { SheetNames: ['Sheet1'], Sheets: { Sheet1: {} } }; },
    utils: {
        sheet_to_json() { return []; },
        book_new() { return {}; },
        aoa_to_sheet() { return {}; },
        book_append_sheet() {}
    },
    write() { return ''; }
};
const store = {};
const localStorage = {
    getItem(key) { return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null; },
    setItem(key, value) { store[key] = String(value); },
    removeItem(key) { delete store[key]; }
};
const alerts = [];
const fitApi = {
    fit_ups_python: async () => ({ status: 'error', message: 'fit not configured' })
};
const windowStub = {
    pywebview: { api: fitApi },
    addEventListener() {}
};

const context = vm.createContext({
    document: documentStub,
    window: windowStub,
    Plotly,
    XLSX,
    localStorage,
    alert(message) { alerts.push(String(message)); },
    confirm() { return true; },
    console,
    setTimeout,
    clearTimeout,
    performance: { now: () => 0 }
});

const scriptMatch = html.match(/<script>\s*let currentPCEFiles[\s\S]*?<\/script>/);
assert(scriptMatch, 'main application script must exist');
const appScript = scriptMatch[0]
    .replace(/^<script>/, '')
    .replace(/<\/script>$/, '')
    .replace(/\nrestoreSettings\(\);[\s\S]*$/, '');
vm.runInContext(appScript, context, { filename: 'src/index.html' });

const api = vm.runInContext(`({
    samples: () => upsSamples,
    setSamples: value => { upsSamples = value; },
    pcbm: () => upsPcbmLevels,
    setPcbm: value => { upsPcbmLevels = value; },
    addUPSSample,
    upsLevels,
    upsCurrentLevels,
    upsCurveShift,
    upsTangentPoints,
    upsCurveRange,
    upsLevelError,
    upsValidDiagramLevels,
    updateUPSEnergyLevel,
    updateUPSCurveShift,
    updateUPSSample,
    updateUPSPCBM,
    resetUPSTangents,
    startUPSTangent,
    renderUPSResults,
    processUPSSamples,
    setReadUPSSpectrum: fn => { readUPSSpectrum = fn; },
    setFitResponse: value => { window.pywebview.api.fit_ups_python = async () => value; }
})`, context);

async function run() {

function makeFit(cutoff = 16.7, onset = 0.8) {
    const cutoffEnergy = [15, 15.5, 16, 16.5, 17, 17.5, 18];
    const onsetEnergy = [-1, 0, 0.5, 1, 1.5, 2, 2.5];
    return {
        cutoff_eV: cutoff,
        onset_eV: onset,
        cutoff: {
            energy: cutoffEnergy,
            intensity: cutoffEnergy.map((value, index) => 100 + index),
            normalized: cutoffEnergy.map((value, index) => 0.2 + index * 0.1),
            fit_line: cutoffEnergy.map(() => 0.5),
            r_squared: 0.991,
            window: [cutoff - 0.2, cutoff + 0.2]
        },
        onset: {
            energy: onsetEnergy,
            intensity: onsetEnergy.map((value, index) => 50 + index),
            normalized: onsetEnergy.map((value, index) => 0.2 + index * 0.1),
            fit_line: onsetEnergy.map(() => 0.5),
            r_squared: 0.981,
            window: [onset - 0.2, onset + 0.2]
        }
    };
}

function makeSample(name = 'S1', options = {}) {
    return {
        name,
        cutoffFile: '0',
        onsetFile: '1',
        bandgap: options.bandgap === undefined ? 1.56 : options.bandgap,
        windows: null,
        fitResult: makeFit(options.cutoff === undefined ? 16.7 : options.cutoff, options.onset === undefined ? 0.8 : options.onset),
        status: 'success',
        error: '',
        cutoffShift: options.cutoffShift === undefined ? 0 : options.cutoffShift,
        onsetShift: options.onsetShift === undefined ? 0 : options.onsetShift,
        energyErrors: { cutoff: '', onset: '', vbm: '', cbm: '', ef: '' },
        bandgapError: '',
        intersections: null,
        manualLines: null,
        onsetRaw: { x: [1, 2], y: [3, 4] },
        cutoffRaw: { x: [5, 6], y: [7, 8] }
    };
}

function approx(actual, expected, message) {
    assert(Math.abs(actual - expected) < 1e-9, `${message}: ${actual} !== ${expected}`);
}

function inlineError(containerId, field) {
    const markup = elements.get(containerId).innerHTML;
    const match = markup.match(new RegExp(`data-ups-error="${field}"[^>]*>([^<]*)<`));
    return match ? match[1].trim() : '';
}

function resetState() {
    api.setSamples([]);
    api.setPcbm({ lumo: -3.90, homo: -5.63 });
    plotlyCalls.length = 0;
    alerts.length = 0;
}

function pcbmState() {
    const value = api.pcbm();
    return { lumo: value.lumo, homo: value.homo };
}

// 1. New samples start with two zero shifts and no legacy energyShift.
resetState();
api.addUPSSample();
const fresh = api.samples()[0];
assert.strictEqual(fresh.cutoffShift, 0, 'new UPS samples must default cutoffShift to 0');
assert.strictEqual(fresh.onsetShift, 0, 'new UPS samples must default onsetShift to 0');
assert.strictEqual(fresh.energyShift, undefined, 'energyShift must not exist');
assert.deepStrictEqual(Object.keys(fresh.energyErrors).sort(), ['cbm', 'cutoff', 'ef', 'onset', 'vbm'], 'all level/curve errors must be tracked');
assert.strictEqual(api.pcbm().lumo, -3.90, 'PCBM LUMO default must be -3.90');
assert.strictEqual(api.pcbm().homo, -5.63, 'PCBM HOMO default must be -5.63');

// 2. Base formulas and the two independent shift directions.
const formulaSample = makeSample('Formula');
const base = api.upsLevels(formulaSample);
approx(base.workFunction, 4.52, 'base work function');
approx(base.vbm, -5.32, 'base VBM');
approx(base.cbm, -3.76, 'base CBM');
approx(base.ef, -4.52, 'base EF');
formulaSample.cutoffShift = 0.10;
let current = api.upsCurrentLevels(formulaSample);
approx(current.cutoff, 16.80, 'cutoffShift changes current cutoff');
approx(current.ef, base.ef + 0.10, 'cutoffShift +0.10 shifts EF +0.10');
approx(current.vbm, base.vbm + 0.10, 'cutoffShift +0.10 shifts VBM +0.10');
approx(current.cbm, base.cbm + 0.10, 'cutoffShift +0.10 shifts CBM +0.10');
approx(current.ef - current.vbm, base.ef - base.vbm, 'cutoffShift preserves EF relative to VBM');
formulaSample.cutoffShift = 0;
formulaSample.onsetShift = 0.10;
current = api.upsCurrentLevels(formulaSample);
approx(current.onset, 0.90, 'onsetShift changes current onset');
approx(current.ef, base.ef, 'onsetShift does not move EF');
approx(current.vbm, base.vbm - 0.10, 'onsetShift +0.10 shifts VBM -0.10');
approx(current.cbm, base.cbm - 0.10, 'onsetShift +0.10 shifts CBM -0.10');
approx(current.cbm - current.vbm, 1.56, 'onsetShift preserves Eg');
formulaSample.cutoffShift = -0.10;
formulaSample.onsetShift = 0;
current = api.upsCurrentLevels(formulaSample);
approx(current.ef, base.ef - 0.10, 'cutoffShift -0.10 shifts EF -0.10');
approx(current.vbm, base.vbm - 0.10, 'cutoffShift -0.10 shifts VBM -0.10');
approx(current.cbm, base.cbm - 0.10, 'cutoffShift -0.10 shifts CBM -0.10');
formulaSample.cutoffShift = 0;
formulaSample.onsetShift = -0.10;
current = api.upsCurrentLevels(formulaSample);
approx(current.ef, base.ef, 'negative onsetShift does not move EF');
approx(current.vbm, base.vbm + 0.10, 'onsetShift -0.10 shifts VBM +0.10');
approx(current.cbm, base.cbm + 0.10, 'onsetShift -0.10 shifts CBM +0.10');

// 3. CBM/VBM/EF input translates all three via cutoffShift only; siblings and PCBM stay fixed.
resetState();
const levelA = makeSample('A');
const levelB = makeSample('B', { cutoffShift: 0.12, onsetShift: -0.07 });
api.setSamples([levelA, levelB]);
const baseA = api.upsLevels(levelA);
const siblingBefore = api.upsCurrentLevels(levelB);
let before = api.upsCurrentLevels(levelA);
assert.strictEqual(api.updateUPSEnergyLevel(0, 'cbm', before.cbm + 0.02), true, 'valid CBM edit must apply');
let after = api.upsCurrentLevels(levelA);
approx(after.vbm, before.vbm + 0.02, 'CBM edit shifts VBM');
approx(after.cbm, before.cbm + 0.02, 'CBM edit shifts CBM');
approx(after.ef, before.ef + 0.02, 'CBM edit shifts EF');
approx(levelA.cutoffShift, 0.02, 'CBM edit is implemented through cutoffShift');
approx(levelA.onsetShift, 0, 'CBM edit leaves onsetShift fixed');
assert.deepStrictEqual(api.upsLevels(levelA), baseA, 'base fitted levels stay untouched');
assert.deepStrictEqual(api.upsCurrentLevels(levelB), siblingBefore, 'editing one sample must not move another');
assert.deepStrictEqual(pcbmState(), { lumo: -3.90, homo: -5.63 }, 'editing one sample must not move PCBM');

before = api.upsCurrentLevels(levelA);
assert.strictEqual(api.updateUPSEnergyLevel(0, 'ef', before.ef - 0.03), true, 'valid EF edit must apply');
after = api.upsCurrentLevels(levelA);
approx(after.vbm, before.vbm - 0.03, 'EF edit shifts VBM');
approx(after.cbm, before.cbm - 0.03, 'EF edit shifts CBM');
approx(after.ef, before.ef - 0.03, 'EF edit shifts EF');
approx(levelA.cutoffShift, -0.01, 'EF edit accumulates cutoffShift');

// 4. Ecutoff/Eonset inputs shift the corresponding curve and intersection value.
resetState();
const curveSample = makeSample('Curve', { cutoff: 16.734, onset: 0.812 });
api.setSamples([curveSample]);
let curveBefore = api.upsCurrentLevels(curveSample);
assert.strictEqual(api.updateUPSCurveShift(0, 'cutoff', String(curveBefore.cutoff + 0.10)), true, 'valid Ecutoff edit must apply');
let curveAfter = api.upsCurrentLevels(curveSample);
approx(curveAfter.cutoff, curveBefore.cutoff + 0.10, 'Ecutoff input changes current cutoff');
approx(curveAfter.onset, curveBefore.onset, 'Ecutoff input leaves current onset fixed');
approx(curveAfter.ef, curveBefore.ef + 0.10, 'Ecutoff +0.10 shifts EF +0.10');
approx(curveAfter.vbm, curveBefore.vbm + 0.10, 'Ecutoff +0.10 shifts VBM +0.10');
approx(curveAfter.cbm, curveBefore.cbm + 0.10, 'Ecutoff +0.10 shifts CBM +0.10');
approx(curveSample.cutoffShift, 0.10, 'Ecutoff input stores cutoffShift');
approx(curveSample.onsetShift, 0, 'Ecutoff input leaves onsetShift fixed');
curveBefore = api.upsCurrentLevels(curveSample);
assert.strictEqual(api.updateUPSCurveShift(0, 'onset', String(curveBefore.onset + 0.10)), true, 'valid Eonset edit must apply');
curveAfter = api.upsCurrentLevels(curveSample);
approx(curveAfter.onset, curveBefore.onset + 0.10, 'Eonset input changes current onset');
approx(curveAfter.ef, curveBefore.ef, 'Eonset input leaves EF unchanged');
approx(curveAfter.vbm, curveBefore.vbm - 0.10, 'Eonset +0.10 shifts VBM -0.10');
approx(curveAfter.cbm, curveBefore.cbm - 0.10, 'Eonset +0.10 shifts CBM -0.10');
approx(curveSample.onsetShift, 0.10, 'Eonset input stores onsetShift');

// 5. Rounded display commits are no-ops and reverse edits return to the base values.
resetState();
const driftSample = makeSample('Drift', { cutoff: 16.734, onset: 0.812, cutoffShift: 0.25, onsetShift: -0.15 });
api.setSamples([driftSample]);
const driftSnapshot = { cutoffShift: driftSample.cutoffShift, onsetShift: driftSample.onsetShift };
for (const field of ['cutoff', 'onset', 'vbm', 'cbm', 'ef']) {
    const live = api.upsCurrentLevels(driftSample);
    const displayed = Number(live[field].toFixed(2));
    if (field === 'cutoff' || field === 'onset') {
        assert.strictEqual(api.updateUPSCurveShift(0, field, String(displayed)), true, `${field} rounded display must be accepted`);
    } else {
        assert.strictEqual(api.updateUPSEnergyLevel(0, field, String(displayed)), true, `${field} rounded display must be accepted`);
    }
    assert.strictEqual(driftSample.cutoffShift, driftSnapshot.cutoffShift, `${field} no-op must not change cutoffShift`);
    assert.strictEqual(driftSample.onsetShift, driftSnapshot.onsetShift, `${field} no-op must not change onsetShift`);
}
assert.strictEqual(api.updateUPSCurveShift(0, 'cutoff', String(api.upsLevels(driftSample).cutoff)), true, 'reverse Ecutoff edit must apply');
approx(driftSample.cutoffShift, 0, 'reverse Ecutoff edit returns to base');
assert.strictEqual(api.updateUPSCurveShift(0, 'onset', String(api.upsLevels(driftSample).onset)), true, 'reverse Eonset edit must apply');
approx(driftSample.onsetShift, 0, 'reverse Eonset edit returns to base');
assert.deepStrictEqual(api.upsLevels(driftSample), api.upsLevels(makeSample('Drift', { cutoff: 16.734, onset: 0.812 })), 'base levels remain the fitted values');

// 6. Invalid level and curve edits are atomic with inline errors.
resetState();
const invalid = makeSample('Invalid', { cutoffShift: 0.10, onsetShift: -0.05 });
api.setSamples([invalid]);
const fitSnapshot = JSON.parse(JSON.stringify(invalid.fitResult));
const rawSnapshot = JSON.parse(JSON.stringify(invalid.onsetRaw));
const invalidBefore = api.upsCurrentLevels(invalid);
for (const badValue of ['', '   ', 'not-a-number', 'NaN', 'Infinity', '-Infinity', '0', '0.5']) {
    assert.strictEqual(api.updateUPSEnergyLevel(0, 'cbm', badValue), false, `CBM edit ${JSON.stringify(badValue)} must be rejected`);
}
for (const badValue of ['', 'abc', 'NaN', 'Infinity']) {
    assert.strictEqual(api.updateUPSCurveShift(0, 'cutoff', badValue), false, `Ecutoff edit ${JSON.stringify(badValue)} must be rejected`);
    assert.strictEqual(api.updateUPSCurveShift(0, 'onset', badValue), false, `Eonset edit ${JSON.stringify(badValue)} must be rejected`);
}
assert.strictEqual(api.updateUPSCurveShift(0, 'cutoff', String(api.upsCurrentLevels(invalid).cutoff + 100)), false, 'level-breaking Ecutoff edit must be rejected');
assert.deepStrictEqual(api.upsCurrentLevels(invalid), invalidBefore, 'rejected edits must not change current levels');
assert.deepStrictEqual(invalid.fitResult, fitSnapshot, 'rejected edits must not change fitted results');
assert.deepStrictEqual(invalid.onsetRaw, rawSnapshot, 'rejected edits must not change raw data');
assert(inlineError('ups-fit-controls', 'cbm').length > 0, 'rejected level edit must show an inline error');
assert(api.updateUPSCurveShift(0, 'cutoff', String(api.upsCurrentLevels(invalid).cutoff)) === true, 'valid cutoff after an error must apply');
assert.strictEqual(inlineError('ups-fit-controls', 'cutoff'), '', 'valid cutoff must clear its inline error');

// 7. Eg edits keep current VBM/EF, recompute CBM, and preserve both shifts; invalid Eg is atomic.
resetState();
const egSample = makeSample('Eg', { cutoffShift: 0.30, onsetShift: -0.20 });
api.setSamples([egSample]);
const egBefore = api.upsCurrentLevels(egSample);
const egShiftBefore = { cutoffShift: egSample.cutoffShift, onsetShift: egSample.onsetShift };
api.updateUPSSample(0, 'bandgap', '1.80');
const egAfter = api.upsCurrentLevels(egSample);
approx(egSample.bandgap, 1.80, 'valid Eg must update the stored bandgap');
approx(egAfter.vbm, egBefore.vbm, 'Eg edit keeps current VBM');
approx(egAfter.ef, egBefore.ef, 'Eg edit keeps current EF');
approx(egAfter.cbm, egBefore.vbm + 1.80, 'Eg edit recomputes current CBM');
assert.deepStrictEqual({ cutoffShift: egSample.cutoffShift, onsetShift: egSample.onsetShift }, egShiftBefore, 'Eg edit preserves both shifts');
for (const badEg of ['', 'abc', '0', '-0.5', '0.5', '20']) {
    const gapSnapshot = egSample.bandgap;
    const levelSnapshot = api.upsCurrentLevels(egSample);
    api.updateUPSSample(0, 'bandgap', badEg);
    assert.strictEqual(egSample.bandgap, gapSnapshot, `invalid Eg ${JSON.stringify(badEg)} must not change the bandgap`);
    assert.deepStrictEqual(api.upsCurrentLevels(egSample), levelSnapshot, `invalid Eg ${JSON.stringify(badEg)} must not change levels`);
    assert(inlineError('ups-pairs', 'bandgap').length > 0, `invalid Eg ${JSON.stringify(badEg)} must show an inline error`);
}
api.updateUPSSample(0, 'bandgap', '1.80');
assert.strictEqual(inlineError('ups-pairs', 'bandgap'), '', 'valid Eg must clear the inline error');

// 8. Fit/raw arrays are untouched by all link edits.
resetState();
const immutable = makeSample('Immutable', { cutoffShift: 0.10, onsetShift: 0.05 });
api.setSamples([immutable]);
const immutableFit = JSON.parse(JSON.stringify(immutable.fitResult));
const immutableRaw = JSON.parse(JSON.stringify(immutable.onsetRaw));
api.updateUPSCurveShift(0, 'cutoff', String(api.upsCurrentLevels(immutable).cutoff + 0.05));
api.updateUPSCurveShift(0, 'onset', String(api.upsCurrentLevels(immutable).onset - 0.02));
api.updateUPSEnergyLevel(0, 'vbm', api.upsCurrentLevels(immutable).vbm + 0.01);
api.updateUPSSample(0, 'bandgap', '1.70');
assert.deepStrictEqual(immutable.fitResult, immutableFit, 'link edits must not mutate fitted arrays');
assert.deepStrictEqual(immutable.onsetRaw, immutableRaw, 'link edits must not mutate raw arrays');

// 9. Reset, file changes, and refit reset both shifts for the affected sample only.
resetState();
api.setPcbm({ lumo: -3.80, homo: -5.50 });
const resetSample = makeSample('Reset', { cutoffShift: 0.60, onsetShift: -0.20 });
resetSample.manualLines = { cutoff: { points: [[16, 1], [16.5, 0]], intersection: 16.7 } };
resetSample.intersections = { cutoff: 16.7, onset: 0.8 };
api.setSamples([resetSample]);
api.resetUPSTangents(0);
assert.strictEqual(resetSample.cutoffShift, 0, 'tangent reset must clear cutoffShift');
assert.strictEqual(resetSample.onsetShift, 0, 'tangent reset must clear onsetShift');
assert.strictEqual(resetSample.manualLines, null, 'tangent reset must clear manual lines');
assert.strictEqual(resetSample.intersections, null, 'tangent reset must clear intersections');
assert.deepStrictEqual(pcbmState(), { lumo: -3.80, homo: -5.50 }, 'tangent reset must retain PCBM');

const fileSample = makeSample('File', { cutoffShift: 0.42, onsetShift: -0.31 });
api.setSamples([fileSample]);
api.updateUPSSample(0, 'onsetFile', '2');
assert.strictEqual(fileSample.cutoffShift, 0, 'file changes reset cutoffShift');
assert.strictEqual(fileSample.onsetShift, 0, 'file changes reset onsetShift');
assert.strictEqual(fileSample.fitResult, null, 'file changes still clear the old fit');
assert.strictEqual(fileSample.status, 'pending', 'file changes return the sample to pending');
assert.deepStrictEqual(pcbmState(), { lumo: -3.80, homo: -5.50 }, 'file changes retain PCBM');

const fitSample = makeSample('Fit', { cutoffShift: 0.55, onsetShift: 0.25 });
fitSample.status = 'pending';
fitSample.fitResult = null;
api.setSamples([fitSample]);
api.setReadUPSSpectrum(async () => ({ x: [1, 2, 3], y: [4, 5, 6] }));
const refitResult = makeFit();
api.setFitResponse({ status: 'success', result: refitResult });
await api.processUPSSamples();
assert.strictEqual(fitSample.cutoffShift, 0, 'refitting must reset cutoffShift');
assert.strictEqual(fitSample.onsetShift, 0, 'refitting must reset onsetShift');
assert.strictEqual(fitSample.status, 'success', 'refit must succeed with the stubbed fitter');
assert.strictEqual(fitSample.fitResult, refitResult, 'refit must store the returned fit result');
assert.deepStrictEqual(pcbmState(), { lumo: -3.80, homo: -5.50 }, 'refitting must retain PCBM');

// 10. Accepted manual tangents store base coordinates and preserve both shifts.
resetState();
const manualSample = makeSample('Manual', { cutoffShift: 0.20, onsetShift: -0.10 });
api.setSamples([manualSample]);
api.renderUPSResults();
const cutoffPlot = getElementById('ups-curve-cutoff-0');
api.startUPSTangent(0, 'cutoff');
cutoffPlot.emit('plotly_click', { points: [{ x: 16.2, y: 10, data: { meta: { role: 'ups-curve', sampleIndex: 0 } } }] });
cutoffPlot.emit('plotly_click', { points: [{ x: 17.2, y: 0, data: { meta: { role: 'ups-curve', sampleIndex: 0 } } }] });
assert(manualSample.manualLines && manualSample.manualLines.cutoff, 'accepted manual tangent must be stored');
approx(manualSample.manualLines.cutoff.points[0][0], 16, 'first click x must be converted back to base coordinates');
approx(manualSample.manualLines.cutoff.points[1][0], 17, 'second click x must be converted back to base coordinates');
assert.strictEqual(manualSample.manualLines.cutoff.points[0][1], 10, 'first click y must be retained');
assert.strictEqual(manualSample.manualLines.cutoff.points[1][1], 0, 'second click y must be retained');
approx(manualSample.manualLines.cutoff.intersection, 17, 'manual base intersection must be stored');
approx(manualSample.intersections.cutoff, 17, 'base manual intersection must be recorded');
assert.strictEqual(manualSample.cutoffShift, 0.20, 'accepted manual tangent must preserve cutoffShift');
assert.strictEqual(manualSample.onsetShift, -0.10, 'accepted manual tangent must preserve onsetShift');
approx(api.upsCurrentLevels(manualSample).cutoff, 17.2, 'current manual intersection must include cutoffShift');
const manualTangent = api.upsTangentPoints(manualSample, 'cutoff', 15, 18);
assert(manualTangent.some(point => Math.abs(point[0] - 17.2) < 1e-9 && point[1] === 0), 'manual tangent must be plotted at shifted coordinates');
api.resetUPSTangents(0);
assert.strictEqual(manualSample.cutoffShift, 0, 'manual reset must clear cutoffShift');
assert.strictEqual(manualSample.onsetShift, 0, 'manual reset must clear onsetShift');
assert.strictEqual(manualSample.manualLines, null, 'manual reset must clear manual lines');

// 11. Summary stays on fitted values while the energy diagram uses current values.
resetState();
const summarySample = makeSample('Summary', { cutoffShift: 0.30, onsetShift: -0.20 });
api.setSamples([summarySample]);
plotlyCalls.length = 0;
api.renderUPSResults();
const summaryBase = api.upsLevels(summarySample);
const summaryCurrent = api.upsCurrentLevels(summarySample);
const summaryHtml = elements.get('ups-summary-table').innerHTML;
assert(summaryHtml.includes(summaryBase.vbm.toFixed(3)), 'summary must show fitted VBM');
assert(summaryHtml.includes(summaryBase.cbm.toFixed(3)), 'summary must show fitted CBM');
assert(!summaryHtml.includes(summaryCurrent.vbm.toFixed(3)), 'summary must not show shifted VBM');
assert(!summaryHtml.includes(summaryCurrent.cbm.toFixed(3)), 'summary must not show shifted CBM');
const energyCall = plotlyCalls.find(call => call.id === 'ups-energy-ref');
assert(energyCall, 'default reference energy plot must render');
const energyLines = energyCall.layout.shapes.filter(shape => shape.type === 'line');
assert(energyLines.some(shape => shape.y0 === summaryCurrent.vbm && shape.y1 === summaryCurrent.vbm), 'reference plot must place VBM at its current numeric value');
assert(energyLines.some(shape => shape.y0 === summaryCurrent.cbm && shape.y1 === summaryCurrent.cbm), 'reference plot must place CBM at its current numeric value');
assert(energyLines.some(shape => shape.y0 === summaryCurrent.ef && shape.y1 === summaryCurrent.ef), 'reference plot must place EF at its current numeric value');
const controlsHtml = elements.get('ups-fit-controls').innerHTML;
assert(controlsHtml.includes(`value="${summaryCurrent.cutoff.toFixed(2)}"`), 'Ecutoff editor must show current cutoff');
assert(controlsHtml.includes(`value="${summaryCurrent.onset.toFixed(2)}"`), 'Eonset editor must show current onset');
assert(controlsHtml.includes(`value="${summaryCurrent.vbm.toFixed(2)}"`), 'VBM editor must show current VBM');
assert(controlsHtml.includes(`value="${summaryCurrent.cbm.toFixed(2)}"`), 'CBM editor must show current CBM');
assert(controlsHtml.includes(`value="${summaryCurrent.ef.toFixed(2)}"`), 'EF editor must show current EF');

console.log('UPS linked cutoff/onset behavioral checks passed');
}

run().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
