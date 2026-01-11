<template>
  <div class="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
    <WDHeader
      :project="project"
      :progress="progress"
      :completed-chapters="completedChapters"
      :total-chapters="totalChapters"
      :is-auto-running="isAutoRunning"
      :is-all-chapters-completed="isAllChaptersCompleted"
      :is-admin="isAdmin"
      @go-back="goBack"
      @view-project-detail="viewProjectDetail"
      @toggle-sidebar="toggleSidebar"
      @start-auto-run="startAutoRun"
      @stop-auto-run="stopAutoRun"
    />

    <!-- 主要内容区域 -->
    <div class="flex-1 w-full px-4 sm:px-6 lg:px-8 py-6 overflow-hidden">
      <!-- 加载状态 -->
      <div v-if="novelStore.isLoading" class="h-full flex justify-center items-center">
        <div class="text-center">
          <div class="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p class="text-gray-600">正在加载项目数据...</p>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="novelStore.error" class="text-center py-20">
        <div class="bg-red-50 border border-red-200 rounded-xl p-8 max-w-md mx-auto">
          <svg class="w-12 h-12 text-red-400 mx-auto mb-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
          </svg>
          <h3 class="text-lg font-semibold text-red-900 mb-2">加载失败</h3>
          <p class="text-red-700 mb-4">{{ novelStore.error }}</p>
          <button
            @click="loadProject"
            class="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            重新加载
          </button>
        </div>
      </div>

      <!-- 主要内容 -->
      <div v-else-if="project" class="h-full flex gap-6">
        <WDSidebar
          :project="project"
          :sidebar-open="sidebarOpen"
          :selected-chapter-number="selectedChapterNumber"
          :generating-chapter="generatingChapter"
          :evaluating-chapter="evaluatingChapter"
          :is-generating-outline="isGeneratingOutline"
          @close-sidebar="closeSidebar"
          @select-chapter="selectChapter"
          @generate-chapter="generateChapter"
          @edit-chapter="openEditChapterModal"
          @delete-chapter="deleteChapter"
          @generate-outline="generateOutline"
        />

        <div class="flex-1 min-w-0">
          <WDWorkspace
            :project="project"
            :selected-chapter-number="selectedChapterNumber"
          :generating-chapter="generatingChapter"
          :evaluating-chapter="evaluatingChapter"
          :show-version-selector="showVersionSelector"
          :chapter-generation-result="chapterGenerationResult"
          :selected-version-index="selectedVersionIndex"
          :available-versions="availableVersions"
          :is-selecting-version="isSelectingVersion"
          @regenerate-chapter="regenerateChapter"
          @evaluate-chapter="evaluateChapter"
          @hide-version-selector="hideVersionSelector"
          @update:selected-version-index="selectedVersionIndex = $event"
          @show-version-detail="showVersionDetail"
          @confirm-version-selection="confirmVersionSelection"
          @generate-chapter="generateChapter"
          @show-evaluation-detail="showEvaluationDetailModal = true"
          @fetch-chapter-status="fetchChapterStatus"
          @edit-chapter="editChapterContent"
          />
        </div>
      </div>
    </div>
    <WDVersionDetailModal
      :show="showVersionDetailModal"
      :detail-version-index="detailVersionIndex"
      :version="availableVersions[detailVersionIndex]"
      :is-current="isCurrentVersion(detailVersionIndex)"
      @close="closeVersionDetail"
      @select-version="selectVersionFromDetail"
    />
    <WDEvaluationDetailModal
      :show="showEvaluationDetailModal"
      :evaluation="selectedChapter?.evaluation || null"
      @close="showEvaluationDetailModal = false"
    />
    <WDEditChapterModal
      :show="showEditChapterModal"
      :chapter="editingChapter"
      @close="showEditChapterModal = false"
      @save="saveChapterChanges"
    />
    <WDGenerateOutlineModal
      :show="showGenerateOutlineModal"
      @close="showGenerateOutlineModal = false"
      @generate="handleGenerateOutline"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import type { Chapter, ChapterOutline, ChapterGenerationResponse, ChapterVersion } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import Tooltip from '@/components/Tooltip.vue'
