import React, { useState } from 'react';
import {
  Activity,
  Stethoscope,
  Heart,
  ChevronDown,
  Dumbbell,
  Salad,
  Pill,
  Scale,
  Wine,
  CigaretteOff,
  Trash2,
  Plus,
} from 'lucide-react';
import { GlassCard } from '../shared';
import { useTheme } from '../../context/ThemeContext';
import { InlineEdit } from './CarePlanSection';

/* Lifestyle category → icon + colour. Keys mirror clinicalMappers.classifyLifestyle.
   Each category gets a distinct tint so the cards are scannable at a glance;
   the generic 'Lifestyle' fallback keeps the house teal. */
const LIFESTYLE_STYLE = {
  Exercise:  { Icon: Dumbbell,     text: 'text-emerald-600', chip: 'bg-emerald-500/10 text-emerald-600' },
  Diet:      { Icon: Salad,        text: 'text-lime-600',    chip: 'bg-lime-500/10 text-lime-600' },
  Smoking:   { Icon: CigaretteOff, text: 'text-rose-600',    chip: 'bg-rose-500/10 text-rose-600' },
  Alcohol:   { Icon: Wine,         text: 'text-purple-600',  chip: 'bg-purple-500/10 text-purple-600' },
  Weight:    { Icon: Scale,        text: 'text-amber-600',   chip: 'bg-amber-500/10 text-amber-600' },
  Adherence: { Icon: Pill,         text: 'text-sky-600',     chip: 'bg-sky-500/10 text-sky-600' },
  Lifestyle: { Icon: Heart,        text: 'text-teal-700',    chip: 'bg-[var(--accent-primary)]/12 text-teal-700' },
};

const URGENCY_OPTIONS = ['Routine', 'This admission', 'Today'];

/* Urgency pill colours */
function urgencyPillCls(value) {
  if (value === 'Today') return 'bg-red-100 text-red-700';
  if (value === 'This admission') return 'bg-amber-100 text-amber-700';
  return 'bg-slate-100 text-slate-500';
}

