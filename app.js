// === Theme Toggle ===
(function() {
  const btn = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  root.setAttribute('data-theme', theme);
  updateThemeIcon();

  btn && btn.addEventListener('click', () => {
    theme = theme === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', theme);
    updateThemeIcon();
  });

  function updateThemeIcon() {
    if (!btn) return;
    btn.innerHTML = theme === 'dark'
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }
})();

// === Helpers ===
function parsePrice(str) {
  if (!str) return 0;
  return parseInt(str.replace(/[^0-9]/g, ''), 10) || 0;
}

function getRouteCheapest(route) {
  const cronPrice = parsePrice(route.cheapest_price);
  const tableMin = route.flights.length > 0
    ? route.flights.reduce((min, f) => Math.min(min, parsePrice(f.price_usd)), Infinity)
    : Infinity;
  const best = Math.min(cronPrice || Infinity, tableMin);
  return best < Infinity ? `$${best}` : route.cheapest_price;
}

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function formatLastUpdated(isoStr) {
  const d = new Date(isoStr);
  const now = new Date();
  const diffMin = Math.floor((now - d) / 60000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function buildGoogleFlightsLink(fromCode, toCode, date) {
  return `https://www.google.com/travel/flights?q=Flights+to+${toCode}+from+${fromCode}+on+${date}+oneway&curr=USD`;
}

// === Price Signal Logic ===
function computePriceLevel(currentPrice, typicalLow, typicalHigh) {
  const current = parsePrice(currentPrice);
  const low = parsePrice(typicalLow);
  const high = parsePrice(typicalHigh);
  if (!current || !low || !high) return 'unknown';
  if (current < low) return 'low';
  if (current > high) return 'high';
  return 'typical';
}

function getPriceLevelConfig(level) {
  const l = (level || '').toLowerCase();
  if (l === 'low') return { label: 'Low', icon: '↓', cssClass: 'signal-low', recommendation: 'Good time to book' };
  if (l === 'typical') return { label: 'Typical', icon: '→', cssClass: 'signal-typical', recommendation: 'Normal pricing' };
  if (l === 'high') return { label: 'High', icon: '↑', cssClass: 'signal-high', recommendation: 'Consider waiting' };
  return { label: 'Unknown', icon: '?', cssClass: 'signal-unknown', recommendation: '' };
}

function getTrendConfig(trend) {
  const t = (trend || '').toLowerCase();
  if (t.includes('increasing') || t.includes('risen') || t.includes('climbed') || t.includes('upward')) {
    return { label: 'Rising', icon: '↗', cssClass: 'trend-up' };
  }
  if (t.includes('decreasing') || t.includes('falling') || t.includes('dropped') || t.includes('down')) {
    return { label: 'Falling', icon: '↘', cssClass: 'trend-down' };
  }
  if (t.includes('stable') || t.includes('flat') || t.includes('steady')) {
    return { label: 'Stable', icon: '→', cssClass: 'trend-stable' };
  }
  return { label: 'Unknown', icon: '', cssClass: 'trend-unknown' };
}

function renderPriceGauge(currentPrice, typicalLow, typicalHigh) {
  const current = parsePrice(currentPrice);
  const low = parsePrice(typicalLow);
  const high = parsePrice(typicalHigh);

  if (!current || !low || !high || low >= high) return '';

  const allValues = [current, low, high];
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const span = maxVal - minVal;
  const padding = Math.max(span * 0.25, (low + high) / 2 * 0.1);
  const scaleMin = Math.floor(minVal - padding);
  const scaleMax = Math.ceil(maxVal + padding);
  const scaleRange = scaleMax - scaleMin;

  const toPct = (val) => ((val - scaleMin) / scaleRange * 100).toFixed(1);

  const typicalLeftPct = toPct(low);
  const typicalRightPct = toPct(high);
  const typicalWidthPct = (typicalRightPct - typicalLeftPct).toFixed(1);
  const currentPct = Math.min(Math.max(parseFloat(toPct(current)), 2), 98).toFixed(1);

  const overpay = current > high ? current - high : 0;
  const underpay = current < low ? low - current : 0;

  let deltaLabel = '';
  if (overpay > 0) deltaLabel = `<span class="gauge-delta delta-over">+$${overpay} above typical</span>`;
  else if (underpay > 0) deltaLabel = `<span class="gauge-delta delta-under">$${underpay} below typical</span>`;
  else deltaLabel = `<span class="gauge-delta delta-in">Within typical range</span>`;

  return `
    <div class="price-gauge">
      <div class="gauge-marker-row" style="padding-left:${currentPct}%">
        <span class="gauge-marker-label">${currentPrice}</span>
      </div>
      <div class="gauge-bar">
        <div class="gauge-typical" style="left:${typicalLeftPct}%;width:${typicalWidthPct}%"></div>
        <div class="gauge-marker" style="left:${currentPct}%">
          <div class="gauge-marker-line"></div>
        </div>
      </div>
      <div class="gauge-labels-row">
        <span class="gauge-label-low" style="left:${typicalLeftPct}%">${typicalLow}</span>
        <span class="gauge-label-high" style="left:${typicalRightPct}%">${typicalHigh}</span>
      </div>
      ${deltaLabel}
    </div>
  `;
}

// === State ===
let activeCardIndex = null;

// === Build summary cards (clickable) ===
function renderSummary(data) {
  const container = document.getElementById('summaryCards');
  let html = '';

  let lowCount = 0, typCount = 0, highCount = 0, actualTotal = 0;

  const routeDetails = data.routes.map(route => {
    const ins = route.price_insights || {};
    const cheapest = getRouteCheapest(route);
    actualTotal += parsePrice(cheapest);

    const level = computePriceLevel(cheapest, ins.typical_low, ins.typical_high);
    if (level === 'low') lowCount++;
    else if (level === 'typical') typCount++;
    else if (level === 'high') highCount++;

    return { actualCheapest: cheapest, level };
  });

  data.routes.forEach((route, idx) => {
    const ins = route.price_insights || {};
    const { actualCheapest, level } = routeDetails[idx];
    const levelConfig = getPriceLevelConfig(level);

    html += `
      <div class="kpi-card" data-route-index="${idx}" role="button" tabindex="0">
        <div class="kpi-label">${route.from_city} → ${route.to_city}</div>
        <div class="kpi-value">${actualCheapest}</div>
        <div class="kpi-signal">
          <span class="signal-badge ${levelConfig.cssClass}">${levelConfig.icon} ${levelConfig.label}</span>
          <span class="kpi-range">${ins.typical_low || '?'}–${ins.typical_high || '?'}</span>
        </div>
        <div class="kpi-date">${formatDate(route.date)}</div>
        <div class="kpi-expand-hint">Click for details</div>
      </div>
    `;
  });

  html += `
    <div class="kpi-card total">
      <div class="kpi-label">Total (Cheapest)</div>
      <div class="kpi-value">$${actualTotal}</div>
      <div class="kpi-signal-summary">
        ${highCount > 0 ? `<span class="signal-count signal-high">${highCount} high</span>` : ''}
        ${typCount > 0 ? `<span class="signal-count signal-typical">${typCount} typical</span>` : ''}
        ${lowCount > 0 ? `<span class="signal-count signal-low">${lowCount} low</span>` : ''}
      </div>
    </div>
  `;

  container.innerHTML = html;

  // Attach click handlers
  container.querySelectorAll('.kpi-card[data-route-index]').forEach(card => {
    card.addEventListener('click', () => {
      const idx = parseInt(card.dataset.routeIndex);
      toggleDetail(idx, data);
    });
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const idx = parseInt(card.dataset.routeIndex);
        toggleDetail(idx, data);
      }
    });
  });
}

