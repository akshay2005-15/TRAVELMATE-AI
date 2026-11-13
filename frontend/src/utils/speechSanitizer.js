/**
 * Speech Sanitizer Utility for TRAVELMATE AI Text-to-Speech (TTS).
 * Converts structured markdown, flight listings, timestamps, and symbols into
 * natural, clean, fluent spoken English.
 *
 * Rules:
 * - Omits technical metadata (e.g. `[SIMULATION / MOCK OFFER]`, provider status lines).
 * - Strips markdown symbols (**, *, #, bullet points, brackets, backticks).
 * - Converts currency codes (INR -> rupees, USD -> dollars).
 * - Formats flight schedules conversationally (Departure: 11:30 AM -> "departs at 11:30 AM").
 * - Avoids reading out raw symbols like emojis, pipes (|), bullets (•).
 * - Keeps spoken output concise so multi-flight tables don't overwhelm audio.
 */

export function sanitizeTextForSpeech(rawText) {
  if (!rawText || typeof rawText !== 'string') return '';

  let text = rawText;

  // 1. Remove Provider / Simulation status lines completely
  text = text.replace(/⚡\s*\*\*Provider Status:\*\*.*$/gim, '');
  text = text.replace(/✈️\s*\*\*Provider Status:\*\*.*$/gim, '');
  text = text.replace(/\[(?:SIMULATION|MOCK OFFER|DUFFEL TEST SANDBOX|LIVE VERIFIED)[^\]]*\]/gi, '');

  // 2. Normalize and format Currency codes into natural spoken words
  text = text.replace(/\bINR\s*([\d,]+(?:\.\d{2})?)\b/gi, '$1 rupees');
  text = text.replace(/\bUSD\s*([\d,]+(?:\.\d{2})?)\b/gi, '$1 dollars');
  text = text.replace(/\bEUR\s*([\d,]+(?:\.\d{2})?)\b/gi, '$1 euros');
  text = text.replace(/\bGBP\s*([\d,]+(?:\.\d{2})?)\b/gi, '$1 pounds');
  text = text.replace(/₹\s*([\d,]+)/g, '$1 rupees');
  text = text.replace(/\$\s*([\d,]+)/g, '$1 dollars');

  // Remove .00 decimals in spoken prices (e.g., 5,400.00 -> 5,400)
  text = text.replace(/([\d,]+)\.00\s*(rupees|dollars|euros|pounds)/gi, '$1 $2');

  // 3. Clean flight listing bullet points and flight headers
  // Convert: "**1. IndiGo 6E-2054** — **5,400 rupees** *(...)*" -> "Option 1: IndiGo 6E-2054 for 5,400 rupees."
  text = text.replace(/\*\*(\d+)\.\s*([^*]+?)\*\*\s*[—–-]\s*\*\*([^*]+?)\*\*(?:\s*\*\(.*?\)\*)?/gi, 'Option $1: $2 for $3.');

  // Convert flight details: "• Departure: 11:30 AM | Arrival: 02:15 PM (2h 45m, Non-stop)"
  text = text.replace(/[•*-]\s*Departure:\s*([^|\n]+)\s*\|\s*Arrival:\s*([^(\n]+)(?:\(([^)]+)\))?/gi, (_, dep, arr, details) => {
    let extra = details ? `, ${details.replace('Non-stop', 'non-stop')}` : '';
    return `Departs at ${dep.trim()}, arrives at ${arr.trim()}${extra}.`;
  });

  // Remove cabin class and baggage metadata bullet lines to keep speech concise
  text = text.replace(/[•*-]\s*Class:[^\n]*/gi, '');

  // 4. Remove emojis, pictographs, and variation selectors
  text = text.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}]/gu, '');
  text = text.replace(/[•*|`_#~<>]/g, ' ');

  // 5. Clean up markdown bold/italic remnants
  text = text.replace(/\*\*(.*?)\*\*/g, '$1');
  text = text.replace(/\*(.*?)\*/g, '$1');

  // 6. Clean punctuation & excessive spaces
  text = text.replace(/\s+/g, ' ');
  text = text.replace(/\s+([.,?!])/g, '$1');
  text = text.replace(/(\.\s*)+/g, '. ');
  text = text.replace(/\(\s*\)/g, '');

  return text.trim();
}
