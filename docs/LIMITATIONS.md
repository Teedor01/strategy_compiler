# What is actually tested, and what isn't

## Second re-audit (Track 3 registration, discovery, evidence registry, adversarial tests)

**Track 3 registration: resolved, not just flagged.** Confirmed, from RYO's
own live OpenAPI schema (`docs/ryo-openapi-subset.json`,
`HackathonSubmissionFields`, `additionalProperties: false`): the hackathon
submission schema has exactly twelve fields (team_name, participant_name,
email, discord_id, github_username, project_name, tracks[],
project_description, demo_video_url, repo_url, x_post_url, agree_rules,
confirm_no_secrets) and **no field for registering a skill name**. The
`/api/skills/{name}/invoke` endpoint's `name` parameter is typed as a plain
`string`, not the closed `SkillName` enum... and that endpoint requires a
platform-user `HTTPBearer` token, a different credential from the
hackathon's own `RYO_MCP_KEY`, with no connection to the submission flow at
all. Cross-checked against the organizer's own Discord submission checklist
(reproduced in `PugarHuda/nota`'s `docs/SUBMISSION.md`): the real submission
process is code on `main` + docs + `.env.example` + Project Submission Form
+ demo video + `/apply` in Discord... nothing about registering a skill
name anywhere. Conclusion: `SkillName` is RYO's own internal/production
skill catalog, unrelated to what Track 3 entrants build. A Track 3 skill is
demonstrated by following RYO's `SkillDefinition`/envelope *shape*, served
from the entrant's own code, judged by reading the repo... exactly this
project's existing approach. **No implementation change was needed or made
as a result of this finding**... it confirms the design, it doesn't correct
it.

**A real bug found via a live-recorded response, not a guess.** The
original `momentum_state` field path, `technicals.rsi_14`, was never
actually confirmed against any schema... the guide only describes RSI(14)
in prose, and no `analyze_token` response schema exists in
`ryo-openapi-subset.json`. A real, live-recorded `analyze_token/SOL`
response committed to `PugarHuda/nota` (`fixtures/recorded/analyze_token/SOL.json`
-- a real call made with a real `RYO_MCP_KEY`) shows the actual key is
`technical_analysis.rsi_14`. Fixed in `resolver.py`, with a dedicated
regression test (`tests/test_resolver_real_shape.py`) built from that real
structure so this can't silently regress. Worth stating plainly: this
project's own prior claim that this path was "verified" was overstated...
it was inferred from prose, not confirmed by a schema or a real response,
until this pass.

**Dynamic tool discovery: genuinely usable, now implemented as the source
of truth.** `GET /api/mcp/tools` (confirmed real endpoint, `McpToolInfo[]`
response: `name`, `description`, `inputSchema` as real JSON Schema) is
exactly what the guide recommends reading at startup instead of
hard-coding. `RyoClient.refresh_catalog()` now fetches it and, on success,
replaces the client's argument-validation table with the live one;
`_validate_args` reads from that per-instance table, not the module-level
constant. On any failure (network error, malformed response, empty
catalog) it fails closed and keeps the previous table... never two sources
of truth consulted at once. Tested against a mocked transport for both the
adopt-live-catalog path and every failure-closed path
(`tests/test_ryo_client.py`); not exercised against the real endpoint, for
the same credential reason as everything else RYO-side.

**Evidence registry: four additions, each passing all five audit
questions, each grounded in a real recorded response.** `price_usd`,
`change_24h_pct`, `market_cap_rank` (all from `analyze_token`, the same
tool call `momentum_state` already uses) and `fear_greed_index` (from
`market_overview`, the same tool call `market_regime` already uses) --
zero new RYO tool calls added. Full audit, including what did NOT pass and
why (free-text narrative fields, cross-token comparison needing a schema
change, derivatives deferred for scope, news verification RYO doesn't
provide at all), is in `resolver.py`'s own comments next to `REGISTRY`.
Tested in `tests/test_evidence_registry_audit.py`, including that a *new*
metric with vague human language still correctly refuses to invent a
threshold (`test_new_metric_with_vague_language_still_needs_clarification`)
-- adding metrics didn't quietly relax the ambiguity policy.

**Adversarial compiler tests: all six from the audit, all correctly
refused.** `tests/test_adversarial_compiler.py`... five land on
`NEEDS_CLARIFICATION` (a real, supported metric with an undefined
qualifier: "cheap", "huge pump", "sentiment is good", "BTC is weak"; one
genuinely un-mappable concept: "upside worth the risk"), one lands on
`UNSUPPORTED` rather than `NEEDS_CLARIFICATION` on purpose
("diversified" has a stated number but no evidence source covers
cross-portfolio diversification at all... a different failure mode from a
missing number, and the tests assert the distinction explicitly). None of
the six ever compiles to `EXECUTABLE`.

## Prior pass's findings (still true)

### First re-audit findings


A line-by-line re-read of `docs/MCP-Builder-Guide.md` against the existing
`ryo_client.py` found one real bug and one genuinely open question. Both
are recorded here rather than silently fixed-and-forgotten or silently
guessed at.

**Fixed: REST envelope was read unwrapped.** The guide's own Python REST
client example does `response.json()["result"]`, not `response.json()`
directly... the REST endpoint wraps the public envelope in a top-level
`"result"` key, matching the MCP JSON-RPC transport's own wrapping. The
first version of `RyoClient.call` read the top-level body as the envelope
itself, which would have parsed every real field as missing. Fixed, and
`tests/test_ryo_client.py::test_call_unwraps_the_result_key_per_the_guides_own_example`
exists specifically to catch a regression of this exact bug using
`httpx.MockTransport` (no live credential needed to test the fix).

**Unresolved, flagged rather than guessed: the `SkillName` enum.**
`docs/ryo-openapi-subset.json`'s `SkillName` schema is a *closed* enum of
RYO's own production skill names (`scan_market`, `analyze_token`,
`check_safety`, `execute_trade`, `create_wallet`, `swap`, ... 27 total,
including guarded/execution skills the Builder Guide is explicit hackathon
tools cannot use). Two things follow from actually reading this list rather
than assuming:

