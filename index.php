<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes" />
  <title>养虾助手 · 拌料计算 & 离线查料 & 知识测验</title>
  <meta name="description" content="专为养虾人设计的手机工具：拌料计算器、离线材料查询、养殖知识测验。提升效率，随时可用。" />
  <meta name="theme-color" content="#0a7e8c" />
  <!-- Apple 全屏模式及图标 (示意) -->
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
  <link rel="apple-touch-icon" href="/promo-site/assets/icons/icon-192.png" />
  <!-- Manifest (请确保文件真实存在) -->
  <link rel="manifest" href="/promo-site/manifest.json" />
  <!-- 基础样式内嵌以保证核心展示，外部样式可作为增强 -->
  <style>
    /* 全局重置与字体 */
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
      background: #f4f9fb;
      color: #1e2f4d;
      line-height: 1.5;
      scroll-behavior: smooth;
    }
    .container {
      max-width: 960px;
      margin: 0 auto;
      padding: 1.5rem 1rem;
    }
    /* 头部 */
    .site-header {
      background: #ffffffcc;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      box-shadow: 0 2px 10px rgba(0,40,40,0.05);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .header-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.75rem 1rem;
    }
    .logo {
      font-weight: 600;
      font-size: 1.4rem;
      background: linear-gradient(135deg, #0a7e8c, #1e5d7c);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .main-nav a {
      margin-left: 1.2rem;
      text-decoration: none;
      color: #1e2f4d;
      font-weight: 500;
      font-size: 1.05rem;
      transition: color 0.2s;
    }
    .main-nav a:hover { color: #0a7e8c; }
    /* 通用标题 */
    h2 {
      font-size: 2rem;
      font-weight: 600;
      margin-bottom: 1.5rem;
      letter-spacing: -0.01em;
      background: linear-gradient(145deg, #0a5e6c, #164a5f);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    /* hero */
    .hero {
      background: linear-gradient(115deg, #d2ecf2 0%, #b6dee9 100%);
      border-radius: 0 0 2.5rem 2.5rem;
      margin: 0 0.5rem;
      padding: 2.5rem 1rem;
      text-align: center;
    }
    .hero-content h1 {
      font-size: 2.1rem;
      font-weight: 700;
      line-height: 1.2;
      max-width: 700px;
      margin: 0 auto 1rem;
      color: #093c4b;
    }
    .hero p {
      font-size: 1.2rem;
      color: #1a4c5c;
      max-width: 600px;
      margin: 0 auto 2rem;
    }
    .cta {
      display: inline-block;
      background: #0a7e8c;
      color: white;
      padding: 0.9rem 2.2rem;
      border-radius: 60px;
      font-weight: 600;
      font-size: 1.2rem;
      text-decoration: none;
      box-shadow: 0 8px 20px #0a7e8c60;
      transition: 0.2s;
      border: none;
      cursor: pointer;
    }
    .cta:hover {
      background: #0e96a8;
      transform: scale(1.02);
      box-shadow: 0 12px 24px #0a7e8ca0;
    }
    /* why 区域列表 */
    #why ul {
      list-style: none;
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fit, minmax(220px,1fr));
      margin-top: 1.8rem;
    }
    #why li {
      background: white;
      padding: 1.8rem 1.2rem;
      border-radius: 1.8rem;
      box-shadow: 0 6px 14px #d0e3e9;
      font-weight: 500;
      border: 1px solid #ffffff80;
      backdrop-filter: blur(4px);
      display: flex;
      align-items: center;
      gap: 0.8rem;
    }
    #why li::before {
      content: "🦐";
      font-size: 1.8rem;
      filter: drop-shadow(0 2px 2px #577e8a);
    }
    /* 特性网格 */
    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 2rem;
      margin: 2rem 0;
    }
    .feature {
      background: white;
      border-radius: 2rem;
      padding: 2rem 1.5rem;
      text-align: center;
      box-shadow: 0 12px 24px -8px #b3d3dc;
      transition: all 0.2s;
      border: 1px solid #e2f0f5;
    }
    .feature:hover { transform: translateY(-6px); }
    .icon {
      font-size: 3.3rem;
      margin-bottom: 0.8rem;
    }
    .feature h3 { margin: 0.5rem 0; color: #0a5e70; }
    /* 测验卡片 */
    .quiz-card {
      background: white;
      border-radius: 2rem;
      padding: 2rem 1.8rem;
      box-shadow: 0 12px 28px #c0dbe3;
      margin: 2rem 0 1.5rem;
    }
    .q {
      border: none;
      margin-bottom: 2rem;
      padding: 0.5rem 0;
    }
    .q legend {
      font-weight: 600;
      font-size: 1.2rem;
      margin-bottom: 0.75rem;
      color: #145b6b;
    }
    .q label {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin: 0.7rem 0 0.7rem 1.5rem;
      font-size: 1.05rem;
      background: #f2fafd;
      padding: 0.5rem 1.2rem;
      border-radius: 40px;
      border: 1px solid #cbe7f0;
      cursor: pointer;
      transition: 0.1s;
    }
    .q label:hover { background: #dff2f8; }
    input[type=radio] {
      width: 1.2rem;
      height: 1.2rem;
      accent-color: #0a7e8c;
    }
    .btn {
      background: #154f61;
      color: white;
      border: none;
      padding: 1rem 2.2rem;
      border-radius: 60px;
      font-weight: 600;
      font-size: 1.2rem;
      cursor: pointer;
      box-shadow: 0 4px 12px #0a4d5e70;
      transition: 0.15s;
      margin-right: 0.5rem;
      border: 1px solid #26879b;
    }
    .btn:hover { background: #1d677d; }
    .quiz-result {
      background: #def0f5;
      border-radius: 2rem;
      padding: 1.6rem;
      margin: 1.5rem 0 0.5rem;
      white-space: pre-line;
      border-left: 6px solid #0a7e8c;
    }
    .quiz-result h4 { margin-bottom: 0.8rem; color: #023b48; }
    .quiz-result .correct-msg { color: #086343; font-weight: 500; }
    .quiz-result .wrong-msg { color: #a12d2d; }
    /* 下载区域 */
    #download {
      text-align: center;
      background: #e1f1f5;
      border-radius: 3rem 3rem 1.5rem 1.5rem;
      margin-top: 2rem;
    }
    .note {
      margin-top: 1.8rem;
      color: #536d79;
      font-size: 0.95rem;
    }
    .apk-hint {
      background: #fff7e0;
      padding: 0.5rem 1rem;
      border-radius: 50px;
      font-size: 0.9rem;
      display: inline-block;
      margin-top: 1rem;
    }
    .site-footer {
      text-align: center;
      color: #557885;
      border-top: 1px solid #cae2ea;
      margin-top: 2rem;
      font-size: 0.95rem;
    }
    @media (max-width: 480px) {
      h2 { font-size: 1.8rem; }
      .hero-content h1 { font-size: 1.8rem; }
      .main-nav a { margin-left: 0.8rem; font-size: 0.95rem; }
      .feature { padding: 1.5rem 1rem; }
      .q label { margin-left: 0.5rem; }
    }
  </style>
  <!-- 预连接（可选） -->
  <link rel="preconnect" href="http://53102897.nat123.top" />
</head>
<body>
  <header class="site-header" aria-label="顶部导航栏">
    <div class="container header-inner">
      <div class="logo" aria-label="养虾助手">🦐 养虾助手</div>
      <nav class="main-nav" aria-label="主要页面跳转">
        <a href="#home">首页</a>
        <a href="#features">特性</a>
        <a href="#quiz">测验</a>
        <a href="#download">下载</a>
      </nav>
    </div>
  </header>

  <section class="hero" id="home" aria-labelledby="hero-heading">
    <div class="container hero-content">
      <h1 id="hero-heading">拌料计算、离线查料、知识测验<br>养虾人的随身工具</h1>
      <p>不用纸笔，不用网络，快速计算配料，随时查阅材料，碎片时间刷题巩固技术。</p>
      <a class="cta" href="#download" aria-label="下载养虾助手应用">立即下载 →</a>
    </div>
  </section>

  <section id="why" class="container" aria-labelledby="why-heading">
    <h2 id="why-heading">为什么用养虾助手？</h2>
    <ul>
      <li>拌料计算：减少误差，投喂一致，节省时间</li>
      <li>离线查料：塘边无网络也能查配方、材料</li>
      <li>知识测验：养殖题库 + 答案解析，提升技术</li>
      <li>完全离线可用，简单直接，无广告</li>
    </ul>
  </section>

  <section id="features" class="features container" aria-labelledby="features-heading">
    <h2 id="features-heading">核心特性</h2>
    <div class="features-grid">
      <div class="feature">
        <div class="icon" aria-hidden="true">🧮</div>
        <h3>拌料计算器</h3>
        <p>按配方和比重快速算料，避免浪费，提升投喂科学性。</p>
      </div>
      <div class="feature">
        <div class="icon" aria-hidden="true">📂</div>
        <h3>离线材料库</h3>
        <p>预载常用原料、添加剂信息，现场查阅，无需流量。</p>
      </div>
      <div class="feature">
        <div class="icon" aria-hidden="true">🧠</div>
        <h3>知识测验</h3>
        <p>涵盖水质、营养、病害，边答边学，进步可见。</p>
      </div>
    </div>
  </section>

  <section id="quiz" class="quiz container" aria-labelledby="quiz-heading">
    <h2 id="quiz-heading">📝 养虾小测验</h2>
    <p>4道基础题，测测你的养虾常识（提交后显示答案）</p>
    <div class="quiz-card" id="quiz-card">
      <!-- 使用 fieldset 增强可访问性 -->
      <fieldset class="q" data-id="q1">
        <legend>1️⃣ 拌料时，哪种原料过量最容易导致水质恶化？</legend>
        <label><input type="radio" name="q1" value="A" /> A. 过多蛋白质原料</label>
        <label><input type="radio" name="q1" value="B" /> B. 低蛋白高纤维配比</label>
        <label><input type="radio" name="q1" value="C" /> C. 合理的碳氮比</label>
      </fieldset>
      <fieldset class="q" data-id="q2">
        <legend>2️⃣ 养虾常用的优质蛋白质来源是？</legend>
        <label><input type="radio" name="q2" value="A" /> A. 玉米</label>
        <label><input type="radio" name="q2" value="B" /> B. 大豆粉/豆粕</label>
        <label><input type="radio" name="q2" value="C" /> C. 面粉</label>
      </fieldset>
      <fieldset class="q" data-id="q3">
        <legend>3️⃣ 以下哪项最有助于维持水体稳定？</legend>
        <label><input type="radio" name="q3" value="A" /> A. 频繁大量换水</label>
        <label><input type="radio" name="q3" value="B" /> B. 稳定的底质管理与日常监测</label>
        <label><input type="radio" name="q3" value="C" /> C. 高温高盐暴喂</label>
      </fieldset>
      <fieldset class="q" data-id="q4">
        <legend>4️⃣ 如果需要离线工作，首要具备的功能是？</legend>
        <label><input type="radio" name="q4" value="A" /> A. 离线数据缓存</label>
        <label><input type="radio" name="q4" value="B" /> B. 线上实时同步</label>
        <label><input type="radio" name="q4" value="C" /> C. 导出CSV报表</label>
      </fieldset>
    </div>
    <button id="submit-quiz" class="btn">📊 提交并查看解析</button>
    <div id="quiz-result" class="quiz-result" aria-live="polite" role="status"></div>
  </section>

  <section id="download" class="download container" aria-labelledby="download-heading">
    <h2 id="download-heading">📲 开始使用</h2>
    <p>下载安卓APK，安装后即可离线使用所有功能。</p>
    <a class="cta" href="http://53102897.nat123.top/养虾助手1.66.89.apk" rel="noopener noreferrer" target="_blank" aria-label="下载APK文件（请确认来源）">⬇️ 下载APK (v1.66.89)</a>

    <p class="note">静态推广页 | 所有功能均可在应用内离线使用</p>
  </section>

  <footer class="site-footer container" aria-label="页脚信息">
    <p>© 2026 养虾助手 · 让养殖更轻松</p>
    <p style="font-size:0.85rem; margin-top:0.3rem;">🪪 本页为PWA示范，支持添加到主屏幕</p>
  </footer>

  <!-- 交互脚本：测验逻辑、平滑锚点等 -->
  <script>
    (function() {
      // 测验正确答案（可根据实际题库调整）
      const ANSWERS = { q1: 'A', q2: 'B', q3: 'B', q4: 'A' };
      const EXPLANATIONS = {
        q1: '过多蛋白质未被同化，会转化为氨氮，恶化水质。',
        q2: '豆粕/大豆粉是虾料最常用的植物蛋白；玉米、面粉能量高但蛋白低。',
        q3: '频繁换水反而应激；稳定底质和监测才是根本。',
        q4: '离线工作的核心是本地缓存数据，保证无网可用。'
      };

      const submitBtn = document.getElementById('submit-quiz');
      const resultDiv = document.getElementById('quiz-result');

      function evaluateQuiz() {
        let selected = {};
        let allSelected = true;
        for (let q in ANSWERS) {
          const radios = document.getElementsByName(q);
          let checkedVal = null;
          for (let radio of radios) {
            if (radio.checked) {
              checkedVal = radio.value;
              break;
            }
          }
          if (!checkedVal) allSelected = false;
          selected[q] = checkedVal;
        }

        if (!allSelected) {
          resultDiv.innerHTML = '<span style="color:#b44;">⚠️ 请先回答全部4道题再提交</span>';
          return;
        }

        let correctCount = 0;
        let html = '<h4>📋 测验结果与解析</h4>';
        for (let q in ANSWERS) {
          const userAns = selected[q] || '(未选)';
          const isCorrect = (userAns === ANSWERS[q]);
          if (isCorrect) correctCount++;
          const icon = isCorrect ? '✅' : '❌';
          const qNumber = q.replace('q', '第');
          html += `<p><strong>${qNumber}题</strong> ${icon} 你的答案: ${userAns || '无'}  `;
          html += `(正确答案: ${ANSWERS[q]}) <br> <span style="margin-left:1.2rem;font-size:0.95rem;">📌 ${EXPLANATIONS[q]}</span></p>`;
        }
        html += `<p style="font-size:1.3rem; margin-top:1rem;">🎯 得分: ${correctCount} / 4 ${correctCount === 4 ? '👍 太棒了！' : correctCount >= 2 ? '🐟 继续加油' : '🦐 多看看知识库'}</p>`;
        resultDiv.innerHTML = html;
        // 滚动到结果以便查看
        resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }

      submitBtn.addEventListener('click', evaluateQuiz);

      // 平滑内部锚点 (对导航增强)
      document.querySelectorAll('.main-nav a[href^="#"], .cta[href^="#"]').forEach(link => {
        link.addEventListener('click', function(e) {
          const targetId = this.getAttribute('href');
          if (targetId === '#') return;
          const targetEl = document.querySelector(targetId);
          if (targetEl) {
            e.preventDefault();
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // 可选更新url hash (不强制)
            history.pushState(null, null, targetId);
          }
        });
      });

      // 若url直接带hash，平滑滚动
      if (window.location.hash) {
        const el = document.querySelector(window.location.hash);
        if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth' }), 100);
      }


  </script>

  <!-- 简单的Service Worker 注册 (需确保 /promo-site/service-worker.js 存在且支持离线) -->
  <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function() {
        navigator.serviceWorker.register('/promo-site/service-worker.js').catch(function(err) {
          console.log('SW注册失败，可能是路径问题或非https环境', err);
        });
      });
    }
  </script>
</body>
</html>