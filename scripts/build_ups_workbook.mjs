import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const root = "E:/Vibe coding/Perovskite_PC";
const outDir = `${root}/outputs/ups_plot`;
const payload = JSON.parse(await fs.readFile(`${outDir}/ups_data.json`, "utf8"));
const bandGap = 1.56;

const wb = Workbook.create();
const fig = wb.worksheets.add("UPS图");
const calc = wb.worksheets.add("拟合计算");
const raw = wb.worksheets.add("原始数据");
const font = "Arial";
const colors = { A: "#159A75", B: "#2B77A8", dark: "#263238", light: "#E8EEF1" };

for (const sheet of [fig, calc, raw]) {
  sheet.showGridLines = false;
  sheet.getRange("A1:AZ900").format.font = { name: font, size: 10, color: colors.dark };
  sheet.getRange("A1:AZ900").format.verticalAlignment = "center";
}

// Raw source data, preserved as flat numeric tables.
raw.getRange("A1:H1").values = [[
  "A -5 V energy (eV)", "A -5 V intensity (counts/s)",
  "B -5 V energy (eV)", "B -5 V intensity (counts/s)",
  "A 0 V energy (eV)", "A 0 V intensity (counts/s)",
  "B 0 V energy (eV)", "B 0 V intensity (counts/s)"
]];
raw.getRange("A1:H1").format = {
  fill: "#37474F", font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center", wrapText: true,
};

const spectraOrder = ["A_m5V", "B_m5V", "A_0V", "B_0V"];
const maxRows = Math.max(...spectraOrder.map(k => payload.spectra[k].energy.length));
const rawRows = [];
for (let i = 0; i < maxRows; i++) {
  const row = [];
  for (const key of spectraOrder) {
    row.push(payload.spectra[key].energy[i] ?? null, payload.spectra[key].intensity[i] ?? null);
  }
  rawRows.push(row);
}
raw.getRange("A2").write(rawRows);
raw.getRange(`A2:H${maxRows + 1}`).format.numberFormat = "0.000";
raw.getRange("A:H").format.columnWidth = 20;
raw.getRange("A1:H1").format.rowHeight = 36;
raw.freezePanes.freezeRows(1);

