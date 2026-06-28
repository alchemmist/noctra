import {useEffect, useState} from 'react';
import {Button, Select} from '@gravity-ui/uikit';
import {fetchConfig, fetchSettings, updateSettings} from '../api';
import {useI18n} from '../i18n';

export function SettingsPanel() {
    const {t} = useI18n();
    const [models, setModels] = useState<string[]>([]);
    const [languages, setLanguages] = useState<string[]>([]);
    const [allFormats, setAllFormats] = useState<string[]>([]);
    const [model, setModel] = useState('');
    const [language, setLanguage] = useState('');
    const [formats, setFormats] = useState<string[]>([]);
    const [device, setDevice] = useState('');
    const [computeType, setComputeType] = useState('');
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([fetchConfig(), fetchSettings()])
            .then(([config, settings]) => {
                setModels(config.models);
                setLanguages(config.languages);
                setAllFormats(config.formats);
                setModel(settings.model);
                setLanguage(settings.language);
                setFormats(settings.formats);
                setDevice(settings.device);
                setComputeType(settings.compute_type);
            })
            .catch(() => undefined);
    }, []);

    const onSave = async () => {
        setBusy(true);
        setMessage(null);
        try {
            await updateSettings({model, language, formats});
            setMessage(t('settings.saved'));
        } catch (err) {
            setMessage(err instanceof Error ? err.message : String(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <section className="surface settings">
            <div className="panel-title">{t('settings.title')}</div>
            <div className="command-hint">{t('settings.hint')}</div>

            <div className="settings-grid">
                <label className="settings-field">
                    <span className="command-model__label">{t('command.model')}</span>
                    <Select
                        value={model ? [model] : []}
                        onUpdate={(v) => setModel(v[0] ?? '')}
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
                </label>

                <label className="settings-field">
                    <span className="command-model__label">{t('command.language')}</span>
                    <Select
                        value={language ? [language] : []}
                        onUpdate={(v) => setLanguage(v[0] ?? '')}
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
                </label>

                <label className="settings-field">
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
                </label>
            </div>

            <div className="settings-readonly">
                <div>
                    <span className="command-model__label">{t('settings.device')}</span>
                    <code>{device}</code>
                </div>
                <div>
                    <span className="command-model__label">{t('settings.computeType')}</span>
                    <code>{computeType}</code>
                </div>
                <div className="command-hint">{t('settings.readonly')}</div>
            </div>

            <div className="command-actions">
                <Button view="action" size="l" onClick={onSave} loading={busy}>
                    {t('settings.save')}
                </Button>
            </div>
            {message && <div className="command-msg command-msg_ok">{message}</div>}
        </section>
    );
}
