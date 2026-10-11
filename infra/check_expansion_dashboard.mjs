// Local, dependency-free Chromium/CDP interaction QA. No remote pages or paid calls.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const [chrome, htmlPath, outputDirectory] = process.argv.slice(2);
if (!chrome || !path.isAbsolute(htmlPath ?? '') || !outputDirectory) {
  throw Error('Require existing Chromium path, absolute local HTML path, and fresh output directory');
}
// Refuse to mix this receipt with another render or overwrite prior screenshots.
fs.mkdirSync(outputDirectory);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'olens-expansion-qa-'));
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const report = {
  checked_utc: new Date().toISOString(), local_html: htmlPath,
  data_path: path.join(path.dirname(htmlPath), 'expansion-data.json'),
  scope: 'Local browser interaction QA reads saved published aggregate original/full/test/development/pilot and new available results. No raw sealed records, remote page, paid calls, installation, or publication.',
  checks: [], screenshots: [], errors: [], remote_requests: [],
};
report.data_sha256 = sha256(report.data_path);
report.source_hashes = JSON.parse(fs.readFileSync(report.data_path, 'utf8')).source_hashes;
report.javascript_sha256 = sha256(path.join(path.dirname(htmlPath), 'expansion.js'));
const child = spawn(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu',
  '--disable-dev-shm-usage', '--disable-background-networking', '--disable-component-update',
  '--disable-sync', '--no-first-run', '--no-default-browser-check', '--metrics-recording-only',
  '--disable-features=OptimizationHints,MediaRouter', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'],
{stdio: ['ignore', 'ignore', 'pipe']});
let stderr = '', socket, sessionId, nextId = 0, deadline;
const pending = new Map();
child.stderr.on('data', buffer => {stderr = (stderr + buffer.toString()).slice(-20000);});
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function command(method, params = {}, session = sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {pending.delete(id); reject(Error(`CDP timeout: ${method}`));}, 10000);
    pending.set(id, {resolve, reject, timer});
    socket.send(JSON.stringify({id, method, params, ...(session ? {sessionId: session} : {})}));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description ?? 'Browser evaluation failed');
  return result.result.value;
}
function check(name, result) {
  report.checks.push({name, ...result});
  if (!result.pass) report.errors.push(name);
}
async function screenshot(name) {
  const result = await command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
  const file = path.join(outputDirectory, `${name}.png`);
  fs.writeFileSync(file, Buffer.from(result.data, 'base64'), {flag: 'wx'});
  report.screenshots.push(file);
}
async function viewport(width, mobile) {
  await command('Emulation.setDeviceMetricsOverride', {width, height: 1000, deviceScaleFactor: 1, mobile});
}
async function overflow(name) {
  check(name, await evaluate(`(() => {
    const width = document.documentElement.clientWidth;
    const offenders = [...document.querySelectorAll('main *')].filter(node => {
      if (node.closest('.table-wrap') || node.closest('svg') || !node.getClientRects().length) return false;
      const rect = node.getBoundingClientRect();
      return rect.right > width + 1 || rect.left < -1;
    }).map(node => ({tag:node.tagName,id:node.id,right:node.getBoundingClientRect().right}));
    return {pass:document.documentElement.scrollWidth <= width + 1, width,
      scrollWidth:document.documentElement.scrollWidth,offenders};
  })()`));
}
async function run() {
  const portPath = path.join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 60 && !fs.existsSync(portPath); i++) await sleep(100);
  if (!fs.existsSync(portPath)) throw Error('Chromium did not publish its debugging port');
  const [port, wsPath] = fs.readFileSync(portPath, 'utf8').trim().split('\n');
  socket = new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('CDP connection timeout')), 5000);
    socket.onopen = () => {clearTimeout(timer); resolve();};
    socket.onerror = () => {clearTimeout(timer); reject(Error('CDP connection failed'));};
  });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') report.errors.push(message.params.exceptionDetails.text);
    if (message.method === 'Network.requestWillBeSent' && !/^(file:|data:|about:)/.test(message.params.request.url)) {
      report.remote_requests.push(message.params.request.url);
    }
    const operation = pending.get(message.id);
    if (!operation) return;
    clearTimeout(operation.timer);
    pending.delete(message.id);
    if (message.error) operation.reject(Error(message.error.message)); else operation.resolve(message.result);
  };
  const {targetId} = await command('Target.createTarget', {url: 'about:blank'}, null);
  ({sessionId} = await command('Target.attachToTarget', {targetId, flatten: true}, null));
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Network.enable');
  await viewport(1280, false);
  const navigation = await command('Page.navigate', {url: pathToFileURL(htmlPath).href});
  if (navigation.errorText) throw Error(navigation.errorText);
  for (let i = 0; i < 50; i++) {
    if (await evaluate(`document.readyState === 'complete' && document.querySelectorAll('#matrix [data-group]').length > 0`)) break;
    await sleep(100);
  }
  check('initial matrix, four curves, capped default', await evaluate(`({
    pass:document.querySelectorAll('#matrix [data-group]').length === 7 &&
      document.querySelectorAll('#scaling svg').length === 4 && element('reference').value === defaultReference,
    groups:document.querySelectorAll('#matrix [data-group]').length, curves:document.querySelectorAll('#scaling svg').length,
    conditions:data.conditions.length, status:element('status').textContent
  })`));
  await overflow('desktop overview has no page overflow');
  await screenshot('desktop-overview');
  check('expand all 70 settings and all detail task graphs', await evaluate(`(() => {
    element('expand-all').click();
    const buttons = [...document.querySelectorAll('#matrix [data-condition]')];
    const failures = [];
    for (const button of buttons) {
      button.click();
      const id = button.dataset.condition;
      if (!element('detail').open || document.querySelectorAll('#detail-content .detail-grid article').length !== 4) failures.push(id);
      for (const family of families) {
        const graph = document.querySelector('#detail-content [data-task="' + family + '"] svg');
        const measured = metric(id, family)?.value != null;
        const interval = metric(id, family)?.ci95;
        if (!graph || (graph.dataset.measured === 'true') !== measured ||
          (measured && !graph.querySelector('circle.estimate')) ||
          (measured && interval && !graph.querySelector('line.interval')) ||
          (!measured && graph.querySelector('circle.estimate'))) failures.push(id + ':' + family);
      }
      element('close-detail').click();
      if (element('detail').open) failures.push(id + ':close');
    }
    return {pass:buttons.length === 70 && !failures.length,settings:buttons.length,failures};
  })()`));
  check('cohort, paired view, actual comparison references', await evaluate(`(() => {
    const results = [];
    for (const name of Object.keys(data.cohorts)) {
      element('cohort').value = name; element('cohort').dispatchEvent(new Event('change'));
      const expected = [...new Set((data.cohorts[name].comparisons ?? []).filter(row =>
        !row.scope || row.scope === 'original_item' || row.scope === 'original_grid')
        .map(row => row.reference ?? row.baseline_condition))].sort();
      const actual = [...element('reference').options].filter(option => !option.disabled).map(option => option.value).sort();
      for (const view of ['rates','change']) {
        element('view').value = view; element('view').dispatchEvent(new Event('change'));
        const cells = document.querySelectorAll('#matrix [data-condition]').length;
        results.push({cohort:name,view,settings:cells,refs:actual.length,pass:cells === 70 &&
          JSON.stringify(expected) === JSON.stringify(actual) && element('reference').disabled === !expected.length &&
          document.querySelectorAll('#scaling svg').length === 4});
      }
    }
    element('cohort').value = 'test'; element('cohort').dispatchEvent(new Event('change'));
    const parent = [...element('reference').options].find(option => !option.disabled && option.value === 'prune_loo_a32_0.005-n32');
    if (parent) {element('reference').value = parent.value; element('reference').dispatchEvent(new Event('change'));}
    const parentAccessible = Boolean(parent) && element('reference').value === parent.value;
    element('cohort').value = 'full'; element('cohort').dispatchEvent(new Event('change'));
    element('reference').value = defaultReference; element('reference').dispatchEvent(new Event('change'));
    return {pass:results.every(result => result.pass) && parentAccessible,results,parentAccessible};
  })()`));
  await screenshot('desktop-paired');
  check('ordinary wording search aliases', await evaluate(`(() => {
    const results = ['pooling','OMP','orthogonal matching pursuit','consensus','repeated statements'].map(query => {
      element('search').value=query; element('search').dispatchEvent(new Event('input'));
      const ids=[...document.querySelectorAll('#matrix [data-condition]')].map(button => button.dataset.condition);
      return {query,matches:ids.length,pass:ids.length > 0};
    });
    element('search').value=''; element('search').dispatchEvent(new Event('input'));
    return {pass:results.every(result=>result.pass) && results[1].matches===results[2].matches,results};
  })()`));
  check('paired bootstrap warnings are visible', await evaluate(`(() => {
    const failures=[];let checked=0;
    for(const [name,current] of Object.entries(data.cohorts)) {
      const warnings=(current.comparisons ?? []).filter(row=>row.warning &&
        (!row.scope || row.scope==='original_item' || row.scope==='original_grid'));
      element('cohort').value=name; element('cohort').dispatchEvent(new Event('change'));
      for(const row of warnings) {
        element('reference').value=row.reference ?? row.baseline_condition;
        element('reference').dispatchEvent(new Event('change'));detail(row.condition);
        if(!element('detail-content').textContent.includes(row.warning)) failures.push(row.condition+':'+row.family);
        checked++;element('close-detail').click();
      }
    }
    element('cohort').value='full';element('cohort').dispatchEvent(new Event('change'));
    element('reference').value=defaultReference;element('reference').dispatchEvent(new Event('change'));
    return {pass:checked>0 && !failures.length,checked,failures};
  })()`));
  check('undefined rate labels and valid zero (synthetic endpoint edge cases only)', await evaluate(`(() => {
    const row=cohort().rows.find(row=>row.family==='hallucination');const original=row.metric;
    row.metric={...original,value:null,denominator:0,ci95:null};render();detail(row.condition);
    const undefinedGraph=document.querySelector('[data-task="hallucination"] svg');
    const undefinedPass=document.querySelector('[data-task="hallucination"] strong').textContent==='No specific readouts' &&
      !undefinedGraph.querySelector('circle.estimate');element('close-detail').click();
    row.metric={...original,value:0,denominator:1,numerator:0,ci95:[0,0]};detail(row.condition);
    const zeroPass=document.querySelector('[data-task="hallucination"] strong').textContent==='0.0%' &&
      Boolean(document.querySelector('[data-task="hallucination"] svg circle.estimate'));
    element('close-detail').click();row.metric=original;render();
    return {pass:undefinedPass && zeroPass,undefinedPass,zeroPass};
  })()`));
  check('tradeoff axes, intervals, group highlight, click', await evaluate(`(() => {
    const results=[];
    for(const family of families.slice(1)) {
      element('tradeoff-family').value=family; element('tradeoff-family').dispatchEvent(new Event('change'));
      const points=[...document.querySelectorAll('.tradeoff-point')];
      const expected=data.conditions.filter(condition => metric(condition.condition_id,family)?.value != null &&
        metric(condition.condition_id,'hallucination')?.value != null).length;
      const bars=points.every(point => (!metric(point.dataset.condition,family)?.ci95 || point.querySelector('.horizontal-interval')) &&
        (!metric(point.dataset.condition,'hallucination')?.ci95 || point.querySelector('.vertical-interval')));
      results.push({family,points:points.length,pass:points.length===expected && bars});
    }
    element('tradeoff-group').value='selection'; element('tradeoff-group').dispatchEvent(new Event('change'));
    const first=document.querySelector('.tradeoff-point');
    const faint=[...document.querySelectorAll('.tradeoff-point')].some(point=>point.getAttribute('opacity')==='0.28');
    const bright=[...document.querySelectorAll('.tradeoff-point')].some(point=>point.getAttribute('opacity')==='0.95');
    first.dispatchEvent(new PointerEvent('pointerenter')); const hovered=first.getAttribute('opacity')==='1';
    first.dispatchEvent(new PointerEvent('pointerleave'));
    first.dispatchEvent(new MouseEvent('click')); const clicked=element('detail').open;
    element('close-detail').click();
    first.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'})); const keyboard=element('detail').open;
    element('close-detail').click();
    return {pass:results.every(result=>result.pass)&&faint&&bright&&hovered&&clicked&&keyboard,results,faint,bright,hovered,clicked,keyboard};
  })()`));
  await evaluate(`element('tradeoff').scrollIntoView({block:'center'})`);
  await screenshot('desktop-tradeoff');
  await evaluate(`element('view').value='rates';element('view').dispatchEvent(new Event('change'));document.querySelector('#matrix [data-condition]').click()`);
  await screenshot('desktop-method-dialog');
  await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await command('Input.dispatchKeyEvent', {type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  check('native Escape closes modal', {pass:await evaluate(`!element('detail').open`)});
  await viewport(390, true);
  await evaluate(`scrollTo(0,0)`);
  await overflow('mobile overview has no page overflow');
  await screenshot('mobile-overview');
  await evaluate(`element('tradeoff').scrollIntoView({block:'center'})`);
  await screenshot('mobile-tradeoff');
  check('all 70 mobile dialogs contain their content', await evaluate(`(() => {
    const failures=[];
    for(const button of document.querySelectorAll('#matrix [data-condition]')) {
      button.click();
      const modal=element('detail');
      if(modal.scrollWidth>modal.clientWidth+1) failures.push({id:button.dataset.condition,width:modal.clientWidth,scrollWidth:modal.scrollWidth});
      element('close-detail').click();
    }
    return {pass:!failures.length,failures};
  })()`));
  await evaluate(`document.querySelector('#matrix [data-condition]').click()`);
  await screenshot('mobile-method-dialog');
  await evaluate(`element('close-detail').click();element('view').value='change';element('view').dispatchEvent(new Event('change'))`);
  await overflow('mobile paired controls have no page overflow');
  check('contained comparison table permits horizontal scrolling', await evaluate(`(() => {
    const table=document.querySelector('.table-wrap'); return {pass:table.scrollWidth>table.clientWidth &&
      getComputedStyle(table).overflowX==='auto',clientWidth:table.clientWidth,scrollWidth:table.scrollWidth};
  })()`));
  // Only status is overridden here; scientific data remain the saved aggregate.
  check('complete_exploratory status branch (synthetic status only)', await evaluate(`(() => {
    const embedded=element('embedded-data');const original=JSON.parse(embedded.textContent);
    embedded.textContent=JSON.stringify({...original,status:'complete_exploratory'});
    return start().then(()=>({pass:element('status').textContent==='Expanded comparison complete'}));
  })()`));
  check('no remote browser requests', {pass:!report.remote_requests.length,urls:report.remote_requests});
}
try {
  await Promise.race([run(),new Promise((_,reject)=>{
    deadline=setTimeout(()=>reject(Error('Overall QA deadline: 120 seconds')),120000);
  })]);
} catch (error) {
  report.errors.push(error.stack);
} finally {
  clearTimeout(deadline);
  for(const operation of pending.values()) clearTimeout(operation.timer);
  socket?.close();child.kill('SIGTERM');
  await Promise.race([new Promise(resolve=>child.once('exit',resolve)),sleep(1500)]);
  if(child.exitCode===null) child.kill('SIGKILL');
  fs.rmSync(profile,{recursive:true,force:true});
  fs.writeFileSync(path.join(outputDirectory,'browser-stderr.log'),stderr,{flag:'wx'});
  report.pass=!report.errors.length;
  fs.writeFileSync(path.join(outputDirectory,'interaction.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify(report));
  if(!report.pass) process.exitCode=1;
}