- It resolves an apparent contradiction from an earlier draft of this
  project: `check_safety` and `supported_tokens` *do* exist as real RYO
  skill names — just not among the six read-only tools the Builder Guide
  exposes to hackathon builders. They're part of RYO's own internal/product
  skill surface (wallet creation, order placement, etc.), not the hackathon
  MCP surface. An earlier document that listed them as Builder MCP tools
  was wrong about *where* they live, but the names themselves aren't
  fabricated — this is worth stating plainly rather than treating that
  document as either "all correct" or "all wrong."
- It means `compile_strategy` (this project's own Track 3 skill name)
  is **not** a member of RYO's current `SkillName` enum, and neither is any
  other Track 3 entrant's own skill name (e.g. Nota's `narrative_convergence`
  isn't in it either). That strongly implies Track 3 submissions register
  new skill names through some other mechanism than this literal enum...
  but nothing inspected in this environment says what that mechanism
  actually is. `tests/test_skill_contract.py` therefore validates
  `compile_strategy`'s definition shape (field names) against
  `SkillDefinition`/`SkillArgSchema`, but does **not** attempt to validate
  the `name` value against `SkillName`, because doing so would either
  falsely fail (if the enum really is meant to be exhaustive) or require
  guessing that it's fine to ignore (if it isn't) — this is exactly the
  "fix it or clearly mark it as unresolved" case. Resolve by asking in the
  hackathon's Discord/Telegram support channels before submission, not by
  assuming either answer.

**Implemented but still unexercised live:** `RyoClient.health()`,
`.whoami()`, and `.discover_tools()` were added to match the guide's own
recommendation to "read the live catalog at startup instead of hard-coding
assumptions" — but `RYO_TOOLS` in `ryo_client.py` is still the guide's
documented six-tool table, hard-coded, not fetched from `.discover_tools()`
at runtime. Wiring that up is a real remaining gap, named here rather than
left looking finished.



