document.addEventListener('DOMContentLoaded', () => {
    let network = null;
    let nodesData = new vis.DataSet();
    let edgesData = new vis.DataSet();
    
    const container = document.getElementById('network-graph');
    const thresholdSlider = document.getElementById('threshold-slider');
    const thresholdVal = document.getElementById('threshold-val');
    const neighborSlider = document.getElementById('neighbor-slider');
    const neighborVal = document.getElementById('neighbor-val');
    const refreshButton = document.getElementById('refresh-button');
    const isolateToggle = document.getElementById('isolate-toggle');
    const feedContainer = document.getElementById('feed');
    const feedSearch = document.getElementById('feed-search');
    const feedCount = document.getElementById('feed-count');
    const graphCount = document.getElementById('graph-count');
    const graphEdgeCount = document.getElementById('graph-edge-count');
    const graphEmpty = document.getElementById('graph-empty');
    
    const detailsPanel = document.getElementById('thought-details');
    const selectedText = document.getElementById('selected-text');
    const selectedMeta = document.getElementById('selected-meta');
    const selectedFields = document.getElementById('selected-fields');
    const selectedSource = document.getElementById('selected-source');
    const selectedSourceText = document.getElementById('selected-source-text');
    const closeDetailsBtn = document.getElementById('close-details');
    const entitySelect = document.getElementById('entity-select');
    const REFRESH_INTERVAL_MS = 15000;
    let feedSignature = null;
    let graphSignature = null;
    let refreshPromise = null;
    let entitySignature = null;
    let selectedEntityCount = null;
    let currentThoughts = [];
    let latestGraphData = null;
    let physicsFreezeTimer = null;

    function entityParam() {
        const value = entitySelect.value;
        return value ? `&entity=${encodeURIComponent(value)}` : '';
    }
    
    // Vis.js Options (Dark Theme, smooth physics)
    const options = {
        nodes: {
            shape: 'dot',
            size: 9,
            font: {
                size: 12,
                color: '#e0e0e0',
                face: 'Segoe UI',
                strokeWidth: 4,
                strokeColor: '#121212'
            },
            color: {
                border: '#4fc1ff',
                background: '#007acc',
                highlight: {
                    border: '#ffffff',
                    background: '#4fc1ff'
                },
                hover: {
                    border: '#ffffff',
                    background: '#4fc1ff'
                }
            },
            borderWidth: 2,
            shadow: false
        },
        edges: {
            width: 1,
            color: {
                color: 'rgba(112, 181, 203, 0.28)',
                highlight: 'rgba(158, 225, 242, 0.95)',
                hover: 'rgba(158, 225, 242, 0.7)'
            },
            smooth: false
        },
        physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -45,
                centralGravity: 0.012,
                springLength: 85,
                springConstant: 0.07,
                damping: 0.4,
                avoidOverlap: 0.75
            },
            stabilization: {
                iterations: 300,
                fit: true
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200,
            zoomView: true
        }
    };

    // Initialize Network
    network = new vis.Network(container, { nodes: nodesData, edges: edgesData }, options);
    function freezeGraphLayout() {
        if (physicsFreezeTimer) {
            clearTimeout(physicsFreezeTimer);
            physicsFreezeTimer = null;
        }
        network.stopSimulation();
        network.setOptions({ physics: { enabled: false } });
        const positions = network.getPositions();
        nodesData.update(Object.entries(positions).map(([id, position]) => ({
            id,
            x: position.x,
            y: position.y,
            fixed: { x: true, y: true }
        })));
        if (nodesData.length > 0) {
            network.fit({ animation: false });
        }
    }

    network.on('stabilized', freezeGraphLayout);
    network.on('stabilizationIterationsDone', freezeGraphLayout);

    function revealNeighborhood(nodeId) {
        const neighborhood = new Set([nodeId, ...network.getConnectedNodes(nodeId)]);
        nodesData.update(nodesData.get().map(node => ({
            id: node.id,
            label: neighborhood.has(node.id) ? node.short_label : ''
        })));
    }

    function clearNeighborhoodLabels() {
        nodesData.update(nodesData.get().map(node => ({ id: node.id, label: '' })));
    }

    network.on("selectNode", function (params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const node = nodesData.get(nodeId);
            revealNeighborhood(nodeId);
            showDetails(node);
        }
    });

    network.on("deselectNode", function () {
        clearNeighborhoodLabels();
        hideDetails();
    });

    closeDetailsBtn.addEventListener('click', () => {
        network.unselectAll();
        clearNeighborhoodLabels();
        hideDetails();
    });

    // Update threshold live
    thresholdSlider.addEventListener('input', (e) => {
        thresholdVal.textContent = e.target.value;
    });

    thresholdSlider.addEventListener('change', (e) => {
        loadGraph(e.target.value, neighborSlider.value);
    });

    neighborSlider.addEventListener('input', (e) => {
        neighborVal.textContent = e.target.value;
    });

    neighborSlider.addEventListener('change', (e) => {
        loadGraph(thresholdSlider.value, e.target.value);
    });

    function showDetails(item) {
        if (!item) return;

        selectedMeta.innerHTML = '';
        [
            [item.person_id, 'person'],
            [item.claim_type, (item.claim_type || '').toLowerCase()],
            [item.evidence_id, 'evidence']
        ].forEach(([value, className]) => {
            if (!value) return;
            const badge = document.createElement('span');
            badge.className = `meta-badge ${className}`;
            badge.textContent = value;
            selectedMeta.appendChild(badge);
        });

        selectedText.textContent = item.text || item.full_text || '';
        selectedFields.innerHTML = '';
        [
            ['Section', item.source_section],
            ['Confidence', item.confidence]
        ].forEach(([name, value]) => {
            if (!value) return;
            const term = document.createElement('dt');
            term.textContent = name;
            const description = document.createElement('dd');
            description.textContent = value;
            selectedFields.append(term, description);
        });

        if (item.raw_profile_language) {
            selectedSourceText.textContent = item.raw_profile_language;
            selectedSource.classList.remove('hidden');
        } else {
            selectedSourceText.textContent = '';
            selectedSource.classList.add('hidden');
        }
        detailsPanel.classList.remove('hidden');
        
        document.querySelectorAll('.thought-card').forEach(card => {
            if (card.dataset.id === String(item.id)) {
                card.classList.add('active');
                card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                card.classList.remove('active');
            }
        });
    }

    function hideDetails() {
        detailsPanel.classList.add('hidden');
        document.querySelectorAll('.thought-card').forEach(card => card.classList.remove('active'));
    }

    async function fetchJson(url) {
        const response = await fetch(url, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`${url} returned ${response.status}`);
        }
        return response.json();
    }

    async function loadEntities() {
        try {
            const data = await fetchJson('/api/entities');
            if (!Array.isArray(data.entities)) return;
            const nextSignature = JSON.stringify(data.entities);
            if (nextSignature === entitySignature) return;
            entitySignature = nextSignature;

            const current = localStorage.getItem('selectedEntity') || entitySelect.value;
            entitySelect.innerHTML = '';
            data.entities.forEach(item => {
                const option = document.createElement('option');
                option.value = item.default ? '' : item.entity;
                option.textContent = item.default
                    ? `Subconscious (default) — ${item.count}`
                    : `${item.entity} — ${item.count}`;
                entitySelect.appendChild(option);
            });
            entitySelect.value = current;
            if (entitySelect.selectedIndex === -1) entitySelect.selectedIndex = 0;
            const selectedEntity = data.entities.find(item => (
                entitySelect.value ? item.entity === entitySelect.value : item.default
            ));
            selectedEntityCount = selectedEntity ? selectedEntity.count : null;
        } catch (err) {
            console.error("Failed to load entities:", err);
        }
    }

    function renderFeed() {
        const query = feedSearch.value.trim().toLowerCase();
        const thoughts = currentThoughts.filter(thought => {
            if (!query) return true;
            return [
                thought.text,
                thought.person_id,
                thought.evidence_id,
                thought.claim_type,
                thought.source_section,
                thought.confidence,
                thought.raw_profile_language
            ].filter(Boolean).join(' ').toLowerCase().includes(query);
        });

        feedCount.textContent = query
            ? `${thoughts.length} of ${currentThoughts.length} claims`
            : `${currentThoughts.length} claims`;
        feedContainer.innerHTML = '';

        if (thoughts.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'feed-empty';
            empty.textContent = 'No evidence matches this filter.';
            feedContainer.appendChild(empty);
            return;
        }

        thoughts.forEach(thought => {
            const div = document.createElement('div');
            div.className = `thought-card ${(thought.claim_type || '').toLowerCase()}`;
            div.dataset.id = thought.id;
            if (thought.person_id || thought.claim_type || thought.evidence_id) {
                const metadata = document.createElement('span');
                metadata.className = 'thought-meta';
                metadata.textContent = [
                    thought.person_id,
                    thought.claim_type,
                    thought.evidence_id
                ].filter(Boolean).join(' · ');
                div.appendChild(metadata);
            }
            const text = document.createElement('p');
            text.textContent = thought.text;
            div.appendChild(text);

            div.addEventListener('click', () => {
                if (!nodesData.get(thought.id) && latestGraphData) {
                    isolateToggle.checked = true;
                    renderGraph(latestGraphData, thresholdSlider.value);
                }
                network.selectNodes([thought.id]);
                revealNeighborhood(thought.id);
                network.focus(thought.id, {
                    scale: 1.35,
                    animation: { duration: 500, easingFunction: "easeInOutQuad" }
                });
                showDetails(nodesData.get(thought.id) || thought);
            });

            feedContainer.appendChild(div);
        });
    }

    async function loadFeed() {
        try {
            const data = await fetchJson(`/api/thoughts?_=1${entityParam()}`);
            if (!Array.isArray(data.thoughts)) {
                throw new Error('/api/thoughts returned an invalid payload');
            }

            const thoughts = [...data.thoughts].sort((first, second) => {
                return new Date(second.timestamp || 0) - new Date(first.timestamp || 0);
            });
            const nextSignature = JSON.stringify(thoughts);
            if (nextSignature === feedSignature) {
                return;
            }

            feedSignature = nextSignature;
            currentThoughts = thoughts;
            renderFeed();
        } catch (err) {
            console.error("Failed to load feed:", err);
        }
    }

    function renderGraph(data, threshold) {
        const linkedIds = new Set();
        data.edges.forEach(edge => {
            linkedIds.add(edge.from);
            linkedIds.add(edge.to);
        });
        const sourceNodes = isolateToggle.checked
            ? data.nodes
            : data.nodes.filter(node => linkedIds.has(node.id));
        const visibleIds = new Set(sourceNodes.map(node => node.id));
        const nodes = sourceNodes.map(node => ({ ...node }));
        const edges = data.edges
            .filter(edge => visibleIds.has(edge.from) && visibleIds.has(edge.to))
            .map(edge => ({ ...edge }));
        const timestamps = nodes
            .map(node => Date.parse(node.timestamp))
            .filter(timestamp => !Number.isNaN(timestamp));
        const oldest = Math.min(...timestamps);
        const newest = Math.max(...timestamps);
        const degrees = Object.fromEntries(nodes.map(node => [node.id, 0]));

        edges.forEach(edge => {
            degrees[edge.from] = (degrees[edge.from] || 0) + 1;
            degrees[edge.to] = (degrees[edge.to] || 0) + 1;
            edge.width = 0.75 + Math.max(0, edge.value - Number(threshold)) * 8;
        });
        nodes.forEach(node => {
            node.short_label = [node.person_id, node.evidence_id]
                .filter(Boolean)
                .join(' · ');
            node.label = '';
            node.size = 8 + Math.min(degrees[node.id] || 0, 5) * 1.4;
            if (node.claim_type === 'FACT') {
                node.shape = 'dot';
                node.color = {
                    background: '#168a82',
                    border: '#9cf4e8',
                    highlight: { background: '#20a89e', border: '#ffffff' },
                    hover: { background: '#20a89e', border: '#ffffff' }
                };
                return;
            }
            if (node.claim_type === 'INFERENCE') {
                node.shape = 'diamond';
                node.color = {
                    background: '#b66a19',
                    border: '#ffd18a',
                    highlight: { background: '#d18128', border: '#ffffff' },
                    hover: { background: '#d18128', border: '#ffffff' }
                };
                return;
            }
            const timestamp = Date.parse(node.timestamp);
            const age = Number.isNaN(timestamp) || newest === oldest
                ? 0
                : (timestamp - oldest) / (newest - oldest);
            const red = Math.round(35 + age * 44);
            const green = Math.round(93 + age * 100);
            const blue = Math.round(130 + age * 100);
            node.color = {
                background: `rgb(${red}, ${green}, ${blue})`,
                border: '#d6f3ff',
                highlight: { background: '#4fc1ff', border: '#ffffff' },
                hover: { background: '#4fc1ff', border: '#ffffff' }
            };
        });

        graphCount.textContent = isolateToggle.checked
            ? `${nodes.length} claims shown`
            : `${nodes.length} linked claims`;
        graphEdgeCount.textContent = `${edges.length} semantic links`;
        graphEmpty.classList.toggle('hidden', edges.length > 0);

        nodesData.clear();
        edgesData.clear();
        network.setOptions({ physics: { enabled: true } });
        nodesData.add(nodes);
        edgesData.add(edges);
        physicsFreezeTimer = setTimeout(freezeGraphLayout, 1800);
        network.startSimulation();
    }

    async function loadGraph(threshold, maxNeighbors) {
        try {
            const data = await fetchJson(
                `/api/graph?threshold=${encodeURIComponent(threshold)}` +
                `&max_neighbors=${encodeURIComponent(maxNeighbors)}${entityParam()}`
            );
            if (!Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
                throw new Error('/api/graph returned an invalid payload');
            }

            const nextSignature = JSON.stringify([
                Number(threshold),
                Number(maxNeighbors),
                data
            ]);
            if (nextSignature === graphSignature) {
                return;
            }

            graphSignature = nextSignature;
            latestGraphData = data;
            renderGraph(data, threshold);
        } catch (err) {
            console.error("Failed to load graph:", err);
        }
    }

    function refreshDashboard() {
        if (refreshPromise) {
            return refreshPromise;
        }

        refreshPromise = loadEntities()
            .then(() => Promise.all([
                loadFeed(),
                loadGraph(thresholdSlider.value, neighborSlider.value)
            ]))
            .finally(() => {
                refreshPromise = null;
            });
        return refreshPromise;
    }

    async function refreshWhenChanged() {
        try {
            const data = await fetchJson('/api/entities');
            if (!Array.isArray(data.entities)) return;
            const selected = data.entities.find(item => (
                entitySelect.value ? item.entity === entitySelect.value : item.default
            ));
            const nextCount = selected ? selected.count : null;
            if (nextCount === selectedEntityCount) return;

            selectedEntityCount = nextCount;
            entitySignature = null;
            feedSignature = null;
            graphSignature = null;
            await refreshDashboard();
        } catch (err) {
            console.error("Failed to check for corpus changes:", err);
        }
    }

    entitySelect.addEventListener('change', () => {
        localStorage.setItem('selectedEntity', entitySelect.value);
        entitySignature = null;
        feedSignature = null;
        graphSignature = null;
        feedSearch.value = '';
        hideDetails();
        refreshDashboard();
    });

    isolateToggle.addEventListener('change', () => {
        if (latestGraphData) renderGraph(latestGraphData, thresholdSlider.value);
    });
    feedSearch.addEventListener('input', renderFeed);
    refreshButton.addEventListener('click', refreshDashboard);
    window.addEventListener('focus', refreshWhenChanged);

    refreshDashboard();
    setInterval(refreshWhenChanged, REFRESH_INTERVAL_MS);
});