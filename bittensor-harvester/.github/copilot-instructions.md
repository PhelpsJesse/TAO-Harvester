# TAO Harvester Workspace Instructions

This repository is governed by the active requirements baseline in `docs/REQUIREMENTS_SPEC_v1.5.md`.

Mandatory guardrails:

- Treat `docs/REQUIREMENTS_SPEC_v1.5.md` as the controlling source for architecture, behavior, and implementation decisions.
- Treat `docs/IMPLEMENTATION_CHECKLIST_v1.5.md` as execution guidance under that baseline, not as a replacement for the specification.
- Before making code changes that affect behavior, verify the change against the relevant section of `docs/REQUIREMENTS_SPEC_v1.5.md`.
- If implementation and the requirements spec conflict, the spec governs until it is explicitly updated.
- Do not treat optional future exchange execution as a reason to skip required read-only accounting, reconciliation, or audit behavior already mandated by the spec.
- Keep development within Tier 1/Tier 2/Tier 3 boundaries defined by the requirements baseline.
- Preserve unattended resiliency guardrails: bounded retries, fail-closed behavior, explicit manual-intervention outcomes, and rerunnable recovery paths.
- When modifying any versioned requirements or checklist document, up-rev the document version instead of editing the old active baseline in place.

Working rules for this codebase:

- For reconciliation or harvesting work, re-check Section 7 and related constraints before changing formulas or adjustment logic.
- For workflow, retry, or automation changes, re-check the resiliency and stage-control sections before changing behavior.
- For execution, transfer, signing, or exchange work, re-check the phase and safety boundaries before enabling new actions.
- If a requested change is not covered clearly by the current baseline, stop and update the requirements documentation first or ask for that requirement decision.

Preferred implementation behavior:

- Make the smallest change that satisfies the active baseline.
- Maintain traceability between code behavior and the requirement it implements.
- Flag any discovered drift between code and `docs/REQUIREMENTS_SPEC_v1.5.md` as a defect to be corrected, not as an invitation to reinterpret the baseline.