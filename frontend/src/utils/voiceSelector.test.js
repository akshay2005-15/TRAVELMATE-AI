import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  selectPreferredVoice,
  isMaleVoice,
  isFemaleVoice,
  isIndianEnglishVoice,
  CONVERSATIONAL_VOICE_SETTINGS,
} from './voiceSelector.js';

describe('Voice Selector - Natural Female Indian English Preference', () => {
  test('strictly prefers Microsoft Neerja Online (Natural) when available in Edge/Windows', () => {
    const voices = [
      { name: 'Microsoft David Desktop - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Zira Desktop - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Neerja Online (Natural) - English (India)', lang: 'en-IN' },
      { name: 'Microsoft Jenny Online (Natural) - English (United States)', lang: 'en-US' },
    ];

    const selected = selectPreferredVoice(voices);
    assert.ok(selected);
    assert.equal(selected.name, 'Microsoft Neerja Online (Natural) - English (India)');
  });

  test('prefers Google English (India) when available in Google Chrome', () => {
    const voices = [
      { name: 'Microsoft David Desktop - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Zira Desktop - English (United States)', lang: 'en-US' },
      { name: 'Google US English', lang: 'en-US' },
      { name: 'Google UK English Female', lang: 'en-GB' },
      { name: 'Google English (India)', lang: 'en-IN' },
    ];

    const selected = selectPreferredVoice(voices);
    assert.ok(selected);
    assert.equal(selected.name, 'Google English (India)');
  });

  test('selects Veena on Apple/macOS systems', () => {
    const voices = [
      { name: 'Alex', lang: 'en-US' },
      { name: 'Samantha', lang: 'en-US' },
      { name: 'Veena', lang: 'en-IN' },
      { name: 'Daniel', lang: 'en-GB' },
    ];

    const selected = selectPreferredVoice(voices);
    assert.ok(selected);
    assert.equal(selected.name, 'Veena');
  });

  test('selects female en-IN voice on mobile/Android devices', () => {
    const voices = [
      { name: 'en-us-x-sfg#male_1-local', lang: 'en-US' },
      { name: 'en-in-x-cxx#female_1-local', lang: 'en-IN' },
      { name: 'en-gb-x-rjs#male_1-local', lang: 'en-GB' },
    ];

    const selected = selectPreferredVoice(voices);
    assert.ok(selected);
    assert.equal(selected.name, 'en-in-x-cxx#female_1-local');
  });

  test('selects non-male en-IN voice when explicit female name is not present', () => {
    const voices = [
      { name: 'Microsoft David Desktop - English (United States)', lang: 'en-US' },
      { name: 'English India Standard Voice', lang: 'en-IN' },
      { name: 'Microsoft Mark Desktop - English (United States)', lang: 'en-US' },
    ];

    const selected = selectPreferredVoice(voices);
    assert.ok(selected);
    assert.equal(selected.name, 'English India Standard Voice');
  });
});

