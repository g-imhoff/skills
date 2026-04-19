# Tauri v2: IPC, Security & Performance

## IPC Patterns

### Commands (invoke) -- Request-Response

The primary pattern for frontend-to-backend communication.

```typescript
// Frontend
const project = await invoke<Project>("create_project", { name, path });

// Backend
#[tauri::command]
async fn create_project(name: String, path: String) -> Result<Project, AppError> {
    // ...
}
```

**Rules:**
- All I/O commands MUST be `async` to avoid blocking the UI thread
- Async commands run on `async_runtime::spawn` -- they cannot use borrowed types (`&str`, `State<'_, T>`)
- Use owned types (`String`) in async command signatures
- Async commands MUST return `Result<T, E>`
- Use `tauri::ipc::Response` for large/binary data to bypass JSON serialization

### Channels -- Streaming (Rust to Frontend)

Use for ordered, high-throughput data: agent events, terminal output, progress.

```rust
// Backend
#[tauri::command]
async fn stream_data(channel: Channel<StreamEvent>) -> Result<(), AppError> {
    channel.send(StreamEvent::Data { ... })?;
    Ok(())
}
```

```typescript
// Frontend
const channel = new Channel<StreamEvent>();
channel.onmessage = (event) => { /* handle */ };
await invoke("stream_data", { channel });
```

**Rules:**
- Channels are strongly typed and faster than events
- Deliver ordered data
- Best for: file streaming, progress, real-time feeds, agent/terminal events

### Events -- Fire-and-Forget

Use only for lifecycle notifications and loose coupling between windows.

**Rules:**
- Not type-safe (payloads are JSON strings)
- Cannot return values
- NOT designed for high throughput -- use Channels instead
- Always call `unlisten()` on component unmount to prevent memory leaks

### Decision Matrix

| Need | Use |
|------|-----|
| Request/response with return value | Commands (`invoke`) |
| Streaming data from Rust to frontend | Channels |
| Fire-and-forget notification | Events |
| Binary/large data transfer | `tauri::ipc::Response` or raw `Request` body |

## Security

### Capabilities & Permissions

- Defined as JSON/TOML in `src-tauri/capabilities/`
- All files in that directory auto-enabled unless explicitly listed in `tauri.conf.json`
- Target windows by **label** (not title) -- labels are the security boundary
- Follow naming: `<plugin>:allow-<command>` / `<plugin>:deny-<command>`
- All dangerous commands blocked by default -- explicitly allow them
- Use **scopes** for fine-grained resource access

### Content Security Policy

- Configured in `tauri.conf.json` under `app.security.csp`
- Restrict to `'self'`, avoid remote scripts/CDNs
- Add `'wasm-unsafe-eval'` only if using WebAssembly

### Security Checklist

- Validate all data crossing the Rust/WebView trust boundary
- Perform API calls with secrets in Rust, never in the frontend
- Use Tauri file system API, not Node.js fs directly
- Restrict window creation to higher-privileged windows
- Consider the Isolation Pattern for supply chain attack protection

## State Management (Rust Side)

```rust
// Setup
app.manage(DatabaseState::new(conn));
app.manage(AgentService::new(providers));

// In commands
#[tauri::command]
async fn list_projects(db: State<'_, DatabaseState>) -> Result<Vec<Project>, AppError> {
    // ...
}
```

**Rules:**
- Use `app.manage(...)` in setup, access via `State<'_, T>` in commands
- NEVER wrap state in `Arc` -- Tauri handles this internally
- Use `std::sync::Mutex` by default. Only use `tokio::sync::Mutex` when holding guards across `.await`
- Type mismatch in State injection (`State<'_, AppState>` vs `State<'_, Mutex<AppState>>`) causes **runtime panic** -- use type aliases
- `AppHandle` is cheap to clone -- pass it into threads instead of `State`
- For async I/O resources: spawn a dedicated task and use message passing rather than async mutex

## Bundle Size Optimization

### Cargo.toml Release Profile

```toml
[profile.release]
codegen-units = 1    # Better LLVM optimization
lto = true           # Link-time optimization
opt-level = "s"      # Optimize for size ("z" for even smaller)
panic = "abort"      # Remove panic unwinding code
strip = true         # Remove debug symbols
```

### Tauri 2.4+ Unused Command Removal

```json
{
  "build": {
    "removeUnusedCommands": true
  }
}
```

Strips commands never allowed in capability files from the binary.

## Anti-Patterns to Avoid

1. **Wrapping state in `Arc`** -- Tauri already wraps managed state in `Arc`
2. **Using `&str` in async command signatures** -- causes compile errors, use `String`
3. **Sync commands for I/O** -- blocks UI thread, always use `async`
4. **Using events for streaming** -- use Channels instead
5. **Not cleaning up event listeners** -- memory leaks, always `unlisten()`
6. **API calls with secrets in frontend** -- always from Rust
7. **Returning large data as JSON** -- use `tauri::ipc::Response` for binary/large data
8. **Type mismatch in State injection** -- runtime panic, use type aliases
9. **Async Mutex when std Mutex suffices** -- higher overhead, only for guards across `.await`
10. **Overly permissive capabilities** -- follow principle of least privilege
