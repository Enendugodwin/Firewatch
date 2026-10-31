"""Small offline gazetteer for map navigation.

Approximate country and city centroids plus coordinate parsing. This exists so
"geographic search" works with no API key and no external geocoder: the map is a
navigation aid, not an authority. Boundary geometry arrives with the basemap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

COORDINATE_PATTERN = re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


@dataclass(frozen=True)
class Place:
    name: str
    kind: str  # "country" | "city" | "coordinates"
    latitude: float
    longitude: float
    iso: str | None = None
    zoom: float = 4.0

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "iso": self.iso,
            "zoom": self.zoom,
        }


# Approximate centroids, good enough to frame a country or a basin.
COUNTRIES: tuple[Place, ...] = (
    Place("Afghanistan", "country", 33.94, 67.71, "AF"),
    Place("Algeria", "country", 28.03, 1.66, "DZ"),
    Place("Angola", "country", -11.20, 17.87, "AO"),
    Place("Argentina", "country", -38.42, -63.62, "AR"),
    Place("Australia", "country", -25.27, 133.78, "AU"),
    Place("Austria", "country", 47.52, 14.55, "AT"),
    Place("Bangladesh", "country", 23.68, 90.36, "BD"),
    Place("Belgium", "country", 50.50, 4.47, "BE"),
    Place("Benin", "country", 9.31, 2.32, "BJ"),
    Place("Bolivia", "country", -16.29, -63.59, "BO"),
    Place("Botswana", "country", -22.33, 24.68, "BW"),
    Place("Brazil", "country", -14.24, -51.93, "BR"),
    Place("Burkina Faso", "country", 12.24, -1.56, "BF"),
    Place("Cambodia", "country", 12.57, 104.99, "KH"),
    Place("Cameroon", "country", 7.37, 12.35, "CM"),
    Place("Canada", "country", 56.13, -106.35, "CA"),
    Place("Chad", "country", 15.45, 18.73, "TD"),
    Place("Chile", "country", -35.68, -71.54, "CL"),
    Place("China", "country", 35.86, 104.20, "CN"),
    Place("Colombia", "country", 4.57, -74.30, "CO"),
    Place("Côte d'Ivoire", "country", 7.54, -5.55, "CI"),
    Place("DR Congo", "country", -4.04, 21.76, "CD"),
    Place("Ecuador", "country", -1.83, -78.18, "EC"),
    Place("Egypt", "country", 26.82, 30.80, "EG"),
    Place("Ethiopia", "country", 9.15, 40.49, "ET"),
    Place("Finland", "country", 61.92, 25.75, "FI"),
    Place("France", "country", 46.23, 2.21, "FR"),
    Place("Germany", "country", 51.17, 10.45, "DE"),
    Place("Ghana", "country", 7.95, -1.02, "GH"),
    Place("Greece", "country", 39.07, 21.82, "GR"),
    Place("Guinea", "country", 9.95, -9.70, "GN"),
    Place("India", "country", 20.59, 78.96, "IN"),
    Place("Indonesia", "country", -0.79, 113.92, "ID"),
    Place("Iran", "country", 32.43, 53.69, "IR"),
    Place("Iraq", "country", 33.22, 43.68, "IQ"),
    Place("Italy", "country", 41.87, 12.57, "IT"),
    Place("Japan", "country", 36.20, 138.25, "JP"),
    Place("Kazakhstan", "country", 48.02, 66.92, "KZ"),
    Place("Kenya", "country", -0.02, 37.91, "KE"),
    Place("Libya", "country", 26.34, 17.23, "LY"),
    Place("Madagascar", "country", -18.77, 46.87, "MG"),
    Place("Malawi", "country", -13.25, 34.30, "MW"),
    Place("Mali", "country", 17.57, -4.00, "ML"),
    Place("Mauritania", "country", 21.01, -10.94, "MR"),
    Place("Mexico", "country", 23.63, -102.55, "MX"),
    Place("Morocco", "country", 31.79, -7.09, "MA"),
    Place("Mozambique", "country", -18.67, 35.53, "MZ"),
    Place("Myanmar", "country", 21.91, 95.96, "MM"),
    Place("Namibia", "country", -22.96, 18.49, "NA"),
    Place("Nepal", "country", 28.39, 84.12, "NP"),
    Place("Niger", "country", 17.61, 8.08, "NE"),
    Place("Nigeria", "country", 9.08, 8.68, "NG"),
    Place("Norway", "country", 60.47, 8.47, "NO"),
    Place("Pakistan", "country", 30.38, 69.35, "PK"),
    Place("Papua New Guinea", "country", -6.31, 143.96, "PG"),
    Place("Paraguay", "country", -23.44, -58.44, "PY"),
    Place("Peru", "country", -9.19, -75.02, "PE"),
    Place("Philippines", "country", 12.88, 121.77, "PH"),
    Place("Poland", "country", 51.92, 19.15, "PL"),
    Place("Portugal", "country", 39.40, -8.22, "PT"),
    Place("Romania", "country", 45.94, 24.97, "RO"),
    Place("Russia", "country", 61.52, 105.32, "RU"),
    Place("Senegal", "country", 14.50, -14.45, "SN"),
    Place("Sierra Leone", "country", 8.46, -11.78, "SL"),
    Place("Somalia", "country", 5.15, 46.20, "SO"),
    Place("South Africa", "country", -30.56, 22.94, "ZA"),
    Place("South Sudan", "country", 6.88, 31.31, "SS"),
    Place("Spain", "country", 40.46, -3.75, "ES"),
    Place("Sudan", "country", 12.86, 30.22, "SD"),
    Place("Sweden", "country", 60.13, 18.64, "SE"),
    Place("Tanzania", "country", -6.37, 34.89, "TZ"),
    Place("Thailand", "country", 15.87, 100.99, "TH"),
    Place("Turkey", "country", 38.96, 35.24, "TR"),
    Place("Uganda", "country", 1.37, 32.29, "UG"),
    Place("Ukraine", "country", 48.38, 31.17, "UA"),
    Place("United Kingdom", "country", 55.38, -3.44, "GB"),
    Place("United States", "country", 37.09, -95.71, "US"),
    Place("Venezuela", "country", 6.42, -66.59, "VE"),
    Place("Vietnam", "country", 14.06, 108.28, "VN"),
    Place("Zambia", "country", -13.13, 27.85, "ZM"),
    Place("Zimbabwe", "country", -19.02, 29.15, "ZW"),
)

CITIES: tuple[Place, ...] = (
    Place("Abidjan", "city", 5.36, -4.01, "CI", 9),
    Place("Abuja", "city", 9.06, 7.49, "NG", 9),
    Place("Accra", "city", 5.60, -0.19, "GH", 9),
    Place("Addis Ababa", "city", 9.02, 38.75, "ET", 9),
    Place("Bamako", "city", 12.64, -8.00, "ML", 9),
    Place("Brasília", "city", -15.79, -47.88, "BR", 9),
    Place("Cairo", "city", 30.04, 31.24, "EG", 9),
    Place("Cape Town", "city", -33.92, 18.42, "ZA", 9),
    Place("Dar es Salaam", "city", -6.79, 39.21, "TZ", 9),
    Place("Dhaka", "city", 23.81, 90.41, "BD", 9),
    Place("Jakarta", "city", -6.21, 106.85, "ID", 9),
    Place("Kano", "city", 12.00, 8.52, "NG", 9),
    Place("Kinshasa", "city", -4.44, 15.27, "CD", 9),
    Place("Kolkata", "city", 22.57, 88.36, "IN", 9),
    Place("Lagos", "city", 6.52, 3.38, "NG", 9),
    Place("Lima", "city", -12.05, -77.04, "PE", 9),
    Place("Lusaka", "city", -15.39, 28.32, "ZM", 9),
    Place("Manila", "city", 14.60, 120.98, "PH", 9),
    Place("Mexico City", "city", 19.43, -99.13, "MX", 9),
    Place("Nairobi", "city", -1.29, 36.82, "KE", 9),
    Place("Ouagadougou", "city", 12.37, -1.52, "BF", 9),
    Place("Perth", "city", -31.95, 115.86, "AU", 9),
    Place("Rio de Janeiro", "city", -22.91, -43.17, "BR", 9),
    Place("Sydney", "city", -33.87, 151.21, "AU", 9),
)

PLACES: tuple[Place, ...] = COUNTRIES + CITIES


def parse_coordinates(query: str) -> Place | None:
    match = COORDINATE_PATTERN.match(query)
    if not match:
        return None
    latitude = float(match.group(1))
    longitude = float(match.group(2))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return Place(
        name=f"{latitude:.4f}, {longitude:.4f}",
        kind="coordinates",
        latitude=latitude,
        longitude=longitude,
        zoom=9,
    )


def search(query: str, limit: int = 8) -> list[Place]:
    """Prefix-first search; coordinate pairs take precedence."""
    text = query.strip()
    if not text:
        return []

    coordinates = parse_coordinates(text)
    if coordinates is not None:
        return [coordinates]

    lowered = text.lower()
    prefix: list[Place] = []
    contains: list[Place] = []
    for place in PLACES:
        name = place.name.lower()
        if name.startswith(lowered):
            prefix.append(place)
        elif lowered in name:
            contains.append(place)

    prefix.sort(key=lambda place: (place.kind != "country", len(place.name)))
    return (prefix + contains)[:limit]
