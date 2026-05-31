/**
 * Map ClinicalPlanResponse.ddx → diagnosis state shape for DiagnosisSection
 */
export function mapDdxToDiagnosis(ddxList, cpgsMatched) {
  const differentials = ddxList.map((d, i) => {
    const rawScore = d.score_breakdown?.final_score !== undefined
      ? d.score_breakdown.final_score
      : d.similarity;
    // final_score = base + incl_boost − excl_penalty and can exceed 1.0 when an
    // inclusion / red-flag boost fires. Clamp before rendering so the UI never
    // shows a >100% confidence (clinically nonsensical and erodes trust).
    const scoreVal = Math.max(0, Math.min(1, rawScore ?? 0));
    return {
      id: i + 1,
      name: d.title,
      icdCode: d.code,
      probability: Math.round(scoreVal * 100),
      risk: scoreVal >= 0.75 ? 'high' : scoreVal >= 0.45 ? 'medium' : 'low',
      reasoning: d.reasoning || [],       // LLM reasoning for display
      inclusionMatch: d.inclusion_match,
      // Re-ranking & override data
      mathRank: d.math_rank,
      llmRank: d.llm_rank,
      rankDelta: d.rank_delta,
      overrideReason: d.override_reason,
      exclusionMatch: d.exclusion_match,
      matchedExclusion: d.matched_exclusion,
      exclusionPenalty: d.exclusion_penalty,
      scoreBreakdown: d.score_breakdown,
    };
  });

  return {
    differentials,
    selectedDiagnosisIds: differentials.length > 0 ? [differentials[0].id] : [],
    cpgsMatched,    // e.g. ["CPG AF Management", "CPG Hypertension"]
  };
}

/**
 * Map ClinicalPlanResponse.treatment_plan → carePlan state shape for CarePlanSection
 */
