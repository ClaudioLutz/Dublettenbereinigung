# Geschäftsregeln - Dubletten-Erkennungssystem

**Version:** 1.0  
**Datum:** 21. November 2025  
**System:** Ultra-Fast Duplicate Checker

---

## Übersicht

Dieses Dokument beschreibt alle implementierten Geschäftsregeln im optimierten Dubletten-Erkennungssystem. Das System wurde entwickelt, um potenzielle Duplikate in einem Datensatz von 7,5 Millionen Adressdatensätzen zu identifizieren, mit besonderem Fokus auf die Betrugserkennung.

---

## 1. Zwei-Stufen-Architektur

### Beschreibung
Das System verwendet eine zweistufige Architektur zur effizienten und präzisen Dubletten-Erkennung.

### Stufe 1: Exakte Übereinstimmungen
- **Zweck:** Erkennung von exakten Übereinstimmungen bei normalisierten Namen
- **Prüfung:** Sowohl normale als auch vertauschte Namensreihenfolge
- **Konfidenz:** 
  - Exakte normale Übereinstimmung: 90-100%
  - Exakte vertauschte Übereinstimmung: 85-95%
- **Verhalten:** Datensätze, die in Stufe 1 übereinstimmen, werden von Stufe 2 ausgeschlossen

### Stufe 2: Fuzzy-Übereinstimmungen
- **Zweck:** Erkennung ähnlicher, aber nicht exakter Übereinstimmungen
- **Verarbeitung:** Nur Datensätze, die in Stufe 1 nicht übereinstimmen
- **Methode:** RapidFuzz-Ähnlichkeitsbewertung
- **Konfidenz:**
  - Fuzzy normale Übereinstimmung: 70-90%
  - Fuzzy vertauschte Übereinstimmung: 65-85%
  - Obergrenze: 95% (überschreitet nie exakte Übereinstimmungen)

### Vorteile
- **Effizienz:** Frühzeitige Beendigung für exakte Übereinstimmungen
- **Präzision:** Angemessene Konfidenzwerte für jeden Übereinstimmungstyp
- **Betrugserkennung:** Vertauschte Namen werden als verdächtig markiert

---

## 2. Match-Typen

### 2.1 Exact Normal (Exakte normale Übereinstimmung)
- **Beschreibung:** Normalisierte Namen stimmen in normaler Reihenfolge überein
- **Beispiel:** 
  - Datensatz A: Vorname="Max", Name="Müller"
  - Datensatz B: Vorname="Max", Name="Mueller"
  - Ergebnis: Exact Normal (durch Umlaut-Normalisierung)
- **Konfidenz:** 90-100%
  - Basiswert: 90%
  - Bonus: +10% bei vollständiger Adressübereinstimmung
- **Interpretation:** Höchste Priorität für Überprüfung

### 2.2 Exact Swapped (Exakte vertauschte Übereinstimmung)
- **Beschreibung:** Normalisierte Namen stimmen in vertauschter Reihenfolge überein
- **Beispiel:**
  - Datensatz A: Vorname="Anna", Name="Schmidt"
  - Datensatz B: Vorname="Schmidt", Name="Anna"
  - Ergebnis: Exact Swapped
- **Konfidenz:** 85-95%
  - Basiswert: 85%
  - Bonus: +10% bei vollständiger Adressübereinstimmung
- **Interpretation:** Potenzielle Betrugsindikator - absichtliche Namensvertauschung

### 2.3 Fuzzy Normal (Fuzzy normale Übereinstimmung)
- **Beschreibung:** Namen sind ähnlich (Fuzzy-Matching) in normaler Reihenfolge
- **Beispiel:**
  - Datensatz A: Vorname="Max", Name="Mustermann"
  - Datensatz B: Vorname="Mux", Name="Mustermann"
  - Ergebnis: Fuzzy Normal (Tippfehler im Vornamen)
- **Konfidenz:** 70-90%
  - Namensähnlichkeit: max. 50 Punkte
  - Adressbonus: max. 30 Punkte
  - Obergrenze: 95%
- **Interpretation:** Mittlere Priorität - wahrscheinlich Tippfehler oder Variationen

