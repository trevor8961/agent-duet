import { createApp } from 'vue'
import './theme.css'
import './style.css'
import { initTheme } from './theme'
import App from './App.vue'

initTheme()
createApp(App).mount('#app')
