import { defineStore } from 'pinia'
import { apiGet, apiPost, getActiveCollectionId, setActiveCollectionId } from '../api/http'

const ROLE_RANK = { viewer: 1, editor: 2, owner: 3 }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,            // { id, email, display_name, is_super_admin, mfa_enabled, mfa_required }
    collections: [],       // [{ id, name, role, is_owner, is_personal }]
    activeCollectionId: null,
    ready: false,          // true once the initial /me probe has completed
    needsSetup: false,     // true when no users exist yet (first-run bootstrap)
  }),
  getters: {
    isAuthed: (s) => !!s.user,
    isSuperAdmin: (s) => !!s.user?.is_super_admin,
    // True when the user must enroll TOTP before they can use the app.
    mustEnrollMfa: (s) => !!(s.user && s.user.mfa_required && !s.user.mfa_enabled),
    activeCollection: (s) => s.collections.find((c) => c.id === s.activeCollectionId) || null,
    activeRole() {
      if (this.isSuperAdmin) return 'owner'
      return this.activeCollection?.role || null
    },
    canWrite() {
      return (ROLE_RANK[this.activeRole] || 0) >= ROLE_RANK.editor
    },
    isActiveOwner() {
      return this.isSuperAdmin || this.activeCollection?.is_owner || this.activeRole === 'owner'
    },
  },
  actions: {
    _syncActiveCollection() {
      const stored = parseInt(getActiveCollectionId(), 10)
      const ids = this.collections.map((c) => c.id)
      if (stored && ids.includes(stored)) {
        this.activeCollectionId = stored
      } else if (ids.length) {
        this.activeCollectionId = ids[0]
      } else {
        this.activeCollectionId = null
      }
      setActiveCollectionId(this.activeCollectionId || '')
    },

    setActiveCollection(id) {
      const num = parseInt(id, 10)
      if (this.collections.some((c) => c.id === num)) {
        this.activeCollectionId = num
        setActiveCollectionId(num)
      }
    },

    async fetchMe() {
      const { ok, data } = await apiGet('/api/auth/me')
      if (ok && data) {
        this.user = {
          id: data.id,
          email: data.email,
          display_name: data.display_name,
          is_super_admin: data.is_super_admin,
          mfa_enabled: data.mfa_enabled,
          mfa_required: data.mfa_required,
        }
        this.collections = data.collections || []
        this._syncActiveCollection()
      } else {
        this.user = null
        this.collections = []
        this.activeCollectionId = null
      }
      this.ready = true
      return this.isAuthed
    },

    async checkBootstrap() {
      const { ok, data } = await apiGet('/api/auth/bootstrap')
      this.needsSetup = !!(ok && data?.needs_setup)
      return this.needsSetup
    },

    async bootstrap(payload) {
      const res = await apiPost('/api/auth/bootstrap', payload)
      if (res.ok) {
        this.needsSetup = false
        await this.fetchMe()
      }
      return res
    },

    async login(payload) {
      const res = await apiPost('/api/auth/login', payload)
      if (res.ok) await this.fetchMe()
      return res
    },

    async logout() {
      await apiPost('/api/auth/logout')
      this.user = null
      this.collections = []
      this.activeCollectionId = null
      // Clear the persisted active collection so the next user doesn't inherit it.
      setActiveCollectionId('')
    },

    // Called when http.js detects an unrecoverable 401.
    handleExpired() {
      this.user = null
      this.collections = []
    },

    async refreshCollections() {
      await this.fetchMe()
    },
  },
})
