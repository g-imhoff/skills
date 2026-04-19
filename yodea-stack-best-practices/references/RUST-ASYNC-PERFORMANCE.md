# Rust Async, Tokio & Performance

## Tokio Runtime Patterns

### Task Spawning

- Never spawn a task for trivially small work -- inline it
- Use `async move { ... }` to move owned data into spawned tasks
- Share cross-task data via `Arc`
- Use `tokio::task::spawn_blocking` for CPU-bound or synchronous I/O
- NEVER run blocking code on Tokio worker threads -- starves the executor
- Never call `block_on` inside a Tokio worker thread -- deadlocks

### Structured Concurrency

Use `JoinSet` + `CancellationToken` + `TaskTracker` together:

```rust
let token = CancellationToken::new();
let tracker = TaskTracker::new();

// In accept loop:
tracker.spawn(handle_connection(token.child_token(), conn));

// On SIGTERM:
tracker.close();
token.cancel();
tracker.wait().await; // waits for all in-flight tasks
```

- **`JoinSet`**: Manages spawned tasks, supports `abort_all()`, collects results via `join_next().await`
- **`CancellationToken`**: Graceful shutdown. Use `child_token()` for hierarchy (cancelling child doesn't cancel parent)
- **`TaskTracker`**: Lighter than JoinSet when you only need to wait for completion without results

### Backpressure

Always use bounded channels. Wrap remote calls with `tokio::time::timeout`. Unbounded queues are memory leaks.

## Async Traits (Rust 1.75+)

Native `async fn` in traits is stabilized. No crate needed for static dispatch.

| Scenario | Solution |
|---|---|
| Static dispatch, single-threaded | Native `async fn` in trait |
| Static dispatch, multi-threaded | Native + `trait_variant::make` for Send |
| Dynamic dispatch (`dyn Trait`) | `#[async_trait]` or manual `Pin<Box<dyn Future>>` |
| Library API needing max flexibility | Provide both via `trait_variant` |

## Error Handling

### Architecture

```
Library layer:  thiserror enums with #[from] and #[source]
       |  (automatic From conversion)
       v
Application layer:  anyhow::Result with .context()
       |
       v
main/API boundary:  log or display the full error chain
```

### thiserror Rules

- Use `#[from]` for automatic `From<T>` conversions
- Use `#[error(transparent)]` to wrap underlying errors
- Use `#[source]` to preserve the error chain
- Always `derive(Debug)` on error types
- Don't over-engineer: if 20 variants all handled identically, consolidate

### anyhow Rules

- Use `.context("what was being attempted")` at every `?` propagation
- Use `anyhow!("message")` for ad-hoc errors, `bail!("message")` for early returns
- Use `.downcast_ref::<SpecificError>()` when you occasionally need the underlying type

## reqwest Best Practices

### Connection Pooling

Create ONE `Client` and reuse it everywhere (`Arc<Client>` or in app state).

```rust
let client = Client::builder()
    .timeout(Duration::from_secs(30))           // overall request timeout
    .connect_timeout(Duration::from_secs(5))     // TCP + TLS handshake
    .pool_idle_timeout(Duration::from_secs(90))  // idle connection lifetime
    .pool_max_idle_per_host(10)
    .build()?;
```

### Streaming

- Use `response.bytes_stream()` for large payloads
- Enable `gzip`/`brotli` features for automatic decompression
- For SSE, pair with `reqwest-eventsource`

## SSE Streaming (reqwest-eventsource)

```rust
let mut es = reqwest_eventsource::EventSource::get(url);
while let Some(event) = es.next().await {
    match event {
        Ok(Event::Open) => { /* connected */ },
        Ok(Event::Message(msg)) => { process(msg).await; },
        Err(_) => { es.close(); break; }
    }
}
```

Always handle reconnection. Use `Last-Event-ID` for resumability.

## WebSocket (tokio-tungstenite)

### Reconnection

- Exponential backoff with **jitter** (start 1s, max 30s, random 0-500ms jitter)
- Without jitter, server restarts cause thundering herd
- Track sequence numbers for message resumability

### Production Hardening

- Set maximum connection counts
- Implement ping/pong for dead connection detection
- Reject oversized messages
- Use `DashMap` instead of `Arc<RwLock<HashMap>>` for connection registries
- Use bounded channels -- unbounded channels are memory leaks for slow consumers
- Send WebSocket close frames before dropping connections

## Serde Performance

### Zero-Copy Deserialization

```rust
#[derive(Deserialize)]
struct Event<'a> {
    id: u32,
    name: &'a str,                    // zero-copy, implicit borrow
    #[serde(borrow)]
    description: Cow<'a, str>,         // zero-copy when possible, owned when escaped
    #[serde(borrow)]
    tags: Vec<&'a str>,               // zero-copy for each element
}
// Use from_str (not from_reader) to enable borrowing:
let event: Event = serde_json::from_str(&input)?;
```

### Rules

- Use `Deserialize<'de>` when input outlives output (e.g., `from_str`)
- Use `DeserializeOwned` when input is transient (e.g., `from_reader`, streaming)
- Use `#[serde(skip_serializing_if = "Option::is_none")]` to reduce output size
- Use `#[serde(rename_all = "camelCase")]` at container level
- Prefer `from_str` over `from_reader` -- enables zero-copy

## Memory Management

### Clone Avoidance Hierarchy (prefer top to bottom)

1. **Move ownership** when original is no longer needed
2. **Borrow (`&T` / `&mut T`)** for temporary access
3. **`Cow<'a, T>`** for usually-borrow, occasionally-own
4. **`Arc<T>`** for shared immutable ownership across threads
5. **`Arc<RwLock<T>>`** only when shared mutable access is truly needed
6. **`.clone()`** as last resort

### Alternatives to `Arc<Mutex<T>>`

| Pattern | When | Benefit |
|---|---|---|
| Channels (`mpsc`, `oneshot`) | Producer-consumer | No shared state, no lock contention |
| `RwLock` | Read-heavy, write-rare | Multiple concurrent readers |
| Lock-free (`DashMap`) | High-contention concurrent access | No deadlock, scales with cores |
| Actor model | Complex distributed state | Encapsulated, message-driven |

### Practical Async Patterns

- `Arc<Client>` (reqwest), `Arc<Pool>` (database) -- no mutex needed (internally sync)
- Config: load once, wrap in `Arc<Config>`, clone Arc (cheap) to each task
- Accumulating results: use `mpsc::channel` not `Arc<Mutex<Vec<T>>>`
- Split structs: immutable `Arc<Data>` + mutable `Arc<Mutex<State>>` to minimize lock scope