import WDHeader from '@/components/writing-desk/WDHeader.vue'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import WDVersionDetailModal from '@/components/writing-desk/WDVersionDetailModal.vue'
import WDEvaluationDetailModal from '@/components/writing-desk/WDEvaluationDetailModal.vue'
import WDEditChapterModal from '@/components/writing-desk/WDEditChapterModal.vue'
import WDGenerateOutlineModal from '@/components/writing-desk/WDGenerateOutlineModal.vue'

interface Props {
  id: string
}

const props = defineProps<Props>()
const router = useRouter()
const novelStore = useNovelStore()
const authStore = useAuthStore()

// 管理员权限检查
const isAdmin = computed(() => authStore.user?.is_admin ?? false)

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const chapterGenerationResult = ref<ChapterGenerationResponse | null>(null)
const selectedVersionIndex = ref<number>(0)
const generatingChapter = ref<number | null>(null)
const isSelectingVersionLocal = ref(false)  // 本地状态，独立于 store，用于显示加载状态
const sidebarOpen = ref(false)
const showVersionDetailModal = ref(false)
const detailVersionIndex = ref<number>(0)
const showEvaluationDetailModal = ref(false)
const showEditChapterModal = ref(false)
const editingChapter = ref<ChapterOutline | null>(null)
const isGeneratingOutline = ref(false)
const showGenerateOutlineModal = ref(false)

// 一键写作状态
const isAutoRunning = ref(false)
const autoRunStopRequested = ref(false)
const isPageVisible = ref(true) // 页面可见性状态
const autoRunLogs = ref<string[]>([]) // 自动写作日志

// 计算属性
const project = computed(() => novelStore.currentProject)

const selectedChapter = computed(() => {
  if (!project.value || selectedChapterNumber.value === null) return null
  return project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const showVersionSelector = computed(() => {
  if (!selectedChapter.value) return false
  const status = selectedChapter.value.generation_status
  return status === 'waiting_for_confirm' || status === 'evaluating' || status === 'evaluation_failed' || status === 'selecting'
})

const evaluatingChapter = computed(() => {
  if (selectedChapter.value?.generation_status === 'evaluating') {
    return selectedChapter.value.chapter_number
  }
  return null
})

const isSelectingVersion = computed(() => {
  return isSelectingVersionLocal.value || selectedChapter.value?.generation_status === 'selecting'
})

const selectedChapterOutline = computed(() => {
  if (!project.value?.blueprint?.chapter_outline || selectedChapterNumber.value === null) return null
  return project.value.blueprint.chapter_outline.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const progress = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 0
  const totalChapters = project.value.blueprint.chapter_outline.length
  const completedChapters = project.value.chapters.filter(ch => ch.content).length
  return Math.round((completedChapters / totalChapters) * 100)
})

const totalChapters = computed(() => {
  return project.value?.blueprint?.chapter_outline?.length || 0
})

const completedChapters = computed(() => {
  return project.value?.chapters?.filter(ch => ch.content)?.length || 0
})

const isAllChaptersCompleted = computed(() => {
  return totalChapters.value > 0 && completedChapters.value >= totalChapters.value
})

const isCurrentVersion = (versionIndex: number) => {
  if (!selectedChapter.value?.content || !availableVersions.value?.[versionIndex]?.content) return false

  // 使用cleanVersionContent函数清理内容进行比较
  const cleanCurrentContent = cleanVersionContent(selectedChapter.value.content)
  const cleanVersionContentStr = cleanVersionContent(availableVersions.value[versionIndex].content)

  return cleanCurrentContent === cleanVersionContentStr
}

const cleanVersionContent = (content: string): string => {
  if (!content) return ''

  // 尝试解析JSON，看是否是完整的章节对象
  try {
    // 在解析 JSON 之前，先转义控制字符
    const escapedContent = content
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t')

    const parsed = JSON.parse(escapedContent)
    if (parsed && typeof parsed === 'object') {
      // 优先使用 full_content，其次是 content
      if (parsed.full_content) {
        content = parsed.full_content
      } else if (parsed.content) {
        content = parsed.content
      }
    }
  } catch (error) {
    // 如果不是JSON，继续处理字符串
  }

  // 去掉开头和结尾的引号
  let cleaned = content.replace(/^"|"$/g, '')

  // 处理转义字符 - 将转义序列还原为实际字符
  cleaned = cleaned.replace(/\\n/g, '\n')  // 换行符
  cleaned = cleaned.replace(/\\r/g, '\r')  // 回车符
  cleaned = cleaned.replace(/\\"/g, '"')   // 引号
  cleaned = cleaned.replace(/\\t/g, '\t')  // 制表符
  cleaned = cleaned.replace(/\\\\/g, '\\') // 反斜杠

  return cleaned
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!project.value?.blueprint?.chapter_outline) return false

  // 检查前面所有章节是否都已成功生成
  const outlines = project.value.blueprint.chapter_outline.sort((a, b) => a.chapter_number - b.chapter_number)
  
  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break
    
    const chapter = project.value?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false // 前面有章节未完成
    }
  }

  // 检查当前章节是否已经完成
  const currentChapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true // 已完成的章节可以重新生成
  }

  return true // 前面章节都完成了，可以生成当前章节
}

