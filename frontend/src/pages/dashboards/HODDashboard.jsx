/**
 * HOD (Head of Department) Dashboard Component
 * ============================================
 * 
 * Provides an overview tailored specifically for Department Heads.
 * They don't need to see the entire college's data; they only need to see 
 * metrics (teachers, sections) related to their specific department.
 * 
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 * Sprint: 1
 */

// Import React hooks and Router components
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

// Import global Auth Context to identify which department this user belongs to
import { useAuth } from '../../context/AuthContext';
// Import specific API endpoints allowed for HODs, plus change requests for dynamic pending stats
import { teacherAPI, sectionAPI, changeRequestAPI } from '../../services/api';

function HODDashboard() {
    // ---------------------------------------------------------
    // STATE & CONTEXT
    // ---------------------------------------------------------
    const { user } = useAuth(); // Contains `user.department` (e.g., 'CSE')

    // Local state for numeric overview metrics
    const [stats, setStats] = useState({
        deptTeachers: 0,
        deptCourses: 0,
        deptSections: 0,
        pendingApprovals: 0,
    });

    // Loading flag
    const [loading, setLoading] = useState(true);

    // ---------------------------------------------------------
    // DATA FETCHING
    // ---------------------------------------------------------
    // The dependency array includes `user`, so this effect reruns if the user changes.
    useEffect(() => {
        loadDeptStats();
    }, [user]);

    /**
     * Loads aggregated counts specifically filtered by the HOD's department.
     */
    const loadDeptStats = async () => {
        // Yield early if the user object hasn't loaded a department yet
        if (!user?.department) return;

        try {
            // Fetch teachers, sections, and dynamic pending request counts concurrently
            const [teachers, sections, pendingRes] = await Promise.all([
                teacherAPI.byDepartment(user.department), // Requires specialized backend endpoint
                sectionAPI.getAll(),                      // Fetches all, filters locally
                changeRequestAPI.getPendingCount().catch(() => ({ data: { count: 0 } }))
            ]);

            // Safely extract the data arrays regardless of pagination settings
            const sectionData = sections.data.results || sections.data || [];

            // Client-side filtering: Only keep sections matching this HOD's department
            const deptSections = sectionData.filter(s => s.department === user.department);

            // Update the state with the calculated lengths
            setStats({
                deptTeachers: teachers.data.results?.length || teachers.data.length || 0,
                deptCourses: 0, // Placeholder, would need a specialized department-course endpoint
                deptSections: deptSections.length,
                pendingApprovals: pendingRes.data.count || 0,
            });
        } catch (error) {
            console.error('Error loading HOD stats:', error);
        } finally {
            setLoading(false);
        }
    };

    // Show a loading screen while resolving the promises
    if (loading) return <div className="loading-spinner">Loading department dashboard...</div>;

    // ---------------------------------------------------------
    // RENDER UI
    // ---------------------------------------------------------
    return (
        <div className="fade-in">
            {/* Header dynamically displays the user's department name */}
            <div className="page-header">
                <h1 className="page-title">Head of Department: {user.department}</h1>
                <p className="page-description">Oversee departmental academic planning and schedules.</p>
            </div>

            {/* Quick overview metric cards */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-label">Faculty Members</div>
                    <div className="stat-value">{stats.deptTeachers}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Active Sections</div>
                    <div className="stat-value">{stats.deptSections}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Pending Approvals</div>
                    <div className="stat-value" style={{ color: '#e67e22' }}>{stats.pendingApprovals}</div>
                </div>
            </div>

            {/* Quick Links tailored to HOD responsibilities */}
            <div className="actions-section">
                <h2 className="actions-header">Department Actions</h2>
                <div className="actions-grid">
                    <Link to="/data" className="action-card">
                        <h3>Manage Faculty</h3>
                        <p>View and edit faculty details.</p>
                    </Link>
                    <Link to="/timetable" className="action-card">
                        <h3>Dept Timetable</h3>
                        <p>View generated schedules for {user.department}.</p>
                    </Link>
                    <Link to="/analytics" className="action-card">
                        <h3>Workload Reports</h3>
                        <p>Check faculty workload distribution.</p>
                    </Link>
                </div>
            </div>

            {/* Hardcoded notice board (could be made dynamic later) */}
            <div className="card" style={{ marginTop: '2rem' }}>
                <h3>Department Notices via Scheduler</h3>
                <ul>
                    <li>Please review constraints for the upcoming semester.</li>
                    <li>Ensure all elective courses are assigned to sections.</li>
                </ul>
            </div>
        </div>
    );
}

export default HODDashboard;
