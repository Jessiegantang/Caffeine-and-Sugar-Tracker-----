<script setup>
import { computed, ref } from 'vue';

const props = defineProps({ candidates: { type: Array, default: () => [] }, evidence: { type: Array, default: () => [] }, loading: Boolean });
const emit = defineEmits(['approve', 'approve-many', 'delete-candidate', 'delete-candidates', 'delete-evidence', 'delete-evidence-many']);
const selectedCandidates = ref([]);
const selectedEvidence = ref([]);

const candidateRows = computed(() => props.candidates.map(candidate => ({ candidate, evidence: props.evidence.filter(row => row.candidate_id === candidate.id) })));
const orphanEvidence = computed(() => props.evidence.filter(row => !props.candidates.some(candidate => candidate.id === row.candidate_id)));

function sourceGroups(rows) {
  const groups = new Map();
  rows.forEach(row => {
    const key = [row.source_type || 'manual', row.source_url || '', row.raw_evidence || ''].join('|');
    if (!groups.has(key)) groups.set(key, { key, source_type: row.source_type, source_url: row.source_url, rows: [] });
    groups.get(key).rows.push(row);
  });
  return Array.from(groups.values());
}

function selectGroup(rows, checked) {
  const ids = new Set(selectedEvidence.value);
  rows.forEach(row => checked ? ids.add(row.id) : ids.delete(row.id));
  selectedEvidence.value = Array.from(ids);
}

function groupChecked(rows) {
  return rows.length > 0 && rows.every(row => selectedEvidence.value.includes(row.id));
}

function typeLabel(type) {
  return ({ coffee: '咖啡', teacoffee: '茶咖', tea: '原叶茶', milktea: '奶茶', milk_tea: '奶茶', fruittea: '果茶', fruit_tea: '果茶', soda: '汽水', other: '其他' })[type] || type || '-';
}

function statusLabel(status) {
  return ({ pending_review: '待审核', evidence_ready: '证据待审核', approved: '已入库', rejected: '已拒绝' })[status] || status || '-';
}

function sourceLabel(source) {
  return ({ image_upload: '图片识别', official_image: '官方图片', nutrition_label_image: '营养表图片', community_screenshot: '用户截图', official: '官方', nutrition_label: '营养表', community_measurement: '实测', user_feedback: '用户反馈', manual: '手动' })[source] || source || '手动';
}

function value(value, unit) {
  return value == null ? '未知' : `${value}${unit}`;
}

</script>

<template>
  <div class="acquisition-review-panel">
    <div class="section-header-row compact-row">
      <span class="acquisition-meta">已选 {{ selectedCandidates.length }} 个候选、{{ selectedEvidence.length }} 条证据</span>
      <div class="bulk-actions"><button type="button" class="mini-secondary-btn" :disabled="!selectedEvidence.length" @click="emit('approve-many', selectedEvidence)">入库选中证据</button><button type="button" class="mini-danger-btn" :disabled="!selectedEvidence.length" @click="emit('delete-evidence-many', selectedEvidence)">删除选中证据</button><button type="button" class="mini-danger-btn" :disabled="!selectedCandidates.length" @click="emit('delete-candidates', selectedCandidates)">删除选中候选</button></div>
    </div>
    <div v-if="loading" class="acquisition-empty">正在加载审核队列...</div>
    <div v-else-if="!candidateRows.length && !orphanEvidence.length" class="acquisition-empty">暂无待审核内容</div>
    <div v-else class="acquisition-list acquisition-review-list">
      <div v-for="row in candidateRows" :key="row.candidate.id" class="acquisition-review-group">
        <div class="acquisition-review-head"><input v-model="selectedCandidates" type="checkbox" :value="row.candidate.id" aria-label="选择候选"><div><div class="acquisition-title">{{ row.candidate.brand || '-' }} {{ row.candidate.name }}</div><div class="acquisition-meta">{{ typeLabel(row.candidate.type) }} · {{ statusLabel(row.candidate.status) }} · {{ row.evidence.length }} 条证据</div></div><div class="acquisition-actions"><button type="button" class="mini-danger-btn" @click="emit('delete-candidate', row.candidate.id)">删除候选</button></div></div>
        <div v-if="!row.evidence.length" class="acquisition-empty inline-empty">还没有证据，可以在上方添加证据文本。</div>
        <div v-for="group in sourceGroups(row.evidence)" v-else :key="group.key" class="acquisition-source-group">
          <div class="acquisition-source-head"><input type="checkbox" :checked="groupChecked(group.rows)" @change="selectGroup(group.rows, $event.target.checked)"><div><div class="acquisition-title">{{ sourceLabel(group.source_type) }}</div><div class="acquisition-meta">{{ group.source_url || '无来源链接' }} · {{ group.rows.length }} 条</div></div><div class="acquisition-actions"><button type="button" class="btn btn-primary" @click="emit('approve-many', group.rows.map(item => item.id))">整组入库</button><button type="button" class="mini-danger-btn" @click="emit('delete-evidence-many', group.rows.map(item => item.id))">删除组</button></div></div>
          <div class="acquisition-evidence-stack"><div v-for="item in group.rows" :key="item.id" class="acquisition-item acquisition-evidence-item"><input v-model="selectedEvidence" type="checkbox" :value="item.id"><div><div class="acquisition-title">{{ sourceLabel(item.source_type) }} · {{ statusLabel(item.status) }}</div><div class="acquisition-meta">{{ item.extracted?.volume || '-' }}ml · 咖啡因 {{ value(item.extracted?.caffeine, 'mg') }} · 糖分 {{ value(item.extracted?.sugar, 'g') }}</div></div><div class="acquisition-actions"><button type="button" class="btn btn-primary" @click="emit('approve', item.id)">入库</button><button type="button" class="mini-danger-btn" @click="emit('delete-evidence', item.id)">删除</button></div></div></div>
        </div>
      </div>
      <div v-if="orphanEvidence.length" class="acquisition-review-group"><div class="acquisition-title">未匹配证据</div><div class="acquisition-evidence-stack"><div v-for="item in orphanEvidence" :key="item.id" class="acquisition-item acquisition-evidence-item"><input v-model="selectedEvidence" type="checkbox" :value="item.id"><div><div class="acquisition-title">{{ sourceLabel(item.source_type) }}</div><div class="acquisition-meta">咖啡因 {{ value(item.extracted?.caffeine, 'mg') }} · 糖分 {{ value(item.extracted?.sugar, 'g') }}</div></div><div class="acquisition-actions"><button type="button" class="btn btn-primary" @click="emit('approve', item.id)">入库</button><button type="button" class="mini-danger-btn" @click="emit('delete-evidence', item.id)">删除</button></div></div></div></div>
    </div>
  </div>
</template>
