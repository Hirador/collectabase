<template>
  <div class="admin-view">
    <h1>Users & Sharing</h1>

    <!-- USER MANAGEMENT (super admin only) -->
    <section v-if="auth.isSuperAdmin" class="panel">
      <h2>Users</h2>
      <table class="grid">
        <thead>
          <tr><th>Email</th><th>Name</th><th>Role</th><th>2FA</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.email }}</td>
            <td>{{ u.display_name || '—' }}</td>
            <td>{{ u.is_super_admin ? 'Super admin' : 'User' }}</td>
            <td>{{ u.mfa_enabled ? '🔐' : '—' }}</td>
            <td>{{ u.is_active ? 'Active' : 'Disabled' }}</td>
            <td class="actions">
              <button v-if="u.id !== auth.user?.id" class="mini" @click="toggleActive(u)">
                {{ u.is_active ? 'Disable' : 'Enable' }}
              </button>
              <button v-if="u.id !== auth.user?.id" class="mini danger" @click="removeUser(u)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>

      <h3>Create user</h3>
      <div class="form-row">
        <input v-model="newUser.display_name" placeholder="Name" />
        <input v-model="newUser.email" type="email" placeholder="Email" />
        <input v-model="newUser.password" type="password" placeholder="Password (min 8)" />
        <label class="chk"><input type="checkbox" v-model="newUser.is_super_admin" /> Super admin</label>
        <button class="btn-primary" :disabled="busy" @click="createUser">Create</button>
      </div>
      <p v-if="userError" class="error">{{ userError }}</p>
    </section>

    <!-- COLLECTIONS & SHARING -->
    <section class="panel">
      <h2>Collections</h2>
      <div class="form-row">
        <input v-model="newCollectionName" placeholder="New collection name" />
        <button class="btn-primary" :disabled="busy" @click="createCollection">Create collection</button>
      </div>

      <div v-for="c in collections" :key="c.id" class="collection-block">
        <div class="collection-head">
          <strong>{{ c.name }}</strong>
          <span class="badge">{{ c.role }}</span>
          <span class="muted">{{ c.item_count }} items · {{ c.member_count }} members</span>
        </div>

        <div v-if="canManage(c)" class="members">
          <div v-for="m in (members[c.id] || [])" :key="m.user_id" class="member">
            <span>{{ m.display_name || m.email }}</span>
            <select :value="m.role" @change="(e) => changeRole(c, m, e.target.value)"
                    :disabled="m.user_id === c.owner_user_id">
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
              <option value="owner">Owner</option>
            </select>
            <button v-if="m.user_id !== c.owner_user_id" class="mini danger" @click="removeMember(c, m)">Remove</button>
          </div>
          <div class="form-row">
            <input v-model="invite[c.id]" type="email" placeholder="Add member by email" />
            <select v-model="inviteRole[c.id]">
              <option value="viewer">Viewer</option>
              <option value="editor" selected>Editor</option>
              <option value="owner">Owner</option>
            </select>
            <button class="btn-secondary" @click="addMember(c)">Add</button>
          </div>
        </div>
        <p v-else class="muted">You need owner access to manage members.</p>
      </div>
      <p v-if="shareError" class="error">{{ shareError }}</p>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const busy = ref(false)
const users = ref([])
const collections = ref([])
const members = reactive({})
const invite = reactive({})
const inviteRole = reactive({})
const newUser = reactive({ display_name: '', email: '', password: '', is_super_admin: false })
const newCollectionName = ref('')
const userError = ref('')
const shareError = ref('')

function canManage(c) {
  return auth.isSuperAdmin || c.is_owner || c.role === 'owner'
}

async function loadUsers() {
  if (!auth.isSuperAdmin) return
  const { ok, data } = await apiGet('/api/users')
  if (ok) users.value = data.users
}

async function loadCollections() {
  const { ok, data } = await apiGet('/api/collections')
  if (!ok) return
  collections.value = data.collections
  for (const c of data.collections) {
    if (canManage(c)) loadMembers(c.id)
  }
}

async function loadMembers(cid) {
  const { ok, data } = await apiGet(`/api/collections/${cid}/members`)
  if (ok) members[cid] = data.members
}