const isChapterFailed = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
  // waiting_for_confirm状态表示等待选择版本 = 进行中状态
  return chapter && chapter.generation_status === 'waiting_for_confirm'
}

// 可用版本列表 (合并生成结果和已有版本)
const availableVersions = computed(() => {
  // 优先使用新生成的版本（对象数组格式）
  if (chapterGenerationResult.value?.versions) {
    console.log('使用生成结果版本:', chapterGenerationResult.value.versions)
    return chapterGenerationResult.value.versions
  }

  // 使用章节已有的版本（字符串数组格式，需要转换为对象数组）
  if (selectedChapter.value?.versions && Array.isArray(selectedChapter.value.versions)) {
    console.log('原始章节版本 (字符串数组):', selectedChapter.value.versions)

    // 将字符串数组转换为ChapterVersion对象数组
    const convertedVersions = selectedChapter.value.versions.map((versionString, index) => {
      console.log(`版本 ${index} 原始字符串:`, versionString)

      try {
        // 解析JSON字符串
        const versionObj = JSON.parse(versionString)
        console.log(`版本 ${index} 解析后的对象:`, versionObj)

        // 提取content字段作为实际内容
        const actualContent = versionObj.content || versionString

        console.log(`版本 ${index} 实际内容:`, actualContent.substring(0, 100) + '...')

        return {
          content: actualContent,
          style: '标准' // 默认风格
        }
      } catch (error) {
        // 如果JSON解析失败，直接使用原始字符串
        console.log(`版本 ${index} JSON解析失败，使用原始字符串:`, error)
        return {
          content: versionString,
          style: '标准'
        }
      }
    })

    console.log('转换后的版本对象:', convertedVersions)
    return convertedVersions
  }

  console.log('没有可用版本，selectedChapter:', selectedChapter.value)
  return []
})


// 方法
const goBack = () => {
  router.push('/workspace')
}

