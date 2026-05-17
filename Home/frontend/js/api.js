/**
 * API Layer — Fetch wrapper with JWT token management
 */

const API_BASE = '/api';

// ─── Token Management ───

function getTokens() {
    const tokens = localStorage.getItem('tokens');
    return tokens ? JSON.parse(tokens) : null;
}

function saveTokens(tokens) {
    localStorage.setItem('tokens', JSON.stringify(tokens));
}

function getAccessToken() {
    const tokens = getTokens();
    return tokens ? tokens.access : null;
}

function clearAuth() {
    localStorage.removeItem('tokens');
    localStorage.removeItem('user');
}

function saveUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
}

function getUser() {
    const u = localStorage.getItem('user');
    return u ? JSON.parse(u) : null;
}

function isLoggedIn() {
    return !!getAccessToken();
}

// ─── Fetch Wrapper ───

async function apiCall(endpoint, options = {}, isFormData = false) {
    const url = `${API_BASE}${endpoint}`;
    const headers = { ...options.headers };
    
    if (!isFormData) {
        headers['Content-Type'] = 'application/json';
    }

    const token = getAccessToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    try {
        let response = await fetch(url, {
            ...options,
            headers,
        });

        // If 401 (token expired), try to refresh
        if (response.status === 401 && token) {
            const refreshed = await refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${getAccessToken()}`;
                response = await fetch(url, { ...options, headers });
            } else {
                clearAuth();
                window.location.href = '/';
                return null;
            }
        }
        let data = null;
        if (response.status !== 204) {
            data = await response.json();
        }

        if (!response.ok) {
            throw { status: response.status, data };
        }

        return data;
    } catch (err) {
        if (err.status) throw err;
        console.error('API Error:', err);
        throw { status: 0, data: { error: 'Network error. Please try again.' } };
    }
}

async function refreshToken() {
    const tokens = getTokens();
    if (!tokens || !tokens.refresh) return false;

    try {
        const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: tokens.refresh }),
        });

        if (response.ok) {
            const data = await response.json();
            tokens.access = data.access;
            saveTokens(tokens);
            return true;
        }
        return false;
    } catch {
        return false;
    }
}

// ─── Auth API ───

async function checkVoterRoll(voter_id, email) {
    return apiCall('/auth/check-voter-roll/', { method: 'POST', body: JSON.stringify({ voter_id, email }) });
}
async function sendVoterOTP(voter_id, email) {
    return apiCall('/auth/send-voter-otp/', { method: 'POST', body: JSON.stringify({ voter_id, email }) });
}
async function verifyVoterOTP(voter_id, email, otp) {
    return apiCall('/auth/verify-voter-otp/', { method: 'POST', body: JSON.stringify({ voter_id, email, otp }) });
}
async function register(formData) {
    return apiCall('/auth/register/', {
        method: 'POST',
        body: JSON.stringify(formData),
    });
}

async function login(email, password) {
    return apiCall('/auth/login/', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
    });
}

async function verifyOTP(email, code) {
    return apiCall('/auth/otp-verify/', {
        method: 'POST',
        body: JSON.stringify({ email, code }),
    });
}

async function getProfile() {
    return apiCall('/auth/profile/');
}

async function updateProfile(data) {
    return apiCall('/auth/profile/', {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}

// ─── Elections API ───

async function getElections(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return apiCall(`/elections/elections/${qs ? '?' + qs : ''}`);
}

async function getActiveElections() {
    return apiCall('/elections/elections/active/');
}

async function getEligibleElections() {
    return apiCall('/elections/elections/eligible/');
}

async function getElection(id) {
    return apiCall(`/elections/elections/${id}/`);
}

async function createElection(data) {
    return apiCall('/elections/elections/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

async function updateElection(id, data) {
    return apiCall(`/elections/elections/${id}/`, {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}

async function deleteElection(id) {
    return apiCall(`/elections/elections/${id}/`, { method: 'DELETE' });
}

async function approveElection(id) {
    return apiCall(`/elections/elections/${id}/approve/`, { method: 'POST' });
}

async function rejectElection(id) {
    return apiCall(`/elections/elections/${id}/reject/`, { method: 'POST' });
}

// ─── Candidates API ───

async function getCandidates(electionId) {
    return apiCall(`/elections/candidates/?election=${electionId}`);
}

async function createCandidate(data) {
    const isFormData = data instanceof FormData;
    return apiCall('/elections/candidates/', {
        method: 'POST',
        body: isFormData ? data : JSON.stringify(data),
    }, isFormData);
}

async function updateCandidate(id, data) {
    const isFormData = data instanceof FormData;
    return apiCall(`/elections/candidates/${id}/`, {
        method: 'PATCH',
        body: isFormData ? data : JSON.stringify(data),
    }, isFormData);
}

async function deleteCandidate(id) {
    return apiCall(`/elections/candidates/${id}/`, { method: 'DELETE' });
}

// ─── Voting API ───

async function castVote(electionId, candidateId, otpCode) {
    return apiCall('/voting/cast/', {
        method: 'POST',
        body: JSON.stringify({
            election_id: electionId,
            candidate_id: candidateId,
            otp_code: otpCode,
        }),
    });
}

async function sendVoteOTP() {
    return apiCall('/voting/send-otp/', {
        method: 'POST',
        body: JSON.stringify({})
    });
}

async function getVoteStatus(electionId) {
    return apiCall(`/voting/status/${electionId}/`);
}

// ─── Results API ───

async function getResults(electionId) {
    return apiCall(`/results/${electionId}/`);
}

// ─── Notifications API ───

async function getNotifications() {
    return apiCall('/notifications/');
}

async function getUnreadCount() {
    return apiCall('/notifications/unread-count/');
}

async function markNotificationRead(id) {
    return apiCall(`/notifications/${id}/read/`, { method: 'POST' });
}

async function markAllRead() {
    return apiCall('/notifications/read-all/', { method: 'POST' });
}

// ─── Password Reset API ───

async function requestPasswordReset(email) {
    return apiCall('/auth/password-reset-request/', {
        method: 'POST',
        body: JSON.stringify({ email }),
    });
}

async function confirmPasswordReset(email, otp, password) {
    return apiCall('/auth/password-reset-confirm/', {
        method: 'POST',
        body: JSON.stringify({ email, otp, password }),
    });
}

// ─── Admin API ───

async function getUsers(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return apiCall(`/auth/users/${qs ? '?' + qs : ''}`);
}

// ─── Accounts API ───

async function getDashboardStats() {
    return apiCall('/auth/dashboard-stats/');
}

async function getVoterRoll() {
    return apiCall('/auth/voter-roll/');
}
async function createVoterRoll(data) {
    return apiCall('/auth/voter-roll/', { method: 'POST', body: JSON.stringify(data) });
}
async function deleteVoterRoll(id) {
    return apiCall(`/auth/voter-roll/${id}/`, { method: 'DELETE' });
}
async function updateVoterRoll(id, data) {
    return apiCall(`/auth/voter-roll/${id}/`, { method: 'PUT', body: JSON.stringify(data) });
}

async function getVillageAdmins() {
    return apiCall('/auth/village-admins/');
}
async function createVillageAdmin(data) {
    return apiCall('/auth/village-admins/', { method: 'POST', body: JSON.stringify(data) });
}
async function deleteVillageAdmin(id) {
    return apiCall(`/auth/village-admins/${id}/`, { method: 'DELETE' });
}

// ─── Registration Request API ───

async function submitRegistrationRequest(data) {
    return apiCall('/auth/registration-requests/submit/', {
        method: 'POST', body: JSON.stringify(data)
    });
}
async function getRegistrationRequests(status) {
    return apiCall(`/auth/registration-requests/${status ? '?status='+status : ''}`);
}
async function forwardRegistrationRequest(id, notes) {
    return apiCall(`/auth/registration-requests/${id}/forward/`, {
        method: 'POST', body: JSON.stringify({ notes })
    });
}
async function approveRegistrationRequest(id, notes) {
    return apiCall(`/auth/registration-requests/${id}/approve/`, {
        method: 'POST', body: JSON.stringify({ notes })
    });
}
async function rejectRegistrationRequest(id, notes) {
    return apiCall(`/auth/registration-requests/${id}/reject/`, {
        method: 'POST', body: JSON.stringify({ notes })
    });
}

// ─── UI Helpers ───

function showToast(message, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `alert alert-${type}`;
    toast.innerHTML = `
        <span>${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
        <span>${message}</span>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function showLoading() {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.id = 'loading-overlay';
    overlay.innerHTML = '<div class="spinner"></div><p>Loading...</p>';
    document.body.appendChild(overlay);
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.remove();
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = '/';
        return false;
    }
    return true;
}

function requireAdmin() {
    const user = getUser();
    if (!user || user.role !== 'admin') {
        showToast('Access denied. Admin only.', 'error');
        window.location.href = '/dashboard/';
        return false;
    }
    return true;
}
