<template>
  <el-select :modelValue="modelValue" @update:modelValue="handleChange" size="small">
    <el-option-group label="自定义">
      <el-option value="none" label="自定义文本" />
    </el-option-group>
    <el-option-group label="区域信息">
      <el-option value="province" label="省份" />
      <el-option value="city" label="城市" />
      <el-option value="district" label="区县" />
      <el-option value="province_en" label="省份（英文）" />
      <el-option value="city_en" label="城市（英文）" />
      <el-option value="district_en" label="区县（英文）" />
      <el-option value="region" label="区域（中文组合）" />
      <el-option value="region_en" label="区域（英文组合）" />
    </el-option-group>
    <el-option-group label="道路信息">
      <el-option value="road_number" label="道路编号" />
      <el-option value="road_name" label="道路名称" />
      <el-option value="road_name_en" label="道路英文名" />
    </el-option-group>
    <el-option-group label="运动数据">
      <el-option value="speed" label="速度" />
      <el-option value="elevation" label="海拔" />
      <el-option value="compass_angle" label="方位角" />
    </el-option-group>
    <el-option-group label="时间距离">
      <el-option value="elapsed_distance" label="已行驶距离" />
      <el-option value="elapsed_time" label="已用时间" />
      <el-option value="remain_distance" label="剩余距离" />
      <el-option value="remain_time" label="剩余时间" />
    </el-option-group>
    <el-option-group label="坐标时间">
      <el-option value="current_time" label="当前时间" />
      <el-option value="latitude" label="纬度" />
      <el-option value="longitude" label="经度" />
    </el-option-group>
  </el-select>
</template>

<script setup lang="ts">
import type { DataSource } from '@/api/overlayTemplate'

interface Props {
  modelValue: DataSource
}

interface Emits {
  (e: 'update:modelValue', value: DataSource): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const handleChange = (value: DataSource) => {
  emit('update:modelValue', value)
}
</script>
