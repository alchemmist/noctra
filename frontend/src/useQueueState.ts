import {useEffect, useState} from 'react';
import {fetchState, type QueueState} from './api';

function wsUrl(): string {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${window.location.host}/ws`;
}

/**
 * Live queue state. Subscribes to the backend WebSocket (which pushes a fresh
 * snapshot on every change) and reconnects automatically. Falls back to a one
 * shot REST fetch until the socket is up.
 */
export function useQueueState(): QueueState | null {
    const [state, setState] = useState<QueueState | null>(null);

    useEffect(() => {
        let socket: WebSocket | null = null;
        let reconnect: ReturnType<typeof setTimeout> | undefined;
        let closed = false;

        // Seed immediately so the UI is not blank before the socket connects.
        fetchState()
            .then((s) => setState((prev) => prev ?? s))
            .catch(() => undefined);

        const connect = () => {
            if (closed) return;
            socket = new WebSocket(wsUrl());
            socket.onmessage = (event) => {
                try {
                    setState(JSON.parse(event.data) as QueueState);
                } catch {
                    /* ignore malformed frames */
                }
            };
            socket.onclose = () => {
                if (!closed) reconnect = setTimeout(connect, 1000);
            };
            socket.onerror = () => socket?.close();
        };
        connect();

        return () => {
            closed = true;
            if (reconnect) clearTimeout(reconnect);
            socket?.close();
        };
    }, []);

    return state;
}
