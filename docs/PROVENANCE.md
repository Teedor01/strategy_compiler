# Provenance of docs/MCP-Builder-Guide.md and docs/ryo-openapi-subset.json

These are copies of RYO's own official builder documentation and OpenAPI
schema, not something written for this project. They were obtained from the
`docs/` folder of the public GitHub repository `PugarHuda/nota` (an existing,
verified RYO-CHAN Hackathon 2026 submission), because `ryobuild.com`'s
JavaScript-rendered pages could not be fetched directly in this environment.

This matters for two reasons, both worth stating plainly rather than
glossing over:

1. This is a secondhand copy, not a first-party fetch. The guide's own
   closing line says the live catalog (`GET /api/mcp/tools`) "is the final
   source of truth if this guide and the deployed server ever differ"...
   the same caveat applies here, one level further removed, to this copy of
   the guide itself. Before relying on this for a real submission, verify
   directly against `https://app-ryochan.com/api/mcp/tools` and against the
   live `ryobuild.com` documentation once you have a way to render it (a
   headless browser, or asking a teammate who already has the MCP Builder
   Guide open).
2. It is used here strictly as a factual API/schema reference (tool names,
   argument shapes, response envelope fields) to build against... the same
   way any project vendors an OpenAPI spec it doesn't own... not
   reproduced as content in its own right.

Everything in `strategy_compiler/` was written by reading these files
first, per the brief's explicit instruction to verify the real specification
before implementing the evidence resolver rather than relying on the
six-tool marketing summary.
