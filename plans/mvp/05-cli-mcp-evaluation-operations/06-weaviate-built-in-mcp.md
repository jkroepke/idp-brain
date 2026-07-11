# 5.6: Built-In Weaviate MCP Server

## Goal

Use Weaviate's built-in MCP server as the default agent interface and avoid an application-owned MCP service.

Documentation: https://docs.weaviate.io/weaviate/configuration/mcp-server

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
10. Use separate collections or tenants when different callers need different evidence.

## Checks

- built-in MCP hybrid search returns the expected fixture
- citation properties are present
- write tools are unavailable
- unauthorized collections or tenants are inaccessible
- no custom Python MCP server is started
- `mise run ci`

## Acceptance Criteria

Agents can query the intended evidence through Weaviate MCP with read-only authorization and no application-owned MCP server.
