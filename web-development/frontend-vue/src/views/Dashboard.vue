<template>
  <div>
    <header class="pt-10 pb-8 text-center">
      <div class="flex items-center justify-center gap-3">
        <span class="text-4xl">🍎</span>
        <h1 class="text-3xl md:text-4xl font-bold text-[#1d1d1f] tracking-tight">
          AI 기반 지능형 지역 마케팅 (Vue.js)
        </h1>
      </div>
    </header>

    <div class="max-w-4xl mx-auto px-6 pb-16">
      <section class="bg-white rounded-2xl p-8 mb-6 shadow-sm border border-gray-100">
        <h2 class="text-2xl font-bold text-[#1d1d1f] mb-2">AI 활용한 수요 매층 재고 추천 시스템</h2>
        <p class="text-[#6e6e73] text-base">
          AI 활용한 수요 매층 재고 추천 시스템
        </p>
      </section>

      <section class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h3 class="text-sm font-medium text-[#6e6e73] mb-4">모델 상태</h3>
          <div class="inline-flex items-center gap-2 px-4 py-3 bg-[#f5f5f7] rounded-xl">
            <span
              class="w-2.5 h-2.5 rounded-full"
              :class="loading ? 'bg-amber-500' : data ? 'bg-[#34c759]' : 'bg-amber-500'"
            />
            <span class="text-[#1d1d1f] font-medium">
              {{ loading ? '연결 중...' : data ? '예측 모델 연결됨' : '예측 모델 연결 대기 중' }}
            </span>
          </div>
          <p v-if="error" class="text-amber-600 text-sm mt-2">{{ error }}</p>
        </div>
        <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h3 class="text-sm font-medium text-[#6e6e73] mb-4">마지막 업데이트</h3>
          <p class="text-2xl font-bold text-[#1d1d1f]">{{ lastUpdated }}</p>
        </div>
      </section>

      <section class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
        <h3 class="text-base font-semibold text-[#1d1d1f] mb-4">Vue.js 기능</h3>
        <ul class="list-disc list-inside text-[#6e6e73] space-y-2">
          <li>Vue 3 Composition API + &lt;script setup&gt;</li>
          <li>Vue Router (라우팅)</li>
          <li>동일 백엔드 API 호출 (/api/apple-data)</li>
          <li>Tailwind CSS 스타일</li>
          <li>반응형 레이아웃</li>
        </ul>
      </section>

      <p class="text-center text-[#86868b] text-sm mt-8">백엔드 API와 실시간 연동 (Vue.js 프론트엔드)</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const data = ref<Record<string, unknown> | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const lastUpdated = ref('—')

async function fetchData() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/api/apple-data')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = await res.json()
    data.value = json
    lastUpdated.value = (json as { last_updated?: string }).last_updated ?? '—'
  } catch (e) {
    error.value = '백엔드 연결 실패'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>
