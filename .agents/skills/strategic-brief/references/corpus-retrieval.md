# Corpus retrieval

Retrieve ranked evidence from `state/app.db` for the framing's topic. No new code — run
this `sqlite3` query directly.

## Choosing FTS match terms

Expand the framing topic into **3–6 OR-joined keyword stems** and prefer recall over
precision (ranking + the N-cap winnow the result). Rules:
- Include morphological variants explicitly — FTS5 does not stem: `agent OR agentic OR agents`.
- Quote a multi-word phrase **only** when the phrase itself is the concept
  (`"data platform"`); otherwise OR the words (`data OR platform`).
- Example for "agentic coding platforms": `agent OR agentic OR agents OR orchestration OR coding`.

## Query

Replace `QUERY` with the OR-joined terms above. `N` is the **retrieval cap** (default 25) —
a candidate pool to rank and winnow, NOT the number of items that land in the draft. A
~1-page exec-update may cite only the top 3–5; a 2-page brief more. Always winnow to what
the artifact's length target supports.

```bash
sqlite3 -json state/app.db "
SELECT
  b.tweet_id,
  b.source_name,
  b.author_username,
  b.created_at,
  b.first_seen_at,
  b.source_ref,
  e.summary, e.tags, e.entities, e.topic,
  m.strategic_relevance, m.time_horizon, m.organizational_impact, m.leadership_question,
  CASE WHEN b.tweet_id GLOB '*[A-Za-z=]*' THEN 1 ELSE 0 END AS broken_source_link,
  bm25(bookmarks_fts) AS rank
FROM bookmarks_fts
JOIN bookmarks b ON b.rowid = bookmarks_fts.rowid
LEFT JOIN enrichments e ON e.tweet_id = b.tweet_id
LEFT JOIN leadership_metadata m ON m.tweet_id = b.tweet_id
WHERE bookmarks_fts MATCH 'QUERY'
ORDER BY rank
LIMIT N;"
```

Lower `bm25` rank = more relevant (FTS5 returns ascending relevance). `ORDER BY rank` is correct.

## Resolve the vault note path for an evidence item

The exporter names files `<text-slug>-<slugified-tweet_id>.md`, where the id suffix is the
tweet_id **slugified**: lowercased with every non-`[a-z0-9]` character removed. Base64
node-IDs therefore lose their trailing `=` and any `:` — a glob on the raw id will NOT
match them (the exact ~38 rows the trust contract most needs to link).

Derive the slug id, then resolve with `find` (layout-independent; do NOT rely on `vault/**`,
which needs shell `globstar` that is off by default):

```bash
slug_id=$(printf '%s' "<tweet_id>" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9')
find vault -name "*$slug_id*.md" -not -path 'vault/stories/*' | head -1
```

`find` returns both the bookmark note (`vault/YYYY/MM/...`) and the story note
(`vault/stories/...`); exclude `vault/stories/` and take the first match for the `[corpus]`
"Open note" link.

## Broken source links

When `broken_source_link = 1` (base64 node-ID, ~38 rows), the X URL in `source_ref` will
not resolve. Link the vault note as primary and mark the external link **unavailable** —
do NOT emit a dead URL.

## Empty result

If the query returns no rows, the corpus is thin on this topic. Say so plainly, proceed
research-led, and flag the gap in the artifact.
