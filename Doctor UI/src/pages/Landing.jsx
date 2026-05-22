import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight, Hash, Workflow, BookOpen, FileCheck2,
  BrainCircuit, ShieldAlert, Eye, Camera, Activity, ListChecks,
  Heart, Stethoscope,
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
          <img src="/MHNexus.png" alt="MHNexus" className="h-14 w-auto -my-2.5" />
          <span className="w-px h-7 bg-slate-300" />
          <span className="font-display italic text-teal-700 text-2xl leading-none tracking-tight">
            ClearPath.
          </span>
        </a>
        <div className="hidden md:flex items-center gap-7 text-sm">
          <a href="#how" className="text-slate-600 hover:text-teal-700 transition-colors">How it works</a>
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
          <div className="inline-flex items-center gap-2.5 px-3 py-1.5 pl-2 bg-white/70 backdrop-blur border border-slate-200/60 rounded-full text-xs text-slate-700 font-medium mb-6">
            <span className="bg-teal-50 text-teal-700 border border-teal-100 px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide">NEW</span>
            Now piloting
            <span className="text-slate-400" aria-hidden>→</span>
          </div>

          <h1 className="font-display text-[76px] leading-[1.02] tracking-[-0.02em] text-slate-900 mb-6 text-balance">
            Clinician's <em className="italic text-teal-700 not-italic-fix">second opinion</em>, at the speed of a glance.
          </h1>

          <p className="text-lg text-slate-600 max-w-[50ch] mb-9 leading-[1.6]">
            ClearPath reads vitals, history, and chief complaint — then drafts a
            CPG-aligned care plan with citations in under a minute.
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
              // Canonical MHNexus probability colors (19-probability.html)
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
    { Icon: BookOpen, n: '30', unit: 'CPGs', label: 'MOH-endorsed guidelines indexed' },
    { Icon: Hash, n: '248', unit: 'codes', label: 'WHO ICD-11 codes mapped to scope' },
    { Icon: Workflow, n: '5', unit: 'stage', label: 'Agentic reasoning pipeline, end-to-end' },
    { Icon: FileCheck2, n: '100', unit: '%', label: 'Decisions audit-logged with citations' },
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

