const plotLog10 = values => values.map(v => v !== 0 ? Math.log10(Math.abs(v)) : null);

console.assert(JSON.stringify(plotLog10([1, 10, -100, 0])) === JSON.stringify([0, 1, 2, null]));
console.log('J-axis log10 display check passed');
