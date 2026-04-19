# React 19, Zustand v5 & Component Patterns

## React 19 Features

### Actions

Async functions used in transitions. Integrate with `<form>` via `action`/`formAction` props.

```tsx
<form action={submitAction}>
  <input name="email" />
  <button type="submit">Subscribe</button>
</form>
```

- `useActionState` -- get pending state and result from form actions
- `useFormStatus` -- access parent form's pending state in child components
- `useOptimistic` -- instant UI feedback that reverts on failure

### `use()` Hook

Reads promises or context during render. Can be called conditionally (unlike other hooks).

```tsx
function Details({ id }) {
  const data = use(fetchData(id));  // Must be wrapped in <Suspense>
  return <h1>{data.name}</h1>;
}
```

### `useTransition` (Refined)

Marks state updates as non-urgent. Now supports async functions directly.

- Use `useTransition` when UI needs to show progress (`isPending`)
- Use `startTransition` for fire-and-forget non-urgent updates

### React 19.2 Additions

- **`<Activity>`**: Controls visibility while preserving state. `mode="hidden"` defers updates until idle -- use for pre-rendering likely next navigations
- **`useEffectEvent`**: Extracts non-reactive logic from effects. Must not appear in dependency arrays
- **`ref` as prop**: No more `forwardRef` -- pass refs directly as props

## Zustand v5 Best Practices

### Store Design

```typescript
// Create with dependencies (Yodea pattern)
export function createProjectsStore(repository: ProjectRepository) {
  return create<ProjectsStore>()((set, get) => ({
    projects: [],
    loadProjects: async () => {
      const projects = await repository.listProjects();
      set({ projects });
    },
  }));
}
```

**Rules:**
- Use `create<State>()(fn)` -- double parentheses for proper type inference
- One store per domain concern (projects, conversations, terminal, git, etc.)
- Keep stores small and focused
- Use Zustand for global state; keep transient/local state in `useState`

### Selectors (Three Tiers)

```typescript
// Tier 1: Primitives -- no wrapper needed
const count = useStore(state => state.count);

// Tier 2: Objects/arrays -- use useShallow
const { comments, hidden } = useStore(useShallow(state => ({
  comments: state.commentsByScope,
  hidden: state.hiddenFilesByScope,
})));

// Tier 3: Deep transformations -- extract to custom hook with useMemo
const pets = useStore(state => state.pets);
const enriched = useMemo(() => pets.map(enrich), [pets]);
```

**Critical:** Never destructure the full store. `const { a, b } = useStore()` creates a new object every render.

### Export Custom Hooks

```typescript
export const useProjects = () => useProjectsStore(s => s.projects);
export const useLoadProjects = () => useProjectsStore(s => s.loadProjects);
```

### Async Mutations

```typescript
deleteProject: async (id) => {
  await repository.deleteProject(id);
  set(state => ({ projects: state.projects.filter(p => p.id !== id) }));
},
```

### Subscriptions for Side Effects

```typescript
useEffect(() => {
  const unsub = store.subscribe(
    (state) => state.projectId,
    (newId) => { /* react to change */ }
  );
  return unsub;
}, []);
```

## Component Patterns

### Composition Over Props

- **Children as props**: Default for content composition, avoids prop drilling
- **Compound Components**: Parent manages shared state via Context; children consume
- **Render props**: When children need data from parent (less common with hooks)

### Render Optimization

1. **Move state down**: Keep state in the lowest component that needs it
2. **Lift content up**: Pass children as props to avoid re-rendering static subtrees
3. Use `React.memo` only when profiling shows a real bottleneck
4. `useMemo`/`useCallback` still needed for:
   - Functions as `useEffect` dependencies
   - Props passed to `React.memo` components
   - Third-party library integration requiring stable references

### Keys

- Always use stable, unique keys (IDs, never array indices)
- Use key to force remount: `<Form key={selectedUserId} />`

### Lazy Loading

```typescript
// Route-level
const ConversationView = lazy(async () => ({
  default: (await import("@/features/conversations/ui/ConversationView")).ConversationView,
}));

// Component-level with parallel imports
const StreamdownRenderer = lazy(async () => {
  const [{ Streamdown }, { code }, { math }] = await Promise.all([
    import("streamdown"),
    import("@streamdown/code"),
    import("@streamdown/math"),
  ]);
  // ...
});
```

### Streaming UI Patterns

- **Frame-First Layout**: Render shell immediately, stream dynamic content into Suspense boundaries
- **Above-the-Fold First**: Each screenful gets its own Suspense boundary
- **Layout-Matched Fallbacks**: Skeleton heights must match final content to prevent CLS
- **High-frequency updates (20+ msg/s)**: Buffer in `useRef`, flush via `requestAnimationFrame`
- Use `useTransition` to mark stream data updates as non-urgent

## React Router v7

### Granular Lazy Loading (v7.5+)

```javascript
{
  path: '/projects',
  lazy: {
    loader: async () => (await import('./projects/loader')).loader,
    Component: async () => (await import('./projects/component')).Component,
  }
}
```

Loaders execute as soon as their code resolves, without waiting for Component code.

### Strategy

- Split loader/action code from Component code into separate files
- Lazy-load rarely visited or heavy routes
- Load critical routes (conversation view) upfront

## Testing (@testing-library/react)

### Query Priority

1. `getByRole` -- accessible, robust, matches user perspective
2. `getByLabelText` -- best for form inputs
3. `getByPlaceholderText`, `getByText` -- fallbacks
4. `getByTestId` -- last resort

### Async Patterns

- Use `findBy*` for elements that appear asynchronously (not `waitFor` + `getBy*`)
- Never wrap `render`/`fireEvent` in `act` -- Testing Library already does this
- Always prefer `userEvent` over `fireEvent`

### Rules

- Use `screen` for queries (not destructured `render` return)
- Use `query*` only to assert non-existence
- Clean up is automatic -- do not call `cleanup` manually

## Anti-Patterns to Avoid

1. **Storing derived state**: Compute during render, not `useState` + `useEffect` sync
2. **useEffect for synchronous work**: Effects are for I/O only
3. **useEffect without cleanup**: Always clean up subscriptions, timers, listeners
4. **Inline object/array literals as props**: Hoist constants or use `useMemo`
5. **Single monolithic Context**: Split by update frequency or use Zustand
6. **Array index as key**: Causes state mismatches on reorders
7. **Direct state mutation**: Bypasses reconciliation
8. **Unnecessary `forwardRef`**: React 19 passes refs as regular props
9. **Prop drilling through many layers**: Use composition, Context, or Zustand
10. **Over-destructuring Zustand stores**: Use atomic selectors
