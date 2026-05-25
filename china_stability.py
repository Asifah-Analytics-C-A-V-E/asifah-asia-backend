<!DOCTYPE html>
<!-- Asifah Analytics - China Stability Index v1.1.0 — HKEX integration May 25 2026 -->
<html lang="en">
<head>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Z9114D1Z5C"></script>
    <!-- Chart.js for HKEX sparkline (v1.1 May 25 2026) -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-Z9114D1Z5C');
    </script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>China Stability Index | Asifah Analytics v1.0.0</title>
    <link rel="icon" type="image/png" href="https://raw.githubusercontent.com/SassAndSweet/asifah-analytics/main/Asifah_Analytics_1_25_26_V1_LOGO.png">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-color: #f5f5f5;
            --container-bg: #ffffff;
            --card-bg: #ffffff;
            --card-border: #e1e8ed;
            --text-primary: #2c3e50;
            --text-secondary: #7f8c8d;
            --text-muted: #95a5a6;
            --header-gradient-start: #1e3a5f;
            --header-gradient-end: #2c5282;
            --header-text: #ffffff;
            --metric-bg: #ffffff;
            --metric-hover-shadow: rgba(0,0,0,0.15);
            --article-bg: #f8f9fa;
            --article-hover: #e8f4f8;
            --watermark-opacity: 0.50;
            --watermark-filter: grayscale(20%) brightness(0.8);
            --watermark-size: 1800px;
            --watermark-blend: normal;
            --loading-overlay-bg: rgba(245, 245, 245, 0.98);
            --loading-spinner-bg: rgba(100, 149, 237, 0.2);
            --accent: #6495ED;
        }

        [data-theme="dark"] {
            --bg-color: #1a1a1a;
            --container-bg: #2d2d2d;
            --card-bg: #2d2d2d;
            --card-border: #404040;
            --text-primary: #e0e0e0;
            --text-secondary: #b0b0b0;
            --text-muted: #808080;
            --header-gradient-start: #1e3a5f;
            --header-gradient-end: #2c5282;
            --header-text: #ffffff;
            --metric-bg: #2d2d2d;
            --metric-hover-shadow: rgba(255,255,255,0.1);
            --article-bg: #353535;
            --article-hover: #404040;
            --watermark-opacity: 0.18;
            --watermark-filter: drop-shadow(0 0 30px rgba(0,212,255,0.9)) drop-shadow(0 0 60px rgba(0,212,255,0.5)) drop-shadow(0 0 90px rgba(0,180,255,0.3)) saturate(2) brightness(1.4);
            --watermark-size: 1800px;
            --watermark-blend: screen;
            --loading-overlay-bg: rgba(26, 26, 26, 0.98);
            --loading-spinner-bg: rgba(100, 149, 237, 0.3);
        }

        body {
            font-family: 'Times New Roman', Times, serif;
            font-size: 14px;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
            min-height: 100vh;
            transition: background-color 0.3s ease, color 0.3s ease;
            position: relative;
        }

        body::before {
            content: '';
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: var(--watermark-size, 1800px);
            height: var(--watermark-size, 1800px);
            background-image: url('https://raw.githubusercontent.com/SassAndSweet/asifah-analytics/main/Asifah_Analytics_1_25_26_V1_LOGO.png');
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
            opacity: var(--watermark-opacity);
            filter: var(--watermark-filter, none);
            mix-blend-mode: var(--watermark-blend, normal);
            z-index: 0;
            pointer-events: none;
            user-select: none;
        }

        .loading-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: var(--loading-overlay-bg);
            backdrop-filter: blur(10px);
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            z-index: 9999;
            transition: opacity 0.5s ease, visibility 0.5s ease;
        }
        .loading-overlay.hidden { opacity: 0; visibility: hidden; }
        .loading-spinner {
            width: 60px; height: 60px;
            border: 5px solid var(--loading-spinner-bg);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 30px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-status { text-align: center; max-width: 500px; padding: 0 20px; }
        .loading-title { font-size: 24px; font-weight: bold; color: var(--accent); margin-bottom: 20px; letter-spacing: 1px; }
        .loading-steps { margin-top: 20px; }
        .loading-step {
            display: flex; align-items: center; justify-content: center; gap: 12px;
            padding: 12px; font-size: 15px; color: var(--text-secondary); transition: all 0.3s ease;
        }
        .loading-step.active { color: var(--accent); font-weight: bold; }
        .loading-step.complete { color: #4ade80; }
        .step-icon { font-size: 18px; min-width: 20px; }
        .loading-progress { margin-top: 25px; font-size: 13px; color: var(--text-secondary); font-style: italic; }
        .loading-error {
            color: #f87171; font-size: 16px; margin-top: 20px; padding: 15px;
            background: rgba(248, 113, 113, 0.1); border: 1px solid rgba(248, 113, 113, 0.3); border-radius: 8px;
        }

        .container { max-width: 1400px; margin: 0 auto; position: relative; z-index: 1; }

        header {
            background: linear-gradient(135deg, var(--header-gradient-start) 0%, var(--header-gradient-end) 100%);
            color: var(--header-text);
            padding: 35px; border-radius: 12px; margin-bottom: 30px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            position: relative; display: flex; align-items: center; gap: 30px;
        }
        .header-logo { width: 80px; height: 80px; flex-shrink: 0; border-radius: 50%; margin-top: 48px; }
        .header-content { flex: 1; text-align: center; }
        h1 { font-size: 28px; font-weight: bold; margin-bottom: 10px; letter-spacing: 2px; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        .subtitle { font-size: 16px; font-weight: normal; opacity: 0.95; letter-spacing: 0.5px; }
        .last-updated { font-size: 13px; opacity: 0.85; margin-top: 10px; }

        .header-controls {
            position: absolute; top: 35px; right: 35px;
            display: flex; flex-direction: column; gap: 10px; z-index: 1000;
        }
        [dir="rtl"] .header-controls { right: auto; left: 35px; }

        .language-switcher {
            display: flex; gap: 8px;
            background: rgba(255,255,255,0.15); padding: 8px 12px;
            border-radius: 8px; backdrop-filter: blur(10px);
        }
        .theme-toggle {
            display: flex; align-items: center; justify-content: center; gap: 8px;
            background: rgba(255,255,255,0.15); padding: 8px 12px;
            border-radius: 8px; backdrop-filter: blur(10px);
        }
        .theme-toggle-label {
            font-size: 11px; color: rgba(255,255,255,0.9); margin-right: 8px;
            text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;
        }
        .theme-toggle-switch {
            position: relative; width: 50px; height: 26px;
            background: rgba(255,255,255,0.2); border-radius: 13px; cursor: pointer;
            transition: all 0.3s ease; border: 2px solid rgba(255,255,255,0.3);
        }
        .theme-toggle-switch:hover { background: rgba(255,255,255,0.3); border-color: rgba(255,255,255,0.5); }
        .theme-toggle-slider {
            position: absolute; top: 2px; left: 2px; width: 18px; height: 18px;
            background: white; border-radius: 50%; transition: transform 0.3s ease;
            display: flex; align-items: center; justify-content: center; font-size: 10px;
        }
        .theme-toggle-slider::before { content: '\2600\FE0F'; }
        [data-theme="dark"] .theme-toggle-slider { transform: translateX(24px); }
        [data-theme="dark"] .theme-toggle-slider::before { content: '\1F319'; }

        .lang-btn {
            background: rgba(255,255,255,0.2); border: 2px solid rgba(255,255,255,0.3);
            color: white; padding: 6px 14px; font-family: 'Times New Roman', Times, serif;
            font-size: 14px; font-weight: bold; border-radius: 6px; cursor: pointer;
            transition: all 0.2s ease;
        }
        .lang-btn:hover { background: rgba(255,255,255,0.3); border-color: rgba(255,255,255,0.5); }
        .lang-btn.active { background: white; color: #1e3a5f; border-color: white; }

        .back-link {
            display: inline-block; position: absolute; top: 20px; left: 20px; margin: 0;
            padding: 12px 24px; background: rgba(255,255,255,0.2); color: white;
            text-decoration: none; border-radius: 8px; border: 2px solid rgba(255,255,255,0.3);
            transition: all 0.2s ease; font-size: 14px; font-weight: bold;
        }
        .back-link:hover { background: rgba(255,255,255,0.3); border-color: rgba(255,255,255,0.5); }

        .map-section {
            background: var(--container-bg); border: 2px solid var(--card-border);
            border-radius: 12px; padding: 25px; margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: background 0.3s ease, border-color 0.3s ease;
        }
        .map-section h2 { font-size: 20px; margin-bottom: 10px; color: var(--text-primary); }
        .map-subtitle { font-size: 13px; color: var(--text-secondary); margin-bottom: 15px; font-style: italic; }

        .knowledge-library {
            background: var(--container-bg); border: 2px solid var(--card-border);
            border-radius: 12px; padding: 25px; margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: background 0.3s ease, border-color 0.3s ease;
        }
        .knowledge-library h2 { font-size: 24px; margin-bottom: 20px; color: var(--text-primary); display: flex; align-items: center; gap: 10px; }
        .library-icon { font-size: 28px; }
        .knowledge-categories { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .knowledge-card { background: var(--card-bg); border: 2px solid var(--card-border); border-radius: 10px; overflow: hidden; transition: all 0.3s ease; }
        .knowledge-card:hover { transform: translateY(-3px); box-shadow: 0 6px 16px var(--metric-hover-shadow); }
        .knowledge-header {
            background: linear-gradient(135deg, rgba(100, 149, 237, 0.1) 0%, rgba(30, 82, 130, 0.1) 100%);
            padding: 18px 20px; cursor: pointer; display: flex; justify-content: space-between;
            align-items: center; transition: background 0.3s ease;
        }
        .knowledge-header:hover { background: linear-gradient(135deg, rgba(100, 149, 237, 0.15) 0%, rgba(30, 82, 130, 0.15) 100%); }
        .knowledge-header-title { display: flex; align-items: center; gap: 12px; font-size: 16px; font-weight: bold; color: var(--text-primary); }
        .category-icon { font-size: 22px; }
        .collapse-icon { font-size: 20px; color: var(--accent); transition: transform 0.3s ease; }
        .knowledge-card.collapsed .collapse-icon { transform: rotate(-90deg); }
        .knowledge-content { padding: 20px; max-height: 500px; overflow-y: auto; transition: max-height 0.3s ease, padding 0.3s ease; }
        .knowledge-card.collapsed .knowledge-content { max-height: 0; padding: 0 20px; overflow: hidden; }
        .knowledge-content p { font-size: 13px; line-height: 1.6; color: var(--text-secondary); margin-bottom: 12px; }
        .knowledge-content ul { margin-left: 20px; margin-bottom: 12px; }
        .knowledge-content li { font-size: 13px; line-height: 1.6; color: var(--text-secondary); margin-bottom: 6px; }
        .knowledge-content strong { color: var(--text-primary); }
        .open-source-disclaimer { font-size: 11px; color: var(--text-muted); font-style: italic; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--card-border); }
        .report-links-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 15px; }
        .report-link {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 10px 16px; background: var(--accent); color: white;
            text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold;
            transition: all 0.3s ease;
        }
        .report-link:hover { background: #4169E1; transform: translateX(3px); box-shadow: 0 4px 12px rgba(100, 149, 237, 0.3); }
        [dir="rtl"] .report-link:hover { transform: translateX(-3px); }
        .knowledge-content::-webkit-scrollbar { width: 8px; }
        .knowledge-content::-webkit-scrollbar-track { background: var(--article-bg); border-radius: 4px; }
        .knowledge-content::-webkit-scrollbar-thumb { background: var(--card-border); border-radius: 4px; }
        .knowledge-content::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

        .articles-section {
            background: var(--container-bg); border-radius: 12px; padding: 25px; margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 2px solid var(--card-border);
            transition: background 0.3s ease, border-color 0.3s ease;
        }
        .section-title { font-size: 20px; margin-bottom: 20px; color: var(--text-primary); font-weight: bold; letter-spacing: 0.5px; }
        .article-item {
            background: var(--article-bg); padding: 15px; border-radius: 8px; margin-bottom: 10px;
            transition: background 0.2s ease, transform 0.2s; border-left: 4px solid #1e3a5f;
        }
        [dir="rtl"] .article-item { border-left: none; border-right: 4px solid #1e3a5f; }
        .article-item:hover { background: var(--article-hover); transform: translateX(4px); }
        [dir="rtl"] .article-item:hover { transform: translateX(-4px); }
        .article-title { color: var(--text-primary); font-size: 14px; margin-bottom: 5px; font-weight: 500; }
        .article-meta { font-size: 12px; color: var(--text-secondary); }
        .article-link { color: var(--accent); text-decoration: none; font-size: 13px; }
        .article-link:hover { text-decoration: underline; }

        /* ── STABILITY INDEX CARD ── */
        .stability-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 20px;
        }
        @media (max-width: 768px) { .stability-grid { grid-template-columns: 1fr; } }
        .stability-index-card {
            background: var(--container-bg); border-radius: 12px; padding: 20px;
            border: 1px solid var(--card-border); box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .stability-score-big {
            font-size: 48px; font-weight: 700; line-height: 1;
            color: var(--text-primary); margin-bottom: 4px;
        }
        .stability-bar-track {
            width: 100%; height: 8px; background: rgba(107,114,128,0.2);
            border-radius: 4px; overflow: hidden; margin: 8px 0;
        }
        .stability-bar-fill { height: 100%; border-radius: 4px; transition: width 0.8s ease; }
        /* ── LEADERSHIP CARDS ── */
        .leadership-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }
        .leader-card {
            background: var(--container-bg); border-radius: 10px; padding: 14px;
            border: 1px solid var(--card-border);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .leader-card:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.15); }
        .lc-role { font-size: 9px; text-transform: uppercase; letter-spacing: 1.5px;
                   color: var(--text-muted); font-weight: 700; margin-bottom: 6px; }
        .lc-name { font-size: 15px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
        .lc-since { font-size: 10px; color: var(--text-muted); margin-bottom: 6px; }
        .lc-note { font-size: 11px; color: var(--text-secondary); line-height: 1.4; }
        .lc-risk { font-size: 10px; color: #f59e0b; margin-top: 6px;
                   padding-top: 6px; border-top: 1px solid var(--card-border); font-style: italic; }
        
        /* ── RHETORIC BANNER + CARD ── */
        .rhetoric-link-banner {
            background: linear-gradient(135deg, #052e16, #064e23);
            border: 2px solid rgba(34,197,94,0.4);
            border-radius: 10px; padding: 14px 20px;
            margin-bottom: 15px;
            display: flex; align-items: center;
            justify-content: space-between; gap: 15px; flex-wrap: wrap;
        }
        .rhetoric-vector-pills { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 8px; }
        .rhetoric-vector-pill {
            font-size: 10px; font-weight: 700; padding: 2px 8px;
            border-radius: 4px; color: white; letter-spacing: 0.5px;
        }

        footer {
            background: var(--container-bg); padding: 25px; border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 2px solid var(--card-border);
            font-size: 12px; text-align: center; margin-top: 40px; color: var(--text-secondary);
            transition: background 0.3s ease, border-color 0.3s ease;
        }

        @media (max-width: 768px) {
            header { flex-direction: column; gap: 20px; padding: 25px 20px; }
            .header-logo { width: 60px; height: 60px; }
            .header-content { text-align: center; }
            .header-controls { position: static; align-items: center; }
            h1 { font-size: 24px; }
            .back-link { position: static; display: block; width: fit-content; margin: 0 auto 15px; }
            .knowledge-categories { grid-template-columns: 1fr; }
        }

        /* ═══════════════════════════════════════════════════════════
           COMMODITY EXPOSURE CARD — Gold Standard v2.0 (May 7, 2026)
           Mirrors russia.html canonical pattern. Always-rendered.
           Prose + adaptive alert banner + tiles + Strategic Linkage footer.
           ═══════════════════════════════════════════════════════════ */
        .commodity-card {
            background: var(--container-bg);
            border: 2px solid var(--card-border);
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        [data-theme="dark"] .commodity-card {
            box-shadow: 0 0 6px rgba(56,189,248,0.15);
        }
        .commodity-card-title {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-secondary);
            margin-bottom: 12px;
            padding-bottom: 9px;
            border-bottom: 1px solid var(--card-border);
        }
        .commodity-prose {
            font-size: 13.5px;
            line-height: 1.65;
            color: var(--text-secondary);
            margin: 10px 0 16px 0;
            padding: 12px 14px;
            background: rgba(2,6,23,0.5);
            border-left: 3px solid #38bdf8;
            border-radius: 6px;
        }
        [data-theme="light"] .commodity-prose { background: #f8fbfe; }
        .commodity-convergence-alert {
            display: none;
            margin: 10px 0 14px 0;
            padding: 12px 14px;
            background: linear-gradient(135deg, rgba(251,146,60,0.18) 0%, rgba(239,68,68,0.18) 100%);
            border: 2px solid #f59e0b;
            border-radius: 8px;
        }
        .commodity-convergence-alert.active { display: block; }
        .cca-title {
            font-size: 12px;
            font-weight: 700;
            color: #f59e0b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .cca-detail {
            font-size: 11px;
            color: #fbbf24;
            line-height: 1.5;
        }
        .commodity-alert-banner {
            margin-bottom: 14px;
            padding: 10px 14px;
            border-radius: 6px;
            border-left: 4px solid;
            font-size: 12px;
            display: none;
        }
        .commodity-alert-banner.show { display: block; }
        .commodity-alert-banner.alert-normal   { background: rgba(34,197,94,0.08);  border-left-color: #22c55e; color: #22c55e; }
        .commodity-alert-banner.alert-elevated { background: rgba(234,179,8,0.10);  border-left-color: #eab308; color: #eab308; }
        .commodity-alert-banner.alert-high     { background: rgba(249,115,22,0.10); border-left-color: #f97316; color: #f97316; }
        .commodity-alert-banner.alert-surge    { background: rgba(239,68,68,0.12);  border-left-color: #ef4444; color: #ef4444; }
        .commodity-alert-banner strong { letter-spacing: 1.5px; }
        .commodity-alert-banner .ab-meta { color: var(--text-muted); font-weight: 400; margin-left: 10px; }

        .commodity-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 12px;
            margin-top: 14px;
        }
        .commodity-pill {
            background: rgba(2,6,23,0.5);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 14px;
            transition: all 0.3s;
            text-decoration: none;
            color: inherit;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        [data-theme="light"] .commodity-pill { background: #f8fbfe; }
        .commodity-pill:hover {
            transform: translateY(-2px);
            border-color: #38bdf8;
            box-shadow: 0 4px 12px rgba(56,189,248,0.15);
        }
        .commodity-pill-header { display: flex; align-items: center; gap: 10px; }
        .commodity-pill-icon { font-size: 22px; line-height: 1; }
        .commodity-pill-name { font-size: 13px; font-weight: 700; color: var(--text-primary); flex: 1; }
        .commodity-pill-rank { font-size: 9px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .commodity-pill-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .commodity-pill-alert {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        .commodity-alert-normal   { background: rgba(34,197,94,0.12);  color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
        .commodity-alert-elevated { background: rgba(234,179,8,0.12);  color: #eab308; border: 1px solid rgba(234,179,8,0.3); }
        .commodity-alert-high     { background: rgba(249,115,22,0.15); color: #f97316; border: 1px solid rgba(249,115,22,0.4); }
        .commodity-alert-surge    { background: rgba(239,68,68,0.15);  color: #ef4444; border: 1px solid rgba(239,68,68,0.4); }
        .commodity-pill-role-badge {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            background: rgba(56,189,248,0.12);
            color: #38bdf8;
            border: 1px solid rgba(56,189,248,0.25);
        }
        .commodity-pill-signal-count {
            font-size: 10px;
            color: var(--text-muted);
            font-weight: 600;
        }
        .commodity-pill-price {
            font-size: 12px;
            color: var(--text-primary);
            font-weight: 600;
            font-family: 'Courier New', monospace;
        }
        .commodity-pill-price .price-up   { color: #22c55e; }
        .commodity-pill-price .price-down { color: #ef4444; }
        .commodity-pill-spark { width: 100%; height: 28px; display: block; }
        .commodity-pill-note {
            font-size: 11px;
            color: var(--text-secondary);
            line-height: 1.45;
            margin-top: 4px;
        }
        .commodity-top-signals {
            margin-top: 14px;
            padding: 10px 14px;
            background: rgba(2,6,23,0.5);
            border-radius: 6px;
            border-left: 3px solid var(--text-muted);
            font-size: 11px;
        }
        [data-theme="light"] .commodity-top-signals { background: #f8fbfe; }
        .commodity-top-signals .ts-title {
            color: var(--text-muted);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 6px;
            font-size: 10px;
        }
        .commodity-top-signals a {
            color: var(--text-secondary);
            text-decoration: none;
            display: block;
            padding: 3px 0;
            line-height: 1.45;
        }
        .commodity-top-signals a:hover { color: #38bdf8; }
        .commodity-top-signals .ts-source { color: var(--text-muted); font-size: 10px; }
    
        /* ═══════════════════════════════════════════════════════════
           CANONICAL ASIA SIDEBAR (Gold Standard — May 8, 2026)
           Mirrors japan-stability.html canonical pattern.
           ═══════════════════════════════════════════════════════════ */
        .page-with-sidebar { display: flex; gap: 20px; align-items: flex-start; }
        .nav-sidebar {
            width: 200px;
            flex-shrink: 0;
            position: sticky;
            top: 20px;
            background: var(--container-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 12px 10px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .nav-sidebar-label {
            font-size: 9px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: var(--text-muted);
            padding: 8px 8px 4px 8px;
        }
        .nav-divider {
            height: 1px;
            background: var(--card-border);
            margin: 6px 4px;
        }
        .nav-btn {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            text-decoration: none;
            color: var(--text-secondary);
            background: transparent;
            border: 1px solid transparent;
            transition: all 0.18s;
        }
        .nav-btn:hover {
            background: rgba(56,189,248,0.08);
            border-color: rgba(56,189,248,0.20);
            color: var(--text-primary);
        }
        .nav-btn-label { flex: 1; }
        .nav-btn-status {
            font-size: 9px;
            color: var(--text-muted);
            font-weight: 500;
            margin-left: 8px;
        }
        .active-nav .nav-btn-status { color: #38bdf8; }
        .rhetoric-btn:hover { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.20); }
        .rhetoric-btn .nav-btn-status { color: #22c55e; }
        .military-btn:hover { background: rgba(168,85,247,0.08); border-color: rgba(168,85,247,0.25); }
        .military-btn .nav-btn-status { color: #a855f7; }
        .commodity-btn:hover { background: rgba(250,204,21,0.08); border-color: rgba(250,204,21,0.25); }
        .commodity-btn .nav-btn-status { color: #facc15; }
        .inactive-nav { opacity: 0.45; cursor: not-allowed; }
        .inactive-nav .nav-btn-status { color: var(--text-muted); }
        .current-page {
            background: rgba(56,189,248,0.12);
            border-color: rgba(56,189,248,0.40);
            color: var(--text-primary);
            cursor: default;
        }
        .current-page .nav-btn-status { color: #38bdf8; font-weight: 700; }
        .main-content { flex: 1; min-width: 0; }

        @media (max-width: 1024px) {
            .page-with-sidebar { flex-direction: column; }
            .nav-sidebar { width: 100%; position: static; flex-direction: row; flex-wrap: wrap; }
            .nav-sidebar-label { width: 100%; }
            .nav-btn { flex: 1; min-width: 140px; }
            .nav-divider { display: none; }
        }
    </style>
</head>
<body>
    <!-- Loading Overlay -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
        <div class="loading-status">
            <div class="loading-title">Loading China Stability Data</div>
            <div class="loading-steps" id="loadingSteps">
                <div class="loading-step active" id="step1">
                    <span class="step-icon">&#x23F3;</span>
                    <span>Fetching OSINT articles on China...</span>
                </div>
                <div class="loading-step" id="step2">
                    <span class="step-icon">&#x23F3;</span>
                    <span>Scanning PLA posture signals...</span>
                </div>
                <div class="loading-step" id="step3">
                    <span class="step-icon">&#x23F3;</span>
                    <span>Analyzing South China Sea incidents...</span>
                </div>
                <div class="loading-step" id="step4">
                    <span class="step-icon">&#x23F3;</span>
                    <span>Compiling Taiwan Strait indicators...</span>
                </div>
                <div class="loading-step" id="step5">
                    <span class="step-icon">&#x23F3;</span>
                    <span>Rendering dashboard...</span>
                </div>
            </div>
            <div class="loading-progress" id="loadingProgress">This may take 20-40 seconds...</div>
            <div class="loading-error" id="loadingError" style="display: none;"></div>
        </div>
    </div>

    <div class="container">
        <header>
            <a href="asia.html" class="back-link" data-i18n="backLink">&#8592; Back to Dashboard</a>
            <img src="https://raw.githubusercontent.com/SassAndSweet/asifah-analytics/main/Asifah_Analytics_1_25_26_V1_LOGO.png" alt="Asifah Analytics Logo" class="header-logo">
            <div class="header-content">
                <h1 data-i18n="pageTitle">🇨🇳 CHINA STABILITY INDEX</h1>
                <div class="subtitle" data-i18n="pageSubtitle">Multi-Factor Analysis: PLA Posture, South China Sea, Taiwan Strait Dynamics &amp; Economic Coercion</div>
                <div class="last-updated" id="lastUpdated" data-i18n="lastUpdated">Last updated: Loading...</div>
            </div>
            <div class="header-controls" style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;">
                <div class="language-switcher">
                    <button class="lang-btn active" onclick="switchLanguage('en', this)">EN</button>
                    <button class="lang-btn" onclick="switchLanguage('zh', this)">中文</button>
                    <button class="lang-btn" onclick="switchLanguage('ja', this)">日本語</button>
                    <button class="lang-btn" onclick="switchLanguage('ko', this)">한국어</button>
                </div>
                <div class="theme-toggle" style="padding:4px 8px;">
                    <span class="theme-toggle-label" style="font-size:9px;" data-i18n="themeToggle">Theme</span>
                    <div class="theme-toggle-switch" onclick="toggleTheme()" style="width:36px;height:20px;">
                        <div class="theme-toggle-slider" style="width:14px;height:14px;"></div>
                    </div>
                </div>
                <a href="military.html" style="padding:4px 10px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);border-radius:6px;color:white;text-decoration:none;font-size:11px;font-weight:bold;white-space:nowrap;">🎖️ Mil Tracker</a>
            </div>
        </header>

        <!-- ═══════════════════════════════════════════════════════════
             CANONICAL ASIA SIDEBAR (Gold Standard — May 8 2026)
             ═══════════════════════════════════════════════════════════ -->
        <div class="page-with-sidebar">
        <nav class="nav-sidebar">
            <div class="nav-sidebar-label" data-i18n="nav_dashboards">Dashboards</div>
            <a href="africa.html" class="nav-btn active-nav">
                <span class="nav-btn-label" data-i18n="nav_africa">🌍 Africa</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="asia.html" class="nav-btn active-nav">
                <span class="nav-btn-label" data-i18n="nav_asia_pacific">🌏 Asia &amp; Pacific</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="europe.html" class="nav-btn active-nav">
                <span class="nav-btn-label" data-i18n="nav_europe">🌍 Europe</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="middle-east.html" class="nav-btn active-nav">
                <span class="nav-btn-label" data-i18n="nav_me">🕌 Middle East</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="wha.html" class="nav-btn active-nav">
                <span class="nav-btn-label" data-i18n="nav_wha">🌎 W. Hemisphere</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <div class="nav-divider"></div>
            <a href="military.html" class="nav-btn military-btn">
                <span class="nav-btn-label" data-i18n="nav_military">🎖️ Military Tracker</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="gpi.html" class="nav-btn military-btn">
                <span class="nav-btn-label" data-i18n="nav_gpi">🌐 Global Pressure</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="commodities.html" class="nav-btn commodity-btn">
                <span class="nav-btn-label" data-i18n="nav_commodities">🛢️ Commodities</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <div class="nav-divider"></div>
            <div class="nav-sidebar-label" data-i18n="nav_rhetoric">Regional Rhetoric</div>
            <a href="rhetoric-index.html" class="nav-btn rhetoric-btn">
                <span class="nav-btn-label" data-i18n="nav_rhetoric_me">🕌 Middle East</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="rhetoric-asia.html" class="nav-btn rhetoric-btn">
                <span class="nav-btn-label" data-i18n="nav_rhetoric_asia">🌏 Asia</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="rhetoric-europe.html" class="nav-btn rhetoric-btn">
                <span class="nav-btn-label" data-i18n="nav_rhetoric_europe">🌍 Europe</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="rhetoric-wha.html" class="nav-btn rhetoric-btn">
                <span class="nav-btn-label" data-i18n="nav_rhetoric_wha">🌎 W. Hemisphere</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <div class="nav-divider"></div>
            <div class="nav-sidebar-label" data-i18n="nav_china">China</div>
            <a href="rhetoric-china.html" class="nav-btn rhetoric-btn">
                <span class="nav-btn-label" data-i18n="nav_china_rhetoric">🇨🇳 China Rhetoric</span>
                <span class="nav-btn-status">● Live</span>
            </a>
            <a href="china-stability.html" class="nav-btn current-page">
                <span class="nav-btn-label" data-i18n="nav_china_stability">🇨🇳 China Stability</span>
                <span class="nav-btn-status" data-i18n="nav_here">◉ You are here</span>
            </a>
        </nav>

        <!-- ═══════════════════════════════════════════════════════════
             MAIN CONTENT
             ═══════════════════════════════════════════════════════════ -->
        <div class="main-content">


        <!-- U.S. STATE DEPARTMENT — WORLDWIDE CAUTION -->
        <div style="
            background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 50%, #7f1d1d 100%);
            border: 2px solid #ef4444; border-radius: 10px; padding: 14px 20px;
            margin-bottom: 10px; display: flex; align-items: center; gap: 14px;
            box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3);
        ">
            <div style="font-size: 24px; flex-shrink: 0;">🚨</div>
            <div style="flex: 1;">
                <div style="font-size: 12px; font-weight: bold; color: #fca5a5; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 3px;" data-i18n="ww_caution_label">⚠️ U.S. State Department — Worldwide Caution</div>
                <div style="font-size: 12px; color: #fde8e8; line-height: 1.4;" data-i18n="ww_caution_text">Following the launch of U.S. combat operations in Iran, Americans worldwide and especially in the Middle East should follow guidance from the nearest U.S. embassy or consulate.</div>
            </div>
            <a href="https://travel.state.gov/en/international-travel/travel-advisories/global-events/worldwide-caution.html" target="_blank" rel="noopener" style="flex-shrink:0; padding:6px 14px; background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3); border-radius:6px; color:white; text-decoration:none; font-size:11px; font-weight:bold; white-space:nowrap;" data-i18n="ww_caution_button">VIEW CAUTION →</a>
        </div>

        <!-- CHINA TRAVEL ADVISORY — Level 2 -->
        <div style="
            background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
            border: 2px solid #f59e0b; border-radius: 10px; padding: 14px 20px;
            margin-bottom: 15px; display: flex; align-items: center; gap: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        ">
            <div style="font-size: 24px; flex-shrink: 0;">🇨🇳</div>
            <div style="flex: 1;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                    <span style="font-size: 11px; font-weight: bold; color: #fca5a5; text-transform: uppercase; letter-spacing: 1.5px;" data-i18n="travel_label">U.S. State Department — China Travel Advisory</span>
                    <span style="background: #f59e0b; color: white; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 3px; letter-spacing: 1px;" data-i18n="travel_level2">LEVEL 2</span>
                </div>
                <div style="font-size: 12px; color: #e2e8f0; line-height: 1.4;" data-i18n-html="travel_text"><strong style='color: #f59e0b;'>Exercise Increased Caution in China</strong> due to arbitrary enforcement of local laws, including exit bans, and the risk of wrongful detentions. U.S. citizens may be detained without access to U.S. consular services.</div>
            </div>
            <a href="https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/china-travel-advisory.html" target="_blank" rel="noopener" style="flex-shrink:0; padding:6px 14px; background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3); border-radius:6px; color:white; text-decoration:none; font-size:11px; font-weight:bold; white-space:nowrap;" data-i18n="travel_button">VIEW ADVISORY →</a>
        </div>

        <!-- RHETORIC BANNER -->
        <div class="rhetoric-link-banner">
            <div>
                <div style="font-size:13px;font-weight:bold;color:white;" data-i18n="rhetoric_banner_title">📡 China Rhetoric &amp; Coercion Tracker</div>
                <div style="font-size:11px;color:rgba(255,255,255,0.7);margin-top:3px;" data-i18n="rhetoric_banner_actors">Xi/CMC · PLA Operational · MFA/Global Times · TAO · Economic Coercion</div>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">
                <span id="rhetoricLevelBadge" style="background:#6b7280;color:white;font-size:12px;font-weight:700;padding:5px 14px;border-radius:6px;letter-spacing:0.5px;">📡 Loading…</span>
                <a href="rhetoric-china.html" style="padding:8px 18px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);border-radius:6px;color:white;text-decoration:none;font-size:12px;font-weight:bold;white-space:nowrap;" data-i18n="open_tracker">Open Tracker →</a>
            </div>
        </div>

        <!-- RHETORIC CARD -->
        <div style="background:var(--container-bg);border-radius:12px;padding:20px;margin-bottom:20px;border:1px solid var(--card-border);box-shadow:0 4px 12px rgba(0,0,0,0.08);">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-secondary);margin-bottom:12px;" data-i18n="rhetoric_card_title">📡 RHETORIC TRACKER</div>
            <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:6px;">
                <div style="font-size:32px;font-weight:700;color:var(--text-primary);" id="rhetoricScore">--</div>
                <span id="rhetoricTheatreLabel" style="font-size:13px;font-weight:bold;padding:3px 10px;border-radius:4px;background:#6b7280;color:white;">--</span>
            </div>
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:12px;" data-i18n="rhetoric_card_subtitle">Outbound coercion score · Updated every 6h</div>
            <div id="rhetoricActorList" style="font-size:12px;color:var(--text-secondary);">
                <span style="font-style:italic;">Loading...</span>
            </div>
            <div id="rhetoricVectorPills" class="rhetoric-vector-pills"></div>
            <div style="margin-top:15px;padding-top:12px;border-top:1px solid var(--card-border);text-align:center;">
                <a href="rhetoric-china.html" style="color:#00c8d4;text-decoration:none;font-size:12px;font-weight:600;" data-i18n="view_full_rhetoric">View Full Rhetoric Analysis →</a>
            </div>
            <div id="rhetoricScanInfo" style="margin-top:8px;font-size:10px;color:var(--text-secondary);text-align:center;">--</div>
        </div>

        <!-- ═══ COMMODITY EXPOSURE CARD — Gold Standard v2.0 (May 7, 2026) ═══ -->
        <!-- Always-rendered canonical pattern. Mirrors russia.html. -->
        <!-- Hormuz-China oil convergence alert surfaces when Iran pressure intersects China's ~50% oil import dep. -->
        <div class="commodity-card" id="chinaCommodityCard">
            <div class="commodity-card-title">📊 <span data-i18n="commodityTitle">CHINA COMMODITY EXPOSURE</span></div>
            <!-- Convergence alert (China-specific, surfaces when hormuz_china_oil_dependency_active = true) -->
            <div class="commodity-convergence-alert" id="commodityConvergenceAlert">
                <div class="cca-title" id="commodityConvergenceAlertTitle">⚠️ Hormuz-China oil convergence: ACTIVE</div>
                <div class="cca-detail" id="commodityConvergenceAlertDetail">
                    Iran/Hormuz pressure × China's ~50% oil import dependency through the Strait — compound energy security risk.
                </div>
            </div>
            <div class="commodity-prose" id="commodityProse" data-i18n="commodityLoading">Loading exposure profile…</div>
            <div class="commodity-alert-banner" id="commodityAlertBanner"></div>
            <div class="commodity-grid" id="commodityGrid"></div>
            <div class="commodity-top-signals" id="commodityTopSignals" style="display:none;"></div>
            <!-- Strategic Linkage: China-specific dual-role framing (consumer + producer) -->
            <div style="margin-top:14px;padding:10px 14px;background:rgba(56,189,248,0.06);border:1px solid rgba(56,189,248,0.2);border-radius:8px;font-size:11px;color:var(--text-secondary);line-height:1.55;">
                <strong style="color:#38bdf8;">Strategic Linkage:</strong> China is a <strong>dual-role commodity power</strong> — world's #1 importer of oil (~50% via Hormuz), soybeans (~60% global imports), copper (~50% global consumption), and lithium for EVs; simultaneously the world's #1 producer of rare earths (60% production, 85% refining) with export-control leverage. Tracker reads consumer-side surges as supply-chain pressure (BRI/CPEC substitution moves, yuan settlement deals, MFA "stability" framing) and producer-side moves as economic-coercion tools (REE export controls, dual-use restrictions). Hormuz dependency is the structural reason China consistently mediates Iran-Saudi tensions.
            </div>
            <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--card-border);text-align:center;">
                <a href="commodities.html" style="color:#38bdf8;text-decoration:none;font-size:12px;font-weight:600;" data-i18n="commodityFullLink">View Full Commodity Tracker →</a>
            </div>
            <div id="commodityCacheNote" style="margin-top:8px;font-size:10px;color:var(--text-muted);font-style:italic;text-align:right;"></div>
        </div>

        <!-- STABILITY INDEX + ECONOMIC INDICATORS -->
        <div class="stability-grid">

            <!-- Stability Score Card -->
            <div class="stability-index-card">
                <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-secondary);margin-bottom:12px;">🇨🇳 CHINA STABILITY INDEX</div>
                <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px;">
                    <div class="stability-score-big" id="stabilityScore">--</div>
                    <span id="stabilityLabel" style="font-size:13px;font-weight:bold;padding:3px 10px;border-radius:4px;background:#6b7280;color:white;">--</span>
                </div>
                <div class="stability-bar-track">
                    <div class="stability-bar-fill" id="stabilityBarFill" style="width:0%;background:#22c55e;"></div>
                </div>
                <div style="font-size:10px;color:var(--text-muted);margin-bottom:14px;">100 = Controlled · 0 = Crisis Risk</div>
                <!-- Vector breakdown -->
                <div id="stabilityVectors" style="font-size:12px;color:var(--text-secondary);">
                    <span style="font-style:italic;">Loading...</span>
                </div>
                <div id="stabilityScanInfo" style="margin-top:10px;font-size:10px;color:var(--text-muted);text-align:center;">--</div>
            </div>

            <!-- Live Economic Indicators Card -->
            <div class="stability-index-card">
                <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-secondary);margin-bottom:12px;">💹 LIVE ECONOMIC INDICATORS</div>
                <!-- Yuan/USD -->
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--card-border);">
                    <div>
                        <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Yuan / USD Rate</div>
                        <div style="font-size:22px;font-weight:700;color:var(--text-primary);" id="yuanRate">--</div>
                        <div style="font-size:10px;color:var(--text-muted);">CNY per 1 USD · Higher = weaker yuan</div>
                    </div>
                    <span id="yuanStatus" style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:4px;background:#6b7280;color:white;">--</span>
                </div>
                <!-- Brent Oil -->
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--card-border);">
                    <div>
                        <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Brent Crude</div>
                        <div style="font-size:22px;font-weight:700;color:var(--text-primary);" id="brentPrice">--</div>
                        <div style="font-size:10px;color:var(--text-muted);" id="brentChange">-- · China imports ~75% of oil needs</div>
                    </div>
                    <span id="brentStatus" style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:4px;background:#6b7280;color:white;">--</span>
                </div>
                <!-- HKEX Hang Seng (v1.0 May 25 2026 — TASE-pattern Black Swan POC) -->
                <div style="display:flex;justify-content:space-between;align-items:flex-start;padding:10px 0;border-bottom:1px solid var(--card-border);">
                    <div style="flex:1;">
                        <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">📊 <span data-i18n="hkex_label">HKEX Hang Seng</span></div>
                        <div style="font-size:22px;font-weight:700;color:var(--text-primary);" id="hkexValue">--</div>
                        <div style="font-size:10px;color:var(--text-secondary);" id="hkexChange">-- · <span data-i18n="hkex_subtitle">Hong Kong equity confidence proxy</span></div>
                        <!-- HKEX 5-day sparkline -->
                        <div class="sparkline-container" id="hkexSparklineContainer" style="display:none; margin-top:10px;">
                            <span class="sparkline-label" data-i18n="hkex_sparkline_label">5-day:</span>
                            <canvas id="hkexSparkline" class="sparkline-canvas" style="width:100%; height:40px;"></canvas>
                        </div>
                    </div>
                    <span id="hkexStatus" style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:4px;background:#6b7280;color:white; margin-left:8px;">--</span>
                </div>
                <!-- US-China tension level -->
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;">
                    <div>
                        <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">US-China Tension</div>
                        <div style="font-size:10px;color:var(--text-secondary);margin-top:3px;">Tariffs · Tech decoupling · Sanctions</div>
                    </div>
                    <span id="usChinaLevel" style="font-size:11px;font-weight:700;padding:4px 10px;border-radius:4px;background:#6b7280;color:white;">L--</span>
                </div>
                <div id="econScanInfo" style="margin-top:8px;font-size:10px;color:var(--text-muted);text-align:center;">--</div>
            </div>
        </div>

        <!-- LEADERSHIP CARDS -->
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-secondary);margin-bottom:10px;">👥 KEY LEADERSHIP</div>
        <div class="leadership-grid" id="leadershipGrid">
            <!-- Populated by JS -->
        </div>


        <!-- HUMANITARIAN MONITOR -->
        <div style="margin-bottom:20px;">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-secondary);margin-bottom:10px;" data-i18n="humanitarianTitle">🔴 HUMANITARIAN & HUMAN RIGHTS MONITOR</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;" id="humanitarianGrid">

                <!-- Xinjiang Card -->
                <div style="background:linear-gradient(135deg,rgba(220,38,38,0.08),rgba(153,27,27,0.05));border:1px solid rgba(220,38,38,0.3);border-radius:10px;padding:16px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                        <span style="font-size:18px;">🔴</span>
                        <span style="font-size:12px;font-weight:700;color:#ef4444;text-transform:uppercase;letter-spacing:1px;" data-i18n="xinjiangTitle">Xinjiang</span>
                    </div>
                    <div style="font-size:22px;font-weight:700;color:var(--text-primary);margin-bottom:2px;">1.0M – 1.8M</div>
                    <div style="font-size:11px;color:var(--text-secondary);margin-bottom:8px;" data-i18n="xinjiangDesc">Estimated Uyghur detainees in "vocational training centers"</div>
                    <div style="font-size:10px;background:rgba(220,38,38,0.1);border-radius:4px;padding:6px 8px;color:#fca5a5;margin-bottom:8px;">
                        <span style="font-weight:700;" data-i18n="sourceLabel">Source:</span> UN OHCHR &nbsp;·&nbsp; <span data-i18n="dataAsOf">Data as of:</span> Aug 2022
                    </div>
                    <div style="font-size:10px;color:var(--text-muted);font-style:italic;margin-bottom:10px;" data-i18n="xinjiangCaveat">⚠️ China denies independent access to verification</div>
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        <div style="font-size:11px;color:var(--text-secondary);">🏗️ <strong>380+</strong> detention facilities <span style="color:var(--text-muted);">(ASPI, 2022)</span></div>
                        <div style="font-size:11px;color:var(--text-secondary);">🌍 <strong>6+ govts</strong> genocide designation <span style="color:var(--text-muted);">(2024)</span></div>
                        <div style="font-size:11px;color:var(--text-secondary);">📦 <strong>UFLPA</strong> enforcement active <span style="color:var(--text-muted);">(US CBP)</span></div>
                    </div>
                    <div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(220,38,38,0.2);">
                        <a href="https://www.ohchr.org/en/documents/country-reports/ohchr-assessment-human-rights-concerns-xinjiang-uyghur-autonomous-region" target="_blank" style="font-size:11px;color:#7dd3fc;text-decoration:none;" data-i18n="unReportLink">🇺🇳 UN OHCHR Report →</a>
                    </div>
                </div>

                <!-- Tibet Card -->
                <div style="background:linear-gradient(135deg,rgba(245,158,11,0.08),rgba(180,83,9,0.05));border:1px solid rgba(245,158,11,0.3);border-radius:10px;padding:16px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                        <span style="font-size:18px;">🟡</span>
                        <span style="font-size:12px;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:1px;" data-i18n="tibetTitle">Tibet</span>
                    </div>
                    <div style="font-size:22px;font-weight:700;color:var(--text-primary);margin-bottom:2px;">150+</div>
                    <div style="font-size:11px;color:var(--text-secondary);margin-bottom:8px;" data-i18n="tibetDesc">Self-immolations in protest since 2009</div>
                    <div style="font-size:10px;background:rgba(245,158,11,0.1);border-radius:4px;padding:6px 8px;color:#fde68a;margin-bottom:8px;">
                        <span style="font-weight:700;" data-i18n="sourceLabel">Source:</span> TCHRD &nbsp;·&nbsp; <span data-i18n="dataAsOf">Data as of:</span> Mar 2024
                    </div>
                    <div style="font-size:10px;color:var(--text-muted);font-style:italic;margin-bottom:10px;" data-i18n="tibetCaveat">⚠️ China controls access — actual count may be higher</div>
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        <div style="font-size:11px;color:var(--text-secondary);">👦 <strong>Panchen Lama</strong> missing since 1995 <span style="color:var(--text-muted);">(UN)</span></div>
                        <div style="font-size:11px;color:var(--text-secondary);">📷 <strong>Permit required</strong> for all foreign visitors <span style="color:var(--text-muted);">(State Dept)</span></div>
                        <div style="font-size:11px;color:var(--text-secondary);">🕌 <strong>Monasteries</strong> under surveillance & patriotic education</div>
                    </div>
                    <div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(245,158,11,0.2);">
                        <a href="https://tchrd.org/" target="_blank" style="font-size:11px;color:#7dd3fc;text-decoration:none;" data-i18n="tchrdLink">🏔️ TCHRD Tibet HR →</a>
                    </div>
                </div>

                <!-- Hong Kong Card -->
                <div style="background:linear-gradient(135deg,rgba(139,92,246,0.08),rgba(109,40,217,0.05));border:1px solid rgba(139,92,246,0.3);border-radius:10px;padding:16px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                        <span style="font-size:18px;">🟣</span>
                        <span style="font-size:12px;font-weight:700;color:#a78bfa;text-transform:uppercase;letter-spacing:1px;" data-i18n="hkTitle">Hong Kong</span>
                    </div>
                    <div style="font-size:22px;font-weight:700;color:var(--text-primary);margin-bottom:2px;">260+</div>
                    <div style="font-size:11px;color:var(--text-secondary);margin-bottom:8px;" data-i18n="hkDesc">Arrested under National Security Law since 2020</div>
                    <div style="font-size:10px;background:rgba(139,92,246,0.1);border-radius:4px;padding:6px 8px;color:#ddd6fe;margin-bottom:8px;">
                        <span style="font-weight:700;" data-i18n="sourceLabel">Source:</span> HRW &nbsp;·&nbsp; <span data-i18n="dataAsOf">Data as of:</span> 2024
                    </div>
                    <div style="font-size:10px;color:var(--text-muted);font-style:italic;margin-bottom:10px;" data-i18n="hkCaveat">⚠️ Arrests ongoing; prosecution rate very high under NSL</div>
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        <div style="font-size:11px;color:var(--text-secondary);">📰 <strong>5+ media outlets</strong> shuttered post-2020 <span style="color:var(--text-muted);">(CPJ)</span></div>
                        <div style="font-size:11px;color:var(--text-secondary);">🗳️ <strong>Electoral overhaul</strong> 2021 — patriots only <span style="color:var(--text-muted);">(HRW)</span></div>
                        <div style="font-size:11px;color:var(--text-secondary);">📅 <strong>2047</strong> "One Country Two Systems" deadline</div>
                    </div>
                    <div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(139,92,246,0.2);">
                        <a href="https://www.hrw.org/tag/hong-kong" target="_blank" style="font-size:11px;color:#7dd3fc;text-decoration:none;" data-i18n="hrwHkLink">📋 HRW Hong Kong →</a>
                    </div>
                </div>
            </div>

            <!-- Annual Reports Row -->
            <div style="margin-top:12px;padding:12px 16px;background:var(--container-bg);border:1px solid var(--card-border);border-radius:8px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
                <span style="font-size:11px;color:var(--text-muted);font-weight:700;text-transform:uppercase;letter-spacing:1px;" data-i18n="annualReportsLabel">Annual Reports:</span>
                <a href="https://www.hrw.org/world-report/2024/country-chapters/china" target="_blank" style="font-size:11px;padding:4px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:4px;color:#93c5fd;text-decoration:none;">📋 HRW 2024</a>
                <a href="https://www.amnesty.org/en/location/asia-and-the-pacific/east-asia/china/report-china/" target="_blank" style="font-size:11px;padding:4px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:4px;color:#93c5fd;text-decoration:none;">📋 Amnesty 2023-24</a>
                <a href="https://www.ohchr.org/en/documents/country-reports/ohchr-assessment-human-rights-concerns-xinjiang-uyghur-autonomous-region" target="_blank" style="font-size:11px;padding:4px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:4px;color:#93c5fd;text-decoration:none;">🇺🇳 UN OHCHR 2022</a>
                <a href="https://www.state.gov/reports/2022-country-reports-on-human-rights-practices/china/" target="_blank" style="font-size:11px;padding:4px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:4px;color:#93c5fd;text-decoration:none;">🇺🇸 State Dept 2023</a>
                <a href="https://freedomhouse.org/country/china/freedom-world/2024" target="_blank" style="font-size:11px;padding:4px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:4px;color:#93c5fd;text-decoration:none;">🗽 Freedom House 2024</a>
                <a href="https://xjdp.aspi.org.au/" target="_blank" style="font-size:11px;padding:4px 10px;background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);border-radius:4px;color:#93c5fd;text-decoration:none;">🛰️ ASPI Xinjiang Data</a>
            </div>

            <!-- Live HR Signal -->
            <div id="hrSignalBar" style="margin-top:10px;display:none;padding:10px 16px;border-radius:8px;font-size:12px;"></div>

            <!-- Mobile responsive -->
            <style>
                @media (max-width: 768px) {
                    #humanitarianGrid { grid-template-columns: 1fr !important; }
                }
            </style>
        </div>

        <!-- MAP SECTION — Leaflet -->
        <div class="map-section">
            <h2>🗺️ <span data-i18n="mapTitle">China — Strategic Overview</span></h2>
            <div class="map-subtitle" data-i18n="mapSubtitle">Key cities, military zones, South China Sea flashpoints & Taiwan Strait.</div>
            <div id="chinaMap" style="width:100%;height:500px;border:2px solid var(--card-border);border-radius:8px;z-index:1;"></div>
        </div>

        <!-- KNOWLEDGE LIBRARY -->
        <div class="knowledge-library">
            <h2>
                <span class="library-icon">&#x1F4DA;</span>
                <span data-i18n="knowledgeLibraryTitle">Knowledge Library</span>
            </h2>
            <p class="open-source-disclaimer">
                Note: Background information is compiled from open-source research and analysis. One-pager documents for each category are under development.
            </p>

            <div class="knowledge-categories">

                <!-- PLA Military Posture &amp; Modernization -->
                <div class="knowledge-card collapsed" id="card-pla">
                    <div class="knowledge-header" onclick="toggleKnowledgeCard('pla')">
                        <div class="knowledge-header-title">
                            <span class="category-icon">⚔️</span>
                            <span>PLA Military Posture &amp; Modernization</span>
                        </div>
                        <span class="collapse-icon">&#x25BC;</span>
                    </div>
                    <div class="knowledge-content">
                        <p><strong>The People's Liberation Army (PLA)</strong> is undergoing its most significant modernization in decades, pursuing capabilities to fight and win wars against technologically advanced adversaries — primarily the United States.</p>
                        <p><strong>Key Developments:</strong></p>
                        <ul>
                            <li><strong>Nuclear Expansion:</strong> Rapidly expanding nuclear arsenal; estimated 500+ warheads as of 2024, on track for 1,000+ by 2030</li>
                            <li><strong>PLAN:</strong> World's largest navy by hull count; rapidly expanding aircraft carrier program (Fujian class); growing blue-water capability</li>
                            <li><strong>PLARF:</strong> Rocket Force controls world's largest missile arsenal including DF-21D and DF-26 anti-ship ballistic missiles threatening U.S. carriers</li>
                            <li><strong>A2/AD:</strong> Layered anti-access/area-denial systems designed to deny U.S. forces freedom of action in the First and Second Island Chains</li>
                            <li><strong>Cyber/Space:</strong> Advanced cyber warfare capabilities; anti-satellite weapons demonstrated; GPS jamming operations observed</li>
                        </ul>
                        <div class="open-source-disclaimer">* Based on open-source intelligence, academic research, and publicly available government reports</div>
                        <div class="report-links-grid">
                            <a href="https://www.defense.gov/News/Releases/?sort=date&categories=China" target="_blank" class="report-link">&#x1F4D1; DoD - China Reports</a>
<a href="https://www.csis.org/programs/china-power-project" target="_blank" class="report-link">&#x1F4D1; CSIS China Power Project</a>
<a href="https://www.uscc.gov/" target="_blank" class="report-link">&#x1F4D1; US-China Economic Security Commission</a>
                        </div>
                    </div>
                </div>

                <!-- South China Sea &amp; Maritime Disputes -->
                <div class="knowledge-card collapsed" id="card-scs">
                    <div class="knowledge-header" onclick="toggleKnowledgeCard('scs')">
                        <div class="knowledge-header-title">
                            <span class="category-icon">🚢</span>
                            <span>South China Sea &amp; Maritime Disputes</span>
                        </div>
                        <span class="collapse-icon">&#x25BC;</span>
                    </div>
                    <div class="knowledge-content">
                        <p><strong>The South China Sea</strong> is the world's most contested maritime region, with China claiming approximately 90% of the sea through its historical "nine-dash line" claim rejected by the 2016 UNCLOS tribunal.</p>
                        <p><strong>Key Flashpoints:</strong></p>
                        <ul>
                            <li><strong>Spratly Islands:</strong> China has built artificial islands with military installations (runways, hangars, missile systems) on previously submerged reefs</li>
                            <li><strong>Scarborough Shoal:</strong> Contested with Philippines; China Coast Guard conducts water cannon operations against Filipino resupply vessels</li>
                            <li><strong>Second Thomas Shoal:</strong> Ongoing standoff; Philippines maintains troops on grounded vessel BRP Sierra Madre; China attempts to block resupply</li>
                            <li><strong>Freedom of Navigation:</strong> U.S. and allied naval vessels conduct FONOPs; China shadows and intercepts with increasing aggressiveness</li>
                            <li><strong>ASEAN Tensions:</strong> Vietnam, Malaysia, Brunei, and the Philippines all have overlapping claims</li>
                        </ul>
                        <div class="open-source-disclaimer">* Based on open-source intelligence, academic research, and publicly available government reports</div>
                        <div class="report-links-grid">
                            <a href="https://amti.csis.org/" target="_blank" class="report-link">&#x1F4D1; CSIS Asia Maritime Transparency Initiative</a>
<a href="https://www.cfr.org/global-conflict-tracker/conflict/territorial-disputes-south-china-sea" target="_blank" class="report-link">&#x1F4D1; CFR - South China Sea</a>
<a href="https://www.eia.gov/" target="_blank" class="report-link">&#x1F4D1; EIA - South China Sea Energy</a>
                        </div>
                    </div>
                </div>

                <!-- Taiwan Strait Dynamics -->
                <div class="knowledge-card collapsed" id="card-taiwan">
                    <div class="knowledge-header" onclick="toggleKnowledgeCard('taiwan')">
                        <div class="knowledge-header-title">
                            <span class="category-icon">🏝️</span>
                            <span>Taiwan Strait Dynamics</span>
                        </div>
                        <span class="collapse-icon">&#x25BC;</span>
                    </div>
                    <div class="knowledge-content">
                        <p><strong>The Taiwan Strait</strong> is the most consequential potential flashpoint in the Indo-Pacific. China considers Taiwan a core interest and has never renounced the use of force for reunification.</p>
                        <p><strong>Current Dynamics:</strong></p>
                        <ul>
                            <li><strong>PLA Exercises:</strong> Large-scale military exercises around Taiwan increasing in frequency and complexity; Joint Sword exercises (2023, 2024) simulated blockade</li>
                            <li><strong>ADIZ Violations:</strong> PLA aircraft regularly enter Taiwan's Air Defense Identification Zone; Taiwan scrambles fighters in response</li>
                            <li><strong>U.S. Commitment:</strong> Strategic ambiguity policy; Taiwan Relations Act commits U.S. to provide defensive arms; Congress increasingly hawkish on Taiwan</li>
                            <li><strong>Timeline Debates:</strong> U.S. military leaders have cited 2027 as a key date; others assess risk is real but not imminent</li>
                            <li><strong>Economic Stakes:</strong> Taiwan produces ~90% of world's most advanced semiconductors (TSMC); a Taiwan conflict would be globally catastrophic</li>
                        </ul>
                        <div class="open-source-disclaimer">* Based on open-source intelligence, academic research, and publicly available government reports</div>
                        <div class="report-links-grid">
                            <a href="https://www.csis.org/programs/international-security-program/asia-division/taiwan" target="_blank" class="report-link">&#x1F4D1; CSIS - Taiwan</a>
<a href="https://www.brookings.edu/topic/taiwan/" target="_blank" class="report-link">&#x1F4D1; Brookings - Taiwan</a>
<a href="https://foreignpolicy.com/tag/taiwan/" target="_blank" class="report-link">&#x1F4D1; Foreign Policy - Taiwan</a>
                        </div>
                    </div>
                </div>

                <!-- Regional Competition &amp; Indo-Pacific -->
                <div class="knowledge-card collapsed" id="card-regional_competition">
                    <div class="knowledge-header" onclick="toggleKnowledgeCard('regional_competition')">
                        <div class="knowledge-header-title">
                            <span class="category-icon">🌏</span>
                            <span>Regional Competition &amp; Indo-Pacific</span>
                        </div>
                        <span class="collapse-icon">&#x25BC;</span>
                    </div>
                    <div class="knowledge-content">
                        <p><strong>China's rise</strong> is reshaping regional security architecture, challenging U.S. primacy and creating new alliance dynamics across the Indo-Pacific.</p>
                        <p><strong>Key Dynamics:</strong></p>
                        <ul>
                            <li><strong>QUAD:</strong> U.S., Japan, India, Australia security dialogue focused on countering Chinese influence; increasing military exercises</li>
                            <li><strong>AUKUS:</strong> Australia to receive nuclear-powered submarines with U.S./UK technology; represents significant strategic shift</li>
                            <li><strong>China-Russia:</strong> "No limits partnership" deepened since Ukraine war; Russia provides energy, China provides manufactured goods and diplomatic cover</li>
                            <li><strong>BRI:</strong> Belt and Road Initiative investments create economic dependencies across Asia, Africa, and Europe; debt trap concerns</li>
                            <li><strong>India-China:</strong> Galwan Valley clash (2020); ongoing LAC tensions; India increasingly tilting toward U.S./Quad alignment</li>
                        </ul>
                        <div class="open-source-disclaimer">* Based on open-source intelligence, academic research, and publicly available government reports</div>
                        <div class="report-links-grid">
                            <a href="https://www.iiss.org/" target="_blank" class="report-link">&#x1F4D1; IISS - Asia-Pacific</a>
<a href="https://carnegieendowment.org/" target="_blank" class="report-link">&#x1F4D1; Carnegie Endowment</a>
<a href="https://www.rsis.edu.sg/" target="_blank" class="report-link">&#x1F4D1; RSIS Singapore</a>
                        </div>
                    </div>
                </div>
            <!-- Xinjiang & Tibet — Human Rights Indicators -->
                <div class="knowledge-card collapsed" id="card-human_rights">
                    <div class="knowledge-header" onclick="toggleKnowledgeCard('human_rights')">
                        <div class="knowledge-header-title">
                            <span class="category-icon">🔍</span>
                            <span>Xinjiang, Tibet &amp; Human Rights Indicators</span>
                        </div>
                        <span class="collapse-icon">&#x25BC;</span>
                    </div>
                    <div class="knowledge-content">
                        <p><strong>China's repression of ethnic minorities</strong> in Xinjiang and Tibet represents one of the most significant human rights situations of the 21st century, with major geopolitical consequences.</p>
                        <p><strong>Xinjiang:</strong></p>
                        <ul>
                            <li><strong>Mass Detention:</strong> Estimated 1–1.8 million Uyghurs and other Turkic Muslims held in "vocational training centers"; extensive surveillance state</li>
                            <li><strong>Genocide Designation:</strong> U.S., UK, Canada, Netherlands, and others have formally designated Chinese actions as genocide or crimes against humanity</li>
                            <li><strong>Supply Chain Impact:</strong> Uyghur Forced Labor Prevention Act (UFLPA) bans imports with Xinjiang supply chain links; significant trade disruption</li>
                            <li><strong>International Response:</strong> Sanctions on Chinese officials; diplomatic boycotts of 2022 Beijing Olympics; ongoing UN investigations</li>
                        </ul>
                        <p><strong>Tibet:</strong></p>
                        <ul>
                            <li><strong>Self-Immolations:</strong> Over 150 Tibetans have self-immolated since 2009 protesting Chinese rule; ongoing protests suppressed</li>
                            <li><strong>Religious Suppression:</strong> Dalai Lama reincarnation dispute; Panchen Lama disappeared in 1995; monasteries under state surveillance</li>
                            <li><strong>Strategic Importance:</strong> Tibet Plateau controls headwaters for major Asian rivers; significant military infrastructure buildup</li>
                        </ul>
                        <div class="open-source-disclaimer">* Based on open-source intelligence, UN reports, and publicly available government assessments. Updated March 2026.</div>
                        <div class="report-links-grid">
                            <a href="https://www.state.gov/reports/2022-country-reports-on-human-rights-practices/china/" target="_blank" class="report-link">&#x1F4D1; State Dept - China HR</a>
                            <a href="https://www.ohchr.org/en/documents/thematic-reports/ohchrass-xinjiang" target="_blank" class="report-link">&#x1F4D1; UN - Xinjiang Report</a>
                            <a href="https://www.rfa.org/english/news/uyghur/" target="_blank" class="report-link">&#x1F4D1; RFA - Uyghur</a>
                        </div>
                    </div>
                </div>

                <!-- Economic Coercion & Trade War -->
                <div class="knowledge-card collapsed" id="card-economy">
                    <div class="knowledge-header" onclick="toggleKnowledgeCard('economy')">
                        <div class="knowledge-header-title">
                            <span class="category-icon">💹</span>
                            <span>Economic Coercion &amp; Trade War Dynamics</span>
                        </div>
                        <span class="collapse-icon">&#x25BC;</span>
                    </div>
                    <div class="knowledge-content">
                        <p><strong>China's use of economic coercion</strong> as a geopolitical tool has intensified, with trade bans, rare earth export controls, and financial pressure targeting adversaries.</p>
                        <p><strong>Key Vectors (2025–2026):</strong></p>
                        <ul>
                            <li><strong>Rare Earth Controls:</strong> China controls ~85% of global rare earth processing; export restrictions on gallium, germanium, antimony announced 2023–2024; direct threat to Western defense supply chains</li>
                            <li><strong>US-China Trade War:</strong> Tariffs exceeding 100% on key goods; technology decoupling accelerating; TSMC export controls restricting advanced chips to China</li>
                            <li><strong>Taiwan Economic Leverage:</strong> China is Taiwan's largest trading partner; economic interdependence complicates cross-strait calculus</li>
                            <li><strong>Belt and Road:</strong> Debt distress in Pakistan, Sri Lanka, Zambia; BRI leverage as geopolitical tool increasingly recognized</li>
                            <li><strong>Iran Connection:</strong> China purchasing discounted Russian and Iranian oil; sanctions evasion enabling both Iran and Russia to sustain war economies</li>
                            <li><strong>Hormuz Risk:</strong> ~20% of global oil transits Hormuz; US-Iran conflict disruption raises Chinese energy costs and increases its leverage as a mediator</li>
                        </ul>
                        <div class="open-source-disclaimer">* Based on open-source intelligence, academic research, and publicly available government reports. Updated March 2026.</div>
                        <div class="report-links-grid">
                            <a href="https://www.uscc.gov/" target="_blank" class="report-link">&#x1F4D1; US-China Commission</a>
                            <a href="https://www.csis.org/programs/china-power-project" target="_blank" class="report-link">&#x1F4D1; CSIS China Power</a>
                            <a href="https://www.piie.com/blogs/trade-investment-policy-watch" target="_blank" class="report-link">&#x1F4D1; PIIE Trade Watch</a>
                        </div>
                    </div>
                </div>
                
            </div>
        </div>

        <!-- RECENT ARTICLES — TABBED -->
        <div class="articles-section">
            <div class="section-title" data-i18n="articles_title">📰 Recent China & PLA Articles</div>
            <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
                <button onclick="switchArticleTab('en')" id="tab-en" style="padding:6px 16px;border-radius:6px;border:2px solid var(--accent);background:var(--accent);color:white;font-family:'Times New Roman',serif;font-size:13px;font-weight:bold;cursor:pointer;">🇺🇸 English</button>
                <button onclick="switchArticleTab('zh')" id="tab-zh" style="padding:6px 16px;border-radius:6px;border:2px solid var(--card-border);background:transparent;color:var(--text-secondary);font-family:'Times New Roman',serif;font-size:13px;font-weight:bold;cursor:pointer;">🇨🇳 中文</button>
                <button onclick="switchArticleTab('reddit')" id="tab-reddit" style="padding:6px 16px;border-radius:6px;border:2px solid var(--card-border);background:transparent;color:var(--text-secondary);font-family:'Times New Roman',serif;font-size:13px;font-weight:bold;cursor:pointer;">💬 Reddit</button>
                <button onclick="switchArticleTab('telegram')" id="tab-telegram" style="padding:6px 16px;border-radius:6px;border:2px solid var(--card-border);background:transparent;color:var(--text-secondary);font-family:'Times New Roman',serif;font-size:13px;font-weight:bold;cursor:pointer;">📡 Telegram</button>
            </div>
            <div id="articlesContainer">
                <div style="text-align:center;color:var(--text-secondary);padding:30px;">Loading articles...</div>
            </div>
        </div>

        </div> <!-- /main-content -->
        </div> <!-- /page-with-sidebar -->

        <footer>
            <div class="footer-grid" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:25px;margin-bottom:20px;">
                <div>
                    <h4 style="font-size:0.95em;margin-bottom:8px;color:var(--text-primary);" data-i18n="footer_methodology_title">Methodology</h4>
                    <p style="font-size:0.8em;color:var(--text-secondary);line-height:1.55;" data-i18n="footer_methodology_text">Multi-factor stability assessment integrating PLA posture, South China Sea maritime activity, Taiwan Strait dynamics, economic coercion vectors, and humanitarian indicators (Xinjiang, Tibet, Hong Kong). Rhetoric tracker score (theatre 0-100) drawn from /api/rhetoric/china; humanitarian monitor from china_humanitarian.py. Articles aggregated from rhetoric tracker, deduped by URL.</p>
                </div>
                <div>
                    <h4 style="font-size:0.95em;margin-bottom:8px;color:var(--text-primary);" data-i18n="footer_sources_title">Data Sources</h4>
                    <p style="font-size:0.8em;color:var(--text-secondary);line-height:1.55;" data-i18n="footer_sources_text">RSS (SCMP, Global Times, Xinhua, Reuters, Nikkei Asia), GDELT (English + Mandarin queries), NewsAPI, Brave Search (tertiary fallback), BlueSky Asia aggregator, Telegram (@PLA_Daily, @ChinaWatcher_Asia). Reddit r/China, r/geopolitics, r/CredibleDefense. AMTI, ACLED, DoD China Reports for background. HKEX Hang Seng via Yahoo Finance.</p>
                </div>
                <div>
                    <h4 style="font-size:0.95em;margin-bottom:8px;color:var(--text-primary);" data-i18n="footer_contact_title">Asifah Analytics</h4>
                    <p style="font-size:0.8em;color:var(--text-secondary);line-height:1.55; margin-bottom:12px;">Backend: <a href="https://asifah-asia-backend.onrender.com" style="color:var(--accent);">asifah-asia-backend.onrender.com</a><br>Cadence: ~12-hour Redis refresh<br>Open-source OSINT · Not for operational use</p>
                </div>
            </div>

            <!-- Canonical pill CTAs (BMC + Contact) — added May 25 2026 -->
            <div style="display:flex; justify-content:center; gap:12px; flex-wrap:wrap; margin:18px 0 14px;">
                <a href="https://www.buymeacoffee.com/asifahanalytics" target="_blank" rel="noopener" style="display:inline-flex; align-items:center; gap:6px; padding:10px 22px; background:linear-gradient(180deg, #fbbf24 0%, #d97706 100%); color:#fff; border:2px solid rgba(255,255,255,0.2); border-radius:6px; font-weight:bold; font-size:14px; text-decoration:none; transition:all 0.3s ease; box-shadow:0 3px 8px rgba(217,119,6,0.3);" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 5px 12px rgba(217,119,6,0.4)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 3px 8px rgba(217,119,6,0.3)';" data-i18n="footer_bmc_pill">☕ Buy Me a Coffee</a>
                <a href="mailto:asifahanalytics@gmail.com" style="display:inline-flex; align-items:center; gap:6px; padding:10px 22px; background:linear-gradient(180deg, #38bdf8 0%, #0284c7 100%); color:#fff; border:2px solid rgba(255,255,255,0.2); border-radius:6px; font-weight:bold; font-size:14px; text-decoration:none; transition:all 0.3s ease; box-shadow:0 3px 8px rgba(2,132,199,0.3);" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 5px 12px rgba(2,132,199,0.4)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 3px 8px rgba(2,132,199,0.3)';" data-i18n="footer_contact_pill">✉️ Contact Asifah</a>
            </div>

            <div style="padding:15px; background:rgba(139,0,0,0.15); border-radius:8px; font-size:0.8em; color:var(--text-secondary); line-height:1.55;" data-i18n-html="footer_disclaimer">
                <strong>⚠️ DISCLAIMER:</strong> This dashboard provides probability estimates based on open-source intelligence aggregation and algorithmic analysis. It does not constitute intelligence assessments, military advice, or policy recommendations. Stability indicators reflect media signal intensity and should not be interpreted as ground-truth predictions. Always consult authoritative sources for decision-making. Updated every ~12 hours · Not for operational use.
            </div>

            <!-- Small text links (Mission · Privacy · Home) -->
            <div style="margin-top:18px; text-align:center; font-size:0.75em; color:var(--text-muted);">
                <a href="mission.html" style="color:var(--text-muted); text-decoration:none; margin:0 8px;" data-i18n="footer_mission_link">Mission Statement</a>·
                <a href="privacy.html" style="color:var(--text-muted); text-decoration:none; margin:0 8px;" data-i18n="footer_privacy_link">Privacy Policy</a>·
                <a href="index.html" style="color:var(--text-muted); text-decoration:none; margin:0 8px;" data-i18n="footer_home_link">Home</a>
            </div>

            <div style="margin-top:18px; font-size:0.75em; color:var(--text-muted); text-align:center;">
                &copy; 2025-2026 ASIFAH ANALYTICS — ALL RIGHTS RESERVED — v2.1.0<br>
                Proprietary and Confidential. Unauthorized use, reproduction, or distribution prohibited.
            </div>
        </footer>
    </div>

    <script data-cfasync="false" src="/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js"></script><script>
        const BACKEND_URL = 'https://asifah-asia-backend.onrender.com';
        const RTL_LANGS = [];

        // Theme
        function initTheme() {
            const savedTheme = localStorage.getItem('asifah-theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);
        }
        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('asifah-theme', next);
        }
        initTheme();

        // Knowledge Library Toggle
        function toggleKnowledgeCard(cardId) {
            const card = document.getElementById('card-' + cardId);
            if (card) card.classList.toggle('collapsed');
        }

        // Loading Overlay
        let loadingStepIndex = 0;
        let loadingInterval = null;
        let loadingTimeout = null;
        const STEP_COUNT = 5;

        function startLoadingProgress() {
            const steps = Array.from({length: STEP_COUNT}, (_, i) => 'step' + (i + 1));
            loadingInterval = setInterval(() => {
                if (loadingStepIndex < steps.length - 1) {
                    const cur = document.getElementById(steps[loadingStepIndex]);
                    if (cur) { cur.classList.remove('active'); cur.classList.add('complete'); cur.querySelector('.step-icon').textContent = '\u2713'; }
                    loadingStepIndex++;
                    const next = document.getElementById(steps[loadingStepIndex]);
                    if (next) next.classList.add('active');
                }
            }, 5000);
            loadingTimeout = setTimeout(() => {
                document.getElementById('loadingError').style.display = 'block';
                document.getElementById('loadingError').textContent = '\u26A0\uFE0F Loading is taking longer than expected. Please wait or refresh.';
            }, 60000);
        }

        function hideLoadingOverlay() {
            if (loadingInterval) clearInterval(loadingInterval);
            if (loadingTimeout) clearTimeout(loadingTimeout);
            document.querySelectorAll('.loading-step').forEach(step => {
                step.classList.remove('active');
                step.classList.add('complete');
                step.querySelector('.step-icon').textContent = '\u2713';
            });
            setTimeout(() => {
                const overlay = document.getElementById('loadingOverlay');
                if (overlay) overlay.classList.add('hidden');
            }, 500);
        }

        // Fetch articles from backend
        async function loadArticles() {
            try {
                const response = await fetch(BACKEND_URL + '/api/asia/threat/china');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();
                const articles = data.articles_en || data.articles || [];
                const articlesZh = data.articles_zh || [];
                const articlesReddit = data.articles_reddit || [];
                const articlesTelegram = data.articles_telegram || [];
                const combined = [
                    ...articles.map(a => ({...a, language: a.language || 'en'})),
                    ...articlesZh.map(a => ({...a, language: 'zh'})),
                    ...articlesReddit.map(a => ({...a, language: 'reddit'})),
                    ...articlesTelegram.map(a => ({...a, language: 'telegram'})),
                ];
                if (combined.length > 0) {
                    displayArticles(combined);
                } else {
                    displayArticlesFallbackStatic();
                }
            } catch (error) {
                console.warn('Primary endpoint failed:', error.message);
                displayArticlesFallbackStatic();
            }
        }

        let _allArticles = [];

        function switchArticleTab(lang) {
            ['en','zh','reddit','telegram'].forEach(t => {
                const btn = document.getElementById('tab-' + t);
                if (!btn) return;
                if (t === lang) {
                    btn.style.background = 'var(--accent)';
                    btn.style.color = 'white';
                    btn.style.borderColor = 'var(--accent)';
                } else {
                    btn.style.background = 'transparent';
                    btn.style.color = 'var(--text-secondary)';
                    btn.style.borderColor = 'var(--card-border)';
                }
            });
            const filtered = _allArticles.filter(a => {
                const src = (a.source || a.source_name || '').toLowerCase();
                const lng = (a.language || '').toLowerCase();
                if (lang === 'reddit') return src.includes('r/') || src.includes('reddit') || lng === 'reddit';
                if (lang === 'telegram') return src.includes('telegram') || lng === 'telegram';
                if (lang === 'zh') return lng === 'zh' || lng === 'zho';
                return lng === 'en' || lng === '' || lng === 'multi' ||
                    (!src.includes('r/') && !src.includes('reddit') &&
                     !src.includes('telegram') && lng !== 'zh' && lng !== 'zho');
            });
            renderArticleList(filtered.length > 0 ? filtered : _allArticles.slice(0, 20));
        }

        function renderArticleList(articles) {
            const container = document.getElementById('articlesContainer');
            if (!articles || articles.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-secondary);font-style:italic;">No articles in this category yet — try another tab or run a fresh scan.</div>';
                return;
            }
            container.innerHTML = articles.slice(0, 20).map(article => {
                const title = article.title || 'Untitled';
                const source = typeof article.source === 'object'
                    ? (article.source.name || '') : (article.source || article.source_name || '');
                const published = article.published || article.publishedAt || article.date || '';
                const url = article.url || article.link || '#';
                const description = article.description || '';
                let dateStr = '';
                if (published) {
                    try { dateStr = new Date(published).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
                    catch(e) { dateStr = published; }
                }
                return '<div class="article-item">' +
                    '<div class="article-title">' + title + '</div>' +
                    (description ? '<div style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;line-height:1.5;">' + description.substring(0, 200) + (description.length > 200 ? '...' : '') + '</div>' : '') +
                    '<div class="article-meta">' + source + (dateStr ? ' · ' + dateStr : '') + '</div>' +
                    (url !== '#' ? '<a href="' + url + '" target="_blank" class="article-link">Read article →</a>' : '') +
                    '</div>';
            }).join('');
        }

        function displayArticles(articles) {
            _allArticles = articles || [];
            switchArticleTab('en');
        }

        function displayArticlesFallbackStatic() {
            const container = document.getElementById('articlesContainer');
            container.innerHTML =
                '<div style="text-align:center; padding:30px; color:var(--text-secondary);">' +
                '<p style="font-size:16px; margin-bottom:15px;">&#x1F4E1; Live article feed loading for China.</p>' +
                '<p style="font-size:13px; margin-bottom:20px;">Check these curated OSINT sources:</p>' +
                '<div style="display:flex; flex-wrap:wrap; justify-content:center; gap:10px; margin-top:15px;">' +
                '<a href="https://www.scmp.com/" target="_blank" style="padding:10px 18px; background:var(--accent); color:white; border-radius:6px; text-decoration:none; font-size:13px; font-weight:bold;">SCMP</a>' +
                '<a href="https://thediplomat.com/tag/china/" target="_blank" style="padding:10px 18px; background:var(--accent); color:white; border-radius:6px; text-decoration:none; font-size:13px; font-weight:bold;">The Diplomat</a>' +
                '<a href="https://amti.csis.org/" target="_blank" style="padding:10px 18px; background:var(--accent); color:white; border-radius:6px; text-decoration:none; font-size:13px; font-weight:bold;">CSIS AMTI</a>' +
                '<a href="https://www.globaltimes.cn/" target="_blank" style="padding:10px 18px; background:var(--accent); color:white; border-radius:6px; text-decoration:none; font-size:13px; font-weight:bold;">Global Times</a>' +
                '</div>' +
                '</div>';
        }

        async function loadRhetoricData() {
            try {
                const r = await fetch('https://asifah-asia-backend.onrender.com/api/rhetoric/china/summary');
                const data = await r.json();
                if (!data.success) return;
                const LEVELS = { 0:'#6b7280',1:'#3b82f6',2:'#f59e0b',3:'#f97316',4:'#ef4444',5:'#dc2626' };
                const LABELS = { 0:'Baseline',1:'Rhetoric',2:'Warning',3:'Confrontation',4:'Coercion',5:'Active Conflict' };
                const level = data.outbound_max_level || 0;
                const color = LEVELS[level] || '#6b7280';
                // Banner badge
                const badge = document.getElementById('rhetoricLevelBadge');
                if (badge) { badge.style.background = color; badge.textContent = `⚡ Level ${level} — ${LABELS[level]}`; }
                // Card
                const scoreEl = document.getElementById('rhetoricScore');
                if (scoreEl) scoreEl.textContent = `${data.outbound_score || 0}/100`;
                const labelEl = document.getElementById('rhetoricTheatreLabel');
                if (labelEl) { labelEl.textContent = LABELS[level] || '--'; labelEl.style.background = color; }
                // Scan info
                const scanEl = document.getElementById('rhetoricScanInfo');
                if (scanEl && data.scanned_at) {
                    const ago = Math.round((Date.now() - new Date(data.scanned_at)) / 60000);
                    scanEl.textContent = `Last scan: ${ago < 60 ? ago+'m' : Math.round(ago/60)+'h'} ago`;
                }
                // Actor rows
                const actorEl = document.getElementById('rhetoricActorList');
                if (actorEl) {
                    const actors = [
                        { label: '👁️ Xi / CMC',          level: data.xi_level || 0 },
                        { label: '⚔️ PLA Operational',    level: data.pla_level || 0 },
                        { label: '📢 MFA / Global Times',  level: data.mfa_level || 0 },
                        { label: '💹 Economic Coercion',   level: data.econ_level || 0 },
                    ];
                    actorEl.innerHTML = actors.map(a =>
                        `<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--card-border);">
                            <span>${a.label}</span>
                            <span style="font-weight:700;color:${LEVELS[a.level]};">L${a.level}</span>
                        </div>`
                    ).join('');
                }
            } catch(e) { console.warn('[Rhetoric] Load failed:', e); }
        }

        // China Stability Data
        async function loadStabilityData() {
            try {
                const r = await fetch('https://asifah-asia-backend.onrender.com/api/china/stability/summary');
                const data = await r.json();
                if (!data.success) return;

                const LEVEL_COLORS = {0:'#6b7280',1:'#3b82f6',2:'#f59e0b',3:'#f97316',4:'#ef4444',5:'#dc2626'};

                // Stability score card
                const score = data.stability_score || 0;
                const scoreEl = document.getElementById('stabilityScore');
                if (scoreEl) scoreEl.textContent = score;

                const labelEl = document.getElementById('stabilityLabel');
                if (labelEl) {
                    labelEl.textContent = data.stability_label || '--';
                    labelEl.style.background = data.stability_color || '#6b7280';
                }

                const barEl = document.getElementById('stabilityBarFill');
                if (barEl) {
                    barEl.style.width = score + '%';
                    barEl.style.background = data.stability_color || '#22c55e';
                }

                // Vector breakdown
                const vectorEl = document.getElementById('stabilityVectors');
                if (vectorEl) {
                    const vectors = [
                        { label: '💹 Economic',      level: data.econ_level || 0 },
                        { label: '📡 Rhetoric/PLA',  level: data.rhetoric_level || 0 },
                        { label: '✊ Unrest',        level: data.unrest_level || 0 },
                        { label: '👁️ Leadership',    level: data.leadership_level || 0 },
                        { label: '🔴 Minorities',    level: data.minority_level || 0 },
                        { label: '🇺🇸 US-China',     level: data.us_china_level || 0 },
                    ];
                    vectorEl.innerHTML = vectors.map(v =>
                        `<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--card-border);">
                            <span>${v.label}</span>
                            <span style="font-weight:700;color:${LEVEL_COLORS[v.level]};">L${v.level}</span>
                        </div>`
                    ).join('');
                }

                // Scan time
                const scanEl = document.getElementById('stabilityScanInfo');
                if (scanEl && data.scanned_at) {
                    const ago = Math.round((Date.now() - new Date(data.scanned_at)) / 60000);
                    scanEl.textContent = `Last scan: ${ago < 60 ? ago+'m' : Math.round(ago/60)+'h'} ago`;
                }

                // Economic indicators
                if (data.yuan_usd) {
                    const yuanEl = document.getElementById('yuanRate');
                    if (yuanEl) yuanEl.textContent = data.yuan_usd.toFixed(4);
                    const yuanStatusEl = document.getElementById('yuanStatus');
                    if (yuanStatusEl) {
                        const colors = { stable:'#22c55e', warning:'#f59e0b', stress:'#ef4444', unknown:'#6b7280' };
                        yuanStatusEl.textContent = (data.yuan_status || 'unknown').toUpperCase();
                        yuanStatusEl.style.background = colors[data.yuan_status] || '#6b7280';
                    }
                }

                if (data.brent_price) {
                    const brentEl = document.getElementById('brentPrice');
                    if (brentEl) brentEl.textContent = `$${data.brent_price.toFixed(2)}`;
                    const brentChangeEl = document.getElementById('brentChange');
                    if (brentChangeEl) {
                        const chg = data.brent_change_pct || 0;
                        brentChangeEl.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}% today · China imports ~75% of oil needs`;
                        brentChangeEl.style.color = chg >= 0 ? '#ef4444' : '#22c55e';
                    }
                    const brentStatusEl = document.getElementById('brentStatus');
                    if (brentStatusEl) {
                        const colors = { normal:'#22c55e', elevated:'#f59e0b', stress:'#ef4444', unknown:'#6b7280' };
                        brentStatusEl.textContent = (data.brent_status || 'unknown').toUpperCase();
                        brentStatusEl.style.background = colors[data.brent_status] || '#6b7280';
                    }
                }

                // HKEX Hang Seng (v1.0 May 25 2026 — Black Swan POC, TASE-pattern mirror)
                const hkex = data.hkex || {};
                if (hkex.value) {
                    const hkexValueEl = document.getElementById('hkexValue');
                    if (hkexValueEl) hkexValueEl.textContent = hkex.value.toLocaleString();
                    const hkexChangeEl = document.getElementById('hkexChange');
                    if (hkexChangeEl) {
                        const chg = hkex.change_pct_24h || 0;
                        const marketSuffix = hkex.market_status === 'closed' ? ' (market closed)' : '';
                        hkexChangeEl.innerHTML = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%${marketSuffix} · <span data-i18n="hkex_subtitle">Hong Kong equity confidence proxy</span>`;
                        hkexChangeEl.style.color = chg >= 0 ? '#22c55e' : '#ef4444';
                    }
                    const hkexStatusEl = document.getElementById('hkexStatus');
                    if (hkexStatusEl) {
                        // Derive status from trend + magnitude
                        const chg = hkex.change_pct_24h || 0;
                        let status = 'stable';
                        if (chg <= -2.0) status = 'stress';
                        else if (chg <= -1.0) status = 'warning';
                        else if (chg >= 2.0) status = 'rally';
                        else status = 'stable';
                        const colors = { stable:'#22c55e', warning:'#f59e0b', stress:'#ef4444', rally:'#0ea5e9', unknown:'#6b7280' };
                        hkexStatusEl.textContent = status.toUpperCase();
                        hkexStatusEl.style.background = colors[status] || '#6b7280';
                    }
                    // Build sparkline if data available
                    if (hkex.sparkline && hkex.sparkline.length > 0) {
                        buildHkexSparkline(hkex.sparkline);
                    }
                } else {
                    const hkexValueEl = document.getElementById('hkexValue');
                    if (hkexValueEl) hkexValueEl.textContent = 'N/A';
                    const hkexChangeEl = document.getElementById('hkexChange');
                    if (hkexChangeEl) hkexChangeEl.textContent = hkex.source === 'Unavailable' ? 'Live feed unavailable' : '--';
                }

                const usChinaEl = document.getElementById('usChinaLevel');
                if (usChinaEl) {
                    const lvl = data.us_china_level || 0;
                    usChinaEl.textContent = `L${lvl}`;
                    usChinaEl.style.background = LEVEL_COLORS[lvl] || '#6b7280';
                }

                const econScanEl = document.getElementById('econScanInfo');
                if (econScanEl && data.scanned_at) {
                    const ago = Math.round((Date.now() - new Date(data.scanned_at)) / 60000);
                    econScanEl.textContent = `Updated: ${ago < 60 ? ago+'m' : Math.round(ago/60)+'h'} ago`;
                }

                // Leadership cards
                const leadership = data.leadership || [];
                const gridEl = document.getElementById('leadershipGrid');
                if (gridEl && leadership.length > 0) {
                    gridEl.innerHTML = leadership.map(l => `
                        <div class="leader-card">
                            <div class="lc-role">${l.flag || '🇨🇳'} ${l.role}</div>
                            <div class="lc-name">${l.name}</div>
                            <div class="lc-since">Since ${l.since}</div>
                            <div class="lc-note">${l.note}</div>
                            ${l.risk_note ? `<div class="lc-risk">⚠️ ${l.risk_note}</div>` : ''}
                        </div>
                    `).join('');
                }

            } catch(e) {
                console.warn('[Stability] Load failed:', e);
            }
        }
        
        // Leaflet Map — China Strategic Overview
        function initChinaMap() {
            if (!document.getElementById('chinaMap')) return;
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(link);
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            script.onload = function() {
                const map = L.map('chinaMap', { zoomControl: true, scrollWheelZoom: false })
                    .setView([35.0, 105.0], 4);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors',
                    maxZoom: 10
                }).addTo(map);

                // ── CITIES & MILITARY ──
                const cities = [
                    { name: '🏛️ Beijing',       lat: 39.91, lng: 116.39, color: '#ef4444', note: 'Capital — CCP/CMC headquarters' },
                    { name: '💼 Shanghai',       lat: 31.22, lng: 121.47, color: '#f97316', note: 'Financial center — economic bellwether' },
                    { name: '🏭 Chongqing',      lat: 29.56, lng: 106.55, color: '#f59e0b', note: 'Major inland industrial city' },
                    { name: '⚓ Qingdao',        lat: 36.07, lng: 120.37, color: '#3b82f6', note: 'PLAN North Sea Fleet HQ' },
                    { name: '⚓ Zhoushan',       lat: 30.00, lng: 122.10, color: '#3b82f6', note: 'PLAN East Sea Fleet HQ' },
                    { name: '⚓ Sanya',          lat: 18.25, lng: 109.51, color: '#3b82f6', note: 'PLAN South Sea Fleet HQ — South China Sea base' },
                    { name: '⚠️ Taiwan Strait',  lat: 24.50, lng: 120.00, color: '#f59e0b', note: 'Key flashpoint — PLA exercise zone' },
                    { name: '⚠️ Scarborough Shoal', lat: 15.14, lng: 117.75, color: '#ef4444', note: 'Active standoff with Philippines' },
                    { name: '⚠️ Spratly Islands', lat: 10.00, lng: 114.50, color: '#f97316', note: 'Artificial islands with PLA military installations' },
                ];

                // ── HUMANITARIAN SITES ──
                const humanitarianSites = [
                    // Xinjiang detention clusters (ASPI-identified regions)
                    { name: '🔴 Urumqi — Xinjiang Hub', lat: 43.79, lng: 87.60, color: '#dc2626',
                      note: '<strong style="color:#ef4444;">XINJIANG</strong><br>Regional capital — major detention facility cluster<br><em>Source: ASPI Xinjiang Data Project (2022)</em>' },
                    { name: '🔴 Kashgar — Southern Xinjiang', lat: 39.47, lng: 75.99, color: '#dc2626',
                      note: '<strong style="color:#ef4444;">XINJIANG</strong><br>Southern Xinjiang — highest concentration of Uyghur population and facilities<br><em>Source: ASPI Xinjiang Data Project (2022)</em>' },
                    { name: '🔴 Hotan — Xinjiang', lat: 37.11, lng: 79.92, color: '#dc2626',
                      note: '<strong style="color:#ef4444;">XINJIANG</strong><br>Hotan Prefecture — significant detention infrastructure identified via satellite<br><em>Source: ASPI Xinjiang Data Project (2022)</em>' },
                    { name: '🔴 Aksu — Central Xinjiang', lat: 41.17, lng: 80.26, color: '#dc2626',
                      note: '<strong style="color:#ef4444;">XINJIANG</strong><br>Aksu Prefecture — mid-region detention cluster<br><em>Source: ASPI Xinjiang Data Project (2022)</em>' },
                    // Tibet
                    { name: '🟡 Lhasa — Tibet', lat: 29.65, lng: 91.11, color: '#d97706',
                      note: '<strong style="color:#f59e0b;">TIBET</strong><br>Tibet Autonomous Region capital — monasteries under surveillance; patriotic education campaigns<br>150+ self-immolations since 2009 across TAR<br><em>Source: TCHRD (March 2024)</em>' },
                    { name: '🟡 Shigatse — Tibet', lat: 29.27, lng: 88.88, color: '#d97706',
                      note: '<strong style="color:#f59e0b;">TIBET</strong><br>Shigatse — seat of Panchen Lama; Tashilhunpo Monastery under CCP administration since 1995<br><em>Source: UN Committee on Rights of the Child</em>' },
                    // Hong Kong
                    { name: '🟣 Hong Kong', lat: 22.32, lng: 114.17, color: '#8b5cf6',
                      note: '<strong style="color:#a78bfa;">HONG KONG SAR</strong><br>260+ NSL arrests since 2020 · 5+ media outlets shuttered<br>Electoral system overhauled 2021 — opposition barred<br><em>Source: HRW 2024</em>' },
                ];

                // Render city markers (larger)
                cities.forEach(city => {
                    const icon = L.divIcon({
                        html: `<div style="background:${city.color};width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(0,0,0,0.4);"></div>`,
                        className: '', iconSize: [12, 12], iconAnchor: [6, 6]
                    });
                    L.marker([city.lat, city.lng], { icon })
                        .addTo(map)
                        .bindPopup(`<strong>${city.name}</strong><br><span style="font-size:12px;">${city.note}</span>`);
                });

                // Render humanitarian markers (pulsing diamond shape)
                humanitarianSites.forEach(site => {
                    const icon = L.divIcon({
                        html: `<div style="width:14px;height:14px;background:${site.color};border:2px solid white;transform:rotate(45deg);box-shadow:0 0 8px ${site.color}88;"></div>`,
                        className: '', iconSize: [14, 14], iconAnchor: [7, 7]
                    });
                    L.marker([site.lat, site.lng], { icon })
                        .addTo(map)
                        .bindPopup(`<div style="max-width:220px;font-size:12px;line-height:1.5;">${site.note}</div>`);
                });

                // ── ZONE OVERLAYS ──

                // Xinjiang XUAR boundary (approximate)
                const xinjiangZone = L.polygon([
                    [49.0, 73.5], [49.0, 96.0], [37.0, 96.0], [35.5, 79.0], [37.0, 73.5]
                ], { color: '#dc2626', weight: 1.5, fillColor: '#dc2626', fillOpacity: 0.06, dashArray: '6,4' })
                    .addTo(map);
                xinjiangZone.bindPopup('<strong style="color:#ef4444;">🔴 Xinjiang Uyghur Autonomous Region</strong><br>Est. 1.0–1.8M detained · 380+ facilities (ASPI)<br>Genocide designation by US, UK, Canada & others');

                // Tibet TAR boundary (approximate)
                const tibetZone = L.polygon([
                    [36.5, 78.5], [36.5, 99.5], [26.5, 99.5], [26.5, 78.5]
                ], { color: '#d97706', weight: 1.5, fillColor: '#d97706', fillOpacity: 0.06, dashArray: '6,4' })
                    .addTo(map);
                tibetZone.bindPopup('<strong style="color:#f59e0b;">🟡 Tibet Autonomous Region</strong><br>150+ self-immolations since 2009<br>Foreign access restricted — permit required');

                // South China Sea nine-dash line (approximate)
                const scsZone = L.polygon([
                    [20.0, 109.0], [20.0, 120.0], [10.0, 120.0], [3.0, 112.0], [3.0, 108.0], [10.0, 108.0]
                ], { color: '#ef4444', weight: 1.5, fillColor: '#ef4444', fillOpacity: 0.06, dashArray: '6,4' })
                    .addTo(map);
                scsZone.bindPopup('<strong style="color:#ef4444;">⚠️ Nine-Dash Line Claim</strong><br>Rejected by 2016 UNCLOS tribunal<br>Disputed by Vietnam, Philippines, Malaysia, Brunei');

                // ── MAP LEGEND ──
                const legend = L.control({ position: 'bottomright' });
                legend.onAdd = function() {
                    const div = L.DomUtil.create('div');
                    div.style.cssText = 'background:rgba(0,0,0,0.75);color:white;padding:10px 14px;border-radius:8px;font-size:11px;line-height:1.8;';
                    div.innerHTML =
                        '<div style="font-weight:700;margin-bottom:4px;letter-spacing:1px;font-size:10px;">MAP LEGEND</div>' +
                        '<div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#3b82f6;margin-right:6px;vertical-align:middle;"></span>PLAN Fleet HQ</div>' +
                        '<div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;margin-right:6px;vertical-align:middle;"></span>Capital / Flashpoint</div>' +
                        '<div><span style="display:inline-block;width:10px;height:10px;transform:rotate(45deg);background:#dc2626;margin-right:6px;vertical-align:middle;"></span>🔴 Xinjiang Detention Zone</div>' +
                        '<div><span style="display:inline-block;width:10px;height:10px;transform:rotate(45deg);background:#d97706;margin-right:6px;vertical-align:middle;"></span>🟡 Tibet Repression Zone</div>' +
                        '<div><span style="display:inline-block;width:10px;height:10px;transform:rotate(45deg);background:#8b5cf6;margin-right:6px;vertical-align:middle;"></span>🟣 Hong Kong NSL</div>';
                    return div;
                };
                legend.addTo(map);
            };
            document.head.appendChild(script);
        }


        // Humanitarian data loader
        async function loadHumanitarianData() {
            try {
                const r = await fetch('https://asifah-asia-backend.onrender.com/api/china/humanitarian/summary');
                if (!r.ok) return;
                const data = await r.json();
                if (!data.success) return;

                // Show HR signal bar if alerts exist
                const alerts = data.alerts || [];
                const signalBar = document.getElementById('hrSignalBar');
                if (signalBar && alerts.length > 0) {
                    const colors = ['#6b7280','#3b82f6','#f59e0b','#ef4444'];
                    const level = data.hr_signal_level || 0;
                    signalBar.style.display = 'block';
                    signalBar.style.background = `rgba(${level >= 3 ? '239,68,68' : level >= 2 ? '245,158,11' : '59,130,246'},0.15)`;
                    signalBar.style.border = `1px solid ${colors[level]}44`;
                    signalBar.style.color = colors[level];
                    const cats = [...new Set(alerts.map(a => a.category))];
                    signalBar.innerHTML = `⚠️ <strong>Live HR Signal L${level}:</strong> Active reporting detected — ${cats.join(', ')} · ${data.hr_article_count || 0} articles scanned`;
                }
            } catch(e) {
                console.warn('[Humanitarian] Load failed:', e);
            }
        }

        // Translation system — full page including all new cards
        const translations = {
            en: {
                "pageTitle":            "🇨🇳 CHINA STABILITY INDEX",
                "pageSubtitle":         "Multi-Factor Analysis: PLA Posture, South China Sea, Taiwan Strait Dynamics & Economic Coercion",
                "backLink":             "← Back to Dashboard",
                "themeToggle":          "Theme",
                "lastUpdated":          "Last updated: ",
                "mapTitle":             "China — Strategic & Humanitarian Overview",
                "mapSubtitle":          "Key cities, PLAN fleet HQs, South China Sea flashpoints, Xinjiang detention zones & Tibet.",
                "knowledgeLibraryTitle":"Knowledge Library",
                "recentArticles":       "📰 Recent China & PLA Articles",
                "stabilityIndexTitle":  "🇨🇳 CHINA STABILITY INDEX",
                "econIndicatorsTitle":  "💹 LIVE ECONOMIC INDICATORS",
                "leadershipTitle":      "👥 KEY LEADERSHIP",
                "humanitarianTitle":    "🔴 HUMANITARIAN & HUMAN RIGHTS MONITOR",
                "xinjiangTitle":        "Xinjiang",
                "xinjiangDesc":         "Estimated Uyghur detainees in \"vocational training centers\"",
                "xinjiangCaveat":       "⚠️ China denies independent access to verification",
                "tibetTitle":           "Tibet",
                "tibetDesc":            "Self-immolations in protest since 2009",
                "tibetCaveat":          "⚠️ China controls access — actual count may be higher",
                "hkTitle":              "Hong Kong",
                "hkDesc":               "Arrested under National Security Law since 2020",
                "hkCaveat":             "⚠️ Arrests ongoing; prosecution rate very high under NSL",
                "sourceLabel":          "Source:",
                "dataAsOf":             "Data as of:",
                "annualReportsLabel":   "Annual Reports:",
                "unReportLink":         "🇺🇳 UN OHCHR Report →",
                "tchrdLink":            "🏔️ TCHRD Tibet HR →",
                "hrwHkLink":            "📋 HRW Hong Kong →",
                "yuanLabel":            "Yuan / USD Rate",
                "yuanSubLabel":         "CNY per 1 USD · Higher = weaker yuan",
                "brentLabel":           "Brent Crude",
                "usChinaLabel":         "US-China Tension",
                "usChinaSubLabel":      "Tariffs · Tech decoupling · Sanctions",
                "stabilityLegend":      "100 = Controlled · 0 = Crisis Risk",
                "nav_dashboards":        "Dashboards",
                "nav_rhetoric":          "Regional Rhetoric",
                "nav_china":             "China",
                "nav_africa":            "🌍 Africa",
                "nav_future":            "🔒 Future",
                "hkex_label":            "HKEX Hang Seng",
                "hkex_subtitle":         "Hong Kong equity confidence proxy",
                "hkex_sparkline_label":  "5-day:",
                "nav_asia_pacific":      "🌏 Asia & Pacific",
                "nav_europe":            "🌍 Europe",
                "nav_me":                "🕌 Middle East",
                "nav_wha":               "🌎 W. Hemisphere",
                "nav_military":          "🎖️ Military Tracker",
                "nav_gpi":               "🌐 Global Pressure",
                "nav_commodities":       "🛢️ Commodities",
                "nav_rhetoric_me":       "🕌 Middle East",
                "nav_rhetoric_asia":     "🌏 Asia",
                "nav_rhetoric_europe":   "🌍 Europe",
                "nav_rhetoric_wha":      "🌎 W. Hemisphere",
                "nav_china_rhetoric":    "🇨🇳 China Rhetoric",
                "nav_china_stability":   "🇨🇳 China Stability",
                "nav_here":              "◉ You are here",
                "ww_caution_label":      "⚠️ U.S. State Department — Worldwide Caution",
                "ww_caution_text":       "Following the launch of U.S. combat operations in Iran, Americans worldwide and especially in the Middle East should follow guidance from the nearest U.S. embassy or consulate.",
                "ww_caution_button":     "VIEW CAUTION →",
                "travel_label":          "U.S. State Department — China Travel Advisory",
                "travel_level2":         "LEVEL 2",
                "travel_text":           "<strong style=\"color: #f59e0b;\">Exercise Increased Caution in China</strong> due to arbitrary enforcement of local laws, including exit bans, and the risk of wrongful detentions. U.S. citizens may be detained without access to U.S. consular services.",
                "travel_button":         "VIEW ADVISORY →",
                "rhetoric_banner_title": "📡 China Rhetoric & Coercion Tracker",
                "rhetoric_banner_actors":"Xi/CMC · PLA Operational · MFA/Global Times · TAO · Economic Coercion",
                "open_tracker":          "Open Tracker →",
                "rhetoric_card_title":   "📡 RHETORIC TRACKER",
                "rhetoric_card_subtitle":"Outbound coercion score · Updated every 6h",
                "view_full_rhetoric":    "View Full Rhetoric Analysis →",
                "articles_title":        "📰 Recent China & PLA Articles",
                "footer_methodology_title":"Methodology",
                "footer_methodology_text":"Multi-factor stability assessment integrating PLA posture, South China Sea maritime activity, Taiwan Strait dynamics, economic coercion vectors, and humanitarian indicators (Xinjiang, Tibet, Hong Kong). Rhetoric tracker score (theatre 0-100) drawn from /api/rhetoric/china; humanitarian monitor from china_humanitarian.py. Articles aggregated from rhetoric tracker, deduped by URL.",
                "footer_sources_title":  "Data Sources",
                "footer_sources_text":   "RSS (SCMP, Global Times, Xinhua, Reuters, Nikkei Asia), GDELT (English + Mandarin queries), NewsAPI, Brave Search (tertiary fallback), BlueSky Asia aggregator, Telegram (@PLA_Daily, @ChinaWatcher_Asia). Reddit r/China, r/geopolitics, r/CredibleDefense. AMTI, ACLED, DoD China Reports for background.",
                "footer_contact_title":  "Contact",
                "footer_contact_text":   "Built by Asifah Analytics — <a href=\"https://asifahanalytics.com\" style=\"color:var(--accent);\">asifahanalytics.com</a><br>Inquiries: <a href=\"mailto:asifahanalytics@gmail.com\" style=\"color:var(--accent);\">asifahanalytics@gmail.com</a>",
                "footer_disclaimer":     "<strong>⚠️ DISCLAIMER:</strong> This dashboard provides probability estimates based on open-source intelligence aggregation and algorithmic analysis. It does not constitute intelligence assessments, military advice, or policy recommendations. Stability indicators reflect media signal intensity and should not be interpreted as ground-truth predictions. Always consult authoritative sources for decision-making. Updated every ~12 hours · Not for operational use.",
                "footer_support":        "If you find Asifah Analytics useful and want to support ongoing development, you can ☕ <a href=\"https://www.buymeacoffee.com/asifahanalytics\" target=\"_blank\" style=\"color:var(--accent);\">buy me a coffee</a>",
                "commodityTitle":        "🛢️ Commodity Exposure & Strategic Pressure",
                "commodityLoading":      "⏳ Loading commodity exposure tiles…",
                "commodityFullLink":     "View Full Commodity Dashboard →",
            },
            zh: {
                "pageTitle":            "🇨🇳 中国稳定指数",
                "pageSubtitle":         "多因素分析：解放军态势、南海争端、台湾海峡动态与经济胁迫",
                "backLink":             "← 返回仪表板",
                "themeToggle":          "主题",
                "lastUpdated":          "最后更新：",
                "mapTitle":             "中国 — 战略与人道主义概览",
                "mapSubtitle":          "主要城市、海军舰队司令部、南海争端点、新疆拘留区与西藏",
                "knowledgeLibraryTitle":"知识库",
                "recentArticles":       "📰 最新中国与南海报道",
                "stabilityIndexTitle":  "🇨🇳 中国稳定指数",
                "econIndicatorsTitle":  "💹 实时经济指标",
                "leadershipTitle":      "👥 核心领导层",
                "humanitarianTitle":    "🔴 人道主义与人权监测",
                "xinjiangTitle":        "新疆",
                "xinjiangDesc":         "估计被关押在「职业培训中心」的维吾尔族人",
                "xinjiangCaveat":       "⚠️ 中国否认独立核实",
                "tibetTitle":           "西藏",
                "tibetDesc":            "2009年以来的抗议自焚事件",
                "tibetCaveat":          "⚠️ 中国控制进入权限 — 实际数字可能更高",
                "hkTitle":              "香港",
                "hkDesc":               "2020年以来依《国家安全法》被捕人数",
                "hkCaveat":             "⚠️ 逮捕持续进行；《国安法》起诉率极高",
                "sourceLabel":          "来源：",
                "dataAsOf":             "数据截至：",
                "annualReportsLabel":   "年度报告：",
                "unReportLink":         "🇺🇳 联合国人权事务高专办报告 →",
                "tchrdLink":            "🏔️ 西藏人权与民主促进中心 →",
                "hrwHkLink":            "📋 人权观察 香港 →",
                "yuanLabel":            "人民币 / 美元汇率",
                "yuanSubLabel":         "每1美元兑人民币 · 越高代表人民币越弱",
                "brentLabel":           "布伦特原油",
                "usChinaLabel":         "中美紧张关系",
                "usChinaSubLabel":      "关税 · 技术脱钩 · 制裁",
                "stabilityLegend":      "100 = 稳定 · 0 = 危机风险",
                "nav_dashboards":        "区域仪表盘",
                "nav_rhetoric":          "区域言论",
                "nav_china":             "中国",
                "nav_africa":            "🌍 非洲",
                "nav_future":            "🔒 未来",
                "hkex_label":            "港交所恒生指数",
                "hkex_subtitle":         "香港股市信心代理指标",
                "hkex_sparkline_label":  "5天:",
                "nav_asia_pacific":      "🌏 亚太",
                "nav_europe":            "🌍 欧洲",
                "nav_me":                "🕌 中东",
                "nav_wha":               "🌎 西半球",
                "nav_military":          "🎖️ 军事追踪",
                "nav_gpi":               "🌐 全球压力",
                "nav_commodities":       "🛢️ 大宗商品",
                "nav_rhetoric_me":       "🕌 中东",
                "nav_rhetoric_asia":     "🌏 亚洲",
                "nav_rhetoric_europe":   "🌍 欧洲",
                "nav_rhetoric_wha":      "🌎 西半球",
                "nav_china_rhetoric":    "🇨🇳 中国言论",
                "nav_china_stability":   "🇨🇳 中国稳定",
                "nav_here":              "◉ 当前页面",
                "ww_caution_label":      "⚠️ 美国国务院 — 全球警示",
                "ww_caution_text":       "美国对伊朗发动作战行动后，全球各地特别是中东的美国公民应遵从最近的美国大使馆或领事馆指引。",
                "ww_caution_button":     "查看警示 →",
                "travel_label":          "美国国务院 — 中国旅行警示",
                "travel_level2":         "二级",
                "travel_text":           "<strong style=\"color: #f59e0b;\">在中国加强警惕。</strong> 因当地法律执行随意性，包括出境禁令以及错误拘留风险。美国公民可能在无法获得美国领事服务的情况下被拘留。",
                "travel_button":         "查看公告 →",
                "rhetoric_banner_title": "📡 中国言论与胁迫追踪器",
                "rhetoric_banner_actors":"习近平/中央军委 · 解放军作战 · 外交部/环球时报 · 国台办 · 经济胁迫",
                "open_tracker":          "打开追踪器 →",
                "rhetoric_card_title":   "📡 言论追踪器",
                "rhetoric_card_subtitle":"对外胁迫评分 · 每 6 小时更新",
                "view_full_rhetoric":    "查看完整言论分析 →",
                "articles_title":        "📰 最新中国与解放军报道",
                "footer_methodology_title":"方法论",
                "footer_methodology_text":"多因素稳定性评估，整合解放军态势、南海海上活动、台海动态、经济胁迫向量和人道指标（新疆、西藏、香港）。战区评分（0-100）来自 /api/rhetoric/china；人道监测器来自 china_humanitarian.py。文章从言论追踪器汇总，按 URL 去重。",
                "footer_sources_title":  "数据来源",
                "footer_sources_text":   "RSS（《南华早报》、《环球时报》、新华社、路透社、《日经亚洲》）、GDELT（英语+中文查询）、NewsAPI、Brave Search（第三级备援）、BlueSky 亚洲聚合、Telegram（@PLA_Daily、@ChinaWatcher_Asia）。Reddit r/China、r/geopolitics、r/CredibleDefense。AMTI、ACLED、美国国防部中国报告作为背景。",
                "footer_contact_title":  "联系",
                "footer_contact_text":   "由 Asifah Analytics 构建 — <a href=\"https://asifahanalytics.com\" style=\"color:var(--accent);\">asifahanalytics.com</a><br>咨询：<a href=\"mailto:asifahanalytics@gmail.com\" style=\"color:var(--accent);\">asifahanalytics@gmail.com</a>",
                "footer_disclaimer":     "<strong>⚠️ 免责声明：</strong> 本仪表盘基于开源情报聚合和算法分析提供概率估计，不构成情报评估、军事建议或政策推荐。稳定性指标反映媒体信号强度，不应解读为地面真相预测。决策时请始终参考权威来源。每约 12 小时更新 · 不可用于作战目的。",
                "footer_support":        "如果您觉得 Asifah Analytics 有用并希望支持持续开发，您可以 ☕ <a href=\"https://www.buymeacoffee.com/asifahanalytics\" target=\"_blank\" style=\"color:var(--accent);\">请我喝咖啡</a>",
                "commodityTitle":        "🛢️ 大宗商品风险敞口与战略压力",
                "commodityLoading":      "⏳ 正在加载大宗商品风险敞口图块…",
                "commodityFullLink":     "查看完整大宗商品仪表盘 →",
            },
            ja: {
                "pageTitle":            "🇨🇳 中国安定指数",
                "pageSubtitle":         "多要因分析：PLA態勢、南シナ海、台湾海峡ダイナミクス",
                "backLink":             "← ダッシュボードに戻る",
                "themeToggle":          "テーマ",
                "lastUpdated":          "最終更新：",
                "mapTitle":             "中国 — 戦略・人道的概観",
                "mapSubtitle":          "主要都市、海軍艦隊司令部、南シナ海紛争点、新疆拘留区、チベット",
                "knowledgeLibraryTitle":"ナレッジライブラリ",
                "recentArticles":       "📰 最新の中国・南シナ海記事",
                "stabilityIndexTitle":  "🇨🇳 中国安定指数",
                "econIndicatorsTitle":  "💹 リアルタイム経済指標",
                "leadershipTitle":      "👥 主要指導部",
                "humanitarianTitle":    "🔴 人道・人権モニター",
                "xinjiangTitle":        "新疆",
                "xinjiangDesc":         "「職業訓練センター」に収容されているウイグル人の推定数",
                "xinjiangCaveat":       "⚠️ 中国は独立した検証へのアクセスを否定",
                "tibetTitle":           "チベット",
                "tibetDesc":            "2009年以降の抗議焼身自殺",
                "tibetCaveat":          "⚠️ 中国がアクセスを制限 — 実際の数はより多い可能性あり",
                "hkTitle":              "香港",
                "hkDesc":               "2020年以降の国家安全法による逮捕者数",
                "hkCaveat":             "⚠️ 逮捕継続中；NSLによる起訴率は非常に高い",
                "sourceLabel":          "出典：",
                "dataAsOf":             "データ基準日：",
                "annualReportsLabel":   "年次報告書：",
                "unReportLink":         "🇺🇳 国連人権高等弁務官事務所報告 →",
                "tchrdLink":            "🏔️ チベット人権民主化センター →",
                "hrwHkLink":            "📋 ヒューマン・ライツ・ウォッチ 香港 →",
                "yuanLabel":            "人民元 / 米ドル レート",
                "yuanSubLabel":         "1米ドルあたりの人民元 · 高いほど人民元安",
                "brentLabel":           "ブレント原油",
                "usChinaLabel":         "米中緊張",
                "usChinaSubLabel":      "関税 · 技術デカップリング · 制裁",
                "stabilityLegend":      "100 = 安定 · 0 = 危機リスク",
                "nav_dashboards":        "地域ダッシュボード",
                "nav_rhetoric":          "地域レトリック",
                "nav_china":             "中国",
                "nav_africa":            "🌍 アフリカ",
                "nav_future":            "🔒 将来",
                "hkex_label":            "HKEX ハンセン指数",
                "hkex_subtitle":         "香港株式市場の信頼度指標",
                "hkex_sparkline_label":  "5日間:",
                "nav_asia_pacific":      "🌏 アジア太平洋",
                "nav_europe":            "🌍 欧州",
                "nav_me":                "🕌 中東",
                "nav_wha":               "🌎 西半球",
                "nav_military":          "🎖️ 軍事トラッカー",
                "nav_gpi":               "🌐 グローバル圧力",
                "nav_commodities":       "🛢️ コモディティ",
                "nav_rhetoric_me":       "🕌 中東",
                "nav_rhetoric_asia":     "🌏 アジア",
                "nav_rhetoric_europe":   "🌍 欧州",
                "nav_rhetoric_wha":      "🌎 西半球",
                "nav_china_rhetoric":    "🇨🇳 中国レトリック",
                "nav_china_stability":   "🇨🇳 中国安定",
                "nav_here":              "◉ 現在のページ",
                "ww_caution_label":      "⚠️ 米国務省 — 世界規模の注意喚起",
                "ww_caution_text":       "米国のイラン作戦行動開始を受け、世界中、特に中東にいる米国民は、最寄りの米国大使館・領事館の指示に従ってください。",
                "ww_caution_button":     "注意喚起を見る →",
                "travel_label":          "米国務省 — 中国渡航勧告",
                "travel_level2":         "レベル 2",
                "travel_text":           "<strong style=\"color: #f59e0b;\">中国では警戒を強化してください。</strong> 出国禁止を含む現地法の恣意的執行、不当拘束のリスクがあるため。米国民は米国領事サービスにアクセスできないまま拘束される可能性があります。",
                "travel_button":         "勧告を見る →",
                "rhetoric_banner_title": "📡 中国レトリック・威圧トラッカー",
                "rhetoric_banner_actors":"習近平/中央軍事委員会 · 人民解放軍作戦 · 外交部/環球時報 · 台湾事務弁公室 · 経済的威圧",
                "open_tracker":          "トラッカーを開く →",
                "rhetoric_card_title":   "📡 レトリックトラッカー",
                "rhetoric_card_subtitle":"対外威圧スコア · 6 時間ごと更新",
                "view_full_rhetoric":    "完全なレトリック分析を見る →",
                "articles_title":        "📰 中国・人民解放軍 最新記事",
                "footer_methodology_title":"方法論",
                "footer_methodology_text":"人民解放軍態勢、南シナ海海洋活動、台湾海峡動態、経済的威圧ベクトル、人道指標（新疆・チベット・香港）を統合した多要素安定性評価。戦域スコア（0-100）は /api/rhetoric/china、人道モニターは china_humanitarian.py から取得。記事はレトリックトラッカーから集約し、URL で重複排除。",
                "footer_sources_title":  "データソース",
                "footer_sources_text":   "RSS（サウスチャイナ・モーニング・ポスト、環球時報、新華社、ロイター、日経アジア）、GDELT（英語＋中国語クエリ）、NewsAPI、Brave Search（第三段フォールバック）、BlueSky アジア集約、Telegram（@PLA_Daily、@ChinaWatcher_Asia）。Reddit r/China、r/geopolitics、r/CredibleDefense。AMTI、ACLED、米国防総省中国報告書を背景情報として参照。",
                "footer_contact_title":  "連絡先",
                "footer_contact_text":   "Asifah Analytics 構築 — <a href=\"https://asifahanalytics.com\" style=\"color:var(--accent);\">asifahanalytics.com</a><br>お問い合わせ：<a href=\"mailto:asifahanalytics@gmail.com\" style=\"color:var(--accent);\">asifahanalytics@gmail.com</a>",
                "footer_disclaimer":     "<strong>⚠️ 免責事項：</strong> 本ダッシュボードはオープンソース情報の集約とアルゴリズム分析に基づく確率推定を提供します。情報評価・軍事助言・政策提言を構成するものではありません。安定性指標はメディアのシグナル強度を反映するもので、地上真実の予測として解釈すべきではありません。意思決定には常に権威ある情報源を参照してください。約 12 時間ごとに更新 · 作戦使用は不可。",
                "footer_support":        "Asifah Analytics が役立つと感じ、継続的な開発を支援したい場合は、☕ <a href=\"https://www.buymeacoffee.com/asifahanalytics\" target=\"_blank\" style=\"color:var(--accent);\">コーヒーをご馳走</a>いただけます",
                "commodityTitle":        "🛢️ コモディティ依存度と戦略的圧力",
                "commodityLoading":      "⏳ コモディティ依存度タイルを読み込み中…",
                "commodityFullLink":     "完全なコモディティダッシュボードを見る →",
            },
            ko: {
                "pageTitle":            "🇨🇳 중국 안정 지수",
                "pageSubtitle":         "다요인 분석: PLA 태세, 남중국해, 대만해협 역학",
                "backLink":             "← 대시보드로 돌아가기",
                "themeToggle":          "테마",
                "lastUpdated":          "마지막 업데이트: ",
                "mapTitle":             "중국 — 전략 및 인도주의 개요",
                "mapSubtitle":          "주요 도시, 해군 함대 사령부, 남중국해 분쟁 지점, 신장 구금 지역, 티베트",
                "knowledgeLibraryTitle":"지식 라이브러리",
                "recentArticles":       "📰 최신 중국·남중국해 기사",
                "stabilityIndexTitle":  "🇨🇳 중국 안정 지수",
                "econIndicatorsTitle":  "💹 실시간 경제 지표",
                "leadershipTitle":      "👥 핵심 지도부",
                "humanitarianTitle":    "🔴 인도주의 및 인권 모니터",
                "xinjiangTitle":        "신장",
                "xinjiangDesc":         "\"직업훈련센터\"에 수용된 위구르인 추정 수",
                "xinjiangCaveat":       "⚠️ 중국은 독립적 검증 접근 거부",
                "tibetTitle":           "티베트",
                "tibetDesc":            "2009년 이후 항의 분신자살 건수",
                "tibetCaveat":          "⚠️ 중국이 접근 통제 — 실제 수치는 더 높을 수 있음",
                "hkTitle":              "홍콩",
                "hkDesc":               "2020년 이후 국가보안법 체포자 수",
                "hkCaveat":             "⚠️ 체포 계속; NSL 기소율 매우 높음",
                "sourceLabel":          "출처:",
                "dataAsOf":             "데이터 기준일:",
                "annualReportsLabel":   "연간 보고서:",
                "unReportLink":         "🇺🇳 유엔 인권최고대표사무소 보고서 →",
                "tchrdLink":            "🏔️ 티베트 인권민주화센터 →",
                "hrwHkLink":            "📋 HRW 홍콩 →",
                "yuanLabel":            "위안화 / 미달러 환율",
                "yuanSubLabel":         "1달러당 위안화 · 높을수록 위안화 약세",
                "brentLabel":           "브렌트 원유",
                "usChinaLabel":         "미중 긴장",
                "usChinaSubLabel":      "관세 · 기술 디커플링 · 제재",
                "stabilityLegend":      "100 = 안정 · 0 = 위기 위험",
                "nav_dashboards":        "지역 대시보드",
                "nav_rhetoric":          "지역 레토릭",
                "nav_china":             "중국",
                "nav_africa":            "🌍 아프리카",
                "nav_future":            "🔒 향후",
                "hkex_label":            "HKEX 항셍지수",
                "hkex_subtitle":         "홍콩 주식 신뢰도 지표",
                "hkex_sparkline_label":  "5일:",
                "nav_asia_pacific":      "🌏 아시아 태평양",
                "nav_europe":            "🌍 유럽",
                "nav_me":                "🕌 중동",
                "nav_wha":               "🌎 서반구",
                "nav_military":          "🎖️ 군사 추적기",
                "nav_gpi":               "🌐 글로벌 압력",
                "nav_commodities":       "🛢️ 원자재",
                "nav_rhetoric_me":       "🕌 중동",
                "nav_rhetoric_asia":     "🌏 아시아",
                "nav_rhetoric_europe":   "🌍 유럽",
                "nav_rhetoric_wha":      "🌎 서반구",
                "nav_china_rhetoric":    "🇨🇳 중국 레토릭",
                "nav_china_stability":   "🇨🇳 중국 안정성",
                "nav_here":              "◉ 현재 페이지",
                "ww_caution_label":      "⚠️ 미 국무부 — 전 세계 주의 권고",
                "ww_caution_text":       "미국의 이란 작전 개시에 따라, 전 세계 특히 중동에 있는 미국 시민은 가장 가까운 미국 대사관·영사관의 안내를 따르십시오.",
                "ww_caution_button":     "주의 권고 보기 →",
                "travel_label":          "미 국무부 — 중국 여행 권고",
                "travel_level2":         "레벨 2",
                "travel_text":           "<strong style=\"color: #f59e0b;\">중국에서 주의를 강화하십시오.</strong> 출국 금지 등 현지 법 자의적 시행과 부당 구금 위험으로 인함. 미국 시민은 미국 영사 서비스에 접근하지 못한 채 구금될 수 있습니다.",
                "travel_button":         "권고 보기 →",
                "rhetoric_banner_title": "📡 중국 레토릭·강압 추적기",
                "rhetoric_banner_actors":"시진핑/중앙군사위 · 인민해방군 작전 · 외교부/환구시보 · 대만판공실 · 경제 강압",
                "open_tracker":          "추적기 열기 →",
                "rhetoric_card_title":   "📡 레토릭 추적기",
                "rhetoric_card_subtitle":"대외 강압 점수 · 6시간마다 갱신",
                "view_full_rhetoric":    "전체 레토릭 분석 보기 →",
                "articles_title":        "📰 중국·인민해방군 최신 기사",
                "footer_methodology_title":"방법론",
                "footer_methodology_text":"인민해방군 태세, 남중국해 해상 활동, 대만해협 동학, 경제 강압 벡터, 인도주의 지표(신장·티베트·홍콩)를 통합한 다요인 안정성 평가. 전구 점수(0-100)는 /api/rhetoric/china에서, 인도주의 모니터는 china_humanitarian.py에서 가져옴. 기사는 레토릭 추적기에서 집계해 URL로 중복 제거.",
                "footer_sources_title":  "데이터 출처",
                "footer_sources_text":   "RSS(SCMP, 환구시보, 신화통신, 로이터, 닛케이 아시아), GDELT(영어+중국어 쿼리), NewsAPI, Brave Search(3차 폴백), BlueSky 아시아 집계, Telegram(@PLA_Daily, @ChinaWatcher_Asia). Reddit r/China, r/geopolitics, r/CredibleDefense. AMTI, ACLED, 미 국방부 중국 보고서를 배경으로.",
                "footer_contact_title":  "연락처",
                "footer_contact_text":   "Asifah Analytics 제작 — <a href=\"https://asifahanalytics.com\" style=\"color:var(--accent);\">asifahanalytics.com</a><br>문의: <a href=\"mailto:asifahanalytics@gmail.com\" style=\"color:var(--accent);\">asifahanalytics@gmail.com</a>",
                "footer_disclaimer":     "<strong>⚠️ 면책 조항:</strong> 본 대시보드는 오픈소스 정보 집계와 알고리즘 분석에 기반한 확률 추정을 제공합니다. 정보 평가·군사 자문·정책 권고에 해당하지 않습니다. 안정성 지표는 미디어 시그널 강도를 반영하며, 지상 사실 예측으로 해석해서는 안 됩니다. 의사결정 시 권위 있는 출처를 항상 참조하십시오. 약 12시간마다 갱신 · 작전 용도 사용 불가.",
                "footer_support":        "Asifah Analytics가 유용하다고 느끼시고 지속적 개발을 지원하고 싶으시다면, ☕ <a href=\"https://www.buymeacoffee.com/asifahanalytics\" target=\"_blank\" style=\"color:var(--accent);\">커피 한 잔 사주실 수 있습니다</a>",
                "commodityTitle":        "🛢️ 원자재 노출도 및 전략 압력",
                "commodityLoading":      "⏳ 원자재 노출 타일 로드 중…",
                "commodityFullLink":     "전체 원자재 대시보드 보기 →",
            }
        };

        // ════════════════════════════════════════════════════════════
        // LANGUAGE — canonical Asia i18n pattern (May 8 2026)
        // ════════════════════════════════════════════════════════════
        let currentLang = 'en';
        try {
            const saved = localStorage.getItem('asifah-china-lang');
            if (saved && translations[saved]) currentLang = saved;
        } catch (e) {}

        // ─────────────────────────────────────────────────────────────
        // HKEX SPARKLINE BUILDER (v1.1 May 25 2026 — Chart.js)
        // Renders 5-day Hang Seng intraday/daily series as a small line
        // chart in the economic indicators card. Mirrors TASE pattern.
        // ─────────────────────────────────────────────────────────────
        let hkexChartInstance = null;
        function buildHkexSparkline(sparklineData) {
            try {
                const ctx = document.getElementById('hkexSparkline');
                if (!ctx || !window.Chart) return;
                const values = sparklineData.map(p => p.value);
                const labels = sparklineData.map(p => p.time || '');
                if (hkexChartInstance) { hkexChartInstance.destroy(); }
                // Determine line color: green if last >= first, red if down
                const trendUp = values.length > 1 && values[values.length - 1] >= values[0];
                const lineColor = trendUp ? '#22c55e' : '#ef4444';
                const bgColor = trendUp ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)';
                hkexChartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            borderColor: lineColor,
                            backgroundColor: bgColor,
                            fill: true,
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 0,
                            pointHoverRadius: 3,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false }, tooltip: { enabled: true } },
                        scales: {
                            x: { display: false },
                            y: { display: false, beginAtZero: false }
                        }
                    }
                });
                const cont = document.getElementById('hkexSparklineContainer');
                if (cont) cont.style.display = 'block';
            } catch (e) {
                console.warn('[HKEX] Sparkline build failed:', e);
            }
        }

        function applyTranslations() {
            const t = translations[currentLang] || translations.en;
            // textContent for plain data-i18n
            document.querySelectorAll('[data-i18n]').forEach(element => {
                const key = element.getAttribute('data-i18n');
                if (t[key] === undefined) return;
                if (key === 'lastUpdated' && element.id === 'lastUpdated') {
                    const currentText = element.textContent;
                    if (currentText.includes(':')) {
                        const timestamp = currentText.split(': ').slice(1).join(': ');
                        element.textContent = t[key] + timestamp;
                    } else {
                        element.textContent = t[key] + 'Loading...';
                    }
                } else {
                    element.textContent = t[key];
                }
            });
            // innerHTML for data-i18n-html (allows formatting + links inside translated text)
            document.querySelectorAll('[data-i18n-html]').forEach(element => {
                const key = element.getAttribute('data-i18n-html');
                if (t[key] !== undefined) element.innerHTML = t[key];
            });
            document.documentElement.setAttribute('lang', currentLang);
            if (RTL_LANGS.includes(currentLang)) {
                document.documentElement.setAttribute('dir', 'rtl');
            } else {
                document.documentElement.setAttribute('dir', 'ltr');
            }
        }

        function switchLanguage(lang, button) {
            currentLang = lang;
            try { localStorage.setItem('asifah-china-lang', lang); } catch (e) {}
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            if (button) button.classList.add('active');
            applyTranslations();
        }

        // Apply translations + active lang button on first load
        document.addEventListener('DOMContentLoaded', () => {
            applyTranslations();
            // Mark the correct language button as active
            const labelMap = { en: 'EN', zh: '中文', ja: '日本語', ko: '한국어' };
            document.querySelectorAll('.lang-btn').forEach(b => {
                b.classList.remove('active');
                if (b.textContent === labelMap[currentLang]) b.classList.add('active');
            });
        });

        // ════════════════════════════════════════════════════════════
        // COMMODITY EXPOSURE — Gold Standard v2.0 (May 7, 2026)
        // Mirrors russia.html pattern. Resilient fetch:
        //   1. Try Asia proxy (/api/asia/commodity/china) — fast, cached
        //   2. Fallback to ME backend direct (/api/commodity-pressure/china)
        //   3. Always render: prose + alert banner + tiles + Strategic Linkage
        // Hormuz convergence alert surfaces when iran_hormuz_pressure is active.
        // ════════════════════════════════════════════════════════════
        async function loadCommodity() {
            const COUNTRY_KEY = 'china';
            const ASIA_BACKEND = 'https://asifah-asia-backend.onrender.com';
            const ME_BACKEND   = 'https://asifah-backend.onrender.com';
            const card = document.getElementById('chinaCommodityCard');
            if (!card) return;

            // ── Resilient fetch: Asia proxy first, ME backend fallback ──
            let data = null;
            let usedFallback = false;
            try {
                const r = await fetch(`${ASIA_BACKEND}/api/asia/commodity/${COUNTRY_KEY}`);
                if (!r.ok) throw new Error('Asia proxy HTTP ' + r.status);
                data = await r.json();
                if (!data || data.success === false) throw new Error('Asia proxy returned failure');
            } catch (e) {
                console.warn(`[China Commodity] Asia proxy failed (${e.message}); trying ME backend direct...`);
                try {
                    const r = await fetch(`${ME_BACKEND}/api/commodity-pressure/${COUNTRY_KEY}`);
                    if (!r.ok) throw new Error('ME backend HTTP ' + r.status);
                    data = await r.json();
                    usedFallback = true;
                } catch (e2) {
                    console.warn(`[China Commodity] ME backend fallback also failed:`, e2.message);
                    const proseEl = document.getElementById('commodityProse');
                    if (proseEl) proseEl.textContent = 'Commodity exposure data temporarily unavailable. Please refresh.';
                    return;
                }
            }

            // ── Prose paragraph (uses backend prose if present, else placeholder) ──
            // China's full Strategic Linkage prose lives in static HTML below tiles.
            // This dynamic prose slot is intentionally minimal — backend may populate later.
            const proseEl = document.getElementById('commodityProse');
            if (proseEl) {
                proseEl.textContent = data.prose ||
                    `China tracks ${data.commodity_summaries?.length || 0} strategic commodity exposures — dual-role profile (major importer + major producer). See tiles below for live status; Strategic Linkage at footer for analytical framing.`;
            }

            // ── Adaptive alert banner ──
            const banner = document.getElementById('commodityAlertBanner');
            const alertLevel = (data.alert_level || 'normal').toLowerCase();
            const alertLabels = {
                normal:   '✓ NO ACTIVE COMMODITY PRESSURE',
                elevated: '◐ ELEVATED COMMODITY PRESSURE',
                high:     '▲ HIGH COMMODITY PRESSURE',
                surge:    '🚨 COMMODITY PRESSURE SURGE'
            };
            const pressure = (data.commodity_pressure || 0);
            banner.className = `commodity-alert-banner alert-${alertLevel} show`;
            banner.innerHTML = `
                <strong>${alertLabels[alertLevel] || alertLabels.normal}</strong>
                <span class="ab-meta">Pressure score: ${Number(pressure).toFixed(1)} · ${data.commodity_summaries?.length || 0} exposures tracked${data.has_live_data === false ? ' · awaiting live signals' : ''}</span>
            `;

            // ── Hormuz-China oil convergence alert ──
            // Read from China rhetoric tracker's top_signals (which the interpreter
            // populates with hormuz_china_oil_dependency_active when Iran/Hormuz pressure
            // intersects China's oil import dependency).
            try {
                const rhetoricResp = await fetch(`${ASIA_BACKEND}/api/rhetoric/china`);
                if (rhetoricResp.ok) {
                    const rhetoric = await rhetoricResp.json();
                    const hormuzSig = (rhetoric.top_signals || [])
                        .find(s => s.category === 'hormuz_china_oil_dependency' || s.hormuz_china_oil_dependency_active);
                    const convergenceEl = document.getElementById('commodityConvergenceAlert');
                    const detailEl = document.getElementById('commodityConvergenceAlertDetail');
                    if (hormuzSig && convergenceEl) {
                        const cs = (hormuzSig.convergence_states || {}).hormuz_china_oil_dependency || {};
                        const alertLvl = (cs.alert_level || 'elevated').toUpperCase();
                        const iranScore = cs.iran_score || 0;
                        const iranIrgc = cs.iran_irgc || 0;
                        convergenceEl.classList.add('active');
                        if (detailEl) {
                            detailEl.innerHTML = `Iran posture at <strong>${alertLvl}</strong> (theatre score ${iranScore}, IRGC L${iranIrgc}) × China's ~50% oil import dependency through Strait of Hormuz. Compound energy security risk — watch China MFA "stability" framing, BRI/CPEC investment cadence, RU/Central Asia substitution moves, yuan settlement deals.`;
                        }
                    } else if (convergenceEl) {
                        convergenceEl.classList.remove('active');
                    }
                }
            } catch (e) {
                console.warn('[China Commodity] Convergence read error:', e.message);
            }

            // ── Commodity tiles ──
            const grid = document.getElementById('commodityGrid');
            grid.innerHTML = '';
            (data.commodity_summaries || []).forEach(c => {
                const globalAlert = (c.global_alert_level || 'normal').toLowerCase();
                const role = (c.role || 'consumer').toLowerCase();
                const rankText = c.rank ? `#${c.rank} globally` : '';
                const signalText = c.signal_count > 0 ? `${c.signal_count} signal${c.signal_count !== 1 ? 's' : ''}` : '';

                let sparklineHtml = '';
                let priceHtml = '';
                if (c.sparkline && c.sparkline.spark && c.sparkline.spark.length > 1) {
                    const spark = c.sparkline.spark;
                    const min = Math.min(...spark);
                    const max = Math.max(...spark);
                    const range = max - min || 1;
                    const points = spark.map((v, i) => {
                        const x = (i / (spark.length - 1)) * 100;
                        const y = 100 - ((v - min) / range) * 100;
                        return `${x.toFixed(1)},${y.toFixed(1)}`;
                    }).join(' ');
                    const pctChange = c.sparkline.change_pct_30d || 0;
                    const sparkColor = pctChange >= 0 ? '#22c55e' : '#ef4444';
                    sparklineHtml = `<svg class="commodity-pill-spark" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline fill="none" stroke="${sparkColor}" stroke-width="2" points="${points}"/></svg>`;
                    const priceClass = pctChange >= 0 ? 'price-up' : 'price-down';
                    const arrow = pctChange >= 0 ? '▲' : '▼';
                    priceHtml = `<div class="commodity-pill-price">$${c.sparkline.price?.toFixed(2) || '--'} <span class="${priceClass}">${arrow} ${pctChange.toFixed(2)}% (30d)</span></div>`;
                }

                const tile = document.createElement('a');
                tile.className = 'commodity-pill';
                tile.href = `commodities.html#${c.commodity}`;
                tile.innerHTML = `
                    <div class="commodity-pill-header">
                        <div class="commodity-pill-icon">${c.icon || '📊'}</div>
                        <div style="flex:1;">
                            <div class="commodity-pill-name">${c.name || c.commodity}</div>
                            ${rankText ? `<div class="commodity-pill-rank">${rankText}</div>` : ''}
                        </div>
                    </div>
                    <div class="commodity-pill-row">
                        <span class="commodity-pill-alert commodity-alert-${globalAlert}">${globalAlert}</span>
                        <span class="commodity-pill-role-badge">${role}</span>
                        ${signalText ? `<span class="commodity-pill-signal-count">${signalText}</span>` : ''}
                    </div>
                    ${priceHtml}
                    ${sparklineHtml}
                    ${c.note ? `<div class="commodity-pill-note">${c.note.slice(0, 180)}${c.note.length > 180 ? '…' : ''}</div>` : ''}
                `;
                grid.appendChild(tile);
            });

            // ── Top signals footer ──
            const tsEl = document.getElementById('commodityTopSignals');
            const topSignals = data.top_signals || [];
            if (topSignals.length > 0) {
                const items = topSignals.slice(0, 3).map(s => `
                    <a href="${s.article_url}" target="_blank" rel="noopener">
                        ${s.commodity_icon || '📰'} <strong>${s.commodity_name}:</strong> ${s.article_title}
                        <span class="ts-source">— ${s.source}</span>
                    </a>
                `).join('');
                tsEl.innerHTML = `<div class="ts-title">Top live signals</div>${items}`;
                tsEl.style.display = 'block';
            } else {
                tsEl.style.display = 'none';
            }

            // ── Cache freshness note ──
            const cacheStatus = data.cache_status || (usedFallback ? 'me-direct' : 'unknown');
            const cachedAt = data.proxy_cached_at || data.last_updated;
            let cacheText = '';
            if (cachedAt) {
                const ageMin = Math.floor((Date.now() - new Date(cachedAt).getTime()) / 60000);
                cacheText = `Cache: ${cacheStatus} · ${ageMin < 60 ? ageMin + 'm' : Math.floor(ageMin/60) + 'h ' + (ageMin%60) + 'm'} ago`;
            } else if (usedFallback) {
                cacheText = 'Source: ME backend (Asia proxy unavailable)';
            }
            const cacheEl = document.getElementById('commodityCacheNote');
            if (cacheEl) cacheEl.textContent = cacheText;
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            startLoadingProgress();
            loadRhetoricData();
            loadStabilityData();
            loadHumanitarianData();
            loadCommodity();
            initChinaMap();
            document.getElementById('lastUpdated').textContent =
                'Last updated: ' + new Date().toLocaleString('en-US', {
                    month: 'short', day: 'numeric', year: 'numeric',
                    hour: 'numeric', minute: '2-digit', hour12: true
                });
            loadArticles().then(() => {
                hideLoadingOverlay();
            }).catch(err => {
                console.error('Error loading China data:', err);
                hideLoadingOverlay();
            });
        });
    </script>
</body>
</html>
