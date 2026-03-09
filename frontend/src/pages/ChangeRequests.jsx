/**
 * Change Requests Page (Admin Only)
 * 
 * Review and approve/reject HOD modification requests
 */

import { useState, useEffect } from 'react';
import { changeRequestAPI } from '../services/api';

function ChangeRequests() {
    const [requests, setRequests] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('PENDING'); // PENDING, APPROVED, REJECTED, ALL
    const [selectedRequest, setSelectedRequest] = useState(null);
    const [adminNotes, setAdminNotes] = useState('');
    const [processing, setProcessing] = useState(false);

    useEffect(() => {
        loadRequests();
    }, []);

    const loadRequests = async () => {
        try {
            const response = await changeRequestAPI.getAll();
            setRequests(response.data.results || response.data);
        } catch (error) {
            console.error('Error loading change requests:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleApprove = async (requestId) => {
        if (!window.confirm('Approve this change request? This will apply the changes to the database.')) {
            return;
        }

        setProcessing(true);
        try {
            await changeRequestAPI.approve(requestId, adminNotes);
            alert('Request approved successfully!');
            setSelectedRequest(null);
            setAdminNotes('');
            loadRequests();
        } catch (error) {
            console.error('Error approving request:', error);
            alert('Failed to approve request: ' + (error.response?.data?.error || error.message));
        } finally {
            setProcessing(false);
        }
    };

    const handleReject = async (requestId) => {
        if (!window.confirm('Reject this change request?')) {
            return;
        }

        setProcessing(true);
        try {
            await changeRequestAPI.reject(requestId, adminNotes);
            alert('Request rejected.');
            setSelectedRequest(null);
            setAdminNotes('');
            loadRequests();
        } catch (error) {
            console.error('Error rejecting request:', error);
            alert('Failed to reject request.');
        } finally {
            setProcessing(false);
        }
    };

    const filteredRequests = requests.filter(req =>
        filter === 'ALL' ? true : req.status === filter
    );

    if (loading) return <div className="loading-spinner">Loading requests...</div>;

    const getStatusBadge = (status) => {
        switch (status) {
            case 'PENDING': return 'badge-warning';
            case 'APPROVED': return 'badge-success';
            case 'REJECTED': return 'badge-danger';
            default: return 'badge-secondary';
        }
    };

    const getChangeTypeBadge = (type) => {
        switch (type) {
            case 'CREATE': return 'badge-success';
            case 'UPDATE': return 'badge-warning';
            case 'DELETE': return 'badge-danger';
            case 'SWAP': return 'badge-info';
            default: return 'badge-secondary';
        }
    };

    return (
        <div className="change-requests-page">
            <div className="page-header">
                <h1 className="page-title">Change Requests</h1>
                <p className="page-description">Review and approve HOD modification requests.</p>
            </div>

            <div className="filters" style={{ marginBottom: '1rem' }}>
                <button
                    className={`btn ${filter === 'PENDING' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setFilter('PENDING')}
                >
                    Pending ({requests.filter(r => r.status === 'PENDING').length})
                </button>
                <button
                    className={`btn ${filter === 'APPROVED' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setFilter('APPROVED')}
                    style={{ marginLeft: '0.5rem' }}
                >
                    Approved
                </button>
                <button
                    className={`btn ${filter === 'REJECTED' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setFilter('REJECTED')}
                    style={{ marginLeft: '0.5rem' }}
                >
                    Rejected
                </button>
                <button
                    className={`btn ${filter === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setFilter('ALL')}
                    style={{ marginLeft: '0.5rem' }}
                >
                    All
                </button>
            </div>

            <div className="card">
                {filteredRequests.length === 0 ? (
                    <p>No {filter.toLowerCase()} requests found.</p>
                ) : (
                    <div className="table-container">
                        <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ background: '#f8f9fa', textAlign: 'left' }}>
                                    <th style={{ padding: '12px', borderBottom: '2px solid #ddd' }}>Requested By</th>
                                    <th style={{ padding: '12px', borderBottom: '2px solid #ddd' }}>Type</th>
                                    <th style={{ padding: '12px', borderBottom: '2px solid #ddd' }}>Target</th>
                                    <th style={{ padding: '12px', borderBottom: '2px solid #ddd' }}>Status</th>
                                    <th style={{ padding: '12px', borderBottom: '2px solid #ddd' }}>Date</th>
                                    <th style={{ padding: '12px', borderBottom: '2px solid #ddd' }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredRequests.map((req) => (
                                    <tr key={req.id} style={{ borderBottom: '1px solid #eee' }}>
                                        <td style={{ padding: '12px' }}>
                                            {req.requested_by_name}
                                            <br />
                                            <small style={{ color: '#666' }}>{req.requested_by_department}</small>
                                        </td>
                                        <td style={{ padding: '12px' }}>
                                            <span className={`badge ${getChangeTypeBadge(req.change_type)}`}>
                                                {req.change_type}
                                            </span>
                                        </td>
                                        <td style={{ padding: '12px' }}>
                                            {req.change_type === 'SWAP' ? (
                                                <>
                                                    <strong>{req.proposed_data?.course_id}</strong>
                                                    <br />
                                                    <small>Section: {req.proposed_data?.section_id}</small>
                                                </>
                                            ) : (
                                                <>
                                                    {req.target_model}
                                                    {req.target_id && <><br /><small>{req.target_id}</small></>}
                                                </>
                                            )}
                                        </td>
                                        <td style={{ padding: '12px' }}>
                                            <span className={`badge ${getStatusBadge(req.status)}`}>
                                                {req.status}
                                            </span>
                                        </td>
                                        <td style={{ padding: '12px', fontSize: '0.875rem' }}>
                                            {new Date(req.created_at).toLocaleDateString()}
                                        </td>
                                        <td style={{ padding: '12px' }}>
                                            <button
                                                onClick={() => setSelectedRequest(req)}
                                                className="btn btn-sm btn-secondary"
                                                style={{ padding: '0.25rem 0.5rem' }}
                                            >
                                                View Details
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Detail Modal */}
            {selectedRequest && (
                <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                    <div className="modal-content" style={{ background: 'white', padding: '2rem', borderRadius: '8px', maxWidth: '800px', maxHeight: '80vh', overflow: 'auto', width: '90%' }}>
                        <h2>Change Request Details</h2>

                        <div style={{ marginBottom: '1rem' }}>
                            <strong>Requested by:</strong> {selectedRequest.requested_by_name} ({selectedRequest.requested_by_department})<br />
                            <strong>Type:</strong> {selectedRequest.change_type} {selectedRequest.target_model}<br />
                            <strong>Status:</strong> <span className={`badge ${getStatusBadge(selectedRequest.status)}`}>{selectedRequest.status}</span><br />
                            <strong>Date:</strong> {new Date(selectedRequest.created_at).toLocaleString()}
                        </div>

                        {selectedRequest.request_notes && (
                            <div style={{ marginBottom: '1rem', padding: '1rem', background: '#f8f9fa', borderRadius: '4px' }}>
                                <strong>HOD Notes:</strong><br />
                                {selectedRequest.request_notes}
                            </div>
                        )}

                        <div style={{ marginBottom: '1rem' }}>
                            <h3>Proposed Changes:</h3>
                            <pre style={{ background: '#f8f9fa', padding: '1rem', borderRadius: '4px', overflow: 'auto' }}>
                                {JSON.stringify(selectedRequest.proposed_data, null, 2)}
                            </pre>
                        </div>

                        {selectedRequest.current_data && (
                            <div style={{ marginBottom: '1rem' }}>
                                <h3>Current Data:</h3>
                                <pre style={{ background: '#fff3cd', padding: '1rem', borderRadius: '4px', overflow: 'auto' }}>
                                    {JSON.stringify(selectedRequest.current_data, null, 2)}
                                </pre>
                            </div>
                        )}

                        {selectedRequest.status === 'PENDING' && (
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                                    Admin Notes:
                                </label>
                                <textarea
                                    value={adminNotes}
                                    onChange={(e) => setAdminNotes(e.target.value)}
                                    placeholder="Optional notes about your decision..."
                                    style={{ width: '100%', padding: '0.5rem', border: '1px solid #ddd', borderRadius: '4px', minHeight: '80px' }}
                                />
                            </div>
                        )}

                        {selectedRequest.admin_notes && (
                            <div style={{ marginBottom: '1rem', padding: '1rem', background: '#e7f3ff', borderRadius: '4px' }}>
                                <strong>Admin Review Notes:</strong><br />
                                {selectedRequest.admin_notes}<br />
                                <small>Reviewed by: {selectedRequest.reviewed_by_name} on {new Date(selectedRequest.reviewed_at).toLocaleString()}</small>
                            </div>
                        )}

                        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                            {selectedRequest.status === 'PENDING' && (
                                <>
                                    <button
                                        onClick={() => handleApprove(selectedRequest.id)}
                                        className="btn btn-success"
                                        disabled={processing}
                                    >
                                        ✓ Approve
                                    </button>
                                    <button
                                        onClick={() => handleReject(selectedRequest.id)}
                                        className="btn btn-danger"
                                        disabled={processing}
                                    >
                                        ✗ Reject
                                    </button>
                                </>
                            )}
                            <button
                                onClick={() => { setSelectedRequest(null); setAdminNotes(''); }}
                                className="btn btn-secondary"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ChangeRequests;
