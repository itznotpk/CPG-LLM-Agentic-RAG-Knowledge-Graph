/**
 * Supabase migration-contract smoke tests (offline, static).
 *
 * These do NOT touch a live database. They parse the migration SQL and the
 * `updateConsultation` call site and assert the invariants that have actually
 * broken this RPC before (see CLAUDE.md "update_consultation RPC overload trap"):
 *
 *  1. SUPERSET CHAIN — each successive migration's update_consultation signature
 *     is a superset of the previous one. A migration that drops a param silently
 *     breaks callers that still pass it (PostgREST 42883 "function not found",
 *     or a silent no-op when an overload still matches).
 *  2. DROP-ALL-OVERLOADS — the latest migration removes every overload via the
 *     pg_proc loop (not a hand-listed DROP), so the unqualified GRANT can't fail
 *     with 42725 "function name is not unique".
 *  3. BACKEND-CALLED PARAMS RETAINED — p_pipeline_timings / p_request_id stay
 *     (db_utils.save_pipeline_timings calls them by name).
 *  4. JS↔SQL CONTRACT — every p_* key the frontend sends exists in the latest
 *     signature.
 *  5. SCHEMA GOTCHA — p_consultation_id is INTEGER, not UUID.
 *
 * A live round-trip integration test (start → update → read-back) remains a
 * separate, planned tier — it needs a disposable test project, not the prod DB.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const sqlDir = resolve(__dirname, '../../supabase');
const readSql = (name) => readFileSync(resolve(sqlDir, name), 'utf8');
const readSrc = (name) => readFileSync(resolve(__dirname, name), 'utf8');

/** Pull the p_* parameter names out of a `CREATE OR REPLACE FUNCTION update_consultation(...)` block. */
function rpcSignatureParams(sql) {
  const m = sql.match(/CREATE OR REPLACE FUNCTION\s+update_consultation\s*\(([\s\S]*?)\)\s*RETURNS/i);
  if (!m) return [];
  return [...m[1].matchAll(/\b(p_[a-z_]+)\b/gi)].map((x) => x[1].toLowerCase());
}

/** Pull the p_* keys passed by the `.rpc('update_consultation', { ... })` call in supabase.js. */
function jsRpcKeys(js) {
  const m = js.match(/\.rpc\(\s*['"]update_consultation['"]\s*,\s*\{([\s\S]*?)\}\s*\)/);
  if (!m) return [];
  return [...m[1].matchAll(/\b(p_[a-z_]+)\s*:/gi)].map((x) => x[1].toLowerCase());
}

const flagsParams    = rpcSignatureParams(readSql('add_safety_flags.sql'));
const timingsParams  = rpcSignatureParams(readSql('add_pipeline_timings.sql'));
const ackSql         = readSql('add_safety_acknowledgement.sql');
const ackParams      = rpcSignatureParams(ackSql);
const jsKeys         = jsRpcKeys(readSrc('supabase.js'));

describe('update_consultation — signature superset chain', () => {
  it('each migration parses a non-empty signature (parser sanity)', () => {
    expect(flagsParams.length).toBeGreaterThan(10);
    expect(timingsParams.length).toBeGreaterThan(flagsParams.length - 1);
    expect(ackParams.length).toBeGreaterThan(timingsParams.length - 1);
  });

  it('pipeline_timings migration is a superset of safety_flags migration', () => {
    for (const p of flagsParams) expect(timingsParams).toContain(p);
  });

  it('safety_acknowledgement migration (latest) is a superset of pipeline_timings migration', () => {
    for (const p of timingsParams) expect(ackParams).toContain(p);
  });

  it('the latest signature adds the four acknowledgement params', () => {
    for (const p of ['p_safe_to_proceed', 'p_safety_acknowledged', 'p_safety_acknowledged_by', 'p_safety_acknowledged_at']) {
      expect(ackParams).toContain(p);
    }
  });

  it('RETAINS the backend-called params (db_utils calls these by name)', () => {
    expect(ackParams).toContain('p_pipeline_timings');
    expect(ackParams).toContain('p_request_id');
  });
});

describe('update_consultation — overload-trap guards', () => {
  it('drops EVERY overload via the pg_proc loop, not a hand-listed DROP', () => {
    expect(ackSql).toMatch(/FROM\s+pg_proc/i);
    expect(ackSql).toMatch(/proname\s*=\s*'update_consultation'/i);
    expect(ackSql).toMatch(/DROP FUNCTION/i);
  });

  it('re-grants EXECUTE to anon and authenticated after the rebuild', () => {
    expect(ackSql).toMatch(/GRANT EXECUTE ON FUNCTION update_consultation TO anon/i);
    expect(ackSql).toMatch(/GRANT EXECUTE ON FUNCTION update_consultation TO authenticated/i);
  });

  it('adds the new columns idempotently (ADD COLUMN IF NOT EXISTS)', () => {
    expect(ackSql).toMatch(/ADD COLUMN IF NOT EXISTS\s+safe_to_proceed/i);
    expect(ackSql).toMatch(/ADD COLUMN IF NOT EXISTS\s+safety_acknowledged_by/i);
  });
});

describe('update_consultation — JS↔SQL call contract', () => {
  it('parses the frontend call keys (sanity)', () => {
    expect(jsKeys).toContain('p_consultation_id');
    expect(jsKeys.length).toBeGreaterThan(10);
  });

  it('every key the frontend sends exists in the latest RPC signature', () => {
    for (const k of jsKeys) expect(ackParams).toContain(k);
  });

  it('the frontend does NOT send p_patient_education (column dropped 2026-06-02)', () => {
    expect(jsKeys).not.toContain('p_patient_education');
  });
});

describe('schema gotcha', () => {
  it('p_consultation_id is INTEGER, not UUID (consultations.id is INTEGER)', () => {
    expect(ackSql).toMatch(/p_consultation_id\s+INTEGER/i);
    expect(ackSql).not.toMatch(/p_consultation_id\s+UUID/i);
  });
});