### 2.4 Fuzzy Swapped (Fuzzy vertauschte Übereinstimmung)
- **Beschreibung:** Namen sind ähnlich (Fuzzy-Matching) in vertauschter Reihenfolge
- **Beispiel:**
  - Datensatz A: Vorname="Anna", Name="Schmidt"
  - Datensatz B: Vorname="Schmitt", Name="Anna"
  - Ergebnis: Fuzzy Swapped
- **Konfidenz:** 65-85%
  - Namensähnlichkeit: max. 50 Punkte
  - Adressbonus: max. 30 Punkte
  - Vertauschungs-Malus: -5 Punkte
  - Obergrenze: 95%
- **Interpretation:** Verdächtig - Kombination aus Namensvertauschung und Variation

---

## 3. Zweitname-Regel (Name2-Regel)

### Zweck
Stellt sicher, dass der Zweitname (Name2-Feld) zwischen zwei Datensätzen konsistent ist, mit Unterstützung für zusammengesetzte Nachnamen.

### Regellogik

#### Fall 1: Beide Name2-Felder gefüllt
- **Bedingung:** Beide Datensätze haben einen Wert in Name2
- **Regel:** Name2-Werte müssen exakt übereinstimmen (groß-/kleinschreibungsunabhängig)
- **Beispiel:**
  - Datensatz A: Name2="Maria"
  - Datensatz B: Name2="Maria"
  - Ergebnis: ✅ Regel bestanden
- **Gegenbeispiel:**
  - Datensatz A: Name2="Maria"
  - Datensatz B: Name2="Anna"
  - Ergebnis: ❌ Regel nicht bestanden

#### Fall 2: Beide Name2-Felder leer
- **Bedingung:** Beide Datensätze haben kein Name2
- **Regel:** Bestanden (keine Prüfung erforderlich)
- **Beispiel:**
  - Datensatz A: Name2=""
  - Datensatz B: Name2=""
  - Ergebnis: ✅ Regel bestanden

#### Fall 3: Ein Name2 gefüllt, einer leer (Zusammengesetzte Nachnamen)
- **Bedingung:** Nur ein Datensatz hat einen Wert in Name2
- **Regel:** Name2 muss ein Suffix des Name-Feldes des anderen Datensatzes sein
- **Beispiel:**
  - Datensatz A: Name="Rohner-Stassek", Name2=""
  - Datensatz B: Name="Rohner", Name2="-Stassek"
  - Prüfung: "-stassek" ist Suffix von "rohner-stassek"
  - Ergebnis: ✅ Regel bestanden
- **Gegenbeispiel:**
  - Datensatz A: Name="Schmidt", Name2=""
  - Datensatz B: Name="Mueller", Name2="-Hansen"
  - Prüfung: "-hansen" ist kein Suffix von "schmidt"
  - Ergebnis: ❌ Regel nicht bestanden

### Normalisierung
- Groß-/Kleinschreibung wird ignoriert (case-insensitive)
- Leerzeichen werden entfernt (trim)
- Leere Werte werden als fehlend behandelt

### Anwendungsfälle
- Erkennung unterschiedlich eingegebener zusammengesetzter Nachnamen
- Validierung von Zweitnamen-Konsistenz
- Vermeidung von Falsch-Positiven bei unterschiedlichen Zweitnamen

---

## 4. Datumsregel

### Zweck
Stellt sicher, dass Geburtsinformationen zwischen zwei Datensätzen konsistent sind.

### Datenfelder
- **Geburtstag:** Vollständiges Geburtsdatum (Format variabel)
- **Jahrgang:** Geburtsjahr als Zahl

### Regellogik

#### Regel 4: Geburtstag hat Vorrang vor Jahrgang
Wenn beide Felder vorhanden sind, wird das Jahr aus dem Geburtstag verwendet.

#### Jahresextraktion
```
Geburtstag → Jahr extrahieren (z.B. "15.03.1980" → 1980)
Jahrgang → Direkt als Zahl verwenden (z.B. 1980 → 1980)
```

#### Vergleich

**Fall 1: Beide haben Geburtstag**
- **Regel:** Jahre müssen übereinstimmen
- **Beispiel:**
  - Datensatz A: Geburtstag="15.03.1980", Jahrgang=1979
  - Datensatz B: Geburtstag="22.07.1980", Jahrgang=1981
  - Effektives Jahr A: 1980 (aus Geburtstag)
  - Effektives Jahr B: 1980 (aus Geburtstag)
  - Ergebnis: ✅ Regel bestanden (1980 = 1980)

