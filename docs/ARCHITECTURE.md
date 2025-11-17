# Dubletten Project - Architecture Documentation

## Project Overview

**Project Name:** Dubletten (Duplicates Detection System)  
**Purpose:** Data analysis tool for detecting and analyzing duplicate address records from a SQL Server database  
**Primary Language:** Python  
**Database:** Microsoft SQL Server (CAG_Analyse)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Dubletten System                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   Configuration  │         │   Data Layer     │         │  External Data   │
│                  │         │                  │         │                  │
│  ┌────────────┐  │         │  ┌────────────┐  │         │  ┌────────────┐  │
│  │  .env      │──┼────────▶│  │  data.py   │◀─┼─────────│  │SQL Server  │  │
│  │            │  │         │  │            │  │         │  │            │  │
│  │ - Server   │  │         │  │ - Engine   │  │         │  │PRODSVCREPORT│
│  │ - DB       │  │         │  │ - Queries  │  │         │  │    70      │  │
│  │ - Driver   │  │         │  │ - DataOps  │  │         │  │            │  │
│  └────────────┘  │         │  └────────────┘  │         │  │CAG_Analyse │  │
│                  │         │                  │         │  │  Database  │  │
└──────────────────┘         └──────────────────┘         │  │            │  │
                                      │                    │  │vAdresse_   │  │
                                      │                    │  │Quelle95    │  │
                                      ▼                    │  └────────────┘  │
                             ┌──────────────────┐         └──────────────────┘
                             │  Data Processing │
                             │                  │
                             │  ┌────────────┐  │
                             │  │  Pandas    │  │
                             │  │  DataFrames│  │
                             │  └────────────┘  │
                             │                  │
                             │  ┌────────────┐  │
                             │  │  NumPy     │  │
                             │  │  Arrays    │  │
                             │  └────────────┘  │
                             └──────────────────┘
                                      │
                                      ▼
                             ┌──────────────────┐
                             │  Visualization   │
                             │                  │
                             │  ┌────────────┐  │
                             │  │ Matplotlib │  │
                             │  │   Plots    │  │
                             │  └────────────┘  │
                             └──────────────────┘
```

---

## System Components

### 1. Configuration Layer

#### `.env` File
- **Purpose:** Centralized configuration management
- **Contents:**
  - `DEFAULT_DRIVER`: ODBC Driver 17 for SQL Server
  - `DEFAULT_SERVER`: PRODSVCREPORT70
  - `DEFAULT_DB`: CAG_Analyse
- **Security:** Excluded from version control (should contain sensitive data)

### 2. Data Access Layer

#### `data.py` - Main Application Module
Core module handling database connectivity and data operations.

**Key Functions:**

##### `conn_string_sql_alchemy(server, db, driver)`
- **Purpose:** Constructs SQLAlchemy connection string
- **Parameters:**
  - `server`: SQL Server instance name
  - `db`: Database name
  - `driver`: ODBC driver specification
- **Returns:** Connection string with Windows authentication
- **Format:** `mssql://{server}/{db}?trusted_connection=yes&driver={driver}`

##### `erzeuge_engine_von_conn_string_sql_alchemy(conn_string)`
- **Purpose:** Creates and validates SQLAlchemy engine
- **Parameters:** Connection string
- **Returns:** SQLAlchemy engine object or None on failure
- **Features:**
  - Connection validation on creation
  - Exception handling and error reporting
  - Resource management

##### `schliess_engine(engine)`
- **Purpose:** Properly closes database engine and releases resources
- **Parameters:** SQLAlchemy engine
- **Returns:** None
- **Best Practice:** Ensures clean connection disposal

##### `lade_daten(engine, query)`
- **Purpose:** Executes SQL query and returns results as DataFrame
- **Parameters:**
  - `engine`: SQLAlchemy engine
  - `query`: SQL query string
- **Returns:** Pandas DataFrame with query results
- **Usage:** Primary data retrieval interface

### 3. Data Source

#### SQL Server Database
- **Server:** PRODSVCREPORT70
- **Database:** CAG_Analyse
- **Primary Table/View:** `vAdresse_Quelle95`
- **Authentication:** Windows Trusted Connection

#### Data Schema (vAdresse_Quelle95)
```sql
Columns:
- Name          : VARCHAR  - Last name
- Vorname       : VARCHAR  - First name
- Name2         : VARCHAR  - Additional name field
- Strasse       : VARCHAR  - Street name
- HausNummer    : VARCHAR  - House number
- Plz           : VARCHAR  - Postal code
- Ort           : VARCHAR  - City/Location
- Crefo         : INT      - Crefo identifier
- Geburtstag    : DATE     - Birth date
- Jahrgang      : INT      - Birth year
- Erfasst       : DATETIME - Record creation date
- Quelle_95     : VARCHAR  - Source identifier
```

### 4. Data Processing Layer

#### Libraries & Frameworks
- **Pandas:** DataFrame operations and data manipulation
- **NumPy:** Numerical operations and array handling
- **SQLAlchemy:** Database abstraction and ORM
- **Matplotlib:** Data visualization and plotting

---

## Data Flow

```
1. Configuration Loading
   └─▶ .env variables read

2. Connection Establishment
   ├─▶ Connection string construction
   ├─▶ SQLAlchemy engine creation
   └─▶ Connection validation

3. Data Retrieval
   ├─▶ SQL query execution
   ├─▶ Result set retrieval
   └─▶ DataFrame conversion

4. Data Processing
   ├─▶ Pandas data manipulation
   ├─▶ NumPy computations
   └─▶ Duplicate detection logic

5. Result Presentation
   ├─▶ Data visualization
   └─▶ Report generation
```

