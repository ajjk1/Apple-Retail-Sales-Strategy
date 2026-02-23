import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Dashboard', component: () => import('./views/Dashboard.vue') },
  ],
})

const app = createApp(App)
app.use(router)
app.mount('#app')
