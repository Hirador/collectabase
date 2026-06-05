<template>
  <div id="app" class="app-layout">
    <NotificationStack />

    <!-- Desktop Sidebar -->
    <aside v-if="!isPublic" class="desktop-sidebar" :class="{ 'collapsed': collapsed }">
      <div class="sidebar-top">
        <router-link to="/" class="sidebar-logo">
          <img src="/icons/android-chrome-192x192.png" alt="Collectabase Logo" class="logo-img" />
          <span class="logo-text" v-show="!collapsed">Collectabase</span>
        </router-link>
        <button class="collapse-btn" @click="toggleSidebar" :title="collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'">
          <svg v-if="collapsed" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 17 18 12 13 7"></polyline><polyline points="6 17 11 12 6 7"></polyline></svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"></polyline><polyline points="18 17 13 12 18 7"></polyline></svg>
        </button>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/" active-class="" exact-active-class="active" title="My Collection">
          <span class="nav-icon">📚</span> <span v-show="!collapsed">My Collection</span>
        </router-link>
        <router-link to="/stats" title="Stats">
          <span class="nav-icon">📈</span> <span v-show="!collapsed">Stats</span>
        </router-link>
        <router-link to="/prices" title="Prices Browser">
          <span class="nav-icon">💰</span> <span v-show="!collapsed">Prices</span>
        </router-link>
        <router-link to="/wishlist" title="Wishlist">
          <span class="nav-icon">⭐</span> <span v-show="!collapsed">Wishlist</span>
        </router-link>
        <router-link to="/lots" title="Lots & Resale">
          <span class="nav-icon">📦</span> <span v-show="!collapsed">Lots</span>
        </router-link>
        <router-link to="/import" title="Import / Export">
          <span class="nav-icon">🧾</span> <span v-show="!collapsed">Import / Export</span>
        </router-link>
        <router-link v-if="auth.isSuperAdmin" to="/more" title="More Options">
          <span class="nav-icon">⚙️</span> <span v-show="!collapsed">More</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div v-if="!collapsed && collections.length" class="collection-switcher">
          <label>Collection</label>
          <select :value="activeCollectionId" @change="onCollectionChange">
            <option v-for="c in collections" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <router-link to="/collections" class="manage-collections-link">Manage collections…</router-link>
        </div>
        <router-link to="/add" class="btn btn-primary add-btn" active-class="btn-active" title="Add Item">
          <span v-if="collapsed" style="font-size: 1.25rem;">+</span>
          <span v-else>+ Add Item</span>
        </router-link>

        <!-- Username menu: Manage account + Log out -->
        <div v-if="user" class="user-menu" :class="{ collapsed }">
          <button class="user-trigger" @click="userMenuOpen = !userMenuOpen" :title="user.email">
            <span class="user-avatar">{{ (user.display_name || user.email || '?').charAt(0).toUpperCase() }}</span>
            <span v-show="!collapsed" class="user-trigger-name">{{ user.display_name || user.email }}</span>
            <span v-show="!collapsed" class="user-caret">⌄</span>
          </button>
          <div v-if="userMenuOpen" class="user-dropdown">
            <router-link to="/account" class="user-dropdown-item" @click="userMenuOpen = false">⚙️ Manage account</router-link>
            <button class="user-dropdown-item" @click="logout">🚪 Log out</button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Mobile Top Header -->
    <header v-if="!isPublic" class="mobile-header">
      <router-link to="/" class="logo">
        <img src="/icons/android-chrome-192x192.png" alt="Collectabase Logo" class="logo-img" />
        Collectabase
      </router-link>
      <div class="mobile-header-actions">
        <select v-if="collections.length > 1" class="mobile-collection" :value="activeCollectionId" @change="onCollectionChange">
          <option v-for="c in collections" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <router-link to="/add" class="btn btn-primary btn-compact">+ Add</router-link>
      </div>
    </header>

    <main class="main-content">
      <router-view />
    </main>

    <!-- Mobile-only bottom navigation -->
    <nav v-if="!isPublic" class="mobile-nav" aria-label="Main navigation">
      <router-link to="/" active-class="" exact-active-class="nav-active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
        <span>Library</span>
      </router-link>

      <router-link to="/stats" active-class="nav-active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <line x1="18" y1="20" x2="18" y2="10"/>
          <line x1="12" y1="20" x2="12" y2="4"/>
          <line x1="6" y1="20" x2="6" y2="14"/>
        </svg>
        <span>Stats</span>
      </router-link>

      <router-link to="/wishlist" active-class="nav-active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        <span>Wishlist</span>
      </router-link>

      <router-link to="/lots" active-class="nav-active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
        <span>Lots</span>
      </router-link>

      <button type="button" class="mobile-menu-btn" :class="{ 'nav-active': mobileMenuOpen }" @click="mobileMenuOpen = true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="1.5"/>
          <circle cx="19" cy="12" r="1.5"/>
          <circle cx="5" cy="12" r="1.5"/>
        </svg>
        <span>Menu</span>
      </button>
    </nav>

    <!-- Mobile overflow sheet (secondary destinations) -->
    <div v-if="!isPublic && mobileMenuOpen" class="mobile-sheet-backdrop" @click="mobileMenuOpen = false">
      <div class="mobile-sheet" @click.stop>
        <div class="sheet-handle"></div>
        <router-link to="/prices" class="sheet-item" @click="mobileMenuOpen = false">💰 Prices</router-link>
        <router-link to="/import" class="sheet-item" @click="mobileMenuOpen = false">🧾 Import / Export</router-link>
        <router-link to="/collections" class="sheet-item" @click="mobileMenuOpen = false">🗂️ Manage collections</router-link>
        <router-link to="/account" class="sheet-item" @click="mobileMenuOpen = false">👤 Account</router-link>
        <router-link v-if="auth.isSuperAdmin" to="/more" class="sheet-item" @click="mobileMenuOpen = false">⚙️ More (admin)</router-link>
        <button class="sheet-item danger" @click="logout">🚪 Log out</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import NotificationStack from './components/NotificationStack.vue'
