<template>
  <div class="container">
    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="!game" class="empty">
      <h3>Game not found</h3>
      <router-link to="/">Back to list</router-link>
    </div>

    <div v-else class="detail-layout">
      <!-- LEFT COLUMN -->
      <div class="left-column">
        <div class="card cover-card">
          <div class="cover-large">
            <img v-if="currentCoverSrc" :src="currentCoverSrc" class="cover-image" @error="onDetailCoverError" />
          <span v-else>{{ coverEmoji(game?.item_type) }}</span>
          <button
            v-if="game.cover_url && !isSvgDataCover(game.cover_url)"
            @click="removeCover"
            class="cover-remove-btn"
            title="Remove cover"
          >✕</button>
        </div>
        <div class="cover-upload-row">
          <input
            ref="coverFileInput"
            type="file"
            accept="image/*"
            capture="environment"
            style="display:none"
            @change="onCoverFileSelected"
          />
          <details ref="coverUploadMenu" class="cover-upload-menu">
            <summary class="btn btn-secondary cover-upload-btn focus-ring" :class="{ disabled: coverUploading }">
              {{ coverUploading ? '⏳ Uploading...' : '📷 Cover Actions ▼' }}
            </summary>
            <div class="cover-upload-menu-list">
              <button type="button" class="cover-upload-menu-item" @click="triggerCoverUpload" :disabled="coverUploading">
                📷 Upload Photo...
              </button>
              <button type="button" class="cover-upload-menu-item" @click="openCoverGallery" :disabled="coverUploading">
                🖼 Choose from Gallery...
              </button>
              <hr class="more-menu-divider" />
              <button type="button" class="cover-upload-menu-item" @click="enrichCover" :disabled="enriching">
                {{ enriching ? '⏳ Fetching...' : '🪄 Auto-Fetch Cover' }}
              </button>
              <button type="button" class="cover-upload-menu-item" @click="useConsolePlaceholder" :disabled="placeholderApplying">
                {{ placeholderApplying ? '⏳ Applying...' : '📦 Use Console Logo' }}
              </button>
            </div>
          </details>
          <span v-if="coverUploadError" class="cover-upload-error">{{ coverUploadError }}</span>
        </div>
      </div>

      <!-- IMAGE GALLERY -->
      <div class="card mt-3">
        <h3 class="chunk-title m-0 mb-2">Image Gallery</h3>
        <div v-if="imagesLoading" class="text-muted text-sm">Loading gallery...</div>
        <div v-else class="item-gallery-grid">
          <div v-for="img in itemImages" :key="img.id" class="gallery-thumb-wrap">
            <img :src="img.image_url" class="gallery-thumb" loading="lazy" />
            <div class="gallery-thumb-actions">
              <button type="button" class="btn btn-sm btn-primary" title="Set as Cover" @click="setPrimaryItemImage(img.id)">🌟</button>
              <button type="button" class="btn btn-sm btn-danger margin-left-auto" title="Delete Image" @click="deleteItemImage(img.id)">🗑</button>
            </div>
            <div v-if="img.is_primary" class="primary-badge">Cover</div>
          </div>
          
          <div class="gallery-upload-wrap">
            <input
              ref="galleryFileInput"
              type="file"
              accept="image/*"
              style="display:none"
              multiple
              @change="onGalleryFileSelected"
            />
            <button type="button" class="btn btn-secondary gallery-upload-btn" @click="triggerGalleryUpload" :disabled="galleryUploading">
              {{ galleryUploading ? '⏳' : '+ Add' }}
            </button>
          </div>
        </div>
      </div>
      </div>

      <!-- RIGHT COLUMN -->
      <div class="info-layout">
        <div class="flex flex-between items-start mb-2 detail-header">
          <div class="detail-title-block">
            <h1>{{ game.title }}</h1>
            <p class="text-muted">{{ game.platform_name }}</p>
          </div>
          <div class="actions actions-compact actions-toolbar">
            <router-link :to="`/edit/${game.id}`" class="btn btn-primary btn-compact">Edit</router-link>
            <details class="more-menu">
              <summary class="btn btn-secondary btn-compact more-trigger" aria-label="More actions" title="More actions">⋮</summary>
              <div class="more-menu-list">
                <button type="button" class="more-menu-link more-menu-btn" @click="openPriceBrowserSearch">🔎 Open in Price Browser</button>
                <a :href="ebayUrl()" target="_blank" rel="noopener" class="more-menu-link">🛒 eBay Sold Items</a>
                <a :href="priceChartingUrl()" target="_blank" rel="noopener" class="more-menu-link">📈 PriceCharting Page</a>
                <a :href="rawgUrl()" target="_blank" rel="noopener" class="more-menu-link">🎮 RAWG Database</a>
                <hr class="more-menu-divider" />
                <button type="button" class="more-menu-link more-menu-btn text-danger" @click="deleteGame">🗑 Delete Game</button>
              </div>
            </details>
          </div>
        </div>

        <div class="info-cards-container">
          <!-- METADATA CARD -->
          <div class="chunk-card">
            <h3 class="chunk-title">Metadata</h3>
            <div class="details-grid">
              <div v-if="game.item_type" class="detail-item">
                <label>Type</label>
                <span>{{ game.item_type.charAt(0).toUpperCase() + game.item_type.slice(1) }}</span>
              </div>
              <div v-if="game.region" class="detail-item">
                <label>Region</label>
                <span>{{ game.region }}</span>
              </div>
              <div v-if="game.barcode" class="detail-item">
                <label>Barcode</label>
                <span>{{ game.barcode }}</span>
              </div>
              <div v-if="game.release_date" class="detail-item">
                <label>Release Date</label>
                <span>{{ game.release_date }}</span>
              </div>
              <div v-if="game.genre" class="detail-item">
                <label>Genre</label>
                <span>{{ game.genre }}</span>
              </div>
              <div v-if="game.developer" class="detail-item">
                <label>Developer</label>
                <span>{{ game.developer }}</span>
              </div>
              <div v-if="game.publisher" class="detail-item">
                <label>Publisher</label>
                <span>{{ game.publisher }}</span>
              </div>
              <div v-if="game.character_name" class="detail-item">
                <label>Character</label>
                <span>{{ game.character_name }}</span>
              </div>
              <div v-if="game.series_name" class="detail-item">
                <label>Series</label>
                <span>{{ game.series_name }}</span>
              </div>
              <div v-if="game.scale" class="detail-item">
                <label>Scale</label>
                <span>{{ game.scale }}</span>
              </div>
              <div v-if="game.funko_number" class="detail-item">
                <label>Funko #</label>
                <span>{{ game.funko_number }}</span>
              </div>
              <div v-if="game.vinyl_format" class="detail-item">
                <label>Format</label>
                <span>{{ game.vinyl_format }}</span>
              </div>
              <div v-if="game.is_wishlist && game.wishlist_max_price" class="detail-item">
                <label>Max Wishlist Price</label>
                <span>€{{ game.wishlist_max_price }}</span>
              </div>
            </div>
          </div>

        </div>

        <!-- MY COPIES — horizontal cards -->
        <div class="copies-section">
          <h3 class="chunk-title">My Copies ({{ copies.length }})</h3>
          <div class="copies-row">
            <!-- Existing copy cards -->
            <div v-for="(copy, idx) in copies" :key="copy.id" class="copy-card">
              <!-- Edit mode -->
              <template v-if="editingCopyId === copy.id">
                <div class="copy-card-title">Edit Copy {{ idx + 1 }}</div>
                <div class="copy-form-fields">
                  <div class="copy-form-row">
                    <label>Condition</label>
                    <select v-model="copyForm.condition">
                      <option value="">—</option>
                      <option>Mint</option><option>Good</option><option>Fair</option><option>Poor</option>
                    </select>
                  </div>
                  <div class="copy-form-row">
                    <label>Completeness</label>
                    <select v-model="copyForm.completeness">
                      <option value="">—</option>
                      <option>Loose</option><option>Item &amp; Box</option><option>Item &amp; Manual</option>
                      <option>Complete</option><option>New</option>
                      <option>Graded CIB</option><option>Graded New</option>
                      <option>Box Only</option><option>Manual Only</option>
                    </select>
                  </div>
                  <div class="copy-form-row">
                    <label>Price (€)</label>
                    <input v-model.number="copyForm.purchase_price" type="number" step="0.01" />
                  </div>
                  <div class="copy-form-row">
                    <label>Purchase Date</label>
                    <input v-model="copyForm.purchase_date" type="date" />
                  </div>
                  <div class="copy-form-row">
                    <label>Location</label>
                    <input v-model="copyForm.location" placeholder="Shelf A…" />
                  </div>
                  <div class="copy-form-row">
                    <label>Notes</label>
                    <textarea v-model="copyForm.notes" rows="2"></textarea>
                  </div>
                </div>
                <div class="copy-card-btns mt-2">
                  <button type="button" class="btn btn-primary btn-sm" @click="saveCopyForm" :disabled="copySaving">
                    {{ copySaving ? '...' : 'Save' }}
                  </button>
                  <button type="button" class="btn btn-secondary btn-sm" @click="editingCopyId = null">Cancel</button>
                </div>
              </template>

              <!-- Display mode -->
              <template v-else>
                <div class="copy-card-header">
                  <span class="copy-card-num">Copy {{ idx + 1 }}</span>
                  <div class="copy-card-actions">
                    <button type="button" class="btn btn-sm btn-secondary" @click="startEditCopy(copy)" title="Edit">✎</button>
                    <button type="button" class="btn btn-sm btn-danger" @click="deleteCopy(copy.id)" title="Delete">✕</button>
                  </div>
                </div>
                <div class="copy-fields">
                  <div v-if="copy.condition" class="copy-field">
                    <span class="copy-field-label">Condition</span>
                    <span>{{ copy.condition }}</span>
                  </div>
                  <div v-if="copy.completeness" class="copy-field">
                    <span class="copy-field-label">Completeness</span>
                    <span>{{ copy.completeness }}</span>
                  </div>
                  <div v-if="copy.purchase_price" class="copy-field">
                    <span class="copy-field-label">Paid</span>
                    <span>€{{ copy.purchase_price }}</span>
                  </div>
                  <div v-if="copy.purchase_date" class="copy-field">
                    <span class="copy-field-label">Date</span>
                    <span>{{ copy.purchase_date }}</span>
                  </div>
                  <div v-if="copy.location" class="copy-field">
                    <span class="copy-field-label">Location</span>
                    <span>{{ copy.location }}</span>
                  </div>
                  <div v-if="copyValue(copy) != null && copy.purchase_price" class="copy-field copy-pl-row">
                    <span class="copy-field-label">P/L</span>
                    <span class="pl-pill" :class="copyValue(copy) >= copy.purchase_price ? 'profit' : 'loss'">
                      {{ copyValue(copy) >= copy.purchase_price ? '↑' : '↓' }}
                      €{{ Math.abs(copyValue(copy) - copy.purchase_price).toFixed(2) }}
                    </span>
                  </div>
                  <div v-if="copy.current_value != null" class="copy-field">
                    <span class="copy-field-label">Baseline</span>
                    <span class="copy-baseline-val">€{{ formatMoney(copy.current_value) }}</span>
                  </div>
                </div>
                <div v-if="copy.notes" class="copy-card-notes">{{ copy.notes }}</div>
              </template>
            </div>

            <!-- Add new copy: inline form card OR trigger card -->
            <div v-if="addingCopy" class="copy-card copy-card-new">
              <div class="copy-card-title">New Copy</div>
              <div class="copy-form-fields">
                <div class="copy-form-row">
                  <label>Condition</label>
                  <select v-model="copyForm.condition">
                    <option value="">—</option>
                    <option>Mint</option><option>Good</option><option>Fair</option><option>Poor</option>
                  </select>
                </div>
                <div class="copy-form-row">
                  <label>Completeness</label>
                  <select v-model="copyForm.completeness">
                    <option value="">—</option>
                    <option>Loose</option><option>Item &amp; Box</option><option>Item &amp; Manual</option>
                    <option>Complete</option><option>New</option>
                    <option>Graded CIB</option><option>Graded New</option>
                    <option>Box Only</option><option>Manual Only</option>
                  </select>
                </div>
                <div class="copy-form-row">
                  <label>Price (€)</label>
                  <input v-model.number="copyForm.purchase_price" type="number" step="0.01" />
                </div>
                <div class="copy-form-row">
                  <label>Purchase Date</label>
                  <input v-model="copyForm.purchase_date" type="date" />
                </div>
                <div class="copy-form-row">
                  <label>Location</label>
                  <input v-model="copyForm.location" placeholder="Shelf A…" />
                </div>
                <div class="copy-form-row">
                  <label>Notes</label>
                  <textarea v-model="copyForm.notes" rows="2"></textarea>
                </div>
              </div>
              <div class="copy-card-btns mt-2">
                <button type="button" class="btn btn-primary btn-sm" @click="saveCopyForm" :disabled="copySaving">
                  {{ copySaving ? '...' : 'Add Copy' }}
                </button>
                <button type="button" class="btn btn-secondary btn-sm" @click="addingCopy = false">Cancel</button>
              </div>
            </div>
            <button v-else type="button" class="copy-card copy-card-add" @click="startAddCopy">
              <span class="copy-add-icon">+</span>
              <span class="copy-add-label">Add Copy</span>
            </button>
          </div>
        </div>

        <div v-if="game.description" class="notes card">
          <label>Description</label>
          <p class="description-text" v-html="formattedDescription"></p>
        </div>

        <!-- MARKET PRICES -->
        <div class="price-section card">
          <div class="price-section-header flex flex-between items-center mb-2">
            <h3 class="chunk-title m-0">Market Prices</h3>
            <div class="actions-compact">
              <button @click="checkPrice" class="btn btn-secondary btn-sm" :disabled="priceLoading">
                {{ priceLoading ? '⏳' : '📊 PriceCharting' }}
              </button>
              <button @click="checkPriceEbay" class="btn btn-secondary btn-sm" :disabled="priceLoading">
                {{ priceLoading ? '⏳' : '🛒 eBay' }}
              </button>
            </div>
          </div>

          <div v-if="latestPrice" class="price-cells">
            <template v-for="pc in priceColumns" :key="pc.key">
              <div v-if="latestPrice[pc.field] != null"
                   class="price-cell"
                   :class="{ relevant: relevantKey() === pc.key }">
                <span class="p-label">{{ pc.label }}</span>
                <span class="p-val">€{{ latestPrice[pc.field].toFixed(2) }}</span>
              </div>
            </template>
          </div>
          <div v-if="latestPrice" class="price-meta mt-2">
            Last checked: {{ formatDate(latestPrice.fetched_at) }}
            <span :class="`source-pill source-${latestPrice.source}`">{{ latestPrice.source }}</span>
          </div>

          <div v-if="priceError" class="price-error mt-2">{{ priceError }}</div>
          <div v-if="priceError" class="price-catalog-help mt-1">
            <button class="btn btn-secondary btn-sm" @click="openPriceBrowserSearch">
              🔎 Select from Price Catalog
            </button>
          </div>

          <div class="start-value-row mt-3 pt-2">
            <button class="btn btn-secondary btn-sm" @click="toggleBaselinePanel">
              {{ baselineOpen ? 'Close' : 'Update Base Line' }}
            </button>
          </div>

          <!-- Inline baseline editor -->
          <div v-if="baselineOpen" class="baseline-panel mt-2">
            <!-- Price update message -->
            <div v-if="priceUpdateMessage" class="baseline-update-msg mb-2">
              <template v-if="priceUpdateMessage.type === 'updated'">
                <div class="text-sm font-semibold mb-1">Values updated:</div>
                <div v-for="line in priceUpdateMessage.lines" :key="line" class="text-sm text-muted">{{ line }}</div>
              </template>
              <div v-else class="text-sm text-muted">No price update.</div>
            </div>
            <!-- Per-copy values -->
            <div class="baseline-section" v-if="copies.length">
              <div class="baseline-section-title">Per-Copy Baseline</div>
              <div class="baseline-section-desc text-muted">Set the current market value for each copy. Used for P/L calculation.</div>
              <div class="baseline-copies-list mt-2">
                <div v-for="(copy, idx) in copies" :key="copy.id" class="baseline-copy-row">
                  <div class="baseline-copy-info">
                    <span class="baseline-copy-num">Copy {{ idx + 1 }}</span>
                    <span v-if="copy.condition" class="badge ml-1">{{ copy.condition }}</span>
                    <span v-if="copy.completeness" class="badge ml-1">{{ copy.completeness }}</span>
                  </div>
                  <div class="baseline-copy-controls">
                    <input
                      v-model.number="baselineCopyInputs[copy.id]"
                      type="number" step="0.01" placeholder="€"
                      class="search-input baseline-copy-input"
                    />
                    <select
                      v-if="latestPrice"
                      @change="applyCompletenessPrice($event, 'copy', copy.id)"
                      class="search-input baseline-pick-select"
                    >
                      <option value="">{{ copy.completeness ? copy.completeness + ' — use…' : 'Use price for…' }}</option>
                      <option
                        v-for="opt in completenessSelectOptions"
                        :key="opt.label"
                        :value="opt.label"
                        :disabled="opt.price == null"
                      >{{ opt.label }}{{ opt.price != null ? ' — €' + opt.price.toFixed(2) : ' (N/A)' }}</option>
                    </select>
                    <button type="button" class="btn btn-danger btn-sm" title="Clear" @click="baselineCopyInputs[copy.id] = null">✕</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="flex gap-2 mt-2 justify-end">
              <button type="button" class="btn btn-secondary btn-sm" @click="toggleBaselinePanel">Cancel</button>
              <button type="button" class="btn btn-primary btn-sm" @click="saveBaseline" :disabled="baselineSaving">
                {{ baselineSaving ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </div>

          <div v-if="rawgReference" class="rawg-reference mt-3">
            <div class="rawg-title text-muted mb-1">RAWG reference links:</div>
            <div class="flex gap-2 flex-wrap">
              <a v-if="rawgReference.rawg_url" :href="rawgReference.rawg_url" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
                🎮 RAWG.io Game Page
              </a>
              <a
                v-for="(store, idx) in rawgReference.store_links"
                :key="`${store.url}-${idx}`"
                :href="store.url"
                target="_blank"
                rel="noopener"
                class="btn btn-secondary btn-sm"
              >
                {{ store.name || 'Store' }}
              </a>
            </div>
          </div>

          <!-- Price History Chart -->
          <div v-if="priceHistory.length >= 2" class="price-chart-wrapper mt-3">
            <canvas ref="priceChartEl"></canvas>
          </div>
          <!-- Empty State Chart Info -->
          <div v-else class="empty-chart-state mt-4">
            <div class="icon">📈</div>
            <h4>No Price Trends Yet</h4>
            <p>Fetch the market price directly above to start charting the value of your game over time.</p>
          </div>
          
          <details class="advanced-price-tools mt-4">
            <summary class="text-muted text-sm cursor-pointer hover:text-white transition">Show Advanced Entry Options</summary>
            
            <!-- Manual Entry -->
            <div class="manual-entry mt-3 p-3">
              <div class="manual-entry-label mb-2">Add Manual Price Point</div>
              <div class="manual-entry-fields">
                <div class="manual-field">
                  <span class="p-label text-xs">Loose (€)</span>
                  <input v-model.number="manualEntry.loose_price" type="number" step="0.01" class="search-input py-1 px-2" placeholder="—" />
                </div>
                <div class="manual-field">
                  <span class="p-label text-xs">CIB (€)</span>
                  <input v-model.number="manualEntry.complete_price" type="number" step="0.01" class="search-input py-1 px-2" placeholder="—" />
                </div>
                <div class="manual-field">
                  <span class="p-label text-xs">New (€)</span>
                  <input v-model.number="manualEntry.new_price" type="number" step="0.01" class="search-input py-1 px-2" placeholder="—" />
                </div>
                <button class="btn btn-primary" @click="addManualEntry" :disabled="manualSaving">
                  {{ manualSaving ? 'Saving...' : '+ Add' }}
                </button>
              </div>
            </div>

            <div v-if="priceHistory.length" class="price-history-list mt-3">
              <div class="manual-entry-label text-sm mb-2">Recent History Log</div>
              <div
                v-for="entry in recentPriceEntries"
                :key="entry.id"
                class="price-history-row rounded p-2 mb-1"
                style="background: rgba(255,255,255,0.03);"
              >
                <div class="price-history-main">
                  <span class="text-xs text-muted">{{ formatDate(entry.fetched_at) }}</span>
                  <span :class="`source-pill source-${entry.source} text-xs ml-2`">{{ entry.source }}</span>
                  <span class="ml-auto text-sm font-semibold">{{ entryDisplayValue(entry) }}</span>
                </div>
                <button
                  class="btn btn-danger btn-sm ml-3"
                  :disabled="deletingEntryId === entry.id"
                  @click="removePriceEntry(entry)"
                >
                  ✕
                </button>
              </div>
            </div>
          </details>

        </div>
      </div>
    </div>

    <div v-if="coverGalleryOpen" class="cover-gallery-backdrop" @click.self="closeCoverGallery">
      <div class="cover-gallery-modal card">
        <div class="cover-gallery-header">
          <strong>Console Gallery</strong>
          <button type="button" class="cover-gallery-close" @click="closeCoverGallery">✕</button>
        </div>
        <input
          v-model.trim="coverGalleryFilter"
          class="search-input cover-gallery-search"
          placeholder="Filter gallery..."
        />
        <div v-if="coverGalleryLoading" class="text-muted">Loading gallery...</div>
        <div v-else-if="coverGalleryError" class="cover-upload-error">{{ coverGalleryError }}</div>
        <div v-else-if="filteredCoverGalleryItems.length === 0" class="text-muted">
          No images found.
        </div>
        <div v-else class="cover-gallery-grid">
          <button
            v-for="item in filteredCoverGalleryItems"
            :key="item.url"
            type="button"
            class="cover-gallery-item"
            @click="applyGalleryCover(item.url)"
            :disabled="coverGalleryApplying"
          >
            <img :src="item.url" :alt="item.name || item.filename || 'Cover image'" loading="lazy" />
            <span>{{ item.name || item.filename }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { gamesApi, lookupApi, priceApi } from '../api'
import { useGameStore } from '../stores/useGameStore'
import { notifyError, notifySuccess } from '../composables/useNotifications'
import { coverEmoji, isSvgDataCover, makeFallbackCoverDataUrl, needsAutoCover } from '../utils/coverFallback'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Legend,
  Tooltip
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Legend, Tooltip)

const route = useRoute()
const router = useRouter()
const game = ref(null)
const loading = ref(true)
const enriching = ref(false)
const priceLoading = ref(false)
const priceHistory = ref([])
const priceError = ref('')
const priceUpdateMessage = ref(null)
const rawgReference = ref(null)
const priceChartEl = ref(null)
const coverFileInput = ref(null)
const galleryFileInput = ref(null)
const coverUploadMenu = ref(null)
const coverUploading = ref(false)
const galleryUploading = ref(false)
const coverUploadError = ref('')
const placeholderApplying = ref(false)
const coverGalleryOpen = ref(false)
const coverGalleryLoading = ref(false)
const coverGalleryApplying = ref(false)
const coverGalleryError = ref('')
const coverGalleryFilter = ref('')
const coverGalleryItems = ref([])
const itemImages = ref([])
const imagesLoading = ref(false)
const manualEntry = ref({ loose_price: null, complete_price: null, new_price: null })
const manualSaving = ref(false)
const deletingEntryId = ref(null)
const coverHasError = ref(false)
const coverAutoFixing = ref(false)
const coverAutoEnrichTried = ref(false)
const copies = ref([])
const editingCopyId = ref(null)
const addingCopy = ref(false)
const copySaving = ref(false)
const copyForm = ref({
  condition: '', completeness: '',
  purchase_price: null, purchase_date: '', location: '', notes: ''
})
const baselineOpen = ref(false)
const baselineCopyInputs = ref({})
const baselineSaving = ref(false)
let chartInstance = null

const latestPrice = computed(() => priceHistory.value[0] ?? null)
const recentPriceEntries = computed(() => priceHistory.value.slice(0, 10))
const currentCoverSrc = computed(() => {
  if (!game.value) return null
  if (game.value.cover_url && !coverHasError.value) return game.value.cover_url
  if (needsAutoCover(game.value.item_type)) return makeFallbackCoverDataUrl(game.value)
  return null
})
const formattedDescription = computed(() => formatDescriptionHtml(game.value?.description || ''))
const filteredCoverGalleryItems = computed(() => {
  const query = normalizeSearch(coverGalleryFilter.value)
  if (!query) return coverGalleryItems.value
  return coverGalleryItems.value.filter((item) => {
    return normalizeSearch(item.name).includes(query) || normalizeSearch(item.filename).includes(query)
  })
})

function decodeHtmlEntities(input) {
  const area = document.createElement('textarea')
  area.innerHTML = String(input || '')
  return area.value
}

function normalizeDescriptionInput(input) {
  let text = decodeHtmlEntities(input || '').trim()
  if (!text) return ''

  text = text.replace(
    /<a\b[^>]*href=(["'])(https?:\/\/[^"']+)\1[^>]*>(.*?)<\/a>/gi,
    (_m, _q, href, label) => `${(label || href).trim()} (${href.trim()})`
  )
  text = text.replace(/<\/?br\s*\/?>/gi, '\n')
  return text
}

function normalizeSearch(value) {
  return String(value || '').trim().toLowerCase()
}

function formatDescriptionHtml(input) {
  let text = String(input || '').trim()
  if (!text) return ''

  // Support basic markdown links [text](url) -> <a href="url" target="_blank" rel="noopener">text</a>
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')

  // Convert raw URLs to links (if they are not already inside an href="...")
  const urlRegex = /(?<!href=["'])(https?:\/\/[^\s<>"'()]+)(?![^<]*>|[^<>]*<\/a>)/gi
  text = text.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')

  // Convert pure linebreaks to <br> if they aren't part of existing HTML blocks
  text = text.replace(/(?:\r\n|\r|\n)/g, '<br>')

  return text
}

function formatChartDate(dt) {
  if (!dt) return ''
  // SQLite CURRENT_TIMESTAMP is "YYYY-MM-DD HH:MM:SS" — replace space with T for valid ISO 8601
  const d = new Date(typeof dt === 'string' ? dt.replace(' ', 'T') : dt)
  if (isNaN(d.getTime())) return String(dt)
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yy = String(d.getFullYear()).slice(-2)
  return `${dd}.${mm}.${yy}`
}

function buildChart() {
  if (!priceChartEl.value) return
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }

  // priceHistory is ordered newest-first; reverse for chronological order on chart
  const ordered = [...priceHistory.value].reverse()
  const labels = ordered.map(r => formatChartDate(r.fetched_at))
  const datasets = [
    {
      label: 'Loose',
      data: ordered.map(r => r.loose_price),
      borderColor: '#60a5fa',
      backgroundColor: 'transparent',
      tension: 0.3,
      pointRadius: 4,
      spanGaps: true
    },
    {
      label: 'CIB',
      data: ordered.map(r => r.complete_price),
      borderColor: '#34d399',
      backgroundColor: 'transparent',
      tension: 0.3,
      pointRadius: 4,
      spanGaps: true
    },
    {
      label: 'New',
      data: ordered.map(r => r.new_price),
      borderColor: '#fb923c',
      backgroundColor: 'transparent',
      tension: 0.3,
      pointRadius: 4,
      spanGaps: true
    }
  ]

  chartInstance = new Chart(priceChartEl.value, {
    type: 'line',
    data: {
      labels,
      datasets
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            footer(items) {
              const idx = items[0]?.dataIndex
              if (idx == null) return []
              const src = ordered[idx]?.source || ''
              const labels = { pricecharting: '📊 PriceCharting', manual: '✏️ Manual', ebay: '🛒 eBay', 'Start Value': '💰 Start Value' }
              return [labels[src] || src]
            }
          }
        }
      },
      scales: {
        x: { title: { display: false } },
        y: {
          title: { display: true, text: 'EUR' },
          beginAtZero: false
        }
      }
    }
  })
}

watch(
  () => priceHistory.value,
  async (newVal) => {
    if (newVal.length >= 2) {
      await nextTick()
      buildChart()
    } else {
      if (chartInstance) {
        chartInstance.destroy()
        chartInstance = null
      }
    }
  },
  { deep: true }
)

// The 6 real PriceCharting condition tiers (verified from pricecharting.com HTML)
const priceColumns = [
  { key: 'loose',        label: 'Loose',        field: 'loose_price' },
  { key: 'complete',     label: 'Complete',     field: 'complete_price' },
  { key: 'new',          label: 'New',          field: 'new_price' },
  { key: 'graded',       label: 'Graded',       field: 'graded_price' },
  { key: 'box_only',     label: 'Box Only',     field: 'box_only_price' },
  { key: 'manual_only',  label: 'Manual Only',  field: 'manual_only_price' },
]

// completeness value → PC price key
// "Item & Box" and "Item & Manual" are collector labels; nearest PC tier is complete_price
const COMPLETENESS_TO_PC = {
  'Loose':         'loose',
  'Item & Box':    'complete',
  'Item & Manual': 'complete',
  'Complete':      'complete',
  'New':           'new',
  'Graded CIB':    'graded',
  'Graded New':    'graded',
  'Box Only':      'box_only',
  'Manual Only':   'manual_only',
}

const suggestableColumns = priceColumns

// All 9 collector completeness labels mapped to their PC price, for the baseline selector
const completenessSelectOptions = computed(() => [
  { label: 'Loose',         pcKey: 'loose' },
  { label: 'Item & Box',    pcKey: 'complete' },
  { label: 'Item & Manual', pcKey: 'complete' },
  { label: 'Complete',      pcKey: 'complete' },
  { label: 'New',           pcKey: 'new' },
  { label: 'Graded CIB',    pcKey: 'graded' },
  { label: 'Graded New',    pcKey: 'graded' },
  { label: 'Box Only',      pcKey: 'box_only' },
  { label: 'Manual Only',   pcKey: 'manual_only' },
].map(opt => {
  const col = priceColumns.find(c => c.key === opt.pcKey)
  const price = (latestPrice.value && col) ? latestPrice.value[col.field] : null
  return { ...opt, price }
}))

function applyCompletenessPrice(event, _target, copyId) {
  const label = event.target.value
  event.target.value = ''
  if (!label) return
  const opt = completenessSelectOptions.value.find(o => o.label === label)
  if (!opt || opt.price == null) return
  baselineCopyInputs.value[copyId] = opt.price
}

function relevantKey() {
  const comp = copies.value[0]?.completeness || game.value?.completeness || ''
  return COMPLETENESS_TO_PC[comp] || 'loose'
}

function copyValue(copy) {
  return copy.current_value ?? null
}

function conditionSuggestions(copy) {
  const bestKey = COMPLETENESS_TO_PC[copy.completeness] || 'loose'
  return [
    priceColumns.find(c => c.key === bestKey),
    ...priceColumns.filter(c => c.key !== bestKey)
  ].filter(Boolean)
}

function toggleBaselinePanel() {
  if (!baselineOpen.value) {
    const inputs = {}
    for (const copy of copies.value) {
      inputs[copy.id] = copy.current_value ?? null
    }
    baselineCopyInputs.value = inputs
  }
  baselineOpen.value = !baselineOpen.value
}

async function saveBaseline() {
  if (!game.value) return
  baselineSaving.value = true
  try {
    for (const copy of copies.value) {
      const raw = baselineCopyInputs.value[copy.id]
      const val = raw != null && raw !== '' ? Number(raw) : null
      if (val !== copy.current_value) {
        const res = await gamesApi.setCopyValue(route.params.id, copy.id, val)
        if (!res.ok) {
          const detail = res.data?.detail
          notifyError(detail?.message || detail || `Failed to update Copy ${copy.id} baseline.`)
        }
      }
    }

    notifySuccess('Base line updated.')
    priceUpdateMessage.value = null
    baselineOpen.value = false
    await loadGame()
    if (priceHistory.value.length >= 2) {
      await nextTick()
      buildChart()
    }
  } catch (e) {
    console.error('Failed saving baseline:', e)
    notifyError('Failed to save base line.')
  } finally {
    baselineSaving.value = false
  }
}

function ebayUrl() {
  const q = encodeURIComponent(`${game.value?.title || ''} ${game.value?.platform_name || ''}`)
  return `https://www.ebay.de/sch/i.html?_nkw=${q}&LH_Sold=1&LH_Complete=1`
}

function priceChartingUrl() {
  const q = encodeURIComponent(`${game.value?.title || ''} ${game.value?.platform_name || ''}`.trim())
  return `https://www.pricecharting.com/search-products?type=prices&q=${q}`
}

function rawgUrl() {
  const q = encodeURIComponent(`${game.value?.title || ''} ${game.value?.platform_name || ''}`.trim())
  return `https://rawg.io/search?query=${q}`
}

function openPriceBrowserSearch() {
  if (!game.value) return
  const query = {}
  const title = String(game.value.title || '').trim()
  const platform = String(game.value.platform_name || '').trim().toLowerCase()
  if (title) query.search = title
  if (platform) query.platform = platform
  if (game.value.id != null) query.linkGame = String(game.value.id)
  query.returnTo = `/game/${game.value.id}`
  router.push({ path: '/prices', query })
}

function formatDate(dt) {
  if (!dt) return ''
  const d = new Date(typeof dt === 'string' ? dt.replace(' ', 'T') : dt)
  if (isNaN(d.getTime())) return String(dt)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function formatMoney(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

function formatMatchScore(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return 'n/a'
  const percent = Math.max(0, Math.min(100, Math.round(num * 100)))
  return `${percent}%`
}


function entryDisplayValue(entry) {
  if (!entry) return '—'
  if (entry.loose_price != null) return `Loose €${formatMoney(entry.loose_price)}`
  if (entry.complete_price != null) return `CIB €${formatMoney(entry.complete_price)}`
  if (entry.new_price != null) return `New €${formatMoney(entry.new_price)}`
  return '—'
}

async function checkPrice() {
  priceLoading.value = true
  priceError.value = ''
  priceUpdateMessage.value = null
  rawgReference.value = null
  try {
    const res = await priceApi.check(route.params.id)
    const data = res.data || {}
    if (!res.ok) {
      priceError.value = data?.detail?.message || data?.detail || data?.error || 'Price check failed'
      notifyError(priceError.value)
      return
    }
    if (data.error) {
      if (data.source === 'rawg') {
        priceError.value = data.error
        rawgReference.value = data
      } else {
        priceError.value = data.error
      }
    } else {
      await loadGame()
      await loadPriceHistory()
      const inputs = {}
      for (const copy of copies.value) {
        inputs[copy.id] = copy.current_value ?? null
      }
      baselineCopyInputs.value = inputs
      const updatedCopies = data.copies_updated || []
      if (updatedCopies.length > 0) {
        priceUpdateMessage.value = {
          type: 'updated',
          lines: updatedCopies.map(c => `Copy ${c.copy_id} (${c.completeness}): €${c.current_value}`)
        }
      } else {
        priceUpdateMessage.value = { type: 'no_update' }
      }
      baselineOpen.value = true
    }
  } catch (e) {
    priceError.value = 'Price check failed'
    console.error(e)
    notifyError('Price check failed.')
  } finally {
    priceLoading.value = false
  }
}

async function checkPriceEbay() {
  priceLoading.value = true
  priceError.value = ''
  priceUpdateMessage.value = null
  rawgReference.value = null
  try {
    const res = await priceApi.check(route.params.id, 'ebay')
    const data = res.data || {}
    if (!res.ok) {
      priceError.value = data?.detail?.message || data?.detail || data?.error || 'eBay price check failed'
      notifyError(priceError.value)
      return
    }
    if (data.error) {
      priceError.value = data.error
    } else {
      await loadGame()
      await loadPriceHistory()
      const inputs = {}
      for (const copy of copies.value) {
        inputs[copy.id] = copy.current_value ?? null
      }
      baselineCopyInputs.value = inputs
      const updatedCopies = data.copies_updated || []
      if (updatedCopies.length > 0) {
        priceUpdateMessage.value = {
          type: 'updated',
          lines: updatedCopies.map(c => `Copy ${c.copy_id} (${c.completeness}): €${c.current_value}`)
        }
      } else {
        priceUpdateMessage.value = { type: 'no_update' }
      }
      baselineOpen.value = true
    }
  } catch (e) {
    priceError.value = 'eBay price check failed'
    console.error(e)
    notifyError('eBay price check failed.')
  } finally {
    priceLoading.value = false
  }
}

async function loadPriceHistory() {
  try {
    const res = await priceApi.history(route.params.id)
    if (res.ok) {
      priceHistory.value = res.data || []
    }
  } catch (e) {
    console.error('Failed to load price history:', e)
    notifyError('Failed to load price history.')
  }
}

async function enrichCover() {
  enriching.value = true
  try {
    const res = await gamesApi.enrich(route.params.id)
    if (res.ok) {
      notifySuccess('Cover enriched.')
      await loadGame()
    } else {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Could not enrich cover.')
    }
  } catch (e) {
    console.error('Enrich failed:', e)
    notifyError('Cover enrichment failed.')
  } finally {
    enriching.value = false
  }
}

async function useConsolePlaceholder() {
  if (!game.value) return
  placeholderApplying.value = true
  try {
    const res = await gamesApi.placeholderCover(route.params.id)
    if (!res.ok) {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Could not apply console placeholder.')
      return
    }
    const newUrl = res.data?.cover_url
    if (newUrl) {
      game.value.cover_url = newUrl
      coverHasError.value = false
    }
    notifySuccess('Console placeholder applied.')
  } catch (e) {
    console.error('Placeholder apply failed:', e)
    notifyError('Could not apply console placeholder.')
  } finally {
    placeholderApplying.value = false
  }
}

function hasMissingOrFallbackCover() {
  if (!game.value) return true
  const url = game.value.cover_url
  if (!url) return true
  return isSvgDataCover(url)
}

async function tryAutoEnrichNonGameCover() {
  if (!game.value || !needsAutoCover(game.value.item_type)) return false
  if (coverAutoEnrichTried.value) return false
  coverAutoEnrichTried.value = true

  try {
    const res = await gamesApi.enrich(route.params.id)
    const enriched = res.ok ? (res.data?.cover_url || null) : null
    if (enriched) {
      game.value.cover_url = enriched
      coverHasError.value = false
      return true
    }
  } catch (e) {
    console.warn('Auto enrich cover failed:', e)
  }
  return false
}

async function ensureNonGameCover() {
  if (!game.value || !needsAutoCover(game.value.item_type)) return
  if (coverAutoFixing.value) return
  if (!coverHasError.value && !hasMissingOrFallbackCover()) return

  coverAutoFixing.value = true
  try {
    const enriched = await tryAutoEnrichNonGameCover()
    if (enriched) return

    const fallback = makeFallbackCoverDataUrl(game.value)
    if (game.value.cover_url !== fallback) {
      const saved = await saveCoverUrl(fallback)
      if (saved) {
        game.value.cover_url = fallback
        coverHasError.value = false
      }
    } else {
      coverHasError.value = false
    }
  } finally {
    coverAutoFixing.value = false
  }
}

async function onDetailCoverError() {
  coverHasError.value = true
  await ensureNonGameCover()
}

async function loadGame() {
  try {
    const res = await gamesApi.get(route.params.id)
    if (res.ok) {
      game.value = res.data
      copies.value = res.data.copies || []
      coverAutoEnrichTried.value = false
      coverHasError.value = false
      await ensureNonGameCover()
      await loadItemImages()
    }
  } catch (e) {
    console.error('Failed to load game:', e)
    notifyError('Failed to load game.')
  } finally {
    loading.value = false
  }
}

function startAddCopy() {
  editingCopyId.value = null
  copyForm.value = { condition: '', completeness: '', purchase_price: null, purchase_date: '', location: '', notes: '' }
  addingCopy.value = true
}

function startEditCopy(copy) {
  addingCopy.value = false
  copyForm.value = {
    condition: copy.condition || '',
    completeness: copy.completeness || '',
    purchase_price: copy.purchase_price ?? null,
    purchase_date: copy.purchase_date || '',
    location: copy.location || '',
    notes: copy.notes || ''
  }
  editingCopyId.value = copy.id
}

async function saveCopyForm() {
  copySaving.value = true
  try {
    const payload = { ...copyForm.value }
    let res
    if (editingCopyId.value !== null) {
      res = await gamesApi.updateCopy(route.params.id, editingCopyId.value, payload)
    } else {
      res = await gamesApi.addCopy(route.params.id, payload)
    }
    if (res.ok) {
      notifySuccess(editingCopyId.value !== null ? 'Copy updated.' : 'Copy added.')
      editingCopyId.value = null
      addingCopy.value = false
      await loadGame()
    } else {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Failed to save copy.')
    }
  } catch (e) {
    console.error('Failed to save copy:', e)
    notifyError('Failed to save copy.')
  } finally {
    copySaving.value = false
  }
}

async function deleteCopy(copyId) {
  const isLast = copies.value.length <= 1
  const msg = isLast
    ? 'This is the last copy. Deleting it will remove the entire item. Continue?'
    : 'Delete this copy?'
  if (!confirm(msg)) return
  try {
    const res = await gamesApi.deleteCopy(route.params.id, copyId)
    if (res.ok) {
      if (res.data?.game_deleted) {
        notifySuccess('Item deleted.')
        useGameStore().refresh()
        router.push('/')
      } else {
        notifySuccess('Copy deleted.')
        await loadGame()
      }
    } else {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Failed to delete copy.')
    }
  } catch (e) {
    console.error('Failed to delete copy:', e)
    notifyError('Failed to delete copy.')
  }
}

async function deleteGame() {
  if (!confirm('Are you sure you want to delete this game?')) return

  try {
    const res = await gamesApi.remove(route.params.id)
    if (res.ok) {
      notifySuccess('Game deleted.')
      // Drop it from the cached store so the list doesn't show it until reload.
      useGameStore().removeGame(Number(route.params.id))
      router.push('/')
    } else {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Failed to delete game.')
    }
  } catch (e) {
    console.error('Failed to delete:', e)
    notifyError('Failed to delete game.')
  }
}

async function saveCoverUrl(url) {
  const res = await gamesApi.update(route.params.id, { ...game.value, cover_url: url })
  if (res.ok) {
    game.value.cover_url = url
    coverHasError.value = false
    return true
  }
  if (res.status !== 404) {
    const detail = res.data?.detail
    notifyError(detail?.message || detail || 'Failed to save cover.')
  }
  return false
}

function closeCoverUploadMenu() {
  if (coverUploadMenu.value?.open) {
    coverUploadMenu.value.open = false
  }
}

function triggerCoverUpload() {
  if (coverUploading.value) return
  closeCoverUploadMenu()
  coverFileInput.value?.click()
}

async function loadCoverGallery() {
  coverGalleryLoading.value = true
  coverGalleryError.value = ''
  try {
    const res = await lookupApi.consoleFallbacks()
    if (!res.ok) {
      const detail = res.data?.detail
      coverGalleryError.value = detail?.message || detail || 'Could not load gallery.'
      return
    }
    const items = Array.isArray(res.data?.items) ? res.data.items : []
    coverGalleryItems.value = items
  } catch (e) {
    console.error('Failed loading console gallery:', e)
    coverGalleryError.value = 'Could not load gallery.'
  } finally {
    coverGalleryLoading.value = false
  }
}

async function openCoverGallery() {
  closeCoverUploadMenu()
  coverGalleryOpen.value = true
  if (!coverGalleryItems.value.length) {
    await loadCoverGallery()
  }
}

function closeCoverGallery() {
  coverGalleryOpen.value = false
}

async function applyGalleryCover(url) {
  if (!url || coverGalleryApplying.value) return
  coverGalleryApplying.value = true
  try {
    const saved = await saveCoverUrl(url)
    if (saved) {
      notifySuccess('Cover set from gallery.')
      closeCoverGallery()
    }
  } finally {
    coverGalleryApplying.value = false
  }
}

async function onCoverFileSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  coverUploadError.value = ''
  if (file.size > 5 * 1024 * 1024) {
    coverUploadError.value = 'File exceeds 5 MB limit.'
    event.target.value = ''
    return
  }
  coverUploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await gamesApi.uploadCover(form)
    if (!res.ok) {
      const err = res.data || {}
      coverUploadError.value = err?.detail?.message || err?.detail || err?.error || 'Upload failed.'
      notifyError(coverUploadError.value)
      return
    }
    const { url } = res.data
    const saved = await saveCoverUrl(url)
    if (saved) notifySuccess('Cover uploaded.')
  } catch (e) {
    coverUploadError.value = 'Upload failed.'
    console.error(e)
    notifyError('Upload failed.')
  } finally {
    coverUploading.value = false
    event.target.value = ''
  }
}

async function loadItemImages() {
  imagesLoading.value = true
  try {
    const res = await gamesApi.getImages(route.params.id)
    if (res.ok) {
      itemImages.value = res.data || []
    }
  } catch (e) {
    console.error('Failed to load images:', e)
  } finally {
    imagesLoading.value = false
  }
}

function triggerGalleryUpload() {
  if (galleryUploading.value) return
  galleryFileInput.value?.click()
}

async function onGalleryFileSelected(event) {
  const files = event.target.files
  if (!files || !files.length) return
  
  galleryUploading.value = true
  let okCount = 0
  
  try {
    for (const file of files) {
      if (file.size > 5 * 1024 * 1024) {
        notifyError(`File ${file.name} exceeds 5 MB limit.`)
        continue
      }
      const form = new FormData()
      form.append('file', file)
      const res = await gamesApi.uploadCover(form) // use same endpoint to upload to storage
      if (res.ok) {
        // add to item_images
        const { url } = res.data
        const addRes = await gamesApi.uploadImage(route.params.id, { image_url: url })
        if (addRes.ok) {
          okCount++
          if (addRes.data.is_primary) {
            game.value.cover_url = url
            coverHasError.value = false
          }
        }
      } else {
        notifyError(`Failed to upload ${file.name}.`)
      }
    }
    
    if (okCount > 0) {
      notifySuccess(`Uploaded ${okCount} image(s).`)
      await loadItemImages()
    }
  } catch (e) {
    console.error('Gallery upload error:', e)
    notifyError('Gallery upload failed.')
  } finally {
    galleryUploading.value = false
    event.target.value = ''
  }
}

async function deleteItemImage(imgId) {
  if (!confirm('Are you sure you want to delete this image?')) return
  try {
    const res = await gamesApi.deleteImage(route.params.id, imgId)
    if (res.ok) {
      notifySuccess('Image deleted.')
      await loadItemImages()
      // reload game in case primary cover changed
      const gameRes = await gamesApi.get(route.params.id)
      if (gameRes.ok) game.value.cover_url = gameRes.data.cover_url
    } else {
      notifyError('Failed to delete image.')
    }
  } catch (e) {
    console.error('Error deleting image:', e)
  }
}

async function setPrimaryItemImage(imgId) {
  try {
    const res = await gamesApi.setPrimaryImage(route.params.id, imgId)
    if (res.ok) {
      notifySuccess('Cover updated.')
      await loadItemImages()
      const gameRes = await gamesApi.get(route.params.id)
      if (gameRes.ok) game.value.cover_url = gameRes.data.cover_url
    } else {
      notifyError('Failed to set cover.')
    }
  } catch (e) {
    console.error('Error setting cover:', e)
  }
}

async function removeCover() {
  const saved = await saveCoverUrl('')
  if (saved) notifySuccess('Cover removed.')
}

async function addManualEntry() {
  const { loose_price, complete_price, new_price } = manualEntry.value
  if (loose_price == null && complete_price == null && new_price == null) return
  manualSaving.value = true
  try {
    const res = await priceApi.manual(route.params.id, { loose_price, complete_price, new_price })
    if (res.ok) {
      manualEntry.value = { loose_price: null, complete_price: null, new_price: null }
      notifySuccess('Manual price entry added.')
      await loadPriceHistory()
    } else {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Failed to save manual entry.')
    }
  } catch (e) {
    console.error('Failed to save manual entry:', e)
    notifyError('Failed to save manual entry.')
  } finally {
    manualSaving.value = false
  }
}

async function removePriceEntry(entry) {
  if (!entry?.id) return
  if (!confirm('Delete this price entry?')) return

  deletingEntryId.value = entry.id
  try {
    const res = await priceApi.deleteHistory(route.params.id, entry.id)
    if (!res.ok) {
      const detail = res.data?.detail
      notifyError(detail?.message || detail || 'Failed to delete price entry.')
      return
    }
    notifySuccess('Price entry removed.')
    await loadPriceHistory()
  } catch (e) {
    console.error('Failed to delete price entry:', e)
    notifyError('Failed to delete price entry.')
  } finally {
    deletingEntryId.value = null
  }
}

onMounted(async () => {
  await loadGame()
  await loadPriceHistory()
})
</script>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 2rem;
}

.left-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

@media (max-width: 768px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 639px) {
  /* Cap cover height so info section is visible without scrolling */
  .cover-large {
    max-height: 260px;
    font-size: 4rem;
  }

  /* Title + actions: stack on very small screens */
  .detail-header {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }
}

.cover-card {
  position: relative;
  z-index: 2;
  border-radius: 1rem;
  border: 1px solid var(--glass-border);
  backdrop-filter: var(--card-blur);
  -webkit-backdrop-filter: var(--card-blur);
  box-shadow: var(--glass-shadow);
  padding: 1rem;
  background: var(--bg-light);
}

.cover-large {
  aspect-ratio: 3/4;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.05), rgba(0, 0, 0, 0.4));
  border-radius: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 6rem;
  position: relative;
  overflow: hidden;
  box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.3);
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: transparent;
  display: block;
}

