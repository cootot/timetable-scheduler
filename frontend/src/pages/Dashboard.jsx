/**
 * Dashboard Page - Primary Navigation Hub
 * =======================================
 * 
 * This component acts as a high-level router (a "Switchboard") rather than a 
 * standalone visual page. When a user navigates to "/dashboard", this file 
 * intercepts the request, checks their specific RBAC role, and dynamically 
 * renders the correct, role-specific sub-dashboard.
 * 
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 * Sprint: 1
 */

// Import authentication context to get the currently logged-in user
import { useAuth } from '../context/AuthContext';

// Import the specific dashboard layouts for each role
import AdminDashboard from './dashboards/AdminDashboard';
import HODDashboard from './dashboards/HODDashboard';
import FacultyDashboard from './dashboards/FacultyDashboard';

function Dashboard() {
    // Extract the global 'user' object from the AuthContext.
    // This contains their username, role, full name, etc.
    const { user } = useAuth();

    // Safety check during initial page load or hard refresh.
    // If the Context hasn't finished hydrating the user from local storage
    // or the API yet, show a clean loading state instead of crashing.
    if (!user) {
        return <div className="loading-spinner">Loading dashboard...</div>;
    }

    // Evaluate the user's role and return the corresponding React Component.
    // This allows us to keep the code for a teacher's view completely separate
    // from the complex code for an admin's view.
    switch (user.role) {
        case 'ADMIN':
            return <AdminDashboard />;
        
        case 'HOD':
            return <HODDashboard />;
        
        case 'FACULTY':
            return <FacultyDashboard />;
        
        default:
            // Fallback UI for any unhandled or missing roles.
            // Protects the app from throwing a blank page error.
            return (
                <div className="card">
                    <h2>Welcome, {user.username}</h2>
                    <p>Your role ({user.role}) does not have a specific dashboard view configured.</p>
                    <p>Please contact an administrator if you believe this is an error.</p>
                </div>
            );
    }
}

export default Dashboard;

