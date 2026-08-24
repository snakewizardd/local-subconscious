document.addEventListener('DOMContentLoaded', () => {
    let network = null;
    let nodesData = new vis.DataSet();
    let edgesData = new vis.DataSet();
    
    const container = document.getElementById('network-graph');
    const thresholdSlider = document.getElementById('threshold-slider');
    const thresholdVal = document.getElementById('threshold-val');
    const refreshButton = document.getElementById('refresh-button');
    const feedContainer = document.getElementById('feed');
    
    const detailsPanel = document.getElementById('thought-details');
    const selectedText = document.getElementById('selected-text');
    const closeDetailsBtn = document.getElementById('close-details');
    const entitySelect = document.getElementById('entity-select');
    const REFRESH_INTERVAL_MS = 3000;
    let feedSignature = null;
    let graphSignature = null;
    let refreshPromise = null;
    let entitySignature = null;

    function entityParam() {
        const value = entitySelect.value;
        return value ? `&entity=${encodeURIComponent(value)}` : '';
    }
    
    // Vis.js Options (Dark Theme, smooth physics)
    const options = {
        nodes: {
            shape: 'dot',
            size: 16,
            font: {
                size: 14,
                color: '#e0e0e0',
                face: 'Segoe UI'
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
            shadow: true
        },
        edges: {
            width: 1.5,
            color: {
                color: 'rgba(79, 193, 255, 0.3)',
                highlight: 'rgba(79, 193, 255, 0.8)',
                hover: 'rgba(79, 193, 255, 0.5)'
            },
            smooth: {
                type: 'continuous'
            }
        },
        physics: {
            barnesHut: {
                gravitationalConstant: -2000,
                centralGravity: 0.1,
                springLength: 150,
                springConstant: 0.04,
                damping: 0.09
            },
            stabilization: {
                iterations: 150
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

    // Event listener for node selection
    network.on("selectNode", function (params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const node = nodesData.get(nodeId);
            showDetails(nodeId, node.full_text);
        }
    });

    network.on("deselectNode", function () {
        hideDetails();
    });

    closeDetailsBtn.addEventListener('click', () => {
        network.unselectAll();
        hideDetails();
    });

    // Update threshold live
    thresholdSlider.addEventListener('input', (e) => {
        thresholdVal.textContent = e.target.value;
    });

    thresholdSlider.addEventListener('change', (e) => {
        loadGraph(e.target.value);
    });

    function showDetails(id, text) {
        selectedText.textContent = text;
        detailsPanel.classList.remove('hidden');
        
        // Highlight in feed
        document.querySelectorAll('.thought-card').forEach(card => {
            if (card.dataset.id === id) {
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

            const current = entitySelect.value;
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
        } catch (err) {
            console.error("Failed to load entities:", err);
        }
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
            feedContainer.innerHTML = '';
            
            thoughts.forEach(thought => {
                const div = document.createElement('div');
                div.className = 'thought-card';
                div.dataset.id = thought.id;
                const text = document.createElement('p');
                text.textContent = thought.text;
                div.appendChild(text);
                
                div.addEventListener('click', () => {
                    network.selectNodes([thought.id]);
                    network.focus(thought.id, {
                        scale: 1.2,
                        animation: { duration: 500, easingFunction: "easeInOutQuad" }
                    });
                    showDetails(thought.id, thought.text);
                });
                
                feedContainer.appendChild(div);
            });
        } catch (err) {
            console.error("Failed to load feed:", err);
        }
    }

    async function loadGraph(threshold) {
        try {
            const data = await fetchJson(`/api/graph?threshold=${encodeURIComponent(threshold)}${entityParam()}`);
            if (!Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
                throw new Error('/api/graph returned an invalid payload');
            }

            const nextSignature = JSON.stringify(data);
            if (nextSignature === graphSignature) {
                return;
            }

            graphSignature = nextSignature;

            const timestamps = data.nodes
                .map(node => Date.parse(node.timestamp))
                .filter(timestamp => !Number.isNaN(timestamp));
            const oldest = Math.min(...timestamps);
            const newest = Math.max(...timestamps);
            data.nodes.forEach(node => {
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
            
            nodesData.clear();
            edgesData.clear();
            
            nodesData.add(data.nodes);
            edgesData.add(data.edges);
        } catch (err) {
            console.error("Failed to load graph:", err);
        }
    }

    function refreshDashboard() {
        if (refreshPromise) {
            return refreshPromise;
        }

        refreshPromise = Promise.all([
            loadEntities(),
            loadFeed(),
            loadGraph(thresholdSlider.value)
        ]).finally(() => {
            refreshPromise = null;
        });
        return refreshPromise;
    }

    entitySelect.addEventListener('change', () => {
        feedSignature = null;
        graphSignature = null;
        hideDetails();
        refreshDashboard();
    });

    refreshButton.addEventListener('click', refreshDashboard);
    window.addEventListener('focus', refreshDashboard);

    // Initial load and auto-refresh while the page stays open.
    refreshDashboard();
    setInterval(refreshDashboard, REFRESH_INTERVAL_MS);
});