.cover-remove-btn {
  position: absolute;
  top: 0.5rem;
  left: 0.5rem;
  background: rgba(0,0,0,0.55);
  backdrop-filter: blur(8px);
  color: #fff;
  border: 1px solid var(--glass-border);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: all 0.2s;
}

.cover-remove-btn:hover {
  background: rgba(239, 68, 68, 0.8);
  transform: scale(1.1);
}

.cover-upload-row {
  margin-top: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.cover-upload-btn {
  width: 100%;
}

.cover-upload-menu {
  position: relative;
}

.cover-upload-menu > summary {
  list-style: none;
}

.cover-upload-menu > summary::-webkit-details-marker {
  display: none;
}

.cover-upload-menu > summary.disabled {
  opacity: 0.65;
  pointer-events: none;
}

.cover-upload-menu-list {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 0.35rem);
  z-index: 20;
  background: var(--bg-light);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
  padding: 0.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.cover-upload-menu-item {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 0.85rem;
  padding: 0.42rem 0.5rem;
  border-radius: 0.35rem;
  cursor: pointer;
}

.cover-upload-menu-item:hover {
  background: var(--bg-lighter);
}

.cover-upload-menu-item:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cover-upload-error {
  font-size: 0.8rem;
  color: #ef4444;
}

.value-badge {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: var(--success);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-weight: bold;
  font-size: 1.25rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex-shrink: 0;
  justify-content: flex-end;
}

.actions-toolbar {
  margin-left: auto;
  justify-content: flex-end;
  align-items: flex-start;
  align-content: flex-start;
  row-gap: 0.35rem;
  column-gap: 0.35rem;
  max-width: 760px;
}

.actions-toolbar > * {
  min-width: 0;
}

.actions-toolbar .btn-compact {
  min-height: 28px !important;
  padding: 0.22rem 0.5rem !important;
  font-size: 0.72rem !important;
  gap: 0.28rem;
  line-height: 1.1;
  border-radius: 0.4rem;
  white-space: nowrap;
}

.items-start {
  align-items: flex-start;
}

.detail-title-block {
  min-width: 0;
}

.detail-title-block h1 {
  overflow-wrap: anywhere;
  line-height: 1.2;
}

.more-menu {
  position: relative;
}

.more-menu > summary {
  list-style: none;
}

.more-menu > summary::-webkit-details-marker {
  display: none;
}

.more-trigger {
  min-width: 2rem;
  justify-content: center;
  font-size: 0.9rem !important;
  padding-inline: 0.35rem !important;
}

.more-menu-list {
  position: absolute;
  right: 0;
  top: calc(100% + 0.35rem);
  min-width: 190px;
  background: var(--bg-light);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
  padding: 0.3rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  z-index: 25;
  max-width: min(88vw, 280px);
}

.more-menu-link {
  color: var(--text);
  text-decoration: none;
  font-size: 0.78rem;
  padding: 0.4rem 0.5rem;
  border-radius: 0.35rem;
}

.more-menu-link:hover {
  background: var(--bg-lighter);
}

.more-menu-btn {
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  cursor: pointer;
}

.more-menu-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cover-gallery-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.72);
  z-index: 120;
  display: grid;
  place-items: center;
  padding: 1rem;
}

