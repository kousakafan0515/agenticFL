# V10 SkillBank English reference

This is a display-only derivative of the current V10 formal chain. The original
SkillBanks, validation results, controller, and run inputs remain unchanged.

The locked [source manifest](source_manifest.json) lists 30 files: imported v9
B1 seeds for A/B/C; V10 B2-B6 banks for A/B/C; Global1-3 server banks; and the
three downlink replacement banks for each Global. The
[translation map](translation_map.json) lists 295 unique Chinese-bearing skill
text strings (1,700 total occurrences) so repeated text is translated once.

Only `title`, `principle`, `when_to_apply`, `description`, `why_it_happens`, and
`how_to_avoid` would be translated. IDs, Chinese task bucket identifiers,
lineage keys, metadata and JSON structure would be retained exactly. The
planned output is one parallel JSON and one English Markdown reading view per
source bank, with an index and original/reference hash manifest. These files
are not experiment inputs.

The user explicitly authorized sending these 295 texts to the configured
DeepSeek official endpoint for this display-only translation. All 20 batches
are complete. [INDEX.md](INDEX.md) links each English reading view and parallel
JSON bank; [Original and English](ORIGINAL_AND_ENGLISH.md) pairs all 30 sources
with their references. [output_manifest.json](output_manifest.json) records every original
and English-reference hash. The API audit retained 24 raw attempts, including
one truncated attempt for batch 13 and the first three truncated attempts for
batch 14; batch 14's fourth attempt used non-thinking mode and succeeded.
Total reported usage was 27,286 prompt and
59,767 completion tokens. [postedit_audit.json](postedit_audit.json) records
15 narrow grammar corrections to a repeated `use use desklamp` phrase.

All 30 original source hashes and all 30 parallel JSON structures passed
read-only verification. The 30 Markdown views contain no Chinese characters.
Four local unit tests passed. Fourteen unique English strings exceed the
experiment's 900-character skill-field limit; these reference files are not
valid experiment replacements and have not been used in any run. The original
source IDs and Chinese bucket keys are deliberately retained in JSON for
exact alignment; the Markdown views provide English bucket headings.
