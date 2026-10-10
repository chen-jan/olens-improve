// One bounded Chromium/CDP render of the local reviewed dashboard. No remote page.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const [chrome, htmlPath, outputDirectory] = process.argv.slice(2);
if (!chrome || !htmlPath || !outputDirectory || !path.isAbsolute(htmlPath)) {
  throw new Error('Require Chromium path, absolute local HTML path, and output directory');
}
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'olens-dashboard-cdp-'));
fs.mkdirSync(outputDirectory, {recursive: true});
let stderr = '', socket, nextId = 0;
const pending = new Map();
const child = spawn(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu',
  '--disable-dev-shm-usage', '--disable-background-networking', '--disable-component-update',
  '--disable-sync', '--no-first-run', '--no-default-browser-check', '--metrics-recording-only',
  '--disable-features=OptimizationHints,MediaRouter', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], {stdio: ['ignore', 'ignore', 'pipe']});
child.stderr.on('data', b => {stderr = (stderr + b.toString()).slice(-20000);});
const sleep = ms => new Promise(r => setTimeout(r, ms));
function command(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {pending.delete(id); reject(new Error(`CDP timeout: ${method}`));}, 7000);
    pending.set(id, {resolve, reject, timer});
    socket.send(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}));
  });
}
let deadline;
try {
  await Promise.race([
    (async () => {
      const portPath = path.join(profile, 'DevToolsActivePort');
      for (let i = 0; i < 60 && !fs.existsSync(portPath); i++) await sleep(100);
      if (!fs.existsSync(portPath)) throw new Error('Chrome did not publish a debugging port within 6 seconds');
      const [port, wsPath] = fs.readFileSync(portPath, 'utf8').trim().split('\n');
      socket = new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
      await new Promise((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('CDP handshake timeout')), 5000);
        socket.onopen = () => {clearTimeout(t); resolve();};
        socket.onerror = () => {clearTimeout(t); reject(new Error('CDP connection failed'));};
      });
      socket.onmessage = e => {
        const r = JSON.parse(e.data); const p = pending.get(r.id);
        if (!p) return;
        clearTimeout(p.timer); pending.delete(r.id);
        if (r.error) p.reject(new Error(r.error.message)); else p.resolve(r.result);
      };
      const {targetId} = await command('Target.createTarget', {url: 'about:blank'});
      const {sessionId} = await command('Target.attachToTarget', {targetId, flatten: true});
      await command('Page.enable', {}, sessionId);
      await command('Emulation.setDeviceMetricsOverride', {width: 1280, height: 1600, deviceScaleFactor: 1, mobile: false}, sessionId);
      const navigation = await command('Page.navigate', {url: pathToFileURL(htmlPath).href}, sessionId);
      if (navigation.errorText) throw new Error(navigation.errorText);
      await sleep(1000);
      const {result} = await command('Runtime.evaluate', {expression: 'JSON.stringify({title:document.title,ready:document.readyState,width:innerWidth,height:innerHeight,scrollHeight:document.documentElement.scrollHeight,svgCount:document.querySelectorAll("svg").length})', returnByValue: true}, sessionId);
      const page = JSON.parse(result.value);
      if (page.ready !== 'complete') throw new Error(`Local page not complete: ${page.ready}`);
      const {data} = await command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false}, sessionId);
      const screenshot = path.join(outputDirectory, 'desktop.png');
      fs.writeFileSync(screenshot, Buffer.from(data, 'base64'), {flag: 'wx'});
      const report = {checked_utc: new Date().toISOString(), local_html: htmlPath, screenshot, page,
        scope: 'Local browser render only. No validation/test artifact opened, network page, or publication.'};
      fs.writeFileSync(path.join(outputDirectory, 'render.json'), JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
      console.log(JSON.stringify(report));
    })(),
    new Promise((_, reject) => {deadline = setTimeout(() => reject(new Error('Overall render deadline: 35 seconds')), 35000);}),
  ]);
} finally {
  clearTimeout(deadline);
  for (const p of pending.values()) {clearTimeout(p.timer); p.reject(new Error('Browser closing'));}
  socket?.close();
  child.kill('SIGTERM');
  await Promise.race([new Promise(resolve => child.once('exit', resolve)), sleep(1500)]);
  if (child.exitCode === null) child.kill('SIGKILL');
  fs.writeFileSync(path.join(outputDirectory, 'browser-stderr.log'), stderr, {flag: 'wx'});
}
