<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { fetchLogsApi, submitNutritionFeedbackApi } from '../api.js';
import { LOG_SELECTED_EVENT, NUTRITION_RESULT_EVENT, onAppEvent } from '../app-events.js';
import { TYPE_DEFINITIONS } from '../drinks-database.js';
import { state } from '../state.js';
import { saveLogs } from '../storage.js';

const feedbackStatus = ref('');
const feedbackTone = ref('');
const submitting = ref(false);
const workspace = ref(null);
const eventUnsubscribers = [];
const feedbackForm = reactive({
  brand: '',
  name: '',
  type: 'coffee',
  volume: 500,
  caffeine: 0,
  sugarContent: 0,
  source_note: '',
  apply_to_log: true,
  submit_as_evidence: false,
});

const result = computed(() => state.lastNutritionResult);
const explainability = computed(() => result.value?.explainability || {});
const feedback = computed(() => explainability.value.feedback || result.value?.feedback || null);
const components = computed(() => explainability.value.components || result.value?.composition?.components || []);
const reasoning = computed(() => normalizeTextList(explainability.value.reasoning || result.value?.reasoning));
const assumptions = computed(() => normalizeTextList(explainability.value.assumptions || result.value?.composition?.assumptions));
const warnings = computed(() => normalizeTextList(explainability.value.warnings || result.value?.composition?.warnings));
const traceEvents = computed(() => normalizeTraceEvents(explainability.value.graph_trace));
const verification = computed(() => explainability.value.verification || null);
const usedComposition = computed(() => Boolean(explainability.value.used_composition));
const usedKnowledge = computed(() => Boolean(explainability.value.used_knowledge_match));
const sourceLabel = computed(() => mapEstimateSource(result.value, explainability.value, feedback.value));
const explanation = computed(() => getEstimateExplanation(sourceLabel.value, explainability.value, result.value));
const typeOptions = Object.entries(TYPE_DEFINITIONS).map(([value, definition]) => ({
  value,
  label: getTypeText(value, definition?.label),
}));

watch(result, resetFeedbackForm, { immediate: true });

onMounted(() => {
  eventUnsubscribers.push(
    onAppEvent(LOG_SELECTED_EVENT, handleLogSelected),
    onAppEvent(NUTRITION_RESULT_EVENT, handleNutritionResult),
  );
});

onBeforeUnmount(() => {
  eventUnsubscribers.splice(0).forEach(unsubscribe => unsubscribe());
});

function handleNutritionResult(nutritionResult) {
  state.lastNutritionResult = nutritionResult || null;
}

