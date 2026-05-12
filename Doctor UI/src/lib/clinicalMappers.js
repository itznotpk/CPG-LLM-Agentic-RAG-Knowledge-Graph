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

  // Split pharmacological recommendations by action field
  const byAction = (action) => pharmacological
    .filter(r => (r.action ?? 'start') === action)
    .map((r, i) => ({
      id: i + 1,
      name: r.intervention,
      reason: r.rationale,
      cpgRef: r.cpg_source,
      evidenceGrade: r.evidence_grade || null,
      accepted: true,
    }));

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

  const referralItems = referrals.map((r, i) => ({
    id: i + 1,
    specialty: r.intervention,
    reason: r.rationale,
    cpgRef: r.cpg_source,
    accepted: true,
  }));

  // Collect unique CPG source strings across all recommendations
  const allRecs = plan.recommendations ?? [];
  const cpgSourceSet = new Set(
    allRecs.map((r) => r.cpg_source).filter(Boolean)
  );
  const cpgReferences = [...cpgSourceSet].map((src) => ({ title: src }));

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
