import {useState} from 'react';
import {Button, Icon, TextArea} from '@gravity-ui/uikit';
import {ListUl, Play, Plus, TrashBin} from '@gravity-ui/icons';
import {control, enqueue} from '../api';

interface Message {
    text: string;
    error: boolean;
}

export function CommandBar({running}: {running: boolean}) {
    const [paths, setPaths] = useState('');
    const [message, setMessage] = useState<Message | null>(null);
    const [busy, setBusy] = useState(false);

    const run = async (action: () => Promise<void>) => {
        setBusy(true);
        try {
            await action();
        } catch (err) {
            setMessage({text: err instanceof Error ? err.message : String(err), error: true});
        } finally {
            setBusy(false);
        }
    };

    const onAdd = () =>
        run(async () => {
            const list = paths
                .split('\n')
                .map((line) => line.trim())
                .filter(Boolean);
            if (list.length === 0) {
                setMessage({text: 'Добавьте хотя бы один путь', error: true});
                return;
            }
            const res = await enqueue(list);
            setMessage({
                text: `Добавлено: ${res.added.length} · пропущено: ${res.skipped.length} · не найдено: ${res.missing.length}`,
                error: false,
            });
            setPaths('');
        });

    const onStart = () => run(() => control('start').then(() => undefined));
    const onClear = () =>
        run(() =>
            control('clear').then(() => setMessage({text: 'Очередь очищена', error: false})),
        );

    return (
        <section className="surface command">
            <div className="panel-title">
                <Icon data={ListUl} size={17} />
                Новая очередь
            </div>
            <div className="command-hint">
                Пути к аудиофайлам или папкам — по одному на строку.
            </div>
            <TextArea
                value={paths}
                onUpdate={setPaths}
                minRows={7}
                placeholder={'/path/to/audio.m4a\n/path/to/folder'}
                disabled={busy}
                size="l"
            />
            <div className="command-actions">
                <Button view="action" size="l" onClick={onAdd} loading={busy}>
                    <Icon data={Plus} size={16} />
                    Добавить
                </Button>
                <Button
                    view="outlined-success"
                    size="l"
                    onClick={onStart}
                    disabled={busy || running}
                >
                    <Icon data={Play} size={16} />
                    Старт
                </Button>
                <Button view="outlined-danger" size="l" onClick={onClear} disabled={busy}>
                    <Icon data={TrashBin} size={16} />
                </Button>
            </div>
            {message && (
                <div className={`command-msg ${message.error ? 'command-msg_error' : 'command-msg_ok'}`}>
                    {message.text}
                </div>
            )}
        </section>
    );
}