async function handleLogSelected({ log } = {}) {
  if (!log) return;
  state.lastNutritionResult = buildNutritionResultFromLog(log);
  await nextTick();
  workspace.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function resetFeedbackForm(current) {
  feedbackStatus.value = '';
  feedbackTone.value = '';
  if (!current) return;
  const corrected = current.explainability?.feedback?.corrected || current.feedback?.corrected || {};
  feedbackForm.brand = corrected.brand ?? current.brand ?? '';
  feedbackForm.name = corrected.name ?? current.name ?? '';
  feedbackForm.type = corrected.type ?? current.type ?? 'coffee';
  feedbackForm.volume = corrected.volume ?? current.volume ?? 500;
  feedbackForm.caffeine = corrected.caffeine ?? current.caffeine ?? 0;
  feedbackForm.sugarContent = corrected.sugarContent ?? current.sugarContent ?? 0;
  feedbackForm.source_note = '';
  feedbackForm.apply_to_log = true;
  feedbackForm.submit_as_evidence = false;
}

async function submitFeedback() {
  if (!result.value?.log_id || submitting.value) return;
  if (feedbackForm.submit_as_evidence && !feedbackForm.source_note.trim()) {
    feedbackStatus.value = '加入审核队列时需要填写数据来源说明。';
    feedbackTone.value = 'error';
    return;
  }

  const payload = {
    corrected: {
      brand: feedbackForm.brand.trim() || null,
      name: feedbackForm.name.trim(),
      type: feedbackForm.type,
      volume: Number(feedbackForm.volume),
      caffeine: Number(feedbackForm.caffeine),
      sugarContent: Number(feedbackForm.sugarContent),
    },
    source_type: 'user_feedback',
    source_note: feedbackForm.source_note.trim(),
    apply_to_log: feedbackForm.apply_to_log,
    submit_as_evidence: feedbackForm.submit_as_evidence,
  };

  submitting.value = true;
  feedbackStatus.value = '提交中...';
  feedbackTone.value = '';
  try {
    const data = await submitNutritionFeedbackApi(result.value.log_id, payload);
    if (payload.apply_to_log) {
      state.logs = (await fetchLogsApi()) || [];
      saveLogs(state.logs);
    }
    const notices = [];
    if (payload.apply_to_log) notices.push('这条记录已更新。');
    if (data.evidence || payload.submit_as_evidence) notices.push('修正已加入审核队列。');
    state.lastNutritionResult = buildNutritionResultFromLog(
      data.log || { ...result.value, ...payload.corrected },
      notices.join(' ') || '修正已保存。',
    );
    feedbackStatus.value = notices.join(' ') || '修正已保存。';
    feedbackTone.value = 'success';
  } catch (error) {
    feedbackStatus.value = error.message || '修正提交失败';
    feedbackTone.value = 'error';
  } finally {
    submitting.value = false;
  }
}

function buildNutritionResultFromLog(log, notice = '') {
  return {
    log_id: log.id || log.log_id,
    brand: log.brand,
    name: log.name,
    type: log.type,
    volume: log.volume,
    caffeine: log.caffeine,
    sugarContent: log.sugarContent,
    estimation_method: log.estimation_method || '未知',
    data_source: log.data_source || '未知',
    matched_knowledge_id: log.matched_knowledge_id || null,
    retrieval_score: log.retrieval_score ?? null,
    reasoning: normalizeTextList(log.reasoning),
    composition: log.composition || null,
    explainability: log.explainability || {
      method: log.estimation_method || '未知',
      used_composition: false,
      used_knowledge_match: Boolean(log.matched_knowledge_id),
      matched_knowledge_id: log.matched_knowledge_id || null,
      retrieval_score: log.retrieval_score ?? null,
      reasoning: normalizeTextList(log.reasoning || ['这条记录没有保存可解释性详情']),
      components: [],
      assumptions: [],
      warnings: log.reasoning ? [] : ['这条记录没有保存可解释性详情'],
    },
    feedback_notice: notice,
  };
}

function mapEstimateSource(current, details, currentFeedback) {
  if (!current) return '未知';
  const method = String(current.estimation_method || details.method || '').toLowerCase();
  const source = String(current.data_source || '').toLowerCase();
  if (currentFeedback?.corrected || method.includes('feedback') || source.includes('user')) return '用户修正';
  if (details.used_knowledge_match || current.matched_knowledge_id || source.includes('knowledge')) return '知识库匹配';
  if (details.used_composition || current.composition || method.includes('composition')) return '成分估算';
  return '兜底估算';
}

function getEstimateExplanation(source, details, current) {
  if (source === '用户修正') return '这个结果包含你为本条记录保存的人工修正。';
  if (source === '知识库匹配') return '这个结果来自已审核的饮品知识库匹配，并按容量和糖度做了换算。';
  if (source === '成分估算') return '没有找到足够可信的产品匹配，所以后端根据可能的成分组成进行了估算。';
  if (current?.feedback_notice) return current.feedback_notice;
  if (details.warnings?.length) return '这是兜底估算；如果你有包装营养表或官方数据，可以在下方修正。';
  return '这是基于当前饮品信息得到的兜底估算。';
}

function normalizeTextList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(item => typeof item === 'string' ? item : JSON.stringify(item));
  if (typeof value !== 'string') return [String(value)];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String) : [String(parsed)];
  } catch {
    return [value];
  }
}

function normalizeTraceEvents(trace) {
  return (Array.isArray(trace) ? trace : []).map((event) => {
    if (typeof event === 'string') return createTraceEvent({ id: event });
    return createTraceEvent(event || {});
  });
}

function createTraceEvent(event) {
  return {
    id: event.id || event.node || '',
    label: event.label || getTraceLabel(event.id || event.node),
    phase: event.phase || '流程',
    agent: event.agent || 'Nutrition Agent',
    status: event.status || 'completed',
    summary: event.summary || '',
    input: event.input || null,
    output: event.output || null,
    decision: event.decision || null,
  };
}

