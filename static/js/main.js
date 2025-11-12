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
    
    // Disable form during submission
    submitBtn.disabled = true;
    submitBtn.textContent = 'Connecting...';
    
    qs('#progress').classList.remove('hidden');
    qs('#progress').textContent = 'Finding connections...';
    
    // Clear previous results with fade
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
        
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        
        const data = await res.json();
        
        // Add to history
        addToHistory(body.concept_a, body.concept_b, data);
        
        // Render results
        renderResults(data);
        
        // Fade in results
        resultsArea.style.opacity = '1';
        resultsArea.style.transition = 'opacity 0.3s ease';
        
        qs('#progress').textContent = 'Connection complete!';
        setTimeout(() => {
            qs('#progress').classList.add('hidden');
        }, 1000);
        
    } catch (error) {
        console.error('Error:', error);
        qs('#progress').textContent = 'Error: ' + error.message;
        qs('#progress').style.background = '#d32f2f';
        
        setTimeout(() => {
            qs('#progress').classList.add('hidden');
            qs('#progress').style.background = '';
        }, 3000);
        
        resultsArea.style.opacity = '1';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
});

function renderGraph(connections){
    const container = d3.select('#connection-graph');
    container.html('');
    
    if (!connections || connections.length === 0) {
        container.append('div')
            .attr('class', 'empty-state')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .style('height', '100%')
            .html('<p style="color: #999;">No connections found</p>');
        return;
    }
    
    const width = container.node().clientWidth;
    const height = container.node().clientHeight;

    const nodes = [];
    const links = [];

    connections.forEach(c => {
        c.path.forEach((p, i) => {
            if (!nodes.find(n => n.id === p)) nodes.push({id: p});
            if (i < c.path.length - 1) {
                links.push({source: p, target: c.path[i+1]});
            }
        });
    });

    const svg = container.append('svg')
        .attr('width', width)
        .attr('height', height);

    // Add arrow marker definition
    svg.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '-0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .append('svg:path')
        .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
        .attr('fill', '#999');

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).distance(150).id(d => d.id))
        .force('charge', d3.forceManyBody().strength(-400))
        .force('center', d3.forceCenter(width/2, height/2))
        .force('collision', d3.forceCollide().radius(50));

    const link = svg.append('g').selectAll('line')
        .data(links)
        .enter().append('line')
        .attr('stroke', '#999')
        .attr('stroke-width', 2)
        .attr('marker-end', 'url(#arrowhead)');

    const nodeGroup = svg.append('g').selectAll('g')
        .data(nodes)
        .enter().append('g')
        .call(drag(simulation));

    nodeGroup.append('circle')
        .attr('r', 12)
        .attr('fill', '#1a1a2e')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .style('cursor', 'pointer')
        .on('mouseover', function() {
            d3.select(this).transition().duration(200)
                .attr('r', 15)
                .attr('fill', '#16213e');
        })
        .on('mouseout', function() {
            d3.select(this).transition().duration(200)
                .attr('r', 12)
                .attr('fill', '#1a1a2e');
        });

    nodeGroup.append('text')
        .text(d => d.id)
        .attr('font-size', 12)
        .attr('font-weight', 500)
        .attr('dx', 18)
        .attr('dy', 4)
        .style('pointer-events', 'none')
        .style('user-select', 'none');

    simulation.on('tick', () => {
        link.attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    function drag(simulation) {
        return d3.drag()
            .on('start', event => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            })
            .on('drag', event => {
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            })
            .on('end', event => {
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            });
    }
}

function renderResults(data){
    // Hide empty state
    qs('.empty-state-main')?.classList.add('hidden');
    
    // Show result sections
    qs('.explanation-section')?.classList.remove('hidden');
    qs('.analogy-section')?.classList.remove('hidden');
    qs('.bias-review')?.classList.remove('hidden');
    
    // Draw the graph
    renderGraph(data.connections);

    // Update explanations
    const explanationsEl = qs('#explanations');
    if (data.explanations && data.explanations.length > 0) {
        explanationsEl.innerHTML = data.explanations
            .map(exp => `<p>${exp}</p>`)
            .join('');
    } else {
        explanationsEl.innerHTML = '<p style="color: #999;">No explanations available.</p>';
    }

    // Update analogies
    const analogiesEl = qs('#analogies');
    if (data.analogies) {
        analogiesEl.innerHTML = data.analogies;
    } else {
        analogiesEl.innerHTML = '<p style="color: #999;">No analogies available.</p>';
    }

    // Update bias review
    const biasEl = qs('#bias-output');
    if (data.review) {
        biasEl.textContent = JSON.stringify(data.review, null, 2);
    } else {
        biasEl.textContent = 'No bias review available.';
    }
}

// History management
function addToHistory(conceptA, conceptB, data) {
    const historyItem = {
        id: Date.now(),
        conceptA,
        conceptB,
        timestamp: new Date().toLocaleString(),
        data
    };
    
    sessionHistory.unshift(historyItem);
    
    // Keep only last 10 items
    if (sessionHistory.length > 10) {
        sessionHistory = sessionHistory.slice(0, 10);
    }
    
    saveHistory();
    renderHistory();
}

function saveHistory() {
    // Store in sessionStorage for persistence during session
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
        historyList.innerHTML = '<li style="color: #999; cursor: default;">No history yet</li>';
        return;
    }
    
    historyList.innerHTML = sessionHistory.map(item => `
        <li data-id="${item.id}" title="Click to view">
            <strong>${item.conceptA}</strong> ↔ <strong>${item.conceptB}</strong>
            <div style="font-size: 0.75rem; color: #999; margin-top: 0.25rem;">${item.timestamp}</div>
        </li>
    `).join('');
    
    // Add click handlers
    qsa('#history-list li[data-id]').forEach(li => {
        li.addEventListener('click', () => {
            const id = parseInt(li.dataset.id);
            const item = sessionHistory.find(h => h.id === id);
            if (item) {
                // Populate form
                qs('input[name="concept_a"]').value = item.conceptA;
                qs('input[name="concept_b"]').value = item.conceptB;
                
                // Show results
                renderResults(item.data);
                
                // Highlight clicked item
                qsa('#history-list li').forEach(l => l.style.background = '#f5f5f5');
                li.style.background = '#e8e8e8';
            }
        });
    });
}

// Initialize empty state for graph
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