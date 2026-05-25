/**
 * Map ClinicalPlanResponse.ddx → diagnosis state shape for DiagnosisSection
 */
export function mapDdxToDiagnosis(ddxList, cpgsMatched) {
  const differentials = ddxList.map((d, i) => ({
    id: i + 1,
    name: d.title,
    icdCode: d.code,
    probability: Math.round(d.similarity * 100),
    risk: d.similarity >= 0.75 ? 'high' : d.similarity >= 0.45 ? 'medium' : 'low',
    reasoning: d.reasoning || [],       // LLM reasoning for display
    inclusionMatch: d.inclusion_match,
  }));

  return {
    differentials,
    selectedDiagnosisIds: differentials.length > 0 ? [differentials[0].id] : [],
    cpgsMatched,    // e.g. ["CPG AF Management", "CPG Hypertension"]
  };
}

/**
 * Map ClinicalPlanResponse.treatment_plan → carePlan state shape for CarePlanSection
 */
export function mapTreatmentPlanToCarePlan(plan) {
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

  const referralItems = referrals.map((r, i) => {
    const text = (r.intervention || '').toLowerCase();
    let urgency = 'Routine';
    if (text.includes('urgent')) urgency = 'Urgent';
    else if (text.includes('semi-urgent') || text.includes('prompt')) urgency = 'Semi-Urgent';
    
    return {
      id: i + 1,
      specialty: r.intervention,
      reason: r.rationale,
      urgency,
      cpgRef: r.cpg_source,
      accepted: true,
    };
  });

  // Collect unique CPG source strings across all recommendations
  const allRecs = plan.recommendations ?? [];
  const cpgSourceSet = new Set(
    allRecs.map((r) => r.cpg_source).filter(Boolean)
  );

  // Expand abbreviated CPG prefixes to full document titles.
  // Order matters: longer/more-specific prefixes must come first.
  const CPG_PREFIX_MAP = [
    ['CPG Heart Failure and Diabetes', 'CPG Heart Failure & Diabetes Mellitus'],
    ['CPG HF and Diabetes',            'CPG Heart Failure & Diabetes Mellitus'],
    ['CPG Heart Failure',              'CPG Management of Heart Failure (4th Edition)'],
    ['CPG HF',                         'CPG Management of Heart Failure (4th Edition)'],
    ['CPG T2DM',                       'CPG Type 2 Diabetes Mellitus (6th Edition)'],
  ];

  const expandCpgSource = (src) => {
    let result = src;
    for (const [abbrev, full] of CPG_PREFIX_MAP) {
      result = result.replaceAll(abbrev, full);
    }
    return result;
  };

  const cpgReferences = [...cpgSourceSet].map((src) => ({ title: expandCpgSource(src) }));

  return {
    clinicalSummary: plan.summary ?? '',
    icdPrimary: plan.icd_primary,
    icdAlternates: plan.icd_alternates,
    confidence: plan.confidence,
    cpgReferences,
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
