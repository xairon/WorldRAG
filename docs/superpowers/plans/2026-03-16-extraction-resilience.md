# Extraction Resilience: 429 Handling, Error UI, Ollama Fallback

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Gemini returns 429 (quota exhausted), stop the extraction pipeline, show the error in the UI with a "Retry with Ollama" button, and resume from the last failed chapter.

**Architecture:** Add a `QuotaExhaustedError` exception that bubbles up from retry logic through the worker to SSE. The worker publishes an `"error"` SSE event and stops. The frontend shows the error and offers retry with `provider=ollama`. The extract route accepts an optional `provider` param that overrides the config's LLM spec throughout the extraction chain.

**Tech Stack:** Python (FastAPI, arq, tenacity), TypeScript (React 19, Zustand, SSE), Redis pub/sub

---

## Chunk 1: Backend — Quota Error Detection & Pipeline Stop

### Task 1: Add `QuotaExhaustedError` exception

**Files:**
- Modify: `backend/app/core/exceptions.py`

- [ ] **Step 1: Add the exception class**

Add to `backend/app/core/exceptions.py`:

```python
class QuotaExhaustedError(Exception):
    """Raised when an LLM provider returns 429 after all retries."""

    def __init__(self, provider: str, message: str = ""):
        self.provider = provider
        self.message = message or f"{provider} quota exhausted (429)"
        super().__init__(self.message)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/exceptions.py
git commit -m "feat: add QuotaExhaustedError exception"
```

---

### Task 2: Raise `QuotaExhaustedError` from retry logic

**Files:**
- Modify: `backend/app/services/extraction/retry.py`

The current retry logic catches 429 as transient and retries 3 times. After exhausting retries, the generic `RetryError` propagates. We need to catch that and raise `QuotaExhaustedError` instead.

- [ ] **Step 1: Wrap the retry call to detect quota exhaustion**

In `backend/app/services/extraction/retry.py`, modify the `extract_with_retry` function. After the tenacity-decorated inner function, catch `RetryError` and check if the last attempt was a 429:

```python
from app.core.exceptions import QuotaExhaustedError

# Inside extract_with_retry, wrap the call to _extract_inner:
try:
    return await _extract_inner()
except RetryError as retry_err:
    last_exc = retry_err.last_attempt.exception()
    if last_exc and _is_quota_error(last_exc):
        raise QuotaExhaustedError(
            provider=model_id.split("/")[0] if "/" in model_id else model_id,
            message=str(last_exc),
        ) from last_exc
    raise
```

Also add a helper `_is_quota_error` near the existing `_is_transient` function:

```python
def _is_quota_error(exc: BaseException) -> bool:
    """Check if the exception is specifically a 429 quota error."""
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg or "quota" in msg
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/extraction/retry.py
git commit -m "feat: raise QuotaExhaustedError after 429 retry exhaustion"
```

---

### Task 3: Worker catches `QuotaExhaustedError`, publishes error SSE, and stops

**Files:**
- Modify: `backend/app/workers/tasks.py`

Both `process_book_extraction` (v1) and `process_book_extraction_v3` need this. Focus on v3 since that's the default pipeline (`use_v3_pipeline=True`), but also fix v1 for completeness.

- [ ] **Step 1: Add `QuotaExhaustedError` handling in v3 worker (sequential loop)**

In `process_book_extraction_v3`, the chapter loop (line ~275) already catches `CostCeilingError` and `Exception`. Add `QuotaExhaustedError` as a specific catch BEFORE the generic `Exception`:

```python
from app.core.exceptions import QuotaExhaustedError

# In the chapter loop, add before `except Exception as exc:`
except QuotaExhaustedError as qe:
    logger.warning(
        "v3_quota_exhausted",
        book_id=book_id,
        chapter=chapter.number,
        provider=qe.provider,
        chapters_processed=len(chapter_stats),
    )
    failed_chapters.append(chapter.number)
    # Publish error event to SSE
    await _publish_progress(
        chapter.number,
        len(content_chapters),
        "error_quota",
        total_entities,
    )
    # Update book status with resume info
    await book_repo.update_book_status(book_id, "error_quota")
    # Return early — do NOT continue to next chapters
    return {
        "chapters_processed": len(chapter_stats),
        "chapters_failed": len(failed_chapters),
        "total_entities": total_entities,
        "stopped_reason": "quota_exhausted",
        "stopped_at_chapter": chapter.number,
        "provider": qe.provider,
    }
```

