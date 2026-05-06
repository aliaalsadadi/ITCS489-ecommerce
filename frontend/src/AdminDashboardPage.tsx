import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "./api";
import type { AdminAuditLog, AdminDashboardSummary, AdminUser, UnpaidAuctionOrder, UnpaidAuctionOrdersResponse } from "./types";

const LOG_LIMIT = 500;

type AdminTab = "overview" | "users" | "reports" | "unpaid" | "health";

function parseError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatMoney(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) {
    return "0.00";
  }
  return n.toFixed(2);
}

function downloadCsv(filename: string, rows: string[][]): void {
  const escapeCsv = (value: string) => {
    if (value.includes(",") || value.includes("\"") || value.includes("\n")) {
      return `"${value.split("\"").join("\"\"")}"`;
    }
    return value;
  };

  const content = rows.map((row) => row.map((cell) => escapeCsv(cell)).join(",")).join("\n");
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function toServerRoot(apiBase: string): string {
  if (apiBase.endsWith("/api/v1")) {
    return apiBase.slice(0, -7);
  }
  return apiBase;
}

function isWithinDateRange(isoDate: string, from: string, to: string): boolean {
  const value = new Date(isoDate).getTime();
  if (Number.isNaN(value)) {
    return false;
  }

  if (from) {
    const fromMs = new Date(`${from}T00:00:00`).getTime();
    if (!Number.isNaN(fromMs) && value < fromMs) {
      return false;
    }
  }

  if (to) {
    const toMs = new Date(`${to}T23:59:59`).getTime();
    if (!Number.isNaN(toMs) && value > toMs) {
      return false;
    }
  }

  return true;
}

export function AdminDashboardPage({ token }: { token: string }) {
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [statusText, setStatusText] = useState("");

  const [summary, setSummary] = useState<AdminDashboardSummary | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);

  const [userSearch, setUserSearch] = useState("");
  const [userRole, setUserRole] = useState("");

  const [logAction, setLogAction] = useState("");
  const [logTargetType, setLogTargetType] = useState("");
  const [filterUserId, setFilterUserId] = useState<string>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [healthText, setHealthText] = useState("Checking API health...");
  const [healthCheckedAt, setHealthCheckedAt] = useState("");

  const [unpaidOrders, setUnpaidOrders] = useState<UnpaidAuctionOrder[]>([]);
  const [unpaidTotal, setUnpaidTotal] = useState(0);
  const [isLoadingUnpaid, setIsLoadingUnpaid] = useState(false);

  async function loadSummary(): Promise<void> {
    try {
      const data = await apiRequest<AdminDashboardSummary>("/admin/dashboard", {}, token);
      setSummary(data);
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  async function loadUsers(): Promise<void> {
    try {
      const query = new URLSearchParams({
        limit: "200",
        search: userSearch,
        role: userRole,
      });
      const data = await apiRequest<AdminUser[]>(`/admin/users?${query.toString()}`, {}, token);
      setUsers(data);
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  async function loadLogs(): Promise<void> {
    try {
      const params = new URLSearchParams({
        limit: String(LOG_LIMIT),
      });
      if (logAction) params.append("action", logAction);
      if (logTargetType) params.append("target_type", logTargetType);
      if (filterUserId) params.append("admin_id", filterUserId);
      if (dateFrom) params.append("date_from", new Date(`${dateFrom}T00:00:00`).toISOString());
      if (dateTo) params.append("date_to", new Date(`${dateTo}T23:59:59`).toISOString());

      const data = await apiRequest<AdminAuditLog[]>(
        `/admin/audit-logs?${params.toString()}`,
        {},
        token
      );
      setLogs(data);
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  async function checkHealth(): Promise<void> {
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || "/api/v1";
      const root = toServerRoot(apiBase);
      const response = await fetch(`${root}/health`);
      if (!response.ok) {
        throw new Error(`Health endpoint failed (${response.status})`);
      }
      const data = (await response.json()) as { status?: string };
      setHealthText(data.status === "ok" ? "API healthy" : "API responded with unknown status");
      setHealthCheckedAt(new Date().toLocaleString());
    } catch (error) {
      setHealthText(`Health check failed: ${parseError(error)}`);
      setHealthCheckedAt(new Date().toLocaleString());
    }
  }

  async function loadUnpaidOrders(): Promise<void> {
    setIsLoadingUnpaid(true);
    try {
      const data = await apiRequest<UnpaidAuctionOrdersResponse>(
        "/admin/auctions/unpaid-orders?limit=100&offset=0",
        {},
        token
      );
      setUnpaidOrders(data.items);
      setUnpaidTotal(data.total);
    } catch (error) {
      setStatusText(parseError(error));
    } finally {
      setIsLoadingUnpaid(false);
    }
  }

  async function toggleSuspension(user: AdminUser): Promise<void> {
    try {
      const payload = { is_suspended: !user.is_suspended };
      await apiRequest<AdminUser>(`/admin/users/${user.id}/suspension`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }, token);
      setStatusText(`User ${payload.is_suspended ? "suspended" : "unsuspended"}`);
      await Promise.all([loadUsers(), loadLogs(), loadSummary()]);
    } catch (error) {
      setStatusText(parseError(error));
    }
  }

  useEffect(() => {
    void Promise.all([loadSummary(), loadUsers(), loadLogs()]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    void loadUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userSearch, userRole]);

  useEffect(() => {
    void loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logAction, logTargetType, filterUserId, dateFrom, dateTo]);

  useEffect(() => {
    if (activeTab === "health") {
      void checkHealth();
    }
  }, [activeTab]);

  const filteredLogsForReport = useMemo(() => {
    return logs.filter((log) => isWithinDateRange(log.created_at, dateFrom, dateTo));
  }, [logs, dateFrom, dateTo]);

  const reportActionBreakdown = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of filteredLogsForReport) {
      map.set(item.action, (map.get(item.action) ?? 0) + 1);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [filteredLogsForReport]);

  const securityEventCount = useMemo(() => {
    return filteredLogsForReport.filter((item) => item.action.includes("suspension") || item.action.includes("role")).length;
  }, [filteredLogsForReport]);

  function exportReportCsv(): void {
    const rows: string[][] = [["created_at", "admin_id", "action", "target_type", "target_id", "details"]];
    for (const item of filteredLogsForReport) {
      rows.push([
        item.created_at,
        item.admin_id ?? "",
        item.action,
        item.target_type,
        item.target_id,
        JSON.stringify(item.details),
      ]);
    }
    downloadCsv("admin-activity-report.csv", rows);
  }

  function printReport(): void {
    const printWindow = window.open("", "_blank", "noopener,noreferrer,width=1100,height=800");
    if (!printWindow) {
      setStatusText("Pop-up blocked. Please allow pop-ups for this site, then try Print / Save PDF again.");
      return;
    }

    const rangeText = `${dateFrom || "start"} to ${dateTo || "now"}`;
    const generatedAt = new Date().toLocaleString();
    const rows = filteredLogsForReport
      .map((log) => {
        const adminUser = users.find((user) => user.id === log.admin_id);
        const adminLabel = adminUser ? `${adminUser.full_name || adminUser.email} (${adminUser.email})` : "System";
        return `
          <tr>
            <td>${escapeHtml(new Date(log.created_at).toLocaleString())}</td>
            <td>${escapeHtml(log.action)}</td>
            <td>${escapeHtml(adminLabel)}</td>
            <td>${escapeHtml(log.target_type)}</td>
            <td><code>${escapeHtml(log.target_id)}</code></td>
            <td><pre>${escapeHtml(JSON.stringify(log.details, null, 2))}</pre></td>
          </tr>
        `;
      })
      .join("");
    const breakdown = reportActionBreakdown
      .map(([action, count]) => `<li><strong>${escapeHtml(action)}</strong><span>${count}</span></li>`)
      .join("");

    printWindow.document.write(`<!doctype html>
      <html>
        <head>
          <title>Admin Activity Report</title>
          <style>
            * { box-sizing: border-box; }
            body { margin: 32px; color: #2e2b29; font-family: Arial, sans-serif; }
            h1, h2 { margin: 0 0 8px; }
            p { margin: 4px 0; color: #5f5a55; }
            .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 22px 0; }
            .summary article { border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
            .summary strong { display: block; font-size: 22px; margin-top: 4px; }
            ul { list-style: none; padding: 0; margin: 16px 0 24px; display: grid; gap: 8px; }
            li { border: 1px solid #ddd; border-radius: 8px; padding: 10px 12px; display: flex; justify-content: space-between; gap: 16px; }
            table { width: 100%; border-collapse: collapse; margin-top: 12px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; font-size: 12px; }
            th { background: #f4f2ef; }
            pre { white-space: pre-wrap; margin: 0; font-size: 11px; }
            code { font-family: Consolas, monospace; }
            @media print {
              body { margin: 18mm; }
              .summary { grid-template-columns: repeat(3, 1fr); }
              tr, article, li { break-inside: avoid; }
            }
          </style>
        </head>
        <body>
          <h1>Admin Activity Report</h1>
          <p>Generated: ${escapeHtml(generatedAt)}</p>
          <p>Range: ${escapeHtml(rangeText)}</p>
          <section class="summary">
            <article><p>Total events</p><strong>${filteredLogsForReport.length}</strong></article>
            <article><p>Security events</p><strong>${securityEventCount}</strong></article>
            <article><p>Actions tracked</p><strong>${reportActionBreakdown.length}</strong></article>
          </section>
          <h2>Action Breakdown</h2>
          <ul>${breakdown || "<li><strong>No actions</strong><span>0</span></li>"}</ul>
          <h2>Activity Events</h2>
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Admin</th>
                <th>Target</th>
                <th>Target ID</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6">No matching activity events.</td></tr>'}</tbody>
          </table>
          <script>
            window.addEventListener("load", () => {
              window.focus();
              window.print();
            });
          </script>
        </body>
      </html>`);
    printWindow.document.close();
  }

  return (
    <main className="site-wrap section-block">
      <div className="section-head">
        <h1>Admin Dashboard</h1>
        <span className="muted">Monitoring, user controls, and reporting</span>
      </div>

      {statusText && <p className="status-text">{statusText}</p>}

      <div className="tab-row top-gap">
        {(["overview", "users", "reports", "unpaid", "health"] as AdminTab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            className={`chip${activeTab === tab ? " active" : ""}`}
            onClick={() => {
              setActiveTab(tab);
              if (tab === "unpaid") {
                void loadUnpaidOrders();
              }
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <section className="card-grid four-col top-gap">
          <article className="card admin-stat-card">
            <p className="muted">Users</p>
            <h2>{summary?.users_total ?? "-"}</h2>
          </article>
          <article className="card admin-stat-card">
            <p className="muted">Suspended users</p>
            <h2>{summary?.users_suspended ?? "-"}</h2>
          </article>
          <article className="card admin-stat-card">
            <p className="muted">Unpaid Auctions</p>
            <h2 style={{ color: summary && summary.unpaid_auctions_count > 0 ? "#e74c3c" : "#2ecc71" }}>
              {summary?.unpaid_auctions_count ?? "-"}
            </h2>
            {summary && summary.unpaid_auctions_count > 0 && (
              <button
                className="outline-btn"
                onClick={() => setActiveTab("unpaid")}
                style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}
              >
                View
              </button>
            )}
          </article>
          <article className="card admin-stat-card">
            <p className="muted">Orders</p>
            <h2>{summary?.orders_total ?? "-"}</h2>
          </article>
          <article className="card admin-stat-card">
            <p className="muted">Revenue</p>
            <h2>BHD {summary ? formatMoney(summary.revenue_total) : "-"}</h2>
          </article>
        </section>
      )}

      {activeTab === "users" && (
        <section className="top-gap">
          <div className="filter-row admin-filter-row">
            <input placeholder="Search by email" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} />
            <select value={userRole} onChange={(event) => setUserRole(event.target.value)}>
              <option value="">All roles</option>
              <option value="customer">Customer</option>
              <option value="artisan">Artisan</option>
              <option value="admin">Admin</option>
            </select>
            <button type="button" className="ghost-btn" onClick={() => void loadUsers()}>
              Refresh
            </button>
          </div>

          <ul className="history-list top-gap">
            {users.map((user) => (
              <li key={user.id}>
                <div>
                  <strong>{user.full_name || user.email}</strong>
                  <p className="muted">{user.email}</p>
                  <p className="muted">
                    Role: {user.role} | Created: {new Date(user.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="admin-row-actions">
                  <span className={`status-pill ${user.is_suspended ? "canceled" : "delivered"}`}>
                    {user.is_suspended ? "suspended" : "active"}
                  </span>
                  <button type="button" className="ghost-btn" onClick={() => void toggleSuspension(user)}>
                    {user.is_suspended ? "Unsuspend" : "Suspend"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {activeTab === "reports" && (
        <section className="top-gap report-sheet card section-card">
          <div className="filter-row admin-filter-row">
            <label>
              Admin:
              <select value={filterUserId} onChange={(event) => setFilterUserId(event.target.value)}>
                <option value="">All admins</option>
                {users
                  .filter((user) => user.role === "admin")
                  .map((admin) => (
                    <option key={admin.id} value={admin.id}>
                      {admin.full_name || admin.email}
                    </option>
                  ))}
              </select>
            </label>

            <label>
              Action:
              <select value={logAction} onChange={(event) => setLogAction(event.target.value)}>
                <option value="">All actions</option>
                <option value="product_created">Product Created</option>
                <option value="product_updated">Product Updated</option>
                <option value="product_deleted">Product Deleted</option>
                <option value="set_user_suspension">User Suspension</option>
                <option value="set_user_role">Role Change</option>
                <option value="set_product_status">Product Status</option>
                <option value="set_order_status">Order Status</option>
                <option value="set_auction_status">Auction Status</option>
              </select>
            </label>

            <label>
              Target:
              <select value={logTargetType} onChange={(event) => setLogTargetType(event.target.value)}>
                <option value="">All targets</option>
                <option value="USER">USER</option>
                <option value="PRODUCT">PRODUCT</option>
                <option value="ORDER">ORDER</option>
                <option value="AUCTION">AUCTION</option>
              </select>
            </label>

            <label>
              From:
              <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
            </label>

            <label>
              To:
              <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
            </label>

            <button type="button" className="ghost-btn" onClick={() => void loadLogs()}>
              Refresh
            </button>
            <button type="button" className="ghost-btn" onClick={exportReportCsv}>
              Export CSV
            </button>
            <button type="button" className="solid-btn" onClick={printReport}>
              Print / Save PDF
            </button>
          </div>

          <h2 className="top-gap">Activity Report</h2>
          <p className="muted">
            Range: {dateFrom || "start"} to {dateTo || "now"} | Total events: {filteredLogsForReport.length}
          </p>
          <p className="muted">Security-related events (suspension/role): {securityEventCount}</p>

          <div className="card-grid three-col top-gap">
            {reportActionBreakdown.map(([action, count]) => (
              <article key={action} className="card admin-stat-card">
                <p className="muted">{action}</p>
                <h3>{count}</h3>
              </article>
            ))}
          </div>

          <table className="admin-activity-table top-gap">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Admin</th>
                <th>Target</th>
                <th>Target ID</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogsForReport.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <span className="muted">No matching activity events.</span>
                  </td>
                </tr>
              ) : (
                filteredLogsForReport.map((log) => {
                  const adminUser = users.find((user) => user.id === log.admin_id);
                  const actionClass = log.action.includes("product_")
                    ? "action-product"
                    : log.action.includes("suspension")
                      ? "action-security"
                      : "action-default";
                  const badgeType = log.action.includes("product_")
                    ? "product"
                    : log.action.includes("suspension")
                      ? "danger"
                      : "default";

                  return (
                    <tr key={log.id} className={actionClass}>
                      <td>{new Date(log.created_at).toLocaleString()}</td>
                      <td className="action-badge-cell">
                        <span className={`badge badge-${badgeType}`}>{log.action}</span>
                      </td>
                      <td>
                        {adminUser ? (
                          <>
                            <strong>{adminUser.full_name || adminUser.email}</strong>
                            <br />
                            <small>{adminUser.email}</small>
                          </>
                        ) : (
                          <span className="muted">System</span>
                        )}
                      </td>
                      <td>{log.target_type}</td>
                      <td>
                        <code>{log.target_id}</code>
                      </td>
                      <td>
                        <details>
                          <summary>View</summary>
                          <pre>{JSON.stringify(log.details, null, 2)}</pre>
                        </details>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </section>
      )}

      {activeTab === "unpaid" && (
        <section className="top-gap card section-card">
          <div className="section-head">
            <h2>Unpaid Auction Orders</h2>
            <span className="muted">{unpaidTotal} winner(s) haven't paid yet</span>
          </div>

          {isLoadingUnpaid && <p className="muted">Loading...</p>}

          {!isLoadingUnpaid && unpaidOrders.length === 0 && (
            <p className="muted" style={{ marginTop: "1rem" }}>
              No unpaid orders - all auction winners have paid! 🎉
            </p>
          )}

          {!isLoadingUnpaid && unpaidOrders.length > 0 && (
            <div style={{ overflowX: "auto", marginTop: "1rem" }}>
              <table className="data-table" style={{ width: "100%" }}>
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Email</th>
                    <th>Product</th>
                    <th>Winning Bid</th>
                    <th>Hours Pending</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {unpaidOrders.map((order) => {
                    let statusColor = "#2ecc71"; // green, < 4 hours
                    if (order.hours_pending >= 24) {
                      statusColor = "#e74c3c"; // red, 24+ hours
                    } else if (order.hours_pending >= 4) {
                      statusColor = "#f39c12"; // orange, 4-24 hours
                    }

                    return (
                      <tr key={order.order_id}>
                        <td>{order.customer_name || "Unknown"}</td>
                        <td>{order.customer_email}</td>
                        <td>{order.product_name}</td>
                        <td>BHD {order.winning_bid_amount}</td>
                        <td style={{ color: statusColor, fontWeight: "bold" }}>
                          {order.hours_pending.toFixed(1)}h
                        </td>
                        <td>{new Date(order.created_at).toLocaleString()}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {activeTab === "health" && (
        <section className="top-gap card section-card">
          <h2>System Health</h2>
          <p className="muted">{healthText}</p>
          <p className="muted">Last checked: {healthCheckedAt || "-"}</p>
          <button type="button" className="ghost-btn" onClick={() => void checkHealth()}>
            Recheck
          </button>
        </section>
      )}
    </main>
  );
}
