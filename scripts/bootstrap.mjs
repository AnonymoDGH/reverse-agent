#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const windows = process.platform === 'win32';
const python = path.join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python');

function bunCandidates() {
  return windows
    ? [
        path.join(root, 'node_modules', 'bun', 'bin', 'bun.exe'),
        path.join(root, 'node_modules', '.bin', 'bun.exe'),
        path.join(root, 'node_modules', '.bin', 'bun.cmd'),
      ]
    : [path.join(root, 'node_modules', '.bin', 'bun')];
}
function hasBun() { return bunCandidates().some(existsSync); }

const major = Number(process.versions.node.split('.')[0]);
if (major < 20) {
  console.error(`Se requiere Node.js 20 o superior (actual: ${process.version}). Descarga: https://nodejs.org`);
  process.exit(1);
}

function run(command, args, label, options = {}) {
  console.log(`\n▶ ${label}`);
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    env: process.env,
    ...options,
  });
  if (result.error) {
    console.error(`${label}: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!hasBun()) {
  // En Windows, spawnSync('npm.cmd', ...) puede fallar con EINVAL. npm start
  // expone la ruta real de npm-cli.js en npm_execpath; ejecutarla con Node
  // evita por completo los shims .cmd y funciona igual en las tres plataformas.
  const npmCli = process.env.npm_execpath;
  if (npmCli && existsSync(npmCli)) {
    run(process.execPath, [npmCli, 'install', '--no-audit', '--no-fund'], 'Instalando dependencias TypeScript y Bun');
  } else if (windows) {
    const comspec = process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe';
    run(comspec, ['/d', '/s', '/c', 'npm install --no-audit --no-fund'], 'Instalando dependencias TypeScript y Bun', { windowsHide: false });
  } else {
    run('npm', ['install', '--no-audit', '--no-fund'], 'Instalando dependencias TypeScript y Bun');
  }
}

if (!hasBun()) {
  console.error('npm terminó, pero no se encontró el ejecutable de Bun. Borra node_modules y vuelve a ejecutar npm start.');
  process.exit(1);
}

let qwenReady = false;
if (existsSync(python)) {
  const check = spawnSync(python, ['-c', 'import qwen_reverse, multipart'], { cwd: root, stdio: 'ignore' });
  qwenReady = check.status === 0;
}
if (!qwenReady) {
  run(process.execPath, ['scripts/setup-qwen.mjs'], 'Preparando qwen-reverse');
}

run(process.execPath, ['scripts/prepare-config.mjs'], 'Preparando la configuración local');
run(process.execPath, ['scripts/qwen-run.mjs', ...process.argv.slice(2)], 'Abriendo Qwen Code');
