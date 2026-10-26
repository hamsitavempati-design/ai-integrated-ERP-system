
(() => {
    "use strict";

    // =========================================================
    // DOM HELPERS
    // =========================================================

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) =>
        Array.from(root.querySelectorAll(selector));

    const state = {
        user: null,
        chart: null,

        metrics: {
            revenue: 282176,
            units: 2182,
            lowStock: 10,
            suppliers: 3,
            orders: 9,
            products: 13,
            average: 129.32
        },

        products: [
            { name: "Full Cream Milk 1L", category: "Dairy", stock: 24, reorder: 50, units: 420, price: 68, icon: "🥛" },
            { name: "Basmati Rice 5kg", category: "Groceries", stock: 42, reorder: 60, units: 310, price: 480, icon: "🌾" },
            { name: "Bathing Soap Pack", category: "Personal Care", stock: 18, reorder: 40, units: 285, price: 145, icon: "🧼" },
            { name: "Sunflower Oil 1L", category: "Groceries", stock: 31, reorder: 45, units: 260, price: 145, icon: "🫙" },
            { name: "Shampoo 340ml", category: "Hair Care", stock: 22, reorder: 35, units: 225, price: 210, icon: "🧴" },
            { name: "Baby Diapers M", category: "Baby Care", stock: 16, reorder: 30, units: 190, price: 399, icon: "🧷" },
            { name: "Toor Dal 1kg", category: "Groceries", stock: 38, reorder: 40, units: 176, price: 168, icon: "🫘" },
            { name: "Face Moisturizer", category: "Skin Care", stock: 12, reorder: 25, units: 150, price: 299, icon: "🧴" },
            { name: "Curd 500g", category: "Dairy", stock: 20, reorder: 35, units: 142, price: 35, icon: "🥣" },
            { name: "Sanitary Pads Pack", category: "Personal Care", stock: 19, reorder: 28, units: 130, price: 120, icon: "📦" }
        ]
    };

    const salesLabels = ["May", "Jun", "Jul", "Aug", "Sep", "Oct"];
    const salesValues = [36500, 41200, 38900, 46700, 49300, 69576];

    // =========================================================
    // UTILITIES
    // =========================================================

    function safe(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[character]);
    }

    function money(value) {
        return new Intl.NumberFormat("en-IN", {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 0
        }).format(Number(value) || 0);
    }

    function toast(message, isError = false) {
        const region = $("#toast-region");

        if (!region) {
            console.log(message);
            return;
        }

        const element = document.createElement("div");
        element.className = "toast" + (isError ? " error" : "");
        element.textContent = message;

        region.appendChild(element);
        setTimeout(() => element.remove(), 3600);
    }

    function screen(isLoggedIn) {
        const loginScreen = $("#login-screen");
        const appScreen = $("#app-screen");

        if (loginScreen) {
            loginScreen.classList.toggle("is-hidden", isLoggedIn);
        }

        if (appScreen) {
            appScreen.classList.toggle("is-hidden", !isLoggedIn);
        }
        $("#erp-chatbot")?.classList.toggle("is-hidden", !isLoggedIn);
    }

    
