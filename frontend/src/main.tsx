import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// Force HTTPS in production
if (window.location.protocol === 'http:' && window.location.hostname !== 'localhost') {
  window.location.replace(`https://${window.location.hostname}${window.location.pathname}${window.location.search}`);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
