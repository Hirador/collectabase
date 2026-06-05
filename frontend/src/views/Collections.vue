<template>
  <div class="collections-view">
    <h1>Collections &amp; Sharing</h1>
    <p class="subtitle">Create collections and share them with other users.</p>

    <div class="create-row">
      <input v-model="newName" placeholder="New collection name" @keyup.enter="createCollection" />
      <button class="btn-primary" :disabled="busy || !newName.trim()" @click="createCollection">+ Add collection</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-for="c in collections" :key="c.id" class="collection-card">
      <div class="collection-head">
        <div class="collection-title">
          <strong>{{ c.name }}</strong>
          <span class="badge" :class="c.role">{{ c.role }}</span>
          <span v-if="c.id === auth.activeCollectionId" class="badge active">active</span>
        </div>
        <div class="collection-meta">{{ c.item_count }} items · {{ c.member_count }} members</div>
      </div>

      <div class="collection-actions">
        <button v-if="c.id !== auth.activeCollectionId" class="mini" @click="makeActive(c)">Switch to</button>
        <button v-if="canManage(c)" class="mini" @click="rename(c)">Rename</button>
        <button v-if="canManage(c) && collections.length > 1" class="mini danger" @click="remove(c)">Delete</button>
      </div>

      <!-- members -->
      <div v-if="canManage(c)" class="members">
        <div class="members-label">Members</div>
        <div v-for="m in (members[c.id] || [])" :key="m.user_id" class="member">
          <span class="member-name">{{ m.display_name || m.email }}</span>
          <select :value="m.role" @change="(e) => changeRole(c, m, e.target.value)"
                  :disabled="m.user_id === c.owner_user_id">
            <option value="viewer">Viewer</option>
            <option value="editor">Editor</option>
            <option value="owner">Owner</option>
          </select>
          <button v-if="m.user_id !== c.owner_user_id" class="mini danger" @click="removeMember(c, m)">Remove</button>
          <span v-else class="owner-tag">owner</span>
        </div>
        <div class="add-member">
          <input v-model="invite[c.id]" type="email" placeholder="Add member by email" />
          <select v-model="inviteRole[c.id]">
            <option value="viewer">Viewer</option>
            <option value="editor">Editor</option>
            <option value="owner">Owner</option>
          </select>
          <button class="btn-secondary" @click="addMember(c)">Add</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const busy = ref(false)
const error = ref('')
const collections = ref([])
const members = reactive({})
const invite = reactive({})
const inviteRole = reactive({})
const newName = ref('')

function canManage(c) {
  return auth.isSuperAdmin || c.is_owner || c.role === 'owner'
}

async function load() {
  const { ok, data } = await apiGet('/api/collections')
  if (!ok) return
  collections.value = data.collections
  for (const c of data.collections) {
    if (!inviteRole[c.id]) inviteRole[c.id] = 'editor'
    if (canManage(c)) loadMembers(c.id)
  }
}

async function loadMembers(cid) {
  const { ok, data } = await apiGet(`/api/collections/${cid}/members`)
  if (ok) members[cid] = data.members
}

async function createCollection() {
  if (!newName.value.trim()) return
  busy.value = true; error.value = ''
  const { ok, data } = await apiPost('/api/collections', { name: newName.value.trim() })
  busy.value = false
  if (ok) { newName.value = ''; await auth.refreshCollections(); load() }
  else error.value = data?.detail?.message || 'Could not create collection.'
}

async function rename(c) {
  const name = prompt('Rename collection', c.name)
  if (!name || !name.trim()) return
  await apiPatch(`/api/collections/${c.id}`, { name: name.trim() })
  await auth.refreshCollections(); load()
}

async function remove(c) {
  if (!confirm(`Delete "${c.name}" and everything in it? This cannot be undone.`)) return
  error.value = ''
  const { ok, data } = await apiDelete(`/api/collections/${c.id}`)
  if (!ok) { error.value = data?.detail?.message || 'Could not delete collection.'; return }
  await auth.refreshCollections()
  // If we deleted the active one, the store re-syncs to another; reload to refresh views.
  window.location.reload()
}

function makeActive(c) {
  auth.setActiveCollection(c.id)
  window.location.reload()
}

async function addMember(c) {
  error.value = ''
  const email = (invite[c.id] || '').trim()
  if (!email) return
  const { ok, data } = await apiPost(`/api/collections/${c.id}/members`, { email, role: inviteRole[c.id] || 'editor' })
  if (ok) { invite[c.id] = ''; loadMembers(c.id); load() }
  else error.value = data?.detail?.message || 'Could not add member.'
}

async function changeRole(c, m, role) {
  await apiPatch(`/api/collections/${c.id}/members/${m.user_id}`, { role })
  loadMembers(c.id)
}

async function removeMember(c, m) {
  await apiDelete(`/api/collections/${c.id}/members/${m.user_id}`)
  loadMembers(c.id); load()
}

onMounted(load)
</script>

<style scoped>
.collections-view { max-width: 760px; margin: 0 auto; padding: 1.5rem; }
h1 { margin-bottom: 0.25rem; }
.subtitle { color: var(--text-muted); margin-top: 0; }
.create-row { display: flex; gap: 0.5rem; margin: 1rem 0; }
.create-row input { flex: 1; }
input, select { padding: 0.55rem 0.7rem; border-radius: 0.6rem; border: 1px solid var(--glass-border); background: var(--bg); color: var(--text); }
.collection-card { background: var(--bg-light); border: 1px solid var(--glass-border); border-radius: 0.9rem; padding: 1.1rem; margin-bottom: 1rem; }
.collection-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; flex-wrap: wrap; }
.collection-title { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.collection-meta { color: var(--text-muted); font-size: 0.82rem; }
.badge { padding: 0.1rem 0.5rem; border-radius: 0.5rem; font-size: 0.72rem; text-transform: capitalize; background: rgba(255,255,255,0.08); color: var(--text-muted); }
.badge.owner { background: rgba(139,92,246,0.18); color: var(--primary); }
.badge.active { background: rgba(74,222,128,0.18); color: #4ade80; }
.collection-actions { display: flex; gap: 0.4rem; margin-top: 0.7rem; flex-wrap: wrap; }
.members { margin-top: 0.9rem; padding-top: 0.8rem; border-top: 1px solid var(--glass-border); }
.members-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin-bottom: 0.5rem; }
.member { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.45rem; }
.member-name { flex: 1; font-size: 0.9rem; }
.owner-tag { font-size: 0.72rem; color: var(--text-muted); }
.add-member { display: flex; gap: 0.5rem; margin-top: 0.6rem; flex-wrap: wrap; }
.add-member input { flex: 1; min-width: 160px; }
.btn-primary { background: var(--primary, #8b5cf6); color: #fff; border: none; padding: 0.55rem 0.9rem; border-radius: 0.6rem; cursor: pointer; }
.btn-primary[disabled] { opacity: 0.5; cursor: default; }
.btn-secondary { background: transparent; border: 1px solid var(--glass-border); color: var(--text); padding: 0.5rem 0.9rem; border-radius: 0.6rem; cursor: pointer; }
.mini { background: transparent; border: 1px solid var(--glass-border); color: var(--text-muted); padding: 0.3rem 0.6rem; border-radius: 0.5rem; cursor: pointer; font-size: 0.78rem; }
.mini.danger { color: #ff6b6b; border-color: rgba(255,107,107,0.4); }
.error { color: #ff6b6b; }
</style>
