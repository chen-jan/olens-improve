/* Display-only comparison of frozen full-bank results. No new scoring. */
(() => {
  'use strict';
  const root = document.getElementById('fit-quality');
  if (!root) return;
  const settings = [
    ['More samples', 'best_n_exact-n32', 'capped_n1-n1', '#246ea3'],
    ['Keep repeats', 'consensus_semantic_v5_support0.125_compaton_vetoon-n16', 'consensus_exact_support0-n16', '#926124'],
    ['Remove weak bullets', 'prune_loo_a32_0.005-n32', 'best_n_exact-n32', '#a64e5c'],
    ['Combine bullets', 'pooled_greedy_swap-n32', 'capped_n1-n1', '#13756c'],
    ['Edit pooled text', 'editing_round2-n32', 'pooled_greedy_swap-n32', '#745b99'],
    ['Combine + prune', 'pooled_greedy_swap_then_prune_0.005-n32', 'pooled_greedy_swap-n32', '#536b31'],
  ].map(([label, id, parent, color], i) => ({label, id, parent, color, number: i + 1}));
  const families = [
    ['hallucination', 'Hallucination (chat)', 'Contradicted specific readouts; lower is better.', true],
    ['multihop_mt', 'Multihop (multi-token)', 'Questions recovering all required intermediate names; higher is better.', false],
    ['chain_intermediates', 'Chained intermediates', 'Questions recovering a required first-ranked intermediate number; higher is better.', false],
    ['role_bound_association', 'Role-bound association', 'Questions recovering the entity–role binding; higher is better.', false],
  ];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct = (v, digits = 1) => Number.isFinite(v) ? `${(v * 100).toFixed(digits)}%` : 'Unavailable';
  const interval = (ci, digits = 1) => ci ? `${pct(ci[0], digits)} to ${pct(ci[1], digits)}` : 'unavailable';
  let source;
  const quality = (id, family) => source.cohorts.full.rows.find(r => r.condition === id && r.family === family)?.metric;
  const fit = (id, family) => source.reconstruction?.rows.find(r => r.condition === id && r.family === family);
  const name = id => source.conditions.find(r => r.condition_id === id)?.label ?? id;
  const point = (id, family) => ({id, q: quality(id, family), r: fit(id, family)});
  const valid = p => Number.isFinite(p?.q?.value) && Number.isFinite(p?.r?.mean_fve);
  const hint = (p, label) => `${label}: AR reconstruction ${pct(p.r?.mean_fve, 2)} (95% ${interval(p.r?.mean_fve_ci95, 2)}); task rate ${pct(p.q?.value)} (95% ${interval(p.q?.ci95)}). ${p.q?.numerator ?? '?'} / ${p.q?.denominator ?? '?'}; ${p.r?.scored_site_count ?? '?'} / ${p.r?.full_site_count ?? '?'} reconstruction sites.`;
  const extent = values => {
    const lo = Math.min(...values), hi = Math.max(...values);
    const pad = Math.max(.025, (hi - lo) * .12);
    return [Math.max(0, Math.floor((lo - pad) * 20) / 20), Math.min(1, Math.ceil((hi + pad) * 20) / 20)];
  };

  function render() {
    const chosen = document.getElementById('fit-quality-method').value;
    const selected = settings.filter(s => chosen === 'all' || s.id === chosen);
    const parents = document.getElementById('fit-quality-parents').checked;
    document.querySelectorAll('#fit-quality-legend button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.method === chosen)));
    document.getElementById('fit-quality-preview').textContent = 'Hover or focus a numbered dot for both values and uncertainty; select it for the existing method details.';
    document.getElementById('fit-quality-plots').innerHTML = families.map(([family, title, explanation, errors], fi) => {
      const rows = selected.map(s => ({s, p: point(s.id, family), parent: point(s.parent, family)}));
      const capped = point('capped_n1-n1', family);
      const original = quality('raw_n1-n1', family);
      const plotted = rows.flatMap(r => [r.p, ...(parents ? [r.parent] : [])]).concat([capped]).filter(valid);
      if (!plotted.length) return `<article><h3>${title}</h3><p>Comparable reconstruction unavailable.</p></article>`;
      const [xl, xh] = extent(plotted.flatMap(p => [p.r.mean_fve, ...(p.r.mean_fve_ci95 ?? [])]));
      const [yl, yh] = extent([...plotted.flatMap(p => [p.q.value, ...(p.q.ci95 ?? [])]), ...(original ? [original.value, ...(original.ci95 ?? [])] : [])]);
      const compact = window.innerWidth < 650;
      const w = compact ? 390 : 520, left = compact ? 64 : 70, right = w - 22, top = 34, bottom = 274, h = 332;
      const x = v => left + (right - left) * (v - xl) / (xh - xl);
      const y = v => errors ? top + (bottom - top) * (v - yl) / (yh - yl) : bottom - (bottom - top) * (v - yl) / (yh - yl);
      const bits = [];
      for (let i = 0; i <= 4; i++) {
        const xv = xl + i * (xh - xl) / 4, yv = yl + i * (yh - yl) / 4;
        bits.push(`<path d="M${x(xv)} ${top}V${bottom}M${left} ${y(yv)}H${right}" stroke="#e4ebf1" fill="none"/>`);
        bits.push(`<text x="${x(xv)}" y="${bottom + 21}" text-anchor="middle">${pct(xv, 0)}</text><text x="${left - 9}" y="${y(yv) + 4}" text-anchor="end">${pct(yv, 0)}</text>`);
      }
      bits.push(`<path d="M${left} ${top}V${bottom}H${right}" fill="none" stroke="#95a9b8"/>`);
      if (Number.isFinite(original?.value)) {
        bits.push(`<path class="fq-original-line" d="M${left} ${y(original.value)}H${right}" stroke="#19344b" stroke-dasharray="5 4"><title>Original released Oracle Lens: ${pct(original.value)}</title></path>`);
      }
      if (parents) rows.forEach(({s, p, parent}) => {
        if (!valid(p) || !valid(parent)) return;
        const dx = x(p.r.mean_fve) - x(parent.r.mean_fve), dy = y(p.q.value) - y(parent.q.value);
        if (Math.hypot(dx, dy) > 12) {
          const a = Math.atan2(dy, dx), length = Math.hypot(dx, dy) - 11;
          const ex = x(parent.r.mean_fve) + Math.cos(a) * length, ey = y(parent.q.value) + Math.sin(a) * length;
          bits.push(`<path class="fq-parent-arrow" d="M${x(parent.r.mean_fve)} ${y(parent.q.value)}L${ex} ${ey}" fill="none" stroke="${s.color}" stroke-width="1.7" opacity=".6" marker-end="url(#fq-arrow-${fi}-${s.number})"><title>${esc(name(s.parent))} → ${esc(s.label)}; connects point estimates.</title></path>`);
        }
        bits.push(`<circle class="fq-parent" cx="${x(parent.r.mean_fve)}" cy="${y(parent.q.value)}" r="4" fill="white" stroke="${s.color}" stroke-width="1.6"><title>${esc(hint(parent, 'Starting method: ' + name(s.parent)))}</title></circle>`);
      });
      if (valid(capped)) {
        const cx = x(capped.r.mean_fve), cy = y(capped.q.value);
        bits.push(`<path class="fq-capped" d="M${cx} ${cy - 7}L${cx + 7} ${cy}L${cx} ${cy + 7}L${cx - 7} ${cy}Z" fill="white" stroke="#19344b" stroke-width="2"><title>${esc(hint(capped, 'Original, four bullets'))}</title></path>`);
      }
      rows.forEach(({s, p}) => {
        if (!valid(p)) return;
        const cx = x(p.r.mean_fve), cy = y(p.q.value), xc = p.r.mean_fve_ci95, yc = p.q.ci95;
        const warnings = [...(p.r.mean_fve_warnings ?? []), ...(p.q.warnings ?? [])].join(' ');
        const label = hint(p, s.label) + (warnings ? ' ' + warnings : '');
        bits.push(`<g class="fq-point" tabindex="0" role="button" aria-label="${esc(label)}" data-condition="${esc(s.id)}" data-family="${family}" data-reference="${esc(s.parent)}" data-ar-value="${p.r.mean_fve}" data-task-value="${p.q.value}" data-preview="${esc(label)}"><title>${esc(label)}</title>`);
        if (xc) bits.push(`<path class="fq-interval" d="M${x(xc[0])} ${cy}H${x(xc[1])}M${x(xc[0])} ${cy - 3}V${cy + 3}M${x(xc[1])} ${cy - 3}V${cy + 3}" stroke="${s.color}"/>`);
        if (yc) bits.push(`<path class="fq-interval" d="M${cx} ${y(yc[0])}V${y(yc[1])}M${cx - 3} ${y(yc[0])}H${cx + 3}M${cx - 3} ${y(yc[1])}H${cx + 3}" stroke="${s.color}"/>`);
        bits.push(`<circle cx="${cx}" cy="${cy}" r="10" fill="${s.color}" stroke="white" stroke-width="1.5"/><text class="fq-number" x="${cx}" y="${cy + 4}" text-anchor="middle">${s.number}</text></g>`);
      });
      bits.push(`<text x="${(left + right) / 2}" y="${h - 13}" text-anchor="middle">AR reconstruction (%) →</text><text transform="translate(17 ${(top + bottom) / 2}) rotate(-90)" text-anchor="middle">${errors ? 'Contradicted readouts (%)' : 'Questions recovered (%)'}</text><text x="${right}" y="18" text-anchor="end">Better task result ↑</text>`);
      const defs = settings.map(s => `<marker id="fq-arrow-${fi}-${s.number}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="${s.color}"/></marker>`).join('');
      const overlap = rows.some((a, i) => rows.some((b, j) => i < j && valid(a.p) && valid(b.p) && Math.hypot(x(a.p.r.mean_fve) - x(b.p.r.mean_fve), y(a.p.q.value) - y(b.p.q.value)) < 20));
      const selectedValues = rows.length === 1 ? `<p class="fq-selected-values"><strong>${esc(rows[0].s.label)}</strong><br>AR reconstruction: <strong>${pct(rows[0].p.r?.mean_fve, 2)}</strong> · ${errors ? 'Contradicted readouts' : 'Questions recovered'}: <strong>${pct(rows[0].p.q?.value)}</strong></p>` : '';
      return `<article class="fq-panel" id="fit-quality-${family}"><div class="chart-heading"><h3>${title}</h3><button type="button" class="chart-expand" data-expand-chart="fit-quality-${family}" data-chart-title="${title}: reconstruction and task performance">Enlarge</button></div><p class="fq-endpoint">${explanation}</p><p class="original-reference"><strong>Original released lens: ${pct(original?.value)}</strong><br>Four-bullet original: ${pct(capped.q?.value)}; AR fit ${pct(capped.r?.mean_fve, 2)}.</p><svg viewBox="0 0 ${w} ${h}" role="group" aria-label="${title}: AR reconstruction horizontally and task rate vertically, with higher performance toward the upper right"><defs>${defs}</defs>${bits.join('')}</svg>${selectedValues}${overlap ? '<p class="fq-overlap">Some methods overlap. Choose one above to inspect its values and starting point.</p>' : ''}</article>`;
    }).join('');
    root.querySelectorAll('.fq-point').forEach(p => {
      const preview = () => { document.getElementById('fit-quality-preview').textContent = p.dataset.preview; };
      p.addEventListener('pointerenter', preview); p.addEventListener('focus', preview);
      const open = () => { if (typeof window.detail === 'function') window.detail(p.dataset.condition, p.dataset.reference); };
      p.addEventListener('click', open);
      p.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
  }

  function initialize(data) {
    source = data;
    document.getElementById('fit-quality-method').innerHTML = '<option value="all">All six methods</option>' + settings.map(s => `<option value="${s.id}">${s.number}. ${s.label}</option>`).join('');
    document.getElementById('fit-quality-legend').innerHTML = settings.map(s => `<button type="button" data-method="${s.id}" aria-pressed="false"><span style="background:${s.color}">${s.number}</span>${s.label}</button>`).join('');
    document.getElementById('fit-quality-legend').addEventListener('click', e => {
      const b = e.target.closest('button[data-method]'); if (!b) return;
      const select = document.getElementById('fit-quality-method'); select.value = select.value === b.dataset.method ? 'all' : b.dataset.method; render();
    });
    for (const id of ['fit-quality-method', 'fit-quality-parents']) document.getElementById(id).addEventListener('change', render);
    window.addEventListener('resize', render);
    document.getElementById('fit-quality-values').innerHTML = families.map(([family, title, explanation]) => `<h3>${title}</h3><p>${explanation}</p><div class="table-wrap"><table><thead><tr><th>Method</th><th>AR reconstruction</th><th>Task rate</th><th>Starting method</th></tr></thead><tbody>${settings.map(s => {
      const p = point(s.id, family);
      return `<tr><td>${s.number}. ${s.label}</td><td>${pct(p.r?.mean_fve, 2)}<small>95%: ${interval(p.r?.mean_fve_ci95, 2)}</small></td><td>${pct(p.q?.value)}<small>95%: ${interval(p.q?.ci95)}; ${p.q?.numerator ?? '?'} / ${p.q?.denominator ?? '?'}</small></td><td>${esc(name(s.parent))}</td></tr>`;
    }).join('')}</tbody></table></div>`).join('');
    render();
  }
  const embedded = document.getElementById('embedded-data');
  try {
    if (embedded) initialize(JSON.parse(embedded.textContent));
    else fetch('expansion-data.json').then(r => { if (!r.ok) throw Error('Data request failed'); return r.json(); }).then(initialize).catch(e => { document.getElementById('fit-quality-preview').textContent = e.message; });
  } catch (e) { document.getElementById('fit-quality-preview').textContent = `Comparison unavailable: ${e.message}`; }
})();
