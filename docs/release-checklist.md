# Releasing regdrift (human steps)

The release workflow is fully automated EXCEPT these owner-only steps,
in this order:

1. Merge the open PR stack bottom-up (GitHub retargets each PR as its
   base merges). CI must be green on every merge.
2. On pypi.org (logged in as the owner): Account -> Publishing -> add a
   **pending trusted publisher** for project `regdrift`: owner
   `Pranav-s79`, repository `regdrift`, workflow `release.yml`,
   environment `pypi`.
3. On GitHub: Settings -> Environments -> create environment `pypi`
   (no secrets needed; optionally restrict to tags).
4. Update CHANGELOG.md: change `- unreleased` to the release date, and
   commit via PR.
5. Tag and push (this is the publish trigger):
   `git tag v0.1.0-alpha && git push origin v0.1.0-alpha`
6. Watch the Release workflow; when green, verify from a clean machine:
   `pipx install regdrift==0.1.0a1 && regdrift --version`
7. Create the GitHub Release from the tag; paste the 0.1.0a1 CHANGELOG
   section as notes.
8. Publish the Action to the Marketplace from the release page using
   the listing text below.
9. Switch the README Action snippet from `@main` to `@v0.1.0-alpha`.

## Marketplace listing text (paste verbatim)

**Name:** regdrift check

**Summary:** Fail pull requests that silently break a CMSIS-SVD
register map.

**Description:** regdrift diffs the pull request's SVD file against the
base branch and classifies every change - moved registers, renamed
fields, renumbered interrupts, inverted write-one-to-clear semantics -
as BREAKING, WARNING, or SAFE against a published, argueable rulebook
(RULES.md). Breaking findings fail the check, annotate the file, and
land in one sticky PR comment. Intentional breaks are acknowledged in
a `.regdrift.toml` allowlist instead of disabling the gate. Alpha:
the rulebook documents exactly what is not checked yet.

**Categories:** Continuous integration, Code quality
