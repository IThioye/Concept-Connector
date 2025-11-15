const qs = (s, r=document) => r.querySelector(s);
const qsa = (s, r=document) => Array.from(r.querySelectorAll(s));

// Session history stored in memory
let sessionHistory = [];
let lastResult = null;
let lastConceptPair = { conceptA: '', conceptB: '' };

const sessionId = (() => {
    const key = 'connectorSessionId';
    try {
        let existing = localStorage.getItem(key);
        if (!existing) {
            const random = (window.crypto && window.crypto.randomUUID)
                ? window.crypto.randomUUID()
                : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            localStorage.setItem(key, random);
            existing = random;
        }
        return existing;
    } catch (error) {
        console.warn('Falling back to ephemeral session id', error);
        return `session-${Date.now()}`;
    }
})();

// Load history on page load
loadHistory();

// Handle profile collapse
const profileToggle = qs('#profile-toggle');
const profileContent = qs('#profile-content');

if (profileToggle && profileContent) {
    profileToggle.addEventListener('click', () => {
        profileContent.classList.toggle('collapsed');
        profileToggle.classList.toggle('collapsed');
    });
}

// Handle random example button
qs('#random-btn')?.addEventListener('click', () => {
    const examples = [
        {a: 'Photosynthesis', b: 'Solar Panels'},
        {a: 'Neural Networks', b: 'Human Brain'},
        {a: 'Supply and Demand', b: 'Ecosystem Balance'},
        {a: 'Quantum Entanglement', b: 'Blockchain'},
        {a: 'Evolution', b: 'Machine Learning'}
    ];
    const random = examples[Math.floor(Math.random() * examples.length)];
    qs('input[name="concept_a"]').value = random.a;
    qs('input[name="concept_b"]').value = random.b;
});

// Handle clear all button
qs('#clear-btn')?.addEventListener('click', () => {
    qs('#query-form').reset();
    qs('.empty-state-main')?.classList.remove('hidden');
    qs('.explanation-section')?.classList.add('hidden');
    qs('.analogy-section')?.classList.add('hidden');
    qs('.bias-review')?.classList.add('hidden');
    d3.select('#connection-graph').html('');
});

qs('#query-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Connecting...';
    
    qs('#progress').classList.remove('hidden');
    qs('#progress').textContent = 'Finding connections...';
    
    const resultsArea = qs('#results');
    resultsArea.style.opacity = '0.3';
    
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    body.session_id = sessionId;
    lastConceptPair = { conceptA: body.concept_a, conceptB: body.concept_b };

    try {
        const res = await fetch('/api/connect', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify(body)
        });
        
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        
        const data = await res.json();

        lastResult = data;

        addToHistory(body.concept_a, body.concept_b, data);
        renderResults(data);
        
        resultsArea.style.opacity = '1';
        resultsArea.style.transition = 'opacity 0.3s ease';
        
        qs('#progress').textContent = 'Connection complete!';
        setTimeout(() => qs('#progress').classList.add('hidden'), 800);
        
    } catch (error) {
        console.error('Error:', error);
        qs('#progress').textContent = 'Error: ' + error.message;
        qs('#progress').style.background = '#d32f2f';
        setTimeout(() => {
            qs('#progress').classList.add('hidden');
            qs('#progress').style.background = '';
        }, 2000);
        resultsArea.style.opacity = '1';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
});

const feedbackForm = qs('#feedback-form');
if (feedbackForm) {
    feedbackForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(feedbackForm);
        const payload = {
            session_id: sessionId,
            rating: fd.get('rating') ? Number(fd.get('rating')) : null,
            comments: fd.get('comments')?.trim() || null,
            connection_id: (lastResult?.connections?.path || []).join(' → ') || null,
        };

        const status = qs('#feedback-status');
        try {
            const res = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            if (status) {
                status.textContent = 'Thanks for the feedback!';
                status.classList.remove('error');
            }
        } catch (err) {
            console.error('Feedback error', err);
            if (status) {
                status.textContent = 'Could not save feedback. Please try again later.';
                status.classList.add('error');
            }
        }
    });
}


/* --------------------------------------------------------------------------
   GRAPH RENDERING FOR SINGLE CONNECTION OBJECT
---------------------------------------------------------------------------*/