async function jsonResponse(response) {
    const body = await response.json().catch(() => ({}));

    if (!response.ok) {
        const detail = body.detail ?? body.message;

        let message;

        if (Array.isArray(detail)) {
            message = detail
                .map(item =>
                    typeof item === "string"
                        ? item
                        : item.msg || JSON.stringify(item)
                )
                .join("; ");
        } else if (typeof detail === "string") {
            message = detail;
        } else if (detail != null) {
            message = JSON.stringify(detail);
        } else {
            message = `Request failed (${response.status})`;
        }

        throw new Error(message);
    }

    return body;
}


    async function postJSON(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify(payload)
        });

        return jsonResponse(response);
    }

    // =========================================================
    // AUTHENTICATION
    // =========================================================

    function setInitials() {
        const profileButton = $("#profileButton");

        if (!profileButton) return;

        const email = state.user?.email || "Owner";

        profileButton.textContent =
            email.split("@")[0]
                .split(/[._ -]/)
                .map(part => part[0] || "")
                .join("")
                .slice(0, 2)
                .toUpperCase() || "OW";
    }

    async function checkSession() {
        try {
            const response = await fetch("/auth/me", {
                credentials: "same-origin",
                headers: { "Accept": "application/json" }
            });

            if (!response.ok) {
                state.user = null;
                screen(false);
                return;
            }

            const data = await response.json();

            state.user = data.user || data;

            screen(true);
            setInitials();

            await initDashboard();
        } catch (error) {
            console.error("Session check failed:", error);
            state.user = null;
            screen(false);
        }
    }

    async function login(event) {
        event.preventDefault();

        const emailInput = $("#username");
        const passwordInput = $("#password");
        const errorElement = $("#login-error");
        const loginButton = $("#login-button");

        const email = emailInput.value.trim();
        const password = passwordInput.value;

        errorElement.textContent = "";

        if (!emailInput.checkValidity()) {
            errorElement.textContent = "Enter a valid email address.";
            emailInput.focus();
            return;
        }

        if (!password) {
            errorElement.textContent = "Enter your password.";
            passwordInput.focus();
            return;
        }

        loginButton.disabled = true;
        loginButton.textContent = "Signing in...";

        try {
            const data = await postJSON("/auth/login", {
                email,
                password,
                remember_me: $("#rememberMe")?.checked ?? false
            });

            state.user = data.user || { email };

            screen(true);
            setInitials();

            await initDashboard();

            $("#loginForm").reset();
            toast("Signed in successfully.");
        } catch (error) {
            console.error("Login failed:", error);

            screen(false);

            if (error.message.includes("Failed to fetch")) {
                errorElement.textContent =
                    "Cannot connect to the server. Check that FastAPI is running.";
            } else if (error.message.includes("401") ||
                       /invalid credentials|incorrect password|invalid email/i.test(error.message)) {
                errorElement.textContent = "Invalid email or password.";
            } else {
                errorElement.textContent = error.message;
            }
        } finally {
            loginButton.disabled = false;
            loginButton.textContent = "Log in";
        }
    }

    async function logout() {
        try {
            const response = await fetch("/auth/logout", {
                method: "POST",
                credentials: "same-origin"
            });

            if (!response.ok && response.status !== 401) {
                throw new Error("Logout request failed.");
            }

            state.user = null;

            $("#loginForm")?.reset();

            if ($("#login-error")) {
                $("#login-error").textContent = "";
            }

            screen(false);
            closePopover();

            toast("You have been logged out.");
        } catch (error) {
            console.error("Logout failed:", error);
            toast(error.message, true);
        }
    }

    
const sidebarToggle = $("#sidebarToggle");
const appScreen = $("#app-screen");

