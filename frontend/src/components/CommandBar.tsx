import {useEffect, useState} from 'react';
import {Button, Icon, Select, TextArea} from '@gravity-ui/uikit';
import {ListUl, Play, Plus, TrashBin} from '@gravity-ui/icons';
import {control, enqueue, fetchConfig} from '../api';
import {useI18n} from '../i18n';

interface Message {
    text: string;
    error: boolean;
}

export function CommandBar({running}: {running: boolean}) {
    const {t} = useI18n();
    const [paths, setPaths] = useState('');
    const [message, setMessage] = useState<Message | null>(null);
    const [busy, setBusy] = useState(false);
    const [models, setModels] = useState<string[]>([]);
    const [model, setModel] = useState<string>('');
    const [allFormats, setAllFormats] = useState<string[]>([]);
    const [formats, setFormats] = useState<string[]>([]);

    useEffect(() => {
        fetchConfig()
            .then((config) => {
                setModels(config.models);
                setModel(config.default_model);
                setAllFormats(config.formats);
                setFormats(config.default_formats);
            })
            .catch(() => undefined);
    }, []);

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
                setMessage({text: t('command.needPath'), error: true});
                return;
            }
            const res = await enqueue(list, model || undefined, formats);
            setMessage({
                text: t('command.added', {
                    added: res.added.length,
                    skipped: res.skipped.length,
                    missing: res.missing.length,
                }),
                error: false,
            });
            setPaths('');
        });

    const onStart = () => run(() => control('start').then(() => undefined));
    const onClear = () =>
        run(() =>
            control('clear').then(() => setMessage({text: t('command.cleared'), error: false})),
        );

    return (
        <section className="surface command">
            <div className="panel-title">
                <Icon data={ListUl} size={17} />
                {t('command.title')}
            </div>
            <div className="command-hint">{t('command.hint')}</div>
            <TextArea
                value={paths}
                onUpdate={setPaths}
                minRows={7}
                placeholder={'/path/to/audio.m4a\n/path/to/folder'}
                disabled={busy}
                size="l"
            />
            <div className="command-model">
                <span className="command-model__label">{t('command.model')}</span>
                <Select
                    value={model ? [model] : []}
                    onUpdate={(values) => setModel(values[0] ?? '')}
                    disabled={busy || models.length === 0}
                    size="l"
                    width="max"
                >
                    {models.map((name) => (
                        <Select.Option key={name} value={name}>
                            {name}
                        </Select.Option>
                    ))}
                </Select>
            </div>
            <div className="command-model">
                <span className="command-model__label">{t('command.formats')}</span>
                <Select
                    multiple
                    value={formats}
                    onUpdate={setFormats}
                    disabled={busy || allFormats.length === 0}
                    size="l"
                    width="max"
                >
                    {allFormats.map((name) => (
                        <Select.Option key={name} value={name}>
                            {name}
                        </Select.Option>
                    ))}
                </Select>
            </div>
            <div className="command-actions">
                <Button view="action" size="l" onClick={onAdd} loading={busy}>
                    <Icon data={Plus} size={16} />
                    {t('command.add')}
                </Button>
                <Button
                    view="outlined-success"
                    size="l"
                    onClick={onStart}
                    disabled={busy || running}
                >
                    <Icon data={Play} size={16} />
                    {t('command.start')}
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
