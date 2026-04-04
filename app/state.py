import asyncio

# Keyed by scan_run_id. Pipeline writes lines; SSE endpoint reads.
# None sentinel signals end of stream.
scan_queues: dict[int, asyncio.Queue[str | None]] = {}
