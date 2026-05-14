/* ─────────────────────────────────────────────────────────────────────────────
   Tab C — Knowledge Graph
   Force-directed graph on a dark canvas. Nodes are bigger, labels readable,
   edges have animated dashes. Hover shows a detail panel.
───────────────────────────────────────────────────────────────────────────── */
import { useEffect, useRef, useState } from 'react';
import { GRAPH_NODES, GRAPH_EDGES, NODE_COLORS } from '../../data/mockGraph.js';

const R      = 28;   // node radius
const W      = 1000;
const H      = 540;

const EDGE_COLORS = {
  treats:        '#2a9d6c',
  indicated_for: '#2f5fd0',
  coded_in:      '#8b86a8',
  presents_with: '#b4843a',
};

const TYPE_LABELS  = { cpg: 'CPG Guideline', icd: 'ICD-11 Code', drug: 'Drug', symptom: 'Symptom' };
const TYPE_ICONS   = { cpg: '📖', icd: '🔖', drug: '💊', symptom: '🩺' };

/* ── Force layout ──────────────────────────────────────────── */
function useForceLayout(nodes, edges) {
  const posRef   = useRef({});
  const velRef   = useRef({});
  const frameRef = useRef(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    // seed positions in a loose ellipse
    nodes.forEach((n, i) => {
      const angle = (i / nodes.length) * 2 * Math.PI;
      posRef.current[n.id] = {
        x: W / 2 + 200 * Math.cos(angle),
        y: H / 2 + 160 * Math.sin(angle),
      };
      velRef.current[n.id] = { x: (Math.random() - 0.5) * 2, y: (Math.random() - 0.5) * 2 };
    });

    let alpha = 1;

    const step = () => {
      if (alpha < 0.004) return;
      alpha *= 0.978;
      const pos = posRef.current;
      const vel = velRef.current;

      // repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i].id, b = nodes[j].id;
          const dx = pos[b].x - pos[a].x;
          const dy = pos[b].y - pos[a].y;
          const dist = Math.max(Math.sqrt(dx*dx + dy*dy), 1);
          const f = (4200 / (dist * dist)) * alpha;
          vel[a].x -= (dx/dist)*f;  vel[a].y -= (dy/dist)*f;
          vel[b].x += (dx/dist)*f;  vel[b].y += (dy/dist)*f;
        }
      }

      // spring attraction on edges
      edges.forEach(e => {
        const a = pos[e.source], b = pos[e.target];
        if (!a || !b) return;
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.max(Math.sqrt(dx*dx + dy*dy), 1);
        const ideal = 160;
        const f = ((dist - ideal) / dist) * 0.055 * alpha;
        vel[e.source].x += dx*f;  vel[e.source].y += dy*f;
        vel[e.target].x -= dx*f;  vel[e.target].y -= dy*f;
      });

      // gravity
      nodes.forEach(n => {
        vel[n.id].x += (W/2 - pos[n.id].x) * 0.007 * alpha;
        vel[n.id].y += (H/2 - pos[n.id].y) * 0.007 * alpha;
      });

      // integrate
      nodes.forEach(n => {
        vel[n.id].x *= 0.80;
        vel[n.id].y *= 0.80;
        pos[n.id].x = Math.max(R+8, Math.min(W-R-8, pos[n.id].x + vel[n.id].x));
        pos[n.id].y = Math.max(R+8, Math.min(H-R-8, pos[n.id].y + vel[n.id].y));
      });

      setTick(t => t + 1);
      frameRef.current = requestAnimationFrame(step);
    };

    frameRef.current = requestAnimationFrame(step);
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); };
  }, []);

  return posRef.current;
}

/* ── Stagger reveal ──────────────────────────────────────────── */
function useStaggerReveal(total, ms) {
  const [visible, setVisible] = useState(0);
  useEffect(() => {
    if (visible >= total) return;
    const t = setTimeout(() => setVisible(v => v + 1), ms);
    return () => clearTimeout(t);
  }, [visible, total, ms]);
  return visible;
}

/* ── Wrap label to two lines ────────────────────────────────── */
function wrapLabel(label, maxChars = 12) {
  if (label.length <= maxChars) return [label];
  const idx = label.lastIndexOf(' ', maxChars);
  if (idx === -1) return [label.slice(0, maxChars), label.slice(maxChars)];
  return [label.slice(0, idx), label.slice(idx + 1)];
}