/* Editable urgency — small select styled as a pill */
function UrgencySelect({ value, onChange }) {
  return (
    <select
      value={URGENCY_OPTIONS.includes(value) ? value : 'Routine'}
      onChange={(e) => onChange(e.target.value)}
      className={`appearance-none cursor-pointer text-[11px] font-semibold px-2.5 py-0.5 rounded-full whitespace-nowrap border-0 focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/40 ${urgencyPillCls(value)}`}
      title="Set urgency"
    >
      {URGENCY_OPTIONS.map((o) => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  );
}

/* Small delete button — appears on row hover, mirrors the medications table */
function DeleteBtn({ onClick, label }) {
  const { isDark } = useTheme();
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={`p-1 rounded-md opacity-0 group-hover/row:opacity-100 transition-all flex-shrink-0 ${
        isDark ? 'text-red-400 hover:bg-red-500/20 hover:text-red-300' : 'text-red-400 hover:bg-red-50 hover:text-red-600'
      }`}
    >
      <Trash2 className="w-3.5 h-3.5" strokeWidth={1.7} />
    </button>
  );
}

function AddBtn({ onClick, children }) {
  const { isDark } = useTheme();
  return (
    <button
      type="button"
      onClick={onClick}
      className={`mt-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
        isDark
          ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
          : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'
      }`}
    >
      <Plus className="w-3.5 h-3.5" strokeWidth={2.5} />
      {children}
    </button>
  );
}

export default function CareMonitoringPanel({ carePlan, dispatch }) {
  const { isDark } = useTheme();
  const [activeTab, setActiveTab] = useState('proc');
  const [expandedId, setExpandedId] = useState(null);

  const procedures = carePlan.interventions || [];
  const monitoring = carePlan.monitoring || [];
  const lifestyle = carePlan.lifestyle || [];
  const total = procedures.length + monitoring.length + lifestyle.length;

  const addItem = (section) => dispatch({ type: 'ADD_CARE_ITEM', payload: { section } });
  const deleteItem = (section, id) => dispatch({ type: 'DELETE_CARE_ITEM', payload: { section, id } });
  const updateField = (section, id, field, value) =>
    dispatch({ type: 'UPDATE_CARE_ITEM_FIELD', payload: { section, id, field, value } });

  const tabs = [
    { key: 'proc', label: 'Procedures & Interventions', icon: Stethoscope, n: procedures.length },
    { key: 'mon', label: 'Monitoring & Testing', icon: Activity, n: monitoring.length },
    { key: 'life', label: 'Lifestyle Recommendation', icon: Heart, n: lifestyle.length },
  ];

  const PROC_COLS = 'minmax(0,168px) minmax(0,1fr) 120px 30px 28px';
  const MON_COLS = 'minmax(0,150px) minmax(0,1fr) 172px 28px';

  const headerCls = `text-[10.5px] font-bold tracking-[0.06em] uppercase pb-2.5 ${
    isDark ? 'text-slate-500' : 'text-slate-400'
  }`;
  const rowBorder = isDark ? 'border-white/5' : 'border-slate-100';

  return (
    <GlassCard className="p-0 overflow-hidden">
      {/* Header */}
      <div className={`px-[22px] pt-[18px] pb-4 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[var(--accent-primary)]/12 text-teal-700 flex items-center justify-center">
            <Activity size={17} strokeWidth={1.8} />
          </div>
          <h3 className={`text-[17px] font-semibold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
            Care &amp; Monitoring
          </h3>
          <span
            className={`text-[12px] font-semibold px-2.5 py-0.5 rounded-full ${
              isDark ? 'bg-white/10 text-slate-400' : 'bg-slate-100 text-slate-500'
            }`}
          >
            {total}
          </span>
        </div>

        {/* Segmented control */}
        <div className={`mt-4 flex gap-1 p-1 rounded-xl ${isDark ? 'bg-white/5' : 'bg-slate-100'}`}>
          {tabs.map((t) => {
            const on = activeTab === t.key;
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setActiveTab(t.key)}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-2.5 rounded-[9px] text-[13.5px] font-semibold cursor-pointer transition-all duration-150 ${
                  on
                    ? isDark
                      ? 'bg-white/10 shadow-sm text-white'
                      : 'bg-white shadow-sm text-slate-800'
                    : 'bg-transparent text-slate-500'
                }`}
              >
                <Icon size={15} strokeWidth={1.8} className={on ? 'text-teal-700' : 'text-slate-400'} />
                <span className="truncate">{t.label}</span>
                <span
                  className={`text-[11.5px] font-semibold px-[7px] py-px rounded-full ${
                    on
                      ? 'bg-[var(--accent-primary)]/12 text-teal-700'
                      : isDark
                      ? 'bg-white/10 text-slate-400'
                      : 'bg-white text-slate-400'
                  }`}
                >
                  {t.n}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active sub-section */}
      <div className="px-[22px] pt-3.5 pb-4">
        {/* PROCEDURES */}
        {activeTab === 'proc' && (
          <>
            <div
              className={`grid gap-4 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}
              style={{ gridTemplateColumns: PROC_COLS }}
            >
              <div className={headerCls}>Procedure</div>
              <div className={headerCls}>Rationale</div>
              <div className={`${headerCls} text-right`}>When</div>
              <div className={headerCls} />
              <div className={headerCls} />
            </div>
            {procedures.length === 0 && (
              <div className="py-6 text-center text-[13px] text-slate-400">No procedures or interventions.</div>
            )}
            {procedures.map((p, i) => {
              const note = p.reasoning || p.cpgRef;
              const open = expandedId === p.id;
              const last = i === procedures.length - 1;
              return (
                <div key={p.id} className={`border-b ${last ? 'border-transparent' : rowBorder} group/row`}>
                  <div className="grid gap-4 items-start py-3.5" style={{ gridTemplateColumns: PROC_COLS }}>
                    <div className={`text-[14.5px] font-semibold leading-snug ${isDark ? 'text-white' : 'text-slate-800'}`}>
                      <InlineEdit value={p.name} onChange={(v) => updateField('interventions', p.id, 'name', v)} placeholder="Procedure name" />
                    </div>
                    <div className={`text-[12.5px] leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      <InlineEdit value={p.rationale} onChange={(v) => updateField('interventions', p.id, 'rationale', v)} multiline placeholder="Rationale" />
                    </div>
                    <div className="flex justify-end pt-px">
                      <UrgencySelect value={p.urgency} onChange={(v) => updateField('interventions', p.id, 'urgency', v)} />
                    </div>
                    {note ? (
                      <button
                        type="button"
                        onClick={() => setExpandedId(open ? null : p.id)}
                        aria-expanded={open}
                        title="AI reasoning"
                        className={`w-[26px] h-[26px] rounded-lg border flex items-center justify-center justify-self-end transition-all duration-150 ${
                          open
                            ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-teal-700'
                            : isDark
                            ? 'border-white/10 text-slate-400'
                            : 'border-slate-200 text-slate-400'
                        }`}
                      >
                        <ChevronDown
                          size={15}
                          strokeWidth={2}
                          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .18s ease' }}
                        />
                      </button>
                    ) : (
                      <div />
                    )}
                    <div className="flex justify-end pt-0.5">
                      <DeleteBtn onClick={() => deleteItem('interventions', p.id)} label="Remove procedure" />
                    </div>
                  </div>
                  {open && note && (
                    <div
                      className={`rounded-[10px] mb-3.5 px-3.5 py-[11px] border border-l-[2.5px] border-l-[var(--accent-primary)] ${
                        isDark ? 'bg-white/5 border-white/10' : 'bg-[#f8fafc] border-slate-200'
                      }`}
                      style={{ marginLeft: 0 }}
                    >
                      <div className="text-[10px] font-bold tracking-widest uppercase text-teal-700 mb-1">
                        AI reasoning
                      </div>
                      <div className={`text-[12.5px] leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                        {note}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            <AddBtn onClick={() => addItem('interventions')}>Add Procedure</AddBtn>
          </>
        )}

        {/* MONITORING */}
        {activeTab === 'mon' && (
          <>
            <div
              className={`grid gap-4 border-b ${isDark ? 'border-white/10' : 'border-slate-200'}`}
              style={{ gridTemplateColumns: MON_COLS }}
            >
              <div className={headerCls}>Test</div>
              <div className={headerCls}>Schedule</div>
              <div className={headerCls}>Target</div>
              <div className={headerCls} />
            </div>
            {monitoring.length === 0 && (
              <div className="py-6 text-center text-[13px] text-slate-400">No monitoring or testing items.</div>
            )}
            {monitoring.map((m, i) => {
              const last = i === monitoring.length - 1;
              return (
                <div
                  key={m.id}
                  className={`grid gap-4 items-start py-3.5 border-b ${last ? 'border-transparent' : rowBorder} group/row`}
                  style={{ gridTemplateColumns: MON_COLS }}
                >
                  <div className={`text-[14.5px] font-semibold leading-snug ${isDark ? 'text-white' : 'text-slate-800'}`}>
                    <InlineEdit
                      value={m.parameter || m.task}
                      onChange={(v) => updateField('monitoring', m.id, m.parameter !== undefined ? 'parameter' : 'task', v)}
                      placeholder="Test name"
                    />
                  </div>
                  <div className="pt-px text-[13px] font-medium text-teal-700">
                    <InlineEdit value={m.schedule} onChange={(v) => updateField('monitoring', m.id, 'schedule', v)} placeholder="Schedule" />
                  </div>
                  <div className={`text-[12.5px] leading-snug pt-0.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    <InlineEdit value={m.target} onChange={(v) => updateField('monitoring', m.id, 'target', v)} placeholder="—" />
                  </div>
                  <div className="flex justify-end pt-0.5">
                    <DeleteBtn onClick={() => deleteItem('monitoring', m.id)} label="Remove test" />
                  </div>
                </div>
              );
            })}
            <AddBtn onClick={() => addItem('monitoring')}>Add Test</AddBtn>
          </>
        )}

        {/* LIFESTYLE */}
        {activeTab === 'life' && (
          <>
            <div className="grid grid-cols-2 gap-3 py-1">
              {lifestyle.length === 0 && (
                <div className="col-span-2 py-6 text-center text-[13px] text-slate-400">
                  No lifestyle recommendations.
                </div>
              )}
              {lifestyle.map((l) => {
                const style = LIFESTYLE_STYLE[l.category] || LIFESTYLE_STYLE.Lifestyle;
                const Icon = style.Icon;
                return (
                  <div
                    key={l.id}
                    className={`group/row flex gap-3 items-start p-3.5 rounded-2xl border transition-colors duration-150 ${
                      isDark ? 'bg-white/5 border-white/10' : 'bg-[#fcfdfd] border-slate-200'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${style.chip}`}>
                      <Icon size={16} strokeWidth={1.8} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={`text-[10.5px] font-bold tracking-wider uppercase mb-1 ${style.text}`}>
                        <InlineEdit value={l.category} onChange={(v) => updateField('lifestyle', l.id, 'category', v)} placeholder="Category" />
                      </div>
                      <div className={`text-[13px] font-medium leading-snug ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                        <InlineEdit value={l.goal} onChange={(v) => updateField('lifestyle', l.id, 'goal', v)} multiline placeholder="Goal" />
                      </div>
                      <div className={`text-[12px] leading-snug mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        <InlineEdit value={l.detail} onChange={(v) => updateField('lifestyle', l.id, 'detail', v)} multiline placeholder="Add benefit / detail" />
                      </div>
                    </div>
                    <DeleteBtn onClick={() => deleteItem('lifestyle', l.id)} label="Remove recommendation" />
                  </div>
                );
              })}
            </div>
            <AddBtn onClick={() => addItem('lifestyle')}>Add Recommendation</AddBtn>
          </>
        )}
      </div>
    </GlassCard>
  );
}
