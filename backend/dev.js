const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const isWin = process.platform === 'win32';
const backendDir = __dirname;
const rootDir = path.resolve(backendDir, '..');

// Find Python / Uvicorn executable
let uvicornCmd = 'uvicorn';
let uvicornArgs = ['app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload', '--app-dir', backendDir];

const venvUvicornWin = path.join(backendDir, 'venv', 'Scripts', 'uvicorn.exe');
const venvPythonWin = path.join(backendDir, 'venv', 'Scripts', 'python.exe');
const venvUvicornUnix = path.join(backendDir, 'venv', 'bin', 'uvicorn');

if (isWin && fs.existsSync(venvUvicornWin)) {
  uvicornCmd = venvUvicornWin;
  uvicornArgs = ['app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload', '--app-dir', backendDir];
} else if (isWin && fs.existsSync(venvPythonWin)) {
  uvicornCmd = venvPythonWin;
  uvicornArgs = ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload', '--app-dir', backendDir];
} else if (!isWin && fs.existsSync(venvUvicornUnix)) {
  uvicornCmd = venvUvicornUnix;
  uvicornArgs = ['app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload', '--app-dir', backendDir];
}

// Kill existing process on port 8000 if stuck on Windows
if (isWin) {
  try {
    const netstatOut = execSync('netstat -ano | findstr :8000', { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] });
    const lines = netstatOut.split('\n').filter(Boolean);
    const pids = new Set();
    for (const line of lines) {
      if (line.includes('LISTENING')) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== '0') pids.add(pid);
      }
    }
    for (const pid of pids) {
      try {
        process.stdout.write(`Freeing port 8000 from stale process PID ${pid}...\n`);
        execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' });
      } catch (e) {}
    }
  } catch (e) {
    // Port was free
  }
}

console.log(`\n🚀 Starting ResQChain FastAPI Backend on http://localhost:8000...`);
console.log(`Executable: ${uvicornCmd}\n`);

const child = spawn(uvicornCmd, uvicornArgs, {
  cwd: backendDir,
  stdio: 'inherit',
  shell: isWin,
  env: {
    ...process.env,
    PYTHONPATH: backendDir,
  },
});

child.on('error', (err) => {
  console.error('Failed to start uvicorn:', err.message);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code || 0);
});

['SIGINT', 'SIGTERM'].forEach((sig) => {
  process.on(sig, () => {
    child.kill(sig);
    process.exit(0);
  });
});

