# Resume Agent (Codex template)

A Codex project that tailors your resume and writes a cover letter for each job
posting you give it, using only facts you've written down. It never makes up
experience, and it never submits an application for you.

Codex reads `AGENTS.md` automatically. That file holds the whole workflow.

## What it produces, per posting

In `outputs/<company>-<role>/`:

- `resume.pdf` — a one-page resume tailored to the posting
- `cover-letter.pdf` — a one-page cover letter
- `application-answers.json` — ready-made answers for "why this company?",
  "why this role?" and similar form questions
- `ats_scan.json` — a keyword and parseability check against the posting
- `changelog.md` — what changed and why, plus any **honest gaps**: things the
  posting asks for that your records don't show

After a batch it also writes `outputs/_batch-reports/<date>-interview-odds.md`, a
deliberately blunt estimate of which applications are worth your time.

## One-time setup

**Easiest way:** open this folder in Codex and say *"Set me up."* It installs the
tools (asking first), asks for your existing resume, interviews you about your
experience, and fills in every file below. The steps here are what it does, if
you'd rather do it by hand.

### 1. Install the tools (macOS)

```bash
brew install tectonic poppler      # LaTeX compiler + pdftotext
cd resume-agent-template
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The first scan downloads a small embedding model (about 90 MB). Linux: install
`tectonic` and `poppler-utils` with your package manager.

### 2. Put your own information in

The agent can only use what's written here, so this step matters most. Write
more than fits on one page. It picks the best parts for each posting.

1. **`master-resume/master-resume.tex`**: replace every `[PLACEHOLDER]` with your
   real resume content. Keep the commands (`\resumeItem{...}` etc.) as they are.
   If you have a resume in Word or PDF already, give it to Codex and ask it to fill
   in this file for you, then check what it wrote.
2. **`master-resume/cover-letter-template.tex`**: put your name and contact
   details in the header.
3. **`context/experiences/`**: one `.mdx` file per job. Copy
   `_example-job.mdx` to start. `context/research/` and `context/systems/` work
   the same way for research and for projects, clubs or volunteering. Delete the
   `_example-*` files once you have real ones.
4. **`context/profile/about-me.mdx`**: coursework, real skill levels, languages,
   credentials, work authorization, preferences.
5. **`context/profile/application-profile.json`**: contact details and form
   fields. Leave anything you're unsure of as `null`, and the agent will ask.

You can also do steps 1 to 5 by talking it through. Open the folder in Codex
and say *"Help me set up my master resume and context files"*. Paste in an
old resume or LinkedIn export and answer its questions.

### 3. Optional: browser form filling

`.codex/agents/application-filler.toml` fills in application forms in Codex's
built-in browser (the bundled **Browser** plugin, on by default in the Codex app;
check it's enabled under plugins if not). Ask Codex to *"use the
application-filler agent on <posting URL>"*. It fills the form, leaves the tab open
for you to review, and stops. It never submits, never creates accounts or enters
passwords, and never answers demographic, legal-attestation or salary questions.

## Using it

1. Save each job posting as a text file in `inputs/`, named like
   `acme-marketing-coordinator.txt`. Paste the whole posting.
2. Open this folder in Codex and say:

   > Tailor my resume for everything in inputs/.

3. Read each `changelog.md`, especially the honest-gaps section, and check
   the PDFs before you send anything.
4. When you hear back, fill in the `outcome` field for that row in
   `logs/scan_log.jsonl` and `logs/interview_odds_log.jsonl` (`"interview"`,
   `"rejected"`, `"no_response"`). Over time this shows whether the scores and
   odds estimates are any good.

Finished postings move to `inputs/archive/`. Keep them there: they're the
comparison set for the ranking part of the scan (Layer 2), which means little
until you've done five or so.

## Adapting it to your field

`AGENTS.md` Step 6 has a table of rough interview-rate base rates by employer
type. It's generic as shipped. Ask Codex to replace it with numbers for your
industry the first time you run a batch.

## Layout

```
AGENTS.md                     the workflow Codex follows
.codex/                       Codex config + application-filler agent
master-resume/                your master resume + cover letter template (LaTeX)
context/                      everything you've done, in more detail than the resume
  profile/                    standing facts about you + form-fill profile
inputs/                       job postings to do (archive/ = done)
outputs/                      one folder per application
scoring/                      the ATS scan script and schemas
logs/                         append-only score and odds logs
```
