"""
Curated Airport & IATA Directory for City/Airport code resolution.
Complies with SRS FR-012 (Airport/City input normalization).
"""

from typing import List, Optional
from app.schemas.flight import AirportInfo

AIRPORTS_DATABASE: List[AirportInfo] = [
    # Top Indian Domestic Hubs
    AirportInfo(iata_code="BLR", city_name="Bengaluru", airport_name="Kempegowda International Airport", country="India"),
    AirportInfo(iata_code="DEL", city_name="New Delhi", airport_name="Indira Gandhi International Airport", country="India"),
    AirportInfo(iata_code="BOM", city_name="Mumbai", airport_name="Chhatrapati Shivaji Maharaj International Airport", country="India"),
    AirportInfo(iata_code="MAA", city_name="Chennai", airport_name="Chennai International Airport", country="India"),
    AirportInfo(iata_code="CCU", city_name="Kolkata", airport_name="Netaji Subhash Chandra Bose International Airport", country="India"),
    AirportInfo(iata_code="HYD", city_name="Hyderabad", airport_name="Rajiv Gandhi International Airport", country="India"),
    AirportInfo(iata_code="COK", city_name="Kochi", airport_name="Cochin International Airport", country="India"),
    AirportInfo(iata_code="GOI", city_name="Goa", airport_name="Dabolim Airport", country="India"),
    AirportInfo(iata_code="GOX", city_name="Goa (Mopa)", airport_name="Manohar International Airport", country="India"),
    AirportInfo(iata_code="PNQ", city_name="Pune", airport_name="Pune Airport", country="India"),
    AirportInfo(iata_code="AMD", city_name="Ahmedabad", airport_name="Sardar Vallabhbhai Patel International Airport", country="India"),
    AirportInfo(iata_code="JAI", city_name="Jaipur", airport_name="Jaipur International Airport", country="India"),
    AirportInfo(iata_code="TRV", city_name="Thiruvananthapuram", airport_name="Trivandrum International Airport", country="India"),
    AirportInfo(iata_code="IXC", city_name="Chandigarh", airport_name="Shaheed Bhagat Singh International Airport", country="India"),
    AirportInfo(iata_code="GAU", city_name="Guwahati", airport_name="Lokpriya Gopinath Bordoloi International Airport", country="India"),
    AirportInfo(iata_code="LKO", city_name="Lucknow", airport_name="Chaudhary Charan Singh International Airport", country="India"),
    AirportInfo(iata_code="PAT", city_name="Patna", airport_name="Jay Prakash Narayan Airport", country="India"),
    AirportInfo(iata_code="BBI", city_name="Bhubaneswar", airport_name="Biju Patnaik Airport", country="India"),
    AirportInfo(iata_code="SXR", city_name="Srinagar", airport_name="Sheikh ul-Alam International Airport", country="India"),
    AirportInfo(iata_code="IXB", city_name="Bagdogra", airport_name="Bagdogra Airport", country="India"),

    # Top Global International Hubs
    AirportInfo(iata_code="LHR", city_name="London", airport_name="Heathrow Airport", country="United Kingdom"),
    AirportInfo(iata_code="LGW", city_name="London", airport_name="Gatwick Airport", country="United Kingdom"),
    AirportInfo(iata_code="JFK", city_name="New York", airport_name="John F. Kennedy International Airport", country="United States"),
    AirportInfo(iata_code="EWR", city_name="New York", airport_name="Newark Liberty International Airport", country="United States"),
    AirportInfo(iata_code="SFO", city_name="San Francisco", airport_name="San Francisco International Airport", country="United States"),
    AirportInfo(iata_code="DXB", city_name="Dubai", airport_name="Dubai International Airport", country="United Arab Emirates"),
    AirportInfo(iata_code="SIN", city_name="Singapore", airport_name="Singapore Changi Airport", country="Singapore"),
    AirportInfo(iata_code="DOH", city_name="Doha", airport_name="Hamad International Airport", country="Qatar"),
    AirportInfo(iata_code="CDG", city_name="Paris", airport_name="Charles de Gaulle Airport", country="France"),
    AirportInfo(iata_code="FRA", city_name="Frankfurt", airport_name="Frankfurt Airport", country="Germany"),
    AirportInfo(iata_code="AMS", city_name="Amsterdam", airport_name="Amsterdam Airport Schiphol", country="Netherlands"),
    AirportInfo(iata_code="BKK", city_name="Bangkok", airport_name="Suvarnabhumi Airport", country="Thailand"),
    AirportInfo(iata_code="KUL", city_name="Kuala Lumpur", airport_name="Kuala Lumpur International Airport", country="Malaysia"),
    AirportInfo(iata_code="HND", city_name="Tokyo", airport_name="Haneda Airport", country="Japan"),
    AirportInfo(iata_code="NRT", city_name="Tokyo", airport_name="Narita International Airport", country="Japan"),
    AirportInfo(iata_code="SYD", city_name="Sydney", airport_name="Sydney Kingsford Smith Airport", country="Australia"),
    AirportInfo(iata_code="YYZ", city_name="Toronto", airport_name="Toronto Pearson International Airport", country="Canada"),
]


