document.addEventListener('DOMContentLoaded', () => {
    let network = null;
    let nodesData = new vis.DataSet();
    let edgesData = new vis.DataSet();
    
    const container = document.getElementById('network-graph');
    const thresholdSlider = document.getElementById('threshold-slider');
    const thresholdVal = document.getElementById('threshold-val');
    const feedContainer = document.getElementById('feed');
    
    const detailsPanel = document.getElementById('thought-details');
    const selectedText = document.getElementById('selected-text');
    const closeDetailsBtn = document.getElementById('close-details');
    
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

    async function loadFeed() {
        try {
            const res = await fetch('/api/thoughts');
            const data = await res.json();
            
            feedContainer.innerHTML = '';
            const thoughts = data.thoughts.sort((first, second) => {
                return new Date(second.timestamp || 0) - new Date(first.timestamp || 0);
            });
            
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
            const res = await fetch(`/api/graph?threshold=${threshold}`);
            const data = await res.json();

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

    // Initial load
    loadFeed();
    loadGraph(thresholdSlider.value);
});