/**
 * Faculty Course Mapping Module
 *
 * Tabs:
 *  1. Faculty Courses     — For each faculty, list all courses they handle
 *  2. Course → Faculty    — Search by course name/code to find the handling faculty
 *  3. Sections by Faculty — Which sections each faculty teaches
 *  4. Elective Slots      — Overview of PE/FE group slots and classrooms
 *
 * Author: Frontend Team
 */

import React, { useState, useEffect } from 'react';
import { teacherAPI, courseAPI } from '../services/api';

const ELECTIVE_COLORS = {
    PE: { bg: '#fffbeb', border: '#f59e0b', text: '#78350f', badge: 'pe-badge' },
    FREE: { bg: '#ecfdf5', border: '#10b981', text: '#064e3b', badge: 'fe-badge' },
};

function getElectiveStyle(elective_group) {
    if (!elective_group) return {};
    if (elective_group.includes('PE_')) return ELECTIVE_COLORS.PE;
    if (elective_group.includes('FREE_')) return ELECTIVE_COLORS.FREE;
    return {};
}

// ─── Helper Pill ─────────────────────────────────────────────────────────────
function ElectivePill({ group }) {
    if (!group) return null;
    if (group.includes('PE_')) return <span className="elective-badge pe-badge">PE</span>;
    if (group.includes('FREE_')) return <span className="elective-badge fe-badge">FE</span>;
    return null;
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function FacultyMapping() {
    const [activeTab, setActiveTab] = useState('faculty-courses');
    const [teachers, setTeachers] = useState([]);
    const [courses, setCourses] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedFaculty, setSelectedFaculty] = useState('');

    const [mappings, setMappings] = useState([]);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            // Import teacherCourseMappingAPI locally to avoid lint issues if not at top-level
            const { teacherCourseMappingAPI } = await import('../services/api');
            const [teachersRes, coursesRes, mappingsRes] = await Promise.all([
                teacherAPI.getAll(),
                courseAPI.getAll(),
                teacherCourseMappingAPI.getAll()
            ]);
            setTeachers(teachersRes.data?.results || teachersRes.data || []);
            setCourses(coursesRes.data?.results || coursesRes.data || []);
            setMappings(mappingsRes.data?.results || mappingsRes.data || []);
        } catch (err) {
            console.error('Error loading faculty mapping data:', err);
        } finally {
            setLoading(false);
        }
    };

    // Filter teachers for display
    const filteredTeachers = selectedFaculty
        ? teachers.filter(t => t.teacher_id === selectedFaculty)
        : teachers;

    // Course search results
    const lowerSearch = searchQuery.toLowerCase();
    const filteredCourses = courses.filter(c =>
        c.course_name?.toLowerCase().includes(lowerSearch) ||
        c.course_id?.toLowerCase().includes(lowerSearch)
    );

    // Group courses by elective group
    const electiveGroups = {};
    courses.filter(c => c.is_elective && c.elective_group).forEach(c => {
        if (!electiveGroups[c.elective_group]) electiveGroups[c.elective_group] = [];
        electiveGroups[c.elective_group].push(c);
    });

    const TABS = [
        { id: 'faculty-courses', label: ' Faculty Courses', desc: 'All courses per faculty' },
        { id: 'course-lookup', label: 'Course Lookup', desc: 'Find faculty by course' },
        { id: 'section-handling', label: 'Sections by Faculty', desc: 'Which sections each faculty covers' },
        { id: 'elective-slots', label: 'Elective Slots', desc: 'PE/FE group overview' },
    ];

    return (
        <div className="fade-in">
            <div className="page-header">
                <h1 className="page-title">Faculty Course Mapping</h1>
                <p className="page-description">
                    Explore course assignments, elective groupings, and faculty workload distribution
                </p>
            </div>

            {/* Tab Navigation */}
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                {TABS.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        style={{
                            padding: '0.6rem 1.2rem',
                            borderRadius: '0.75rem',
                            border: activeTab === tab.id ? 'none' : '1px solid var(--border)',
                            background: activeTab === tab.id
                                ? 'linear-gradient(135deg, var(--primary), var(--primary-dark))'
                                : 'var(--card-bg)',
                            color: activeTab === tab.id ? '#fff' : 'var(--text-primary)',
                            fontWeight: 600,
                            fontSize: '0.875rem',
                            cursor: 'pointer',
                            boxShadow: activeTab === tab.id ? '0 4px 12px rgba(124, 58, 237, 0.3)' : 'none',
                            transition: 'all 0.2s ease',
                        }}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="loading">
                    <div className="spinner" />
                    <p>Loading faculty mappings...</p>
                </div>
            ) : (
                <>
                    {/* ── Tab 1: Faculty Courses ─────────────────────────────────────── */}
                    {activeTab === 'faculty-courses' && (
                        <div>
                            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                <div className="filter-group">
                                    <label className="filter-label">Filter by Faculty</label>
                                    <select
                                        className="filter-select"
                                        value={selectedFaculty}
                                        onChange={e => setSelectedFaculty(e.target.value)}
                                    >
                                        <option value="">All Faculty</option>
                                        {teachers.map(t => (
                                            <option key={t.teacher_id} value={t.teacher_id}>{t.teacher_name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))' }}>
                                {filteredTeachers.map(teacher => {
                                    // Find mappings tied to this teacher specifically
                                    const teacherMappings = mappings.filter(m => m.teacher === teacher.teacher_id || m.teacher?.teacher_id === teacher.teacher_id);

                                    // Compute total assigned hours based on mapping rules
                                    const assignedHours = teacherMappings.reduce((sum, mapItem) => {
                                        const cId = mapItem.course?.course_id || mapItem.course;
                                        const cData = courses.find(c => c.course_id === cId);
                                        return sum + (cData?.weekly_slots || 0);
                                    }, 0);

                                    // Deduplicate courses visually if needed, though showing section instances separates them clearly
                                    return (
                                        <div key={teacher.teacher_id} className="card" style={{ padding: '1.25rem', marginBottom: 0 }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                                                <div style={{
                                                    width: 42, height: 42, borderRadius: '50%',
                                                    background: 'linear-gradient(135deg, var(--primary), var(--primary-dark))',
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    color: '#fff', fontWeight: 800, fontSize: '1rem', flexShrink: 0
                                                }}>
                                                    {teacher.teacher_name?.charAt(0) || 'T'}
                                                </div>
                                                <div>
                                                    <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{teacher.teacher_name}</div>
                                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                                        {teacher.teacher_id} · {teacher.department}
                                                    </div>
                                                </div>
                                                <div style={{ marginLeft: 'auto', textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                                    {(() => {
                                                        // Cap the percentage explicitly at 100% so it never prints visually invalid metrics per user request
                                                        const limit = teacher.max_hours_per_week || 40;
                                                        const rawPct = Math.round((assignedHours / limit) * 100);
                                                        const pct = Math.min(rawPct, 100);
                                                        const displayHours = Math.min(assignedHours, limit);
                                                        const color = rawPct > 95 ? 'var(--danger)' : (rawPct < 40 ? 'var(--warning)' : 'var(--success)');
                                                        return (
                                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                                                                <div style={{ fontWeight: 800, color: color, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                                    {pct}% <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>({displayHours}/{limit}h)</span>
                                                                </div>
                                                                <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '2px' }}>Total Workload</div>
                                                            </div>
                                                        );
                                                    })()}
                                                </div>
                                            </div>

                                            {teacherMappings.length === 0 ? (
                                                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                                    No courses currently mapped
                                                </p>
                                            ) : (
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                                                    {teacherMappings.map((m, idx) => {
                                                        const cId = m.course?.course_id || m.course;
                                                        const cData = courses.find(c => c.course_id === cId);
                                                        const style = getElectiveStyle(cData?.elective_group);
                                                        return (
                                                            <div key={idx} style={{
                                                                display: 'flex', alignItems: 'center', gap: '0.5rem',
                                                                padding: '0.4rem 0.6rem', borderRadius: '0.5rem', fontSize: '0.8rem',
                                                                background: style.bg || 'var(--bg-tertiary)',
                                                                borderLeft: `3px solid ${style.border || 'var(--primary)'}`,
                                                                color: style.text || 'var(--text-primary)',
                                                            }}>
                                                                <span style={{ fontWeight: 600 }}>{cData?.course_id || cId}</span>
                                                                <span style={{ flex: 1 }}>{cData?.course_name || 'Unknown'}</span>

                                                                {m.section_group && (
                                                                    <span style={{ background: 'rgba(0,0,0,0.05)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>
                                                                        Sec {m.section_group}
                                                                    </span>
                                                                )}
                                                                {m.domain_name && (
                                                                    <span style={{ fontSize: '0.7rem', color: style.text || 'grey' }}>
                                                                        {m.domain_name}
                                                                    </span>
                                                                )}

                                                                <ElectivePill group={cData?.elective_group} />
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* ── Tab 2: Course Lookup ───────────────────────────────────────── */}
                    {activeTab === 'course-lookup' && (
                        <div>
                            <div style={{ marginBottom: '1.25rem' }}>
                                <input
                                    type="text"
                                    className="filter-select"
                                    placeholder="🔍 Search by course name or code..."
                                    value={searchQuery}
                                    onChange={e => setSearchQuery(e.target.value)}
                                    style={{ width: '100%', maxWidth: 480, fontSize: '0.95rem', padding: '0.75rem 1rem' }}
                                />
                            </div>

                            <div className="table-container card" style={{ padding: 0, overflow: 'hidden' }}>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Course ID</th>
                                            <th>Course Name</th>
                                            <th>Year / Sem</th>
                                            <th>Type</th>
                                            <th>Elective Group</th>
                                            <th>Weekly Slots</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredCourses.length === 0 ? (
                                            <tr>
                                                <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                                                    {searchQuery ? `No courses matching "${searchQuery}"` : 'No courses found'}
                                                </td>
                                            </tr>
                                        ) : filteredCourses.map(c => {
                                            const style = getElectiveStyle(c.elective_group);
                                            return (
                                                <tr key={c.course_id} style={c.is_elective ? { background: style.bg } : {}}>
                                                    <td style={{ fontWeight: 700, color: 'var(--primary)' }}>{c.course_id}</td>
                                                    <td>{c.course_name}</td>
                                                    <td>Year {c.year} · {c.semester?.toUpperCase()}</td>
                                                    <td>
                                                        {c.is_lab ? <span className="lab-badge" style={{ fontSize: '0.65rem' }}>LAB</span> : null}
                                                        {c.is_elective ? <ElectivePill group={c.elective_group} /> : (
                                                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Regular</span>
                                                        )}
                                                    </td>
                                                    <td style={{ fontSize: '0.8rem', color: style.text || 'var(--text-muted)' }}>
                                                        {c.elective_group || '—'}
                                                    </td>
                                                    <td style={{ fontWeight: 600, textAlign: 'center' }}>{c.weekly_slots}</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* ── Tab 3: Sections by Faculty ─────────────────────────────────── */}
                    {activeTab === 'section-handling' && (
                        <div>
                            <div style={{ marginBottom: '1rem' }}>
                                <input
                                    type="text"
                                    className="filter-select"
                                    placeholder="🔍 Search faculty name..."
                                    value={searchQuery}
                                    onChange={e => setSearchQuery(e.target.value)}
                                    style={{ width: '100%', maxWidth: 360, padding: '0.65rem 1rem' }}
                                />
                            </div>

                            <div className="table-container card" style={{ padding: 0, overflow: 'hidden' }}>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Faculty ID</th>
                                            <th>Faculty Name</th>
                                            <th>Department</th>
                                            <th>Max Hrs/Wk</th>
                                            <th>Qualification</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {teachers
                                            .filter(t =>
                                                !searchQuery ||
                                                t.teacher_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                                                t.teacher_id?.toLowerCase().includes(searchQuery.toLowerCase())
                                            )
                                            .map(teacher => (
                                                <tr key={teacher.teacher_id}>
                                                    <td style={{ fontWeight: 700, color: 'var(--primary)', fontFamily: 'monospace' }}>
                                                        {teacher.teacher_id}
                                                    </td>
                                                    <td style={{ fontWeight: 600 }}>{teacher.teacher_name}</td>
                                                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                                        {teacher.department || '—'}
                                                    </td>
                                                    <td style={{ textAlign: 'center', fontWeight: 600 }}>
                                                        {teacher.max_hours_per_week ?? '—'}
                                                    </td>
                                                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                                        {teacher.qualification || '—'}
                                                    </td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* ── Tab 4: Elective Slots ──────────────────────────────────────── */}
                    {activeTab === 'elective-slots' && (
                        <div>
                            <div style={{
                                display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap',
                            }}>
                                <div style={{
                                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                                    fontSize: '0.85rem', color: 'var(--text-secondary)',
                                    padding: '0.4rem 0.75rem', border: '1px solid var(--border)', borderRadius: '0.5rem',
                                    background: 'var(--card-bg)'
                                }}>
                                    <span style={{ width: 12, height: 12, borderRadius: 3, background: '#f59e0b', display: 'inline-block' }} />
                                    Professional Elective (PE)
                                </div>
                                <div style={{
                                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                                    fontSize: '0.85rem', color: 'var(--text-secondary)',
                                    padding: '0.4rem 0.75rem', border: '1px solid var(--border)', borderRadius: '0.5rem',
                                    background: 'var(--card-bg)'
                                }}>
                                    <span style={{ width: 12, height: 12, borderRadius: 3, background: '#10b981', display: 'inline-block' }} />
                                    Free Elective (FE)
                                </div>
                            </div>

                            {Object.entries(electiveGroups).length === 0 ? (
                                <div className="alert alert-info">No elective groups found in the database.</div>
                            ) : (
                                <div style={{ display: 'grid', gap: '1.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))' }}>
                                    {Object.entries(electiveGroups).map(([groupName, groupCourses]) => {
                                        const isPE = groupName.includes('PE_');
                                        const isFE = groupName.includes('FREE_');
                                        const borderColor = isPE ? '#f59e0b' : isFE ? '#10b981' : 'var(--primary)';
                                        const headerBg = isPE ? 'linear-gradient(135deg, #f59e0b, #d97706)'
                                            : isFE ? 'linear-gradient(135deg, #10b981, #059669)'
                                                : 'linear-gradient(135deg, var(--primary), var(--primary-dark))';

                                        return (
                                            <div key={groupName} className="card" style={{
                                                padding: 0, borderTop: `4px solid ${borderColor}`, marginBottom: 0, overflow: 'hidden'
                                            }}>
                                                <div style={{
                                                    background: headerBg, padding: '0.75rem 1.25rem',
                                                    color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                                                }}>
                                                    <div>
                                                        <div style={{ fontWeight: 800, fontSize: '1rem' }}>{groupName}</div>
                                                        <div style={{ fontSize: '0.75rem', opacity: 0.85 }}>
                                                            {groupCourses.length} course options
                                                        </div>
                                                    </div>
                                                    <div style={{
                                                        fontSize: '0.7rem', background: 'rgba(255,255,255,0.2)',
                                                        padding: '0.2rem 0.6rem', borderRadius: '0.5rem', fontWeight: 700
                                                    }}>
                                                        {isPE ? 'PE' : isFE ? 'FE' : 'ELECTIVE'}
                                                    </div>
                                                </div>

                                                <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                                                    {groupCourses.map(c => (
                                                        <div key={c.course_id} style={{
                                                            display: 'flex', gap: '0.5rem', alignItems: 'center',
                                                            padding: '0.4rem 0.6rem', borderRadius: '0.5rem',
                                                            background: 'var(--bg-tertiary)', fontSize: '0.8rem',
                                                        }}>
                                                            <span style={{ fontWeight: 700, color: borderColor, minWidth: 80 }}>{c.course_id}</span>
                                                            <span style={{ flex: 1, color: 'var(--text-primary)' }}>{c.course_name}</span>
                                                            <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                                                                {c.weekly_slots} slots
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
