// Somente controla a instalação: nenhuma foto ou informação pessoal é armazenada offline.
if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/static/sw.js', {scope:'/'}).catch(console.warn));
}
