import json

# Roda na tela de listas do BIT, no navegador já logado. Não faz login nem altera nada:
# aproveita as respostas que a própria página recebe, que trazem o ID de cada acesso.
_CODIGO = """
(async function(){
var O=__ORIGEM__;
if(location.hostname!=='bitpanel.vip'||location.pathname.indexOf('/lines')!==0){alert('Abra a tela de listas do BIT (bitpanel.vip/lines) e clique de novo.');return;}
var w=window.open(O+'/conferencia/bit/receber/','conferencia_bit');
if(!w){alert('O navegador bloqueou a nova aba. Permita pop-ups em bitpanel.vip e clique de novo.');return;}
var espera=function(ms){return new Promise(function(r){setTimeout(r,ms);});};
var botoes=function(t){return Array.from(document.querySelectorAll('button')).filter(function(b){return b.innerText.trim()===t;});};
var reg={},total=null;
var P=XMLHttpRequest.prototype,oo=P.open,os=P.send;
P.open=function(m,u){this.__url=String(u);return oo.apply(this,arguments);};
P.send=function(){this.addEventListener('load',function(){try{if(/\\/lines(\\?|$)/.test(this.__url)){var j=JSON.parse(this.responseText);total=j.total;(j.data||[]).forEach(function(l){reg[l.id]=l;});}}catch(e){}});return os.apply(this,arguments);};
Array.from(document.querySelectorAll('[role=tab]')).filter(function(b){return b.innerText.trim()==='Tudo';}).forEach(function(b){b.click();});
await espera(1000);
var at=botoes('Atualizar')[0];if(at)at.click();
await espera(2000);
for(var i=0;i<300;i++){if(total!==null&&Object.keys(reg).length>=total)break;var b=botoes('Mostrar mais dados')[0];if(b&&!b.disabled)b.click();await espera(800);}
P.open=oo;P.send=os;
var ls=Object.values(reg);
if(total===null||ls.length!==total){alert('Não foi possível carregar todas as listas do BIT. Nada foi enviado.');return;}
var linhas=ls.map(function(l){return{id:l.id,usuario:l.username,senha:l.password,estado:l.status,telas:l.screens,validade:l.expiresAt,whatsapp:l.whatsapp,observacao:l.notes};});
var ok=false;
window.addEventListener('message',function(e){if(e.origin===O&&e.data==='recebido')ok=true;});
for(var n=0;n<120&&!ok&&!w.closed;n++){w.postMessage({tipo:'leitura_bit',total:total,linhas:linhas},O);await espera(500);}
if(!ok)alert('Não foi possível entregar a leitura ao sistema. Confira se você está logado e clique de novo.');
})();
"""


def gerar_bookmarklet(origem):
    codigo = ''.join(linha.strip() for linha in _CODIGO.strip().splitlines())
    return 'javascript:' + codigo.replace('__ORIGEM__', json.dumps(origem))
