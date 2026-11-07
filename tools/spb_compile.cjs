#!/usr/bin/env node
// Standalone SamPr Basic compiler runner using the VS Code extension compiler engine
const fs = require('fs');
const path = require('path');
const Module = require('module');

const origLoad = Module._load;
Module._load = function(request) {
  if (request === 'vscode') return {};
  return origLoad.apply(this, arguments);
};

const extPath = 'C:/Users/nicol/.vscode/extensions/fpracek.samprbasic-1.4.2/dist/extension.js';
const toolsDir = 'C:/Users/nicol/.vscode/extensions/fpracek.samprbasic-1.4.2/tools';

let extSrc = fs.readFileSync(extPath, 'utf8');
extSrc += '\n; module.exports.compile = compile;\n';

const extModule = new Module('sampr-ext');
extModule._compile(extSrc, 'sampr-ext.js');

const targetFile = process.argv[2] || 'JSW000.SPB';
const projectDir = path.resolve(process.argv[3] || '.');

console.log(`Compiling ${targetFile} in ${projectDir}...`);
const res = extModule.exports.compile(projectDir, toolsDir, targetFile);

console.log(`Compilation result: ok=${res.ok}, kind=${res.kind}, output=${res.output}`);
if (res.diagnostics && res.diagnostics.length > 0) {
  console.log('Diagnostics:');
  for (const d of res.diagnostics) {
    console.log(`  [${d.file}:${d.line}] Error ${d.code}: ${d.message}`);
  }
}
if (!res.ok) {
  process.exit(1);
}
