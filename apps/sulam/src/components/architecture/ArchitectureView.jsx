/* ─────────────────────────────────────────────────────────────────────────────
   Tab B — "How It Works"
   Pure-SVG architecture diagram with new safety agents added.
───────────────────────────────────────────────────────────────────────────── */

import { User, Brain, Database, Shield, GitBranch, FileText, AlertTriangle, TrendingUp } from 'lucide-react';

const W = 1200;
const H = 600;

/* Arrowhead marker */
function Defs() {
  return (
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="rgba(47,95,208,0.8)" />
      </marker>
      <marker id="arrow-faint" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="rgba(139,134,168,0.6)" />
      </marker>
      <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="rgba(192,67,63,0.8)" />
      </marker>
      <filter id="glow-blue" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="6" result="blur" />
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
  );
}

/* Animated dashed connector with optional arrowhead */
function Arrow({ d, faint, delay = 0, color = 'blue' }) {
  const stroke = faint ? 'rgba(139,134,168,0.55)' :
                 color === 'red' ? 'rgba(192,67,63,0.85)' :
                 'rgba(47,95,208,0.85)';
  const bgStroke = faint ? 'rgba(139,134,168,0.18)' :
                   color === 'red' ? 'rgba(192,67,63,0.15)' :
                   'rgba(47,95,208,0.15)';
  const marker = faint ? 'url(#arrow-faint)' :
                 color === 'red' ? 'url(#arrow-red)' :
                 'url(#arrow)';

  return (
    <g>
      <path d={d} fill="none" stroke={bgStroke} strokeWidth="2.5" />
      <path
        d={d} fill="none" stroke={stroke} strokeWidth="2.5"
        strokeDasharray="7 5" strokeLinecap="round"
        markerEnd={marker}
        style={{ animation: `dashFlow 1.6s linear infinite`, animationDelay: `${delay}s` }}
      />
    </g>
  );
}

/* Glassmorphism node */
function Node({ cx, cy, w, h, title, sub, Icon, highlight, tag }) {
  const x = cx - w / 2;
  const y = cy - h / 2;
  const fill   = highlight ? 'rgba(47,95,208,0.22)'  : 'rgba(255,255,255,0.62)';
  const stroke = highlight ? 'rgba(47,95,208,0.65)'  : 'rgba(255,255,255,0.75)';
  const sw     = highlight ? 2 : 1.5;

  return (
    <g filter={highlight ? 'url(#glow-blue)' : undefined}>
      {/* frosted backing */}
      <rect x={x} y={y} width={w} height={h} rx={12} fill={fill} stroke={stroke} strokeWidth={sw} />

      {/* agent glow ring */}
      {highlight && (
        <rect x={x-3} y={y-3} width={w+6} height={h+6} rx={15}
          fill="none" stroke="rgba(47,95,208,0.25)" strokeWidth={3}
          strokeDasharray="4 4"
          style={{ animation: 'spinRing 12s linear infinite', transformOrigin: `${cx}px ${cy}px` }}
        />
      )}

      {/* icon */}
      <foreignObject x={cx - 10} y={cy - (sub ? 20 : 12)} width={20} height={20}>
        <Icon size={20} color={highlight ? '#c8d8ff' : '#161a23'} strokeWidth={1.5} />
      </foreignObject>

      {/* title */}
      <text x={cx} y={cy + (sub ? 6 : 12)} textAnchor="middle" dominantBaseline="middle"
        fontFamily="var(--font-mono)" fontSize={highlight ? 12 : 11} fontWeight="700"
        letterSpacing="0.04em" fill={highlight ? '#c8d8ff' : '#161a23'} textTransform="uppercase">
        {title}
      </text>

      {/* subtitle */}
      {sub && (
        <text x={cx} y={cy + 22} textAnchor="middle" dominantBaseline="middle"
          fontFamily="var(--font-mono)" fontSize={9} fill={highlight ? 'rgba(200,216,255,0.7)' : '#5b6273'}>
          {sub}
        </text>
      )}

      {/* badge above highlight node */}
      {tag && (
        <>
          <rect x={cx - 38} y={y - 16} width={76} height={18} rx={9}
            fill="rgba(47,95,208,0.9)" />
          <text x={cx} y={y - 7} textAnchor="middle" dominantBaseline="middle"
            fontFamily="var(--font-mono)" fontSize={9} fill="#fff" fontWeight="600" letterSpacing="0.08em">
            {tag}
          </text>
        </>
      )}
    </g>
  );
}

