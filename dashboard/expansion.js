'use strict';

const element = id => document.getElementById(id);
const families = ['hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association'];
const titles = ['Transcript contradictions', 'Hidden intermediate names', 'Intermediate numbers', 'Who did what'];
const groups = {
  selection: 'Choose a complete readout',
  consensus: 'Keep repeated statements',
  pruning: 'Remove weak bullets',
  pooling: 'Combine original bullets',
  verification: 'Compare activation evidence',
  editing: 'Edit a readout',
  combinations: 'Combine approaches',
};
const descriptions = {
  selection: 'Score each complete candidate by how well its text vectors reconstruct the activation, then choose one.',
  consensus: 'Keep original bullets supported by repeated samples. Semantic helpers check equivalence and, in some settings, compatibility.',
  pruning: 'Delete bullets with little reconstruction contribution, or small fitted weights. Random deletion gives a shortening control.',
  pooling: 'Choose up to four original bullets from several samples, refitting their joint reconstruction after each addition.',
  verification: 'Compare scores under the true activation and frozen control activations. Likelihood is a separate signal from reconstruction.',
  editing: 'A separate Luna helper proposes bounded edits. The frozen reconstructor chooses among them; one or two rounds are tested.',
  combinations: 'Apply recorded components together, with parent and component-off controls. This is a fixed menu, not an unrestricted search.',
};
const aliases = {
  selection: 'selection sampling best of readout reconstruction',
  consensus: 'consensus repeated statements repetition agreement support',
  pruning: 'pruning prune removal removing deletion weak bullets',
  pooling: 'pooling pool pooled combine combining composition omp orthogonal matching pursuit',
  verification: 'verification specificity contrastive controls likelihood activation evidence',
  editing: 'editing edit editor refinement rewrite',
  combinations: 'combinations components ablations',
};
const defaultReference = 'capped_n1-n1';
function methodDescription(condition) {
  if (condition.method === 'raw_n1') return 'Use the first original Oracle Lens sample as emitted.';
  if (condition.method === 'capped_n1') return 'Keep the first original sample, with the frozen deterministic cap of four bullets.';
  if (condition.method === 'random_complete') return 'Choose a complete sample with the frozen random seed, independently of its reconstruction score.';
  if (condition.method === 'best_n_exact' && condition.n === 1) return 'Score the first sample with the frozen reconstruction eligibility rule; there is no choice among samples.';
  return descriptions[condition.group];
}
let data;
let expanded = new Set();
let allExpanded = false;
let changeExtent = 0.3;

