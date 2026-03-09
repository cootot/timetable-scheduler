/**
 * API Service for M3 Timetable System
 * 
 * Centralized API calls to Django backend
 * 
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 * Sprint: 1
 */

import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to attach token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for handling token expiration and refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Prevent infinite loops
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
            refresh: refreshToken
          });

          const newAccessToken = response.data.access;
          localStorage.setItem('access_token', newAccessToken);

          // Update header and retry
          api.defaults.headers.common['Authorization'] = `Bearer ${newAccessToken}`;
          originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;

          return api(originalRequest);
        }
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError);
        // Clear tokens and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Core Data APIs
export const teacherAPI = {
  getAll: () => api.get('/teachers/'),
  getById: (id) => api.get(`/teachers/${id}/`),
  create: (data) => api.post('/teachers/', data),
  update: (id, data) => api.put(`/teachers/${id}/`, data),
  delete: (id) => api.delete(`/teachers/${id}/`),
  byDepartment: (dept) => api.get(`/teachers/by_department/?department=${dept}`),
};

export const courseAPI = {
  getAll: () => api.get('/courses/'),
  getById: (id) => api.get(`/courses/${id}/`),
  create: (data) => api.post('/courses/', data),
  update: (id, data) => api.put(`/courses/${id}/`, data),
  delete: (id) => api.delete(`/courses/${id}/`),
  byYear: (year) => api.get(`/courses/by_year/?year=${year}`),
  bySemester: (sem) => api.get(`/courses/by_semester/?semester=${sem}`),
  byDepartment: (dept) => api.get(`/courses/by_department/?department=${dept}`),
};

export const roomAPI = {
  getAll: () => api.get('/rooms/'),
  getById: (id) => api.get(`/rooms/${id}/`),
  create: (data) => api.post('/rooms/', data),
  update: (id, data) => api.put(`/rooms/${id}/`, data),
  delete: (id) => api.delete(`/rooms/${id}/`),
  byType: (type) => api.get(`/rooms/by_type/?type=${type}`),
};

export const sectionAPI = {
  getAll: () => api.get('/sections/'),
  getById: (id) => api.get(`/sections/${id}/`),
  create: (data) => api.post('/sections/', data),
  update: (id, data) => api.put(`/sections/${id}/`, data),
  delete: (id) => api.delete(`/sections/${id}/`),
  byYear: (year) => api.get(`/sections/by_year/?year=${year}`),
  byDepartment: (dept) => api.get(`/sections/by_department/?department=${dept}`),
};

export const teacherCourseMappingAPI = {
  getAll: () => api.get('/teacher-course-mappings/'),
  getById: (id) => api.get(`/teacher-course-mappings/${id}/`),
  create: (data) => api.post('/teacher-course-mappings/', data),
  update: (id, data) => api.put(`/teacher-course-mappings/${id}/`, data),
  delete: (id) => api.delete(`/teacher-course-mappings/${id}/`),
  byTeacher: (teacherId) => api.get(`/teacher-course-mappings/by_teacher/?teacher_id=${teacherId}`),
};

export const timeslotAPI = {
  getAll: () => api.get('/timeslots/'),
  getById: (id) => api.get(`/timeslots/${id}/`),
  create: (data) => api.post('/timeslots/', data),
  update: (id, data) => api.put(`/timeslots/${id}/`, data),
  delete: (id) => api.delete(`/timeslots/${id}/`),
  byDay: (day) => api.get(`/timeslots/by_day/?day=${day}`),
};

export const scheduleAPI = {
  getAll: () => api.get('/schedules/'),
  getById: (id) => api.get(`/schedules/${id}/`),
  create: (data) => api.post('/schedules/', data),
  delete: (id) => api.delete(`/schedules/${id}/`),
  getEntries: (id) => api.get(`/schedules/${id}/entries/`),
  getConflicts: (id) => api.get(`/schedules/${id}/conflicts/`),
  getFilters: (id) => api.get(`/schedules/${id}/filters/`),
  getAvailableFaculty: (id, courseId, sectionId) =>
    api.get(`/schedules/${id}/available_faculty/?course_id=${courseId}&section_id=${sectionId}`),
  swapFaculty: (id, courseId, sectionId, newTeacherId) =>
    api.post(`/schedules/${id}/swap_faculty/`, {
      course_id: courseId,
      section_id: sectionId,
      new_teacher_id: newTeacherId
    }),
};



// Faculty APIs
export const facultyAPI = {
  getMySchedule: (scheduleId) => {
    let url = '/scheduler/my-schedule';
    if (scheduleId) url += `?schedule_id=${scheduleId}`;
    return api.get(url);
  },
};

// Scheduler APIs
export const schedulerAPI = {
  generate: (data) => api.post('/scheduler/generate', data),
  getWorkload: (scheduleId) => api.get(`/scheduler/analytics/workload?schedule_id=${scheduleId}`),
  getRoomUtilization: (scheduleId) => api.get(`/scheduler/analytics/rooms?schedule_id=${scheduleId}`),
  getTimetable: (scheduleId, section = null, teacher = null, course = null, room = null) => {
    let url = `/scheduler/timetable?schedule_id=${scheduleId}`;
    if (section) url += `&section=${section}`;
    if (teacher) url += `&teacher=${teacher}`;
    if (course) url += `&course=${course}`;
    if (room) url += `&room=${room}`;
    return api.get(url);
  },
  validateSchedule: (scheduleId) => api.get(`/scheduler/validate/${scheduleId}/`),
  validateMove: (entryId, targetDay, targetSlot) =>
    api.get(`/scheduler/validate-move?entry_id=${entryId}&target_day=${targetDay}&target_slot=${targetSlot}`),
  moveEntry: (data) => api.post('/scheduler/move-entry', data),
  getStatus: (scheduleId) => api.get(`/scheduler/status/${scheduleId}/`),
  publish: (scheduleId) => api.post(`/scheduler/publish/${scheduleId}/`),
};

// System Health & Backup APIs
export const systemAPI = {
  getInfo: () => api.get('/system/info/'),
  listBackups: () => api.get('/system/backups/'),
  createBackup: (label = '') => api.post('/system/backups/create/', { label }),
  restoreBackup: (filename) => api.post(`/system/restore/${filename}/`),
  deleteBackup: (filename) => api.delete(`/system/backups/${filename}/`),
  resetSemester: (data) => api.post('/system/reset-semester/', data),
};

export const auditLogAPI = {
  getAll: () => api.get('/audit-logs/'),
  getById: (id) => api.get(`/audit-logs/${id}/`),
};

export const userAPI = {
  getAll: () => api.get('/auth/users/'),
  delete: (id) => api.delete(`/auth/users/${id}/`),
};

export const changeRequestAPI = {
  getAll: () => api.get('/change-requests/'),
  getById: (id) => api.get(`/change-requests/${id}/`),
  create: (data) => api.post('/change-requests/', data),
  approve: (id, admin_notes = '') => api.post(`/change-requests/${id}/approve/`, { admin_notes }),
  reject: (id, admin_notes = '') => api.post(`/change-requests/${id}/reject/`, { admin_notes }),
  getPendingCount: () => api.get('/change-requests/pending_count/'),
};

export const notificationAPI = {
  getAll: () => api.get('/notifications/'),
  markRead: (id) => api.post(`/notifications/${id}/mark_read/`),
  markAllRead: () => api.post('/notifications/mark_all_read/'),
  getUnreadCount: () => api.get('/notifications/unread_count/'),
};

export default api;
