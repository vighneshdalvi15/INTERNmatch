/*
  InternMatch frontend SPA script.

  Responsibilities:
  - SPA navigation (view switching)
  - Authentication (signup/login) via Flask JWT APIs
  - Profile editing + skills picker
  - Jobs browsing, applying, and AI matching
  - Courses grid + watch tracking
  - Mock tests runner + submission + results
*/

const API = {
  token: localStorage.getItem("im_token") || null,
  user: JSON.parse(localStorage.getItem("im_user") || "null"),
};

function byId(id) {
  return document.getElementById(id);
}

function setTextIfPresent(id, value) {
  const el = byId(id);
  if (el) el.innerText = value;
}

function authHeaders() {
  return API.token ? { Authorization: `Bearer ${API.token}` } : {};
}

async function apiFetch(path, { method = "GET", headers = {}, body = null } = {}) {
  const init = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...headers,
    },
  };
  if (body !== null) init.body = JSON.stringify(body);

  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // If the token is stale/invalid, clear it to stop 401 spam + incorrect UI.
    if (res.status === 401) {
      API.token = null;
      API.user = null;
      localStorage.removeItem("im_token");
      localStorage.removeItem("im_user");
      try {
        onAuthed();
      } catch {
        // ignore
      }
    }
    const msg = data?.error || "request_failed";
    throw new Error(msg);
  }
  return data;
}

function showToast(title, msg) {
  const toast = document.getElementById("toast");
  document.getElementById("toast-title").innerText = title || "";
  document.getElementById("toast-msg").innerText = msg || "";
  toast.classList.remove("hidden");
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => hideToast(), 4200);
}

function hideToast() {
  document.getElementById("toast").classList.add("hidden");
}

function toggleMobileNav(force) {
  const el = document.getElementById("mobile-nav");
  if (typeof force === "boolean") el.classList.toggle("hidden", !force);
  else el.classList.toggle("hidden");
}

function showView(viewId, btn = null) {
  const targetView = document.getElementById(viewId + "-view");
  if (!targetView) return;

  document.querySelectorAll(".view-content").forEach((view) => view.classList.remove("active"));
  targetView.classList.add("active");

  const navButtons = document.querySelectorAll(".nav-btn");
  if (btn) {
    navButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  }

  window.scrollTo({ top: 0, behavior: "smooth" });

  // Auto-refresh dashboard when opened.
  if (viewId === "dashboard") {
    refreshStudentDashboard();
    loadMyApplications();
  }
  if (viewId === "post-job") {
    loadPostingEligibility();
  }
}

function toggleDropdown() {
  document.getElementById("profileDropdown").classList.toggle("show");
}

function showDropdownView(viewId) {
  document.getElementById("profileDropdown").classList.remove("show");
  showView(viewId);
}

document.addEventListener("click", function (event) {
  const profileArea = document.getElementById("userProfileArea");
  if (profileArea && !profileArea.contains(event.target)) {
    document.getElementById("profileDropdown").classList.remove("show");
  }
});

// Auth modal logic
let authMode = "login"; // login | signup
let authRole = "student"; // student | company

function openAuthModal(mode) {
  authMode = mode || "login";
  setAuthRole(authRole);
  syncAuthUI();
  document.getElementById("auth-modal").classList.remove("hidden");
  document.getElementById("auth-modal").classList.add("flex");
  document.body.classList.add("overflow-hidden");
}

function closeAuthModal() {
  const el = document.getElementById("auth-modal");
  el.classList.add("hidden");
  el.classList.remove("flex");
  document.body.classList.remove("overflow-hidden");
}

function toggleAuthMode() {
  authMode = authMode === "login" ? "signup" : "login";
  syncAuthUI();
}

function setAuthRole(role) {
  authRole = role;
  document.getElementById("role-student").classList.toggle("border-blue-500", role === "student");
  document.getElementById("role-student").classList.toggle("bg-blue-50", role === "student");
  document.getElementById("role-company").classList.toggle("border-slate-900", role === "company");
  document.getElementById("role-company").classList.toggle("bg-slate-50", role === "company");
}

function syncAuthUI() {
  document.getElementById("auth-title").innerText = authMode === "login" ? "Login to InternMatch" : "Create your account";
  document.getElementById("auth-subtitle").innerText =
    authMode === "login"
      ? "Sign in to apply, post jobs, and use AI matching."
      : "Sign up as a Student or Company to get started.";
  document.getElementById("auth-submit").innerText = authMode === "login" ? "Login" : "Sign up";
  document.getElementById("auth-toggle").innerText =
    authMode === "login" ? "Need an account? Sign up" : "Already have an account? Login";
}

async function submitAuth() {
  const email = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  if (!email || !password) return showToast("Missing info", "Please enter email and password.");

  try {
    const data =
      authMode === "login"
        ? await apiFetch("/api/auth/login", { method: "POST", body: { email, password } })
        : await apiFetch("/api/auth/signup", { method: "POST", body: { role: authRole, email, password } });

    API.token = data.access_token;
    API.user = data.user;
    localStorage.setItem("im_token", API.token);
    localStorage.setItem("im_user", JSON.stringify(API.user));

    closeAuthModal();
    onAuthed();
    showToast("Welcome", "You’re logged in.");
  } catch (e) {
    const msg = e?.message === "invalid_credentials" ? "Invalid email or password." : `Error: ${e.message}`;
    showToast("Login failed", msg);
  }
}

