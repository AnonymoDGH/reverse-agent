#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const windows = process.platform === 'win32';
const python = path.join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) {
  console.error('Falta el entorno Python del bridge. Ejecuta: npm run setup:backend');
  process.exit(1);
}
const result = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'tests_python', '-p', 'test_*.py'], {
  cwd: root,
  stdio: 'inherit',
});
process.exit(result.status ?? 1);
