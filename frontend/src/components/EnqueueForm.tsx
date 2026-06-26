import {useState} from 'react';
import {Button, Card, Flex, Text, TextArea} from '@gravity-ui/uikit';
import {control, enqueue} from '../api';

interface Message {
    text: string;
    error: boolean;
}

export function EnqueueForm({running}: {running: boolean}) {
    const [paths, setPaths] = useState('');
    const [message, setMessage] = useState<Message | null>(null);
    const [busy, setBusy] = useState(false);

    const run = async (action: () => Promise<void>) => {
        setBusy(true);
        try {
            await action();
        } catch (err) {
            setMessage({text: String(err instanceof Error ? err.message : err), error: true});
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
                text: `Добавлено: ${res.added.length}, пропущено: ${res.skipped.length}, не найдено: ${res.missing.length}`,
                error: false,
            });
            setPaths('');
        });

    const onStart = () => run(() => control('start').then(() => undefined));
    const onClear = () =>
        run(() =>
            control('clear').then(() => {
                setMessage({text: 'Очередь очищена', error: false});
            }),
        );

    return (
        <Card view="outlined" spacing={{p: 4}}>
            <Flex direction="column" gap={3}>
                <Text variant="subheader-2">Новая очередь</Text>
                <Text color="secondary">
                    Пути к аудиофайлам или папкам — по одному на строку.
                </Text>
                <TextArea
                    value={paths}
                    onUpdate={setPaths}
                    minRows={6}
                    placeholder={'/path/to/audio.m4a\n/path/to/folder'}
                    disabled={busy}
                />
                <Flex gap={2} wrap>
                    <Button view="action" size="l" onClick={onAdd} loading={busy}>
                        Добавить
                    </Button>
                    <Button
                        view="outlined-success"
                        size="l"
                        onClick={onStart}
                        disabled={busy || running}
                    >
                        Старт
                    </Button>
                    <Button view="outlined-danger" size="l" onClick={onClear} disabled={busy}>
                        Очистить всё
                    </Button>
                </Flex>
                {message && (
                    <Text color={message.error ? 'danger' : 'positive'}>{message.text}</Text>
                )}
            </Flex>
        </Card>
    );
}
