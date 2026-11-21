
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
            average: 129.32,
            openRca: 0,
            seasonality: 0
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
        ],
        activeDataset: "Products.csv",
        activeDatasetOffset: 0,
        activePageSize: 50,
        selectedSearchQuery: "",
        chartLabels: null,
        chartValues: null
    };

    let welcomeSlideIndex = 0;
    let welcomeAutoplayTimer = null;

    function recordActivity(action, details = "") {
        try {
            const log = JSON.parse(localStorage.getItem("erpActivity") || "[]");
            log.unshift({ action, details, at: new Date().toISOString() });
            localStorage.setItem("erpActivity", JSON.stringify(log.slice(0, 60)));
        } catch (error) {
            console.warn("Could not save activity history:", error);
        }
    }

    function readActivity() {
        try { return JSON.parse(localStorage.getItem("erpActivity") || "[]"); }
        catch { return []; }
    }

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

    function getPreferences() {
        try { return JSON.parse(localStorage.getItem("erpPreferences") || "{}"); }
        catch { return {}; }
    }

    function applyPreferences() {
        const prefs = getPreferences();
        document.body.classList.toggle("compact-tables", !!prefs.compact);
        $("#erp-chatbot")?.classList.toggle("is-hidden", !state.user || prefs.assistant === false);
        $("#notificationButton")?.classList.toggle("is-hidden", prefs.lowStock === false);
        const name = prefs.workspace || "ERP System";
        const brandName = $("#brandHome strong");
        if (brandName) brandName.textContent = name;
        document.title = name;
        const regionTag = $("#workspaceRegion");
        if (regionTag) regionTag.textContent = prefs.region || "Telangana";
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
        if (isLoggedIn) stopWelcomeAutoplay();
        applyPreferences();
        $("#erp-chatbot")?.classList.toggle("is-hidden", !isLoggedIn || getPreferences().assistant === false);
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
            $("#loginForm").reset();
            toast("Signed in successfully.");
            try {
                await initDashboard();
            } catch (dashboardError) {
                console.error("Dashboard initialization failed after sign-in:", dashboardError);
                toast("You are signed in, but some workspace data could not be loaded.", true);
            }
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

    function stopWelcomeAutoplay() {
        window.clearTimeout(welcomeAutoplayTimer);
        welcomeAutoplayTimer = null;
    }

    function startWelcomeAutoplay() {
        stopWelcomeAutoplay();
        const loginScreen = $("#login-screen");
        const accountScreen = $("#account-screen");
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
            document.hidden || !loginScreen || loginScreen.classList.contains("is-hidden") ||
            !accountScreen || !accountScreen.classList.contains("is-hidden")) {
            return;
        }

        welcomeAutoplayTimer = window.setTimeout(() => {
            setWelcomeSlide(welcomeSlideIndex + 1);
        }, 4000);
    }

    function setWelcomeSlide(index) {
        const slides = $$(".welcome-slide", $("#welcome-track"));
        const links = $$("[data-welcome-nav]");
        const track = $("#welcome-track");
        if (!track || !slides.length) return;

        welcomeSlideIndex = (index + slides.length) % slides.length;
        track.style.transform = `translateX(-${welcomeSlideIndex * 100}%)`;
        slides.forEach((slide, slideIndex) => {
            if (slideIndex === welcomeSlideIndex) {
                slide.removeAttribute("aria-hidden");
                slide.removeAttribute("inert");
            } else {
                slide.setAttribute("aria-hidden", "true");
                slide.setAttribute("inert", "");
            }
        });
        links.forEach((link, linkIndex) => {
            link.setAttribute("aria-current", String(linkIndex === welcomeSlideIndex));
        });
        startWelcomeAutoplay();
    }

    function setAccountMode(mode) {
        const create = mode === "create";
        const registerForm = $("#registerForm");
        const loginForm = $("#loginForm");
        const createTab = $("#createAccountTab");
        const loginTab = $("#loginTab");
        if (!registerForm || !loginForm || (create && createTab?.disabled)) return;

        registerForm.classList.toggle("is-hidden", !create);
        loginForm.classList.toggle("is-hidden", create);
        createTab?.setAttribute("aria-selected", String(create));
        loginTab?.setAttribute("aria-selected", String(!create));
        $("#account-title").textContent = create ? "Create your owner account" : "Welcome back";
        $("#account-subtitle").textContent = create
            ? "Set up secure access to your ERP workspace."
            : "Log in to continue to your workspace.";
        $("#register-error").textContent = "";
        $("#login-error").textContent = "";
        $("#registration-status").textContent = create
            ? "Create the first owner account for this workspace."
            : $("#createAccountTab").disabled
                ? "This workspace is already set up. Sign in with the owner account."
                : "";
    }

    async function openWorkspaceAccess() {
        stopWelcomeAutoplay();
        $("#welcome-shell")?.classList.add("is-hidden");
        $("#account-screen")?.classList.remove("is-hidden");

        const createTab = $("#createAccountTab");
        const status = $("#registration-status");
        const accessButton = $("#workspaceAccess");
        if (!createTab || !status) return;

        createTab.disabled = true;
        setAccountMode("login");
        status.textContent = "Checking workspace setup…";
        if (accessButton) accessButton.disabled = true;

        try {
            const response = await fetch("/auth/setup-status", {
                credentials: "same-origin",
                headers: { "Accept": "application/json" }
            });
            const setup = await jsonResponse(response);
            createTab.disabled = Boolean(setup.owner_exists);
            setAccountMode(setup.owner_exists ? "login" : "create");
        } catch (error) {
            createTab.disabled = true;
            setAccountMode("login");
            status.textContent = "Workspace setup could not be checked. Please try again.";
        } finally {
            if (accessButton) accessButton.disabled = false;
        }
    }

    function returnToWelcome() {
        $("#account-screen")?.classList.add("is-hidden");
        $("#welcome-shell")?.classList.remove("is-hidden");
        setWelcomeSlide(0);
    }

    async function registerOwner(event) {
        event.preventDefault();
        const form = $("#registerForm");
        const emailInput = $("#registerEmail");
        const passwordInput = $("#registerPassword");
        const confirmInput = $("#registerConfirmPassword");
        const error = $("#register-error");
        const button = $("#register-button");
        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmInput.value;
        error.textContent = "";

        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        if (password !== confirmPassword) {
            error.textContent = "The passwords do not match.";
            confirmInput.focus();
            return;
        }

        button.disabled = true;
        button.textContent = "Creating account…";
        let accountCreated = false;
        try {
            await postJSON("/auth/register-owner", {
                email,
                password,
                confirm_password: confirmPassword
            });
            accountCreated = true;
            $("#createAccountTab").disabled = true;
            $("#registration-status").textContent = "Account created. Signing you in…";

            const data = await postJSON("/auth/login", {
                email,
                password,
                remember_me: false
            });
            state.user = data.user || { email };
            screen(true);
            setInitials();
            form.reset();
            toast("Owner account created. You are signed in.");
            try {
                await initDashboard();
            } catch (dashboardError) {
                console.error("Dashboard initialization failed after account creation:", dashboardError);
                toast("Your account is ready, but some workspace data could not be loaded.", true);
            }
        } catch (requestError) {
            if (accountCreated) {
                setAccountMode("login");
                $("#username").value = email;
                $("#login-error").textContent = "Your account was created. Log in with your new credentials to continue.";
            } else if (/already set up|already exists|registration is closed/i.test(requestError.message)) {
                button.disabled = true;
                $("#createAccountTab").disabled = true;
                setAccountMode("login");
                $("#registration-status").textContent = "This workspace is already set up. Sign in with the owner account.";
            } else {
                error.textContent = requestError.message || "Could not create the account. Please try again.";
            }
        } finally {
            if (!accountCreated) {
                button.disabled = false;
                button.textContent = "Create owner account";
            }
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
            returnToWelcome();
            closePopover();

            toast("You have been logged out.");
        } catch (error) {
            console.error("Logout failed:", error);
            toast(error.message, true);
        }
    }

    
