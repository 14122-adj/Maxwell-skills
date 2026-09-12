---
name: Pull Request
about: Contribute to ansys-maxwell-motor
title: "[PR] "
---

## What does this PR do?

<!-- One paragraph summary. -->

## Type of change

<!-- Check all that apply -->
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would break existing behavior)
- [ ] Documentation update
- [ ] Refactor (no functional change)

## How was it tested?

<!-- List the test cases you ran. -->
- [ ] `pytest tests/` — all pass
- [ ] `ruff format --check scripts tests examples` — clean
- [ ] `ruff check scripts tests examples` — clean
- [ ] Manual smoke test (describe below)

Manual test:
```bash
# What you ran
python scripts/winding_layout.py 12 8 --list
# Expected output
# ...
```

## Checklist

- [ ] My code follows the project's style (`ruff format` + `ruff check`)
- [ ] I added tests for new functionality (or explained why not in PR description)
- [ ] I updated `CHANGELOG.md` under "Unreleased"
- [ ] I updated `references/winding_layouts.md` if I added a new pole-slot combo
- [ ] I updated `CANONICAL_LAYOUTS` in `scripts/pmsm_winding_builder.py` if applicable
- [ ] My changes don't introduce new warnings

## Related issues

<!-- Link related issues: "Fixes #123" or "Closes #456" -->

## Screenshots / Output

<!-- If applicable, paste the slot map or Maxwell script your change produces. -->
