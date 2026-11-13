/**
 * Client-side validation helpers for user registration.
 * Ensures passwords match, satisfy length criteria, and prevents unsafe submissions.
 */

export function validateRegistrationForm({ fullName, email, password, confirmPassword }) {
  if (!fullName || !fullName.trim()) {
    return { isValid: false, error: 'Full name is required.' };
  }

  if (!email || !email.trim()) {
    return { isValid: false, error: 'Email address is required.' };
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.trim())) {
    return { isValid: false, error: 'Please enter a valid email address.' };
  }

  if (!password || password.length < 8) {
    return { isValid: false, error: 'Password must be at least 8 characters long.' };
  }

  if (password !== confirmPassword) {
    return { isValid: false, error: 'Passwords do not match.' };
  }

  return { isValid: true, error: null };
}

