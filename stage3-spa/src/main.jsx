import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { CartProvider } from './context/CartContext'
import { ExchangeRateProvider } from './context/ExchangeRateContext'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ExchangeRateProvider>
        <CartProvider>
          <App />
        </CartProvider>
      </ExchangeRateProvider>
    </BrowserRouter>
  </StrictMode>,
)
