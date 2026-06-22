/* TEJAS - modern glass dashboard */
(function () {
  const D = window.TEJAS || {};
  const $ = (id) => document.getElementById(id);
  const fmt = new Intl.NumberFormat('en', { maximumFractionDigits: 1 });
  const fmtInt = new Intl.NumberFormat('en', { maximumFractionDigits: 0 });
  const classColor = { A: '#aaa79c', B: '#aaa79c', C: '#b28a4a', M: '#a8614b', X: '#10100f' };

  function getFlareDescription(cls) {
    if (!cls || cls === '—') return 'No Flare';
    const letter = cls.charAt(0).toUpperCase();
    switch (letter) {
      case 'A': return 'Very Weak Flare';
      case 'B': return 'Weak Flare';
      case 'C': return 'Moderate Flare';
      case 'M': return 'Strong Flare';
      case 'X': return 'Extreme Flare';
      default: return 'Solar Flare';
    }
  }

  function goesClassToFlux(cls) {
    if (!cls) return 1e-6;
    const letter = cls.charAt(0).toUpperCase();
    const num = parseFloat(cls.slice(1)) || 1.0;
    let base = 1e-8;
    if (letter === 'A') base = 1e-8;
    else if (letter === 'B') base = 1e-7;
    else if (letter === 'C') base = 1e-6;
    else if (letter === 'M') base = 1e-5;
    else if (letter === 'X') base = 1e-4;
    return base * num;
  }

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

  function updateSolarStatus(prob) {
    const pr = prob != null ? prob : 0.12;
    const prPct = Math.round(pr * 100);
    const forecastVal = $('forecastProbVal');
    if (forecastVal) forecastVal.textContent = `${prPct}%`;

    const badge = $('riskLevelBadge');
    if (badge) {
      badge.className = 'status-badge';
      if (pr < 0.20) {
        badge.textContent = 'LOW';
        badge.classList.add('badge-green');
      } else if (pr < 0.50) {
        badge.textContent = 'MODERATE';
        badge.classList.add('badge-yellow');
      } else if (pr < 0.75) {
        badge.textContent = 'HIGH';
        badge.classList.add('badge-orange');
      } else {
        badge.textContent = 'CRITICAL';
        badge.classList.add('badge-red');
      }
    }

    // System Status
    const sysBadge = $('systemStatusBadge');
    if (sysBadge) {
      sysBadge.className = 'status-badge';
      if (pr >= 0.75) {
        sysBadge.textContent = 'SYSTEM: ALERT';
        sysBadge.classList.add('badge-red');
      } else {
        sysBadge.textContent = 'SYSTEM: NOMINAL';
        sysBadge.classList.add('badge-green');
      }
    }
  }

  // Meta and headline copy.
  $('dateRange').textContent = `${safe(meta.dateStart)} → ${safe(meta.dateEnd)} · ${safe(meta.nDays, 0)} days`;
  $('coverageText').textContent = `${safe(meta.nDays, 0)} observing days · ${fmtInt.format(k.nFlares || 0)} flares catalogued`;
  $('coverageMini').textContent = `${safe(meta.dateStart)} — ${safe(meta.dateEnd)}`;
  $('footerMeta').textContent = `SoLEXS · HEL1OS · GOES · ${safe(meta.nDays, 0)} days`;
  $('calR').textContent = D.calib && D.calib.r != null ? D.calib.r.toFixed(3) : '—';
  $('latestClass').textContent = latest.cls || '—';
  if ($('latestFlareDesc')) $('latestFlareDesc').textContent = getFlareDescription(latest.cls);
  $('outlookAuc').textContent = auc15 != null ? `${auc15.toFixed(2)} AUC` : '— AUC';
  $('outlookLead').textContent = medianLead != null ? `${medianLead} min` : '— min';
  $('statusText').textContent = `${fmtInt.format(k.nFlares || 0)} validated detections`;
  $('feedCount').textContent = flares.length;

  const initialProb = fcurve.length ? fcurve[fcurve.length - 1][1] : 0.12;
  updateSolarStatus(initialProb);

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
    [auc15 != null ? auc15.toFixed(2) : '—', 'AUC @15m', 'Detection accuracy at 15min lead'],
    [medianLead != null ? `${medianLead}m` : '—', 'Median lead', 'Average warning time before flare'],
    [fc.eventRecall != null ? pct(fc.eventRecall) : '—', 'M+ event recall', '% of major flares caught'],
    [wf.ROC_AUC_mean != null ? wf.ROC_AUC_mean.toFixed(2) : '—', 'Walk-forward AUC', 'Real-world simulation accuracy'],
  ];
  $('fcStats').innerHTML = fcStats.map(([v, l, d]) => `<div class="valcell"><div class="v">${v}</div><div class="l">${l}</div><div class="valcell-desc">${d}</div></div>`).join('');

  // Navigation active state / Scroll tracking.
  const navItems = document.querySelectorAll('.nav-item');

  function navigateToSection(targetId) {
    const targetElement = document.querySelector(targetId);
    if (!targetElement) return;

    // Auto-open forecast dropdown if we switched to forecasting
    if (targetId === '#forecasting') {
      const fdContainer = $('forecastDropdown');
      const fdBtn = $('forecastDropdownBtn');
      if (fdContainer && fdBtn && !fdContainer.classList.contains('is-open')) {
        fdBtn.click();
      }
    }

    targetElement.scrollIntoView({ behavior: 'smooth' });

    // Update hash without jumping
    if (history.pushState) {
      history.pushState(null, null, targetId);
    } else {
      window.location.hash = targetId;
    }

    resizeCharts(100);
    resizeCharts(300);
  }

  navItems.forEach(item => item.addEventListener('click', (e) => {
    e.preventDefault();
    const href = item.getAttribute('href');
    navigateToSection(href);
  }));

  // Intercept all internal section links (like explore observations in the hero card)
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    if (link.classList.contains('nav-item')) return;
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (['#overview', '#observations', '#forecasting', '#models'].includes(href)) {
        e.preventDefault();
        navigateToSection(href);
      }
    });
  });

  // Highlight navigation item on scroll using IntersectionObserver
  const observerOptions = {
    root: null, // viewport
    rootMargin: '-20% 0px -60% 0px', // triggers when section occupies central viewport
    threshold: 0
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.getAttribute('id');
        const activeNav = document.querySelector(`.nav-item[href="#${id}"]`);
        if (activeNav) {
          navItems.forEach(n => n.classList.remove('active'));
          activeNav.classList.add('active');
        }
      }
    });
  }, observerOptions);

  // Observe navigation target sections specifically
  ['overview', 'observations', 'forecasting', 'models'].forEach(id => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });

  // Scroll reveal observer for premium fadeUp animation as user scrolls
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('active-reveal');
        revealObserver.unobserve(entry.target);
      }
    });
  }, {
    root: null,
    rootMargin: '0px 0px -8% 0px',
    threshold: 0.05
  });

  document.querySelectorAll('.reveal').forEach(el => {
    revealObserver.observe(el);
  });

  // Handle initial page load hash
  const initialHash = window.location.hash;
  if (initialHash && ['#overview', '#observations', '#forecasting', '#models'].includes(initialHash)) {
    window.setTimeout(() => {
      navigateToSection(initialHash);
    }, 400); // Small delay to let browser finish loading layout/charts
  }

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

  function getFlareMarkers(startMs = null, endMs = null) {
    return flares
      .filter(fl => fl.letter === 'M' || fl.letter === 'X')
      .filter(fl => {
        if (startMs && Date.parse(fl.t) < startMs) return false;
        if (endMs && Date.parse(fl.t) > endMs) return false;
        return true;
      })
      .map(fl => ({
        name: fl.cls,
        coord: [fl.t, goesClassToFlux(fl.clsGoes || fl.cls)],
        itemStyle: { color: classColor[fl.letter] || '#ff9500', shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.5)' }
      }));
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
      {
        name: 'SoLEXS soft', type: 'line', showSymbol: false, sampling: 'lttb', smooth: .18,
        data: light.t.map((t, i) => [t, positive(light.counts[i])]),
        lineStyle: { color: '#f7f4ea', width: 1.65 }, areaStyle: { color: 'rgba(247,244,234,.10)' },
        markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: 'rgba(247,244,234,.72)', width: 1.4 }, data: [] }
      },
      {
        name: 'HEL1OS hard', type: 'line', showSymbol: false, sampling: 'lttb', smooth: .12,
        data: hasHard ? light.t.map((t, i) => [t, positive(light.hard[i])]) : [],
        lineStyle: { color: '#c98265', width: 1.35 }, areaStyle: { color: 'rgba(201,130,101,.09)' }
      },
      {
        name: 'GOES', type: 'line', yAxisIndex: 1, showSymbol: false, sampling: 'lttb', smooth: .2,
        data: light.t.map((t, i) => [t, positive(light.xrsb[i])]),
        lineStyle: { color: '#a8b49c', width: 1.35 }
      },
      {
        name: 'Forecast risk', type: 'line', yAxisIndex: 2, showSymbol: false, sampling: 'lttb', smooth: .15,
        data: fcurve.map(([ms, p]) => [new Date(ms).toISOString(), p]),
        lineStyle: { color: '#b28a4a', width: 1.2, opacity: .9 }, areaStyle: { color: 'rgba(178,138,74,.10)' },
        markLine: fcThreshold != null ? {
          silent: true, symbol: 'none',
          lineStyle: { color: 'rgba(178,138,74,.55)', width: 1, type: 'dashed' },
          label: { formatter: 'alert', color: 'rgba(178,138,74,.8)', fontSize: 9 },
          data: [{ yAxis: fcThreshold }]
        } : { data: [] }
      }
    ]
  });

  const pieChart = registerChart('chartPie', echarts.init($('chartPie')));
  pieChart.setOption({
    backgroundColor: 'transparent',
    color: ['#f7f4ea', '#c98265', '#a8b49c', '#b28a4a'],
    tooltip: { trigger: 'item', ...darkTooltip, formatter: '{b}: {c}' },
    legend: { top: 'bottom', textStyle: { color: 'rgba(247,244,234,.62)' } },
    series: [
      {
        name: 'Observations',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#151514', borderWidth: 2 },
        label: { show: false, position: 'center' },
        emphasis: { label: { show: true, fontSize: 18, fontWeight: 'bold' } },
        labelLine: { show: false },
        minAngle: 15,
        data: [
          { value: 0, name: 'SoLEXS soft', itemStyle: { color: '#f7f4ea' } },
          { value: 0, name: 'HEL1OS hard', itemStyle: { color: '#c98265' } },
          { value: 0, name: 'GOES', itemStyle: { color: '#a8b49c' } },
          { value: 0, name: 'Forecast risk', itemStyle: { color: '#b28a4a' } }
        ]
      }
    ]
  });

  const viewGraphBtn = $('viewGraphBtn');
  const viewPieBtn = $('viewPieBtn');
  const chartLightEl = $('chartLight');
  const chartPieEl = $('chartPie');

  if (viewGraphBtn && viewPieBtn) {
    viewGraphBtn.addEventListener('click', () => {
      viewGraphBtn.style.border = '1px solid rgba(255,255,255,0.2)';
      viewGraphBtn.style.background = 'rgba(255,255,255,0.1)';
      viewGraphBtn.style.color = '#fff';

      viewPieBtn.style.border = '1px solid transparent';
      viewPieBtn.style.background = 'transparent';
      viewPieBtn.style.color = 'rgba(255,255,255,0.6)';

      chartLightEl.style.display = 'block';
      chartPieEl.style.display = 'block'; // echarts requires block to resize properly
      chartPieEl.style.position = 'absolute';
      chartPieEl.style.visibility = 'hidden';

      chartPieEl.style.display = 'none';
      chartPieEl.style.position = 'static';
      chartPieEl.style.visibility = 'visible';
      resizeCharts(10);
    });

    viewPieBtn.addEventListener('click', () => {
      viewPieBtn.style.border = '1px solid rgba(255,255,255,0.2)';
      viewPieBtn.style.background = 'rgba(255,255,255,0.1)';
      viewPieBtn.style.color = '#fff';

      viewGraphBtn.style.border = '1px solid transparent';
      viewGraphBtn.style.background = 'transparent';
      viewGraphBtn.style.color = 'rgba(255,255,255,0.6)';

      chartLightEl.style.display = 'none';
      chartPieEl.style.display = 'block';
      resizeCharts(10);
    });
  }

  function updatePieData(ms) {
    let idx = 0;
    if (originalLight.t && originalLight.t.length) {
      let lo = 0, hi = originalLight.t.length - 1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (Date.parse(originalLight.t[mid]) <= ms) { idx = mid; lo = mid + 1; }
        else { hi = mid - 1; }
      }
    }
    const valSolexs = originalLight.counts[idx] || 0;
    const valHel1os = (hasHard && originalLight.hard[idx]) ? originalLight.hard[idx] : 0;
    const valGoes = originalLight.xrsb[idx] || 0;
    const valForecast = typeof forecastAt === 'function' ? forecastAt(ms) : 0;

    pieChart.setOption({
      series: [{
        data: [
          { value: positive(valSolexs) || 0, name: 'SoLEXS soft', itemStyle: { color: '#f7f4ea' } },
          { value: positive(valHel1os) || 0, name: 'HEL1OS hard', itemStyle: { color: '#c98265' } },
          { value: positive(valGoes) || 0, name: 'GOES', itemStyle: { color: '#a8b49c' } },
          { value: positive(valForecast) || 0, name: 'Forecast risk', itemStyle: { color: '#b28a4a' } }
        ]
      }]
    });
  }

  const letters = ['A', 'B', 'C', 'M', 'X'];
  const distChart = registerChart('chartDist', echarts.init($('chartDist')));
  const distCardEl = distChart.getDom().closest('.chart-card');

  function renderDistChart(counts) {
    const total = letters.reduce((s, l) => s + (counts[l] || 0), 0);
    distChart.setOption({
      backgroundColor: 'transparent', animationDuration: 900, animationEasing: 'cubicOut',
      grid: { left: 48, right: 24, top: 40, bottom: 38 },
      tooltip: {
        trigger: 'axis', ...lightTooltip,
        formatter: function (params) {
          const p = params[0];
          const val = p.value;
          const pctVal = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
          return `Class ${p.name} \u00b7 ${fmtInt.format(val)} flares (${pctVal}%)`;
        }
      },
      xAxis: { type: 'category', data: letters, ...lightAxis },
      yAxis: { type: 'value', ...lightAxis },
      series: [{
        type: 'bar', barWidth: '50%', barMinHeight: 4, label: {
          show: true, position: 'top', fontSize: 10, fontWeight: 700, color: '#555',
          formatter: function (p) { return fmtInt.format(p.value); }
        }, data: letters.map(l => ({
          value: counts[l] || 0,
          itemStyle: { color: classColor[l] || '#aaa79c', borderRadius: [12, 12, 0, 0] }
        }))
      }]
    });
  }

  // Initial render with full dataset
  const initialDistCounts = {};
  letters.forEach(l => { initialDistCounts[l] = (D.dist && D.dist[l]) || 0; });
  renderDistChart(initialDistCounts);

  function updateDistFromFlares(startMs, endMs) {
    const counts = { A: 0, B: 0, C: 0, M: 0, X: 0 };
    flares.forEach(fl => {
      const ms = Date.parse(fl.t);
      if (ms >= startMs && ms <= endMs) {
        const letter = fl.letter || (fl.cls ? fl.cls.charAt(0).toUpperCase() : null);
        if (letter && counts[letter] !== undefined) counts[letter]++;
      }
    });
    // Loading flicker
    if (distCardEl) {
      distCardEl.classList.add('card-loading');
      setTimeout(() => distCardEl.classList.remove('card-loading'), 600);
    }
    renderDistChart(counts);
  }

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
    grid: { left: 74, right: 28, top: 38, bottom: 52 }, tooltip: { trigger: 'item', ...lightTooltip },
    legend: {
      top: 4, right: 10, itemWidth: 10, itemHeight: 10,
      textStyle: { color: '#858781', fontSize: 9, fontWeight: 600 },
      data: ['A/B class', 'C class', 'M class', 'X class']
    },
    xAxis: { type: 'log', name: 'SoLEXS counts (raw detector units, log scale)', nameLocation: 'middle', nameGap: 32, nameTextStyle: { color: '#858781', fontSize: 9, fontWeight: 700 }, ...lightAxis },
    yAxis: { type: 'log', name: 'GOES X-ray flux W/m\u00b2 (log scale)', nameLocation: 'middle', nameGap: 52, nameTextStyle: { color: '#858781', fontSize: 9, fontWeight: 700 }, ...lightAxis },
    series: [
      { name: 'A/B class', type: 'scatter', symbolSize: 7, data: scatter.filter(p => p[2] === 'A' || p[2] === 'B').map(p => ({ value: [p[0], p[1]], itemStyle: { color: classColor[p[2]] || '#aaa79c', opacity: .78 } })) },
      { name: 'C class', type: 'scatter', symbolSize: 7, data: scatter.filter(p => p[2] === 'C').map(p => ({ value: [p[0], p[1]], itemStyle: { color: classColor['C'], opacity: .78 } })) },
      { name: 'M class', type: 'scatter', symbolSize: 7, data: scatter.filter(p => p[2] === 'M').map(p => ({ value: [p[0], p[1]], itemStyle: { color: classColor['M'], opacity: .78 } })) },
      { name: 'X class', type: 'scatter', symbolSize: 7, data: scatter.filter(p => p[2] === 'X').map(p => ({ value: [p[0], p[1]], itemStyle: { color: classColor['X'], opacity: .78 } })) },
      {
        name: 'Fit line', type: 'line', showSymbol: false, data: line, lineStyle: { color: '#10100f', width: 2, type: 'dashed' },
        markPoint: {
          symbol: 'rect', symbolSize: 0,
          label: { show: true, formatter: 'Perfect agreement', fontSize: 9, fontWeight: 600, color: 'rgba(16,16,15,.45)', offset: [0, 8] },
          data: line.length ? [{ coord: line[line.length - 1] }] : []
        }
      }
    ]
  });

  const forecastChart = registerChart('chartForecast', echarts.init($('chartForecast')));
  const sc = fc.skillCurve || [];
  forecastChart.setOption({
    backgroundColor: 'transparent', animationDuration: 1000, animationEasing: 'cubicOut',
    grid: { left: 48, right: 28, top: 40, bottom: 38 },
    tooltip: {
      trigger: 'axis', ...lightTooltip,
      formatter: function (params) {
        let tip = `<b>${params[0].name}</b><br/>`;
        params.forEach(p => {
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px;"></span>`;
          tip += `${dot}${p.seriesName}: <b>${p.value != null ? (typeof p.value === 'number' ? p.value.toFixed(3) : p.value) : '—'}</b><br/>`;
        });
        return tip;
      }
    },
    legend: { top: 0, right: 0, itemWidth: 16, itemHeight: 8, textStyle: { color: '#767873', fontSize: 10, fontWeight: 650 } },
    xAxis: { type: 'category', data: sc.map(s => `${s.h}m`), ...lightAxis },
    yAxis: { type: 'value', min: 0, max: 1, ...lightAxis },
    series: [
      { name: 'AUC soft+hard', type: 'line', symbol: 'circle', symbolSize: 7, data: sc.map(s => s.auc), lineStyle: { color: '#10100f', width: 2.3 }, itemStyle: { color: '#10100f' }, areaStyle: { color: 'rgba(16,16,15,.055)' } },
      { name: 'AUC soft', type: 'line', symbol: 'circle', symbolSize: 5, data: sc.map(s => s.aucSoft), lineStyle: { color: '#4a90d9', width: 1.8, type: 'dashed' }, itemStyle: { color: '#4a90d9' } },
      { name: 'Precision', type: 'line', symbol: 'circle', symbolSize: 6, data: sc.map(s => s.precision), lineStyle: { color: '#a8614b', width: 1.9 }, itemStyle: { color: '#a8614b' } }
    ]
  });

  // Alert feed.
  function feedItem(fl) {
    const letter = fl.letter || 'C';
    const desc = getFlareDescription(fl.cls);
    const duration = fl.durMin != null ? `${fl.durMin.toFixed(1)} minutes` : '—';
    const dateFormatted = shortDate(fl.t);

    // Calculate earth impact
    let impact = 'No Earth impact';
    if (letter === 'C') impact = 'Minimal Earth impact';
    else if (letter === 'M') impact = 'Moderate Earth impact';
    else if (letter === 'X') impact = 'Severe Earth impact';

    // Calculate confidence
    const sig = fl.sig != null ? fl.sig : 3;
    let confidence = '95.0%';
    let strength = 'Moderate';
    if (sig >= 15) { confidence = '99.99%'; strength = 'Extreme'; }
    else if (sig >= 8) { confidence = '99.9%'; strength = 'Very Strong'; }
    else if (sig >= 4) { confidence = '99.0%'; strength = 'Strong'; }
    else { confidence = '97.0%'; strength = 'Moderate'; }

    return `
      <div class="feed-card b-${letter}">
        <div class="feed-card-header">
          <div class="feed-badge c-${letter}">${fl.cls || '—'}</div>
          <h4>${desc}</h4>
        </div>
        <div class="feed-card-grid">
          <div class="feed-grid-item">
            <span class="lbl">Detected</span>
            <span class="val">${dateFormatted}</span>
          </div>
          <div class="feed-grid-item">
            <span class="lbl">Duration</span>
            <span class="val">${duration}</span>
          </div>
          <div class="feed-grid-item">
            <span class="lbl">Earth Impact</span>
            <span class="val impact-${letter}">${impact}</span>
          </div>
          <div class="feed-grid-item">
            <span class="lbl">Confidence</span>
            <span class="val">${confidence} <small class="sig-note">(${strength})</small></span>
          </div>
          <div class="feed-grid-item full-width">
            <span class="lbl">Instruments</span>
            <span class="val text-highlight">Aditya-L1 (SoLEXS + HEL1OS)</span>
          </div>
        </div>
      </div>
    `;
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

    // Update Solar Status Card dynamically
    $('latestClass').textContent = fl.cls || '—';
    if ($('latestFlareDesc')) $('latestFlareDesc').textContent = getFlareDescription(fl.cls);

    feedEl.insertAdjacentHTML('afterbegin', feedItem(fl));
    while (feedEl.children.length > 8) feedEl.lastChild.remove();
  }

  // --- Forecast alerts (the ensemble firing BEFORE a flare) ----------------
  function forecastAt(ms) {
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

    let confidence = '95.0%';
    let strength = 'Moderate';
    if (riskPct >= 75) { confidence = '99.9%'; strength = 'Extreme'; }
    else if (riskPct >= 50) { confidence = '99.0%'; strength = 'Strong'; }

    feedEl.insertAdjacentHTML('afterbegin', `
      <div class="feed-card b-M" style="border-left: 3px solid #ff9500">
        <div class="feed-card-header">
          <div class="feed-badge c-M">FCST</div>
          <h4>Forecast Warning: ${riskPct}% Flare Risk</h4>
        </div>
        <div class="feed-card-grid">
          <div class="feed-grid-item">
            <span class="lbl">Detected</span>
            <span class="val">${shortDate(new Date(ms).toISOString())}</span>
          </div>
          <div class="feed-grid-item">
            <span class="lbl">Implication</span>
            <span class="val text-highlight">${leadTxt}</span>
          </div>
          <div class="feed-grid-item">
            <span class="lbl">Earth Impact</span>
            <span class="val impact-M">Possible Moderate Impact</span>
          </div>
          <div class="feed-grid-item">
            <span class="lbl">Confidence</span>
            <span class="val">${confidence} <small class="sig-note">(${strength})</small></span>
          </div>
          <div class="feed-grid-item full-width">
            <span class="lbl">Instruments</span>
            <span class="val text-highlight">Aditya-L1 (Predictive Ensemble)</span>
          </div>
        </div>
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

  let t0_active = t0;
  let t1_active = t1;
  let span_active = span;

  const duration = 75;
  let playing = false;
  let cur = t1;
  let prev = cur;
  let lastCursor = 0;
  let fcArmed = true;   // re-arms when risk drops below threshold (one alert per rise)
  const slider = $('timeline');
  const playBtn = $('playBtn');

  // Keep a copy of original raw data for filtering and resetting
  const originalLight = {
    t: [...light.t],
    counts: [...light.counts],
    hard: [...light.hard],
    xrsb: [...light.xrsb]
  };
  const originalFcurve = [...fcurve];

  // Helper to format Date to datetime-local local string: YYYY-MM-DDTHH:mm:ss
  function toLocalISOString(d) {
    const pad = num => String(num).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  // Setup Date inputs and listeners
  const filterStartInput = $('filterStart');
  const filterEndInput = $('filterEnd');
  const applyFilterBtn = $('applyFilterBtn');
  const resetFilterBtn = $('resetFilterBtn');

  let fpStart, fpEnd;
  if (filterStartInput && filterEndInput) {
    const initStart = new Date(t0);
    const initEnd = new Date(t1);

    const fpConfig = {
      enableTime: true,
      enableSeconds: true,
      dateFormat: "d M Y, H:i:S",
      minDate: initStart,
      maxDate: initEnd,
      time_24hr: true,
      onReady: function (selectedDates, dateStr, instance) {

        // Inject custom month/year label
        const monthContainer = instance.monthNav;
        const currentMonthContainer = monthContainer.querySelector('.flatpickr-current-month');
        if (currentMonthContainer) currentMonthContainer.style.display = 'none';

        const customLabel = document.createElement('div');
        customLabel.className = 'tejas-month-year';
        monthContainer.insertBefore(customLabel, currentMonthContainer ? currentMonthContainer.nextSibling : null);

        const updateCustomLabel = () => {
          const monthName = instance.l10n.months.longhand[instance.currentMonth];
          customLabel.textContent = `${monthName} ${instance.currentYear}`;
        };
        updateCustomLabel();
        instance.updateCustomLabel = updateCustomLabel;

        const inputs = [
          { el: instance.hourElement, max: 23 },
          { el: instance.minuteElement, max: 59 },
          { el: instance.secondElement, max: 59 }
        ];

        inputs.forEach(({ el, max }) => {
          if (!el) return;
          const wrapper = el.parentNode;
          const prev = document.createElement('div');
          prev.className = 'slot-prev';
          const next = document.createElement('div');
          next.className = 'slot-next';
          wrapper.appendChild(prev);
          wrapper.appendChild(next);

          el.dataset.max = max; // store max for easy access

          const updateSlots = () => {
            let val = parseInt(el.value, 10) || 0;
            let p = val - 1;
            let n = val + 1;
            if (p < 0) p = max;
            if (n > max) n = 0;
            prev.textContent = p.toString().padStart(2, '0');
            next.textContent = n.toString().padStart(2, '0');
          };

          el.addEventListener('input', updateSlots);

          // Override wheel event for infinite looping
          wrapper.addEventListener('wheel', (e) => {
            e.preventDefault();
            e.stopPropagation();
            let val = parseInt(el.value, 10) || 0;
            if (e.deltaY > 0) val--; else val++;
            if (val < 0) val = max;
            if (val > max) val = 0;
            el.value = val.toString().padStart(2, '0');
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true })); // Commit change to flatpickr
            updateSlots();
          }, { passive: false });

          updateSlots();
        });
      },

      onMonthChange: function (selectedDates, dateStr, instance) {
        if (instance.updateCustomLabel) instance.updateCustomLabel();
      },
      onYearChange: function (selectedDates, dateStr, instance) {
        if (instance.updateCustomLabel) instance.updateCustomLabel();
      },
      onValueUpdate: function (selectedDates, dateStr, instance) {
        // Trigger slot updates when time changes via flatpickr API/keyboard
        [instance.hourElement, instance.minuteElement, instance.secondElement].forEach(el => {
          if (el) el.dispatchEvent(new Event('input'));
        });
      }
    };

    fpStart = flatpickr(filterStartInput, { ...fpConfig, defaultDate: initStart });
    fpEnd = flatpickr(filterEndInput, { ...fpConfig, defaultDate: initEnd });
  }

  if (applyFilterBtn && resetFilterBtn) {
    applyFilterBtn.addEventListener('click', () => {
      const startVal = filterStartInput.value;
      const endVal = filterEndInput.value;
      if (!startVal || !endVal) return;

      const startMs = Date.parse(startVal);
      const endMs = Date.parse(endVal);

      if (isNaN(startMs) || isNaN(endMs)) return;
      if (startMs >= endMs) {
        alert('Start date must be before the End date.');
        return;
      }

      // Update active boundaries
      t0_active = startMs;
      t1_active = endMs;
      span_active = Math.max(1, t1_active - t0_active);

      // Filter dataset
      const filteredT = [];
      const filteredCounts = [];
      const filteredHard = [];
      const filteredXrsb = [];

      for (let i = 0; i < originalLight.t.length; i++) {
        const tMs = Date.parse(originalLight.t[i]);
        if (tMs >= startMs && tMs <= endMs) {
          filteredT.push(originalLight.t[i]);
          filteredCounts.push(originalLight.counts[i]);
          filteredHard.push(originalLight.hard[i]);
          filteredXrsb.push(originalLight.xrsb[i]);
        }
      }

      const filteredFcurve = originalFcurve.filter(([ms]) => ms >= startMs && ms <= endMs);

      // Redraw ECharts instance
      lightChart.setOption({
        series: [
          { data: filteredT.map((t, i) => [t, positive(filteredCounts[i])]) },
          { data: hasHard ? filteredT.map((t, i) => [t, positive(filteredHard[i])]) : [] },
          { data: filteredT.map((t, i) => [t, positive(filteredXrsb[i])]) },
          { data: filteredFcurve.map(([ms, p]) => [new Date(ms).toISOString(), p]) }
        ]
      });

      // Update timeline cursor
      playing = false;
      playBtn.querySelector('.play-symbol').textContent = '▶';
      playBtn.querySelector('.play-label').textContent = 'Replay campaign';
      jump(t0_active);

      // Update flares-by-class bar chart
      updateDistFromFlares(startMs, endMs);
    });

    resetFilterBtn.addEventListener('click', () => {
      fpStart.setDate(new Date(t0));
      fpEnd.setDate(new Date(t1));

      t0_active = t0;
      t1_active = t1;
      span_active = span;

      // Restore ECharts instance full raw data
      lightChart.setOption({
        series: [
          { data: originalLight.t.map((t, i) => [t, positive(originalLight.counts[i])]) },
          { data: hasHard ? originalLight.t.map((t, i) => [t, positive(originalLight.hard[i])]) : [] },
          { data: originalLight.t.map((t, i) => [t, positive(originalLight.xrsb[i])]) },
          { data: originalFcurve.map(([ms, p]) => [new Date(ms).toISOString(), p]) }
        ]
      });

      playing = false;
      playBtn.querySelector('.play-symbol').textContent = '▶';
      playBtn.querySelector('.play-label').textContent = 'Replay campaign';
      jump(t1_active);

      // Restore flares-by-class bar chart to full data
      renderDistChart(initialDistCounts);
    });
  }

  function setCampaignClock(ms) {
    const d = new Date(ms);
    $('clock').textContent = d.toISOString().slice(11, 16);
    $('tlDate').textContent = `${d.toISOString().slice(0, 10)} · ${d.toISOString().slice(11, 16)}`;
  }

  function cursor(ms, force) {
    if (!force && performance.now() - lastCursor < 180) return;
    lastCursor = performance.now();
    lightChart.setOption({ series: [{ markLine: { label: { show: false }, data: [{ xAxis: new Date(ms).toISOString() }] } }] });
    if (typeof updatePieData === 'function') updatePieData(ms);
  }

  function jump(ms) {
    cur = ms;
    prev = ms;
    setCampaignClock(ms);
    cursor(ms, true);
    updateMcBars(ms);
    updateSolarStatus(forecastAt(ms));
    slider.value = ((ms - t0_active) / span_active) * 1000;
  }

  let lastTickTime = null;
  function tick(timestamp) {
    if (!playing) {
      lastTickTime = null;
      return;
    }
    if (lastTickTime === null) {
      lastTickTime = timestamp || performance.now();
      requestAnimationFrame(tick);
      return;
    }
    const elapsedRealMs = (timestamp || performance.now()) - lastTickTime;
    lastTickTime = timestamp || performance.now();

    const dtMs = (span_active / (duration * 1000)) * elapsedRealMs;
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
    updateSolarStatus(forecastAt(cur));
    prev = cur;
    setCampaignClock(cur);
    cursor(cur);
    slider.value = ((cur - t0_active) / span_active) * 1000;
    if (cur >= t1_active) {
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
    jump(t0_active + (Number(slider.value) / 1000) * span_active);
  });
  playBtn.addEventListener('click', () => {
    playing = !playing;
    if (playing) {
      if (cur >= t1_active) {
        cur = t0_active;
        prev = cur;
        fcArmed = true;
        feedEl.innerHTML = '';
      }
      playBtn.querySelector('.play-symbol').textContent = 'Ⅱ';
      playBtn.querySelector('.play-label').textContent = 'Pause replay';
      $('statusText').textContent = 'Replaying campaign';
      lastTickTime = null;
      tick();
    } else {
      playBtn.querySelector('.play-symbol').textContent = '▶';
      playBtn.querySelector('.play-label').textContent = 'Replay campaign';
      $('statusText').textContent = 'Monitoring nominally';
    }
  });

  // Expandable chart cards with smooth FLIP transitions.
  const backdrop = $('chartBackdrop');
  let expandedCard = null;

  function closeExpanded() {
    if (!expandedCard) return;
    const card = expandedCard;
    const placeholder = card._placeholder;

    if (placeholder) {
      // Get the target layout position from our placeholder
      const targetRect = placeholder.getBoundingClientRect();
      const currentRect = card.getBoundingClientRect();

      const invertX = targetRect.left - currentRect.left;
      const invertY = targetRect.top - currentRect.top;
      const scaleX = targetRect.width / currentRect.width;
      const scaleY = targetRect.height / currentRect.height;

      // Animate back to its origin layout
      card.style.transition = 'transform 0.46s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.46s cubic-bezier(0.16, 1, 0.3, 1)';
      card.style.transform = `translate(${invertX}px, ${invertY}px) scale(${scaleX}, ${scaleY})`;

      const btn = card.querySelector('.expand-btn');
      if (btn) btn.setAttribute('aria-expanded', 'false');
      backdrop.classList.remove('visible');
      document.body.classList.remove('chart-open');

      // Clean up styles and classes after transition finishes
      const cleanup = () => {
        card.removeEventListener('transitionend', cleanup);
        if (card._placeholder !== placeholder) return; // Guard against rapid multi-clicks
        card.classList.remove('is-expanded');
        card.style.transform = '';
        card.style.transformOrigin = '';
        card.style.transition = '';
        if (placeholder.parentNode) {
          placeholder.parentNode.removeChild(placeholder);
        }
        delete card._placeholder;
        resizeCharts(40);
      };
      card.addEventListener('transitionend', cleanup);
      // Fallback timer in case transitionend event does not fire (e.g. tab hidden)
      setTimeout(() => {
        if (card._placeholder === placeholder) cleanup();
      }, 500);
    } else {
      card.classList.remove('is-expanded');
      card.style.transform = '';
      card.style.transformOrigin = '';
      card.style.transition = '';
      const btn = card.querySelector('.expand-btn');
      if (btn) btn.setAttribute('aria-expanded', 'false');
      backdrop.classList.remove('visible');
      document.body.classList.remove('chart-open');
      resizeCharts(40);
    }
    expandedCard = null;
  }

  function expandCard(button) {
    const card = button.closest('.chart-card');
    if (!card) return;
    if (expandedCard === card) { closeExpanded(); return; }

    // Close any already expanded cards immediately
    if (expandedCard) {
      const prev = expandedCard;
      const ph = prev._placeholder;
      prev.classList.remove('is-expanded');
      prev.style.transform = '';
      prev.style.transformOrigin = '';
      prev.style.transition = '';
      if (ph && ph.parentNode) ph.parentNode.removeChild(ph);
      delete prev._placeholder;
    }

    expandedCard = card;

    // 1. Get initial bounds
    const first = card.getBoundingClientRect();

    // 2. Create placeholder to preserve page height/flow
    const placeholder = document.createElement('div');
    placeholder.id = 'chart-placeholder';
    placeholder.style.width = first.width + 'px';
    placeholder.style.height = first.height + 'px';
    placeholder.style.gridColumn = window.getComputedStyle(card).gridColumn;
    placeholder.style.gridRow = window.getComputedStyle(card).gridRow;
    placeholder.style.margin = window.getComputedStyle(card).margin;
    placeholder.style.visibility = 'hidden'; // Keep layout but don't show
    card.parentNode.insertBefore(placeholder, card);
    card._placeholder = placeholder;

    // 3. Render in expanded state (snaps to fixed dimensions instantly)
    card.classList.add('is-expanded');
    button.setAttribute('aria-expanded', 'true');
    backdrop.classList.add('visible');
    document.body.classList.add('chart-open');

    // 4. Get final bounds
    const last = card.getBoundingClientRect();

    // 5. Invert transform offset calculation
    const invertX = first.left - last.left;
    const invertY = first.top - last.top;
    const scaleX = first.width / last.width;
    const scaleY = first.height / last.height;

    // Set initial layout position offset instantly
    card.style.transformOrigin = 'top left';
    card.style.transform = `translate(${invertX}px, ${invertY}px) scale(${scaleX}, ${scaleY})`;
    card.style.transition = 'none';

    // Force layout reflow
    card.offsetHeight;

    // 6. Play the transition to final bounds
    card.style.transition = 'transform 0.46s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.46s cubic-bezier(0.16, 1, 0.3, 1)';
    card.style.transform = 'none';

    // Trigger instant resize so chart matches new aspect ratio, and resize again at transition end for sharp drawing
    resizeCharts(0);
    resizeCharts(150);
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
