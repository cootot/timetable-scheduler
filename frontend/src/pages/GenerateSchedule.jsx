/**
 * Generate Schedule Page
 * 
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 */

import { useState } from 'react';
import { schedulerAPI } from '../services/api';

function GenerateSchedule() {
    const [formData, setFormData] = useState({
        name: '',
        semester: 'even',  // Changed to 'even' - database only has even semester sections
    });
    const [generating, setGenerating] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const pollStatus = async (scheduleId) => {
        const check = async () => {
            try {
                const response = await schedulerAPI.getStatus(scheduleId);
                const { status, quality_score } = response.data;

                if (status === 'COMPLETED' || status === 'FAILED' || status === 'PARTIAL') {
                    setResult({
                        ...response.data,
                        message: (status === 'COMPLETED' || status === 'PARTIAL')
                            ? 'Schedule generation finished successfully!'
                            : 'Schedule generation failed. Please check conflicts.'
                    });
                    setGenerating(false);
                    return true; // Stop polling
                }
                return false; // Continue polling
            } catch (err) {
                setError('Error checking status');
                setGenerating(false);
                return true; // Stop polling on error
            }
        };

        // Initial check immediately
        const finished = await check();
        if (finished) return;

        // Start polling every 2 seconds
        const intervalId = setInterval(async () => {
            const isDone = await check();
            if (isDone) clearInterval(intervalId);
        }, 2000);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setGenerating(true);
        setError(null);
        setResult(null);

        try {
            const response = await schedulerAPI.generate(formData);
            const scheduleId = response.data.schedule_id;

            // Start polling for completion instead of showing immediate success
            await pollStatus(scheduleId);

        } catch (err) {
            console.error('Generate error:', err.response);
            const errData = err.response?.data;
            // DRF can return errors as { error: "..." } or { field: ["msg"] }
            let msg = 'Failed to trigger schedule generation';
            if (errData) {
                if (errData.error) msg = errData.error;
                else if (typeof errData === 'string') msg = errData;
                else msg = JSON.stringify(errData);
            }
            setError(msg);
            setGenerating(false);
        }
    };

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">Generate Schedule</h1>
                <p className="page-description">Create a new timetable schedule for all years</p>
            </div>

            <div className="card">
                <div className="card-header">
                    <h2 className="card-title">Schedule Configuration</h2>
                </div>

                <form onSubmit={handleSubmit}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '500px' }}>
                        <div className="filter-group">
                            <label className="filter-label">Schedule Name</label>
                            <input
                                type="text"
                                className="filter-select"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                placeholder="e.g., Fall 2024 Schedule"
                                required
                            />
                        </div>

                        <div className="filter-group">
                            <label className="filter-label">Semester</label>
                            <select
                                className="filter-select"
                                value={formData.semester}
                                onChange={(e) => setFormData({ ...formData, semester: e.target.value })}
                            >
                                <option value="odd">Odd Semester</option>
                                <option value="even">Even Semester</option>
                            </select>
                            <small style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                                Generates schedules for all 4 years (Year 1-4) automatically
                            </small>
                        </div>

                        <button type="submit" className="btn btn-success" disabled={generating}>
                            {generating ? 'Generating...' : 'Generate Schedule for All Years'}
                        </button>
                    </div>
                </form>

                {generating && (
                    <div className="loading" style={{ marginTop: '2rem' }}>
                        <div className="spinner"></div>
                        <p>Generating schedule... This may take a moment.</p>
                    </div>
                )}

                {error && (
                    <div className="alert alert-error" style={{ marginTop: '1rem' }}>
                        <strong>Error:</strong> {error}
                    </div>
                )}

                {result && (
                    <div className="alert alert-success" style={{ marginTop: '1rem' }}>
                        <h3 style={{ marginBottom: '0.5rem' }}>Schedule Generated Successfully!</h3>
                        <p><strong>Schedule ID:</strong> {result.schedule_id}</p>
                        <p><strong>Status:</strong> {result.status}</p>
                        <p><strong>Message:</strong> {result.message}</p>
                        {result.data?.quality_score && (
                            <p><strong>Quality Score:</strong> {result.data.quality_score.toFixed(2)}/100</p>
                        )}
                        <p style={{ marginTop: '1rem' }}>
                            Go to <a href="/timetable" style={{ color: 'var(--primary)', fontWeight: 600 }}>View Timetable</a> to see the generated schedule.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}

export default GenerateSchedule;
