// Local HTML-mirror PDF through bounded Chromium/CDP. No remote page.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const [chrome, htmlPath, reportPath] = process.argv.slice(2);
if (!chrome || !path.isAbsolute(htmlPath || '') || !path.isAbsolute(reportPath || '') || fs.existsSync(reportPath)) {
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
    const checks=[];
    const content=await command('Runtime.evaluate',{expression:`(()=>{const d=JSON.parse(document.querySelector('#target-only-data').textContent),examples=d.methods.flatMap(m=>m.examples||[]),cards=d.resources?.cards||[];return {expectedCards:cards.length,cards:document.querySelectorAll('.resource-card').length,expectedExamples:examples.length,findings:document.querySelectorAll('.example-finding').length,exampleDetailsCollapsed:[...document.querySelectorAll('.example > details')].every(e=>!e.open),exactTextInsideDisclosure:[...document.querySelectorAll('.example-columns')].every(e=>!!e.closest('details')),reconstructionMeansPresent:[...(d.resources?.baseline_reconstruction||[]).map(r=>r.mean_fve),...Object.values(d.resources?.search_diagnostics||{}).flatMap(rows=>Object.values(rows).map(r=>r.saved_numeric_fields?.['fits.exact.fve']?.mean))].filter(Number.isFinite).every(v=>document.querySelector('#resources').textContent.includes((100*v).toFixed(2)+'%')),resourceText:document.querySelector('#resources').textContent.slice(0,2000)}})()`,returnByValue:true},sessionId);
    if(content.exceptionDetails)throw Error('Content rendering failed');
    const c=content.result.value;
    if(c.cards!==c.expectedCards||c.findings!==c.expectedExamples||!c.exampleDetailsCollapsed||!c.exactTextInsideDisclosure||!c.reconstructionMeansPresent)throw Error('Resource cards or visible example findings failed');
    checks.push({content:c});
    for (const width of [1440,390]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600},sessionId);
      for (const view of ['rates','original','parent']) {
        const expression=`(()=>{document.querySelector('#view').value=${JSON.stringify(view)};document.querySelector('#view').dispatchEvent(new Event('change'));return {view:document.querySelector('#view').value,charts:document.querySelectorAll('#charts svg').length,warnings:document.querySelectorAll('.chart-warnings').length,pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,rows:document.querySelectorAll('#method-table tr').length,referenceLabels:[...document.querySelectorAll('#charts svg text')].filter(e=>e.textContent.includes('Original released Oracle')).length,status:document.querySelector('#run-status').textContent}})()`;
        const result=await command('Runtime.evaluate',{expression,returnByValue:true},sessionId);
        if(result.exceptionDetails)throw Error('Dashboard script failed');
        const value=result.result.value;
        if(value.charts!==4||value.rows!==10||value.pageWidth>width+2)throw Error('Missing charts/methods or horizontal overflow: '+JSON.stringify(value));
        checks.push({width,...value});
      }
      const interaction=await command('Runtime.evaluate',{expression:`(()=>{document.querySelector('#method').value='bounded_prune_refill_005-n32';document.querySelector('#method').dispatchEvent(new Event('change'));document.querySelector('[data-family]').click();const opened=document.querySelector('#chart-dialog').open;const enlarged=!!document.querySelector('#dialog-chart svg');document.querySelector('#close-chart').click();document.querySelectorAll('details.wide').forEach(d=>d.open=true);return {opened,enlarged,closed:!document.querySelector('#chart-dialog').open,overflow:document.documentElement.scrollWidth>innerWidth+2}})()`,returnByValue:true},sessionId);
      if(interaction.exceptionDetails||!interaction.result.value.opened||!interaction.result.value.enlarged||!interaction.result.value.closed||interaction.result.value.overflow)throw Error('Interactive chart or disclosure failed');
      checks.push({width,interaction:interaction.result.value});
      await command('Runtime.evaluate',{expression:`document.querySelectorAll('details.wide').forEach(d=>d.open=false);document.querySelector('#method').value='all';document.querySelector('#view').value='rates';document.querySelector('#view').dispatchEvent(new Event('change'));`,returnByValue:true},sessionId);
      const screenshot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sessionId);
      fs.writeFileSync(path.join(path.dirname(reportPath),'dashboard-'+width+'.png'),Buffer.from(screenshot.data,'base64'),{flag:'wx'});
    }
    fs.writeFileSync(reportPath,JSON.stringify({status:'pass',checks,engine:version.product,hosted_rendering_verified:false},null,2)+'\n',{flag:'wx'});
    return;
  })(),new Promise((_,reject)=>{deadline=setTimeout(()=>reject(new Error('Overall PDF render deadline')),35000);})]);
} finally {
  clearTimeout(deadline);
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error('Browser closing'));}
  socket?.close();child.kill('SIGTERM');
  await Promise.race([new Promise(r=>child.once('exit',r)),sleep(1500)]);
  if(child.exitCode===null)child.kill('SIGKILL');
  fs.writeFileSync(path.join(path.dirname(reportPath),'layout-chromium-stderr.log'),stderr,{flag:'wx'});
}
