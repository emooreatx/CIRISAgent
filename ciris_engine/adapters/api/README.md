Simple HTTP API adapter components for sending and receiving messages. The
`APIRuntime` registers these services with `Priority.HIGH` so handlers can use
the REST interface when running in API mode.