- [ ] **Step 2: Same for v1 worker**

In `process_book_extraction`, the error handling is inside `build_book_graph` (parallel). We need to propagate `QuotaExhaustedError` out of the semaphore loop. In `backend/app/services/graph_builder.py`, in `build_book_graph`'s `_process_one` inner function:

```python
from app.core.exceptions import QuotaExhaustedError

# In _process_one, re-raise QuotaExhaustedError instead of returning it:
async def _process_one(ch):
    async with sem:
        try:
            stats = await build_chapter_graph(...)
            if on_chapter_done:
                await on_chapter_done(ch.number, total_chapters, "extracted", stats["total_entities"])
            return (ch.number, stats, None)
        except QuotaExhaustedError:
            raise  # Let it propagate — don't catch in DLQ
        except Exception as exc:
            if on_chapter_done:
                await on_chapter_done(ch.number, total_chapters, "failed", 0)
            return (ch.number, None, exc)
```

Then in `process_book_extraction` (tasks.py), catch `QuotaExhaustedError`:

```python
try:
    result = await build_book_graph(...)
except QuotaExhaustedError as qe:
    # Publish error event
    await _publish_progress(0, 0, "error_quota", 0)
    await book_repo.update_book_status(book_id, "error_quota")
    return {
        "chapters_processed": 0,
        "chapters_failed": 1,
        "total_entities": 0,
        "stopped_reason": "quota_exhausted",
        "provider": qe.provider,
    }
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/services/graph_builder.py
git commit -m "feat: stop extraction pipeline on quota exhaustion, publish error SSE"
```

---

### Task 4: SSE stream handles `error` events

**Files:**
- Modify: `backend/app/api/routes/stream.py`

- [ ] **Step 1: Add error event handling in the SSE generator**

In `stream_extraction_progress`, inside the `while True` loop, after the `"started"` check:

```python
# After the started check (line ~62), add:
if status == "error_quota":
    yield {
        "event": "error",
        "data": json.dumps({
            **data,
            "error_type": "quota_exhausted",
            "chapters_done": chapters_done,
        }),
    }
    break  # Stop streaming — pipeline is stopped
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/routes/stream.py
git commit -m "feat: SSE stream emits error event on quota exhaustion"
```

---

## Chunk 2: Backend — Provider Override & Resume

### Task 5: Add `provider` param to extract routes and schemas

**Files:**
- Modify: `backend/app/schemas/pipeline.py`
- Modify: `backend/app/api/routes/books.py`

- [ ] **Step 1: Add `provider` field to extraction request schemas**

In `backend/app/schemas/pipeline.py`:

```python
class ExtractionRequest(BaseModel):
    """Request body for POST /books/{id}/extract."""
    chapters: list[int] | None = Field(None, description="Chapter numbers to extract. null = all chapters.")
    provider: str | None = Field(None, description="LLM provider override: 'gemini', 'local' (ollama). null = use config default.")

class ExtractionRequestV3(BaseModel):
    """Request body for POST /books/{id}/extract/v3."""
    chapters: list[int] | None = Field(None, description="Chapter numbers to extract. null = all chapters.")
    language: str = Field("fr", description="Source language of the book text.")
    series_name: str | None = Field(None, description="Override series name for this extraction.")
    genre: str | None = Field(None, description="Override genre for this extraction.")
    provider: str | None = Field(None, description="LLM provider override: 'gemini', 'local' (ollama). null = use config default.")
```

- [ ] **Step 2: Pass provider to enqueue_job in both extract routes**

In `backend/app/api/routes/books.py`, `extract_book` (v1 route, line ~369):

```python
provider = body.provider if body else None

job = await arq_pool.enqueue_job(
    "process_book_extraction",
    book_id,
    book.get("genre", "litrpg"),
    book.get("series_name", "") or "",
    chapter_list,
    provider,  # NEW positional arg
    _queue_name="worldrag:arq",
    _job_id=f"extract:{book_id}{suffix}",
)
```

