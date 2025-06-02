# CIRIS API Client Expectations

This document outlines how the Wyoming bridge communicates with the CIRIS API.

## Message Submission

- **Endpoint**: `POST /v1/messages`
- **Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <CIRIS_API_KEY>` (optional)
- **Payload**:
  - `content`: user text to send to CIRIS
  - `channel_id`: identifies the integration (default: `home_assistant`)
  - `author_id`: identifier for the voice user
  - `author_name`: human readable name for the user
  - `context`: extra data such as profile and source

The server is expected to respond with JSON containing at least the key `content` with the assistant's reply.

## Response Retrieval

The optional `get_response` helper polls the `/v1/status` endpoint to fetch a stored response. This is useful if the CIRIS server performs asynchronous processing. It returns the field `last_response.content` when available.

## Error Handling

If the API request fails or returns a non-200 status, the client logs the error and returns a fallback message so that the user receives a graceful failure notice.
