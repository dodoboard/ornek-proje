import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api/client";
import { makeJob } from "@/test/jobFixture";

import { useJob } from "./useJob";

class FakeEventSource {
  static CLOSED = 2;
  static instances: FakeEventSource[] = [];
  readyState = 1;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, (event: MessageEvent<string>) => void>();

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, listener);
  }
  emit(type: string, data: unknown) {
    this.listeners.get(type)?.(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
  fail() {
    this.readyState = FakeEventSource.CLOSED;
    this.onerror?.();
  }
  close() {
    this.readyState = FakeEventSource.CLOSED;
  }
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useJob", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("streams updates over SSE and closes on a terminal state", () => {
    const { result } = renderHook(() => useJob("JOB_1"), { wrapper });
    const [source] = FakeEventSource.instances;
    expect(source?.url).toBe("http://127.0.0.1:8000/api/jobs/JOB_1/events");

    act(() => source?.emit("job", makeJob({ progress: 60 })));
    expect(result.current.job?.progress).toBe(60);
    expect(result.current.transport).toBe("sse");

    act(() => source?.emit("job", makeJob({ status: "completed", progress: 100 })));
    expect(result.current.job?.status).toBe("completed");
    expect(source?.readyState).toBe(FakeEventSource.CLOSED);
  });

  it("falls back to polling when the stream fails", async () => {
    const get = vi.spyOn(api.jobs, "get").mockResolvedValue(makeJob({ status: "completed", progress: 100 }));
    const { result } = renderHook(() => useJob("JOB_1"), { wrapper });
    act(() => FakeEventSource.instances[0]?.fail());

    await waitFor(() => expect(result.current.transport).toBe("polling"));
    await waitFor(() => expect(result.current.job?.status).toBe("completed"));
    expect(get).toHaveBeenCalledWith("JOB_1");
  });

  it("does nothing without a job id", () => {
    const { result } = renderHook(() => useJob(null), { wrapper });
    expect(result.current.job).toBeNull();
    expect(FakeEventSource.instances).toHaveLength(0);
  });
});
