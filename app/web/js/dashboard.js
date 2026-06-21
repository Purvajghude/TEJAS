/* TEJAS - modern glass dashboard */
(function () {
  const D = window.TEJAS || {};
  const $ = (id) => document.getElementById(id);
  const fmt = new Intl.NumberFormat('en', { maximumFractionDigits: 1 });
  const fmtInt = new Intl.NumberFormat('en', { maximumFractionDigits: 0 });
  const classColor = { A: '#aaa79c', B: '#aaa79c', C: '#b28a4a', M: '#a8614b', X: '#10100f' };
  const chartRegistry = new Map();

  const icon = {
    flare: '<svg viewBox="0 0 24 24"><path d="M12 3c3 3 5 5.4 5 9a5 5 0 0 1-10 0c0-2.4 1.6-4.2 3.2-5.7-.2 2.5.9 4 2.2 5.1.8-1.2 1.2-2.3 1-4.1"></path></svg>',
    link: '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.2 1.2"></path><path d="M14 11a5 5 0 0 0-7.1 0l-2 2a5 5 0 0 0 7.1 7.1l1.2-1.2"></path></svg>',
    clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>',
    target: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"></circle><circle cx="12" cy="12" r="3"></circle><path d="M12 2v4M12 18v4M2 12h4M18 12h4"></path></svg>',
    trend: '<svg viewBox="0 0 24 24"><path d="M4 17l5-6 4 3 7-9"></path><path d="M15 5h5v5"></path></svg>',
    shield: '<svg viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 4.5-2.8 8.1-7 10-4.2-1.9-7-5.5-7-10V6l7-3z"></path><path d="M9 12l2 2 4-5"></path></svg>'
  };

  function safe(value, fallback = '—') {
    return value == null || Number.isNaN(value) ? fallback : value;
  }

  function pct(value) {
    return value == null ? '—' : `${Math.round(value * 100)}%`;
  }

  function shortDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return `${d.toISOString().slice(0, 10)} · ${d.toISOString().slice(11, 16)} UTC`;
  }

  function positive(v) {
    return v && Number.isFinite(v) && v > 0 ? v : null;
  }

  const meta = D.meta || {};
  const k = D.kpis || {};
  const fusion = D.fusion || {};
  const fc = D.forecast || {};
  const ens = D.ensemble || {};
  const ftrack = ens.track || { t: [], p: [] };
  // Forecast track as [ms, prob] for fast lookup during replay.
  const fcurve = (ftrack.t || []).map((t, i) => [Date.parse(t), ftrack.p[i]]);
  const fcThreshold = (ens.lowFarThreshold != null) ? ens.lowFarThreshold : null;
  const wf = fc.walkForward || {};
  const flares = (D.flares || []).slice().sort((a, b) => Date.parse(a.t) - Date.parse(b.t));
  const latest = flares[flares.length - 1] || {};
  const auc15 = fc.skillCurve && fc.skillCurve.length ? fc.skillCurve[0].auc : null;
  const medianLead = fc.leadMedian != null ? fc.leadMedian : null;
  const neupertLead = fusion.neupertLeadMedianS != null ? fusion.neupertLeadMedianS / 60 : null;

  // Meta and headline copy.
  $('dateRange').textContent = `${safe(meta.dateStart)} → ${safe(meta.dateEnd)} · ${safe(meta.nDays, 0)} days`;
  $('coverageText').textContent = `${safe(meta.nDays, 0)} observing days · ${fmtInt.format(k.nFlares || 0)} flares catalogued`;
  $('coverageMini').textContent = `${safe(meta.dateStart)} — ${safe(meta.dateEnd)}`;
  $('footerMeta').textContent = `SoLEXS · HEL1OS · GOES · ${safe(meta.nDays, 0)} days`;
  $('calR').textContent = D.calib && D.calib.r != null ? D.calib.r.toFixed(3) : '—';
  $('latestClass').textContent = latest.cls || '—';
  $('latestEvent').textContent = latest.id ? `${latest.id} · GOES ${latest.clsGoes || latest.cls}` : 'Awaiting data';
  $('latestTime').textContent = shortDate(latest.t);
  $('outlookAuc').textContent = auc15 != null ? `${auc15.toFixed(2)} AUC` : '— AUC';
  $('outlookLead').textContent = medianLead != null ? `${medianLead} min` : '— min';
  $('statusText').textContent = `${fmtInt.format(k.nFlares || 0)} validated detections`;
  $('feedCount').textContent = flares.length;

  // KPI cards.
  const kpis = [
    { value: fmtInt.format(k.nFlares || 0), label: 'Flares detected', accent: '#10100f', soft: 'rgba(16,16,15,.055)', icon: icon.flare },
    { value: fmtInt.format(fusion.nDualConfirmed || 0), label: 'Soft + hard confirmed', accent: '#a8614b', soft: 'rgba(168,97,75,.12)', icon: icon.link },
    { value: neupertLead != null ? `${neupertLead.toFixed(1)}m` : '—', label: 'Median Neupert lead', accent: '#7f907b', soft: 'rgba(127,144,123,.13)', icon: icon.clock },
    { value: auc15 != null ? auc15.toFixed(2) : '—', label: 'Forecast AUC at 15m', accent: '#b28a4a', soft: 'rgba(178,138,74,.14)', icon: icon.trend },
    { value: pct(k.agreement), label: 'GOES class agreement', accent: '#626e59', soft: 'rgba(98,110,89,.13)', icon: icon.target },
    { value: k.xRecovered ? `${k.xRecovered[0]}/${k.xRecovered[1]}` : '—', label: 'X-class recovered', accent: '#10100f', soft: 'rgba(16,16,15,.06)', icon: icon.shield },
  ];
  $('kpiGrid').innerHTML = kpis.map(item => `
    <article class="kpi glass-surface reveal" style="--accent:${item.accent};--accent-soft:${item.soft}">
      <span class="kpi-icon">${item.icon}</span>
      <div class="v">${item.value}</div>
      <div class="l">${item.label}</div>
    </article>`).join('');

  // Forecast stats.
  const fcStats = [
    [auc15 != null ? auc15.toFixed(2) : '—', 'AUC @15m'],
    [medianLead != null ? `${medianLead}m` : '—', 'Median lead'],
    [fc.eventRecall != null ? pct(fc.eventRecall) : '—', 'M+ event recall'],
    [wf.ROC_AUC_mean != null ? wf.ROC_AUC_mean.toFixed(2) : '—', 'Walk-forward AUC'],
  ];
  $('fcStats').innerHTML = fcStats.map(([v, l]) => `<div class="valcell"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');

  // Navigation active state.
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => item.addEventListener('click', () => {
    navItems.forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    if (item.getAttribute('href') === '#forecasting') {
      const fdContainer = $('forecastDropdown');
      const fdBtn = $('forecastDropdownBtn');
      if (fdContainer && fdBtn && !fdContainer.classList.contains('is-open')) {
        fdBtn.click();
      }
    }
  }));

  // ECharts theme helpers.
  const lightAxis = {
    axisLine: { lineStyle: { color: 'rgba(21,21,20,.22)' } },
    axisTick: { lineStyle: { color: 'rgba(21,21,20,.18)' } },
    axisLabel: { color: '#858781', fontSize: 10, fontWeight: 600 },
    splitLine: { lineStyle: { color: 'rgba(21,21,20,.075)' } }
  };
  const darkAxis = {
    axisLine: { lineStyle: { color: 'rgba(247,244,234,.20)' } },
    axisTick: { lineStyle: { color: 'rgba(247,244,234,.18)' } },
    axisLabel: { color: 'rgba(247,244,234,.50)', fontSize: 10, fontWeight: 600 },
    splitLine: { lineStyle: { color: 'rgba(247,244,234,.075)' } }
  };
  const lightTooltip = {
    backgroundColor: 'rgba(255,255,252,.92)', borderColor: 'rgba(21,21,20,.12)', borderWidth: 1,
    textStyle: { color: '#151514', fontSize: 12 }, extraCssText: 'box-shadow:0 18px 38px rgba(30,30,26,.14);border-radius:14px;backdrop-filter:blur(18px);'
  };
  const darkTooltip = {
    backgroundColor: 'rgba(247,244,234,.94)', borderColor: 'rgba(255,255,255,.16)', borderWidth: 1,
    textStyle: { color: '#151514', fontSize: 12 }, extraCssText: 'box-shadow:0 22px 42px rgba(0,0,0,.24);border-radius:14px;'
  };

  function registerChart(id, chart) {
    chartRegistry.set(id, chart);
    return chart;
  }

  function resizeCharts(delay = 0) {
    window.setTimeout(() => chartRegistry.forEach(chart => chart.resize()), delay);
  }

  const light = D.light || { t: [], counts: [], hard: [], xrsb: [] };
  const hasHard = light.hard && light.hard.some(v => v != null && v > 0);
  const lightChart = registerChart('chartLight', echarts.init($('chartLight'), null, { renderer: 'canvas' }));
  lightChart.setOption({
    backgroundColor: 'transparent', animationDuration: 1100, animationEasing: 'cubicOut',
    grid: { left: 54, right: 54, top: 42, bottom: 34 },
    legend: { top: 0, right: 0, itemWidth: 18, itemHeight: 8, textStyle: { color: 'rgba(247,244,234,.62)', fontSize: 11, fontWeight: 600 } },
    tooltip: { trigger: 'axis', ...darkTooltip },
    xAxis: { type: 'time', ...darkAxis },
    yAxis: [
      { type: 'log', name: 'counts', nameTextStyle: { color: 'rgba(247,244,234,.48)', fontSize: 10, fontWeight: 700 }, ...darkAxis },
      { type: 'log', name: 'GOES W/m²', position: 'right', nameTextStyle: { color: 'rgba(247,244,234,.48)', fontSize: 10, fontWeight: 700 }, ...darkAxis, splitLine: { show: false } },
      { type: 'value', min: 0, max: 1, position: 'right', offset: 0, show: false }
    ],
    series: [
      { name: 'SoLEXS soft', type: 'line', showSymbol: false, sampling: 'lttb', smooth: .18,
        data: light.t.map((t, i) => [t, positive(light.counts[i])]),
        lineStyle: { color: '#f7f4ea', width: 1.65 }, areaStyle: { color: 'rgba(247,244,234,.10)' },
        markLine: { silent: true, symbol: 'none', lineStyle: { color: 'rgba(247,244,234,.72)', width: 1.4 }, data: [] } },
      { name: 'HEL1OS hard', type: 'line', showSymbol: false, sampling: 'lttb', smooth: .12,
        data: hasHard ? light.t.map((t, i) => [t, positive(light.hard[i])]) : [],
        lineStyle: { color: '#c98265', width: 1.35 }, areaStyle: { color: 'rgba(201,130,101,.09)' } },
      { name: 'GOES', type: 'line', yAxisIndex: 1, showSymbol: false, sampling: 'lttb', smooth: .2,
        data: light.t.map((t, i) => [t, positive(light.xrsb[i])]),
        lineStyle: { color: '#a8b49c', width: 1.35 } },
      { name: 'Forecast risk', type: 'line', yAxisIndex: 2, showSymbol: false, sampling: 'lttb', smooth: .15,
        data: fcurve.map(([ms, p]) => [new Date(ms).toISOString(), p]),
        lineStyle: { color: '#b28a4a', width: 1.2, opacity: .9 }, areaStyle: { color: 'rgba(178,138,74,.10)' },
        markLine: fcThreshold != null ? { silent: true, symbol: 'none',
          lineStyle: { color: 'rgba(178,138,74,.55)', width: 1, type: 'dashed' },
          label: { formatter: 'alert', color: 'rgba(178,138,74,.8)', fontSize: 9 },
          data: [{ yAxis: fcThreshold }] } : { data: [] } }
    ]
  });

  const letters = ['A', 'B', 'C', 'M', 'X'];
  const distChart = registerChart('chartDist', echarts.init($('chartDist')));
  distChart.setOption({
    backgroundColor: 'transparent', animationDuration: 900, animationEasing: 'cubicOut',
    grid: { left: 42, right: 18, top: 20, bottom: 34 }, tooltip: { trigger: 'axis', ...lightTooltip },
    xAxis: { type: 'category', data: letters, ...lightAxis }, yAxis: { type: 'value', ...lightAxis },
    series: [{ type: 'bar', barWidth: '50%', data: letters.map(l => ({
      value: (D.dist && D.dist[l]) || 0,
      itemStyle: { color: classColor[l] || '#aaa79c', borderRadius: [12, 12, 0, 0] }
    })) }]
  });

  const calibChart = registerChart('chartCalib', echarts.init($('chartCalib')));
  const scatter = D.scatter || [];
  const xs = scatter.map(p => p[0]).filter(v => v > 0);
  const line = [];
  if (xs.length && D.calib) {
    const xmin = Math.min(...xs), xmax = Math.max(...xs);
    for (let i = 0; i <= 48; i++) {
      const x = xmin * Math.pow(xmax / xmin, i / 48);
      line.push([x, Math.pow(10, D.calib.intercept + D.calib.slope * Math.log10(x))]);
    }
  }
  calibChart.setOption({
    backgroundColor: 'transparent', animationDuration: 950, animationEasing: 'cubicOut',
    grid: { left: 58, right: 20, top: 16, bottom: 36 }, tooltip: { trigger: 'item', ...lightTooltip },
    xAxis: { type: 'log', name: 'counts', nameLocation: 'middle', nameGap: 22, nameTextStyle: { color: '#858781', fontSize: 10, fontWeight: 700 }, ...lightAxis },
    yAxis: { type: 'log', name: 'GOES W/m²', nameTextStyle: { color: '#858781', fontSize: 10, fontWeight: 700 }, ...lightAxis },
    series: [
      { type: 'scatter', symbolSize: 7, data: scatter.map(p => ({ value: [p[0], p[1]], itemStyle: { color: classColor[p[2]] || '#858781', opacity: .78 } })) },
      { type: 'line', showSymbol: false, data: line, lineStyle: { color: '#10100f', width: 2, type: 'dashed' } }
    ]
  });

  const forecastChart = registerChart('chartForecast', echarts.init($('chartForecast')));
  const sc = fc.skillCurve || [];
  forecastChart.setOption({
    backgroundColor: 'transparent', animationDuration: 1000, animationEasing: 'cubicOut',
    grid: { left: 38, right: 22, top: 34, bottom: 32 }, tooltip: { trigger: 'axis', ...lightTooltip },
    legend: { top: 0, right: 0, itemWidth: 16, itemHeight: 8, textStyle: { color: '#767873', fontSize: 10, fontWeight: 650 } },
    xAxis: { type: 'category', data: sc.map(s => `${s.h}m`), ...lightAxis },
    yAxis: { type: 'value', min: 0, max: 1, ...lightAxis },
    series: [
      { name: 'AUC soft+hard', type: 'line', symbol: 'circle', symbolSize: 7, data: sc.map(s => s.auc), lineStyle: { color: '#10100f', width: 2.3 }, itemStyle: { color: '#10100f' }, areaStyle: { color: 'rgba(16,16,15,.055)' } },
      { name: 'AUC soft', type: 'line', symbol: 'none', data: sc.map(s => s.aucSoft), lineStyle: { color: '#9a9c97', width: 1.6, type: 'dashed' } },
      { name: 'Precision', type: 'line', symbol: 'circle', symbolSize: 6, data: sc.map(s => s.precision), lineStyle: { color: '#a8614b', width: 1.9 }, itemStyle: { color: '#a8614b' } }
    ]
  });

  // Alert feed.
  function feedItem(fl) {
    const letter = fl.letter || 'C';
    return `<div class="feed-item b-${letter}">
      <div class="feed-badge c-${letter}">${fl.cls || '—'}</div>
      <div class="feed-meta"><b>${fl.id || 'Unknown event'}</b><small>${shortDate(fl.t)}<br>GOES ${fl.clsGoes || '—'} · ${safe(fl.durMin)}m duration</small></div>
      <div class="feed-sigma">${fl.sig != null ? Math.round(fl.sig) + 'σ' : '—'}</div>
    </div>`;
  }

  const feedEl = $('feed');
  function seedFeed(list = flares.slice(-8).reverse()) {
    feedEl.innerHTML = list.map(feedItem).join('');
  }
  seedFeed();

  function announce(fl) {
    const letter = fl.letter || 'C';
    $('activeClass').textContent = fl.cls || 'Solar flare';
    $('activeLabel').textContent = `${fl.id || 'Event'} · ${shortDate(fl.t)}`;
    $('statusText').textContent = `NOWCAST · ${fl.cls || 'Flare'} detected`;
    feedEl.insertAdjacentHTML('afterbegin', feedItem(fl));
    while (feedEl.children.length > 8) feedEl.lastChild.remove();
  }

  // --- Forecast alerts (the ensemble firing BEFORE a flare) ----------------
  function forecastAt(ms) {
    // last forecast-track probability at or before ms (step lookup)
    if (!fcurve.length || ms < fcurve[0][0]) return null;
    let lo = 0, hi = fcurve.length - 1, ans = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (fcurve[mid][0] <= ms) { ans = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return fcurve[ans][1];
  }

  function nextFlareLead(ms) {
    for (const fl of flares) {
      const d = (Date.parse(fl.t) - ms) / 60000;
      if (d >= 0 && d <= 180) return { lead: Math.round(d), cls: fl.cls, letter: fl.letter };
    }
    return null;
  }

  function announceForecast(prob, ms) {
    const nxt = nextFlareLead(ms);
    const riskPct = Math.round(prob * 100);
    const leadTxt = nxt ? `~${nxt.lead} min lead → ${nxt.cls} onset`
                        : 'elevated flare probability';
    $('statusText').textContent = `FORECAST · ${riskPct}% flare risk`;
    feedEl.insertAdjacentHTML('afterbegin', `
      <div class="feed-item b-M" style="border-left:3px solid #b28a4a">
        <div class="feed-badge" style="background:#b28a4a;color:#fff">FCST</div>
        <div class="feed-meta"><b>Forecast alert · ${riskPct}% risk</b>
          <small>${shortDate(new Date(ms).toISOString())}<br>${leadTxt}</small></div>
        <div class="feed-sigma">${riskPct}%</div>
      </div>`);
    while (feedEl.children.length > 8) feedEl.lastChild.remove();
  }

  if (latest.id) {
    $('activeClass').textContent = latest.cls;
    $('activeClass').style.color = classColor[latest.letter] || '#10100f';
    $('activeLabel').textContent = `${latest.id} · ${shortDate(latest.t)}`;
  }

  // Model leaderboard.
  const mc = D.modelComparison;
  if (mc && mc.ranking) {
    const names = { logistic: 'Logistic regression', rf: 'Random forest', lgbm: 'LightGBM', tcn_transfer: 'GOES → TCN transfer' };
    $('leaderboard').innerHTML = mc.ranking.map((r, idx) => `
      <div class="lb-row lb-win" style="animation-delay:${idx * 60}ms">
        <span>${names[r.model] || r.model}</span><b>${safe(r.auc)}</b>
      </div>`).join('');
  }

  // Multi-class probability bars (live during replay) + QPP panel.
  const mclass = D.multiclass || {};
  const mcClasses = mclass.classes || {};
  const mctrack = mclass.track || {};
  const mcTimes = (mctrack.t || []).map(t => Date.parse(t));
  const mcColors = { C: '#b28a4a', M: '#a8614b', X: '#10100f' };
  const mcOrder = ['C', 'M', 'X'].filter(c => mcClasses[c]);
  if ($('mcHorizon')) $('mcHorizon').textContent = (mclass.horizon || 30) + ' min';
  function renderMcBars(probs) {
    const el = $('mcBars'); if (!el) return;
    el.innerHTML = mcOrder.map(c => {
      const info = mcClasses[c]; const p = probs && probs[c] != null ? probs[c] : 0;
      return `<div class="mc-row">
        <div class="mc-label" style="color:${mcColors[c]}"><b>${c}+</b><small>${(info.label || '').split(' ')[0]}</small></div>
        <div class="mc-track"><div class="mc-fill" data-c="${c}" style="width:${(p * 100).toFixed(1)}%;background:${mcColors[c]}"></div></div>
        <div class="mc-val" data-c="${c}">${Math.round(p * 100)}%</div>
        <div class="mc-skill">AUC ${info.auc} · ${info.lead}m lead</div>
      </div>`;
    }).join('');
  }
  renderMcBars(null);
  function mcAt(ms) {
    if (!mcTimes.length || ms < mcTimes[0]) return null;
    let lo = 0, hi = mcTimes.length - 1, ans = 0;
    while (lo <= hi) { const md = (lo + hi) >> 1; if (mcTimes[md] <= ms) { ans = md; lo = md + 1; } else hi = md - 1; }
    const out = {}; mcOrder.forEach(c => { const a = mctrack['p_' + c]; if (a) out[c] = a[ans]; });
    return out;
  }
  function updateMcBars(ms) {
    const p = mcAt(ms); if (!p) return;
    mcOrder.forEach(c => {
      const f = document.querySelector('.mc-fill[data-c="' + c + '"]');
      const v = document.querySelector('.mc-val[data-c="' + c + '"]');
      if (f && p[c] != null) f.style.width = (p[c] * 100).toFixed(1) + '%';
      if (v && p[c] != null) v.textContent = Math.round(p[c] * 100) + '%';
    });
  }
  const qpp = D.qpp || {};
  (function renderQpp() {
    const el = $('qppBody'); if (!el) return;
    const frac = qpp.fraction != null ? (qpp.fraction * 100).toFixed(1) + '%' : '—';
    const med = qpp.medianPeriodS != null ? (qpp.medianPeriodS / 60).toFixed(1) + ' min' : '—';
    const rng = qpp.periodRangeS ? `${qpp.periodRangeS[0]}–${qpp.periodRangeS[1]} s` : '';
    el.innerHTML = `<div class="qpp-big">${frac}</div>
      <div class="qpp-sub"><b>${fmtInt.format(qpp.nDetected || 0)}</b> of ${fmtInt.format(qpp.nAnalysed || 0)} flares pulsating<br>
      median period <b>${med}</b><br><small>Lomb-Scargle · FAP&lt;1% · ≥3 cycles · ${rng}</small></div>`;
  })();

  // SHARP magnetogram supplement panel.
  const sharp = D.sharp || null;
  (function renderSharp() {
    const el = $('sharpBody'); if (!el) return;
    if (!sharp) { el.innerHTML = '<div class="qpp-sub">Run <code>main.py sharp</code> to add magnetogram context.</div>'; return; }
    const v = sharp.validation || {};
    const pct = v.fraction_above_quiet_median != null ? Math.round(v.fraction_above_quiet_median * 100) + '%' : '';
    el.innerHTML = `<div class="qpp-big">${v.elevation_ratio != null ? v.elevation_ratio + '×' : '—'}</div>
      <div class="qpp-sub">higher magnetic complexity 6 h before M+ flares<br>
      <small>SHARP validated${pct ? ' · ' + pct + ' of M+ above quiet baseline' : ''}${sharp.topFeatures && sharp.topFeatures.length ? ' · top: ' + sharp.topFeatures.slice(0, 3).join(', ') : ''}<br>
      neutral as a 30-min feature (ΔAUC ${sharp.benefitAuc}) — value is longer-horizon / per-AR</small></div>`;
  })();

  // Timeline replay.
  const t0 = light.t && light.t.length ? Date.parse(light.t[0]) : Date.now();
  const t1 = light.t && light.t.length ? Date.parse(light.t[light.t.length - 1]) : Date.now();
  const span = Math.max(1, t1 - t0);
  const duration = 75;
  let playing = false;
  let cur = t1;
  let prev = cur;
  let lastCursor = 0;
  let fcArmed = true;   // re-arms when risk drops below threshold (one alert per rise)
  const slider = $('timeline');
  const playBtn = $('playBtn');

  function setCampaignClock(ms) {
    const d = new Date(ms);
    $('clock').textContent = d.toISOString().slice(11, 16);
    $('tlDate').textContent = `${d.toISOString().slice(0, 10)} · ${d.toISOString().slice(11, 16)}`;
  }

  function cursor(ms, force) {
    if (!force && performance.now() - lastCursor < 180) return;
    lastCursor = performance.now();
    lightChart.setOption({ series: [{ markLine: { data: [{ xAxis: new Date(ms).toISOString() }] } }] });
  }

  function jump(ms) {
    cur = ms;
    prev = ms;
    setCampaignClock(ms);
    cursor(ms, true);
    updateMcBars(ms);
    slider.value = ((ms - t0) / span) * 1000;
  }

  function tick() {
    if (!playing) return;
    const dtMs = (span / duration) * (1 / 60);
    cur += dtMs;
    for (const fl of flares) {
      const ms = Date.parse(fl.t);
      if (ms > prev && ms <= cur) announce(fl);
    }
    if (fcThreshold != null) {
      const pr = forecastAt(cur);
      if (pr != null) {
        if (pr >= fcThreshold && fcArmed) { announceForecast(pr, cur); fcArmed = false; }
        else if (pr < fcThreshold) { fcArmed = true; }
      }
    }
    updateMcBars(cur);
    prev = cur;
    setCampaignClock(cur);
    cursor(cur);
    slider.value = ((cur - t0) / span) * 1000;
    if (cur >= t1) {
      playing = false;
      playBtn.querySelector('.play-symbol').textContent = '▶';
      playBtn.querySelector('.play-label').textContent = 'Replay campaign';
      $('statusText').textContent = 'Campaign replay complete';
      return;
    }
    requestAnimationFrame(tick);
  }

  setCampaignClock(t1);
  cursor(t1, true);
  slider.addEventListener('input', () => {
    playing = false;
    playBtn.querySelector('.play-symbol').textContent = '▶';
    playBtn.querySelector('.play-label').textContent = 'Replay campaign';
    jump(t0 + (Number(slider.value) / 1000) * span);
  });
  playBtn.addEventListener('click', () => {
    playing = !playing;
    if (playing) {
      if (cur >= t1) {
        cur = t0;
        prev = cur;
        fcArmed = true;
        feedEl.innerHTML = '';
      }
      playBtn.querySelector('.play-symbol').textContent = 'Ⅱ';
      playBtn.querySelector('.play-label').textContent = 'Pause replay';
      $('statusText').textContent = 'Replaying campaign';
      tick();
    } else {
      playBtn.querySelector('.play-symbol').textContent = '▶';
      playBtn.querySelector('.play-label').textContent = 'Replay campaign';
      $('statusText').textContent = 'Monitoring nominally';
    }
  });

  // Expandable chart cards.
  const backdrop = $('chartBackdrop');
  let expandedCard = null;
  function closeExpanded() {
    if (!expandedCard) return;
    expandedCard.classList.remove('is-expanded');
    const btn = expandedCard.querySelector('.expand-btn');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    backdrop.classList.remove('visible');
    document.body.classList.remove('chart-open');
    expandedCard = null;
    resizeCharts(80);
  }
  function expandCard(button) {
    const card = button.closest('.chart-card');
    if (!card) return;
    if (expandedCard === card) { closeExpanded(); return; }
    closeExpanded();
    expandedCard = card;
    card.classList.add('is-expanded');
    button.setAttribute('aria-expanded', 'true');
    backdrop.classList.add('visible');
    document.body.classList.add('chart-open');
    resizeCharts(60);
    resizeCharts(460);
  }
  document.querySelectorAll('.expand-btn').forEach(btn => {
    btn.setAttribute('aria-expanded', 'false');
    btn.addEventListener('click', () => expandCard(btn));
  });
  backdrop.addEventListener('click', closeExpanded);
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeExpanded();
  });
  window.addEventListener('resize', () => resizeCharts(40));

  const fdBtn = $('forecastDropdownBtn');
  const fdContainer = $('forecastDropdown');
  if (fdBtn && fdContainer) {
    // Start fully hidden (no space taken)
    fdContainer.style.display = 'none';
    fdContainer.style.maxHeight = '0';
    fdContainer.style.opacity = '0';

    fdBtn.addEventListener('click', () => {
      const isOpen = fdContainer.classList.contains('is-open');
      if (isOpen) {
        fdContainer.style.maxHeight = '0';
        fdContainer.style.opacity = '0';
        fdContainer.classList.remove('is-open');
        fdBtn.querySelector('span').style.transform = 'rotate(0deg)';
        // Hide after transition ends so it takes no space
        fdContainer.addEventListener('transitionend', function hide() {
          if (!fdContainer.classList.contains('is-open')) {
            fdContainer.style.display = 'none';
          }
          fdContainer.removeEventListener('transitionend', hide);
        });
      } else {
        fdContainer.style.display = 'grid';
        // Allow paint before animating
        requestAnimationFrame(() => {
          fdContainer.style.maxHeight = '1500px';
          fdContainer.style.opacity = '1';
        });
        fdContainer.classList.add('is-open');
        fdBtn.querySelector('span').style.transform = 'rotate(180deg)';
      }
    });
  }
})();
