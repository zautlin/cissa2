# Technology Stack

**Analysis Date:** 2026-03-02

## Languages

**Primary:**
- Python 3.14 - Core implementation language for CISSA methodology and portfolio optimization

**Secondary:**
- None currently specified

## Runtime

**Environment:**
- Python 3.14 (as specified in README)
- Note: System has Python 3.12.3 available; environment setup uses conda for version management

**Package Manager:**
- pip - Python package installer
- conda - Conda environment/package manager (for virtual environment creation)
- Lockfile: Not present (requirements.txt exists but is empty)

## Frameworks

**Core:**
- No frameworks currently specified in requirements.txt

**Planned Dependencies (based on project purpose):**
- Numerical computation: Likely numpy or scipy for financial calculations
- Data handling: Likely pandas for managing company financial data
- Optimization: Likely scipy.optimize or specialized portfolio optimization library (e.g., cvxpy, pulp)
- Data science: Potentially scikit-learn for modeling

**Testing:**
- Not yet specified - will likely use pytest or unittest

**Build/Dev:**
- Not yet specified

## Key Dependencies

**Critical (to be added):**
- Numerical/Scientific: For valuation calculations and mathematical operations
- Optimization: For portfolio optimization algorithms
- Data Processing: For handling financial data inputs

**Infrastructure:**
- None currently specified

## Configuration

**Environment:**
- Virtual environment: Managed via conda with Python 3.14
- Configuration approach: Not yet established
- dotenv support: Mentioned in .gitignore (.env file exclusion) - suggests future use

**Build:**
- No build system currently configured
- Likely candidates: setuptools, setuptools with pyproject.toml, or poetry

## Platform Requirements

**Development:**
- Python 3.14 (as specified in README)
- conda or pip for package management
- Virtual environment recommended (conda create)
- Git for version control

**Production:**
- Python 3.14 runtime
- Installed dependencies from requirements.txt
- Deployment target not specified (could be: cloud function, web service, batch job, etc.)

## Package Structure

**Current:**
- Single requirements.txt at root (empty)
- No setup.py or pyproject.toml present

**Recommended Future Structure:**
- `requirements.txt` - Production dependencies
- `requirements-dev.txt` - Development dependencies (testing, linting, docs)
- `setup.py` or `pyproject.toml` - Package metadata and installation configuration
- Optional: `poetry.lock` or `Pipfile.lock` for dependency locking

## Version Constraints

**Python Version:**
- Required: 3.14 (strict requirement per README)
- Note: This is a future version; ensure CI/CD and development environments have access

**Dependency Versions:**
- Not yet specified - to be determined based on library selections

---

*Stack analysis: 2026-03-02*
