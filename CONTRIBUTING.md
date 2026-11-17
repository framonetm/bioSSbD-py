# Contributing

Thank you for helping improve bioSSbD-py.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev,notebooks]"
pytest -q
```

## Good first contributions

- **Hazard data:** add substances to `src/biossbd/hazards.py` with their harmonised GHS classification and a source.
- **Process hazards:** biological or process hazards for other biorefinery routes (fermentation, pyrolysis, HTL).
- **Indices:** further inherent-safety indices (PIIS, I2SI, Dow F&EI) in `src/biossbd/safety/indices.py`, with a test against a published worked example.
- **Case studies:** a YAML system in `examples/` plus a test reproducing published results.

## Rules

- Every new method needs a test, ideally reproducing a published number.
- Cite the source of every default value in the docstring.
- Keep the core dependency-free beyond numpy, pandas, pydantic and pyyaml; heavier libraries go in optional extras.
- Licence: contributions are accepted under MIT. Do not copy code from copyleft (GPL) projects.
