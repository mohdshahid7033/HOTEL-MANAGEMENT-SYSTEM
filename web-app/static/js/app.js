/**
 * Taj Banjara Hotel — Management System
 * Single Page Application Controller
 * Project Owner & Sole Developer: Mohd Shahid Moin Uddin
 */

(function () {
  'use strict';

  // Application State
  const state = {
    currentUser: null,
    currentView: 'view-welcome',
    activePeriod: 'Monthly',
    selectedCheckoutRoom: null,
    updateActiveRoom: null
  };

  // DOM Elements cache
  const el = {
    headerClock: document.getElementById('header-clock'),
    userBadge: document.getElementById('user-badge'),
    userBadgeName: document.getElementById('user-badge-name'),
    btnLogout: document.getElementById('btn-logout'),
    brandHomeBtn: document.getElementById('brand-home-btn'),
    statusBar: document.getElementById('system-status-bar'),
    statusText: document.getElementById('status-text'),
    views: document.querySelectorAll('.view-panel'),

    // Welcome
    btnWelcomeEnter: document.getElementById('btn-welcome-enter'),

    // Setup
    setupForm: document.getElementById('setup-form'),
    setupFeedback: document.getElementById('setup-feedback'),

    // Login
    loginForm: document.getElementById('login-form'),
    loginFeedback: document.getElementById('login-feedback'),
    btnQuickStaff: document.getElementById('btn-quick-staff'),

    // Dashboard
    dashTime: document.getElementById('dash-time'),
    dashUser: document.getElementById('dash-user'),
    kpiAvailable: document.getElementById('kpi-available'),
    kpiOccupied: document.getElementById('kpi-occupied'),
    kpiCleaning: document.getElementById('kpi-cleaning'),
    kpiRevenue: document.getElementById('kpi-revenue'),
    btnDashExit: document.getElementById('btn-dash-exit'),

    // Booking
    bookingForm: document.getElementById('booking-form'),
    bookingRoomBadge: document.getElementById('booking-room-badge'),
    bookingFeedback: document.getElementById('booking-feedback'),
    btnConfirmBook: document.getElementById('btn-confirm-book'),

    // Checkout
    checkoutRoomSelect: document.getElementById('checkout-room-select'),
    btnCalcBill: document.getElementById('btn-calc-bill'),
    billDisplayBox: document.getElementById('bill-display-box'),
    billContent: document.getElementById('bill-content'),
    btnConfirmCheckout: document.getElementById('btn-confirm-checkout'),
    checkoutFeedback: document.getElementById('checkout-feedback'),

    // Search
    guestSearchInput: document.getElementById('guest-search-input'),
    btnExecSearch: document.getElementById('btn-exec-search'),
    guestSearchTbody: document.getElementById('guest-search-tbody'),
    searchFeedback: document.getElementById('search-feedback'),

    // Room Status
    roomCardsGrid: document.getElementById('room-cards-grid'),
    roomStatusTbody: document.getElementById('room-status-tbody'),

    // Staff
    staffTbody: document.getElementById('staff-tbody'),
    addStaffForm: document.getElementById('add-staff-form'),
    addStaffFeedback: document.getElementById('add-staff-feedback'),
    staffFeedback: document.getElementById('staff-feedback'),
    editStaffModal: document.getElementById('edit-staff-modal'),
    editStaffForm: document.getElementById('edit-staff-form'),
    modalStaffClose: document.getElementById('modal-staff-close'),
    modalStaffCancel: document.getElementById('modal-staff-cancel'),
    modalFeedback: document.getElementById('modal-feedback'),

    // History
    historyTbody: document.getElementById('history-tbody'),

    // Update
    updateRoomInput: document.getElementById('update-room-input'),
    btnSearchUpdate: document.getElementById('btn-search-update'),
    updateDetailsBox: document.getElementById('update-details-box'),
    updateCurrentInfo: document.getElementById('update-current-info'),
    updateBookingForm: document.getElementById('update-booking-form'),
    updateDays: document.getElementById('update-days'),
    updateFood: document.getElementById('update-food'),
    updateFeedback: document.getElementById('update-feedback'),

    // Housekeeping
    housekeepingTbody: document.getElementById('housekeeping-tbody'),
    housekeepingFeedback: document.getElementById('housekeeping-feedback'),

    // Revenue
    revFilterBtns: document.querySelectorAll('.rev-filter-btn'),
    revenueReportText: document.getElementById('revenue-report-text'),
    revenueFeedback: document.getElementById('revenue-feedback')
  };

  // ==========================================
  // Utility & Status Bar Methods
  // ==========================================

  function getFormattedTime() {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
  }

  function getFormattedDateTime() {
    const now = new Date();
    const d = String(now.getDate()).padStart(2, '0');
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const y = now.getFullYear();
    const t = getFormattedTime();
    return `${d}/${m}/${y} ${t}`;
  }

  function updateClock() {
    const timeStr = getFormattedTime();
    if (el.headerClock) {
      el.headerClock.textContent = timeStr;
    }
    if (el.dashTime) {
      el.dashTime.textContent = getFormattedDateTime();
    }
  }

  function showStatus(msg, isError = false) {
    if (!el.statusText) return;
    const time = getFormattedTime();
    el.statusText.textContent = `[${time}] ${msg}`;
    if (isError) {
      el.statusBar.classList.add('error');
    } else {
      el.statusBar.classList.remove('error');
    }
  }

  function setFeedback(element, msg, isError = false) {
    if (!element) return;
    element.textContent = msg || '';
    element.className = 'feedback-msg ' + (msg ? (isError ? 'error show' : 'success show') : '');
  }

  // ==========================================
  // View Navigation
  // ==========================================

  function navigateTo(viewId) {
    state.currentView = viewId;
    el.views.forEach((v) => {
      v.classList.remove('active');
    });

    const target = document.getElementById(viewId);
    if (target) {
      target.classList.add('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Refresh view-specific content
    onViewActivated(viewId);
  }

  function onViewActivated(viewId) {
    switch (viewId) {
      case 'view-dashboard':
        loadDashboardMetrics();
        break;
      case 'view-booking':
        loadBookingView();
        break;
      case 'view-checkout':
        loadCheckoutView();
        break;
      case 'view-search':
        if (el.guestSearchInput) {
          el.guestSearchInput.focus();
        }
        break;
      case 'view-room-status':
        loadRoomStatusView();
        break;
      case 'view-staff':
        loadStaffView();
        break;
      case 'view-history':
        loadHistoryView();
        break;
      case 'view-update':
        resetUpdateView();
        break;
      case 'view-housekeeping':
        loadHousekeepingView();
        break;
      case 'view-revenue':
        loadRevenueReport(state.activePeriod);
        break;
    }
  }

  function updateAuthUI() {
    if (state.currentUser) {
      el.userBadge.classList.remove('hidden');
      el.userBadgeName.textContent = `${state.currentUser.name} (${state.currentUser.designation})`;
      el.btnLogout.classList.remove('hidden');
      if (el.dashUser) {
        el.dashUser.textContent = `Logged in as: ${state.currentUser.name} (${state.currentUser.designation})`;
      }
    } else {
      el.userBadge.classList.add('hidden');
      el.btnLogout.classList.add('hidden');
    }
  }

  // ==========================================
  // Auth Operations
  // ==========================================

  async function checkInitialAuth() {
    try {
      const res = await API.getAuthStatus();
      if (res.needs_setup) {
        showStatus('System uninitialized. Please create the initial administrator.');
        navigateTo('view-setup');
      } else if (res.logged_in) {
        state.currentUser = res.user;
        updateAuthUI();
        showStatus(`Welcome back, ${res.user.name}.`);
        navigateTo('view-dashboard');
      } else {
        updateAuthUI();
        showStatus('System Ready. Please log in.');
        navigateTo('view-welcome');
      }
    } catch (err) {
      showStatus('Unable to connect to server: ' + err.message, true);
      navigateTo('view-welcome');
    }
  }

  async function handleSetupSubmit(e) {
    e.preventDefault();
    setFeedback(el.setupFeedback, '');

    const name = document.getElementById('setup-name').value.trim();
    const contact = document.getElementById('setup-contact').value.trim();
    const username = document.getElementById('setup-username').value.trim();
    const password = document.getElementById('setup-password').value;
    const confirmPassword = document.getElementById('setup-confirm').value;

    if (!name || !contact || !username || !password || !confirmPassword) {
      setFeedback(el.setupFeedback, 'All fields are required.', true);
      return;
    }

    if (password !== confirmPassword) {
      setFeedback(el.setupFeedback, 'Passwords do not match.', true);
      return;
    }

    try {
      const res = await API.setupAdmin({
        name,
        contact,
        username,
        password,
        confirm_password: confirmPassword
      });

      showStatus(`Administrator '${username}' created successfully! Please log in.`);
      el.setupForm.reset();
      document.getElementById('login-username').value = username;
      setFeedback(el.loginFeedback, `Administrator account '${username}' created! Please log in with your credentials.`);
      navigateTo('view-login');
    } catch (err) {
      setFeedback(el.setupFeedback, err.message, true);
      showStatus('Setup failed: ' + err.message, true);
    }
  }

  async function handleLoginSubmit(e) {
    e.preventDefault();
    setFeedback(el.loginFeedback, '');

    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    if (!username || !password) {
      setFeedback(el.loginFeedback, 'Please enter username and password.', true);
      return;
    }

    try {
      const res = await API.login(username, password);
      state.currentUser = res.user;
      updateAuthUI();
      showStatus(`Login successful. Welcome, ${res.user.name}.`);
      el.loginForm.reset();
      navigateTo('view-dashboard');
    } catch (err) {
      setFeedback(el.loginFeedback, err.message, true);
      showStatus('Login failed: ' + err.message, true);
    }
  }

  async function handleLogout() {
    try {
      await API.logout();
    } catch (err) {
      console.warn('Logout notification error:', err);
    }
    state.currentUser = null;
    updateAuthUI();
    showStatus('Logged out successfully.');
    navigateTo('view-welcome');
  }

  // Quick Demo Login Pills
  function setupQuickLogin(username, password) {
    document.getElementById('login-username').value = username;
    document.getElementById('login-password').value = password;
    el.loginForm.dispatchEvent(new Event('submit', { cancelable: true }));
  }

  // ==========================================
  // Module 1: Dashboard
  // ==========================================

  async function loadDashboardMetrics() {
    try {
      const [roomsRes, revRes, hkRes] = await Promise.all([
        API.getRooms(),
        API.getRevenueReport('Monthly'),
        API.getHousekeeping()
      ]);

      el.kpiAvailable.textContent = roomsRes.available_count;
      el.kpiOccupied.textContent = roomsRes.occupied_count;

      const needsCleaningCount = (hkRes.rooms || []).filter((r) => r.status === 'Needs Cleaning').length;
      el.kpiCleaning.textContent = needsCleaningCount;

      el.kpiRevenue.textContent = `₹${(revRes.total_revenue || 0).toLocaleString('en-IN')}`;
      showStatus('Dashboard KPIs synchronized.');
    } catch (err) {
      console.error('Failed to load dashboard metrics:', err);
    }
  }

  // ==========================================
  // Module 2: Book Room
  // ==========================================

  let currentAssignedRoom = null;

  async function loadBookingView() {
    setFeedback(el.bookingFeedback, '');
    el.bookingForm.reset();
    el.bookingRoomBadge.textContent = 'Room No (Auto-Assigned): Checking availability...';
    el.bookingRoomBadge.className = 'room-assigned-banner';
    el.btnConfirmBook.disabled = true;

    try {
      const res = await API.getNextAvailableRoom();
      if (res.available && res.room_no) {
        currentAssignedRoom = res.room_no;
        el.bookingRoomBadge.textContent = `★ Room No (Auto-Assigned): ${res.room_no}`;
        el.bookingRoomBadge.className = 'room-assigned-banner available';
        el.btnConfirmBook.disabled = false;
        showStatus(`Auto-assigned Room ${res.room_no} ready for booking.`);
      } else {
        currentAssignedRoom = null;
        el.bookingRoomBadge.textContent = '⚠️ All 10 Rooms are currently occupied or unavailable!';
        el.bookingRoomBadge.className = 'room-assigned-banner occupied';
        el.btnConfirmBook.disabled = true;
        showStatus('No vacant rooms available at this moment.', true);
      }
    } catch (err) {
      el.bookingRoomBadge.textContent = 'Error checking room availability.';
      showStatus('Failed to query available rooms: ' + err.message, true);
    }
  }

  async function handleBookingSubmit(e) {
    e.preventDefault();
    setFeedback(el.bookingFeedback, '');

    const guestName = document.getElementById('book-name').value.trim();
    const days = parseInt(document.getElementById('book-days').value, 10);
    const foodRadio = document.querySelector('input[name="book-food"]:checked');
    const foodOption = foodRadio ? foodRadio.value : 'None';

    if (!guestName || !days || days <= 0) {
      setFeedback(el.bookingFeedback, 'Please enter valid guest name and number of days (1-90).', true);
      return;
    }

    try {
      el.btnConfirmBook.disabled = true;
      const res = await API.createBooking({
        room_no: currentAssignedRoom,
        guest_name: guestName,
        days: days,
        food_option: foodOption
      });

      const bookedRoom = res.booking.room_no;
      setFeedback(el.bookingFeedback, `★ Room ${bookedRoom} booked successfully for ${guestName} (${days} days, Food: ${foodOption})!`);
      showStatus(`Room ${bookedRoom} booked for guest '${guestName}'.`);
      el.bookingForm.reset();

      // Refresh next available
      setTimeout(loadBookingView, 1200);
    } catch (err) {
      el.btnConfirmBook.disabled = false;
      setFeedback(el.bookingFeedback, err.message, true);
      showStatus('Booking failed: ' + err.message, true);
    }
  }

  // ==========================================
  // Module 3: Checkout & Billing
  // ==========================================

  async function loadCheckoutView() {
    setFeedback(el.checkoutFeedback, '');
    el.billDisplayBox.classList.add('hidden');
    el.billContent.textContent = '';
    el.btnConfirmCheckout.classList.add('hidden');
    el.checkoutRoomSelect.innerHTML = '<option value="">-- Choose Booked Room --</option>';

    try {
      const res = await API.getRooms();
      const occupiedRooms = (res.rooms || []).filter((r) => r.status === 'Booked' || r.status === 'Occupied');

      if (occupiedRooms.length === 0) {
        el.checkoutRoomSelect.innerHTML = '<option value="">-- No Occupied Rooms Found --</option>';
        showStatus('No active bookings currently checked in.');
        return;
      }

      occupiedRooms.forEach((r) => {
        const opt = document.createElement('option');
        opt.value = r.room_no;
        opt.textContent = `Room ${r.room_no} — ${r.guest_name} (${r.days} days)`;
        el.checkoutRoomSelect.appendChild(opt);
      });

      showStatus(`Found ${occupiedRooms.length} occupied rooms eligible for checkout.`);
    } catch (err) {
      showStatus('Failed to load occupied rooms: ' + err.message, true);
    }
  }

  async function handleCalculateBill() {
    setFeedback(el.checkoutFeedback, '');
    const roomNo = el.checkoutRoomSelect.value;
    if (!roomNo) {
      setFeedback(el.checkoutFeedback, 'Please select a room to calculate bill.', true);
      return;
    }

    try {
      state.selectedCheckoutRoom = roomNo;
      const res = await API.getCheckoutPreview(roomNo);
      el.billContent.textContent = res.receipt_text;
      el.billDisplayBox.classList.remove('hidden');
      el.btnConfirmCheckout.classList.remove('hidden');
      el.btnConfirmCheckout.textContent = `Checkout Room ${roomNo} & Confirm Payment (₹${(res.bill.total_cost || 0).toLocaleString('en-IN')})`;
      showStatus(`Bill calculated for Room ${roomNo}. Total: ₹${res.bill.total_cost}`);
    } catch (err) {
      setFeedback(el.checkoutFeedback, err.message, true);
      showStatus('Failed to calculate bill: ' + err.message, true);
    }
  }

  async function handleConfirmCheckout() {
    if (!state.selectedCheckoutRoom) return;
    const roomNo = state.selectedCheckoutRoom;

    try {
      el.btnConfirmCheckout.disabled = true;
      const res = await API.checkoutRoom(roomNo);
      el.billContent.textContent = res.receipt_text;
      el.btnConfirmCheckout.classList.add('hidden');
      setFeedback(el.checkoutFeedback, `★ Room ${roomNo} successfully checked out! Room status is now 'Needs Cleaning'.`);
      showStatus(`Checkout completed for Room ${roomNo}. Total paid: ₹${res.bill.total_cost}`);
      state.selectedCheckoutRoom = null;
      // Reload room selector
      setTimeout(loadCheckoutView, 2000);
    } catch (err) {
      el.btnConfirmCheckout.disabled = false;
      setFeedback(el.checkoutFeedback, err.message, true);
      showStatus('Checkout failed: ' + err.message, true);
    }
  }

  // ==========================================
  // Module 4: Search Guest
  // ==========================================

  let searchDebounceTimer = null;

  async function executeGuestSearch() {
    setFeedback(el.searchFeedback, '');
    const query = el.guestSearchInput.value.trim();

    if (!query) {
      el.guestSearchTbody.innerHTML = '<tr><td colspan="5" class="table-empty">Please enter a guest name above to search.</td></tr>';
      return;
    }

    try {
      const res = await API.searchGuests(query);
      const results = res.results || [];

      if (results.length === 0) {
        el.guestSearchTbody.innerHTML = `<tr><td colspan="5" class="table-empty">No bookings found matching "${query}".</td></tr>`;
        showStatus(`No guests found matching "${query}".`);
        return;
      }

      el.guestSearchTbody.innerHTML = results
        .map(
          (b) => `
        <tr>
          <td><strong>Room ${b.room_no}</strong></td>
          <td>${escapeHtml(b.guest_name)}</td>
          <td>${escapeHtml(b.checkin_time || '--')}</td>
          <td>${b.days}</td>
          <td><span class="status-badge ${b.status === 'Active' ? 'badge-occupied' : 'badge-clean'}">${escapeHtml(b.status)}</span></td>
        </tr>
      `
        )
        .join('');

      showStatus(`Found ${results.length} record(s) matching "${query}".`);
    } catch (err) {
      setFeedback(el.searchFeedback, err.message, true);
      showStatus('Search failed: ' + err.message, true);
    }
  }

  // ==========================================
  // Module 5: Room Status
  // ==========================================

  async function loadRoomStatusView() {
    el.roomCardsGrid.innerHTML = '<div class="table-empty">Loading room cards...</div>';
    el.roomStatusTbody.innerHTML = '<tr><td colspan="5" class="table-empty">Loading room status...</td></tr>';

    try {
      const res = await API.getRooms();
      const rooms = res.rooms || [];

      // Render Visual Cards
      el.roomCardsGrid.innerHTML = rooms
        .map((r) => {
          const isOcc = r.status === 'Booked' || r.status === 'Occupied';
          const cardClass = isOcc ? 'card-occupied' : 'card-available';
          const statusClass = isOcc ? 'badge-occupied' : 'badge-clean';
          return `
          <div class="room-card ${cardClass}">
            <div class="room-card-number">Room ${r.room_no}</div>
            <div class="room-card-status">
              <span class="status-badge ${statusClass}">${escapeHtml(r.status)}</span>
            </div>
            <div class="room-card-details">
              ${
                isOcc
                  ? `<strong>Guest:</strong> ${escapeHtml(r.guest_name || 'N/A')}<br>
                     <strong>Days:</strong> ${r.days}<br>
                     <strong>Food:</strong> ${escapeHtml(r.food_plan || r.food_option || 'None')}`
                  : `<span class="room-vacant-text">Ready for Check-in</span>`
              }
            </div>
          </div>
        `;
        })
        .join('');

      // Render Detailed Table
      el.roomStatusTbody.innerHTML = rooms
        .map((r) => {
          const isOcc = r.status === 'Booked' || r.status === 'Occupied';
          const badgeClass = isOcc ? 'badge-occupied' : 'badge-clean';
          return `
          <tr>
            <td><strong>Room ${r.room_no}</strong></td>
            <td><span class="status-badge ${badgeClass}">${escapeHtml(r.status)}</span></td>
            <td>${isOcc ? escapeHtml(r.guest_name) : '—'}</td>
            <td>${isOcc ? r.days : '—'}</td>
            <td>${isOcc ? escapeHtml(r.food_plan || r.food_option || 'None') : '—'}</td>
          </tr>
        `;
        })
        .join('');

      showStatus(`Room status updated. (${res.available_count} Available, ${res.occupied_count} Occupied)`);
    } catch (err) {
      showStatus('Failed to load room status: ' + err.message, true);
    }
  }

  // ==========================================
  // Module 6: Staff Management
  // ==========================================

  async function loadStaffView() {
    setFeedback(el.staffFeedback, '');
    setFeedback(el.addStaffFeedback, '');
    el.staffTbody.innerHTML = '<tr><td colspan="6" class="table-empty">Loading staff records...</td></tr>';

    if (!state.currentUser || !state.currentUser.is_admin) {
      el.staffTbody.innerHTML = '<tr><td colspan="6" class="table-empty" style="color: #FF4D4D;">Access Denied: Staff Management is restricted to Administrators.</td></tr>';
      showStatus('Access Denied: Admin authorization required.', true);
      return;
    }

    try {
      const res = await API.getStaff();
      const staffList = res.staff || [];

      if (staffList.length === 0) {
        el.staffTbody.innerHTML = '<tr><td colspan="6" class="table-empty">No staff accounts registered.</td></tr>';
        return;
      }

      el.staffTbody.innerHTML = staffList
        .map(
          (s) => `
        <tr>
          <td><strong>${escapeHtml(s.staff_id)}</strong></td>
          <td>${escapeHtml(s.name)}</td>
          <td><span class="staff-role-badge ${s.designation.toLowerCase().includes('admin') || s.designation.toLowerCase().includes('manager') ? 'badge-admin' : ''}">${escapeHtml(s.designation)}</span></td>
          <td>${escapeHtml(s.contact)}</td>
          <td><code>${escapeHtml(s.username)}</code></td>
          <td>
            <button class="btn-gold btn-small btn-edit-staff" data-id="${escapeHtml(s.staff_id)}" data-name="${escapeHtml(s.name)}" data-desig="${escapeHtml(s.designation)}" data-contact="${escapeHtml(s.contact)}">
              Edit
            </button>
          </td>
        </tr>
      `
        )
        .join('');

      // Attach edit button listeners
      document.querySelectorAll('.btn-edit-staff').forEach((btn) => {
        btn.addEventListener('click', () => {
          openEditStaffModal(btn.dataset.id, btn.dataset.name, btn.dataset.desig, btn.dataset.contact);
        });
      });

      showStatus(`Staff roster loaded (${staffList.length} members).`);
    } catch (err) {
      setFeedback(el.staffFeedback, err.message, true);
      showStatus('Failed to load staff roster: ' + err.message, true);
    }
  }

  async function handleAddStaffSubmit(e) {
    e.preventDefault();
    setFeedback(el.addStaffFeedback, '');

    const name = document.getElementById('new-staff-name').value.trim();
    const designation = document.getElementById('new-staff-desig').value.trim();
    const contact = document.getElementById('new-staff-contact').value.trim();
    const username = document.getElementById('new-staff-username').value.trim();
    const password = document.getElementById('new-staff-password').value;

    if (!name || !designation || !contact || !username || !password) {
      setFeedback(el.addStaffFeedback, 'All fields are required.', true);
      return;
    }

    try {
      const res = await API.addStaff({ name, designation, contact, username, password });
      setFeedback(el.addStaffFeedback, `Staff member '${name}' (${res.staff_id}) added successfully!`);
      showStatus(`New staff account '${username}' created with ID ${res.staff_id}.`);
      el.addStaffForm.reset();

      // Switch to roster tab after 1 second
      setTimeout(() => {
        document.querySelector('[data-tab="tab-view-staff"]').click();
      }, 1000);
    } catch (err) {
      setFeedback(el.addStaffFeedback, err.message, true);
      showStatus('Add staff failed: ' + err.message, true);
    }
  }

  function openEditStaffModal(id, name, designation, contact) {
    document.getElementById('edit-staff-id').value = id;
    document.getElementById('edit-staff-name').value = name;
    document.getElementById('edit-staff-desig').value = designation;
    document.getElementById('edit-staff-contact').value = contact;
    document.getElementById('modal-staff-title').textContent = `Edit Staff: ${name} (${id})`;
    setFeedback(el.modalFeedback, '');
    el.editStaffModal.classList.remove('hidden');
  }

  function closeEditStaffModal() {
    el.editStaffModal.classList.add('hidden');
  }

  async function handleEditStaffSubmit(e) {
    e.preventDefault();
    setFeedback(el.modalFeedback, '');

    const id = document.getElementById('edit-staff-id').value;
    const name = document.getElementById('edit-staff-name').value.trim();
    const designation = document.getElementById('edit-staff-desig').value.trim();
    const contact = document.getElementById('edit-staff-contact').value.trim();

    if (!name || !designation || !contact) {
      setFeedback(el.modalFeedback, 'All fields are required.', true);
      return;
    }

    try {
      await API.updateStaff(id, { name, designation, contact });
      showStatus(`Staff member ${id} details updated.`);
      closeEditStaffModal();
      loadStaffView();
    } catch (err) {
      setFeedback(el.modalFeedback, err.message, true);
    }
  }

  // ==========================================
  // Module 7: Booking History
  // ==========================================

  async function loadHistoryView() {
    el.historyTbody.innerHTML = '<tr><td colspan="8" class="table-empty">Loading booking history...</td></tr>';

    try {
      const res = await API.getBookingHistory();
      const bookings = res.bookings || [];

      if (bookings.length === 0) {
        el.historyTbody.innerHTML = '<tr><td colspan="8" class="table-empty">No booking history records found.</td></tr>';
        showStatus('No booking history recorded.');
        return;
      }

      el.historyTbody.innerHTML = bookings
        .map((b) => {
          const isActive = b.status === 'Active';
          const badgeClass = isActive ? 'badge-occupied' : 'badge-clean';
          const totalPaid = b.total_billed ? `₹${Number(b.total_billed).toLocaleString('en-IN')}` : '—';
          return `
          <tr>
            <td><strong>Room ${b.room_no}</strong></td>
            <td>${escapeHtml(b.guest_name)}</td>
            <td>${escapeHtml(b.checkin_time || '--')}</td>
            <td>${escapeHtml(b.checkout_time || '—')}</td>
            <td>${b.days}</td>
            <td>${escapeHtml(b.food_option)}</td>
            <td><span class="status-badge ${badgeClass}">${escapeHtml(b.status)}</span></td>
            <td><strong>${totalPaid}</strong></td>
          </tr>
        `;
        })
        .join('');

      showStatus(`Booking history loaded (${bookings.length} total records).`);
    } catch (err) {
      showStatus('Failed to load booking history: ' + err.message, true);
    }
  }

  // ==========================================
  // Module 8: Update Booking
  // ==========================================

  function resetUpdateView() {
    setFeedback(el.updateFeedback, '');
    el.updateRoomInput.value = '';
    el.updateDetailsBox.classList.add('hidden');
    state.updateActiveRoom = null;
  }

  async function handleSearchBookingForUpdate() {
    setFeedback(el.updateFeedback, '');
    const roomStr = el.updateRoomInput.value.trim();
    const roomNo = parseInt(roomStr, 10);

    if (!roomNo || isNaN(roomNo)) {
      setFeedback(el.updateFeedback, 'Please enter a valid room number (e.g. 101).', true);
      return;
    }

    try {
      const res = await API.getActiveBooking(roomNo);
      const b = res.booking;

      state.updateActiveRoom = roomNo;
      el.updateCurrentInfo.innerHTML = `
        <strong>Active Booking Found for Room ${b.room_no}:</strong><br>
        Guest: <strong>${escapeHtml(b.guest_name)}</strong> |
        Current Days: <strong>${b.days}</strong> |
        Current Food Plan: <strong>${escapeHtml(b.food_option)}</strong> |
        Check-in: <em>${escapeHtml(b.checkin_time || '--')}</em>
      `;
      el.updateDays.value = b.days;
      el.updateFood.value = b.food_option;
      el.updateDetailsBox.classList.remove('hidden');
      showStatus(`Active booking for Room ${roomNo} loaded for modification.`);
    } catch (err) {
      el.updateDetailsBox.classList.add('hidden');
      state.updateActiveRoom = null;
      setFeedback(el.updateFeedback, err.message, true);
      showStatus('Update search failed: ' + err.message, true);
    }
  }

  async function handleUpdateBookingSubmit(e) {
    e.preventDefault();
    setFeedback(el.updateFeedback, '');

    if (!state.updateActiveRoom) return;
    const roomNo = state.updateActiveRoom;
    const days = parseInt(el.updateDays.value, 10);
    const foodOption = el.updateFood.value;

    if (!days || days <= 0) {
      setFeedback(el.updateFeedback, 'Please enter a valid number of days.', true);
      return;
    }

    try {
      const res = await API.updateBooking(roomNo, { days, food_option: foodOption });
      setFeedback(el.updateFeedback, `★ Room ${roomNo} booking updated successfully! (Days: ${days}, Food: ${foodOption})`);
      showStatus(`Room ${roomNo} booking updated.`);
      handleSearchBookingForUpdate(); // Refresh banner
    } catch (err) {
      setFeedback(el.updateFeedback, err.message, true);
      showStatus('Update failed: ' + err.message, true);
    }
  }

  // ==========================================
  // Module 9: Housekeeping Status
  // ==========================================

  async function loadHousekeepingView() {
    setFeedback(el.housekeepingFeedback, '');
    el.housekeepingTbody.innerHTML = '<tr><td colspan="4" class="table-empty">Loading housekeeping status...</td></tr>';

    try {
      const res = await API.getHousekeeping();
      const rooms = res.rooms || [];

      el.housekeepingTbody.innerHTML = rooms
        .map((r) => {
          let badgeClass = 'badge-clean';
          let actionLabel = 'Mark Needs Cleaning';

          if (r.status === 'Needs Cleaning') {
            badgeClass = 'badge-needs-cleaning';
            actionLabel = 'Start Cleaning';
          } else if (r.status === 'In Progress') {
            badgeClass = 'badge-in-progress';
            actionLabel = 'Mark as Clean';
          }

          return `
          <tr>
            <td><strong>Room ${r.room_no}</strong></td>
            <td><span class="status-badge ${badgeClass}">${escapeHtml(r.status)}</span></td>
            <td>${escapeHtml(r.last_cleaned_by || '—')}</td>
            <td>
              <button class="btn-gold btn-small btn-cycle-hk" data-room="${r.room_no}">
                ${actionLabel}
              </button>
            </td>
          </tr>
        `;
        })
        .join('');

      document.querySelectorAll('.btn-cycle-hk').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const roomNo = btn.dataset.room;
          btn.disabled = true;
          try {
            const res = await API.cycleHousekeeping(roomNo);
            showStatus(`Room ${roomNo} status changed to '${res.new_status}'.`);
            loadHousekeepingView();
          } catch (err) {
            btn.disabled = false;
            setFeedback(el.housekeepingFeedback, err.message, true);
            showStatus('Housekeeping update failed: ' + err.message, true);
          }
        });
      });

      showStatus('Housekeeping status synchronized.');
    } catch (err) {
      showStatus('Failed to load housekeeping: ' + err.message, true);
    }
  }

  // ==========================================
  // Module 10: Revenue Report
  // ==========================================

  async function loadRevenueReport(period) {
    state.activePeriod = period;
    setFeedback(el.revenueFeedback, '');
    el.revenueReportText.textContent = `Loading ${period} revenue report...`;

    el.revFilterBtns.forEach((b) => {
      if (b.dataset.period === period) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });

    try {
      const res = await API.getRevenueReport(period);
      el.revenueReportText.textContent = res.report_text || 'No report data available.';
      showStatus(`${period} revenue report loaded. Total: ₹${(res.total_revenue || 0).toLocaleString('en-IN')}`);
    } catch (err) {
      setFeedback(el.revenueFeedback, err.message, true);
      showStatus('Failed to load revenue report: ' + err.message, true);
    }
  }

  // ==========================================
  // Helpers
  // ==========================================

  function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, (m) => map[m]);
  }

  // ==========================================
  // Event Bindings
  // ==========================================

  function bindEvents() {
    // Brand header click
    el.brandHomeBtn.addEventListener('click', () => {
      if (state.currentUser) {
        navigateTo('view-dashboard');
      } else {
        navigateTo('view-welcome');
      }
    });

    // Global Logout
    el.btnLogout.addEventListener('click', handleLogout);

    // Welcome Enter
    el.btnWelcomeEnter.addEventListener('click', () => {
      if (state.currentUser) {
        navigateTo('view-dashboard');
      } else {
        navigateTo('view-login');
      }
    });

    // Setup Form
    el.setupForm.addEventListener('submit', handleSetupSubmit);

    // Login Form
    el.loginForm.addEventListener('submit', handleLoginSubmit);

    // Demo Quick-Login (Restricted Receptionist Portfolio Access)
    if (el.btnQuickStaff) {
      el.btnQuickStaff.addEventListener('click', () => {
        setupQuickLogin('demo_staff', 'StaffPass@2026');
      });
    }

    // Back to Welcome navigation buttons
    document.querySelectorAll('.nav-back-welcome').forEach((btn) => {
      btn.addEventListener('click', () => navigateTo('view-welcome'));
    });

    // Back to Dashboard navigation buttons
    document.querySelectorAll('.nav-to-dash').forEach((btn) => {
      btn.addEventListener('click', () => navigateTo('view-dashboard'));
    });

    // Dashboard 10 Modules Navigation Grid
    document.querySelectorAll('.dash-btn[data-target]').forEach((btn) => {
      btn.addEventListener('click', () => {
        navigateTo(btn.dataset.target);
      });
    });

    // Dashboard Exit
    el.btnDashExit.addEventListener('click', () => {
      if (confirm('Are you sure you want to sign out and return to the welcome screen?')) {
        handleLogout();
      }
    });

    // Module 2: Booking Form
    el.bookingForm.addEventListener('submit', handleBookingSubmit);

    // Module 3: Checkout
    el.btnCalcBill.addEventListener('click', handleCalculateBill);
    el.btnConfirmCheckout.addEventListener('click', handleConfirmCheckout);

    // Module 4: Search Guest
    el.btnExecSearch.addEventListener('click', executeGuestSearch);
    el.guestSearchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        executeGuestSearch();
      }
    });
    el.guestSearchInput.addEventListener('input', () => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(executeGuestSearch, 300);
    });

    // Module 6: Staff Management Tabs
    document.querySelectorAll('.tab-btn[data-tab]').forEach((tabBtn) => {
      tabBtn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach((c) => c.classList.remove('active'));
        tabBtn.classList.add('active');
        const targetTab = document.getElementById(tabBtn.dataset.tab);
        if (targetTab) {
          targetTab.classList.add('active');
        }
        if (tabBtn.dataset.tab === 'tab-view-staff') {
          loadStaffView();
        }
      });
    });

    el.addStaffForm.addEventListener('submit', handleAddStaffSubmit);

    // Staff Edit Modal
    el.modalStaffClose.addEventListener('click', closeEditStaffModal);
    el.modalStaffCancel.addEventListener('click', closeEditStaffModal);
    el.editStaffForm.addEventListener('submit', handleEditStaffSubmit);

    // Module 8: Update Booking
    el.btnSearchUpdate.addEventListener('click', handleSearchBookingForUpdate);
    el.updateRoomInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSearchBookingForUpdate();
      }
    });
    el.updateBookingForm.addEventListener('submit', handleUpdateBookingSubmit);

    // Module 10: Revenue Filter Tabs
    el.revFilterBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        loadRevenueReport(btn.dataset.period);
      });
    });
  }

  // ==========================================
  // Initialization
  // ==========================================

  function init() {
    updateClock();
    setInterval(updateClock, 1000);
    bindEvents();
    checkInitialAuth();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
