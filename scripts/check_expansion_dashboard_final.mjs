// Final-only source-bound dashboard browser QA. Local Chromium/CDP; no remote page or inference.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const supplied=process.argv.slice(2), options={};
const names=new Set(['chrome','html','report','review','native','reconstruction','effort','qualitative-notes','inventory','native-state','reconstruction-state','qualitative-state','original-whole','original-report']);
for(let i=0;i<supplied.length;i++) {
  const flag=supplied[i];
  if(flag==='--preflight'){if(options.preflight)throw Error('Duplicate preflight flag');options.preflight=true;continue;}
  const key=flag.startsWith('--')?flag.slice(2):'';
  if(!names.has(key)||key in options||!supplied[i+1]||supplied[i+1].startsWith('--'))throw Error('Unknown, duplicate or incomplete option: '+flag);
  options[key]=supplied[++i];
}
for(const key of ['chrome','html','report','review','native','reconstruction','effort','qualitative-notes','inventory'])if(!options[key])throw Error('Required final input --'+key);
const chrome=options.chrome,htmlPath=path.resolve(options.html),reportPath=path.resolve(options.report);
if(!path.isAbsolute(options.html)||!path.isAbsolute(options.report)||fs.existsSync(reportPath))throw Error('Require absolute HTML/report and a new report path');
const inputPins={};
const hash=b=>createHash('sha256').update(b).digest('hex');
function requireTrue(value,message){if(!value)throw Error(message);}
function readInput(p){p=path.resolve(p);requireTrue(fs.existsSync(p)&&fs.statSync(p).isFile(),'Missing immutable source: '+p);const bytes=fs.readFileSync(p);inputPins[p]=hash(bytes);return JSON.parse(bytes);}
function rawPin(p){p=path.resolve(p);requireTrue(fs.existsSync(p)&&fs.statSync(p).isFile(),'Missing immutable source: '+p);inputPins[p]=hash(fs.readFileSync(p));return inputPins[p];}
function canonical(v){if(Array.isArray(v))return v.map(canonical);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])]));return v;}
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
const review=readInput(options.review);
requireTrue(review.status==='root_reviewed'&&!review.synthetic_layout_fixture,'Final root review is absent, unreviewed or synthetic');
const inventory=readInput(options.inventory),inventorySha=inputPins[path.resolve(options.inventory)];
requireTrue(inventory.status==='sealed'&&review.manifest_sha256===inventorySha,'Final frozen manifest authority differs');
const active=inventory.conditions.filter(r=>['cached_selector_full_bank','scheduled_full_bank'].includes(r.status));
const activeIds=new Set(active.map(r=>r.condition_id)),families=['hallucination','multihop_mt','chain_intermediates','role_bound_association'];
requireTrue(active.length===70&&activeIds.size===70&&inventory.families.length===families.length,'Require exact sealed70 by four families');
const intended=active.length*families.length;
const native=readInput(options.native),nativeSha=inputPins[path.resolve(options.native)];
requireTrue(native.status==='complete_exploratory'&&!native.synthetic_layout_fixture&&native.manifest_sha256===inventorySha&&review.results_sha256===nativeSha,'Native source is not exact reviewed terminal final');
requireTrue(native.complete_condition_families.length===intended&&native.missing_condition_families.length===0&&native.cohorts.full.comparison_family_complete,'Incomplete final native grids/contrast family');
const nativeState=readInput(options['native-state']||'.state/expanded-final-native-v1.service.json');
requireTrue(nativeState.status==='complete_pending_root_review'&&nativeState.scientific_inputs_validated_complete===true&&nativeState.output_sha256===nativeSha,'Native gate is not terminal or differs from retained source');
const nativeReceipt=readInput(path.join(nativeState.snapshot,'receipt.json'));
requireTrue(inputPins[path.resolve(path.join(nativeState.snapshot,'receipt.json'))]===nativeState.receipt_sha256&&nativeReceipt.status==='sealed_all280_terminal_inputs'&&nativeReceipt.descriptor_count===32&&nativeReceipt.condition_family_count===intended,'Native canonical32 receipt differs');
function uniqueRows(rows,label){const map=new Map();for(const r of rows){const key=r.condition+'|'+r.family;requireTrue(activeIds.has(r.condition)&&families.includes(r.family)&&!map.has(key),'Foreign/duplicate '+label);map.set(key,r);}requireTrue(map.size===intended,'Incomplete '+label);return map;}
const nativeRows=uniqueRows(native.cohorts.full.rows,'native rows');
const declared=new Set(inventory.headline_comparison_family.flatMap(p=>families.map(f=>p.condition+'|'+p.reference+'|'+f)));
requireTrue(declared.size===inventory.headline_comparison_family.length*families.length,'Duplicate frozen contrasts');
const nativeComparisons=new Map();for(const c of native.cohorts.full.comparisons){const k=c.condition+'|'+c.reference+'|'+c.family;requireTrue(declared.has(k)&&!nativeComparisons.has(k),'Duplicate/off-menu native comparison');nativeComparisons.set(k,c);}
requireTrue(nativeComparisons.size===declared.size,'Missing declared final comparisons');
const reconstruction=readInput(options.reconstruction),reconstructionSha=inputPins[path.resolve(options.reconstruction)];
requireTrue(['complete_secondary_diagnostic','partial_secondary_diagnostic'].includes(reconstruction.status)&&!reconstruction.synthetic_layout_fixture&&reconstruction.manifest_sha256===inventorySha&&reconstruction.quality_analysis_sha256===nativeSha&&review.reconstruction_sha256===reconstructionSha,'Unbound reconstruction source');
requireTrue(reconstruction.objective==='1-squared_residual/squared_target'&&reconstruction.solver==='scipy_exact'&&reconstruction.vector_contract_sha256===inventory.vector_contract.sha256,'Reconstruction objective/vector contract differs');
uniqueRows(reconstruction.rows,'reconstruction rows');requireTrue(reconstruction.rows.every(r=>r.missing_selection_sites===0),'Reconstruction selection source is incomplete');
const reconstructionState=readInput(options['reconstruction-state']||'.state/expanded-final-reconstruction-v1.service.json');
requireTrue(reconstructionState.status==='complete_pending_root_review'&&reconstructionState.output_sha256===reconstructionSha&&reconstructionState.quality_analysis_sha256===nativeSha,'Reconstruction gate not terminal/bound');
const effort=readInput(options.effort),effortSha=inputPins[path.resolve(options.effort)];
requireTrue(effort.status==='complete_retrospective'&&!effort.synthetic_layout_fixture&&effort.manifest_sha256===inventorySha&&review.effort_sha256===effortSha&&same(Object.keys(effort.method_effort).sort(),[...activeIds].sort()),'Effort source is partial, foreign or unreviewed');
const effortReceipt=readInput(path.join(path.dirname(options.effort),'receipt.json'));
requireTrue(effortReceipt.status==='terminal_effort_sealed_pending_root_review'&&effortReceipt.effort_sha256===effortSha&&effortReceipt.native.sha256===nativeSha,'Effort terminal receipt differs');
const notes=readInput(options['qualitative-notes']),notesSha=inputPins[path.resolve(options['qualitative-notes'])];
requireTrue(notes.status==='all_fresh_and_inherited_reviews_validated'&&notes.eligible_for_complete_final_public_notes===true&&notes.pending_partitions.length===0&&notes.analysis_sha256===nativeSha&&notes.manifest_sha256===inventorySha,'Final qualitative notes are absent, nonterminal or incomplete');
requireTrue(notes.new_case_notes.length===notes.required_new_case_reference_count&&notes.reviewed_new_case_reference_count===notes.required_new_case_reference_count,'Final qualitative reference count differs');
requireTrue(new Set(notes.new_case_notes.map(n=>JSON.stringify(canonical(n.source_reference)))).size===notes.new_case_notes.length,'Duplicate final qualitative references');
requireTrue((review.review_sources||[]).some(s=>path.resolve(s.path)===path.resolve(options['qualitative-notes'])&&s.sha256===notesSha),'Root review does not bind exact final qualitative notes');
for(const s of review.review_sources||[])requireTrue(rawPin(s.path)===s.sha256,'Root review source pin differs: '+s.path);
const qualitativeState=readInput(options['qualitative-state']||'.state/expanded-final-qualitative-v1.service.json');
requireTrue(qualitativeState.status==='prepared_pending_final_human_reviews'&&qualitativeState.analysis_sha256===nativeSha&&qualitativeState.condition_families===intended,'Final qualitative producer not terminal/bound');
for(const [p,digest]of Object.entries(qualitativeState.outputs))requireTrue(rawPin(p)===digest,'Terminal qualitative output changed: '+p);
const packs=new Map();for(const s of review.qualitative_sources||[]){const pack=readInput(s.path);requireTrue(inputPins[path.resolve(s.path)]===s.sha256&&pack.manifest_sha256===inventorySha,'Qualitative source pin/menu differs');packs.set(s.sha256,pack);}
requireTrue([...packs.values()].some(p=>p.analysis_sha256===nativeSha&&Object.keys(p.conditions).length===active.length),'No final full-cohort qualitative pack in reviewed sources');
const expectedExamples={},caseKeys=new Set();
for(const [condition,items]of Object.entries(review.dashboard_examples||{})){
 requireTrue(activeIds.has(condition)&&Array.isArray(items),'Foreign dashboard example condition');expectedExamples[condition]=[];
 for(const item of items){const pack=packs.get(item.source_sha256);requireTrue(pack,'Example source not pinned by root review');const own=pack.conditions[condition]?.families[item.family]?.[item.kind];requireTrue(own&&families.includes(item.family)&&['fixed_anchor','outcome_selected'].includes(item.kind),'Example family/policy missing');const found=own.filter(c=>c.cell_id===item.cell_id);requireTrue(found.length===1,'Missing/ambiguous example');const c=found[0],reference=item.reference??c.baseline_condition;let before,endpoint;
  if(c.parents&&reference in c.parents){const parent=c.parents[reference];requireTrue(parent.status==='complete','Example parent not complete');before=parent.output;endpoint=parent.endpoint_evidence;}
  else if(c.parents&&reference===c.original_baseline_condition){before=c.original_baseline;endpoint=c.endpoint_evidence;}
  else{requireTrue(!c.parents&&reference===c.baseline_condition,'Example reference lacks actual evidence');before=c.baseline;endpoint=c.endpoint_evidence;}
  const key=[condition,item.family,item.kind,item.cell_id,reference].join('|');caseKeys.add(key);requireTrue(item.analysis&&item.title,'Example not explicitly reviewed');const after=c.proposed;
  expectedExamples[condition].push({title:item.title,analysis:item.analysis,baseline_text:before.text,text:after.text,baseline_condition:reference,evidence:{baseline_class:before.class,selected_class:after.class,baseline_site_pass:before.pass,selected_site_pass:after.pass,whole_question_evidence:endpoint},context:pack.contexts[c.context_ref].source_bank_item,cell_id:item.cell_id,family:item.family,kind:item.kind,selection_policy:c.selection_policy,source_sha256:item.source_sha256,official_evidence:{reference:before.evidence??null,selected:after.evidence??null}});
 }
}
requireTrue(caseKeys.size>0,'No reviewed dashboard cases');
function normalExamples(examples){return Object.fromEntries(Object.entries(examples).map(([k,a])=>[k,a.map(e=>({...e,evidence:typeof e.evidence==='string'?JSON.parse(e.evidence):e.evidence,context:typeof e.context==='string'?JSON.parse(e.context):e.context}))]));}
const htmlBytes=fs.readFileSync(htmlPath);inputPins[htmlPath]=hash(htmlBytes);const embedded=htmlBytes.toString().match(/<script type="application\/json" id="embedded-data">([\s\S]*?)<\/script>/g);requireTrue(embedded?.length===1,'Require one exact embedded source payload');const expectedData=JSON.parse(embedded[0].replace(/^.*?>/,'').replace(/<\/script>$/,''));
const sidecar=readInput(path.join(path.dirname(htmlPath),'expansion-data.json'));requireTrue(same(sidecar,expectedData),'Embedded source differs from sidecar');
for(const asset of ['expansion.js','expansion.css'])rawPin(path.join(path.dirname(htmlPath),asset));
const expectedSourceHashes={expanded_results:nativeSha,root_review:inputPins[path.resolve(options.review)],reconstruction:reconstructionSha,effort:effortSha,original_whole:rawPin(options['original-whole']||'${OLENS_DATA_ROOT}/runs/whole-cohort-descriptive-v1.json'),original_report:rawPin(options['original-report']||'dashboard/report.json')};
requireTrue(expectedData.status==='complete_exploratory'&&expectedData.manifest_sha256===inventorySha&&same(expectedData.source_hashes,expectedSourceHashes),'Dashboard source hashes/status differ');
requireTrue(expectedData.conditions.length===active.length&&same(expectedData.conditions.map(c=>c.condition_id).sort(),[...activeIds].sort()),'Dashboard finite70 differs');
for(const a of active){const c=expectedData.conditions.find(c=>c.condition_id===a.condition_id);for(const k of ['method','n','parent_condition_ids','thresholds'])requireTrue(same(c[k],a[k]),'Dashboard inventory metadata changed');}
const embeddedRows=uniqueRows(expectedData.cohorts.full.rows,'embedded native rows');for(const [k,r]of nativeRows)requireTrue(same(r,embeddedRows.get(k)),'Embedded native row differs: '+k);
for(const [k,c]of nativeComparisons){const matches=expectedData.cohorts.full.comparisons.filter(p=>[p.condition,p.reference??p.baseline_condition,p.family].join('|')===k&&same(p,c));requireTrue(matches.length===1,'Embedded declared comparison missing/duplicated: '+k);}
requireTrue(same(expectedData.reconstruction,reconstruction)&&same(expectedData.resources,effort)&&same(expectedData.method_findings,review.method_findings)&&same(normalExamples(expectedData.examples),expectedExamples),'Embedded fit/resources/reviewed examples differ from expected artifacts');
const exampleCondition=['editing_round2-n32','consensus_exact_support0-n16',...Object.keys(expectedExamples)].find(c=>expectedExamples[c]?.length);const exampleChoice={condition:exampleCondition,cell_id:expectedExamples[exampleCondition][0].cell_id};
const exampleExpression=`element('detail').close();detail(${JSON.stringify(exampleChoice.condition)});var ex=[...document.querySelectorAll('dialog details.example')].find(e=>e.textContent.includes(${JSON.stringify(exampleChoice.cell_id)}));if(!ex)throw Error('Expected audited example absent');ex.open=true;ex.scrollIntoView({block:'start'});`;
const expectedDataString=JSON.stringify(expectedData),caseCount=Object.values(expectedExamples).reduce((n,a)=>n+a.length,0);
const authority={source_paths:options,input_sha256:inputPins,active_conditions:active.length,condition_family_rows:intended,declared_contrasts:declared.size,dashboard_case_entries:caseCount,dashboard_case_reference_identities:caseKeys.size,approved_repeated_case_identity_entries:caseCount-caseKeys.size,final_new_review_references:notes.required_new_case_reference_count,final_inherited_review_references:notes.inherited_reference_count,prior_audited_references:notes.prior_audited_reference_count,pending_partition_counts:notes.required_partition_comparison_counts,source_pin_map_digests:{native:hash(JSON.stringify(canonical(native.source_sha256))),reconstruction:hash(JSON.stringify(canonical(reconstruction.source_sha256))),qualitative_notes:hash(JSON.stringify(canonical(notes.source_sha256)))},limits:['Partial reconstruction diagnostic status is permitted only with all280 selection sources complete, exact terminal numeric gate and root binding; invalid/unavailable fits remain explicit.','Historical dashboard comparison records may coexist; every frozen final declared comparison is matched exactly once without double-counting native metric rows.','Every root-approved dashboard entry is matched exactly, including preserved historical repeated identities; entry and unique-reference counts are distinct.','No rejudging, statistical recomputation, paid calls, source mutation, native-PPTX or hosted-browser attestation.']};
function checkInputPins(){for(const [p,digest]of Object.entries(inputPins))requireTrue(hash(fs.readFileSync(p))===digest,'Input changed during QA: '+p);}
if(options.preflight){checkInputPins();process.stdout.write(JSON.stringify({status:'final_inputs_preflight_passed_no_browser',authority})+'\n');process.exit(0);}
requireTrue(fs.existsSync(chrome)&&fs.existsSync(path.dirname(reportPath)),'Missing browser or output parent');
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
    async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true},sessionId);if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
    const checked=[];const sourceSnapshot=await evaluate('JSON.stringify(data)');
    if(sourceSnapshot!==expectedDataString)throw Error('Browser source object differs from exact preflight embedded artifacts');
    const sources=await evaluate('data.source_hashes');
    const initial=await evaluate(`({panels:document.querySelectorAll('#scaling article').length,hiddenTitle:document.body.textContent.includes('Hidden intermediate names'),chainTitle:document.body.textContent.includes('Intermediate numbers'),rankingRule:document.body.textContent.includes('ranked first by the judge'),caption:document.body.textContent.includes('the final answer is optional')})`);
    if(initial.panels!==4||!initial.hiddenTitle||!initial.chainTitle||!initial.rankingRule||!initial.caption)throw Error('Plain language title/caption missing');
    const measurements=await evaluate(`(() => {
      const sourceBefore=JSON.stringify(data);if(Object.values(data.examples).reduce((n,a)=>n+a.length,0)!==${caseCount})throw Error('Derived reviewed example count differs'); const rows=data.reconstruction.rows.filter(r=>r.mean_fve!=null);
      const failures=rows.filter(r=>fve(r.mean_fve)!==(100*r.mean_fve).toFixed(2)+'%').map(r=>r.condition+':'+r.family);
      detail('best_n_exact-n32');
      const panels=[...document.querySelectorAll('.reconstruction-grid article')];let parents=0;
      panels.forEach((panel,i)=>{
        const r=reconstruction('best_n_exact-n32',families[i]);
        if(!panel.textContent.includes('Mean '+fve(r.mean_fve)))failures.push(families[i]+':mean');
        const intervalTitles=[...panel.querySelectorAll('svg line title')].map(t=>t.textContent);
        const expectedInterval=r.mean_fve_ci95?'Raw FVE interval '+r.mean_fve_ci95[0]+' to '+r.mean_fve_ci95[1]:null;
        if(expectedInterval?!intervalTitles.includes(expectedInterval):intervalTitles.some(t=>t.startsWith('Raw FVE interval')))failures.push(families[i]+':fit-errorbar');
        if(panel.querySelector('circle').getAttribute('data-raw-value')!==String(r.mean_fve))failures.push(families[i]+':raw');
        for(const p of r.parent_comparisons){parents++;if(!panel.textContent.includes(conditionName(p.reference))||panel.textContent.includes(p.reference)||!panel.textContent.includes(fveDelta(p.mean_delta)))failures.push(p.reference+':parent-label');}
      });
      const qualityPanels=[...document.querySelectorAll('.detail-grid article')];
      qualityPanels.forEach((panel,i)=>{const m=metric('best_n_exact-n32',families[i]);const bar=panel.querySelector('svg line.interval');if(m.ci95&&m.value!=null){if(!bar||Math.abs(Number(bar.getAttribute('x1'))-(22+216*m.ci95[0]))>1e-6||Math.abs(Number(bar.getAttribute('x2'))-(22+216*m.ci95[1]))>1e-6)failures.push(families[i]+':quality-errorbar');}else if(bar)failures.push(families[i]+':unexpected-quality-errorbar');});
      element('detail').close();element('scaling-metric').value='reconstruction';scaling();
      const curves=[...document.querySelectorAll('#scaling article')];
      curves.forEach((curve,i)=>{
        const a=reconstruction('best_n_exact-n1',families[i]),b=reconstruction('best_n_exact-n32',families[i]);
        if(!curve.textContent.includes('1 → 32 samples: '+fveDelta(b.mean_fve-a.mean_fve))||!curve.textContent.includes('Difference of available site means'))failures.push(families[i]+':gain');
        for(const c of curve.querySelectorAll('circle'))if(!c.querySelector('title').textContent.includes('raw FVE '+c.getAttribute('data-raw-value')))failures.push(families[i]+':tooltip');
      });
      element('tradeoff-group').value='all';tradeoff();if([...document.querySelectorAll('.tradeoff-point')].some(x=>x.dataset.opacity!=='.95'&&x.dataset.opacity!=='0.95'))failures.push('all-groups-opacity');
      const project=projectAccounting(data.resources.ledger_audit); showResources();
      const cards=[...document.querySelectorAll('.resource-grid article')];
      const money=v=>'$'+v.toFixed(2); const card=cards[0];
      if(cards.length!==4 || !card.textContent.includes('Project API usage') || !card.textContent.includes(money(project.settled)) || !card.textContent.includes(money(project.unknown)) || !card.textContent.includes(money(project.pending)) || !card.textContent.includes(money(project.committed)) || !card.textContent.includes(money(project.ceiling)))failures.push('project-resource-card');
      const labels=[...document.querySelectorAll('#scaling svg text')];
      if(labels.some(n=>n.getBBox().x<0))failures.push('cropped-scaling-tick');
      const sourceObjectsMutated=sourceBefore!==JSON.stringify(data); if(sourceObjectsMutated)failures.push('source-object-mutation');
      return {failures,formattedMeans:rows.length,taskPanels:panels.length,exactParents:parents,sourceObjectsMutated,projectAccounting:project,resourceCards:cards.length};
    })()`);
    if(measurements.failures.length)throw Error(JSON.stringify(measurements));
    for(const [name,width,expr] of [
      ['desktop-overview',1280,"element('scaling-metric').value='quality';scaling();scrollTo(0,0);"],
      ['desktop-variance-scaling',1280,"element('scaling-metric').value='reconstruction';scaling();element('scaling').scrollIntoView({block:'center'});"],
      ['desktop-quality-details',1280,"detail('best_n_exact-n32');"],
      ['desktop-variance-details',1280,"document.querySelector('.reconstruction-grid').scrollIntoView({block:'center'});"],
      ['mobile-variance-details',390,"element('detail').close();detail('best_n_exact-n32');document.querySelector('.reconstruction-grid').scrollIntoView({block:'start'});"],
      ['mobile-parent-details',390,"element('detail').close();detail('pooled_greedy_swap_then_prune_0.005-n32');document.querySelector('.reconstruction-grid').scrollIntoView({block:'start'});"],
      ['mobile-variance-scaling',390,"element('detail').close();element('scaling').scrollIntoView({block:'start'});"],
      ['mobile-overview',390,"scrollTo(0,0);"],
      ['desktop-project-resources',1280,"element('resources-section').scrollIntoView({block:'start'});"],
      ['mobile-project-resources',390,"element('resources-section').scrollIntoView({block:'start'});"],
      ['desktop-likelihood-details',1280,"detail('likelihood_true_minus_mean_two_controls-n8');element('detail-content').scrollIntoView({block:'start'});"],
      ['desktop-pruning-details',1280,"element('detail').close();detail('pooled_greedy_swap_then_prune_0.005-n32');element('detail-content').scrollIntoView({block:'start'});"],
      ['desktop-method-audited-examples',1280,exampleExpression],
      ['mobile-method-audited-examples',390,exampleExpression],
    ]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<500},sessionId);
      await evaluate(expr);await sleep(150);
      const stats=await evaluate('({width:innerWidth,documentWidth:document.documentElement.scrollWidth,dialogWidth:document.querySelector("dialog").scrollWidth,dialogClientWidth:document.querySelector("dialog").clientWidth,fitPanels:document.querySelectorAll(".reconstruction-grid article").length})');
      if(stats.documentWidth>stats.width||stats.dialogWidth>stats.dialogClientWidth+2)throw Error('Horizontal overflow '+name+JSON.stringify(stats));
      const png=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sessionId);fs.writeFileSync(path.join(path.dirname(reportPath),name+'.png'),Buffer.from(png.data,'base64'),{flag:'wx'});checked.push({name,...stats});
    }
    if(await evaluate('JSON.stringify(data)')!==sourceSnapshot)throw Error('Source object changed during full browser pass');
    checkInputPins();
    fs.writeFileSync(reportPath,JSON.stringify({status:'pass',scope:'Actual final source-bound dashboard browser QA. Exact embedded native/numeric/effort/root-review/case objects match explicit immutable expected inputs and remain unchanged through all14 interactions. No publication or inference.',authority,sources,measurements,initial,checked,engine:version.product},null,2)+'\n',{flag:'wx'});
    return;
  })(),new Promise((_,reject)=>{deadline=setTimeout(()=>reject(new Error('Overall dashboard browser QA deadline')),60000);})]);
} finally {
  clearTimeout(deadline);
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error('Browser closing'));}
  socket?.close();child.kill('SIGTERM');
  await Promise.race([new Promise(r=>child.once('exit',r)),sleep(1500)]);
  if(child.exitCode===null)child.kill('SIGKILL');
  fs.writeFileSync(path.join(path.dirname(reportPath),'layout-chromium-stderr.log'),stderr,{flag:'wx'});
}