function escape(value) {
  const entities = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};
  return String(value ?? '').replace(/[&<>"']/g, character => entities[character]);
}

function breakableId(value) {
  return escape(value).replace(/([_-])/g, '$1<wbr>');
}

function conditionName(id) { return data.conditions.find(row => row.condition_id === id)?.label ?? 'Recorded reference'; }
function conditionLabel(id) { return `<span title='${escape(id)}'>${escape(conditionName(id))}</span>`; }
function taskCaption(family) { return family === 'multihop_mt' ? "<p class='detail-note task-caption'>Recover the required intermediate entities; the final answer is optional.</p>" : ''; }

function percent(value) {
  return value == null ? '—' : `${(100 * value).toFixed(1)}%`;
}

function signed(value) {
  return value == null ? '—' : `${value > 0 ? '+' : ''}${(100 * value).toFixed(1)} points`;
}

function cohort() {
  return data.cohorts[element('cohort').value];
}

function metric(id, family) {
  return cohort().rows.find(row => row.condition === id && row.family === family)?.metric;
}

function reconstruction(id, family) {
  return data.reconstruction?.rows.find(row => row.condition === id && row.family === family);
}

function fve(value) { return value == null ? 'Unavailable' : `${(100 * value).toFixed(2)}%`; }
function fveDelta(value) { return value == null ? 'Unavailable' : `${value > 0 ? '+' : ''}${(100 * value).toFixed(2)} pp`; }

function fitGraph(row, label) {
  if (row?.mean_fve == null) return '';
  const ci = row.mean_fve_ci95;
  const lo = Math.min(0, row.mean_fve, row.median_fve ?? 0, ...(ci ?? []));
  const hi = Math.max(1, row.mean_fve, row.median_fve ?? 0, ...(ci ?? []));
  const x = v => 24 + 232 * (v - lo) / (hi - lo);
  return `<svg class='fit-graph' viewBox='0 0 280 65' role='img' aria-label='${escape(label)} mean explained activation variance and pointwise 95% interval'>
    <line x1='24' x2='256' y1='26' y2='26' stroke='#bacddc'/>
    ${ci ? `<line x1='${x(ci[0])}' x2='${x(ci[1])}' y1='26' y2='26' stroke='#246ea3' stroke-width='3'><title>Raw FVE interval ${ci[0]} to ${ci[1]}</title></line>` : ''}
    <circle cx='${x(row.mean_fve)}' cy='26' r='5' fill='#13756c' data-raw-value='${row.mean_fve}'><title>Mean ${fve(row.mean_fve)}; raw FVE ${row.mean_fve}</title></circle>
    ${row.median_fve == null ? '' : `<line x1='${x(row.median_fve)}' x2='${x(row.median_fve)}' y1='16' y2='36' stroke='#a56c25'><title>Median ${fve(row.median_fve)}; raw FVE ${row.median_fve}</title></line>`}
    <text x='24' y='55' font-size='12'>${fve(lo)}</text><text x='256' y='55' text-anchor='end' font-size='12'>${fve(hi)}</text></svg>`;
}

function reconstructionDetails(id) {
  if (!data.reconstruction) return '';
  const panels = families.map((family, index) => {
    const row = reconstruction(id, family);
    if (!row) return `<article><h4>${titles[index]}</h4><p>Not yet extracted.</p></article>`;
    const ci = row.mean_fve_ci95;
    const parents = (row.parent_comparisons ?? []).map(p => `<p>Versus ${conditionLabel(p.reference)}: <strong title='Raw FVE change ${p.mean_delta}'>${fveDelta(p.mean_delta)}</strong>
      ${p.ci95_delta ? `(${fveDelta(p.ci95_delta[0])} to ${fveDelta(p.ci95_delta[1])}; pointwise 95%)` : '(interval unavailable)'}.
      ${p.paired_sites} / ${p.intended_paired_sites} common-valid sites.
      ${p.warning ? `<span class='detail-note'>${escape(p.warning)}</span>` : ''}</p>`).join('');
    return `<article><h4>${titles[index]}</h4><strong title='Raw FVE ${row.mean_fve}'>Mean ${fve(row.mean_fve)}</strong>${fitGraph(row, titles[index])}
      <p>Median ${fve(row.median_fve)}. ${row.scored_site_count} / ${row.full_site_count} intended activation sites scored.
      ${ci ? `Mean pointwise 95% interval: ${fve(ci[0])} to ${fve(ci[1])}.` : 'Mean interval unavailable.'}</p>
      ${(row.mean_fve_warnings ?? []).map(w => `<p class='detail-note'>${escape(w)}</p>`).join('')}
      ${Object.keys(row.unavailable_reasons ?? {}).length ? `<p class='detail-note'>Unavailable: ${escape(JSON.stringify(row.unavailable_reasons))}</p>` : ''}
      ${parents}</article>`;
  }).join('');
  return `<h3>Explained activation variance · secondary measure</h3><p class='detail-note'>Reconstruction snapshot: ${escape(data.reconstruction.updated_utc ?? 'Unavailable')}. All 469 questions, regardless of the selected subcohort. Higher percentages mean the retained text vectors explain more of the activation. This measures fit, not truthful prose. Changes are in percentage points (pp). Dot: mean; amber tick: median; line: grouped pointwise 95% interval. Paired changes use the same valid sites and are outside the headline contrast family.</p><div class='reconstruction-grid'>${panels}</div>
    <details><summary>Reconstruction objective and measurement limits</summary><p class='detail-note'>Exact nonnegative least-squares fit: 1 minus squared residual / squared target norm. Fits use the first 32 cleaned tokens of retained atoms under the sealed whitening/vector contract; they do not score the full prose. Empty emitted readouts have zero fit. Raw unmodified N1 has no comparable fit.</p>
      ${(data.reconstruction.limits ?? []).map(note => `<p class='detail-note'>${escape(note)}</p>`).join('')}</details>`;
}

function eligibleComparison(row) {
  return !row.scope || row.scope === 'original_item' || row.scope === 'original_grid';
}

function comparisonReference(row) {
  return row.reference ?? row.baseline_condition;
}

function paired(id, family) {
  const reference = element('reference').value;
  return (cohort().comparisons ?? []).find(row =>
    row.condition === id && row.family === family &&
    comparisonReference(row) === reference && eligibleComparison(row));
}

function displayed(id, family) {
  if (element('view').value === 'rates') return metric(id, family);
  const comparison = paired(id, family);
  if (!comparison) return null;
  return {
    value: comparison.delta,
    ci95: comparison.ci95_delta,
    items: comparison.items,
    independent_groups: comparison.independent_groups,
  };
}

function referenceIds(current) {
  return new Set((current.comparisons ?? [])
    .filter(eligibleComparison).map(comparisonReference).filter(Boolean));
}

function populateReferences() {
  const ids = new Set(Object.values(data.cohorts).flatMap(current => [...referenceIds(current)]));
  // Keep the established default when a snapshot has no paired evidence yet.
  if (!ids.size) ids.add(defaultReference);
  const labels = new Map(data.conditions.map(condition => [condition.condition_id, condition.label]));
  const ordered = [...ids].sort((a, b) => {
    if (a === defaultReference) return -1;
    if (b === defaultReference) return 1;
    return (labels.get(a) ?? a).localeCompare(labels.get(b) ?? b);
  });
  element('reference').innerHTML = ordered.map(id => {
    const label = id === defaultReference ? 'Original, capped' : labels.get(id) ?? id;
    return `<option value='${escape(id)}'>${escape(label)}</option>`;
  }).join('');
  element('reference').value = ids.has(defaultReference) ? defaultReference : ordered[0];
}

function updateReferenceAvailability() {
  const available = referenceIds(cohort());
  const select = element('reference');
  for (const option of select.options) option.disabled = !available.has(option.value);
  if (available.size && !available.has(select.value)) {
    select.value = available.has(defaultReference) ? defaultReference : [...available][0];
  }
  select.disabled = !available.size;
  select.title = available.size ? '' : 'No paired comparisons have been measured for this cohort.';
  changeExtent = 0.3;
  for (const row of cohort().comparisons ?? []) {
    if (!eligibleComparison(row) || comparisonReference(row) !== select.value) continue;
    for (const value of [row.delta, ...(row.ci95_delta ?? [])]) {
      if (Number.isFinite(value)) changeExtent = Math.max(changeExtent, Math.abs(value));
    }
  }
}

function intervalText(measurement, delta = false) {
  if (!measurement?.ci95) return 'Interval unavailable';
  const format = delta ? signed : percent;
  return `95% interval ${format(measurement.ci95[0])} to ${format(measurement.ci95[1])}`;
}

function missingLabel(measurement, family, delta = false) {
  if (!measurement) return 'Unmeasured';
  if (delta) return 'No defined change';
  return family === 'hallucination' && measurement.denominator === 0 ? 'No specific readouts' : 'No defined rate';
}

function measurementHint(measurement, delta = false, family) {
  if (measurement?.value == null) return `${missingLabel(measurement, family, delta)}; no estimate or interval available`;
  const value = delta ? `Paired change: ${signed(measurement.value)}` : percent(measurement.value);
  return `${value}; ${intervalText(measurement, delta)}; ${measurement.items ?? '?'} questions, ` +
    `${measurement.independent_groups ?? '?'} groups`;
}

function pointAndInterval(measurement, x, y) {
  if (measurement?.value == null) return '';
  const ci = measurement.ci95;
  const interval = ci ? `
    <line class='interval' x1='${x(ci[0])}' x2='${x(ci[1])}' y1='${y}' y2='${y}'
      stroke='#246ea3' stroke-width='2'/>
    <path d='M${x(ci[0])} ${y - 5}v10M${x(ci[1])} ${y - 5}v10' stroke='#246ea3'/>` : '';
  return `${interval}<circle class='estimate' cx='${x(measurement.value)}' cy='${y}' r='4' fill='#13756c'/>`;
}

function mini(measurement, delta = false, family) {
  if (measurement?.value == null) return `<span class='empty'>${missingLabel(measurement, family, delta)}</span>`;
  const low = delta ? -changeExtent : 0;
  const high = delta ? changeExtent : 1;
  const x = value => 14 + 116 * (Math.max(low, Math.min(high, value)) - low) / (high - low);
  const hint = escape(measurementHint(measurement, delta));
  const zero = delta ? `<line x1='${x(0)}' x2='${x(0)}' y1='4' y2='25' stroke='#bbc9d3'/>` : '';
  const count = delta ? '' : `<small class='metric-count'>${measurement.numerator ?? '?'} / ${measurement.denominator ?? '?'}</small>`;
  return `<svg class='mini' viewBox='0 0 145 32' role='img' aria-label='${hint}'>
    <title>${hint}</title><line x1='14' x2='130' y1='14' y2='14' stroke='#d9e4ed'/>
    ${zero}${pointAndInterval(measurement, x, 14)}</svg>
    <span class='metric-text'>${delta ? signed(measurement.value) : percent(measurement.value)}</span>${count}`;
}

function detailGraph(measurement, title, delta = false, family) {
  const low = delta ? -changeExtent : 0;
  const high = delta ? changeExtent : 1;
  const x = value => 22 + 216 * (value - low) / (high - low);
  const ticks = delta ? [low, 0, high] : [0, 0.25, 0.5, 0.75, 1];
  const hint = escape(`${title}: ${measurementHint(measurement, delta, family)}`);
  const labels = ticks.map(value => `<line x1='${x(value)}' x2='${x(value)}' y1='18' y2='44' stroke='#d9e4ed'/>
    <text x='${x(value)}' y='64' text-anchor='middle' font-size='11' fill='#536678'>
      ${delta ? (value * 100).toFixed(0) : (value * 100).toFixed(0) + '%'}
    </text>`).join('');
  const unmeasured = measurement?.value == null
    ? `<text x='130' y='36' text-anchor='middle' font-size='13' fill='#778998'>${missingLabel(measurement, family, delta)}</text>` : '';
  return `<svg class='detail-measurement' data-measured='${measurement?.value != null}'
    viewBox='0 0 260 84' width='100%' height='84' role='img' aria-label='${hint}'>
    <title>${hint}</title>${labels}<line x1='22' x2='238' y1='32' y2='32' stroke='#bacddc'/>
    ${pointAndInterval(measurement, x, 32)}${unmeasured}
    ${delta ? `<text x='130' y='81' text-anchor='middle' font-size='10' fill='#536678'>Percentage points</text>` : ''}
  </svg>`;
}

function matchesSearch(condition, query) {
  const parentTerms = (condition.parent_condition_ids ?? []).map(id => {
    const parent = data.conditions.find(row => row.condition_id === id);
    return parent ? `${parent.label} ${parent.group} ${aliases[parent.group] ?? ''}` : id;
  });
  const terms = [condition.label, condition.group, condition.condition_id, groups[condition.group],
    descriptions[condition.group], aliases[condition.group], ...parentTerms].join(' ').toLowerCase();
  return query.split(/\s+/).filter(Boolean).every(word =>
    word === 'omp' ? /\bomp\b/.test(terms) : terms.includes(word));
}

function groupRow(key, members, open, delta) {
  const heading = `<td><button class='group-toggle' data-group='${key}' aria-expanded='${Boolean(open)}'>
    ${open ? '▾' : '▸'} ${groups[key]}</button>
    <span class='group-count'>${members.length} recorded settings</span></td>`;
  const cells = families.map(family => {
    const measurements = members.map(condition => displayed(condition.condition_id, family))
      .filter(measurement => measurement?.value != null);
    if (!measurements.length) {
      const undefinedRate = members.map(condition => displayed(condition.condition_id, family)).find(Boolean);
      return `<td><span class='empty'>${missingLabel(undefinedRate, family, delta)}</span></td>`;
    }
    const values = measurements.map(measurement => measurement.value);
    const format = delta ? signed : percent;
    const range = format(Math.min(...values)) + (values.length > 1 ? ` to ${format(Math.max(...values))}` : '');
    return `<td><span class='metric-text'>${range}</span>
      <small class='metric-count'>${measurements.length} / ${members.length} measured</small></td>`;
  }).join('');
  return `<tr class='group-row'>${heading}${cells}</tr>`;
}

function variantRow(condition, delta) {
  const label = `<td><button class='variant-link' data-condition='${escape(condition.condition_id)}'>
    ${escape(condition.label)}</button></td>`;
  const cells = families.map(family => `<td>${mini(displayed(condition.condition_id, family), delta, family)}</td>`).join('');
  return `<tr>${label}${cells}</tr>`;
}

function render() {
  updateReferenceAvailability();
  const current = cohort();
  const delta = element('view').value === 'change';
  const query = element('search').value.toLowerCase().trim();
  element('scope').textContent = current.scope + (delta
    ? ' · Paired changes use the same questions; positive means a higher measured rate.'
    : ' · Per-method grouped 95% intervals.');
  element('reference-control').hidden = !delta;
  const active = data.conditions.filter(condition => matchesSearch(condition, query));
  const rows = [];
  for (const key of Object.keys(groups)) {
    const members = active.filter(condition => condition.group === key);
    if (!members.length) continue;
    const open = expanded.has(key) || Boolean(query);
    rows.push(groupRow(key, members, open, delta));
    if (open) rows.push(...members.map(condition => variantRow(condition, delta)));
  }
  element('matrix').innerHTML = rows.join('');
  for (const button of element('matrix').querySelectorAll('[data-group]')) {
    button.addEventListener('click', () => {
      const key = button.dataset.group;
      if (expanded.has(key)) expanded.delete(key); else expanded.add(key);
      render();
    });
  }
  for (const button of element('matrix').querySelectorAll('[data-condition]')) {
    button.addEventListener('click', () => detail(button.dataset.condition));
  }
  scaling();
  tradeoff();
}

function setupTradeoff() {
  if (!element('tradeoff') || !element('tradeoff-family') || !element('tradeoff-group')) return;
  element('tradeoff-family').innerHTML = families.slice(1).map((family, index) =>
    `<option value='${family}'>${titles[index + 1]}</option>`).join('');
  element('tradeoff-group').innerHTML = `<option value='all'>All approaches</option>` +
    Object.entries(groups).map(([key, label]) => `<option value='${key}'>${label}</option>`).join('');
  for (const id of ['tradeoff-family', 'tradeoff-group']) element(id).addEventListener('change', tradeoff);
  window.addEventListener('resize', tradeoff);
}

function tradeoff() {
  const container = element('tradeoff');
  if (!container || !element('tradeoff-family') || !element('tradeoff-group')) return;
  const family = element('tradeoff-family').value;
  const selectedGroup = element('tradeoff-group').value;
  const endpoint = element('cohort').value === 'pilot' ? 'Per-activation recovery (pilot)' : 'Native recovery';
  // Use fewer SVG units on narrow screens so axis text remains readable.
  const compact = container.clientWidth < 550;
  const width = compact ? 420 : 720;
  const height = compact ? 355 : 420;
  const left = compact ? 52 : 64;
  const right = compact ? 394 : 654;
  const top = compact ? 40 : 60;
  const bottom = compact ? 300 : 360;
  const colors = ['#246ea3', '#13756c', '#946033', '#745b99', '#a64e5c', '#5d7650', '#586573'];
  const color = key => colors[Object.keys(groups).indexOf(key)];
  const x = value => left + (right - left) * value;
  const y = value => bottom - (bottom - top) * value;
  const parts = [];
  for (const value of [0, 0.25, 0.5, 0.75, 1]) {
    parts.push(`<line x1='${left}' x2='${right}' y1='${y(value)}' y2='${y(value)}' stroke='#d9e4ed'/>
      <line x1='${x(value)}' x2='${x(value)}' y1='${top}' y2='${bottom}' stroke='#d9e4ed'/>
      <text x='${x(value)}' y='${bottom + 20}' text-anchor='middle' font-size='12' fill='#536678'>${value * 100}%</text>
      <text x='${left - 8}' y='${y(value) + 4}' text-anchor='end' font-size='12' fill='#536678'>${value * 100}%</text>`);
  }
  const measured = data.conditions.filter(condition => metric(condition.condition_id, family)?.value != null &&
    metric(condition.condition_id, 'hallucination')?.value != null);
  for (const condition of measured) {
    const horizontal = metric(condition.condition_id, family);
    const vertical = metric(condition.condition_id, 'hallucination');
    const hint = `${condition.label}; ${titles[families.indexOf(family)]}: ${measurementHint(horizontal)}; ` +
      `Transcript contradictions: ${measurementHint(vertical)}. Outcomes from different task banks.`;
    const opacity = selectedGroup === 'all' || condition.group === selectedGroup ? 0.95 : 0.28;
    const horizontalBar = horizontal.ci95 ? `<line class='horizontal-interval'
      x1='${x(horizontal.ci95[0])}' x2='${x(horizontal.ci95[1])}' y1='${y(vertical.value)}' y2='${y(vertical.value)}'/>
      <path d='M${x(horizontal.ci95[0])} ${y(vertical.value) - 4}v8M${x(horizontal.ci95[1])} ${y(vertical.value) - 4}v8'/>` : '';
    const verticalBar = vertical.ci95 ? `<line class='vertical-interval'
      x1='${x(horizontal.value)}' x2='${x(horizontal.value)}' y1='${y(vertical.ci95[0])}' y2='${y(vertical.ci95[1])}'/>
      <path d='M${x(horizontal.value) - 4} ${y(vertical.ci95[0])}h8M${x(horizontal.value) - 4} ${y(vertical.ci95[1])}h8'/>` : '';
    parts.push(`<g class='tradeoff-point' data-condition='${escape(condition.condition_id)}' data-opacity='${opacity}'
      tabindex='0' role='button' aria-label='${escape(hint)}' opacity='${opacity}'
      stroke='${color(condition.group)}' stroke-width='1.5' style='cursor:pointer'>
      <title>${escape(hint)}</title>${horizontalBar}${verticalBar}
      <circle cx='${x(horizontal.value)}' cy='${y(vertical.value)}' r='5' fill='${color(condition.group)}'/></g>`);
  }
  container.innerHTML = `<svg viewBox='0 0 ${width} ${height}' width='100%' role='img'
    aria-label='${endpoint} versus transcript contradictions across separate task banks, with pointwise grouped 95% intervals'>
    ${parts.join('')}
    <text x='${width / 2}' y='${height - 11}' text-anchor='middle' font-size='14' fill='#263e50'>${titles[families.indexOf(family)]}: ${endpoint.toLowerCase()} (higher)</text>
    <text transform='translate(18 ${(top + bottom) / 2}) rotate(-90)' text-anchor='middle' font-size='14' fill='#263e50'>Transcript contradictions (lower)</text>
    ${measured.length ? '' : `<text x='${width / 2}' y='${(top + bottom) / 2}' text-anchor='middle' fill='#536678'>No measured task pairs in this cohort</text>`}
    </svg><p class='detail-note'>${measured.length} measured settings. Pointwise grouped 95% intervals on both axes.
      Outcomes come from different task banks, not within-example precision/recall. No pooled average.
      ${element('cohort').value === 'pilot' ? 'Pilot points measure per-activation recovery rather than the native complete-question endpoint.' : ''}</p>
    <p>${Object.entries(groups).map(([key, label]) =>
      `<span style='display:inline-block;margin:0 16px 8px 0;color:${color(key)}'>● ${escape(label)}</span>`).join('')}</p>`;
  for (const point of container.querySelectorAll('.tradeoff-point')) {
    const highlight = active => {
      point.setAttribute('opacity', active ? '1' : point.dataset.opacity);
      point.querySelector('circle').setAttribute('r', active ? '7' : '5');
    };
    point.addEventListener('pointerenter', () => highlight(true));
    point.addEventListener('pointerleave', () => highlight(false));
    point.addEventListener('focus', () => highlight(true));
    point.addEventListener('blur', () => highlight(false));
    point.addEventListener('click', () => detail(point.dataset.condition));
    point.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        detail(point.dataset.condition);
      }
    });
  }
}

