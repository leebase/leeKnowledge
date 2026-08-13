# New Project Onboard

Place this file in a new repository when you want that project to be built with
Agent-Orch using the AgentFlow methodology.

## Purpose

Agent-Orch is the execution system for governed multi-step delivery work.
AgentFlow is the working method that shapes the work into explicit docs,
explicit workflows, explicit verification, and explicit handoff.

Use this repo as if:

- Agent-Orch is the primary builder for broad feature work, sprint slices,
  roadmap milestones, and unattended delivery.
- AgentFlow is the required methodology for how the work is structured.
- Manual one-off coding is only for small local fixes, unblockers, or when the
  human explicitly wants hands-on editing instead of orchestration.

Important:

- "Run AgentFlow" means "author a workflow that follows AgentFlow, then run it
  with Agent-Orch."
- The executable command is Agent-Orch, not a separate `agentflow` CLI.

## Default Operating Model

For any broad request:

1. Reconcile the repo's canon docs first.
2. Collapse the next meaningful delivery scope into one governed workflow under
   `playbooks/`.
3. Validate the workflow before running it.
4. Run Agent-Orch against that workflow.
5. Start the dashboard watcher that refreshes `dashboard.html` every minute.
6. Tell the human exactly where the dashboard file lives.
7. Use resume instead of replay when a run fails mid-workflow.

Prefer one explicit long-running workflow over many ad hoc manual sessions.

If work is organized by sprint, each sprint should end with:

- repair and verification
- review
- context and handoff updates

## AgentFlow Workflow Shape

For new feature delivery, use the repair-before-review pattern:

1. define the slice
2. plan the slice
3. implement the slice
4. document the slice
5. repair and verify the slice fully
6. review the slice
7. close out sprint docs and handoff notes

Each step should be narrow, auditable, and explicit about:

- `allowed_paths`
- required outputs
- validations
- whether it is documentation, planning, implementation, verification, or
  review

Do not let review happen before the dedicated repair-and-verification step.

## How To Author Optimal Workflows

When creating a workflow:

- Prefer one workflow for the whole meaningful slice, not one workflow per tiny
  subtask.
- Keep steps outcome-based, not activity-based.
- Give each step a concrete artifact or acceptance target.
- Restrict `allowed_paths` to the minimum needed write scope.
- Add validators that prove the step outcome from trusted artifacts.
- Keep the human-visible story coherent in `name`, `mission`, and step order.
- Use resume-friendly structure so failed later steps can restart without
  replaying passed earlier steps.

Good step examples:

- define Sprint 3 fallback-routing contract
- implement dashboard navigation and local-time rendering
- repair and verify the dashboard UX slice
- review sprint results and update handoff docs

Weak step examples:

- do more coding
- work on the app
- think about architecture

## Harness And Model Assignment Guidance

Agent-Orch supports explicit playbook-default and per-step routing intent for
both harness and model. Use that routing layer directly instead of trying to
encode model choice inside `execution`.

Use `execution` for task intent and `routing` for the requested harness/model:

```yaml
execution:
  task_type: coding_task
  capabilities_required:
    - repo_edit

routing:
  primary:
    harness: codex_cli
    model: gpt-5.4-mini
  fallback:
    harness: pi_cli
    model: gpt-5.4
```

Guidance:

- Use lighter planning or documentation steps for discovery, outlining, docs,
  and handoff artifacts.
- Use stronger coding steps for implementation, refactors, bug fixes, and test
  repair.
- Use strong, deterministic verification steps for test execution, validation,
  and review.
- Set `routing.primary.harness` and `routing.primary.model` when you know the
  preferred first route for that job.
- Set `routing.fallback.harness` and `routing.fallback.model` when you want a
  governed token-exhaustion reroute target.
- Let the router choose the final route, but make your configured primary and
  fallback intent explicit when the workflow has a clear routing policy.

Current truthful rule:

- per-step primary harness: yes
- per-step primary model: yes, through `routing.primary.model`
- playbook-wide default primary/fallback route pair: yes, through
  `defaults.routing`
- configured route intent is not the same thing as executed-model evidence

### Concrete per-step example

Use playbook defaults for the common case, then override only the steps that
need different model choices:

```yaml
defaults:
  worker: pi_cli
  execution:
    task_type: coding_task
    capabilities_required:
      - repo_edit
  routing:
    primary:
      harness: pi_cli
      model: gpt-5.4-mini
    fallback:
      harness: pi_cli
      model: gpt-5.4

steps:
  - step_id: implement_slice
    name: Implement the slice
    routing:
      primary:
        model: gpt-5.4-mini

  - step_id: verify_slice
    name: Repair and verify
    routing:
      primary:
        model: gpt-5.3-codex

  - step_id: review_slice
    name: Review the slice
    routing:
      primary:
        model: gpt-5.4
```

That means:

- implementation prefers `pi_cli` on `gpt-5.4-mini`
- verification asks for `gpt-5.3-codex`
- review asks for `gpt-5.4`
- the fallback route stays available for trusted token exhaustion

If you are using an external router, these values become explicit router input.
If you are not using an external router, whole-run adapter settings such as
`AGENT_ORCH_PI_MODEL` may still be the practical enforcement path for some
adapters even though the playbook can now record step-level routing intent.