if (sidebarToggle && appScreen) {
    sidebarToggle.addEventListener("click", () => {
        const isClosed = appScreen.classList.toggle("sidebar-closed");

        sidebarToggle.setAttribute(
            "aria-expanded",
            String(!isClosed)
        );

        sidebarToggle.setAttribute(
            "aria-label",
            isClosed ? "Open sidebar" : "Close sidebar"
        );
    });
}


    // =========================================================
    // PASSWORD VISIBILITY
    // =========================================================

    function togglePassword() {
        const input = $("#password");
        const button = $("#passwordToggle");

        if (!input || !button) return;

        const showPassword = input.type === "password";

        input.type = showPassword ? "text" : "password";

        button.setAttribute(
            "aria-label",
            showPassword ? "Hide password" : "Show password"
        );

        button.innerHTML = showPassword
            ? `<svg viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="1.8"
                    stroke-linecap="round" stroke-linejoin="round"
                    aria-hidden="true">
                    <path d="M3 3l18 18"></path>
                    <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"></path>
                    <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a15 15 0 0 1-3.1 3.8"></path>
                    <path d="M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7c1 0 1.9-.2 2.8-.5"></path>
                </svg>`
            : `<svg viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="1.8"
                    stroke-linecap="round" stroke-linejoin="round"
                    aria-hidden="true">
                    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                </svg>`;
    }

    // =========================================================
    // FORGOT PASSWORD
    // =========================================================

    async function forgotPassword(event) {
        event?.preventDefault();

        const emailInput = $("#username");
        const email = emailInput?.value.trim() || "";

        // Reuse the email field if populated; otherwise ask for it.
        const enteredEmail = email || window.prompt(
            "Enter the email address associated with your ERP owner account:"
        );

        if (!enteredEmail) return;

        const normalizedEmail = enteredEmail.trim();

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
    toast("Enter a valid email address.", true);
    return;
}

        try {
            await postJSON("/auth/forgot-password", {
                email: normalizedEmail
            });

            // The backend should use a generic response so account
            // existence is not revealed.
            toast("If the account exists, password reset instructions will be sent.");
        } catch (error) {
            console.error("Password reset request failed:", error);
            toast(error.message || "Could not request a password reset.", true);
        }
    }

    // =========================================================
    // RESET PASSWORD SCREEN
    // Opens automatically if the URL contains ?reset_token=...
    // =========================================================

    function showResetPasswordForm(token) {
        if ($("#resetPasswordOverlay")) {
            $("#resetPasswordOverlay").remove();
        }

        const overlay = document.createElement("div");
        overlay.id = "resetPasswordOverlay";

        overlay.style.cssText = [
            "position:fixed",
            "inset:0",
            "z-index:99999",
            "display:flex",
            "align-items:center",
            "justify-content:center",
            "padding:20px",
            "background:rgba(15,23,42,.65)"
        ].join(";");

        overlay.innerHTML = `
            <section style="
                width:100%;
                max-width:420px;
                padding:28px;
                border-radius:16px;
                background:#fff;
                color:#172033;
                box-shadow:0 20px 60px rgba(0,0,0,.2);
                font-family:Arial,sans-serif;
            ">
                <h2 style="margin:0 0 8px;">Reset your password</h2>
                <p style="margin:0 0 20px;color:#64748b;">
                    Choose a new password for your ERP owner account.
                </p>

                <form id="resetPasswordForm">
                    <label for="newPassword"
                        style="display:block;margin-bottom:6px;">
                        New password
                    </label>

                    <input id="newPassword" type="password"
                        required minlength="12" autocomplete="new-password"
                        style="box-sizing:border-box;width:100%;padding:12px;
                        margin-bottom:16px;border:1px solid #cbd5e1;
                        border-radius:8px;">

                    <label for="confirmPassword"
                        style="display:block;margin-bottom:6px;">
                        Confirm new password
                    </label>

                    <input id="confirmPassword" type="password"
                        required minlength="12" autocomplete="new-password"
                        style="box-sizing:border-box;width:100%;padding:12px;
                        margin-bottom:16px;border:1px solid #cbd5e1;
                        border-radius:8px;">

                    <p id="resetPasswordError" role="alert"
                        style="color:#dc2626;font-size:14px;"></p>

                    <button id="resetPasswordSubmit" type="submit"
                        style="width:100%;padding:12px;border:0;
                        border-radius:8px;background:#2563eb;color:#fff;
                        font-weight:600;cursor:pointer;">
                        Update password
                    </button>

                    <button id="cancelPasswordReset" type="button"
                        style="width:100%;padding:10px;margin-top:8px;
                        border:0;background:transparent;color:#475569;
                        cursor:pointer;">
                        Cancel
                    </button>
                </form>
            </section>
        `;

        document.body.appendChild(overlay);

        $("#cancelPasswordReset").onclick = () => {
            overlay.remove();

            const url = new URL(window.location.href);
            url.searchParams.delete("reset_token");
            window.history.replaceState({}, "", url.pathname + url.search + url.hash);
        };

        $("#resetPasswordForm").addEventListener("submit", async event => {
            event.preventDefault();

            const newPassword = $("#newPassword").value;
            const confirmPassword = $("#confirmPassword").value;
            const errorElement = $("#resetPasswordError");
            const submitButton = $("#resetPasswordSubmit");

            errorElement.textContent = "";

            if (newPassword.length < 12) {
                errorElement.textContent =
                    "Your password must contain at least 8 characters.";
                return;
            }

            if (newPassword !== confirmPassword) {
                errorElement.textContent = "The passwords do not match.";
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = "Updating...";

            try {
                await postJSON("/auth/reset-password", {
                    token,
                    password: newPassword,
                    confirm_password: confirmPassword
                });

                overlay.remove();

                const url = new URL(window.location.href);
                url.searchParams.delete("reset_token");

                window.history.replaceState(
                    {},
                    "",
                    url.pathname + url.search + url.hash
                );

                screen(false);

                toast("Password updated. You can now sign in.");
                $("#username")?.focus();
            } catch (error) {
                console.error("Password reset failed:", error);
                errorElement.textContent = error.message;
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = "Update password";
            }
        });
    }

    // =========================================================
    // PROFILE AND NOTIFICATIONS
    // =========================================================

    function closePopover() {
        const popoverElement = $("#header-popover");

        if (!popoverElement) return;

        popoverElement.classList.add("is-hidden");
        popoverElement.innerHTML = "";
    }

    function popover(type) {
        const element = $("#header-popover");

        if (!element) return;

        if (
            !element.classList.contains("is-hidden") &&
            element.dataset.type === type
        ) {
            closePopover();
            return;
        }

        element.dataset.type = type;
        element.classList.remove("is-hidden");

        if (type === "profile") {
            element.innerHTML = `
                <p class="popover-title">${safe(state.user?.email || "Signed-in user")}</p>
                <p class="popover-copy">Role: ${safe(state.user?.role || "Owner")}</p>
                <button class="popover-action" id="logoutButton">
                    Log out
                </button>
            `;

            $("#logoutButton").onclick = logout;
            const sidebarLogout = $("#sidebarLogout");

if (sidebarLogout) {
    sidebarLogout.onclick = logout;
}
        } else {
            element.innerHTML = `
                <p class="popover-title">Notifications</p>
                <p class="popover-copy">
                    Review inventory levels and products that may need restocking.
                </p>
                <button class="popover-action" id="notifyRestock">
                    Review restocking →
                </button>
            `;

            $("#notifyRestock").onclick = () => navigate("restocking");
        }
    }

    // =========================================================
    // CSV EXPORT
    // =========================================================

    function csv(filename, headers, rows) {
        const quote = value =>
            '"' + String(value ?? "").replace(/"/g, '""') + '"';

        const content = [headers, ...rows]
            .map(row => row.map(quote).join(","))
            .join("\r\n");

        const blob = new Blob(["\uFEFF" + content], {
            type: "text/csv;charset=utf-8"
        });

        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");

        anchor.href = url;
        anchor.download = filename;

        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();

        URL.revokeObjectURL(url);

        toast(`${filename} exported.`);
    }

    function table(headers, rows) {
        return `
            <div class="data-table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            ${headers.map(header => `<th>${safe(header)}</th>`).join("")}
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    // =========================================================
    // DASHBOARD FEATURE PAGES
    // =========================================================

    function renderFeature(page) {
        const titles = {
            restocking: "Restocking predictions",
            seasonal: "Seasonal & festival forecast",
            "root-cause": "Root cause analysis",
            inventory: "Product inventory",
            "high-sellers": "High-selling products"
        };

        const descriptions = {
            restocking: "Review products at or below their reorder level.",
            seasonal: "Review seasonal demand and festival planning.",
            "root-cause": "Investigate operational changes using evidence.",
            inventory: "Browse products and stock levels.",
            "high-sellers": "Review products ranked by units sold."
        };

        $("#featurePageHeading").textContent = titles[page];
        $("#featurePageDescription").textContent = descriptions[page];

        const body = $("#featurePageBody");

        if (!body) return;

        if (["restocking", "inventory", "high-sellers"].includes(page)) {
            let products = [...state.products];

            if (page === "restocking") {
                products = products
                    .filter(product => product.stock <= product.reorder)
                    .sort((a, b) =>
                        a.stock / a.reorder - b.stock / b.reorder
                    );
            }

            if (page === "high-sellers") {
                products.sort((a, b) => b.units - a.units);
            }

            if (page === "inventory") {
                products.sort((a, b) => a.name.localeCompare(b.name));
            }

            const rows = products.map(product => `
                <tr>
                    <td><strong>${safe(product.name)}</strong></td>
                    <td>${safe(product.category)}</td>
                    <td>${product.stock}</td>
                    <td>${product.reorder}</td>
                    <td>${product.units}</td>
                    <td>${money(product.price)}</td>
                    <td>
                        <span class="table-status ${
                            product.stock > product.reorder ? "good" : ""
                        }">
                            ${
                                product.stock <= product.reorder * 0.5
                                    ? "Critical"
                                    : product.stock <= product.reorder
                                        ? "Reorder"
                                        : "Healthy"
                            }
                        </span>
                    </td>
                    <td>
                        <button class="table-action"
                            data-product="${safe(product.name)}">
                            View details
                        </button>
                    </td>
                </tr>
            `).join("");

            body.innerHTML = `
                <article class="panel">
                    <div class="panel-heading">
                        <div>
                            <h2>${titles[page]}</h2>
                            <p>${products.length} products in the current view</p>
                        </div>
                        <button class="secondary-button" id="downloadTable">
                            Export CSV ↓
                        </button>
                    </div>

                    ${table([
                        "Product",
                        "Category",
                        "Stock",
                        "Reorder level",
                        "Units sold",
                        "Price",
                        "Status",
                        "Action"
                    ], rows)}
                </article>
            `;

            $("#downloadTable").onclick = () => csv(
                `${page}.csv`,
                ["Product", "Category", "Stock", "Reorder level", "Units sold", "Price"],
                products.map(product => [
                    product.name,
                    product.category,
                    product.stock,
                    product.reorder,
                    product.units,
                    product.price
                ])
            );

            $$("[data-product]", body).forEach(button => {
                button.onclick = () => {
                    const product = state.products.find(
                        item => item.name === button.dataset.product
                    );

                    if (product) {
                        toast(
                            `${product.name}: stock ${product.stock}, reorder level ${product.reorder}.`
                        );
                    }
                };
            });

            return;
        }

        if (page === "seasonal") {
            body.innerHTML = `
                <div class="insight-grid">
                    <article class="insight-card">
                        <span class="insight-value">Festival readiness</span>
                        <h3>Review high-demand essentials</h3>
                        <p>Compare previous festival sales and current stock before planning purchases.</p>
                        <button data-checklist="Festival demand review">
                            Create review checklist
                        </button>
                    </article>

                    <article class="insight-card">
                        <span class="insight-value">Seasonal planning</span>
                        <h3>Review seasonal changes</h3>
                        <p>Compare past sales, stock coverage and supplier lead times.</p>
                        <button data-checklist="Seasonal demand review">
                            Create review checklist
                        </button>
                    </article>

                    <article class="insight-card">
                        <h3>Export planning prompts</h3>
                        <p>Export a starter checklist for seasonal planning.</p>
                        <button id="seasonExport">Export prompts</button>
                    </article>

                    <article class="insight-card">
                        <h3>Verify before purchase</h3>
                        <p>Review proposed quantities before submitting purchase orders.</p>
                        <button id="seasonInventory">Review inventory</button>
                    </article>
                </div>
            `;

            $$("[data-checklist]").forEach(button => {
                button.onclick = () =>
                    toast(`${button.dataset.checklist} prepared for this session.`);
            });

            $("#seasonExport").onclick = () => csv(
                "seasonal-planning.csv",
                ["Area", "Action"],
                [
                    ["Festival", "Compare prior festival sales and stock"],
                    ["Seasonal", "Review seasonality and supplier lead times"],
                    ["Approval", "Review proposed order quantities"]
                ]
            );

            $("#seasonInventory").onclick = () => navigate("inventory");

            return;
        }

        body.innerHTML = `
            <div class="insight-grid">
                <article class="insight-card">
                    <span class="insight-value">${state.metrics.lowStock}</span>
                    <h3>Products at reorder threshold</h3>
                    <p>Review sales velocity, delayed replenishment and stock accuracy.</p>
                    <button id="rcaStock">Inspect low-stock items</button>
                </article>

                <article class="insight-card">
                    <span class="insight-value">${state.metrics.suppliers}</span>
                    <h3>Supplier risk signals</h3>
                    <p>Review supplier delivery reliability and delays.</p>
                    <button id="rcaSupplier">Review supplier signals</button>
                </article>

                <article class="insight-card">
                    <h3>Sales investigation checklist</h3>
                    <p>Compare units sold, discounts, stockouts and previous periods.</p>
                    <button id="rcaExport">Export checklist</button>
                </article>

                <article class="insight-card">
                    <h3>Root-cause workflow</h3>
                    <p>Define the issue, compare records, validate causes and assign action.</p>
                    <button id="rcaWorkflow">Show workflow</button>
                </article>
            </div>
        `;

        $("#rcaStock").onclick = () => navigate("restocking");

        $("#rcaSupplier").onclick = () =>
            toast("Connect supplier records to investigate supplier risks.");

        $("#rcaExport").onclick = () => csv(
            "root-cause-checklist.csv",
            ["Step", "Action"],
            [
                ["1", "Describe the issue and timeframe"],
                ["2", "Compare sales, inventory and purchase records"],
                ["3", "Validate possible causes"],
                ["4", "Assign corrective action and owner"]
            ]
        );

        $("#rcaWorkflow").onclick = () =>
            toast("Workflow: define, compare, validate and assign action.");
    }

    // =========================================================
    // NAVIGATION
    // =========================================================

    function navigate(page) {
        const pages = {
            overview: [
                "Overview",
                "A clear view of your store's performance and operations."
            ],
            restocking: [
                "Restocking predictions",
                "Review products that may need replenishment."
            ],
            seasonal: [
                "Seasonal & festival forecast",
                "Plan for seasonal changes and festival demand."
            ],
            "root-cause": [
                "Root cause analysis",
                "Review evidence behind operational changes."
            ],
            inventory: [
                "Product inventory",
                "Browse the current product catalogue."
            ],
            "high-sellers": [
                "High-selling products",
                "Compare products by units sold."
            ]
        };

        if (!pages[page]) page = "overview";

        $("#pageTitle").textContent = pages[page][0];
        $("#pageSubtitle").textContent = pages[page][1];
        $("#breadcrumbCurrent").textContent = pages[page][0];

        $("#overview-page").classList.toggle("is-hidden", page !== "overview");

        $("#feature-page").classList.toggle(
            "is-hidden",
            page === "overview" || page === "search"
        );

        $("#search-page").classList.add("is-hidden");

        closePopover();

        if (page !== "overview") {
            renderFeature(page);
        }
    }

    // =========================================================
    // DASHBOARD PRODUCTS AND CHART
    // =========================================================

    function renderTop() {
        const list = $("#topProductsList");

        if (!list) return;

        list.innerHTML = [...state.products]
            .sort((a, b) => b.units - a.units)
            .slice(0, 5)
            .map(product => `
                <div class="product-row">
                    <span class="product-thumb">${product.icon}</span>

                    <div>
                        <div class="product-name">${safe(product.name)}</div>
                        <div class="product-category">${safe(product.category)}</div>
                    </div>

                    <div class="product-units">
                        ${product.units}
                        <small>units sold</small>
                    </div>
                </div>
            `).join("");
    }

    function renderChart(count = 6) {
        const canvas = $("#salesChart");

        if (!canvas || typeof Chart === "undefined") return;

        if (state.chart) {
            state.chart.destroy();
        }

        state.chart = new Chart(canvas, {
            type: "line",

            data: {
                labels: salesLabels.slice(-count),

                datasets: [{
                    label: "Revenue",
                    data: salesValues.slice(-count),
                    borderColor: "#2864e8",
                    backgroundColor: "rgba(40,100,232,.10)",
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2.5,
                    pointRadius: 3,
                    pointBackgroundColor: "#fff",
                    pointBorderWidth: 2,
                    pointBorderColor: "#2864e8"
                }]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,

                plugins: {
                    legend: { display: false },

                    tooltip: {
                        callbacks: {
                            label: context => " Revenue: " + money(context.raw)
                        }
                    }
                },

                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: "#8b98aa" }
                    },

                    y: {
                        beginAtZero: true,
                        grid: { color: "#edf1f6" },
                        ticks: {
                            color: "#8b98aa",
                            callback: value => "₹" + value / 1000 + "k"
                        }
                    }
                }
            }
        });
    }

    async function loadMetrics() {
        try {
            const response = await fetch("/api/stats", {
                credentials: "same-origin"
            });

            if (!response.ok) return;

            const data = await response.json();

            const aliases = {
                revenue: ["total_sales_revenue", "total_revenue", "sales_revenue"],
                units: ["total_sales_quantity", "total_units_sold", "units_sold"],
                lowStock: ["low_stock_products", "low_stock_count"],
                suppliers: ["supplier_risk_count", "supplier_risks"],
                orders: ["pending_purchase_orders", "pending_orders"],
                products: ["product_count", "total_products"],
                average: ["average_selling_price", "avg_selling_price"]
            };

            for (const [key, possibleKeys] of Object.entries(aliases)) {
                const foundKey = possibleKeys.find(
                    candidate => data[candidate] !== undefined
                );

                if (foundKey) {
                    state.metrics[key] = Number(data[foundKey]) || 0;
                }
            }
        } catch (error) {
            console.error("Could not load dashboard metrics:", error);
        }
    }

    function updateKpis() {
        const values = {
            "#kpiRevenue": money(state.metrics.revenue),
            "#kpiUnits": state.metrics.units.toLocaleString("en-IN"),
            "#kpiLowStock": state.metrics.lowStock,
            "#kpiSuppliers": state.metrics.suppliers,
            "#kpiOrders": state.metrics.orders,
            "#kpiProducts": state.metrics.products,
            "#kpiAverage": new Intl.NumberFormat("en-IN", {
                style: "currency",
                currency: "INR",
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).format(state.metrics.average)
        };

        for (const [selector, value] of Object.entries(values)) {
            const element = $(selector);

            if (element) {
                element.textContent = value;
            }
        }
    }

    async function initDashboard() {
        updateKpis();
        renderTop();

        renderChart(Number($("#salesRange")?.value || 6));

        await loadMetrics();

        updateKpis();
        renderTop();
    }

    // =========================================================
    // GLOBAL SEARCH
    // =========================================================

    function search(query) {
        const originalQuery = query.trim();
        const normalizedQuery = originalQuery.toLowerCase();

        if (!normalizedQuery) {
            navigate("overview");
            return;
        }

        $("#pageTitle").textContent = "Search results";
        $("#pageSubtitle").textContent =
            `Results matching "${originalQuery}"`;

        $("#breadcrumbCurrent").textContent = "Search results";

        $("#overview-page").classList.add("is-hidden");
        $("#feature-page").classList.add("is-hidden");
        $("#search-page").classList.remove("is-hidden");

        const products = state.products.filter(product =>
            `${product.name} ${product.category}`
                .toLowerCase()
                .includes(normalizedQuery)
        );

        const features = [
            ["Restocking predictions", "restocking"],
            ["Monthly sales", "overview"],
            ["Seasonal & festival forecast", "seasonal"],
            ["Root cause analysis", "root-cause"],
            ["Product inventory", "inventory"],
            ["High-selling products", "high-sellers"]
        ].filter(feature =>
            feature.join(" ").toLowerCase().includes(normalizedQuery)
        );

        $("#searchSummary").textContent =
            `${products.length + features.length} result(s)`;

        const results = [
            ...products.map(product => `
                <div class="search-result">
                    <div>
                        <strong>${safe(product.name)}</strong>
                        <small>
                            ${safe(product.category)} · Stock ${product.stock}
                        </small>
                    </div>

                    <button class="table-action"
                        data-product="${safe(product.name)}">
                        Details
                    </button>
                </div>
            `),

            ...features.map(feature => `
                <div class="search-result">
                    <strong>${safe(feature[0])}</strong>

                    <button class="table-action"
                        data-searchpage="${safe(feature[1])}">
                        Open
                    </button>
                </div>
            `)
        ];

        $("#searchResults").innerHTML = results.length
            ? `<div class="search-results-list">${results.join("")}</div>`
            : '<div class="empty-note">No results. Try a product, category, or feature.</div>';

        $$("[data-product]").forEach(button => {
            button.onclick = () => {
                const product = state.products.find(
                    item => item.name === button.dataset.product
                );

                if (product) {
                    toast(
                        `${product.name}: stock ${product.stock}; reorder level ${product.reorder}.`
                    );
                }
            };
        });

        $$("[data-searchpage]").forEach(button => {
            button.onclick = () => navigate(button.dataset.searchpage);
        });
    }

    // =========================================================
    // EVENT LISTENERS
    // =========================================================

    function events() {
        // Login
        $("#loginForm")?.addEventListener("submit", login);

        // Password visibility
        $("#passwordToggle")?.addEventListener("click", togglePassword);

        // Focus the email field
        $("#emailButton")?.addEventListener("click", event => {
            event.preventDefault();
            $("#username")?.focus();
        });

        // Google OAuth: backend must implement the callback.
        $("#googleButton")?.addEventListener("click", event => {
            event.preventDefault();
            window.location.href = "/auth/google";
        });

        // Password reset request
        $("#forgotPassword")?.addEventListener("click", forgotPassword);

        // Profile and notifications
        $("#profileButton")?.addEventListener("click", () => popover("profile"));

        $("#notificationButton")?.addEventListener(
            "click",
            () => popover("notifications")
        );

        // Home / brand
        $("#brandHome")?.addEventListener("click", event => {
            event.preventDefault();
            navigate("overview");
        });

        // Export report
        $("#exportReport")?.addEventListener("click", () => {
            csv(
                "erp-overview-report.csv",
                ["Metric", "Value"],
                Object.entries(state.metrics)
            );
        });

        // Refresh dashboard
        $("#refreshDashboard")?.addEventListener("click", async () => {
            await loadMetrics();
            updateKpis();
            renderTop();
            renderChart(Number($("#salesRange")?.value || 6));

            toast("Dashboard refreshed.");
        });

        // Chart range
        $("#salesRange")?.addEventListener("change", event => {
            renderChart(Number(event.target.value));
        });

        // Back to overview
        $("#backOverview")?.addEventListener("click", () => {
            navigate("overview");
        });

        // Navigation buttons
        $$("[data-page]").forEach(button => {
            button.addEventListener("click", () => {
                navigate(button.dataset.page);
            });
        });

        // Global search
        $("#globalSearch")?.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                search(event.currentTarget.value);
            }
        });

        // Keyboard shortcuts
        document.addEventListener("keydown", event => {
            if (
                (event.ctrlKey || event.metaKey) &&
                event.key.toLowerCase() === "k"
            ) {
                event.preventDefault();
                $("#globalSearch")?.focus();
            }

            if (event.key === "Escape") {
                closePopover();
            }
        });

        // Close popover when clicking outside the top bar
        document.addEventListener("click", event => {
            if (!event.target.closest(".topbar-actions")) {
                closePopover();
            }
        });
    }

/* =========================================
   ERP ASSISTANT CHATBOT
========================================= */
let erpChatHistory = [];
let erpChatBusy = false;

function addErpChatMessage(text, sender) {
  const messages = $("#erp-chat-messages");
  if (!messages) return;

  const bubble = document.createElement("div");
  bubble.className = `erp-message ${sender}`;
  bubble.textContent = String(text ?? "");
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

async function sendErpChatMessage(event) {
  event.preventDefault();

  if (erpChatBusy) return;

  const input = $("#erp-chat-input");
  const sendButton = $("#erp-chat-send");
  const prompt = input?.value.trim();

  if (!prompt) return;

  input.value = "";
  addErpChatMessage(prompt, "user");

  erpChatHistory.push({ role: "user", content: prompt });
const historyForRequest = [...erpChatHistory];
  erpChatBusy = true;
  sendButton.disabled = true;
  addErpChatMessage("Thinking…", "bot");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({
        prompt,
        chat_history: historyForRequest
      })
    });

    const data = await response.json();
    const thinking = $("#erp-chat-messages")?.lastElementChild;

    if (thinking?.textContent === "Thinking…") {
      thinking.remove();
    }

    if (!response.ok) {
      throw new Error(
        data.response || data.detail || "The request failed."
      );
    }

    const answer = String(
      data.response || "I received an empty response."
    );

    addErpChatMessage(answer, "bot");
    erpChatHistory.push({ role: "assistant", content: answer });
  } catch (error) {
    const thinking = $("#erp-chat-messages")?.lastElementChild;

    if (thinking?.textContent === "Thinking…") {
      thinking.remove();
    }

    console.error("ERP chatbot error:", error);
    addErpChatMessage(
      "Sorry, I couldn't connect to the ERP Assistant. Please try again.",
      "bot"
    );
  } finally {
    erpChatBusy = false;
    if (sendButton) sendButton.disabled = false;
    input?.focus();
  }
}

function openErpChat() {
  $("#erp-chat-window")?.classList.remove("is-hidden");
  $("#erp-robot-launcher")?.classList.add("is-hidden");
  $("#erp-chat-input")?.focus();
}

function closeErpChat() {
  $("#erp-chat-window")?.classList.add("is-hidden");
  $("#erp-robot-launcher")?.classList.remove("is-hidden");
}

/* Register chatbot controls */
$("#erp-robot-launcher")?.addEventListener("click", openErpChat);
$("#erp-chat-close")?.addEventListener("click", closeErpChat);
$("#erp-chat-form")?.addEventListener("submit", sendErpChatMessage);

    // =========================================================
    // STARTUP
    // =========================================================

    document.addEventListener("DOMContentLoaded", () => {
        events();

        // Handle password-reset links sent by the backend.
        const url = new URL(window.location.href);
        const resetToken = url.searchParams.get("reset_token");

        if (resetToken) {
            screen(false);
            showResetPasswordForm(resetToken);
            return;
        }

        checkSession();
    });

})();