const sidebarToggle = $("#sidebarToggle");
const appScreen = $("#app-screen");
const sidebarElement = $("#appSidebar");
const sidebarBrand = $("#brandHome");
let sidebarPinnedOpen = false;
$$(".sidebar-nav .sidebar-link").forEach(button => {
    const label = button.textContent.trim().replace(/\s+/g, " ");
    button.setAttribute("aria-label", label);
    button.title = label;
});
$("#sidebarLogout")?.setAttribute("aria-label", "Sign out");
if ($("#sidebarLogout")) $("#sidebarLogout").title = "Sign out";

function setSidebarCollapsed(collapsed) {
    if (!appScreen) return;
    appScreen.classList.toggle("sidebar-collapsed", collapsed);
    appScreen.classList.remove("sidebar-closed");
    sidebarBrand?.setAttribute("aria-expanded", String(!collapsed));
    if (sidebarToggle) {
        sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
        sidebarToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
    }
}

function closeSidebarOnMobileNavigation() {
    if (window.matchMedia("(max-width: 760px)").matches) {
        sidebarPinnedOpen = false;
        setSidebarCollapsed(true);
    }
}

if (sidebarToggle && appScreen) {
    sidebarToggle.addEventListener("click", () => {
        sidebarPinnedOpen = appScreen.classList.contains("sidebar-collapsed");
        setSidebarCollapsed(!sidebarPinnedOpen);
    });
}

