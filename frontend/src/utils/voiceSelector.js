/**
 * Voice Selector Utility for TRAVELMATE AI Text-to-Speech (TTS).
 *
 * Provides intelligent, multi-tiered voice selection optimized for a natural,
 * friendly female voice with an Indian English accent (similar in clarity and
 * warmth to Google Assistant).
 *
 * Selection Hierarchy:
 * - Tier 1: Natural Female Indian English (en-IN)
 *     Priority: Microsoft Neerja, Microsoft Heera, Google English (India), Veena,
 *     followed by any non-male Indian English voice.
 * - Tier 2: Natural / Neural Female English (Google Assistant & Edge Natural style)
 *     Priority: Microsoft Jenny Online (Natural), Microsoft Aria Online (Natural),
 *     Google UK English Female, Google US English (Chrome's natural female voice), Samantha, Karen.
 * - Tier 3: Standard Local Female English
 *     Priority: Microsoft Zira Desktop (clean, clear built-in Windows female voice),
 *     or any local female English voice.
 * - Tier 4: Any English voice that is NOT explicitly male/robotic.
 * - Tier 5: Browser default fallback.
 *
 * Strictly avoids robotic male voices (e.g. Microsoft David, Microsoft Mark).
 */

const MALE_INDICATORS = [
  'david',
  'mark',
  'guy',
  'george',
  'prabhat',
  'ravi',
  'richard',
  'james',
  'sean',
  'daniel',
  'stefan',
  'male',
  'boy',
  'man',
  'robotic',
];

const FEMALE_INDICATORS = [
  'female',
  'woman',
  'girl',
  'neerja',
  'heera',
  'veena',
  'aditi',
  'priya',
  'swara',
  'ananya',
  'kavya',
  'rani',
  'geeta',
  'sunita',
  'lata',
  'jenny',
  'aria',
  'sonia',
  'zira',
  'samantha',
  'karen',
  'victoria',
  'moira',
  'tessa',
  'hazel',
  'susan',
  'cora',
];

/**
 * Checks if a voice has male names or indicators.
 * Strictly distinguishes "male" and "man" from "female" and "woman".
 */
export function isMaleVoice(voice) {
  if (!voice) return false;
  const rawName = (voice.name || '').toLowerCase();

  // Strip 'female' and 'woman' before checking 'male' or 'man' to avoid false positives
  const sanitizedName = rawName.replace(/female/g, '').replace(/woman/g, '');

  return MALE_INDICATORS.some((m) => {
    if (m === 'male' || m === 'man') {
      return sanitizedName.includes(m);
    }
    return rawName.includes(m);
  });
}

/**
 * Checks if a voice has female names or indicators.
 */
export function isFemaleVoice(voice) {
  if (!voice) return false;
  const name = (voice.name || '').toLowerCase();
  return FEMALE_INDICATORS.some((f) => name.includes(f));
}

/**
 * Checks if a voice is an Indian English voice.
 */
export function isIndianEnglishVoice(voice) {
  if (!voice) return false;
  const lang = (voice.lang || '').toLowerCase().replace(/_/g, '-');
  const name = (voice.name || '').toLowerCase();

  return (
    lang === 'en-in' ||
    lang.startsWith('en-in-') ||
    (name.includes('india') && (lang.startsWith('en') || name.includes('english')))
  );
}

/**
 * Selects the optimal natural female voice from available browser voices.
 *
 * @param {SpeechSynthesisVoice[]} voiceList - List of voices from window.speechSynthesis.getVoices()
 * @returns {SpeechSynthesisVoice|null} Best matching natural female voice
 */
export function selectPreferredVoice(voiceList) {
  if (!Array.isArray(voiceList) || voiceList.length === 0) {
    return null;
  }

  // Tier 1A: Specific high-priority Indian English female voices
  const tier1Named = [
    'microsoft neerja online (natural)',
    'microsoft neerja',
    'microsoft heera',
    'google english (india)',
    'google en-in',
    'veena',
  ];
  for (const target of tier1Named) {
    const matched = voiceList.find((v) => (v.name || '').toLowerCase().includes(target));
    if (matched) return matched;
  }

  // Tier 1B: Any Indian English voice with female indicator (and not male)
  const indianFemale = voiceList.find(
    (v) => isIndianEnglishVoice(v) && isFemaleVoice(v) && !isMaleVoice(v)
  );
  if (indianFemale) return indianFemale;

  // Tier 1C: Any Indian English voice that is not male
  const indianNonMale = voiceList.find(
    (v) => isIndianEnglishVoice(v) && !isMaleVoice(v)
  );
  if (indianNonMale) return indianNonMale;

  // Tier 2: Natural / Neural Female English (Chrome & Edge Natural voices)
  const tier2Named = [
    'microsoft jenny online (natural)',
    'microsoft aria online (natural)',
    'microsoft sonia online (natural)',
    'google uk english female',
    'google us english', // Clean, friendly Google Assistant voice in Chrome
    'samantha',
    'karen',
    'victoria',
  ];
  for (const target of tier2Named) {
    const matched = voiceList.find((v) => (v.name || '').toLowerCase().includes(target));
    if (matched) return matched;
  }

  // Tier 3: Standard Local Female English (e.g. Microsoft Zira on Windows)
  const zira = voiceList.find((v) => (v.name || '').toLowerCase().includes('zira'));
  if (zira) return zira;

  const localFemale = voiceList.find(
    (v) => (v.lang || '').toLowerCase().startsWith('en') && isFemaleVoice(v) && !isMaleVoice(v)
  );
  if (localFemale) return localFemale;

  // Tier 4: Any English voice that is NOT male / robotic
  const nonMaleEnglish = voiceList.find(
    (v) => (v.lang || '').toLowerCase().startsWith('en') && !isMaleVoice(v)
  );
  if (nonMaleEnglish) return nonMaleEnglish;

  // Tier 5: Any English voice
  const anyEnglish = voiceList.find((v) => (v.lang || '').toLowerCase().startsWith('en'));
  if (anyEnglish) return anyEnglish;

  return voiceList[0] || null;
}

/**
 * Conversational speech tuning parameters for warm, articulate, friendly delivery.
 */
export const CONVERSATIONAL_VOICE_SETTINGS = {
  rate: 0.98,  // Clear, articulate pacing for travel dates, prices, and flight details
  pitch: 1.05, // Slightly warm, upbeat intonation resembling Google Assistant
  volume: 1.0, // Full clear volume
};
