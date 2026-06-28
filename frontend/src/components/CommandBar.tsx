import {useEffect, useRef, useState} from 'react';
import {Button, Icon, Select, TextArea, useToaster} from '@gravity-ui/uikit';
import {ArrowUpFromSquare, ListUl, Play, Plus, TrashBin} from '@gravity-ui/icons';
import {control, enqueue, fetchConfig, uploadFiles} from '../api';
import {useI18n} from '../i18n';

export function CommandBar({running}: {running: boolean}) {
    const {t} = useI18n();
    const {add} = useToaster();
    const [paths, setPaths] = useState('');
    const [busy, setBusy] = useState(false);
    const [models, setModels] = useState<string[]>([]);
    const [model, setModel] = useState<string>('');
    const [allFormats, setAllFormats] = useState<string[]>([]);
    const [formats, setFormats] = useState<string[]>([]);
    const [languages, setLanguages] = useState<string[]>([]);
    const [language, setLanguage] = useState<string>('');
    const [dragging, setDragging] = useState(false);
    const fileInput = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetchConfig()
            .then((config) => {
                setModels(config.models);
                setModel(config.default_model);
                setAllFormats(config.formats);
                setFormats(config.default_formats);
                setLanguages(config.languages);
                setLanguage(config.default_language);
            })
            .catch(() => undefined);
    }, []);

    const toastOk = (title: string) =>
        add({name: `ok-${Date.now()}`, title, theme: 'success', autoHiding: 4000});
    const toastErr = (title: string) =>
        add({name: `err-${Date.now()}`, title, theme: 'danger', autoHiding: 6000});

    const addedTitle = (res: {added: unknown[]; skipped: unknown[]; missing: unknown[]}) =>
        t('command.added', {
            added: res.added.length,
            skipped: res.skipped.length,
            missing: res.missing.length,
        });

    const run = async (action: () => Promise<void>) => {
        setBusy(true);
        try {
            await action();
        } catch (err) {
            toastErr(err instanceof Error ? err.message : String(err));
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
                toastErr(t('command.needPath'));
                return;
            }
            const res = await enqueue(list, model || undefined, formats, language || undefined);
            toastOk(addedTitle(res));
            setPaths('');
        });

    const uploadList = (fileList: FileList | null) => {
        const list = fileList ? Array.from(fileList) : [];
        if (list.length === 0) {
            return;
        }
        run(async () => {
            const res = await uploadFiles(list, model || undefined, formats, language || undefined);
            toastOk(addedTitle(res));
        });
    };

    const onDrop = (event: React.DragEvent) => {
        event.preventDefault();
        setDragging(false);
        uploadList(event.dataTransfer.files);
    };

    const onStart = () => run(() => control('start').then(() => undefined));
    const onClear = () =>
        run(() => control('clear').then(() => toastOk(t('command.cleared'))));

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
                <span className="command-model__label">{t('command.language')}</span>
                <Select
                    value={language ? [language] : []}
                    onUpdate={(values) => setLanguage(values[0] ?? '')}
                    disabled={busy || languages.length === 0}
                    size="l"
                    width="max"
                    filterable
                >
                    {languages.map((code) => (
                        <Select.Option key={code} value={code}>
                            {code}
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
            <div
                className={`dropzone ${dragging ? 'dropzone_active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => fileInput.current?.click()}
                onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
            >
                <Icon data={ArrowUpFromSquare} size={18} />
                <span>{busy ? t('command.uploading') : t('command.drop')}</span>
            </div>
            <input
                ref={fileInput}
                type="file"
                multiple
                accept="audio/*,video/*,.m4a,.mp3,.wav,.flac,.ogg,.opus,.webm,.mp4,.m4v,.mov,.mkv,.avi"
                hidden
                onChange={(e) => {
                    uploadList(e.target.files);
                    e.target.value = '';
                }}
            />
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
        </section>
    );
}
