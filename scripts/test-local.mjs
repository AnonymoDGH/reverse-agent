#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const bun = path.join(root, 'node_modules', '.bin', process.platform === 'win32' ? 'bun.exe' : 'bun');
function run(code) {
  const result = spawnSync(bun, ['-e', code], { cwd: root, encoding: 'utf8' });
  if (result.status !== 0) {
    process.stderr.write(result.stdout || '');
    process.stderr.write(result.stderr || '');
    process.exit(result.status ?? 1);
  }
  process.stdout.write(result.stdout);
}
run("import {ripGrep} from './src/utils/ripgrep.ts'; const r=await ripGrep(['-n','DEFAULT_QWEN_MODEL'],'src/services/api',AbortSignal.timeout(10000)); if(!r.length)throw new Error('ripgrep sin resultados'); console.log('✓ ripgrep',r.length)");
run("import {getAllBaseTools} from './src/tools.ts'; const n=getAllBaseTools().length; if(n<20)throw new Error('registro de herramientas incompleto'); console.log('✓ herramientas',n)");
run("import {getDefaultOpusModel} from './src/utils/model/model.ts'; const m=getDefaultOpusModel(); if(!m.startsWith('qwen'))throw new Error('modelo predeterminado no es Qwen: '+m); console.log('✓ modelo',m)");
