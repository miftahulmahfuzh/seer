/**
 * The prompt that turns one Gotrade "Order Summary" screenshot into JSON.
 *
 * Built on the rules that measured best in ~/run-insights (lib/llm/prompts/extraction.ts): a
 * system prompt of numbered rules that opens with "transcribe ONLY what is literally visible",
 * one user turn with a labelled image followed by the exact JSON shape LAST, and "Return ONLY a
 * JSON object" at the end. Unlike run-insights, the model converts NOTHING here: every value is
 * the printed text, and money.ts parses it. Copying "$1,063.886" is what a vision model does
 * best; turning it into 1063.886 is code's job, where it can be tested.
 *
 * If you change ORDER_SYSTEM_PROMPT or ORDER_SHAPE, re-run the live smoke script against the real
 * receipts before shipping (web/scripts/sean-vision-smoke.mjs).
 */

type VisionTextPart = { type: 'text'; text: string };
type VisionImagePart = { type: 'image_url'; image_url: { url: string } };
export type VisionContentPart = VisionTextPart | VisionImagePart;

export const ORDER_SYSTEM_PROMPT = `You transcribe ONE screenshot of the Gotrade app's "Order Summary" sheet into JSON.

RULES -- these matter more than anything else:
1. Transcribe ONLY what is literally visible. Never infer, never compute, never fill a
   plausible value. If a field is not visible, use null.
2. Read ONLY the white "Order Summary" card. Ignore the phone's status bar (its clock is not
   the order time), the dimmed screen behind the card, and the "Got it" button.
3. Copy every money value EXACTLY as printed, as a string: keep the "$", the "+" or "-" sign
   when one is printed, the thousands commas and EVERY decimal digit. "$1,063.886" stays
   "$1,063.886"; "-$0.15" stays "-$0.15". Never round, never drop a digit, never add one.
4. Copy share counts EXACTLY as printed, as a string, with every decimal digit:
   "0.026224614" stays "0.026224614"; "5" stays "5".
5. Copy "Date" and "Time" exactly as printed: "October 07, 2026" and "21:55 WIB".
6. The price row is labelled either "Average price" or "Execution price". Put that label in
   "priceLabel" and its value in "price".
7. Under "Average price" the sheet may list partial fills, one line each, like
   "· 0.38 shares" on the left and "@ $131.47" on the right. Copy every such line, in order,
   into "fills" as {"shares": "0.38", "price": "$131.47"}. When no such lines are printed,
   "fills" is an empty array [].
8. "Trading fee", "Regulatory fee" and "PPN" are three separate rows. Copy each with its sign.
9. "Net Profit" is printed only on some sells, below "Total". Copy its value with its sign if
   one is printed, and put the colour of that value's text in "netProfitColor" ("green" or
   "red"). When there is no Net Profit row, both are null.
10. If the picture is not a Gotrade Order Summary sheet, set "isOrderSummary" to false and every
   other field to null (fills: []).

Return ONLY a JSON object. No markdown fences, no commentary, no text before or after the
JSON object.`;

export const ORDER_SHAPE = `{
  "isOrderSummary": boolean,
  "status": string|null,          // "Filled"
  "date": string|null,            // "October 07, 2026"
  "time": string|null,            // "21:55 WIB"
  "orderType": string|null,       // "Market Buy", "Market Sell", "Limit Buy", ...
  "ticker": string|null,          // "PLTR"
  "priceLabel": string|null,      // "Average price" or "Execution price"
  "price": string|null,           // "$131.47"
  "fills": [ { "shares": string, "price": string } ],   // [] when no partial-fill lines
  "filledShares": string|null,    // "5.38"
  "tradeAmount": string|null,     // "$707.31"
  "tradingFee": string|null,      // "+$0.00"
  "regulatoryFee": string|null,   // "+$2.13"
  "ppn": string|null,             // "+$0.00"
  "total": string|null,           // "$709.44"
  "netProfit": string|null,       // "$22.31", sells only
  "netProfitColor": "green"|"red"|null
}`;

/** `data:image/jpeg;base64,...` from bare base64 (a data: prefix already there is kept). */
export function jpegDataUri(imageB64: string): string {
  return imageB64.startsWith('data:') ? imageB64 : `data:image/jpeg;base64,${imageB64}`;
}

/** The user turn: the labelled image, then the request and the shape, last. */
export function buildOrderUserContent(imageB64: string): VisionContentPart[] {
  return [
    { type: 'text', text: 'IMAGE -- Gotrade Order Summary screenshot:' },
    { type: 'image_url', image_url: { url: jpegDataUri(imageB64) } },
    {
      type: 'text',
      text: `This is ONE Gotrade Order Summary screenshot.\n\nReturn one JSON object with exactly this shape:\n${ORDER_SHAPE}`,
    },
  ];
}

/**
 * The repair note, sent after the model's first reply in the SAME conversation, with the image
 * still in it (vision.ts repairOrderWithFetch re-sends the user turn above). Deliberately NOT
 * run-insights' text-only repair: there the measured failure was a wrong shape, here the likely
 * failure is a misread digit that the arithmetic checks caught, and a model that cannot see the
 * picture again can only "fix" that by inventing a number that adds up. One receipt costs ~2,400
 * prompt tokens and 5-10 s (measured); a made-up fee in the owner's ledger costs more.
 */
export function buildRepairNote(issues: string): string {
  return (
    'Your last reply did not match the required JSON shape, or its numbers do not add up the way ' +
    'a Gotrade Order Summary always does. Look at the screenshot again and reply with ONLY the ' +
    'corrected JSON object, in exactly the same shape. Re-read the values the problems below ' +
    'point at, digit by digit, and copy them exactly as printed. Never change a value just to ' +
    'make the numbers add up.\n\nProblems found:\n' +
    issues
  );
}
