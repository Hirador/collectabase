<template>
  <div class="container">
    <h1 class="mb-3">Wishlist</h1>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="games.length === 0" class="empty">
      <h3>Your wishlist is empty</h3>
      <p>Add items you want to track or purchase</p>
      <router-link to="/prices" class="btn btn-secondary empty-cta">Browse Prices →</router-link>
    </div>

    <div v-else class="wishlist-grid">
      <div v-for="game in games" :key="game.id" class="wish-card">
        <router-link :to="`/game/${game.id}`" class="wish-cover-link">
          <div class="wish-cover">
            <img v-if="coverSrc(game)" :src="coverSrc(game)" class="cover-image" @error="markBroken(game.id)" />
            <span v-else>{{ coverEmoji(game.item_type) }}</span>
          </div>
        </router-link>

        <div class="wish-body">
          <div class="wish-title">{{ game.title }}</div>
          <div class="wish-platform text-muted">{{ game.platform_name }}</div>
          <div class="wish-tags">
            <span v-if="game.completeness" class="wish-tag">{{ game.completeness }}</span>
            <span v-if="game.condition" class="wish-tag">{{ game.condition }}</span>
          </div>
          <div v-if="game.wishlist_max_price" class="wish-max-price">
            Max: €{{ game.wishlist_max_price }}
          </div>

          <!-- Convert panel -->
          <div v-if="convertingId === game.id" class="convert-panel mt-2">
            <div class="convert-panel-title">Purchase details</div>
            <div class="copy-form-fields mt-1">
              <div class="copy-form-row">
                <label>Condition</label>
                <select v-model="convertForm.condition">
                  <option value="">—</option>
                  <option>Mint</option><option>Good</option><option>Fair</option><option>Poor</option>
                </select>
              </div>
              <div class="copy-form-row">
                <label>Completeness</label>
                <select v-model="convertForm.completeness">
                  <option value="">—</option>
                  <option>Loose</option><option>Item &amp; Box</option><option>Item &amp; Manual</option>
                  <option>Complete</option><option>New</option>
                  <option>Graded CIB</option><option>Graded New</option>
                  <option>Box Only</option><option>Manual Only</option>
                </select>
              </div>
              <div class="copy-form-row">
                <label>Purchase Price (€)</label>
                <input v-model.number="convertForm.purchase_price" type="number" step="0.01" />
              </div>
              <div class="copy-form-row">
                <label>Purchase Date</label>
                <input v-model="convertForm.purchase_date" type="date" />
              </div>
              <div class="copy-form-row">
                <label>Location</label>
                <input v-model="convertForm.location" placeholder="Shelf A…" />
              </div>
              <div class="copy-form-row">
                <label>Notes</label>
                <textarea v-model="convertForm.notes" rows="2"></textarea>
              </div>
            </div>
            <div class="copy-card-btns mt-2">
              <button type="button" class="btn btn-primary btn-sm" @click="confirmConvert(game)" :disabled="converting">
                {{ converting ? '...' : 'Add to Collection' }}
              </button>
              <button type="button" class="btn btn-secondary btn-sm" @click="convertingId = null">Cancel</button>
            </div>
          </div>

          <!-- Actions -->
          <div v-else class="wish-actions mt-2">
            <button type="button" class="btn btn-primary btn-sm" @click="startConvert(game.id)">
              ✓ I bought it
            </button>
            <button type="button" class="btn btn-danger btn-sm" @click="removeWishlistItem(game)" :disabled="deletingId === game.id">
              {{ deletingId === game.id ? '...' : '✕ Remove' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useGameStore } from '../stores/useGameStore'
import { storeToRefs } from 'pinia'
import { gamesApi } from '../api'
import { coverEmoji, makeFallbackCoverDataUrl, needsAutoCover } from '../utils/coverFallback'
import { notifyError, notifySuccess } from '../composables/useNotifications'

const store = useGameStore()
const { wishlist: games, loading } = storeToRefs(store)

const brokenCoverIds = ref({})
const deletingId = ref(null)
const convertingId = ref(null)
const converting = ref(false)
const convertForm = ref({
  condition: '', completeness: '', purchase_price: null, purchase_date: '', location: '', notes: ''
})

function markBroken(id) {
  brokenCoverIds.value[id] = true
}

function coverSrc(game) {
  if (!game) return null
  if (game.cover_url && !brokenCoverIds.value[game.id]) return game.cover_url
  if (needsAutoCover(game.item_type)) return makeFallbackCoverDataUrl(game)
  return null
}

function startConvert(id) {
  convertForm.value = { condition: '', completeness: '', purchase_price: null, purchase_date: '', location: '', notes: '' }
  convertingId.value = id
}

async function confirmConvert(game) {
  converting.value = true
  try {
    // Move out of wishlist
    const updateRes = await gamesApi.update(game.id, { ...game, is_wishlist: false })
    if (!updateRes.ok) {
      const detail = updateRes.data?.detail
      notifyError(detail?.message || detail || 'Failed to move to collection.')
      return
    }

    // Update copy 1 with purchase details
    const gameData = await gamesApi.get(game.id)
    if (gameData.ok) {
      const copies = gameData.data.copies || []
      if (copies.length > 0) {
        const copy1 = copies[0]
        const payload = { ...copy1, ...convertForm.value }
        await gamesApi.updateCopy(game.id, copy1.id, payload)
      }
    }

    notifySuccess(`"${game.title}" added to your collection.`)
    convertingId.value = null
    store.refresh()
  } catch (e) {
    console.error('Convert failed:', e)
    notifyError('Failed to move to collection.')
  } finally {
    converting.value = false
  }
}

async function removeWishlistItem(game) {
  if (!confirm(`Remove "${game.title}" from wishlist?`)) return
  deletingId.value = game.id
  try {
    const res = await gamesApi.remove(game.id)
    if (res.ok) {
      notifySuccess('Removed from wishlist.')
      store.refresh()
    } else {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Failed to remove.')
    }
  } catch (e) {
    console.error('Delete failed:', e)
    notifyError('Failed to remove.')
  } finally {
    deletingId.value = null
  }
}

store.load()
</script>

<style scoped>
.wishlist-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.wish-card {
  background: var(--bg-light);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.wish-cover-link {
  display: block;
  text-decoration: none;
}

.wish-cover {
  aspect-ratio: 3/4;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 4rem;
  overflow: hidden;
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.wish-body {
  padding: 0.85rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.wish-title {
  font-weight: 600;
  font-size: 0.9rem;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.wish-platform {
  font-size: 0.78rem;
  margin-top: 0.2rem;
}

.wish-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.3rem;
}

.wish-tag {
  font-size: 0.7rem;
  background: rgba(255,255,255,0.07);
  border: 1px solid var(--border);
  border-radius: 0.3rem;
  padding: 0.1rem 0.4rem;
  color: var(--text-muted);
}

.wish-max-price {
  font-size: 0.82rem;
  color: var(--warning, #facc15);
  font-weight: 600;
  margin-top: 0.3rem;
}

.wish-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-top: auto;
}

.convert-panel {
  border-top: 1px dashed var(--glass-border);
  padding-top: 0.6rem;
}

.convert-panel-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.copy-form-fields {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.copy-form-row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.copy-form-row label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--text-muted);
}

.copy-form-row select,
.copy-form-row input,
.copy-form-row textarea {
  width: 100%;
  font-size: 0.82rem;
  padding: 0.28rem 0.4rem;
  background: rgba(0,0,0,0.3);
  border: 1px solid var(--border, rgba(255,255,255,0.1));
  border-radius: 0.35rem;
  color: var(--text);
}

.copy-form-row textarea {
  resize: vertical;
}

.copy-card-btns {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.empty-cta {
  margin-top: 0.75rem;
}
</style>