## Verified against RYO's real, official specification

`docs/MCP-Builder-Guide.md` and `docs/ryo-openapi-subset.json` in this
repository are copies of RYO's actual published documentation (sourced from
the one public, verified RYO integration that exists -- see the commit
history / README note on provenance). They were read in full before any
code in `strategy_compiler/` was written. Specifically verified from them,
not from memory or from any secondary summary:

- The exact six tool names, required/optional arguments
  (`ryo_client.py::RYO_TOOLS`).
- The public response envelope shape: `schema_version, tool, status,
  data_mode, as_of, request, data, summary, availability, warnings`
  (`envelope.py`).
- That RYO is read-only and explicitly does not read portfolio/user state
  (`resolver.py`'s `EvidenceSource.USER_DECLARED` split exists because of
  this, not as a design guess).
- The REST call shape (`POST {base}/tools/{tool}/call` with a bare argument
  object) and recommended retry/backoff behaviour
  (`ryo_client.py::RyoClient.call`).
- The Track 3 skill contract shape (`SkillDefinition`, `SkillArgSchema`,
  `SkillCallRequest`, `SkillCallResponse`) straight from
  `docs/ryo-openapi-subset.json`'s `schemas` section (`skill.py`).

## What has been executed and passed in this environment

- The entire compiler classification logic (`compiler.py`): ambiguity
  detection, unsupported-metric detection, conflict detection -- exercised
  against the ugly test sentences from the brief's own test list, via
  `FixtureLLM` (a labelled, non-LLM test double, not a live model call).
- The entire deterministic evaluator (`evaluator.py`): PASS/FAIL/UNKNOWN
  logic, momentum RSI thresholding, final ALLOW/BLOCK/UNKNOWN folding --
  exercised against hand-built `ResolvedEvidence` fixtures.
- Envelope parsing (`envelope.py`) against a fixture shaped exactly like the
  guide's documented envelope, including the "null must never become 0"
  rule (`MissingEvidence`).
- The resolver's split between RYO-sourced and user-declared evidence
  (`resolver.py`), including the "evidence genuinely unavailable" path.
- Receipt construction and its deterministic `trace_id` (`receipt.py`):
  `tests/test_determinism.py` runs the identical strategy through identical
  fixtures 5 times and asserts every field of the receipt is byte-identical
  except the two wall-clock timestamps; `tests/integration/test_cause_and_effect.py`
  runs the brief's own two-scenario sequence (20% vs 10% allocation, same
  evidence) and asserts, at the rule level, which single rule caused the
  decision to flip -- not just that the two receipts differ.
- The FastAPI app boots and `/api/decide` returns a well-formed receipt
  against fixture data, including the new provenance fields
  (`tests/test_api.py`, `tests/test_provenance.py`).
- `RyoClient`'s own HTTP handling (envelope unwrapping, 429 retry/backoff,
  400 non-retry, argument validation) against a mocked transport --
  `tests/test_ryo_client.py`. This is what caught the unwrapping bug above.
- The Track 3 skill's error handling: missing argument, wrong argument
  type (both `strategy_text` and `user_declared`), unsupported-evidence
  strategies, and that every failure mode returns the same stable top-level
  shape (`tests/test_skill_contract.py`).
- Evidence provenance labelling: fixture RYO evidence is always labelled
  `"simulated"`, user-declared evidence is always labelled
  `"user_declared"`, and unresolved evidence is labelled `"unresolved"`...
  never blank, never confusable with a live read (`tests/test_provenance.py`).
- The real-integration test files (`tests/integration/test_real_ryo_integration.py`,
  `tests/integration/test_real_llm_integration.py`) themselves: confirmed
  they report `SKIPPED: RYO_MCP_KEY not configured` /
  `SKIPPED: ANTHROPIC_API_KEY not configured` and do not attempt a network
  call, when no credential is present -- run directly and observed the
  actual pytest output, not assumed from reading the code.
