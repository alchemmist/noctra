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
    model: string;
    formats: string;
    language: string;
}

export interface Config {
    models: string[];
    default_model: string;
    formats: string[];
    default_formats: string[];
    languages: string[];
    default_language: string;
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

export async function fetchConfig(): Promise<Config> {
    const res = await fetch('/api/config');
    if (!res.ok) {
        throw new Error(`config failed (${res.status})`);
    }
    return res.json();
}

export function enqueue(
    paths: string[],
    model?: string,
    formats?: string[],
    language?: string,
): Promise<EnqueueResult> {
    const body: {paths: string[]; model?: string; formats?: string[]; language?: string} = {paths};
    if (model) {
        body.model = model;
    }
    if (formats && formats.length > 0) {
        body.formats = formats;
    }
    if (language) {
        body.language = language;
    }
    return postJson<EnqueueResult>('/api/enqueue', body);
}

export function control(action: 'start' | 'clear'): Promise<unknown> {
    return postJson('/api/control', {action});
}

export async function uploadFiles(
    files: File[],
    model?: string,
    formats?: string[],
    language?: string,
): Promise<EnqueueResult> {
    const form = new FormData();
    for (const file of files) {
        form.append('files', file);
    }
    if (model) {
        form.append('model', model);
    }
    if (formats && formats.length > 0) {
        form.append('formats', formats.join(','));
    }
    if (language) {
        form.append('language', language);
    }
    const res = await fetch('/api/upload', {method: 'POST', body: form});
    const text = await res.text();
    if (!res.ok) {
        throw new Error(text || `upload failed (${res.status})`);
    }
    return (text ? JSON.parse(text) : {}) as EnqueueResult;
}

export type JobAction = 'cancel' | 'retry' | 'delete';

export function jobControl(id: number, action: JobAction): Promise<unknown> {
    return postJson('/api/job', {id, action});
}