function logout() {
  API.token = null;
  API.user = null;
  localStorage.removeItem("im_token");
  localStorage.removeItem("im_user");
  onAuthed();
  showView("landing");
  showToast("Logged out", "See you next time.");
}

function initialsFromEmail(email) {
  const v = (email || "U").split("@")[0].replace(/[^a-z0-9]/gi, " ").trim();
  const parts = v.split(/\s+/).filter(Boolean);
  const a = (parts[0] || "U")[0] || "U";
  const b = (parts[1] || parts[0] || "U")[1] || "";
  return (a + b).toUpperCase();
}

function onAuthed() {
  const loggedIn = !!API.token;

  document.getElementById("loginBtn").classList.toggle("hidden", loggedIn);
  document.getElementById("signupBtn").classList.toggle("hidden", loggedIn);
  document.getElementById("userProfileArea").classList.toggle("hidden", !loggedIn);
  document.getElementById("ai-status-box").classList.toggle("hidden", !loggedIn);

  const companyNav = document.getElementById("company-nav");
  const companyDrop = document.getElementById("companyProfileDrop");
  const isCompany = API.user?.role === "company";
  companyNav.classList.toggle("hidden", !loggedIn || !isCompany);
  companyDrop.classList.toggle("hidden", !loggedIn || !isCompany);

  if (loggedIn) {
    document.getElementById("userAvatarBtn").innerText = initialsFromEmail(API.user?.email);
  }

  if (loggedIn && API.user?.role === "student") {
    loadStudentProfile();
    loadJobs();
    loadMyApplications();
  }

  if (loggedIn && API.user?.role === "company") {
    loadCompanyProfile();
    loadJobs();
    loadMyApplications();
    loadPostingEligibility();
  }
}

// Student profile
let profileIsEditing = false;
function toggleProfileEdit(force) {
  if (typeof force === "boolean") profileIsEditing = force;
  else profileIsEditing = !profileIsEditing;

  const inputs = document.querySelectorAll(".prof-input");
  inputs.forEach((el) => {
    if (el.tagName === "SELECT") el.disabled = !profileIsEditing;
    else el.readOnly = !profileIsEditing;

    if (profileIsEditing) {
      el.classList.add("ring-2", "ring-blue-100", "bg-white");
      el.classList.remove("bg-slate-50");
    } else {
      el.classList.remove("ring-2", "ring-blue-100", "bg-white");
      el.classList.add("bg-slate-50");
    }
  });
  document.getElementById("profileSaveContainer").classList.toggle("hidden", !profileIsEditing);
  document.getElementById("profileEditBtn").classList.toggle("hidden", profileIsEditing);
  toggleEduDetails();

  // Skills widget inputs
  document.getElementById("skills-search")?.toggleAttribute("readonly", !profileIsEditing);
  const addBtn = document.getElementById("skills-add-btn");
  if (addBtn) addBtn.disabled = !profileIsEditing;
}

function toggleEduDetails() {
  const status = document.getElementById("prof-edu-status").value;
  const pursuingFields = document.getElementById("pursuing-fields");
  const completedFields = document.getElementById("completed-fields");

  pursuingFields.classList.add("hidden");
  completedFields.classList.add("hidden");

  if (status === "pursuing") pursuingFields.classList.remove("hidden");
  else if (status === "completed") completedFields.classList.remove("hidden");
}

// Skills picker (searchable multi-select)
const SKILL_CATALOG = [
  // Programming
  "Python","JavaScript","TypeScript","Java","C","C++","C#","Go","Rust","PHP","Ruby","Kotlin","Swift",
  // Web Dev
  "HTML","CSS","React","Next.js","Node.js","Express","MongoDB","PostgreSQL","MySQL","REST API","GraphQL","Tailwind CSS",
  // Data & AI
  "SQL","Data Analysis","Data Science","Machine Learning","Deep Learning","NLP","Computer Vision","Pandas","NumPy",
  // Tools
  "Git","GitHub","Docker","AWS","Azure","GCP","Figma","Linux","Postman","CI/CD",
  // Creative
  "Canva","Photoshop","Video Editing","UI/UX",
  // Other
  "Communication","Problem Solving","DSA","System Design","Agile",
];

let selectedSkills = [];

function normalizeSkillLabel(s) {
  return String(s || "").trim();
}

function syncSkillsToHiddenField() {
  const hidden = document.getElementById("prof-skills");
  if (hidden) hidden.value = selectedSkills.join(", ");
}

function renderSkillChips() {
  const wrap = document.getElementById("skills-chips");
  if (!wrap) return;
  if (!selectedSkills.length) {
    wrap.innerHTML = `<span class="text-sm text-slate-500">No skills selected yet.</span>`;
    syncSkillsToHiddenField();
    return;
  }
  wrap.innerHTML = selectedSkills
    .map(
      (s) => `
      <span class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-800 text-sm font-bold border border-blue-100">
        ${s}
        ${profileIsEditing ? `<button class="text-blue-600 hover:text-blue-900" onclick="removeSkill('${encodeURIComponent(s)}')" type="button"><i class="fa-solid fa-xmark"></i></button>` : ""}
      </span>
    `
    )
    .join("");
  syncSkillsToHiddenField();
}

function renderAiSnapshotSkills() {
  const wrap = document.getElementById("ai-snapshot-skills");
  if (!wrap) return;
  const list = (selectedSkills || []).slice(0, 12);
  if (!list.length) {
    wrap.innerHTML = `<span class="text-sm text-slate-600">No skills yet. Add skills in Profile to unlock better matches.</span>`;
    return;
  }
  wrap.innerHTML = list
    .map((s) => `<span class="px-3 py-1 rounded-full bg-slate-100/70 text-slate-700 text-xs font-bold border border-slate-200">${s}</span>`)
    .join("");
}

