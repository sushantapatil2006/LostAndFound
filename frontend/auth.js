const API = "/api";
let authMode = "register";

const message = (text, error = false) => {
  const element = document.querySelector("#message");
  element.textContent = text;
  element.classList.toggle("error", error);
};

function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === "register";
  document.querySelector("#register-tab").classList.toggle("active", registering);
  document.querySelector("#login-tab").classList.toggle("active", !registering);
  document.querySelector("#register-tab").setAttribute("aria-selected", registering);
  document.querySelector("#login-tab").setAttribute("aria-selected", !registering);
  document.querySelector("#name-field").hidden = !registering;
  document.querySelector("#name").required = registering;
  document.querySelector("#auth-title").textContent = registering ? "Create your account" : "Welcome back";
  document.querySelector("#auth-subtitle").textContent = registering ? "Sign up to browse and post campus listings." : "Log in to browse listings and manage your posts.";
  document.querySelector("#auth-submit").innerHTML = registering ? "Create account <span>→</span>" : "Log in <span>→</span>";
}

document.querySelector("#register-tab").addEventListener("click", () => setAuthMode("register"));
document.querySelector("#login-tab").addEventListener("click", () => setAuthMode("login"));

document.querySelector("#auth-form").addEventListener("submit", async event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  const endpoint = authMode === "register" ? "register" : "login";
  try {
    const response = await fetch(`${API}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    const body = await response.json();
    if (!response.ok) return message(body.error || "Unable to authenticate", true);
    localStorage.setItem("campus-token", body.token);
    window.location.replace("index.html");
  } catch {
    message("Cannot connect to the server. Make sure Flask is running.", true);
  }
});

setAuthMode("register");
