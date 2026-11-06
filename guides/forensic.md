# Forensic — outcome guide

**Outcome:** Build a traceable demonstrative reconstruction.

## When to use
Use workflow.forensic_recon or workflow.forensic_scene for supported explicit measurements. Keep measured facts, hypotheses and approximations separate. Capture source units and references.

## When not to use
Do not present inferred geometry or camera angles as forensic evidence, do not claim legal admissibility, and do not hide missing dimensions.

## Preconditions
Measured scene geometry, coordinate system, provenance per input and scenario assumptions

## Verification
Export measurements, render views, scene file and an evidence ledger with unknowns clearly labeled.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