function addSkill(skill) {
  const v = normalizeSkillLabel(skill);
  if (!v) return;
  if (selectedSkills.some((x) => x.toLowerCase() === v.toLowerCase())) return;
  selectedSkills.push(v);
  selectedSkills.sort((a, b) => a.localeCompare(b));
  renderSkillChips();
}

function removeSkill(encoded) {
  const s = decodeURIComponent(encoded);
  selectedSkills = selectedSkills.filter((x) => x !== s);
  renderSkillChips();
}

function openSkillsPicker() {
  if (!profileIsEditing) return;
  const modal = document.getElementById("skills-modal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.getElementById("skills-modal-search").value = "";
  renderSkillsModalList("");
  document.body.classList.add("overflow-hidden");
}

function closeSkillsPicker() {
  const modal = document.getElementById("skills-modal");
  modal.classList.add("hidden");
  modal.classList.remove("flex");
  document.body.classList.remove("overflow-hidden");
}

function renderSkillsModalList(query) {
  const q = String(query || "").trim().toLowerCase();
  const list = document.getElementById("skills-modal-list");
  if (!list) return;
  const items = SKILL_CATALOG.filter((s) => !q || s.toLowerCase().includes(q)).slice(0, 200);
  list.innerHTML = items
    .map((s) => {
      const active = selectedSkills.some((x) => x.toLowerCase() === s.toLowerCase());
      return `
        <button class="text-left px-4 py-3 rounded-2xl border ${active ? "border-blue-400 bg-blue-50 text-blue-900" : "border-slate-200 hover:border-blue-200 hover:bg-slate-50"} font-bold" onclick="toggleSkillFromModal('${encodeURIComponent(s)}')" type="button">
          ${s}
        </button>
      `;
    })
    .join("");
}

function toggleSkillFromModal(encoded) {
  const s = decodeURIComponent(encoded);
  const exists = selectedSkills.some((x) => x.toLowerCase() === s.toLowerCase());
  if (exists) selectedSkills = selectedSkills.filter((x) => x.toLowerCase() !== s.toLowerCase());
  else addSkill(s);
  renderSkillsModalList(document.getElementById("skills-modal-search").value);
}

function fillStudentForm(p) {
  document.getElementById("prof-name").value = p.full_name || "";
  document.getElementById("prof-phone").value = p.phone || "";
  document.getElementById("prof-uni").value = p.education?.university || "";
  document.getElementById("prof-major").value = p.education?.major || "";
  document.getElementById("prof-edu-status").value = p.education?.status || "";
  document.getElementById("prof-year").value = p.education?.year || "1";
  document.getElementById("prof-sem").value = p.education?.semester || "";
  document.getElementById("prof-grad-year").value = p.education?.graduation_year || "";
  selectedSkills = (p.skills || []).map(normalizeSkillLabel).filter(Boolean);
  renderSkillChips();
  renderAiSnapshotSkills();
  document.getElementById("prof-experience").value = p.experience || "";
  document.getElementById("prof-pref-role").value = p.preferences?.preferred_role || "";
  document.getElementById("prof-pref-loc").value = p.preferences?.preferred_location || "";
  document.getElementById("prof-linkedin").value = p.links?.linkedin || "";
  document.getElementById("prof-github").value = p.links?.github || "";
  document.getElementById("prof-portfolio").value = p.links?.portfolio || "";
  document.getElementById("prof-resume-url").value = p.resume_url || "";
  toggleEduDetails();
}

async function loadStudentProfile() {
  if (!API.token || API.user?.role !== "student") return;
  try {
    const data = await apiFetch("/api/students/me");
    fillStudentForm(data.profile || {});
  } catch (e) {
    showToast("Profile", "Could not load profile yet. Save to create one.");
  }
}

async function saveStudentProfile() {
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "student") return showToast("Not allowed", "Switch to a student account to edit this profile.");

  const education = {
    university: document.getElementById("prof-uni").value.trim(),
    major: document.getElementById("prof-major").value.trim(),
    status: document.getElementById("prof-edu-status").value,
    year: document.getElementById("prof-year").value,
    semester: document.getElementById("prof-sem").value,
    graduation_year: document.getElementById("prof-grad-year").value,
  };
  const skills = selectedSkills;
  const preferences = {
    preferred_role: document.getElementById("prof-pref-role").value.trim(),
    preferred_location: document.getElementById("prof-pref-loc").value.trim(),
  };
  const links = {
    linkedin: document.getElementById("prof-linkedin").value.trim(),
    github: document.getElementById("prof-github").value.trim(),
    portfolio: document.getElementById("prof-portfolio").value.trim(),
  };

  const body = {
    full_name: document.getElementById("prof-name").value.trim(),
    phone: document.getElementById("prof-phone").value.trim(),
    education,
    skills,
    experience: document.getElementById("prof-experience").value.trim(),
    preferences,
    links,
    resume_url: document.getElementById("prof-resume-url").value.trim(),
  };

  if (!body.full_name) return showToast("Missing info", "Please enter your full name.");

  try {
    const data = await apiFetch("/api/students/me", { method: "PUT", body });
    fillStudentForm(data.profile || {});
    toggleProfileEdit(false);
    showToast("Saved", "Profile updated successfully.");
  } catch (e) {
    showToast("Save failed", `Error: ${e.message}`);
  }
}