/* ---------- FEATURES ---------- */
function Features() {
  const feats = [
    { Icon: BrainCircuit, t: 'Agentic RAG', d: 'The agent actively chooses which guidelines to retrieve based on its own working diagnosis — never blind keyword search.', meta: ['working DDx', 'retrieval loop'] },
    { Icon: ShieldAlert, t: 'Safety critic', d: 'Before the plan reaches you, a critic screens every drug for allergy, interaction, dose, and contraindication against the patient’s comorbidities.', meta: ['DDI checker', 'allergy guard'] },
    { Icon: Eye, t: 'Transparent reasoning', d: 'Watch the agent think — every retrieval, critic, and ranking step is visible live, and each recommendation tags the exact CPG paragraph it came from.', meta: ['chain of thought', 'paragraph-level cites'] },
    { Icon: Camera, t: 'rPPG vital capture', d: 'Pulse, SpO₂, respiratory rate — measured from the camera feed. No cuff, no probe, no friction.', meta: ['contactless', '15-sec scan'] },
    { Icon: Activity, t: 'Clinician override', d: 'Disagree? Pick a different differential and ClearPath re-routes the entire plan against the new working diagnosis.', meta: ['re-synth', 'versioned'] },
    { Icon: ListChecks, t: 'Audit trail', d: 'Every consultation, plan, and citation is persisted with timestamps in the session record — a full, reviewable history of each decision.', meta: ['session log', 'timestamped'] },
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
              className="group relative bg-white border border-slate-200 rounded-[20px] p-8 overflow-hidden hover:-translate-y-1 hover:border-teal-300 hover:shadow-[0_24px_48px_-16px_rgba(15,23,42,0.12)] transition-all"
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: 'linear-gradient(90deg, transparent, #14b8a6, transparent)' }} />
              <span className="w-12 h-12 bg-teal-50 border border-teal-100 text-teal-700 rounded-[14px] inline-flex items-center justify-center mb-5">
                <Icon className="w-[22px] h-[22px]" strokeWidth={1.8} />
              </span>
              <h3 className="text-[19px] font-semibold tracking-tight mb-2.5">{t}</h3>
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
function Cases() {
  const cases = [
    {
      Icon: Stethoscope, tag: 'T2DM follow-up',
      title: 'Uncontrolled diabetes with hypertension',
      body: '67yo F, HbA1c 8.5%, BP 142/88. Routed against MOH T2DM (6th Ed) and Hypertension (5th Ed); intensification proposed with the plan screened by the safety critic.',
      outcomes: [['2', 'CPGs cited'], ['4', 'DDx ranked'], ['0', 'Safety flags']],
    },
    {
      Icon: Heart, tag: 'cardiac',
      title: 'Reduced ejection fraction',
      body: '58yo M, exertional dyspnoea, EF 38%. Differentials ranked against MOH Heart Failure (5th Ed), with guideline-directed therapy drafted and every claim cited to a paragraph.',
      outcomes: [['1', 'CPG cited'], ['3', 'DDx ranked'], ['1', 'Safety flag']],
    },
    {
      Icon: Activity, tag: 'clinician override',
      title: 'Dyslipidaemia, re-routed',
      body: 'Clinician rejects the top differential and selects another; ClearPath re-synthesises the whole plan against the new working diagnosis using MOH Dyslipidaemia (6th Ed).',
      outcomes: [['1', 'CPG cited'], ['1', 'Re-synth'], ['Full', 'Trace']],
    },
  ];
  return (
    <section className="px-8 py-24" id="cases" style={{ background: 'linear-gradient(180deg, #fff, #fafbfc)' }}>
      <div className="max-w-[1280px] mx-auto">
        <SectionHead
          eyebrow="Clinical scenarios"
          title={<><span className="whitespace-nowrap">Real consults,</span> <em className="italic text-teal-700">traced end-to-end</em>.</>}
          sub="Anonymised samples of how ClearPath reasons through the complexity of clinical work."
        />
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {cases.map(({ Icon, tag, title, body, outcomes }, i) => (
            <motion.article
              key={title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="bg-white border border-slate-200 rounded-[20px] overflow-hidden hover:-translate-y-1 hover:shadow-[0_24px_48px_-16px_rgba(15,23,42,0.12)] transition-all"
            >
              <div className="aspect-video relative flex items-center justify-center overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #f0fdfa, #f1f5f9)' }}>
                <div className="absolute inset-0"
                  style={{
                    backgroundImage:
                      'linear-gradient(rgba(15,23,42,0.05) 1px, transparent 1px),' +
                      'linear-gradient(90deg, rgba(15,23,42,0.05) 1px, transparent 1px)',
                    backgroundSize: '24px 24px',
                  }} />
                <Icon className="w-14 h-14 text-teal-600 relative" strokeWidth={1.4} />
              </div>
              <div className="p-6">
                <span className="inline-block font-mono text-[10px] text-teal-700 bg-teal-50 border border-teal-100 px-2 py-1 rounded-md tracking-wider uppercase font-semibold mb-3">{tag}</span>
                <h3 className="text-[18px] font-semibold mb-2 tracking-tight">{title}</h3>
                <p className="text-[13.5px] text-slate-600 mb-4 leading-relaxed">{body}</p>
                <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                  {outcomes.map(([v, l]) => (
                    <div key={l} className="flex-1">
                      <div className="font-display italic text-2xl text-teal-700 leading-none">{v}</div>
                      <div className="text-[10.5px] text-slate-500 mt-1 tracking-wide uppercase font-medium">{l}</div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.article>
          ))}
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
            An Evidence-Based Clinical Practice Guidance System — a research collaboration
            between Universiti Malaya and MHNexus.
          </p>
        </div>
        <FootCol title="Product" links={['Features', 'How it works', 'Use cases', 'Request a pilot']} />
        <FootCol title="Research" links={['CPG corpus', 'Validation methodology', 'rPPG vital capture', 'Agentic pipeline']} />
        <FootCol title="Trust" links={['Cited recommendations', 'Audit logging', 'Security overview', 'Contact IT']} />
      </div>
      <div className="max-w-[1280px] mx-auto mt-8 flex justify-between items-center text-xs text-slate-500">
        <span>© 2026 ClearPath · UM × MHNexus</span>
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
