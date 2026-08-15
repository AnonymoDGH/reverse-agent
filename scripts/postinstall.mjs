#!/usr/bin/env node
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const dir = path.join(root, 'node_modules', 'bundle');
mkdirSync(dir, { recursive: true });
writeFileSync(path.join(dir, 'package.json'), JSON.stringify({ name: 'bundle', version: '0.0.1', type: 'module', main: 'index.js' }));
writeFileSync(path.join(dir, 'index.js'), `// Polyfill multiplataforma de bun:bundle.\nconst enabled = new Set((process.env.QWEN_CODE_FEATURES || '').split(',').filter(Boolean));\nexport const feature = name => enabled.has(name);\n`);
console.log('✓ Polyfill bun:bundle instalado');