.cover-gallery-modal {
  width: min(940px, 96vw);
  max-height: min(85vh, 900px);
  overflow: auto;
}

.cover-gallery-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.cover-gallery-close {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  border-radius: 0.35rem;
  width: 30px;
  height: 30px;
  cursor: pointer;
}

.cover-gallery-search {
  margin-bottom: 0.75rem;
}

.cover-gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.65rem;
}

.cover-gallery-item {
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: 0.45rem;
  overflow: hidden;
  text-align: left;
  padding: 0;
  color: var(--text);
  cursor: pointer;
  display: flex;
  flex-direction: column;
}

.cover-gallery-item img {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: contain;
  background: rgba(15, 23, 42, 0.7);
}

.cover-gallery-item span {
  font-size: 0.72rem;
  padding: 0.45rem 0.5rem 0.5rem;
  word-break: break-word;
}

.info-layout {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  min-width: 0; 
}

.info-cards-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

.chunk-card {
  background: var(--bg-light);
  border: 1px solid var(--glass-border);
  border-radius: 1rem;
  padding: 1.25rem;
  backdrop-filter: var(--card-blur);
  -webkit-backdrop-filter: var(--card-blur);
  box-shadow: var(--glass-shadow);
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}

.chunk-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.45);
  border-color: var(--glass-border-hover);
}

