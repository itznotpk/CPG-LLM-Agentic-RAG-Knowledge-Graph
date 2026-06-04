# Doctor UI Design System

## Aesthetic Direction
**Clinical Luxury / Trustworthy Healthcare**
A refined, modern medical interface that feels expensive and highly reliable. Clean lines, intentional typography, and a calming yet distinct palette.

## Typography
- **Primary/Body**: `Geist` (clean, highly legible, modern)
- **Monospace**: `Geist Mono` (for data, codes, dosages)
- *Note: Inter is strictly banned.*

## Color Palette
- **Backgrounds**: Slate neutrals (`slate-50` to `slate-100` for light mode, `slate-800` to `slate-900` for dark mode).
- **Primary Accent**: Muted Emerald / Teal (`teal-500` to `teal-600`). Conveys health, trust, and cleanliness without feeling like generic Tailwind cyan.
- **Shadows**: Tinted slate shadows, no pure black drops.

## Layout & Components
- **Heroes & Headers**: Asymmetric or balanced grids. Avoid centered generic headers.
- **Feature/Data Sections**: Use Bento grids or `divide-y` rows for dense data (like patient vitals). Avoid 3-equal-card marketing rows.
- **Containers**: `max-w-7xl` or custom `max-w-[1400px]`, heavily utilizing CSS grid.

## Motion
- Spring physics for interactions. No linear easing for UI elements.
- Hover states should lift and cast a tinted shadow.

## Data Rules
- **NO GENERIC DATA**: Avoid "John Doe", "Acme", etc. Use realistic clinical placeholders (e.g., "Patient: Mei Ling", "Diagnosis: Type II Diabetes").

*This file acts as the project's persistent design memory.*
