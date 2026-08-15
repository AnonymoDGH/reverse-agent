#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const windows = process.platform === 'win32';
const python = path.join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python');
const bunCandidates = windows
  ? [
      path.join(root, 'node_modules', 'bun', 'bin', 'bun.exe'),
      path.join(root, 'node_modules', '.bin', 'bun.exe'),
      path.join(root, 'node_modules', '.bin', 'bun.cmd'),
    ]
  : [path.join(root, 'node_modules', '.bin', 'bun')];
const bun = bunCandidates.find(existsSync);
const port = new URL(process.env.QWEN_REVERSE_BASE_URL || 'http://127.0.0.1:8090').port || '8090';
if (!existsSync(python)) {
  console.error('Falta el backend (qwen-reverse). Ejecuta: npm start');
  process.exit(1);
}
if (!bun) {
  console.error('Falta Bun. Ejecuta: npm start');
  process.exit(1);
}

const env = {
  ...process.env,
  QWEN_REVERSE: '1',
  QWEN_REVERSE_BASE_URL: process.env.QWEN_REVERSE_BASE_URL || `http://127.0.0.1:${port}`,
  ANTHROPIC_BASE_URL: process.env.QWEN_REVERSE_BASE_URL || `http://127.0.0.1:${port}`,
  ANTHROPIC_API_KEY: 'qwen-reverse',
  QWEN_MODEL: process.env.QWEN_MODEL || 'qwen3.8-max-thinking',
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: '1',
  CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS: '1',
  ENABLE_TOOL_SEARCH: 'false',
  DISABLE_TELEMETRY: '1',
  // Este fork corre sobre bun/npm desde el source, no con el "native installer".
  // Suprime la notificación de deprecación de npm que no aplica aquí.
  DISABLE_INSTALLATION_CHECKS: '1',
};

async function healthy() {
  try { return (await fetch(`${env.QWEN_REVERSE_BASE_URL}/health`, { signal: AbortSignal.timeout(1000) })).ok; }
  catch { return false; }
}

let server;
if (!(await healthy())) {
  server = spawn(python, ['-m', 'uvicorn', 'qwen_bridge:app', '--host', '127.0.0.1', '--port', port, '--no-access-log', '--log-level', 'warning'], {
    cwd: root, env, stdio: ['ignore', 'ignore', 'inherit'],
  });
  for (let i = 0; i < 80 && !(await healthy()); i++) {
    if (server.exitCode !== null) process.exit(server.exitCode || 1);
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  if (!(await healthy())) {
    server.kill();
    throw new Error('El servidor bridge (qwen-reverse) no inició en 20 segundos');
  }
}

const args = process.argv.slice(2);
// Si npm creó únicamente bun.cmd, debe ejecutarse a través de cmd.exe.
const bunIsCmd = windows && bun.toLowerCase().endsWith('.cmd');
const command = bunIsCmd ? (process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe') : bun;
const commandArgs = bunIsCmd
  ? ['/d', '/s', '/c', `"${bun}" run src/entry.ts ${args.map(arg => `"${arg.replaceAll('"', '\\"')}"`).join(' ')}`]
  : ['run', 'src/entry.ts', ...args];
const child = spawn(command, commandArgs, { cwd: root, env, stdio: 'inherit' });
const stop = () => server?.kill('SIGTERM');
process.on('SIGINT', () => child.kill('SIGINT'));
process.on('SIGTERM', () => child.kill('SIGTERM'));
child.on('error', error => {
  stop();
  console.error(`No se pudo iniciar Bun: ${error.message}`);
  process.exit(1);
});
child.on('exit', code => { stop(); process.exit(code ?? 1); });
