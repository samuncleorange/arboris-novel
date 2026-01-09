<template>
  <div class="flex-shrink-0 z-30 bg-white/80 backdrop-blur-lg border-b border-gray-200 shadow-sm">
    <div class="px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- 左侧：项目信息 -->
        <div class="flex items-center gap-2 sm:gap-4 min-w-0">
          <button
            @click="$emit('goBack')"
            class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
          >
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L4.414 9H17a1 1 0 110 2H4.414l5.293 5.293a1 1 0 010 1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
          <div class="min-w-0">
            <h1 class="text-base sm:text-lg font-bold text-gray-900 truncate">{{ project?.title || '加载中...' }}</h1>
            <div class="hidden sm:flex items-center gap-2 md:gap-4 text-xs md:text-sm text-gray-600">
              <span>{{ project?.blueprint?.genre || '--' }}</span>
              <span class="hidden md:inline">•</span>
              <span class="hidden md:inline">{{ progress }}% 完成</span>
              <span class="hidden lg:inline">•</span>
              <span class="hidden lg:inline">{{ completedChapters }}/{{ totalChapters }} 章</span>
            </div>
          </div>
        </div>

        <!-- 右侧：操作按钮 -->
        <div class="flex items-center gap-1 sm:gap-2">
          <!-- 一键写作按钮 -->
          <button
            v-if="!isAutoRunning && !isAllChaptersCompleted && hasChapterOutline"
            @click="$emit('startAutoRun')"
            class="px-3 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg flex items-center gap-2 text-sm font-medium"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"></path>
            </svg>
            <span class="hidden sm:inline">一键写作</span>
          </button>

          <!-- 停止自动写作按钮 -->
          <button
            v-if="isAutoRunning"
            @click="$emit('stopAutoRun')"
            class="px-3 py-2 bg-gradient-to-r from-red-500 to-orange-500 text-white rounded-lg hover:from-red-600 hover:to-orange-600 transition-all shadow-md hover:shadow-lg flex items-center gap-2 text-sm font-medium animate-pulse"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clip-rule="evenodd"></path>
            </svg>
            <span class="hidden sm:inline">停止写作</span>
          </button>

          <!-- 已完成标识 -->
          <span
            v-if="isAllChaptersCompleted"
            class="px-3 py-2 bg-green-100 text-green-700 rounded-lg flex items-center gap-2 text-sm font-medium"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
            </svg>
            <span class="hidden sm:inline">已完成</span>
          </span>

          <div class="w-px h-6 bg-gray-300 hidden sm:block"></div>

          <button
            @click="$emit('viewProjectDetail')"
            class="p-2 sm:px-3 sm:py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path>
              <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path>
            </svg>
            <span class="hidden md:inline text-sm">项目详情</span>
          </button>
          <div class="w-px h-6 bg-gray-300 hidden sm:block"></div>
          <button
            @click="handleLogout"
            class="p-2 sm:px-3 sm:py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span class="hidden md:inline text-sm">退出登录</span>
          </button>
          <button
            @click="$emit('toggleSidebar')"
            class="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors lg:hidden"
          >
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"></path>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { NovelProject } from '@/api/novel'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

interface Props {
  project: NovelProject | null
  progress: number
  completedChapters: number
  totalChapters: number
  isAutoRunning?: boolean
  isAllChaptersCompleted?: boolean
}

const props = defineProps<Props>()

// 检查是否有章节大纲
const hasChapterOutline = computed(() => {
  return props.project?.blueprint?.chapter_outline && props.project.blueprint.chapter_outline.length > 0
})

defineEmits(['goBack', 'viewProjectDetail', 'toggleSidebar', 'startAutoRun', 'stopAutoRun'])
</script>
