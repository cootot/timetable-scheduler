import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

// Import custom authentication hook to access login methods
import { useAuth } from '../context/AuthContext';

// Import Framer Motion for smooth, declarative animations
import { motion, AnimatePresence } from 'framer-motion';

// Import SVG icons from lucide-react for UI elements
import { User, Lock, Loader2, ArrowRight, LayoutGrid, Chrome, CheckCircle2 } from 'lucide-react';

// Import Google's official React wrapper for the One Tap and standard OAuth flow
import { GoogleLogin } from '@react-oauth/google';

// Import specific CSS styles for this page
import '../styles/Login.css';

/**
 * Login Page - Amrita Branded Edition
 * ====================================
 * 
 * Handles user authentication via standard credentials or Google OAuth.
 * It also handles edge cases like "Master Accounts" that contain multiple roles, 
 * prompting the user to select which specific sub-account they want to log into.
 * 
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 * Sprint: 1
 */
const Login = () => {
    // ---------------------------------------------------------
    // STATE MANAGEMENT
    // ---------------------------------------------------------
    
    // User input fields
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    
    // UI Feedback states
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    
    // States specifically for handling users with multiple roles linked to one Google account
    const [matchingUsers, setMatchingUsers] = useState([]);      // Array of users linked to the Google email
    const [showSelection, setShowSelection] = useState(false);   // UI toggle: Show form vs Show selection list
    const [googleToken, setGoogleToken] = useState(null);        // Temporary storage of the Google credential token

    // ---------------------------------------------------------
    // HOOKS & CONTEXT
    // ---------------------------------------------------------
    
    // Extract login methods from the global Auth Context
    const { login, googleLogin } = useAuth();
    
    // React Router hooks for programmatic navigation
    const navigate = useNavigate();
    const location = useLocation();

    // Determine where the user was trying to go before being redirected to login.
    // If they were just visiting the root, default to '/' (which redirects to dashboard).
    const from = location.state?.from?.pathname || '/';

    // ---------------------------------------------------------
    // EVENT HANDLERS
    // ---------------------------------------------------------

    /**
     * Handles the routing logic after a successful authentication event.
     * Faculty go directly to their timetable, others go to the dashboard/previous page.
     * @param {Object} user - The authenticated user object
     */
    const handleLoginSuccess = (user) => {
        if (user?.role === 'FACULTY') {
            navigate('/timetable', { replace: true });
        } else {
            // Replace: true prevents the user from hitting the "back" button and returning to the login page
            navigate(from, { replace: true });
        }
    };

    /**
     * Standard Username/Password form submission handler.
     */
    const handleSubmit = async (e) => {
        e.preventDefault(); // Prevent default browser form submission (page reload)
        
        // Reset old errors and disable button
        setError('');
        setIsLoading(true);

        // Call the context function which talks to the Django REST API
        const result = await login(username, password);

        // Evaluate the response
        if (result.success) {
            handleLoginSuccess(result.user);
        } else {
            setError(result.error); // Display exactly what went wrong (e.g., "Invalid credentials")
        }
        
        // Re-enable button
        setIsLoading(false);
    };

    /**
     * Callback triggered when Google successfully authenticates the user on their end.
     * We receive a JWT token from Google, which we send to our Django backend for validation.
     * 
     * @param {Object} credentialResponse - Response from the Google Identity Services snippet
     */
    const handleGoogleSuccess = async (credentialResponse) => {
        setError('');
        setIsLoading(true);
        
        // Save the raw token temporarily in case we need it for Step 2 (Account Selection)
        const token = credentialResponse.credential;
        setGoogleToken(token);

        // Send token to backend via context
        const result = await googleLogin(token);

        if (result.success) {
            // Edge Case: The backend found multiple user accounts linked to this 1 Google email
            // (e.g., an Admin who is also a Faculty member).
            // We must pause the login flow and ask them which account they want to use today.
            if (result.needsSelection) {
                setMatchingUsers(result.users); // Store the options
                setShowSelection(true);         // Flip UI to show the selection list
            } else {
                // Normal Case: 1 Email = 1 User Account
                handleLoginSuccess(result.user);
            }
        } else {
            setError(result.error);
            // Hide the Google Sign-in button temporarily if it failed to prevent spamming
        }
        setIsLoading(false);
    };

    /**
     * Step 2 of the Google Login Flow (Only for users with multiple roles).
     * Re-submits the Google token but specifies the exact internal User ID they want to log in as.
     * 
     * @param {number|string} userId - The primary key of the selected user account
     */
    const handleSelectUser = async (userId) => {
        setIsLoading(true);
        
        // Second attempt to login, this time providing the discriminator `userId`
        const result = await googleLogin(googleToken, userId);
        
        if (result.success) {
            handleLoginSuccess(result.user);
        } else {
            setError(result.error);
            setShowSelection(false); // Fallback to standard login view on failure
        }
        setIsLoading(false);
    };

    // ---------------------------------------------------------
    // RENDER UI
    // ---------------------------------------------------------
    return (
        <div className="login-page">

            {/* 
                =========================================
                Left Section: Brand Visuals & Animations
                =========================================
            */}
            <motion.div
                // Framer motion properties for sliding in from the left
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6 }}
                className="login-brand-section"
            >
                {/* Decorative CSS background shapes */}
                <div className="blob blob-1"></div>
                <div className="blob blob-2"></div>

                <div className="brand-content">
                    <motion.div
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ delay: 0.2, duration: 0.5 }}
                        className="brand-logo-wrapper"
                    >
                        <LayoutGrid size={32} color="var(--primary-light)" />
                    </motion.div>

                    <motion.h1
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        transition={{ delay: 0.3, duration: 0.5 }}
                        className="brand-title"
                    >
                        Master your <br />
                        <span className="highlight-text">
                            Academic Schedule
                        </span>
                    </motion.h1>

                    <motion.p
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        transition={{ delay: 0.4, duration: 0.5 }}
                        className="brand-desc"
                    >
                        Automated conflict-free scheduling for Amrita University.
                        Optimize resources, manage faculty workloads, and generate timetables in seconds.
                    </motion.p>
                </div>
            </motion.div>

            {/* 
                =========================================
                Right Section: Authenticaton Form
                =========================================
            */}
            <div className="login-form-section">
                <motion.div
                    // Slighly different entrance animation for the form card (sliding up)
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="form-card"
                >
                    <div className="form-header">
                        <h2>Welcome back</h2>
                        <p>Sign in to access the dashboard.</p>
                    </div>

                    {/* Display API/Validation errors clearly at the top of the form */}
                    {error && (
                        <div className="error-alert">
                            <span>⚠️</span> {error}
                        </div>
                    )}

                    {/* 
                        AnimatePresence enables exit animations.
                        When switching between the Form and the User Selection list, 
                        the outgoing component fades out before the new one fades in.
                    */}
                    <AnimatePresence mode="wait">
                        {!showSelection ? (
                            /* --- Standard Login Form View --- */
                            <motion.div
                                key="login-form"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                            >
                                <form onSubmit={handleSubmit}>
                                    
                                    {/* Username Field */}
                                    <div className="form-group">
                                        <label className="input-label">Username / Email</label>
                                        <div className="input-wrapper">
                                            <div className="input-icon">
                                                <User size={20} />
                                            </div>
                                            <input
                                                type="text"
                                                value={username}
                                                onChange={(e) => setUsername(e.target.value)}
                                                required
                                                className="input-field"
                                                placeholder="Enter your username"
                                            />
                                        </div>
                                    </div>

                                    {/* Password Field */}
                                    <div className="form-group">
                                        <label className="input-label">Password</label>
                                        <div className="input-wrapper">
                                            <div className="input-icon">
                                                <Lock size={20} />
                                            </div>
                                            <input
                                                type="password"
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                required
                                                className="input-field"
                                                placeholder="••••••••"
                                            />
                                        </div>
                                    </div>

                                    {/* Submit Button with interactive states */}
                                    <motion.button
                                        whileHover={{ scale: 1.02 }}
                                        whileTap={{ scale: 0.98 }}
                                        type="submit"
                                        disabled={isLoading}
                                        className="submit-btn"
                                    >
                                        {/* State-driven button text/icon */}
                                        {isLoading ? (
                                            <>
                                                <Loader2 className="btn-spinner" size={20} />
                                                <span>Verifying...</span>
                                            </>
                                        ) : (
                                            <>
                                                <span>Sign In</span>
                                                <ArrowRight size={18} />
                                            </>
                                        )}
                                    </motion.button>
                                </form>

                                {/* Visual divider */}
                                <div className="divider">
                                    <span>Or continue with</span>
                                </div>

                                {/* Google Identity Services Button Wrapper */}
                                <div className="google-login-container">
                                    <GoogleLogin
                                        onSuccess={handleGoogleSuccess}
                                        onError={() => setError('Google Login Failed. Please try again or use a manual login.')}
                                        useOneTap // Attempts to show the slide-down Google prompt if the user is already logged in on the browser
                                        width="100%"
                                        text="signin_with"
                                        shape="rectangular"
                                        theme="outline"
                                    />
                                </div>
                            </motion.div>
                        ) : (
                            /* --- Multi-Role Selection View --- */
                            /* Appears ONLY if Google Login finds multiple matching accounts */
                            <motion.div
                                key="account-selection"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                className="selection-view"
                            >
                                <div className="selection-header">
                                    <h3>Select Account</h3>
                                    <p>Since you are using a master Gmail account, please select which profile you want to access.</p>
                                </div>

                                <div className="user-list">
                                    {/* Render a button for each matching account */}
                                    {matchingUsers.map(user => (
                                        <button
                                            key={user.id}
                                            onClick={() => handleSelectUser(user.id)}
                                            className="user-select-item"
                                            disabled={isLoading}
                                        >
                                            <div className="user-info">
                                                <span className="user-name">{user.display_name}</span>
                                                <span className="user-role">{user.role} ({user.username})</span>
                                            </div>
                                            <CheckCircle2 size={18} className="select-icon" />
                                        </button>
                                    ))}
                                </div>

                                {/* Emergency escape hatch backend to the main form */}
                                <button
                                    onClick={() => setShowSelection(false)}
                                    className="back-btn"
                                >
                                    Back to Login
                                </button>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Footer legal text */}
                    <div className="form-footer">
                        M3 System for Amrita University v1.0 © 2026
                    </div>
                </motion.div>
            </div>
        </div>
    );
};

export default Login;