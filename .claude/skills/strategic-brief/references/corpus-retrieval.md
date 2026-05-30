# Corpus retrieval

Retrieve ranked evidence from `state/app.db` for the framing's topic. No new code — run
this `sqlite3` query directly.

## Query

Replace `QUERY` with FTS5 match terms derived from the framing (OR-join key terms, e.g.
`agent OR agentic OR orchestration`). Replace `N` with the evidence cap (default 25).

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

Exported note filenames end with the lowercased `tweet_id`. Find the note path by globbing:

```bash
ls vault/**/*<tweet_id-lowercased>*.md 2>/dev/null
```

Use that path for the `[corpus]` "Open note" link.

## Broken source links

When `broken_source_link = 1` (base64 node-ID, ~38 rows), the X URL in `source_ref` will
not resolve. Link the vault note as primary and mark the external link **unavailable** —
do NOT emit a dead URL.

## Empty result

If the query returns no rows, the corpus is thin on this topic. Say so plainly, proceed
research-led, and flag the gap in the artifact.
