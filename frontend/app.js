const API = "/api";
let token = localStorage.getItem("campus-token");

const message = (text, error = false) => {
  const element = document.querySelector("#message");
  element.textContent = text;
  element.classList.toggle("error", error);
};

const authHeaders = () => token ? { Authorization: `Bearer ${token}` } : {};

async function loadItems(url = `${API}/items`) {
  const listings = document.querySelector("#listings");
  const count = document.querySelector("#listing-count");
  listings.innerHTML = '<p class="empty">Loading listings...</p>';
  try {
    const response = await fetch(url);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Unable to load listings");
    count.textContent = `${body.items.length} ${body.items.length === 1 ? "listing" : "listings"}`;
    listings.innerHTML = body.items.length ? body.items.map(renderItem).join("") : '<p class="empty">No listings yet. Be the first to post an item.</p>';
  } catch (error) {
    count.textContent = "Unavailable";
    listings.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function sanitizeImageUrl(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return escapeHtml(url);
    }
  } catch {
    if (url.startsWith("/") && !url.startsWith("//")) {
      return escapeHtml(url);
    }
  }
  return "";
}

function renderItem(item) {
  const safeImg = sanitizeImageUrl(item.image_url);
  return `<article class="card">${safeImg ? `<img src="${safeImg}" alt="${escapeHtml(item.title)}">` : ""}
    <div class="card-top"><span class="tag">${escapeHtml(item.item_type)}</span><span class="status">${escapeHtml(item.status)}</span></div>
    <h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.description)}</p><span class="location">${escapeHtml(item.location)}</span></article>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character]));
}

document.querySelector("#search-form").addEventListener("submit", async event => {
  event.preventDefault();
  const query = document.querySelector("#query").value.trim();
  await loadItems(query ? `${API}/search?q=${encodeURIComponent(query)}` : `${API}/items`);
});

document.querySelector("#all").addEventListener("click", () => {
  document.querySelector("#query").value = "";
  loadItems();
});

document.querySelector("#item-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!token) return message("Please create an account or log in first.", true);
  const response = await fetch(`${API}/items`, { method: "POST", headers: authHeaders(), body: new FormData(event.target) });
  const body = await response.json();
  if (!response.ok) return message(body.error, true);
  event.target.reset();
  message("Listing published successfully.");
  await loadItems();
});

const logoutBtn = document.querySelector("#logout-btn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("campus-token");
    window.location.replace("auth.html");
  });
}

loadItems();
