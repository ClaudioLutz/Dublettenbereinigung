# Data Contract

This document defines the input requirements and expected data formats for the Duplicate Checker pipelines.

## 1. Input Source
The system expects data from a SQL Server View `vAdresse_Quelle95`.

## 2. Required Columns

| Column Name | Type | Description | Mandatory? |
| :--- | :--- | :--- | :--- |
| `Name` | VARCHAR | Last Name | Yes |
| `Vorname` | VARCHAR | First Name | No (but recommended) |
| `Name2` | VARCHAR | Additional Name / Company Suffix | No |
| `Strasse` | VARCHAR | Street Name | Yes |
| `HausNummer` | VARCHAR | House Number | No |
| `Plz` | VARCHAR | Postal Code (Postleitzahl) | Yes (for blocking) |
| `Ort` | VARCHAR | City | No |
| `Crefo` | INT | Unique Identifier (Source ID) | Yes (used as `record_id`) |
| `Geburtstag` | DATE | Date of Birth | No |
| `Jahrgang` | INT | Year of Birth | No (used for phonetic pass) |
| `Erfasst` | DATETIME | Record Creation Date | Yes (for filtering) |
| `Quelle_95` | VARCHAR | Source System ID | No |

## 3. Data Types & Normalization

*   **NULL Handling**:
    *   Missing strings should be `NULL` or empty string `''`.
    *   The pipeline converts all text to lowercase and strips whitespace during normalization.
    *   Missing `Plz` is treated as an empty string, preventing it from matching in the address blocking pass.
*   **PLZ (Postal Code)**:
    *   Expected to be a 5-digit string for German addresses.
    *   Leading zeros should be preserved (e.g., `01234`).
    *   Invalid PLZs (non-numeric) may cause blocking inefficiencies but are handled gracefully.
*   **Dates**:
    *   `Geburtstag` should be a valid SQL Date.
    *   `Jahrgang` is derived or explicitly provided as an Integer (YYYY).

## 4. Minimal Example Row

```json
{
  "Name": "Mustermann",
  "Vorname": "Max",
  "Name2": null,
  "Strasse": "Musterstraße",
  "HausNummer": "1",
  "Plz": "12345",
  "Ort": "Berlin",
  "Crefo": 100001,
  "Geburtstag": "1980-01-01",
  "Jahrgang": 1980,
  "Erfasst": "2023-01-01 12:00:00",
  "Quelle_95": "CRM"
}
```

## 5. PII & Security

*   **Personally Identifiable Information (PII)**: This dataset contains sensitive personal data (Names, Addresses, Birthdates).
*   **Handling**:
    *   Do not log actual data values in production logs (use `DEBUG` level only if necessary and sanitized).
    *   Do not commit CSV exports containing real data to version control.
    *   Ensure the `.gitignore` excludes `*.csv` and `*.parquet`.
