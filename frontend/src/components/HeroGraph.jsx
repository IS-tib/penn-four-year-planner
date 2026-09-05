import { useEffect, useState } from "react";

/**
 * A real slice of the Computer Science prerequisite graph, drawn.
 *
 * The landing page claims prerequisites are a graph rather than a list, and a
 * paragraph saying so is weaker than the graph itself. Every node and edge here
 * is transcribed from the catalog: CIS 1210 really does need CIS 1200 and
 * CIS 1600 together, and CIS 3200 really does sit downstream of both.
 *
 * The edges draw themselves once on load and then carry a slow pulse, which is
 * the point being made visually: a prerequisite is something that flows.
 *
 * The entrance is a transition rather than a keyframe animation, and the state
 * it transitions to lives on a parent attribute. A keyframe animation, even
 * with fill both, restarts when the page is resized, and a full-page
 * screenshot resizes the page: the graph came out half faded in every capture.
 * A transition has no such memory. Its resting state is just the computed
 * style, so it survives anything.
 *
 * Geometry note. Every node box is 100 wide and 30 tall, so the left and right
 * attachment points are the centre plus or minus 50. Edges are written to those
 * points rather than to the centres, because an edge that ends at a centre
 * spends its last fifty pixels hidden underneath the box.
 */

const HALF = 50;

const NODES = [
  { code: "CIS 1100", x: 58, y: 210, delay: 0 },
  { code: "CIS 1600", x: 58, y: 86, delay: 0.16 },
  { code: "CIS 1200", x: 218, y: 210, delay: 0.34 },
  { code: "CIS 1210", x: 378, y: 148, delay: 0.6 },
  { code: "CIS 2400", x: 378, y: 272, delay: 0.7 },
  { code: "CIS 3200", x: 538, y: 104, delay: 0.92 },
  { code: "CIS 4710", x: 538, y: 230, delay: 1.02 },
];

const EDGES = [
  { id: "a", d: "M 108 210 L 168 210", delay: 0.28 },
  { id: "b", d: "M 108 86 C 210 86, 250 116, 328 144", delay: 0.44 },
  { id: "c", d: "M 268 204 C 300 199, 300 158, 328 151", delay: 0.52 },
  { id: "d", d: "M 268 216 C 300 224, 300 264, 328 270", delay: 0.6 },
  { id: "e", d: "M 428 143 C 458 136, 468 116, 488 107", delay: 0.78 },
  { id: "f", d: "M 428 267 C 458 260, 468 242, 488 233", delay: 0.86 },
];

// Pulses run through the boxes rather than stopping at their edges, because
// what is being shown is a chain and a chain does not pause at each link.
const PULSES = [
  {
    path: "M 108 210 L 218 210 C 300 202, 300 156, 378 148 C 450 140, 470 118, 538 104",
    dur: 4.2,
    begin: 1.5,
  },
  { path: "M 108 86 C 220 86, 280 116, 378 148 C 450 140, 470 118, 538 104", dur: 4.2, begin: 3.1 },
  { path: "M 218 210 C 300 218, 320 264, 378 272 C 450 264, 470 244, 538 230", dur: 3.6, begin: 4.4 },
];

export function HeroGraph() {
  // SMIL is not covered by the reduced-motion rule in the stylesheet, which
  // only reaches CSS animations, so the pulses are gated here instead.
  const [animate, setAnimate] = useState(true);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setAnimate(!query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  return (
    <svg
      className="hero-graph"
      viewBox="0 0 600 340"
      role="img"
      aria-label="Part of the Computer Science prerequisite graph: CIS 1100 leads to CIS 1200, which with CIS 1600 leads to CIS 1210 and CIS 2400, which lead to CIS 3200 and CIS 4710"
    >
      <defs>
        {/* userSpaceOnUse, not the default objectBoundingBox. A horizontal
            straight edge has a zero-height bounding box, and a gradient
            measured against that degenerates: CIS 1100 to CIS 1200 simply did
            not render. Measuring in the viewBox also means the fade runs left
            to right across the whole graph rather than restarting per edge. */}
        <linearGradient id="edge-fade" gradientUnits="userSpaceOnUse" x1="60" y1="0" x2="540" y2="0">
          <stop offset="0%" stopColor="#8fb0ef" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#cfe0ff" stopOpacity="0.95" />
        </linearGradient>
      </defs>

      {EDGES.map((edge) => (
        <path
          key={edge.id}
          className="hero-edge"
          d={edge.d}
          style={{ transitionDelay: `${edge.delay}s` }}
        />
      ))}

      {/* opacity 0 in the markup, not only in the animation: before its begin
          time a SMIL circle renders at its own cx and cy, which left a stray
          dot in the corner of the graph. */}
      {animate
        ? PULSES.map((pulse, index) => (
            <circle key={index} className="hero-pulse" r="3.4" opacity="0">
              <animateMotion
                path={pulse.path}
                dur={`${pulse.dur}s`}
                begin={`${pulse.begin}s`}
                repeatCount="indefinite"
              />
              <animate
                attributeName="opacity"
                values="0;1;1;0"
                keyTimes="0;0.1;0.82;1"
                dur={`${pulse.dur}s`}
                begin={`${pulse.begin}s`}
                repeatCount="indefinite"
              />
            </circle>
          ))
        : null}

      {NODES.map((node) => (
        <g
          key={node.code}
          className="hero-node"
          style={{ transitionDelay: `${node.delay}s`, transformOrigin: `${node.x}px ${node.y}px` }}
        >
          <rect x={node.x - HALF} y={node.y - 15} width={HALF * 2} height="30" rx="9" />
          <text x={node.x} y={node.y + 4.5} textAnchor="middle">
            {node.code}
          </text>
        </g>
      ))}
    </svg>
  );
}
