import {Card, Text} from '@gravity-ui/uikit';
import type {Job} from '../api';
import {JobCard} from './JobCard';

export function JobList({jobs}: {jobs: Job[]}) {
    if (jobs.length === 0) {
        return (
            <Card view="outlined" spacing={{p: 5}}>
                <Text color="secondary">Очередь пуста — добавьте файлы слева.</Text>
            </Card>
        );
    }

    return (
        <div className="job-list">
            {jobs.map((job, index) => (
                <JobCard key={job.id} job={job} index={index} />
            ))}
        </div>
    );
}
