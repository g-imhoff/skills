# Build Tooling: Vite 7, TypeScript 5.8, ESLint 9 & Bun

## Vite 7

### Breaking Changes

- Node.js 20.19+ or 22.12+ required (18 dropped)
- `splitVendorChunkPlugin` removed -- use `manualChunks` directly
- Legacy Sass API removed (use modern Sass API)
- Vitest 3.2+ required
- Default browser target: `'baseline-widely-available'` (Chrome 107+, Firefox 104+, Safari 16+)

### Chunking Strategy

```typescript
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        vendor: ["react", "react-dom"],
        ui: ["@radix-ui/react-dialog", "@radix-ui/react-popover", "cmdk"],
        terminal: ["@xterm/xterm"],
      },
    },
  },
}
```

**Rules:**
- Isolate large, stable deps (React, UI libs) for long-term caching
- Split by route/feature for on-demand loading
- Use dynamic `import()` for code not needed on initial load
- Don't over-split into excessive small chunks (increases HTTP requests)
- Don't lazy-load tiny components (overhead exceeds benefit)

### Rolldown (Experimental)

Rust-based bundler available via `rolldown-vite`:
- Build speed: up to 16x faster
- Memory: up to 100x peak reduction
- Try on a branch to benchmark before adopting

### HMR

- 40% faster for deep component trees via Rolldown's module graph traversal
- No more spurious full reloads on deeply nested stateful components

## TypeScript 5.8

### Features to Adopt

- **Granular return expression checks**: catches bugs in ternary returns previously hidden by `any`
- **`--erasableSyntaxOnly`**: aligns with Node.js native TS stripping. Errors on `enum`, `namespace` with runtime code
- **Import attributes**: `with { type: "json" }` replaces `assert { type: "json" }` (now errors under `--module nodenext`)

### Patterns to Prefer

- ECMAScript features over TS-specific constructs (avoid `enum`, use `as const`)
- Run `tsc` as dedicated type-checker separate from runtime
- Enable `strict: true` + `exactOptionalPropertyTypes`
- Use `NoInfer<T>` for fine-grained generic inference control
- Use `using`/`await using` for deterministic resource cleanup
- Prefer `unknown` over `any` and narrow with type guards

### ts-rs (Rust-to-TypeScript)

- Annotate Rust types with `#[derive(TS)]` and `#[ts(export)]`
- Run `cargo test` to generate bindings
- Set `TS_RS_EXPORT_DIR` in `.cargo/config.toml` for consistent paths
- Enable feature flags: `chrono-impl`, `uuid-impl`, `serde-json-impl`, `url-impl`
- **CI enforcement**: if generated bindings differ from committed, fail the build

Key attributes:
- `#[ts(rename = "...")]` -- override TypeScript name
- `#[ts(skip)]` -- exclude fields
- `#[ts(as = "...")]` / `#[ts(type = "...")]` -- override TS type
- `#[ts(optional_fields)]` -- `Option<T>` emits `t?: T` instead of `t: T | null`

Respects serde attributes: `rename`, `rename_all`, `tag`, `content`, `untagged`, `skip`, `flatten`.

## ESLint 9 (Flat Config)

### Recommended Pattern

```javascript
import { defineConfig, globalIgnores } from "eslint/config";
import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default defineConfig([
  globalIgnores(["dist", "node_modules", "coverage", "**/*.d.ts"]),
  eslint.configs.recommended,
  {
    files: ["**/*.ts", "**/*.tsx"],
    extends: [tseslint.configs.recommended],
    languageOptions: { parser: tseslint.parser },
  },
  {
    files: ["**/*.js", "**/*.mjs"],
    extends: [tseslint.configs.disableTypeChecked],
  },
]);
```

**Rules:**
- Use `defineConfig()` for type safety and auto-flattening
- Use `extends` within config objects for scoped composition
- Use `globalIgnores()` for directory-level ignores
- Disable type-checked rules for JS files via `tseslint.configs.disableTypeChecked`
- Ignore `**/*.d.ts` (generated type declarations)

## Bun (Test Runner)

### Performance

| Runner | Full Run (1500 tests) | vs Jest |
|---|---|---|
| Jest (SWC) | 45s | baseline |
| Vitest | 12s | 3.7x faster |
| Bun test | 4s | 11x faster |

### When to Use

- Pure TypeScript/JavaScript logic tests (no DOM)
- Projects already on Bun runtime
- CI pipelines where fast feedback is critical
- Use Vitest instead for React component testing (JSDOM/happy-dom)

### Best Practices

- Use `describe()` blocks with shared setup/teardown
- `spyOn()` for tracking existing methods; `mock.module()` for full replacement
- `mockRestore()` in `afterEach` to return original state
- `mockClear()` between tests to reset call history

## Code Splitting Strategy

### Route-Based (Primary)

```tsx
const ConversationView = lazy(() => import("@/features/conversations/ui/ConversationView"));
const SkillsPage = lazy(() => import("@/features/skills/ui/SkillsPage"));
const SettingsPage = lazy(() => import("@/features/settings/ui/SettingsPage"));
```

### Dynamic Import for Heavy Dependencies

Good candidates: Shiki, rich text editors, charting, PDF viewers, Streamdown plugins.

```typescript
// Load Streamdown plugins in parallel
const [{ Streamdown }, { code }, { math }, { mermaid }] = await Promise.all([
  import("streamdown"),
  import("@streamdown/code"),
  import("@streamdown/math"),
  import("@streamdown/mermaid"),
]);
```

### Anti-Patterns

- Over-splitting into excessive small chunks
- Lazy-loading tiny components (overhead > benefit)
- Splitting frequently-accessed features always needed on load
- Nesting Suspense boundaries excessively

### Bundle Analysis

Use `rollup-plugin-visualizer` to identify duplicate code and oversized dependencies.

### Built-in Vite Optimizations (No Config Needed)

- Tree-shaking
- Minification
- Hashed filenames for cache busting
- Module preloading
- Dead code elimination for `import.meta.env.DEV` blocks
