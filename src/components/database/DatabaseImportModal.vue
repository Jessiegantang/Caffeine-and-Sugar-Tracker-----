<script setup>
import { ref } from 'vue';

const props = defineProps({ open: Boolean, importer: { type: Function, required: true } });
const emit = defineEmits(['close']);
const fileInput = ref(null);
const file = ref(null);
const status = ref('');
const tone = ref('');
const importing = ref(false);

function selectFile(event) {
  file.value = event.target.files?.[0] || null;
  status.value = '';
}

async function executeImport() {
  if (!file.value || importing.value) return;
  importing.value = true;
  status.value = '导入中...';
  tone.value = '';
  try {
    const result = await props.importer(await file.value.text());
    status.value = result.message;
    tone.value = result.success ? 'success' : 'error';
  } catch (error) {
    status.value = error.message || '导入失败';
    tone.value = 'error';
  } finally {
    importing.value = false;
  }
}
</script>

<template>
  <div v-if="open" class="modal-overlay" style="display: flex" @click.self="emit('close')">
    <div class="modal-content">
      <div class="modal-header"><h3>批量导入饮品</h3><button type="button" class="modal-close-btn" aria-label="关闭" @click="emit('close')">×</button></div>
      <div class="import-content">
        <div class="import-format-info"><h4>CSV 文件格式</h4><p>首行为表头，后续列顺序为：类型、品牌、名称、咖啡因(mg)、糖分(g)、容量(ml)。文件请使用 UTF-8 编码。</p></div>
        <div class="import-upload">
          <input ref="fileInput" type="file" accept=".csv,text/csv" style="display: none" @change="selectFile">
          <button type="button" class="btn btn-primary" @click="fileInput?.click()">选择 CSV 文件</button>
          <div class="import-filename">{{ file?.name || '' }}</div>
          <button type="button" class="btn btn-success" :disabled="!file || importing" @click="executeImport">{{ importing ? '导入中...' : '开始导入' }}</button>
          <div class="import-result" :class="tone">{{ status }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