import { useAuthStore } from './stores/auth'

const collapsed = ref(false)
const userMenuOpen = ref(false)
const mobileMenuOpen = ref(false)
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { user, collections, activeCollectionId } = storeToRefs(auth)

// On /login (and any future public route) we render only the page, no app chrome.
const isPublic = computed(() => !!route.meta.public)

onMounted(() => {
  const saved = localStorage.getItem('collectabase_sidebar_collapsed')
  if (saved === 'true') {
    collapsed.value = true
  }
})

function toggleSidebar() {
  collapsed.value = !collapsed.value
  localStorage.setItem('collectabase_sidebar_collapsed', String(collapsed.value))
}

function onCollectionChange(event) {
  auth.setActiveCollection(event.target.value)
  // Reload so every view refetches scoped to the newly active collection.
  window.location.reload()
}

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
/* ── Desktop Layout ── */
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

.desktop-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-light);
  border-right: 1px solid var(--glass-border);
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 1.5rem;
  z-index: 100;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), padding 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.desktop-sidebar.collapsed {
  width: 80px;
  padding: 1.5rem 0.75rem;
}

.sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2.5rem;
}

.desktop-sidebar.collapsed .sidebar-top {
  flex-direction: column;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

.collapse-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem;
  border-radius: 0.35rem;
  transition: color 0.2s, background 0.2s;
}

.collapse-btn:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.1);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
}

.logo-img {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  object-fit: contain;
  box-shadow: 0 2px 10px rgba(139, 92, 246, 0.2);
  flex-shrink: 0;
}

.logo-text {
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -0.03em;
  white-space: nowrap;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}

.sidebar-nav a {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border-radius: 0.75rem;
  color: var(--text-muted);
  text-decoration: none;
  font-weight: 600;
  font-size: 1rem;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  white-space: nowrap;
}

.desktop-sidebar.collapsed .sidebar-nav a {
  justify-content: center;
  padding: 0.875rem 0;
}

.sidebar-nav a:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
}

.sidebar-nav a.active,
.sidebar-nav a.router-link-active {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));
  border-color: rgba(139, 92, 246, 0.3);
  color: var(--primary);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.nav-icon {
  font-size: 1.25rem;
  opacity: 0.8;
  flex-shrink: 0;
  display: inline-flex;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 1.5rem;
}

