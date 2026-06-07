/**
 * Unit tests for the pure UI helpers.
 *
 * safeJson is the JSONB-array guard used across the Supabase read path: a column
 * may arrive already-parsed (array), as a JSON string, or NULL. It must never
 * throw and must always return an array, or downstream `.map()` calls crash.
 */
import { describe, it, expect } from 'vitest';
import { safeJson, getInitials, getAvatarColor, getPatientAvatarColor } from './helpers';

describe('safeJson', () => {
  it('returns an already-parsed array unchanged', () => {
    expect(safeJson(['a', 'b'])).toEqual(['a', 'b']);
  });
  it('parses a JSON-array string', () => {
    expect(safeJson('[1,2,3]')).toEqual([1, 2, 3]);
  });
  it('returns [] for null / undefined / empty', () => {
    expect(safeJson(null)).toEqual([]);
    expect(safeJson(undefined)).toEqual([]);
    expect(safeJson('')).toEqual([]);
  });
  it('returns [] for malformed JSON instead of throwing', () => {
    expect(safeJson('{not json')).toEqual([]);
  });
});

describe('getInitials', () => {
  it('takes first + last initial for a full name', () => {
    expect(getInitials('Ahmad Bin Ismail')).toBe('AI');
  });
  it('takes the first two letters of a single name', () => {
    expect(getInitials('Siti')).toBe('SI');
  });
  it('defaults to P for an empty name', () => {
    expect(getInitials('')).toBe('P');
  });
});

describe('avatar colours', () => {
  it('getAvatarColor is deterministic for the same name', () => {
    expect(getAvatarColor('Lim Wei')).toBe(getAvatarColor('Lim Wei'));
  });
  it('getPatientAvatarColor is gender-aware (f → rose, m → sky, other → teal)', () => {
    expect(getPatientAvatarColor('female')).toContain('rose');
    expect(getPatientAvatarColor('male')).toContain('sky');
    expect(getPatientAvatarColor('')).toContain('teal');
  });
});