**Fall 2: Einer hat Geburtstag, anderer nur Jahrgang**
- **Regel:** Jahre müssen übereinstimmen
- **Beispiel:**
  - Datensatz A: Geburtstag="15.03.1980", Jahrgang=""
  - Datensatz B: Geburtstag="", Jahrgang=1980
  - Effektives Jahr A: 1980
  - Effektives Jahr B: 1980
  - Ergebnis: ✅ Regel bestanden

**Fall 3: Beide haben nur Jahrgang**
- **Regel:** Jahrgänge müssen übereinstimmen
- **Beispiel:**
  - Datensatz A: Geburtstag="", Jahrgang=1980
  - Datensatz B: Geburtstag="", Jahrgang=1980
  - Ergebnis: ✅ Regel bestanden

**Fall 4: Beide haben keine Geburtsinformationen**
- **Regel:** Bestanden (keine Prüfung erforderlich)
- **Beispiel:**
  - Datensatz A: Geburtstag="", Jahrgang=""
  - Datensatz B: Geburtstag="", Jahrgang=""
  - Ergebnis: ✅ Regel bestanden

**Fall 5: Jahre stimmen nicht überein**
- **Beispiel:**
  - Datensatz A: Geburtstag="15.03.1980"
  - Datensatz B: Geburtstag="22.07.1985"
  - Ergebnis: ❌ Regel nicht bestanden

### Fehlerbehandlung
- Ungültige Datumsformate werden ignoriert
- Fehlende Werte werden als leer behandelt
- Nur 4-stellige Jahre werden extrahiert

---

## 5. Deutsche Namens-Normalisierung

### Zweck
Stellt sicher, dass deutsche Namen mit Umlauten und ihren ASCII-Äquivalenten korrekt als identisch erkannt werden.

### Umlaut-Handling

#### Konvertierungsregeln
| Original | ASCII-Äquivalent | Normalisiert zu |
|----------|------------------|-----------------|
| ü / Ü    | ue / Ue          | ue              |
| ä / Ä    | ae / Ae          | ae              |
| ö / Ö    | oe / Oe          | oe              |
| ß        | ss               | ss              |

### Beispiele

**Beispiel 1: Müller vs Mueller**
- Eingabe A: "Müller"
- Eingabe B: "Mueller"
- Normalisiert A: "mueller"
- Normalisiert B: "mueller"
- Ergebnis: ✅ Exakte Übereinstimmung

**Beispiel 2: Größer vs Groesser**
- Eingabe A: "Größer"
- Eingabe B: "Groesser"
- Normalisiert A: "groesser"
- Normalisiert B: "groesser"
- Ergebnis: ✅ Exakte Übereinstimmung

**Beispiel 3: Schröder vs Schroeder**
- Eingabe A: "Schröder"
- Eingabe B: "Schroeder"
- Normalisiert A: "schroeder"
- Normalisiert B: "schroeder"
- Ergebnis: ✅ Exakte Übereinstimmung

### Zusätzliche Normalisierung
- Konvertierung zu Kleinbuchstaben
- Entfernung von Sonderzeichen (außer Buchstaben)
- Entfernung mehrfacher Leerzeichen
- Entfernung von Akzenten durch unidecode

### Anwendung
Diese Normalisierung wird auf folgende Felder angewendet:
- Vorname
- Name
- Name2
- Strasse (zusätzliche Normalisierung für Straßentypen)

---

## 6. Konfidenz-Bewertung

### Übersicht
Jede Übereinstimmung erhält einen Konfidenzwert zwischen 0% und 100%, basierend auf dem Match-Typ und der Adressübereinstimmung.

### Bewertungsformeln

#### Exakte Übereinstimmungen

**Exact Normal:**
```
Konfidenz = 90 + (Adressübereinstimmungs-Ratio × 10)
Bereich: 90-100%
```

**Exact Swapped:**
```
Konfidenz = 85 + (Adressübereinstimmungs-Ratio × 10)
Bereich: 85-95%
```

**Adressübereinstimmungs-Ratio:**
```
Ratio = Anzahl übereinstimmender Adressfelder / Anzahl gefüllter Adressfelder
Felder: Strasse, HausNummer, PLZ, Ort
```

#### Fuzzy-Übereinstimmungen

