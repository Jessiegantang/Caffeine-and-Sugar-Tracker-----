<script setup>
import AppHeader from './components/AppHeader.vue';
import AppTabs from './components/AppTabs.vue';
import AgentBudget from './components/AgentBudget.vue';
import CalendarPicker from './components/CalendarPicker.vue';
import ChatPanel from './components/ChatPanel.vue';
import CustomDrinkLibrary from './components/CustomDrinkLibrary.vue';
import DailyDashboard from './components/DailyDashboard.vue';
import DailyInsights from './components/DailyInsights.vue';
import DailyLogs from './components/DailyLogs.vue';
import DatabaseManager from './components/DatabaseManager.vue';
import DrinkSearch from './components/DrinkSearch.vue';
import DrinkForm from './components/DrinkForm.vue';
import NutritionExplainability from './components/NutritionExplainability.vue';
import KnowledgeAcquisition from './components/KnowledgeAcquisition.vue';
import PopularDrinks from './components/PopularDrinks.vue';
import SleepEntry from './components/SleepEntry.vue';
import WeeklyPanel from './components/WeeklyPanel.vue';
import { useAppController } from './composables/useAppController.js';
import { state } from './state.js';

useAppController();

function selectTab(tabId) {
  state.activeTab = tabId;
}
</script>

<template>
  <div class="container">
    <AppHeader />
    <AppTabs :active-tab="state.activeTab" @select="selectTab" />

    <div class="tab-content-wrapper">
      <div v-show="state.activeTab === 'tab-daily'" id="main-content" class="main-content">
        <div class="workspace-grid">
          <aside id="workspace-left" class="workspace-left">
            <CalendarPicker />
            <DrinkSearch />
            <PopularDrinks />
            <CustomDrinkLibrary />
            <DrinkForm />
            <SleepEntry />
            <DailyLogs />
            <NutritionExplainability />
          </aside>

          <main class="workspace-right">
            <div id="tab-daily" class="tab-content active">
              <DailyDashboard />
              <AgentBudget />
              <DailyInsights />
              <ChatPanel />
              <WeeklyPanel />
            </div>
          </main>
        </div>
      </div>

      <main
        v-show="state.activeTab === 'tab-database'"
        id="tab-database"
        class="tab-content database-full-width active"
      >
        <DatabaseManager />
        <KnowledgeAcquisition />
      </main>
    </div>

    <footer class="app-footer-note">
      <p>免责声明：本工具估算数据基于日常均值规则，仅供个人膳食管理参考，不构成医疗诊断或专业建议。</p>
    </footer>

    <svg class="chart-gradient-definitions" aria-hidden="true">
      <defs>
        <linearGradient id="caffeine-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#2f8f83" />
          <stop offset="100%" stop-color="#6fc0a8" />
        </linearGradient>
        <linearGradient id="sugar-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#d59a22" />
          <stop offset="100%" stop-color="#f0c96b" />
        </linearGradient>
      </defs>
    </svg>
  </div>
</template>

<style scoped>
.chart-gradient-definitions {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
}
</style>
