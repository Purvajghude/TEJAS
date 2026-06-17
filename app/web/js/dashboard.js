/* ============================================================
   TEJAS — command-center logic: panels, feed, timeline replay
   ============================================================ */
(function () {
  const D = window.TEJAS;
  const CC = { A: '#ffe07a', B: '#ffe07a', C: '#ffd23f', M: '#ff7b29', X: '#ff3b30' };
  const $ = (id) => document.getElementById(id);
  const fmtT = (d) => d.toISOString().substr(11, 8);
  const fmtD = (d) => d.toISOString().substr(0, 10);

  // ---------------- header / meta ----------------
  $('dateRange').textContent = `${D.meta.dateStart} → ${D.meta.dateEnd} · ${D.meta.nDays} DAYS`;
  $('calR').textContent = D.calib.r.toFixed(3);

  // ---------------- KPIs (soft + hard + forecast story) ----------------
  const k = D.kpis;
  const fz = D.fusion || {};
  const fc = D.forecast || {};
  const auc15 = fc.skillCurve && fc.skillCurve.length ? fc.skillCurve[0].auc : null;
  const neup = fz.neupertLeadMedianS != null
    ? (fz.neupertLeadMedianS / 60).toFixed(1) + 'm' : '—';
  const kpis = [
    [k.nFlares, 'FLARES DETECTED', '#46e0ff'],
    [fz.nDualConfirmed != null ? fz.nDualConfirmed : '—', 'SOFT+HARD CONFIRMED', '#ff7b29'],
    [neup, 'NEUPERT LEAD (median)', '#ff3b30'],
    [auc15 != null ? auc15.toFixed(2) : '—', 'FORECAST AUC @15m', '#c89bff'],
    [(k.agreement * 100).toFixed(0) + '%', 'GOES AGREEMENT', '#ffb547'],
    [`${k.xRecovered[0]}/${k.xRecovered[1]}`, 'X-CLASS RECOVERED', '#39d98a'],
  ];
  $('kpiGrid').innerHTML = kpis.map(([v, l, c]) =>
    `<div class="kpi"><div class="v" style="color:${c}">${v}</div><div class="l">${l}</div></div>`
  ).join('');

  // ---------------- forecast headline stats ----------------
  const wf = fc.walkForward || {};
  const fcStats = [
    [auc15 != null ? auc15.toFixed(2) : '—', 'AUC @15min'],
    [fc.leadMedian != null ? fc.leadMedian + 'm' : '—', 'MEDIAN LEAD'],
    [fc.eventRecall != null ? (fc.eventRecall * 100).toFixed(0) + '%' : '—', 'M+ RECALL'],
    [wf.ROC_AUC_mean != null ? wf.ROC_AUC_mean.toFixed(2) : '—', 'WALK-FWD AUC'],
  ];
  $('fcStats').innerHTML = fcStats.map(([v, l]) =>
    `<div class="valcell"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');

  // ---------------- model leaderboard (rigorous comparison) ----------------
  const mc = D.modelComparison;
  if (mc && mc.ranking) {
    const names = { logistic: 'Logistic ✓', rf: 'Random Forest',
      lgbm: 'LightGBM', tcn_transfer: 'GOES→TCN (deep)' };
    $('leaderboard').innerHTML =
      `<div class="lb-h">Models compared · ROC-AUC @${mc.horizon}m</div>` +
      mc.ranking.map(r =>
        `<div class="lb-row${r.model === mc.winner ? ' lb-win' : ''}">` +
        `<span>${names[r.model] || r.model}</span><b>${r.auc}</b></div>`).join('');
  }

  // ---------------- ticker ----------------
  const strong = D.flares.filter(x => x.letter === 'X' || x.letter === 'M')
    .slice(-14).map(x => `<b>${x.cls}</b> ${x.t.substr(0, 10)} ${x.t.substr(11, 5)}UTC`);
  $('ticker').innerHTML = '◢ TEJAS LIVE FEED &nbsp; ' +
    strong.join(' &nbsp;◦&nbsp; ') + ' &nbsp;◦&nbsp; ' +
    `${k.nFlares} FLARES CATALOGUED &nbsp;◦&nbsp; ${(k.agreement * 100).toFixed(0)}% GOES AGREEMENT &nbsp;◦&nbsp; 100% X-CLASS RECOVERY`;

  // ---------------- ECharts dark base ----------------
  const AX = { axisLine: { lineStyle: { color: 'rgba(90,140,200,.4)' } },
    axisLabel: { color: '#7f93b8', fontSize: 9 },
    splitLine: { lineStyle: { color: 'rgba(90,140,200,.1)' } } };
  const transparent = 'rgba(0,0,0,0)';

  // light curve
  const lightChart = echarts.init($('chartLight'), null, { renderer: 'canvas' });
  const hasHard = D.light.hard && D.light.hard.some(v => v != null);
  lightChart.setOption({
    backgroundColor: transparent,
    grid: { left: 44, right: 44, top: 24, bottom: 22 },
    legend: { data: ['SoLEXS soft', 'HEL1OS hard', 'GOES'], top: 0, right: 6,
      textStyle: { color: '#7f93b8', fontSize: 9 }, itemWidth: 14, itemHeight: 8 },
    tooltip: { trigger: 'axis', backgroundColor: '#0a1020', borderColor: '#46e0ff',
      textStyle: { color: '#dbe7ff', fontSize: 11 } },
    xAxis: { type: 'time', ...AX },
    yAxis: [
      { type: 'log', name: 'counts/s', nameTextStyle: { color: '#46e0ff', fontSize: 9 }, ...AX },
      { type: 'log', name: 'GOES W/m²', position: 'right', nameTextStyle: { color: '#e879f9', fontSize: 9 }, ...AX, splitLine: { show: false } },
    ],
    series: [
      { name: 'SoLEXS soft', type: 'line', showSymbol: false, sampling: 'lttb',
        lineStyle: { color: '#46e0ff', width: 1.2 },
        areaStyle: { color: 'rgba(70,224,255,.12)' },
        data: D.light.t.map((t, i) => [t, D.light.counts[i]]),
        markLine: { silent: true, symbol: 'none',
          lineStyle: { color: '#fff', width: 1.5, type: 'solid' }, data: [] } },
      { name: 'HEL1OS hard', type: 'line', showSymbol: false, sampling: 'lttb',
        lineStyle: { color: '#ff7b29', width: 1 },
        areaStyle: { color: 'rgba(255,123,41,.06)' },
        data: hasHard ? D.light.t.map((t, i) => [t, D.light.hard[i]]) : [] },
      { name: 'GOES', type: 'line', yAxisIndex: 1, showSymbol: false, sampling: 'lttb',
        lineStyle: { color: '#e879f9', width: 1.1 },
        data: D.light.t.map((t, i) => [t, D.light.xrsb[i]]) },
    ],
  });

  // class distribution
  const distChart = echarts.init($('chartDist'));
  const letters = ['A', 'B', 'C', 'M', 'X'];
  distChart.setOption({
    backgroundColor: transparent,
    grid: { left: 36, right: 14, top: 14, bottom: 22 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: letters, ...AX },
    yAxis: { type: 'value', ...AX },
    series: [{ type: 'bar', data: letters.map(l => ({ value: D.dist[l] || 0,
      itemStyle: { color: CC[l], borderRadius: [3, 3, 0, 0] } })), barWidth: '52%' }],
  });

  // calibration scatter
  const calibChart = echarts.init($('chartCalib'));
  const xs = D.scatter.map(p => p[0]);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const line = [];
  for (let i = 0; i <= 40; i++) {
    const x = xmin * Math.pow(xmax / xmin, i / 40);
    line.push([x, Math.pow(10, D.calib.intercept + D.calib.slope * Math.log10(x))]);
  }
  calibChart.setOption({
    backgroundColor: transparent,
    grid: { left: 50, right: 14, top: 14, bottom: 26 },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'log', name: 'counts', nameLocation: 'middle', nameGap: 16, nameTextStyle: { color: '#7f93b8', fontSize: 9 }, ...AX },
    yAxis: { type: 'log', name: 'GOES W/m²', nameTextStyle: { color: '#7f93b8', fontSize: 9 }, ...AX },
    series: [
      { type: 'scatter', symbolSize: 5, data: D.scatter.map(p => ({ value: [p[0], p[1]], itemStyle: { color: CC[p[2]] || '#888', opacity: .8 } })) },
      { type: 'line', showSymbol: false, data: line, lineStyle: { color: '#46e0ff', width: 2, type: 'dashed' } },
    ],
  });

  // forecast skill vs lead-time (AUC soft vs soft+hard, + precision)
  const forecastChart = echarts.init($('chartForecast'));
  const sc = (fc.skillCurve) || [];
  forecastChart.setOption({
    backgroundColor: transparent,
    grid: { left: 34, right: 30, top: 26, bottom: 22 },
    legend: { data: ['AUC soft+hard', 'AUC soft', 'precision'], top: 0,
      textStyle: { color: '#7f93b8', fontSize: 8 }, itemWidth: 12, itemHeight: 7 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: sc.map(s => s.h + 'm'),
      name: 'lead', nameTextStyle: { color: '#7f93b8', fontSize: 8 }, ...AX },
    yAxis: { type: 'value', min: 0, max: 1, ...AX },
    series: [
      { name: 'AUC soft+hard', type: 'line', symbol: 'circle', symbolSize: 6,
        data: sc.map(s => s.auc), lineStyle: { color: '#46e0ff', width: 2 },
        itemStyle: { color: '#46e0ff' } },
      { name: 'AUC soft', type: 'line', symbol: 'none',
        data: sc.map(s => s.aucSoft),
        lineStyle: { color: '#7f93b8', width: 1, type: 'dashed' } },
      { name: 'precision', type: 'line', symbol: 'circle', symbolSize: 5,
        data: sc.map(s => s.precision), lineStyle: { color: '#ffb547', width: 1.5 },
        itemStyle: { color: '#ffb547' } },
    ],
  });

  window.addEventListener('resize', () => {
    lightChart.resize(); distChart.resize(); calibChart.resize(); forecastChart.resize();
  });

  // ---------------- alert feed ----------------
  function feedItem(fl) {
    return `<div class="feed-item b-${fl.letter}">
      <div class="feed-badge c-${fl.letter}">${fl.cls}</div>
      <div class="feed-meta"><b>${fl.id}</b> · ${fl.t.substr(11, 5)} UTC<br>
      GOES ${fl.clsGoes || '—'} · ${fl.sig.toFixed(0)}σ · ${fl.durMin}m</div></div>`;
  }
  const feedEl = $('feed');
  function seedFeed() {
    feedEl.innerHTML = D.flares.slice(-7).reverse().map(feedItem).join('');
  }
  seedFeed();

  // ---------------- big readout + status ----------------
  let statusTimer = null;
  function announce(fl) {
    $('bigClass').textContent = fl.cls;
    $('bigClass').style.color = CC[fl.letter];
    $('bigLabel').textContent = `${fl.letter}-CLASS FLARE DETECTED · ${fl.id}`;
    $('statusDot').style.background = CC[fl.letter];
    $('statusDot').style.boxShadow = `0 0 12px ${CC[fl.letter]}`;
    $('statusText').textContent = `🚨 NOWCAST · ${fl.cls} FLARE IN PROGRESS`;
    feedEl.insertAdjacentHTML('afterbegin', feedItem(fl));
    while (feedEl.children.length > 8) feedEl.lastChild.remove();
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => {
      $('bigClass').textContent = '—'; $('bigClass').style.color = '#5b6b8c';
      $('bigLabel').textContent = 'MONITORING';
      $('statusDot').style.background = '#39d98a';
      $('statusDot').style.boxShadow = '0 0 12px #39d98a';
      $('statusText').textContent = 'SYSTEM NOMINAL · MONITORING SOFT X-RAY';
    }, 3200);
  }

  // ---------------- timeline replay ----------------
  const flares = D.flares.map(fl => ({ ...fl, ms: Date.parse(fl.t) }))
    .sort((a, b) => a.ms - b.ms);
  const t0 = Date.parse(D.light.t[0]);
  const t1 = Date.parse(D.light.t[D.light.t.length - 1]);
  const SPAN = t1 - t0;
  const DURATION = 75; // seconds to replay whole campaign

  let playing = false, cur = t1, lastCursor = 0;
  const slider = $('timeline');

  function setClock(ms) {
    const d = new Date(ms);
    $('clock').textContent = fmtT(d) + ' UTC';
    $('tlDate').textContent = fmtD(d) + ' ' + fmtT(d).substr(0, 5);
  }
  function cursor(ms, force) {
    if (!force && performance.now() - lastCursor < 200) return;
    lastCursor = performance.now();
    lightChart.setOption({ series: [{ markLine: { data: [{ xAxis: new Date(ms).toISOString() }] } }] });
  }
  setClock(t1);

  function jump(ms) {
    cur = ms; setClock(ms); cursor(ms, true); slider.value = ((ms - t0) / SPAN) * 1000;
  }
  slider.addEventListener('input', () => {
    playing = false; $('playBtn').textContent = '▶ REPLAY CAMPAIGN';
    jump(t0 + (slider.value / 1000) * SPAN);
  });

  $('playBtn').addEventListener('click', () => {
    playing = !playing;
    $('playBtn').textContent = playing ? '⏸ PAUSE' : '▶ REPLAY CAMPAIGN';
    if (playing) {
      if (cur >= t1) { cur = t0; feedEl.innerHTML = ''; }
      window.TejasSun.ambientEnabled = false;
      prev = cur; tick();
    } else {
      window.TejasSun.ambientEnabled = true;
    }
  });

  let prev = cur;
  function tick() {
    if (!playing) return;
    const dtMs = (SPAN / DURATION) * (1 / 60);
    cur += dtMs;
    // fire flares crossed this step
    for (const fl of flares) {
      if (fl.ms > prev && fl.ms <= cur) {
        window.TejasSun.fireFlare(fl.lat, fl.lon, fl.letter);
        announce(fl);
      }
    }
    prev = cur;
    setClock(cur); cursor(cur);
    slider.value = ((cur - t0) / SPAN) * 1000;
    if (cur >= t1) {
      playing = false; $('playBtn').textContent = '▶ REPLAY CAMPAIGN';
      window.TejasSun.ambientEnabled = true;
      $('bigLabel').textContent = 'CAMPAIGN REPLAY COMPLETE';
      return;
    }
    requestAnimationFrame(tick);
  }
})();
