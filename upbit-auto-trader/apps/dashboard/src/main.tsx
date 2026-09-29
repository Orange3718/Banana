import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity, AlertTriangle, Bitcoin, CircleDollarSign, Clock3, Power, RefreshCw, ShieldAlert, Terminal, TrendingUp, WalletCards, Wifi, WifiOff} from 'lucide-react';
import './style.css';

type Position={symbol:string;market:string;quantity:string;price:string|null;value:string|null;unrealized:string|null;side?:string;entry_price?:string;leverage?:string;margin_type?:string};
type Snapshot={as_of:string;currency:string;cash:string;equity:string|null;priced_subtotal:string;unrealized:string|null;positions:Position[];unpriced:string[]};
type Account={snapshot:Snapshot|null;collector:{status:string};history:{as_of:string;equity:string|null}[]};
type Overview={accounts:{upbit:Account;binance_futures:Account};runtime:Record<string,unknown>;settings:Record<string,unknown>;recommendations:any[];connections:{id:string;label:string;status:string}[]};
type LivePayload={overview:Overview;terminal:{sections:{label:string;text:string;updated_at:string|null}[]};events:any[];streamed_at:string};
type Page='overview'|'upbit'|'binance'|'activity'|'kiwoom';
type KiwoomRow={stk_cd:string;stk_nm:string;cur_prc:string;flu_rt?:string;trde_qty:string};
type KiwoomRankings={as_of:string;connected:boolean;error:string|null;top_change:KiwoomRow[];top_volume:KiwoomRow[]};
type OrderLevel={price:string;qty:string};
type OrderBook={as_of:string;connected:boolean;error:string|null;stk_cd:string;base_time:string;asks:OrderLevel[];bids:OrderLevel[];total_ask_qty:string;total_bid_qty:string};

