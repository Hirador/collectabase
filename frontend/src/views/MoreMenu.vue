<template>
  <div class="container">
    <h1 class="mb-3">More</h1>
    <p class="more-intro">Collection tools and admin actions.</p>

    <div class="more-section">
      <h2 class="more-section-title">Collection</h2>
      <div class="more-grid">
        <router-link to="/add" class="more-card">
          <div class="more-icon">➕</div>
          <div class="more-copy">
            <div class="more-title">Add Game</div>
            <div class="more-sub">Create a new entry</div>
          </div>
        </router-link>

        <router-link to="/wishlist" class="more-card">
          <div class="more-icon">⭐</div>
          <div class="more-copy">
            <div class="more-title">Wishlist</div>
            <div class="more-sub">Track wanted games</div>
          </div>
        </router-link>

        <router-link to="/lots" class="more-card">
          <div class="more-icon">📦</div>
          <div class="more-copy">
            <div class="more-title">Lots & Resale</div>
            <div class="more-sub">Bundle cost basis and sales</div>
          </div>
        </router-link>
      </div>
    </div>

    <div class="more-section">
      <h2 class="more-section-title">Game Database</h2>
      <div class="catalog-card">
        <div class="catalog-head">
          <div class="more-icon">📀</div>
          <div>
            <div class="more-title">Serial Catalog</div>
            <div class="more-sub">Redump · No-Intro · GameDB — for serial &amp; region lookup</div>
          </div>
        </div>

        <div class="catalog-status">
          <template v-if="loadingStatus">Loading…</template>
          <template v-else-if="status">
            <strong>{{ (status.total_entries || 0).toLocaleString() }}</strong> entries ·
            {{ status.systems.length }} systems · last updated {{ lastUpdated }}
          </template>
          <template v-else>Status unavailable.</template>
        </div>

        <div v-if="isRunning" class="catalog-progress">
          <div class="catalog-bar"><div class="catalog-bar-fill" :style="{ width: progressPct + '%' }"></div></div>
          <span class="catalog-progress-text">Updating… {{ job?.progress || 0 }}/{{ job?.total || 0 }} systems</span>
        </div>
        <p v-else-if="job && job.state === 'done'" class="catalog-done">
          ✓ Done — {{ job.success }} system(s) updated{{ job.failed ? `, ${job.failed} failed` : '' }}.
        </p>
        <p v-if="errorMsg" class="catalog-error">{{ errorMsg }}</p>

        <div class="catalog-actions">
          <button class="btn btn-primary" :disabled="isRunning" @click="startUpdate">
            {{ isRunning ? 'Updating…' : 'Update catalog' }}
          </button>
        </div>
        <p class="catalog-note">
          Downloads the latest DAT files and imports only what changed. The first run can take several minutes.
        </p>
      </div>
    </div>

    <div class="more-section">
      <h2 class="more-section-title">Data & Admin</h2>
      <div class="more-grid">
        <router-link to="/import" class="more-card">
          <div class="more-icon">🧾</div>
          <div class="more-copy">
            <div class="more-title">Import / Export</div>
            <div class="more-sub">CSV and CLZ tools</div>
          </div>
        </router-link>

        <router-link to="/settings" class="more-card">
          <div class="more-icon">⚙️</div>
          <div class="more-copy">
            <div class="more-title">Settings</div>
            <div class="more-sub">System, jobs, cleanup</div>
          </div>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { catalogApi, jobsApi } from '../api'

const status = ref(null)
const loadingStatus = ref(true)
const job = ref(null)
const updating = ref(false)
const errorMsg = ref('')
let pollTimer = null

const isRunning = computed(() => updating.value || job.value?.state === 'running')

const lastUpdated = computed(() => {
  const ts = status.value?.last_update_at
  if (!ts) return 'never'
  try { return new Date(ts).toLocaleString() } catch { return ts }
})

const progressPct = computed(() => {
  const j = job.value
  if (!j || !j.total) return 0
  return Math.min(100, Math.round((j.progress / j.total) * 100))
})

async function loadStatus() {
  loadingStatus.value = true
  try {
    const res = await catalogApi.status()
    if (res.ok) status.value = res.data
  } finally {
    loadingStatus.value = false
  }
}

async function startUpdate() {
  errorMsg.value = ''
  job.value = null
  updating.value = true
  try {
    const res = await catalogApi.update(false)
    if (!res.ok) {
      errorMsg.value = res.data?.detail?.message || res.data?.detail || 'Failed to start update.'
      updating.value = false
      return
    }
    job.value = { state: 'running', progress: 0, total: res.data.total }
    pollJob(res.data.job_id)
  } catch (e) {
    errorMsg.value = 'Failed to start update.'
    updating.value = false
  }
}

function pollJob(jobId) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    const res = await jobsApi.get(jobId)
    if (!res.ok || !res.data) return
    job.value = res.data
    if (res.data.state !== 'running') {
      clearInterval(pollTimer)
      pollTimer = null
      updating.value = false
      if (res.data.state === 'error') errorMsg.value = res.data.error || 'Update failed.'
      await loadStatus()
    }
  }, 2000)
}

onMounted(loadStatus)
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.more-intro {
  margin: -0.5rem 0 1rem;
  color: var(--text-muted);
  max-width: 560px;
}

.more-section + .more-section {
  margin-top: 1rem;
}

.more-section-title {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin: 0 0 0.45rem;
}

.catalog-card {
  background: var(--bg-light);
  border: 1px solid var(--glass-border);
  border-radius: 1rem;
  padding: 1.1rem 1.25rem;
  backdrop-filter: var(--card-blur);
  -webkit-backdrop-filter: var(--card-blur);
  box-shadow: var(--glass-shadow);
}

.catalog-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.catalog-status {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.catalog-progress {
  margin-top: 0.75rem;
}

.catalog-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--glass-border);
  overflow: hidden;
}

.catalog-bar-fill {
  height: 100%;
  background: var(--primary, #6366f1);
  transition: width 0.4s ease;
}

.catalog-progress-text {
  display: inline-block;
  margin-top: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.catalog-done {
  margin: 0.6rem 0 0;
  font-size: 0.85rem;
  color: #34d399;
}

.catalog-error {
  margin: 0.6rem 0 0;
  font-size: 0.85rem;
  color: #f87171;
}

.catalog-actions {
  margin-top: 0.9rem;
}

.catalog-note {
  margin: 0.7rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.more-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
}

.more-card {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  background: var(--bg-light);
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.8rem 0.9rem;
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.18s ease, transform 0.18s ease;
}

.more-card:hover {
  border-color: var(--primary);
  transform: translateY(-1px);
}

.more-icon {
  width: 1.9rem;
  height: 1.9rem;
  border-radius: 0.45rem;
  background: var(--bg);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.more-copy {
  min-width: 0;
}

.more-title {
  font-weight: 700;
}

.more-sub {
  margin-top: 0.2rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}
</style>
