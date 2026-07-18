<script setup>
import { reactive } from 'vue';
import { TYPE_DEFINITIONS } from '../../drinks-database.js';

const emit = defineEmits(['submit']);
const form = reactive({ type: 'coffee', brand: '', name: '', caffeine: 100, baseSugar: 10, defaultVolume: 500 });
const types = Object.entries(TYPE_DEFINITIONS).map(([value, definition]) => ({ value, label: definition.label }));

function submit() {
  emit('submit', { ...form });
  form.brand = '';
  form.name = '';
  form.caffeine = 100;
  form.baseSugar = 10;
  form.defaultVolume = 500;
}
</script>

<template>
  <section class="add-drink-form-section card glass">
    <h3 class="card-title">添加新饮品</h3>
    <form autocomplete="off" @submit.prevent="submit">
      <div class="form-row">
        <div class="form-group flex-1"><label>品牌</label><input v-model.trim="form.brand" type="text" placeholder="例如：瑞幸咖啡"></div>
        <div class="form-group flex-2"><label>饮品名称 <span class="required">*</span></label><input v-model.trim="form.name" type="text" minlength="2" placeholder="例如：冰美式" required></div>
      </div>
      <div class="form-group">
        <label>饮品类型 <span class="required">*</span></label>
        <div class="radio-chips-group">
          <label v-for="type in types" :key="type.value" class="radio-chip"><input v-model="form.type" type="radio" :value="type.value"><span class="chip-label">{{ type.label }}</span></label>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group flex-1"><label>咖啡因含量 (mg) <span class="required">*</span></label><input v-model.number="form.caffeine" type="number" min="0" max="500" required></div>
        <div class="form-group flex-1"><label>糖分含量 (g) <span class="required">*</span></label><input v-model.number="form.baseSugar" type="number" min="0" max="100" step="0.1" required></div>
        <div class="form-group flex-1"><label>容量 (ml) <span class="required">*</span></label><input v-model.number="form.defaultVolume" type="number" min="10" max="2000" required></div>
      </div>
      <button type="submit" class="submit-btn">添加到数据库</button>
    </form>
  </section>
</template>
