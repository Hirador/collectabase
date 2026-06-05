import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import { applyUiPrefs, loadUiPrefs } from './utils/uiPreferences'

// Views
import GamesList from './views/GamesList.vue'
import GameDetail from './views/GameDetail.vue'
import AddGame from './views/AddGame.vue'
import Wishlist from './views/Wishlist.vue'
import Import from './views/Import.vue'
import Stats from './views/Stats.vue'
import Settings from './views/Settings.vue'
import PriceBrowser from './views/PriceBrowser.vue'
import MoreMenu from './views/MoreMenu.vue'
import LotsView from './views/LotsView.vue'
import Login from './views/Login.vue'
import { useAuthStore } from './stores/auth'

const routes = [
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/', component: GamesList },
  { path: '/game/:id', component: GameDetail, props: true },
  { path: '/add', component: AddGame },
  { path: '/edit/:id', component: AddGame },
  { path: '/wishlist', component: Wishlist },
  { path: '/import', component: Import },
  { path: '/stats', component: Stats },
  { path: '/prices', component: PriceBrowser },
  { path: '/settings', component: Settings },
  { path: '/lots', component: LotsView },
  { path: '/more', component: MoreMenu },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0, behavior: 'smooth' }
  }
})

applyUiPrefs(loadUiPrefs())

const pinia = createPinia()
const app = createApp(App)
app.use(pinia)
app.use(router)

const auth = useAuthStore(pinia)

// Probe the session once, then gate every navigation on auth.
router.beforeEach(async (to) => {
  if (!auth.ready) await auth.fetchMe()
  if (!to.meta.public && !auth.isAuthed) {
    return { path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }
  if (to.path === '/login' && auth.isAuthed) {
    return '/'
  }
  return true
})

// http.js broadcasts this when a 401 can't be refreshed away.
window.addEventListener('auth:expired', () => {
  auth.handleExpired()
  if (router.currentRoute.value.path !== '/login') {
    router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
  }
})

app.mount('#app')

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(() => console.log('SW registered'))
      .catch(err => console.log('SW failed:', err))
  })
}
