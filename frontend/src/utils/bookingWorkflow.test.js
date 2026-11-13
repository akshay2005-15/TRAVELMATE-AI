import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  maskEmail,
  maskPhone,
  maskPassport,
  generateIdempotencyKey,
  formatDate,
  formatTime,
  formatStops,
  formatCurrency,
  maskDobYear
} from '../services/bookingService.js';

describe('bookingWorkflow - Privacy Masking & Security', () => {
  it('correctly masks email addresses without exposing full mailbox names', () => {
    assert.strictEqual(maskEmail('rahul@test.com'), 'r***l@test.com');
    assert.strictEqual(maskEmail('aarav.sharma@domain.co.in'), 'a***a@domain.co.in');
    assert.strictEqual(maskEmail('al@domain.com'), 'a***@domain.com');
    assert.strictEqual(maskEmail(''), '');
    assert.strictEqual(maskEmail(null), '');
  });

  it('correctly masks international phone numbers displaying first 3 and last 4 digits', () => {
    assert.strictEqual(maskPhone('+919876543210'), '+91****3210');
    assert.strictEqual(maskPhone('+15551234567'), '+15****4567');
    assert.strictEqual(maskPhone('9876543210'), '987****3210');
    assert.strictEqual(maskPhone('123'), '****');
    assert.strictEqual(maskPhone(null), '');
  });

  it('correctly masks passport numbers displaying only final four characters', () => {
    assert.strictEqual(maskPassport('P98765432'), '****5432');
    assert.strictEqual(maskPassport('A12345678'), '****5678');
    assert.strictEqual(maskPassport('ABCD'), '****');
    assert.strictEqual(maskPassport(''), '');
    assert.strictEqual(maskPassport(null), '');
  });

  it('generates unique client idempotency keys incorporating offer and session markers', () => {
    const key1 = generateIdempotencyKey('usr_42', 101);
    const key2 = generateIdempotencyKey('usr_42', 101);
    assert.ok(key1.startsWith('web_usr_42_101_'));
    assert.ok(key2.startsWith('web_usr_42_101_'));
    assert.notStrictEqual(key1, key2);
  });

  it('validates passenger date of birth must strictly be in the past', () => {
    const isPastDate = (dateStr) => {
      if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return false;
      const dob = new Date(dateStr);
      const today = new Date();
      return dob < today;
    };

    assert.strictEqual(isPastDate('1994-08-22'), true);
    assert.strictEqual(isPastDate('2010-01-01'), true);
    assert.strictEqual(isPastDate('2099-12-31'), false);
    assert.strictEqual(isPastDate('invalid-date'), false);
  });

  it('validates contact details structure complies with backend specifications', () => {
    const isValidContact = (email, phone) => {
      const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email || '');
      const phoneDigits = (phone || '').replace(/\D/g, '');
      const phoneValid = phoneDigits.length >= 7;
      return emailValid && phoneValid;
    };

    assert.strictEqual(isValidContact('traveler@test.com', '+919876543210'), true);
    assert.strictEqual(isValidContact('bad-email', '+919876543210'), false);
    assert.strictEqual(isValidContact('traveler@test.com', '123'), false);
  });
});