async function uploadResume(file) {
  if (!file) return;
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "student") return showToast("Not allowed", "Only students can upload resumes.");

  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/uploads/resume", {
      method: "POST",
      headers: { ...authHeaders() },
      body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || "upload_failed");
    document.getElementById("prof-resume-url").value = data.url;
    showToast("Uploaded", "Resume uploaded. Save profile to store it.");
  } catch (e) {
    showToast("Upload failed", `Error: ${e.message}`);
  }
}

// Company profile
let companyIsEditing = false;
function toggleCompanyEdit(force) {
  if (typeof force === "boolean") companyIsEditing = force;
  else companyIsEditing = !companyIsEditing;
  document.querySelectorAll(".comp-input").forEach((el) => {
    if (el.tagName === "SELECT") el.disabled = !companyIsEditing;
    else el.readOnly = !companyIsEditing;
    if (companyIsEditing) {
      el.classList.add("ring-2", "ring-blue-100", "bg-white");
      el.classList.remove("bg-slate-50");
    } else {
      el.classList.remove("ring-2", "ring-blue-100", "bg-white");
      el.classList.add("bg-slate-50");
    }
  });
  document.getElementById("companySaveContainer").classList.toggle("hidden", !companyIsEditing);
  document.getElementById("companyEditBtn").classList.toggle("hidden", companyIsEditing);
}

function fillCompanyForm(p) {
  document.getElementById("comp-name").value = p.company_name || "";
  document.getElementById("comp-website").value = p.website || "";
  document.getElementById("comp-location").value = p.location || "";
  document.getElementById("comp-industry").value = p.industry || "";
  document.getElementById("comp-about").value = p.about || "";
  const sz = document.getElementById("comp-size");
  if (sz) sz.value = p.size || "";
  const li = document.getElementById("comp-linkedin");
  if (li) li.value = p.linkedin_url || "";
  const ce = document.getElementById("comp-careers-email");
  if (ce) ce.value = p.careers_contact_email || "";
}

function renderCompanyVerifyBanner(posting) {
  const box = document.getElementById("company-verify-banner");
  if (!box) return;
  if (!posting) {
    box.classList.add("hidden");
    return;
  }
  const vs = posting.verification_status;
  const can = posting.can_post;
  let cls = "border-emerald-200 bg-emerald-50/90 text-emerald-950";
  let title = "Company verification";
  let msg = posting.verification_note || "";

  if (posting.skip_verify_env) {
    cls = "border-slate-200 bg-slate-50 text-slate-800";
    title = "Dev mode";
    msg = "Company posting checks are relaxed (INTERNMATCH_SKIP_COMPANY_VERIFY=1).";
  } else if (vs === "email_domain_match" || vs === "manual_verified") {
    title = "Verified employer";
    msg = msg || "Your company domain matches your work email. You can post jobs.";
  } else {
    cls = "border-amber-200 bg-amber-50/90 text-amber-950";
    title = "Verification required to post jobs";
    msg =
      msg ||
      "Use a company email on the same domain as your website (not Gmail/Yahoo), then save your profile. Complete all required fields including a detailed About section.";
  }

  if (!posting.profile_complete && posting.missing_profile_fields?.length) {
    msg += ` Missing: ${posting.missing_profile_fields.join(", ")}.`;
  }

  box.className = `mb-6 rounded-[1.75rem] border p-5 backdrop-blur-md ${cls}`;
  box.innerHTML = `<p class="font-extrabold">${title}</p><p class="mt-1 text-sm opacity-90">${msg}</p><p class="mt-2 text-xs opacity-80">Status: <span class="font-bold">${vs || "unverified"}</span>${can ? " • Can post" : " • Cannot post yet"}</p>`;
  box.classList.remove("hidden");
}

async function loadPostingEligibility() {
  if (!API.token || API.user?.role !== "company") return;
  try {
    const data = await apiFetch("/api/companies/me/posting-eligibility");
    window.__companyPosting = data;
    const gate = document.getElementById("post-job-gate");
    const btn = document.getElementById("post-job-submit");
    if (gate) {
      if (!data.can_post) {
        gate.classList.remove("hidden");
        gate.innerHTML = `<p class="font-extrabold">Complete verification before publishing</p><p class="mt-1">${data.verification_note || "Finish your company profile and use a work email that matches your website domain."}</p>${
          data.missing_profile_fields?.length ? `<p class="mt-2 text-xs">Missing profile fields: ${data.missing_profile_fields.join(", ")}</p>` : ""
        }`;
      } else {
        gate.classList.add("hidden");
        gate.innerHTML = "";
      }
    }
    if (btn) btn.disabled = !data.can_post;
  } catch {
    const gate = document.getElementById("post-job-gate");
    if (gate) gate.classList.add("hidden");
  }
}

async function loadCompanyProfile() {
  if (!API.token || API.user?.role !== "company") return;
  try {
    const data = await apiFetch("/api/companies/me");
    fillCompanyForm(data.profile || {});
    renderCompanyVerifyBanner(data.posting);
  } catch (e) {
    showToast("Company", "Could not load profile yet. Save to create one.");
  }
}

