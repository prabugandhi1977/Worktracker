const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : `${window.location.protocol}//${window.location.hostname}:8000`;

const state = {
  token: localStorage.getItem("worktrack_token") || null,
  role: localStorage.getItem("worktrack_role") || null,
  username: localStorage.getItem("worktrack_username") || null,
};

let liveRefreshTimer = null;

// ---------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------

async function api(path, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    logout();
    throw new Error("Session expired, please log in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ? JSON.stringify(body.detail) : detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function apiJSON(path, method, payload) {
  return api(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------

function showApp() {
  document.getElementById("login-screen").hidden = true;
  document.getElementById("app").hidden = false;
  document.getElementById("whoami").textContent = `${state.username} (${state.role})`;
  initTabs();
  loadDashboard();
}

function showLogin() {
  document.getElementById("login-screen").hidden = false;
  document.getElementById("app").hidden = true;
  if (liveRefreshTimer) clearInterval(liveRefreshTimer);
}

function logout() {
  state.token = null;
  state.role = null;
  state.username = null;
  localStorage.removeItem("worktrack_token");
  localStorage.removeItem("worktrack_role");
  localStorage.removeItem("worktrack_username");
  showLogin();
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.hidden = true;

  try {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${API_BASE}/auth/login`, { method: "POST", body });
    if (!res.ok) throw new Error("Invalid username or password.");
    const data = await res.json();

    state.token = data.access_token;
    state.role = data.role;
    state.username = username;
    localStorage.setItem("worktrack_token", state.token);
    localStorage.setItem("worktrack_role", state.role);
    localStorage.setItem("worktrack_username", state.username);

    showApp();
  } catch (err) {
    errorEl.textContent = err.message || "Could not sign in. Is the API running?";
    errorEl.hidden = false;
  }
});

document.getElementById("logout-btn").addEventListener("click", logout);

// ---------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------

function initTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tab}`);
  });

  if (liveRefreshTimer) {
    clearInterval(liveRefreshTimer);
    liveRefreshTimer = null;
  }

  if (tab === "dashboard") loadDashboard();
  if (tab === "employees") loadEmployees();
  if (tab === "projects") loadProjects();
  if (tab === "attendance") loadAttendance();
  if (tab === "timelogs") loadTimeLogs();
  if (tab === "exceptions") loadExceptions();
  if (tab === "simulate") loadSimulate();
}

// ---------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------

async function loadDashboard() {
  try {
    const mgmt = await api("/dashboard/management");
    renderStatCards(mgmt);
  } catch (err) {
    renderStatCards(null, err.message);
  }

  await refreshLiveTable();
  liveRefreshTimer = setInterval(refreshLiveTable, 5000);
}

function renderStatCards(mgmt, errorMessage) {
  const container = document.getElementById("mgmt-cards");
  if (!mgmt) {
    container.innerHTML = `<div class="stat-card"><div class="label">Error</div><div class="value">${errorMessage}</div></div>`;
    return;
  }
  const cards = [
    ["Total employees", mgmt.total_employees],
    ["Present today", mgmt.present_today],
    ["Working now", mgmt.working_now],
    ["On break", mgmt.on_break_now],
    ["Overtime hrs today", mgmt.total_overtime_hours_today],
    ["Active projects", mgmt.active_projects],
    ["Open exceptions", mgmt.open_exceptions],
    ["Utilization %", mgmt.utilization_pct],
  ];
  container.innerHTML = cards
    .map(([label, value]) => `<div class="stat-card"><div class="value">${value}</div><div class="label">${label}</div></div>`)
    .join("");
}

async function refreshLiveTable() {
  const tbody = document.querySelector("#live-table tbody");
  try {
    const rows = await api("/dashboard/live");
    if (!rows.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No one has clocked in today yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td>${r.employee_name ?? r.employee_id}</td>
        <td><span class="status-pill status-${r.status.toLowerCase()}">${r.status}</span></td>
        <td>${r.project_id ?? "-"}</td>
        <td>${formatTime(r.session_started_at)}</td>
        <td>${r.duration_minutes ?? "-"}</td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">${err.message}</td></tr>`;
  }
}

// ---------------------------------------------------------------------
// Employees
// ---------------------------------------------------------------------

async function loadEmployees() {
  const deptSelect = document.getElementById("emp-department");
  try {
    const departments = await api("/departments");
    deptSelect.innerHTML = departments.map((d) => `<option value="${d.id}">${d.name}</option>`).join("");
  } catch (err) {
    deptSelect.innerHTML = "";
  }

  const tbody = document.querySelector("#employees-table tbody");
  try {
    const employees = await api("/employees");
    if (!employees.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No employees yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = employees
      .map(
        (e) => `
      <tr>
        <td>${e.employee_code}</td>
        <td>${e.name}</td>
        <td>${e.department_id}</td>
        <td>${e.designation}</td>
        <td>${e.employment_status}</td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">${err.message}</td></tr>`;
  }
}

document.getElementById("employee-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await apiJSON("/employees", "POST", {
      employee_code: document.getElementById("emp-code").value.trim(),
      name: document.getElementById("emp-name").value.trim(),
      department_id: Number(document.getElementById("emp-department").value),
      designation: document.getElementById("emp-designation").value.trim(),
      employment_status: "ACTIVE",
    });
    event.target.reset();
    loadEmployees();
  } catch (err) {
    alert(`Could not add employee: ${err.message}`);
  }
});

