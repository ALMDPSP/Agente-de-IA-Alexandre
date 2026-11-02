(() => {
 const platform=document.getElementById('platform'),button=document.getElementById('installBtn'),help=document.getElementById('installHelp');
 const ua=navigator.userAgent||'';const ios=/iPad|iPhone|iPod/.test(ua)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 const android=/Android/i.test(ua);const standalone=window.matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;
 const sections={ios:document.getElementById('ios'),android:document.getElementById('android')};
 if(standalone){platform.textContent='✓ O aplicativo já está aberto em modo instalado';}
 else if(ios){platform.textContent='iPhone detectado: siga as instruções do Safari';sections.ios.classList.add('recommended');}
 else if(android){platform.textContent='Android detectado: use o Chrome para instalar';sections.android.classList.add('recommended');}
 else{platform.textContent='Escolha abaixo o guia do seu celular';}
 let promptEvent=null;
 window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();promptEvent=e;if(!standalone&&!ios){button.hidden=false;help.textContent='Seu navegador permite solicitar a instalação.'}});
 button.addEventListener('click',async()=>{if(!promptEvent){help.textContent='Abra o menu ⋮ do Chrome e selecione Instalar app ou Adicionar à tela inicial.';return;} const ev=promptEvent;promptEvent=null;button.hidden=true;try{await ev.prompt();const choice=await ev.userChoice;help.textContent=choice.outcome==='accepted'?'Instalação solicitada. Confira a tela inicial do celular.':'Instalação cancelada. Você pode tentar pelo menu do navegador.';}catch{help.textContent='Não foi possível abrir a instalação automática. Use o menu ⋮ do Chrome.'}});
 window.addEventListener('appinstalled',()=>{platform.textContent='✓ Aplicativo instalado';button.hidden=true;help.textContent='Abra Meu Controle de Peso na sua tela inicial.'});
 document.getElementById('copyLink').addEventListener('click',async()=>{const t=document.getElementById('copyStatus');try{await navigator.clipboard.writeText(location.origin+'/instalar');t.textContent='Link copiado!'}catch{t.textContent='Copie o endereço mostrado acima.'}});
})();