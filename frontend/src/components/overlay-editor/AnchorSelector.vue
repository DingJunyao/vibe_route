<template>
  <el-select :modelValue="modelValue" @update:modelValue="handleChange" size="small">
    <el-option value="top-left" label="左上">
      <span class="anchor-option">
        <span class="anchor-icon">↖</span>
        <span>左上</span>
      </span>
    </el-option>
    <el-option value="top" label="上中">
      <span class="anchor-option">
        <span class="anchor-icon">↑</span>
        <span>上中</span>
      </span>
    </el-option>
    <el-option value="top-right" label="右上">
      <span class="anchor-option">
        <span class="anchor-icon">↗</span>
        <span>右上</span>
      </span>
    </el-option>
    <el-option value="left" label="左中">
      <span class="anchor-option">
        <span class="anchor-icon">←</span>
        <span>左中</span>
      </span>
    </el-option>
    <el-option value="center" label="中心">
      <span class="anchor-option">
        <span class="anchor-icon">⊙</span>
        <span>中心</span>
      </span>
    </el-option>
    <el-option value="right" label="右中">
      <span class="anchor-option">
        <span class="anchor-icon">→</span>
        <span>右中</span>
      </span>
    </el-option>
    <el-option value="bottom-left" label="左下">
      <span class="anchor-option">
        <span class="anchor-icon">↙</span>
        <span>左下</span>
      </span>
    </el-option>
    <el-option value="bottom" label="下中">
      <span class="anchor-option">
        <span class="anchor-icon">↓</span>
        <span>下中</span>
      </span>
    </el-option>
    <el-option value="bottom-right" label="右下">
      <span class="anchor-option">
        <span class="anchor-icon">↘</span>
        <span>右下</span>
      </span>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import type { ContainerAnchor } from '@/api/overlayTemplate'

interface Props {
  modelValue: ContainerAnchor
}

interface Emits {
  (e: 'update:modelValue', value: ContainerAnchor): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const handleChange = (value: ContainerAnchor) => {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.anchor-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.anchor-icon {
  display: inline-flex;
  width: 20px;
  justify-content: center;
  font-size: 16px;
}
</style>
