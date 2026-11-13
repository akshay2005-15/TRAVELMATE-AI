"""
Intent and Slot Extraction Engine using Google Gemini API with robust Rule-Based Fallback.
Complies with SRS FR-011 to FR-015, SAD Section 4.1, and Phase 3 Step 4 specifications.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, Tuple, List, Optional
import json
import re
import logging

from app.core.config import settings
from app.adapters.airports import resolve_iata, search_airports
from app.ai.prompts import EXTRACTION_SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)

# Month and Day name mappings for date resolution
MONTHS_DICT = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12
}

DAY_NAME_TO_INT = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}


def parse_date_expression(text: str, reference_date: Optional[date] = None) -> Optional[str]:
    """
    Parses natural language relative or explicit dates into ISO YYYY-MM-DD.
    Supports:
      - 'tomorrow', 'today', 'day after tomorrow', 'next week'
      - '2 days later', 'in 3 days', 'after 4 days', '5 days from now'
      - '11 November 2026', '11th Nov 2026', 'Nov 11, 2026'
      - '11 November' (inferred year)
      - 'next friday', 'this monday'
      - '2026-11-20', '15/12/2026', '15-12-2026'
    """
    if not text:
        return None

    ref = reference_date or date.today()
    clean = text.lower().strip()

    # 1. Exact ISO date: YYYY-MM-DD
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", clean)
    if iso_match:
        return iso_match.group(1)

    # 2. DD/MM/YYYY or DD-MM-YYYY
    dmy_num = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", clean)
    if dmy_num:
        try:
            d, m, y = int(dmy_num.group(1)), int(dmy_num.group(2)), int(dmy_num.group(3))
            return date(y, m, d).isoformat()
        except ValueError:
            pass

    # 3. Common relative keywords
    if "day after tomorrow" in clean:
        return (ref + timedelta(days=2)).isoformat()
    if "tomorrow" in clean:
        return (ref + timedelta(days=1)).isoformat()
    if "today" in clean:
        return ref.isoformat()
    if "next week" in clean:
        return (ref + timedelta(days=7)).isoformat()

    # 4. Numerical day offset: '2 days later', 'in 3 days', 'after 4 days', '5 days from now'
    offset_match = re.search(r"\b(?:in\s+)?(\d+)\s+days?\s*(?:later|after|from\s+now)\b", clean)
    if not offset_match:
        offset_match = re.search(r"\bin\s+(\d+)\s+days?\b", clean)
    if not offset_match:
        offset_match = re.search(r"\bafter\s+(\d+)\s+days?\b", clean)
    if offset_match:
        days = int(offset_match.group(1))
        return (ref + timedelta(days=days)).isoformat()

    # 5. Day Month Year: '11 November 2026', '11th Nov 2026', '1st January 2027'
    dmy_match = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s+(\d{4})\b",
        clean
    )
    if dmy_match:
        day = int(dmy_match.group(1))
        m_str = dmy_match.group(2)
        year = int(dmy_match.group(3))
        if m_str in MONTHS_DICT:
            try:
                return date(year, MONTHS_DICT[m_str], day).isoformat()
            except ValueError:
                pass

    # 6. Month Day Year: 'November 11 2026', 'Nov 11, 2026'
    mdy_match = re.search(
        r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
        clean
    )
    if mdy_match:
        m_str = mdy_match.group(1)
        day = int(mdy_match.group(2))
        year = int(mdy_match.group(3))
        if m_str in MONTHS_DICT:
            try:
                return date(year, MONTHS_DICT[m_str], day).isoformat()
            except ValueError:
                pass

    # 7. Day Month (year omitted): '11 November', '11th Nov'
    dm_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\b", clean)
    if dm_match:
        day = int(dm_match.group(1))
        m_str = dm_match.group(2)
        if m_str in MONTHS_DICT:
            try:
                target_date = date(ref.year, MONTHS_DICT[m_str], day)
                if target_date < ref:
                    target_date = date(ref.year + 1, MONTHS_DICT[m_str], day)
                return target_date.isoformat()
            except ValueError:
                pass

    # 8. Weekday names: 'this friday', 'next monday'
    day_match = re.search(r"\b(?:next|this)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", clean)
    if day_match:
        target_weekday = DAY_NAME_TO_INT[day_match.group(1)]
        current_weekday = ref.weekday()
        days_ahead = (target_weekday - current_weekday) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (ref + timedelta(days=days_ahead)).isoformat()

    return None


# Backward-compatible alias
parse_relative_date = parse_date_expression


def extract_time_preference(text: str) -> Optional[str]:
    """
    Extracts structured departure-time window preference from user query.
    Values: 'morning', 'afternoon', 'evening', 'night'.
    """
    clean = text.lower()
    # Morning: 'morning', 'early morning', 'before 12 PM', 'before 12pm', 'before noon', 'before 12:00'
    if re.search(r"\b(?:early\s+morning|morning|before\s+12(?::00)?\s*(?:pm|noon)?|before\s+noon)\b", clean):
        return "morning"
    # Afternoon: 'afternoon', 'noon', 'midday', 'after 12 PM', 'after 12pm', 'after noon', 'after 12:00'
    if re.search(r"\b(?:afternoon|noon|midday|after\s+12(?::00)?\s*(?:pm|noon)?|after\s+noon)\b", clean):
        return "afternoon"
    # Evening: 'evening', 'late afternoon'
    if re.search(r"\b(?:evening)\b", clean):
        return "evening"
    # Night: 'night', 'red-eye', 'late night', 'overnight'
    if re.search(r"\b(?:night|red-eye|late\s+night|overnight)\b", clean):
        return "night"
    return None


def _extract_origin_from_tokens(text: str) -> Optional[str]:
    """Extract origin airport code from natural phrases (e.g. 'from BLR', 'departing from Bangalore')."""
    words = text.split()
    for i, w in enumerate(words):
        cleaned_w = w.lower().strip(".,?!:;")
        if cleaned_w in ("from", "departing", "leaving") and i + 1 < len(words):
            c1 = words[i + 1].strip(".,?!:;")
            if i + 2 < len(words):
                c2 = f"{c1} {words[i + 2].strip('.,?!:;')}"
                code2 = resolve_iata(c2)
                if code2:
                    return code2
            code1 = resolve_iata(c1)
            if code1:
                return code1
    return None


def _extract_destination_from_tokens(text: str) -> Optional[str]:
    """Extract destination airport code from natural phrases (e.g. 'to DEL', 'fly to Delhi', 'visiting London')."""
    words = text.split()
    for i, w in enumerate(words):
        cleaned_w = w.lower().strip(".,?!:;")
        if cleaned_w in ("to", "towards", "into", "visit", "visiting") and i + 1 < len(words):
            c1 = words[i + 1].strip(".,?!:;")
            if i + 2 < len(words):
                c2 = f"{c1} {words[i + 2].strip('.,?!:;')}"
                code2 = resolve_iata(c2)
                if code2:
                    return code2
            code1 = resolve_iata(c1)
            if code1:
                return code1
    return None


def extract_passenger_and_contact_tokens(text: str) -> Dict[str, Any]:
    """
    Extracts passenger name, date of birth, gender, email, phone, and profile flag.
    """
    extracted: Dict[str, Any] = {}
    clean = text.strip()
    lower = clean.lower()

    # Profile reuse
    if re.search(r"\b(?:use (?:my )?saved profile|use (?:my )?profile|use saved details|use my details|book for me)\b", lower):
        extracted["use_saved_profile"] = True

    # Email
    email_match = re.search(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", clean)
    if email_match:
        extracted["contact_email"] = email_match.group(1).strip()

    # Phone number (+919876543210, +1-555-1234, 9876543210)
    for phone_match in re.finditer(r"(\+?\d[\d\s\-()]{7,18}\d)", clean):
        cand_phone = phone_match.group(1).strip()
        # Ensure it's not an ISO date like 2026-11-25 or 1991-03-20
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", cand_phone):
            digits_only = re.sub(r"\D", "", cand_phone)
            if len(digits_only) >= 7:
                extracted["contact_phone"] = cand_phone
                break

    # Date of Birth (YYYY-MM-DD)
    dob_match = re.search(r"\b(?:dob|born|birth(?:day| date)?)\s*(?:is|on|:)?\s*(\d{4}-\d{2}-\d{2})\b", lower)
    if not dob_match:
        # Check if there is an explicit past date in YYYY-MM-DD
        all_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", clean)
        for cand in all_dates:
            try:
                candidate_d = datetime.strptime(cand, "%Y-%m-%d").date()
                if candidate_d < date.today():
                    extracted["passenger_dob"] = cand
                    break
            except Exception:
                pass
    else:
        extracted["passenger_dob"] = dob_match.group(1)

    # Gender
    if re.search(r"\b(?:male|gentleman|mr)\b", lower) and not re.search(r"\b(?:female)\b", lower):
        extracted["passenger_gender"] = "male"
    elif re.search(r"\b(?:female|woman|lady|ms|mrs)\b", lower):
        extracted["passenger_gender"] = "female"

    # Passenger Name
    name_match = re.search(
        r"\b(?:passenger(?:'s)?(?:\s+name)?|name|traveler(?:'s)?(?:\s+name)?)\s*(?:is|:)?\s*([A-Za-z]+(?:\s+[A-Za-z]+){1,3})\b",
        clean,
        re.IGNORECASE
    )
    if name_match:
        cand_name = name_match.group(1).strip()
        ignore_words = {"male", "female", "other", "economy", "business", "first", "flight", "booking", "confirmed"}
        if not any(w in cand_name.lower().split() for w in ignore_words):
            extracted["passenger_name"] = cand_name

    return extracted


def extract_flight_selection_identifier(text: str) -> Optional[str]:
    """
    Extracts flight selection identifier from user text:
    e.g. '1', '2', 'cheapest', 'fastest', '6E-2054', 'offer 12', etc.
    """
    clean = text.strip()
    lower = clean.lower()

    # Ordinals: first, second, third, etc.
    ordinal_map = {
        "first": "1", "1st": "1",
        "second": "2", "2nd": "2",
        "third": "3", "3rd": "3",
        "fourth": "4", "4th": "4",
        "fifth": "5", "5th": "5",
        "sixth": "6", "6th": "6"
    }
    for ord_word, num in ordinal_map.items():
        if re.search(rf"\b(?:the\s+)?{ord_word}(?:\s+(?:one|flight|option))?\b", lower):
            return num

    if re.search(r"\b(?:cheapest|lowest (?:fare|price))\b", lower):
        return "cheapest"

    if re.search(r"\b(?:fastest|quickest|shortest)\b", lower):
        return "fastest"

    # Explicit offer ID: "offer 42", "offer #42", "flight offer id 42"
    offer_id_match = re.search(r"\boffer\s*(?:id|#)?\s*(\d+)\b", lower)
    if offer_id_match:
        return f"id_{offer_id_match.group(1)}"

    # Specific flight number: "6E-2054", "BA-117", "AI-506", "AI 506"
    fl_match = re.search(r"\b([A-Za-z0-9]{2})\s*[-]?\s*(\d{3,4})(?!\s*[-/]\s*\d{2})\b", clean)
    if fl_match:
        code_part = fl_match.group(1).upper()
        num_part = fl_match.group(2)
        stopwords = {"ON", "IN", "TO", "AT", "NO", "DO", "SO", "MY", "ME", "HE", "WE", "IT", "IS", "AM", "BY", "OR", "IF", "AS", "AN", "OF"}
        if code_part not in stopwords and not code_part.isdigit():
            if code_part.isalpha() and "-" not in fl_match.group(0):
                if any(c.isupper() for c in fl_match.group(1)) or "flight" in lower:
                    return f"{code_part}-{num_part}"
            else:
                return f"{code_part}-{num_part}"

    # Match numeric option if user says "flight 2", "option 2", "select 2", "take 2"
    num_match = re.search(r"\b(?:select|choose|book|take|want)?\s*(?:flight|option|number|#)\s*([1-9])\b", lower)
    if num_match:
        return num_match.group(1)

    # Simple "flight 1", "option 1", or "number 1"
    if re.search(r"\b(?:flight|option)\s*([1-9])\b", lower):
        m = re.search(r"\b(?:flight|option)\s*([1-9])\b", lower)
        return m.group(1)

    return None


def rule_based_extract(
    user_message: str,
    current_slots: Dict[str, Any],
    reference_date: Optional[date] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Deterministic rule-based extractor using token analysis and airport directory resolution.
    Serves as a resilient fallback if Gemini is not configured, rate-limited, or unavailable.
    Preserves and non-destructively merges previously extracted slots.
    """
    msg_clean = user_message.strip()
    msg_lower = msg_clean.lower()
    ref = reference_date or date.today()
    merged = dict(current_slots or {})

    # 1. Booking Lifecycle Intents (Checked first to prevent masking by generic keywords)
    # Cancellation
    if re.search(r"\b(?:cancel|cancel booking|stop booking|abort|start over)\b", msg_lower):
        return "cancel_booking", merged

    # Price change approval
    if re.search(r"\b(?:accept (?:the )?(?:new|updated)?\s*(?:price|fare)|approve (?:the )?(?:new|updated)?\s*(?:price|fare)|confirm (?:with|at) (?:the )?(?:new|updated)?\s*(?:price|fare))\b", msg_lower):
        return "price_change_approval", merged

    # Explicit confirmation
    if re.search(r"\b(?:confirm booking|confirm my booking|proceed with booking|book this flight|book my flight|yes,? please book|confirm reservation|confirm my flight|please proceed with the booking|yes,? confirm booking|yes,? confirm)\b", msg_lower):
        return "confirm_booking", merged

    # Vague confirmation
    if re.search(r"\b(?:looks good|looks great|looks fine|sounds good|sounds great|nice|okay|ok|fine|cool|perfect|that's fine|all good|sure)\b", msg_lower) and not re.search(r"\b(?:confirm|book|proceed)\b", msg_lower):
        return "vague_confirmation", merged

    # Ask flight details
    if re.search(r"\b(?:baggage|luggage|meal|meals|stops?|non-stop|arrival time|departure time|land|landing|duration|aircraft|details about)\b", msg_lower) and ("flight" in msg_lower or "it" in msg_lower or "this" in msg_lower or "option" in msg_lower or "indigo" in msg_lower):
        return "ask_flight_details", merged

    # Provide passenger / contact details
    pax_tokens = extract_passenger_and_contact_tokens(msg_clean)
    if pax_tokens:
        merged.update(pax_tokens)

    # Flight selection
    sel_id = extract_flight_selection_identifier(msg_clean)
    if sel_id:
        merged["selected_flight_identifier"] = sel_id

    # If the user selected a flight (even if they also provided passenger details or profile in the same message)
    if sel_id:
        return "select_flight", merged

    if pax_tokens and any(k in pax_tokens for k in ["passenger_name", "passenger_dob", "contact_email", "contact_phone", "use_saved_profile"]):
        if not any(k in msg_lower for k in ["flights from", "fly from", "search flight", "to "]):
            return "provide_passenger_details", merged

    # 2. Greetings and Out-of-Scope
    if any(re.search(rf"\b{word}\b", msg_lower) for word in ["hi", "hello", "hey", "greetings", "good morning", "good evening"]):
        if not any(k in msg_lower for k in ["flight", "fly", "to", "from", "blr", "del", "bom"]):
            return "greeting", merged

    if any(k in msg_lower for k in ["hotel", "cab", "taxi", "train", "car rental", "room"]):
        return "out_of_scope", merged

    intent = "search_flights"

    # 2. Extract Route
    # Pattern A: "from [origin] to [destination]"
    from_to_match = re.search(
        r"\b(?:from|out of)\s+([a-zA-Z\s]{2,20}?)\s+(?:to|towards)\s+([a-zA-Z\s]{2,20}?)(?:\s+(?:on|next|tomorrow|\d{4}|for|with|in)|$|\.|\?)",
        msg_clean,
        re.IGNORECASE
    )
    if from_to_match:
        orig_code = resolve_iata(from_to_match.group(1).strip())
        dest_code = resolve_iata(from_to_match.group(2).strip())
        if orig_code:
            merged["origin"] = orig_code
        if dest_code:
            merged["destination"] = dest_code

    # Pattern B: "[IATA] to [IATA]" (e.g. "BLR to DEL" or "BLR-DEL")
    if "origin" not in merged or "destination" not in merged:
        code_to_code = re.search(r"\b([a-zA-Z]{3})\s*(?:to|-|->)\s*([a-zA-Z]{3})\b", msg_clean)
        if code_to_code:
            orig_code = resolve_iata(code_to_code.group(1))
            dest_code = resolve_iata(code_to_code.group(2))
            if orig_code and "origin" not in merged:
                merged["origin"] = orig_code
            if dest_code and "destination" not in merged:
                merged["destination"] = dest_code

    # Pattern C: Token scan for origin
    if "origin" not in merged:
        orig = _extract_origin_from_tokens(msg_clean)
        if orig:
            merged["origin"] = orig

    # Pattern D: Token scan for destination
    if "destination" not in merged:
        dest = _extract_destination_from_tokens(msg_clean)
        if dest:
            merged["destination"] = dest

    # 3. Extract Dates (Relative, explicit, and offsets like '2 days later' or '11 November 2026')
    parsed_date = parse_date_expression(msg_clean, reference_date=ref)
    if parsed_date:
        merged["departure_date"] = parsed_date

    # 4. Extract Departure Time Preference (e.g. 'morning', 'afternoon', 'evening')
    if re.search(r"\b(?:any\s+time|all\s+flights|all\s+times|any\s+departure|no\s+preference)\b", msg_clean):
        merged["preferred_time"] = None
    else:
        pref_time = extract_time_preference(msg_clean)
        if pref_time:
            merged["preferred_time"] = pref_time

    # 5. Extract Passenger Count
    pass_match = re.search(r"\b(\d{1})\s*(?:passengers?|adults?|tickets?|people|persons?)\b", msg_lower)
    if pass_match:
        count = int(pass_match.group(1))
        if 1 <= count <= 9:
            merged["passengers"] = count
    elif "2 tickets" in msg_lower or "two tickets" in msg_lower or "for 2" in msg_lower:
        merged["passengers"] = 2
    elif "3 tickets" in msg_lower or "three tickets" in msg_lower:
        merged["passengers"] = 3

    # 6. Extract Cabin Class
    if "first class" in msg_lower or "first" in msg_lower:
        merged["cabin_class"] = "first"
    elif "business class" in msg_lower or "business" in msg_lower:
        merged["cabin_class"] = "business"
    elif "premium economy" in msg_lower:
        merged["cabin_class"] = "premium_economy"
    elif "economy" in msg_lower:
        merged["cabin_class"] = "economy"

    return intent, merged


