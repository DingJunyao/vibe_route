<template>
  <div ref="editorRef" class="codemirror-yaml-editor"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import { EditorView, basicSetup } from 'codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'
import { linter, Diagnostic } from '@codemirror/lint'
import { Compartment } from '@codemirror/state'

interface Props {
  modelValue: string
  readonly?: boolean
  theme?: 'light' | 'dark'
  minHeight?: string
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false,
  theme: 'light',
  minHeight: '400px'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'valid', isValid: boolean, errors: string[]): void
}>()

const editorRef = ref<HTMLElement>()
let editorView: EditorView | null = null
const themeCompartment = new Compartment()

// YAML 语法校验
const yamlLinter = linter((view) => {
  const diagnostics: Diagnostic[] = []
  const content = view.state.doc.toString()
  const lines = content.split('\n')

  let currentKey = ''
  let currentLine = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // 跳过空行和注释
    if (!trimmed || trimmed.startsWith('#')) {
      continue
    }

    // 检查 YAML 键值对格式
    if (trimmed.includes(':')) {
      const colonIndex = trimmed.indexOf(':')
      const key = trimmed.substring(0, colonIndex).trim()
      const value = trimmed.substring(colonIndex + 1).trim()

      // 检查键是否为空
      if (!key) {
        diagnostics.push({
          from: view.state.doc.line(i + 1).from,
          to: view.state.doc.line(i + 1).to,
          severity: 'error',
          message: '键不能为空'
        })
        continue
      }

      // 检查值是否为空（允许空值，但给出警告）
      if (!value) {
        diagnostics.push({
          from: view.state.doc.line(i + 1).from,
          to: view.state.doc.line(i + 1).to,
          severity: 'warning',
          message: '值为空'
        })
      }

      // 检查是否包含中文字符（建议）
      const hasChinese = /[\u4e00-\u9fa5]/.test(key)
      if (!hasChinese) {
        diagnostics.push({
          from: view.state.doc.line(i + 1).from,
          to: view.state.doc.line(i + 1).to,
          severity: 'info',
          message: '建议使用中文键名'
        })
      }

      currentKey = key
      currentLine = i
    } else if (trimmed && !trimmed.startsWith('#')) {
      // 非 KV 对的文本
      diagnostics.push({
        from: view.state.doc.line(i + 1).from,
        to: view.state.doc.line(i + 1).to,
        severity: 'error',
        message: '无效的 YAML 格式，应为 "键: 值"'
      })
    }
  }

  // 触发校验事件
  const errors = diagnostics
    .filter(d => d.severity === 'error')
    .map(d => d.message)
  emit('valid', errors.length === 0, errors)

  return diagnostics
})

onMounted(() => {
  if (!editorRef.value) return

  // 创建编辑器
  editorView = new EditorView({
    doc: props.modelValue,
    extensions: [
      basicSetup,
      yaml(),
      yamlLinter,
      themeCompartment.of(props.theme === 'dark' ? oneDark : []),
      EditorView.theme({
        '&': {
          minHeight: props.minHeight,
          fontSize: '14px',
          fontFamily: 'Consolas, Monaco, "Courier New", monospace'
        },
        '.cm-scroller': {
          overflow: 'auto',
          borderRadius: '4px'
        },
        '.cm-content': {
          padding: '12px'
        },
        '.cm-focused': {
          outline: 'none'
        },
        '.cm-line': {
          padding: '0 0'
        },
        // 错误样式
        '.cm-diagnostic': {
          padding: '3px 6px',
          marginLeft: '-6px'
        },
        '.cm-diagnostic-error': {
          borderLeft: '3px solid #f56c6c'
        },
        '.cm-diagnostic-warning': {
          borderLeft: '3px solid #e6a23c'
        },
        '.cm-diagnostic-info': {
          borderLeft: '3px solid #909399'
        }
      }),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const newValue = update.state.doc.toString()
          emit('update:modelValue', newValue)
        }
      }),
      // 只读模式
      EditorView.editable.of(!props.readonly)
    ],
    parent: editorRef.value
  })
})

// 监听 modelValue 变化
watch(() => props.modelValue, (newValue) => {
  if (editorView && newValue !== editorView.state.doc.toString()) {
    editorView.dispatch({
      changes: {
        from: 0,
        to: editorView.state.doc.length,
        insert: newValue
      }
    })
  }
})

// 监听主题变化
watch(() => props.theme, (newTheme) => {
  if (editorView) {
    editorView.dispatch({
      effects: themeCompartment.reconfigure(newTheme === 'dark' ? oneDark : [])
    })
  }
})

// 监听只读状态变化
watch(() => props.readonly, (readonly) => {
  // CodeMirror 6 的只读状态需要重建编辑器或使用复杂的状态更新
  // 简单起见，这里通过 CSS 禁用编辑
  if (editorView) {
    editorView.contentDOM.setAttribute('contenteditable', readonly ? 'false' : 'true')
  }
})

onBeforeUnmount(() => {
  editorView?.destroy()
})
</script>

<style scoped>
.codemirror-yaml-editor {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  transition: border-color 0.2s;
}

.codemirror-yaml-editor:focus-within {
  border-color: var(--el-color-primary);
}

.codemirror-yaml-editor :deep(.cm-scroller) {
  font-family: Consolas, Monaco, 'Courier New', monospace;
  line-height: 1.6;
}

.codemirror-yaml-editor :deep(.cm-gutters) {
  background-color: var(--el-fill-color-light);
  border-right: 1px solid var(--el-border-color);
}

.codemirror-yaml-editor :deep(.cm-activeLineGutter) {
  background-color: var(--el-fill-color);
}

.codemirror-yaml-editor :deep(.cm-activeLine) {
  background-color: var(--el-fill-color-lighter);
}

.codemirror-yaml-editor :deep(.cm-selectionBackground) {
  background-color: var(--el-color-primary-light-9);
}

/* 语法高亮颜色（浅色主题） */
.codemirror-yaml-editor :deep(.cm-keyword) {
  color: #0000ff;
  font-weight: bold;
}

.codemirror-yaml-editor :deep(.cm-atom) {
  color: #219fe3;
}

.codemirror-yaml-editor :deep(.cm-number) {
  color: #164;
}

.codemirror-yaml-editor :deep(.cm-string) {
  color: #a11;
}

.codemirror-yaml-editor :deep(.cm-string-2) {
  color: #a50;
}

.codemirror-yaml-editor :deep(.cm-property) {
  color: #00c;
}

.codemirror-yaml-editor :deep(.cm-variable) {
  color: #000;
}

.codemirror-yaml-editor :deep(.cm-variable-2) {
  color: #0050a0;
}

.codemirror-yaml-editor :deep(.cm-comment) {
  color: #999;
  font-style: italic;
}

.codemirror-yaml-editor :deep(.cm-def) {
  color: #00c;
}

.codemirror-yaml-editor :deep(.cm-meta) {
  color: #555;
}

.codemirror-yaml-editor :deep(.cm-qualifier) {
  color: #555;
}

.codemirror-yaml-editor :deep(.cm-builtin) {
  color: #30a;
}

.codemirror-yaml-editor :deep(.cm-bracket) {
  color: #997;
}

.codemirror-yaml-editor :deep(.cm-tag) {
  color: #170;
}

.codemirror-yaml-editor :deep(.cm-error) {
  color: #f00;
}

.codemirror-yaml-editor :deep(.cm-invalidchar) {
  color: #f00;
}
</style>