function scaling() {
  const samples = [1, 2, 4, 8, 16, 32];
  const fit = element('scaling-metric').value === 'reconstruction';
  element('scaling-note').textContent = fit ? 'Secondary all-bank activation-site means with grouped pointwise 95% intervals; valid scored sites only. These are not question recovery rates. Raw unmodified text has no comparable fit. Missing points remain blank.' : 'Native task endpoints retain the selected cohort and original denominators. Grouped pointwise 95% intervals accompany each value. Reconstruction fit does not verify the truth of a description.';
  element('scaling').innerHTML = families.map((family, index) => {
    const rows = samples.map(n => {
      const row = reconstruction(`best_n_exact-n${n}`, family);
      return {n, metric: fit ? row ? {value: row.mean_fve, ci95: row.mean_fve_ci95, scored: row.scored_site_count, intended: row.full_site_count} : null : metric(`best_n_exact-n${n}`, family)};
    });
    const lower = fit ? Math.min(0, ...rows.flatMap(r => r.metric?.value == null ? [] : [r.metric.value, ...(r.metric.ci95 ?? [])])) : 0;
    const upper = fit ? Math.max(1, ...rows.flatMap(r => r.metric?.value == null ? [] : [r.metric.value, ...(r.metric.ci95 ?? [])])) : 1;
    const x = n => 50 + samples.indexOf(n) * 35;
    const y = value => 170 - 140 * (value - lower) / (upper - lower);
    const parts = [
      `<line x1='50' y1='30' x2='50' y2='170' stroke='#bacddc'/>`,
      `<line x1='50' y1='170' x2='225' y2='170' stroke='#bacddc'/>`,
    ];
    for (const value of [lower, (upper + lower) / 2, upper]) {
      parts.push(`<text x='44' y='${y(value) + 4}' text-anchor='end' font-size='10' fill='#536678'>${percent(value)}</text>
        <line x1='50' x2='225' y1='${y(value)}' y2='${y(value)}' stroke='#d9e4ed'/>`);
    }
    rows.forEach((row, position) => {
      parts.push(`<text x='${x(row.n)}' y='190' text-anchor='middle' font-size='11' fill='#536678'>${row.n}</text>`);
      if (row.metric?.value == null) return;
      const value = row.metric.value;
      const ci = row.metric.ci95;
      const previous = rows[position - 1];
      if (previous?.metric?.value != null) {
        parts.push(`<line x1='${x(previous.n)}' x2='${x(row.n)}' y1='${y(previous.metric.value)}'
          y2='${y(value)}' stroke='#246ea3' stroke-width='2'/>`);
      }
      if (ci) parts.push(`<line x1='${x(row.n)}' x2='${x(row.n)}' y1='${y(ci[0])}' y2='${y(ci[1])}' stroke='#246ea3'/>`);
      parts.push(`<circle cx='${x(row.n)}' cy='${y(value)}' r='4' fill='#13756c' data-raw-value='${value}'>
        <title>${row.n} samples: ${fit ? `${fve(value)} explained activation variance; raw FVE ${value}; ${row.metric.scored}/${row.metric.intended} sites${ci ? `; 95% ${ci.map(fve).join(' to ')}` : ''}` : `${percent(value)}${ci ? `, ${intervalText(row.metric)}` : ''}`}</title></circle>`);
    });
    const first = rows[0].metric;
    const last = rows[rows.length - 1].metric;
    const recorded = fit ? reconstruction('best_n_exact-n32', family)?.parent_comparisons?.find(p => p.reference === 'best_n_exact-n1') : null;
    const gain = fit && first?.value != null && last?.value != null ? `<p class='fit-gain'><strong>1 → 32 samples: ${fveDelta(recorded ? recorded.mean_delta : last.value - first.value)}</strong><br><small title='First ${first.scored}/${first.intended} sites; 32 samples ${last.scored}/${last.intended} sites'>${recorded ? `Paired change${recorded.ci95_delta ? `; 95% ${recorded.ci95_delta.map(fveDelta).join(' to ')}` : ''}` : 'Difference of available site means'}</small></p>` : '';
    const endpoint = element('cohort').value === 'pilot' ? 'Per activation diagnostic' : 'Original benchmark endpoint';
    return `<article class='curve-box'><h3>${titles[index]}</h3>${gain}
      <svg viewBox='0 0 260 215' role='img' aria-label='${titles[index]} against sample count'>
        ${parts.join('')}<text x='140' y='212' text-anchor='middle' font-size='11' fill='#536678'>Samples per activation</text>
      </svg>${taskCaption(family)}<p>${fit ? 'Explained activation variance · all-bank sites (secondary)' : `${index === 0 ? 'Lower' : 'Higher'} is better · ${endpoint}`}</p></article>`;
  }).join('');
}

