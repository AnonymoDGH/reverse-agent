#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const windows = process.platform === 'win32';

function available(command, args = []) {
  const result = spawnSync(command, [...args, '--version'], { stdio: 'ignore' });
  return result.status === 0;
}

const candidates = [];
if (process.env.PYTHON) candidates.push({ command: process.env.PYTHON, args: [] });
if (windows) candidates.push({ command: 'py', args: ['-3'] }, { command: 'python', args: [] });
else candidates.push({ command: 'python3', args: [] }, { command: 'python', args: [] });
const host = candidates.find(item => available(item.command, item.args));
if (!host) {
  console.error('No se encontró Python 3.10 o superior. Instálalo desde https://python.org y vuelve a ejecutar npm start.');
  process.exit(1);
}

const venv = path.join(root, '.venv');
if (!existsSync(venv)) {
  console.log('Preparando el entorno Python…');
  const created = spawnSync(host.command, [...host.args, '-m', 'venv', '.venv'], { cwd: root, stdio: 'inherit' });
  if (created.status !== 0) process.exit(created.status ?? 1);
}
const python = path.join(venv, windows ? 'Scripts/python.exe' : 'bin/python');
console.log('Instalando/validando qwen-reverse…');
const installed = spawnSync(python, ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements.txt'], { cwd: root, stdio: 'inherit' });
process.exit(installed.status ?? 1);