Same for `extract_book_v3` (line ~463):

```python
provider = body.provider if body else None

job = await arq_pool.enqueue_job(
    "process_book_extraction_v3",
    book_id,
    genre,
    series_name,
    chapter_list,
    language,
    provider,  # NEW positional arg
    _queue_name="worldrag:arq",
    _job_id=f"extract-v3:{book_id}{suffix}",
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/pipeline.py backend/app/api/routes/books.py
git commit -m "feat: add provider param to extraction routes"
```

---

### Task 6: Worker and graph builder use provider override

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/services/graph_builder.py`
- Modify: `backend/app/services/extraction/retry.py`

- [ ] **Step 1: Add `provider` to worker task signatures**

In `tasks.py`, update `process_book_extraction`:

```python
async def process_book_extraction(
    ctx: dict[str, Any],
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    chapters: list[int] | None = None,
    provider: str | None = None,  # NEW
) -> dict[str, Any]:
```

And `process_book_extraction_v3`:

```python
async def process_book_extraction_v3(
    ctx: dict[str, Any],
    book_id: str,
    genre: str = "litrpg",
    series_name: str = "",
    chapters: list[int] | None = None,
    language: str = "fr",
    provider: str | None = None,  # NEW
) -> dict[str, Any]:
```

- [ ] **Step 2: Pass provider through to graph builder**

In `process_book_extraction` (v1), pass to `build_book_graph`:

```python
result = await build_book_graph(
    ...,
    provider=provider,  # NEW
)
```

In `process_book_extraction_v3`, pass to `build_chapter_graph_v3`:

```python
stats = await build_chapter_graph_v3(
    ...,
    provider=provider,  # NEW
)
```

- [ ] **Step 3: Add `provider` param to graph builder functions**

In `backend/app/services/graph_builder.py`:

`build_book_graph`:
```python
async def build_book_graph(
    ...,
    on_chapter_done: ProgressCallback | None = None,
    provider: str | None = None,  # NEW
) -> dict[str, Any]:
```

Pass to `build_chapter_graph`:
```python
stats = await build_chapter_graph(
    ...,
    provider=provider,
)
```

`build_chapter_graph`:
```python
async def build_chapter_graph(
    ...,
    series_entities: list[dict[str, Any]] | None = None,
    provider: str | None = None,  # NEW
) -> dict[str, Any]:
```

`build_chapter_graph_v3`:
```python
async def build_chapter_graph_v3(
    ...,
    source_language: str = "fr",
    provider: str | None = None,  # NEW
) -> dict[str, Any]:
```

- [ ] **Step 4: Resolve provider to model spec and pass to extraction**

In `build_chapter_graph` and `build_chapter_graph_v3`, resolve the provider to a LangExtract model ID. Add near the top of each function:

```python
from app.config import settings

# Resolve LLM model for extraction
if provider == "local":
    model_id = settings.llm_auxiliary  # "local:Qwen/Qwen3.5-4B"
elif provider:
    model_id = f"{provider}:{settings.langextract_model}"
else:
    model_id = None  # use default from config
```

Then pass `model_id` to `extract_chapter()` / `extract_chapter_v3()` calls. This requires checking how those functions accept a model override — they use `settings.langextract_model` internally. The simplest approach: if `provider` is set, temporarily override the model in the call.

Check `extract_chapter_v3` signature and add `model_override` param if needed. If it uses `extract_with_retry` which already accepts `model_id`, thread it through.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/services/graph_builder.py
git commit -m "feat: thread provider override through extraction pipeline"
```

---

### Task 7: Allow extraction resume from failed chapter

**Files:**
- Modify: `backend/app/api/routes/books.py`

- [ ] **Step 1: When book status is `error_quota`, auto-detect resume chapters**

In `extract_book` and `extract_book_v3`, expand the allowed statuses to include `"error_quota"`:

```python
if current_status not in ("completed", "extracted", "partial", "embedded", "error_quota"):
    raise ConflictError(...)
```