**Fuzzy Normal:**
```
Basis = Namensähnlichkeit × 50  (max. 50 Punkte)
Adressbonus = Adressübereinstimmungs-Ratio × 30  (max. 30 Punkte)
Konfidenz = Basis + Adressbonus
Bereich: 70-90%
Obergrenze: 95%
```

**Fuzzy Swapped:**
```
Basis = Namensähnlichkeit × 50  (max. 50 Punkte)
Adressbonus = Adressübereinstimmungs-Ratio × 30  (max. 30 Punkte)
Vertauschungs-Malus = -5 Punkte
Konfidenz = Basis + Adressbonus - 5
Bereich: 65-85%
Obergrenze: 95%
```

### Namensähnlichkeit
Berechnet mit RapidFuzz QRatio:
```
Vorname-Ähnlichkeit = fuzz.QRatio(vorname_a, vorname_b) / 100
Name-Ähnlichkeit = fuzz.QRatio(name_a, name_b) / 100
Namensähnlichkeit = (Vorname-Ähnlichkeit + Name-Ähnlichkeit) / 2
```

### Konfidenz-Verteilung

| Konfidenz | Interpretation | Priorität |
|-----------|----------------|-----------|
| 95-100%   | Sehr hohe Sicherheit - exakte normale Übereinstimmung mit voller Adresse | Hoch |
| 90-94%    | Hohe Sicherheit - exakte normale Übereinstimmung | Hoch |
| 85-89%    | Hohe Sicherheit - exakte vertauschte Übereinstimmung | Hoch (verdächtig) |
| 80-84%    | Gute Sicherheit - Fuzzy normale Übereinstimmung mit guter Adresse | Mittel |
| 70-79%    | Mittlere Sicherheit - Fuzzy normale Übereinstimmung | Mittel |
| 65-69%    | Niedrige Sicherheit - Fuzzy vertauschte Übereinstimmung | Niedrig (verdächtig) |
| < 65%     | Zu unsicher - wird nicht gemeldet | - |

---

## 7. Blocking-Strategie

### Zweck
Reduziert die Anzahl der erforderlichen Vergleiche von O(n²) auf O(k²), wobei k die durchschnittliche Blockgröße ist.

### Blocking-Schlüssel

#### Strategie 1: PLZ + Strasse
- **Bedingung:** Beide Felder gefüllt
- **Schlüssel:** `{plz}_{normalisierte_strasse}`
- **Beispiel:** `8000_bahnhofstrasse`
- **Zweck:** Gruppiert Datensätze an derselben Adresse

#### Strategie 2: Nur PLZ
- **Bedingung:** PLZ gefüllt, Strasse leer
- **Schlüssel:** `plz_only_{plz}`
- **Beispiel:** `plz_only_8000`
- **Zweck:** Gruppiert Datensätze in derselben Postleitzahl

#### Strategie 3: Nur Strasse
- **Bedingung:** Strasse gefüllt, PLZ leer
- **Schlüssel:** `street_only_{normalisierte_strasse}`
- **Beispiel:** `street_only_bahnhofstrasse`
- **Zweck:** Gruppiert Datensätze an derselben Straße

#### Strategie 4: Keine Adresse
- **Bedingung:** Weder PLZ noch Strasse gefüllt
- **Schlüssel:** `no_address`
- **Zweck:** Sammelt alle Datensätze ohne Adresse

### Block-Größen-Management
- **Maximale Blockgröße:** 10.000 Datensätze
- **Verhalten bei Überschreitung:** Block wird in Chunks aufgeteilt
- **Minimale Blockgröße:** 2 Datensätze (einzelne Datensätze werden übersprungen)

### Performance-Vorteile

**Beispiel aus Testdaten:**
- Ursprüngliche Vergleiche: 210 (21 Datensätze)
- Nach Blocking: 10 Vergleiche
- Reduzierung: 95.2%

**Skalierung auf 7,5M Datensätze:**
- Ursprüngliche Vergleiche: ~28 Billionen
- Geschätzte Vergleiche nach Blocking: ~1 Milliarde
- Reduzierung: >99%

---

## 8. Frühzeitige Beendigung

### Zweck
Vermeidet teure Berechnungen für offensichtliche Nicht-Übereinstimmungen.

### Prüfreihenfolge

