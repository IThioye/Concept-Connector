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

const queryForm = qs('#query-form');

const progressSteps = [
    'Gathering learner context',
    'Finding conceptual bridge',
    'Drafting explanations',
    'Creating analogies',
    'Reviewing alignment'
];
let progressTimer = null;
let progressIndex = -1;

const debounce = (fn, wait = 350) => {
    let t;
    let lastArgs;
    const debounced = (...args) => {
        lastArgs = args;
        clearTimeout(t);
        t = setTimeout(() => {
            t = null;
            fn(...(lastArgs || []));
        }, wait);
    };
    debounced.flush = () => {
        if (!t) return;
        clearTimeout(t);
        t = null;
        return fn(...(lastArgs || []));
    };
    return debounced;
};

function updateConceptLabels() {
    const conceptA = qs('input[name="concept_a"]').value.trim() || 'Concept A';
    const conceptB = qs('input[name="concept_b"]').value.trim() || 'Concept B';
    qsa('strong[data-concept="a"]').forEach(el => el.textContent = conceptA);
    qsa('strong[data-concept="b"]').forEach(el => el.textContent = conceptB);
}

function updateSliderDisplays() {
    qsa('input[name="concept_a_knowledge"], input[name="concept_b_knowledge"]').forEach(input => {
        const key = input.name === 'concept_a_knowledge' ? 'concept_a' : 'concept_b';
        const display = qs(`.slider-value[data-display="${key}"]`);
        if (display) {
            display.textContent = input.value;
        }
    });
}

function collectProfileData() {
    if (!queryForm) return {};
    const fd = new FormData(queryForm);
    return {
        session_id: sessionId,
        knowledge_level: fd.get('knowledge_level') || 'intermediate',
        education_level: (fd.get('education_level') || '').trim() || null,
        education_system: (fd.get('education_system') || '').trim() || null,
        concept_a_knowledge: Number(fd.get('concept_a_knowledge') || 0),
        concept_b_knowledge: Number(fd.get('concept_b_knowledge') || 0),
    };
}

