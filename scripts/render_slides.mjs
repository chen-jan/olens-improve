// Local HTML-mirror PDF through bounded Chromium/CDP. No remote page.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const [chrome, htmlPath, pdfPath] = process.argv.slice(2);
if (!chrome || !path.isAbsolute(htmlPath || '') || !path.isAbsolute(pdfPath || '') || fs.existsSync(pdfPath)) {
  throw new Error('Require Chromium, absolute local input and a new PDF path');
}
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'olens-slides-cdp-'));
const child = spawn(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
  '--disable-background-networking', '--disable-component-update', '--disable-sync', '--no-first-run',
  '--no-default-browser-check', '--metrics-recording-only', '--disable-features=OptimizationHints,MediaRouter',
  '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost', '--remote-debugging-port=0',
  `--user-data-dir=${profile}`, 'about:blank'], {stdio:['ignore','ignore','pipe']});
let stderr = '', socket, nextId = 0, deadline;
child.stderr.on('data', b => {stderr = (stderr+b.toString()).slice(-20000);});
const pending = new Map();
const sleep = ms => new Promise(r => setTimeout(r, ms));
function command(method, params={}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {pending.delete(id);reject(new Error('CDP timeout: '+method));}, 10000);
    pending.set(id,{resolve,reject,timer});
    socket.send(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})}));
  });
}
try {
  await Promise.race([(async () => {
    const portPath=path.join(profile,'DevToolsActivePort');
    for(let i=0;i<60&&!fs.existsSync(portPath);i++)await sleep(100);
    if(!fs.existsSync(portPath))throw new Error('Chrome startup deadline');
    const [port,wsPath]=fs.readFileSync(portPath,'utf8').trim().split('\n');
    socket=new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('CDP handshake deadline')),5000);socket.onopen=()=>{clearTimeout(timer);resolve();};socket.onerror=()=>{clearTimeout(timer);reject(new Error('CDP connection failed'));};});
    socket.onmessage=e=>{const r=JSON.parse(e.data),p=pending.get(r.id);if(!p)return;clearTimeout(p.timer);pending.delete(r.id);if(r.error)p.reject(new Error(r.error.message));else p.resolve(r.result);};
    const version=await command('Browser.getVersion');
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},sessionId);
    const navigation=await command('Page.navigate',{url:pathToFileURL(htmlPath).href},sessionId);
    if(navigation.errorText)throw new Error(navigation.errorText);
    await sleep(1000);
    const {result}=await command('Runtime.evaluate',{expression:'document.readyState',returnByValue:true},sessionId);
    if(result.value!=='complete')throw new Error('Slide page did not finish loading');
    const {data}=await command('Page.printToPDF',{printBackground:true,displayHeaderFooter:false,
      preferCSSPageSize:true,paperWidth:13+1/3,paperHeight:7.5,marginTop:0,marginBottom:0,marginLeft:0,marginRight:0},sessionId);
    fs.writeFileSync(pdfPath,Buffer.from(data,'base64'),{flag:'wx'});
    fs.writeFileSync(path.join(path.dirname(pdfPath),'pdf-render-engine.json'),JSON.stringify({engine:version.product,
      route:'Local HTML mirror via CDP, not native PowerPoint rendering',checked_utc:new Date().toISOString()},null,2)+'\n',{flag:'wx'});
  })(),new Promise((_,reject)=>{deadline=setTimeout(()=>reject(new Error('Overall PDF render deadline')),35000);})]);
} finally {
  clearTimeout(deadline);
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error('Browser closing'));}
  socket?.close();child.kill('SIGTERM');
  await Promise.race([new Promise(r=>child.once('exit',r)),sleep(1500)]);
  if(child.exitCode===null)child.kill('SIGKILL');
  fs.writeFileSync(path.join(path.dirname(pdfPath),'chromium-stderr.log'),stderr,{flag:'wx'});
}