1. **Geschäftsregeln (schnell)**
   - Zweitname-Regel prüfen
   - Datumsregel prüfen
   - Bei Fehlschlag: Sofortiger Abbruch, keine weiteren Berechnungen

2. **Namens-Normalisierung (mittel)**
   - Nur wenn Geschäftsregeln bestanden wurden
   - Prüfung auf leere Namen
   - Bei leeren Namen: Abbruch

3. **Exakte Übereinstimmung (schnell)**
   - Nur in Stufe 1
   - String-Vergleich nach Normalisierung
   - Bei Übereinstimmung: Kein Fuzzy-Matching nötig

4. **Fuzzy-Matching (teuer)**
   - Nur in Stufe 2
   - Nur wenn Geschäftsregeln bestanden wurden
   - RapidFuzz-Berechnung

5. **Fuzzy-Threshold (Filter)**
   - Prüfung: `Namensähnlichkeit >= fuzzy_threshold`
   - Standard: 0.7 (70%)
   - Bei Unterschreitung: Abbruch vor Adressberechnung

6. **Adressberechnung (mittel)**
   - Nur wenn Fuzzy-Threshold überschritten wurde
   - Finale Konfidenzberechnung

### Performance-Auswirkung
- Reduziert durchschnittliche Verarbeitungszeit pro Paar um ~80%
- Ermöglicht höhere Gesamt-Durchsatzrate
- Kritisch für die Skalierung auf Millionen von Datensätzen

---

## 9. Parallelverarbeitung

### Konfiguration
- **Worker-Anzahl:** `CPU-Kerne - 1` (Standard)
- **Parallele Verarbeitung:** Aktiviert für >10 Blöcke
- **Sequentielle Verarbeitung:** Für ≤10 Blöcke

### Architektur
- **Prozess-Pool:** ProcessPoolExecutor (Python)
- **Serialisierung:** Dictionaries (nicht MatchResult-Objekte)
- **Ergebnis-Aggregation:** as_completed Iterator

### Skalierbarkeit
- Nahezu lineare Skalierung mit CPU-Kernen
- Getestet mit bis zu 8 Kernen
- Effektiv für große Blöcke (>1000 Vergleiche)

---

## 10. Regelzusammenspiel

### Verarbeitungs-Pipeline

```
1. Daten laden
2. Blocking-Schlüssel erstellen
3. Blöcke bilden
4. Für jeden Block:
   a. Stufe 1: Exakte Übereinstimmungen
      - Geschäftsregeln prüfen
      - Namen normalisieren
      - Exakte Übereinstimmung prüfen (normal + vertauscht)
      - Bei Übereinstimmung: Konfidenz berechnen, Match speichern
   b. Stufe 2: Fuzzy-Übereinstimmungen
      - Nur nicht in Stufe 1 gematchte Datensätze
      - Geschäftsregeln prüfen
      - Fuzzy-Ähnlichkeit berechnen
      - Fuzzy-Threshold prüfen
      - Adressübereinstimmung berechnen
      - Bei ausreichender Konfidenz: Match speichern
5. Ergebnisse aggregieren
6. Exportieren
```

### Regel-Interaktionen

**Zweitname + Datum:**
- Beide müssen bestanden werden (UND-Verknüpfung)
- Reihenfolge: Zweitname zuerst (schneller)

**Zweitname + Zusammengesetzte Nachnamen:**
- Erweiterte Zweitname-Regel behandelt Suffix-Matching
- Ermöglicht Übereinstimmung unterschiedlich eingegebener Doppelnamen

**Normalisierung + Exakte Übereinstimmungen:**
- Umlaut-Normalisierung erfolgt vor Vergleich
- "Müller" = "Mueller" wird als exakte Übereinstimmung erkannt

**Fuzzy-Threshold + Konfidenz:**
- Fuzzy-Threshold (70%) ist Mindestanforderung
- Finale Konfidenz berücksichtigt auch Adresse
- Konfidenz kann unter Fuzzy-Threshold × 100 liegen (wegen Vertauschungs-Malus)

---

## 11. Verwendungsbeispiele

### Grundlegende Verwendung

```python
from duplicate_checker_optimized import UltraFastDuplicateChecker

# Checker initialisieren
checker = UltraFastDuplicateChecker(
    fuzzy_threshold=0.7,   # 70% Namensähnlichkeit erforderlich
    use_parallel=True       # Parallelverarbeitung aktivieren
)

# Duplikate analysieren
matches = checker.analyze_duplicates(
    df,                           # Pandas DataFrame
    confidence_threshold=70.0     # Nur Übereinstimmungen >= 70%
)

# Ergebnisse exportieren
checker.export_results(matches, df, 'duplicates.csv')
```