async function saveCompanyProfile() {
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "company") return showToast("Not allowed", "Switch to a company account to edit this profile.");

  const body = {
    company_name: document.getElementById("comp-name").value.trim(),
    website: document.getElementById("comp-website").value.trim(),
    location: document.getElementById("comp-location").value.trim(),
    industry: document.getElementById("comp-industry").value.trim(),
    about: document.getElementById("comp-about").value.trim(),
    size: document.getElementById("comp-size")?.value || "",
    linkedin_url: document.getElementById("comp-linkedin")?.value.trim() || "",
    careers_contact_email: document.getElementById("comp-careers-email")?.value.trim() || "",
  };
  if (!body.company_name) return showToast("Missing info", "Please enter company name.");

  try {
    const data = await apiFetch("/api/companies/me", { method: "PUT", body });
    fillCompanyForm(data.profile || {});
    renderCompanyVerifyBanner(data.posting);
    toggleCompanyEdit(false);
    showToast("Saved", "Company profile updated.");
  } catch (e) {
    showToast("Save failed", `Error: ${e.message}`);
  }
}

// Jobs
function jobCard(job, extra = "") {
  const req = (job.required_skills || [])
    .slice(0, 6)
    .map((s) => `<span class="px-3 py-1 rounded-full bg-cyan-50/80 text-cyan-800 text-xs font-bold border border-cyan-100">${s}</span>`)
    .join("");
  const metaBits = [
    job.job_type || job.type,
    job.location,
    job.work_mode,
    job.duration,
    job.stipend_salary ? `Stipend: ${job.stipend_salary}` : "",
    job.hours_per_week ? `${job.hours_per_week} hrs/wk` : "",
    job.openings ? `${job.openings} opening(s)` : "",
  ]
    .filter(Boolean)
    .join(" • ");

  return `
    <div class="bg-white/70 border border-cyan-100 p-7 rounded-[2rem] shadow-sm backdrop-blur-md hover:border-emerald-200 transition">
      <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div class="flex-1">
          <div class="flex items-center gap-3">
            <div class="w-11 h-11 rounded-2xl bg-gradient-to-br from-cyan-400 to-emerald-400 text-white flex items-center justify-center font-black shadow-md">${(job.title || "J")[0]}</div>
            <div>
              <h3 class="text-lg font-extrabold text-slate-900">${job.title || "Untitled role"}</h3>
              <p class="text-slate-500 text-sm">${job.company_name ? `${job.company_name} • ` : ""}${metaBits || "—"}</p>
            </div>
          </div>
          <p class="text-slate-600 text-sm mt-4 leading-relaxed">${(job.description || "").slice(0, 240)}${(job.description || "").length > 240 ? "..." : ""}</p>
          <div class="flex flex-wrap gap-2 mt-4">${req}</div>
        </div>
        <div class="flex flex-col gap-2 min-w-[180px]">
          ${extra}
        </div>
      </div>
    </div>
  `;
}

async function loadJobs() {
  try {
    const data = await apiFetch("/api/jobs");
    const q = (document.getElementById("job-search")?.value || "").trim().toLowerCase();
    const items = (data.items || []).filter((j) => {
      if (!q) return true;
      const hay = `${j.title || ""} ${(j.required_skills || []).join(" ")} ${(j.preferred_skills || []).join(" ")}`.toLowerCase();
      return hay.includes(q);
    });
    const list = document.getElementById("jobs-list");
    if (!items.length) {
      list.innerHTML = `<div class="bg-white border border-slate-100 rounded-[2rem] p-8 text-slate-600">No jobs found yet.</div>`;
      return;
    }

    list.innerHTML = items
      .map((job) => {
        let extra = "";
        if (API.token && API.user?.role === "student") {
          extra = `
            <button class="bg-blue-600 text-white px-6 py-3 rounded-2xl font-bold hover:bg-blue-700" onclick="applyToJob('${job.id}')">Apply</button>
            <button class="bg-white border border-slate-200 text-slate-900 px-6 py-3 rounded-2xl font-bold hover:border-purple-300 hover:text-purple-700" onclick="matchJob('${job.id}')">AI Match</button>
          `;
        } else if (!API.token) {
          extra = `<button class="bg-slate-900 text-white px-6 py-3 rounded-2xl font-bold" onclick="openAuthModal('login')">Login to Apply</button>`;
        } else if (API.user?.role === "company") {
          extra = `<button class="bg-slate-900 text-white px-6 py-3 rounded-2xl font-bold" onclick="showView('post-job')">Post Job</button>`;
        }
        return jobCard(job, extra);
      })
      .join("");
  } catch (e) {
    showToast("Jobs", `Error loading jobs: ${e.message}`);
  }
}

async function createJob() {
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "company") return showToast("Not allowed", "Only companies can post jobs.");

  const body = {
    title: document.getElementById("job-title").value.trim(),
    department: document.getElementById("job-department")?.value.trim() || "",
    type: document.getElementById("job-type")?.value || "internship",
    location: document.getElementById("job-location").value.trim(),
    work_mode: document.getElementById("job-mode").value,
    hours_per_week: document.getElementById("job-hours")?.value.trim() || "",
    start_date: document.getElementById("job-start")?.value || "",
    duration: document.getElementById("job-duration").value.trim(),
    openings: document.getElementById("job-openings")?.value || "1",
    stipend_salary: document.getElementById("job-stipend").value.trim(),
    deadline: document.getElementById("job-deadline").value.trim(),
    perks: document.getElementById("job-perks")?.value.trim() || "",
    required_skills: document.getElementById("job-required").value,
    preferred_skills: document.getElementById("job-preferred").value,
    description: document.getElementById("job-desc").value.trim(),
    eligibility: document.getElementById("job-elig").value.trim(),
    role_contact_email: document.getElementById("job-contact-email")?.value.trim() || "",
  };
  if (!body.title || !body.description || !body.required_skills) return showToast("Missing info", "Title, description and required skills are required.");

  try {
    await apiFetch("/api/jobs", { method: "POST", body });
    showToast("Published", "Your job is now live.");
    showView("internship");
    loadJobs();
    loadPostingEligibility();
  } catch (e) {
    const msg = e?.message === "company_not_verified" || e?.message === "incomplete_profile" ? "Complete company profile + domain verification to post." : e.message;
    showToast("Publish failed", `Error: ${msg}`);
  }
}

