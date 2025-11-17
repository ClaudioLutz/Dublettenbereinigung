Here’s a stack that fits *exactly* with your brainstorming and the existing SQL rules (Quelle 95, Zweitname, Geburtstag/Jahrgang etc.). 

I’ll group it by *what* you want to do: fuzzy + name swapping, blocking, normalization, scaling, and (later) ML scoring.

---

## 1. Core for fuzzy name matching & name swapping

### 1.1 RapidFuzz (primary workhorse)

**Library:** `rapidfuzz` ([PyPI][1])

Why it fits:

* Very fast fuzzy string matching in C++ with Python bindings.
* Provides Levenshtein, Jaro(-Winkler), token-based measures, etc.
* MIT license (unlike the older FuzzyWuzzy GPL issue).
* Perfect for:

  * `Vorname` / `Name` fuzzy similarity
  * Testing all 4 combinations (normal + swapped, exact + fuzzy) from your matrix.

Example pattern for your Stage 2 engine:

```python
from rapidfuzz import fuzz, distance

def name_similarity(a_first, a_last, b_first, b_last):
    normal = (fuzz.QRatio(a_first, b_first),
              fuzz.QRatio(a_last,  b_last))
    swapped = (fuzz.QRatio(a_first, b_last),
               fuzz.QRatio(a_last,  b_first))
    return {
        "normal_first": normal[0],
        "normal_last":  normal[1],
        "swapped_first": swapped[0],
        "swapped_last":  swapped[1],
    }
```

You then plug these into your scoring logic (e.g. > 90 = almost exact, 80–90 = suspicious, etc.).

### 1.2 Low-level distance (optional)

If you ever want bare-metal Levenshtein distance (e.g. for custom thresholds per name length):

* **`Levenshtein`** (C extension from the RapidFuzz author) ([GitHub][2])

RapidFuzz already wraps these metrics, so for the POC you can probably stay with RapidFuzz only.

---

## 2. Record linkage / dedup frameworks

These sit on top of the string libraries and give you indexing/blocking + classifiers.

### 2.1 Python Record Linkage Toolkit (`recordlinkage`)

**Library:** `recordlinkage` ([PyPI][3])

What it gives you:

* Indexing (blocking) methods: block on `Plz`, `Plz+Jahrgang`, etc.
* Comparison functions for strings, dates, exact matches.
* Classifiers (e.g. logistic regression) to combine similarities into one match score.

Why it fits your brainstorming:

* You already defined **blocking by PLZ** as primary idea and possibly PLZ+birth year later. 
* RecordLinkage lets you declare:

  * Block on PLZ
  * Compare Vorname/Name with fuzzy metrics
  * Compare Strasse/Hausnummer/Plz/Ort with exact matches (Phase 1)
  * Apply current birthday/Jahrgang rules (exact year match, etc.)

Caveat: docs say it’s aimed at *small to medium* files, but with good blocking and batch processing it can still handle millions of rows reasonably well. ([recordlinkage.readthedocs.io][4])

Use case: good for **transparent POC**, where you want to see and tweak similarity per field.

### 2.2 Dedupe (`dedupe` from dedupe.io)

**Library:** `dedupe` ([GitHub][5])

What it gives you:

* ML-based deduplication and entity resolution on structured data.
* Active learning: you label some pairs (“match / not match”), dedupe learns thresholds and weights.
* Built-in blocking and scalable to large datasets.

Why it fits your fraud setup:

* You eventually want to **learn from confirmed fraud investigations**; dedupe is built exactly for that feedback loop.
* Very strong when:

  * Fields are noisy,
  * Fraudsters change multiple attributes at once,
  * You want the model to refine itself over time.

Trade-off:

* More setup (labeling) than a pure rules/rapidfuzz approach.
* I’d use it in **Phase 2/3** once the conservative rule-based POC is stable, as your brainstorming already suggests a future ML stage. 

---

## 3. Address + name normalization (German specifics)

Right now your POC keeps address fields exact, but you already planned normalisation and German-specific tweaks for later phases. 

### 3.1 International address parsing / normalization

For Strasse/Hausnummer/Plz/Ort:

* **`pypostal` (libpostal bindings)** – parses + normalizes international addresses. ([GitHub][6])

  * Good for: “Musterstr.” vs “Musterstraße”, different orderings, extra suffixes, etc.

