
# Filters & Option Detection

## Core vehicle filters
- **Generation**: must be **992.1** (NOT 991.x, NOT 992.2).
- **Model**: `Carrera 4 GTS` OR `GTS Coupe` (prefer AWD where available).
- **Accident history**: `Unfallfrei` only. Exclude `Nicht unfallfrei`.
- **Warranty**: must include `Porsche Approved` (>= 12 months).
- **Mileage**: <= configured threshold.

## Option keywords (German)
Listings are usually German. Detect options via keyword sets.

### Must-have
- Sport Chrono: `Sport Chrono`, `Sport Chrono Paket`
- Front lift: `Liftsystem Vorderachse`, `Front Axle Lift`, `Lift`
- Rear-axle steering: `Hinterachslenkung`
- Adaptive cruise: `Abstandsregeltempostat`, `ACC`, `InnoDrive`, `Porsche InnoDrive`
- Matrix lights: `LED-Matrix`, `Matrix`, `PDLS Plus`, `Porsche Dynamic Light System Plus`
- Audio: `BOSE`, `Burmester`
- 18-way seats: `Adaptive Sportsitze Plus (18-Wege`, `18-Wege`, `Memory-Paket`

### Nice-to-have
- 90L tank: `Kraftstoffbehälter 90 l`, `90 l`, `90 Liter Tank`
- 360 camera: `Surround View`, `360`, `Rückfahrkamera und Surround View`
- Glass sunroof: `Schiebe-/Hubdach`, `aus Glas`
- PPF: `Steinschlagschutzfolie`, `PPF`

## Explainability
For every listing, output:
- reasons it failed (if any)
- which options were detected
- confidence (low/med/high)