// Courses
function courseCard(c) {
  const skills = (c.skills || []).slice(0, 4).map((s) => `<span class="px-3 py-1 rounded-full bg-emerald-50/90 text-emerald-800 text-xs font-bold border border-emerald-100">${s}</span>`).join("");
  const thumb = c.thumbnail_url || "";
  return `
    <div class="bg-white/70 border border-emerald-100 rounded-[2rem] overflow-hidden shadow-sm hover:border-cyan-200 transition flex flex-col h-full backdrop-blur-md">
      <div class="aspect-video bg-slate-100 overflow-hidden">
        ${thumb ? `<img src="${thumb}" alt="${c.title || "Course"}" class="w-full h-full object-cover">` : `<div class="w-full h-full flex items-center justify-center text-slate-400 font-bold">COURSE</div>`}
      </div>
      <div class="p-6 flex flex-col flex-1">
        <h3 class="text-lg font-extrabold text-slate-900 leading-snug min-h-[56px]">${c.title || "Untitled course"}</h3>
        <div class="flex flex-wrap gap-2 mt-3">${skills}</div>
        <div class="mt-auto pt-5">
          <a class="inline-flex w-full justify-center bg-gradient-to-r from-emerald-400 to-cyan-500 text-white px-6 py-3 rounded-2xl font-bold hover:opacity-95 transition" href="${c.url}" target="_blank" rel="noreferrer" onclick="markCourseWatched('${c.id}')">Watch this course</a>
        </div>
      </div>
    </div>
  `;
}

async function loadCourses() {
  try {
    const data = await apiFetch("/api/courses");
    const items = data.items || [];
    const grid = document.getElementById("courses-grid");
    if (!grid) return;
    if (!items.length) {
      grid.innerHTML = `<div class="bg-white border border-slate-100 rounded-[2rem] p-8 text-slate-600 lg:col-span-3">No courses yet.</div>`;
      return;
    }
    grid.innerHTML = items.map(courseCard).join("");
  } catch (e) {
    showToast("Courses", `Error loading courses: ${e.message}`);
  }
}

async function markCourseWatched(courseId) {
  if (!API.token || API.user?.role !== "student") return;
  try {
    await apiFetch(`/api/courses/${courseId}/watch`, { method: "POST" });
    // update dashboard stats if user is on dashboard
    refreshStudentDashboard();
  } catch (e) {
    // silent
  }
}

// Applications
async function applyToJob(jobId) {
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "student") return showToast("Not allowed", "Only students can apply.");

  try {
    await apiFetch("/api/applications", { method: "POST", body: { job_id: jobId } });
    showToast("Applied", "Application submitted.");
    loadMyApplications();
    refreshStudentDashboard();
  } catch (e) {
    const msg = e.message === "already_applied" ? "You already applied to this job." : `Error: ${e.message}`;
    showToast("Apply failed", msg);
  }
}

async function loadMyApplications() {
  if (!API.token) return;
  try {
    const data = await apiFetch("/api/applications/mine");
    const items = data.items || [];

    // Student dashboard list
    const studentBox = document.getElementById("student-apps");
    if (studentBox) {
      if (!items.length) studentBox.innerHTML = `<p class="text-slate-500">No applications yet.</p>`;
      else studentBox.innerHTML = items.slice(0, 8).map((a) => `<div class="p-3 bg-slate-50 rounded-xl border border-slate-100">Status: <span class="font-bold">${a.status}</span></div>`).join("");
    }

    // Company apps view
    const appsList = document.getElementById("apps-list");
    if (appsList && API.user?.role === "company") {
      if (!items.length) {
        appsList.innerHTML = `<div class="bg-white border border-slate-100 rounded-[2rem] p-8 text-slate-600">No applications yet.</div>`;
      } else {
        appsList.innerHTML = items
          .map((a) => {
            return `
              <div class="bg-white border border-slate-100 p-7 rounded-[2rem] shadow-sm">
                <div class="flex flex-col md:flex-row md:justify-between md:items-center gap-4">
                  <div>
                    <p class="text-sm text-slate-500">Application</p>
                    <p class="font-extrabold text-slate-900">Status: ${a.status}</p>
                    <p class="text-xs text-slate-500 mt-1">Application ID: ${a.id}</p>
                  </div>
                  <div class="flex gap-2 flex-wrap">
                    ${["under_review", "shortlisted", "rejected", "selected"].map((s) => `<button class="px-4 py-2 rounded-xl border border-slate-200 text-sm font-bold hover:border-blue-300 hover:text-blue-700" onclick="setAppStatus('${a.id}','${s}')">${s.replace("_"," ")}</button>`).join("")}
                  </div>
                </div>
              </div>
            `;
          })
          .join("");
      }
    }
  } catch (e) {
    // ignore quietly for now
  }
}

async function setAppStatus(appId, status) {
  try {
    await apiFetch(`/api/applications/${appId}`, { method: "PUT", body: { status } });
    showToast("Updated", `Application marked ${status.replace("_", " ")}.`);
    loadMyApplications();
  } catch (e) {
    showToast("Update failed", `Error: ${e.message}`);
  }
}

