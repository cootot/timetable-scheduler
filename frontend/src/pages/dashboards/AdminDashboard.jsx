/**
 * Admin Dashboard Component
 * =========================
 * 
 * Provides a high-level overview of the entire system for Administrators.
 * Includes aggregate statistics (total teachers, courses, etc.) and quick 
 * links to management sections. 
 * Also contains the critical "End Semester Rollover" functionality.
 * 
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 * Sprint: 1
 */

// Import React hooks and Router components
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

// Import centralized API service functions to talk to the Django backend
import { scheduleAPI, teacherAPI, courseAPI, roomAPI, sectionAPI, systemAPI } from '../../services/api';

function AdminDashboard() {
    // ---------------------------------------------------------
    // STATE MANAGEMENT
    // ---------------------------------------------------------
    
    // State to hold the numerical counts for the top overview cards
    const [stats, setStats] = useState({
        teachers: 0,
        courses: 0,
        rooms: 0,
        sections: 0,
        schedules: 0,
    });
    
    // Loading state for the initial data fetch
    const [loading, setLoading] = useState(true);
    
    // State variables managing the dangerous "Reset Semester" modal
    const [showResetModal, setShowResetModal] = useState(false);
    const [confirmText, setConfirmText] = useState('');     // User must type "CONFIRM"
    const [resetting, setResetting] = useState(false);      // Network loading state for the reset action

    // ---------------------------------------------------------
    // EFFECTS & DATA FETCHING
    // ---------------------------------------------------------

    // useEffect is triggered once when the component first mounts (empty dependency array [])
    useEffect(() => {
        loadStats();
    }, []);

    /**
     * Fetches all necessary counting statistics concurrently.
     */
    const loadStats = async () => {
        try {
            // Promise.all fires all 5 network requests simultaneously to save time
            const [teachers, courses, rooms, sections, schedules] = await Promise.all([
                teacherAPI.getAll(),
                courseAPI.getAll(),
                roomAPI.getAll(),
                sectionAPI.getAll(),
                scheduleAPI.getAll(),
            ]);

            // Update the state with the lengths of the returned arrays.
            // It safely checks for .results (if paginated) or .data (if flat array)
            setStats({
                teachers: teachers.data.results?.length || teachers.data.length || 0,
                courses: courses.data.results?.length || courses.data.length || 0,
                rooms: rooms.data.results?.length || rooms.data.length || 0,
                sections: sections.data.results?.length || sections.data.length || 0,
                schedules: schedules.data.results?.length || schedules.data.length || 0,
            });
        } catch (error) {
            console.error('Error loading stats:', error);
        } finally {
            // Turn off the loading spinner whether the request succeeds or fails
            setLoading(false);
        }
    };

    // If still fetching initial data, show a full-page spinner
    if (loading) return <div className="loading-spinner">Loading dashboard...</div>;

    // ---------------------------------------------------------
    // EVENT HANDLERS
    // ---------------------------------------------------------

    /**
     * Executes the critical End Semester Rollover action.
     * Wipes schedules and assignments but leaves master data intact.
     */
    const handleResetSemester = async () => {
        // Double-check the confirmation text input
        if (confirmText !== 'CONFIRM') return;

        setResetting(true);
        try {
            // Send the request to the Django backend
            await systemAPI.resetSemester({ confirmation: 'CONFIRM' });
            
            // Provide feedback via native browser alert
            alert('Semester reset successful! All schedules and mappings have been cleared.');
            
            // Clean up the modal state
            setShowResetModal(false);
            setConfirmText('');
            
            // Refresh the dashboard numbers (schedules should drop to 0)
            loadStats(); 
        } catch (error) {
            console.error('Reset failed:', error);
            alert('Failed to reset semester: ' + (error.response?.data?.error || error.message));
        } finally {
            setResetting(false);
        }
    };

    // ---------------------------------------------------------
    // RENDER UI
    // ---------------------------------------------------------
    return (
        <div className="admin-dashboard fade-in">
            {/* Page Title */}
            <div className="page-header fade-in">
                <h1 className="page-title">System Admin Dashboard</h1>
                <p className="page-description">Manage system health, data, and schedules.</p>
            </div>

            {/* 
                Top row of data cards showing metrics. 
                Values dynamically loaded from the `stats` state object.
            */}
            <div className="stats-grid fade-in">
                <div className="stat-card">
                    <div className="stat-label">Total Teachers</div>
                    <div className="stat-value">{stats.teachers}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Total Courses</div>
                    <div className="stat-value">{stats.courses}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Total Rooms</div>
                    <div className="stat-value">{stats.rooms}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Total Sections</div>
                    <div className="stat-value">{stats.sections}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Generated Schedules</div>
                    <div className="stat-value">{stats.schedules}</div>
                </div>
            </div>

            {/* 
                Grid of quick links navigating to other administrative pages.
            */}
            <div className="actions-section">
                <h2 className="actions-header">Quick Actions</h2>
                <div className="actions-grid">
                    <Link to="/data" className="action-card">
                        <h3>Data Management</h3>
                        <p>Manage teachers, courses, rooms, and sections.</p>
                    </Link>
                    <Link to="/generate" className="action-card">
                        <h3>Generate Schedule</h3>
                        <p>Run the scheduling algorithm.</p>
                    </Link>
                    <Link to="/users" className="action-card">
                        <h3>User Management</h3>
                        <p>Manage system access and roles.</p>
                    </Link>
                    <Link to="/audit-logs" className="action-card">
                        <h3>Audit Logs</h3>
                        <p>View system activity and history.</p>
                    </Link>
                    <Link to="/analytics" className="action-card">
                        <h3>Analytics</h3>
                        <p>View workload and utilization stats.</p>
                    </Link>
                    <Link to="/change-requests" className="action-card">
                        <h3>Change Requests</h3>
                        <p>Review requests from HODs.</p>
                    </Link>
                </div>
            </div>

            {/* 
                System Administration Section (Dangerous Actions)
            */}
            <div className="section-header" style={{ marginTop: '3rem', marginBottom: '1rem' }}>
                <h2 style={{ fontSize: '1.25rem', color: 'var(--text-primary)' }}>System Administration</h2>
            </div>

            <div className="card" style={{ borderLeft: '4px solid var(--danger)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>End Semester Rollover</h3>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0 }}>
                            Archive current semester data and reset schedules.
                        </p>
                    </div>
                    {/* Hitting this button only OPENS the modal, it doesn't run the API call yet */}
                    <button
                        onClick={() => setShowResetModal(true)}
                        className="btn btn-danger"
                    >
                        Reset Semester
                    </button>
                </div>
            </div>

            {/* 
                Confirmation Modal
                Only rendered natively inside the DOM when showResetModal is true.
            */}
            {showResetModal && (
                <div className="modal-overlay">
                    <div className="modal-content" style={{ maxWidth: '400px' }}>
                        <div className="modal-header" style={{ marginBottom: '1rem' }}>
                            <h3 className="modal-title" style={{ fontSize: '1.25rem' }}>
                                End Semester Rollover
                            </h3>
                        </div>

                        <div className="modal-body" style={{ fontSize: '0.9rem' }}>
                            <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>
                                This action will <strong>permanently delete</strong> all schedules and teacher-course assignments.
                            </p>

                            <div className="modal-warning-box" style={{ padding: '0.75rem', fontSize: '0.85rem' }}>
                                Master data (Teachers, Courses, Data) will be preserved. A backup is created automatically.
                            </div>

                            <div style={{ marginTop: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500', fontSize: '0.85rem' }}>
                                    Type <strong>CONFIRM</strong> to proceed:
                                </label>
                                {/* Text input for safety validation */}
                                <input
                                    type="text"
                                    className="modal-input"
                                    value={confirmText}
                                    onChange={(e) => setConfirmText(e.target.value)}
                                    placeholder="CONFIRM"
                                    autoFocus
                                    style={{ padding: '0.5rem' }}
                                />
                            </div>
                        </div>

                        <div className="modal-footer" style={{ marginTop: '1.5rem' }}>
                            <button
                                onClick={() => { setShowResetModal(false); setConfirmText(''); }}
                                className="btn btn-secondary"
                                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
                                disabled={resetting}
                            >
                                Cancel
                            </button>
                            {/* Execute Request Button. Disabled until text matches precisely. */}
                            <button
                                onClick={handleResetSemester}
                                className="btn btn-danger"
                                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
                                disabled={confirmText !== 'CONFIRM' || resetting}
                            >
                                {resetting ? 'Resetting...' : 'Confirm Reset'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default AdminDashboard;