* **`postal-address`** / **`py-address-formatter`** for formatting / cleaning components. ([PyPI][7])

These aren’t needed for the initial “address exact, only names fuzzy” POC, but are perfect for Phase 2 when you want to safely relax address rules while keeping fraud false-positives low.

### 3.2 Umlauts & accents (Müller / Mueller / ß → ss)

To normalize German names:

* **`Unidecode`**: transliterate “Müller” → “Muller” and in general strip accents in a sensible way. ([PyPI][8])

Combined with your own mapping rules:

```python
from unidecode import unidecode

def normalize_name(name: str) -> str:
    name = name.strip().lower()
    # custom replacements first
    name = name.replace('ß', 'ss')
    # then general accent removal
    name = unidecode(name)
    return name
```

This plugs straight into the preprocessing box you drew in the architecture sketch. 

---

## 4. Scaling to millions of records

Your notes explicitly mention *millions of records* and the need for blocking + vectorization. 

### 4.1 Pandas + Dask (scale-out of your POC)

* **pandas**: first implementation for:

  * Reading from `[CAG_Analyse].[dbo].[vAdresse_Quelle95]`
  * Applying normalization + RapidFuzz pairwise matches within PLZ blocks.

* **Dask**: if data doesn’t fit into RAM on one machine.
  Dask extends pandas-like APIs to out-of-core / distributed computation, ideal for scaling a pandas-based pipeline. ([dask.org][9])

Pattern:

1. Pull data from SQL Server in chunks or via parquet.
2. Block by PLZ (and maybe Jahrgang) using groupby in Dask.
3. Within each block, run vectorized RapidFuzz comparisons.

### 4.2 PySpark (if you already have or plan a Spark stack)

* **PySpark** is the Python API for Apache Spark, used for distributed data processing at large scale. ([Apache Spark][10])

Usage pattern for you:

* Load vAdresse_Quelle95 into a Spark DataFrame.
* Use **Spark SQL** for Stage 1 exact rules (you essentially re-implement your current SQL).
* Use:

  * blocking via `repartition("Plz")` or similar,
  * UDFs or Pandas UDFs calling RapidFuzz for name similarity within each block.

If you *don’t* already have Spark infra, I’d keep it simple and start with pandas + Dask.

---

## 5. ML-based scoring (future phase)

Your brainstorming talks about a **confidence score (0–100)** and later ML for pattern learning.

For that:

* **scikit-learn** – classic ML library for classification/regression on structured features. ([Scikit-learn][11])

Use case:

1. Build feature vectors per candidate pair:

   * e.g. `sim_vorname_normal`, `sim_vorname_swapped`, `sim_name_normal`, `sim_name_swapped`,
   * binary flags for exact address match, exact year match, Zweitname match, etc.
2. Train a model (logistic regression, gradient boosting) to output probability that this pair is a real duplicate/fraud case.
3. Map probability to your 0–100 confidence and set thresholds for manual review.

**Alternative / complement:** use Dedupe’s built-in ML instead of rolling your own classifier (Section 2.2).

---

## 6. Glue to SQL Server and your current rules

To integrate with `[CAG_Analyse].[dbo].[vAdresse_Quelle95]`:

* **`pyodbc` or `SQLAlchemy`** to read from SQL Server into pandas.
* Stage 1 (exact rules) can either:

  * stay in SQL (as now) and only pass candidate pairs to Python for fuzzy Stage 2, or
  * be reimplemented in Python using straightforward filters – but I’d keep it in SQL so you benefit from existing indexes.

---

## 7. Recommended minimal stack per phase

### Phase 1 – conservative POC (fastest path)

* **Data & DB**

  * `pandas` + `pyodbc`/`sqlalchemy`
* **Fuzzy & normalization**

  * `rapidfuzz`
  * `Unidecode` (simple name normalization)
* **Optionally**

  * `recordlinkage` for blocking + comparison framework
* Execution: plain pandas, maybe Dask later.

### Phase 2 – robustness & performance

* Address normalization: `pypostal` (libpostal) + possibly `postal-address` / `py-address-formatter`.
* Scaling: Dask or PySpark, depending on infra.
* More advanced blocking: implemented either manually or via `recordlinkage` / `dedupe`.

### Phase 3 – ML

* Either:

  * `dedupe` for active-learning style entity resolution,
  * or `scikit-learn` for a custom classifier on your engineered similarity features.
