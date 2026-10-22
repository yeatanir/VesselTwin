# Track C pre-registration (C3: excerpt support rule)

Written and committed BEFORE the matcher (llm/excerpt_match.py) exists and before any stored excerpt is re-checked.
C1, C2, C4, C5 compare nothing against data and are not scored; C1 recorded runs are shown as recorded, not as a benchmark.

## Method
An excerpt shown in the Reasoning trace "Literature evidence" step supports the question's parameter only if BOTH hold:
(a) NAME: the excerpt text matches (case-insensitive) one of the alias regexes listed for that question id below
    (name, symbol or alias of the parameter; a bare unit such as "sccm" is not an alias).
(b) VALUE: the excerpt contains a number+unit whose value, after unit normalization (llm.units / pint, temperatures in K,
    flows in cm3/min, masses in mg, lengths in mm), is within 2% (relative) of at least one reference value of that question.
    Reference values = every number in the benchmark item's `change` field (bench/sensitivity/papers.json), a bare number in a
    list ("650 C to 700, 750, 800 C") taking the next explicit unit in the string. A number without a unit never matches.
Otherwise the excerpt is labelled "unverified excerpt". Dimension mismatch = no match. Retrieval (which excerpts are shown) is unchanged;
only the support label is new.

Alias regexes (per question id; unlisted ids have none, so nothing is verifiable):
- s01: `(carrier|gas|argon|Ar)\W+(gas\W+)?flow(\s+rate)?|flow\s+rate`
- s02: `substrate position|transverse|gas-flow position`
- s03, s04: `(Ar|argon)\W+(gas\W+)?flow(\s+rate)?|gas\s+flow\s+rate|flow\s+rate`
- s05: `MoO3\s+amount|amount\s+of\s+MoO3|mg\s+(of\s+)?MoO3|MoO3\s+(powder|precursor|mass)`
- s06: `sulfur\s+amount|sulphur\s+amount|amount\s+of\s+sul(f|ph)ur|mg\s+(of\s+)?sul(f|ph)ur`
- s07, s10, s13: `growth\s+temperature|substrate\s+temperature`
- s08: `vertical\s+gap|source[- ]to[- ]substrate|gap`
- s09: `MoO3\s+(heating\s+)?temperature|(heating\s+)?temperature\s+of\s+(the\s+)?MoO3`
- s11: `sul(f|ph)ur\s+(source\s+)?temperature|temperature\s+of\s+(the\s+)?sul(f|ph)ur`
- s12: `MoO3\s+(film\s+)?thickness|thickness\s+of\s+(the\s+)?MoO3`
- s14: `nanoribbon\s+(density|concentration)|MoO3\s+source\s+density`

## Items, split, seeds
All excerpts produced by `search_literature` for the 14 questions s01-s14 on the committed benchmark and docs/literature/edison_*.json
(deduplicated by (question id, quote)). No split, no randomness, no seeds.

## Metric and threshold
Metric: number of excerpts labelled supporting / total, overall and by source (own paper, sibling benchmark paper, Edison answer sentence).
No pass threshold: this is an audit of what the old loose rule (two shared content words) showed; the result is reported as it comes out.
The matcher is also pinned by known-answer unit tests (tests/test_excerpt_match.py) that are not part of the scored set.
The matcher is scored once after this commit; if the method changes after seeing the counts, a new pre-registration is committed and both results reported.
