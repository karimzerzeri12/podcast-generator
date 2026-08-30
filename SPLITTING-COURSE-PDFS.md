# Splitting a course PDF into topics — what happened, and how to do it yourself

This walks through the "Food Flavour Design -Module 3 4.pdf" fix as a worked example, then
gives you the repeatable steps for any future PDF.

---

## What went wrong

`python -m app.build_course <pdf>` was run on the PDF **without** `--split-on`/`--chapter-on`.
`build_course.py` first tries to split by the PDF's real bookmarks (its outline/table-of-contents).
This PDF has **no bookmarks at all** (0 outline entries), so it fell back to its last resort:
treating the *entire PDF as one topic*. That overwrote the real seed files on disk with:

- `course.json` → title `"Food Flavour Design  Module 3 4"` (from the filename, double space
  where a dash used to be), a generic auto-description
- `topics.json` → **one** topic, title `"Food Flavour Design  Module 3 4"`, description = the
  first 180 characters of raw extracted text (garbage — page headers, professor names, etc.)
- `topics/` → one 110KB file with the whole PDF's text in it

The live database wasn't touched yet (nothing had re-applied the seed files), so the app
itself was still fine — but the next `apply-content.ps1` would have pushed this broken
single-topic version live.

---

## How it was diagnosed and fixed

**1. Check whether the PDF has real bookmarks.**
```python
from pypdf import PdfReader
reader = PdfReader("your.pdf")
print(len(reader.outline or []))
```
`0` → no bookmarks, so `--split-on` (heading-pattern splitting) is required. If this had
printed a real outline, the plain `python -m app.build_course your.pdf` (no flags) would
have worked correctly on its own.

**2. Find the actual heading pattern in the extracted text.**
```python
from app.rag.ingest import extract_pdf_pages
data = open("your.pdf", "rb").read()
text = "\n\n".join(p for p in extract_pdf_pages(data) if p)
print(text[:1500])   # eyeball the heading style
```
This PDF's headings looked like `"3.1 Taste and Odour Receptors"` under a running header
`"Module 3 – Drivers of Flavour perception"` — i.e. `<module>.<section> <Title>` under
`Module <n>`.

**3. Calibrate the regex with `--dry-run` (writes nothing).**
```powershell
python -m app.build_course "your.pdf" --split-on "[0-9]\.[0-9]+ [A-Z]" --chapter-on "Module \d+" --dry-run --no-llm
```
First attempt used `[0-9]\.[0-9]+` and also matched decimal numbers in the text like
`"0.05 was used"` and `"0.33 indicates a significant difference"` (stats/p-values in the
sensory-methods sections) — 8 "topics" instead of 4, half of them junk. Restricting the
first digit to the actual module numbers fixed it:
```powershell
python -m app.build_course "your.pdf" --split-on "[34]\.[0-9]+ [A-Z]" --chapter-on "Module \d+" --dry-run --no-llm
```
→ exactly 4 clean topics, char counts close to the originals (confirming this was indeed
the same source PDF the existing content came from).

**4. Write for real, but into a scratch folder first — not directly into `app/seed/data`.**
```powershell
python -m app.build_course "your.pdf" --split-on "[34]\.[0-9]+ [A-Z]" --chapter-on "Module \d+" --no-llm --out ".\scratch_out"
```
This is the step that was skipped the first time, and is exactly what caused the overwrite.
Always land the output somewhere reviewable first.

**5. Review before promoting.** With `--no-llm`, descriptions are a crude "first 180
characters" fallback (repeats the title, includes "By Prof. X", cuts off mid-sentence) —
fine to preview the split, not fine to ship. The existing `topics.json` already had
hand/LLM-polished descriptions for the same 4 topics, so those were kept and only the
**text bodies** were refreshed from the scratch output (same titles and filenames as
before, so the reseed *updates* the existing topics instead of creating duplicates).
The `"chapter"` field in `topics.json` also has to match a key in `chapters.json` **exactly**,
or that chapter's descriptive blurb silently stops showing on the topics page.

**6. Apply it.**
```powershell
.\apply-content.ps1
```
This stops the backend, deletes `db.sqlite3` + `chroma/` + `scripts/` + `audio/`, and
restarts — which re-seeds from the (now-correct) files and re-embeds every topic into
Chroma from scratch.

**7. Verify.** Checked the DB (`storage/db.sqlite3`) for the 4 expected topics, and queried
the Chroma collection directly to confirm every topic actually has vector chunks:
```python
from app.rag.vectorstore import get_vectorstore
store = get_vectorstore()
res = store.get(limit=200, include=["metadatas"])
from collections import Counter
print(Counter(m.get("topic_id") for m in res["metadatas"]))
```

---

## Do it yourself next time — checklist

1. **Check for bookmarks first** (step 1 above). If the PDF has a real outline/TOC, you
   probably don't need `--split-on` at all — just `--dry-run` the plain command and see.
2. **If no bookmarks, or the bookmark split looks wrong**, extract a text sample and find
   the heading pattern by eye (step 2).
3. **Always start with `--dry-run --no-llm`.** No-op, no API quota spent, just prints the
   breakdown. Iterate on the regex until the topic list and char counts look right — watch
   out for the regex also matching numbers/units in the body text (decimals, page refs,
   figure numbers). Restricting to your actual chapter numbers (like `[34]` instead of
   `[0-9]`) is usually the fix.
4. **Write to `--out <scratch-folder>`, never straight into `app/seed/data`**, until you've
   reviewed the result.
5. **Decide on descriptions.** `--no-llm` gives you a rough fallback (fine to iterate with,
   especially if your Gemini quota is tight); drop it once you're ready to commit, and
   Gemini will write a proper one-sentence description per topic (falls back to the rough
   version automatically if the API call fails, e.g. on quota exhaustion).
6. **If you're updating an existing course** (not creating a new one), keep the same
   `title` and `filename` per topic as what's already in `topics.json` — the upsert matches
   on those, so keeping them identical means "update this topic's material" instead of
   "create a new one alongside it."
7. **Make sure every topic's `"chapter"` matches a key in `chapters.json` exactly**, if you
   want that chapter's blurb to show on the topics page.
8. **Copy the reviewed files into `backend/app/seed/data/`**, then run `.\apply-content.ps1`.
9. **Spot-check afterward**: `python -m app.build_course` prints a summary as it runs, and
   you can query the Chroma collection directly (step 7 above) to confirm every topic
   actually got indexed — that's the check that would have caught the original bug (topics
   1 and 2 having zero vectors) immediately.

---

## Reusable command for this specific PDF

```powershell
python -m app.build_course "Food Flavour Design -Module 3 4.pdf" `
  --split-on "[34]\.[0-9]+ [A-Z]" --chapter-on "Module \d+" --dry-run --no-llm
```
Drop `--dry-run` once you're happy with the preview; drop `--no-llm` once your Gemini quota
has reset if you want it to write fresh descriptions instead of reusing the existing ones.
