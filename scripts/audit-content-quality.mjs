import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const items = JSON.parse(readFileSync(resolve(root, 'stories/catalog.json'), 'utf8'));
const danger = /(충격|무조건|역대급|대박|100%|완치|기적|절대)/i;
const rows = items.map(x => {
  const checks = {
    accurateSpecificHook: /\d|비용|가격|전기료|메모리|용량|문턱|필터|소모품/.test(x.title),
    unresolvedTension: /(이유|착각|무서운|멈추는|요구|못|비싸게|될 수)/.test(x.title),
    concreteEvidence: Array.isArray(x.numbers) && x.numbers.length >= 3,
    decisionHelp: Array.isArray(x.questions) && x.questions.length >= 3,
    toolBridge: typeof x.tool === 'string' && x.tool.length > 0,
    honestPackaging: !danger.test(x.title),
    conciseTitle: [...x.title].length <= 38,
    mobileThumbnail: Boolean(x.image || x.emoji),
  };
  const score = Math.round(Object.values(checks).filter(Boolean).length / Object.keys(checks).length * 100);
  return {slug:x.slug, category:x.label, title:x.title, score, checks,
    next: score >= 88 ? 'READY_FOR_TEST' : 'IMPROVE_BEFORE_PUBLISH'};
});
const duplicateTitles = rows.filter((x,i) => rows.findIndex(y => y.title === x.title) !== i).length;
const result = {
  generatedAt: new Date().toISOString(),
  benchmarkRules: [
    '정확한 제목과 호기심의 결합',
    '첫 화면에서 문제 또는 비교를 즉시 제시',
    '최소 3개의 확인 가능한 숫자와 3개의 구매 질문',
    '글에서 무료 도구로 자연스럽게 이동',
    '과장형 클릭베이트 금지',
    '게시 후 노출·CTR·체류·제휴클릭을 함께 평가',
  ],
  summary: {assets:rows.length, averageScore:Math.round(rows.reduce((a,b)=>a+b.score,0)/rows.length), duplicateTitles},
  items: rows,
};
writeFileSync(resolve(root, 'content-quality-report.json'), JSON.stringify(result,null,2)+'\n');
console.log(`PASS: ${rows.length} assets, avg=${result.summary.averageScore}, duplicateTitles=${duplicateTitles}`);
if (duplicateTitles || rows.some(x => x.score < 75)) process.exitCode = 1;