async function createUser() {
  busy.value = true; userError.value = ''
  const { ok, data } = await apiPost('/api/users', { ...newUser, email: newUser.email.trim() })
  busy.value = false
  if (ok) {
    Object.assign(newUser, { display_name: '', email: '', password: '', is_super_admin: false })
    loadUsers()
  } else {
    userError.value = data?.detail?.message || 'Could not create user.'
  }
}

async function toggleActive(u) {
  await apiPatch(`/api/users/${u.id}`, { is_active: !u.is_active })
  loadUsers()
}

async function removeUser(u) {
  if (!confirm(`Delete ${u.email}? This cannot be undone.`)) return
  const { ok, data } = await apiDelete(`/api/users/${u.id}`)
  if (!ok) userError.value = data?.detail?.message || 'Could not delete user.'
  loadUsers()
}

async function createCollection() {
  if (!newCollectionName.value.trim()) return
  busy.value = true; shareError.value = ''
  await apiPost('/api/collections', { name: newCollectionName.value.trim() })
  busy.value = false
  newCollectionName.value = ''
  await auth.refreshCollections()
  loadCollections()
}

async function addMember(c) {
  shareError.value = ''
  const email = (invite[c.id] || '').trim()
  if (!email) return
  const { ok, data } = await apiPost(`/api/collections/${c.id}/members`, {
    email, role: inviteRole[c.id] || 'editor',
  })
  if (ok) { invite[c.id] = ''; loadMembers(c.id); loadCollections() }
  else shareError.value = data?.detail?.message || 'Could not add member.'
}

async function changeRole(c, m, role) {
  await apiPatch(`/api/collections/${c.id}/members/${m.user_id}`, { role })
  loadMembers(c.id)
}

async function removeMember(c, m) {
  await apiDelete(`/api/collections/${c.id}/members/${m.user_id}`)
  loadMembers(c.id); loadCollections()
}

onMounted(() => { loadUsers(); loadCollections() })
</script>

<style scoped>
.admin-view { max-width: 820px; margin: 0 auto; padding: 1.5rem; }
.panel { background: var(--bg-light); border: 1px solid var(--glass-border); border-radius: 0.9rem; padding: 1.25rem; margin-bottom: 1.25rem; }
.panel h2 { margin-top: 0; }
.grid { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.grid th, .grid td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--glass-border); }
.actions { display: flex; gap: 0.4rem; }
.form-row { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-top: 0.75rem; }
input, select { padding: 0.5rem 0.6rem; border-radius: 0.6rem; border: 1px solid var(--glass-border); background: var(--bg); color: var(--text); }
.chk { display: flex; align-items: center; gap: 0.3rem; color: var(--text-muted); font-size: 0.85rem; }
.collection-block { border-top: 1px solid var(--glass-border); padding-top: 0.9rem; margin-top: 0.9rem; }
.collection-head { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.badge { background: rgba(139,92,246,0.15); color: var(--primary); padding: 0.1rem 0.5rem; border-radius: 0.5rem; font-size: 0.75rem; }
.muted { color: var(--text-muted); font-size: 0.85rem; }
.members { margin-top: 0.6rem; display: flex; flex-direction: column; gap: 0.5rem; }
.member { display: flex; align-items: center; gap: 0.5rem; }
.member span { flex: 1; }
.btn-primary { background: var(--primary, #8b5cf6); color: #fff; border: none; padding: 0.55rem 0.9rem; border-radius: 0.6rem; cursor: pointer; }
.btn-secondary { background: transparent; border: 1px solid var(--glass-border); color: var(--text); padding: 0.5rem 0.9rem; border-radius: 0.6rem; cursor: pointer; }
.mini { background: transparent; border: 1px solid var(--glass-border); color: var(--text-muted); padding: 0.3rem 0.55rem; border-radius: 0.5rem; cursor: pointer; font-size: 0.78rem; }
.mini.danger { color: #ff6b6b; border-color: rgba(255,107,107,0.4); }
.error { color: #ff6b6b; margin-top: 0.5rem; }
</style>
