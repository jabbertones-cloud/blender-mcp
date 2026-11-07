# November 6, 2026: resolve `sharp` vulnerability chain

This is a separate dependency-security remediation from the Blender MCP RQ render release. Exact starting main was `edd10c8ef0c753ac3f663badaa4115ea30eb6dac` and already had a working, live-retested M2 Blender 5.2.3 render deployment. These Node manifest changes do not alter the native Python/RQ path.

## Grounded defect

Three high-severity GitHub Dependabot alerts target the `sharp` manifest dependency: [libvips CVEs](https://github.com/advisories/GHSA-f88m-g3jw-g9cj), [libheif](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c), and [librsvg](https://github.com/advisories/GHSA-wq5f-xc86-pv6w). Dependabot's update job [#1686330820](https://github.com/jabbertones-cloud/blender-mcp/actions/runs/42329459173) could not update `sharp` because the old project had no `package-lock.json`. The original `package.json` declared `sharp:^0.33.5` but no tracked `.js`/`.mjs`/`.cjs`/`.ts` file directly imported it.

Deleting the direct dependency **alone failed**: npm still resolved `@gltf-transform/functions 4.3.0` -> `ndarray-pixels 5.0.1` -> vulnerable `sharp 0.34.5`. `npm audit --package-lock-only --json` reported two high-severity vulnerable package nodes (`sharp` and `ndarray-pixels`) in that attempted graph. This was a measured negative control, not a completed fix.

## Donor solution and measured result

Official npm dependency metadata showed `@gltf-transform/functions 4.5.1` requires `ndarray-pixels:^5.2.0`, and `ndarray-pixels 5.2.0` requires `sharp:^0.35.0`. `sharp 0.35.5` is patched for the reported GHSA ranges and requires **Node >=20.9.0**. We updated the official `@gltf-transform/core`, `/extensions` and `/functions` to `^4.5.1`, removed the unused root `sharp` entry, corrected the Node engine floor, and generated a native npm v3 lockfile. No transitive resolution override, vendored code, or custom package manager was introduced. Packages are MIT or Apache-2.0 per npm package metadata.

The clean lockfile installs `@gltf-transform/* 4.5.1`, `ndarray-pixels 5.2.0`, `sharp 0.35.5`. A fresh `npm ci --ignore-scripts` in a separate directory installed 21 packages. A real Node 22.23.4 test roundtripped a nonempty glTF triangle through `NodeIO` and the glTF Validator with zero errors/warnings, and created a native PNG using `sharp`; `npm audit --omit=dev` reported **zero vulnerabilities**, and `npm audit --package-lock-only` also reported zero. `tests/test_npm_dependency_security.mjs` captures the graph and functional smoke test. After merge, run these against exact main and check for updated Dependabot alerts; GitHub alert closure is asynchronous and must not be assumed from local npm audit.

GitHub Research MCP card search and TaskMap were invoked with this specific transitive-security query; neither returned a relevant preexisting `sharp` Pattern Card (ranking scores zero), so no donor equivalence is inferred from them. SMAT Research code search found no `sharp` match. The direct GitHub alerts, npm registry metadata, resolved lockfile, and clean-install tests are the source of these claims.

**Boundary:** Node 18 is no longer advertised as supported because it cannot run the security-patched `sharp` chain. This does not prove compatibility of every optional legacy Forge script; it does validate the published direct dependency graph and the primary glTF/native-image APIs. Continue to test production scene flows separately.

## Provenance fidelity

GitHub Research PR #34 (merged SHA `b746ddb9f8bb2f0a663ff6147a65d2af106a1f84`) contains a source-pinned Pattern Card and a real M1 TaskMap. Research Fabric jobs `96cf081a-51d8-4129-9a0d-ff0e3bb438cf`, `8a09ee43-9e48-4b55-a4a3-828b3686aa39`, and `2da690f3-0f17-4fdf-8ca3-d9143dcf64ec` were completed but **not sufficient** due donor-verification errors on extraneous repos even when the caller-supplied pinned package source files resolved. Do not record these as Fabric-successful donor verification. The exact release-tag source files were independently fetched via GitHub, metadata checked via official npm, and local M2 runs provide separate measured evidence. `.lego/research/npm_sharp_security_research.json` records this downgrade.

## Remove tracked generated Node dependencies

The original `main` tracked 706 files under `node_modules/` (145,420 source lines according to the index diff) even though `.gitignore` already says `node_modules/`. Keeping those generated files would leave stale vulnerable binaries in source checkouts and make ordinary `npm ci` appear to modify hundreds of tracked files. The security branch removes those **tracked files from Git's index** while preserving the package manifests, the new `package-lock.json`, and tracked application source. `npm ci` remains mandatory after checkout; `.gitignore` continues to keep installed dependency files outside version control. The checked-in Python regression test now fails if `git ls-files node_modules` returns anything. This is not a source-feature deletion: every generated Node dependency is restored from the lockfile.
