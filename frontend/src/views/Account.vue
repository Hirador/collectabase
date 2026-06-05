<template>
  <div class="account-view">
    <h1>Account</h1>
    <p class="subtitle">{{ auth.user?.email }}</p>

    <!-- Two-factor authentication -->
    <section class="panel">
      <h2>Two-factor authentication</h2>
      <p v-if="auth.user?.mfa_enabled" class="status on">✅ Enabled</p>
      <p v-else class="status off">Not enabled</p>

      <template v-if="!auth.user?.mfa_enabled">
        <button v-if="!setup" class="btn-primary" :disabled="busy" @click="startSetup">
          {{ busy ? 'Preparing…' : 'Set up authenticator app' }}
        </button>

        <div v-else class="mfa-setup">
          <p>1. Scan this QR code with your authenticator app (Google Authenticator, Authy, 1Password…).</p>
          <img :src="setup.qr" alt="MFA QR code" class="qr" />
          <details>
            <summary>Can't scan? Enter the key manually</summary>
            <code class="secret">{{ setup.secret }}</code>
          </details>
          <p>2. Enter the 6-digit code it shows:</p>
          <div class="row">
            <input v-model="verifyCode" inputmode="numeric" placeholder="123456" maxlength="8" />
            <button class="btn-primary" :disabled="busy" @click="confirmSetup">Verify & enable</button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
        </div>

        <div v-if="recoveryCodes.length" class="recovery">
          <h3>⚠️ Save your recovery codes</h3>
          <p>Each can be used once if you lose your authenticator. They won't be shown again.</p>
          <ul>
            <li v-for="c in recoveryCodes" :key="c"><code>{{ c }}</code></li>
          </ul>
          <button class="btn-secondary" @click="recoveryCodes = []">I've saved them</button>
        </div>
      </template>

      <template v-else>
        <div class="row">
          <input v-model="disablePassword" type="password" placeholder="Confirm password to disable" />
          <button class="btn-danger" :disabled="busy" @click="disableMfa">Disable 2FA</button>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </template>
    </section>

    <!-- Change password -->
    <section class="panel">
      <h2>Change password</h2>
      <div class="form">
        <input v-model="pw.current_password" type="password" placeholder="Current password" />
        <input v-model="pw.new_password" type="password" placeholder="New password (min 8)" />
        <button class="btn-primary" :disabled="busy" @click="changePassword">Update password</button>
      </div>
      <p v-if="pwMessage" :class="pwError ? 'error' : 'ok'">{{ pwMessage }}</p>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { apiPost } from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const busy = ref(false)
const error = ref('')

const setup = ref(null)
const verifyCode = ref('')
const recoveryCodes = ref([])
const disablePassword = ref('')

const pw = reactive({ current_password: '', new_password: '' })
const pwMessage = ref('')
const pwError = ref(false)

async function startSetup() {
  busy.value = true; error.value = ''
  const { ok, data } = await apiPost('/api/auth/mfa/setup')
  busy.value = false
  if (ok) setup.value = data
  else error.value = data?.detail?.message || 'Could not start setup.'
}

async function confirmSetup() {
  busy.value = true; error.value = ''
  const { ok, data } = await apiPost('/api/auth/mfa/verify', { code: verifyCode.value.trim() })
  busy.value = false
  if (ok) {
    recoveryCodes.value = data.recovery_codes || []
    setup.value = null
    verifyCode.value = ''
    await auth.fetchMe()
  } else {
    error.value = data?.detail?.message || 'Invalid code.'
  }
}

async function disableMfa() {
  busy.value = true; error.value = ''
  const { ok, data } = await apiPost('/api/auth/mfa/disable', { password: disablePassword.value })
  busy.value = false
  if (ok) { disablePassword.value = ''; await auth.fetchMe() }
  else error.value = data?.detail?.message || 'Could not disable.'
}

async function changePassword() {
  busy.value = true; pwMessage.value = ''; pwError.value = false
  const { ok, data } = await apiPost('/api/auth/change-password', { ...pw })
  busy.value = false
  if (ok) {
    pwMessage.value = 'Password updated.'
    pw.current_password = ''; pw.new_password = ''
  } else {
    pwError.value = true
    pwMessage.value = data?.detail?.message || 'Could not update password.'
  }
}
</script>

<style scoped>
.account-view { max-width: 640px; margin: 0 auto; padding: 1.5rem; }
h1 { margin-bottom: 0.25rem; }
.subtitle { color: var(--text-muted); margin-top: 0; }
.panel {
  background: var(--bg-light);
  border: 1px solid var(--glass-border);
  border-radius: 0.9rem;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}
.panel h2 { margin-top: 0; font-size: 1.1rem; }
.status.on { color: #4ade80; }
.status.off { color: var(--text-muted); }
.row { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
.form { display: flex; flex-direction: column; gap: 0.6rem; }
input {
  padding: 0.55rem 0.7rem; border-radius: 0.6rem; border: 1px solid var(--glass-border);
  background: var(--bg); color: var(--text); font-size: 0.95rem;
}
.qr { width: 200px; height: 200px; background: #fff; padding: 8px; border-radius: 8px; }
.secret { display: inline-block; margin-top: 0.4rem; padding: 0.3rem 0.5rem; background: var(--bg); border-radius: 0.4rem; }
.recovery { margin-top: 1rem; padding: 1rem; border: 1px dashed var(--glass-border); border-radius: 0.6rem; }
.recovery ul { columns: 2; list-style: none; padding: 0; }
.recovery li { margin: 0.2rem 0; }
.btn-primary { background: var(--primary, #8b5cf6); color: #fff; border: none; padding: 0.6rem 1rem; border-radius: 0.6rem; cursor: pointer; }
.btn-secondary { background: transparent; border: 1px solid var(--glass-border); color: var(--text); padding: 0.5rem 0.9rem; border-radius: 0.6rem; cursor: pointer; }
.btn-danger { background: #ef4444; color: #fff; border: none; padding: 0.6rem 1rem; border-radius: 0.6rem; cursor: pointer; }
.error { color: #ff6b6b; }
.ok { color: #4ade80; }
.btn-primary[disabled] { opacity: 0.6; }
</style>
