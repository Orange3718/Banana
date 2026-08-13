import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const outputRoot = resolve(root, 'channel-drafts/generated');
const catalog = JSON.parse(readFileSync(resolve(root, 'stories/catalog.json'), 'utf8'));
const baseUrl = (process.env.SITE_BASE_URL || 'https://YOUR-DOMAIN.example').replace(/\/$/, '');
const disclosure = '이 콘텐츠에는 제휴 링크가 포함될 수 있으며, 링크를 통한 구매 시 일정액의 수수료를 제공받을 수 있습니다. 구매 가격에는 영향을 주지 않습니다.';
const generatedAt = new Date().toISOString();

const clean = value => String(value).replace(/\s+/g, ' ').trim();
const esc = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const hash = value => createHash('sha256').update(clean(value)).digest('hex');
const write = (path, value) => {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, value.endsWith('\n') ? value : `${value}\n`);
};
const json = value => `${JSON.stringify(value, null, 2)}\n`;
const absolute = relative => new URL(relative.replace(/^\.\.\//, ''), `${baseUrl}/`).toString();
const utm = (url, source, medium, campaign, content) => {
  const parsed = new URL(url);
  parsed.searchParams.set('utm_source', source);
  parsed.searchParams.set('utm_medium', medium);
  parsed.searchParams.set('utm_campaign', campaign);
  parsed.searchParams.set('utm_content', content);
  return parsed.toString();
};

rmSync(outputRoot, { recursive: true, force: true });

const manifest = {
  schemaVersion: 1,
  generatedAt,
  baseUrl,
  mode: baseUrl.includes('YOUR-DOMAIN') ? 'template' : 'publish-ready',
  policy: {
    externalPublishing: false,
    canonicalOwner: 'atemoya-web',
    duplicateProtection: 'channel-specific copy + SHA-256 fingerprint',
    affiliateDisclosureRequired: true,
  },
  totals: { stories: catalog.length, assets: 0, ready: 0, needsConfiguration: 0 },
  items: [],
};

for (const item of catalog) {
  const canonicalUrl = `${baseUrl}/stories/${item.slug}.html`;
  const campaign = `commerce_${item.category}`;
  const storyDir = resolve(outputRoot, item.slug);
  const numbers = item.numbers.map(value => {
    const [number, meaning] = value.split('|');
    return { number, meaning };
  });
  const sourcePayload = {
    slug: item.slug,
    canonicalUrl,
    title: item.title,
    description: item.dek,
    disclosure,
    cta: {
      label: '내 조건으로 숫자 확인하기',
      url: utm(canonicalUrl, 'atemoya', 'owned_web', campaign, 'story_cta'),
    },
    contentFingerprint: hash(`${item.title}|${item.dek}|${item.hook}|${item.story}|${item.turn}`),
  };

  const bloggerUrl = utm(canonicalUrl, 'blogger', 'referral', campaign, 'article_cta');
  const bloggerHtml = `<p><strong>${esc(disclosure)}</strong></p>
<p>${esc(item.hook)}</p>
<h2>${esc(item.label)}를 고르기 전에 놓치기 쉬운 숫자</h2>
<p>${esc(item.story)}</p>
<ul>${numbers.map(value => `<li><strong>${esc(value.number)}</strong> — ${esc(value.meaning)}</li>`).join('')}</ul>
<h2>결제 직전 확인할 것</h2>
<p>${esc(item.turn)}</p>
<ol>${item.questions.map(value => `<li>${esc(value)}</li>`).join('')}</ol>
<p><a href="${esc(bloggerUrl)}" rel="sponsored nofollow">조건별 계산과 전체 구매 가이드 보기</a></p>
<p>원문: <a href="${esc(canonicalUrl)}" rel="canonical">${esc(canonicalUrl)}</a></p>`;
  const blogger = {
    kind: 'blogger#post',
    title: `${item.title}｜${item.label} 구매 전 체크`,
    content: bloggerHtml,
    labels: [item.label, '구매가이드', '숨은비용', 'Atemoya'],
    customMeta: { canonicalUrl, isDraft: true, disclosureIncluded: true },
  };

  const tistoryUrl = utm(canonicalUrl, 'tistory', 'referral', campaign, 'article_cta');
  const tistory = `<!-- Tistory HTML mode용 초안: 자동 게시하지 않음 -->
<p><b>${esc(disclosure)}</b></p>
<p>${esc(item.dek)}</p>
<blockquote>${esc(item.hook)}</blockquote>
<h2>싸게 사는 것보다 먼저 볼 조건</h2>
<p>${esc(item.turn)}</p>
<h3>숫자로 빠르게 확인하기</h3>
<table><tbody>${numbers.map(value => `<tr><th>${esc(value.number)}</th><td>${esc(value.meaning)}</td></tr>`).join('')}</tbody></table>
<h3>체크리스트</h3>
<ul>${item.questions.map(value => `<li>${esc(value)}</li>`).join('')}</ul>
<p><a href="${esc(tistoryUrl)}" rel="sponsored nofollow">무료 계산기와 상세 근거 확인하기 →</a></p>
<p><small>이 글의 원본과 최신 수정본: ${esc(canonicalUrl)}</small></p>`;

  const naverUrl = utm(canonicalUrl, 'naver_blog', 'referral', campaign, 'article_cta');
  const naver = `[제목]\n${item.label}, ${item.title}\n\n[제휴 고지]\n${disclosure}\n\n[도입]\n${item.dek}\n${item.hook}\n\n[핵심]\n${item.turn}\n\n[숫자 메모]\n${numbers.map(value => `• ${value.number}: ${value.meaning}`).join('\n')}\n\n[구매 전 체크]\n${item.questions.map((value, index) => `${index + 1}. ${value}`).join('\n')}\n\n[CTA]\n내 조건으로 계산하고 상세 근거 보기\n${naverUrl}\n\n[원본·최신 수정본]\n${canonicalUrl}\n\n#${item.label.replace(/\s/g, '')} #구매가이드 #숨은비용 #Atemoya`;

  const threadsUrl = utm(canonicalUrl, 'threads', 'social', campaign, 'hook_post');
  const instagramUrl = utm(canonicalUrl, 'instagram', 'social', campaign, 'caption');
  const social = {
    threads: {
      status: 'draft',
      posts: [
        `${item.title}\n\n${item.hook}\n\n결론: ${item.turn}\n\n${disclosure}\n${threadsUrl}`,
        `${item.label} 살 때 확인할 3가지\n${item.questions.map((value, index) => `${index + 1}) ${value}`).join('\n')}\n\n저장해두고 결제 직전에 확인하세요.\n${threadsUrl}`,
      ],
    },
    instagram: {
      status: 'draft',
      caption: `${item.title}\n\n${item.dek}\n\n${numbers.map(value => `✓ ${value.number} — ${value.meaning}`).join('\n')}\n\n${item.turn}\n\n${disclosure}\n프로필 링크: ${instagramUrl}\n\n#${item.label.replace(/\s/g, '')} #구매팁 #생활비절약 #제품비교 #Atemoya`,
      carousel: [item.title, '가격표에 없는 비용', ...numbers.map(value => `${value.number}\n${value.meaning}`), '구매 전 세 가지 확인', '프로필 링크에서 계산'],
    },
  };

  const youtubeUrl = utm(canonicalUrl, 'youtube', 'video', campaign, 'description');
  const youtube = {
    status: 'script-ready',
    productionMode: 'no-video-generated',
    titleOptions: [item.title, `${item.label} 사기 전 이 숫자부터 보세요`, `${item.label}, 가격만 보고 사면 생기는 일`],
    thumbnailBrief: {
      style: '따뜻한 아마존 편집 삽화풍, 손그림 잉크선, 크림색 종이 질감, 사이버펑크 금지',
      composition: `${item.label} 제품과 숨은 비용을 상징하는 영수증 또는 경고 표식을 좌우 대비로 배치`,
      textOptions: ['이 비용, 보셨나요?', '싸게 샀는데 왜?', numbers[0]?.number || '숨은 숫자'],
      safeArea: '1280×720, 텍스트는 중앙 80% 영역, 모바일에서도 3초 안에 읽히게 6단어 이하',
    },
    script: [
      { section: '0:00 Hook', text: item.hook },
      { section: '0:12 Problem', text: item.story },
      { section: '0:45 Numbers', text: numbers.map(value => `${value.number}, ${value.meaning}`).join('. ') },
      { section: '1:15 Decision', text: item.turn },
      { section: '1:45 Checklist', text: item.questions.join('. ') },
      { section: '2:10 CTA', text: `설명란의 무료 계산기에서 내 조건으로 확인하세요. ${disclosure}` },
    ],
    description: `${item.dek}\n\n무료 계산기·전체 근거: ${youtubeUrl}\n원문: ${canonicalUrl}\n\n${disclosure}\n\n#${item.label.replace(/\s/g, '')} #구매가이드 #Atemoya`,
  };

  const outputs = {
    'web.json': json(sourcePayload),
    'blogger-draft.json': json(blogger),
    'tistory-copy-paste.html': `${tistory}\n`,
    'naver-draft.txt': `${naver}\n`,
    'social-drafts.json': json(social),
    'youtube-package.json': json(youtube),
  };
  const fingerprints = {};
  for (const [filename, content] of Object.entries(outputs)) {
    write(resolve(storyDir, filename), content);
    fingerprints[filename] = hash(content);
  }
  const duplicateFingerprints = Object.values(fingerprints).filter((value, index, all) => all.indexOf(value) !== index);
  if (duplicateFingerprints.length) throw new Error(`${item.slug}: channel output duplication detected`);

  const configured = !baseUrl.includes('YOUR-DOMAIN');
  const record = {
    slug: item.slug,
    category: item.category,
    title: item.title,
    canonicalUrl,
    status: configured ? 'ready-for-review' : 'needs-site-url',
    publishing: { web: 'not-published', blogger: 'draft-only', tistory: 'copy-paste-only', naver: 'copy-paste-only', threads: 'draft-only', instagram: 'draft-only', youtube: 'script-only' },
    fingerprints,
  };
  write(resolve(storyDir, 'status.json'), json(record));
  manifest.items.push(record);
  manifest.totals.assets += Object.keys(outputs).length + 1;
  configured ? manifest.totals.ready++ : manifest.totals.needsConfiguration++;
}

write(resolve(outputRoot, 'manifest.json'), json(manifest));
write(resolve(outputRoot, 'README.md'), `# 생성된 멀티채널 초안\n\n- 생성 시각: ${generatedAt}\n- 원본 사이트: ${baseUrl}\n- 스토리: ${catalog.length}개\n- 외부 자동 게시: 꺼짐\n- 상태표: \`manifest.json\`\n\n\`SITE_BASE_URL=https://example.com node scripts/build-channel-drafts.mjs\`로 실제 원본 URL과 UTM 링크를 다시 생성합니다.\n`);

console.log(`Generated ${manifest.totals.assets} draft assets for ${catalog.length} stories.`);
console.log(`Mode: ${manifest.mode}; manifest: channel-drafts/generated/manifest.json`);