function detailTask(id, family, index) {
  const measurement = metric(id, family);
  const description = measurement?.value != null
    ? `<p>${measurement.numerator ?? '?'} / ${measurement.denominator ?? '?'}<br>
        ${measurement.items ?? '?'} questions · ${measurement.independent_groups ?? '?'} related groups<br>
        ${intervalText(measurement)}</p>`
    : measurement ? `<p>${missingLabel(measurement, family)} for this setting and cohort; no rate or interval is defined.</p>`
      : '<p>Full evaluation is pending for this setting and cohort.</p>';
  const warnings = (measurement?.warnings ?? []).map(warning =>
    `<p class='detail-note'>${escape(warning)}</p>`).join('');
  return `<article data-task='${family}'><h3>${titles[index]}</h3>${taskCaption(family)}
    <strong>${measurement?.value != null ? percent(measurement.value) : missingLabel(measurement, family)}</strong>
    ${detailGraph(measurement, titles[index], false, family)}${description}${warnings}</article>`;
}

function detail(id) {
  const condition = data.conditions.find(row => row.condition_id === id);
  const parts = [
    `<h2>${escape(condition.label)}</h2><p>${escape(methodDescription(condition))}</p>`,
    `<p class='detail-note'>${escape(cohort().scope)}</p>`,
    `<div class='detail-grid'>${families.map((family, index) => detailTask(id, family, index)).join('')}</div>`,
  ];
  const reviewedFinding = data.condition_findings?.[id] ?? data.method_findings?.[condition.group];
  parts.push(reconstructionDetails(id));
  if (reviewedFinding) {
    parts.push(`<h3>What the audited examples show</h3><p>${escape(reviewedFinding.finding)}</p>
      <p class='detail-note'>${escape(reviewedFinding.limits)}</p>`);
  }
  const comparisons = families.map(family => paired(id, family)).filter(Boolean);
  if (comparisons.length) {
    parts.push('<h3>Paired change versus the selected reference</h3>');
    for (const comparison of comparisons) {
      const title = titles[families.indexOf(comparison.family)];
      const measurement = {value: comparison.delta, ci95: comparison.ci95_delta,
        items: comparison.items, independent_groups: comparison.independent_groups};
      parts.push(`<article class='paired-detail'><p>${title}: <strong>${signed(comparison.delta)}</strong>;
        ${intervalText(measurement, true)}.</p>${detailGraph(measurement, title, true)}</article>`);
      const warnings = [comparison.warning, ...(comparison.warnings ?? [])].filter(Boolean);
      if (comparison.bootstrap_replicates && comparison.defined_draws < comparison.bootstrap_replicates) {
        warnings.push(`${comparison.defined_draws} of ${comparison.bootstrap_replicates} bootstrap draws had a defined rate.`);
      }
      for (const warning of warnings) {
        parts.push(`<p class='detail-note paired-warning'>${escape(warning)}</p>`);
      }
      if (comparison.simultaneous_ci95_delta) {
        const ci = comparison.simultaneous_ci95_delta;
        parts.push(`<p>Simultaneous 95% interval: ${signed(ci[0])} to ${signed(ci[1])}</p>`);
      }
    }
  }
  const lengths = cohort().lengths?.[id];
  if (lengths) {
    parts.push('<h3>Actual output length</h3>');
    families.forEach((family, index) => {
      if (!lengths[family]) return;
      parts.push(`<p>${titles[index]}: ${lengths[family].mean_qwen_tokens_all_intended.toFixed(1)} tokens and
        ${lengths[family].mean_bullets_all_intended.toFixed(2)} bullets on average.</p>`);
    });
  }
  if (data.effort[id]) {
    parts.push(`<h3>Inference effort</h3><p>${escape(data.effort[id].summary ?? JSON.stringify(data.effort[id]))}</p>`);
  }
  const effort = data.resources?.method_effort[id];
  if (effort) {
    parts.push(`<h3>New-input inference components</h3><p>${escape(effort.summary)}</p>
      <p class='detail-note'>${effort.original_pool_n} shared samples. Helper recipe: ${escape((effort.new_input_helper_recipe ?? []).join(' + ') || 'None')}.
      Campaign dependencies: ${escape((effort.shared_helper_component_refs ?? []).join(', ') || 'None')}. Shared helper costs belong to phases, not separate variant charges. Benchmark judging is excluded from inference.</p>`);
    for (const phase of effort.shared_helper_component_refs ?? []) {
      const rows = Object.values(data.resources.helper_phases_by_family).filter(r => r.phase === phase);
      const sum = key => rows.reduce((s, r) => s + (r[key] ?? 0), 0);
      const validation = key => rows.reduce((s, r) => s + (r.response_validation?.[key] ?? 0), 0);
      const knownValidation = rows.filter(r => r.response_validation).length;
      const proposalCount = rows.reduce((s, r) => s + (r.proposal_statistics?.validated_proposals ?? 0), 0);
      parts.push(`<details><summary>Shared ${escape(phase.replaceAll('_', ' '))} campaign phase</summary>
        <p>${sum('completed_cells').toLocaleString()} completed sites; ${sum('logical_calls').toLocaleString()} logged logical calls; ${sum('validated_cache_hits').toLocaleString()} validated cache returns.
        ${sum('physical_settled_attempts').toLocaleString()} attributed settled physical attempts, $${sum('actual_usage_estimate_usd').toFixed(2)} usage estimate.</p>
        <p>Retained terminal response validation for ${knownValidation}/4 families: ${validation('valid_physical_responses').toLocaleString()} valid and ${validation('invalid_physical_responses').toLocaleString()} invalid responses. Live families remain unclassified until their evidence is complete.
        ${phase.startsWith('editing') ? `${proposalCount.toLocaleString()} validated bounded proposals; zero proposals can be a valid helper result.` : ''}</p>
        <p class='detail-note'>Shared phase totals, not charges unique to this setting. Logical invocations, physical requests and validated outputs have different denominators.</p></details>`);
    }
  }
  const parents = (condition.parent_condition_ids ?? []).map(conditionLabel).join(', ') || 'Original reference';
  parts.push(`<details><summary>Exact setting and parent comparisons</summary>
    <p class='detail-note'>${breakableId(id)}<br>Parents: ${parents}</p>
    <pre>Parameters: ${escape(JSON.stringify(condition.thresholds))}</pre></details>`);
  const examples = data.examples[id] ?? [];
  if (examples.length) {
    parts.push('<h3>Audited examples</h3><p class="detail-note">These are all-bank examples, independent of the selected subcohort. Fixed anchors and outcome-selected cases are labeled separately. They illustrate differences and do not estimate their frequency.</p>');
    for (const example of examples) {
      parts.push(`<details class='example'><summary>${escape(example.title ?? example.kind)}</summary>
        <p>${escape(example.analysis ?? example.observation)}</p><div class='quote-pair'>
        <section><strong>Reference: ${example.baseline_condition ? conditionLabel(example.baseline_condition) : 'Original capped readout'}</strong><pre>${escape(example.baseline_text)}</pre></section>
        <section><strong>This setting</strong><pre>${escape(example.text)}</pre></section></div>
        <p class='detail-note'>${escape(example.cell_id ?? '')} · ${escape(example.kind ?? '')}</p>
        <details><summary>Official verdict and benchmark context</summary>
          <p class='detail-note'>Context is used only for this audit. Official scores remain unchanged.</p>
          <pre>${escape(example.evidence ?? '')}</pre><pre>${escape(example.context ?? '')}</pre>
          ${example.official_evidence ? `<details><summary>Retained judge rationale and spans</summary><pre>${escape(JSON.stringify(example.official_evidence, null, 2))}</pre></details>` : ''}
        </details></details>`);
    }
  } else {
    parts.push(`<p class='detail-note'>Expanded qualitative review is pending. The preserved original study includes earlier paired examples.</p>`);
  }
  element('detail-content').innerHTML = parts.join('');
  element('detail').showModal();
}

