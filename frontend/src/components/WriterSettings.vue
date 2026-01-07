<template>
  <div class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8">
    <h2 class="text-2xl font-bold text-gray-800 mb-6">写作设置</h2>
    <form @submit.prevent="handleSave" class="space-y-6">
      <div>
        <label for="chapter_versions" class="block text-sm font-medium text-gray-700">
          章节版本数量
        </label>
        <p class="mt-1 text-sm text-gray-500">
          每次生成章节时产生的版本数量（1-10个版本）
        </p>
        <div class="mt-2">
          <input
            type="number"
            id="chapter_versions"
            v-model.number="config.chapter_versions"
            min="1"
            max="10"
            class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            placeholder="输入版本数量（1-10）"
          >
        </div>
        <p class="mt-2 text-sm text-gray-500">
          当前值：{{ config.chapter_versions }} 个版本
        </p>
      </div>
      <div class="flex justify-end space-x-4 pt-4">
        <button
          type="button"
          @click="handleDelete"
          class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          恢复默认
        </button>
        <button
          type="submit"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          保存
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { getWriterConfig, updateWriterConfig, deleteWriterConfig, type WriterConfig } from '@/api/writerConfig';

const config = ref<WriterConfig>({
  chapter_versions: 3,
});

onMounted(async () => {
  try {
    const existingConfig = await getWriterConfig();
    if (existingConfig) {
      config.value = existingConfig;
    }
  } catch (error) {
    console.error('获取写作配置失败:', error);
    // 使用默认值
    config.value = { chapter_versions: 3 };
  }
});

const handleSave = async () => {
  try {
    // 验证范围
    if (config.value.chapter_versions < 1 || config.value.chapter_versions > 10) {
      alert('版本数量必须在 1-10 之间！');
      return;
    }

    await updateWriterConfig(config.value);
    alert('设置已保存！');
  } catch (error) {
    console.error('保存写作配置失败:', error);
    alert('保存失败，请重试');
  }
};

const handleDelete = async () => {
  if (confirm('确定要恢复默认配置吗？恢复后将使用环境变量或系统默认值（3个版本）。')) {
    try {
      await deleteWriterConfig();
      // 重新加载配置
      const newConfig = await getWriterConfig();
      config.value = newConfig;
      alert('配置已恢复为默认值！');
    } catch (error) {
      console.error('恢复默认配置失败:', error);
      alert('恢复失败，请重试');
    }
  }
};
</script>
