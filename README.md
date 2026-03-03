# CISSA

This document is Work in Progress.  Do not blindly follow it.

The repo contains the Python implementation of the CISSA methodology to
value companies. It also contains a portfolio optimization tool that uses
the CISSA methodology to optimize a portfolio of companies.

The legacy repository for this work is located in: `https://github.com/rozettatechnology/basos-ds`. This new repository will contain code for the CISSA MVP.

## Installation

Requires Python 3.14 and [Anaconda/Miniconda](https://docs.conda.io/projects/miniconda/en/latest/).

### Setup Steps

1. **Install Miniconda** (if not already installed):
   ```bash
   # Download and install Miniconda
   cd /tmp
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
   bash Miniconda3-latest-Linux-x86_64.sh -b -p ~/miniconda3
   source ~/miniconda3/bin/activate
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/rozettatechnology/cissa
   cd cissa
   ```

3. **Create and activate the virtual environment**:
   ```bash
   source ~/miniconda3/bin/activate
   conda create -n cissa_env python=3.14 -y
   conda activate cissa_env
   ```

4. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

### Using the Environment

To activate the environment in future sessions:
```bash
source ~/miniconda3/bin/activate
conda activate cissa_env
```

To deactivate:
```bash
conda deactivate
```