function showFindings() {
  const defaults = [
    {title: 'A broader comparison is underway', detail: 'Every usable setting receives the same complete four-task banks. A small pilot is not used to rule out methods.'},
    {title: 'Completed results remain available', detail: 'The original study and its 12 complete methods are preserved. New settings are added as their full grids finish.'},
    {title: 'Read uncertainty alongside the effect', detail: 'Per-method intervals and paired changes answer different questions. No single average combines the four task endpoints.'},
  ];
  const findings = data.findings.length ? data.findings : defaults;
  element('findings').innerHTML = findings.slice(0, 3).map(finding =>
    `<article class='finding'><h3>${escape(finding.title)}</h3><p>${escape(finding.detail)}</p></article>`).join('');
}

function projectAccounting(ledger) {
  const rows = ledger.global_commitment ?? [];
  const sum = (status, field) => rows.filter(row => row.status === status).reduce((n, row) => n + (row[field] ?? 0), 0);
  const settled = sum('settled', 'actual_usd');
  const unknown = sum('unknown', 'reserved_usd');
  const pending = sum('reserved', 'reserved_usd');
  return {settled, unknown, pending, committed: settled + unknown + pending, ceiling: ledger.limits.hard};
}

function showResources() {
  const r = data.resources;
  element('resources-section').hidden = !r;
  if (!r) return;
  const buckets = r.ledger_audit.buckets;
  const helpers = Object.entries(buckets).filter(([key]) => key !== 'experimental_benchmark_judging');
  const helperCost = helpers.reduce((sum, [, row]) => sum + row.actual_usage_estimate_usd, 0);
  const helperCalls = helpers.reduce((sum, [, row]) => sum + row.physical_settled_attempts, 0);
  const judge = buckets.experimental_benchmark_judging;
  const money = v => `$${(v ?? 0).toFixed(2)}`;
  const project = projectAccounting(r.ledger_audit);
  const summaries = [
    ['Project API usage', money(project.settled), `Estimated settled usage across the whole project, including earlier stages. Retained unknown holds: ${money(project.unknown)}; live pending reservations: ${money(project.pending)}. Total commitment: ${money(project.committed)} of the authorized ${money(project.ceiling)} ceiling. API only; excludes GPU costs and Codex agent billing.`],
    ['Shared method helper phases', money(helperCost), `${helperCalls.toLocaleString()} settled physical attempts. Campaign labels and edits are reused across variants; this is not a per-method deployment price.`],
    ['Experimental benchmark judging', money(judge?.actual_usage_estimate_usd), `${(judge?.physical_settled_attempts ?? 0).toLocaleString()} settled physical attempts. Used to measure this study; excluded from new-input inference.`],
    ['New-input engineering measurement', `${r.new_input_measurements.cold_pipeline_through_first_selection_seconds.toFixed(1)} s`, 'One separate synthetic N32 input at layer 44; includes fresh generation and reconstruction. This is not an average serving latency.'],
  ];
  element('resources').innerHTML = `<p class='note'>${r.status === 'complete_retrospective' ? 'Terminal' : 'Partial'} resource snapshot generated: ${escape(r.generated_utc)}. Settled API usage cutoff: ${escape(r.ledger_audit.settlement_cutoff_utc)}. Usage-derived estimates, not reconciled invoices. GPU dollars are unavailable; financial holds remain committed.</p>
    <div class='resource-grid'>${summaries.map(([title, value, text]) => `<article><h3>${title}</h3><strong>${value}</strong><p>${text}</p></article>`).join('')}</div>
    <details><summary>Measured phase usage and scope</summary>${Object.entries(buckets).map(([key, row]) => `<p><strong>${escape(key.replaceAll('_', ' '))}</strong>: ${money(row.actual_usage_estimate_usd)}; ${row.physical_settled_attempts.toLocaleString()} physical attempts; ${row.input_tokens.toLocaleString()} input / ${row.output_tokens.toLocaleString()} output tokens; ${row.cached_input_tokens.toLocaleString()} cached input tokens.</p>`).join('')}
    ${r.benchmark_observed_log_counters ? `<p>Completed judge-pass logs retain ${r.benchmark_observed_log_counters.observed_logical_invocations.toLocaleString()} logical invocations, including ${r.benchmark_observed_log_counters.observed_validated_cache_returns.toLocaleString()} validated cache returns.</p><p class='note'>${escape(r.benchmark_observed_log_counters.scope)}</p>` : ''}
    <p class='note'>${escape(r.ledger_audit.benchmark_instrumentation_note)}</p><p class='note'>${escape(r.limits.join(' '))}</p></details>`;
}