const money=(value:unknown,currency='KRW')=>{if(value===null||value===undefined||value==='')return '확인 중';const n=Number(value);if(!Number.isFinite(n))return '확인 중';return currency==='USD'?`$${n.toLocaleString('ko-KR',{maximumFractionDigits:2})}`:`${n.toLocaleString('ko-KR',{maximumFractionDigits:0})}원`;};
const number=(value:unknown,digits=8)=>Number(value||0).toLocaleString('ko-KR',{maximumFractionDigits:digits});
const stamp=(value:unknown)=>typeof value==='string'&&value?new Date(value.includes('T')?value:value.replace(' ','T')+'+09:00').toLocaleTimeString('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—';
const pnlClass=(value:unknown)=>Number(value)>0?'positive':Number(value)<0?'negative':'';
async function get(path:string){const r=await fetch(`/api/v1/${path}`);if(!r.ok)throw Error(`조회 실패 ${r.status}`);return r.json();}

function Metric({label,value,sub,tone='',icon}:{label:string;value:string;sub:string;tone?:string;icon:React.ReactNode}){return <section className="metric"><div className={`metric-icon ${tone}`}>{icon}</div><div><span>{label}</span><strong className={tone}>{value}</strong><small>{sub}</small></div></section>;}

function AccountCard({name,badge,account,accent}:{name:string;badge:string;account:Account|undefined;accent:string}){
 const s=account?.snapshot;const connected=account?.collector.status==='connected';const currency=s?.currency||'KRW';
 return <article className={`account-card ${accent}`}><div className="account-head"><div><span className="exchange-badge">{badge}</span><div><h2>{name}</h2><small>{currency==='USD'?'USD-M 선물':'KRW 현물'}</small></div></div><span className={connected?'live':'offline'}>{connected?'LIVE':'점검 필요'}</span></div><div className="account-balance"><span>{s?.equity?'총 평가자산':'확인된 평가자산'}</span><strong>{money(s?.equity??s?.priced_subtotal,currency)}</strong><small>주문 가능 {money(s?.cash,currency)}</small></div><div className="account-foot"><span>미실현 손익 <b className={pnlClass(s?.unrealized)}>{money(s?.unrealized,currency)}</b></span><span>포지션 <b>{s?.positions.length||0}</b></span><span>갱신 <b>{stamp(s?.as_of)}</b></span></div></article>;
}

function PositionList({account,kind}:{account:Account|undefined;kind:'upbit'|'binance'}){
 const s=account?.snapshot;const currency=s?.currency||'KRW';const positions=s?.positions||[];
 if(!positions.length)return <div className="empty-state"><WalletCards size={26}/><b>열린 포지션이 없습니다</b><span>진입 조건이 충족되면 여기에 표시됩니다.</span></div>;
 return <div className="positions"><div className="table-head"><span>자산</span><span>수량</span><span>현재가</span><span>평가액</span><span>손익</span></div>{positions.map(p=><div className="position-row" key={`${kind}-${p.market}`}><div className="asset"><span className="coin">{p.symbol.slice(0,2)}</span><div><b>{p.symbol}</b><small>{p.side?`${p.side} · ${p.leverage||'—'}x`:p.market}</small></div></div><span data-label="수량">{number(p.quantity)}</span><span data-label="현재가">{money(p.price,currency)}</span><span data-label="평가액">{money(p.value,currency)}</span><strong data-label="손익" className={pnlClass(p.unrealized)}>{money(p.unrealized,currency)}</strong></div>)}</div>;
}

function Controls({runtime,onDone}:{runtime:Record<string,unknown>;onDone:()=>void}){
 const [busy,setBusy]=useState('');const [message,setMessage]=useState('');const paused=Boolean(runtime.paused);
 const command=async(action:'pause'|'kill')=>{setBusy(action);setMessage('');try{const r=await fetch('/api/v1/commands',{method:'POST',headers:{'Content-Type':'application/json','X-Neural-Client':'dashboard'},body:JSON.stringify({action})});const d=await r.json();if(!r.ok)throw Error(d.detail||'제어 실패');setMessage(action==='kill'?'긴급정지가 적용됐습니다.':'신규 진입을 중단했습니다.');onDone();}catch(e){setMessage(String(e));}finally{setBusy('');}};
 return <section className="controls"><div><span className="section-kicker">RISK CONTROL</span><h2>자동매매 제어</h2><p>{paused?'현재 신규 주문이 중단되어 있습니다.':'자동 루프가 조건을 감시하고 있습니다.'}</p>{message&&<small className="control-message">{message}</small>}</div><div className="control-actions"><button disabled={!!busy||paused} onClick={()=>command('pause')}><Power size={18}/>{busy==='pause'?'적용 중':'신규 진입 중단'}</button><button className="danger" disabled={!!busy} onClick={()=>command('kill')}><ShieldAlert size={18}/>{busy==='kill'?'적용 중':'긴급정지'}</button></div></section>;
}

function ActivityView({payload}:{payload:LivePayload|null}){
 const events=(payload?.events||[]).slice(0,20);
 return <div className="activity-grid"><section className="panel"><div className="panel-title"><div><span className="section-kicker">DECISIONS</span><h2>최근 판단·거래</h2></div></div>{events.length?<div className="event-list">{events.map((e:any,i:number)=><div className="event" key={e.id||i}><span className="event-dot"/><div><b>{e.payload?.market||e.kind||'운영 이벤트'}</b><p>{e.payload?.reason||e.payload?.strategy_label||e.kind||'기록'}</p></div><time>{stamp(e.time)}</time></div>)}</div>:<div className="empty-state">최근 기록이 없습니다.</div>}</section><section className="panel logs"><div className="panel-title"><div><span className="section-kicker">LIVE LOGS</span><h2>운영 기록</h2></div></div>{(payload?.terminal.sections||[]).map(s=><details key={s.label}><summary><span><Terminal size={15}/>{s.label}</span><time>{stamp(s.updated_at)}</time></summary><pre>{s.text||'기록 대기 중'}</pre></details>)}</section></div>;
}

function KiwoomTable({title,rows,rateKey}:{title:string;rows:KiwoomRow[];rateKey:'flu_rt'|'trde_qty'}){
 return <section className="panel"><div className="panel-title"><div><span className="section-kicker">KIWOOM</span><h2>{title}</h2></div><span>{rows.length}종목</span></div>{rows.length?<div className="positions">{rows.map((r,i)=><div className="position-row" key={r.stk_cd} style={{gridTemplateColumns:'2.4rem 1.6fr 1fr 1fr'}}><span>{i+1}</span><div className="asset"><div><b>{r.stk_nm}</b><small>{r.stk_cd.replace('_AL','')}</small></div></div><span data-label="현재가">{number(Math.abs(Number(r.cur_prc||0)),0)}원</span><strong data-label={rateKey==='flu_rt'?'등락률':'거래량'} className={rateKey==='flu_rt'?pnlClass(r.flu_rt):''}>{rateKey==='flu_rt'?`${r.flu_rt}%`:number(r.trde_qty,0)}</strong></div>)}</div>:<div className="empty-state">데이터가 없습니다.</div>}</section>;
}

function OrderBookRow({level,side,maxQty}:{level:OrderLevel;side:'ask'|'bid';maxQty:number}){
 const qty=Number(level.qty||0);const pct=maxQty?Math.min(100,qty/maxQty*100):0;
 const barColor=side==='ask'?'rgba(255,107,107,.16)':'rgba(103,240,193,.16)';
 return <div className="position-row" style={{gridTemplateColumns:'1fr 1fr',position:'relative',overflow:'hidden'}}>
  <div style={{position:'absolute',top:0,bottom:0,left:0,width:`${pct}%`,background:barColor,zIndex:0}}/>
  <span style={{position:'relative',color:side==='ask'?'var(--red)':'var(--green)',fontWeight:600}}>{number(Math.abs(Number(level.price||0)),0)}원</span>
  <span style={{position:'relative',textAlign:'right'}}>{number(qty,0)}</span>
 </div>;
}

function OrderBookView(){
 const [code,setCode]=useState('005930');const [input,setInput]=useState('005930');const [data,setData]=useState<OrderBook|null>(null);const [error,setError]=useState('');
 useEffect(()=>{let closed=false;const load=async()=>{try{const d=await get(`kiwoom/orderbook?code=${code}`);if(!closed){setData(d);setError('');}}catch(e){if(!closed)setError(String(e));}};load();const timer=window.setInterval(load,3000);return()=>{closed=true;clearInterval(timer);};},[code]);
 const maxQty=Math.max(1,...(data?.asks||[]).map(a=>Number(a.qty||0)),...(data?.bids||[]).map(b=>Number(b.qty||0)));
 return <section className="panel"><div className="panel-title"><div><span className="section-kicker">KIWOOM · 3초 폴링</span><h2>실시간 호가 (10단계)</h2></div>
  <form onSubmit={e=>{e.preventDefault();setCode(input.replace(/[^0-9]/g,'').slice(0,6)||'005930');}} style={{display:'flex',gap:8}}>
   <input value={input} onChange={e=>setInput(e.target.value)} placeholder="종목코드 (예: 005930)" style={{background:'#0d1218',border:'1px solid var(--line)',borderRadius:8,color:'#fff',padding:'7px 10px',width:130,fontSize:12}}/>
   <button type="submit" style={{border:'1px solid var(--line)',borderRadius:8,background:'transparent',color:'inherit',padding:'7px 12px',cursor:'pointer',fontSize:12}}>조회</button>
  </form></div>
  {error&&<div className="notice error"><AlertTriangle size={18}/>{error}</div>}
  {data&&!data.connected&&<div className="notice error"><AlertTriangle size={18}/>{data.error||'키움 연결 안 됨'}</div>}
  {data&&data.connected&&<>
   <small style={{color:'var(--muted)',display:'block',padding:'12px 20px 0'}}>{data.stk_cd} · 기준시각 {data.base_time.replace(/(\d\d)(\d\d)(\d\d)/,'$1:$2:$3')} · REST 스냅샷(웹소켓 실시간 아님, 3초마다 재조회)</small>
   <div className="table-head" style={{gridTemplateColumns:'1fr 1fr'}}><span>매도 호가</span><span style={{textAlign:'right'}}>잔량</span></div>
   {data.asks.map((a,i)=><OrderBookRow key={`ask-${i}`} level={a} side="ask" maxQty={maxQty}/>)}
   <div className="table-head" style={{gridTemplateColumns:'1fr 1fr',borderTop:'2px solid var(--line)'}}><span>매수 호가</span><span style={{textAlign:'right'}}>잔량</span></div>
   {data.bids.map((b,i)=><OrderBookRow key={`bid-${i}`} level={b} side="bid" maxQty={maxQty}/>)}
   <div className="account-foot" style={{padding:'13px 20px'}}><span>총 매도잔량 <b>{number(data.total_ask_qty,0)}</b></span><span>총 매수잔량 <b>{number(data.total_bid_qty,0)}</b></span></div>
  </>}
 </section>;
}

function KiwoomView(){
 const [data,setData]=useState<KiwoomRankings|null>(null);const [error,setError]=useState('');
 useEffect(()=>{let closed=false;const load=async()=>{try{const d=await get('kiwoom/rankings');if(!closed){setData(d);setError('');}}catch(e){if(!closed)setError(String(e));}};load();const timer=window.setInterval(load,30000);return()=>{closed=true;clearInterval(timer);};},[]);
 return <><div className="notice"><AlertTriangle size={18}/><div><b>참고용 시세 동향입니다</b><span>매수 추천이 아닙니다 — 이 저장소의 종목 스코어러(가치·가격·공시)를 통과한 종목이 아니라, 키움 순위 API가 보여주는 오늘의 등락률·거래량 상위일 뿐입니다.</span></div></div>
 {error&&<div className="notice error"><AlertTriangle size={18}/>{error}</div>}
 {data&&!data.connected&&<div className="notice error"><AlertTriangle size={18}/>{data.error||'키움 연결 안 됨'}</div>}
 {data&&data.connected&&<small style={{color:'var(--muted)',display:'block',margin:'4px 0 14px'}}>갱신 {stamp(data.as_of)} · 30초 캐시</small>}
 <OrderBookView/>
 <KiwoomTable title="전일대비 등락률 상위" rows={data?.top_change||[]} rateKey="flu_rt"/>
 <KiwoomTable title="당일 거래량 상위" rows={data?.top_volume||[]} rateKey="trde_qty"/>
 </>;
}

function App(){
 const [page,setPage]=useState<Page>('overview');const [payload,setPayload]=useState<LivePayload|null>(null);const [stream,setStream]=useState<'connecting'|'live'|'retry'>('connecting');const [error,setError]=useState('');
 const refresh=async()=>{try{const [overview,terminal,events]=await Promise.all([get('overview'),get('terminal'),get('events')]);setPayload({overview,terminal,events,streamed_at:new Date().toISOString()});setError('');}catch(e){setError(String(e));}};
 useEffect(()=>{refresh();let ws:WebSocket|null=null,timer:number|undefined,closed=false;const connect=()=>{setStream('connecting');const protocol=location.protocol==='https:'?'wss:':'ws:';ws=new WebSocket(`${protocol}//${location.host}/api/v1/events/live`);ws.onopen=()=>setStream('live');ws.onmessage=e=>{try{setPayload(JSON.parse(e.data));setStream('live');setError('');}catch{setError('실시간 데이터 처리 실패');}};ws.onerror=()=>ws?.close();ws.onclose=()=>{if(!closed){setStream('retry');timer=window.setTimeout(connect,2000);}};};connect();return()=>{closed=true;if(timer)clearTimeout(timer);ws?.close();};},[]);
 const data=payload?.overview;const upbit=data?.accounts.upbit;const binance=data?.accounts.binance_futures;const runtime=data?.runtime||{};const real=Boolean(runtime.real_trade_enabled)&&!runtime.paused;const positions=(upbit?.snapshot?.positions.length||0)+(binance?.snapshot?.positions.length||0);const unpriced=upbit?.snapshot?.unpriced||[];
 const pageTitle=page==='overview'?'운영 현황':page==='upbit'?'Upbit 현물':page==='binance'?'Binance 선물':page==='kiwoom'?'키움 국내주식 동향':'활동 기록';
 const tabs=useMemo(()=>[{id:'overview' as Page,label:'현황',icon:<Activity size={18}/>},{id:'upbit' as Page,label:'업비트',icon:<Bitcoin size={18}/>},{id:'binance' as Page,label:'바이낸스',icon:<CircleDollarSign size={18}/>},{id:'kiwoom' as Page,label:'키움',icon:<TrendingUp size={18}/>},{id:'activity' as Page,label:'기록',icon:<Terminal size={18}/>}],[]);
 return <div className="shell"><header className="topbar"><div className="identity"><span className="logo">A</span><div><b>ATEMOYA</b><small>TRADING OPERATIONS</small></div></div><nav>{tabs.map(t=><button key={t.id} className={page===t.id?'active':''} onClick={()=>setPage(t.id)}>{t.icon}<span>{t.label}</span></button>)}</nav><div className="top-status"><span className={`stream ${stream}`}>{stream==='live'?<Wifi size={15}/>:<WifiOff size={15}/>} {stream==='live'?'실시간':'재연결 중'}</span><button className="refresh" aria-label="새로고침" onClick={refresh}><RefreshCw size={17}/></button></div></header><main><div className="page-head"><div><span className="section-kicker">LIVE COMMAND CENTER</span><h1>{pageTitle}</h1><p>Upbit 현물과 Binance 선물 자동매매 상태</p></div><div className={`engine ${real?'running':'stopped'}`}><span/><div><b>{real?'실주문 루프 실행 중':'주문 루프 중단'}</b><small>마지막 응답 {stamp(runtime.last_heartbeat)}</small></div></div></div>{error&&<div className="notice error"><AlertTriangle size={18}/>{error}</div>}
 {page==='overview'&&<><div className="account-grid"><AccountCard name="Upbit" badge="U" account={upbit} accent="upbit"/><AccountCard name="Binance Futures" badge="B" account={binance} accent="binance"/></div><div className="metric-grid"><Metric label="전체 포지션" value={`${positions}개`} sub="두 거래소 합계" icon={<WalletCards size={20}/>}/><Metric label="기본 주문" value={money(data?.settings.buy_amount_krw)} sub={`최대 보유 ${String(data?.settings.max_positions??'—')}개`} icon={<CircleDollarSign size={20}/>}/><Metric label="운영 모드" value={real?'실거래':'중단'} sub={runtime.dry_run?'모의 주문':'실주문 허용'} tone={real?'positive':'negative'} icon={<Activity size={20}/>}/><Metric label="루프 응답" value={stamp(runtime.last_heartbeat)} sub="자동 전략 감시" icon={<Clock3 size={20}/>} /></div>{unpriced.length>0&&<div className="notice"><AlertTriangle size={18}/><div><b>가격 미확인 자산 {unpriced.length}개</b><span>{unpriced.join(' · ')} — 총자산과 손익 합계에서 분리했습니다.</span></div></div>}<section className="panel"><div className="panel-title"><div><span className="section-kicker">OPEN POSITIONS</span><h2>보유 포지션</h2></div><button onClick={()=>setPage('upbit')}>전체 보기</button></div><PositionList account={upbit} kind="upbit"/></section><Controls runtime={runtime} onDone={refresh}/></>}
 {page==='upbit'&&<><AccountCard name="Upbit" badge="U" account={upbit} accent="upbit"/><section className="panel"><div className="panel-title"><div><span className="section-kicker">SPOT POSITIONS</span><h2>현물 보유자산</h2></div><span>{upbit?.snapshot?.positions.length||0}개</span></div><PositionList account={upbit} kind="upbit"/></section><Controls runtime={runtime} onDone={refresh}/></>}
 {page==='binance'&&<><AccountCard name="Binance Futures" badge="B" account={binance} accent="binance"/><section className="panel"><div className="panel-title"><div><span className="section-kicker">FUTURES POSITIONS</span><h2>선물 포지션</h2></div><span>{binance?.snapshot?.positions.length||0}개</span></div><PositionList account={binance} kind="binance"/></section><Controls runtime={runtime} onDone={refresh}/></>}
 {page==='kiwoom'&&<KiwoomView/>}
 {page==='activity'&&<ActivityView payload={payload}/>}</main><nav className="mobile-nav">{tabs.map(t=><button key={t.id} className={page===t.id?'active':''} onClick={()=>setPage(t.id)}>{t.icon}<span>{t.label}</span></button>)}</nav></div>;
}

createRoot(document.getElementById('root')!).render(<App/>);