const viewProjectDetail = () => {
  if (project.value) {
    router.push(`/detail/${project.value.id}`)
  }
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebar = () => {
  sidebarOpen.value = false
}

const loadProject = async () => {
  try {
    await novelStore.loadProject(props.id)
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const fetchChapterStatus = async () => {
  if (selectedChapterNumber.value === null) {
    return
  }
  try {
    await novelStore.loadChapter(selectedChapterNumber.value)
    console.log('Chapter status polled and updated.')
  } catch (error) {
    console.error('轮询章节状态失败:', error)
    // 在这里可以决定是否要通知用户轮询失败
  }
}


// 显示版本详情
const showVersionDetail = (versionIndex: number) => {
  detailVersionIndex.value = versionIndex
  showVersionDetailModal.value = true
}

// 关闭版本详情弹窗
const closeVersionDetail = () => {
  showVersionDetailModal.value = false
}

// 隐藏版本选择器，返回内容视图
const hideVersionSelector = () => {
  // Now controlled by computed property, but we can clear the generation result
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
}

const selectChapter = (chapterNumber: number) => {
  selectedChapterNumber.value = chapterNumber
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
  closeSidebar()
}

const generateChapter = async (chapterNumber: number) => {
  // 检查是否可以生成该章节
  if (!canGenerateChapter(chapterNumber) && !isChapterFailed(chapterNumber) && !hasChapterInProgress(chapterNumber)) {
    globalAlert.showError('请按顺序生成章节，先完成前面的章节', '生成受限')
    return
  }

  try {
    generatingChapter.value = chapterNumber
    selectedChapterNumber.value = chapterNumber

    // 在本地更新章节状态为generating
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'generating'
      } else {
        // If chapter does not exist, create a temporary one to show generating state
        const outline = project.value.blueprint?.chapter_outline?.find(o => o.chapter_number === chapterNumber)
        project.value.chapters.push({
          chapter_number: chapterNumber,
          title: outline?.title || '加载中...',
          summary: outline?.summary || '',
          content: '',
          versions: [],
          evaluation: null,
          generation_status: 'generating',
          word_count: 0
        } as Chapter)
      }
    }

    await novelStore.generateChapter(chapterNumber)

    // 强制刷新整个项目数据，确保状态同步
    await novelStore.loadProject(props.id, true)

    // 等待Vue响应式更新完成
    await nextTick()

    chapterGenerationResult.value = null
    selectedVersionIndex.value = 0
    generatingChapter.value = null
  } catch (error) {
    console.error('生成章节失败:', error)

    // 错误状态的本地更新仍然是必要的，以立即反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'failed'
      }
    }

    globalAlert.showError(`生成章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
    generatingChapter.value = null
    throw error // 重新抛出错误，让自动写作可以捕获
  }
}

const regenerateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    await generateChapter(selectedChapterNumber.value)
  }
}

const selectVersion = async (versionIndex: number) => {
  if (selectedChapterNumber.value === null || !availableVersions.value?.[versionIndex]?.content) {
    return
  }

  try {
    // 设置本地状态以立即显示加载界面
    isSelectingVersionLocal.value = true

    // 在本地立即更新状态以反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      if (chapter) {
        chapter.generation_status = 'selecting'
      }
    }

    selectedVersionIndex.value = versionIndex
    await novelStore.selectChapterVersion(selectedChapterNumber.value, versionIndex)

    // 轮询后端状态，直到 generation_status 从 'selecting' 变为 'successful'
    const POLL_INTERVAL = 1000 // 1秒轮询一次
    const MAX_POLL_TIME = 60000 // 最大轮询时间 60秒
    const startTime = Date.now()

    while (Date.now() - startTime < MAX_POLL_TIME) {
      // 刷新项目数据以获取最新状态
      await novelStore.loadProject(props.id, true)
      await nextTick()

      const chapter = project.value?.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      const currentStatus = chapter?.generation_status

      console.log(`[selectVersion] 轮询章节 ${selectedChapterNumber.value} 状态: ${currentStatus}`)

      // 检查状态是否已改变
      if (currentStatus === 'successful') {
        console.log(`[selectVersion] 章节 ${selectedChapterNumber.value} 版本选择成功`)
        isSelectingVersionLocal.value = false
        chapterGenerationResult.value = null
        globalAlert.showSuccess('版本已确认', '操作成功')
        return
      } else if (currentStatus === 'failed') {
        console.error(`[selectVersion] 章节 ${selectedChapterNumber.value} 版本选择失败`)
        isSelectingVersionLocal.value = false
        globalAlert.showError('版本选择失败，请重试', '选择失败')
        return
      }

      // 等待下一次轮询
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL))
    }

    // 超时处理
    console.error(`[selectVersion] 章节 ${selectedChapterNumber.value} 版本选择超时`)
    isSelectingVersionLocal.value = false
    
    // 恢复章节状态
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm'
      }
    }
    
    globalAlert.showError('版本选择超时，请刷新页面后重试', '操作超时')
  } catch (error) {
    console.error('[selectVersion] 选择章节版本失败:', error)
    // 清除本地加载状态
    isSelectingVersionLocal.value = false

    // 错误状态下恢复章节状态
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm'
      }
    }
    globalAlert.showError(`选择章节版本失败: ${error instanceof Error ? error.message : '未知错误'}`, '选择失败')
  }
}

// 从详情弹窗中选择版本
const selectVersionFromDetail = async () => {
  selectedVersionIndex.value = detailVersionIndex.value
  await selectVersion(detailVersionIndex.value)
  closeVersionDetail()
}

const confirmVersionSelection = async () => {
  await selectVersion(selectedVersionIndex.value)
}

const openEditChapterModal = (chapter: ChapterOutline) => {
  editingChapter.value = chapter
  showEditChapterModal.value = true
}

const saveChapterChanges = async (updatedChapter: ChapterOutline) => {
  try {
    await novelStore.updateChapterOutline(updatedChapter)
    globalAlert.showSuccess('章节大纲已更新', '保存成功')
  } catch (error) {
    console.error('更新章节大纲失败:', error)
    globalAlert.showError(`更新章节大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  } finally {
    showEditChapterModal.value = false
  }
}

const evaluateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    try {
      // 在本地更新章节状态为evaluating以立即反映在UI上
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter) {
          chapter.generation_status = 'evaluating'
        }
      }
      await novelStore.evaluateChapter(selectedChapterNumber.value)
      
      // 评审完成后，状态会通过store和轮询更新，这里不需要额外操作
      globalAlert.showSuccess('章节评审结果已生成', '评审成功')
    } catch (error) {
      console.error('评审章节失败:', error)
      
      // 错误状态下恢复章节状态
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter) {
          chapter.generation_status = 'successful' // 恢复为成功状态
        }
      }
      
      globalAlert.showError(`评审章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '评审失败')
    }
  }
}

const deleteChapter = async (chapterNumbers: number | number[]) => {
  const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
  const confirmationMessage = numbersToDelete.length > 1
    ? `您确定要删除选中的 ${numbersToDelete.length} 个章节吗？这个操作无法撤销。`
    : `您确定要删除第 ${numbersToDelete[0]} 章吗？这个操作无法撤销。`

  if (window.confirm(confirmationMessage)) {
    try {
      await novelStore.deleteChapter(numbersToDelete)
      globalAlert.showSuccess('章节已删除', '操作成功')
      // If the currently selected chapter was deleted, unselect it
      if (selectedChapterNumber.value && numbersToDelete.includes(selectedChapterNumber.value)) {
        selectedChapterNumber.value = null
      }
    } catch (error) {
      console.error('删除章节失败:', error)
      globalAlert.showError(`删除章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '删除失败')
    }
  }
}

const generateOutline = async () => {
  showGenerateOutlineModal.value = true
}