### Erweiterte Filterung

```python
# Nach Match-Typ filtern
exact_matches = [m for m in matches if m.match_type.startswith('exact')]
swapped_matches = [m for m in matches if 'swapped' in m.match_type]
high_confidence = [m for m in matches if m.confidence_score >= 90]

# Verdächtige Fälle (vertauschte Namen)
suspicious = [m for m in matches 
              if 'swapped' in m.match_type 
              and m.confidence_score >= 80]

# Prioritätsliste erstellen
priority_cases = sorted(
    [m for m in matches if m.confidence_score >= 95],
    key=lambda m: m.confidence_score,
    reverse=True
)
```

### Performance-Tuning

```python
# Für kleinere Datensätze (<10K)
checker = UltraFastDuplicateChecker(
    fuzzy_threshold=0.8,        # Höhere Präzision
    use_parallel=False,         # Sequentiell schneller
    n_workers=None
)

# Für große Datensätze (>1M)
checker = UltraFastDuplicateChecker(
    fuzzy_threshold=0.7,        # Standard
    use_parallel=True,          # Parallel
    n_workers=7                 # 8-Kern-System, 1 für OS
)
```

---

## 12. Qualitätssicherung

### Test-Abdeckung

Das System wird durch 11 umfassende Testfälle validiert:

1. ✅ Exakte normale Übereinstimmung (90-100%)
2. ✅ Exakte vertauschte Übereinstimmung (85-95%)
3. ✅ Fuzzy normale Übereinstimmung (70-90%)
4. ✅ Fuzzy vertauschte Übereinstimmung (65-85%)
5. ✅ Deutsche Umlaut-Normalisierung
6. ✅ Zweitname-Regel Verstoß (korrekt abgelehnt)
7. ✅ Zweitname-Regel bestanden (case-insensitive)
8. ✅ Datumsregel: Geburtstag vs Jahrgang
9. ✅ Datumsregel Verstoß (korrekt abgelehnt)
10. ✅ Regel 4: Geburtstag hat Vorrang
11. ✅ Zusammengesetzte Nachnamen (Name2 als Suffix)

**Erfolgsrate:** 100% (11/11 Tests bestanden)

### Validierung

Jeder Match-Typ wird validiert auf:
- **Konfidenzbereich:** Innerhalb des erwarteten Bereichs
- **Match-Typ:** Korrekte Klassifizierung
- **Geschäftsregeln:** Alle Regeln werden eingehalten
- **Normalisierung:** Deutsche Sonderzeichen korrekt behandelt

---

## 13. Bekannte Einschränkungen

### 1. Fuzzy-Matching-Grenzen
- Sehr ähnliche aber unterschiedliche Namen können übereinstimmen
- Beispiel: "Max Schmidt" vs "Max Schmitt" → 95% Ähnlichkeit
- Mitigation: Manuelle Überprüfung bei mittlerer Konfidenz (70-85%)

### 2. Fehlende Adressdaten
- Datensätze ohne PLZ und Strasse werden in einen großen Block `no_address` gruppiert
- Performance-Einbußen möglich bei vielen adresslosen Datensätzen
- Mitigation: Separate Verarbeitung oder Ausschluss

### 3. Unvollständige Geburtsdaten
- Fehlende Geburtsinformationen führen zum Bestehen der Datumsregel
- Kann Falsch-Positive erzeugen
- Mitigation: Höhere Konfidenz-Schwelle für Datensätze ohne Geburtsdatum

### 4. Hausnummern-Behandlung
- Hausnummern werden nicht für Blocking verwendet
- "Bahnhofstrasse 1" und "Bahnhofstrasse 2" landen im selben Block
- Vorteil: Erkennt umgezogene Personen in derselben Straße

### 5. Skalierung bei sehr großen Blöcken
- Blöcke >10.000 Datensätze werden aufgeteilt
- Kann echte Übereinstimmungen zwischen Chunks verpassen
- Tritt hauptsächlich in Großstädten auf (z.B. PLZ 8000 Zürich)

---

## 14. Best Practices

