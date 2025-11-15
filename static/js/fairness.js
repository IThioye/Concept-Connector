const sessionKey = 'connectorSessionId';
const fairnessCacheKey = 'connectorFairnessCache';

function computeAggregate(items) {
  if (!Array.isArray(items) || !items.length) {
    return { avg_overall: null, runs: 0, bias_flags: 0 };
  }

  const overalls = items
    .map((entry) => entry?.fairness?.overall)
    .filter((value) => typeof value === 'number');

  const avg = overalls.length
    ? Math.round((overalls.reduce((acc, value) => acc + value, 0) / overalls.length) * 100) / 100
    : null;

  return {
    avg_overall: avg,
    runs: items.length,
    bias_flags: items.filter((entry) => entry?.bias_flag).length,
  };
}

function getSessionIdFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get('session_id');
  return fromUrl && fromUrl.trim() ? fromUrl.trim() : null;
}

function resolveSessionId() {
  const fromQuery = getSessionIdFromQuery();
  if (fromQuery) return fromQuery;

  try {
    let existing = localStorage.getItem(sessionKey);
    if (!existing) {
      existing = `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      localStorage.setItem(sessionKey, existing);
    }
    return existing;
  } catch (error) {
    console.warn('Falling back to ephemeral session id', error);
    return `session-${Date.now()}`;
  }
}

const sessionId = resolveSessionId();

function loadCachedFairness() {
  try {
    const raw = localStorage.getItem(fairnessCacheKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    if (!parsed.aggregate) {
      parsed.aggregate = computeAggregate(parsed.items || []);
    }
    return parsed;
  } catch (error) {
    console.warn('Unable to read cached fairness data', error);
    return null;
  }
}

function persistFairness(payload) {
  try {
    localStorage.setItem(fairnessCacheKey, JSON.stringify(payload));
  } catch (error) {
    console.warn('Unable to persist fairness cache', error);
  }
}

async function fetchFairness() {
  try {
    const res = await fetch(`/api/fairness?session_id=${encodeURIComponent(sessionId)}&limit=6`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data.items) && data.items.length) {
      const aggregate = data.aggregate && typeof data.aggregate === 'object'
        ? data.aggregate
        : computeAggregate(data.items);
      persistFairness({ items: data.items, aggregate });
    }
    return data;
  } catch (error) {
    console.error('Unable to load fairness data', error);
    return { items: [], aggregate: { avg_overall: null, runs: 0, bias_flags: 0 } };
  }
}

function renderSummary(aggregate, items = []) {
  if (!aggregate || typeof aggregate !== 'object') {
    aggregate = computeAggregate(items);
  }
  const avg = document.getElementById('avg-fairness');
  const runs = document.getElementById('reviewed-count');
  const bias = document.getElementById('bias-count');

  if (avg) {
    avg.textContent = aggregate.avg_overall != null ? `${Math.round(aggregate.avg_overall * 100)}%` : '–';
  }
  if (runs) {
    runs.textContent = aggregate.runs || 0;
  }
  if (bias) {
    bias.textContent = aggregate.bias_flags || 0;
  }
}

function renderHistory(items) {
  const container = document.getElementById('fairness-history');
  if (!container) return;

  if (!items.length) {
    container.classList.add('empty');
    container.innerHTML = '<p class="empty-copy">No fairness evaluations recorded yet for this session.</p>';
    return;
  }

  const fragments = items.map((entry) => {
    const fairness = entry.fairness || {};
    const metrics = Array.isArray(fairness.metrics) ? fairness.metrics : [];
    const metricsList = metrics
      .map((metric) => {
        const pct = typeof metric.value === 'number' ? Math.round(metric.value * 100) : 0;
        return `
          <li class="metric-item">
            <div class="metric-label">
              <span>${metric.label}</span>
              <strong>${pct}%</strong>
            </div>
            <p class="metric-detail">${metric.detail || ''}</p>
          </li>
        `;
      })
      .join('');

    const metricsMarkup = metricsList || '<li class="metric-item empty">No fairness metrics recorded.</li>';

    const biasNotes = Array.isArray(entry.bias_review) && entry.bias_review.length
      ? `<ul class="bias-list">${entry.bias_review.map((note) => `<li>${note}</li>`).join('')}</ul>`
      : '<p class="bias-empty">No bias concerns recorded.</p>';

    const overall = typeof fairness.overall === 'number' ? Math.round(fairness.overall * 100) : null;

    return `
      <article class="history-card${entry.bias_flag ? ' bias-flagged' : ''}">
        <header class="history-card__header">
          <div>
            <h3>${entry.concept_a} ↔ ${entry.concept_b}</h3>
            <p class="history-timestamp">${entry.timestamp || ''}</p>
          </div>
          <div class="history-score">
            <span class="score-label">Overall</span>
            <span class="score-value">${overall != null ? overall + '%' : 'n/a'}</span>
          </div>
        </header>
        <div class="history-card__body">
          <section class="history-section">
            <h4>Fairness Metrics</h4>
            <ul class="metric-list">${metricsMarkup}</ul>
          </section>
          <section class="history-section">
            <h4>Bias Review</h4>
            ${biasNotes}
          </section>
        </div>
      </article>
    `;
  });

  container.classList.remove('empty');
  container.innerHTML = fragments.join('');
}

document.addEventListener('DOMContentLoaded', async () => {
  let data = await fetchFairness();
  if (!Array.isArray(data.items) || !data.items.length) {
    const cached = loadCachedFairness();
    if (cached) {
      data = cached;
    }
  }
  const items = Array.isArray(data.items) ? data.items : [];
  renderSummary(data.aggregate, items);
  renderHistory(items);
});

document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState !== 'visible') return;
  let data = await fetchFairness();
  if (!Array.isArray(data.items) || !data.items.length) {
    const cached = loadCachedFairness();
    if (cached) {
      data = cached;
    }
  }
  const items = Array.isArray(data.items) ? data.items : [];
  renderSummary(data.aggregate, items);
  renderHistory(items);
});
