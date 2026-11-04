const fs = require('fs');
const assert = require('assert');
const html = fs.readFileSync('src/index.html', 'utf8');
const backend = fs.readFileSync('build_exe.py', 'utf8');

assert(/id="file-bin-txt"\s+multiple\s+accept="\.bin"/.test(html), 'BIN converter must accept multiple BIN files');
assert(html.includes('function formatBinAsTxt(data, sourceName)'), 'BIN conversion must have a testable formatter');
assert(html.includes("file.name.replace(/\\.bin$/i,'.txt')"), 'converted files must keep their base names');
assert(html.includes('save_text_files_python(converted,failed)'), 'converted TXT files and failures must be sent to the desktop backend');
assert(backend.includes('def save_text_files_python(self, files, failures=None):'), 'desktop backend must save converted TXT files and failure reports');
assert(backend.includes('while os.path.exists(candidate):'), 'existing TXT files must not be overwritten');
assert(html.includes('选择文件夹（递归）'), 'BIN converter must expose recursive folder selection');
assert(html.includes('function convertBinFolders()'), 'folder conversion must report progress in the UI');
assert(backend.includes('def convert_bin_folders_python(self):'), 'desktop backend must convert folders recursively');
assert(backend.includes('for current_dir, _, filenames in os.walk(source_dir):'), 'folder conversion must scan nested folders');
assert(backend.includes("os.path.relpath(current_dir, source_dir)"), 'folder conversion must preserve relative folders');
assert(backend.includes("'BIN转换失败记录.txt'"), 'failed conversions must create a TXT report');

assert(html.includes("view.getFloat32(853,true)"), 'LSV start potential must come from the CHI header');
assert(html.includes("view.getFloat32(857,true)"), 'LSV target potential must come from the CHI header');
assert(html.includes("view.getFloat32(885,true)"), 'LSV step must come from the CHI header');
assert(html.includes("dataOffset!==1453"), 'unsupported BIN layouts must be rejected instead of producing garbage');
console.log('BIN to TXT checks passed');
