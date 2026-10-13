/* Overlay existing full-bank task and reconstruction means on separate axes. */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct = v => Number.isFinite(v) ? `${(100 * v).toFixed(1)}%` : 'Unavailable';
  const budgets = [1, 2, 4, 8, 16, 32];
  let lastSource;
  const families = [
    ['hallucination', 'Hallucination (chat)', 'Contradicted specific readouts', 'lower'],
    ['multihop_mt', 'Multihop (multi-token)', 'Questions recovering all required intermediate names', 'higher'],
    ['chain_intermediates', 'Chained intermediates', 'Questions recovering a required first-ranked intermediate number', 'higher'],
    ['role_bound_association', 'Role-bound association', 'Questions recovering the entity–role binding', 'higher'],
  ];
  const bounds = measurements => {
    const values = measurements.flatMap(m => m?.value == null ? [] : [m.value, ...(m.ci95 ?? [])]).filter(Number.isFinite);
    if (!values.length) return [0, 1];
    const min = Math.min(...values), max = Math.max(...values), pad = Math.max(.025, (max - min) * .16);
    return [Math.max(0, Math.floor((min - pad) * 20) / 20), Math.min(1, Math.ceil((max + pad) * 20) / 20)];
  };
  window.renderSamplingOverlay = source => {
    lastSource = source;
    el('headline-scope').textContent = source.cohorts.full.scope;
    el('scaling-note').textContent = 'Blue circles use the left task axis; amber squares use the right AR reconstruction axis. Axes have separate scales: line crossings do not mean equal values. Error bars show existing grouped pointwise 95% intervals for task rates only, not paired-change intervals. AR intervals remain available on hover or focus. AR fit averages activation sites; the recovery tasks aggregate questions. This overlay is available only for all 469 questions, matching the reconstruction data. No fitted scaling law or new evaluation.';
    el('scaling').innerHTML = families.map(([family, title, endpoint, direction]) => {
      const metric = id => source.cohorts.full.rows.find(r => r.condition === id && r.family === family)?.metric;
      const original = metric('raw_n1-n1');
      const rows = budgets.map(n => {
        const id = `best_n_exact-n${n}`;
        const r = source.reconstruction.rows.find(r => r.condition === id && r.family === family);
        return {n, q:metric(id), r:r ? {value:r.mean_fve,ci95:r.mean_fve_ci95,sites:r.scored_site_count,intended:r.full_site_count} : null};
      });
      const [ql, qh] = bounds([...rows.map(r => r.q), original]);
      const [rl, rh] = bounds(rows.map(r => r.r));
      const compact = window.innerWidth < 650;
      const width = compact ? 390 : 520, left = 60, right = width - 60, top = 46, bottom = 246, height = 305;
      const x = n => left + budgets.indexOf(n) * (right - left) / 5;
      const qy = v => bottom - (v - ql) * (bottom - top) / (qh - ql);
      const ry = v => bottom - (v - rl) * (bottom - top) / (rh - rl);
      const parts=[];
      for (let i=0;i<=4;i++) {
        const v=ql+(qh-ql)*i/4, a=rl+(rh-rl)*i/4, y=bottom-(bottom-top)*i/4;
        parts.push(`<path d="M${left} ${y}H${right}" fill="none" stroke="#e4ebf1"/><text class="so-task-label" x="${left-8}" y="${y+4}" text-anchor="end">${pct(v)}</text><text class="so-fit-label" x="${right+8}" y="${y+4}">${pct(a)}</text>`);
      }
      parts.push(`<path d="M${left} ${top}V${bottom}H${right}V${top}" stroke="#a2b4c2" fill="none"/>`);
      if (Number.isFinite(original?.value)) parts.push(`<path d="M${left} ${qy(original.value)}H${right}" stroke="#637584" stroke-dasharray="3 4"><title>Original released lens task rate: ${pct(original.value)}</title></path>`);
      for (const [key,y,color] of [['q',qy,'#246ea3'],['r',ry,'#a96628']]) {
        rows.forEach((row,i)=>{
          const value=row[key]?.value, ci=row[key]?.ci95;
          if (!Number.isFinite(value)) return;
          const previous=rows[i-1]?.[key]?.value;
          if(Number.isFinite(previous))parts.push(`<path d="M${x(rows[i-1].n)} ${y(previous)}L${x(row.n)} ${y(value)}" fill="none" stroke="${color}" stroke-width="2" ${key==='r'?'stroke-dasharray="7 3"':''}/>`);
          if(key==='q'&&ci)parts.push(`<path class="so-task-interval" d="M${x(row.n)} ${y(ci[0])}V${y(ci[1])}M${x(row.n)-4} ${y(ci[0])}H${x(row.n)+4}M${x(row.n)-4} ${y(ci[1])}H${x(row.n)+4}" stroke="${color}" stroke-width="1.5" opacity=".85" fill="none"/>`);
          const what=key==='q'?`${endpoint}: ${pct(value)}; ${row.q.numerator}/${row.q.denominator}`:`AR reconstruction: ${pct(value)}; ${row.r.sites}/${row.r.intended} sites`;
          const hint=`${row.n} samples. ${what}. ${ci?`95% interval ${pct(ci[0])} to ${pct(ci[1])}.`:'Interval unavailable.'}`;
          parts.push(`<g class="so-point" tabindex="0" role="img" aria-label="${esc(hint)}" data-series="${key==='q'?'task':'reconstruction'}" data-family="${family}" data-n="${row.n}" data-value="${value}"><title>${esc(hint)}</title>${key==='q'?`<circle cx="${x(row.n)}" cy="${y(value)}" r="4" fill="${color}"/>`:`<rect x="${x(row.n)-4}" y="${y(value)-4}" width="8" height="8" fill="${color}"/>`}</g>`);
        });
      }
      budgets.forEach(n=>parts.push(`<text x="${x(n)}" y="${bottom+22}" text-anchor="middle">${n}</text>`));
      parts.push(`<text class="so-task-label" x="${left}" y="19">Task rate · left</text><text class="so-fit-label" x="${right}" y="19" text-anchor="end">AR fit · right</text><text x="${(left+right)/2}" y="${height-12}" text-anchor="middle">Samples per activation</text>`);
      return `<article class="curve-box sampling-overlay" id="samples-${family}"><div class="chart-heading"><h3>${title}</h3><button class="chart-expand" type="button" data-expand-chart="samples-${family}" data-chart-title="${title}: task quality and AR reconstruction">Enlarge</button></div><p>${endpoint}; ${direction} is better. AR fit: higher is better.</p><p class="original-reference"><strong>Original released lens: ${pct(original?.value)}</strong> (gray dashed line). Four-bullet original: ${pct(metric('capped_n1-n1')?.value)}.</p><p class="so-endpoints"><span class="so-task-label">Task: ${pct(rows[0].q?.value)} → ${pct(rows[5].q?.value)}</span><span class="so-fit-label">AR: ${pct(rows[0].r?.value)} → ${pct(rows[5].r?.value)}</span></p><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${title}: task rate on left axis, reconstruction on right axis, both against sample count">${parts.join('')}</svg></article>`;
    }).join('');
  };
  window.addEventListener('resize', () => {
    if (lastSource && el('scaling-metric')?.value === 'both') window.renderSamplingOverlay(lastSource);
  });
  if (typeof data !== 'undefined' && data && el('scaling-metric')?.value === 'both') window.renderSamplingOverlay(data);
})();