function renderGraph(connection) {
    const container = qs('#connection-flow');
    container.innerHTML = '';

    if (!connection || !connection.path) {
        container.innerHTML = `
            <p style="color:#999; text-align:center; width:100%;">
                No connection found
            </p>`;
        return;
    }

    const path = connection.path;
    const disciplines = connection.disciplines || [];

    path.forEach((concept, i) => {

        // Normalize discipline class name
        let d = (disciplines[i] || "other").toLowerCase();
        if (d.includes("bio")) d = "bio";
        else if (d.includes("computer")) d = "cs";
        else if (d.includes("math")) d = "math";
        else if (d.includes("phys")) d = "phys";
        else if (d.includes("energy")) d = "energy";
        else d = "other";

        const node = document.createElement('div');
        node.className = `flow-node ${d}`;
        node.textContent = concept;
        node.style.animationDelay = `${i * 0.15}s`;
        container.appendChild(node);

        // Add arrow unless it's the last item
        if (i < path.length - 1) {
            const arrow = document.createElement('div');
            arrow.className = 'flow-arrow';
            arrow.textContent = '→';
            arrow.style.animationDelay = `${i * 0.15 + 0.075}s`;
            container.appendChild(arrow);
        }
    });
}



/* --------------------------------------------------------------------------
   RENDER RESULTS
---------------------------------------------------------------------------*/

function renderBiasSection(items, hasBiasFlag) {
    const wrapper = qs('.bias-review');
    const biasEl = qs('#bias-output');
    if (!biasEl || !wrapper) return;

    if (Array.isArray(items) && items.length) {
        biasEl.innerHTML = `<ul>${items.map(item => `<li>${item}</li>`).join('')}</ul>`;
    } else {
        biasEl.innerHTML = '<p>No bias concerns surfaced.</p>';
    }

    wrapper.classList.remove('hidden');
    wrapper.classList.toggle('has-alert', !!hasBiasFlag);
}

function renderReviewSection(review) {
    const container = qs('#content-review');
    const wrapper = qs('.review-section');
    if (!container || !wrapper) return;

    if (!review) {
        container.innerHTML = '<p>No reviewer feedback available.</p>';
        wrapper.classList.remove('hidden');
        return;
    }

    const issues = Array.isArray(review.issues) && review.issues.length
        ? `<ul>${review.issues.map(item => `<li>${item}</li>`).join('')}</ul>`
        : '<p>No issues flagged.</p>';

    const actions = Array.isArray(review.suggested_actions) && review.suggested_actions.length
        ? `<ul>${review.suggested_actions.map(item => `<li>${item}</li>`).join('')}</ul>`
        : '<p>No further actions required.</p>';

    container.innerHTML = `
        <div class="review-summary">
            <div><strong>Level alignment:</strong> ${review.level_alignment ? '✅ On target' : '⚠️ Needs adjustment'}</div>
            <div><strong>Estimated reading level:</strong> ${review.reading_level || 'n/a'}</div>
            <div><strong>Bias risk:</strong> ${review.bias_risk || 'unknown'}</div>
        </div>
        <div class="review-issues">
            <h4>Issues</h4>
            ${issues}
        </div>
        <div class="review-actions">
            <h4>Suggested actions</h4>
            ${actions}
        </div>
    `;

    wrapper.classList.remove('hidden');
}

function renderFairnessSection(fairness) {
    const container = qs('#fairness-metrics');
    const wrapper = qs('.fairness-section');
    if (!container || !wrapper) return;

    if (!fairness || !Array.isArray(fairness.metrics)) {
        container.innerHTML = '<p>Fairness metrics unavailable.</p>';
        wrapper.classList.remove('hidden');
        return;
    }

    const rows = fairness.metrics.map(metric => {
        const value = Number(metric.value) || 0;
        const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
        return `
            <li class="fairness-metric">
                <div class="metric-header">
                    <span class="metric-name">${metric.label}</span>
                    <span class="metric-value">${pct}%</span>
                </div>
                <div class="metric-bar">
                    <span class="metric-bar-fill" style="width:${pct}%"></span>
                </div>
                <p class="metric-detail">${metric.detail || ''}</p>
            </li>
        `;
    }).join('');

    container.innerHTML = `
        <div class="fairness-overall">Overall fairness score: <strong>${fairness.overall ?? 'n/a'}</strong></div>
        <ul class="fairness-list">${rows}</ul>
    `;

    wrapper.classList.remove('hidden');
}

function renderGuidanceSection(guidance, mitigated, mitigationText) {
    const wrapper = qs('.guidance-section');
    const textEl = qs('#guidance-text');
    if (!wrapper || !textEl) return;

    const applied = guidance && guidance.trim().length
        ? guidance
        : 'No personalised guidance applied.';
    const mitigationNote = mitigated && mitigationText
        ? `<div class="mitigation-note"><strong>Mitigation applied:</strong> ${mitigationText}</div>`
        : '';

    textEl.innerHTML = `<p>${applied}</p>${mitigationNote}`;
    wrapper.classList.remove('hidden');
}

