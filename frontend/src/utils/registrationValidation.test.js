import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { validateRegistrationForm } from './registrationValidation.js';

describe('Registration Form Validation - Confirm Password & Requirements', () => {
  test('approves registration when password and confirm password match with >= 8 characters', () => {
    const res = validateRegistrationForm({
      fullName: 'Aarav Sharma',
      email: 'aarav@example.com',
      password: 'SecurePassword123!',
      confirmPassword: 'SecurePassword123!',
    });

    assert.equal(res.isValid, true);
    assert.equal(res.error, null);
  });

  test('rejects registration when password and confirm password do not match', () => {
    const res = validateRegistrationForm({
      fullName: 'Aarav Sharma',
      email: 'aarav@example.com',
      password: 'SecurePassword123!',
      confirmPassword: 'DifferentPassword456!',
    });

    assert.equal(res.isValid, false);
    assert.equal(res.error, 'Passwords do not match.');
  });

  test('strictly rejects case-mismatched passwords', () => {
    const res = validateRegistrationForm({
      fullName: 'Aarav Sharma',
      email: 'aarav@example.com',
      password: 'Password123!',
      confirmPassword: 'password123!',
    });

    assert.equal(res.isValid, false);
    assert.equal(res.error, 'Passwords do not match.');
  });

  test('rejects registration when password is shorter than 8 characters even if matching', () => {
    const res = validateRegistrationForm({
      fullName: 'Aarav Sharma',
      email: 'aarav@example.com',
      password: 'Pass1',
      confirmPassword: 'Pass1',
    });

    assert.equal(res.isValid, false);
    assert.equal(res.error, 'Password must be at least 8 characters long.');
  });

  test('rejects empty or whitespace-only name and email', () => {
    const resName = validateRegistrationForm({
      fullName: '   ',
      email: 'aarav@example.com',
      password: 'SecurePassword123!',
      confirmPassword: 'SecurePassword123!',
    });
    assert.equal(resName.isValid, false);
    assert.equal(resName.error, 'Full name is required.');

    const resEmail = validateRegistrationForm({
      fullName: 'Aarav Sharma',
      email: '   ',
      password: 'SecurePassword123!',
      confirmPassword: 'SecurePassword123!',
    });
    assert.equal(resEmail.isValid, false);
    assert.equal(resEmail.error, 'Email address is required.');
  });

  test('validates malformed email addresses', () => {
    const res = validateRegistrationForm({
      fullName: 'Aarav Sharma',
      email: 'invalid-email-address',
      password: 'SecurePassword123!',
      confirmPassword: 'SecurePassword123!',
    });
    assert.equal(res.isValid, false);
    assert.equal(res.error, 'Please enter a valid email address.');
  });
});

