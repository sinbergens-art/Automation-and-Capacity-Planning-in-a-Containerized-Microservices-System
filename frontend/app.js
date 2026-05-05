const TOKEN_KEY = "sre_shop_token";
const USER_KEY  = "sre_shop_user";
const cart = [];

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
 
function getToken() { return localStorage.getItem(TOKEN_KEY); }
function getUser()  { return localStorage.getItem(USER_KEY); }
 
function authHeaders() {
  const t = getToken();
  return t ? { "Authorization": `Bearer ${t}` } : {};
}
 
async function api(method, url, body) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  let data = null;
  try { data = await r.json(); } catch (_) { /* no body */ }
  if (!r.ok) {
    const detail = (data && data.detail) || `HTTP ${r.status}`;
    throw new Error(detail);
  }
  return data;
}

function showApp(username) {
  $("#authSection").classList.add("hidden");
  $("#appSection").classList.remove("hidden");
  $("#userBox").classList.remove("hidden");
  $("#whoami").textContent = `👤 ${username}`;
  switchView("products");
  loadProducts();
  loadOrders();
  loadProfile();
  loadInbox();
}
 
function showAuth() {
  $("#authSection").classList.remove("hidden");
  $("#appSection").classList.add("hidden");
  $("#userBox").classList.add("hidden");
}
 
function switchView(view) {
  $$(".navbtn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach(v => v.classList.add("hidden"));
  $(`#view-${view}`).classList.remove("hidden");
}
 
$$(".tab").forEach(t => t.addEventListener("click", () => {
  $$(".tab").forEach(x => x.classList.toggle("active", x === t));
  if (t.dataset.tab === "login") {
    $("#loginForm").classList.remove("hidden");
    $("#registerForm").classList.add("hidden");
  } else {
    $("#loginForm").classList.add("hidden");
    $("#registerForm").classList.remove("hidden");
  }
}));

$("#registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const msg = $("#registerMsg");
  msg.textContent = "registering...";
  try {
    const data = await api("POST", "/auth/register", {
      username: fd.get("username"),
      email:    fd.get("email"),
      password: fd.get("password"),
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, fd.get("username"));
    showApp(fd.get("username"));
  } catch (err) {
    msg.textContent = "❌ " + err.message;
  }
});

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const msg = $("#loginMsg");
  msg.textContent = "logging in...";
  try {
    const data = await api("POST", "/auth/login", {
      username: fd.get("username"),
      password: fd.get("password"),
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, fd.get("username"));
    showApp(fd.get("username"));
  } catch (err) {
    msg.textContent = "❌ " + err.message;
  }
});
 
$("#logoutBtn").addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  showAuth();
});

$$(".navbtn").forEach(b => b.addEventListener("click", () => {
  switchView(b.dataset.view);
  if (b.dataset.view === "orders")   loadOrders();
  if (b.dataset.view === "products") loadProducts();
  if (b.dataset.view === "profile")  loadProfile();
  if (b.dataset.view === "chat")     loadInbox();
}));

async function loadProducts() {
  const root = $("#products");
  root.innerHTML = "loading...";
  try {
    const list = await api("GET", "/products");
    root.innerHTML = "";
    list.forEach(p => {
      const el = document.createElement("div");
      el.className = "product";
      el.innerHTML = `
        <h3>${p.name}</h3>
        <p>${p.description || ""}</p>
        <p class="price">$${Number(p.price).toFixed(2)}</p>
        <button data-id="${p.id}">Add to cart</button>`;
      el.querySelector("button").addEventListener("click", () => addToCart(p));
      root.appendChild(el);
    });
  } catch (err) {
    root.innerHTML = `❌ ${err.message}`;
  }
}
 
function addToCart(p) {
  const found = cart.find(x => x.product_id === p.id);
  if (found) found.quantity += 1;
  else cart.push({ product_id: p.id, quantity: 1, name: p.name, price: Number(p.price) });
  renderCart();
}
 
function renderCart() {
  const ul = $("#cartItems"); ul.innerHTML = "";
  let total = 0;
  cart.forEach((it) => {
    total += it.price * it.quantity;
    const li = document.createElement("li");
    li.textContent = `${it.name} × ${it.quantity}  ($${(it.price * it.quantity).toFixed(2)})`;
    ul.appendChild(li);
  });
  $("#cartTotal").textContent = total.toFixed(2);
}
 
$("#checkoutBtn").addEventListener("click", async () => {
  const msg = $("#checkoutMsg");
  if (!cart.length) { msg.textContent = "Cart is empty"; return; }
  msg.textContent = "placing order...";
  try {
    const items = cart.map(c => ({ product_id: c.product_id, quantity: c.quantity }));
    const data = await api("POST", "/orders", { username: getUser(), items });
    msg.textContent = `✅ Order #${data.id} created (total $${Number(data.total).toFixed(2)})`;
    cart.length = 0;
    renderCart();
    loadOrders();
  } catch (err) {
    msg.textContent = "❌ " + err.message;
  }
});

async function loadOrders() {
  const tbody = $("#ordersBody");
  tbody.innerHTML = "<tr><td colspan='3'>loading...</td></tr>";
  try {
    const orders = await api("GET", `/orders?username=${encodeURIComponent(getUser())}`);
    tbody.innerHTML = "";
    if (!orders.length) {
      tbody.innerHTML = "<tr><td colspan='3'>No orders yet</td></tr>";
      return;
    }
    orders.forEach(o => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>#${o.id}</td><td>$${Number(o.total).toFixed(2)}</td><td>${o.status}</td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan='3'>❌ ${err.message}</td></tr>`;
  }
}

async function loadProfile() {
  try {
    const p = await api("GET", `/users/${encodeURIComponent(getUser())}`);
    $("#profileForm").full_name.value = p.full_name || "";
    $("#profileForm").bio.value = p.bio || "";
  } catch (err) { /* no profile yet, that's fine */ }
}
 
$("#profileForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const msg = $("#profileMsg");
  try {
    await api("POST", "/users", {
      username: getUser(),
      full_name: fd.get("full_name"),
      bio: fd.get("bio"),
    });
    msg.textContent = "✅ Saved";
  } catch (err) { msg.textContent = "❌ " + err.message; }
});

$("#chatForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("POST", "/chat/send", {
      sender: getUser(),
      receiver: fd.get("receiver"),
      body: fd.get("body"),
    });
    e.target.reset();
    loadInbox();
  } catch (err) { alert(err.message); }
});
 
async function loadInbox() {
  const ul = $("#inbox"); ul.innerHTML = "loading...";
  try {
    const msgs = await api("GET", `/chat/inbox/${encodeURIComponent(getUser())}`);
    ul.innerHTML = "";
    if (!msgs.length) { ul.innerHTML = "<li class='muted'>No messages</li>"; return; }
    msgs.forEach(m => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${m.sender}</strong>: ${m.body}
                      <span class="ts">${new Date(m.created_at).toLocaleString()}</span>`;
      ul.appendChild(li);
    });
  } catch (err) { ul.innerHTML = `❌ ${err.message}`; }
}
 
window.addEventListener("DOMContentLoaded", () => {
  if (getToken() && getUser()) showApp(getUser());
  else showAuth();
});
 