When status is `"error_quota"` and no explicit chapters are provided, auto-detect which chapters still need extraction by querying Neo4j for chapters with status != "extracted":

```python
if current_status == "error_quota" and chapter_list is None:
    # Resume: only extract chapters that aren't already done
    chapter_list = [
        ch["number"] for ch in chapters
        if ch.get("status") != "extracted"
    ]
    logger.info("extraction_resuming", book_id=book_id, remaining_chapters=len(chapter_list))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/routes/books.py
git commit -m "feat: auto-resume extraction from failed chapter on error_quota"
```

---

## Chunk 3: Frontend — Error Display & Ollama Retry

### Task 8: Update extraction store with error_quota state

**Files:**
- Modify: `frontend/stores/extraction-store.ts`

- [ ] **Step 1: Add error_quota status and error details to store**

```typescript
interface ExtractionState {
  status: "idle" | "running" | "done" | "error" | "error_quota"
  chaptersTotal: number
  chaptersDone: number
  entitiesFound: number
  feedMessages: FeedMessage[]
  errorDetail: { type: string; provider: string; message: string } | null  // NEW
  addFeedMessage: (msg: FeedMessage) => void
  setProgress: (data: { chaptersTotal?: number; chaptersDone?: number; entitiesFound?: number }) => void
  setStatus: (status: ExtractionState["status"]) => void
  setErrorDetail: (detail: ExtractionState["errorDetail"]) => void  // NEW
  reset: () => void
}
```

Add `errorDetail: null` to initial state, `setErrorDetail` implementation, and reset `errorDetail` in `reset()`.

- [ ] **Step 2: Commit**

```bash
git add frontend/stores/extraction-store.ts
git commit -m "feat: add error_quota status and errorDetail to extraction store"
```

---

### Task 9: SSE hook listens for error events

**Files:**
- Modify: `frontend/hooks/use-extraction-stream.ts`

- [ ] **Step 1: Add error event listener**

After the existing `addEventListener("done", ...)`:

```typescript
es.addEventListener("error", (event) => {
  try {
    const data = JSON.parse((event as MessageEvent).data)
    const s = useExtractionStore.getState()
    s.setErrorDetail({
      type: data.error_type ?? "unknown",
      provider: data.provider ?? "",
      message: data.message ?? "Extraction stopped due to an error",
    })
    s.setProgress({ chaptersDone: data.chapters_done ?? s.chaptersDone })
    s.setStatus("error_quota")
  } catch {}
  es.close()
})
```

Also add `errorDetail` to the return value:

```typescript
const errorDetail = useExtractionStore((s) => s.errorDetail)
return { connect, disconnect, status, feedMessages, chaptersDone, chaptersTotal, entitiesFound, errorDetail }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/hooks/use-extraction-stream.ts
git commit -m "feat: SSE hook handles error events with quota detail"
```

---

### Task 10: Extraction action button handles error_quota state

**Files:**
- Modify: `frontend/components/extraction/extraction-action.tsx`

- [ ] **Step 1: Add error_quota case to the button state machine**

In the status switch, add after the `"error"` case:

```typescript
case "error_quota":
  return (
    <div className="flex items-center gap-3">
      <Button variant="default" onClick={onRetryOllama} disabled={disabled}>
        <RotateCcw className="mr-2 h-4 w-4" />
        Retry with Ollama
      </Button>
      <Button variant="outline" onClick={onStart} disabled={disabled}>
        Retry with Gemini
      </Button>
    </div>
  )
```

Update the props interface:

```typescript
interface ExtractionActionProps {
  bookStatus: string
  hasProfile: boolean
  isFirstBook: boolean
  onStart: () => void
  onCancel: () => void
  onRetryOllama: () => void  // NEW
  disabled?: boolean
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/extraction/extraction-action.tsx
git commit -m "feat: extraction action shows Retry with Ollama on quota error"
```

---

### Task 11: Dashboard shows error banner and wires retry

**Files:**
- Modify: `frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx`

- [ ] **Step 1: Add error banner component and retry handler**

Add an error banner that shows when status is `error_quota`:

