const fs = require('fs');

const content = fs.readFileSync('src/app/page.js', 'utf8');

const formatBytesFunc = `
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
`;

let newContent = content.replace('function totalBytes(fileList) {\n  return fileList.reduce((sum, file) => sum + file.size, 0);\n}\n', 'function totalBytes(fileList) {\n  return fileList.reduce((sum, file) => sum + file.size, 0);\n}\n' + formatBytesFunc);

newContent = newContent.replace(
  "{files.length} file{files.length === 1 ? '' : 's'} selected",
  "{files.length} file{files.length === 1 ? '' : 's'} selected ({formatBytes(totalBytes(files))})"
);

newContent = newContent.replace(
  "<span>{file.name}</span>",
  "<span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: '1rem', flex: 1 }} title={file.name}>{file.name} <span style={{ color: 'var(--text-muted)', fontSize: '0.9em' }}>({formatBytes(file.size)})</span></span>"
);

// We need to add flex: 1 to make the span take remaining space so truncation works.
// Also disable the Merge button if total size > 4 MB?
// Wait, they can already see the error. But maybe we can change the disabled state of the Merge button?
newContent = newContent.replace(
  "disabled={files.length === 0 || isMerging}",
  "disabled={files.length === 0 || isMerging || totalBytes(files) > MAX_REQUEST_BYTES}"
);

newContent = newContent.replace(
  "aria-busy={isMerging}",
  "aria-busy={isMerging}\n          title={totalBytes(files) > MAX_REQUEST_BYTES ? 'Total size exceeds 4 MB limit' : ''}"
);

fs.writeFileSync('src/app/page.js', newContent);