/* Safety agent node (red highlight) */
function SafetyNode({ cx, cy, w, h, title, sub, Icon }) {
  const x = cx - w / 2;
  const y = cy - h / 2;
  const fill   = 'rgba(192,67,63,0.15)';
  const stroke = 'rgba(192,67,63,0.65)';

  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={12} fill={fill} stroke={stroke} strokeWidth={2} />

      {/* icon */}
      <foreignObject x={cx - 10} y={cy - 20} width={20} height={20}>
        <Icon size={20} color="#c0433f" strokeWidth={1.5} />
      </foreignObject>

      {/* title */}
      <text x={cx} y={cy + 6} textAnchor="middle" dominantBaseline="middle"
        fontFamily="var(--font-mono)" fontSize={11} fontWeight="700"
        letterSpacing="0.04em" fill="#c0433f" textTransform="uppercase">
        {title}
      </text>

      {/* subtitle */}
      {sub && (
        <text x={cx} y={cy + 22} textAnchor="middle" dominantBaseline="middle"
          fontFamily="var(--font-mono)" fontSize={9} fill="#a03935">
          {sub}
        </text>
      )}
    </g>
  );
}

/* Pill label on a connector midpoint */
function EdgeLabel({ x, y, label }) {
  const pw = label.length * 5.5 + 12;
  return (
    <g>
      <rect x={x - pw / 2} y={y - 9} width={pw} height={16} rx={8}
        fill="#1b2436" opacity={0.72} />
      <text x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle"
        fontFamily="var(--font-mono)" fontSize={9} fill="rgba(200,216,255,0.9)" letterSpacing="0.05em">
        {label}
      </text>
    </g>
  );
}

/* Key insight card below the diagram */
function InsightCard({ number, title, body, color }) {
  return (
    <div style={{
      flex: 1, minWidth: 200,
      background: 'var(--surface)',
      border: `1px solid ${color}33`,
      borderTop: `3px solid ${color}`,
      borderRadius: 'var(--r-md)',
      padding: '16px 18px',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
        color, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6,
      }}>
        {number}
      </div>
      <div style={{
        fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700,
        color: 'var(--ink)', marginBottom: 6,
      }}>
        {title}
      </div>
      <div style={{ fontSize: 13, color: 'var(--ink-soft)', lineHeight: 1.55 }}>
        {body}
      </div>
    </div>
  );
}

