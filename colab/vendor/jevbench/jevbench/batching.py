"""Micro-batcher: many concurrent callers, one model, full batches.

Callers `submit(item, size)` and block on the returned future. One worker thread gathers whatever is waiting (up to
`max_wait_s` after the first item), orders it by size so padding stays small, cuts it into batches under both
`max_batch` items and `max_tokens` padded tokens (batch size x longest item), runs `process(items)` once per batch and
hands each caller its own result. This is the usual way to keep a GPU busy when requests arrive one at a time.

`process(items)` must return one result per item, in order. If a batch raises (out of memory, one bad item), it is
split in half and each half is tried again, down to single items; an item that still fails gets that exception and
only that caller sees it. Splitting changes batch composition only: it never swaps in a different answer.
"""
from __future__ import annotations

import collections
import queue
import threading
import time
from concurrent.futures import Future


class MicroBatcher:
    def __init__(self, process, max_batch=32, max_tokens=32768, max_wait_s=0.02, on_batch=None, name="microbatcher"):
        self.process, self.max_batch, self.max_tokens, self.max_wait_s = process, max_batch, max_tokens, max_wait_s
        self.on_batch = on_batch  # optional callback(batch_size, padded_tokens, seconds) for measurement
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, name=name, daemon=True)
        self._t.start()

    def submit(self, item, size=1) -> Future:
        f: Future = Future()
        self._q.put((item, max(1, int(size)), f))
        return f

    def close(self):
        self._stop.set()
        self._q.put(None)
        self._t.join(timeout=5)

    def _gather(self):
        first = self._q.get()
        if first is None:
            return None
        got = [first]
        deadline = time.monotonic() + self.max_wait_s
        while len(got) < self.max_batch * 8:  # take a few batches' worth, then size-sort them
            left = deadline - time.monotonic()
            try:
                nxt = self._q.get(timeout=max(left, 0)) if left > 0 else self._q.get_nowait()
            except queue.Empty:
                break
            if nxt is None:
                self._q.put(None)
                break
            got.append(nxt)
        return got

    def _cut(self, got):
        """Size-sorted greedy cut into batches under max_batch items and max_tokens padded tokens."""
        got = sorted(got, key=lambda x: x[1])
        batches, cur = [], []
        for entry in got:
            n, longest = len(cur) + 1, entry[1]  # sorted ascending, so the newest item is the longest
            if cur and (n > self.max_batch or n * longest > self.max_tokens):
                batches.append(cur)
                cur = []
            cur.append(entry)
        if cur:
            batches.append(cur)
        return batches

    def _run(self, batch):
        t0 = time.perf_counter()
        try:
            out = self.process([b[0] for b in batch])
            if len(out) != len(batch):
                raise RuntimeError(f"process returned {len(out)} results for {len(batch)} items")
        except Exception as e:  # noqa: BLE001 - isolate the failing item(s) rather than fail the whole batch
            if len(batch) == 1:
                batch[0][2].set_exception(e)
                return
            mid = len(batch) // 2
            self._run(batch[:mid])
            self._run(batch[mid:])
            return
        if self.on_batch:
            self.on_batch(len(batch), len(batch) * max(b[1] for b in batch), time.perf_counter() - t0)
        for (_, _, f), r in zip(batch, out):
            f.set_result(r)

    def _loop(self):
        while not self._stop.is_set():
            got = self._gather()
            if got is None:
                break
            for batch in self._cut(got):
                self._run(batch)