function getTraceLabel(id = '') {
  return ({
    normalize_input: '标准化输入',
    lookup_knowledge: '知识库检索',
    route_estimation: '路由决策',
    use_knowledge_result: '采用知识结果',
    composition_decompose: '成分拆解',
    composition_estimate: '成分估算',
    composition_error: '成分估算异常',
    verify_result: '结果校验',
    build_explainability: '生成解释',
  })[id] || id || '未知步骤';
}

function formatTraceKey(key) {
  return ({
    brand: '品牌', name: '名称', type: '类型', volume_ml: '容量', sugar: '甜度', method: '方法',
    source: '来源', caffeine_mg: '咖啡因', sugar_g: '糖分',
    matched_knowledge_id: '知识 ID', retrieval_score: '检索分', components: '成分数', route: '路由',
    drink_type: '饮品类型', espresso_shots: '浓缩份数', tea_base_volume_ml: '茶底',
    milk_volume_ml: '奶基底', fruit_base_volume_ml: '果汁/饮品基底', syrup_pumps: '糖浆泵数',
    sweetness_level: '甜度级别', assumptions: '假设', warnings: '提醒', passed: '通过',
    issues: '问题', error: '错误',
  })[key] || key;
}

function formatTraceValue(value) {
  if (Array.isArray(value)) return value.map(formatTraceValue).join('；');
  if (value && typeof value === 'object') return JSON.stringify(value);
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
  if (typeof value === 'boolean') return value ? '是' : '否';
  return translateNutritionText(value);
}

function formatTraceStatus(status) {
  return ({ error: '异常', warning: '有提醒', skipped: '跳过' })[status] || '完成';
}

function formatNumber(value) {
  const number = Number(value ?? 0);
  return Number.isFinite(number) ? number.toFixed(1) : '0.0';
}

function formatAmount(amount, unit) {
  const number = Number(amount ?? 0);
  const value = Number.isFinite(number) ? number.toFixed(number % 1 === 0 ? 0 : 1) : amount;
  return `${value} ${translateNutritionText(unit || '')}`.trim();
}

function getTypeText(type, fallback = '') {
  return ({ coffee: '咖啡', teacoffee: '茶咖', tea: '原叶茶', milktea: '奶茶', milk_tea: '奶茶',
    fruittea: '果茶', fruit_tea: '果茶', soda: '汽水', other: '其他' })[type] || fallback || type;
}

function translateNutritionText(value) {
  const text = String(value ?? '');
  const translations = {
    coffee: '咖啡', teacoffee: '茶咖', tea: '原叶茶', milktea: '奶茶', milk_tea: '奶茶',
    fruittea: '果茶', fruit_tea: '果茶', soda: '汽水', knowledge: '知识库结果', composition: '成分估算',
    completed: '完成', input: '输入', output: '输出', caffeine_only: '仅咖啡因', sugar_only: '仅糖分',
    caffeine_sugar: '咖啡因和糖分', complete: '完整数据', partial: '部分数据', True: '是', False: '否',
    COMPOSITION: '成分估算', LOCAL: '本地估算', LLM: '模型估算', user_feedback: '用户反馈',
    SQL_EXACT_MATCH: '知识库精确匹配', RAG_MATCH: '知识库语义匹配',
    COMPOSITION_ESTIMATION: '成分拆解估算',
    espresso: '浓缩咖啡', milk: '牛奶', oat_milk: '燕麦奶', coconut_milk: '厚椰乳',
    tea_base: '茶基底', milk_base: '奶基底', fruit_base: '水果/饮品基底', sweetener: '甜味来源',
    none: '无糖', three: '三分糖', half: '半糖', seven: '七分糖', full: '全糖', unknown: '未知',
    'Composition Estimation Agent': '成分估算 Agent', 'Knowledge Lookup Agent': '知识库检索 Agent',
    'Input Normalizer': '输入标准化', 'Estimation Router': '估算路由器', 'Result Verifier': '结果校验器',
    'Explainability Builder': '解释生成器',
  };
  if (translations[text]) return translations[text];
  if (text.includes(' + ')) return text.split(' + ').map(translateNutritionText).join(' + ');
  if (text.startsWith('Warning: ')) return `提醒：${translateNutritionText(text.slice(9))}`;
  return text;
}
</script>