export default function ArchitectureView() {
  /* ── node centres ── */
  const patient  = { cx: 100,  cy: 300 };
  const agent    = { cx: 280,  cy: 300 };
  const vectorDb = { cx: 500,  cy: 150 };
  const kgDb     = { cx: 500,  cy: 450 };
  const pipeline = { cx: 750,  cy: 300 };
  const safetyCritic = { cx: 950, cy: 200 };
  const graphNav = { cx: 950, cy: 400 };
  const output   = { cx: 1100, cy: 300 };

  /* ── connector paths ── */
  const arrows = [
    // patient → agent
    { d: `M${patient.cx+60},${patient.cy} L${agent.cx-80},${agent.cy}`, delay: 0 },
    // agent → vector DB
    { d: `M${agent.cx+50},${agent.cy-20} Q${agent.cx+130},${vectorDb.cy} ${vectorDb.cx-80},${vectorDb.cy}`, delay: 0.3 },
    // agent → KG DB
    { d: `M${agent.cx+50},${agent.cy+20} Q${agent.cx+130},${kgDb.cy} ${kgDb.cx-80},${kgDb.cy}`, delay: 0.6 },
    // vector DB → pipeline (return)
    { d: `M${vectorDb.cx+75},${vectorDb.cy} Q${vectorDb.cx+130},${pipeline.cy-50} ${pipeline.cx-95},${pipeline.cy-40}`, faint: true, delay: 0.9 },
    // KG DB → pipeline (return)
    { d: `M${kgDb.cx+75},${kgDb.cy} Q${kgDb.cx+130},${pipeline.cy+50} ${pipeline.cx-95},${pipeline.cy+40}`, faint: true, delay: 1.1 },
    // agent → pipeline (main)
    { d: `M${agent.cx+80},${agent.cy} L${pipeline.cx-100},${pipeline.cy}`, delay: 1.4 },
    // pipeline → safety critic
    { d: `M${pipeline.cx+100},${pipeline.cy-40} L${safetyCritic.cx-70},${safetyCritic.cy}`, delay: 1.7, color: 'red' },
    // pipeline → graph navigator
    { d: `M${pipeline.cx+100},${pipeline.cy+40} L${graphNav.cx-70},${graphNav.cy}`, delay: 1.7, color: 'red' },
    // safety critic → output
    { d: `M${safetyCritic.cx+70},${safetyCritic.cy} Q${safetyCritic.cx+50},${output.cy} ${output.cx-65},${output.cy}`, delay: 2.0, color: 'red' },
    // graph navigator → output
    { d: `M${graphNav.cx+70},${graphNav.cy} Q${graphNav.cx+50},${output.cy} ${output.cx-65},${output.cy}`, delay: 2.0, color: 'red' },
  ];

  const edgeLabels = [
    { x: (patient.cx+60 + agent.cx-80)/2, y: patient.cy - 13, label: 'patient case' },
    { x: agent.cx+100, y: vectorDb.cy - 14, label: 'embed query' },
    { x: agent.cx+100, y: kgDb.cy + 14,    label: 'ICD lookup' },
    { x: vectorDb.cx+110, y: (vectorDb.cy + pipeline.cy-40)/2, label: 'chunks' },
    { x: kgDb.cx+110,    y: (kgDb.cy + pipeline.cy+40)/2,    label: 'relations' },
    { x: (agent.cx+80 + pipeline.cx-100)/2, y: agent.cy - 13, label: 'orchestrate' },
    { x: (pipeline.cx+100 + safetyCritic.cx-70)/2, y: safetyCritic.cy - 15, label: 'plan' },
    { x: (pipeline.cx+100 + graphNav.cx-70)/2, y: graphNav.cy + 15, label: 'evidence' },
  ];

  const stages = ['DDx', 'CPG\nRouting', 'Evidence\nRetrieval', 'Plan\nSynthesis', 'Safety\nReview'];

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 className="display-heading" style={{ fontSize: 30, marginBottom: 6 }}>How It Works</h1>
        <p style={{ color: 'var(--ink-soft)', fontSize: 15, maxWidth: 700 }}>
          Our system is more than a chatbot — it's an AI <strong>agent</strong> that decides what to look up,
          searches multiple databases, and grounds every answer in real clinical guidelines. Safety agents run in parallel to verify recommendations.
        </p>
      </div>

      {/* Diagram */}
      <div style={{
        background: 'linear-gradient(135deg, #0f1520 0%, #1b2436 60%, #22304d 100%)',
        borderRadius: 'var(--r-lg)',
        padding: '24px 16px',
        overflow: 'hidden',
        position: 'relative',
        boxShadow: 'var(--shadow-lg)',
      }}>
        {/* dot-grid background */}
        <div style={{
          position: 'absolute', inset: 0, opacity: 0.06,
          backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }} />

        <svg
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: '100%', display: 'block', overflow: 'visible' }}
        >
          <Defs />

          {/* connectors (behind nodes) */}
          {arrows.map((a, i) => <Arrow key={i} {...a} />)}
          {edgeLabels.map((l, i) => <EdgeLabel key={i} {...l} />)}

          {/* ── Nodes ── */}
          <Node {...patient}  w={130} h={80} title="Patient Case"    sub="chief complaint · vitals" Icon={User} />

          {/* Agent — the star */}
          <Node {...agent} w={150} h={105} title="AI Orchestrator"
            sub="decides · routes · retrieves · synthesises"
            Icon={Brain}
            highlight tag="⚡ The Agent" />

          <Node {...vectorDb} w={155} h={78} title="Vector DB"       sub="guideline chunks · embeddings" Icon={Database} />
          <Node {...kgDb}     w={155} h={78} title="Knowledge Graph" sub="ICD-11 ↔ CPG ↔ Drug relations" Icon={GitBranch} />

          {/* Pipeline — tall card with stage pills */}
          <g>
            <rect x={pipeline.cx-100} y={pipeline.cy-160} width={200} height={320} rx={12}
              fill="rgba(255,255,255,0.58)" stroke="rgba(255,255,255,0.70)" strokeWidth={1.5} />
            <text x={pipeline.cx} y={pipeline.cy-138} textAnchor="middle"
              fontFamily="var(--font-mono)" fontSize={10} fill="#5b6273" fontWeight={700} letterSpacing="0.08em">
              5-STAGE PIPELINE
            </text>
            {stages.map((s, i) => {
              const py = pipeline.cy - 105 + i * 58;
              const lines = s.split('\n');
              return (
                <g key={i}>
                  <rect x={pipeline.cx-68} y={py-18} width={136} height={36} rx={8}
                    fill="rgba(47,95,208,0.14)" stroke="rgba(47,95,208,0.30)" strokeWidth={1}
                    style={{ animation: `fadeIn 0.4s ease both`, animationDelay: `${i * 0.12}s` }}
                  />
                  <text x={pipeline.cx-50} y={py + (lines.length > 1 ? -3 : 1)} textAnchor="middle"
                    fontFamily="var(--font-mono)" fontSize={10} fill="rgba(200,216,255,0.9)" fontWeight={600}>
                    {i + 1}.
                  </text>
                  {lines.map((l, li) => (
                    <text key={li} x={pipeline.cx+8} y={py + (lines.length > 1 ? li * 13 - 5 : 1)}
                      textAnchor="middle" fontFamily="var(--font-mono)" fontSize={10}
                      fill="rgba(200,216,255,0.9)" fontWeight={600}>
                      {l}
                    </text>
                  ))}
                </g>
              );
            })}
          </g>

          {/* Safety agents (red) */}
          <SafetyNode {...safetyCritic} w={140} h={90} title="Safety Critic" sub="pharmacovigilance" Icon={Shield} />
          <SafetyNode {...graphNav} w={140} h={90} title="Graph Navigator" sub="multi-morbidity" Icon={TrendingUp} />

          <Node {...output} w={130} h={80} title="Cited Care Plan" sub="every rec cites a CPG" Icon={FileText} />
        </svg>

        <style>{`
          @keyframes dashFlow { from { stroke-dashoffset: 24; } to { stroke-dashoffset: 0; } }
          @keyframes spinRing { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
          @keyframes fadeIn   { from { opacity: 0; } to { opacity: 1; } }
        `}</style>
      </div>

      {/* Key insight cards */}
      <div style={{ display: 'flex', gap: 14, marginTop: 20, flexWrap: 'wrap' }}>
        <InsightCard
          number="01 — The Agent"
          title="It decides, not just responds"
          body="Unlike a chatbot, the agent actively chooses which guidelines to retrieve based on its own diagnosis — that's the 'agentic' part."
          color="var(--primary)"
        />
        <InsightCard
          number="02 — Parallel Safety"
          title="Independent verification"
          body="Safety Critic checks for drug interactions & allergies. Graph Navigator evaluates multi-morbidity constraints. Both run while the pipeline synthesizes."
          color="var(--err)"
        />
        <InsightCard
          number="03 — Cited Answers"
          title="Every claim is traceable"
          body="Each recommendation in the care plan is tagged with its CPG source. You can always see why the AI said what it said."
          color="#2a9d6c"
        />
      </div>
    </div>
  );
}