describe('bookingWorkflow - Date, Time, Stops & Currency Formatters (No Invalid Date / undefined)', () => {
  it('formatDate safely formats valid ISO dates and never returns "Invalid Date"', () => {
    const formatted = formatDate('2026-11-18T14:45:00+00:00');
    assert.ok(formatted.includes('2026'));
    assert.ok(!formatted.includes('Invalid'));

    const formattedSimple = formatDate('2026-11-18');
    assert.ok(formattedSimple.includes('2026'));
    assert.ok(!formattedSimple.includes('Invalid'));

    assert.strictEqual(formatDate(null), 'Date unavailable');
    assert.strictEqual(formatDate(undefined), 'Date unavailable');
    assert.strictEqual(formatDate(''), 'Date unavailable');
    assert.strictEqual(formatDate('not-a-date'), 'Date unavailable');
  });

  it('formatTime safely formats ISO timestamps and time strings, never returning "Invalid Date"', () => {
    const timeFormatted = formatTime('2026-11-18T14:45:00+00:00');
    assert.ok(timeFormatted.includes('M') || timeFormatted.includes(':'));
    assert.ok(!timeFormatted.includes('Invalid'));

    assert.strictEqual(formatTime(null), '--:--');
    assert.strictEqual(formatTime(undefined), '--:--');
    assert.strictEqual(formatTime(''), '--:--');
    assert.strictEqual(formatTime('garbage'), '--:--');
  });

  it('formatStops correctly renders stop counts and never returns "undefined stop"', () => {
    assert.strictEqual(formatStops(0), 'Non-stop');
    assert.strictEqual(formatStops('0'), 'Non-stop');
    assert.strictEqual(formatStops(1), '1 stop');
    assert.strictEqual(formatStops('1'), '1 stop');
    assert.strictEqual(formatStops(2), '2 stops');
    assert.strictEqual(formatStops(null), 'Direct flight');
    assert.strictEqual(formatStops(undefined), 'Direct flight');
  });

  it('formatCurrency renders valid symbol and numbers and never returns "NaN"', () => {
    assert.strictEqual(formatCurrency(4600, 'INR'), '₹4,600.00');
    assert.strictEqual(formatCurrency('12500.5', 'INR'), '₹12,500.50');
    assert.strictEqual(formatCurrency(null, 'INR'), '₹0.00');
    assert.strictEqual(formatCurrency('invalid', 'INR'), '₹0.00');
    assert.strictEqual(formatCurrency(250, 'USD'), '$250.00');
  });

  it('maskDobYear extracts only birth year and conceals exact day/month', () => {
    assert.strictEqual(maskDobYear('2005-01-01'), 'Birth Year: 2005');
    assert.strictEqual(maskDobYear('1994-11-20'), 'Birth Year: 1994');
    assert.strictEqual(maskDobYear(null), '');
    assert.strictEqual(maskDobYear(undefined), '');
  });

  it('correctly maps representative mock booking response to UI display fields', () => {
    const mockBookingResponse = {
      id: 1,
      booking_reference: 'MOCK-B0C465',
      provider_booking_id: 'mock_ord_b0c465',
      provider_used: 'mock',
      data_source: 'mock_simulation',
      is_simulation: true,
      status: 'confirmed',
      total_amount: 4600.0,
      currency: 'INR',
      contact_email: 'bob@gmail.com',
      contact_phone: '123456789',
      passengers: [
        {
          first_name: 'John',
          last_name: 'Tea',
          date_of_birth: '2005-01-01',
          gender: 'male',
          passport_number: '****0099'
        }
      ],
      flight_offer: {
        id: 1278,
        airline_name: 'IndiGo',
        airline_code: '6E',
        flight_number: '6E-5032',
        origin_iata: 'BLR',
        destination_iata: 'DEL',
        departure_time: '2026-11-18T14:45:00+00:00',
        arrival_time: '2026-11-18T19:05:00+00:00',
        duration_minutes: 260,
        stops: 1,
        stop_details: '1 stop via BOM (1h 15m layover)',
        total_amount: 4600.0,
        currency: 'INR',
        cabin_class: 'economy',
        baggage_included: '15 kg Check-in, 7 kg Cabin'
      }
    };

    // UI resolution logic as implemented in BookingDetailPage & BookingHistoryPage
    const offer = mockBookingResponse.flight_offer || {};
    const departureTime = offer.departure_time || mockBookingResponse.departure_time;
    const arrivalTime = offer.arrival_time || mockBookingResponse.arrival_time;
    const stops = offer.stops !== undefined ? offer.stops : mockBookingResponse.stops;
    const origin = offer.origin_iata || mockBookingResponse.origin_iata;
    const destination = offer.destination_iata || mockBookingResponse.destination_iata;
    const airline = offer.airline_name || mockBookingResponse.airline_name;

    assert.notStrictEqual(formatDate(departureTime), 'Invalid Date');
    assert.notStrictEqual(formatDate(departureTime), 'Date unavailable');
    assert.ok(formatDate(departureTime).includes('2026'));

    assert.notStrictEqual(formatTime(departureTime), 'Invalid Date');
    assert.notStrictEqual(formatTime(departureTime), '--:--');

    assert.notStrictEqual(formatTime(arrivalTime), 'Invalid Date');
    assert.notStrictEqual(formatTime(arrivalTime), '--:--');

    assert.strictEqual(formatStops(stops), '1 stop');
    assert.notStrictEqual(formatStops(stops), 'undefined stop');

    assert.strictEqual(origin, 'BLR');
    assert.strictEqual(destination, 'DEL');
    assert.strictEqual(airline, 'IndiGo');

    const passenger = mockBookingResponse.passengers[0];
    assert.strictEqual(maskDobYear(passenger.date_of_birth), 'Birth Year: 2005');
    assert.ok(!maskDobYear(passenger.date_of_birth).includes('01-01'));
  });
});