if (sidebarElement && sidebarBrand) {
    const isSmallScreen = () => window.matchMedia("(max-width: 760px)").matches;
    sidebarBrand.addEventListener("mouseenter", () => {
        if (!isSmallScreen() && !sidebarPinnedOpen) setSidebarCollapsed(false);
    });
    sidebarBrand.addEventListener("focus", () => {
        if (!isSmallScreen() && !sidebarPinnedOpen) setSidebarCollapsed(false);
    });
    sidebarElement.addEventListener("mouseleave", () => {
        if (!isSmallScreen() && !sidebarPinnedOpen) setSidebarCollapsed(true);
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
                        border-radius:8px;background:#76506f;color:#fff;
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
                <button class="popover-action" id="openProfilePage">View account details</button>
            `;

            $("#openProfilePage").onclick = () => { closePopover(); navigate("profile"); };
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

    async function requestJSON(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: { "Accept": "application/json", ...(options.headers || {}) },
            ...options
        });
        return jsonResponse(response);
    }

    async function fetchDataset(filename, offset = 0, limit = 50) {
        return requestJSON(`/api/data?dataset=${encodeURIComponent(filename)}&offset=${offset}&limit=${limit}`);
    }

    async function loadUploadedDatasets(host) {
        if (!host) return;
        try {
            const result = await requestJSON("/api/datasets");
            host.innerHTML = `<h3>Connected datasets</h3><div class="file-summary-grid">${(result.datasets || []).map(item => `<div class="file-summary"><strong>${safe(item.name)}</strong><span>${item.rows} records · ${item.columns} fields</span><button type="button" class="link-button" data-open-dataset="${safe(item.name)}">Browse records →</button></div>`).join("")}</div>`;
            $$('[data-open-dataset]', host).forEach(button => button.addEventListener("click", () => { state.activeDataset = button.dataset.openDataset; state.activeDatasetOffset = 0; navigate("data"); }));
        } catch (error) { host.innerHTML = `<div class="empty-note">${safe(error.message)}</div>`; }
    }

    async function uploadDataset(file) {
        if (!file) return;
        if (file.size > 10 * 1024 * 1024) { toast("This file is larger than the 10 MB upload limit.", true); return; }
        const feedback = $("#uploadFeedback");
        if (feedback) feedback.textContent = `Validating ${file.name}…`;
        const formData = new FormData();
        formData.append("file", file);
        try {
            const response = await fetch("/upload", { method: "POST", credentials: "same-origin", body: formData });
            const result = await jsonResponse(response);
            recordActivity("Uploaded dataset", `${result.saved_as || file.name} · ${result.rows || 0} rows`);
            if (feedback) feedback.textContent = result.message || "Dataset uploaded successfully.";
            toast(result.message || "Dataset uploaded successfully.");
            await refreshDashboardData();
            if (state.activeDataset === result.saved_as) navigate("data");
            loadUploadedDatasets($("#uploadedDatasets"));
        } catch (error) {
            if (feedback) feedback.textContent = error.message;
            toast(error.message, true);
        } finally {
            $("#sidebarUploadInput").value = "";
        }
    }

    async function loadOperationalProducts() {
        try {
            const result = await requestJSON("/api/operational-products");
            state.products = result.products || [];
        } catch (error) {
            console.error("Could not load live product records:", error);
            toast("Could not refresh product records. Showing the last available view.", true);
        }
    }

    async function refreshDashboardData() {
        await loadMetrics();
        await loadOperationalProducts();
        updateKpis();
        renderTop();
        renderChart(Number($("#salesRange")?.value || 6));
        if ($("#insightRca")) $("#insightRca").textContent = state.metrics.openRca;
        if ($("#insightSeasonal")) $("#insightSeasonal").textContent = state.metrics.seasonality;
    }

    async function renderDataManagement(body) {
        body.innerHTML = `
            <article class="panel data-management-panel">
                <div class="data-toolbar">
                    <label class="field-compact">Dataset<select id="datasetSelect" aria-label="Choose a dataset"></select></label>
                    <span class="data-meta" id="datasetCount" aria-live="polite">Loading datasets…</span>
                    <label class="field-compact">Rows per page<select id="datasetPageSize"><option>25</option><option selected>50</option><option>100</option><option>250</option></select></label>
                    <button type="button" class="primary-button compact" id="createRecord">＋ Add record</button>
                    <button type="button" class="secondary-button" id="refreshDataset">↻ Refresh</button>
                </div>
                <div id="recordEditorHost"></div>
                <div id="datasetTableHost" aria-live="polite"></div>
                <div class="table-pagination"><span id="datasetPageState"></span><div><button type="button" class="secondary-button" id="datasetPrev">← Previous</button><button type="button" class="secondary-button" id="datasetNext">Next →</button></div></div>
            </article>`;

        const select = $("#datasetSelect", body);
        $("#datasetPageSize", body).value = String(state.activePageSize);
        const tableHost = $("#datasetTableHost", body);
        const editorHost = $("#recordEditorHost", body);
        let currentRows = [];
        let currentColumns = [];

        async function loadSelectedDataset() {
            const filename = select.value;
            state.activeDataset = filename;
            tableHost.innerHTML = '<div class="empty-note">Loading dataset records…</div>';
            try {
                const pageSize = Number($("#datasetPageSize", body).value) || 50;
                const result = await fetchDataset(filename, state.activeDatasetOffset, pageSize);
                if (state.activeDatasetOffset >= result.total && state.activeDatasetOffset > 0) {
                    state.activeDatasetOffset = Math.max(0, Math.floor((result.total - 1) / pageSize) * pageSize);
                    return loadSelectedDataset();
                }
                currentRows = result.rows || [];
                currentColumns = result.columns || [];
                const start = result.total ? state.activeDatasetOffset + 1 : 0;
                const end = Math.min(state.activeDatasetOffset + currentRows.length, result.total);
                $("#datasetCount", body).textContent = `${result.total} ${result.total === 1 ? "record" : "records"}`;
                $("#datasetPageState", body).textContent = result.total ? `Showing ${start}–${end} of ${result.total}` : "No records";
                $("#datasetPrev", body).disabled = state.activeDatasetOffset === 0;
                $("#datasetNext", body).disabled = end >= result.total;
                const rows = currentRows.map(({ row_index, record }) => `
                    <tr>${currentColumns.map(column => `<td>${safe(record[column]) || "—"}</td>`).join("")}
                    <td><div class="row-actions"><button type="button" data-edit-row="${row_index}">Edit</button><button type="button" class="danger" data-delete-row="${row_index}">Delete</button></div></td></tr>`).join("");
                tableHost.innerHTML = currentRows.length
                    ? `<div class="data-table-wrap"><table class="data-table"><thead><tr>${currentColumns.map(column => `<th>${safe(column)}</th>`).join("")}<th>Actions</th></tr></thead><tbody>${rows}</tbody></table></div>`
                    : '<div class="empty-note">No records yet. Add the first record to this dataset.</div>';
            } catch (error) {
                tableHost.innerHTML = `<div class="empty-note">${safe(error.message)}</div>`;
                $("#datasetCount", body).textContent = "Could not load records";
            }
        }

        function showRecordForm(rowIndex = null) {
            const row = rowIndex === null ? {} : currentRows.find(item => item.row_index === rowIndex)?.record || {};
            editorHost.innerHTML = `<form class="record-form" id="recordForm" novalidate>
                ${currentColumns.map(column => {
                    const required = ["Product ID", "Product Name", "Warehouse", "Order ID", "PO Number", "Supplier Name", "Customer ID", "Warehouse ID", "Warehouse Name", "Event Name", "Issue Type"].includes(column);
                    const type = /date/i.test(column) ? "date" : "text";
                    return `<label>${safe(column)}${required ? " *" : ""}<input name="${safe(column)}" type="${type}" value="${safe(row[column] || "")}" ${required ? "required" : ""} autocomplete="off"></label>`;
                }).join("")}
                <div class="form-actions"><button class="primary-button compact" type="submit">${rowIndex === null ? "Create record" : "Save changes"}</button><button class="secondary-button" type="button" data-cancel-editor>Cancel</button><span class="form-note">Changes are written to ${safe(select.value)}. A backup is saved automatically.</span></div>
            </form>`;
            $("#recordForm", editorHost).dataset.rowIndex = rowIndex === null ? "" : String(rowIndex);
            editorHost.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }

        try {
            const catalog = await requestJSON("/api/datasets");
            select.innerHTML = (catalog.datasets || []).map(item => `<option value="${safe(item.name)}">${safe(item.name)}</option>`).join("");
            if ([...select.options].some(option => option.value === state.activeDataset)) select.value = state.activeDataset;
            await loadSelectedDataset();
        } catch (error) {
            tableHost.innerHTML = `<div class="empty-note">${safe(error.message)}. Sign in again and retry.</div>`;
        }

        select.addEventListener("change", () => { state.activeDatasetOffset = 0; loadSelectedDataset(); });
        $("#datasetPageSize", body).addEventListener("change", event => { state.activePageSize = Number(event.target.value) || 50; state.activeDatasetOffset = 0; loadSelectedDataset(); });
        $("#datasetPrev", body).addEventListener("click", () => { state.activeDatasetOffset = Math.max(0, state.activeDatasetOffset - state.activePageSize); loadSelectedDataset(); });
        $("#datasetNext", body).addEventListener("click", () => { state.activeDatasetOffset += state.activePageSize; loadSelectedDataset(); });
        $("#refreshDataset", body).addEventListener("click", loadSelectedDataset);
        $("#createRecord", body).addEventListener("click", () => showRecordForm());
        body.onclick = async event => {
            const editButton = event.target.closest("[data-edit-row]");
            const deleteButton = event.target.closest("[data-delete-row]");
            if (event.target.closest("[data-cancel-editor]")) { editorHost.innerHTML = ""; return; }
            if (editButton) { showRecordForm(Number(editButton.dataset.editRow)); return; }
            if (deleteButton) {
                const index = Number(deleteButton.dataset.deleteRow);
                const record = currentRows.find(item => item.row_index === index)?.record;
                const label = record?.["Product Name"] || record?.["Product ID"] || record?.["Order ID"] || Object.values(record || {})[0] || "this row";
                if (!window.confirm(`Delete ${label} from ${select.value}? A backup will be retained.`)) return;
                deleteButton.disabled = true;
                try {
                    const result = await requestJSON("/api/data/records", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset: select.value, row_index: index }) });
                    recordActivity("Deleted record", `${select.value} · ${label}`);
                    toast(result.message || "Record deleted.");
                    await loadSelectedDataset();
            await refreshDashboardData();
                } catch (error) { toast(error.message, true); deleteButton.disabled = false; }
            }
        };
        editorHost.onsubmit = async event => {
            if (event.target.id !== "recordForm") return;
            event.preventDefault();
            const form = event.target;
            const values = Object.fromEntries(new FormData(form).entries());
            const indexValue = form.dataset.rowIndex;
            const payload = { dataset: select.value, record: values };
            if (indexValue !== "") payload.row_index = Number(indexValue);
            const submitButton = form.querySelector('[type="submit"]');
            submitButton.disabled = true; submitButton.textContent = "Saving…";
            try {
                if (indexValue === "") state.activeDatasetOffset = 0;
                const result = await requestJSON("/api/data/records", { method: indexValue === "" ? "POST" : "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
                const action = indexValue === "" ? "Created record" : "Updated record";
                recordActivity(action, select.value);
                editorHost.innerHTML = "";
                toast(result.message || "Record saved.");
                await loadSelectedDataset();
                await refreshDashboardData();
            } catch (error) {
                toast(error.message, true);
                submitButton.disabled = false; submitButton.textContent = indexValue === "" ? "Create record" : "Save changes";
            }
        };
    }

    async function renderSeasonality(body) {
        body.innerHTML = `<article class="panel"><div class="filter-toolbar"><label class="field-compact">Event type<select id="seasonType"><option value="">All event types</option></select></label><label class="field-compact">Region<select id="seasonRegion"><option value="">All regions</option></select></label><input id="seasonSearch" type="search" placeholder="Filter events or products" aria-label="Filter seasonal events"><button class="secondary-button" id="seasonExport">Export filtered events</button><button class="secondary-button" id="seasonChecklist">Download planning checklist</button></div><div id="seasonResults"></div></article>`;
        const host = $("#seasonResults", body);
        try {
            const result = await fetchDataset("Seasonality.csv", 0, 250);
            const records = result.rows || [];
            let filteredRecords = records;
            const types = [...new Set(records.map(row => row.record["Event Type"]).filter(Boolean))];
            const regions = [...new Set(records.map(row => row.record.Region).filter(Boolean))];
            $("#seasonType", body).innerHTML += types.map(value => `<option>${safe(value)}</option>`).join("");
            $("#seasonRegion", body).innerHTML += regions.map(value => `<option>${safe(value)}</option>`).join("");
            const render = () => {
                const type = $("#seasonType", body).value;
                const region = $("#seasonRegion", body).value;
                const query = $("#seasonSearch", body).value.trim().toLowerCase();
                const filtered = records.filter(({ record }) => (!type || record["Event Type"] === type) && (!region || record.Region === region) && (!query || Object.values(record).join(" ").toLowerCase().includes(query)));
                filteredRecords = filtered;
                host.innerHTML = filtered.length ? `<div class="insight-grid">${filtered.map(({ row_index, record }) => `<article class="insight-card"><span class="insight-value">${safe(record["Expected Impact"] || "Demand signal")}</span><h3>${safe(record["Event Name"])}</h3><p>${safe(record["Event Date"])} · ${safe(record.Region || "All regions")} · ${safe(record["Event Type"] || "Event")}</p><p>${safe(record["Product Name"] || record["Product ID"])} · ${safe(record.Confidence || "Confidence not set")} confidence</p><button type="button" data-season-product="${safe(record["Product Name"] || record["Product ID"])}">View related product data</button></article>`).join("")}</div>` : '<div class="empty-note">No seasonal records match these filters. Clear a filter or upload seasonality data.</div>';
                $$('[data-season-product]', body).forEach(button => button.addEventListener("click", () => search(button.dataset.seasonProduct)));
            };
            ["seasonType", "seasonRegion", "seasonSearch"].forEach(id => $("#" + id, body).addEventListener("input", render));
            ["seasonType", "seasonRegion"].forEach(id => $("#" + id, body).addEventListener("change", render));
            $("#seasonExport", body).addEventListener("click", () => csv("seasonality-events.csv", result.columns, filteredRecords.map(item => result.columns.map(column => item.record[column]))));
            $("#seasonChecklist", body).addEventListener("click", () => csv("seasonal-planning-checklist.csv", ["Event", "Date", "Product", "Region", "Demand impact", "Planning step", "Owner", "Status"], filteredRecords.map(({ record }) => [record["Event Name"], record["Event Date"], record["Product Name"] || record["Product ID"], record.Region, record["Expected Impact"], "Review historical demand, current stock and supplier lead time", "", "To do"])));
            render();
        } catch (error) { host.innerHTML = `<div class="empty-note">${safe(error.message)}</div>`; }
    }

    async function renderRootCause(body) {
        body.innerHTML = `<article class="panel"><div class="filter-toolbar"><label class="field-compact">Priority<select id="rcaPriority"><option value="">All priorities</option></select></label><label class="field-compact">Status<select id="rcaStatus"><option value="">All statuses</option></select></label><input id="rcaSearch" type="search" placeholder="Search issues, products, causes" aria-label="Filter root-cause issues"><button class="secondary-button" id="rcaExport">Export filtered issues</button></div><div id="rcaResults"></div></article>`;
        const host = $("#rcaResults", body);
        try {
            const result = await fetchDataset("RCA Insights.csv", 0, 250);
            const records = result.rows || [];
            const priorities = [...new Set(records.map(item => item.record.Priority).filter(Boolean))];
            const statuses = [...new Set(records.map(item => item.record.Status).filter(Boolean))];
            $("#rcaPriority", body).innerHTML += priorities.map(value => `<option>${safe(value)}</option>`).join("");
            $("#rcaStatus", body).innerHTML += statuses.map(value => `<option>${safe(value)}</option>`).join("");
            const render = () => {
                const priority = $("#rcaPriority", body).value; const status = $("#rcaStatus", body).value; const query = $("#rcaSearch", body).value.trim().toLowerCase();
                const filtered = records.filter(({ record }) => (!priority || record.Priority === priority) && (!status || record.Status === status) && (!query || Object.values(record).join(" ").toLowerCase().includes(query)));
                host.innerHTML = filtered.length ? `<div class="insight-grid">${filtered.map(({ row_index, record }) => `<article class="insight-card"><span class="insight-value">${safe(record.Priority || "Issue")}</span><h3>${safe(record["Issue Type"])} · ${safe(record["Product Name"] || record["Product ID"])}</h3><p>${safe(record["Main Reason"])}${record["Supporting Reason"] ? ` · ${safe(record["Supporting Reason"])}` : ""}</p><p><strong>Impact:</strong> ${safe(record["Business Impact"] || "Not specified")}<br><strong>Suggested action:</strong> ${safe(record["Suggested Action"] || "Review supporting data")}</p><div class="help-actions"><button type="button" data-rca-search="${safe(record["Product Name"] || record["Product ID"])}">Inspect related records</button><button type="button" data-rca-ask="${row_index}">Ask NORA</button><button type="button" data-rca-checklist="${row_index}">Export action checklist</button>${record.Status !== "Closed" ? `<button type="button" data-rca-close="${row_index}">Mark resolved</button>` : `<span class="table-status good">Closed</span>`}</div></article>`).join("")}</div>` : '<div class="empty-note">No issues match these filters.</div>';
                $$('[data-rca-search]', body).forEach(button => button.addEventListener("click", () => search(button.dataset.rcaSearch)));
                $$('[data-rca-ask]', body).forEach(button => button.addEventListener("click", () => { const record = records.find(item => item.row_index === Number(button.dataset.rcaAsk))?.record; if (!record) return; openErpChat(); const input = $("#erp-chat-input"); if (input) input.value = `Analyze the ${record["Issue Type"]} for ${record["Product Name"] || record["Product ID"]}. Consider this evidence: ${record["Main Reason"]}; impact: ${record["Business Impact"]}; suggested action: ${record["Suggested Action"]}.`; }));
                $$('[data-rca-checklist]', body).forEach(button => button.addEventListener("click", () => { const record = records.find(item => item.row_index === Number(button.dataset.rcaChecklist))?.record; if (!record) return; csv("rca-action-checklist.csv", ["Issue", "Product", "Priority", "Reason", "Business impact", "Suggested action", "Owner", "Due date", "Status"], [[record["Issue Type"], record["Product Name"] || record["Product ID"], record.Priority, record["Main Reason"], record["Business Impact"], record["Suggested Action"], "", "", record.Status || "Open"]]); }));
                $$('[data-rca-close]', body).forEach(button => button.addEventListener("click", async () => {
                    const index = Number(button.dataset.rcaClose); const item = records.find(row => row.row_index === index); if (!item) return;
                    button.disabled = true;
                    try { const updated = { ...item.record, Status: "Closed" }; await requestJSON("/api/data/records", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset: "RCA Insights.csv", row_index: index, record: updated }) }); recordActivity("Resolved RCA issue", updated["Product Name"] || updated["Product ID"]); toast("Issue marked resolved."); await refreshDashboardData(); renderRootCause(body); }
                    catch (error) { toast(error.message, true); button.disabled = false; }
                }));
            };
            ["rcaPriority", "rcaStatus", "rcaSearch"].forEach(id => { $("#" + id, body).addEventListener("input", render); $("#" + id, body).addEventListener("change", render); });
            $("#rcaExport", body).addEventListener("click", () => { const query = $("#rcaSearch", body).value.trim().toLowerCase(); const filtered = records.filter(({ record }) => (!$("#rcaPriority", body).value || record.Priority === $("#rcaPriority", body).value) && (!$("#rcaStatus", body).value || record.Status === $("#rcaStatus", body).value) && (!query || Object.values(record).join(" ").toLowerCase().includes(query))); csv("root-cause-insights.csv", result.columns, filtered.map(item => result.columns.map(column => item.record[column]))); });
            render();
        } catch (error) { host.innerHTML = `<div class="empty-note">${safe(error.message)}</div>`; }
    }

    // =========================================================
    // DASHBOARD FEATURE PAGES
    // =========================================================

    async function renderFeature(page) {
        const titles = {
            restocking: "Restocking predictions",
            seasonal: "Seasonal & festival forecast",
            "root-cause": "Root cause analysis",
            inventory: "Product inventory",
            "high-sellers": "High-selling products",
            data: "Data management",
            upload: "Upload & validate",
            activity: "Activity history",
            profile: "My profile",
            settings: "Settings",
            help: "Help & documentation"
        };

        const descriptions = {
            restocking: "Review products at or below their reorder level.",
            seasonal: "Review seasonal demand and festival planning.",
            "root-cause": "Investigate operational changes using evidence.",
            inventory: "Browse products and stock levels.",
            "high-sellers": "Review products ranked by units sold.",
            data: "Browse, create, update, and delete records across your ERP datasets.",
            upload: "Import a CSV or spreadsheet and review validation before replacing a dataset.",
            activity: "Recent changes made in this browser session.",
            profile: "Signed-in account and access information.",
            settings: "Workspace preferences for this browser.",
            help: "Guides for uploads, data management, search, and NORA."
        };

        $("#featurePageHeading").textContent = titles[page];
        $("#featurePageDescription").textContent = descriptions[page];

        const body = $("#featurePageBody");

        if (!body) return;

        if (["restocking", "inventory", "high-sellers"].includes(page)) {
            await loadOperationalProducts();
        }

        if (page === "data") { await renderDataManagement(body); return; }
        if (page === "seasonal") { await renderSeasonality(body); return; }
        if (page === "root-cause") { await renderRootCause(body); return; }

        if (page === "upload") {
            body.innerHTML = `<article class="panel"><div class="panel-heading"><div><h2>Upload a dataset</h2><p>Files are matched to an ERP schema, validated, and backed up before replacement.</p></div></div><div class="upload-dropzone"><span class="upload-mark">⇧</span><strong>Choose a CSV or Excel file</strong><p>Supported formats: CSV, XLSX, XLS · Maximum 10 MB</p><button type="button" class="primary-button compact" id="uploadPageTrigger">Choose file</button><p class="upload-feedback" id="uploadFeedback" aria-live="polite"></p></div><div id="uploadedDatasets" class="file-summary-list"></div></article>`;
            $("#uploadPageTrigger", body).addEventListener("click", () => $("#sidebarUploadInput")?.click());
            loadUploadedDatasets($("#uploadedDatasets", body));
            return;
        }

        if (page === "activity") {
            const entries = readActivity();
            body.innerHTML = `<article class="panel"><div class="panel-heading"><div><h2>Recent activity</h2><p>Actions are recorded in this browser for this workspace.</p></div><div class="help-actions"><button type="button" class="secondary-button" id="activityExport">Export activity</button><button type="button" class="secondary-button" id="activityClear">Clear history</button></div></div><div class="activity-list" id="activityList">${entries.length ? entries.map(item => `<div class="activity-item"><strong>${safe(item.action)}</strong>${item.details ? ` · ${safe(item.details)}` : ""}<time>${safe(new Date(item.at).toLocaleString())}</time></div>`).join("") : '<div class="empty-note">No activity recorded yet. Upload a file or make a data change to see it here.</div>'}</div></article>`;
            $("#activityExport", body).addEventListener("click", () => csv("erp-activity.csv", ["Action", "Details", "Date"], readActivity().map(item => [item.action, item.details, item.at])));
            $("#activityClear", body).addEventListener("click", () => { if (!window.confirm("Clear activity history from this browser?")) return; localStorage.removeItem("erpActivity"); renderFeature("activity"); });
            return;
        }

        if (page === "profile") {
            body.innerHTML = `<div class="insight-grid"><article class="insight-card"><span class="insight-value">${safe((state.user?.role || "Owner").toUpperCase())}</span><h3>Workspace role</h3><p>This account is signed in to the current ERP workspace. Sign out from the sidebar when you are finished.</p></article><article class="insight-card"><span class="insight-value">${safe(state.user?.email || "Signed-in user")}</span><h3>Account email</h3><p>Authentication and account recovery are managed by the existing sign-in service.</p><button type="button" id="profileResetPassword">Request password reset</button></article></div>`;
            $("#profileResetPassword", body).addEventListener("click", async () => { try { await postJSON("/auth/forgot-password", { email: state.user?.email || "" }); toast("If the account exists, password reset instructions will be sent."); } catch (error) { toast(error.message, true); } });
            return;
        }

        if (page === "settings") {
            let prefs = {};
            try { prefs = JSON.parse(localStorage.getItem("erpPreferences") || "{}"); } catch { prefs = {}; }
            body.innerHTML = `<article class="panel"><form class="settings-form" id="settingsForm"><label>Workspace display name<input name="workspace" value="${safe(prefs.workspace || "ERP System")}" maxlength="60"></label><label>Default region<select name="region"><option ${(!prefs.region || prefs.region === "Telangana") ? "selected" : ""}>Telangana</option><option ${prefs.region === "All India" ? "selected" : ""}>All India</option><option ${prefs.region === "Karnataka" ? "selected" : ""}>Karnataka</option></select></label><label class="check-setting"><input type="checkbox" name="compact" ${prefs.compact ? "checked" : ""}> Use compact data tables</label><label class="check-setting"><input type="checkbox" name="assistant" ${prefs.assistant !== false ? "checked" : ""}> Show the NORA assistant button</label><label class="check-setting"><input type="checkbox" name="lowStock" ${prefs.lowStock !== false ? "checked" : ""}> Show low-stock notifications</label><div class="settings-actions"><button type="submit" class="primary-button compact">Save preferences</button><span id="settingsMessage" aria-live="polite"></span></div></form></article>`;
            $("#settingsForm", body).addEventListener("submit", event => { event.preventDefault(); const form = event.currentTarget; const next = { workspace: form.elements.workspace.value.trim() || "ERP System", region: form.elements.region.value, compact: form.elements.compact.checked, assistant: form.elements.assistant.checked, lowStock: form.elements.lowStock.checked }; localStorage.setItem("erpPreferences", JSON.stringify(next)); applyPreferences(); $("#settingsMessage").textContent = "Preferences saved on this browser."; toast("Workspace preferences saved."); });
            return;
        }

        if (page === "help") {
            body.innerHTML = `<div class="insight-grid help-grid"><article class="insight-card"><h3>Upload and validate</h3><p>Choose Upload &amp; validate to select a CSV or spreadsheet. The app recognizes supported ERP columns and reports schema errors before replacing the current file.</p><button data-help-open="upload">Open uploads</button></article><article class="insight-card"><h3>Manage business records</h3><p>Data Management lets you browse every supported dataset, then create, edit, or remove individual rows. Each saved change creates a timestamped backup.</p><button data-help-open="data">Open data management</button></article><article class="insight-card"><h3>Search across the ERP</h3><p>Search product names, suppliers, categories, order values, events, and issues. Comma-separated product terms return their linked records too.</p><button data-help-open="search">Focus workspace search</button></article><article class="insight-card"><h3>Ask NORA</h3><p>Use the floating assistant for natural-language questions about business records.</p><button data-help-open="assistant">Open NORA</button></article></div>`;
            $$('[data-help-open]', body).forEach(button => button.addEventListener("click", () => { const target = button.dataset.helpOpen; if (target === "assistant") { $("#erp-chatbot")?.classList.remove("is-hidden"); openErpChat(); return; } if (target === "search") { $("#globalSearch")?.focus(); return; } navigate(target); }));
            return;
        }

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
                        search(product.name);
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
            ],
            data: ["Data management", "Browse and manage records across your ERP datasets."],
            upload: ["Upload & validate", "Import and validate an ERP dataset."],
            activity: ["Activity history", "Review recent changes made in this browser."],
            profile: ["My profile", "Signed-in account and access information."],
            settings: ["Settings", "Adjust workspace preferences for this browser."],
            help: ["Help & documentation", "Guides for uploads, data, search and NORA."]
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

        $$(".sidebar-nav [data-page]").forEach(button => {
            if (button.dataset.page === page) button.setAttribute("aria-current", "page");
            else button.removeAttribute("aria-current");
        });
        const actionForPage = { upload: "upload", data: "data", activity: "activity", profile: "profile", settings: "settings", help: "help" };
        $$(".sidebar-nav [data-sidebar-action]").forEach(button => {
            if (button.dataset.sidebarAction === actionForPage[page]) button.setAttribute("aria-current", "page");
            else button.removeAttribute("aria-current");
        });

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

    function renderNativeChart(canvas, count) {
        const rect = canvas.getBoundingClientRect();
        const width = Math.max(320, rect.width || 320);
        const height = Math.max(190, rect.height || 260);
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        const context = canvas.getContext("2d");
        if (!context) return;
        context.scale(ratio, ratio);
        context.clearRect(0, 0, width, height);
        const labels = (state.chartLabels || salesLabels).slice(-count);
        const values = (state.chartValues || salesValues).slice(-count);
        const max = Math.max(...values, 1);
        const left = 48, right = width - 12, top = 12, bottom = height - 30;
        context.font = "10px Inter, sans-serif";
        context.textAlign = "right";
        for (let step = 0; step <= 4; step++) {
            const y = top + (bottom - top) * step / 4;
            context.strokeStyle = "rgba(255,255,255,.10)";
            context.beginPath(); context.moveTo(left, y); context.lineTo(right, y); context.stroke();
            context.fillStyle = "#aaa7b4";
            context.fillText(money(max * (4 - step) / 4), left - 8, y + 3);
        }
        const stepX = labels.length > 1 ? (right - left) / (labels.length - 1) : 0;
        context.beginPath();
        values.forEach((value, index) => {
            const x = left + stepX * index;
            const y = bottom - (Number(value) || 0) / max * (bottom - top);
            if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
        });
        context.strokeStyle = "#c9b9ff"; context.lineWidth = 2.5; context.stroke();
        values.forEach((value, index) => {
            const x = left + stepX * index;
            const y = bottom - (Number(value) || 0) / max * (bottom - top);
            context.beginPath(); context.arc(x, y, 3.5, 0, Math.PI * 2); context.fillStyle = "#c9b9ff"; context.fill();
            context.textAlign = "center"; context.fillStyle = "#aaa7b4"; context.fillText(labels[index] || "", x, height - 8);
        });
    }

    function renderChart(count = 6) {
        const canvas = $("#salesChart");

        if (!canvas) return;
        if (typeof Chart === "undefined") { renderNativeChart(canvas, count); return; }

        if (state.chart) {
            state.chart.destroy();
        }

        state.chart = new Chart(canvas, {
            type: "line",

            data: {
                labels: (state.chartLabels || salesLabels).slice(-count),

                datasets: [{
                    label: "Revenue",
                    data: (state.chartValues || salesValues).slice(-count),
                    borderColor: "#c9b9ff",
                    backgroundColor: "rgba(201,185,255,.13)",
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2.5,
                    pointRadius: 3,
                    pointBackgroundColor: "#fff",
                    pointBorderWidth: 2,
                    pointBorderColor: "#c9b9ff"
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
                        ticks: { color: "#aaa7b4" }
                    },

                    y: {
                        beginAtZero: true,
                        grid: { color: "rgba(255,255,255,.10)" },
                        ticks: {
                            color: "#aaa7b4",
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

            if (Array.isArray(data.labels) && Array.isArray(data.values)) {
                state.chartLabels = data.labels;
                state.chartValues = data.values.map(value => Number(value) || 0);
            }

            const aliases = {
                revenue: ["total_sales_revenue", "total_revenue", "sales_revenue"],
                units: ["total_sales", "total_sales_quantity", "total_units_sold", "units_sold"],
                lowStock: ["low_stock_products", "low_stock_count"],
                suppliers: ["supplier_risk_count", "supplier_risks"],
                orders: ["pending_purchase_orders", "pending_orders"],
                products: ["product_count", "total_products"],
                average: ["average_selling_price", "avg_selling_price"],
                openRca: ["open_rca_count"],
                seasonality: ["seasonality_count"]
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
        await loadOperationalProducts();

        updateKpis();
        renderTop();
        renderChart(Number($("#salesRange")?.value || 6));
        const [seasonality, issues] = await Promise.allSettled([
            fetchDataset("Seasonality.csv"), fetchDataset("RCA Insights.csv")
        ]);
        if (seasonality.status === "fulfilled") $("#insightSeasonal").textContent = state.metrics.seasonality || seasonality.value.total;
        if (issues.status === "fulfilled") $("#insightRca").textContent = state.metrics.openRca;
    }

    // =========================================================
    // GLOBAL SEARCH
    // =========================================================

    async function search(query) {
        const originalQuery = query.trim();
        if (!originalQuery) { navigate("overview"); return; }
        state.selectedSearchQuery = originalQuery;
        $("#pageTitle").textContent = "Search results";
        $("#pageSubtitle").textContent = "Matching data from your ERP workspace.";
        $("#breadcrumbCurrent").textContent = "Search results";
        $("#overview-page").classList.add("is-hidden");
        $("#feature-page").classList.add("is-hidden");
        $("#search-page").classList.remove("is-hidden");
        const host = $("#searchResults");
        host.innerHTML = '<div class="empty-note">Searching your business datasets…</div>';
        try {
            const result = await requestJSON(`/api/search?query=${encodeURIComponent(originalQuery)}`);
            $("#searchSummary").textContent = `${result.count || 0} matching records across your ERP datasets.`;
            host.innerHTML = result.results?.length ? `<div class="search-results-list">${result.results.map(item => {
                const title = item.record["Product Name"] || item.record["Event Name"] || item.record["Supplier Name"] || item.record["Order ID"] || item.record["PO Number"] || item.record["Issue Type"] || item.dataset;
                return `<article class="search-result search-record"><div class="search-record-heading"><div><strong>${safe(title)}</strong><small>${safe(item.dataset)} · ${item.match_type === "related" ? "Related record" : "Direct match"}</small></div><button type="button" class="table-action" data-search-dataset="${safe(item.dataset)}">Open dataset</button></div><div class="search-record-fields">${Object.entries(item.record).map(([key,value]) => `<span>${safe(key)}<b>${safe(value) || "—"}</b></span>`).join("")}</div></article>`;
            }).join("")}</div>` : '<div class="empty-note">No matches. Search a product, supplier, category, order, warehouse, event, or issue.</div>';
            $$('[data-search-dataset]', host).forEach(button => button.addEventListener("click", () => { state.activeDataset = button.dataset.searchDataset; state.activeDatasetOffset = 0; navigate("data"); }));
        } catch (error) {
            $("#searchSummary").textContent = "Search could not be completed.";
            host.innerHTML = `<div class="empty-note">${safe(error.message)}. Check your sign-in and retry.</div>`;
        }
    }
    // =========================================================
    // EVENT LISTENERS
    // =========================================================

    function events() {
        // Welcome tour and workspace access
        const welcomeViewport = $("#welcome-viewport");
        let swipeStartX = null;
        $$("[data-welcome-nav]").forEach(button => {
            button.addEventListener("click", () => {
                setWelcomeSlide(Number(button.dataset.welcomeNav));
            });
        });
        welcomeViewport?.addEventListener("pointerdown", event => {
            swipeStartX = event.clientX;
        });
        welcomeViewport?.addEventListener("pointerup", event => {
            if (swipeStartX === null) return;
            const delta = event.clientX - swipeStartX;
            swipeStartX = null;
            if (Math.abs(delta) > 55) {
                setWelcomeSlide(welcomeSlideIndex + (delta < 0 ? 1 : -1));
            }
        });
        welcomeViewport?.addEventListener("pointercancel", () => {
            swipeStartX = null;
        });
        $("#workspaceAccess")?.addEventListener("click", openWorkspaceAccess);
        $("#backToWelcome")?.addEventListener("click", returnToWelcome);
        $("#createAccountTab")?.addEventListener("click", () => setAccountMode("create"));
        $("#loginTab")?.addEventListener("click", () => setAccountMode("login"));
        $("#registerForm")?.addEventListener("submit", registerOwner);
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) stopWelcomeAutoplay();
            else startWelcomeAutoplay();
        });
        setWelcomeSlide(0);

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
            sidebarPinnedOpen = !sidebarPinnedOpen;
            setSidebarCollapsed(!sidebarPinnedOpen);
            navigate("overview");
        });
        $("#sidebarLogout")?.addEventListener("click", logout);

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
            await refreshDashboardData();

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
                closeSidebarOnMobileNavigation();
            });
        });

        // Search form and Enter submit
        $("#globalSearchForm")?.addEventListener("submit", event => {
            event.preventDefault();
            search($("#globalSearch")?.value || "");
        });

        // Global search keyboard fallback
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
                if (window.matchMedia("(max-width: 760px)").matches && appScreen && !appScreen.classList.contains("sidebar-collapsed")) {
                    sidebarPinnedOpen = false;
                    setSidebarCollapsed(true);
                }
            }
        });

        // Close popover when clicking outside the top bar
        document.addEventListener("click", event => {
            if (!event.target.closest(".topbar-actions")) {
                closePopover();
            }
        });
        const sidebarTargets = {
            upload: "upload", data: "data", activity: "activity",
            profile: "profile", settings: "settings", help: "help"
        };
        $$('[data-sidebar-action]').forEach(button => button.addEventListener("click", () => {
            const page = sidebarTargets[button.dataset.sidebarAction];
            if (page) { navigate(page); closeSidebarOnMobileNavigation(); }
        }));

        $("#sidebarUploadInput")?.addEventListener("change", event => {
            const file = event.currentTarget.files?.[0];
            if (file) uploadDataset(file);
        });

        document.addEventListener("click", event => {
            if (window.matchMedia("(max-width: 760px)").matches && !appScreen?.classList.contains("sidebar-collapsed") && !event.target.closest("#appSidebar") && !event.target.closest("#sidebarToggle")) {
                sidebarPinnedOpen = false;
                setSidebarCollapsed(true);
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
      "Sorry, I couldn't connect to NORA. Please try again.",
      "bot"
    );
  } finally {
    erpChatBusy = false;
    if (sendButton) sendButton.disabled = false;
    input?.focus();
  }
}

function openErpChat() {
  $("#erp-chatbot")?.classList.remove("is-hidden");
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
            stopWelcomeAutoplay();
            showResetPasswordForm(resetToken);
            return;
        }

        checkSession();
    });

})();
