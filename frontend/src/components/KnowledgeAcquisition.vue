<script setup>
import { onMounted, reactive, ref } from 'vue';
import {
  addKnowledgeEvidenceApi, approveKnowledgeEvidenceApi, approveKnowledgeEvidenceBulkApi,
  createKnowledgeCandidateApi, deleteKnowledgeCandidateApi, deleteKnowledgeCandidatesBulkApi,
  deleteKnowledgeEvidenceApi, deleteKnowledgeEvidenceBulkApi, fetchKnowledgeCandidatesApi,
  fetchKnowledgeEvidenceApi,
} from '../api.js';
import { loadDatabaseAsync } from '../drinks-database.js';
import { state } from '../state.js';
import KnowledgeIntake from './knowledge/KnowledgeIntake.vue';
import KnowledgeReview from './knowledge/KnowledgeReview.vue';

const candidates = ref([]);
const evidence = ref([]);
const loading = ref(false);
const message = ref('');
const messageTone = ref('');
const candidateForm = reactive({ brand: '', name: '', type: 'coffee', source_url: '' });
const evidenceForm = reactive({ candidate_id: '', source_type: 'official', source_url: '', raw_evidence: '' });

onMounted(loadReviewQueue);

async function loadReviewQueue() {
  loading.value = true;
  try {
    const [candidateData, evidenceData] = await Promise.all([fetchKnowledgeCandidatesApi(), fetchKnowledgeEvidenceApi()]);
    candidates.value = candidateData.candidates || [];
    evidence.value = evidenceData.evidence || [];
    if (!candidates.value.some(item => item.id === evidenceForm.candidate_id)) evidenceForm.candidate_id = candidates.value[0]?.id || '';
  } catch {
    setMessage('无法连接后端采集接口', false);
  } finally {
    loading.value = false;
  }
}

function prefill(data) {
  candidateForm.brand = data.brand;
  candidateForm.name = data.name;
  candidateForm.type = data.type;
  evidenceForm.raw_evidence = data.rawEvidence;
  evidenceForm.source_type = 'manual';
}

async function createCandidate() {
  if (!candidateForm.name.trim()) return setMessage('请输入候选饮品名称', false);
  try {
    await createKnowledgeCandidateApi({ ...candidateForm, brand: candidateForm.brand.trim(), name: candidateForm.name.trim(), source_url: candidateForm.source_url.trim() || null, discovery_method: 'manual' });
    Object.assign(candidateForm, { brand: '', name: '', type: 'coffee', source_url: '' });
    setMessage('候选已创建', true);
    await loadReviewQueue();
  } catch { setMessage('候选创建失败：来源可能被策略拦截或后端未启动', false); }
}

async function createEvidence() {
  if (!evidenceForm.candidate_id || !evidenceForm.raw_evidence.trim()) return setMessage('请选择候选并填写证据文本', false);
  try {
    await addKnowledgeEvidenceApi(evidenceForm.candidate_id, { source_type: evidenceForm.source_type, source_url: evidenceForm.source_url.trim() || null, raw_evidence: evidenceForm.raw_evidence.trim() });
    evidenceForm.source_url = '';
    evidenceForm.raw_evidence = '';
    setMessage('证据已抽取，等待审核入库', true);
    await loadReviewQueue();
  } catch { setMessage('证据提交失败：来源可能被策略拦截或后端未启动', false); }
}

async function approveOne(id) {
  try { await approveKnowledgeEvidenceApi(id); await databaseChanged(); setMessage('证据已审核入库，并同步知识库', true); } catch { setMessage('入库失败：证据字段不足或后端未启动', false); }
}

async function approveMany(ids) {
  if (!ids.length) return;
  try { const data = await approveKnowledgeEvidenceBulkApi(ids); await databaseChanged(); setMessage(`已入库 ${data.approved?.length || 0} 条证据${data.errors?.length ? `，${data.errors.length} 条失败` : ''}`, true); } catch (error) { setMessage(`批量入库失败：${error.message || '请确认后端已启动'}`, false); }
}

async function deleteEvidence(id) {
  try { await deleteKnowledgeEvidenceApi(id); setMessage('证据已删除', true); await loadReviewQueue(); } catch (error) { setMessage(`删除证据失败：${error.message || '请确认后端已启动'}`, false); }
}