function prepareFeedbackForm() {
    const wrapper = qs('.feedback-section');
    const form = qs('#feedback-form');
    const status = qs('#feedback-status');
    if (status) {
        status.textContent = '';
        status.classList.remove('error');
    }
    if (!wrapper || !form) return;

    const connectionInput = form.querySelector('input[name="connection_id"]');
    if (connectionInput) {
        const path = (lastResult?.connections?.path || []).join(' → ');
        connectionInput.value = path;
    }

    const ratingField = form.querySelector('select[name="rating"]');
    if (ratingField) {
        ratingField.value = '4';
    }

    const commentsField = form.querySelector('textarea[name="comments"]');
    if (commentsField) {
        commentsField.value = '';
    }
    wrapper.classList.remove('hidden');
}

function renderResults(data){
    lastResult = data;
    qs('.empty-state-main')?.classList.add('hidden');

    ['.explanation-section', '.analogy-section', '.bias-review', '.review-section', '.fairness-section', '.guidance-section', '.feedback-section']
        .forEach(sel => qs(sel)?.classList.remove('hidden'));

    // Graph
    renderGraph(data.connections);

    // Explanations
    const explanationsEl = qs('#explanations');

    if (data.explanations) {
        if (Array.isArray(data.explanations)) {
            explanationsEl.innerHTML = data.explanations
                .map(exp => `<div class="exp-block">${exp}</div>`)
                .join('');
        } else {
            // Single string
            explanationsEl.innerHTML = `<div class="exp-block">${data.explanations}</div>`;
        }
    } else {
        explanationsEl.innerHTML = '<p style="color:#999;">No explanations available.</p>';
    }

    // Analogies
    const analogiesEl = qs('#analogies');
    if (Array.isArray(data.analogies)) {
        if (data.analogies.length) {
            analogiesEl.innerHTML = `<ul>${data.analogies.map(item => `<li>${item}</li>`).join('')}</ul>`;
        } else {
            analogiesEl.innerHTML = '<p style="color:#999;">No analogies available.</p>';
        }
    } else {
        analogiesEl.innerHTML = data.analogies || '<p style="color:#999;">No analogies available.</p>';
    }

    renderBiasSection(data.bias_review ?? data.review, data.bias_flag);
    renderReviewSection(data.content_review);
    renderFairnessSection(data.fairness);
    renderGuidanceSection(data.feedback_guidance, data.mitigated, data.mitigation_guidance);
    prepareFeedbackForm();
}


/* --------------------------------------------------------------------------
   HISTORY SYSTEM
---------------------------------------------------------------------------*/

function addToHistory(conceptA, conceptB, data) {
    const historyItem = {
        id: Date.now(),
        conceptA,
        conceptB,
        timestamp: new Date().toLocaleString(),
        data
    };
    
    sessionHistory.unshift(historyItem);

    if (sessionHistory.length > 10)
        sessionHistory = sessionHistory.slice(0, 10);
    
    saveHistory();
    renderHistory();
}

function saveHistory() {
    try {
        sessionStorage.setItem('conceptHistory', JSON.stringify(sessionHistory));
    } catch (e) {
        console.warn('Could not save history:', e);
    }
}

function loadHistory() {
    try {
        const saved = sessionStorage.getItem('conceptHistory');
        if (saved) {
            sessionHistory = JSON.parse(saved);
            renderHistory();
        }
    } catch (e) {
        console.warn('Could not load history:', e);
    }
}

function renderHistory() {
    const historyList = qs('#history-list');
    
    if (sessionHistory.length === 0) {
        historyList.innerHTML = '<li style="color: #999;">No history yet</li>';
        return;
    }
    
    historyList.innerHTML = sessionHistory.map(item => `
        <li data-id="${item.id}" title="Click to view">
            <strong>${item.conceptA}</strong> ↔ <strong>${item.conceptB}</strong>
            <div style="font-size:0.75rem;color:#999;margin-top:0.25rem;">
                ${item.timestamp}
            </div>
        </li>
    `).join('');

    qsa('#history-list li[data-id]').forEach(li => {
        li.addEventListener('click', () => {
            const id = parseInt(li.dataset.id);
            const item = sessionHistory.find(h => h.id === id);
            if (item) {
                qs('input[name="concept_a"]').value = item.conceptA;
                qs('input[name="concept_b"]').value = item.conceptB;
                lastResult = item.data;
                lastConceptPair = { conceptA: item.conceptA, conceptB: item.conceptB };
                renderResults(item.data);
                qsa('#history-list li').forEach(l => l.style.background = '#f5f5f5');
                li.style.background = '#e8e8e8';
            }
        });
    });
}

// Initial empty state
d3.select('#connection-graph')
    .append('div')
    .attr('class', 'empty-state')
    .style('display', 'flex')
    .style('align-items', 'center')
    .style('justify-content', 'center')
    .style('height', '100%')
    .style('color', '#999')
    .style('font-size', '0.95rem')
    .html('Graph will appear here');
