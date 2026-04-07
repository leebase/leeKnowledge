# project-plan.md

## Project strategy

Build in the order of risk, not in the order of glamour.

The project succeeds only if extraction is good enough and the downstream pipeline is replayable. Therefore the delivery strategy is:

1. prove extraction feasibility on the user’s real account,
2. lock the raw bundle contract,
3. build normalization and durable storage,
4. add artifact generation,
5. add AI enrichment,
6. add retrieval polish.

Do not build a polished UI, vector database, or cloud deployment before Phase 0 and Phase 1 are stable.

## Recommended delivery order

1. Extraction feasibility
2. Raw run store
3. Canonical schema and dedupe
4. Markdown note rendering
5. Incremental sync mechanics
6. AI enrichment
7. Retrieval and optional vectors
8. Automation convenience features

## MVP scope

MVP includes:
- import-first extraction workflow,
- immutable raw run bundles,
- SQLite catalog,
- dedupe and observation tracking,
- Markdown artifacts,
- keyword search,
- replay commands,
- run reports.

MVP excludes:
- hosted web app,
- team accounts,
- required semantic search,
- required Playwright automation,
- official API dependency.

## Post-MVP scope

- first-party Playwright adapter,
- optional X API adapter,
- semantic retrieval,
- topic pages and synthesis notes,
- browser extension for capture-at-bookmark,
- team-capable deployment.

## Build phases

### Phase 0: Extraction feasibility and contract spike

**Objective**  
Decide the MVP extraction path with evidence.

**Tasks**
- Run at least one current browser-local exporter against the user’s account.
- Measure output shape, item count, folder data availability, and media/link fields.
- Compare export count to visible bookmark count or folder count where possible.
- Prototype the raw run bundle format.
- If exporter output is insufficient, prototype a minimal Playwright-based local extractor to confirm viability.
- Document risks for each adapter.

**Deliverables**
- `docs/extraction-feasibility.md`
- sample raw bundle fixture
- chosen raw bundle schema
- supported exporter matrix

**Exit criteria**
- one real export imported successfully,
- chosen adapter path for MVP,
- known gaps documented,
- raw bundle contract approved.

### Phase 1: Ingestion shell and raw store

**Objective**  
Create the durable ingestion backbone.

**Tasks**
- Scaffold Python project and CLI.
- Implement `import-run` command.
- Create immutable raw store layout.
- Write run manifest generation.
- Persist run metadata in SQLite.
- Add fixture-based tests for import parsing.

**Deliverables**
- CLI skeleton
- `sync_runs` and `raw_items` tables
- import adapter v1
- run manifest writer

**Exit criteria**
- repeated imports are idempotent,
- raw bundles are queryable by run ID,
- failures do not corrupt previous runs.

### Phase 2: Normalization and durable storage

**Objective**  
Convert raw exports into stable records.

**Tasks**
- Define canonical schemas.
- Implement raw-to-canonical mapping.
- Add authors, folders, URL references, and observation model.
- Add duplicate detection and merge rules.
- Write quarantine flow for malformed records.

**Deliverables**
- normalizer module
- schema docs
- canonical fixtures
- normalization audit report

**Exit criteria**
- 95%+ of valid raw items normalize without manual intervention,
- duplicates merge correctly,
- folder membership persists where available.

### Phase 3: Artifact generation and inspectability

**Objective**  
Create the user-facing knowledge base.

**Tasks**
- Design Markdown note templates.
- Implement per-bookmark and per-thread renderers.
- Generate vault directory structure.
- Add provenance fields to frontmatter.
- Create run summary and unresolved-item reports.

**Deliverables**
- renderer module
- golden Markdown fixtures
- example Obsidian-compatible vault output

**Exit criteria**
- notes are readable without the app,
- each note links back to source and provenance,
- render reruns are deterministic.

### Phase 4: Incremental sync and recovery

**Objective**  
Make the system usable week after week.

**Tasks**
- Implement observation-based incremental logic.
- Add “stop after N known posts” heuristic for ordered sources.
- Add integrity sweep mode.
- Add replay commands for normalization, rendering, and indexing.
- Add diff reports between runs.

**Deliverables**
- `sync` command
- run diff report
- integrity sweep report

**Exit criteria**
- incremental sync avoids reprocessing most old bookmarks,
- replay works without re-extraction,
- deleted or unavailable posts are handled gracefully.

### Phase 5: AI enrichment and knowledge generation

**Objective**  
Add value without obscuring source truth.

**Tasks**
- Add provider abstraction for local and remote models.
- Implement summary, tags, and entity extraction.
- Store structured enrichment outputs with version metadata.
- Generate optional topic pages and weekly syntheses.
- Add confidence and failure tracking.