describe('Voice Selector - Fallback Hierarchy & Robotic Voice Elimination', () => {
  test('never selects robotic male voices (David/Mark) when Zira is available on Windows', () => {
    const standardWindowsVoices = [
      { name: 'Microsoft David Desktop - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Zira Desktop - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Mark Desktop - English (United States)', lang: 'en-US' },
    ];

    const selected = selectPreferredVoice(standardWindowsVoices);
    assert.ok(selected);
    assert.equal(selected.name, 'Microsoft Zira Desktop - English (United States)');
    assert.notEqual(selected.name, 'Microsoft David Desktop - English (United States)');
    assert.notEqual(selected.name, 'Microsoft Mark Desktop - English (United States)');
  });

  test('falls back to Google natural female voices in Chrome when Indian voice is absent', () => {
    const chromeWithoutIndia = [
      { name: 'Microsoft David Desktop - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Zira Desktop - English (United States)', lang: 'en-US' },
      { name: 'Google UK English Female', lang: 'en-GB' },
      { name: 'Google US English', lang: 'en-US' },
    ];

    const selected = selectPreferredVoice(chromeWithoutIndia);
    assert.ok(selected);
    assert.equal(selected.name, 'Google UK English Female');
  });

  test('falls back to Google US English female voice when UK female is absent', () => {
    const chromeUSOnly = [
      { name: 'Microsoft David Desktop - English (United States)', lang: 'en-US' },
      { name: 'Google US English', lang: 'en-US' },
      { name: 'Google UK English Male', lang: 'en-GB' },
    ];

    const selected = selectPreferredVoice(chromeUSOnly);
    assert.ok(selected);
    assert.equal(selected.name, 'Google US English');
  });

  test('falls back to Microsoft Jenny Online (Natural) in Edge when Indian voice is absent', () => {
    const edgeVoices = [
      { name: 'Microsoft David Desktop - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Guy Online (Natural) - English (United States)', lang: 'en-US' },
      { name: 'Microsoft Jenny Online (Natural) - English (United States)', lang: 'en-US' },
    ];

    const selected = selectPreferredVoice(edgeVoices);
    assert.ok(selected);
    assert.equal(selected.name, 'Microsoft Jenny Online (Natural) - English (United States)');
  });

  test('handles empty voice lists or null inputs without throwing errors', () => {
    assert.equal(selectPreferredVoice([]), null);
    assert.equal(selectPreferredVoice(null), null);
    assert.equal(selectPreferredVoice(undefined), null);
    assert.equal(selectPreferredVoice('not-an-array'), null);
  });
});

describe('Voice Selector - Gender and Accent Classification Helpers', () => {
  test('correctly identifies male and robotic voice names', () => {
    assert.equal(isMaleVoice({ name: 'Microsoft David Desktop' }), true);
    assert.equal(isMaleVoice({ name: 'Microsoft Mark Desktop' }), true);
    assert.equal(isMaleVoice({ name: 'Google UK English Male' }), true);
    assert.equal(isMaleVoice({ name: 'Microsoft Guy Online (Natural)' }), true);
    assert.equal(isMaleVoice({ name: 'Microsoft Ravi' }), true);
    assert.equal(isMaleVoice({ name: 'Microsoft Zira' }), false);
    assert.equal(isMaleVoice({ name: 'Microsoft Neerja' }), false);
  });

  test('correctly identifies female voice names', () => {
    assert.equal(isFemaleVoice({ name: 'Microsoft Neerja Online (Natural)' }), true);
    assert.equal(isFemaleVoice({ name: 'Microsoft Heera' }), true);
    assert.equal(isFemaleVoice({ name: 'Veena' }), true);
    assert.equal(isFemaleVoice({ name: 'Google UK English Female' }), true);
    assert.equal(isFemaleVoice({ name: 'Microsoft Zira Desktop' }), true);
    assert.equal(isFemaleVoice({ name: 'Microsoft Jenny Online (Natural)' }), true);
    assert.equal(isFemaleVoice({ name: 'Microsoft David Desktop' }), false);
  });

  test('correctly detects Indian English language tags and descriptors', () => {
    assert.equal(isIndianEnglishVoice({ name: 'Neerja', lang: 'en-IN' }), true);
    assert.equal(isIndianEnglishVoice({ name: 'Heera', lang: 'en_in' }), true);
    assert.equal(isIndianEnglishVoice({ name: 'Google English (India)', lang: 'en-US' }), true);
    assert.equal(isIndianEnglishVoice({ name: 'David', lang: 'en-US' }), false);
    assert.equal(isIndianEnglishVoice({ name: 'UK Female', lang: 'en-GB' }), false);
  });

  test('provides conversational speech settings for natural delivery', () => {
    assert.equal(CONVERSATIONAL_VOICE_SETTINGS.rate, 0.98);
    assert.equal(CONVERSATIONAL_VOICE_SETTINGS.pitch, 1.05);
    assert.equal(CONVERSATIONAL_VOICE_SETTINGS.volume, 1.0);
  });
});