.chunk-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
  margin-top: 0;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px dashed var(--glass-border);
  letter-spacing: -0.01em;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.85rem;
}

.detail-item {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--glass-border);
  padding: 0.85rem;
  border-radius: 0.75rem;
  min-width: 0;
  overflow-wrap: anywhere;
  transition: transform 0.2s, background 0.2s;
}

.detail-item:hover {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.04);
  border-color: var(--glass-border-hover);
}

.detail-item label {
  display: block;
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.detail-item-pl {
  background: transparent !important;
  border: none !important;
  padding: 0.85rem 0 !important;
}

.detail-item-pl span {
  font-size: 1.15rem;
}

.pl-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0.85rem;
  border-radius: 2rem;
  font-weight: 700;
  margin-top: 0.25rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}

.pl-pill.profit {
  background: rgba(52, 211, 153, 0.15);
  color: #34d399;
  box-shadow: 0 0 12px rgba(52, 211, 153, 0.15);
  border: 1px solid rgba(52, 211, 153, 0.3);
}

.pl-pill.loss {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.notes {
  background: var(--bg-light);
  border: 1px solid var(--glass-border);
  padding: 1.25rem;
  border-radius: 1rem;
  backdrop-filter: var(--card-blur);
  -webkit-backdrop-filter: var(--card-blur);
  box-shadow: var(--glass-shadow);
}

.notes label {
  display: block;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px dashed var(--glass-border);
  letter-spacing: -0.01em;
}

.description-text {
  white-space: normal;
  line-height: 1.6;
  word-break: break-word;
  color: rgba(255,255,255,0.85);
}

.description-text :deep(a) {
  color: #93c5fd;
  text-decoration: underline;
}

.empty-chart-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1.5rem;
  text-align: center;
  background: rgba(0, 0, 0, 0.2);
  border: 1px dashed var(--glass-border);
  border-radius: 0.75rem;
}

