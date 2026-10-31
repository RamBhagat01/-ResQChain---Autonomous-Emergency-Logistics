const { spawn } = require('child_process');
const path = require('path');

const rootDir = __dirname;
const isWin = process.platform === 'win32';
const npmCmd = isWin ? 'npm.cmd' : 'npm';

console.log('================================================================');
console.log('  ResQChain Swarm - Starting Full Local Environment');
console.log('================================================================');
console.log('  • Backend:  http://localhost:8000  (FastAPI)');
console.log('  • Frontend: http://localhost:5173  (React + Vite)');
console.log('================================================================\n');

// 1. Start Backend
const backend = spawn(npmCmd, ['run', 'dev'], {
  cwd: path.join(rootDir, 'backend'),
  stdio: 'inherit',
  shell: isWin,
});

// 2. Start Frontend
const frontend = spawn(npmCmd, ['run', 'dev'], {
  cwd: path.join(rootDir, 'frontend'),
  stdio: 'inherit',
  shell: isWin,
});

backend.on('error', (err) => console.error('Backend error:', err));
frontend.on('error', (err) => console.error('Frontend error:', err));

const cleanup = () => {
  try { backend.kill(); } catch (e) {}
  try { frontend.kill(); } catch (e) {}
  process.exit(0);
};

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

