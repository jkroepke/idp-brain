# 5.6: Built-In Weaviate MCP Server

## Goal

Use Weaviate's built-in MCP server as the default agent interface and avoid an application-owned MCP service.

Documentation: https://docs.weaviate.io/weaviate/configuration/mcp-server

Step 5.0 is normative. Existing custom MCP plans and code do not define required compatibility behavior.

## Explicit Non-Requirements

The MVP MCP interface does not require:

- server-side trusted corpus eligibility derivation
- hidden application-side source, visibility, sensitivity, license, version, active-state, or index-generation filters
- an application-owned exact lookup path
- authority or freshness post-processing
- separate citation objects
- evidence-bundle assembly
- custom `fetch`, `explain_search`, or `list_sources` tools

Citation metadata is returned as properties of each `EvidenceChunk`. Authorization and evidence separation use Weaviate RBAC, collections, tenants, and read-only credentials.

## Instructions

1. Enable the MCP server on `/v1/mcp`.
2. Use Streamable HTTP.
3. Disable write access.
4. Require a read-only credential outside isolated local development.
5. Restrict the credential with Weaviate RBAC to the intended collection or tenant.
6. Customize tool descriptions for `EvidenceChunk` where useful.
7. Return sanitized content and citation fields through selected return properties.
8. Test the server with a real MCP client.
9. Do not implement:
   - `src/idp_brain/mcp/server.py`
   - custom MCP authentication
   - custom `search`, `fetch`, `explain_search`, or `list_sources` tools
   - duplicate MCP transport telemetry
   - a compatibility wrapper around the former evidence-bundle response
10. Use separate collections or tenants when different callers need different evidence.

## Checks

- built-in MCP hybrid search returns the expected fixture
- citation properties are present on the returned evidence object
- write tools are unavailable
- unauthorized collections or tenants are inaccessible
- no custom Python MCP server is started
- no custom exact, fetch, explain, citation-assembly, or evidence-bundle path is invoked
- `mise run ci`

## Acceptance Criteria

Agents can query the intended evidence through Weaviate MCP with read-only authorization and no application-owned MCP server. Missing legacy custom tools or response contracts are not considered regressions.
