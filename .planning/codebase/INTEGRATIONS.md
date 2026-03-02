# External Integrations

**Analysis Date:** 2026-03-02

## APIs & External Services

**Data Sources:**
- Not yet specified - project will require financial data sources
- Planned inputs: Company financial information (from user, file, or external source)

**Legacy System Integration:**
- Legacy Repository: `https://github.com/rozettatechnology/basos-ds`
- Purpose: Source of reference implementation for CISSA methodology
- Integration: Code migration/adaptation (not API integration)
- Status: To be migrated/reimplemented for MVP

## Data Storage

**Databases:**
- Not specified - project currently works with in-memory data
- Future candidates for consideration:
  - PostgreSQL (relational data for company financials)
  - SQLite (lightweight, local development)
  - No specification yet (may depend on deployment model)

**File Storage:**
- Local filesystem only
- Input format: Not yet specified (likely CSV, JSON, or Excel)
- Output format: Not yet specified

**Caching:**
- None - not currently implemented

## Authentication & Identity

**Auth Provider:**
- Not applicable - MVP appears to be a computational library/tool
- If deployed as a service: Authentication layer to be determined

## Monitoring & Observability

**Error Tracking:**
- Not specified

**Logs:**
- Logging approach: Not yet established
- Log location: .gitignore excludes `*.log` files (indicates logging may be added)
- Log patterns: Legacy references suggest `basos_log.log` may have been used in previous implementation

## CI/CD & Deployment

**Hosting:**
- Not specified - project is an MVP library
- Deployment model not yet determined (could be: PyPI package, private package, container, web service)

**CI Pipeline:**
- Not configured - GitHub repository is set up but no CI/CD workflows present
- Planned tools (not yet implemented):
  - GitHub Actions (likely, given GitHub hosting)
  - Testing runner (pytest expected)
  - Linting/code quality (pylint, flake8, black mentioned in .gitignore patterns)

**GitHub Setup:**
- Repository: `https://github.com/rozettatechnology/cissa`
- Visibility: Appears to be private (RoZetta organization)
- .github/ directory: Not present (CI/CD workflows not yet configured)

## Environment Configuration

**Configuration Approach:**
- Environment variables referenced in .gitignore (.env file exclusion)
- Suggests future use of dotenv for configuration management

**Required env vars:**
- Not yet specified
- Likely candidates once implementation begins:
  - Data source credentials (if consuming external APIs)
  - Database connection strings (if using database)
  - Logging configuration

**Secrets location:**
- .env file (local) - excluded from version control
- .env.local, .env.development.local, .env.production.local - all excluded from git

## Webhooks & Callbacks

**Incoming:**
- Not applicable

**Outgoing:**
- Not applicable

## Development Tools & Services

**Code Quality (indicated by .gitignore):**
- SonarQube: `.scannerwork/` directory excluded (indicates SonarQube may be used for analysis)
- PyLint: `pylint.log` excluded
- ShellCheck: `shellcheck.log` excluded
- YAMLLint: `yamllint.log` excluded

**Testing Output:**
- Test results: `test-results.xml` excluded
- Coverage reports: `coverage/`, `.coverage`, `coverage.xml` excluded (indicates coverage analysis is planned)

**IDE Support:**
- VS Code: `.vscode/` excluded
- IntelliJ IDEA: `.idea/` excluded
- NetBeans: `nbproject` excluded

## Planned Integration Needs

**For CISSA Valuation Engine:**
1. Financial data input source (CSV, API, database)
2. Mathematical/numerical libraries for calculations
3. Optimization libraries for algorithm implementation

**For Portfolio Optimization:**
1. Linear/quadratic programming library (cvxpy, pulp, scipy)
2. Data validation and constraint handling
3. Results output format (JSON, CSV, database)

---

*Integration audit: 2026-03-02*