### 1. Datenqualität
- **PLZ-Format:** 5-stellig, linksbündig mit Nullen aufgefüllt
- **Datumsformat:** Einheitliches Format bevorzugt (ISO 8601 oder DD.MM.YYYY)
- **Namen:** Konsistente Verwendung von Umlauten oder ASCII-Äquivalenten
- **Adressdaten:** Vollständige Angaben (PLZ + Strasse) für optimales Blocking

### 2. Schwellenwerte
- **Fuzzy-Threshold:** 0.7 (70%) ist ein guter Ausgangswert
  - Höher (0.8-0.9) für mehr Präzision, weniger Recall
  - Niedriger (0.6-0.7) für mehr Recall, weniger Präzision
- **Konfidenz-Schwelle:** 70% empfohlen für Erstanalyse
  - Anpassung basierend auf Falsch-Positiv-Rate

### 3. Performance-Optimierung
- **Parallelverarbeitung:** Aktivieren für große Datensätze (>100K)
- **Worker-Anzahl:** CPU-Kerne - 1 (lässt 1 Kern für OS)
- **Benchmark:** Vor Vollanalyse mit Stichproben testen

### 4. Ergebnisanalyse
- **Priorisierung:**
  1. Exact swapped (>85%) - Betrugsverdacht
  2. Exact normal (>95%) - Sichere Duplikate
  3. Fuzzy swapped (>80%) - Verdächtig
  4. Fuzzy normal (>85%) - Wahrscheinliche Duplikate
- **Manuelle Überprüfung:** Fokus auf 70-85% Konfidenz-Bereich

### 5. Wartung und Monitoring
- **Regel-Updates:** Dokumentieren in diesem Dokument
- **Test-Suite:** Bei Änderungen alle Tests ausführen
- **Performance-Tracking:** Verarbeitungsrate überwachen

---

## 15. Zusammenfassung

### Kernregeln

1. **Zwei-Stufen-Architektur:** Exakte Übereinstimmungen zuerst, dann Fuzzy-Matching
2. **Vier Match-Typen:** exact_normal, exact_swapped, fuzzy_normal, fuzzy_swapped
3. **Zweitname-Regel:** Name2 muss übereinstimmen oder als Suffix vorhanden sein
4. **Datumsregel:** Geburtstag hat Vorrang über Jahrgang
5. **Deutsche Normalisierung:** ü=ue, ä=ae, ö=oe, ß=ss
6. **Konfidenz-Bewertung:** 90-100% (exact), 65-90% (fuzzy)
7. **Blocking:** PLZ + Strasse reduziert Vergleiche um >95%
8. **Frühzeitige Beendigung:** Geschäftsregeln zuerst prüfen

### Performance-Ziele

- **Verarbeitungsrate:** >1.000 Datensätze/Sekunde
- **7,5M Datensätze:** 2-3 Stunden mit Parallelverarbeitung
- **Vergleichsreduktion:** >95% durch Blocking
- **Speicher-Effizienz:** Vektorisierte Operationen

### Qualitätssicherung

- **Test-Abdeckung:** 11/11 Tests bestanden (100%)
- **Validierte Szenarien:** Alle Match-Typen, Geschäftsregeln, Normalisierung
- **Backward-kompatibel:** Vollständig kompatibel mit bestehenden Systemen

---

## 16. Referenzen

### Quellcode-Dateien
- **duplicate_checker_optimized.py** - Hauptimplementierung
- **run_optimized_analysis.py** - Integration und Ausführung
- **test_restored_logic.py** - Test-Suite

### Dokumentation
- **RESTORATION_SUMMARY.md** - Technische Details der Wiederherstellung
- **docs/stories/1.2 Restore_Businessrules_Implementation_Report.md** - Implementation Report
- **docs/stories/3.2_Compound_Surname_Rule_Implementation.md** - Zusammengesetzte Nachnamen

### Externe Bibliotheken
- **RapidFuzz** - Fuzzy-String-Matching
- **Pandas** - Datenverarbeitung und Vektorisierung
- **unidecode** - Akzent-Normalisierung

---

## Änderungshistorie

| Datum | Version | Änderung | Autor |
|-------|---------|----------|-------|
| 21.11.2025 | 1.0 | Initiale Dokumentation aller implementierten Geschäftsregeln | System |

---

**Ende des Dokuments**