// AI Matching
async function loadRecommended() {
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "student") return showToast("Not allowed", "AI Match is for students.");

  try {
    const data = await apiFetch("/api/match/jobs/recommended");
    const items = data.items || [];
    const resultsDiv = document.getElementById("ai-match-results");
    const container = document.getElementById("internship-results");
    resultsDiv.classList.toggle("hidden", false);

    if (!items.length) {
      container.innerHTML = `<div class="bg-white border border-slate-100 rounded-[2rem] p-8 text-slate-600">No recommendations yet. Add skills in your profile and try again.</div>`;
      return;
    }

    container.innerHTML = items
      .map((it) => {
        const j = it.job;
        const m = it.match;
        const missing = (m.missing_required_skills || []).slice(0, 8);
        const recs = (m.recommended_courses || []).slice(0, 3);
        const extra = `
          <div class="bg-slate-50 border border-slate-100 rounded-2xl p-4">
            <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Match Score</p>
            <p class="text-2xl font-extrabold text-purple-700 mt-1">${m.score}%</p>
            ${missing.length ? `<p class="text-xs text-slate-600 mt-2"><span class="font-bold">Missing:</span> ${missing.join(", ")}</p>` : `<p class="text-xs text-emerald-700 mt-2 font-bold">All required skills matched</p>`}
            ${recs.length ? `<div class="mt-3 space-y-2">${recs
              .map((c) => `<a class="block text-sm font-bold text-blue-700 hover:underline" href="${c.url}" target="_blank" rel="noreferrer">${c.title} <span class="text-xs text-slate-500">(${c.skill})</span></a>`)
              .join("")}</div>` : ""}
          </div>
          <button class="bg-blue-600 text-white px-6 py-3 rounded-2xl font-bold hover:bg-blue-700" onclick="applyToJob('${j.id}')">Apply</button>
        `;
        return jobCard(j, extra);
      })
      .join("");

    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (e) {
    showToast("AI Match", `Error: ${e.message}. Make sure your student profile is saved with skills.`);
  }
}

// Mock tests
let activeTest = null;
let activeAnswers = {};
let activeQuestionIndex = 0;
let timerEndAt = null;
let timerHandle = null;

