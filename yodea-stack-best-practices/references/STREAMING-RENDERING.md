# Streaming & Rendering Performance

## Shiki (Syntax Highlighting)

### Singleton Pattern

Create the highlighter once and reuse it. There is no built-in caching.

```typescript
// Module-level singleton
let highlighterPromise: Promise<Highlighter> | null = null;

export function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighterCore({
      themes: [import('@shikijs/themes/nord')],
      langs: [import('@shikijs/langs/typescript')],
      engine: createJavaScriptRegexEngine(),
    });
  }
  return highlighterPromise;
}
```

### Fine-Grained Imports

Use `shiki/core` with explicit dynamic imports for only needed themes and languages:

```typescript
import { createHighlighterCore } from 'shiki/core'
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript'
```

Bundle sizes: Full = 6.4 MB / Core = ~12 KB (plus only what you import).

### Engine Selection

- **JavaScript RegExp engine** (`shiki/engine/javascript`): smaller bundle, faster startup -- use for web
- **Oniguruma WASM engine**: full grammar compatibility -- use for server-side only

### Worker-Based Highlighting

Shiki regex execution is CPU-intensive. Offload to a Web Worker for streaming scenarios to prevent main-thread jank.

### Incremental Highlighting

For streaming contexts, use `codeToTokens` for token-level updates instead of full `codeToHtml` re-renders.

### Checklist

1. Singleton highlighter instance, async-bootstrapped before first use
2. Fine-grained imports with only needed langs/themes
3. JavaScript engine for web, Oniguruma for full compatibility
4. Web Worker for highlighting during user interaction
5. `explanations: false` unless specifically needed

## xterm.js (Terminal Emulation)

### Buffer Management

- Typed-array-based buffers recycle memory (write buffer: 50 MB hard limit)
- Data processing designed to complete in under 16ms per frame
- Set `scrollback` to reasonable limit (5000-10000 lines), never unlimited

### Flow Control (Critical)

Use the watermark strategy:

```
Track pending data volume:
  Above HIGH watermark (500 KB) --> pause sending
  Below LOW watermark           --> resume sending
```

- `write()` callback fires once per chunk when processed -- use for backpressure
- Reduce callback frequency: place callbacks only after accumulating significant data (~100 KB)
- For WebSocket transports: implement custom ACK protocol for client-to-server flow control

### Renderer Selection

- **DOM renderer** (default): adequate for most use cases, faster in v6
- **WebGL renderer** (addon): use for high-frequency output or large scrollback
- Canvas renderer: removed in v6 -- migrate to WebGL or DOM

### Addon Lifecycle

- Addons activate via `terminal.loadAddon(addon)` calling `addon.activate(terminal)`
- Always call `addon.dispose()` when removing/destroying terminals
- Only load addons you need -- keeps core lean

### Checklist

1. Set reasonable `scrollback` limits per terminal instance
2. Implement watermark-based flow control for server-connected terminals
3. Use WebGL renderer addon for high-throughput scenarios
4. Dispose addons and terminal instances on unmount
5. Batch server-side data into chunks before sending
6. Stress-test with `yes` + Ctrl-C to validate keystroke responsiveness

## Streamdown (Streaming Markdown)

### Core Principle

Streamdown processes chunks individually, holds back output until structure is unambiguous, then appends new DOM nodes (never replaces all content).

### Integration

```tsx
<Streamdown
  animated
  plugins={{ code, mermaid, math, cjk }}
  isAnimating={status === 'streaming'}
>
  {markdownText}
</Streamdown>
```

### Rules

- **NEVER** use `textContent +=` or `innerHTML +=` -- destroys and recreates all child nodes
- Use `append()` to add new nodes incrementally
- Always sanitize model output before rendering (XSS risk from prompt injection)
- Throttle renders with `requestAnimationFrame` to batch at 60fps
- Only load plugins you need to minimize bundle

### Combined with Shiki

For code blocks in streaming markdown, combine Streamdown's `@streamdown/code` with Shiki's `codeToTokens` for incremental highlighting without re-rendering previously highlighted code.

## Vercel AI SDK (Streaming)

### Abort Handling

```typescript
// Server-side: forward request cancellation
const result = streamText({
  model,
  messages,
  abortSignal: req.signal,
  onAbort: (steps) => {
    // Persist partial results, release resources
  },
});

// Client-side: user-initiated cancellation
const { stop } = useChat();
```

**Rules:**
- ALWAYS pass `abortSignal` in all `streamText` calls
- Implement `onAbort` callback to persist partial results
- Stream abort is incompatible with stream resumption -- choose one per use case
- For `toUIMessageStreamResponse`, check `isAborted` in `onFinish` to prevent memory leaks

### Caching

Enable `cache: 'auto'` for supported providers (Anthropic, MiniMax) to reduce token usage.

### Tools

- `needsApproval: true` for human-in-the-loop (accepts boolean or conditional function)
- `strict: true` for native JSON Schema validation
- `toModelOutput` separates tool results from tokens sent to model (reduces context waste)

### DevTools

Use `npx @ai-sdk/devtools` at localhost:4983 in development to monitor calls, tokens, and timing.

## Cross-Cutting Performance Patterns

### High-Frequency Real-Time Data (20+ msg/s)

```typescript
// Buffer in ref, flush to state via requestAnimationFrame
const bufferRef = useRef<StreamEvent[]>([]);
const rafRef = useRef<number>();

function onMessage(event: StreamEvent) {
  bufferRef.current.push(event);
  if (!rafRef.current) {
    rafRef.current = requestAnimationFrame(() => {
      setState(prev => [...prev, ...bufferRef.current]);
      bufferRef.current = [];
      rafRef.current = undefined;
    });
  }
}
```

### Suspense Architecture

```tsx
<ErrorBoundary fallback={<ErrorMessage />}>
  <Suspense fallback={<Skeleton />}>
    <DataComponent />
  </Suspense>
</ErrorBoundary>
```

- Use narrow, independent Suspense boundaries (slow components don't block fast ones)
- Use `useTransition` to mark stream data updates as non-urgent

### General Rules

1. **Lazy load everything**: Shiki langs/themes, xterm addons, Streamdown plugins
2. **Worker offloading**: CPU-intensive work (highlighting, parsing) off main thread
3. **Incremental/streaming**: Append-only strategies, never re-render entire output
4. **Singleton instances**: Shiki highlighters, xterm terminals, AI SDK agents -- create once
5. **Explicit cleanup**: `.dispose()` for Shiki/xterm, `onAbort` for AI SDK, `onExitComplete` for Motion