<template>
  <section id="agent-workspace" ref="workspace" class="agent-workspace-section card glass estimate-correction-section">
    <div class="agent-panel nutrition-explainability-panel estimate-result-panel">
      <div class="agent-panel-header"><span>估算详情与修正</span></div>
      <div v-if="!result" class="agent-panel-body muted">暂无营养估算结果</div>
      <div v-else class="agent-panel-body nutrition-explainability-body">
        <div class="estimate-result-summary">
          <div class="nutrition-metric"><span>咖啡因</span><strong>{{ formatNumber(result.caffeine) }} mg</strong></div>
          <div class="nutrition-metric"><span>糖分</span><strong>{{ formatNumber(result.sugarContent) }} g</strong></div>
          <div class="nutrition-metric"><span>来源</span><strong>{{ sourceLabel }}</strong></div>
        </div>

        <div class="estimate-explanation">{{ explanation }}</div>

        <details class="nutrition-technical-details">
          <summary>技术详情</summary>
          <div class="nutrition-technical-stack">
            <div class="nutrition-explain-section">
              <div class="nutrition-explain-title">估算方法</div>
              <div class="explain-chips">
                <span class="explain-chip">方法: {{ translateNutritionText(result.estimation_method || explainability.method || '未知') }}</span>
                <span class="explain-chip">原始来源: {{ translateNutritionText(result.data_source || '未知') }}</span>
              </div>
            </div>

            <div class="nutrition-explain-section">
              <div class="nutrition-explain-title">知识库匹配</div>
              <div class="explain-chips">
                <span class="explain-chip">是否使用: {{ usedKnowledge ? '是' : '否' }}</span>
                <span v-if="explainability.matched_knowledge_id || result.matched_knowledge_id" class="explain-chip">
                  匹配 ID: {{ explainability.matched_knowledge_id || result.matched_knowledge_id }}
                </span>
                <span v-if="explainability.retrieval_score ?? result.retrieval_score" class="explain-chip">
                  检索分数: {{ Number(explainability.retrieval_score ?? result.retrieval_score).toFixed(3) }}
                </span>
              </div>
            </div>

            <div v-if="traceEvents.length" class="nutrition-explain-section langgraph-workflow-section">
              <div class="nutrition-workflow-header">
                <div>
                  <div class="nutrition-explain-title">Agent Trace 工作流</div>
                  <div class="nutrition-workflow-subtitle">从输入、检索、路由到估算与校验的流程级可视化</div>
                </div>
                <div class="nutrition-workflow-stats"><span>{{ traceEvents.length }} 步</span></div>
              </div>
              <ol class="agent-trace-timeline">
                <li v-for="(event, index) in traceEvents" :key="`${event.id}-${index}`" class="agent-trace-event" :class="`tone-${event.status}`">
                  <span class="agent-trace-index">{{ index + 1 }}</span>
                  <div class="agent-trace-card">
                    <div class="agent-trace-card-head">
                      <div><strong>{{ event.label }}</strong><span>{{ translateNutritionText(event.agent) }}</span></div>
                      <div class="agent-trace-badges">
                        <span>{{ translateNutritionText(event.phase) }}</span><span>{{ formatTraceStatus(event.status) }}</span>
                      </div>
                    </div>
                    <p v-if="event.summary">{{ translateNutritionText(event.summary) }}</p>
                    <div v-if="event.decision" class="agent-trace-decision">{{ translateNutritionText(event.decision) }}</div>
                    <div class="agent-trace-data-grid">
                      <div v-for="([title, data]) in [['输入', event.input], ['输出', event.output]]" v-show="data && Object.keys(data).length" :key="title" class="agent-trace-data">
                        <span>{{ title }}</span>
                        <dl><div v-for="(value, key) in data" :key="key"><dt>{{ formatTraceKey(key) }}</dt><dd>{{ formatTraceValue(value) }}</dd></div></dl>
                      </div>
                    </div>
                  </div>
                </li>
              </ol>
              <div v-if="verification" class="langgraph-verification">
                <div class="explain-chips"><span class="explain-chip">验证通过: {{ verification.passed == null ? '未知' : verification.passed ? '是' : '否' }}</span></div>
                <div v-if="normalizeTextList(verification.warnings).length" class="langgraph-verification-list tone-warning">
                  <span>警告</span><ul><li v-for="item in normalizeTextList(verification.warnings)" :key="item">{{ translateNutritionText(item) }}</li></ul>
                </div>
                <div v-if="normalizeTextList(verification.issues).length" class="langgraph-verification-list tone-issue">
                  <span>问题</span><ul><li v-for="item in normalizeTextList(verification.issues)" :key="item">{{ translateNutritionText(item) }}</li></ul>
                </div>
              </div>
            </div>

            <div class="nutrition-explain-section">
              <div class="nutrition-explain-title">成分拆解</div>
              <div v-if="usedComposition && components.length" class="nutrition-component-list">
                <div v-for="(component, index) in components" :key="`${component.name}-${index}`" class="nutrition-component-row">
                  <div><strong>{{ translateNutritionText(component.name || '成分') }}</strong><span>{{ translateNutritionText(component.category || '未知类别') }}</span></div>
                  <div>{{ formatAmount(component.amount, component.unit) }}</div>
                  <div>{{ formatNumber(component.caffeine_mg) }}mg</div><div>{{ formatNumber(component.sugar_g) }}g</div>
                  <small>{{ translateNutritionText(component.basis) }}</small>
                </div>
              </div>
              <div v-else class="nutrition-empty-note">{{ usedComposition ? '后端没有返回成分明细。' : '未使用成分拆解，因为已有可信知识库匹配。' }}</div>
            </div>

            <div v-for="section in [{ title: '推理说明', items: reasoning }, { title: '估算假设', items: assumptions }, { title: '提醒', items: warnings, tone: 'warning' }]" v-show="section.items.length" :key="section.title" class="nutrition-explain-section" :class="section.tone ? `tone-${section.tone}` : ''">
              <div class="nutrition-explain-title">{{ section.title }}</div><ul class="nutrition-text-list"><li v-for="item in section.items" :key="item">{{ translateNutritionText(item) }}</li></ul>
            </div>

            <div v-if="feedback || result.feedback_notice" class="nutrition-explain-section feedback-summary">
              <div class="nutrition-explain-title">修正记录</div>
              <div v-if="result.feedback_notice" class="feedback-notice">{{ result.feedback_notice }}</div>
              <template v-if="feedback">
                <div class="explain-chips"><span class="explain-chip">来源: {{ translateNutritionText(feedback.source_type || 'user_feedback') }}</span><span class="explain-chip">差异较大: {{ feedback.high_delta ? '是' : '否' }}</span></div>
                <div v-if="feedback.source_note" class="nutrition-empty-note">{{ feedback.source_note }}</div>
              </template>
            </div>
          </div>
        </details>

        <div v-if="!result.log_id" class="nutrition-feedback-form nutrition-feedback-disabled">
          <div class="nutrition-explain-title">人工修正估算</div><div class="nutrition-empty-note">保存为饮品记录后，可以在这里修正咖啡因和糖分。</div>
        </div>
        <form v-else id="nutrition-feedback-form" class="nutrition-feedback-form" @submit.prevent="submitFeedback">
          <div class="nutrition-explain-title">人工修正估算</div>
          <div class="feedback-form-grid feedback-form-grid-simple">
            <label>咖啡因 mg<input v-model.number="feedbackForm.caffeine" type="number" min="0" max="800" step="0.1" required></label>
            <label>糖分 g<input v-model.number="feedbackForm.sugarContent" type="number" min="0" max="150" step="0.1" required></label>
          </div>
          <label class="feedback-note-label">数据来源说明<textarea v-model="feedbackForm.source_note" rows="2" placeholder="例如：包装营养表标注咖啡因 120mg，糖 18g"></textarea></label>
          <div class="feedback-options"><label><input v-model="feedbackForm.apply_to_log" type="checkbox"> 更新这条记录</label></div>
          <details class="feedback-advanced-details">
            <summary>高级修正字段</summary>
            <div class="feedback-form-grid">
              <label>品牌<input v-model="feedbackForm.brand"></label><label>名称<input v-model="feedbackForm.name" required></label>
              <label>类型<select v-model="feedbackForm.type"><option v-for="option in typeOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
              <label>容量 ml<input v-model.number="feedbackForm.volume" type="number" min="10" max="2000" required></label>
            </div>
            <div class="feedback-options"><label><input v-model="feedbackForm.submit_as_evidence" type="checkbox"> 加入审核队列</label></div>
          </details>
          <div class="feedback-actions"><button type="submit" class="btn btn-primary" :disabled="submitting">{{ submitting ? '提交中...' : '保存修正' }}</button><span class="feedback-status" :class="feedbackTone">{{ feedbackStatus }}</span></div>
        </form>
      </div>
    </div>
  </section>
</template>
