import { readFileSync, writeFileSync } from "node:fs";

const config={
  affiliateUrl:process.env.ATEMOYA_AFFILIATE_URL||"",
  affiliateUrls:{
    humidifier:process.env.AFFILIATE_HUMIDIFIER||"",heating:process.env.AFFILIATE_HEATING||"",
    purifier:process.env.AFFILIATE_PURIFIER||"",disposer:process.env.AFFILIATE_DISPOSER||"",
    robot:process.env.AFFILIATE_ROBOT||"",beauty:process.env.AFFILIATE_BEAUTY||"",
    feeder:process.env.AFFILIATE_FEEDER||"",llm:process.env.AFFILIATE_LLM||"",
    travel:process.env.AFFILIATE_TRAVEL||"",blackfriday:process.env.AFFILIATE_BLACKFRIDAY||""
  },
  affiliateDisclosure:"이 포스팅은 제휴 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다.",
  gaMeasurementId:process.env.ATEMOYA_GA_ID||"",
  adsenseClient:process.env.ATEMOYA_ADSENSE_CLIENT||"",
  contactEmail:process.env.ATEMOYA_CONTACT_EMAIL||"",
  googleSiteVerification:process.env.ATEMOYA_GOOGLE_VERIFY||"",
  naverSiteVerification:process.env.ATEMOYA_NAVER_VERIFY||""
};
writeFileSync("config.js",`window.ATEMOYA_CONFIG=${JSON.stringify(config)};\n`);
const verification=[
  config.googleSiteVerification&&`<meta name="google-site-verification" content="${config.googleSiteVerification.replace(/[\"<>]/g,"")}">`,
  config.naverSiteVerification&&`<meta name="naver-site-verification" content="${config.naverSiteVerification.replace(/[\"<>]/g,"")}">`
].filter(Boolean).join("");
if(verification){for(const file of ["index.html","tools/humidifier-calculator.html"]){const html=readFileSync(file,"utf8");writeFileSync(file,html.replace("</head>",verification+"</head>"))}}
