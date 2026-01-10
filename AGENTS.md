# AGENTS.md - Coding Guidelines for Arboris Novel

## Project Overview
Arboris Novel is a full-stack AI-powered novel writing platform with a Python FastAPI backend and Vue 3 frontend.

## Build / Lint / Test Commands

### Backend (Python/FastAPI)
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run development server (hot reload)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run with custom host/port
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Frontend (Vue 3/TypeScript)
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Type check
npm run type-check

# Build for production
npm run build

# Preview production build
npm run preview

# Format code
npm run format
```

### Docker (Full Stack)
```bash
# Start with default SQLite
docker compose up -d

# Start with MySQL
DB_PROVIDER=mysql docker compose --profile mysql up -d
```

## Backend Code Style (Python)

### Imports
- Use `from __future__ import annotations` at top of all Python files for forward references
- Group imports: stdlib → third-party → local (separated by blank lines)
- Absolute imports: `from app.models.novel import NovelProject`
- Relative imports: `from ...core.config import settings` (3+ levels up)

### Naming Conventions
- Classes: `PascalCase` (e.g., `NovelProject`, `AuthService`)
- Functions/Methods: `snake_case` (e.g., `get_project_schema`, `create_user`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `BIGINT_PK_TYPE`, `LONG_TEXT_TYPE`)
- Private/Protected: prefix with `_` (e.g., `_ensure_prompt`, `_coerce_text`)
- Database models: `PascalCase` with `Mapped[type]` annotations
- Schemas: `PascalCase` (e.g., `NovelProjectSchema`, `ConverseResponse`)

### Type Hints
- Use modern Python 3.10+ syntax: `dict[str, Any]` instead of `Dict[str, Any]`
- Use `Optional[T]` for nullable fields
- Use `from typing import Any, Dict, List, Optional`
- Return types on all functions
- Use `AsyncSession` for database sessions

### Async Patterns
- All database operations use async/await with `AsyncSession`
- Use `async with AsyncSessionLocal() as session:` for session management
- Use `async def` for all route handlers and service methods
- SQLAlchemy 2.0 style: `select(Model).where(Model.id == id)` (no `.all()`, use `session.scalars()`)

### Error Handling
- Raise `HTTPException` for API errors with descriptive detail messages
- Use `status` codes from `fastapi.status` (e.g., `status.HTTP_404_NOT_FOUND`)
- Log errors with `logger.exception()` for full stack traces
- Log info with `logger.info("message", arg1, arg2)` (not % formatting)
- Validate external API responses (JSON, LLM output) before use

### Database Models (SQLAlchemy 2.0)
- Use `Mapped[T]` type annotations for all columns
- Use `mapped_column()` instead of `Column()`
- Use `relationship()` with explicit `back_populates` and `uselist` defaults
- Use `ForeignKey` with `ondelete="CASCADE"` for cascade deletes
- Custom column types for cross-DB compatibility (e.g., `BIGINT_PK_TYPE`, `LONG_TEXT_TYPE`)
- Use `server_default=func.now()` for timestamps
- Descriptor pattern for SQLAlchemy `metadata` column conflict (`_MetadataAccessor`)

### Configuration
- Use `pydantic-settings.BaseSettings` for config
- Load with `@lru_cache` cached `get_settings()` function
- All env vars defined in `Settings` class with `Field()` defaults
- Validate env vars with `@validator` methods
- Use `settings.<property_name>` to access config

### API Routes
- Use `APIRouter` with `prefix` and `tags` (e.g., `router = APIRouter(prefix="/api/novels", tags=["Novels"])`)
- Use `Depends()` for dependency injection
- Response model in decorator: `@router.get("", response_model=List[NovelProjectSummary])`
- Path params as function args: `async def get_novel(project_id: str, ...)`
- Body params: `payload: Blueprint = Body(...)`
- Query params: simple args without Body()

### Services Layer
- One service per domain (e.g., `NovelService`, `AuthService`, `LLMService`)
- Services receive `AsyncSession` via constructor injection
- Use repositories for database access (e.g., `UserRepository`, `NovelRepository`)
- Services contain business logic; repositories handle data access
- Use dependency injection in routes: `def get_novel_service(session: AsyncSession = Depends(get_session)) -> NovelService`

### Logging
- Use module-level loggers: `logger = logging.getLogger(__name__)`
- Configured via `dictConfig` in `app/main.py` with per-module levels
- Log format: `logger.info("Action on resource %s", resource_id)`

### LLM Integration
- Use custom `LLMService` for all LLM calls
- Handle `response_format=None` for non-OpenAI models (Claude)
- Use `timeout` parameter for long-running requests
- Sanitize LLM responses with `json_utils` (remove think tags, unwrap markdown JSON)
- Store prompts in `backend/prompts/*.md` files

## Frontend Code Style (Vue 3 + TypeScript)

### Imports
- Use `@` alias for src: `import { useAuthStore } from '@/stores/auth'`
- Vue Composition API: `import { defineStore } from 'pinia'`
- Group imports: Vue → third-party → local

### Naming Conventions
- Components: `PascalCase.vue` (e.g., `NovelWorkspace.vue`, `Login.vue`)
- Functions/Methods: `camelCase` (e.g., `fetchUser`, `goToInspiration`)
- Variables: `camelCase` (e.g., `authStore`, `novelProjects`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `API_BASE_URL`)
- Interfaces/Types: `PascalCase` (e.g., `NovelProject`, `Blueprint`)
- Stores: `use<Name>Store` (e.g., `useAuthStore`, `useNovelStore`)

### TypeScript
- All functions have explicit return types
- Use `interface` for object shapes, `type` for unions/aliases
- Nullable types with `| null` (e.g., `token: string | null`)
- Use strict mode (tsconfig)
- Avoid `any`; use proper types or `Record<string, any>`

### Vue Components (Composition API)
- Use `<script setup lang="ts">` syntax
- Refs with `ref<T>()` or `computed<T>()`
- Use Pinia stores via composables: `const authStore = useAuthStore()`
- Event handlers in template: `@click="handleClick"`
- Props with `defineProps<{ ... }>()`
- Emits with `defineEmits<{ ... }>()`

### API Layer
- Centralized API calls in `src/api/*.ts` files
- Static methods in API classes: `static async getNovel(projectId: string)`
- Base URL from `API_BASE_URL` (production: '', dev: 'http://127.0.0.1:8000')
- Unified `request()` function handles auth, errors, and 401 redirects
- FormData for file uploads (remove Content-Type header)
- 401 auto-redirect to `/login`

### State Management (Pinia)
- Store definition: `defineStore('name', { state, getters, actions })`
- State in `state()` function
- Computed values in `getters`
- Async methods in `actions`
- Use `localStorage` for persistence (tokens, user data)

### Styling (Tailwind CSS 4)
- Utility-first CSS
- Use `:` for dynamic classes: `:class="[...]"`
- Hover states: `hover:scale-105`
- Transitions: `transition-all duration-300`
- Responsive: `md:grid-cols-2 lg:grid-cols-3`

### Formatting (Prettier)
- No semicolons (`"semi": false`)
- Single quotes (`"singleQuote": true`)
- 100 char line width (`"printWidth": 100`)

### Component Patterns
- Loading states with v-if: `v-if="isLoading"`
- Error states with separate block: `v-else-if="error"`
- Empty states: `v-else-if="items.length === 0"`
- Lists with `v-for` and `:key`

## Testing
No test framework currently configured. When adding tests:
- Backend: Consider pytest + pytest-asyncio
- Frontend: Consider Vitest + Vue Test Utils

## Common Patterns

### Backend - Database Query Pattern
```python
async def get_novel(session: AsyncSession, novel_id: str) -> Optional[NovelProject]:
    result = await session.scalars(
        select(NovelProject).where(NovelProject.id == novel_id)
    )
    return result.first()
```

### Frontend - API Call Pattern
```typescript
static async getNovel(projectId: string): Promise<NovelProject> {
  return request(`${NOVELS_BASE}/${projectId}`)
}
```

### Backend - Error Response Pattern
```python
if not item:
    logger.warning("Item not found: %s", item_id)
    raise HTTPException(status_code=404, detail="Item not found")
```

### Frontend - Store Action Pattern
```typescript
async fetchUser() {
  try {
    const response = await fetchWithAuth(`${API_URL}/users/me`)
    this.user = await response.json()
  } catch (error) {
    this.logout()
  }
}
```