function fmtTime(sec) {
  const s = Math.max(0, sec | 0);
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function stopTimer() {
  if (timerHandle) clearInterval(timerHandle);
  timerHandle = null;
}

function startTimer(durationSeconds) {
  stopTimer();
  timerEndAt = Date.now() + durationSeconds * 1000;
  const el = document.getElementById("test-timer");
  timerHandle = setInterval(() => {
    const left = Math.ceil((timerEndAt - Date.now()) / 1000);
    if (el) el.innerText = `Timer: ${fmtTime(left)}`;
    if (left <= 0) {
      stopTimer();
      showToast("Time up", "Submitting your test automatically.");
      submitTest();
    }
  }, 500);
}

function testCard(t) {
  return `
    <div class="bg-white/75 border border-cyan-100 rounded-[2rem] p-7 shadow-sm hover:border-emerald-200 transition backdrop-blur-md">
      <h3 class="text-xl font-extrabold text-slate-900">${t.title}</h3>
      <p class="text-slate-500 text-sm mt-2">${t.question_count} questions • ${t.marks_per_question} marks each</p>
      <p class="text-slate-500 text-sm">Duration: ${Math.round((t.duration_seconds || 0) / 60)} minutes</p>
      <button class="mt-5 w-full bg-gradient-to-r from-cyan-500 to-emerald-500 text-white px-6 py-3 rounded-2xl font-bold hover:opacity-95" onclick="startTest('${t.test_id}')">Start Test</button>
    </div>
  `;
}

async function loadTests() {
  try {
    const data = await apiFetch("/api/tests");
    const list = document.getElementById("tests-list");
    if (!list) return;
    const items = data.items || [];
    list.innerHTML = items.map(testCard).join("");
  } catch (e) {
    showToast("Mock tests", `Error loading tests: ${e.message}`);
  }
}

function renderQuestion(q, idx) {
  const choices = (q.choices || [])
    .map((c, i) => {
      const checked = activeAnswers[q.id] === i ? "checked" : "";
      return `
        <label class="flex items-start gap-3 p-4 rounded-2xl border border-slate-200 hover:border-blue-300 cursor-pointer bg-white">
          <input type="radio" name="${q.id}" value="${i}" ${checked} onchange="selectAnswer('${q.id}', ${i})" class="mt-1">
          <div>
            <p class="font-bold text-slate-900">${c}</p>
          </div>
        </label>
      `;
    })
    .join("");

  return `
    <div class="bg-white/80 border border-slate-100 rounded-[2rem] p-7 shadow-sm backdrop-blur-md">
      <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Question ${idx + 1}</p>
      <h4 class="text-lg font-extrabold text-slate-900 mt-2">${q.q}</h4>
      <div class="mt-4 grid grid-cols-1 gap-3">${choices}</div>
    </div>
  `;
}

function selectAnswer(qid, index) {
  activeAnswers[qid] = index;
}

function renderActiveQuestion() {
  if (!activeTest) return;
  const qWrap = document.getElementById("test-questions");
  if (!qWrap) return;

  const total = (activeTest.questions || []).length;
  if (!total) {
    qWrap.innerHTML = `<div class="bg-white border border-slate-100 rounded-[2rem] p-6 text-slate-600">No questions available in this test.</div>`;
    return;
  }

  const idx = Math.max(0, Math.min(activeQuestionIndex, total - 1));
  activeQuestionIndex = idx;
  const q = activeTest.questions[idx];
  const nextLabel = idx === total - 1 ? "Finish & Submit" : "Next Question";

  qWrap.innerHTML = `
    <div class="mb-4 flex items-center justify-between">
      <p class="text-sm font-bold text-slate-600">Question ${idx + 1} of ${total}</p>
      <p class="text-xs text-slate-500">Select one option and continue</p>
    </div>
    ${renderQuestion(q, idx)}
    <div class="mt-5 flex flex-wrap gap-3 justify-end">
      <button class="bg-slate-200 text-slate-700 px-5 py-2.5 rounded-xl font-bold ${idx === 0 ? "opacity-50 cursor-not-allowed" : ""}" onclick="prevQuestion()" ${idx === 0 ? "disabled" : ""}>Previous</button>
      <button class="bg-blue-600 text-white px-5 py-2.5 rounded-xl font-bold hover:bg-blue-700" onclick="nextQuestion()">${nextLabel}</button>
    </div>
  `;
}

function prevQuestion() {
  if (!activeTest) return;
  activeQuestionIndex = Math.max(0, activeQuestionIndex - 1);
  renderActiveQuestion();
}

function nextQuestion() {
  if (!activeTest) return;
  const total = (activeTest.questions || []).length;
  if (!total) return;
  if (activeQuestionIndex >= total - 1) {
    submitTest();
    return;
  }
  activeQuestionIndex = Math.min(total - 1, activeQuestionIndex + 1);
  renderActiveQuestion();
}

async function startTest(testId) {
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "student") return showToast("Not allowed", "Mock tests are for students.");

  try {
    const data = await apiFetch(`/api/tests/${testId}/questions`);
    activeTest = data.test;
    activeAnswers = {};
    activeQuestionIndex = 0;

    document.getElementById("test-title").innerText = activeTest.title;
    document.getElementById("test-result").classList.add("hidden");
    document.getElementById("test-runner").classList.remove("hidden");

    renderActiveQuestion();
    startTimer(activeTest.duration_seconds || 900);
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (e) {
    showToast("Start test failed", `Error: ${e.message}`);
  }
}

function exitTest() {
  stopTimer();
  activeTest = null;
  activeAnswers = {};
  activeQuestionIndex = 0;
  document.getElementById("test-runner").classList.add("hidden");
}

async function submitTest() {
  if (!activeTest) return;
  stopTimer();

  try {
    const data = await apiFetch(`/api/tests/${activeTest.test_id}/submit`, { method: "POST", body: { answers: activeAnswers } });
    const r = data.result;
    const el = document.getElementById("test-result");
    document.getElementById("test-result-text").innerText = `Score: ${r.score_marks}/${r.total_marks} • Correct: ${r.correct}/${r.total_questions}`;
    el.classList.remove("hidden");
    refreshStudentDashboard();
  } catch (e) {
    showToast("Submit failed", `Error: ${e.message}`);
  }
}

// Dashboard stats
async function refreshStudentDashboard() {
  if (!API.token || API.user?.role !== "student") return;
  try {
    const data = await apiFetch("/api/students/me/dashboard");
    const s = data?.stats || {};
    const tests = Number(s.tests_given ?? 0) || 0;
    const applied = Number(s.internships_applied ?? 0) || 0;
    const courses = Number(s.courses_watched ?? 0) || 0;
    const skills = Number(s.skills_known ?? 0) || 0;

    setTextIfPresent("stat-tests", String(tests));
    setTextIfPresent("stat-applied", String(applied));
    setTextIfPresent("stat-courses", String(courses));
    setTextIfPresent("stat-skills", String(skills));

  } catch (e) {
    setTextIfPresent("stat-tests", "0");
    setTextIfPresent("stat-applied", "0");
    setTextIfPresent("stat-courses", "0");
    setTextIfPresent("stat-skills", "0");
    showToast("Dashboard", "Could not refresh dashboard right now. Please try again.");
  }
}

async function matchJob(jobId) {
  if (!API.token) return openAuthModal("login");
  if (API.user?.role !== "student") return showToast("Not allowed", "AI Match is for students.");
  try {
    const data = await apiFetch(`/api/match/jobs/${jobId}`);
    const m = data.match;
    const missing = (m.missing_required_skills || []).join(", ") || "None";
    showToast("Match result", `Score: ${m.score}% • Missing: ${missing}`);
  } catch (e) {
    showToast("Match failed", `Error: ${e.message}`);
  }
}

// Global search mirrors job search
document.getElementById("global-search")?.addEventListener("input", (e) => {
  const el = document.getElementById("job-search");
  if (el) el.value = e.target.value;
});
document.getElementById("job-search")?.addEventListener("input", () => loadJobs());

// Initial boot
window.addEventListener("load", () => {
  onAuthed();
  loadJobs();
  loadCourses();
  loadTests();
  refreshStudentDashboard();

  // Skills input: Enter to add
  document.getElementById("skills-search")?.addEventListener("keydown", (e) => {
    if (!profileIsEditing) return;
    if (e.key === "Enter") {
      e.preventDefault();
      addSkill(e.target.value);
      e.target.value = "";
    }
  });
  document.getElementById("skills-modal-search")?.addEventListener("input", (e) => renderSkillsModalList(e.target.value));
  renderSkillChips();
  renderAiSnapshotSkills();
});