export function mapTreatmentPlanToCarePlan(plan, evidence = []) {
  // Split recommendations by type into UI sections
  const pharmacological = plan.recommendations.filter(r => r.type === 'pharmacological');
  const procedures      = plan.recommendations.filter(r => r.type === 'procedure');
  const lifestyle       = plan.recommendations.filter(r => r.type === 'lifestyle');
  const referrals       = plan.recommendations.filter(r => r.type === 'referral');
  const investigations  = plan.recommendations.filter(r => r.type === 'investigation');

  // Split "Drug Name 50mg OD orally..." into { drugName, dose }
  // Cuts at the first standalone number or at known dose keywords
  const splitIntervention = (text) => {
    if (!text) return { drugName: text, dose: null };
    // Try splitting at " — " first (explicit separator from LLM)
    const dashIdx = text.indexOf(' — ');
    if (dashIdx !== -1) return { drugName: text.slice(0, dashIdx).trim(), dose: text.slice(dashIdx + 3).trim() };
    // Split before first dose pattern: number+unit or "up to", "at least", common dose words
    const dosePattern = /\s+(?=\d|\bup to\b|\bat least\b|\bonce\b|\btwice\b|\bthrce\b|\boral|\bIV\b|\bIM\b|\bSC\b|\btopical\b|\bnebulised\b)/i;
    const match = text.search(dosePattern);
    if (match !== -1) return { drugName: text.slice(0, match).trim(), dose: text.slice(match).trim() };
    return { drugName: text, dose: null };
  };

  // Split pharmacological recommendations by action field
  const byAction = (action) => pharmacological
    .filter(r => (r.action ?? 'start') === action)
    .map((r, i) => {
      const { drugName, dose } = splitIntervention(r.intervention);
      return {
        id: i + 1,
        name: drugName,
        dose: dose,
        reason: r.rationale,
        cpgRef: r.cpg_source,
        evidenceGrade: r.evidence_grade || null,
        accepted: true,
      };
    });

  const interventionItems = [...procedures, ...investigations].map((r, i) => ({
    id: i + 1,
    name: r.intervention,
    rationale: r.rationale,
    urgency: '',
    cpgRef: r.cpg_source,
    evidenceGrade: r.evidence_grade || null,
    accepted: true,
  }));

  const lifestyleItems = lifestyle.map((r, i) => ({
    id: i + 1,
    goal: r.intervention,
    rationale: r.rationale,
    cpgRef: r.cpg_source,
    accepted: true,
  }));

  const cleanReferralText = (value = '') => String(value)
    .replace(/\s+/g, ' ')
    .replace(/\s*\((routine|urgent|consider|today|semi-urgent|prompt)\)/gi, '')
    .replace(/^refer\s+to\s+/i, 'Referral to ')
    .trim();

  const referralDepartment = (value = '') => {
    const text = cleanReferralText(value).toLowerCase();
    const departments = [
      ['cardiology', 'Cardiology'],
      ['cardiologist', 'Cardiology'],
      ['multidisciplinary team', 'Multidisciplinary Team'],
      ['physiotherapy', 'Physiotherapy'],
      ['nephrology', 'Nephrology'],
      ['ophthalmology', 'Ophthalmology'],
      ['dietetics', 'Dietetics'],
      ['psychiatry', 'Psychiatry'],
      ['dentistry', 'Dentistry'],
      ['oral health professional', 'Oral Health Professional'],
      ['bariatric surgery', 'Bariatric Surgery'],
    ];
    const match = departments.find(([needle]) => text.includes(needle));
    if (match) return match[1];

    return cleanReferralText(value)
      .replace(/^referral to\s+/i, '')
      .split(/\s+[-–—]\s+|:/)[0]
      .trim();
  };

  const urgencyRank = { Routine: 1, 'Semi-Urgent': 2, Urgent: 3 };

  const referralItems = [];
  const referralByDepartment = new Map();

  referrals.forEach((r) => {
    const text = (r.intervention || '').toLowerCase();
    let urgency = 'Routine';
    if (text.includes('urgent')) urgency = 'Urgent';
    else if (text.includes('semi-urgent') || text.includes('prompt')) urgency = 'Semi-Urgent';

    const department = referralDepartment(r.intervention);
    const existing = referralByDepartment.get(department.toLowerCase());
    if (existing && urgencyRank[existing.urgency] >= urgencyRank[urgency]) return;

    referralByDepartment.set(department.toLowerCase(), {
      id: 0,
      specialty: `Referral to ${department}`,
      reason: r.rationale,
      urgency,
      cpgRef: r.cpg_source,
      accepted: true,
    });
  });

  [...referralByDepartment.values()].forEach((item) => {
    referralItems.push({ ...item, id: referralItems.length + 1 });
  });

  const allRecs = plan.recommendations ?? [];

  // ----- CPG FULL NAME LOOKUP -----
  // Maps the abbreviated CPG names used in cpg_source to full human-readable guideline titles.
  // Abbreviation comes from the LLM's cpg_source (e.g. "CPG PCI §3.2 [chunk 1]").
  // The routing cpg_name values (e.g. "Percutaneous-Coronary-Intervention") are also mapped.
  const CPG_FULL_NAMES = {
    // Cardiology
    'PCI':                'Management of Percutaneous Coronary Intervention',
    'Percutaneous-Coronary-Intervention': 'Management of Percutaneous Coronary Intervention',
    'NSTE-ACS':           'Management of Non-ST Elevation Acute Coronary Syndrome',
    'NSTEMI':             'Management of Non-ST Elevation Acute Coronary Syndrome',
    'STEMI':              'Management of ST Elevation Myocardial Infarction',
    'Stable CAD':         'Management of Stable Coronary Artery Disease',
    'Stable-Coronary-Artery-Disease': 'Management of Stable Coronary Artery Disease',
    'Heart Failure':      'Management of Heart Failure',
    'AF':                 'Management of Atrial Fibrillation',
    'AF Management':      'Management of Atrial Fibrillation',
    'Atrial-Fibrillation': 'Management of Atrial Fibrillation',
    'IE':                 'Prevention of Infective Endocarditis',
    'Infective-Endocarditis': 'Prevention of Infective Endocarditis',
    'PAH':                'Management of Pulmonary Arterial Hypertension',
    'Pulmonary-Arterial-Hypertension': 'Management of Pulmonary Arterial Hypertension',
    'CVD Prevention':     'Primary & Secondary Prevention of Cardiovascular Disease',
    'Dyslipidaemia':      'Management of Dyslipidaemia',
    'Dyslipidemia':       'Management of Dyslipidaemia',
    'Heart-Disease-in-Pregnancy': 'Management of Heart Disease in Pregnancy',
    // Hypertension & Stroke
    'Hypertension':       'Management of Hypertension',
    'HTN':                'Management of Hypertension',
    'Stroke':             'Management of Ischaemic Stroke',
    'Ischaemic Stroke':   'Management of Ischaemic Stroke',
    'Ischaemic-Stroke':   'Management of Ischaemic Stroke',
    // Endocrine
    'T2DM':               'Management of Type 2 Diabetes Mellitus',
    'Type-2-Diabetes':    'Management of Type 2 Diabetes Mellitus',
    'T1DM':               'Management of Type 1 Diabetes Mellitus',
    'Diabetes in Pregnancy': 'Management of Diabetes in Pregnancy',
    'Diabetes-in-Pregnancy': 'Management of Diabetes in Pregnancy',
    'Thyroid':            'Management of Thyroid Disorders',
    'Thyroid-Disorders':  'Management of Thyroid Disorders',
    'Erectile Dysfunction': 'Management of Erectile Dysfunction',
    'Erectile-Dysfunction': 'Management of Erectile Dysfunction',
    'Growth Hormone':     'Use of Growth Hormone',
    'Growth-Hormone':     'Use of Growth Hormone',
    'Obesity':            'Management of Obesity',
    'Obesity-Management': 'Management of Obesity',
    // Oncology
    'Cancer Pain':        'Management of Cancer Pain',
    'Cancer-Pain':        'Management of Cancer Pain',
    'Breast Cancer':      'Management of Breast Cancer',
    'Breast-Carcinoma':   'Management of Breast Cancer',
    'Colorectal':         'Management of Colorectal Carcinoma',
    'Colorectal-Carcinoma': 'Management of Colorectal Carcinoma',
    'Cervical Cancer':    'Management of Cervical Cancer',
    'Cervical-Carcinoma': 'Management of Cervical Cancer',
    'Nasopharyngeal':     'Management of Nasopharyngeal Carcinoma',
    'Nasopharyngeal-Carcinoma': 'Management of Nasopharyngeal Carcinoma',
    // Anaesthesia
    'Pre-Anaesthetic':    'Pre-Anaesthetic Assessment',
    'Pre-Anaesthetic-Assessment': 'Pre-Anaesthetic Assessment',
    'Medication Safety':  'Safe Use of Medications in Anaesthesia',
    'Medication-Safety-In-Anaesthesia': 'Safe Use of Medications in Anaesthesia',
  };

  const resolveCpgFullName = (shortName) => {
    if (!shortName) return shortName;
    // Direct lookup
    if (CPG_FULL_NAMES[shortName]) return CPG_FULL_NAMES[shortName];
    // Try stripping "CPG " prefix
    const stripped = shortName.replace(/^CPG\s+/i, '').trim();
    if (CPG_FULL_NAMES[stripped]) return CPG_FULL_NAMES[stripped];
    // Try case-insensitive
    const lower = stripped.toLowerCase();
    for (const [k, v] of Object.entries(CPG_FULL_NAMES)) {
      if (k.toLowerCase() === lower) return v;
    }
    // Fallback: clean up the raw name (replace hyphens, strip edition tags for display)
    return stripped.replace(/-/g, ' ').replace(/\(.*?\)/g, '').trim() || shortName;
  };

  // Parse a raw cpg_source string into structured fields for the reference card.
  // Example: "CPG PCI §3.2 [chunk 1] — antiplatelet loading before PCI"
  const parseCpgSource = (src, rationale, intervention) => {
    if (!src) return null;
    if (/^no specific cpg/i.test(src.trim())) return null;
    if (/^No loaded CPG/i.test(src.trim())) return null;

    // Extract section (§x.x or Section x.x)
    const sectionMatch = src.match(/§([\d.]+[)\]]?)|Section\s([\d.]+)/i);
    const sectionNum = sectionMatch ? (sectionMatch[1] || sectionMatch[2] || '').replace(/[)\]]/g, '') : null;

    // Extract chunk ID (kept internally for linking, hidden from display)
    const chunkMatch = src.match(/\[chunk\s*(\d+)\]/i);
    const chunkId = chunkMatch ? parseInt(chunkMatch[1]) : null;

    // Extract CPG short name: everything between "CPG " and the first § or [ or —
    const cpgNameMatch = src.match(/^(?:CPG\s+)?(.+?)(?:\s*§|\s*\[|\s*—|\s*Section\s)/i);
    const cpgShortName = cpgNameMatch
      ? cpgNameMatch[1].replace(/\[chunk\s*\d+\]/gi, '').trim()
      : src.replace(/§.*|Section\s.*|\[.*|—.*/gi, '').replace(/^CPG\s+/i, '').trim();

    const fullName = resolveCpgFullName(cpgShortName);

    // Build human-readable section label
    const sectionLabel = sectionNum ? `Section ${sectionNum}` : null;

    // Build clean display title
    const displayTitle = sectionLabel ? `${fullName} — ${sectionLabel}` : fullName;

    // Structured evidence tiers — each tier maps to a hierarchy level in the CPG chunk tree.
    // matchedClause  = the exact CPG text the vector search matched (always available)
    // sectionContext = the H2 subsection containing the clause (available for H3 hits)
    // broaderContext = the H1 parent chapter (with gap marker where the H2 section was)
    let matchedClause = null;
    let sectionContext = null;
    let broaderContext = null;
    // Keep originalText as a backward-compat fallback for any other consumers
    let originalText = null;
    if (chunkId && Array.isArray(evidence) && chunkId > 0 && chunkId <= evidence.length) {
      const chunk = evidence[chunkId - 1];
      if (chunk) {
        matchedClause = chunk.content || null;
        sectionContext = chunk.section_content || null;
        broaderContext = chunk.parent_content || null;
        // Legacy flat string (backward compat)
        if (chunk.parent_content) {
          originalText = chunk.section_content
            ? `Section Context:\n${chunk.section_content}\n\nParent Section Context:\n${chunk.parent_content}\n\nMatched Clause:\n${chunk.content}`
            : `Parent Section Context:\n${chunk.parent_content}\n\nMatched Clause:\n${chunk.content}`;
        } else {
          originalText = chunk.content;
        }
      }
    }

    return {
      raw: src,
      cpgShortName,
      cpgFullName: fullName,
      displayTitle,
      section: sectionLabel,
      sectionNum,
      chunkId,
      // The rationale is the clinical reasoning — what the clinician needs to understand
      // WHY this evidence applies. The inline note (after " — ") is a brief LLM summary.
      context: rationale || null,
      // Structured evidence tiers (new — used by the redesigned CpgReferenceCard)
      matchedClause,
      sectionContext,
      broaderContext,
      // Legacy flat string (backward compat)
      originalText: originalText,
      // Track which recommendation uses this ref
      usedBy: intervention ? [intervention] : [],
    };
  };

  // Collect CPG references from all recommendations, grouped by CPG guideline name.
  // Each unique cpg_source becomes a ref; refs are grouped by cpgFullName.
  const cpgRefMap = new Map(); // key = raw src, value = structured ref
  for (const r of allRecs) {
    const src = (r.cpg_source || '').trim();
    if (!src || /^no specific cpg/i.test(src) || /^No loaded CPG/i.test(src)) continue;
    if (!cpgRefMap.has(src)) {
      cpgRefMap.set(src, parseCpgSource(src, r.rationale, r.intervention));
    } else {
      // Same source cited by another recommendation — track the additional usage
      const existing = cpgRefMap.get(src);
      if (existing && r.intervention && !existing.usedBy.includes(r.intervention)) {
        existing.usedBy.push(r.intervention);
      }
    }
  }
  const allRefs = [...cpgRefMap.values()].filter(Boolean);

  // Group by CPG full name, preserving order
  const groupMap = new Map();
  for (const ref of allRefs) {
    const key = ref.cpgFullName;
    if (!groupMap.has(key)) {
      groupMap.set(key, { cpgFullName: key, refs: [] });
    }
    groupMap.get(key).refs.push(ref);
  }
  const cpgReferences = allRefs;              // flat list (backward compat)
  const cpgReferenceGroups = [...groupMap.values()]; // grouped

  return {
    clinicalSummary: plan.summary ?? '',
    icdPrimary: plan.icd_primary,
    icdAlternates: plan.icd_alternates,
    confidence: plan.confidence,
    cpgReferences,
    cpgReferenceGroups,
    medications: {
      start: byAction('start'),
      stop: byAction('stop'),
      change: byAction('change'),
      continue: byAction('continue'),
      contraindicated: byAction('contraindicated'),
    },
    interventions: interventionItems,
    lifestyle: lifestyleItems,
    referrals: referralItems,
    monitoring: (plan.monitoring ?? []).map((m, i) => ({
      id: i + 1,
      parameter: typeof m === 'string' ? m : m.parameter,
      schedule:  typeof m === 'string' ? null  : m.schedule,
      target:    typeof m === 'string' ? null  : (m.target ?? null),
      cpgRef:    typeof m === 'string' ? null  : (m.cpg_ref ?? null),
    })),
    redFlags: plan.red_flags,
    followUp: plan.follow_up ?? [],
    unresolvedQuestions: plan.unresolved_questions,
  };
}
