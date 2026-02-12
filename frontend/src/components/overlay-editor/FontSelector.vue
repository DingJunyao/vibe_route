<template>
  <el-select :modelValue="modelValue" @update:modelValue="handleChange" size="small" :loading="isLoading">
    <el-option-group v-if="systemFonts.length > 0" label="系统字体">
      <el-option
        v-for="font in systemFonts"
        :key="font.id"
        :label="font.name"
        :value="font.id"
      />
    </el-option-group>
    <el-option-group v-if="adminFonts.length > 0" label="管理员字体">
      <el-option
        v-for="font in adminFonts"
        :key="font.id"
        :label="font.name"
        :value="font.id"
      />
    </el-option-group>
    <el-option-group v-if="userFonts.length > 0" label="我的字体">
      <el-option
        v-for="font in userFonts"
        :key="font.id"
        :label="font.name"
        :value="font.id"
      />
    </el-option-group>
  </el-select>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { overlayTemplateApi, type Font } from '@/api/overlayTemplate'
import type { FontListResponse } from '@/api/overlayTemplate'

interface Props {
  modelValue: string
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const fonts = ref<Font[]>([])
const isLoading = ref(false)

const systemFonts = computed(() => fonts.value.filter(f => f.type === 'system'))
const adminFonts = computed(() => fonts.value.filter(f => f.type === 'admin'))
const userFonts = computed(() => fonts.value.filter(f => f.type === 'user'))

const loadFonts = async () => {
  isLoading.value = true
  try {
    const response = await overlayTemplateApi.listFonts()
    fonts.value = response.items
  } catch (error) {
    console.error('加载字体列表失败:', error)
  } finally {
    isLoading.value = false
  }
}

const handleChange = (value: string) => {
  emit('update:modelValue', value)
}

onMounted(() => {
  loadFonts()
})
</script>
