import json

# Roda na tela de listas do BIT, no navegador já logado. Só lê a tabela e envia ao sistema.
_CODIGO = """
(async function(){
var O=__ORIGEM__;
if(location.hostname!=='bitpanel.vip'||location.pathname.indexOf('/lines')!==0){alert('Abra a tela de listas do BIT (bitpanel.vip/lines) e clique de novo.');return;}
var w=window.open(O+'/conferencia/bit/receber/','conferencia_bit');
if(!w){alert('O navegador bloqueou a nova aba. Permita pop-ups em bitpanel.vip e clique de novo.');return;}
var espera=function(ms){return new Promise(function(r){setTimeout(r,ms);});};
var botoes=function(t){return Array.from(document.querySelectorAll('button')).filter(function(b){return b.innerText.trim()===t;});};
var contagem=function(){var m=document.body.innerText.match(/Mostrando\\s+(\\d+)\\s+de\\s+(\\d+)/i);return m?[+m[1],+m[2]]:null;};
Array.from(document.querySelectorAll('[role=tab]')).filter(function(b){return b.innerText.trim()==='Tudo';}).forEach(function(b){b.click();});
await espera(1500);
for(var i=0;i<300;i++){var c=contagem();if(c&&c[0]>=c[1])break;var b=botoes('Mostrar mais dados')[0];if(b&&!b.disabled)b.click();await espera(800);}
c=contagem();
if(!c||c[0]<c[1]){alert('Não foi possível carregar todas as listas do BIT. Nada foi enviado.');return;}
var t=document.querySelector('table');
var cab=Array.from(t.querySelectorAll('th')).map(function(h){return h.textContent.trim().toLowerCase();});
var col=function(n){return cab.indexOf(n);};
var ci={estado:col('estado'),usuario:col('usuário'),senha:col('senha'),telas:col('telas'),validade:col('validade'),criacao:col('criação')};
if(Object.values(ci).some(function(x){return x<0;})){alert('A tela do BIT mudou e não foi possível ler as colunas. Nada foi enviado.');return;}
var linhas=Array.from(t.querySelectorAll('tbody tr')).map(function(r){var o={};Object.keys(ci).forEach(function(k){o[k]=r.children[ci[k]].textContent.trim();});return o;});
var ok=false;
window.addEventListener('message',function(e){if(e.origin===O&&e.data==='recebido')ok=true;});
for(var n=0;n<120&&!ok&&!w.closed;n++){w.postMessage({tipo:'leitura_bit',total:c[1],linhas:linhas},O);await espera(500);}
if(!ok)alert('Não foi possível entregar a leitura ao sistema. Confira se você está logado e clique de novo.');
})();
"""


def gerar_bookmarklet(origem):
    codigo = ''.join(linha.strip() for linha in _CODIGO.strip().splitlines())
    return 'javascript:' + codigo.replace('__ORIGEM__', json.dumps(origem))