async def extract_slots_and_intent(
    user_message: str,
    current_slots: Dict[str, Any],
    history: Optional[List[Dict[str, str]]] = None,
    force_fallback: bool = False,
    reference_date: Optional[date] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Extracts intent and flight slots from user query.
    Attempts Google Gemini extraction first. If API key is missing or request fails,
    gracefully uses the deterministic rule-based fallback.
    """
    ref = reference_date or date.today()
    merged = dict(current_slots or {})

    # Check if Gemini API is available and not forced to fallback
    has_gemini = (
        bool(settings.GEMINI_API_KEY)
        and len(settings.GEMINI_API_KEY) > 10
        and not settings.GEMINI_API_KEY.startswith("your_")
        and not force_fallback
    )

    if not has_gemini:
        logger.info("Using rule-based extraction (Gemini API key not configured or fallback requested).")
        return rule_based_extract(user_message, current_slots, reference_date=ref)

    # Gemini API Extraction
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=5000))

        today_str = ref.isoformat()
        prompt = (
            f"Reference Today's Date: {today_str}\n"
            f"Already Extracted Slots: {json.dumps(current_slots or {})}\n"
            f"User Message: {user_message}\n\n"
            "Extract intent and slots in the specified JSON format."
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config={
                "system_instruction": EXTRACTION_SYSTEM_INSTRUCTION,
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        )

        raw_text = response.text.strip()
        parsed = json.loads(raw_text)

        intent = parsed.get("intent", "search_flights")

        # Map and resolve extracted slots
        if parsed.get("origin"):
            resolved = resolve_iata(str(parsed["origin"]))
            if resolved:
                merged["origin"] = resolved

        if parsed.get("destination"):
            resolved = resolve_iata(str(parsed["destination"]))
            if resolved:
                merged["destination"] = resolved

        if parsed.get("departure_date"):
            dep_date = str(parsed["departure_date"]).strip()
            # If Gemini returned relative or non-ISO text, parse it with our robust parser
            parsed_iso = parse_date_expression(dep_date, reference_date=ref)
            if parsed_iso:
                merged["departure_date"] = parsed_iso
            else:
                try:
                    dt = datetime.strptime(dep_date, "%Y-%m-%d").date()
                    if dt >= ref:
                        merged["departure_date"] = dep_date
                except Exception:
                    pass
        else:
            # Fallback to local regex date parsing if Gemini didn't extract date slot
            local_date = parse_date_expression(user_message, reference_date=ref)
            if local_date:
                merged["departure_date"] = local_date

        if parsed.get("preferred_time"):
            cls_pref = str(parsed["preferred_time"]).lower().strip()
            if cls_pref in ["morning", "afternoon", "evening", "night"]:
                merged["preferred_time"] = cls_pref
        else:
            local_pref = extract_time_preference(user_message)
            if local_pref:
                merged["preferred_time"] = local_pref

        if parsed.get("return_date"):
            ret_date = str(parsed["return_date"]).strip()
            try:
                datetime.strptime(ret_date, "%Y-%m-%d")
                merged["return_date"] = ret_date
            except Exception:
                pass

        if parsed.get("passengers"):
            p_val = int(parsed["passengers"])
            if 1 <= p_val <= 9:
                merged["passengers"] = p_val

        if parsed.get("cabin_class"):
            cls_val = str(parsed["cabin_class"]).lower()
            if cls_val in ["economy", "premium_economy", "business", "first"]:
                merged["cabin_class"] = cls_val

        # Extract and merge booking-specific fields
        if parsed.get("selected_flight_identifier"):
            merged["selected_flight_identifier"] = str(parsed["selected_flight_identifier"]).strip()
        else:
            sel_local = extract_flight_selection_identifier(user_message)
            if sel_local:
                merged["selected_flight_identifier"] = sel_local

        if parsed.get("passenger_name"):
            merged["passenger_name"] = str(parsed["passenger_name"]).strip()
        if parsed.get("passenger_dob"):
            merged["passenger_dob"] = str(parsed["passenger_dob"]).strip()
        if parsed.get("passenger_gender"):
            merged["passenger_gender"] = str(parsed["passenger_gender"]).strip().lower()
        if parsed.get("contact_email"):
            merged["contact_email"] = str(parsed["contact_email"]).strip()
        if parsed.get("contact_phone"):
            merged["contact_phone"] = str(parsed["contact_phone"]).strip()
        if parsed.get("use_saved_profile"):
            merged["use_saved_profile"] = bool(parsed["use_saved_profile"])

        # Supplement with local regex tokens
        pax_tokens = extract_passenger_and_contact_tokens(user_message)
        for pk, pv in pax_tokens.items():
            if pk not in merged or merged[pk] is None:
                merged[pk] = pv

        return intent, merged

    except Exception as e:
        logger.warning(f"Gemini API extraction failed ({str(e)}). Falling back to rule-based extractor.")
        return rule_based_extract(user_message, current_slots, reference_date=ref)
