
const API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "studyhub_token";

// Get saved login token
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

// Update dashboard statistics
function updateDashboardStats(tasks) {
    const total = tasks.length;

    const completed = tasks.filter(function (task) {
        return Number(task.completed) === 1;
    }).length;

    const pending = total - completed;

    const progress = total === 0
        ? 0
        : Math.round((completed / total) * 100);

    document.getElementById("totalTasks").textContent = total;
    document.getElementById("completedTasks").textContent = completed;
    document.getElementById("pendingTasks").textContent = pending;
    document.getElementById("taskProgress").textContent = progress + "%";
}

// Send requests that require login
async function authenticatedFetch(url, options = {}) {
    const token = getToken();

    if (!token) {
        throw new Error("Please log in first.");
    }

    const headers = {
        ...(options.headers || {}),
        "Authorization": "Bearer " + token
    };

    return fetch(url, {
        ...options,
        headers
    });
}

// Load tasks belonging to the logged-in user
async function loadBackendTasks() {
    const taskList = document.getElementById("taskList");

    if (!taskList) return;

    taskList.innerHTML = "";

    if (!getToken()) {
        taskList.textContent = "Please log in to view your tasks.";
        updateDashboardStats([]);
        return;
    }

    try {
        const response = await authenticatedFetch(
            API_URL + "/api/tasks"
        );

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401) {
                localStorage.removeItem(TOKEN_KEY);
            }

            throw new Error(data.detail || "Failed to load tasks.");
        }

        // Update dashboard cards using real backend data
        updateDashboardStats(data.tasks);

        data.tasks.forEach(function (task) {
            const item = document.createElement("li");
            const taskText = document.createElement("span");

            taskText.textContent = task.text;

            if (Number(task.completed) === 1) {
                taskText.style.textDecoration = "line-through";
            }

            // Complete or undo task
            const completeButton = document.createElement("button");

            completeButton.textContent =
                Number(task.completed) === 1 ? "Undo" : "Done";

            completeButton.onclick = async function () {
                try {
                    const result = await authenticatedFetch(
                        API_URL + "/api/tasks/" + task.id,
                        { method: "PUT" }
                    );

                    if (!result.ok) {
                        const error = await result.json();
                        throw new Error(
                            error.detail || "Update failed."
                        );
                    }

                    await loadBackendTasks();
                } catch (error) {
                    alert(error.message);
                }
            };

            // Delete task
            const deleteButton = document.createElement("button");
            deleteButton.textContent = "Delete";

            deleteButton.onclick = async function () {
                try {
                    const result = await authenticatedFetch(
                        API_URL + "/api/tasks/" + task.id,
                        { method: "DELETE" }
                    );

                    if (!result.ok) {
                        const error = await result.json();
                        throw new Error(
                            error.detail || "Delete failed."
                        );
                    }

                    await loadBackendTasks();
                } catch (error) {
                    alert(error.message);
                }
            };

            item.appendChild(taskText);
            item.appendChild(completeButton);
            item.appendChild(deleteButton);

            taskList.appendChild(item);
        });

        // Show a message when no tasks exist
        if (data.tasks.length === 0) {
            taskList.textContent = "No tasks yet. Add your first task!";
        }

    } catch (error) {
        console.error(error);
        taskList.textContent = error.message;
        updateDashboardStats([]);
    }
}

// Add a new task
async function addTask() {
    const input = document.getElementById("taskInput");
    const text = input.value.trim();

    if (!text) {
        alert("Please enter a task!");
        return;
    }

    try {
        const response = await authenticatedFetch(
            API_URL + "/api/tasks?task=" + encodeURIComponent(text),
            { method: "POST" }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Could not save task."
            );
        }

        input.value = "";
        await loadBackendTasks();

    } catch (error) {
        alert(error.message);
    }
}

// Create a new account
async function signup() {
    const name = document.getElementById("signupName").value.trim();
    const email = document.getElementById("signupEmail").value.trim();
    const password = document.getElementById("signupPassword").value;
    const message = document.getElementById("authMessage");

    if (!name || !email || !password) {
        message.textContent = "Please fill in all signup fields.";
        return;
    }

    try {
        const response = await fetch(API_URL + "/api/signup", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: name,
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Signup failed.");
        }

        message.textContent =
            "Account created successfully! You can now log in.";

    } catch (error) {
        message.textContent = error.message;
    }
}

// Log in and save the token
async function login() {
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;
    const message = document.getElementById("authMessage");

    if (!email || !password) {
        message.textContent = "Please enter your email and password.";
        return;
    }

    try {
        const response = await fetch(API_URL + "/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Login failed.");
        }

        localStorage.setItem(TOKEN_KEY, data.access_token);

document.getElementById("studentName").textContent =
    data.user.name;

message.textContent =
    "Welcome, " + data.user.name + "! Login successful.";

        await loadBackendTasks();

    } catch (error) {
        message.textContent = error.message;
    }
}

// Load dashboard when the page opens
document.addEventListener("DOMContentLoaded", function () {
    updateDashboardStats([]);
    loadBackendTasks();
});
