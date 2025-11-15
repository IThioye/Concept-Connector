const sessionKey = 'connectorSessionId';

function resolveSessionId() {
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

async function fetchFairness() {
  try {
    const res = await fetch(`/api/fairness?session_id=${encodeURIComponent(sessionId)}&limit=6`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error('Unable to load fairness data', error);
    return { items: [], aggregate: { avg_overall: null, runs: 0, bias_flags: 0 } };
  }
}

function renderSummary(aggregate) {
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
  const data = await fetchFairness();
  renderSummary(data.aggregate || {});
  renderHistory(data.items || []);
});
