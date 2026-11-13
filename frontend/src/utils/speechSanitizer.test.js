import { describe, it } from 'node:test';
import assert from 'node:assert';
import { sanitizeTextForSpeech } from './speechSanitizer.js';

describe('speechSanitizer', () => {
  it('handles null, undefined, or empty inputs gracefully', () => {
    assert.strictEqual(sanitizeTextForSpeech(null), '');
    assert.strictEqual(sanitizeTextForSpeech(undefined), '');
    assert.strictEqual(sanitizeTextForSpeech(''), '');
  });

  it('strips simulation status and provider metadata', () => {
    const raw = `⚡ **Provider Status:** Live verified via Duffel Sandbox.\n[SIMULATION / MOCK OFFER] We found 2 options.`;
    const cleaned = sanitizeTextForSpeech(raw);
    assert.doesNotMatch(cleaned, /Provider Status/i);
    assert.doesNotMatch(cleaned, /SIMULATION/i);
    assert.doesNotMatch(cleaned, /MOCK OFFER/i);
    assert.ok(cleaned.includes('We found 2 options.'));
  });

  it('converts currencies to spoken words and removes unnecessary .00 decimals', () => {
    const raw = `Total fare is INR 5,400.00 or USD 120.00 or ₹4500.`;
    const cleaned = sanitizeTextForSpeech(raw);
    assert.ok(cleaned.includes('5,400 rupees'));
    assert.ok(cleaned.includes('120 dollars'));
    assert.ok(cleaned.includes('4500 rupees'));
    assert.doesNotMatch(cleaned, /\.00\s*(rupees|dollars)/i);
  });

  it('converts flight listing cards to conversational spoken English', () => {
    const raw = `**1. IndiGo 6E-2054** — **INR 5,400** *(Cheapest)*\n• Departure: 11:30 AM | Arrival: 02:15 PM (2h 45m, Non-stop)\n• Class: ECONOMY`;
    const cleaned = sanitizeTextForSpeech(raw);
    assert.ok(cleaned.includes('Option 1: IndiGo 6E-2054 for 5,400 rupees.'));
    assert.ok(cleaned.includes('Departs at 11:30 AM, arrives at 02:15 PM, 2h 45m, non-stop.'));
    assert.doesNotMatch(cleaned, /Class:/i);
  });

  it('strips markdown symbols and emojis', () => {
    const raw = `✈️ Here are your **flights** for *tomorrow*! \`Fasten\` your seatbelt.`;
    const cleaned = sanitizeTextForSpeech(raw);
    assert.strictEqual(cleaned, 'Here are your flights for tomorrow! Fasten your seatbelt.');
  });

  it('preserves full assistant response with flight choices and prompt question', () => {
    const raw = `I found 2 morning flights from Bangalore (BLR) to Delhi (DEL) on November 17, 2026:

**1. IndiGo 6E-2054** — **INR 5,400** *(Cheapest)*
• Departure: 06:15 AM | Arrival: 09:00 AM (2h 45m, Non-stop)

**2. Air India AI-804** — **INR 6,100**
• Departure: 08:30 AM | Arrival: 11:15 AM (2h 45m, Non-stop)

Would you like me to book one of these flights?`;
    const cleaned = sanitizeTextForSpeech(raw);
    assert.ok(cleaned.includes('I found 2 morning flights'));
    assert.ok(cleaned.includes('Option 1: IndiGo 6E-2054 for 5,400 rupees.'));
    assert.ok(cleaned.includes('Departs at 06:15 AM, arrives at 09:00 AM, 2h 45m, non-stop.'));
    assert.ok(cleaned.includes('Option 2: Air India AI-804 for 6,100 rupees.'));
    assert.ok(cleaned.includes('Departs at 08:30 AM, arrives at 11:15 AM, 2h 45m, non-stop.'));
    assert.ok(cleaned.includes('Would you like me to book one of these flights?'));
  });
});

