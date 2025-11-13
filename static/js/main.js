const qs = (s, r=document) => r.querySelector(s);
const qsa = (s, r=document) => Array.from(r.querySelectorAll(s));

// Session history stored in memory
let sessionHistory = [];

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
    
    try {
        const res = await fetch('/api/connect', {
            method:'POST', 
            headers:{'Content-Type':'application/json'}, 
            body: JSON.stringify(body)
        });
        
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        
        const data = await res.json();
        
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

function renderResults(data){
    qs('.empty-state-main')?.classList.add('hidden');
    
    qs('.explanation-section')?.classList.remove('hidden');
    qs('.analogy-section')?.classList.remove('hidden');
    qs('.bias-review')?.classList.remove('hidden');
    
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
    analogiesEl.innerHTML = data.analogies || '<p style="color:#999;">No analogies available.</p>';

    // Bias review
    const biasEl = qs('#bias-output');
    biasEl.innerHTML = data.review || '<p>No bias review available.</p>';
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