document.getElementById("department-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await apiJSON("/departments", "POST", { name: document.getElementById("dept-name").value.trim() });
    event.target.reset();
    loadEmployees();
  } catch (err) {
    alert(`Could not add department: ${err.message}`);
  }
});

// ---------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------

async function loadProjects() {
  const tbody = document.querySelector("#projects-table tbody");
  try {
    const projects = await api("/projects");
    if (!projects.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="7">No projects yet.</td></tr>`;
      return;
    }

    const rows = await Promise.all(
      projects.map(async (p) => {
        let actual = "-";
        let remaining = "-";
        try {
          const detail = await api(`/dashboard/project/${p.id}`);
          actual = detail.actual_hours;
          remaining = detail.remaining_hours;
        } catch (_) {
          /* leave as dash */
        }
        return `
        <tr>
          <td>${p.project_code}</td>
          <td>${p.name}</td>
          <td>${p.customer ?? "-"}</td>
          <td>${p.status}</td>
          <td>${p.planned_hours}</td>
          <td>${actual}</td>
          <td>${remaining}</td>
        </tr>`;
      })
    );
    tbody.innerHTML = rows.join("");
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">${err.message}</td></tr>`;
  }
}

document.getElementById("project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const plannedHours = document.getElementById("proj-planned-hours").value;
    await apiJSON("/projects", "POST", {
      project_code: document.getElementById("proj-code").value.trim(),
      name: document.getElementById("proj-name").value.trim(),
      customer: document.getElementById("proj-customer").value.trim() || null,
      status: "ACTIVE",
      planned_hours: plannedHours ? Number(plannedHours) : 0,
    });
    event.target.reset();
    loadProjects();
  } catch (err) {
    alert(`Could not add project: ${err.message}`);
  }
});

// ---------------------------------------------------------------------
// Attendance
// ---------------------------------------------------------------------

