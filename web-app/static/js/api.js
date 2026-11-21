/**
 * Taj Banjara Hotel — Management System
 * API Client with CSRF token management and error handling
 * Project Owner & Sole Developer: Mohd Shahid Moin Uddin
 */

(function (window) {
  'use strict';

  let csrfToken = null;

  async function fetchCsrfToken() {
    try {
      const res = await fetch('/api/csrf-token', { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json();
        csrfToken = data.csrf_token;
        return csrfToken;
      }
    } catch (err) {
      console.error('Failed to retrieve CSRF token:', err);
    }
    return null;
  }

  async function request(url, options = {}, isRetry = false) {
    const opts = { ...options };
    opts.credentials = 'same-origin';
    opts.headers = { ...(opts.headers || {}) };

    const method = (opts.method || 'GET').toUpperCase();
    const needsCsrf = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method);

    if (needsCsrf) {
      if (!csrfToken) {
        await fetchCsrfToken();
      }
      if (csrfToken) {
        opts.headers['X-CSRF-Token'] = csrfToken;
      }
    }

    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }

    let response;
    try {
      response = await fetch(url, opts);
    } catch (netErr) {
      throw new Error('Network error: Unable to reach hotel server.');
    }

    // If 403 due to CSRF failure and not retried yet, refresh token and retry
    if (response.status === 403 && needsCsrf && !isRetry) {
      await fetchCsrfToken();
      return request(url, options, true);
    }

    let data;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      data = { message: text };
    }

    if (!response.ok) {
      const errorMsg = (data && (data.error || data.message)) || `Request failed with status ${response.status}`;
      const err = new Error(errorMsg);
      err.status = response.status;
      err.data = data;
      throw err;
    }

    return data;
  }

  const API = {
    fetchCsrfToken,

    // Auth & Status
    getAuthStatus: () => request('/api/auth/status'),
    setupAdmin: (payload) => request('/api/auth/setup', { method: 'POST', body: payload }),
    login: (username, password) => request('/api/auth/login', { method: 'POST', body: { username, password } }),
    logout: () => request('/api/auth/logout', { method: 'POST' }),

    // Rooms
    getRooms: () => request('/api/rooms'),
    getNextAvailableRoom: () => request('/api/rooms/next-available'),

    // Bookings
    createBooking: (payload) => request('/api/bookings', { method: 'POST', body: payload }),
    getBookingHistory: () => request('/api/bookings/history'),
    searchGuests: (query) => request(`/api/bookings/search?q=${encodeURIComponent(query || '')}`),
    getActiveBooking: (roomNo) => request(`/api/bookings/active/${roomNo}`),
    updateBooking: (roomNo, payload) => request(`/api/bookings/active/${roomNo}`, { method: 'PUT', body: payload }),

    // Checkout
    getCheckoutPreview: (roomNo) => request(`/api/checkout/preview/${roomNo}`),
    checkoutRoom: (roomNo) => request(`/api/checkout/${roomNo}`, { method: 'POST' }),

    // Housekeeping
    getHousekeeping: () => request('/api/housekeeping'),
    cycleHousekeeping: (roomNo) => request(`/api/housekeeping/cycle/${roomNo}`, { method: 'POST' }),

    // Revenue
    getRevenueReport: (period) => request(`/api/revenue/report?period=${encodeURIComponent(period || 'Monthly')}`),

    // Staff
    getStaff: () => request('/api/staff'),
    addStaff: (payload) => request('/api/staff', { method: 'POST', body: payload }),
    updateStaff: (staffId, payload) => request(`/api/staff/${staffId}`, { method: 'PUT', body: payload })
  };

  window.API = API;
})(window);
