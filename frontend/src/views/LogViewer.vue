<template>
  <div class="log-viewer">
    <el-header class="log-viewer-header">
      <div class="header-left">
        <el-button @click="$router.push('/home')" :icon="HomeFilled" />
        <h2>远程日志查看器</h2>
      </div>
      <div class="status" :class="{ connected: isConnected }">
        {{ isConnected ? '已连接' : '未连接' }}
      </div>
    </el-header>
    <el-card class="control-card">
      <div class="control-header">
        <h2>控制面板</h2>
      </div>
      <div class="control-buttons">
        <el-button type="primary" @click="connect" :disabled="isConnected">
          连接
        </el-button>
        <el-button @click="disconnect" :disabled="!isConnected">
          断开
        </el-button>
        <el-button @click="clearLogs">
          清空日志
        </el-button>
        <el-select v-model="levelFilter" placeholder="筛选级别" style="width: 120px; margin-left: 10px;">
          <el-option label="全部" value="" />
          <el-option label="日志" value="log" />
          <el-option label="信息" value="info" />
          <el-option label="警告" value="warn" />
          <el-option label="错误" value="error" />
        </el-select>
      </div>
      <div class="url-info">
        <span>手机端访问 URL 添加参数：<code>?remote-log</code></span>
      </div>
    </el-card>

    <el-card class="logs-card">
      <div class="logs-container" ref="logsContainer">
        <div v-if="filteredLogs.length === 0" class="empty">
          {{ isConnected ? '等待日志...' : '请先连接到日志服务器' }}
        </div>
        <div
          v-for="(log, index) in filteredLogs"
          :key="index"
          :class="['log-entry', `log-${log.level}`]"
        >
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <span v-if="log.tag" class="log-tag">{{ log.tag }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { HomeFilled } from '@element-plus/icons-vue'
import { getWebSocketUrl } from '@/utils/remoteLog'

interface LogEntry {
  level: string
  tag: string
  message: string
  timestamp: number
}

const ws = ref<WebSocket | null>(null)
const isConnected = ref(false)
const logs = ref<LogEntry[]>([])
const logsContainer = ref<HTMLElement>()
const levelFilter = ref('')

const filteredLogs = computed(() => {
  if (!levelFilter.value) return logs.value
  return logs.value.filter(log => log.level === levelFilter.value)
})

function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour12: false }) + '.' +
    date.getMilliseconds().toString().padStart(3, '0')
}

function connect() {
  if (ws.value) return

  const url = getWebSocketUrl()
  console.log('连接到日志服务器:', url)

  ws.value = new WebSocket(url)

  ws.value.onopen = () => {
    isConnected.value = true
    addLog('info', '[LogViewer]', '已连接到日志服务器')
  }

  ws.value.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.type === 'log') {
      addLog(msg.data.level, msg.data.tag, msg.data.message, msg.data.timestamp)
    }
  }

  ws.value.onclose = () => {
    isConnected.value = false
    ws.value = null
    addLog('warn', '[LogViewer]', '连接已断开')
  }

  ws.value.onerror = () => {
    addLog('error', '[LogViewer]', '连接错误')
  }
}

function disconnect() {
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }
}

function addLog(level: string, tag: string, message: string, timestamp?: number) {
  logs.value.push({
    level,
    tag,
    message,
    timestamp: timestamp ?? Date.now()
  })

  // 限制日志数量，避免内存溢出
  if (logs.value.length > 1000) {
    logs.value.splice(0, 100)
  }

  // 自动滚动到底部
  nextTick(() => {
    if (logsContainer.value) {
      logsContainer.value.scrollTop = logsContainer.value.scrollHeight
    }
  })
}

function clearLogs() {
  logs.value = []
}

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.log-viewer {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.log-viewer-header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  flex-shrink: 0;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
}

.log-viewer > .el-card {
  margin: 20px;
}

.control-card {
  margin-bottom: 20px;
}

.control-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.control-header h2 {
  margin: 0;
}

.status {
  padding: 4px 12px;
  border-radius: 4px;
  background: #f56c6c;
  color: white;
  font-size: 12px;
}

.status.connected {
  background: #67c23a;
}

.control-buttons {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.url-info {
  margin-top: 15px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}

.url-info code {
  padding: 2px 6px;
  background: #e6e8eb;
  border-radius: 3px;
  font-family: monospace;
}

.logs-card {
  height: calc(100vh - 220px);
  min-height: 400px;
}

.logs-container {
  height: 100%;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 10px;
  border-radius: 4px;
}

.empty {
  text-align: center;
  color: #6e7681;
  padding: 40px;
}

.log-entry {
  padding: 4px 8px;
  border-bottom: 1px solid #2d2d2d;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.5;
}

.log-entry:hover {
  background: #2a2a2a;
}

.log-time {
  color: #858585;
  flex-shrink: 0;
}

.log-tag {
  color: #4ec9b0;
  flex-shrink: 0;
  font-weight: bold;
}

.log-message {
  color: #d4d4d4;
  word-break: break-all;
}

.log-info .log-message {
  color: #4fc3f7;
}

.log-warn .log-message {
  color: #ffb74d;
}

.log-error .log-message {
  color: #f06292;
}

@media (max-width: 768px) {
  .log-viewer {
    padding: 10px;
  }

  .logs-card {
    height: calc(100vh - 280px);
  }
}
</style>
