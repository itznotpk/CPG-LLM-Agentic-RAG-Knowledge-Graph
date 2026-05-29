// Shared pure helpers — no React, no side-effects, importable anywhere.

/**
 * Safely parse a value that may be a JSONB array (already parsed), a JSON
 * string, or null/undefined. Always returns an array.
 */
export function safeJson(val) {
  if (!val) return [];
  if (Array.isArray(val)) return val;
  try { return JSON.parse(val); } catch { return []; }
}

/**
 * Return 2-character uppercase initials from a full name.
 */
export function getInitials(name) {
  if (!name) return 'P';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.substring(0, 2).toUpperCase();
}

const LIGHT_AVATAR_COLORS = [
  'bg-teal-100 text-teal-800',
  'bg-slate-200 text-slate-800',
  'bg-sky-100 text-sky-800',
  'bg-amber-100 text-amber-800',
  'bg-rose-100 text-rose-800',
  'bg-indigo-100 text-indigo-800',
];

const DARK_AVATAR_COLORS = [
  'bg-teal-900/50 text-teal-200',
  'bg-slate-800 text-slate-200',
  'bg-sky-900/50 text-sky-200',
  'bg-amber-900/50 text-amber-200',
  'bg-rose-900/50 text-rose-200',
  'bg-indigo-900/50 text-indigo-200',
];

/** Hash-based avatar colour for a name string. */
export function getAvatarColor(name, isDark = false) {
  const palette = isDark ? DARK_AVATAR_COLORS : LIGHT_AVATAR_COLORS;
  if (!name) return palette[0];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return palette[Math.abs(hash) % palette.length];
}

/** Gender-aware avatar colour (male → sky, female → rose, other → teal). */
export function getPatientAvatarColor(gender) {
  const g = typeof gender === 'string' ? gender.toLowerCase() : '';
  if (g.startsWith('f')) return 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200';
  if (g.startsWith('m')) return 'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200';
  return 'bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-200';
}