```tsx
import { AlertTriangle } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

// Inside ExtractionDashboard, after the useExtractionStream hook:
const handleRetryOllama = useCallback(async () => {
  setStarting(true)
  useExtractionStore.getState().reset()
  connect()
  try {
    await fetch(`/api/books/${bookId}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "local" }),
    })
  } catch {
    disconnect()
  } finally {
    setStarting(false)
  }
}, [bookId, connect, disconnect])

// In the JSX, add the error banner before the chapter table:
{status === "error_quota" && errorDetail && (
  <Alert variant="destructive">
    <AlertTriangle className="h-4 w-4" />
    <AlertTitle>Extraction stopped — {errorDetail.provider} quota exceeded</AlertTitle>
    <AlertDescription>
      {chaptersDone} / {chaptersTotal} chapters extracted before the API quota was hit.
      You can retry with a local Ollama model (lower quality but no quota limits).
    </AlertDescription>
  </Alert>
)}
```

Pass `onRetryOllama` to `ExtractionAction`:

```tsx
<ExtractionAction
  bookStatus={effectiveStatus}
  hasProfile={hasProfile}
  isFirstBook={isFirstBook}
  onStart={handleStart}
  onCancel={handleCancel}
  onRetryOllama={handleRetryOllama}
  disabled={starting}
/>
```

- [ ] **Step 2: Also handle effectiveStatus for error_quota**

Update the status determination:

```typescript
const effectiveStatus = status === "running" || status === "error_quota"
  ? status
  : book.status
```

This ensures `error_quota` from the store takes precedence over the book's stale Neo4j status.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx
git commit -m "feat: extraction dashboard shows error banner with Ollama retry"
```

---

## Chunk 4: Frontend polish — Progress bar & live feed

### Task 12: Add a progress bar to the extraction dashboard

**Files:**
- Modify: `frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx`

- [ ] **Step 1: Add a visual progress bar**

Import shadcn Progress component and render it when extraction is running:

```tsx
import { Progress } from "@/components/ui/progress"

// In JSX, after the title row and before the chapter table:
{(status === "running" || status === "error_quota") && (
  <div className="space-y-2">
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">
        {status === "running" ? "Extracting..." : "Stopped"}
      </span>
      <span className="tabular-nums font-medium">
        {chaptersDone} / {chaptersTotal} chapters
        {entitiesFound > 0 && (
          <span className="ml-2 text-muted-foreground">
            · {entitiesFound} entities
          </span>
        )}
      </span>
    </div>
    <Progress
      value={chaptersTotal > 0 ? (chaptersDone / chaptersTotal) * 100 : 0}
      className={status === "error_quota" ? "[&>div]:bg-destructive" : ""}
    />
  </div>
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx
git commit -m "feat: add progress bar with chapter count to extraction dashboard"
```

---

### Task 13: Publish richer feed messages from worker

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/api/routes/stream.py`
- Modify: `frontend/hooks/use-extraction-stream.ts`
- Modify: `frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx`

- [ ] **Step 1: Add entity breakdown to worker progress messages**

In `process_book_extraction_v3`, when publishing progress after a successful chapter (line ~318), include entity breakdown:

```python
await _publish_progress(
    chapter.number,
    len(content_chapters),
    "extracted",
    stats.get("total_entities", 0),
)
```

The current `_publish_progress` already includes `entities_found`. Extend it to include chapter-level detail by adding a `detail` field:

```python
async def _publish_progress(chapter: int, total: int, status: str, entities: int, detail: dict | None = None) -> None:
    if dlq_redis is not None:
        import json
        payload = {
            "chapter": chapter,
            "total": total,
            "status": status,
            "entities_found": entities,
            "pipeline": "v3",
        }
        if detail:
            payload["detail"] = detail
        await dlq_redis.publish(
            f"worldrag:progress:{book_id}",
            json.dumps(payload),
        )