**Deliverables**
- enrichment pipeline
- prompt contracts
- structured output validators
- sample synthesis notes

**Exit criteria**
- enrichment is optional,
- enrichment failures do not block core outputs,
- regenerated outputs are versioned.

### Phase 6: Retrieval and refinement

**Objective**  
Improve findability and usefulness.

**Tasks**
- Build SQLite FTS search commands.
- Add filters by author, folder, date, and domain.
- Evaluate whether vectors are justified on the real dataset.
- If justified, add a local vector index and hybrid retrieval.

**Deliverables**
- search CLI
- relevance evaluation set
- optional vector adapter

**Exit criteria**
- user can reliably refind known bookmarks,
- retrieval benchmark is acceptable,
- vector layer is only added if it materially improves results.

## Milestones

### Milestone 1
Extraction feasibility proven; raw bundle contract locked.

### Milestone 2
Canonical ingest pipeline working on full historical export.

### Milestone 3
Vault artifacts generated for the full backlog.

### Milestone 4
Incremental sync stable enough for weekly use.

### Milestone 5
AI enrichment and retrieval layered on top of a stable core.

## Risks by phase

### Phase 0 risks
- exporter output incomplete,
- folder data missing,
- source format unstable.

**Mitigation:** support multiple import adapters and postpone first-party automation.

### Phase 1 risks
- raw bundle schema churn,
- fixture mismatch between exporters.

**Mitigation:** adapter-specific translators feeding one canonical raw contract.

### Phase 2 risks
- malformed records,
- ambiguous IDs,
- bookmark-order assumptions leaking into canonical state.

**Mitigation:** observation model plus quarantine path.

### Phase 3 risks
- note templates become too LLM-dependent,
- artifact filenames churn.

**Mitigation:** stable filenames keyed by post ID; source text always present.

### Phase 4 risks
- incremental sync misses new items,
- integrity drift over time.

**Mitigation:** known-item threshold plus periodic deep sweeps.

### Phase 5 risks
- hallucinated summaries,
- cost creep,
- brittle prompt contracts.

**Mitigation:** structured outputs, provider abstraction, sample review, optional local models.

### Phase 6 risks
- vector search adds complexity without value.

**Mitigation:** require evaluation benchmark before adoption.

## Testing strategy

### 1. Contract tests
- raw bundle schema validation
- adapter output contract tests
- canonical schema validation

### 2. Fixture tests
- sample exporter outputs
- malformed record fixtures
- deleted/protected post fixtures
- foldered bookmark fixtures

### 3. Replay tests
- re-normalize from raw
- re-render from canonical
- re-index from artifacts

### 4. Golden artifact tests
- compare generated Markdown against approved fixtures

### 5. Incremental tests
- old + new mixed runs
- stop-after-known threshold behavior
- folder move or observation change cases

### 6. Human audit tests
- random 50-bookmark sample
- compare note fidelity to source export
- verify search finds expected items

## Validation checkpoints

### Checkpoint A: after Phase 0
Can we get a trustworthy export from the user’s actual account?

### Checkpoint B: after Phase 2
Can we replay normalization from raw without touching X?

### Checkpoint C: after Phase 3
Are the Markdown artifacts actually useful in a vault?

### Checkpoint D: after Phase 4
Does weekly sync work without creating duplicate churn?

### Checkpoint E: after Phase 6
Does the user find old bookmarks faster than in X itself?

## Suggested repo/workstream structure

```text
bookmark-vault/
  docs/
    product-definition.md
    architecture.md
    project-plan.md
    agents.md
    skills.md
    extraction-feasibility.md
  src/bookmark_vault/
    cli/
    config/
    extractors/
      export_import/
      playwright_session/
      x_api/
    contracts/
    models/
    pipeline/
      normalize/
      enrich/
      render/
      index/
    retrieval/
    storage/
    templates/
  tests/
    contract/
    fixtures/
    integration/
    golden/
  scripts/
  vault_examples/
```

## Suggested Codex workstreams

### Workstream A: Extraction and raw contracts
Own Phase 0 and Phase 1.

### Workstream B: Canonical model and persistence
Own Phase 2 and replay mechanics.

### Workstream C: Artifact rendering and retrieval
Own Phase 3 and Phase 6.

### Workstream D: Enrichment and synthesis
Own Phase 5.

### Workstream E: Reliability and test harness
Runs across all phases.

## Final delivery recommendation

Stop after Milestone 3 and use the system for a real week before building semantic search or a first-party Playwright adapter. That pause will expose whether the extraction contract, note format, and incremental model are actually right.