<template>
  <div class="auth-screen">
    <div class="auth-card">
      <div class="auth-brand">
        <h1>Collectabase</h1>
        <p v-if="mode === 'bootstrap'">Create your super-admin account to get started.</p>
        <p v-else>Sign in to your collection.</p>
      </div>

      <!-- First-run: create super admin -->
      <form v-if="mode === 'bootstrap'" @submit.prevent="doBootstrap" class="auth-form">
        <label>Display name
          <input v-model="form.display_name" type="text" autocomplete="name" placeholder="Your name" />
        </label>
        <label>Email
          <input v-model="form.email" type="email" autocomplete="email" required />
        </label>
        <label>Password
          <input v-model="form.password" type="password" autocomplete="new-password" required minlength="8" />
          <small>At least 8 characters.</small>
        </label>
        <p v-if="error" class="auth-error">{{ error }}</p>
        <button type="submit" :disabled="busy">{{ busy ? 'Creating…' : 'Create super admin' }}</button>
      </form>

      <!-- Login (optionally with MFA code) -->
      <form v-else @submit.prevent="doLogin" class="auth-form">
        <label>Email
          <input v-model="form.email" type="email" autocomplete="email" required :disabled="mfaRequired" />
        </label>
        <label v-if="!mfaRequired">Password
          <input v-model="form.password" type="password" autocomplete="current-password" required />
        </label>
        <label v-else>Authenticator code
          <input v-model="form.code" type="text" inputmode="numeric" autocomplete="one-time-code"
                 placeholder="123456 or recovery code" autofocus />
          <small>Open your authenticator app, or use a recovery code.</small>
        </label>
        <p v-if="error" class="auth-error">{{ error }}</p>
        <button type="submit" :disabled="busy">
          {{ busy ? 'Signing in…' : (mfaRequired ? 'Verify' : 'Sign in') }}
        </button>
        <button v-if="mfaRequired" type="button" class="auth-link" @click="resetMfa">← Back</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref('login')        // 'login' | 'bootstrap'
const mfaRequired = ref(false)
const busy = ref(false)
const error = ref('')
const form = reactive({ email: '', password: '', code: '', display_name: '' })

onMounted(async () => {
  if (await auth.checkBootstrap()) mode.value = 'bootstrap'
})

function go() {
  const dest = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  // Full reload (not SPA nav) so no view state from a previous user can linger.
  window.location.assign(dest)
}

async function doBootstrap() {
  busy.value = true; error.value = ''
  const res = await auth.bootstrap({
    email: form.email.trim(),
    display_name: form.display_name.trim() || null,
    password: form.password,
  })
  busy.value = false
  if (res.ok) go()
  else error.value = res.data?.detail?.message || 'Could not create the account.'
}

async function doLogin() {
  busy.value = true; error.value = ''
  const res = await auth.login({
    email: form.email.trim(),
    password: form.password,
    code: form.code.trim() || undefined,
  })
  busy.value = false
  if (res.ok) { go(); return }

  const code = res.data?.detail?.code
  if (code === 'mfa_required') {
    mfaRequired.value = true
    error.value = ''
  } else if (code === 'mfa_invalid') {
    error.value = 'Invalid authenticator or recovery code.'
  } else {
    error.value = res.data?.detail?.message || 'Sign in failed.'
  }
}

function resetMfa() {
  mfaRequired.value = false
  form.code = ''
  form.password = ''
  error.value = ''
}
</script>

<style scoped>
.auth-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: var(--bg, #0f1117);
}
.auth-card {
  width: 100%;
  max-width: 380px;
  background: var(--card-bg, #1a1d27);
  border: 1px solid var(--border, #2a2e3a);
  border-radius: 14px;
  padding: 2rem 1.75rem;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.35);
}
.auth-brand { text-align: center; margin-bottom: 1.5rem; }
.auth-brand h1 { margin: 0 0 0.35rem; font-size: 1.6rem; }
.auth-brand p { margin: 0; color: var(--text-muted, #9aa3b2); font-size: 0.9rem; }
.auth-form { display: flex; flex-direction: column; gap: 0.9rem; }
.auth-form label { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.85rem; color: var(--text-muted, #9aa3b2); }
.auth-form input {
  padding: 0.65rem 0.75rem;
  border-radius: 9px;
  border: 1px solid var(--border, #2a2e3a);
  background: var(--input-bg, #11131b);
  color: var(--text, #e8eaf0);
  font-size: 0.95rem;
}
.auth-form small { color: var(--text-muted, #6b7280); font-size: 0.72rem; }
.auth-form button[type="submit"] {
  margin-top: 0.4rem;
  padding: 0.7rem;
  border: none;
  border-radius: 9px;
  background: var(--accent, #4f7cff);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.auth-form button[disabled] { opacity: 0.6; cursor: default; }
.auth-link { background: none; border: none; color: var(--text-muted, #9aa3b2); cursor: pointer; font-size: 0.85rem; }
.auth-error { margin: 0; color: #ff6b6b; font-size: 0.85rem; }
</style>