```

Call with detail after successful chapter:

```python
neo4j_counts = stats.get("neo4j_counts", {})
await _publish_progress(
    chapter.number,
    len(content_chapters),
    "extracted",
    stats.get("total_entities", 0),
    detail={
        "characters": neo4j_counts.get("characters", 0),
        "events": neo4j_counts.get("events", 0),
        "locations": neo4j_counts.get("locations", 0),
        "items": neo4j_counts.get("items", 0),
    },
)
```

- [ ] **Step 2: SSE stream forwards detail and adds feed messages**

In `stream.py`, include `detail` in the progress event data (it's already forwarded via `**data`).

- [ ] **Step 3: Frontend hook processes feed messages**

In `use-extraction-stream.ts`, in the `progress` listener:

```typescript
es.addEventListener("progress", (event) => {
  try {
    const data = JSON.parse((event as MessageEvent).data)
    const s = useExtractionStore.getState()
    s.setProgress({
      chaptersDone: data.chapters_done,
      entitiesFound: data.entities_found ?? s.entitiesFound,
    })
    // Add feed message
    if (data.chapter) {
      const detail = data.detail
      const parts: string[] = []
      if (detail?.characters) parts.push(`${detail.characters} chars`)
      if (detail?.events) parts.push(`${detail.events} events`)
      if (detail?.locations) parts.push(`${detail.locations} locs`)
      if (detail?.items) parts.push(`${detail.items} items`)
      s.addFeedMessage({
        time: new Date().toLocaleTimeString(),
        chapter: data.chapter,
        type: data.status === "extracted" ? "success" : "error",
        name: parts.length > 0 ? parts.join(", ") : data.status,
      })
    }
  } catch {}
})
```

- [ ] **Step 4: Render live feed in dashboard**

In `dashboard.tsx`, render the feed when running:

```tsx
{status === "running" && feedMessages.length > 0 && (
  <div className="rounded-lg border bg-muted/30 p-4">
    <h3 className="mb-3 text-sm font-medium">Live Feed</h3>
    <div className="max-h-48 space-y-1.5 overflow-y-auto font-mono text-xs">
      {feedMessages.slice(-20).map((msg, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-muted-foreground">{msg.time}</span>
          <span className="font-medium">Ch. {msg.chapter}</span>
          <span className={msg.type === "success" ? "text-green-600" : "text-destructive"}>
            {msg.name}
          </span>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/api/routes/stream.py \
  frontend/hooks/use-extraction-stream.ts \
  frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx
git commit -m "feat: live extraction feed with entity breakdown per chapter"
```

---

## Chunk 5: Integration — Wire v3 as default from frontend

### Task 14: Frontend calls v3 extract endpoint

**Files:**
- Modify: `frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx`

The config has `use_v3_pipeline=True` but the frontend calls `/extract` (v1). Switch to v3.

- [ ] **Step 1: Update handleStart and handleRetryOllama to use v3 endpoint**

```typescript
const extractUrl = `/api/books/${bookId}/extract/v3`

const handleStart = useCallback(async () => {
  setStarting(true)
  connect()
  try {
    await fetch(extractUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    })
  } catch {
    disconnect()
  } finally {
    setStarting(false)
  }
}, [bookId, connect, disconnect])

const handleRetryOllama = useCallback(async () => {
  setStarting(true)
  useExtractionStore.getState().reset()
  connect()
  try {
    await fetch(extractUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "local" }),
    })
  } catch {
    disconnect()
  } finally {
    setStarting(false)
  }
}, [bookId, connect, disconnect])
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx
git commit -m "feat: frontend uses v3 extraction endpoint as default"
```

---

### Task 15: Verify end-to-end and clean up

- [ ] **Step 1: Restart containers**

```bash
docker compose restart backend worker
```

- [ ] **Step 2: Verify backend starts clean**

```bash
docker compose logs --tail=10 backend | grep -i error
docker compose logs --tail=10 worker | grep -i error
```

- [ ] **Step 3: Manual test — trigger extraction, observe SSE progress in browser DevTools**

Open browser network tab → filter EventSource → trigger extraction → verify events arrive.

- [ ] **Step 4: Manual test — simulate 429 by setting an invalid Gemini API key temporarily**

Verify the pipeline stops, error banner appears, "Retry with Ollama" button works.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: extraction resilience — 429 detection, error UI, ollama fallback"
```
