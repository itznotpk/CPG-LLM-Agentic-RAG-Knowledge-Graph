export function mapDdxToDiagnosis(ddxList, cpgsMatched) {
  const differentials = ddxList.map((d, i) => ({
    id: i + 1,
    name: d.title,
    icdCode: d.code,
    probability: Math.round(d.similarity * 100),
    risk: d.similarity >= 0.75 ? 'high' : d.similarity >= 0.45 ? 'medium' : 'low',
    reasoning: d.reasoning || [],
    inclusionMatch: d.inclusion_match,
  }));

  return {
    differentials,
    topDiagnosis: differentials[0] || null,
    cpgsMatched: cpgsMatched || [],
  };
}

export function mapTreatmentPlanToCarePlan(plan) {
  const pharmacological = plan.recommendations.filter(r => r.type === 'pharmacological');
  const lifestyle       = plan.recommendations.filter(r => r.type === 'lifestyle');
  const referrals       = plan.recommendations.filter(r => r.type === 'referral');
  const investigations  = plan.recommendations.filter(r => r.type === 'investigation');
  const procedures      = plan.recommendations.filter(r => r.type === 'procedure');

  return {
    summary:     plan.summary ?? '',
    icdPrimary:  plan.icd_primary,
    medications: pharmacological.map(r => ({
      name:          r.intervention,
      action:        r.action || 'start',
      rationale:     r.rationale,
      cpgSource:     r.cpg_source,
      evidenceGrade: r.evidence_grade || null,
    })),
    lifestyle: lifestyle.map(r => ({
      goal:      r.intervention,
      rationale: r.rationale,
      cpgSource: r.cpg_source,
    })),
    referrals: referrals.map(r => ({
      specialty: r.intervention,
      reason:    r.rationale,
      cpgSource: r.cpg_source,
    })),
    investigations: [...investigations, ...procedures].map(r => ({
      name:      r.intervention,
      rationale: r.rationale,
      cpgSource: r.cpg_source,
    })),
    monitoring: (plan.monitoring ?? []).map(m => ({
      parameter: typeof m === 'string' ? m : m.parameter,
      schedule:  typeof m === 'string' ? null : m.schedule,
      target:    typeof m === 'string' ? null : (m.target ?? null),
      cpgRef:    typeof m === 'string' ? null : (m.cpg_ref ?? null),
    })),
    redFlags:   plan.red_flags ?? [],
    followUp:   plan.follow_up ?? [],
    unresolvedQuestions: plan.unresolved_questions ?? [],
    confidence: plan.confidence ?? null,
  };
}
