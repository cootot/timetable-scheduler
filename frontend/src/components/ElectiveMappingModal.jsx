import React, { useState, useEffect } from 'react';
import { schedulerAPI } from '../services/api';

export default function ElectiveMappingModal({ isOpen, onClose, scheduleId }) {
    const [loading, setLoading] = useState(false);
    const [electiveEntries, setElectiveEntries] = useState([]);

    useEffect(() => {
        if (isOpen && scheduleId) {
            fetchElectiveData();
        }
    }, [isOpen, scheduleId]);

    const fetchElectiveData = async () => {
        setLoading(true);
        try {
            // Get the entire timetable without filters
            const response = await schedulerAPI.getTimetable(scheduleId);
            const rawTimetable = response.data;

            const electives = [];

            // Traverse the Dictionaries: Day -> Slot -> Array of entries
            Object.keys(rawTimetable).forEach(day => {
                const slotsForDay = rawTimetable[day];
                Object.keys(slotsForDay).forEach(slotNum => {
                    const entries = slotsForDay[slotNum];
                    entries.forEach(entry => {
                        if (entry.is_elective) {
                            electives.push({
                                ...entry,
                                day,
                                slotNum
                            });
                        }
                    });
                });
            });

            // Group by Elective Type / Group for easier reading
            const grouped = {};
            electives.forEach(e => {
                const groupName = e.elective_type || e.elective_group || 'Other Elective';
                if (!grouped[groupName]) {
                    grouped[groupName] = [];
                }
                grouped[groupName].push(e);
            });

            setElectiveEntries(grouped);
        } catch (error) {
            console.error('Error fetching elective timetable data:', error);
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(4px)',
            WebkitBackdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000,
            animation: 'fadeIn 0.25s ease-out',
        }}>
            <div style={{
                background: 'var(--card-bg)',
                border: '1px solid var(--card-border)',
                borderRadius: 'var(--radius-lg)',
                boxShadow: 'var(--shadow-xl)',
                width: '90%',
                maxWidth: '850px',
                maxHeight: '85vh',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden'
            }}>
                <div style={{
                    padding: '1.25rem 1.75rem',
                    borderBottom: '1px solid var(--card-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: 'var(--bg-tertiary)'
                }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                        ✨ Elective Handlers & Slots
                    </h3>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'transparent', border: 'none', cursor: 'pointer',
                            fontSize: '1.5rem', color: 'var(--text-muted)', display: 'flex'
                        }}
                    >
                        ×
                    </button>
                </div>

                <div style={{ padding: '1.5rem 1.75rem', overflowY: 'auto', flex: 1 }}>
                    {loading ? (
                        <div className="loading" style={{ margin: '3rem 0' }}>
                            <div className="spinner"></div>
                            <p>Loading elective mappings...</p>
                        </div>
                    ) : Object.keys(electiveEntries).length === 0 ? (
                        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '3rem 0' }}>
                            <p>No electives scheduled in this timetable.</p>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            {Object.entries(electiveEntries).map(([groupName, entries]) => {
                                const isPE = groupName.includes('PE');
                                const isFE = groupName.includes('FE') || groupName.includes('FREE');
                                const headerColor = isPE ? '#f59e0b' : isFE ? '#10b981' : 'var(--primary)';

                                return (
                                    <div key={groupName} style={{
                                        border: `1px solid var(--border)`,
                                        borderRadius: '0.75rem',
                                        overflow: 'hidden'
                                    }}>
                                        <div style={{
                                            background: `linear-gradient(90deg, ${headerColor}22, transparent)`,
                                            borderBottom: '1px solid var(--border)',
                                            padding: '0.75rem 1.25rem',
                                            fontWeight: 700,
                                            color: headerColor,
                                            fontSize: '1.05rem',
                                            display: 'flex',
                                            justifyContent: 'space-between'
                                        }}>
                                            <span>{groupName}</span>
                                            {isPE && <span className="elective-badge pe-badge">PE</span>}
                                            {isFE && <span className="elective-badge fe-badge">FE</span>}
                                        </div>
                                        <div style={{ padding: '0.5rem' }}>
                                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                                                <thead>
                                                    <tr style={{ color: 'var(--text-muted)', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                                                        <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Faculty</th>
                                                        <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Course</th>
                                                        <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Day & Time</th>
                                                        <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Room</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {entries.map((req, idx) => (
                                                        <tr key={idx} style={{ borderBottom: idx < entries.length - 1 ? '1px solid var(--bg-tertiary)' : 'none' }}>
                                                            <td style={{ padding: '0.5rem 0.75rem', color: 'var(--primary)' }}>
                                                                {req.teacher_name}
                                                            </td>
                                                            <td style={{ padding: '0.5rem 0.75rem' }}>
                                                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>{req.course_code}</span>
                                                                {req.course_name}
                                                            </td>
                                                            <td style={{ padding: '0.5rem 0.75rem' }}>
                                                                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'var(--bg-tertiary)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                                                                    {req.day} • {req.start_time} - {req.end_time}
                                                                </div>
                                                            </td>
                                                            <td style={{ padding: '0.5rem 0.75rem' }}>
                                                                {req.room}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
