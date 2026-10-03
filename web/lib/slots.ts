/** Seer's four pick slots spell its name; each has its own pastel sheet. */
export const SLOT_LETTERS = ['S', 'E', 'E', 'R'] as const;
export const SLOT_BG = ['bg-lav', 'bg-butter', 'bg-sky', 'bg-stone'] as const;

export const slotLetter = (slot: number) => SLOT_LETTERS[(slot - 1) % 4];
export const slotBg = (slot: number) => SLOT_BG[(slot - 1) % 4];
