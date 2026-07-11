# Releasing regdrift (human steps)

Package version, git tag, and Action reference must agree:
`0.1.0a3` / `v0.1.0a3` / `@v0.1.0a3`. The Release workflow refuses to
publish if the tag does not match the package version.

One-time setup completed for `v0.1.0a1` (do not repeat): the PyPI
trusted publisher for project `regdrift` (owner `Pranav-s79`, repository
`regdrift`, workflow `release.yml`, environment `pypi`) and the GitHub
`pypi` environment restricted to `v*` tag deployments.

The release workflow is fully automated EXCEPT these owner-only steps,
in this order:

1. Release PR: bump `__version__` in `src/regdrift/__init__.py`, update
   the README status wording, pinned installation commands, and Action
   example (`@v0.1.0a3`), and add a dated CHANGELOG entry. Merge on
   green CI.
2. Tag and push (this is the publish trigger; the tag must be
   `v` + package version):
   `git tag v0.1.0a3 && git push origin v0.1.0a3`
3. Watch the Release workflow; when green, verify the published
   package from a clean machine or venv:
   `pipx install regdrift==0.1.0a3 && regdrift --version`, then run
   one identity comparison (exit 0), one breaking comparison (exit 1,
   e.g. `demo/chip_v1.svd` vs `demo/chip_v2.svd`), and one malformed
   input (exit 2).
4. Create the GitHub Release from the `v0.1.0a3` tag; paste the
   0.1.0a3 CHANGELOG section as notes.
5. If the Marketplace listing needs to be created or refreshed, publish
   it from the release page using the listing text below.

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