For trusted token-exhaustion recovery, you may declare both a generic fallback
and a step-specific override:

```yaml
defaults:
  worker: pi_cli
  execution:
    task_type: coding_task
    capabilities_required:
      - repo_edit
  routing:
    primary:
      harness: codex_cli
      model: gpt-5.4
    fallback:
      harness: pi_cli
      model: gpt-5.4-large

steps:
  - step_id: implement_dashboard
    name: Implement dashboard improvements
    execution:
      task_type: coding_task
      capabilities_required:
        - repo_edit
    routing:
      primary:
        model: gpt-5.4-coding
      fallback:
        harness: codex_cli
```

Routing precedence:

1. use the step primary or fallback field when configured
2. otherwise inherit the playbook default field
3. otherwise fall back to legacy compatibility or router-native selection

Compatibility note:

- legacy `token_exhaustion_fallback` inputs still load, but new workflows
  should prefer `routing.fallback`

## Minimal Workflow Skeleton

```yaml
playbook_id: sprint_delivery
name: Sprint Delivery

defaults:
  worker: pi_cli
  execution:
    task_type: coding_task
    capabilities_required:
      - repo_edit
  routing:
    primary:
      harness: codex_cli
      model: gpt-5.4-mini

steps:
  - step_id: define_slice
    name: Define the delivery slice
    mission: Read the canon docs and write the scoped delivery contract.
    allowed_paths:
      - docs/
      - sprint-plan.md

  - step_id: plan_slice
    name: Plan the delivery
    mission: Turn the scoped contract into an implementation plan.
    allowed_paths:
      - plans/
      - architecture.md

  - step_id: implement_slice
    name: Implement the slice
    mission: Ship the scoped code and tests.
    allowed_paths:
      - src/
      - tests/

  - step_id: document_slice
    name: Document the slice
    mission: Update user-facing and operator-facing docs.
    allowed_paths:
      - README.md
      - user-guide.md
      - docs/

  - step_id: repair_and_verify
    name: Repair and verify
    mission: Run the required checks, repair failures, and stop only when the
      slice is clean.
    allowed_paths:
      - src/
      - tests/
      - docs/

  - step_id: review_slice
    name: Review the slice
    mission: Produce a code review artifact focused on bugs, regressions, and
      testing gaps.
    allowed_paths:
      - code-reviews/

  - step_id: closeout
    name: Close out sprint docs
    mission: Update result review, context, architecture, and sprint state for
      handoff.
    allowed_paths:
      - result-review.md
      - context.md
      - sprint-plan.md
      - WHERE_AM_I.md
      - architecture.md
```

## How To Run The Workflow

Validate first:

```bash
python3 -m agent_orch.main validate-playbook playbooks/<workflow>.yaml
```

For the common validate-run-watch path, prefer `launch-workflow`:

```bash
python3 -m agent_orch.main launch-workflow playbooks/<workflow>.yaml --workspace . --runs-dir artifacts/runs
```

If you want to run the workflow and dashboard watcher separately, you can still
do that:

```bash
python3 -m agent_orch.main run playbooks/<workflow>.yaml --workspace . --runs-dir artifacts/runs
```

For long-running implementation steps, increase the worker budget when needed:

```bash
AGENT_ORCH_CODEX_TIMEOUT_SECONDS=3600 python3 -m agent_orch.main run playbooks/<workflow>.yaml --workspace . --runs-dir artifacts/runs
```

If the run fails after some steps have already passed, resume instead of
starting over:

```bash
python3 -m agent_orch.main resume-run artifacts/runs/<failed_run_id>
```

## How To Run The Dashboard Monitor

If you used `launch-workflow`, Agent-Orch will print the run id and dashboard
path for you.

If you started the run manually, identify the run directory:

- `artifacts/runs/<run_id>/`

Then start the HTML dashboard watcher:

```bash
python3 -m agent_orch.main render-run-dashboard artifacts/runs/<run_id> --output artifacts/runs/<run_id>/dashboard.html --watch --interval 60
```

Optional terminal surface:

```bash
python3 -m agent_orch.main monitor-run artifacts/runs/<run_id>
```

The dashboard is a static HTML file rewritten every 60 seconds. The browser may
still need a manual refresh to show the latest snapshot.

## What You Must Tell The Human

As soon as the run and watcher are started, report:

- the workflow file being run
- the run id
- the exact dashboard path

Use language like:

```text
Workflow started: playbooks/<workflow>.yaml
Run id: <run_id>
Dashboard: <absolute-path-to-repo>/artifacts/runs/<run_id>/dashboard.html
The watcher refreshes that file every 60 seconds.
```

If the repo uses a stable operator path outside the run directory, declare it in
the workflow's operational paths and report that location too.

## Final Rule

Do not treat Agent-Orch as a passive note-taking tool.

For meaningful product work, the expected behavior is:

1. write the workflow
2. validate the workflow
3. run Agent-Orch with the workflow
4. run the dashboard watcher
5. tell the human where `dashboard.html` is
6. resume failed runs instead of redoing completed work
