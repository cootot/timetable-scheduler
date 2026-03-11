/**
 * Analytics Page
 * * Author: Frontend Team (Bhuvanesh, Akshitha)
 */

import { useState, useEffect } from 'react';
import { scheduleAPI, schedulerAPI } from '../services/api';

function Analytics() {
    const [schedules, setSchedules] = useState([]);
    const [selectedSchedule, setSelectedSchedule] = useState('');
    const [workloadData, setWorkloadData] = useState([]);
    const [roomData, setRoomData] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadSchedules();
    }, []);

    const loadSchedules = async () => {
        try {
            const response = await scheduleAPI.getAll();
            setSchedules(response.data.results || []);
        } catch (error) {
            console.error('Error loading schedules:', error);
        }
    };

    const loadAnalytics = async () => {
        if (!selectedSchedule) return;

        setLoading(true);
        try {
            const [workload, rooms] = await Promise.all([
                schedulerAPI.getWorkload(selectedSchedule),
                schedulerAPI.getRoomUtilization(selectedSchedule),
            ]);
            setWorkloadData(workload.data);
            setRoomData(rooms.data);
        } catch (error) {
            console.error('Error loading analytics:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (selectedSchedule) {
            loadAnalytics();
        }
    }, [selectedSchedule]);

    // Reusable styles for the tables
    const tableStyle = { width: '100%', borderCollapse: 'collapse', minWidth: '700px' };
    const thStyle = { padding: '12px 16px', textAlign: 'left', backgroundColor: 'var(--bg-tertiary, #f8fafc)', borderBottom: '2px solid var(--border, #e2e8f0)', fontWeight: '600' };
    const tdStyle = { padding: '12px 16px', borderBottom: '1px solid var(--border, #e2e8f0)', whiteSpace: 'nowrap' };

    // Helper component to safely render the progress bar with fallbacks
    const ProgressBar = ({ utilization }) => {
        const utilValue = Number(utilization) || 0;
        const widthPercent = Math.min(utilValue, 100);
        
        // Default to Success (Green). If >= 75% Warning (Orange). If >= 100% Danger (Red).
        let barColor = 'var(--success, #10b981)'; 
        if (utilValue >= 100) {
            barColor = 'var(--danger, #ef4444)';
        } else if (utilValue >= 75) {
            barColor = 'var(--warning, #f59e0b)';
        }

        return (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{
                    width: '120px',
                    height: '8px',
                    backgroundColor: 'var(--bg-tertiary, #e2e8f0)',
                    borderRadius: '4px',
                    overflow: 'hidden',
                    flexShrink: 0
                }}>
                    <div style={{
                        width: `${widthPercent}%`,
                        height: '100%',
                        backgroundColor: barColor,
                        transition: 'width 0.3s ease'
                    }}></div>
                </div>
                <span style={{ 
                    fontWeight: utilValue >= 100 ? '700' : '500', 
                    minWidth: '45px',
                    color: utilValue >= 100 ? barColor : 'inherit'
                }}>
                    {utilValue}%
                </span>
            </div>
        );
    };

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">Analytics</h1>
                <p className="page-description">Workload and utilization analytics</p>
            </div>

            {/* Schedule Selection */}
            <div className="card">
                <div className="filter-group">
                    <label className="filter-label">Select Schedule</label>
                    <select
                        className="filter-select"
                        value={selectedSchedule}
                        onChange={(e) => setSelectedSchedule(e.target.value)}
                    >
                        <option value="">-- Select Schedule --</option>
                        {schedules.map((schedule) => (
                            <option key={schedule.schedule_id} value={schedule.schedule_id}>
                                {schedule.name} ({schedule.year ? `Year ${schedule.year}` : 'All Years'}, {schedule.semester})
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {loading && (
                <div className="loading">
                    <div className="spinner"></div>
                    <p>Loading analytics...</p>
                </div>
            )}

            {!loading && workloadData.length > 0 && (
                <>
                    {/* Faculty Workload */}
                    <div className="card">
                        <div className="card-header">
                            <h2 className="card-title">Faculty Workload Distribution</h2>
                        </div>
                        
                        <div style={{ overflowX: 'auto', width: '100%', borderRadius: '8px' }}>
                            <table className="data-table" style={tableStyle}>
                                <thead>
                                    <tr>
                                        <th style={thStyle}>Teacher ID</th>
                                        <th style={thStyle}>Teacher Name</th>
                                        <th style={thStyle}>Assigned Hours</th>
                                        <th style={thStyle}>Max Hours</th>
                                        <th style={thStyle}>Utilization</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {workloadData.map((item) => (
                                        <tr key={item.teacher_id}>
                                            <td style={tdStyle}>{item.teacher_id}</td>
                                            <td style={tdStyle}>{item.teacher_name}</td>
                                            <td style={tdStyle}>{item.total_hours}</td>
                                            <td style={tdStyle}>{item.max_hours}</td>
                                            <td style={tdStyle}>
                                                <ProgressBar utilization={item.utilization} />
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Room Utilization */}
                    <div className="card">
                        <div className="card-header">
                            <h2 className="card-title">Room Utilization</h2>
                        </div>
                        
                        <div style={{ overflowX: 'auto', width: '100%', borderRadius: '8px' }}>
                            <table className="data-table" style={tableStyle}>
                                <thead>
                                    <tr>
                                        <th style={thStyle}>Room ID</th>
                                        <th style={thStyle}>Room Type</th>
                                        <th style={thStyle}>Slots Used</th>
                                        <th style={thStyle}>Utilization</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {roomData.map((item) => (
                                        <tr key={item.room_id}>
                                            <td style={tdStyle}>{item.room_id}</td>
                                            <td style={tdStyle}>{item.room_type}</td>
                                            <td style={tdStyle}>{item.total_slots_used} / 40</td>
                                            <td style={tdStyle}>
                                                <ProgressBar utilization={item.utilization} />
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {!selectedSchedule && (
                <div className="alert alert-info">
                    Please select a schedule to view analytics.
                </div>
            )}
        </div>
    );
}

export default Analytics;