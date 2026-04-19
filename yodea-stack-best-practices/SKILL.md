---
name: yodea-stack-best-practices
description: >
  Comprehensive best practices for the Yodea desktop app stack: Tauri v2, Rust/Tokio backend,
  React 19/TypeScript frontend, Zustand state management, Tailwind CSS v4, Shiki syntax highlighting,
  xterm.js terminal, Streamdown markdown streaming, Motion animations, Vercel AI SDK, SQLite/rusqlite,
  shadcn/ui components, Vite 7, and portable-pty. Covers IPC patterns, security, async Rust, streaming
  performance, component architecture, and build optimization. Use when writing, reviewing, or refactoring
  any code in the Yodea codebase to ensure best practices across the full stack.
metadata:
  author: yodea-team
  version: "1.0.0"
---

# Yodea Stack Best Practices

Enforces current best practices (April 2026) across the entire Yodea stack. Yodea is a Tauri v2 desktop
app that provides AI-powered conversations (Claude, Copilot, Codex, OpenCode), embedded terminals,
git worktree management, and a skill/plugin system -- all built with a Clean/Hexagonal architecture
on both the Rust backend and TypeScript frontend.

## When to Use

Apply this skill when:
- Writing or modifying **any** Rust or TypeScript code in the Yodea app
- Reviewing pull requests touching the frontend or backend
- Adding new features, components, stores, or Tauri commands
- Optimizing performance (rendering, streaming, IPC, database)
- Refactoring architecture (DDD layers, IPC patterns, state management)

## Critical Rules (Always Apply)

### Tier 1: Core Technologies

| Technology | Rule | Impact |
|---|---|---|
| **Tauri v2** | Use Channels for streaming, invoke for request-response. Never events for high-throughput | CRITICAL |
| **Tauri v2** | Never wrap managed state in `Arc` -- Tauri does it internally | HIGH |
| **Tauri v2** | All I/O commands must be `async`. Sync commands block the UI thread | CRITICAL |
| **Rust/Tokio** | Use `JoinSet` + `CancellationToken` + `TaskTracker` for structured concurrency | HIGH |
| **Rust/Tokio** | Use `spawn_blocking` for CPU-bound or sync I/O work, never on Tokio worker threads | CRITICAL |
| **Rust** | Use native `async fn` in traits (Rust 1.75+). Only use `#[async_trait]` for `dyn Trait` | HIGH |
| **Rust** | `thiserror` for library/module errors, `anyhow` with `.context()` for application code | HIGH |
| **React 19** | Never store derived state in `useState` + `useEffect`. Compute during render | CRITICAL |
| **React 19** | Use `useTransition` for non-urgent updates. Use `startTransition` for fire-and-forget | HIGH |
| **Zustand** | Never destructure the full store. Use atomic selectors. Use `useShallow` for objects/arrays | CRITICAL |
| **Zustand** | Export custom hooks, not the store directly. One store per domain concern | HIGH |
| **TypeScript** | Enable `strict: true`. Prefer `unknown` over `any`. Use `as const` objects over `enum` | HIGH |
| **SQLite** | Always set: `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`, `foreign_keys=ON` | CRITICAL |
| **Tailwind v4** | All config in CSS via `@theme`. Use `@tailwindcss/vite` plugin, not PostCSS | HIGH |
| **shadcn/ui** | Prefer CSS classes for hover/focus states over `useState` + event handlers | HIGH |
| **Vite 7** | Use `manualChunks` for vendor splitting. `splitVendorChunkPlugin` is removed | HIGH |

### Tier 2: Performance-Critical Libraries

| Technology | Rule | Impact |
|---|---|---|
| **Shiki** | Singleton highlighter instance. Fine-grained imports (langs/themes). JavaScript regex engine for web | CRITICAL |
| **Shiki** | Offload highlighting to Web Worker for streaming scenarios | HIGH |
| **xterm.js** | Set reasonable `scrollback` limits. Implement watermark-based flow control | CRITICAL |
| **xterm.js** | Always `.dispose()` addons and terminal instances on unmount | HIGH |
| **Streamdown** | Use streaming-aware parser, never `innerHTML +=`. Throttle renders to `requestAnimationFrame` | CRITICAL |
| **Motion** | Only animate `transform` and `opacity` (compositor-safe). Never animate `width`/`height`/`margin` | CRITICAL |
| **Motion** | Use string-based `transform` syntax for WAAPI hardware acceleration | HIGH |
| **AI SDK** | Forward `abortSignal` in all `streamText` calls. Implement `onAbort` for cleanup | CRITICAL |
| **reqwest** | Single `Client` instance, reuse everywhere. Always set timeouts | CRITICAL |
| **serde** | Use `&str` / `Cow<str>` with `#[serde(borrow)]` for zero-copy. Prefer `from_str` over `from_reader` | HIGH |
| **ts-rs** | Run `cargo test` in CI to verify bindings. Use `#[ts(export)]` on shared types | HIGH |
| **portable-pty** | Always kill child process and close PTY pair on shutdown. Propagate resize signals | HIGH |

## Architecture Patterns (Enforced)

Yodea uses Clean/Hexagonal architecture on both sides:

```
Feature/
  domain/           -- Core types, interfaces, business rules
  usecase/          -- Orchestration, application logic
  infrastructure/   -- Tauri invoke, file I/O, external APIs
  ui/ (TS only)     -- Components, stores, hooks
```

**Rules:**
- Domain layer has zero external dependencies
- Usecase depends only on domain interfaces (ports)
- Infrastructure implements domain interfaces (adapters)
- UI layer depends on usecase, never directly on infrastructure
- Dependency injection: Rust uses `app.manage()`, TS uses store initialization with repository injection

## Quick Decision Trees

### IPC: Which mechanism?

```
Need return value?
  YES --> invoke (command)
  NO  --> Need streaming?
    YES --> Channel (Rust -> Frontend)
    NO  --> Event (fire-and-forget notification)
```

### State: Where to put it?

```
Used by one component only?
  YES --> useState / useRef
  NO  --> Shared across feature?
    YES --> Zustand store (one per domain)
    NO  --> Derived from existing state?
      YES --> Compute during render (useMemo)
      NO  --> Zustand store
```

### Error handling: Which crate?

```
Code consumed by other modules?
  YES --> thiserror (typed enum with #[from], #[source])
  NO  --> anyhow with .context() at every ? point
```

## Reference Documentation

Deep-dive guides for each technology area:

- [references/TAURI-IPC-SECURITY.md](references/TAURI-IPC-SECURITY.md) -- IPC patterns, capabilities, CSP, async commands, state management, bundle optimization
- [references/REACT-STATE-COMPONENTS.md](references/REACT-STATE-COMPONENTS.md) -- React 19 features, Zustand v5 patterns, component composition, testing
- [references/RUST-ASYNC-PERFORMANCE.md](references/RUST-ASYNC-PERFORMANCE.md) -- Tokio patterns, error handling, serde, memory management, async traits
- [references/STREAMING-RENDERING.md](references/STREAMING-RENDERING.md) -- Shiki, xterm.js, Streamdown, AI SDK streaming, real-time rendering optimization
- [references/STYLING-UI-ANIMATION.md](references/STYLING-UI-ANIMATION.md) -- Tailwind v4, shadcn/ui + Radix, Motion animations, design tokens
- [references/BUILD-TOOLING.md](references/BUILD-TOOLING.md) -- Vite 7, TypeScript 5.8, ESLint 9, Bun, code splitting strategies
- [references/DATABASE-TERMINAL.md](references/DATABASE-TERMINAL.md) -- SQLite/rusqlite, PTY management, migrations, connection architecture