.collection-switcher {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.9rem;
}
.collection-switcher label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}
.collection-switcher select,
.mobile-collection {
  width: 100%;
  padding: 0.5rem 0.6rem;
  border-radius: 0.6rem;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--glass-border);
  font-size: 0.9rem;
}
.user-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-top: 0.9rem;
  padding-top: 0.9rem;
  border-top: 1px solid var(--glass-border);
}
.user-email {
  font-size: 0.8rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.logout-btn {
  flex-shrink: 0;
  background: transparent;
  border: 1px solid var(--glass-border);
  color: var(--text-muted);
  padding: 0.35rem 0.6rem;
  border-radius: 0.5rem;
  font-size: 0.78rem;
  cursor: pointer;
}
.logout-btn:hover { color: var(--text); }

.manage-collections-link {
  display: inline-block;
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  text-decoration: none;
}
.manage-collections-link:hover { color: var(--primary); }

.user-menu { position: relative; margin-top: 0.9rem; padding-top: 0.9rem; border-top: 1px solid var(--glass-border); }
.user-trigger {
  display: flex; align-items: center; gap: 0.55rem; width: 100%;
  background: transparent; border: 1px solid var(--glass-border); color: var(--text);
  padding: 0.5rem 0.6rem; border-radius: 0.6rem; cursor: pointer;
}
.user-menu.collapsed .user-trigger { justify-content: center; padding: 0.5rem 0; }
.user-avatar {
  flex-shrink: 0; width: 28px; height: 28px; border-radius: 50%;
  background: var(--primary, #8b5cf6); color: #fff; font-weight: 700; font-size: 0.85rem;
  display: inline-flex; align-items: center; justify-content: center;
}
.user-trigger-name { flex: 1; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.85rem; }
.user-caret { color: var(--text-muted); }
.user-dropdown {
  position: absolute; bottom: calc(100% + 6px); left: 0; right: 0;
  background: var(--bg-light); border: 1px solid var(--glass-border);
  border-radius: 0.6rem; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.35); z-index: 200;
}
.user-dropdown-item {
  display: block; width: 100%; text-align: left; background: transparent; border: none;
  color: var(--text); padding: 0.6rem 0.8rem; font-size: 0.85rem; cursor: pointer; text-decoration: none;
}
.user-dropdown-item:hover { background: rgba(255,255,255,0.06); }
.mobile-header-actions { display: flex; align-items: center; gap: 0.5rem; }
.mobile-collection { width: auto; max-width: 40vw; }

.add-btn {
  width: 100%;
  justify-content: center;
  font-size: 1.05rem;
  padding: 0.875rem;
  box-shadow: 0 4px 15px rgba(139, 92, 246, 0.25);
  white-space: nowrap;
  overflow: hidden;
}

.desktop-sidebar.collapsed .add-btn {
  padding: 0.875rem 0;
}

.main-content {
  flex: 1;
  min-width: 0; /* Prevents flex children from overflowing */
  display: flex;
  flex-direction: column;
}

/* ── Mobile Layout ── */
.mobile-header {
  display: none;
}

.mobile-nav {
  display: none;
}

.btn-active {
  opacity: 1 !important;
}

/* ── Responsive breakpoints ── */
@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }

  .desktop-sidebar {
    display: none;
  }

  .mobile-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: max(0.875rem, env(safe-area-inset-top)) 1.25rem 0.875rem;
    background: var(--bg-light);
    border-bottom: 1px solid var(--glass-border);
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: var(--card-blur);
    -webkit-backdrop-filter: var(--card-blur);
  }

  .mobile-header .logo {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--text);
    text-decoration: none;
  }

  .mobile-header .logo-img {
    width: 24px;
    height: 24px;
    box-shadow: none;
  }

  .main-content {
    padding-bottom: calc(64px + env(safe-area-inset-bottom));
  }

  .mobile-nav {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 64px;
    background: rgba(9, 9, 11, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-top: 1px solid var(--glass-border);
    z-index: 100;
    padding-bottom: max(0px, env(safe-area-inset-bottom));
    box-shadow: 0 -4px 30px rgba(0, 0, 0, 0.2);
  }

  .mobile-nav a,
  .mobile-nav .mobile-menu-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.65rem;
    font-weight: 500;
    gap: 0.25rem;
    transition: color 0.2s;
    -webkit-tap-highlight-color: transparent;
    background: none;
    border: none;
    cursor: pointer;
    font-family: inherit;
  }

  .mobile-nav a svg,
  .mobile-nav .mobile-menu-btn svg {
    width: 24px;
    height: 24px;
    stroke-width: 2.2;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .mobile-nav a.nav-active,
  .mobile-nav .mobile-menu-btn.nav-active {
    color: var(--primary);
  }

  .mobile-nav a.nav-active svg {
    transform: scale(1.15);
  }
}

/* Mobile overflow sheet — rendered only when opened from the mobile menu button */
.mobile-sheet-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 200;
  display: flex;
  align-items: flex-end;
}
.mobile-sheet {
  width: 100%;
  background: var(--bg-light);
  border-top-left-radius: 1rem;
  border-top-right-radius: 1rem;
  border-top: 1px solid var(--glass-border);
  padding: 0.5rem 0.75rem calc(1rem + env(safe-area-inset-bottom));
  box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.4);
}
.sheet-handle {
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--glass-border);
  margin: 0.5rem auto 0.75rem;
}
.sheet-item {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  font-family: inherit;
  color: var(--text);
  text-decoration: none;
  font-size: 1rem;
  padding: 0.85rem 0.75rem;
  border-radius: 0.6rem;
  cursor: pointer;
}
.sheet-item:hover { background: rgba(255, 255, 255, 0.06); }
.sheet-item.danger { color: #ff6b6b; }
</style>
