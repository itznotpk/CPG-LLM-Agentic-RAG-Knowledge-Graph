import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight, Workflow, BookOpen, FileCheck2,
  BrainCircuit, ShieldAlert, Eye, Camera, Activity,
  Heart, Stethoscope, ChevronDown, AlertTriangle, ShieldX,
  Baby, Pill, FlaskConical, Mic, Network, Send, FileText,
} from 'lucide-react';

/**
 * ClearPath marketing landing page.
 * Renders before Login (see App.jsx Gate). Calls onSignIn() to switch
 * to the existing Login screen.
 */
export default function Landing({ onSignIn }) {
  return (
    <div className="min-h-screen bg-[#fafbfc] text-slate-900 font-sans">
      <Nav onSignIn={onSignIn} />
      <Hero onSignIn={onSignIn} />
      <Stats />
      <HowItWorks />
      <Architecture />
      <Features />
      <Cases />
      <CTA onSignIn={onSignIn} />
      <Footer />
    </div>
  );
}

/* ---------- NAV ---------- */
function Nav({ onSignIn }) {
  return (
    <nav className="sticky top-0 z-50 bg-[rgba(250,251,252,0.78)] backdrop-blur-md border-b border-slate-200">
      <div className="w-full px-6 lg:px-12 py-4 flex items-center justify-between gap-8">
        <a href="#" className="flex items-center gap-3.5 min-w-0">
          <img src="/UniMalaya.png" alt="University of Malaya" className="h-9 w-auto" />
          <span className="w-px h-7 bg-slate-300" />
          <span className="font-display italic text-teal-700 text-2xl leading-none tracking-tight">
            ClearPath.
          </span>
        </a>
        <div className="hidden md:flex items-center gap-7 text-sm">
          <a href="#how" className="text-slate-600 hover:text-teal-700 transition-colors">How it works</a>
          <a href="#architecture" className="text-slate-600 hover:text-teal-700 transition-colors">Architecture</a>
          <a href="#features" className="text-slate-600 hover:text-teal-700 transition-colors">Features</a>
          <a href="#cases" className="text-slate-600 hover:text-teal-700 transition-colors">Use cases</a>
          <button
            onClick={onSignIn}
            className="px-4 py-2.5 rounded-[10px] bg-slate-900 text-white text-[13.5px] font-medium hover:bg-teal-700 transition-colors"
          >
            Sign in <span aria-hidden>→</span>
          </button>
        </div>
        <button
          onClick={onSignIn}
          className="md:hidden px-4 py-2 rounded-[10px] bg-slate-900 text-white text-sm font-medium"
        >
          Sign in
        </button>
      </div>
    </nav>
  );
}

/* ---------- HERO ---------- */
function Hero({ onSignIn }) {
  return (
    <section className="relative overflow-hidden px-8 pt-20 pb-16">
      {/* mesh background */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(circle at 18% 110%, rgba(20,184,166,0.16) 0%, transparent 55%),' +
            'radial-gradient(circle at 88% -5%, rgba(20,184,166,0.12) 0%, transparent 50%),' +
            'linear-gradient(180deg, #fafbfc 0%, #f1f5f9 100%)',
        }}
      />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(15,23,42,0.04) 1px, transparent 1px),' +
            'linear-gradient(90deg, rgba(15,23,42,0.04) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(circle at 50% 30%, #000 0%, transparent 70%)',
          WebkitMaskImage: 'radial-gradient(circle at 50% 30%, #000 0%, transparent 70%)',
        }}
      />
      {/* orbs */}
      <div className="absolute left-[-180px] bottom-[-240px] w-[520px] h-[520px] rounded-full opacity-55 pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(20,184,166,0.45), transparent 70%)', filter: 'blur(80px)' }} />
      <div className="absolute right-[-80px] top-[-120px] w-[380px] h-[380px] rounded-full opacity-60 pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(94,234,212,0.4), transparent 70%)', filter: 'blur(80px)' }} />

      <div className="relative max-w-[1280px] mx-auto grid lg:grid-cols-[1.15fr_1fr] gap-16 items-center">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          <h1 className="font-display text-[76px] leading-[1.02] tracking-[-0.02em] text-slate-900 mb-6 text-balance">
            Clinician's <em className="italic text-teal-700 not-italic-fix">second opinion</em>, at the speed of a glance.
          </h1>

          <p className="text-lg text-slate-600 max-w-[52ch] mb-9 leading-[1.6]">
            A citation-traceable second opinion for rural primary care. ClearPath reads
            vitals, history, and chief complaint, then drafts a care plan — every claim
            cited to a Malaysian MOH guideline and screened by an independent safety
            critic — inside a standard consultation.
          </p>

          <div className="flex flex-wrap gap-3">
            <button onClick={onSignIn} className="inline-flex items-center gap-2.5 px-[22px] py-[13px] rounded-xl text-[14.5px] font-semibold text-white bg-gradient-to-br from-teal-600 to-teal-700 hover:-translate-y-0.5 transition-transform shadow-[0_8px_25px_rgba(20,184,166,0.25)] hover:shadow-[0_12px_40px_rgba(20,184,166,0.32)]">
              Try the demo
              <ArrowRight className="w-4 h-4" />
            </button>
            <a href="#how" className="inline-flex items-center gap-2.5 px-[22px] py-[13px] rounded-xl text-[14.5px] font-semibold text-slate-800 bg-white/70 backdrop-blur border border-slate-200 hover:bg-white hover:border-teal-400 hover:text-teal-700 transition-colors">
              See how it works
            </a>
          </div>
        </motion.div>

        <HeroVisual />
      </div>
    </section>
  );
}

