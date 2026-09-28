import React, {useEffect, useState} from 'react';

export default function PaperPanel() {
  const [data, setData] = useState<any>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const r = await fetch('/api/v1/paper');
        if (!r.ok) throw Error();
        const body = await r.json();
        if (active) { setData(body); setFailed(false); }
      } catch { if (active) setFailed(true); }
    };
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  const rows = data?.portfolios || [];
  const health = Object.values(data?.health || {}) as any[];
  const healthy = health.length === 5 && health.every(h => h.status === 'connected' && Date.now() - Date.parse(h.as_of) < 180000);
  return <section style={{padding:'20px 24px', borderBottom:'1px solid #3c4b54'}}>
    <h2>자동 모의운용 <small className={healthy && !failed ? 'good' : 'warning'}>{failed ? '결과 조회 실패' : healthy ? '수집 정상' : '수집 대기 또는 지연'}</small></h2>
    <p className="muted">가상 자금 · 1시간봉 · 매수 방향 · 진입 비중 20% · 실주문 비활성</p>
    <p className="warning">비용 가정: 편도 수수료 0.1% + 슬리피지 0.1%. Binance 펀딩비 미반영 · 수익 우위 미검증</p>
    <div className="table-scroll"><table><thead><tr><th>거래소 / 종목</th><th>전략</th><th>가상 평가액</th><th>수익률</th><th>최대낙폭</th><th>완료 거래</th><th>최근 판단</th></tr></thead>
      <tbody>{rows.map((r:any) => <tr key={r.exchange+r.symbol+r.strategy}>
        <td>{r.exchange} · {r.symbol}<small>{r.symbol === 'SAMSUNGUSDT' ? '삼성전자 연동 선물' : r.symbol === 'SKHYNIXUSDT' ? 'SK하이닉스 연동 선물' : r.currency}</small></td>
        <td>{r.strategy}</td><td>{r.equity.toLocaleString('ko-KR', {maximumFractionDigits:2})} {r.currency}</td>
        <td>{r.return_pct.toFixed(2)}%</td><td>{r.drawdown.toFixed(2)}%</td><td>{r.trades}</td>
        <td className="wrap">{r.halted ? '신규 진입 중지 · ' : ''}{r.reason}<small>{new Date(r.as_of).toLocaleString('ko-KR')}</small></td>
      </tr>)}</tbody></table></div>
    {!rows.length && <p>첫 시장 데이터 수집 대기</p>}
  </section>;
}