async function deleteEvidenceMany(ids) {
  if (!ids.length) return;
  try { const data = await deleteKnowledgeEvidenceBulkApi(ids); setMessage(`已删除证据 ${data.deleted || 0} 条`, true); await loadReviewQueue(); } catch (error) { setMessage(`批量删除失败：${error.message || '请确认后端已启动'}`, false); }
}

async function deleteCandidate(id) {
  try { await deleteKnowledgeCandidateApi(id); setMessage('候选已删除，关联证据也已隐藏', true); await loadReviewQueue(); } catch (error) { setMessage(`删除候选失败：${error.message || '请确认后端已启动'}`, false); }
}

async function deleteCandidates(ids) {
  if (!ids.length) return;
  try { const data = await deleteKnowledgeCandidatesBulkApi(ids); setMessage(`已删除候选 ${data.deleted || 0} 个`, true); await loadReviewQueue(); } catch (error) { setMessage(`批量删除候选失败：${error.message || '请确认后端已启动'}`, false); }
}

async function databaseChanged() {
  await loadDatabaseAsync();
  state.databaseRevision += 1;
  await loadReviewQueue();
}

function setMessage(text, success) {
  message.value = text;
  messageTone.value = success ? 'success' : 'error';
}
</script>

<template>
  <section class="knowledge-acquisition-section card glass">
    <div class="section-header-row"><h3 class="card-title">知识采集审核</h3><span class="badge count-badge">{{ candidates.length }}</span></div>
    <KnowledgeIntake @message="setMessage($event.text, $event.success)" @prefill="prefill" @refresh="loadReviewQueue" />
    <div class="acquisition-grid">
      <form class="acquisition-form" autocomplete="off" @submit.prevent="createCandidate"><div class="form-row"><div class="form-group flex-1"><label>品牌</label><input v-model="candidateForm.brand" placeholder="例如：瑞幸咖啡"></div><div class="form-group flex-2"><label>候选饮品 <span class="required">*</span></label><input v-model="candidateForm.name" placeholder="例如：新品拿铁" required></div></div><div class="form-row"><div class="form-group flex-1"><label>类型</label><select v-model="candidateForm.type"><option value="coffee">咖啡</option><option value="teacoffee">茶咖</option><option value="tea">原叶茶</option><option value="milktea">奶茶</option><option value="fruittea">果茶</option><option value="soda">汽水</option><option value="other">其他</option></select></div><div class="form-group flex-2"><label>来源链接</label><input v-model="candidateForm.source_url" type="url" placeholder="https://example.com"></div></div><button type="submit" class="submit-btn">创建候选</button></form>
      <form class="acquisition-form" autocomplete="off" @submit.prevent="createEvidence"><div class="form-row"><div class="form-group flex-2"><label>候选饮品 <span class="required">*</span></label><select v-model="evidenceForm.candidate_id" required><option value="">暂无候选</option><option v-for="candidate in candidates" :key="candidate.id" :value="candidate.id">{{ candidate.brand || '-' }} {{ candidate.name }}</option></select></div><div class="form-group flex-1"><label>证据类型</label><select v-model="evidenceForm.source_type"><option value="official">官方</option><option value="nutrition_label">营养表</option><option value="community_measurement">实测</option><option value="manual">手动</option></select></div></div><div class="form-group"><label>证据链接</label><input v-model="evidenceForm.source_url" type="url" placeholder="https://example.com"></div><div class="form-group"><label>证据文本 <span class="required">*</span></label><textarea v-model="evidenceForm.raw_evidence" rows="4" placeholder="例如：容量 500ml 咖啡因: 120mg 糖分: 18g" required></textarea></div><button type="submit" class="submit-btn">抽取证据</button></form>
    </div>
    <div class="acquisition-result" :class="messageTone">{{ message }}</div>
    <KnowledgeReview :candidates="candidates" :evidence="evidence" :loading="loading" @approve="approveOne" @approve-many="approveMany" @delete-evidence="deleteEvidence" @delete-evidence-many="deleteEvidenceMany" @delete-candidate="deleteCandidate" @delete-candidates="deleteCandidates" />
  </section>
</template>
