// ClearPath KG figure queries (Fig. 3.3c) - run in Neo4j Aura "Query" or Neo4j Browser.
// Nodes auto-caption by their `name` property. After it renders, drag nodes apart and
// use the panel's download/export icon to save PNG or SVG.

// ============================================================
// QUERY 1 - Safety-relationship sampler (schema-by-example).
// A few real examples of each safety-relevant edge. Compact and legible.
// ============================================================
MATCH p=(:Drug)-[:CONTRAINDICATED_WITH]->(:Condition) RETURN p LIMIT 4
UNION
MATCH p=(:Drug)-[:INTERACTS_WITH]->(:Drug) RETURN p LIMIT 3
UNION
MATCH p=(:Drug)-[:REQUIRES_MONITORING]->(:DiagnosticTool) RETURN p LIMIT 3
UNION
MATCH p=(:Condition)-[:REQUIRES_REFERRAL]->(:Specialty) RETURN p LIMIT 3
UNION
MATCH p=(:Drug)-[:FIRST_LINE_FOR]->(:Condition) RETURN p LIMIT 3;


// ============================================================
// QUERY 2 - Contraindication hub (the safety story). Many drugs
// converging on one condition via CONTRAINDICATED_WITH. Very clean star shape.
// Swap 'Pregnancy' for any condition.
// ============================================================
MATCH p=(d:Drug)-[:CONTRAINDICATED_WITH]->(c:Condition {name:'Pregnancy'})
RETURN p LIMIT 8;


// ============================================================
// QUERY 3 - Single-drug ego network. All safety-relevant edges around one drug.
// Swap 'Warfarin' for any drug name (case-sensitive, use the name shown on a node).
// ============================================================
MATCH p=(d:Drug {name:'Warfarin'})-[r]->(x)
WHERE type(r) IN ['CONTRAINDICATED_WITH','INTERACTS_WITH','REQUIRES_MONITORING','FIRST_LINE_FOR','CAUSES']
RETURN p LIMIT 15;
