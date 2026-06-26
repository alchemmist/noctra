export type JobStatus = 'pending' | 'processing' | 'done' | 'failed' | 'canceled';

export interface Job {
    id: number;
    path: string;
    queue_order: number;
    status: JobStatus;
    text_path: string;
    error: string;
    progress: number;
    duration: number;
    cancel_requested: boolean;
    source_dir: string;
}

export interface QueueState {
    next_id: number;
    running: boolean;
    jobs: Job[];
    pending: number;
    processing: number;
    done: number;
    failed: number;
    canceled: number;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
    const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
        throw new Error(text || `${url} failed (${res.status})`);
    }
    return (text ? JSON.parse(text) : {}) as T;
}

export async function fetchState(): Promise<QueueState> {
    const res = await fetch('/api/state');
    if (!res.ok) {
        throw new Error(`state failed (${res.status})`);
    }
    return res.json();
}

export interface EnqueueResult {
    added: Job[];
    skipped: string[];
    missing: string[];
}

export function enqueue(paths: string[]): Promise<EnqueueResult> {
    return postJson<EnqueueResult>('/api/enqueue', {paths});
}

export function control(action: 'start' | 'clear'): Promise<unknown> {
    return postJson('/api/control', {action});
}
