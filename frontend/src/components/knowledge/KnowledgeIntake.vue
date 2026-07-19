<script setup>
import { onBeforeUnmount, ref } from 'vue';
import { analyzeKnowledgeImageApi, analyzeKnowledgeTextApi, importKnowledgeImageItemsApi } from '../../api.js';
import { TYPE_DEFINITIONS } from '../../drinks-database.js';

const emit = defineEmits(['message', 'prefill', 'refresh']);
const fileInput = ref(null);
const imageFile = ref(null);
const previewUrl = ref('');
const sourceType = ref('image_upload');
const pastedText = ref('');
const pasteStatus = ref('支持粘贴图片、拖入图片或直接粘贴文字。');
const pasteTone = ref('info');
const items = ref([]);
const analyzing = ref(false);
const staging = ref(false);
const types = Object.entries(TYPE_DEFINITIONS).map(([value, definition]) => ({ value, label: definition.label }));

onBeforeUnmount(clearPreview);

function setFile(file) {
  clearPreview();
  imageFile.value = file || null;
  items.value = [];
  if (file) previewUrl.value = URL.createObjectURL(file);
}

function selectFile(event) {
  setFile(event.target.files?.[0]);
}

function handlePaste(event) {
  const clipboardItem = Array.from(event.clipboardData?.items || []).find(item => item.type.startsWith('image/'));
  const file = clipboardItem?.getAsFile();
  if (!file) return;
  event.preventDefault();
  setFile(new File([file], file.name || `clipboard-${Date.now()}.png`, { type: file.type || 'image/png' }));
  setPasteStatus('已粘贴图片，可以开始识别。', 'success');
}

function handleDrop(event) {
  const file = Array.from(event.dataTransfer?.files || []).find(item => item.type.startsWith('image/'));
  if (!file) return;
  setFile(file);
  setPasteStatus('已放入图片，可以开始识别。', 'success');
}

async function analyzeImage() {
  if (!imageFile.value) {
    emit('message', { text: '请先选择一张图片', success: false });
    return;
  }
  analyzing.value = true;
  try {
    const data = await analyzeKnowledgeImageApi(imageFile.value, pastedText.value.trim());
    setItems(data.items || []);
    emit('message', { text: data.message || `识别完成：${items.value.length} 条`, success: items.value.length > 0 });
  } catch (error) {
    items.value = [];
    emit('message', { text: `图片识别失败：${error.message || '请确认后端与视觉模型配置'}`, success: false });
  } finally {
    analyzing.value = false;
  }
}

async function analyzeText() {
  const text = pastedText.value.trim();
  if (!text) {
    setPasteStatus('请先粘贴一段文字。', 'error');
    return;
  }
  analyzing.value = true;
  setPasteStatus('正在交给后端 Agent 识别文字...', 'info');
  try {
    const data = await analyzeKnowledgeTextApi(text, 'manual_text');
    setItems(data.items || []);
    if (!items.value.length) {
      setPasteStatus(data.message || '没有识别到可审核的饮品营养项。', 'error');
      return;
    }
    const first = items.value[0];
    emit('prefill', { brand: first.brand || '', name: first.name || '', type: first.type || 'coffee', rawEvidence: first.raw_evidence || text });
    setPasteStatus(`Agent 已识别 ${items.value.length} 条，请检查后加入审核。`, 'success');
  } catch (error) {
    items.value = [];
    setPasteStatus(`文字识别失败：${error.message || '请确认后端已启动'}`, 'error');
  } finally {
    analyzing.value = false;
  }
}

async function stageItems() {
  const selected = items.value.filter(item => item.selected && item.name.trim()).map(({ selected: _selected, ...item }) => ({
    ...item,
    brand: item.brand.trim() || null,
    name: item.name.trim(),
    volume: optionalNumber(item.volume),
    caffeine: optionalNumber(item.caffeine),
    sugar: optionalNumber(item.sugar),
  }));
  if (!selected.length) {
    emit('message', { text: '请选择至少一条识别结果', success: false });
    return;
  }
  staging.value = true;
  try {
    const data = await importKnowledgeImageItemsApi(selected, sourceType.value);
    const skipped = data.skipped?.length || 0;
    emit('message', { text: `已加入审核队列：${data.count || 0} 条${skipped ? `，跳过 ${skipped} 条` : ''}`, success: true });
    emit('refresh');
  } catch (error) {
    emit('message', { text: `批量加入审核失败：${error.message || '请确认后端已启动'}`, success: false });
  } finally {
    staging.value = false;
  }
}