// Auditable fit parameters and formula-based UPS results.
calc.getRange("A1:N1").values = [["UPS 拟合计算", null, null, null, null, null, null, null, null, null, null, null, null, null]];
calc.getRange("A1:N1").format = { font: { name: font, size: 14, bold: true, color: colors.dark } };
calc.getRange("A3:Q3").values = [[
  "样品", "光子能量 (eV)", "截止区基线", "截止斜率", "截止截距",
  "价带区基线", "价带斜率", "价带截距", "Ecutoff (eV)", "Eonset (eV)",
  "功函数 Φ (eV)", "VBM (eV)", "截止拟合 R²", "价带拟合 R²", "Eg (eV)", "CBM (eV)", "结果判断"
]];
calc.getRange("A3:N3").format = {
  fill: "#37474F", font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center", wrapText: true,
};
for (let i = 0; i < 2; i++) {
  const sample = i === 0 ? "A" : "B";
  const r = payload.results[sample];
  const row = 4 + i;
  calc.getRange(`A${row}:H${row}`).values = [[
    `Sample ${sample}`, payload.photon_energy_eV, r.cutoff_baseline, r.cutoff_slope, r.cutoff_intercept,
    r.onset_baseline, r.onset_slope, r.onset_intercept,
  ]];
  calc.getRange(`I${row}`).formulas = [[`=(C${row}-E${row})/D${row}`]];
  calc.getRange(`J${row}`).formulas = [[`=(F${row}-H${row})/G${row}`]];
  calc.getRange(`K${row}`).formulas = [[`=B${row}-I${row}`]];
  calc.getRange(`L${row}`).formulas = [[`=-(K${row}+J${row})`]];
  calc.getRange(`M${row}:N${row}`).values = [[r.cutoff_r2, r.onset_r2]];
  calc.getRange(`O${row}`).values = [[bandGap]];
  calc.getRange(`P${row}`).formulas = [[`=L${row}+O${row}`]];
  calc.getRange(`Q${row}`).values = [[sample === "A" ? "能级合理" : "能级偏浅，建议复核"]];
}
calc.getRange("B4:P5").format.numberFormat = "0.000";
calc.getRange("A3:Q5").format.borders = { preset: "outside", style: "thin", color: "#90A4AE" };
calc.getRange("A7:F7").values = [["样品", "截止拟合区间 (eV)", "价带拟合区间 (eV)", "截止基线区间 (eV)", "价带基线区间 (eV)", "说明"]];
calc.getRange("A7:F7").format = { fill: "#607D8B", font: { name: font, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
calc.getRange("A8:F9").values = [
  ["Sample A", "16.10–16.60", "1.00–2.00", "18.00–21.00", "−0.80–0.30", "线性区与基线交点"],
  ["Sample B", "16.20–16.70", "0.60–1.60", "18.00–21.00", "−0.80–0.30", "线性区与基线交点"],
];
calc.getRange("A:Q").format.columnWidth = 15;
calc.getRange("A:A").format.columnWidth = 13;
calc.getRange("F:F").format.columnWidth = 19;
calc.getRange("A3:N3").format.rowHeight = 42;

function selectedSeries(key, minX, maxX, descending = true) {
  const s = payload.spectra[key];
  let pairs = s.energy.map((x, i) => [x, s.intensity[i]]).filter(([x]) => x >= minX && x <= maxX);
  pairs.sort((a, b) => descending ? b[0] - a[0] : a[0] - b[0]);
  return pairs;
}

function plotRows(kind) {
  const isCutoff = kind === "cutoff";
  const suffix = isCutoff ? "m5V" : "0V";
  const minX = isCutoff ? 15 : -1;
  const maxX = isCutoff ? 18 : 2;
  const a = selectedSeries(`A_${suffix}`, minX, maxX);
  const b = selectedSeries(`B_${suffix}`, minX, maxX);
  const count = Math.min(a.length, b.length);
  const rows = [];
  for (let i = 0; i < count; i++) {
    const x = a[i][0];
    const ra = payload.results.A;
    const rb = payload.results.B;
    const ba = isCutoff ? ra.cutoff_baseline : ra.onset_baseline;
    const bb = isCutoff ? rb.cutoff_baseline : rb.onset_baseline;
    const sa = isCutoff ? ra.cutoff_scale : ra.onset_scale;
    const sb = isCutoff ? rb.cutoff_scale : rb.onset_scale;
    const ma = isCutoff ? ra.cutoff_slope : ra.onset_slope;
    const mb = isCutoff ? rb.cutoff_slope : rb.onset_slope;
    const ia = isCutoff ? ra.cutoff_intercept : ra.onset_intercept;
    const ib = isCutoff ? rb.cutoff_intercept : rb.onset_intercept;
    const wa = isCutoff ? ra.cutoff_window : ra.onset_window;
    const wbw = isCutoff ? rb.cutoff_window : rb.onset_window;
    rows.push([
      x,
      Math.max(0, (a[i][1] - ba) / sa),
      Math.max(0, (b[i][1] - bb) / sb),
      x >= wa[0] && x <= wa[1] ? (ma * x + ia - ba) / sa : null,
      x >= wbw[0] && x <= wbw[1] ? (mb * x + ib - bb) / sb : null,
      0,
    ]);
  }
  return rows;
}

const cutoffRows = plotRows("cutoff");
const onsetRows = plotRows("onset");
calc.getRange("A12:F12").values = [["Binding energy (eV)", "Sample A", "Sample B", "A linear fit", "B linear fit", "Baseline"]];
calc.getRange("A13").write(cutoffRows);
const onsetStart = 13 + cutoffRows.length + 3;
calc.getRange(`A${onsetStart}:F${onsetStart}`).values = [["Binding energy (eV)", "Sample A", "Sample B", "A linear fit", "B linear fit", "Baseline"]];
calc.getRange(`A${onsetStart + 1}`).write(onsetRows);
calc.getRange(`A12:F${onsetStart + onsetRows.length}`).format.numberFormat = "0.000";
calc.getRange("A12:F12").format = { fill: "#CFD8DC", font: { name: font, bold: true }, horizontalAlignment: "center" };
calc.getRange(`A${onsetStart}:F${onsetStart}`).format = { fill: "#CFD8DC", font: { name: font, bold: true }, horizontalAlignment: "center" };

// Reader-facing figure sheet.
fig.getRange("A2:AA2").values = [["UPS analysis of Sample A and Sample B", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
fig.getRange("A2:AA2").format = { font: { name: font, size: 14, bold: true, color: colors.dark }, borders: { bottom: { style: "thin", color: "#90A4AE" } } };
fig.getRange("A4:H4").values = [["样品", "Ecutoff (eV)", "Eonset (eV)", "功函数 Φ (eV)", "VBM (eV)", "Eg (eV)", "CBM (eV)", "判断"]];
fig.getRange("A4:H4").format = { fill: "#37474F", font: { name: font, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
fig.getRange("A5:H6").values = [["Sample A", null, null, null, null, bandGap, null, "能级合理"], ["Sample B", null, null, null, null, bandGap, null, "能级偏浅，建议复核"]];
fig.getRange("B5:E5").formulas = [["='拟合计算'!I4", "='拟合计算'!J4", "='拟合计算'!K4", "='拟合计算'!L4"]];
fig.getRange("B6:E6").formulas = [["='拟合计算'!I5", "='拟合计算'!J5", "='拟合计算'!K5", "='拟合计算'!L5"]];
fig.getRange("G5").formulas = [["='拟合计算'!P4"]];
fig.getRange("G6").formulas = [["='拟合计算'!P5"]];
fig.getRange("B5:G6").format.numberFormat = "0.00";
fig.getRange("A5:A5").format.font = { name: font, bold: true, color: colors.A };
fig.getRange("A6:A6").format.font = { name: font, bold: true, color: colors.B };
fig.getRange("A4:H6").format.borders = { preset: "outside", style: "thin", color: "#90A4AE" };
fig.getRange("H6").format = { fill: "#FFF3CD", font: { name: font, bold: true, color: "#8A5700" } };

const cutoffChart = fig.charts.add("line", calc.getRange(`A12:F${12 + cutoffRows.length}`));
cutoffChart.title = "Secondary electron cutoff";
cutoffChart.titleTextStyle.typeface = font;
cutoffChart.titleTextStyle.fontSize = 12;
cutoffChart.legend = { position: "top", textStyle: { typeface: font, fontSize: 9 } };
cutoffChart.xAxis = { axisType: "textAxis", tickLabelInterval: 10, textStyle: { typeface: font, fontSize: 9 } };
cutoffChart.yAxis = { numberFormatCode: "0.0", numberFormatSourceLinked: false, textStyle: { typeface: font, fontSize: 9 } };
cutoffChart.xAxis.title.text = "Binding energy (eV)";
cutoffChart.yAxis.title.text = "Normalized intensity (a.u.)";
cutoffChart.setPosition("A8", "I25");

const onsetChart = fig.charts.add("line", calc.getRange(`A${onsetStart}:F${onsetStart + onsetRows.length}`));
onsetChart.title = "Valence-band onset";
onsetChart.titleTextStyle.typeface = font;
onsetChart.titleTextStyle.fontSize = 12;
onsetChart.legend = { position: "top", textStyle: { typeface: font, fontSize: 9 } };
onsetChart.xAxis = { axisType: "textAxis", tickLabelInterval: 10, textStyle: { typeface: font, fontSize: 9 } };
onsetChart.yAxis = { numberFormatCode: "0.0", numberFormatSourceLinked: false, textStyle: { typeface: font, fontSize: 9 } };
onsetChart.xAxis.title.text = "Binding energy (eV)";
onsetChart.yAxis.title.text = "Normalized intensity (a.u.)";
onsetChart.setPosition("J8", "R25");

for (const chart of [cutoffChart, onsetChart]) {
  const series = chart.series.items;
  if (series[0]) series[0].line = { fill: colors.A, style: "solid", width: 2 };
  if (series[1]) series[1].line = { fill: colors.B, style: "solid", width: 2 };
  if (series[2]) series[2].line = { fill: colors.A, style: "dashed", width: 1.5 };
  if (series[3]) series[3].line = { fill: colors.B, style: "dashed", width: 1.5 };
  if (series[4]) series[4].line = { fill: "#546E7A", style: "dotted", width: 1 };
}

// Compact energy-level schematic, styled after the provided reference.
fig.getRange("T7:AA7").values = [["Energy-level diagram", null, null, null, null, null, null, null]];
fig.getRange("T7:AA7").format = { font: { name: font, size: 12, bold: true, color: colors.dark }, horizontalAlignment: "center" };
fig.getRange("T8:V20").merge();
fig.getRange("T8:V20").values = [["Sample A\nCBM  −4.08 eV\n\nEg  1.56 eV\n\nVBM  −5.64 eV"]];
fig.getRange("T8:V20").format = { fill: "#A8DCCB", font: { name: font, size: 13, bold: true, color: "#12372C" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "outside", style: "thin", color: "#7CB9A4" } };
fig.getRange("X6:Z20").merge();
fig.getRange("X6:Z20").values = [["Sample B\nCBM  −3.28 eV\n\nEg  1.56 eV\n\nVBM  −4.84 eV"]];
fig.getRange("X6:Z20").format = { fill: "#A8D3E8", font: { name: font, size: 13, bold: true, color: "#174A63" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "outside", style: "thin", color: "#6DAFCF" } };
fig.getRange("T21:V21").merge(); fig.getRange("T21:V21").formulas = [["='拟合计算'!L4"]];
fig.getRange("X21:Z21").merge(); fig.getRange("X21:Z21").formulas = [["='拟合计算'!L5"]];
fig.getRange("T21:Z21").format = { font: { name: font, size: 13, bold: true }, horizontalAlignment: "center", numberFormat: "0.00" };
fig.getRange("T23:V23").merge(); fig.getRange("T23:V23").formulas = [["='拟合计算'!K4"]];
fig.getRange("X23:Z23").merge(); fig.getRange("X23:Z23").formulas = [["='拟合计算'!K5"]];
fig.getRange("T22:V22").merge(); fig.getRange("T22:V22").values = [["Φ (eV)"]];
fig.getRange("X22:Z22").merge(); fig.getRange("X22:Z22").values = [["Φ (eV)"]];
fig.getRange("T22:Z23").format = { font: { name: font, size: 10 }, horizontalAlignment: "center", numberFormat: "0.00" };
fig.getRange("A27:AA27").values = [["Photon energy: He I, 21.22 eV. VBM = −(Φ + Eonset); CBM = VBM + Eg; Eg = 1.56 eV. Sample B is unusually shallow and should be rechecked.", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
fig.getRange("A27:AA27").format = { font: { name: font, size: 9, italic: true, color: "#546E7A" } };
fig.getRange("A:H").format.columnWidth = 14;
fig.getRange("H:H").format.columnWidth = 20;
fig.getRange("T:Z").format.columnWidth = 11;
fig.getRange("A4:H4").format.rowHeight = 28;

wb.recalculate();

const keyCheck = await wb.inspect({ kind: "table", range: "UPS图!A2:Z23", include: "values,formulas", tableMaxRows: 25, tableMaxCols: 26, maxChars: 5000 });
console.log(keyCheck.ndjson);
const errors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(errors.ndjson);

await fs.mkdir(outDir, { recursive: true });
const preview = await wb.render({ sheetName: "UPS图", range: "A1:AA27", scale: 1.5, format: "png" });
await fs.writeFile(`${outDir}/UPS_plot_preview.png`, new Uint8Array(await preview.arrayBuffer()));
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(`${outDir}/UPS_analysis.xlsx`);

console.log(`Saved ${outDir}/UPS_analysis.xlsx`);
console.log(`Saved ${outDir}/UPS_plot_preview.png`);
