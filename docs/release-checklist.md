# Releasing regdrift (human steps)

Package version, git tag, and Action reference must agree:
`0.1.0a1` / `v0.1.0a1` / `@v0.1.0a1`. The Release workflow refuses to
publish if the tag does not match the package version.

The release workflow is fully automated EXCEPT these owner-only steps,
in this order:

1. GitHub cleanup (see the section below): close the superseded PR
   stack, correct issue #26's state, and leave the Dependabot PRs
   unmerged.
2. On pypi.org (logged in as the owner): Account -> Publishing -> add a
   **pending trusted publisher** for project `regdrift`: owner
   `Pranav-s79`, repository `regdrift`, workflow `release.yml`,
   environment `pypi`.
3. On GitHub: Settings -> Environments -> create environment `pypi`
   and **restrict its deployments to `v*` tags** (required: this stops
   a branch push or a non-release ref from ever reaching the publish
   job).
4. Release PR: replace the `YYYY-MM-DD` placeholder in CHANGELOG.md
   with the actual release date and confirm the README Action example
   references `@v0.1.0a1`. Merge on green CI.
5. Tag and push (this is the publish trigger; the tag must be
   `v` + package version):
   `git tag v0.1.0a1 && git push origin v0.1.0a1`
6. Watch the Release workflow; when green, verify the published
   package from a clean machine or venv:
   `pipx install regdrift==0.1.0a1 && regdrift --version`, then run
   one identity comparison (exit 0), one breaking comparison (exit 1,
   e.g. `demo/chip_v1.svd` vs `demo/chip_v2.svd`), and one malformed
   input (exit 2).
7. Create the GitHub Release from the `v0.1.0a1` tag; paste the
   0.1.0a1 CHANGELOG section as notes.
8. Publish the Action to the Marketplace from the release page using
   the listing text below.
9. Post-publication README PR: replace the Installation section's
   source-only instructions ("No PyPI release has been published
   yet...") with the published commands
   (`python -m pip install regdrift` / `pipx install regdrift`).

## GitHub cleanup (before tagging)

- Close PRs #24-#31 as **superseded** - their content already reached
  `main` (finalized via #32); merging the stale stack now would produce
  no-ops or conflicts. Close, do not merge.
- Issue #26 (`dim` `[%s]` array vs `%s` list) is closed as COMPLETED,
  but the behavior remains unimplemented and RULES.md documents it as
  not checked. Reopen it (or re-close it as "not planned" with an
  explanatory comment) so the RULES.md status link is truthful.
- Leave Dependabot PRs #33-#38 unmerged until after the alpha ships.
  Take the artifact-action major bumps (upload-artifact and
  download-artifact) together and re-test the Release workflow's
  build-to-publish artifact handoff before merging them.

## Marketplace listing text (paste verbatim)

**Name:** regdrift check

**Summary:** Fail pull requests that silently break a CMSIS-SVD
register map.

**Description:** regdrift diffs the pull request's SVD file against the
base branch and classifies every change - moved registers, renamed
fields, renumbered interrupts, inverted write-one-to-clear semantics -
as BREAKING, WARNING, or SAFE against a published, arguable rulebook
(RULES.md). Breaking findings fail the check, annotate the file, and
land in one sticky PR comment. Intentional breaks are acknowledged in
a `.regdrift.toml` allowlist instead of disabling the gate. Alpha:
the rulebook documents exactly what is not checked yet.

**Categories:** Continuous integration, Code quality
