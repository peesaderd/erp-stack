#!/usr/bin/env node
const fs = require('fs');
const graphPath = process.argv[2];
const outputPath = process.argv[3];
try {
  const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
  const issues = [], warnings = [];
  if (!Array.isArray(graph.nodes)) { issues.push('graph.nodes is missing'); graph.nodes = []; }
  if (!Array.isArray(graph.edges)) { issues.push('graph.edges is missing'); graph.edges = []; }
  const nodeIds = new Set(), seen = new Map();
  graph.nodes.forEach((n, i) => {
    if (!n.id) { issues.push(`Node[${i}] missing id`); return; }
    if (!n.type) issues.push(`Node[${i}] '${n.id}' missing type`);
    if (!n.name) issues.push(`Node[${i}] '${n.id}' missing name`);
    if (!n.filePath) issues.push(`Node[${i}] '${n.id}' missing filePath`);
    if (!n.summary) issues.push(`Node[${i}] '${n.id}' missing summary`);
    if (!n.tags || !n.tags.length) issues.push(`Node[${i}] '${n.id}' missing tags`);
    if (seen.has(n.id)) issues.push(`Duplicate node '${n.id}' at ${seen.get(n.id)} and ${i}`);
    else seen.set(n.id, i);
    nodeIds.add(n.id);
  });
  graph.edges.forEach((e, i) => {
    if (!e.source || !e.target) issues.push(`Edge[${i}] missing source/target`);
    else {
      if (!nodeIds.has(e.source)) issues.push(`Edge[${i}] source '${e.source}' not found`);
      if (!nodeIds.has(e.target)) issues.push(`Edge[${i}] target '${e.target}' not found`);
    }
  });
  // Validate layers
  if (!Array.isArray(graph.layers)) { if (graph.layers) warnings.push('layers not array'); graph.layers = []; }
  if (!Array.isArray(graph.tour)) { if (graph.tour) warnings.push('tour not array'); graph.tour = []; }
  const assigned = new Map();
  graph.layers.forEach(layer => {
    if (!layer.id) issues.push('Layer missing id');
    if (!layer.name) issues.push('Layer missing name');
    (layer.nodeIds || []).forEach(id => {
      if (!nodeIds.has(id)) issues.push(`Layer '${layer.id}' refs missing node '${id}'`);
      else if (assigned.has(id)) issues.push(`Node '${id}' in multiple layers`);
      else assigned.set(id, layer.id);
    });
  });
  graph.tour.forEach((step, i) => {
    if (!step.title) issues.push(`Tour[${i}] missing title`);
    (step.nodeIds || []).forEach(id => {
      if (!nodeIds.has(id)) issues.push(`Tour[${i}] refs missing node '${id}'`);
    });
  });
  const stats = {
    totalNodes: graph.nodes.length,
    totalEdges: graph.edges.length,
    totalLayers: graph.layers.length,
    tourSteps: graph.tour.length,
    nodeTypes: graph.nodes.reduce((a,n)=>{a[n.type]=(a[n.type]||0)+1; return a;},{}),
    edgeTypes: graph.edges.reduce((a,e)=>{a[e.type]=(a[e.type]||0)+1; return a;},{})
  };
  fs.writeFileSync(outputPath, JSON.stringify({issues,warnings,stats},null,2));
  process.exit(0);
} catch(err) { process.stderr.write(err.message+'\n'); process.exit(1); }
