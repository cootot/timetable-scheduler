/**
 * View Timetable Page — With Drag-and-Drop Move Support
 *
 * Features:
 * - Full HTML5 drag-and-drop for class blocks (Admin/HOD only)
 * - Drag-and-drop disabled for Electives and AVP Programs (Displays warning)
 * - Real-time visual indicators: green = valid drop, red = conflict
 * - Optimistic-locking to prevent concurrent admin overwrites
 * - Conflict tooltip shown on hover over a red drop zone
 *
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 * Sprint: 2
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { scheduleAPI, schedulerAPI, sectionAPI, teacherAPI, courseAPI, roomAPI, changeRequestAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import ElectiveMappingModal from '../components/ElectiveMappingModal';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
const SLOTS = [1, 2, 3, 4, 5, 6, 7, 8];

// Debounce utility
function useDebouncedCallback(fn, delay) {
    const timer = useRef(null);
    return useCallback((...args) => {
        clearTimeout(timer.current);
        timer.current = setTimeout(() => fn(...args), delay);
    }, [fn, delay]);
}

// ─── Component ────────────────────────────────────────────────────────────────

function ViewTimetable() {
    const { user } = useAuth();

    // ── Data state ──
    const [schedules, setSchedules] = useState([]);
    const [sections, setSections] = useState([]);
    const [teachers, setTeachers] = useState([]);
    const [courses, setCourses] = useState([]);
    const [rooms, setRooms] = useState([]);
    const [selectedSchedule, setSelectedSchedule] = useState('');
    const [selectedSection, setSelectedSection] = useState('');
    const [selectedTeacher, setSelectedTeacher] = useState('');
    const [selectedCourse, setSelectedCourse] = useState('');
    const [selectedRoom, setSelectedRoom] = useState('');
    const [timetable, setTimetable] = useState(null);
    const [loading, setLoading] = useState(false);

    // ── Verification modal ──
    const [verificationResult, setVerificationResult] = useState(null);
    const [showVerificationModal, setShowVerificationModal] = useState(false);
    const [showElectiveModal, setShowElectiveModal] = useState(false);
    const [verifying, setVerifying] = useState(false);

    // ── Publish state ──
    const [publishing, setPublishing] = useState(false);

    // ── Swap Faculty state ──
    const [showSwapModal, setShowSwapModal] = useState(false);
    const [swapTarget, setSwapTarget] = useState(null);
    const [availableFaculty, setAvailableFaculty] = useState([]);
    const [loadingFaculty, setLoadingFaculty] = useState(false);
    const [submittingSwap, setSubmittingSwap] = useState(false);
    const [swapNotes, setSwapNotes] = useState('');
    const [selectedNewTeacher, setSelectedNewTeacher] = useState('');

    // ── Drag-and-drop state ──
    const [dragging, setDragging] = useState(null);
    const [dropTargets, setDropTargets] = useState({});
    const [activeDropCell, setActiveDropCell] = useState(null);
    const [moveStatus, setMoveStatus] = useState(null);
    const validationAbortRef = useRef(null);

    const isAdminOrHOD = user?.role === 'ADMIN' || user?.role === 'HOD';

    // ── Initial data load ──
    useEffect(() => {
        loadInitialData();
    }, [user]);

    useEffect(() => {
        if (user && user.role === 'FACULTY' && user.teacher_id) {
            setSelectedTeacher(user.teacher_id);
        }
    }, [user]);

    const loadInitialData = async () => {
        try {
            const promises = [
                scheduleAPI.getAll(),
                sectionAPI.getAll(),
                courseAPI.getAll(),
                roomAPI.getAll()
            ];

            const isAdminOrHODCheck = user && (user.role === 'ADMIN' || user.role === 'HOD');
            if (isAdminOrHODCheck) {
                promises.push(teacherAPI.getAll());
            }

            const results = await Promise.allSettled(promises);

            if (results[0].status === 'fulfilled') {
                const res = results[0].value;
                setSchedules(res.data.results || res.data || []);
            }
            if (results[1].status === 'fulfilled') {
                const res = results[1].value;
                setSections(res.data.results || res.data || []);
            }
            if (results[2].status === 'fulfilled') {
                const res = results[2].value;
                setCourses(res.data.results || res.data || []);
            }
            if (results[3].status === 'fulfilled') {
                const res = results[3].value;
                setRooms(res.data.results || res.data || []);
            }
            if (isAdminOrHODCheck && results[4] && results[4].status === 'fulfilled') {
                const res = results[4].value;
                setTeachers(res.data.results || res.data || []);
            }

            if (user?.role === 'FACULTY' && !selectedSchedule && results[0].status === 'fulfilled') {
                const avail = results[0].value.data.results || results[0].value.data || [];
                if (avail.length > 0) setSelectedSchedule(avail[0].schedule_id);
            }
        } catch (error) {
            console.error('Fatal error in loadInitialData:', error);
        }
    };

    const loadTimetable = async () => {
        if (!selectedSchedule) return;
        setLoading(true);
        try {
            const teacherId = (user && user.role === 'FACULTY') ? user.teacher_id : selectedTeacher;
            const response = await schedulerAPI.getTimetable(
                selectedSchedule,
                selectedSection || null,
                teacherId || null,
                selectedCourse || null,
                selectedRoom || null
            );
            setTimetable(response.data);
            setDropTargets({});
            setDragging(null);
            setMoveStatus(null);
        } catch (error) {
            console.error('Error loading timetable:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (selectedSchedule) {
            loadTimetable();
            loadSmartFilters();
        } else {
            loadInitialData();
        }
    }, [selectedSchedule]);

    useEffect(() => {
        if (selectedSchedule) loadTimetable();
    }, [selectedSection, selectedTeacher, selectedCourse, selectedRoom]);

    const loadSmartFilters = async () => {
        if (!selectedSchedule) return;
        try {
            const response = await scheduleAPI.getFilters(selectedSchedule);
            const { sections: s, teachers: t, courses: c, rooms: r } = response.data;

            setSections(s.map(i => ({ class_id: i.class_id })));
            setTeachers(t);
            setCourses(c);
            setRooms(r.map(i => ({ room_id: i.room_id, block: i.block })));

            if (selectedSection && !s.some(i => i.class_id === selectedSection)) setSelectedSection('');
            if (selectedTeacher && !t.some(i => i.teacher_id === selectedTeacher)) {
                if (user?.role !== 'FACULTY') setSelectedTeacher('');
            }
            if (selectedCourse && !c.some(i => i.course_id === selectedCourse)) setSelectedCourse('');
            if (selectedRoom && !r.some(i => i.room_id === selectedRoom)) setSelectedRoom('');

        } catch (error) {
            console.error('Error loading smart filters:', error);
        }
    };

    // ── Verify & Publish ──
    const handleVerifySchedule = async () => {
        if (!selectedSchedule) return;
        setVerifying(true);
        try {
            const response = await schedulerAPI.validateSchedule(selectedSchedule);
            setVerificationResult(response.data);
            setShowVerificationModal(true);
        } catch (error) {
            alert('Failed to verify schedule');
        } finally {
            setVerifying(false);
        }
    };

    const handlePublishSchedule = async () => {
        if (!selectedSchedule) return;
        const scheduleName = schedules.find(s => s.schedule_id == selectedSchedule)?.name || 'this schedule';
        if (!window.confirm(`Publish "${scheduleName}"? This will notify all teachers whose timetable has changed.`)) return;

        setPublishing(true);
        try {
            const response = await schedulerAPI.publish(selectedSchedule);
            setMoveStatus({
                type: 'success',
                message: response.data.message || 'Schedule published successfully!',
            });
            const schedulesRes = await scheduleAPI.getAll();
            setSchedules(schedulesRes.data.results || schedulesRes.data || []);
        } catch (error) {
            const errMsg = error.response?.data?.error || 'Failed to publish schedule';
            setMoveStatus({ type: 'error', message: errMsg });
        } finally {
            setPublishing(false);
        }
    };

    const selectedScheduleObj = schedules.find(s => s.schedule_id == selectedSchedule);
    const isPublished = selectedScheduleObj?.status === 'PUBLISHED';

    // ── Swap Faculty ──
    const handleOpenSwapModal = async (classItem) => {
        setSwapTarget({
            entryId: classItem.entry_id,
            courseId: classItem.course_code,
            sectionId: classItem.section,
            currentTeacherId: classItem.teacher_id,
            currentTeacherName: classItem.teacher_name,
            timeslotId: classItem.timeslot_id
        });
        setShowSwapModal(true);
        setLoadingFaculty(true);
        setAvailableFaculty([]);
        setSelectedNewTeacher('');

        try {
            const res = await scheduleAPI.getAvailableFaculty(
                selectedSchedule,
                classItem.course_code,
                classItem.section
            );
            const filtered = res.data.filter(t => t.teacher_id !== classItem.teacher_id);
            setAvailableFaculty(filtered);
        } catch (error) {
            setMoveStatus({ type: 'error', message: 'Failed to load available faculty.' });
        } finally {
            setLoadingFaculty(false);
        }
    };

    const handleSubmitSwapRequest = async () => {
        if (!selectedNewTeacher) return;
        setSubmittingSwap(true);
        try {
            const isAdmin = user?.role === 'ADMIN';

            if (isAdmin) {
                await scheduleAPI.swapFaculty(
                    selectedSchedule,
                    swapTarget.courseId,
                    swapTarget.sectionId,
                    selectedNewTeacher
                );
                setMoveStatus({ type: 'success', message: 'Faculty swapped successfully.' });
                await loadTimetable();
            } else {
                const proposedData = {
                    entry_id: swapTarget.entryId,
                    new_teacher_id: selectedNewTeacher,
                    course_id: swapTarget.courseId,
                    section_id: swapTarget.sectionId,
                    timeslot_id: swapTarget.timeslotId
                };
                const currentData = {
                    current_teacher_id: swapTarget.currentTeacherId,
                    current_teacher_name: swapTarget.currentTeacherName
                };

                await changeRequestAPI.create({
                    target_model: 'ScheduleEntry',
                    target_id: swapTarget.entryId.toString(),
                    change_type: 'SWAP',
                    proposed_data: proposedData,
                    current_data: currentData,
                    request_notes: swapNotes || `Swap teacher for ${swapTarget.courseId} (${swapTarget.sectionId})`
                });

                setMoveStatus({ type: 'success', message: 'Swap request submitted to admin.' });
            }

            setShowSwapModal(false);
        } catch (error) {
            setMoveStatus({
                type: 'error',
                message: error.response?.data?.error || `Failed to ${user?.role === 'ADMIN' ? 'apply' : 'submit'} swap.`
            });
        } finally {
            setSubmittingSwap(false);
        }
    };

    // ── PDF ──
    const handleDownloadPDF = () => {
        if (!timetable) return;
        const doc = new jsPDF();
        doc.setFontSize(18);
        const title = user?.role === 'FACULTY'
            ? `Timetable - ${user.first_name} ${user.last_name}`
            : `Timetable - ${schedules.find(s => s.schedule_id === selectedSchedule)?.name || 'Schedule'}`;
        doc.text(title, 14, 22);
        doc.setFontSize(11);
        let subtitle = '';
        if (selectedSection) subtitle += `Section: ${selectedSection}  `;
        if (selectedCourse) {
            const cName = courses.find(c => c.course_id === selectedCourse)?.course_name || selectedCourse;
            subtitle += `Course: ${cName}  `;
        }
        if (selectedRoom) subtitle += `Room: ${selectedRoom}  `;
        if (selectedTeacher && user?.role !== 'FACULTY') {
            const tName = teachers.find(t => t.teacher_id === selectedTeacher)?.teacher_name || selectedTeacher;
            subtitle += `Teacher: ${tName}`;
        }
        if (subtitle) doc.text(subtitle, 14, 30);

        const tableColumn = ["Time", ...DAYS];
        const tableRows = [];
        SLOTS.forEach(slot => {
            const rowData = [`Slot ${slot}`];
            DAYS.forEach(day => {
                const classes = timetable[day]?.[slot] || [];
                const cellContent = classes.map(c => {
                    const isProject = c.course_name?.toLowerCase().includes('project phase');
                    const label = (c.is_elective && c.elective_group) ? `[${c.elective_group}]` : c.course_code;
                    const displayName = (c.year === 4 && c.is_elective && c.constraint_reason)
                        ? c.constraint_reason
                        : c.course_name;
                    let text = `${label}\n${displayName}`;

                    if (!c.is_elective && !isProject) {
                        text += `\n${c.room} (${c.section})`;
                    } else if (c.section) {
                        text += `\n(${c.section})`;
                    }

                    if (c.is_lab_session && !isProject && c.year !== 4) text += ' [LAB]';
                    if (isProject) text += ' [PROJECT]';
                    return text;
                }).join('\n\n');
                rowData.push(cellContent);
            });
            tableRows.push(rowData);

            if (slot === 2) {
                tableRows.push(["10:30-10:45", "INTERVAL", "INTERVAL", "INTERVAL", "INTERVAL", "INTERVAL"]);
            }
            if (slot === 5) {
                tableRows.push(["13:15-14:05", "LUNCH BREAK", "LUNCH BREAK", "LUNCH BREAK", "LUNCH BREAK", "LUNCH BREAK"]);
            }
        });

        autoTable(doc, {
            head: [tableColumn],
            body: tableRows,
            startY: subtitle ? 35 : 25,
            theme: 'grid',
            styles: { fontSize: 8, cellPadding: 2, overflow: 'linebreak' },
            headStyles: { fillColor: [124, 58, 237], textColor: 255 },
            columnStyles: { 0: { cellWidth: 20, fontStyle: 'bold' } },
            didParseCell: (data) => {
                if (data.section === 'body' && data.column.index > 0 && data.cell.raw) {
                    const cellStr = data.cell.raw.toString();
                    if (cellStr.includes('[LAB]')) {
                        data.cell.styles.fillColor = [240, 248, 255];
                    }
                    if (cellStr.includes('[PROJECT]')) {
                        data.cell.styles.fillColor = [243, 232, 255];
                    }
                    data.cell.text = data.cell.text.map(t => t.replace(' [LAB]', '').replace(' [PROJECT]', ''));
                }
            },
            didDrawCell: (data) => {
                if (data.section === 'body' && data.column.index > 0 && data.cell.raw) {
                    const rawText = data.cell.raw.toString();
                    if (rawText.includes('[LAB]')) {
                        const slotX = data.cell.x;
                        const slotY = data.cell.y;
                        const slotWidth = data.cell.width;

                        doc.setDrawColor(0, 123, 255);
                        doc.setFillColor(0, 123, 255);
                        doc.roundedRect(slotX + slotWidth - 12, slotY + 2, 10, 4, 1, 1, "FD");

                        doc.setTextColor(255, 255, 255);
                        doc.setFontSize(5);
                        doc.setFont("helvetica", "bold");
                        doc.text("LAB", slotX + slotWidth - 7, slotY + 5.2, { align: 'center' });

                        doc.setTextColor(0, 0, 0);
                        doc.setFontSize(8);
                        doc.setFont("helvetica", "normal");
                    }
                }
            }
        });
        doc.save('timetable.pdf');
    };

    // ──────────────────────────────────────────────────────────────────────────
    // DRAG-AND-DROP HANDLERS
    // ──────────────────────────────────────────────────────────────────────────

    const handleDragStart = (e, classItem, day, slot) => {
        if (!isAdminOrHOD) return;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('application/json', JSON.stringify({
            entryId: classItem.entry_id,
            lastModified: classItem.last_modified,
        }));
        setDragging({ entryId: classItem.entry_id, day, slot, lastModified: classItem.last_modified, classItem });
        setDropTargets({});
        setMoveStatus(null);
    };

    const handleDragEnd = () => {
        setDragging(null);
        setDropTargets({});
        setActiveDropCell(null);
        if (validationAbortRef.current) validationAbortRef.current = null;
    };

    const handleCellDragEnter = useCallback(async (e, day, slot) => {
        e.preventDefault();
        if (!dragging) return;

        const cellKey = `${day}-${slot}`;
        setActiveDropCell(cellKey);

        if (dropTargets[cellKey] !== undefined) return;
        if (dragging.day === day && dragging.slot === slot) {
            setDropTargets(prev => ({ ...prev, [cellKey]: { valid: true, conflicts: [] } }));
            return;
        }

        setDropTargets(prev => ({ ...prev, [cellKey]: null }));

        try {
            const res = await schedulerAPI.validateMove(dragging.entryId, day, slot);
            setDropTargets(prev => ({
                ...prev,
                [cellKey]: { valid: res.data.valid, conflicts: res.data.conflicts || [] }
            }));
        } catch {
            setDropTargets(prev => ({ ...prev, [cellKey]: { valid: false, conflicts: ['Validation failed'] } }));
        }
    }, [dragging, dropTargets]);

    const handleCellDragOver = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    };

    const handleCellDragLeave = (e, day, slot) => {
        const related = e.relatedTarget;
        if (related && e.currentTarget.contains(related)) return;
        setActiveDropCell(prev => (prev === `${day}-${slot}` ? null : prev));
    };

    const handleDrop = async (e, targetDay, targetSlot) => {
        e.preventDefault();
        if (!dragging) return;

        const cellKey = `${targetDay}-${targetSlot}`;
        const validation = dropTargets[cellKey];

        if (validation && !validation.valid) {
            setMoveStatus({ type: 'error', message: `Cannot move here: ${validation.conflicts[0] || 'Conflict detected'}` });
            setDragging(null);
            setDropTargets({});
            setActiveDropCell(null);
            return;
        }

        if (dragging.day === targetDay && dragging.slot === targetSlot) {
            setDragging(null);
            setDropTargets({});
            setActiveDropCell(null);
            return;
        }

        try {
            const response = await schedulerAPI.moveEntry({
                entry_id: dragging.entryId,
                target_day: targetDay,
                target_slot: targetSlot,
                last_modified: dragging.lastModified,
            });

            if (response.data.success) {
                setMoveStatus({ type: 'success', message: `Moved to ${targetDay} Slot ${targetSlot} ✓` });
                await loadTimetable();
            }
        } catch (err) {
            const errData = err.response?.data;
            if (err.response?.status === 409) {
                setMoveStatus({ type: 'warn', message: errData?.error || 'Concurrent edit detected — please refresh.' });
                await loadTimetable();
            } else {
                setMoveStatus({ type: 'error', message: errData?.conflicts?.[0] || errData?.error || 'Move failed' });
            }
        } finally {
            setDragging(null);
            setDropTargets({});
            setActiveDropCell(null);
        }
    };

    useEffect(() => {
        if (!moveStatus) return;
        const t = setTimeout(() => setMoveStatus(null), 5000);
        return () => clearTimeout(t);
    }, [moveStatus]);

    const getCellDropStyle = (day, slot) => {
        if (!dragging) return {};
        const cellKey = `${day}-${slot}`;
        const isActive = activeDropCell === cellKey;
        const validation = dropTargets[cellKey];

        if (!isActive && !validation) return {};
        if (validation === null) return { outline: '2px dashed #94a3b8', background: 'rgba(148,163,184,0.15)' };
        if (validation?.valid) return { outline: '2px solid #10b981', background: 'rgba(16,185,129,0.12)', boxShadow: '0 0 12px rgba(16,185,129,0.3)' };
        if (validation?.valid === false) return { outline: '2px solid #ef4444', background: 'rgba(239,68,68,0.1)', boxShadow: '0 0 12px rgba(239,68,68,0.25)' };
        return {};
    };

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <div className="fade-in">
            <div className="page-header">
                <h1 className="page-title">{user?.role === 'FACULTY' ? 'My Timetable' : 'View Timetable'}</h1>
                <p className="page-description">
                    {user?.role === 'FACULTY'
                        ? `Viewing schedule for ${user.first_name} ${user.last_name}`
                        : isAdminOrHOD
                            ? 'View & manually rearrange classes by dragging blocks to a new slot'
                            : 'View generated timetable schedules'}
                </p>
            </div>

            {moveStatus && (
                <div className={`alert ${moveStatus.type === 'success' ? 'alert-success' : moveStatus.type === 'warn' ? 'alert-info' : 'alert-error'}`} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', animation: 'fadeIn 0.3s ease', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '1.1rem' }}>{moveStatus.type === 'success' ? '✅' : moveStatus.type === 'warn' ? '⚠️' : '❌'}</span>
                    {moveStatus.message}
                </div>
            )}

            {isAdminOrHOD && timetable && (
                <div style={{ display: 'flex', gap: '1.25rem', alignItems: 'center', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Drag & Drop:</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}><span style={{ width: 12, height: 12, borderRadius: 3, background: '#059669', display: 'inline-block', flexShrink: 0 }} /> Valid drop zone</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}><span style={{ width: 12, height: 12, borderRadius: 3, background: '#dc2626', display: 'inline-block', flexShrink: 0 }} /> Conflict — drop blocked</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}><span style={{ width: 12, height: 12, borderRadius: 3, border: '1.5px dashed var(--text-muted)', display: 'inline-block', flexShrink: 0 }} /> Validating…</span>
                </div>
            )}

            <div className="card">
                <div className="filters">
                    <div className="filter-group">
                        <label className="filter-label">Select Schedule</label>
                        <select className="filter-select" value={selectedSchedule} onChange={(e) => setSelectedSchedule(e.target.value)}>
                            <option value="">-- Select Schedule --</option>
                            {schedules.map((schedule) => (
                                <option key={schedule.schedule_id} value={schedule.schedule_id}>
                                    {schedule.name} ({schedule.year ? `Year ${schedule.year}` : 'All Years'}, {schedule.semester})
                                </option>
                            ))}
                        </select>
                        {(selectedSchedule && isAdminOrHOD) && (
                            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                                <button className="btn btn-success" onClick={handleVerifySchedule} disabled={verifying} style={{ flex: 1 }}>{verifying ? 'Verifying...' : 'Verify Schedule'}</button>
                                <button className="btn btn-danger" onClick={async () => {
                                    if (window.confirm("Are you sure you want to delete this schedule?")) {
                                        try {
                                            await scheduleAPI.delete(selectedSchedule);
                                            alert("Schedule deleted successfully.");
                                            setSelectedSchedule('');
                                            setTimetable(null);
                                            loadInitialData();
                                        } catch (err) { alert("Error deleting schedule"); }
                                    }
                                }} style={{ flex: 1 }}>Delete Schedule</button>
                                {user?.role === 'ADMIN' && (
                                    <button className="btn" onClick={handlePublishSchedule} disabled={publishing || isPublished} style={{ flex: 1, background: isPublished ? 'var(--text-muted)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff', border: 'none', cursor: isPublished ? 'not-allowed' : 'pointer', fontWeight: 600 }}>
                                        {publishing ? 'Publishing...' : isPublished ? '✓ Published' : '🚀 Publish Schedule'}
                                    </button>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="filter-group">
                        <label className="filter-label">{user?.role === 'FACULTY' ? 'Filter My Schedule by Section' : 'Filter by Section'}</label>
                        <select className="filter-select" value={selectedSection} onChange={(e) => setSelectedSection(e.target.value)}>
                            <option value="">All Sections</option>
                            {sections.map((section) => (<option key={section.class_id} value={section.class_id}>{section.class_id}</option>))}
                        </select>
                    </div>

                    {isAdminOrHOD && (
                        <div className="filter-group">
                            <label className="filter-label">Filter by Teacher</label>
                            <select className="filter-select" value={selectedTeacher} onChange={(e) => setSelectedTeacher(e.target.value)}>
                                <option value="">All Teachers</option>
                                {teachers.map((teacher) => (<option key={teacher.teacher_id} value={teacher.teacher_id}>{teacher.teacher_name}</option>))}
                            </select>
                        </div>
                    )}

                    <div className="filter-group">
                        <label className="filter-label">Filter by Course</label>
                        <select className="filter-select" value={selectedCourse} onChange={(e) => setSelectedCourse(e.target.value)}>
                            <option value="">All Courses</option>
                            {courses.map((course) => (<option key={course.course_id} value={course.course_id}>[{course.course_id}] {course.course_name}</option>))}
                        </select>
                    </div>

                    <div className="filter-group">
                        <label className="filter-label">Filter by Room</label>
                        <select className="filter-select" value={selectedRoom} onChange={(e) => setSelectedRoom(e.target.value)}>
                            <option value="">All Rooms</option>
                            {rooms.map((room) => (<option key={room.room_id} value={room.room_id}>{room.room_id} ({room.block})</option>))}
                        </select>
                    </div>
                </div>
            </div>

            {loading && (<div className="loading"><div className="spinner"></div><p>Loading timetable...</p></div>)}

            {!loading && timetable && (
                <div className="card">
                    <div className="card-header">
                        <h2 className="card-title">Weekly Schedule</h2>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                            <button className="btn btn-primary" onClick={() => setShowElectiveModal(true)} style={{ fontSize: '0.875rem', padding: '0.25rem 0.5rem', backgroundColor: '#eab308', borderColor: '#eab308' }}>✨ View Elective Handlers</button>
                            <button className="btn btn-primary" onClick={handleDownloadPDF} style={{ fontSize: '0.875rem', padding: '0.25rem 0.5rem' }}>Download PDF</button>
                            {user?.role === 'FACULTY' && <span className="badge-pill badge-primary">Faculty View</span>}
                            {(selectedTeacher && user?.role !== 'FACULTY') && <span className="badge-pill badge-info">Teacher: {teachers.find(t => t.teacher_id === selectedTeacher)?.teacher_name || selectedTeacher}</span>}
                            {selectedCourse && <span className="badge-pill badge-info">Course: {selectedCourse}</span>}
                            {selectedRoom && <span className="badge-pill badge-info">Room: {selectedRoom}</span>}
                        </div>
                    </div>

                    <div className="timetable-grid" style={{ userSelect: dragging ? 'none' : 'auto' }}>
                        <div className="grid-header">Time</div>
                        {DAYS.map((day) => (<div key={day} className="grid-header">{day}</div>))}

                        {SLOTS.map((slot) => (
                            <React.Fragment key={`slot-row-${slot}`}>
                                <div key={`time-${slot}`} className="grid-time">
                                    <div style={{ fontWeight: 700, color: 'var(--primary)' }}>Slot {slot}</div>
                                    <div style={{ fontSize: '0.65rem', opacity: 0.7 }}>{Object.values(timetable || {}).find(d => d[slot])?.[slot]?.[0]?.time || ''}</div>
                                </div>
                                {DAYS.map((day) => {
                                    const cellKey = `${day}-${slot}`;
                                    const validation = dropTargets[cellKey];
                                    const dropStyle = getCellDropStyle(day, slot);
                                    const hasConflictHint = validation?.valid === false && activeDropCell === cellKey;

                                    return (
                                        <div
                                            key={cellKey}
                                            className="grid-cell"
                                            style={{ ...dropStyle, transition: 'outline 0.15s ease, background 0.15s ease, box-shadow 0.15s ease', position: 'relative' }}
                                            onDragEnter={(e) => handleCellDragEnter(e, day, slot)}
                                            onDragOver={handleCellDragOver}
                                            onDragLeave={(e) => handleCellDragLeave(e, day, slot)}
                                            onDrop={(e) => handleDrop(e, day, slot)}
                                        >
                                            {hasConflictHint && validation?.conflicts?.length > 0 && (
                                                <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: '#dc2626', color: '#ffffff', borderRadius: '0.5rem', padding: '0.4rem 0.75rem', fontSize: '0.72rem', fontWeight: 700, zIndex: 50, pointerEvents: 'none', whiteSpace: 'nowrap', width: 'max-content', boxShadow: '0 4px 16px rgba(0,0,0,0.45)', border: '1.5px solid #ef4444', letterSpacing: '0.01em' }}>⛔ {validation.conflicts[0]}</div>
                                            )}
                                            {activeDropCell === cellKey && validation?.valid === true && (
                                                <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: '#059669', color: '#ffffff', borderRadius: '0.5rem', padding: '0.35rem 0.7rem', fontSize: '0.72rem', fontWeight: 700, zIndex: 50, pointerEvents: 'none', whiteSpace: 'nowrap', boxShadow: '0 4px 16px rgba(0,0,0,0.35)', border: '1.5px solid #10b981', letterSpacing: '0.01em' }}>✓ Drop to move here</div>
                                            )}

                                            {(() => {
                                                const items = timetable[day]?.[slot] || [];
                                                const groupedItems = [];
                                                const isTeacherView = Boolean(selectedTeacher || user?.role === 'FACULTY');
                                                const isCourseView = Boolean(selectedCourse);

                                                if (isTeacherView || isCourseView) {
                                                    const courseMap = new Map();
                                                    items.forEach(item => {
                                                        const key = `${item.course_id}-${item.session_type}`;
                                                        if (courseMap.has(key)) {
                                                            const existing = courseMap.get(key);
                                                            if (!existing.section.split(', ').includes(item.section)) existing.section += `, ${item.section}`;
                                                            if (existing.teacher_name && item.teacher_name && !existing.teacher_name.split(', ').includes(item.teacher_name)) existing.teacher_name += `, ${item.teacher_name}`;
                                                            if (existing.room && item.room && !existing.room.split(', ').includes(item.room)) existing.room += `, ${item.room}`;
                                                        } else { courseMap.set(key, { ...item }); }
                                                    });
                                                    groupedItems.push(...Array.from(courseMap.values()));
                                                } else {
                                                    const electiveGroupsSeen = new Set();
                                                    const groupCounts = {};
                                                    items.forEach(item => { if (item.is_elective && item.elective_group) groupCounts[item.elective_group] = (groupCounts[item.elective_group] || 0) + 1; });

                                                    items.forEach(item => {
                                                        if (item.is_elective && item.elective_group && groupCounts[item.elective_group] > 1) {
                                                            if (!electiveGroupsSeen.has(item.elective_group)) {
                                                                electiveGroupsSeen.add(item.elective_group);
                                                                const groupItems = items.filter(i => i.is_elective && i.elective_group === item.elective_group);
                                                                const uniqueCourses = [...new Set(groupItems.map(i => i.course_name))].filter(Boolean).join(' / ');
                                                                const uniqueTeachers = [...new Set(groupItems.map(i => i.teacher_name))].filter(Boolean).join(', ');
                                                                const uniqueRooms = [...new Set(groupItems.map(i => i.room))].filter(Boolean).join(', ');

                                                                groupedItems.push({
                                                                    ...item, is_group_header: true, course_code: item.elective_group, course_name: uniqueCourses || (item.elective_type ? `${item.elective_type} Electives` : 'Elective Group'), teacher_name: uniqueTeachers, room: uniqueRooms
                                                                });
                                                            }
                                                        } else { groupedItems.push(item); }
                                                    });
                                                }

                                                return groupedItems.map((classItem, idx) => {
                                                    const isDraggingThis = dragging?.entryId === classItem.entry_id;

                                                    // Identify Special Courses (Electives, Projects, AVPs)
                                                    const safeCourseName = classItem.course_name || '';
                                                    const safeCourseCode = classItem.course_code || '';
                                                    
                                                    // Identify Special Courses (Electives, Projects, AVPs)
                                                    const isProject = safeCourseName.toLowerCase().includes('project phase');
                                                    const isAVP = safeCourseName.toLowerCase().includes('avp') || safeCourseCode.toLowerCase().includes('avp');
                                                    const isSpecialCourse = classItem.is_elective || isProject || isAVP;
                                                    // -------------------------------------------------------------------------
                                                                                                
                                                    const sessionTypeClass = isProject ? 'project' : (classItem.session_type?.toLowerCase() || 'theory');
                                                    const isTeacherHighlight = classItem.teacher_id === (user?.teacher_id || selectedTeacher);
                                                    return (
                                                        <div
                                                            key={idx}
                                                            className={`class-block ${sessionTypeClass} ${isTeacherHighlight ? 'highlight-teacher' : ''}`}
                                                            // Keep it technically draggable so we can intercept the drag event to show the warning
                                                            draggable={isAdminOrHOD && !!classItem.entry_id}
                                                            onDragStart={(e) => {
                                                                if (isAdminOrHOD && isSpecialCourse) {
                                                                    e.preventDefault(); // Stop the drag
                                                                    setMoveStatus({
                                                                        type: 'warn',
                                                                        message: 'Drag-and-drop is disabled for Electives, Projects, and AVP courses.'
                                                                    });
                                                                    return;
                                                                }
                                                                handleDragStart(e, classItem, day, slot);
                                                            }}
                                                            onDragEnd={handleDragEnd}
                                                            style={{
                                                                cursor: isAdminOrHOD ? (isSpecialCourse ? 'not-allowed' : 'grab') : 'default',
                                                                opacity: isDraggingThis ? 0.35 : 1,
                                                                transition: 'opacity 0.2s ease, transform 0.2s ease',
                                                                transform: isDraggingThis ? 'scale(0.95)' : undefined,
                                                                padding: '10px',
                                                                minHeight: classItem.is_lab_session ? '100%' : 'auto',
                                                                position: 'relative',
                                                                flexShrink: 0
                                                            }}
                                                            title={isAdminOrHOD ? (isSpecialCourse ? 'Drag disabled for this course type' : `Drag to move ${classItem.course_code} (${classItem.section})`) : undefined}
                                                        >
                                                            {isAdminOrHOD && !isSpecialCourse && (
                                                                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: '4px', letterSpacing: '1px', userSelect: 'none' }}>⠿</div>
                                                            )}
                                                            {classItem.is_lab_session && !isProject && classItem.year !== 4 && (
                                                                <div style={{ position: 'absolute', top: '8px', right: '8px', backgroundColor: '#007bff', color: 'white', fontSize: '0.55rem', fontWeight: 800, padding: '2px 6px', borderRadius: '8px', textTransform: 'uppercase', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', zIndex: 10 }}>LAB</div>
                                                            )}
                                                            <div className="class-content" style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                                                <div className="class-code" style={{ fontWeight: 800, fontSize: '0.85rem' }}>
                                                                    {classItem.is_elective && classItem.elective_group ? `[${classItem.elective_group}]` : classItem.course_code}
                                                                </div>
                                                                <div className="class-name" style={{ fontSize: '0.7rem', fontWeight: 600, opacity: 0.9, lineHeight: '1.2' }}>
                                                                    {classItem.year === 4 && classItem.is_elective && classItem.constraint_reason ? classItem.constraint_reason : classItem.course_name}
                                                                </div>

                                                                {!classItem.is_elective && !isProject && (
                                                                    <>
                                                                        <div className="class-teacher" style={{ fontSize: '0.65rem', marginTop: '2px', wordBreak: 'break-word', lineHeight: '1.2' }}>{classItem.teacher_name}</div>
                                                                        <div className="class-room-sec" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '2px', fontSize: '0.6rem', fontWeight: 700, marginTop: '4px' }}>
                                                                            <span>Room: {classItem.room}</span><span>Sec: {classItem.section}</span>
                                                                        </div>
                                                                    </>
                                                                )}

                                                                {(classItem.is_elective || isProject) && (
                                                                    <div className="class-room-sec" style={{ display: 'flex', justifyContent: 'flex-end', flexWrap: 'wrap', fontSize: '0.6rem', fontWeight: 700, marginTop: '4px' }}>
                                                                        <span>{classItem.section}</span>
                                                                    </div>
                                                                )}
                                                            </div>

                                                            {isAdminOrHOD && (
                                                                <button
                                                                    className="btn btn-primary"
                                                                    style={{ fontSize: '0.6rem', padding: '2px 6px', marginTop: '8px', width: '100%', background: 'rgba(0,0,0,0.05)', color: 'inherit', border: '1px solid currentColor', fontWeight: 'bold' }}
                                                                    onClick={(e) => { e.stopPropagation(); handleOpenSwapModal(classItem); }}
                                                                >
                                                                    Swap Faculty
                                                                </button>
                                                            )}
                                                        </div>
                                                    );
                                                })
                                            })()}
                                        </div>
                                    );
                                })}

                                {slot === 2 && (
                                    <>
                                        <div className="grid-break-time">10:30-10:45</div>
                                        {DAYS.map(day => (<div key={`interval-${day}`} className="grid-break">INTERVAL</div>))}
                                    </>
                                )}
                                {slot === 5 && (
                                    <>
                                        <div className="grid-break-time">13:15-14:05</div>
                                        {DAYS.map(day => (<div key={`lunch-${day}`} className="grid-break">LUNCH BREAK</div>))}
                                    </>
                                )}
                            </React.Fragment>
                        ))}
                    </div>
                </div>
            )}

            {!loading && !timetable && selectedSchedule && (
                <div className="alert alert-info">{user?.role === 'FACULTY' ? "You have no classes assigned in this schedule selection." : "No timetable data available for this selection."}</div>
            )}

            {!selectedSchedule && (<div className="alert alert-info">Please select a schedule to view the timetable.</div>)}

            {/* Swap Faculty Modal */}
            {showSwapModal && swapTarget && (
                <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100 }}>
                    <div className="modal-content" style={{ background: 'white', padding: '2rem', borderRadius: '12px', width: '90%', maxWidth: '500px', boxShadow: 'var(--shadow-lg)' }}>
                        <h2 style={{ marginBottom: '1rem', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>{user?.role === 'ADMIN' ? '🔄 Direct Faculty Swap' : '🔄 Request Faculty Swap'}</h2>
                        <div style={{ marginBottom: '1.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                            {user?.role === 'ADMIN' ? `You are directly replacing ${swapTarget.currentTeacherName} with a new teacher across ALL slots.` : `This will request to replace ${swapTarget.currentTeacherName} with a new teacher for ALL scheduled slots of ${swapTarget.courseId} for ${swapTarget.sectionId}.`}
                        </div>
                        <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                            <label className="filter-label" style={{ display: 'block', marginBottom: '8px', fontWeight: 600 }}>Select Replacement Teacher</label>
                            {loadingFaculty ? (
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Finding available faculty...</div>
                            ) : (
                                <select className="filter-select" style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #ddd' }} value={selectedNewTeacher} onChange={(e) => setSelectedNewTeacher(e.target.value)}>
                                    <option value="">-- Choose available teacher --</option>
                                    {availableFaculty.length === 0 ? (<option disabled>No other teachers available at this time</option>) : (
                                        availableFaculty.map(t => (<option key={t.teacher_id} value={t.teacher_id}>{t.teacher_name} ({t.department})</option>))
                                    )}
                                </select>
                            )}
                        </div>
                        {user?.role === 'HOD' && (
                            <div className="form-group" style={{ marginBottom: '1.5rem' }}>
                                <label className="filter-label" style={{ display: 'block', marginBottom: '8px', fontWeight: 600 }}>Reason for Swap (Notes for Admin)</label>
                                <textarea className="filter-select" style={{ width: '100%', height: '80px', padding: '10px', borderRadius: '8px', border: '1px solid #ddd', resize: 'none' }} placeholder="E.g., Teacher on medical leave, urgent duty..." value={swapNotes} onChange={(e) => setSwapNotes(e.target.value)} />
                            </div>
                        )}
                        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" style={{ padding: '8px 16px' }} onClick={() => setShowSwapModal(false)}>Cancel</button>
                            <button className="btn btn-primary" style={{ padding: '8px 16px', background: 'var(--primary)', color: 'white', border: 'none', borderRadius: '6px', cursor: (!selectedNewTeacher || submittingSwap) ? 'not-allowed' : 'pointer', opacity: (!selectedNewTeacher || submittingSwap) ? 0.7 : 1 }} disabled={!selectedNewTeacher || submittingSwap} onClick={handleSubmitSwapRequest}>{submittingSwap ? (user?.role === 'ADMIN' ? 'Applying...' : 'Submitting...') : (user?.role === 'ADMIN' ? 'Apply Swap' : 'Submit Request')}</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Verification Modal */}
            {showVerificationModal && verificationResult && (
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0, 0, 0, 0.5)', backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, animation: 'fadeIn 0.3s ease-out' }}>
                    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--card-border)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xl)', padding: 'var(--spacing-lg)', maxWidth: '480px', width: '90%', maxHeight: '80vh', overflow: 'auto' }}>
                        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>{verificationResult.valid ? '✅ Schedule Verified' : '⚠️ Issues Detected'}</h3>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: 'var(--spacing-md)' }}>{verificationResult.valid ? 'No conflicts found. This schedule is ready to publish.' : `${verificationResult.conflicts.length} conflict(s) need attention before publishing.`}</p>
                        {!verificationResult.valid && (
                            <div style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-sm) var(--spacing-md)', marginBottom: 'var(--spacing-lg)', maxHeight: '220px', overflowY: 'auto', border: '1px solid var(--border)' }}>
                                {verificationResult.conflicts.map((conflict, idx) => (
                                    <div key={idx} style={{ padding: '0.5rem 0', borderBottom: idx < verificationResult.conflicts.length - 1 ? '1px solid var(--border)' : 'none', fontSize: '0.85rem', color: 'var(--text-primary)' }}>{conflict}</div>
                                ))}
                            </div>
                        )}
                        <button className="btn btn-primary" onClick={() => setShowVerificationModal(false)} style={{ width: '100%' }}>Close</button>
                    </div>
                </div>
            )}

            {/* Elective Mapping Modal */}
            {showElectiveModal && (
                <ElectiveMappingModal isOpen={showElectiveModal} onClose={() => setShowElectiveModal(false)} scheduleId={selectedSchedule || ''} />
            )}
        </div>
    );
}

export default ViewTimetable;