# SQLite (rusqlite) & PTY Terminal Management

## SQLite / rusqlite

### Essential PRAGMAs (Set on Every Connection Open)

```sql
PRAGMA journal_mode = WAL;        -- persistent, set once per DB file
PRAGMA busy_timeout = 5000;       -- per-connection, wait 5s for locks
PRAGMA synchronous = NORMAL;      -- safe with WAL, better performance
PRAGMA cache_size = -64000;       -- 64MB cache
PRAGMA foreign_keys = ON;         -- enforce FK constraints
PRAGMA temp_store = MEMORY;       -- temp tables in RAM
PRAGMA mmap_size = 268435456;     -- 256MB memory-mapped I/O
```

### WAL Mode

- Allows concurrent readers with a single writer
- ~4x throughput over default DELETE journal mode
- Creates two sidecar files (`-wal`, `-shm`) -- do not delete while DB is open
- Does NOT work over network filesystems
- `journal_mode = WAL` is persistent across connections; set it once
- `busy_timeout` is per-connection; set it every time

### `busy_timeout` is Non-Negotiable

Without it, concurrent write attempts throw immediate `SQLITE_BUSY` errors instead of retrying.
Set to 3000-5000ms. Below 5000ms, write-heavy workloads may still hit contention.

### Connection Architecture

- **Single writer connection**: serialize all writes through one connection
- **Multiple reader connections**: scale to 4-6 for read-heavy workloads
- SQLite serializes writes regardless of thread count
- Use `BEGIN IMMEDIATE` for write transactions to acquire the write lock upfront

### Async Patterns

| Approach | Model | Use Case |
|---|---|---|
| `async-sqlite` | Pool of background threads | Production, connection pooling with WAL |
| `tokio::task::spawn_blocking` + raw rusqlite | Manual | Maximum control, minimal deps |

### Migration Strategy

- Use a `migrations` table with version numbers
- Run migrations at app startup before any other DB access
- Wrap each migration in a transaction
- Store migration SQL alongside Rust source code

### Common Pitfalls

1. **Omitting `busy_timeout`** -- immediate failures under concurrency
2. **Not setting `foreign_keys = ON`** -- off by default in SQLite
3. **Very large transactions (>100 MB) in WAL mode** -- poor performance
4. **Disabling idle/max-lifetime timeouts on connection pools** -- can trigger WAL cleanup and errors

## PTY Terminal Management (portable-pty)

### API Pattern

```rust
let pty_system = native_pty_system();
let pair = pty_system.openpty(PtySize { rows: 24, cols: 80, .. })?;
let child = pair.slave.spawn_command(CommandBuilder::new("bash"))?;
let reader = pair.master.try_clone_reader()?;  // clone for async read task
let writer = pair.master.take_writer()?;        // move into write task
pair.master.resize(PtySize { rows: 30, cols: 120, .. })?;
```

### Best Practices

- **Resize propagation**: Listen for terminal resize signals (`SIGWINCH` on Unix) and call `master.resize()`. The Yodea app handles this via `terminal_session_resize` IPC command
- **Cleanup**: Always `kill()` the child process and close the PTY pair on shutdown. Leaked PTYs consume file descriptors
- **Non-blocking I/O**: portable-pty reader/writer are synchronous `std::io::Read`/`Write`. Wrap with `tokio::task::spawn_blocking` or async adapters
- **Session leader**: Both crates make the child a session leader -- signals to the process group affect all descendants. Important for clean shutdown of shell pipelines
- **Buffer management**: PTY output includes raw bytes with ANSI escape sequences. xterm.js handles parsing on the frontend

### Flow Control (Yodea Pattern)

```
PTY reader thread: reads 4KB chunks
  |
  v
High-watermark check (256KB)
  |
  v  (if below watermark)
Emit terminal session event to frontend
  |
  v
Frontend (xterm.js) processes & acknowledges
  |
  v
terminal_session_ack_output releases backlog
```

**Rules:**
- 4KB chunks balance latency vs memory
- 256KB high-watermark implements xterm.js backpressure
- Async acknowledgement from frontend before sending more
- Track output backlog per session to prevent memory explosion

### Lifecycle

```
connecting --> connected --> ended/error
```

- In-memory HashMap of active sessions
- Create: spawn PTY + shell with environment variables
- Write: send input to PTY master
- Resize: update terminal dimensions
- End: kill child process, close PTY pair, remove from registry