---

## Technology Stack

### Core Technologies
| Component | Technology | Version/Specification |
|-----------|-----------|----------------------|
| Language | Python | 3.x |
| Database | Microsoft SQL Server | - |
| ODBC Driver | ODBC Driver 17 for SQL Server | 17 |
| ORM/Database | SQLAlchemy | Latest |
| Data Processing | Pandas | Latest |
| Numerical Computing | NumPy | Latest |
| Visualization | Matplotlib | Latest |

### Development Environment
- **IDE:** Visual Studio Code
- **Platform:** Windows 11
- **Shell:** PowerShell

---

## Design Patterns & Principles

### 1. Connection Factory Pattern
- `erzeuge_engine_von_conn_string_sql_alchemy()` acts as a factory for database engines
- Centralizes engine creation logic
- Provides validation and error handling

### 2. Separation of Concerns
- Configuration (`.env`)
- Data access (`conn_string`, `lade_daten`)
- Business logic (to be implemented)
- Visualization (matplotlib integration)

### 3. Resource Management
- Explicit engine disposal with `schliess_engine()`
- Context managers for connection handling
- Error handling for connection failures

---

## Security Considerations

### Current Implementation
- **Windows Authentication:** Uses trusted connections (no passwords in code)
- **Environment Variables:** Database credentials in `.env` file
- **Connection String:** Parameterized construction

### Recommendations
1. Ensure `.env` is in `.gitignore`
2. Implement connection pooling for production
3. Add query parameterization to prevent SQL injection
4. Consider implementing read-only database access
5. Add audit logging for data access

---

## Future Architecture Considerations

### Scalability
1. **Connection Pooling:** Implement SQLAlchemy connection pools
2. **Batch Processing:** Handle large datasets in chunks
3. **Caching:** Add result caching for frequently run queries

### Modularity
1. **Separation of Modules:**
   - `config.py` - Configuration management
   - `database.py` - Database operations
   - `analysis.py` - Duplicate detection logic
   - `visualization.py` - Reporting and charts

2. **Configuration Management:**
   - Move to `python-dotenv` for `.env` loading
   - Add configuration validation
   - Support multiple environments (dev, test, prod)

### Testing
1. **Unit Tests:** Test individual functions
2. **Integration Tests:** Test database connectivity
3. **Mock Data:** Use test fixtures for development

### Duplicate Detection Enhancement
1. **Fuzzy Matching:** Implement string similarity algorithms
2. **Configurable Rules:** Define duplicate criteria
3. **Confidence Scoring:** Rate duplicate matches
4. **Manual Review Interface:** Flag uncertain matches

---

## Current Limitations

1. **Hard-coded Query:** SQL query embedded in main script
2. **No Error Handling:** Limited error handling for data operations
3. **No Logging:** No structured logging implementation
4. **No CLI Interface:** Interactive development only
5. **No Output Management:** No structured result export
6. **No Testing:** No automated tests present

---

## Deployment Architecture

### Current State
- **Deployment Type:** Development/Local execution
- **Execution Model:** Interactive (Jupyter-style cells with #%%)
- **Database Access:** Direct connection to production server

### Recommended Production Architecture
```
┌─────────────────────────────────────────────┐
│           Production Environment            │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │     Application Server             │    │
│  │                                    │    │
│  │  ┌──────────────────────────────┐ │    │
│  │  │   Dubletten Application      │ │    │
│  │  │   (Containerized)            │ │    │
│  │  └──────────────────────────────┘ │    │
│  └────────────────────────────────────┘    │
│                    │                        │
│                    ▼                        │
│  ┌────────────────────────────────────┐    │
│  │     Database Connection Pool       │    │
│  └────────────────────────────────────┘    │
│                    │                        │
└────────────────────┼────────────────────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │   SQL Server           │
         │   (Read Replica)       │
         └────────────────────────┘
```

---

## Integration Points

### Current Integrations
1. **SQL Server Database:** Primary data source
2. **ODBC Driver:** Database connectivity layer

### Potential Future Integrations
1. **Export Formats:** CSV, Excel, JSON
2. **Notification Systems:** Email alerts for duplicates
3. **Web Interface:** Dashboard for duplicate review
4. **API Layer:** REST API for programmatic access

---

## Documentation Structure

```
docs/
├── ARCHITECTURE.md          # This file - System architecture
├── API.md                   # API documentation (to be created)
├── DEPLOYMENT.md            # Deployment guide (to be created)
├── USER_GUIDE.md            # User manual (to be created)
└── sprint-artifacts/        # Agile artifacts and sprint docs
    ├── sprint-1/
    ├── sprint-2/
    └── ...
```

---

## Maintenance & Support

### Code Maintenance
- **Language:** German (variable names, comments)
- **Coding Style:** PEP 8 compliance recommended
- **Dependencies:** Managed via pip/requirements.txt (to be created)

### Monitoring
- No monitoring currently implemented
- Recommended: Add logging with Python's logging module
- Track: Query performance, error rates, data volumes

---

## Glossary

| Term | Definition |
|------|------------|
| Dubletten | German for "duplicates" - records appearing multiple times |
| Adresse | Address |
| Quelle | Source |
| Erfasst | Captured/Recorded |
| Geburtstag | Birthday |
| Jahrgang | Year of birth |
| Strasse | Street |
| Plz | Postal code (Postleitzahl) |
| Ort | Location/City |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-14 | Initial architecture documentation |

---

## Contact & Support

For questions or support regarding this architecture documentation, please refer to the project repository or contact the development team.
