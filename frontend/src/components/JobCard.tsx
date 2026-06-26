import {Card, Flex, Label, Progress, Text} from '@gravity-ui/uikit';
import type {Job, JobStatus} from '../api';

type LabelTheme = 'unknown' | 'info' | 'success' | 'danger' | 'warning';

const STATUS: Record<JobStatus, {text: string; theme: LabelTheme}> = {
    pending: {text: 'в очереди', theme: 'unknown'},
    processing: {text: 'идёт', theme: 'info'},
    done: {text: 'готово', theme: 'success'},
    failed: {text: 'ошибка', theme: 'danger'},
    canceled: {text: 'отменено', theme: 'warning'},
};

export function JobCard({job, index}: {job: Job; index: number}) {
    const status = STATUS[job.status];
    const percent = Math.round(job.progress * 100);

    return (
        <Card view="outlined" spacing={{p: 3}}>
            <Flex direction="column" gap={2}>
                <Flex justifyContent="space-between" alignItems="center" gap={2}>
                    <Text variant="subheader-2">#{index + 1}</Text>
                    <Label theme={status.theme} size="m">
                        {status.text}
                    </Label>
                </Flex>

                <Text className="job-path">{job.path}</Text>

                {job.status === 'processing' && <Progress value={percent} text={`${percent}%`} />}

                {job.status === 'done' && (
                    <Text color="secondary">
                        → {job.text_path}
                        {job.duration ? ` · ${Math.round(job.duration)} с` : ''}
                    </Text>
                )}

                {job.status === 'failed' && job.error && (
                    <Text color="danger">{job.error}</Text>
                )}
            </Flex>
        </Card>
    );
}
