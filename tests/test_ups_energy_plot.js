const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('src/index.html', 'utf8');
const mainMatch = html.match(/<script>\s*let currentPCEFiles[\s\S]*?<\/script>/);
const appearanceMatch = html.match(/<script>\s*\(function \(\) \{\s*'use strict';[\s\S]*?<\/script>/);
assert(mainMatch, 'main application script must exist');
assert(appearanceMatch, 'appearance script must exist');

assert(html.includes('ups-energy-scroll'), 'energy figure must have a horizontal scroll container');
assert(/\.ups-energy-scroll\s*\{[^}]*overflow-x:auto/.test(html), 'narrow viewports must scroll rather than compress the energy figure');
assert(html.includes("exportUPSPlot('energy','png')"), 'energy PNG export button must exist');
assert(html.includes('Shifted Summary') && html.includes('Cutoff Plot Shifted') && html.includes('Onset Plot Shifted'), 'workbook must expose shifted sheets');
assert(html.includes('Energy Levels') && html.includes('signed_offset_eV'), 'workbook must expose current Energy Levels');
assert(html.includes('Nanomaterials 2022') && html.includes('10.3390/nano12030532'), 'PCBM source must be cited');
assert(html.includes('if (isUPSReferencePlot(element))'), 'UPS plots must bypass the react theme wrapper');
assert(/if \(isUPSReferencePlot\(el\)\) return;/.test(html), 'UPS plots must bypass live theme relayout');
assert(!html.includes('energyShift'), 'the old energyShift state must be absent');

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
        dataset: {},
        checked: false,
        type: 'number',
        classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
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

function createHarness() {
    const elements = new Map();
    const getElementById = id => {
        if (!elements.has(id)) elements.set(id, makeElement(id));
        return elements.get(id);
    };
    const plotElements = [];
    const plotlyCalls = [];
    const relayoutCalls = [];
    const restyleCalls = [];
    const toImageCalls = [];
    const alerts = [];
    const store = {};

    const recordPlot = (id, traces, layout, config) => {
        const element = getElementById(id);
        element.__plotly = true;
        element.data = traces;
        element.layout = layout || {};
        if (!plotElements.includes(element)) plotElements.push(element);
        plotlyCalls.push({ id, traces, layout, config, element });
    };

    const Plotly = {
        react(id, traces, layout, config) { recordPlot(id, traces, layout, config); },
        newPlot(id, traces, layout, config) { recordPlot(id, traces, layout, config); },
        relayout(element, update) { relayoutCalls.push({ id: element && element.id, update }); },
        restyle(element, update, indices) { restyleCalls.push({ id: element && element.id, update, indices }); },
        toImage(id, options) { toImageCalls.push({ id, options }); return 'data'; }
    };

    const documentStub = {
        readyState: 'complete',
        documentElement: { dataset: {} },
        body: makeElement('body'),
        getElementById,
        querySelector(selector) {
            if (selector.includes('rename_type')) return { value: '1' };
            if (selector.includes('mode')) return { value: '7' };
            return null;
        },
        querySelectorAll(selector) {
            if (selector === '.js-plotly-plot') return plotElements;
            return [];
        },
        createElement(tag) { return makeElement(tag); },
        addEventListener() {}
    };

    const localStorage = {
        getItem(key) { return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null; },
        setItem(key, value) { store[key] = String(value); },
        removeItem(key) { delete store[key]; }
    };

    const windowStub = {
        addEventListener() {},
        matchMedia() { return { matches: false, addEventListener() {} }; },
        pywebview: {
            api: {
                save_plot_python: async () => 'success',
                save_excel_python: async () => 'success'
            }
        }
    };

    const context = vm.createContext({
        document: documentStub,
        window: windowStub,
        Plotly,
        localStorage,
        alert(message) { alerts.push(String(message)); },
        confirm() { return true; },
        getComputedStyle() { return { getPropertyValue() { return ''; } }; },
        console,
        setTimeout() { return 0; },
        clearTimeout() {},
        performance: { now: () => 0 }
    });

    vm.runInContext(fs.readFileSync('src/vendor/xlsx.full.min.js', 'utf8'), context, { filename: 'xlsx.full.min.js' });
    assert(context.XLSX, 'bundled XLSX must load in the test VM');
    const XLSX = context.XLSX;

    const mainScript = mainMatch[0]
        .replace(/^<script>/, '')
        .replace(/<\/script>$/, '')
        .replace(/\nrestoreSettings\(\);[\s\S]*$/, '');
    vm.runInContext(mainScript, context, { filename: 'src/index.html' });
    vm.runInContext(appearanceMatch[0].replace(/^<script>/, '').replace(/<\/script>$/, ''), context, { filename: 'appearance' });

    const api = vm.runInContext(`({
        setSamples: value => { upsSamples = value; },
        samples: () => upsSamples,
        setPcbm: value => { upsPcbmLevels = value; upsPcbmError = ''; },
        pcbm: () => upsPcbmLevels,
        pcbmError: () => upsPcbmError,
        upsEnergyFigure,
        upsReferenceEnergyFigure,
        upsEnergyWidth,
        upsSignedOffset,
        buildUPSWorkbook,
        exportUPSPlot,
        renderUPSResults,
        updateUPSPCBM,
        updateUPSEnergyLevel,
        updateUPSCurveShift,
        clearUI,
        upsLevels,
        upsCurrentLevels,
        upsCurveShift,
        upsTangentPoints,
        upsCurveRange,
        colors: UPS_ENERGY_COLORS,
        pcbmColor: UPS_PCBM_COLOR,
        openSettings: () => window.openSettings()
    })`, context);

    return { api, elements, plotlyCalls, relayoutCalls, restyleCalls, toImageCalls, alerts, XLSX, localStorage, root: documentStub.documentElement };
}

const { api, elements, plotlyCalls, relayoutCalls, restyleCalls, toImageCalls, XLSX, localStorage, root } = createHarness();

function makeFit(cutoff, onset) {
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
    const cutoff = options.cutoff === undefined ? 16.7 : options.cutoff;
    const onset = options.onset === undefined ? 0.8 : options.onset;
    return {
        name,
        cutoffFile: '0',
        onsetFile: '1',
        bandgap: options.bandgap === undefined ? 1.56 : options.bandgap,
        windows: null,
        fitResult: makeFit(cutoff, onset),
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

function reset() {
    api.setSamples([]);
    api.setPcbm({ lumo: -3.90, homo: -5.63 });
    plotlyCalls.length = 0;
    relayoutCalls.length = 0;
    restyleCalls.length = 0;
    toImageCalls.length = 0;
    localStorage.setItem('perovskite-workstation-appearance-v1', JSON.stringify({ mode: 'light', accent: 'ocean' }));
}

function sheetRows(workbook, name) {
    return XLSX.utils.sheet_to_json(workbook.Sheets[name], { header: 1, defval: '' });
}

function roundtrip(workbook) {
    const base64 = XLSX.write(workbook, { bookType: 'xlsx', type: 'base64' });
    return XLSX.read(base64, { type: 'base64' });
}

function column(headers, rows, name) {
    const index = headers.indexOf(name);
    assert(index >= 0, `missing column ${name}`);
    return rows.map(row => row[index]);
}

async function run() {
    const A = makeSample('A', { cutoff: 16.7, onset: 0.8 });
    const B = makeSample('B', { cutoff: 16.9, onset: 0.95 });

    // 1. Current-level figure: width, white/no-grid, shared y, colors, arrows, footer.
    reset();
    A.cutoffShift = 0.10;
    B.onsetShift = 0.10;
    api.setSamples([A, B]);
    const figure = api.upsEnergyFigure(api.samples());
    assert.strictEqual(figure.width, 1100, '2-panel figure width');
    assert.strictEqual(figure.height, 540, 'energy figure height');
    assert.strictEqual(figure.layout.width, 1100, 'layout width');
    assert.strictEqual(figure.layout.paper_bgcolor, '#fff', 'white paper');
    assert.strictEqual(figure.layout.plot_bgcolor, '#fff', 'white plot area');
    assert.strictEqual(figure.layout.yaxis.showgrid, false, 'no y grid');
    assert.strictEqual(figure.layout.yaxis.domain[0], 0, 'shared y domain start');
    assert.strictEqual(figure.layout.yaxis.domain[1], 1, 'shared y domain end');
    assert.strictEqual(Object.keys(figure.layout).includes('yaxis2'), false, 'only one shared y axis');
    const axisKeys = Object.keys(figure.layout).filter(key => /^xaxis\d*$/.test(key));
    assert.strictEqual(axisKeys.length, 2, 'one x axis per panel');
    for (const key of axisKeys) assert.strictEqual(figure.layout[key].showgrid, false, 'no x grid');
    assert.strictEqual(figure.traces.length, 2, 'one anchor trace per panel');

    const rects = figure.layout.shapes.filter(shape => shape.type === 'rect');
    const perovskiteRects = rects.filter(shape => shape.fillcolor !== api.pcbmColor);
    const pcbmRects = rects.filter(shape => shape.fillcolor === api.pcbmColor);
    assert.deepStrictEqual(Array.from(perovskiteRects, shape => shape.fillcolor), ['#2876AD', '#C84845'], 'stable sample colors');
    assert.strictEqual(pcbmRects.length, 2, 'one PCBM band per panel');
    assert(pcbmRects.every(shape => shape.fillcolor === '#6E56A0'), 'PCBM color');
    const solid = figure.layout.shapes.filter(shape => shape.type === 'line' && shape.x0 === 0.28 && shape.line.width === 3);
    assert.deepStrictEqual(Array.from(solid, shape => shape.line.color), ['#2876AD', '#2876AD', '#C84845', '#C84845'], 'CBM/VBM use sample colors');
    const pcbmSolid = figure.layout.shapes.filter(shape => shape.type === 'line' && shape.x0 === 1.95 && shape.line.width === 3);
    assert.strictEqual(pcbmSolid.length, 4, 'LUMO/HOMO solid lines');
    const dashed = figure.layout.shapes.filter(shape => shape.type === 'line' && shape.line.dash === 'dash');
    assert.strictEqual(dashed.length, 2, 'one dashed EF per panel');
    assert.strictEqual(figure.layout.shapes.filter(shape => shape.type === 'line' && shape.y0 === 0 && shape.y1 === 0).length, 2, 'vacuum line per panel');
    assert.strictEqual(figure.layout.annotations.filter(annotation => annotation.showarrow).length, 2, 'one CBM-LUMO arrow per panel');
    const footer = figure.layout.annotations.filter(annotation => annotation.xref === 'paper');
    assert.strictEqual(footer.length, 0, '能级图不再带页脚说明文字');
    for (const sample of [A, B]) {
        const current = api.upsCurrentLevels(sample);
        const texts = figure.layout.annotations.map(annotation => annotation.text || '');
        assert(texts.includes(`${sample.name}: perovskite`), 'dynamic perovskite label');
        assert(texts.includes(`CBM: ${current.cbm.toFixed(2)} eV`), 'current CBM label');
        assert(texts.includes(`VBM: ${current.vbm.toFixed(2)} eV`), 'current VBM label');
        assert(texts.includes(`E<sub>F</sub>: ${current.ef.toFixed(2)} eV`), 'current EF label');
        assert(texts.includes(`E<sub>g</sub> = ${(current.cbm - current.vbm).toFixed(2)} eV`), 'current Eg label');
    }

    const reference = api.upsReferenceEnergyFigure(api.samples());
    const currentLevels = api.samples().map(api.upsCurrentLevels);
    assert.strictEqual(reference.height, 360, 'reference figure uses the confirmed height');
    assert.strictEqual(reference.layout.shapes.filter(shape => shape.y0 === 0 && shape.y1 === 0).length, 2, 'all samples share vacuum at 0 eV');
    for (const current of currentLevels) {
        for (const value of [current.cbm, current.ef, current.vbm]) {
            assert(reference.layout.shapes.some(shape => shape.y0 === value && shape.y1 === value), 'energy line stays at its actual numeric value');
        }
    }
    const workFunctionArrows = reference.layout.annotations.filter(annotation => annotation.showarrow);
    assert.deepStrictEqual(Array.from(workFunctionArrows, arrow => arrow.ay), [0, 0], 'work-function arrows start at the common vacuum level');
    assert.deepStrictEqual(Array.from(workFunctionArrows, arrow => arrow.y), currentLevels.map(level => level.ef), 'work-function arrows end at each actual EF');

    // 2. Shifted curve traces, markers, fit lines, and auto ranges.
    reset();
    A.cutoffShift = 0.10;
    B.onsetShift = 0.10;
    api.setSamples([A, B]);
    const baseFit = JSON.parse(JSON.stringify(A.fitResult));
    api.renderUPSResults();
    const lastCall = (id) => plotlyCalls.filter(call => call.id === id).pop();
    const aCut = lastCall('ups-curve-cutoff-0');
    const bCut = lastCall('ups-curve-cutoff-1');
    const aOnset = lastCall('ups-curve-onset-0');
    const bOnset = lastCall('ups-curve-onset-1');
    assert(aCut && bCut && aOnset && bOnset, 'each sample gets its own cutoff and onset panel');
    const curveOf = call => call.traces.find(trace => trace.mode === 'lines' && trace.meta);
    const fitOf = call => call.traces.find(trace => trace.mode === 'lines' && !trace.meta);
    const markerOf = call => call.traces.find(trace => trace.mode === 'markers');
    assert(curveOf(aCut).x.every(x => x >= 15.7 - 1e-9 && x <= 17.9 + 1e-9), 'A cutoff panel window follows the shifted edge');
    assert(markerOf(aCut).x[0] === 16.8, 'A cutoff marker uses current intersection');
    assert(markerOf(bCut).x[0] === 16.9, 'B cutoff marker stays at base intersection');
    assert(fitOf(aCut).x.some(x => Math.abs(x - 16.8) < 1e-9), 'A cutoff tangent includes shifted intersection');
    assert(markerOf(aOnset).x[0] === 0.8, 'A onset marker stays at base onset');
    assert(markerOf(bOnset).x[0] === 1.05, 'B onset marker includes onsetShift');
    assert(aCut.layout.xaxis.range[0] > aCut.layout.xaxis.range[1], 'cutoff axis remains reversed');
    assert(aCut.layout.xaxis.range[0] >= 16.8 && aCut.layout.xaxis.range[1] <= 16.8, 'cutoff window contains the shifted intercept');
    assert(aOnset.layout.xaxis.range[0] > aOnset.layout.xaxis.range[1], 'onset axis remains reversed');
    assert(aOnset.layout.xaxis.range[0] >= 0.8 && aOnset.layout.xaxis.range[1] <= 0.8, 'onset window contains the intercept');
    assert(aCut.layout.annotations.some(a => a.text === 'Cutoff'), 'panel labels the cutoff region');
    assert(aCut.layout.annotations.some(a => String(a.text).includes('Φ =')), 'cutoff panel shows the work function inline');
    assert.deepStrictEqual(A.fitResult, baseFit, 'plot rendering must not mutate fitted arrays');
    const summaryHtml = elements.get('ups-summary-table').innerHTML;
    assert(summaryHtml.includes(api.upsLevels(A).cutoff.toFixed(3)), 'summary needs the fitted cutoff');
    assert(!summaryHtml.includes(api.upsCurrentLevels(A).cutoff.toFixed(3)), 'summary must not substitute the current cutoff');

    // 3. XLSX round-trip: original sheets stay fitted; shifted sheets and sample columns move.
    reset();
    const workbookA = makeSample('A', { cutoff: 16.7, onset: 0.8 });
    const workbookB = makeSample('B', { cutoff: 16.9, onset: 0.95 });
    api.setSamples([workbookA, workbookB]);
    const zeroBook = roundtrip(api.buildUPSWorkbook(api.samples()));
    workbookA.cutoffShift = 0.10;
    workbookB.onsetShift = 0.10;
    const shiftedBook = roundtrip(api.buildUPSWorkbook(api.samples()));
    for (const sheet of ['Summary', 'Cutoff Plot', 'Onset Plot', 'Shifted Summary', 'Cutoff Plot Shifted', 'Onset Plot Shifted', 'Energy Levels', 'Method', 'A', 'B']) {
        assert(zeroBook.SheetNames.includes(sheet), `workbook must preserve/add ${sheet}`);
        assert(shiftedBook.SheetNames.includes(sheet), `workbook must preserve/add ${sheet}`);
    }
    for (const sheet of ['Summary', 'Cutoff Plot', 'Onset Plot']) {
        assert.deepStrictEqual(sheetRows(shiftedBook, sheet), sheetRows(zeroBook, sheet), `${sheet} must stay on original data`);
    }
    const shiftedSummary = sheetRows(shiftedBook, 'Shifted Summary');
    const shiftedHeaders = shiftedSummary[0];
    const shiftedA = shiftedSummary.find(row => row[0] === 'A');
    assert.deepStrictEqual(
        ['Ecutoff_eV', 'Eonset_eV', 'work_function_eV', 'EF_eV', 'VBM_eV', 'CBM_eV', 'cutoffShift_eV', 'onsetShift_eV'].map(name => shiftedA[shiftedHeaders.indexOf(name)]),
        [api.upsCurrentLevels(workbookA).cutoff, api.upsCurrentLevels(workbookA).onset, api.upsCurrentLevels(workbookA).workFunction, api.upsCurrentLevels(workbookA).ef, api.upsCurrentLevels(workbookA).vbm, api.upsCurrentLevels(workbookA).cbm, 0.10, 0],
        'Shifted Summary must expose current levels and both shifts'
    );
    const origCutoff = sheetRows(zeroBook, 'Cutoff Plot');
    const shiftedCutoff = sheetRows(shiftedBook, 'Cutoff Plot Shifted');
    const origCutoffHeaders = origCutoff[0], shiftedCutoffHeaders = shiftedCutoff[0];
    const aCutoffOrig = column(origCutoffHeaders, origCutoff.slice(1), 'A_energy_eV').filter(value => typeof value === 'number');
    const aCutoffShifted = column(shiftedCutoffHeaders, shiftedCutoff.slice(1), 'A_energy_eV').filter(value => typeof value === 'number');
    assert.strictEqual(aCutoffShifted.length, aCutoffOrig.length, 'shifted cutoff column length');
    for (let i = 0; i < aCutoffOrig.length; i++) approx(aCutoffShifted[i], aCutoffOrig[i] + 0.10, 'shifted cutoff energy');
    assert.deepStrictEqual(
        column(shiftedCutoffHeaders, shiftedCutoff.slice(1), 'A_normalized').filter(value => typeof value === 'number'),
        column(origCutoffHeaders, origCutoff.slice(1), 'A_normalized').filter(value => typeof value === 'number'),
        'shifted cutoff intensity shape unchanged'
    );
    const origOnset = sheetRows(zeroBook, 'Onset Plot');
    const shiftedOnset = sheetRows(shiftedBook, 'Onset Plot Shifted');
    const origOnsetHeaders = origOnset[0], shiftedOnsetHeaders = shiftedOnset[0];
    const bOnsetOrig = column(origOnsetHeaders, origOnset.slice(1), 'B_energy_eV').filter(value => typeof value === 'number');
    const bOnsetShifted = column(shiftedOnsetHeaders, shiftedOnset.slice(1), 'B_energy_eV').filter(value => typeof value === 'number');
    const bOnsetOrigNorm = column(origOnsetHeaders, origOnset.slice(1), 'B_normalized').filter(value => typeof value === 'number');
    const bOnsetShiftedNorm = column(shiftedOnsetHeaders, shiftedOnset.slice(1), 'B_normalized').filter(value => typeof value === 'number');
    const pairedOnset = bOnsetOrig.map((value, index) => ({ value, norm: bOnsetOrigNorm[index] })).filter(item => item.value + 0.10 <= 2.5 + 1e-9);
    assert(pairedOnset.length > 0, 'shifted onset must contain values within the window');
    for (let i = 0; i < pairedOnset.length; i++) {
        approx(bOnsetShifted[i], pairedOnset[i].value + 0.10, 'shifted onset energy');
        approx(bOnsetShiftedNorm[i], pairedOnset[i].norm, 'shifted onset intensity shape unchanged');
    }

    const sampleSheet = sheetRows(shiftedBook, 'A');
    const sampleHeaders = sampleSheet[0];
    const zeroSampleSheet = sheetRows(zeroBook, 'A');
    const zeroSampleHeaders = zeroSampleSheet[0];
    assert.strictEqual(new Set(sampleSheet.slice(1).map(row => row.length)).size, 1, 'sample sheet rows have one length');
    assert.strictEqual(sampleHeaders.length, sampleSheet[1].length, 'sample sheet header and row lengths match');
    const cOrig = column(sampleHeaders, sampleSheet.slice(1), 'cutoff_energy_original_eV').filter(value => typeof value === 'number');
    const cShift = column(sampleHeaders, sampleSheet.slice(1), 'cutoff_energy_shifted_eV').filter(value => typeof value === 'number');
    assert.strictEqual(cShift.length, cOrig.length, 'sample cutoff original/shifted lengths match');
    for (let i = 0; i < cOrig.length; i++) approx(cShift[i], cOrig[i] + 0.10, 'sample cutoff shifted energy');
    assert.deepStrictEqual(
        column(sampleHeaders, sampleSheet.slice(1), 'cutoff_intensity').filter(value => typeof value === 'number'),
        column(zeroSampleHeaders, zeroSampleSheet.slice(1), 'cutoff_intensity').filter(value => typeof value === 'number'),
        'sample cutoff intensity retained'
    );
    const tOrigX = column(sampleHeaders, sampleSheet.slice(1), 'cutoff_tangent_x_original_eV').filter(value => typeof value === 'number');
    const tShiftX = column(sampleHeaders, sampleSheet.slice(1), 'cutoff_tangent_x_shifted_eV').filter(value => typeof value === 'number');
    assert(tOrigX.length > 0 && tShiftX.length === tOrigX.length, 'sample tangent x arrays present and aligned');
    for (let i = 0; i < tOrigX.length; i++) approx(tShiftX[i], tOrigX[i] + 0.10, 'sample tangent x is shifted');

    const energyRows = sheetRows(shiftedBook, 'Energy Levels');
    const energyHeaders = energyRows[0];
    const energyA = energyRows.find(row => row[0] === 'A');
    assert.strictEqual(energyHeaders.includes('energyShift_eV'), false, 'legacy energyShift column must be absent');
    for (const name of ['original_Ecutoff_eV', 'original_Eonset_eV', 'original_Phi_eV', 'original_EF_eV', 'original_VBM_eV', 'original_CBM_eV', 'current_Ecutoff_eV', 'current_Eonset_eV', 'current_Phi_eV', 'current_EF_eV', 'current_VBM_eV', 'current_CBM_eV', 'Eg_eV', 'cutoffShift_eV', 'onsetShift_eV', 'PCBM_HOMO_eV', 'PCBM_LUMO_eV', 'signed_offset_eV']) {
        assert(energyHeaders.includes(name), `Energy Levels missing ${name}`);
    }
    const baseEnergy = api.upsLevels(workbookA), currentEnergy = api.upsCurrentLevels(workbookA);
    approx(energyA[energyHeaders.indexOf('original_Ecutoff_eV')], baseEnergy.cutoff, 'original cutoff in Energy Levels');
    approx(energyA[energyHeaders.indexOf('original_EF_eV')], baseEnergy.ef, 'original EF in Energy Levels');
    approx(energyA[energyHeaders.indexOf('current_Ecutoff_eV')], currentEnergy.cutoff, 'current cutoff in Energy Levels');
    approx(energyA[energyHeaders.indexOf('current_EF_eV')], currentEnergy.ef, 'current EF in Energy Levels');
    approx(energyA[energyHeaders.indexOf('cutoffShift_eV')], 0.10, 'cutoff shift in Energy Levels');
    approx(energyA[energyHeaders.indexOf('signed_offset_eV')], currentEnergy.cbm - (-3.90), 'current CBM-LUMO offset');

    // 4. Reverse edits return both current and XLSX values to the base.
    workbookA.cutoffShift = 0;
    workbookB.onsetShift = 0;
    const reversedBook = roundtrip(api.buildUPSWorkbook(api.samples()));
    const reversedEnergy = sheetRows(reversedBook, 'Energy Levels').find(row => row[0] === 'A');
    approx(reversedEnergy[energyHeaders.indexOf('current_Ecutoff_eV')], baseEnergy.cutoff, 'reverse cutoff current value');
    const reversedB = sheetRows(reversedBook, 'Energy Levels').find(row => row[0] === 'B');
    approx(reversedB[energyHeaders.indexOf('current_Eonset_eV')], api.upsLevels(workbookB).onset, 'reverse onset current value');
    assert.deepStrictEqual(sheetRows(reversedBook, 'Summary'), sheetRows(zeroBook, 'Summary'), 'Summary remains original after reverse');

    // 4b. Negative shifts produce -0.10 energy differences with unchanged intensity shape.
    workbookA.cutoffShift = -0.10;
    workbookB.onsetShift = -0.10;
    const negativeBook = roundtrip(api.buildUPSWorkbook(api.samples()));
    const negativeCutoff = sheetRows(negativeBook, 'Cutoff Plot Shifted');
    const negativeCutoffHeaders = negativeCutoff[0];
    const aCutoffNegative = column(negativeCutoffHeaders, negativeCutoff.slice(1), 'A_energy_eV').filter(value => typeof value === 'number');
    assert.strictEqual(aCutoffNegative.length, aCutoffOrig.length, 'negative shifted cutoff column length');
    for (let i = 0; i < aCutoffOrig.length; i++) approx(aCutoffNegative[i], aCutoffOrig[i] - 0.10, 'negative cutoff energy diff');
    const negativeOnset = sheetRows(negativeBook, 'Onset Plot Shifted');
    const negativeOnsetHeaders = negativeOnset[0];
    const bOnsetNegative = column(negativeOnsetHeaders, negativeOnset.slice(1), 'B_energy_eV').filter(value => typeof value === 'number');
    const bOnsetNegativeNorm = column(negativeOnsetHeaders, negativeOnset.slice(1), 'B_normalized').filter(value => typeof value === 'number');
    const pairedNegative = bOnsetOrig.map((value, index) => ({ value, norm: bOnsetOrigNorm[index] })).filter(item => item.value - 0.10 >= -1 - 1e-9);
    assert(pairedNegative.length > 0, 'negative shifted onset values present');
    for (let i = 0; i < pairedNegative.length; i++) {
        approx(bOnsetNegative[i], pairedNegative[i].value - 0.10, 'negative onset energy diff');
        approx(bOnsetNegativeNorm[i], pairedNegative[i].norm, 'negative onset intensity shape unchanged');
    }
    workbookA.cutoffShift = 0;
    workbookB.onsetShift = 0;

    // 5. Manual corrections are labelled, not presented as immutable fit.
    workbookA.manualLines = { cutoff: { points: [[16, 1], [16.5, 0]], intersection: 16.7 } };
    workbookA.intersections = { cutoff: 16.7, onset: 0.8 };
    const manualBook = roundtrip(api.buildUPSWorkbook([workbookA]));
    const manualSummary = sheetRows(manualBook, 'Summary');
    const manualSummaryHeaders = manualSummary[0];
    assert.strictEqual(manualSummary[1][manualSummaryHeaders.indexOf('cutoff_R2')], 'manual', 'manual cutoff must be labelled in Summary');
    const manualSheet = sheetRows(manualBook, 'A');
    const manualHeaders = manualSheet[0];
    assert.strictEqual(manualSheet[1][manualHeaders.indexOf('cutoff_tangent_source')], 'manual', 'manual tangent source must be labelled');

    // 6. Energy export uses the full N-panel width; theme wrapper keeps the energy plot white.
    reset();
    A.cutoffShift = 0.10;
    api.setSamples([A, B]);
    api.renderUPSResults();
    toImageCalls.length = 0;
    await api.exportUPSPlot('energy', 'png');
    assert.strictEqual(toImageCalls.length, 1, 'PNG export calls Plotly once');
    assert.strictEqual(toImageCalls[0].options.width, 904, 'PNG export uses the full adaptive 2-sample width');
    assert.strictEqual(toImageCalls[0].options.height, 360, 'PNG export uses the reference energy height');
    await api.exportUPSPlot('energy', 'svg');
    assert.strictEqual(toImageCalls[1].options.format, 'svg', 'SVG export format');
    assert.strictEqual(toImageCalls[1].options.width, 904, 'SVG export width');

    const energyRender = plotlyCalls.filter(call => call.id === 'ups-energy-ref').pop();
    const curveRender = plotlyCalls.filter(call => call.id.startsWith('ups-curve-cutoff')).pop();
    assert.strictEqual(energyRender.layout.paper_bgcolor, '#ffffff', 'energy plot keeps white paper');
    assert.strictEqual(energyRender.layout.font.color, '#111111', 'energy plot keeps black text');
    assert.strictEqual(energyRender.config.displayModeBar, false, 'energy plot has no mode bar');
    assert.strictEqual(energyRender.layout.dragmode, undefined, 'energy plot has no drag mode');
    assert.strictEqual(curveRender.layout.paper_bgcolor, '#ffffff', 'reference curves keep white paper');
    relayoutCalls.length = 0;
    restyleCalls.length = 0;
    localStorage.setItem('perovskite-workstation-appearance-v1', JSON.stringify({ mode: 'dark', accent: 'ocean' }));
    api.openSettings();
    assert(!relayoutCalls.some(call => call.id && call.id.startsWith('ups-curve-')), 'live theme must keep reference curves white');
    assert(!relayoutCalls.some(call => call.id === 'ups-energy-ref'), 'live theme must not relayout the energy plot');
    assert(!restyleCalls.some(call => call.id === 'ups-energy-ref'), 'live theme must not restyle the energy plot');
    assert.strictEqual(elements.get('ups-energy-ref').layout.paper_bgcolor, '#ffffff', 'energy plot stays white after dark mode');

    // 7. No legacy shift is exported anywhere.
    const allText = Object.values(shiftedBook.Sheets).map(sheet => XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' }).flat().join('|')).join('|');
    assert(!allText.includes('energyShift'), 'workbook must not export a stale energyShift');

    console.log('UPS linked stage2 energy/workbook checks passed');
}

run().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
