const assert = require('assert');
const fs = require('fs');

const html = fs.readFileSync('src/index.html', 'utf8');
assert(html.includes('id="update-dialog"'), 'update dialog must exist');
assert(html.includes('check_update_python'), 'frontend must start an asynchronous update check');
assert(html.includes('download_update_python'), 'frontend must start a download');
assert(html.includes('launch_update_python'), 'frontend must launch the verified updater');
assert(html.includes('updateHasUnsavedData'), 'frontend must guard unsaved data');
assert(html.includes('updateTaskRunning'), 'frontend must guard running tasks');
console.log('update UI checks passed');
