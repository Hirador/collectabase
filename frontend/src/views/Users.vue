<template>
  <div class="users-view">
    <h1>Users</h1>
    <p class="subtitle">Create accounts and manage access. (Super admin only.)</p>

    <div class="user-table">
      <div class="row head">
        <span class="c-name">User</span>
        <span class="c-role">Role</span>
        <span class="c-mfa">MFA</span>
        <span class="c-status">Status</span>
        <span class="c-actions"></span>
      </div>
      <div v-for="u in users" :key="u.id" class="row">
        <span class="c-name">
          <strong>{{ u.display_name || u.email }}</strong>
          <small v-if="u.display_name">{{ u.email }}</small>
        </span>
        <span class="c-role">
          <span class="pill" :class="{ admin: u.is_super_admin }">{{ u.is_super_admin ? 'Super admin' : 'User' }}</span>
        </span>
        <span class="c-mfa">
          <span v-if="u.mfa_enabled" class="pill ok">On</span>
          <span v-else-if="u.mfa_required" class="pill warn">Required</span>
          <span v-else class="pill">Off</span>
        </span>
        <span class="c-status">
          <span class="pill" :class="u.is_active ? 'ok' : 'off'">{{ u.is_active ? 'Active' : 'Disabled' }}</span>
        </span>
        <span class="c-actions">
          <template v-if="u.id !== auth.user?.id">
            <label class="enforce" :title="u.is_super_admin ? 'Super admins always require MFA' : 'Require this user to set up MFA'">
              <input type="checkbox" :checked="u.is_super_admin || u.mfa_required" :disabled="u.is_super_admin"
                     @change="(e) => setMfaRequired(u, e.target.checked)" /> Enforce MFA
            </label>
            <button class="mini" @click="toggleActive(u)">{{ u.is_active ? 'Disable' : 'Enable' }}</button>
            <button class="mini danger" @click="removeUser(u)">Delete</button>
          </template>
          <span v-else class="muted">you</span>
        </span>
      </div>
    </div>

    <div class="create">
      <h2>Create user</h2>
      <div class="create-grid">
        <input v-model="newUser.display_name" placeholder="Name" />
        <input v-model="newUser.email" type="email" placeholder="Email" />
        <input v-model="newUser.password" type="password" placeholder="Password (min 8)" />
        <label class="chk"><input type="checkbox" v-model="newUser.is_super_admin" /> Super admin</label>
        <label class="chk"><input type="checkbox" v-model="newUser.mfa_required" :disabled="newUser.is_super_admin" /> Require MFA</label>
        <button class="btn-primary" :disabled="busy" @click="createUser">Create</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const users = ref([])
const busy = ref(false)
const error = ref('')
const newUser = reactive({ display_name: '', email: '', password: '', is_super_admin: false, mfa_required: false })

async function load() {
  const { ok, data } = await apiGet('/api/users')
  if (ok) users.value = data.users
}

async function createUser() {
  busy.value = true; error.value = ''
  const { ok, data } = await apiPost('/api/users', { ...newUser, email: newUser.email.trim() })
  busy.value = false
  if (ok) {
    Object.assign(newUser, { display_name: '', email: '', password: '', is_super_admin: false, mfa_required: false })
    load()
  } else {
    error.value = data?.detail?.message || 'Could not create user.'
  }
}

async function setMfaRequired(u, value) {
  await apiPatch(`/api/users/${u.id}`, { mfa_required: value })
  load()
}

async function toggleActive(u) {
  const { ok, data } = await apiPatch(`/api/users/${u.id}`, { is_active: !u.is_active })
  if (!ok) error.value = data?.detail?.message || 'Could not update user.'
  load()
}

async function removeUser(u) {
  if (!confirm(`Delete ${u.email}? This cannot be undone.`)) return
  const { ok, data } = await apiDelete(`/api/users/${u.id}`)
  if (!ok) error.value = data?.detail?.message || 'Could not delete user.'
  load()
}

onMounted(load)
</script>

<style scoped>
.users-view { max-width: 820px; margin: 0 auto; padding: 1.5rem; }
h1 { margin-bottom: 0.25rem; }
.subtitle { color: var(--text-muted); margin-top: 0; }
.user-table { border: 1px solid var(--glass-border); border-radius: 0.9rem; overflow: hidden; }
.row { display: grid; grid-template-columns: 2fr 1fr 0.8fr 1fr 2.4fr; align-items: center; gap: 0.5rem; padding: 0.7rem 0.9rem; border-bottom: 1px solid var(--glass-border); }
.row:last-child { border-bottom: none; }
.row.head { background: rgba(255,255,255,0.04); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); }
.c-name { display: flex; flex-direction: column; }
.c-name small { color: var(--text-muted); font-size: 0.75rem; }
.c-actions { display: flex; align-items: center; gap: 0.5rem; justify-content: flex-end; flex-wrap: wrap; }
.pill { padding: 0.12rem 0.5rem; border-radius: 0.5rem; font-size: 0.74rem; background: rgba(255,255,255,0.08); color: var(--text-muted); }
.pill.admin { background: rgba(139,92,246,0.18); color: var(--primary); }
.pill.ok { background: rgba(74,222,128,0.16); color: #4ade80; }
.pill.warn { background: rgba(251,191,36,0.16); color: #fbbf24; }
.pill.off { background: rgba(255,107,107,0.14); color: #ff6b6b; }
.enforce { display: flex; align-items: center; gap: 0.3rem; font-size: 0.76rem; color: var(--text-muted); }
.muted { color: var(--text-muted); font-size: 0.8rem; }
.create { margin-top: 1.5rem; background: var(--bg-light); border: 1px solid var(--glass-border); border-radius: 0.9rem; padding: 1.1rem; }
.create h2 { margin-top: 0; font-size: 1.05rem; }
.create-grid { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
input { padding: 0.5rem 0.65rem; border-radius: 0.6rem; border: 1px solid var(--glass-border); background: var(--bg); color: var(--text); }
.chk { display: flex; align-items: center; gap: 0.3rem; color: var(--text-muted); font-size: 0.85rem; }
.btn-primary { background: var(--primary, #8b5cf6); color: #fff; border: none; padding: 0.55rem 0.9rem; border-radius: 0.6rem; cursor: pointer; }
.btn-primary[disabled] { opacity: 0.5; }
.mini { background: transparent; border: 1px solid var(--glass-border); color: var(--text-muted); padding: 0.3rem 0.6rem; border-radius: 0.5rem; cursor: pointer; font-size: 0.78rem; }
.mini.danger { color: #ff6b6b; border-color: rgba(255,107,107,0.4); }
.error { color: #ff6b6b; margin-top: 0.5rem; }
@media (max-width: 640px) {
  .row { grid-template-columns: 1fr 1fr; }
  .c-actions { grid-column: 1 / -1; justify-content: flex-start; }
}
</style>