/* hero mock app card */
function HeroVisual() {
  return (
    <div className="relative aspect-[5/4]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut', delay: 0.1 }}
        className="absolute inset-0 bg-white border border-slate-200 rounded-[18px] overflow-hidden shadow-[0_40px_80px_-25px_rgba(15,23,42,0.22),0_14px_30px_-12px_rgba(15,23,42,0.1)]"
        style={{ transform: 'perspective(1200px) rotateY(-13deg) rotateX(7deg) rotateZ(-1deg)', transformOrigin: 'center right' }}
      >
        {/* window bar */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100 bg-slate-50">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
          <span className="ml-3 font-mono text-[11px] text-slate-500 tracking-wider">
            CLEARPATH · CONSULTATION 09:15
          </span>
        </div>

        <div className="p-5 grid gap-4">
          {/* patient banner */}
          <div className="grid grid-cols-[40px_1fr_auto] gap-3 items-center px-3.5 py-3 rounded-xl border border-teal-100"
            style={{ background: 'linear-gradient(135deg, #f0fdfa, #fff)' }}>
            <div className="w-10 h-10 rounded-xl bg-teal-100 text-teal-700 inline-flex items-center justify-center font-semibold text-sm">ML</div>
            <div>
              <div className="font-semibold text-sm text-slate-900">Mei Ling</div>
              <div className="font-mono text-[11px] text-slate-500 mt-0.5">670911-07-0517 · 67 F · T2DM</div>
            </div>
            <span className="bg-amber-100 text-amber-700 border border-amber-200 px-2 py-1 rounded-md text-[11px] font-semibold">Moderate</span>
          </div>

          {/* vitals */}
          <div className="grid grid-cols-4 gap-2.5">
            {[
              ['HR', '82', 'bpm'],
              ['BP', '142', '/88'],
              ['SpO₂', '97', '%'],
              ['HbA1c', '8.5', '%'],
            ].map(([l, v, u]) => (
              <div key={l} className="bg-slate-50 border border-slate-100 rounded-[10px] px-3 py-2.5">
                <div className="text-[9px] tracking-widest uppercase text-slate-500 font-semibold">{l}</div>
                <div className="font-mono text-lg font-semibold text-slate-900 mt-1">
                  {v}<span className="text-[9px] text-slate-400 ml-0.5 font-mono">{u}</span>
                </div>
              </div>
            ))}
          </div>

          {/* ddx */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="px-3.5 py-2.5 border-b border-slate-100 flex items-center gap-2.5 text-[11px] text-slate-500 tracking-wider uppercase font-semibold">
              <span className="bg-teal-600 text-white px-1.5 py-0.5 rounded text-[9px]">AI</span>
              Differentials · 3 CPGs cited
            </div>
            {[
              ['01', 'T2DM, uncontrolled', '5A11', 87, true],
              ['02', 'Hypertension stage 2', 'BA00', 71, false],
              ['03', 'Metabolic syndrome', '5A40', 64, false],
            ].map(([rk, nm, icd, pct, top]) => {
              // Canonical ClearPath probability colors (19-probability.html)
              const barFill = pct >= 70 ? '#ef4444' : pct >= 40 ? '#f59e0b' : '#22c55e';
              return (
                <div
                  key={rk}
                  className={`px-3.5 py-2.5 border-t border-slate-100 first:border-t-0 ${top ? 'border-l-[3px] !border-l-teal-600 bg-teal-50/40' : ''}`}
                >
                  {/* row 1: rank · name · icd · % */}
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="font-mono text-xs font-semibold text-teal-700 shrink-0">{rk}</span>
                    <span className="text-[13px] text-slate-900 font-medium flex-1 truncate">{nm}</span>
                    <span className="font-mono text-[10px] text-slate-500 shrink-0">ICD-11 · {icd}</span>
                    <span
                      className="font-mono text-xs shrink-0"
                      style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: '#0f172a' }}
                    >
                      {pct}%
                    </span>
                  </div>
                  {/* row 2: canonical probability bar */}
                  <div style={{ height: 6, borderRadius: 4, background: '#f1f5f9', overflow: 'hidden' }}>
                    <div style={{ height: '100%', borderRadius: 4, background: barFill, width: `${pct}%`, transition: 'width 0.7s cubic-bezier(0.4,0,0.2,1)' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </motion.div>

      {/* ECG floater */}
      <motion.div
        initial={{ opacity: 0, x: 30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="absolute -right-8 -bottom-8 w-[200px] bg-white/95 border border-teal-100 rounded-2xl px-3 py-2 shadow-[0_16px_40px_-12px_rgba(15,23,42,0.18)] z-10"
      >
        <div className="font-mono text-[9px] text-teal-700 tracking-widest">LIVE · ECG II</div>
        <svg viewBox="0 0 400 36" preserveAspectRatio="none" className="w-full h-9 mt-1 block">
          <path
            d="M 0 18 L 60 18 L 80 18 L 95 14 L 110 22 L 125 18 L 160 18 L 180 18 L 195 6 L 205 30 L 215 0 L 225 34 L 235 18 L 280 18 L 310 18 L 325 14 L 340 22 L 355 18 L 400 18"
            fill="none"
            stroke="#0d9488"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              strokeDasharray: 800,
              strokeDashoffset: 800,
              animation: 'cp-trace 4s linear infinite',
            }}
          />
        </svg>
        <div className="font-mono text-[10px] text-slate-600 mt-0.5">
          HR <b className="text-slate-900 font-semibold">72</b> bpm · SpO<sub>2</sub> <b className="text-slate-900 font-semibold">98</b>%
        </div>
        <style>{`@keyframes cp-trace { 0%{stroke-dashoffset:800} 70%{stroke-dashoffset:0} 100%{stroke-dashoffset:-800} }`}</style>
      </motion.div>
    </div>
  );
}

/* ---------- STATS ---------- */
function Stats() {
  const items = [
    { Icon: Workflow, n: '100', unit: '%', label: 'Guideline-routing accuracy (44/44, Top-1)' },
    { Icon: FileCheck2, n: '86.4', unit: '%', label: 'Care-plan claims cited to evidence (849/979)' },
    { Icon: ShieldAlert, n: '92', unit: '%', label: 'Safety-critic hazard sensitivity (100% specificity)' },
    { Icon: Stethoscope, n: '4.93', unit: '/5', label: 'Clinician clinical-safety score, blinded evaluation' },
  ];
  return (
    <section className="bg-white border-y border-slate-200">
      <div className="max-w-[1280px] mx-auto grid grid-cols-2 md:grid-cols-4 px-8">
        {items.map(({ Icon, n, unit, label }, i) => (
          <div key={i} className={`p-8 ${i > 0 ? 'md:border-l border-slate-100' : ''} flex flex-col`}>
            <span className="w-9 h-9 rounded-[10px] bg-teal-50 text-teal-700 border border-teal-100 inline-flex items-center justify-center mb-4">
              <Icon className="w-[18px] h-[18px]" strokeWidth={1.8} />
            </span>
            <div className="font-display italic text-[44px] leading-none tracking-tight text-slate-900">
              {n}<small className="text-lg text-teal-700 ml-1 italic">{unit}</small>
            </div>
            <div className="text-[12.5px] text-slate-600 mt-2 leading-snug">{label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ---------- HOW IT WORKS ---------- */
function HowItWorks() {
  const steps = [
    {
      num: '01', title: 'Capture',
      body: 'Vitals from rPPG or hospital monitor, plus chief complaint, history, and labs — entered or voice-dictated.',
      tags: ['vitals', 'history', { label: 'rPPG', primary: true }],
    },
    {
      num: '02', title: 'Reason',
      body: 'An agentic loop retrieves the right CPGs from its own working diagnosis, drafts a care plan, then runs a safety critic over it before you see it.',
      tags: [{ label: 'Agentic RAG', primary: true }, '+ safety critic'],
    },
    {
      num: '03', title: 'Decide',
      body: 'Review a ranked differential and a CPG-cited care plan. Every claim is traceable to a paragraph in the source guideline.',
      tags: ['DDx', { label: 'cited plan', primary: true }],
    },
  ];
  return (
    <section className="px-8 py-24" id="how">
      <div className="max-w-[1280px] mx-auto">
        <SectionHead
          eyebrow="How it works"
          title={<><span className="whitespace-nowrap">From triage to care plan,</span> <em className="italic text-teal-700">in three steps</em>.</>}
          sub="No new EMR to learn. ClearPath sits next to your existing workflow and does the reading, retrieval, and reasoning so you can focus on the patient."
        />
        <div className="grid md:grid-cols-[1fr_auto_1fr_auto_1fr] gap-4 md:gap-0 items-stretch">
          {steps.map((s, i) => (
            <React.Fragment key={s.num}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="bg-white border border-slate-200 rounded-[20px] p-8 hover:-translate-y-1 hover:border-teal-300 hover:shadow-[0_24px_48px_-16px_rgba(15,23,42,0.12)] transition-all"
              >
                <div className="w-9 h-9 bg-slate-900 text-white rounded-[10px] inline-flex items-center justify-center font-mono text-[13px] font-semibold mb-6">{s.num}</div>
                <h3 className="text-[22px] font-semibold tracking-tight mb-2.5">{s.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed">{s.body}</p>
                <div className="mt-6 pt-6 border-t border-slate-100 flex items-center gap-2.5 font-mono text-[11px] text-slate-500 flex-wrap">
                  {s.tags.map((t, j) => {
                    const isObj = typeof t === 'object';
                    const label = isObj ? t.label : t;
                    const primary = isObj && t.primary;
                    return (
                      <span
                        key={j}
                        className={`px-2 py-1 rounded-md border ${primary ? 'bg-teal-50 border-teal-100 text-teal-700' : 'bg-slate-50 border-slate-200 text-slate-700'}`}
                      >
                        {label}
                      </span>
                    );
                  })}
                </div>
              </motion.div>
              {i < 2 && (
                <div className="hidden md:flex self-center text-slate-300 px-4">
                  <ArrowRight className="w-7 h-7" strokeWidth={1.5} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- ARCHITECTURE (7-stage pipeline) ---------- */
const STAGE_TYPES = {
  capture: { label: 'Multimodal capture', cls: 'bg-slate-100 text-slate-600 border-slate-200' },
  llm: { label: 'LLM reasoning', cls: 'bg-teal-50 text-teal-700 border-teal-200' },
  rule: { label: 'Deterministic', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  mixed: { label: 'LLM + deterministic', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
};

const STAGES = [
  {
    n: '1', Icon: Activity, type: 'capture', title: 'Patient Intake & Vitals',
    desc: 'Vitals captured contactlessly from the camera (rPPG) or the ward monitor; the consultation is voice-recorded and turned into a SOAP note. History, labs, and chief complaint are entered or dictated.',
    tags: ['rPPG', 'voice → SOAP'],
  },
  {
    n: '2', Icon: BrainCircuit, type: 'llm', title: 'Differential Diagnosis',
    desc: 'The presentation is mapped to ranked ICD-11 differentials. A four-layer determinism stack keeps the candidate pool stable across reruns; an LLM re-ranks for this specific patient.',
    tags: ['ICD-11', 'LLM rerank', 'reproducible'],
  },
  {
    n: '3', Icon: Workflow, type: 'rule', title: 'Deterministic Scoped Routing',
    desc: 'A six-level rule cascade (D1–D6) resolves each diagnosis to the governing Malaysian MOH guidelines — no LLM, no blind keyword search. Out-of-scope presentations are refused, not guessed.',
    tags: ['D1–D6 cascade', 'scope-gated'],
  },
  {
    n: '4', Icon: BookOpen, type: 'mixed', title: 'Evidence-Graded Retrieval',
    desc: 'LLM-written queries pull the relevant paragraphs from the routed guidelines via hybrid vector + keyword search — each chunk carrying its original MOH evidence grade.',
    tags: ['hybrid RRF', 'graded evidence'],
  },
  {
    n: '4.5', Icon: Network, type: 'rule', title: 'Knowledge-Graph Injection',
    desc: 'Before synthesis, drug–condition and drug–drug edges from the clinical knowledge graph are injected as structured “prefer / avoid” evidence — pure Cypher, no LLM.',
    tags: ['Neo4j', 'prefer / avoid'],
    half: true,
  },
  {
    n: '5', Icon: FileText, type: 'llm', title: 'Care-Plan Synthesis',
    desc: 'An LLM drafts the eight-section executable care plan, constrained to the retrieved evidence and passed through an eight-layer post-synthesis validator chain (dedup, coverage, anti-hallucination).',
    tags: ['8-section plan', 'cite-or-abstain'],
  },
  {
    n: '6', Icon: ShieldAlert, type: 'mixed', title: 'Hybrid Safety Critic',
    desc: 'An independent dual-source critic — an LLM pharmacist in parallel with a knowledge-graph verifier — screens every drug for allergy, interaction, dose, and contraindication. Any critical concern blocks sign-off.',
    tags: ['LLM ∥ KG', 'blocks sign-off'],
  },
  {
    n: '7', Icon: Send, type: 'rule', title: 'Delivery',
    desc: 'On clinician approval, a fully cited care-plan PDF is generated, audit-logged, and delivered to the consented patient. A structured prior-visit summary is written for continuity.',
    tags: ['cited PDF', 'audit-logged'],
  },
];

function Architecture() {
  return (
    <section className="px-8 py-24" id="architecture" style={{ background: 'linear-gradient(180deg, #fafbfc, #fff)' }}>
      <div className="max-w-[1280px] mx-auto">
        <SectionHead
          eyebrow="Architecture"
          title={<><span className="whitespace-nowrap">Seven stages —</span> <em className="italic text-teal-700">deterministic by default</em>.</>}
          sub="Safety comes from the system around the model, not its size. The pipeline is rule-driven wherever a rule will do, and reserves language models strictly for the reasoning that can't be expressed as rules — each one constrained to cited evidence."
        />

        {/* legend */}
        <div className="flex flex-wrap items-center justify-center gap-2.5 mb-12">
          {Object.values(STAGE_TYPES).map((t) => (
            <span key={t.label} className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full border ${t.cls}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
              {t.label}
            </span>
          ))}
        </div>

        {/* vertical pipeline */}
        <div className="relative max-w-[860px] mx-auto">
          {STAGES.map((s, i) => {
            const t = STAGE_TYPES[s.type];
            const isLast = i === STAGES.length - 1;
            return (
              <motion.div
                key={s.n}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ duration: 0.4, delay: (i % 3) * 0.08 }}
                className="relative flex gap-5 pb-6 last:pb-0"
              >
                {/* connector line */}
                {!isLast && (
                  <div className="absolute left-[27px] top-[58px] bottom-0 w-px bg-gradient-to-b from-slate-300 to-slate-200" />
                )}
                {/* stage number badge */}
                <div className={`relative shrink-0 w-14 h-14 rounded-2xl border-2 inline-flex items-center justify-center font-mono font-bold bg-white
                  ${s.type === 'llm' ? 'border-teal-300 text-teal-700' : s.type === 'rule' ? 'border-indigo-200 text-indigo-700' : s.type === 'mixed' ? 'border-amber-200 text-amber-700' : 'border-slate-200 text-slate-500'}
                  ${s.half ? 'text-[13px]' : 'text-lg'}`}
                >
                  {s.n}
                </div>
                {/* stage card */}
                <div className={`flex-1 bg-white border border-slate-200 rounded-[18px] p-5 hover:border-teal-300 hover:shadow-[0_20px_40px_-18px_rgba(15,23,42,0.14)] transition-all ${s.half ? 'border-dashed' : ''}`}>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2.5">
                      <span className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-100 text-teal-700 inline-flex items-center justify-center shrink-0">
                        <s.Icon className="w-[17px] h-[17px]" strokeWidth={1.8} />
                      </span>
                      <h3 className="text-[16px] font-semibold tracking-tight text-slate-900">
                        {s.half && <span className="font-mono text-[11px] text-slate-400 mr-1.5">Stage {s.n}</span>}
                        {s.title}
                      </h3>
                    </div>
                    <span className={`shrink-0 inline-flex items-center text-[10.5px] font-semibold px-2 py-1 rounded-md border ${t.cls}`}>
                      {t.label}
                    </span>
                  </div>
                  <p className="text-[13.5px] text-slate-600 leading-relaxed mb-3 pl-[42px]">{s.desc}</p>
                  <div className="flex flex-wrap gap-2 pl-[42px]">
                    {s.tags.map((tag) => (
                      <span key={tag} className="font-mono text-[10.5px] text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-md">{tag}</span>
                    ))}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ---------- FEATURES ---------- */
function Features() {
  const feats = [
    { Icon: BrainCircuit, t: 'Agentic RAG', d: 'The agent actively chooses which guidelines to retrieve based on its own working diagnosis — never blind keyword search.', meta: ['working DDx', 'retrieval loop'] },
    { Icon: ShieldAlert, t: 'Safety critic', d: 'Before the plan reaches you, a critic screens every drug for allergy, interaction, dose, and contraindication against the patient’s comorbidities.', meta: ['DDI checker', 'allergy guard'] },
    { Icon: Eye, t: 'Transparent reasoning', d: 'Watch the agent think — every retrieval, critic, and ranking step is visible live, and each recommendation tags the exact CPG paragraph it came from.', meta: ['chain of thought', 'paragraph-level cites'] },
    { Icon: Camera, t: 'rPPG vital capture', d: 'Pulse, SpO₂, respiratory rate — measured from the camera feed. No cuff, no probe, no friction.', meta: ['contactless', '15-sec scan'] },
    { Icon: Activity, t: 'Clinician override', d: 'Disagree? Pick a different differential and ClearPath re-routes the entire plan against the new working diagnosis.', meta: ['re-synth', 'versioned'] },
    { Icon: Mic, t: 'Voice-to-SOAP', d: 'Record the whole consultation — ClearPath transcribes it with speaker diarisation and writes a structured SOAP note straight into your clinical notes. Audio is deleted the moment it’s transcribed.', meta: ['diarised', 'auto-SOAP'] },
  ];
  return (
    <section className="px-8 py-24" id="features" style={{ background: 'linear-gradient(180deg, #fafbfc, #fff)' }}>
      <div className="max-w-[1280px] mx-auto">
        <SectionHead
          eyebrow="Powered by"
          title={<><span className="whitespace-nowrap">Decision support that</span> <em className="italic text-teal-700">shows its work</em>.</>}
          sub="Six capabilities, one workflow. Every recommendation is grounded in a specific CPG paragraph and a specific reasoning trace — never a black box."
        />
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {feats.map(({ Icon, t, d, meta }, i) => (
            <motion.article
              key={t}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.4, delay: (i % 3) * 0.08 }}
              className="group relative bg-white border border-slate-200 rounded-[20px] p-8 overflow-hidden hover:-translate-y-1.5 hover:border-teal-400 hover:shadow-[0_28px_56px_-16px_rgba(20,184,166,0.28)] transition-all duration-300"
            >
              {/* top accent bar */}
              <div className="absolute top-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{ background: 'linear-gradient(90deg, transparent, #14b8a6, transparent)' }} />
              {/* soft teal glow that fades in on hover */}
              <div className="absolute -top-16 -right-16 w-44 h-44 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                style={{ background: 'radial-gradient(circle, rgba(20,184,166,0.18), transparent 70%)', filter: 'blur(20px)' }} />
              <span className="relative w-12 h-12 bg-teal-50 border border-teal-100 text-teal-700 rounded-[14px] inline-flex items-center justify-center mb-5 transition-all duration-300 group-hover:bg-teal-600 group-hover:border-teal-600 group-hover:text-white group-hover:scale-105 group-hover:shadow-[0_8px_20px_-6px_rgba(20,184,166,0.5)]">
                <Icon className="w-[22px] h-[22px]" strokeWidth={1.8} />
              </span>
              <h3 className="relative text-[19px] font-semibold tracking-tight mb-2.5 transition-colors duration-300 group-hover:text-teal-700">{t}</h3>
              <p className="text-sm text-slate-600 mb-4 leading-relaxed">{d}</p>
              <div className="font-mono text-[11px] text-slate-500 flex gap-3 flex-wrap">
                {meta.map((m) => (
                  <span key={m} className="px-2 py-1 rounded-md bg-slate-50 border border-slate-200">{m}</span>
                ))}
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- CASES ---------- */
const CASES = [
  {
    Icon: Heart,
    capability: 'Comorbid-CPG reconciliation',
    tag: 'Case 08 · Cardiometabolic',
    title: 'New HFrEF in a patient already on diabetes therapy',
    patient: [['62 M', 'demographics'], ['LVEF 25%', 'echo'], ['NYHA II', 'class'], ['HbA1c 8.4%', 'glycaemia']],
    body: 'Newly diagnosed heart failure on routine echo, here for a management plan while on metformin and a sulfonylurea. ClearPath routes the Heart Failure and T2DM guidelines together and drafts guideline-directed therapy across both.',
    signal: {
      tone: 'caution', Icon: Pill, label: 'Sulfonylurea flagged independently',
      text: 'Gliclazide may worsen heart-failure outcomes — raised as its own safety flag even though the draft plan only proposed to “review” it.',
    },
    cpgs: ['Heart Failure (5th Ed)', 'Type 2 Diabetes (6th Ed)'],
    outcomes: [['2', 'CPGs routed'], ['GDMT', 'drafted'], ['8-section', 'plan']],
    detail: [
      'Reconciles two chronic-disease guidelines into one non-conflicting plan.',
      'Initiates foundational HFrEF therapy (driven by LVEF 25%, NYHA II) with every step cited.',
      'No eGFR was supplied — the plan says so rather than inventing a renal value to justify dosing.',
    ],
  },
  {
    Icon: Baby,
    capability: 'Knowledge-graph teratogen veto',
    tag: 'Case 10 · Obstetric',
    title: 'Late booking visit — a teratogen hiding in the current meds',
    patient: [['35 F', 'demographics'], ['30 wks', 'gestation'], ['158/104', 'BP'], ['OGTT +', 'GDM']],
    body: 'A primigravida books at 30 weeks with high BP and new gestational diabetes — and a losartan prescription started two years ago, before the pregnancy was known. The clinician never asks about it.',
    signal: {
      tone: 'critical', Icon: ShieldX, label: 'Existing med vetoed',
      text: 'The knowledge graph stops losartan on its own — an ARB is teratogenic in pregnancy — auditing a drug the patient is actively taking, not one the plan proposed.',
    },
    cpgs: ['Heart Disease in Pregnancy (2nd Ed)', 'Diabetes in Pregnancy (2017)'],
    outcomes: [['1', 'teratogen vetoed'], ['2', 'obstetric CPGs'], ['PPCM', 'bridge']],
    detail: [
      'Sex- and pregnancy-aware routing unlocks the obstetric guidelines other cases exclude.',
      'A family history of peripartum cardiomyopathy bridges in the cardiac-pregnancy guidance.',
      'Safe-in-pregnancy antihypertensive alternatives are named where the contraindicated drug is removed.',
    ],
  },
  {
    Icon: AlertTriangle,
    capability: 'Cross-guideline conflict surfacing',
    tag: 'Case 11 · Conflict + safety',
    title: 'Erectile dysfunction in stable coronary disease',
    patient: [['56 M', 'demographics'], ['PCI 18 mo', 'cardiac'], ['on nitrate', 'current Rx'], ['BMI 31', 'obesity']],
    body: 'Two guidelines apply and disagree: the ED guideline makes a PDE5 inhibitor first-line, while the stable-CAD regimen keeps a long-acting nitrate. ClearPath names the conflict instead of silently picking a side.',
    signal: {
      tone: 'critical', Icon: ShieldX, label: 'CRITICAL · PDE5i × nitrate',
      text: 'The absolute nitrate contraindication is pre-empted from the current-med list, and the upstream β-blocker as an occult ED contributor is raised as a swap lever.',
    },
    cpgs: ['Erectile Dysfunction CPG', 'Stable Coronary Artery Disease CPG'],
    outcomes: [['2', 'CPGs conflict'], ['1', 'CRITICAL flag'], ['1', 'upstream lever']],
    detail: [
      'Emits the explicit line “Two CPGs apply and conflict on first-line therapy”, not a quiet override.',
      'Routes both an upstream-decision referral and the original-problem workup as structured recommendations.',
      'Surfaces bisoprolol as a possible medication-induced cause — a lever the first pass missed.',
    ],
  },
];

const SIGNAL_TONES = {
  caution: { box: 'bg-amber-50 border-amber-200', icon: 'text-amber-600', label: 'text-amber-800' },
  critical: { box: 'bg-rose-50 border-rose-200', icon: 'text-rose-600', label: 'text-rose-800' },
};

function Cases() {
  const [open, setOpen] = useState(null);
  return (
    <section className="px-8 py-24" id="cases" style={{ background: 'linear-gradient(180deg, #fff, #fafbfc)' }}>
      <div className="max-w-[1280px] mx-auto">
        <SectionHead
          eyebrow="Clinical scenarios"
          title={<><span className="whitespace-nowrap">Three hard consults,</span> <em className="italic text-teal-700">traced end-to-end</em>.</>}
          sub="The evaluation cases ClearPath is benchmarked on — each one a distinct failure mode that a single-guideline tool would miss. Open a card to see what the pipeline catches."
        />
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 items-start">
          {CASES.map((c, i) => {
            const { Icon, capability, tag, title, patient, body, signal, cpgs, outcomes, detail } = c;
            const tone = SIGNAL_TONES[signal.tone];
            const isOpen = open === i;
            const SignalIcon = signal.Icon;
            return (
              <motion.article
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="flex flex-col bg-white border border-slate-200 rounded-[20px] overflow-hidden hover:-translate-y-1 hover:shadow-[0_24px_48px_-16px_rgba(15,23,42,0.12)] transition-all"
              >
                {/* header: capability + case icon */}
                <div className="relative px-6 pt-6 pb-5 overflow-hidden"
                  style={{ background: 'linear-gradient(135deg, #f0fdfa, #f1f5f9)' }}>
                  <div className="absolute inset-0"
                    style={{
                      backgroundImage:
                        'linear-gradient(rgba(15,23,42,0.05) 1px, transparent 1px),' +
                        'linear-gradient(90deg, rgba(15,23,42,0.05) 1px, transparent 1px)',
                      backgroundSize: '24px 24px',
                    }} />
                  <div className="relative flex items-start justify-between gap-3">
                    <div>
                      <div className="font-mono text-[10px] text-teal-700 tracking-wider uppercase font-semibold mb-1.5">{tag}</div>
                      <div className="text-[15px] font-semibold text-slate-900 leading-snug max-w-[22ch]">{capability}</div>
                    </div>
                    <span className="shrink-0 w-11 h-11 rounded-[12px] bg-white/80 border border-teal-100 text-teal-600 inline-flex items-center justify-center">
                      <Icon className="w-[22px] h-[22px]" strokeWidth={1.6} />
                    </span>
                  </div>
                </div>

                <div className="p-6 flex flex-col flex-1">
                  <h3 className="text-[17px] font-semibold mb-3 tracking-tight leading-snug">{title}</h3>

                  {/* patient snapshot chips */}
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {patient.map(([v, l]) => (
                      <span key={l} title={l} className="font-mono text-[11px] text-slate-700 bg-slate-50 border border-slate-200 px-2 py-1 rounded-md">{v}</span>
                    ))}
                  </div>

                  <p className="text-[13.5px] text-slate-600 mb-4 leading-relaxed">{body}</p>

                  {/* signature catch */}
                  <div className={`rounded-xl border ${tone.box} px-3.5 py-3 mb-4`}>
                    <div className="flex items-center gap-2 mb-1">
                      <SignalIcon className={`w-4 h-4 ${tone.icon}`} strokeWidth={2} />
                      <span className={`text-[11px] font-bold tracking-wide uppercase ${tone.label}`}>{signal.label}</span>
                    </div>
                    <p className="text-[12.5px] text-slate-700 leading-relaxed">{signal.text}</p>
                  </div>

                  {/* routed CPGs */}
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {cpgs.map((g) => (
                      <span key={g} className="inline-flex items-center gap-1.5 text-[11px] text-teal-700 bg-teal-50 border border-teal-100 px-2 py-1 rounded-md">
                        <BookOpen className="w-3 h-3" strokeWidth={1.8} />{g}
                      </span>
                    ))}
                  </div>

                  {/* outcome stats */}
                  <div className="flex items-center gap-3 pt-4 border-t border-slate-100 mt-auto">
                    {outcomes.map(([v, l]) => (
                      <div key={l} className="flex-1">
                        <div className="font-display italic text-[22px] text-teal-700 leading-none">{v}</div>
                        <div className="text-[10px] text-slate-500 mt-1 tracking-wide uppercase font-medium">{l}</div>
                      </div>
                    ))}
                  </div>

                  {/* expand: what the pipeline did */}
                  <button
                    onClick={() => setOpen(isOpen ? null : i)}
                    aria-expanded={isOpen}
                    className="mt-4 w-full flex items-center justify-between text-[12px] font-semibold text-slate-700 hover:text-teal-700 transition-colors"
                  >
                    <span>{isOpen ? 'Hide reasoning trace' : 'See what the pipeline did'}</span>
                    <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} strokeWidth={2} />
                  </button>
                  <motion.div
                    initial={false}
                    animate={{ height: isOpen ? 'auto' : 0, opacity: isOpen ? 1 : 0 }}
                    transition={{ duration: 0.28, ease: 'easeInOut' }}
                    className="overflow-hidden"
                  >
                    <ul className="mt-3 flex flex-col gap-2.5 list-none p-0">
                      {detail.map((d) => (
                        <li key={d} className="flex gap-2.5 text-[12.5px] text-slate-600 leading-relaxed">
                          <FlaskConical className="w-3.5 h-3.5 text-teal-500 mt-0.5 shrink-0" strokeWidth={1.8} />
                          <span>{d}</span>
                        </li>
                      ))}
                    </ul>
                  </motion.div>
                </div>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ---------- CTA BAND ---------- */
function CTA({ onSignIn }) {
  return (
    <section className="px-8 pt-12 pb-12" id="cta">
      <div
        className="relative max-w-[calc(1280px+0px)] mx-8 lg:mx-auto rounded-[32px] p-14 lg:p-20 overflow-hidden text-white"
        style={{
          background:
            'radial-gradient(circle at 80% 20%, rgba(20,184,166,0.3) 0%, transparent 50%),' +
            'radial-gradient(circle at 10% 80%, rgba(20,184,166,0.2) 0%, transparent 50%),' +
            'linear-gradient(135deg, #0f172a 0%, #134e4a 100%)',
        }}
      >
        <div className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),' +
              'linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
            backgroundSize: '56px 56px',
            maskImage: 'radial-gradient(circle at 50% 50%, #000 0%, transparent 80%)',
            WebkitMaskImage: 'radial-gradient(circle at 50% 50%, #000 0%, transparent 80%)',
          }} />
        <div className="relative max-w-[1024px] mx-auto grid md:grid-cols-[1.5fr_1fr] gap-12 items-center">
          <div>
            <span className="text-[11px] tracking-widest uppercase text-teal-300 font-semibold mb-4 inline-block">Ready when you are</span>
            <h2 className="font-display italic text-[56px] leading-[1.04] tracking-tight mb-4 text-balance">
              Spend your hours <em className="not-italic text-teal-300">with patients,</em> not paperwork.
            </h2>
            <p className="text-base text-white/70 max-w-[50ch] leading-relaxed">
              Pilot ClearPath at your facility. Built on Malaysia's Clinical Practice
              Guidelines, with every recommendation cited and every decision logged.
            </p>
          </div>
          <div className="flex flex-col gap-3">
            <button
              onClick={onSignIn}
              className="inline-flex items-center justify-center gap-2.5 px-[22px] py-[13px] rounded-xl text-[14.5px] font-semibold text-teal-700 bg-white hover:bg-teal-50 shadow-[0_8px_24px_rgba(255,255,255,0.2)] transition-colors"
            >
              Sign in
              <ArrowRight className="w-4 h-4" />
            </button>
            <a href="#" className="inline-flex items-center justify-center gap-2.5 px-[22px] py-[13px] rounded-xl text-[14.5px] font-semibold text-white bg-transparent border border-white/20 hover:bg-white/5 hover:border-white/40 backdrop-blur transition-colors">
              Request a pilot
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------- FOOTER ---------- */
function Footer() {
  return (
    <footer className="px-8 pt-16 pb-8">
      <div className="max-w-[1280px] mx-auto grid md:grid-cols-[1.5fr_1fr_1fr_1fr] gap-12 pb-8 border-b border-slate-200">
        <div>
          <div className="font-display italic text-teal-700 text-[26px] leading-none mb-4">ClearPath.</div>
          <p className="text-[13px] text-slate-600 max-w-[36ch] leading-relaxed">
            An Evidence-Based Clinical Practice Guidance System — a research project
            at Universiti Malaya.
          </p>
        </div>
        <FootCol title="Product" links={['Features', 'How it works', 'Use cases', 'Request a pilot']} />
        <FootCol title="Research" links={['CPG corpus', 'Validation methodology', 'rPPG vital capture', 'Agentic pipeline']} />
        <FootCol title="Trust" links={['Cited recommendations', 'Audit logging', 'Security overview', 'Contact IT']} />
      </div>
      <div className="max-w-[1280px] mx-auto mt-8 flex justify-between items-center text-xs text-slate-500">
        <span>© 2026 ClearPath · UM</span>
        <span className="font-mono tracking-wide">30 MOH CPGs · Cited · Audit-logged</span>
      </div>
    </footer>
  );
}

function FootCol({ title, links }) {
  return (
    <div>
      <h4 className="text-[11px] tracking-widest uppercase text-slate-500 font-semibold mb-3.5">{title}</h4>
      <ul className="flex flex-col gap-2.5 list-none p-0 m-0">
        {links.map((l) => (
          <li key={l}>
            <a href="#" className="text-[13.5px] text-slate-700 hover:text-teal-700 transition-colors">{l}</a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------- Section head ---------- */
function SectionHead({ eyebrow, title, sub }) {
  return (
    <div className="text-center mb-14">
      <span className="inline-block text-[11px] tracking-widest uppercase text-teal-700 font-semibold mb-4">{eyebrow}</span>
      <h2 className="font-display text-[56px] leading-[1.04] tracking-tight max-w-[26ch] mx-auto mb-4 text-balance">
        {title}
      </h2>
      <p className="text-[17px] text-slate-600 max-w-[62ch] mx-auto leading-relaxed">{sub}</p>
    </div>
  );
}
