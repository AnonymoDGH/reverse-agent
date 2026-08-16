#!/usr/bin/env node
/**
 * Localiza un ejecutable de Bun REAL.
 *
 * El paquete npm "bun" instala primero un placeholder diminuto
 * (bin/bun.exe, ~450 bytes) que su postinstall reemplaza por el binario
 * real. Si la instalación se interrumpe (Ctrl+C), el placeholder queda
 * ahí y parece que Bun está instalado, pero ejecutarlo falla con
 * "spawn UNKNOWN". Por eso:
 *   1. Un candidato local solo vale si es un shim .cmd/.ps1 o pesa >= 100 KB.
 *   2. Como respaldo se busca el binario real en los paquetes de
 *      plataforma @oven/bun-<os>-<arch>, que npm extrae siempre aunque
 *      el postinstall no haya corrido.
 *   3. Último recurso: un bun global en el PATH.
 *
 * Uso como módulo:  import { findBun, bunNeedsRepair, repairBun } from './find-bun.mjs'
 * Uso directo:      node scripts/find-bun.mjs   (imprime la ruta o sale 1)
 */
import { existsSync, statSync, copyFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

/** Tamaño mínimo para considerar que un binario no es el placeholder. */
const MIN_REAL_SIZE = 100_000;

function platformCandidates(root) {
  const platform = process.platform;
  const arch = process.arch;
  const binName = platform === 'win32' ? 'bun.exe' : 'bun';
  const oven = (...names) =>
    names.map(name => path.join(root, 'node_modules', '@oven', name, 'bin', binName));
  if (platform === 'win32') {
    return oven(
      arch === 'arm64' ? 'bun-windows-aarch64' : 'bun-windows-x64',
      'bun-windows-x64',
      'bun-windows-x64-baseline',
      'bun-windows-aarch64',
    );
  }
  if (platform === 'darwin') {
    return oven('bun-darwin-aarch64', 'bun-darwin-x64', 'bun-darwin-x64-baseline');
  }
  if (platform === 'linux') {
    return oven(
      arch === 'arm64' ? 'bun-linux-aarch64' : 'bun-linux-x64',
      'bun-linux-x64',
      'bun-linux-x64-baseline',
      'bun-linux-aarch64',
      'bun-linux-aarch64-baseline',
      'bun-linux-x64-musl',
      'bun-linux-x64-musl-baseline',
    );
  }
  return [];
}

/** Orden de preferencia de shims en Windows (menor = mejor). */
function scoreWindows(p) {
  const lower = p.toLowerCase();
  if (lower.endsWith('.exe')) return 0;
  if (lower.endsWith('.cmd')) return 1;
  if (lower.endsWith('.ps1')) return 2;
  return 3;
}

function isRealBinary(candidate) {
  try {
    return statSync(candidate).size >= MIN_REAL_SIZE;
  } catch {
    return false;
  }
}

/**
 * Devuelve { path, isCmd } del primer Bun ejecutable, o null.
 */
export function findBun(root) {
  const windows = process.platform === 'win32';
  const binName = windows ? 'bun.exe' : 'bun';
  const candidates = [
    path.join(root, 'node_modules', 'bun', 'bin', binName),
    path.join(root, 'node_modules', '.bin', binName),
    ...(windows ? [path.join(root, 'node_modules', '.bin', 'bun.cmd')] : []),
    ...platformCandidates(root),
  ];
  for (const candidate of candidates) {
    if (!existsSync(candidate)) continue;
    const lower = candidate.toLowerCase();
    if (lower.endsWith('.cmd') || lower.endsWith('.ps1')) {
      return { path: candidate, isCmd: true };
    }
    if (isRealBinary(candidate)) {
      return { path: candidate, isCmd: false };
    }
  }
  // Último recurso: bun global en el PATH.
  const which = spawnSync(windows ? 'where' : 'which', ['bun'], { encoding: 'utf8' });
  if (which.status === 0) {
    const entries = (which.stdout || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    // En Windows 'where' puede devolver primero el shim POSIX sin extensión,
    // que no es ejecutable con spawn; preferir .exe/.cmd/.ps1.
    const ranked = windows
      ? entries.sort((a, b) => scoreWindows(a) - scoreWindows(b))
      : entries;
    for (const entry of ranked) {
      if (!existsSync(entry)) continue;
      const lower = entry.toLowerCase();
      if (windows && !lower.endsWith('.exe') && !lower.endsWith('.cmd') && !lower.endsWith('.ps1')) {
        continue; // shim POSIX sin extensión: no ejecutable en Windows
      }
      return { path: entry, isCmd: lower.endsWith('.cmd') };
    }
  }
  return null;
}

/**
 * ¿El bun local es el placeholder roto? (existe el paquete bun pero el
 * binario es diminuto y no hay shim .cmd funcional)
 */
export function bunNeedsRepair(root) {
  const windows = process.platform === 'win32';
  const binName = windows ? 'bun.exe' : 'bun';
  const placeholder = path.join(root, 'node_modules', 'bun', 'bin', binName);
  if (!existsSync(placeholder)) return false;
  if (isRealBinary(placeholder)) return false;
  // Existe el placeholder: ¿hay un binario real de @oven para reparar?
  return platformCandidates(root).some(existsSync);
}

/**
 * Repara una instalación rota de bun. El postinstall oficial (install.js)
 * a veces no puede resolver el paquete de plataforma, así que primero se
 * intenta copiar el binario real directamente desde @oven/bun-<os>-<arch>.
 * Si eso falla, se cae al postinstall. Devuelve true si quedó un binario real.
 */
export function repairBun(root) {
  const windows = process.platform === 'win32';
  const binName = windows ? 'bun.exe' : 'bun';
  const target = path.join(root, 'node_modules', 'bun', 'bin', binName);
  // 1) Copia directa del binario real del paquete de plataforma.
  const source = platformCandidates(root).find(p => existsSync(p) && isRealBinary(p));
  if (source) {
    try {
      copyFileSync(source, target);
      console.log('▶ Bun reparado: binario real copiado desde @oven.');
      return true;
    } catch {
      // seguir con el postinstall
    }
  }
  // 2) Postinstall oficial.
  const script = path.join(root, 'node_modules', 'bun', 'install.js');
  if (!existsSync(script)) return false;
  console.log('▶ Reparando la instalación local de Bun (postinstall)…');
  const result = spawnSync(process.execPath, [script], { cwd: root, stdio: 'inherit' });
  return result.status === 0;
}

// Modo CLI: node scripts/find-bun.mjs
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = path.resolve(import.meta.dirname, '..');
  if (bunNeedsRepair(root)) {
    repairBun(root);
  }
  const found = findBun(root);
  if (found) {
    console.log(found.path);
  } else {
    console.error('No se encontró un binario de Bun ejecutable.');
    process.exit(1);
  }
}
