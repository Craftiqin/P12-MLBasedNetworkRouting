# Python ML and graph-simulation setup

## Requirements

Python **3.11** recommended and pinned dependencies in root `requirements.txt`: NetworkX, NumPy, pandas, scikit-learn, joblib (transitive), Streamlit, Plotly; pytest for checks. Current lock pins reflect the validated authoring environment. The application imports from the repository root; run commands there.

### macOS/Linux

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python tools/validation/validate_environment.py --python-only
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python tools/validation/validate_environment.py --python-only
```

If PowerShell blocks activation, use the current process only: `Set-ExecutionPolicy -Scope Process RemoteSigned`, then activate. Or call `.venv\Scripts\python.exe` directly.

### Windows Command Prompt

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python tools\validation\validate_environment.py --python-only
```

Train via `python train_model.py`; run paired experiments via `python run_experiments.py`; open dashboard via `streamlit run app.py`. Details: [ML README](../../ml/README.md). No network/database credentials required.