function setItems(values) {
  items.value = values.map(item => ({ ...item, selected: true, brand: item.brand || '', name: item.name || '', type: item.type || 'coffee', volume: item.volume ?? '', caffeine: item.caffeine ?? '', sugar: item.sugar ?? '' }));
}

function clearAll() {
  pastedText.value = '';
  setFile(null);
  if (fileInput.value) fileInput.value.value = '';
  setPasteStatus('已清空粘贴内容。', 'info');
}

function clearPreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = '';
}

function setPasteStatus(text, tone) {
  pasteStatus.value = text;
  pasteTone.value = tone;
}

function optionalNumber(value) {
  if (value === '' || value == null) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

</script>

<template>
  <div class="image-acquisition-panel">
    <div class="image-upload-row">
      <div class="form-group flex-2"><label>上传菜单/营养表图片</label><input ref="fileInput" type="file" accept="image/*" @change="selectFile"></div>
      <div class="form-group flex-1"><label>图片来源</label><select v-model="sourceType"><option value="image_upload">普通图片</option><option value="official_image">官方图片</option><option value="nutrition_label_image">营养表图片</option><option value="community_screenshot">用户截图</option></select></div>
      <button type="button" class="btn btn-primary" :disabled="analyzing" @click="analyzeImage">{{ analyzing ? '识别中...' : '识别图片' }}</button>
    </div>
    <div class="acquisition-paste-panel" @paste="handlePaste" @dragover.prevent @drop.prevent="handleDrop">
      <div class="acquisition-paste-header"><div><h4>粘贴导入</h4><p>粘贴截图或文字，识别后可检查营养字段并加入审核。</p></div><button type="button" class="btn acquisition-paste-clear" @click="clearAll">清空</button></div>
      <textarea v-model="pastedText" rows="4" placeholder="例如：瑞幸咖啡 生椰拿铁 500ml 咖啡因 120mg 糖分 18g"></textarea>
      <div class="acquisition-paste-actions"><button type="button" class="btn btn-primary" :disabled="analyzing" @click="analyzeText">从文字生成审核项</button><span class="acquisition-paste-status" :class="pasteTone">{{ pasteStatus }}</span></div>
    </div>
    <div class="image-preview-grid">
      <div :class="previewUrl ? 'image-preview-box' : 'image-preview-empty'"><img v-if="previewUrl" :src="previewUrl" alt="上传图片预览"><template v-else>暂无图片</template></div>
      <div>
        <div class="section-header-row compact-row"><h4 class="subsection-title">识别结果</h4><button type="button" class="btn btn-primary" :disabled="!items.length || staging" @click="stageItems">{{ staging ? '提交中...' : '批量加入审核' }}</button></div>
        <div class="image-analysis-result">
          <div v-if="!items.length" class="acquisition-empty">暂无识别结果</div>
          <div v-else class="image-items-table-wrap"><table class="image-items-table"><thead><tr><th>选</th><th>品牌</th><th>饮品</th><th>类型</th><th>容量</th><th>咖啡因</th><th>糖分</th></tr></thead><tbody>
            <tr v-for="(item, index) in items" :key="index"><td><input v-model="item.selected" type="checkbox"></td><td><input v-model="item.brand"></td><td><input v-model="item.name"></td><td><select v-model="item.type"><option v-for="type in types" :key="type.value" :value="type.value">{{ type.label }}</option></select></td><td><input v-model="item.volume" type="number" placeholder="ml"></td><td><input v-model="item.caffeine" type="number" placeholder="mg"></td><td><input v-model="item.sugar" type="number" placeholder="未知"></td></tr>
          </tbody></table></div>
        </div>
      </div>
    </div>
  </div>
</template>
