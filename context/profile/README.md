# `context/profile/` — standing facts about you

`context/experiences/`, `context/research/` and `context/systems/` describe things
you have *done*. This directory holds facts about *you* that are true,
resume-relevant, and written down nowhere else: coursework, real proficiency
levels, credentials and licences, languages, logistics, preferences.

Everything here ranks as a source of truth alongside
`master-resume/master-resume.tex` and the rest of `context/`. The anti-fabrication
rule applies unchanged: if a fact is not in one of those places, it does not go on
a resume.

## Why it exists

An agent that cannot find a fact will treat it as missing, and may write a cover
letter that apologizes for a skill you actually have. Files here mean a fact only
has to be established once. When you tell the agent something new about yourself,
it should write it here in the same session (AGENTS.md, Guardrails).

## Files here

- `about-me.mdx` — coursework, proficiency, credentials, gaps, preferences.
  Split it into more files as it grows.
- `application-profile.json` — fields used to fill application forms. Anything
  under `needs_candidate` that is `null` is unknown and must be asked, never
  guessed.