export default function GraphView() {
  const pos         = useForceLayout(GRAPH_NODES, GRAPH_EDGES);
  const visEdges    = useStaggerReveal(GRAPH_EDGES.length, 60);
  const visNodes    = useStaggerReveal(GRAPH_NODES.length, 120);
  const [hovered, setHovered] = useState(null);

  const hoveredNode = hovered ? GRAPH_NODES.find(n => n.id === hovered) : null;
  const hoveredEdges = hovered
    ? GRAPH_EDGES.filter(e => e.source === hovered || e.target === hovered)
    : [];
  const connectedIds = new Set(hoveredEdges.flatMap(e => [e.source, e.target]));

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1 className="display-heading" style={{ fontSize: 30, marginBottom: 6 }}>
          Knowledge Graph
        </h1>
        <p style={{ color: 'var(--ink-soft)', fontSize: 15, maxWidth: 620 }}>
          We use <strong>two</strong> databases — not just a Vector DB. The Knowledge Graph links
          diseases, drugs, guidelines, and symptoms so the AI understands relationships, not just similarity.
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10, flexWrap: 'wrap' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--primary)',
            background: 'var(--primary-soft)', padding: '4px 12px', borderRadius: 999,
          }}>
            <span style={{ animation: 'pulseGreen 1.5s ease-in-out infinite' }}>●</span>
            live-streaming from graph DB
          </div>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-soft)' }}>
            Hover a node to see its connections
          </span>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 14, flexWrap: 'wrap' }}>
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{
              width: 14, height: 14, borderRadius: '50%', background: color,
              boxShadow: `0 0 6px ${color}88`,
            }} />
            <div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink)', fontWeight: 600 }}>
                {TYPE_LABELS[type]}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-soft)', marginLeft: 5 }}>
                ({GRAPH_NODES.filter(n => n.type === type).length})
              </span>
            </div>
          </div>
        ))}

        {/* Edge type legend */}
        <div style={{ borderLeft: '1px solid var(--line)', paddingLeft: 16, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          {Object.entries(EDGE_COLORS).map(([type, color]) => (
            <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <svg width="22" height="6"><line x1="0" y1="3" x2="22" y2="3" stroke={color} strokeWidth="2" strokeDasharray="4 2"/></svg>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--ink-soft)' }}>
                {type.replace('_', ' ')}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Graph canvas + hover panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 14, alignItems: 'start' }}>
        <div style={{
          background: '#0b1120',
          border: '1px solid rgba(47,95,208,0.2)',
          borderRadius: 'var(--r-lg)',
          overflow: 'hidden',
          boxShadow: '0 0 40px rgba(47,95,208,0.08), var(--shadow-lg)',
        }}>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }}>
            <defs>
              {Object.entries(EDGE_COLORS).map(([type, color]) => (
                <marker key={type} id={`arrow-${type}`} markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L7,3 z" fill={color} opacity="0.8" />
                </marker>
              ))}
            </defs>

            {/* Edges */}
            {GRAPH_EDGES.slice(0, visEdges).map((e, i) => {
              const a = pos[e.source], b = pos[e.target];
              if (!a || !b) return null;
              const isHighlighted = hovered && connectedIds.has(e.source) && connectedIds.has(e.target);
              const isDimmed = hovered && !isHighlighted;
              const color = EDGE_COLORS[e.label] || '#5b6273';
              const mx = (a.x + b.x) / 2;
              const my = (a.y + b.y) / 2;
              const lw = label => label.length * 5.2 + 10;
              return (
                <g key={i} opacity={isDimmed ? 0.12 : isHighlighted ? 1 : 0.55}>
                  {/* base line */}
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color} strokeWidth={isDimmed ? 1 : 1.5} opacity={0.25} />
                  {/* animated dash */}
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                    stroke={color} strokeWidth={isDimmed ? 1 : isHighlighted ? 2.5 : 1.5}
                    strokeDasharray="6 5"
                    markerEnd={`url(#arrow-${e.label})`}
                    style={{ animation: `edgeDash 2s linear infinite`, animationDelay: `${i * 0.07}s` }}
                  />
                  {/* label pill */}
                  {(isHighlighted || !hovered) && (
                    <g>
                      <rect x={mx - lw(e.label)/2} y={my - 8} width={lw(e.label)} height={14} rx={7}
                        fill="#0b1120" stroke={color} strokeWidth={0.8} opacity={0.9} />
                      <text x={mx} y={my + 1} textAnchor="middle" dominantBaseline="middle"
                        fontFamily="var(--font-mono)" fontSize={8.5} fill={color} fontWeight={600} letterSpacing="0.03em">
                        {e.label.replace('_', ' ')}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* Nodes */}
            {GRAPH_NODES.slice(0, visNodes).map((n) => {
              const p = pos[n.id];
              if (!p) return null;
              const color = NODE_COLORS[n.type] || '#999';
              const isHov = hovered === n.id;
              const isConnected = connectedIds.has(n.id) && !isHov;
              const isDimmed = hovered && !isHov && !isConnected;
              const lines = wrapLabel(n.label, 11);
              const r = isHov ? R + 5 : R;

              return (
                <g key={n.id} transform={`translate(${p.x},${p.y})`}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHovered(n.id)}
                  onMouseLeave={() => setHovered(null)}>

                  {/* outer glow ring on hover */}
                  {isHov && (
                    <circle r={r + 9} fill="none" stroke={color} strokeWidth={2} opacity={0.35}
                      style={{ animation: 'pulseRing 1.5s ease-in-out infinite' }} />
                  )}
                  {isConnected && (
                    <circle r={r + 5} fill="none" stroke={color} strokeWidth={1.5} opacity={0.25} />
                  )}

                  {/* node body */}
                  <circle r={r} fill={color}
                    opacity={isDimmed ? 0.2 : 0.92}
                    style={{
                      filter: isHov ? `drop-shadow(0 0 10px ${color})` : isConnected ? `drop-shadow(0 0 5px ${color})` : 'none',
                      transition: 'r 0.15s',
                    }}
                  />

                  {/* type icon */}
                  <text y={lines.length > 1 ? -9 : -4} textAnchor="middle" dominantBaseline="middle"
                    fontSize={lines.length > 1 ? 11 : 13} opacity={isDimmed ? 0.3 : 1}>
                    {TYPE_ICONS[n.type]}
                  </text>

                  {/* label lines */}
                  {lines.map((line, li) => (
                    <text key={li}
                      y={(lines.length > 1 ? 6 : 8) + li * 11}
                      textAnchor="middle" dominantBaseline="middle"
                      fontFamily="var(--font-mono)" fontSize={lines.length > 1 ? 7.5 : 8.5}
                      fill="#fff" fontWeight={700}
                      opacity={isDimmed ? 0.3 : 1}
                      style={{ pointerEvents: 'none' }}>
                      {line}
                    </text>
                  ))}
                </g>
              );
            })}
          </svg>
        </div>

        {/* Hover detail panel */}
        <div style={{
          width: 220,
          minHeight: 200,
          background: 'var(--surface)',
          border: '1px solid var(--line)',
          borderRadius: 'var(--r-lg)',
          padding: '16px',
          boxShadow: 'var(--shadow-md)',
          transition: 'opacity 0.2s',
          opacity: hoveredNode ? 1 : 0.4,
        }}>
          {hoveredNode ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <div style={{
                  width: 12, height: 12, borderRadius: '50%',
                  background: NODE_COLORS[hoveredNode.type],
                  boxShadow: `0 0 6px ${NODE_COLORS[hoveredNode.type]}`,
                  flexShrink: 0,
                }} />
                <div className="mono-label">{TYPE_LABELS[hoveredNode.type]}</div>
              </div>
              <div style={{
                fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700,
                color: 'var(--ink)', marginBottom: 12, lineHeight: 1.3,
              }}>
                {hoveredNode.label}
              </div>

              {hoveredEdges.length > 0 && (
                <>
                  <div className="mono-label" style={{ marginBottom: 8 }}>Connections</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {hoveredEdges.map((e, i) => {
                      const otherId = e.source === hoveredNode.id ? e.target : e.source;
                      const other = GRAPH_NODES.find(n => n.id === otherId);
                      const isOut = e.source === hoveredNode.id;
                      const edgeColor = EDGE_COLORS[e.label] || '#5b6273';
                      return (
                        <div key={i} style={{
                          padding: '7px 10px',
                          background: 'var(--surface-soft)',
                          borderRadius: 'var(--r-sm)',
                          border: '1px solid var(--line)',
                        }}>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9.5,
                            color: edgeColor, fontWeight: 700, marginBottom: 2,
                            textTransform: 'uppercase', letterSpacing: '0.05em',
                          }}>
                            {isOut ? '→' : '←'} {e.label.replace('_', ' ')}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--ink)', fontWeight: 600 }}>
                            {other?.label}
                          </div>
                          <div style={{
                            fontFamily: 'var(--font-mono)', fontSize: 9,
                            color: NODE_COLORS[other?.type], marginTop: 1,
                          }}>
                            {TYPE_LABELS[other?.type]}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', paddingTop: 32 }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>👆</div>
              <div className="mono-label">Hover a node</div>
              <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 6 }}>
                to see its type and connections
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes edgeDash    { from { stroke-dashoffset: 22; } to { stroke-dashoffset: 0; } }
        @keyframes pulseGreen  { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes pulseRing   { 0%,100% { opacity: 0.35; transform: scale(1); }
                                  50% { opacity: 0.15; transform: scale(1.15); } }
      `}</style>
    </div>
  );
}
