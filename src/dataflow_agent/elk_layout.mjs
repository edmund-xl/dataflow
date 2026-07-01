import fs from "fs";
import ELK from "elkjs/lib/elk.bundled.js";

const input = fs.readFileSync(0, "utf8");
const payload = JSON.parse(input);
const nodeWidth = payload.nodeWidth || 230;
const nodeHeight = payload.nodeHeight || 94;

const elk = new ELK();
const graph = {
  id: "dataflow",
  layoutOptions: {
    "elk.algorithm": "layered",
    "elk.direction": "RIGHT",
    "elk.edgeRouting": "ORTHOGONAL",
    "elk.spacing.nodeNode": "150",
    "elk.spacing.edgeNode": "80",
    "elk.spacing.edgeEdge": "70",
    "elk.layered.spacing.nodeNodeBetweenLayers": "360",
    "elk.layered.spacing.edgeNodeBetweenLayers": "95",
    "elk.layered.spacing.edgeEdgeBetweenLayers": "82",
    "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
    "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    "elk.layered.layering.strategy": "NETWORK_SIMPLEX",
    "elk.padding": "[top=80,left=80,bottom=80,right=80]",
  },
  children: payload.nodes.map((node) => ({
    id: node.id,
    width: nodeWidth,
    height: nodeHeight,
    labels: [{ text: node.label || node.id }],
  })),
  edges: payload.edges.map((edge, index) => ({
    id: edge.id,
    sources: [edge.source],
    targets: [edge.target],
    labels: [{ text: `E${index + 1}` }],
  })),
};

try {
  const layout = await elk.layout(graph);
  const result = {
    width: layout.width || 0,
    height: layout.height || 0,
    positions: {},
    routes: {},
  };
  for (const node of layout.children || []) {
    result.positions[node.id] = { x: node.x || 0, y: node.y || 0 };
  }
  for (const edge of layout.edges || []) {
    const section = edge.sections && edge.sections[0];
    if (!section) continue;
    result.routes[edge.id] = [
      section.startPoint,
      ...(section.bendPoints || []),
      section.endPoint,
    ].map((point) => ({ x: point.x || 0, y: point.y || 0 }));
  }
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  process.stderr.write(error && error.stack ? error.stack : String(error));
  process.exit(1);
}