.empty-chart-state .icon {
  font-size: 2.5rem;
  margin-bottom: 0.75rem;
  filter: drop-shadow(0 0 8px rgba(255,255,255,0.2));
}

.empty-chart-state h4 {
  font-size: 1.1rem;
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.empty-chart-state p {
  font-size: 0.85rem;
  color: var(--text-muted);
  max-width: 320px;
  margin: 0;
  line-height: 1.4;
}

/* Price section */
.price-section {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--glass-border);
  padding: 1rem;
  border-radius: 0.75rem;
}

.price-section > label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.price-cells {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.price-cell {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.p-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.p-val {
  font-size: 1.4rem;
  font-weight: bold;
}

.price-cell.relevant .p-val {
  color: var(--success);
}

.price-meta {
  margin-top: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.price-error {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #ef4444;
}

.price-catalog-help {
  margin-top: 0.45rem;
}

.price-warning {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #f59e0b;
}

.market-suggestion {
  margin-top: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: rgba(255, 255, 255, 0.03);
}

.market-suggestion-text {
  font-size: 0.9rem;
}

.market-match {
  margin-top: 0.3rem;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.market-suggestion-actions {
  margin-top: 0.6rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.start-value-row {
  margin-top: 0.6rem;
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.rawg-reference {
  margin-top: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
}

.rawg-title {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.rawg-stores {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.4rem;
}

.rawg-link {
  color: #93c5fd;
  text-decoration: underline;
  font-size: 0.85rem;
}

.price-chart-wrapper {
  margin-top: 1rem;
}

.price-chart-hint {
  margin-top: 0.75rem;
  font-size: 0.8rem;
}

.source-pill {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-left: 0.4rem;
  vertical-align: middle;
}
.source-pill.source-pricecharting { background: rgba(96,165,250,0.15); color: #60a5fa; }
.source-pill.source-manual        { background: rgba(52,211,153,0.15);  color: #34d399; }
.source-pill.source-ebay          { background: rgba(251,146,60,0.15);  color: #fb923c; }

.manual-entry {
  border-top: 1px solid var(--border, rgba(255,255,255,0.08));
  padding-top: 0.75rem;
}

.manual-entry-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.manual-entry-fields {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  align-items: flex-end;
}

.manual-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.manual-field input {
  width: 90px;
  padding: 0.35rem 0.5rem;
  font-size: 0.9rem;
}

.price-history-list {
  border-top: 1px solid var(--border, rgba(255,255,255,0.08));
  padding-top: 0.75rem;
}

.price-history-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.4rem 0;
  border-bottom: 1px dashed var(--border, rgba(255,255,255,0.08));
}

.price-history-row:last-child {
  border-bottom: 0;
}

.price-history-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  min-width: 0;
}

.price-history-date {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.price-history-value {
  font-size: 0.85rem;
}

/* ── Horizontal copy cards ── */
.copies-section {
  background: var(--bg-light);
  border: 1px solid var(--glass-border);
  border-radius: 1rem;
  padding: 1.25rem;
  backdrop-filter: var(--card-blur);
  -webkit-backdrop-filter: var(--card-blur);
  box-shadow: var(--glass-shadow);
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}

.copies-section:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.45);
  border-color: var(--glass-border-hover);
}

.copies-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  align-items: flex-start;
}

.copy-card {
  flex: 1 1 200px;
  min-width: 180px;
  max-width: 280px;
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--glass-border);
  border-radius: 0.75rem;
  padding: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.copy-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px 0 rgba(0, 0, 0, 0.35);
  border-color: var(--glass-border-hover);
}

.copy-card-add {
  background: transparent;
  border: 2px dashed var(--glass-border);
  cursor: pointer;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 0.35rem;
  transition: border-color 0.2s, color 0.2s;
  min-height: 90px;
}

.copy-card-add:hover {
  border-color: var(--primary, #6366f1);
  color: var(--text);
}

.copy-add-icon {
  font-size: 1.4rem;
  line-height: 1;
}

.copy-add-label {
  font-size: 0.8rem;
}

.copy-card-new {
  border-style: solid;
  border-color: var(--primary, #6366f1);
}

.copy-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.copy-card-num {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.copy-card-actions {
  display: flex;
  gap: 0.3rem;
}

.copy-card-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.15rem;
}

.copy-card-btns {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.copy-fields {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.copy-field {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.4rem;
  font-size: 0.82rem;
}

.copy-field-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.copy-card-notes {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-style: italic;
  border-top: 1px dashed var(--glass-border);
  padding-top: 0.4rem;
  margin-top: 0.1rem;
  word-break: break-word;
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

@media (max-width: 639px) {
  .copy-card {
    flex: 1 1 100%;
    max-width: none;
  }
}

@media (max-width: 639px) {
  .value-badge {
    top: 0.6rem;
    right: 0.6rem;
    font-size: 1rem;
    padding: 0.35rem 0.7rem;
  }

  .actions-toolbar {
    margin-left: 0;
    max-width: none;
    width: 100%;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .actions-toolbar .btn-compact,
  .actions-toolbar > .btn,
  .actions-toolbar > .more-menu {
    width: 100%;
    min-height: 34px !important;
    justify-content: center;
    text-align: center;
    white-space: normal;
  }

  .actions-toolbar > .btn-danger {
    grid-column: span 2;
  }

  .more-menu {
    width: 100%;
  }

  .more-menu > summary {
    width: 100%;
    display: inline-flex;
  }

  .more-menu-list {
    left: 0;
    right: 0;
    min-width: 0;
    max-width: none;
    width: 100%;
  }

  .details-grid {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }

  .detail-item {
    padding: 0.8rem;
  }

  .price-cells {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.5rem;
  }

  .price-cell {
    min-width: 0;
  }

  .p-val {
    font-size: 1.05rem;
  }

  .start-value-row {
    flex-direction: column;
    align-items: stretch;
  }

  .start-value-row .btn {
    width: 100%;
  }

  .market-suggestion-actions {
    flex-direction: column;
  }

  .market-suggestion-actions .btn {
    width: 100%;
  }

  .manual-entry-fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.6rem;
    align-items: stretch;
  }

  .manual-field input {
    width: 100%;
  }

  .manual-entry-fields > .btn {
    grid-column: span 2;
    width: 100%;
  }

  .price-history-row {
    flex-direction: column;
    align-items: stretch;
  }

  .price-history-row .btn {
    width: 100%;
  }
}

/* Baseline inline panel */
.baseline-panel {
  border: 1px solid var(--glass-border);
  border-radius: 0.6rem;
  padding: 1rem;
  background: rgba(0,0,0,0.18);
}

.baseline-section {
  border: 1px solid var(--glass-border);
  border-radius: 0.6rem;
  padding: 1rem;
}

.baseline-section-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.25rem;
}

.baseline-section-desc {
  font-size: 0.75rem;
}

.baseline-ref-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.baseline-ref-input {
  width: 110px;
}

.baseline-suggest-btns {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.baseline-suggest-btn {
  font-size: 0.68rem !important;
  padding: 0.2rem 0.45rem !important;
  min-height: 26px !important;
}

.baseline-copies-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.baseline-copy-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.6rem 0.75rem;
  background: rgba(0,0,0,0.18);
  border-radius: 0.45rem;
  border: 1px solid var(--glass-border);
}

.baseline-copy-info {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
  min-width: 120px;
}

.baseline-copy-num {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.baseline-copy-controls {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  flex: 1;
}

.baseline-copy-input {
  width: 100px;
}

.baseline-pick-select {
  flex: 1;
  min-width: 160px;
  max-width: 260px;
  font-size: 0.78rem;
  padding: 0.3rem 0.5rem;
  height: auto;
}

.copy-baseline-val {
  font-size: 0.82rem;
  color: #60a5fa;
}

.justify-end {
  justify-content: flex-end;
}
</style>
