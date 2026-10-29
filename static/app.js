/* Saliksik AI dashboard — talks to the public REST API of the same origin. */
(function () {
  "use strict";

  var TOKEN_KEY = "saliksik.access_token";
  var USER_KEY = "saliksik.user";
  var state = {
    token: null,
    user: null,
    taskId: null,
    pollTimer: null,
    historyPage: 1,
    hasProfile: false,
    adminPage: 1,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function showAlert(container, message, kind) {
    var box = $(container);
    if (!box) return;
    box.textContent = message || "";
    box.className = "alert" + (message ? " show " + (kind || "info") : "");
  }

  function setToken(token, user) {
    state.token = token;
    state.user = user || null;
    if (token) {
      window.localStorage.setItem(TOKEN_KEY, token);
      if (user) window.localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(USER_KEY);
    }
    renderAuthState();
  }

  function loadSession() {
    var token = window.localStorage.getItem(TOKEN_KEY);
    var raw = window.localStorage.getItem(USER_KEY);
    state.token = token || null;
    try {
      state.user = raw ? JSON.parse(raw) : null;
    } catch (error) {
      state.user = null;
    }
    renderAuthState();
  }

  function renderAuthState() {
    var signedIn = !!state.token;
    $("auth-card").classList.toggle("hidden", signedIn);
    ["analysis-card", "history-card", "reviewer-card", "tools-card"].forEach(function (id) {
      $(id).classList.toggle("hidden", !signedIn);
    });
    $("admin-card").classList.toggle("hidden", !(signedIn && isAdmin()));
    var badge = $("user-badge");
    var logout = $("logout-btn");
    if (signedIn) {
      var name = state.user ? state.user.username : "signed in";
      badge.textContent = name;
      badge.className = "badge ok";
      badge.classList.remove("hidden");
      logout.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
      logout.classList.add("hidden");
    }
  }

  function errorMessage(response, body) {
    if (body && body.error && body.error.message) return body.error.message;
    if (body && body.detail) {
      if (typeof body.detail === "string") return body.detail;
      if (Array.isArray(body.detail) && body.detail.length) {
        return body.detail.map(function (item) {
          return item.msg || JSON.stringify(item);
        }).join("; ");
      }
    }
    return "Request failed (" + response.status + ")";
  }

  function api(path, options) {
    options = options || {};
    var headers = options.headers || {};
    if (state.token) headers["Authorization"] = "Bearer " + state.token;
    return fetch(path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body,
    }).then(function (response) {
      return response
        .json()
        .catch(function () {
          return null;
        })
        .then(function (body) {
          if (!response.ok) {
            var error = new Error(errorMessage(response, body));
            error.status = response.status;
            throw error;
          }
          return body;
        });
    });
  }

  /* ---------------------------------------------------------------- health */

  function checkHealth() {
    var badge = $("health-badge");
    fetch("/health")
      .then(function (response) {
        return response.json().then(function (body) {
          return { ok: response.ok, body: body };
        });
      })
      .then(function (result) {
        if (result.ok && result.body.status === "healthy") {
          badge.textContent = "healthy";
          badge.className = "badge ok";
        } else {
          badge.textContent = (result.body && result.body.status) || "unhealthy";
          badge.className = "badge warn";
        }
      })
      .catch(function () {
        badge.textContent = "offline";
        badge.className = "badge bad";
      });
  }

  /* -------------------------------------------------------------- auth */

  function login() {
    var username = $("login-username").value.trim();
    var password = $("login-password").value;
    if (!username || !password) {
      showAlert("auth-alert", "Enter a username and a password.", "error");
      return;
    }
    var form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    api("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    })
      .then(function (data) {
        setToken(data.access_token, data.user);
        showAlert("auth-alert", "", "info");
        $("login-password").value = "";
        loadHistory();
        loadReviewerProfile();
      })
      .catch(function (error) {
        showAlert("auth-alert", error.message, "error");
      });
  }

  function register() {
    var username = $("register-username").value.trim();
    var email = $("register-email").value.trim();
    var password = $("register-password").value;
    var institution = $("register-institution").value.trim();
    if (!username || !email || !password) {
      showAlert("auth-alert", "Username, email and password are required.", "error");
      return;
    }
    var payload = { username: username, email: email, password: password };
    if (institution) payload.institution = institution;

    api("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (data) {
        setToken(data.access_token, data.user);
        showAlert("auth-alert", "Account created. You are signed in.", "success");
        $("register-password").value = "";
        loadHistory();
        loadReviewerProfile();
      })
      .catch(function (error) {
        showAlert("auth-alert", error.message, "error");
      });
  }

  function logout() {
    var refresh = window.localStorage.getItem("saliksik.refresh_token");
    var request = api("/api/v1/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(refresh ? { refresh_token: refresh } : {}),
    }).catch(function () {
      /* logging out locally must work even when the server call fails */
    });
    request.then(function () {
      setToken(null);
      showAlert("auth-alert", "You have been logged out.", "info");
    });
  }

  /* ---------------------------------------------------------- analysis */

  function submitAnalysis() {
    var text = $("manuscript-text").value.trim();
    var file = $("manuscript-file").files[0];
    if (!text && !file) {
      showAlert("analysis-alert", "Provide the manuscript text or a PDF file.", "error");
      return;
    }

    var form = new FormData();
    if (text) form.append("manuscript_text", text);
    if (file) form.append("manuscript_file", file);

    $("submit-btn").disabled = true;
    $("task-status").textContent = "submitting";
    showAlert("analysis-alert", "", "info");

    api("/api/v1/analysis/pre-review", { method: "POST", body: form })
      .then(function (data) {
        state.taskId = data.task_id;
        $("task-status").textContent = "queued";
        pollStatus();
      })
      .catch(function (error) {
        $("submit-btn").disabled = false;
        $("task-status").textContent = "failed";
        showAlert("analysis-alert", error.message, "error");
      });
  }

  function pollStatus() {
    if (!state.taskId) return;
    api("/api/v1/analysis/status/" + encodeURIComponent(state.taskId))
      .then(function (data) {
        if (data.summary !== undefined && data.status === undefined) {
          renderResult(data);
          $("task-status").textContent = "completed";
          $("submit-btn").disabled = false;
          loadHistory();
          loadReviewerSuggestions(data.metadata ? data.metadata.analysis_id : null);
          return;
        }
        $("task-status").textContent = (data.status || "processing").toLowerCase();
        if (data.status === "FAILED") {
          $("submit-btn").disabled = false;
          showAlert("analysis-alert", data.message || "The analysis failed.", "error");
          return;
        }
        state.pollTimer = window.setTimeout(pollStatus, 3000);
      })
      .catch(function (error) {
        $("submit-btn").disabled = false;
        $("task-status").textContent = "failed";
        showAlert("analysis-alert", error.message, "error");
      });
  }

  function metric(label, value) {
    return (
      '<div class="metric"><div class="value">' +
      value +
      '</div><div class="label">' +
      label +
      "</div></div>"
    );
  }

  function renderResult(result) {
    $("result-area").classList.remove("hidden");
    var quality = result.language_quality || {};
    var meta = result.metadata || {};

    $("result-metrics").innerHTML = [
      metric("Words", quality.word_count || 0),
      metric("Sentences", quality.sentence_count || 0),
      metric(
        "Readability",
        (quality.readability_approximate ? "≈" : "") + Math.round((quality.readability_score || 0) * 10) / 10
      ),
      metric("Entities", quality.named_entities || 0),
      metric("Processing", (meta.processing_time || 0).toFixed(2) + "s"),
    ].join("");

    $("result-summary").textContent = result.summary || "";

    var keywords = $("result-keywords");
    keywords.innerHTML = "";
    (result.keywords || []).forEach(function (keyword) {
      var tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = keyword;
      keywords.appendChild(tag);
    });

    var language = $("result-language");
    if (result.language) {
      language.innerHTML =
        "<h3>Detected language</h3><span class='badge ok'>" +
        result.language.name +
        " (" +
        result.language.code +
        ", confidence " +
        Math.round((result.language.confidence || 0) * 100) +
        "%)</span>";
    } else {
      language.innerHTML = "";
    }

    var plagiarism = $("result-plagiarism");
    if (result.plagiarism) {
      var score = Math.round((result.plagiarism.overall_similarity || 0) * 100);
      plagiarism.innerHTML =
        "<h3>Plagiarism</h3><span class='badge " +
        (result.plagiarism.is_plagiarized ? "bad" : "ok") +
        "'>" +
        (result.plagiarism.is_plagiarized ? "similar content found" : "no significant overlap") +
        "</span> <span class='badge'>highest similarity " +
        score +
        "%</span> <span class='badge'>unique content " +
        Math.round(result.plagiarism.unique_content_percentage || 0) +
        "%</span>";
    } else {
      plagiarism.innerHTML = "";
    }

    var citations = $("result-citations");
    if (result.citation_analysis) {
      citations.innerHTML =
        "<h3>Citations</h3><span class='badge'>" +
        result.citation_analysis.total_citations +
        " references</span> <span class='badge'>" +
        result.citation_analysis.format_detected +
        "</span> <span class='badge'>" +
        Math.round(result.citation_analysis.format_consistency || 0) +
        "% consistent</span>";
    } else {
      citations.innerHTML = "";
    }
  }

  function loadReviewerSuggestions(analysisId) {
    var container = $("result-reviewers");
    if (!analysisId) {
      container.innerHTML = "";
      return;
    }
    api("/api/v1/reviewers/analysis/" + analysisId + "/suggestions")
      .then(function (data) {
        var suggestions = data.suggestions || [];
        if (!suggestions.length) {
          container.innerHTML = "<h3>Reviewer suggestions</h3><p class='muted small'>No suggestions available.</p>";
          return;
        }
        container.innerHTML =
          "<h3>Reviewer suggestions</h3>" +
          suggestions
            .slice(0, 5)
            .map(function (item) {
              return (
                "<span class='badge'>" +
                item.username +
                " — " +
                Math.round((item.match_score || 0) * 100) +
                "%</span>"
              );
            })
            .join(" ");
      })
      .catch(function () {
        container.innerHTML = "";
      });
  }

  /* ----------------------------------------------------------- history */

  function loadHistory() {
    if (!state.token) return;
    api("/api/v1/analysis/history?page=" + state.historyPage + "&page_size=10")
      .then(function (data) {
        var results = data.results || [];
        var pagination = data.pagination || {};
        if (!results.length) {
          $("history-body").innerHTML = '<p class="muted small">No analyses yet.</p>';
        } else {
          var rows = results
            .map(function (item) {
              var created = item.created_at ? new Date(item.created_at).toLocaleString() : "";
              return (
                "<tr><td>" +
                (item.filename || "Manuscript") +
                "</td><td>" +
                (item.word_count || 0) +
                "</td><td>" +
                Math.round((item.readability_score || 0) * 10) / 10 +
                "</td><td>" +
                created +
                "</td></tr>"
              );
            })
            .join("");
          $("history-body").innerHTML =
            "<table><thead><tr><th>Manuscript</th><th>Words</th><th>Readability</th><th>Created</th></tr></thead><tbody>" +
            rows +
            "</tbody></table>";
        }
        $("history-prev").disabled = !pagination.has_previous;
        $("history-next").disabled = !pagination.has_next;
      })
      .catch(function (error) {
        showAlert("history-alert", error.message, "error");
      });
  }

  /* ---------------------------------------------------------- reviewer */

  function loadReviewerProfile() {
    if (!state.token) return;
    api("/api/v1/reviewers/me")
      .then(function (profile) {
        state.hasProfile = true;
        $("reviewer-state").textContent = "profile saved";
        $("reviewer-state").className = "badge ok";
        $("reviewer-keywords").value = (profile.expertise_keywords || []).join(", ");
        $("reviewer-description").value = profile.expertise_description || "";
        $("reviewer-institution").value = profile.institution || "";
        $("reviewer-department").value = profile.department || "";
        $("reviewer-orcid").value = profile.orcid_id || "";
        $("reviewer-max").value = profile.max_assignments || 5;
      })
      .catch(function (error) {
        if (error.status === 404) {
          state.hasProfile = false;
          $("reviewer-state").textContent = "no profile";
          $("reviewer-state").className = "badge";
        } else {
          showAlert("reviewer-alert", error.message, "error");
        }
      });
  }

  function saveReviewerProfile() {
    var keywords = $("reviewer-keywords")
      .value.split(",")
      .map(function (item) {
        return item.trim();
      })
      .filter(function (item) {
        return item.length > 0;
      });
    if (!keywords.length) {
      showAlert("reviewer-alert", "Add at least one expertise keyword.", "error");
      return;
    }
    var payload = {
      expertise_keywords: keywords,
      expertise_description: $("reviewer-description").value.trim() || null,
      institution: $("reviewer-institution").value.trim() || null,
      department: $("reviewer-department").value.trim() || null,
      orcid_id: $("reviewer-orcid").value.trim() || null,
      max_assignments: parseInt($("reviewer-max").value, 10) || 5,
    };
    showAlert("reviewer-alert", "", "info");

    var method = state.hasProfile ? "PUT" : "POST";
    var path = state.hasProfile ? "/api/v1/reviewers/me" : "/api/v1/reviewers/";

    api(path, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function () {
        state.hasProfile = true;
        $("reviewer-state").textContent = "profile saved";
        $("reviewer-state").className = "badge ok";
        showAlert("reviewer-alert", "Profile saved.", "success");
      })
      .catch(function (error) {
        showAlert("reviewer-alert", error.message, "error");
      });
  }

  /* ------------------------------------------------------------- tools */

  function analyseCitations() {
    var text = $("citation-text").value.trim();
    if (text.length < 100) {
      showAlert("tools-alert", "Provide at least 100 characters of manuscript text.", "error");
      return;
    }
    showAlert("tools-alert", "", "info");
    api("/api/v1/citations/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manuscript_text: text }),
    })
      .then(function (data) {
        var issues = data.issues || [];
        $("tools-output").innerHTML =
          "<div class='metrics'>" +
          metric("References", data.total_citations || 0) +
          metric("Valid", data.valid_citations || 0) +
          metric("Format", data.format_detected || "unknown") +
          metric("Consistency", Math.round(data.format_consistency || 0) + "%") +
          "</div>" +
          (issues.length
            ? "<h3 style='margin-top:16px'>Issues</h3><ul class='small'>" +
              issues
                .slice(0, 15)
                .map(function (issue) {
                  return "<li>" + (issue.description || issue.issue_type) + "</li>";
                })
                .join("") +
              "</ul>"
            : "<p class='muted small'>No issues found.</p>");
      })
      .catch(function (error) {
        showAlert("tools-alert", error.message, "error");
      });
  }

  function checkPlagiarism() {
    var text = $("citation-text").value.trim();
    if (text.length < 50) {
      showAlert("tools-alert", "Provide at least 50 characters of manuscript text.", "error");
      return;
    }
    showAlert("tools-alert", "", "info");
    api("/api/v1/plagiarism/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manuscript_text: text }),
    })
      .then(function (data) {
        $("tools-output").innerHTML =
          "<div class='metrics'>" +
          metric("Similarity", Math.round((data.overall_similarity || 0) * 100) + "%") +
          metric("Unique", Math.round(data.unique_content_percentage || 0) + "%") +
          metric("Compared", data.checked_against || 0) +
          metric("Flagged", data.is_plagiarized ? "yes" : "no") +
          "</div>";
      })
      .catch(function (error) {
        showAlert("tools-alert", error.message, "error");
      });
  }

  function loadIndexStats() {
    showAlert("tools-alert", "", "info");
    api("/api/v1/plagiarism/stats")
      .then(function (data) {
        $("tools-output").innerHTML =
          "<div class='metrics'>" +
          metric("Indexed", data.documents_indexed || 0) +
          metric("Threshold", data.threshold || 0) +
          metric("Permutations", data.num_permutations || 0) +
          metric("Shingle size", data.shingle_size || 0) +
          "</div>";
      })
      .catch(function (error) {
        showAlert("tools-alert", error.message, "error");
      });
  }

  /* ---------------------------------------------------------- admin */

  function isAdmin() {
    return !!(state.user && state.user.role === "admin");
  }

  function loadAdminStats() {
    if (!isAdmin()) return;
    api("/api/v1/admin/stats")
      .then(function (data) {
        $("admin-stats").innerHTML = [
          metric("Users", data.total_users || 0),
          metric("Active", data.active_users || 0),
          metric("Verified", data.verified_users || 0),
          metric("Analyses", data.total_analyses || 0),
          metric("Completed", data.completed_analyses || 0),
          metric("Failed", data.failed_analyses || 0),
          metric("Reviewers", data.total_reviewers || 0),
          metric("Assignments", data.total_assignments || 0),
        ].join("");
      })
      .catch(function (error) {
        showAlert("admin-alert", error.message, "error");
      });
  }

  function loadAdminUsers() {
    if (!isAdmin()) return;
    var params = new URLSearchParams();
    params.append("page", String(state.adminPage));
    params.append("page_size", "10");
    var search = $("admin-search").value.trim();
    if (search) params.append("search", search);
    var role = $("admin-role").value;
    if (role) params.append("role", role);
    var active = $("admin-active").value;
    if (active) params.append("is_active", active);

    api("/api/v1/admin/users?" + params.toString())
      .then(function (data) {
        var results = data.results || [];
        if (!results.length) {
          $("admin-users").innerHTML = '<p class="muted small">No users match the filter.</p>';
        } else {
          var rows = results
            .map(function (item) {
              var roleOptions = ["user", "editor", "admin"]
                .map(function (role) {
                  return (
                    '<option value="' +
                    role +
                    '"' +
                    (item.role === role ? " selected" : "") +
                    ">" +
                    role +
                    "</option>"
                  );
                })
                .join("");
              return (
                "<tr><td>" +
                item.username +
                '<div class="muted small">' +
                item.email +
                "</div></td>" +
                '<td><select data-role-for="' +
                item.id +
                '">' +
                roleOptions +
                "</select></td>" +
                "<td>" +
                '<span class="badge ' +
                (item.is_active ? "ok" : "bad") +
                '">' +
                (item.is_active ? "active" : "inactive") +
                "</span></td>" +
                '<td><button class="secondary" data-save-user="' +
                item.id +
                '">Save</button></td></tr>'
              );
            })
            .join("");
          $("admin-users").innerHTML =
            "<table><thead><tr><th>User</th><th>Role</th><th>Status</th><th></th></tr></thead><tbody>" +
            rows +
            "</tbody></table>";
          $("admin-users").querySelectorAll("[data-save-user]").forEach(function (button) {
            button.addEventListener("click", function () {
              saveAdminUser(button.getAttribute("data-save-user"));
            });
          });
        }
        $("admin-prev").disabled = !data.has_previous;
        $("admin-next").disabled = !data.has_next;
      })
      .catch(function (error) {
        showAlert("admin-alert", error.message, "error");
      });
  }

  function saveAdminUser(userId) {
    var select = $("admin-users").querySelector('[data-role-for="' + userId + '"]');
    if (!select) return;
    api("/api/v1/admin/users/" + userId, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: select.value }),
    })
      .then(function () {
        showAlert("admin-alert", "User updated.", "success");
        loadAdminStats();
        loadAdminUsers();
      })
      .catch(function (error) {
        showAlert("admin-alert", error.message, "error");
      });
  }

  /* -------------------------------------------------------------- init */

  document.addEventListener("DOMContentLoaded", function () {
    loadSession();
    checkHealth();
    window.setInterval(checkHealth, 30000);

    $("login-btn").addEventListener("click", login);
    $("register-btn").addEventListener("click", register);
    $("logout-btn").addEventListener("click", logout);
    $("submit-btn").addEventListener("click", submitAnalysis);
    $("history-refresh").addEventListener("click", loadHistory);
    $("history-prev").addEventListener("click", function () {
      if (state.historyPage > 1) {
        state.historyPage -= 1;
        loadHistory();
      }
    });
    $("history-next").addEventListener("click", function () {
      state.historyPage += 1;
      loadHistory();
    });
    $("reviewer-save").addEventListener("click", saveReviewerProfile);
    $("citation-btn").addEventListener("click", analyseCitations);
    $("plagiarism-btn").addEventListener("click", checkPlagiarism);
    $("stats-btn").addEventListener("click", loadIndexStats);
    $("admin-refresh").addEventListener("click", function () {
      state.adminPage = 1;
      loadAdminStats();
      loadAdminUsers();
    });
    $("admin-search").addEventListener("change", function () {
      state.adminPage = 1;
      loadAdminUsers();
    });
    $("admin-role").addEventListener("change", function () {
      state.adminPage = 1;
      loadAdminUsers();
    });
    $("admin-active").addEventListener("change", function () {
      state.adminPage = 1;
      loadAdminUsers();
    });
    $("admin-prev").addEventListener("click", function () {
      if (state.adminPage > 1) {
        state.adminPage -= 1;
        loadAdminUsers();
      }
    });
    $("admin-next").addEventListener("click", function () {
      state.adminPage += 1;
      loadAdminUsers();
    });

    if (state.token) {
      loadHistory();
      loadReviewerProfile();
      loadAdminStats();
      loadAdminUsers();
    }
  });
})();