async function loadAttendance() {
  const employeeId = document.getElementById("att-employee-id").value;
  const workDate = document.getElementById("att-date").value;
  const params = new URLSearchParams();
  if (employeeId) params.set("employee_id", employeeId);
  if (workDate) params.set("work_date", workDate);

  const tbody = document.querySelector("#attendance-table tbody");
  try {
    const rows = await api(`/attendance?${params.toString()}`);
    if (!rows.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="8">No attendance records found.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td>${r.employee_id}</td>
        <td>${r.work_date}</td>
        <td>${formatTime(r.first_entry)}</td>
        <td>${formatTime(r.last_exit)}</td>
        <td>${(r.gross_minutes / 60).toFixed(2)}</td>
        <td>${(r.break_minutes / 60).toFixed(2)}</td>
        <td>${(r.net_minutes / 60).toFixed(2)}</td>
        <td>${(r.overtime_minutes / 60).toFixed(2)}</td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">${err.message}</td></tr>`;
  }
}

document.getElementById("attendance-filter").addEventListener("submit", (event) => {
  event.preventDefault();
  loadAttendance();
});

// ---------------------------------------------------------------------
// Time logs
// ---------------------------------------------------------------------

async function loadTimeLogs() {
  const employeeId = document.getElementById("tl-employee-id").value;
  const projectId = document.getElementById("tl-project-id").value;
  const params = new URLSearchParams();
  if (employeeId) params.set("employee_id", employeeId);
  if (projectId) params.set("project_id", projectId);

  const tbody = document.querySelector("#timelogs-table tbody");
  try {
    const rows = await api(`/timelogs?${params.toString()}`);
    if (!rows.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="8">No time logs found.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td>${r.employee_id}</td>
        <td>${r.project_id ?? "-"}</td>
        <td>${r.activity_id ?? "-"}</td>
        <td>${formatTime(r.start_time)}</td>
        <td>${formatTime(r.end_time)}</td>
        <td>${r.duration_minutes}</td>
        <td>${r.is_break ? "Yes" : "No"}</td>
        <td>${r.status}</td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">${err.message}</td></tr>`;
  }
}

document.getElementById("timelogs-filter").addEventListener("submit", (event) => {
  event.preventDefault();
  loadTimeLogs();
});

// ---------------------------------------------------------------------
// Exceptions
// ---------------------------------------------------------------------

async function loadExceptions() {
  const tbody = document.querySelector("#exceptions-table tbody");
  try {
    const rows = await api("/exceptions");
    if (!rows.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="7">No exceptions.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td>${r.exception_type}</td>
        <td>${r.employee_id ?? "-"}</td>
        <td>${r.description ?? "-"}</td>
        <td>${r.severity}</td>
        <td><span class="status-pill status-${r.status.toLowerCase()}">${r.status}</span></td>
        <td>${formatTime(r.created_at)}</td>
        <td>${
          r.status === "OPEN"
            ? `<button class="small" onclick="resolveException(${r.id})">Resolve</button>`
            : "-"
        }</td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">${err.message}</td></tr>`;
  }
}

async function resolveException(id) {
  const resolution = prompt("Resolution note:");
  if (resolution === null) return;
  try {
    await apiJSON(`/exceptions/${id}/resolve`, "POST", { resolution, status: "RESOLVED" });
    loadExceptions();
  } catch (err) {
    alert(`Could not resolve exception: ${err.message}`);
  }
}
window.resolveException = resolveException;

// ---------------------------------------------------------------------
// Simulate scan
// ---------------------------------------------------------------------

async function loadSimulate() {
  const select = document.getElementById("sim-reader");
  try {
    const readers = await api("/readers");
    select.innerHTML = readers
      .map((r) => `<option value="${r.reader_code}">${r.reader_code} — ${r.name} (${r.reader_type})</option>`)
      .join("");
  } catch (err) {
    select.innerHTML = `<option value="">Could not load readers</option>`;
  }
}

document.getElementById("simulate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const resultBox = document.getElementById("simulate-result");
  const readerCode = document.getElementById("sim-reader").value;
  const cardUid = document.getElementById("sim-card").value.trim();

  try {
    const [readers, gateways] = await Promise.all([api("/readers"), api("/gateways")]);
    const reader = readers.find((r) => r.reader_code === readerCode);
    const gateway = gateways.find((g) => g.id === (reader ? reader.gateway_id : null));
    const payload = {
      event_id: crypto.randomUUID(),
      rfid_uid: cardUid,
      reader_id: readerCode,
      gateway_id: gateway ? gateway.gateway_code : "UNKNOWN-GATEWAY",
      timestamp: new Date().toISOString(),
    };
    const result = await apiJSON("/events/rfid", "POST", payload);
    resultBox.textContent = JSON.stringify(result, null, 2);
  } catch (err) {
    resultBox.textContent = `Error: ${err.message}`;
  }
});

// ---------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------

function formatTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString();
}

// ---------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------

if (state.token) {
  showApp();
} else {
  showLogin();
}
