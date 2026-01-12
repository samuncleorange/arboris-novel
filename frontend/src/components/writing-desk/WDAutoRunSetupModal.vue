<template>
  <div v-if="show" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-md flex flex-col">
      <!-- 模态框头部 -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200">
        <h3 class="text-xl font-bold text-gray-900 bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-indigo-600">
          一键自动写作设置
        </h3>
        <button
          @click="$emit('close')"
          class="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 模态框内容 -->
      <div class="p-6 space-y-4">
        <p class="text-gray-600 text-sm">
          AI 将自动为您生成后续章节，包括自动重试失败的步骤和选择最佳版本。您可以设置一个目标章节，AI 将在完成该章节后停止。
        </p>

        <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">自动停止目标</label>
            <select
              v-model="targetChapter"
              class="w-full px-3 py-2 bg-white border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
            >
              <!-- 仅列出当前进度及之后的章节 -->
              <option :value="-1">一直写到完结 (第 {{ maxChapter }} 章)</option>
              <option
                v-for="ch in availableChapters"
                :key="ch.chapter_number"
                :value="ch.chapter_number"
              >
                写到第 {{ ch.chapter_number }} 章 - {{ ch.title }}
              </option>
            </select>
        </div>

        <div class="bg-indigo-50 p-4 rounded-lg flex items-start gap-3">
          <svg class="w-5 h-5 text-indigo-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
          </svg>
          <div class="text-sm text-indigo-800">
            <p class="font-medium mb-1">提示</p>
            <p>您可以随时点击顶部的"停止写作"按钮手动作废任务。</p>
          </div>
        </div>
      </div>

      <!-- 模态框底部 -->
      <div class="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50 rounded-b-2xl">
        <button
          @click="$emit('close')"
          class="px-4 py-2 text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg transition-all"
        >
          取消
        </button>
        <button
          @click="handleStart"
          class="px-6 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"></path>
          </svg>
          开始自动写作
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { ChapterOutline } from '@/api/novel'

interface Props {
  show: boolean
  outlines: ChapterOutline[]
  startFromChapter: number
}

const props = defineProps<Props>()
const emit = defineEmits(['close', 'start'])

const targetChapter = ref<number>(-1)

const maxChapter = computed(() => {
  if (!props.outlines.length) return 0
  return Math.max(...props.outlines.map(o => o.chapter_number))
})

const availableChapters = computed(() => {
  return props.outlines
    .filter(o => o.chapter_number >= props.startFromChapter)
    .sort((a, b) => a.chapter_number - b.chapter_number)
})

const handleStart = () => {
  const actualTarget = targetChapter.value === -1 ? maxChapter.value : targetChapter.value
  emit('start', actualTarget)
}

// Reset selection when modal opens
watch(() => props.show, (newVal) => {
  if (newVal) {
    targetChapter.value = -1
  }
})
</script>
