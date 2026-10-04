import type { Engine } from './strategy';

/** Seer's four pick slots spell its name; each has its own pastel sheet. Only bracket strategies have slots. */
export const SLOT_LETTERS = ['S', 'E', 'E', 'R'] as const;
export const SLOT_BG = ['bg-lav', 'bg-butter', 'bg-sky', 'bg-stone'] as const;
export const BRACKET_SLOTS = 4;

/** 0..3 for any integer, negatives included. */
const wrap = (i: number) => ((Math.trunc(i) % 4) + 4) % 4;

export const slotLetter = (slot: number) => SLOT_LETTERS[wrap(slot - 1)];
export const slotBg = (slot: number) => SLOT_BG[wrap(slot - 1)];

/** Pick slots a strategy fills: 4 for bracket strategies, none for book and benchmark strategies. */
export const slotCount = (engine: Engine) => (engine === 'bracket' ? BRACKET_SLOTS : 0);

/** A card's pastel sheet: its slot's sheet when it has a slot, else cycled by its 0-based place in the list. */
export const cardBg = (slot: number | null, index: number) => (slot === null ? SLOT_BG[wrap(index)] : slotBg(slot));