const saveProfile = debounce(async () => {
    const payload = collectProfileData();
    if (!payload.session_id) return;
    try {
        await fetch('/api/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    } catch (error) {
        console.warn('Unable to persist profile preferences', error);
    }
}, 400);

async function loadProfile() {
    if (!queryForm) return;
    try {
        const res = await fetch(`/api/profile?session_id=${encodeURIComponent(sessionId)}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data) return;

        const level = queryForm.querySelector('select[name="knowledge_level"]');
        if (level && data.knowledge_level) {
            level.value = data.knowledge_level;
        }
        const educationLevel = queryForm.querySelector('input[name="education_level"]');
        if (educationLevel && data.education_level) {
            educationLevel.value = data.education_level;
        }
        const educationSystem = queryForm.querySelector('input[name="education_system"]');
        if (educationSystem && data.education_system) {
            educationSystem.value = data.education_system;
        }
        const conceptASlider = queryForm.querySelector('input[name="concept_a_knowledge"]');
        if (conceptASlider && typeof data.concept_a_knowledge === 'number') {
            conceptASlider.value = data.concept_a_knowledge;
        }
        const conceptBSlider = queryForm.querySelector('input[name="concept_b_knowledge"]');
        if (conceptBSlider && typeof data.concept_b_knowledge === 'number') {
            conceptBSlider.value = data.concept_b_knowledge;
        }

        updateSliderDisplays();
    } catch (error) {
        console.warn('Unable to load stored profile', error);
    }
}

function attachProfileInteractions() {
    if (!queryForm) return;

    const profileToggle = qs('#profile-toggle');
    const profileContent = qs('#profile-content');
    if (profileToggle && profileContent) {
        profileToggle.addEventListener('click', () => {
            profileContent.classList.toggle('collapsed');
            profileToggle.classList.toggle('collapsed');
        });
    }

    qsa('input[name="concept_a"], input[name="concept_b"]').forEach((input) => {
        input.addEventListener('input', () => {
            updateConceptLabels();
        });
    });

    qsa('select[name="knowledge_level"], input[name="education_level"], input[name="education_system"], input[name="concept_a_knowledge"], input[name="concept_b_knowledge"]').forEach((field) => {
        const eventType = field.type === 'range' ? 'input' : 'change';
        field.addEventListener(eventType, () => {
            if (field.type === 'range') {
                updateSliderDisplays();
            }
            saveProfile();
        });
    });
}

function initialiseProgress() {
    const container = qs('#progress-steps');
    if (!container) return;
    container.innerHTML = progressSteps
        .map((label, index) => `<li data-step="${index}" class="progress-step">${label}</li>`)
        .join('');
    progressIndex = -1;
}

function advanceProgress() {
    const container = qs('#progress-steps');
    if (!container) return;
    progressIndex += 1;
    const items = qsa('.progress-step');
    items.forEach((item, idx) => {
        if (idx < progressIndex) {
            item.classList.add('completed');
            item.classList.remove('active');
        } else if (idx === progressIndex) {
            item.classList.add('active');
        }
    });
    if (progressIndex >= items.length - 1 && progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
    }
}

function startProgress() {
    const progressBox = qs('#progress');
    if (!progressBox) return;
    progressBox.classList.remove('hidden');
    progressBox.classList.remove('error');
    const text = progressBox.querySelector('.progress-text');
    if (text) text.textContent = 'Coordinating agents...';
    initialiseProgress();
    advanceProgress();
    progressTimer = setInterval(advanceProgress, 1100);
}

function finishProgress({ success, message }) {
    const progressBox = qs('#progress');
    if (!progressBox) return;
    if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
    }

    qsa('.progress-step').forEach((item) => item.classList.add('completed'));

    const text = progressBox.querySelector('.progress-text');
    if (text) {
        text.textContent = message || (success ? 'Connection complete!' : 'Something went wrong');
    }

    if (success) {
        progressBox.classList.remove('error');
        setTimeout(() => progressBox.classList.add('hidden'), 900);
    } else {
        progressBox.classList.add('error');
    }
}

async function initialiseProfile() {
    await loadProfile();
    attachProfileInteractions();
    updateSliderDisplays();
    updateConceptLabels();
}

if (queryForm) {
    loadHistory();
    initialiseProfile();

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
        const conceptAInput = qs('input[name="concept_a"]');
        const conceptBInput = qs('input[name="concept_b"]');
        if (conceptAInput) conceptAInput.value = random.a;
        if (conceptBInput) conceptBInput.value = random.b;
        updateConceptLabels();
    });

    // Handle clear all button
    qs('#clear-btn')?.addEventListener('click', () => {
        queryForm.reset();
        updateSliderDisplays();
        updateConceptLabels();
        qs('.empty-state-main')?.classList.remove('hidden');
        qs('.explanation-section')?.classList.add('hidden');
        qs('.analogy-section')?.classList.add('hidden');
        qs('.feedback-section')?.classList.add('hidden');
        const progressBox = qs('#progress');
        if (progressBox) {
            progressBox.classList.add('hidden');
            progressBox.classList.remove('error');
        }
        d3.select('#connection-flow').html('');
    });

    queryForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        await saveProfile.flush?.();

        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn ? submitBtn.textContent : '';
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Connecting...';
        }

        const resultsArea = qs('#results');
        if (resultsArea) {
            resultsArea.style.opacity = '0.3';
        }

        startProgress();

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

            if (resultsArea) {
                resultsArea.style.opacity = '1';
                resultsArea.style.transition = 'opacity 0.3s ease';
            }

            finishProgress({ success: true, message: 'Connection complete!' });

        } catch (error) {
            console.error('Error:', error);
            if (resultsArea) {
                resultsArea.style.opacity = '1';
            }
            finishProgress({ success: false, message: `Error: ${error.message}` });
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        }
    });
}

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

    ['.explanation-section', '.analogy-section', '.feedback-section']
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
    if (!historyList) return;

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
                updateConceptLabels();
                qsa('#history-list li').forEach(l => l.style.background = '#f5f5f5');
                li.style.background = '#e8e8e8';
            }
        });
    });
}

// Initial empty state
if (document.getElementById('connection-graph')) {
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
}