def search_airports(query: str, limit: int = 10) -> List[AirportInfo]:
    """
    Search airports by IATA code, city name, or airport name (case-insensitive).
    """
    if not query or len(query.strip()) < 1:
        return AIRPORTS_DATABASE[:limit]

    q = query.strip().lower()
    matches = []

    # Prioritize exact IATA code match first
    for airport in AIRPORTS_DATABASE:
        if airport.iata_code.lower() == q:
            matches.append(airport)
            break

    # Then match city name starts-with
    for airport in AIRPORTS_DATABASE:
        if airport not in matches and airport.city_name.lower().startswith(q):
            matches.append(airport)
            if len(matches) >= limit:
                return matches

    # Then match anywhere in city, airport name, or code
    for airport in AIRPORTS_DATABASE:
        if airport not in matches:
            if (
                q in airport.iata_code.lower()
                or q in airport.city_name.lower()
                or q in airport.airport_name.lower()
            ):
                matches.append(airport)
                if len(matches) >= limit:
                    return matches

    return matches[:limit]


# Common city aliases and colloquial names
CITY_ALIASES = {
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "bombay": "BOM",
    "chennai": "MAA",
    "madras": "MAA",
    "kolkata": "CCU",
    "calcutta": "CCU",
    "hyderabad": "HYD",
    "cochin": "COK",
    "kochi": "COK",
    "pune": "PNQ",
    "ahmedabad": "AMD",
    "jaipur": "JAI",
    "goa": "GOI",
    "london": "LHR",
    "new york": "JFK",
    "nyc": "JFK",
    "san francisco": "SFO",
    "dubai": "DXB",
    "singapore": "SIN",
    "paris": "CDG",
    "frankfurt": "FRA",
    "amsterdam": "AMS",
    "tokyo": "HND",
}


STOP_WORDS = {
    "to", "from", "go", "going", "fly", "flying", "flight", "flights",
    "want", "need", "for", "on", "at", "me", "us", "the", "a", "an",
    "in", "into", "of", "off", "out", "by", "ticket", "tickets", "book", "find"
}


def resolve_iata(text: str) -> Optional[str]:
    """
    Resolve free-text user input into a canonical 3-letter IATA code.
    Example: "Bangalore" -> "BLR", "delhi" -> "DEL", "LHR" -> "LHR".
    """
    if not text:
        return None

    cleaned = text.strip()
    if cleaned.lower() in STOP_WORDS:
        return None

    upper_cleaned = cleaned.upper()

    # 1. Exact 3-letter IATA code match
    if len(upper_cleaned) == 3:
        for airport in AIRPORTS_DATABASE:
            if airport.iata_code == upper_cleaned:
                return upper_cleaned

    # 2. Check alias mapping (case-insensitive)
    alias_match = CITY_ALIASES.get(cleaned.lower())
    if alias_match:
        return alias_match

    # 3. Search by city or airport name
    results = search_airports(cleaned, limit=1)
    if results:
        return results[0].iata_code

    return None


# ---------------------------------------------------------------------------
# Airport Timezone Registry (Asia/Kolkata default for Indian airports)
# ---------------------------------------------------------------------------
AIRPORT_TIMEZONES = {
    # Domestic (Indian Hubs) - Asia/Kolkata (IST = UTC+05:30)
    "BLR": "Asia/Kolkata",
    "DEL": "Asia/Kolkata",
    "BOM": "Asia/Kolkata",
    "MAA": "Asia/Kolkata",
    "CCU": "Asia/Kolkata",
    "HYD": "Asia/Kolkata",
    "COK": "Asia/Kolkata",
    "GOI": "Asia/Kolkata",
    "GOX": "Asia/Kolkata",
    "PNQ": "Asia/Kolkata",
    "AMD": "Asia/Kolkata",
    "JAI": "Asia/Kolkata",
    "TRV": "Asia/Kolkata",
    "IXC": "Asia/Kolkata",
    "GAU": "Asia/Kolkata",
    "LKO": "Asia/Kolkata",
    "PAT": "Asia/Kolkata",
    "BBI": "Asia/Kolkata",
    "SXR": "Asia/Kolkata",
    "IXB": "Asia/Kolkata",

    # UK
    "LHR": "Europe/London",
    "LGW": "Europe/London",

    # USA
    "JFK": "America/New_York",
    "EWR": "America/New_York",
    "SFO": "America/Los_Angeles",

    # Middle East
    "DXB": "Asia/Dubai",
    "DOH": "Asia/Qatar",

    # Europe
    "CDG": "Europe/Paris",
    "FRA": "Europe/Berlin",
    "AMS": "Europe/Amsterdam",

    # Asia-Pacific & Others
    "SIN": "Asia/Singapore",
    "BKK": "Asia/Bangkok",
    "KUL": "Asia/Kuala_Lumpur",
    "HND": "Asia/Tokyo",
    "NRT": "Asia/Tokyo",
    "SYD": "Australia/Sydney",
    "YYZ": "America/Toronto",
}


def get_airport_timezone(iata_code: Optional[str]) -> str:
    """
    Returns the IANA timezone for an airport IATA code.
    Defaults to 'Asia/Kolkata' for Indian airports or unknown domestic hubs.
    """
    if not iata_code:
        return "Asia/Kolkata"
    return AIRPORT_TIMEZONES.get(iata_code.strip().upper(), "Asia/Kolkata")

