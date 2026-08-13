const $=s=>document.querySelector(s);const fmt=n=>Math.round(n).toLocaleString('ko-KR');
function track(name,data={}){window.dataLayer=window.dataLayer||[];window.dataLayer.push({event:name,...data})}
function calculate(){
 const area=+$('#area').value,ceiling=+$('#ceiling').value,current=+$('#current').value,target=Math.min(50,+$('#target').value),hours=+$('#hours').value,power=+$('#power').value,rate=+$('#rate').value;
 const gap=Math.max(5,target-current),load=18+(gap/25)*12,output=Math.round(area*(ceiling/2.4)*load/10)*10;
 const tank=Math.max(1,output*hours/1000),kwh=power*hours*30/1000,cost=kwh*rate;
 $('#output').innerHTML=`${fmt(output)} <span>mL/h 권장 범위 중심값</span>`;$('#range').textContent=`${fmt(output*.8)}~${fmt(output*1.2)} mL/h`;$('#tank').textContent=`${tank.toFixed(1)} L/일`;$('#energy').textContent=`${kwh.toFixed(1)} kWh/월`;$('#cost').textContent=`약 ${fmt(cost)}원/월`;$('#goal').textContent=`${target}% 이하로 관리`;track('tool_complete',{tool:'humidifier',area,target});
}
function setup(){
 const c=window.ATEMOYA_CONFIG||{};if(c.affiliateUrl){$('#affiliate').classList.add('active');$('#affiliate-link').href=c.affiliateUrl;$('#disclosure').textContent=c.affiliateDisclosure}
 if(c.gaMeasurementId){let s=document.createElement('script');s.async=true;s.src=`https://www.googletagmanager.com/gtag/js?id=${c.gaMeasurementId}`;document.head.appendChild(s);window.dataLayer=[];window.gtag=function(){dataLayer.push(arguments)};gtag('js',new Date());gtag('config',c.gaMeasurementId)}
 if(c.adsenseClient){let a=document.createElement('script');a.async=true;a.crossOrigin='anonymous';a.src=`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${c.adsenseClient}`;document.head.appendChild(a)}
 $('#calc').addEventListener('click',calculate);document.querySelectorAll('input,select').forEach(x=>x.addEventListener('change',calculate));$('#affiliate-link').addEventListener('click',()=>track('affiliate_click',{tool:'humidifier'}));calculate();track('tool_start',{tool:'humidifier'});
}document.addEventListener('DOMContentLoaded',setup);
