# Contributing

Thank you for helping improve Alfaifi Model Advisor.

## Good contribution areas

- Hardware detection for additional Windows GPU configurations.
- Trusted official model-family adapters.
- Model compatibility and memory-estimation improvements.
- Recommendation calibration supported by reproducible evidence.
- Accessibility, terminal compatibility, documentation, and tests.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Contribution requirements

- Keep the user interface and documentation in English.
- Add tests for behavior changes.
- Use official or primary sources for model metadata.
- Never add telemetry or upload hardware information without a separately
  reviewed, explicit opt-in design.
- Never download a model without explicit user approval.
- Do not add arbitrary shell execution or untrusted model sources.
- Preserve the LICENSE, NOTICE, and trademark policy.

By intentionally submitting a contribution for inclusion in this project, you
agree that it is licensed under the Apache License, Version 2.0, as described in
Section 5 of that license.
