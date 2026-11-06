# Reconstruction — outcome guide

**Outcome:** Rebuild or correct geometry, lighting and motion from references.

## When to use
Use workflow.reference_attach to register evidence; workflow.reference_score/score_sequence for numeric comparisons; workflow.reference_correct to recommend a typed correction; workflow.image_to_asset/image_to_scene/character_from_image for supported import/reconstruction; workflow.reference_camera_solve only on video.

## When not to use
Do not describe a single still as solved photogrammetry, promise 3D fidelity from an uncalibrated image, or auto-accept aesthetic similarity from PSNR alone. Check availability of optional generators.

## Preconditions
Reference file or plate, role, score tier, supported source, desired output, camera/calibration limits

## Verification
Compare rendered pixels, framing and geometry against the source; record PSNR/SSIM/LPIPS where possible and mark unresolved subjective differences.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