async function start() {
  try {
    const embedded = element('embedded-data');
    if (embedded) data = JSON.parse(embedded.textContent);
    else {
      const response = await fetch('expansion-data.json', {cache: 'no-store'});
      if (!response.ok) throw Error('Data request failed');
      data = await response.json();
    }
    const complete = data.conditions.filter(condition => families.every(family =>
      data.cohorts.full.rows.some(row => row.condition === condition.condition_id &&
        row.family === family && row.metric?.value != null))).length;
    const finished = data.status === 'complete' || data.status === 'complete_exploratory';
    element('status').textContent = finished ? 'Expanded comparison complete' : 'Expanded comparison running';
    element('coverage').textContent = `${complete} / ${data.conditions.length} settings cover all four tasks`;
    element('updated').textContent = `Scientific source snapshot: ${new Date(data.updated_utc).toLocaleString()}`;
    populateReferences();
    setupTradeoff();
    showFindings();
    showResources();
    element('scaling-metric').querySelector('[value="reconstruction"]').disabled = !data.reconstruction;
    element('scaling-metric').addEventListener('change', scaling);
    for (const id of ['cohort', 'view', 'reference', 'search']) {
      element(id).addEventListener(id === 'search' ? 'input' : 'change', render);
    }
    element('expand-all').addEventListener('click', () => {
      allExpanded = !allExpanded;
      expanded = allExpanded ? new Set(Object.keys(groups)) : new Set();
      element('expand-all').textContent = allExpanded ? 'Collapse all settings' : 'Expand all settings';
      render();
    });
    element('close-detail').addEventListener('click', () => element('detail').close());
    render();
  } catch (error) {
    element('status').textContent = 'Results could not be loaded';
    element('coverage').textContent = 'Open the preserved original study';
    element('updated').textContent = error.message;
  }
}

start();