const editChapterContent = async (data: { chapterNumber: number, content: string }) => {
  if (!project.value) return

  try {
    await novelStore.editChapterContent(project.value.id, data.chapterNumber, data.content)
    globalAlert.showSuccess('章节内容已更新', '保存成功')
  } catch (error) {
    console.error('编辑章节内容失败:', error)
    globalAlert.showError(`编辑章节内容失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}

const handleGenerateOutline = async (numChapters: number) => {
  if (!project.value) return
  isGeneratingOutline.value = true
  try {
    const startChapter = (project.value.blueprint?.chapter_outline?.length || 0) + 1
    await novelStore.generateChapterOutline(startChapter, numChapters)
    globalAlert.showSuccess('新的章节大纲已生成', '操作成功')
  } catch (error) {
    console.error('生成大纲失败:', error)
    globalAlert.showError(`生成大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  } finally {
    isGeneratingOutline.value = false
  }
}

// ==================== 一键写作功能 ====================

// 最大重试次数
const MAX_RETRIES = 3
const RETRY_DELAY = 2000 // 2秒后重试

// 获取下一个需要生成的章节号
const getNextChapterToGenerate = (): number | null => {
  if (!project.value?.blueprint?.chapter_outline) return null

  const outlines = project.value.blueprint.chapter_outline
    .slice()
    .sort((a, b) => a.chapter_number - b.chapter_number)

  for (const outline of outlines) {
    const chapter = project.value.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    // 如果章节不存在，或者状态不是 successful，则需要生成
    if (!chapter || chapter.generation_status !== 'successful') {
      // 如果状态是 waiting_for_confirm，需要先选择版本
      if (chapter?.generation_status === 'waiting_for_confirm') {
        return outline.chapter_number
      }
      // 如果状态是其他（not_generated, failed 等），需要生成
      if (!chapter || chapter.generation_status === 'not_generated' || chapter.generation_status === 'failed') {
        return outline.chapter_number
      }
    }
  }
  return null // 所有章节都已完成
}

// 自动选择版本（选择第一个版本）
const autoSelectVersion = async (chapterNumber: number): Promise<boolean> => {
  let retries = 0
  while (retries < MAX_RETRIES) {
    try {
      selectedChapterNumber.value = chapterNumber
      await nextTick()

      // 等待数据刷新
      await novelStore.loadProject(props.id, true)
      await nextTick()

      const chapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
      if (!chapter || chapter.generation_status !== 'waiting_for_confirm') {
        console.log(`[AutoRun] 章节 ${chapterNumber} 不需要选择版本，状态: ${chapter?.generation_status}`)
        return true
      }

      // 自动选择第一个版本
      if (project.value?.chapters) {
        const ch = project.value.chapters.find(c => c.chapter_number === chapterNumber)
        if (ch) {
          ch.generation_status = 'selecting'
        }
      }

      await novelStore.selectChapterVersion(chapterNumber, 0)

      // 等待版本选择完成
      await new Promise(resolve => setTimeout(resolve, 2000))

      // 刷新项目数据
      await novelStore.loadProject(props.id, true)
      await nextTick()

      const updatedChapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
      if (updatedChapter?.generation_status === 'successful') {
        console.log(`[AutoRun] 章节 ${chapterNumber} 版本选择成功`)
        return true
      } else if (updatedChapter?.generation_status === 'waiting_for_confirm') {
        console.log(`[AutoRun] 章节 ${chapterNumber} 版本选择后仍需确认，重试 (${retries + 1}/${MAX_RETRIES})`)
        retries++
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
      } else {
        console.log(`[AutoRun] 章节 ${chapterNumber} 版本选择完成，状态: ${updatedChapter?.generation_status}`)
        return true
      }
    } catch (error) {
      console.error(`[AutoRun] 自动选择版本失败 (章节 ${chapterNumber}, 尝试 ${retries + 1}/${MAX_RETRIES}):`, error)
      retries++
      if (retries >= MAX_RETRIES) {
        return false
      }
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
    }
  }
  
  console.error(`[AutoRun] 章节 ${chapterNumber} 版本选择最终失败`)
  return false
}

// 生成单个章节（带重试）
const generateSingleChapter = async (chapterNumber: number): Promise<boolean> => {
  let retries = 0
  while (retries < MAX_RETRIES) {
    try {
      console.log(`[AutoRun] 开始生成章节 ${chapterNumber} (尝试 ${retries + 1}/${MAX_RETRIES})`)
      await generateChapter(chapterNumber)

      // 生成完成后，等待状态更新
      await new Promise(resolve => setTimeout(resolve, 2000))

      // 检查状态
      await novelStore.loadProject(props.id, true)
      await nextTick()

      const chapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
      const status = chapter?.generation_status

      console.log(`[AutoRun] 章节 ${chapterNumber} 生成完成，状态: ${status}`)

      if (status === 'waiting_for_confirm') {
        return true // 成功，需要选择版本
      } else if (status === 'failed') {
        console.log(`[AutoRun] 章节 ${chapterNumber} 生成失败，重试 (${retries + 1}/${MAX_RETRIES})`)
        retries++
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
      } else if (status === 'successful') {
        return true // 已经是成功状态
      } else {
        // 等待状态
        console.log(`[AutoRun] 章节 ${chapterNumber} 状态: ${status}，继续等待...`)
        await new Promise(resolve => setTimeout(resolve, 3000))
      }
    } catch (error) {
      console.error(`[AutoRun] 生成章节 ${chapterNumber} 失败 (尝试 ${retries + 1}/${MAX_RETRIES}):`, error)
      retries++
      if (retries >= MAX_RETRIES) {
        return false
      }
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
    }
  }
  
  console.error(`[AutoRun] 章节 ${chapterNumber} 生成最终失败`)
  return false
}

// 一键写作主方法（仅管理员可用）
const startAutoRun = async () => {
  // 权限检查
  if (!isAdmin.value) {
    globalAlert.showError('此功能仅管理员可用', '权限不足')
    return
  }

  if (isAutoRunning.value) return

  if (!project.value?.blueprint?.chapter_outline?.length) {
    globalAlert.showError('请先生成章节大纲', '无法开始')
    return
  }

  isAutoRunning.value = true
  autoRunStopRequested.value = false

  console.log('[AutoRun] ========== 启动一键写作 ==========')
  console.log(`[AutoRun] 页面可见性: ${isPageVisible.value ? '可见' : '隐藏'}`)
  console.log(`[AutoRun] 最大重试次数: ${MAX_RETRIES}`)
  console.log(`[AutoRun] 重试延迟: ${RETRY_DELAY}ms`)
  globalAlert.showSuccess('一键写作已启动，将自动完成所有章节', '开始写作')

  try {
    let currentChapter = getNextChapterToGenerate()
    let loopCount = 0
    const MAX_LOOPS = 1000 // 防止无限循环
    let stuckDetection = { chapter: null as number | null, status: null as string | null, count: 0 }

    while (!autoRunStopRequested.value && currentChapter !== null && loopCount < MAX_LOOPS) {
      loopCount++

      console.log(`[AutoRun] ---------- 循环 ${loopCount} ----------`)
      console.log(`[AutoRun] 当前处理章节: ${currentChapter}`)
      
      selectedChapterNumber.value = currentChapter

      const chapter = project.value?.chapters.find(ch => ch.chapter_number === currentChapter)
      const currentStatus = chapter?.generation_status

      // 卡住检测：如果同一章节和状态持续多次，抛出错误
      if (stuckDetection.chapter === currentChapter && stuckDetection.status === currentStatus) {
        stuckDetection.count++
        console.log(`[AutoRun] 检测到相同状态 ${stuckDetection.count} 次: 章节 ${currentChapter}, 状态 ${currentStatus}`)
        
        if (stuckDetection.count >= 5) {
          console.error(`[AutoRun] 检测到章节 ${currentChapter} 卡住，状态持续为 ${currentStatus}`)
          globalAlert.showError(`章节 ${currentChapter} 卡住，状态持续为 ${currentStatus}，自动写作暂停`, '检测到卡住')
          break
        }
      } else {
        stuckDetection = { chapter: currentChapter, status: currentStatus || null, count: 1 }
      }

      // 检查章节状态
      if (chapter?.generation_status === 'waiting_for_confirm') {
        console.log(`[AutoRun] 章节 ${currentChapter} 需要选择版本`)
        const success = await autoSelectVersion(currentChapter)
        if (!success) {
          console.error(`[AutoRun] 章节 ${currentChapter} 版本选择失败`)
          globalAlert.showError(`章节 ${currentChapter} 版本选择失败，自动写作暂停`, '选择失败')
          break
        }
        console.log(`[AutoRun] 章节 ${currentChapter} 版本选择完成`)
        currentChapter = getNextChapterToGenerate()
      } else if (!chapter || chapter.generation_status === 'not_generated' || chapter.generation_status === 'failed') {
        console.log(`[AutoRun] 章节 ${currentChapter} 需要生成`)
        const success = await generateSingleChapter(currentChapter)
        if (!success) {
          console.error(`[AutoRun] 章节 ${currentChapter} 生成失败`)
          globalAlert.showError(`章节 ${currentChapter} 生成失败，自动写作暂停`, '生成失败')
          break
        }
        // 生成成功后，重新检查是否需要选择版本
        await novelStore.loadProject(props.id, true)
        await nextTick()
        currentChapter = getNextChapterToGenerate()
      } else if (chapter?.generation_status === 'successful') {
        console.log(`[AutoRun] 章节 ${currentChapter} 已完成，跳过`)
        currentChapter = getNextChapterToGenerate()
      } else {
        // 等待其他状态完成
        console.log(`[AutoRun] 章节 ${currentChapter} 当前状态: ${chapter?.generation_status}，等待...`)
        
        // 根据页面可见性调整延迟
        const delay = isPageVisible.value ? 1000 : 5000
        console.log(`[AutoRun] 延迟 ${delay}ms (页面${isPageVisible.value ? '可见' : '隐藏'})`)
        
        await new Promise(resolve => setTimeout(resolve, delay))
        await novelStore.loadProject(props.id, true)
        await nextTick()
      }

      // 根据页面可见性调整延迟
      const loopDelay = isPageVisible.value ? 1000 : 5000
      console.log(`[AutoRun] 循环延迟 ${loopDelay}ms (页面${isPageVisible.value ? '可见' : '隐藏'})`)
      await new Promise(resolve => setTimeout(resolve, loopDelay))
    }

    if (currentChapter === null) {
      console.log('[AutoRun] ========== 所有章节已完成写作 ==========')
      globalAlert.showSuccess('所有章节已完成写作！', '写作完成')
    } else if (loopCount >= MAX_LOOPS) {
      console.error('[AutoRun] ========== 自动写作达到最大循环次数 ==========')
      globalAlert.showError('自动写作达到最大循环次数，已暂停', '超时停止')
    }
  } catch (error) {
    console.error('[AutoRun] ========== 自动写作过程出错 ==========')
    console.error('[AutoRun] 错误:', error)
    globalAlert.showError(`自动写作出现错误: ${error instanceof Error ? error.message : '未知错误'}`, '出错')
  } finally {
    console.log('[AutoRun] ========== 停止一键写作 ==========')
    isAutoRunning.value = false
    autoRunStopRequested.value = false
  }
}

// 停止一键写作
const stopAutoRun = () => {
  if (isAutoRunning.value) {
    console.log('[AutoRun] 收到停止请求')
    autoRunStopRequested.value = true
    globalAlert.showSuccess('正在停止自动写作...', '停止中')
  }
}

onMounted(() => {
  loadProject()
  
  // 监听页面可见性变化
  if (typeof document !== 'undefined') {
    const handleVisibilityChange = () => {
      isPageVisible.value = !document.hidden
      if (!isPageVisible.value) {
        console.log('[AutoRun] 页面进入后台，降低自动写作刷新频率')
      } else {
        console.log('[AutoRun] 页面回到前台，恢复自动写作刷新频率')
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    
    // 存储清理函数
    ;(window as any).__cleanupVisibilityHandler = () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }
})
</script>

<style scoped>
/* 自定义样式 */
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}

/* 动画效果 */
.fade-in {
  animation: fadeIn 0.6s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
