<script setup>
import { reactive, watch } from 'vue';
import { TYPE_DEFINITIONS } from '../../drinks-database.js';

const props = defineProps({ drink: { type: Object, default: null } });
const emit = defineEmits(['close', 'delete', 'save']);
const form = reactive({ id: '', brand: '', name: '', type: 'coffee', caffeine: 0, baseSugar: 0, defaultVolume: 500 });
const types = Object.entries(TYPE_DEFINITIONS).map(([value, definition]) => ({ value, label: definition.label }));

watch(() => props.drink, (drink) => {
  if (!drink) return;
  Object.assign(form, { id: drink.id, brand: drink.brand || '', name: drink.name || '', type: drink.type || 'coffee', caffeine: drink.caffeine || 0, baseSugar: drink.baseSugar || 0, defaultVolume: drink.defaultVolume || 500 });
}, { immediate: true });
</script>

<template>
  <div v-if="drink" class="modal-overlay" style="display: flex" @click.self="emit('close')">
    <div class="modal-content">
      <div class="modal-header"><h3>编辑饮品</h3><button type="button" class="modal-close-btn" aria-label="关闭" @click="emit('close')">×</button></div>
      <form autocomplete="off" @submit.prevent="emit('save', { ...form })">
        <div class="form-row"><div class="form-group flex-1"><label>品牌</label><input v-model.trim="form.brand"></div><div class="form-group flex-2"><label>饮品名称 <span class="required">*</span></label><input v-model.trim="form.name" minlength="2" required></div></div>
        <div class="form-row"><div class="form-group flex-1"><label>饮品类型</label><select v-model="form.type"><option v-for="type in types" :key="type.value" :value="type.value">{{ type.label }}</option></select></div><div class="form-group flex-1"><label>咖啡因含量 (mg)</label><input v-model.number="form.caffeine" type="number" min="0" max="500"></div></div>
        <div class="form-row"><div class="form-group flex-1"><label>糖分含量 (g)</label><input v-model.number="form.baseSugar" type="number" min="0" max="100" step="0.1"></div><div class="form-group flex-1"><label>容量 (ml)</label><input v-model.number="form.defaultVolume" type="number" min="10" max="2000"></div></div>
        <div class="modal-footer"><button type="button" class="btn btn-danger" @click="emit('delete', form.id)">删除</button><button type="submit" class="submit-btn">保存修改</button></div>
      </form>
    </div>
  </div>
</template>