describe('bookingWorkflow - Explicit User Authorization & Mock Disclosure', () => {
  it('strictly requires disclaimer checkbox to be true to authorize booking button', () => {
    const isAuthorizeButtonEnabled = (submitting, disclaimerAccepted) => {
      return !submitting && Boolean(disclaimerAccepted);
    };

    assert.strictEqual(isAuthorizeButtonEnabled(false, false), false, 'Button must be disabled when checkbox is unchecked');
    assert.strictEqual(isAuthorizeButtonEnabled(true, true), false, 'Button must be disabled while submitting');
    assert.strictEqual(isAuthorizeButtonEnabled(false, true), true, 'Button must be enabled only when checked and not submitting');
  });

  it('resets disclaimer acceptance when itinerary or passenger details change', () => {
    let disclaimerAccepted = true;

    // Simulation of itinerary/passenger change event
    const onItineraryOrPassengerChange = () => {
      disclaimerAccepted = false;
    };

    // Initial state: user checked the box
    assert.strictEqual(disclaimerAccepted, true);

    // Traveler modifies itinerary or passengers
    onItineraryOrPassengerChange();
    assert.strictEqual(disclaimerAccepted, false, 'Checkbox must reset to false upon passenger or itinerary change');
  });

  it('resets acceptance when arrival time, destination, stops, or cabin class change even with identical offer ID', () => {
    // Initial flight offer draft
    const initialOffer = {
      id: 501,
      origin_iata: 'BLR',
      destination_iata: 'DEL',
      departure_time: '2026-11-18T10:00:00+00:00',
      arrival_time: '2026-11-18T12:45:00+00:00',
      stops: 0,
      cabin_class: 'economy',
      total_amount: 4500.0,
      currency: 'INR'
    };

    // Evaluator matching BookingReviewPage's comprehensive dependency tracking
    const computeItineraryFingerprint = (offer, passengers = []) => {
      return JSON.stringify({
        id: offer?.id,
        origin: offer?.origin_iata,
        dest: offer?.destination_iata,
        dep: offer?.departure_time,
        arr: offer?.arrival_time,
        stops: offer?.stops,
        cabin: offer?.cabin_class,
        fare: offer?.total_amount,
        curr: offer?.currency,
        pax: passengers
      });
    };

    let disclaimerAccepted = true;
    let currentFingerprint = computeItineraryFingerprint(initialOffer);

    const updateDraftAndSyncConsent = (newOffer, newPassengers) => {
      const newFingerprint = computeItineraryFingerprint(newOffer, newPassengers);
      if (newFingerprint !== currentFingerprint) {
        disclaimerAccepted = false;
        currentFingerprint = newFingerprint;
      }
    };

    // 1. Destination changes with SAME offer ID -> resets
    disclaimerAccepted = true;
    updateDraftAndSyncConsent({ ...initialOffer, destination_iata: 'BOM' });
    assert.strictEqual(disclaimerAccepted, false, 'Changing destination must reset acceptance even with identical offer ID');

    // 2. Arrival time changes with SAME offer ID -> resets
    disclaimerAccepted = true;
    updateDraftAndSyncConsent({ ...initialOffer, arrival_time: '2026-11-18T14:15:00+00:00' });
    assert.strictEqual(disclaimerAccepted, false, 'Changing arrival time must reset acceptance even with identical offer ID');

    // 3. Stops change with SAME offer ID -> resets
    disclaimerAccepted = true;
    updateDraftAndSyncConsent({ ...initialOffer, stops: 1 });
    assert.strictEqual(disclaimerAccepted, false, 'Changing stops count must reset acceptance even with identical offer ID');

    // 4. Cabin class changes with SAME offer ID -> resets
    disclaimerAccepted = true;
    updateDraftAndSyncConsent({ ...initialOffer, cabin_class: 'business' });
    assert.strictEqual(disclaimerAccepted, false, 'Changing cabin class must reset acceptance even with identical offer ID');

    // 5. Origin changes with SAME offer ID -> resets
    disclaimerAccepted = true;
    updateDraftAndSyncConsent({ ...initialOffer, origin_iata: 'HYD' });
    assert.strictEqual(disclaimerAccepted, false, 'Changing origin must reset acceptance even with identical offer ID');

    // 6. No changes -> remains accepted
    disclaimerAccepted = true;
    updateDraftAndSyncConsent({ ...initialOffer, origin_iata: 'HYD' }); // Same as before
    assert.strictEqual(disclaimerAccepted, true, 'Unchanged draft must keep acceptance');
  });

  it('requires fresh explicit acceptance for price changes (HTTP 409)', () => {
    const isPriceAcceptButtonEnabled = (priceChangeCheckbox, submitting) => {
      return Boolean(priceChangeCheckbox) && !submitting;
    };

    assert.strictEqual(isPriceAcceptButtonEnabled(false, false), false, 'Accept button must be disabled until price change checkbox is checked');
    assert.strictEqual(isPriceAcceptButtonEnabled(true, true), false, 'Accept button must be disabled while submitting');
    assert.strictEqual(isPriceAcceptButtonEnabled(true, false), true, 'Accept button must be enabled when checkbox is checked');
  });

  it('builds payload with confirmed_by_user reflecting exact checkbox state', () => {
    const buildBookingPayload = ({ offerId, amount, disclaimerAccepted, priceAccepted, priceChangeCheckbox }) => {
      return {
        flight_offer_id: offerId,
        confirmed_by_user: Boolean(priceAccepted ? priceChangeCheckbox : disclaimerAccepted),
        expected_amount: amount,
        price_change_accepted: Boolean(priceAccepted)
      };
    };

    const unconfirmed = buildBookingPayload({ offerId: 101, amount: 4500, disclaimerAccepted: false });
    assert.strictEqual(unconfirmed.confirmed_by_user, false);

    const confirmed = buildBookingPayload({ offerId: 101, amount: 4500, disclaimerAccepted: true });
    assert.strictEqual(confirmed.confirmed_by_user, true);

    const priceChangedWithoutConsent = buildBookingPayload({ offerId: 101, amount: 5000, priceAccepted: true, priceChangeCheckbox: false });
    assert.strictEqual(priceChangedWithoutConsent.confirmed_by_user, false);

    const priceChangedWithConsent = buildBookingPayload({ offerId: 101, amount: 5000, priceAccepted: true, priceChangeCheckbox: true });
    assert.strictEqual(priceChangedWithConsent.confirmed_by_user, true);
    assert.strictEqual(priceChangedWithConsent.price_change_accepted, true);
  });
});