// === Toggle detail panel ===
function toggleDetail(idx, data) {
  const panel = document.getElementById('detailPanel');
  const allCards = document.querySelectorAll('.kpi-card[data-route-index]');

  // If clicking the same card, close it
  if (activeCardIndex === idx) {
    activeCardIndex = null;
    panel.innerHTML = '';
    panel.classList.remove('open');
    allCards.forEach(c => c.classList.remove('active'));
    return;
  }

  activeCardIndex = idx;
  allCards.forEach(c => c.classList.remove('active'));
  allCards[idx].classList.add('active');

  const route = data.routes[idx];
  const displayPrice = getRouteCheapest(route);
  const googleLink = buildGoogleFlightsLink(route.from_code, route.to_code, route.date);
  const ins = route.price_insights || {};
  const derivedLevel = computePriceLevel(displayPrice, ins.typical_low, ins.typical_high);
  const levelConfig = getPriceLevelConfig(derivedLevel);
  const trendConfig = getTrendConfig(ins.trend);
  const gaugeHtml = renderPriceGauge(displayPrice, ins.typical_low, ins.typical_high);

  let html = `
    <div class="detail-content">
      <div class="detail-header">
        <div class="detail-route">
          <span class="detail-route-number">${idx + 1}</span>
          <span class="detail-route-cities">${route.from_city} <span class="detail-arrow">→</span> ${route.to_city}</span>
          <span class="detail-route-codes">${route.from_code} → ${route.to_code}</span>
          <span class="detail-route-date">${formatDate(route.date)}</span>
        </div>
        <div class="detail-actions">
          ${levelConfig.recommendation ? `<span class="insight-recommendation ${levelConfig.cssClass}">${levelConfig.recommendation}</span>` : ''}
          ${trendConfig.label !== 'Unknown' ? `
          <div class="trend-indicator ${trendConfig.cssClass}">
            <span class="trend-icon">${trendConfig.icon}</span>
            <span class="trend-label">${trendConfig.label}</span>
          </div>
          ` : ''}
          <a href="${googleLink}" target="_blank" rel="noopener" class="route-link">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
            Google Flights
          </a>
        </div>
      </div>
      ${gaugeHtml ? `<div class="detail-gauge">${gaugeHtml}</div>` : '<div class="detail-no-gauge">No typical price range available for this route</div>'}
      ${route.flights.length > 0 ? `
      <div class="detail-prices">
        <div class="detail-prices-label">All prices found</div>
        <div class="detail-price-chips">
          ${route.flights.map((f, i) => {
            const isCheapest = i === 0;
            return `<span class="price-chip ${isCheapest ? 'cheapest' : ''}">${f.price_usd}${isCheapest ? ' ✦' : ''}</span>`;
          }).join('')}
        </div>
      </div>
      ` : ''}
    </div>
  `;

  panel.innerHTML = html;
  panel.classList.add('open');
}

// === Load data ===
async function loadData() {
  try {
    const res = await fetch('flight_data.json?t=' + Date.now());
    const data = await res.json();

    document.getElementById('lastUpdated').textContent = formatLastUpdated(data.last_updated);
    renderSummary(data);
  } catch (err) {
    console.error('Failed to load flight data:', err);
    document.getElementById('summaryCards').innerHTML = '<div class="kpi-card" style="grid-column: 1/-1; text-align:center; padding:32px;">Failed to load flight data. Please refresh.</div>';
  }
}

loadData();
