<?php
/**
 * ZVER TAJ — Mini App
 * Дар як папка бо zbot.php гузоред.
 */
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
// --- Security headers ---
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Frame-Options: ALLOW-FROM https://web.telegram.org');   // танҳо Telegram метавонад frame кунад
header('Strict-Transport-Security: max-age=31536000; includeSubDomains');
$VER = 'zapp-6.5-audit';
if (isset($_GET['v']) && !ctype_digit((string)$_GET['v'])) {
    header('Content-Type: text/plain; charset=utf-8');
    echo "ZVER APP\nVERSION: $VER\nFILE: " . date('Y-m-d H:i:s', (int)@filemtime(__FILE__)) . "\n";
    exit;
}
$API = 'zbot.php?api=';
?>
<!DOCTYPE html>
<html lang="tg">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>ZVER TAJ</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{
  --bg:#080809; --pane:#101013; --pane2:#17171c; --line:#232329;
  --tx:#f2f2f4; --mut:#77777f;
  --red:#ff2d3d; --red2:#c8101f; --ok:#22c55e; --warn:#f5a524;
  --r:4px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
a,a:visited,a:active,button{color:var(--tx);-webkit-text-fill-color:currentColor;
  text-decoration:none}
.row,.row *,.act,.act *,.way,.way *{-webkit-text-fill-color:currentColor}
svg{display:block;flex:none}
button{font-family:inherit;cursor:pointer}
html,body{margin:0;padding:0;background:var(--bg)}
body{
  color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  padding-bottom:78px;-webkit-font-smoothing:antialiased;
}
.mono{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-variant-numeric:tabular-nums}

/* ---------- HEADER ---------- */
.top{position:sticky;top:0;z-index:40;background:rgba(8,8,9,.92);
     backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.tin{display:flex;align-items:center;gap:12px;padding:13px 16px}
.logo{font-size:16px;font-weight:900;letter-spacing:2.5px}
.logo i{color:var(--red);font-style:normal}
.tbal{margin-left:auto;text-align:right;line-height:1.15}
.tbal .l{font-size:8.5px;color:var(--mut);letter-spacing:1.4px;font-weight:700}
.tbal .v{font-size:15px;font-weight:800}
.tbal .v u{color:var(--red);text-decoration:none;font-size:11px;margin-left:3px}
.iconb{width:34px;height:34px;border:1px solid var(--line);background:var(--pane);
       color:var(--mut);display:grid;place-items:center;border-radius:var(--r)}
.iconb:active{border-color:var(--red);color:var(--red)}

.wrap{padding:16px}
.hd{display:flex;align-items:center;gap:9px;margin:0 0 13px}
.hd b{font-size:10.5px;font-weight:800;letter-spacing:2px;color:var(--mut)}
.hd span{flex:1;height:1px;background:var(--line)}
.hd em{font-style:normal;font-size:10.5px;color:var(--red);font-weight:800}

/* ---------- ACTIONS ---------- */
.live{position:relative;background:linear-gradient(135deg,#141418,#0d0d10);
      border:1px solid var(--line);border-radius:var(--r);padding:0;margin-bottom:12px;
      overflow:hidden}
.live:before{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;
      background:linear-gradient(180deg,var(--ok),var(--red))}
.live .top2{display:flex;align-items:center;gap:11px;padding:13px 15px 12px}
.live .dot{width:8px;height:8px;border-radius:50%;background:var(--ok);flex:none;
      box-shadow:0 0 0 0 rgba(34,197,94,.6);animation:pulse2 2.2s infinite}
@keyframes pulse2{0%{box-shadow:0 0 0 0 rgba(34,197,94,.5)}
                  70%{box-shadow:0 0 0 8px rgba(34,197,94,0)}
                  100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.live .on{display:flex;align-items:baseline;gap:6px}
.live .on b{font-size:16px;font-weight:900;line-height:1}
.live .on span{font-size:9.5px;color:var(--mut);letter-spacing:1.6px;font-weight:800}
.live .sep{width:1px;height:22px;background:var(--line);margin:0 2px}
.live .cnt{display:flex;align-items:baseline;gap:6px;margin-left:auto}
.live .cnt b{font-size:16px;font-weight:900;color:var(--red);line-height:1}
.live .cnt span{font-size:9.5px;color:var(--mut);letter-spacing:1.6px;font-weight:800}
.live .feed{position:relative;height:38px;border-top:1px solid var(--line);
      background:rgba(255,255,255,.015)}
.live .feed div{position:absolute;left:15px;right:15px;top:0;height:38px;
      display:flex;align-items:center;gap:9px;font-size:12px;color:var(--mut);
      opacity:0;transform:translateY(10px);transition:opacity .4s,transform .4s;
      pointer-events:none}
.live .feed div.on{opacity:1;transform:none}
.live .feed .ok{width:18px;height:18px;border-radius:50%;background:rgba(34,197,94,.16);
      color:var(--ok);display:grid;place-items:center;flex:none}
.live .feed .tx{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.live .feed .tx b{color:var(--tx);font-weight:700}
.live .feed .tx em{font-style:normal;color:var(--tx);font-weight:600}
.live .feed .ago{font-size:10px;color:var(--line);flex:none;font-weight:700}
.acts{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:20px}
.act{background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
     padding:14px 13px;display:flex;align-items:center;gap:11px;color:var(--tx);text-align:left}
.act:active{border-color:var(--red)}
.act .ic{color:var(--red)}
.act{color:var(--tx)}
.act b{font-size:12.5px;font-weight:700;display:block;color:var(--tx)}
.act span{font-size:9.5px;color:var(--mut);display:block;margin-top:1px}
.act.full b,.act.full span{color:#fff}
.act.full{grid-column:1/-1;background:linear-gradient(100deg,var(--red2),var(--red));
          border-color:transparent}
.act.full .ic,.act.full span{color:rgba(255,255,255,.82)}

/* ---------- SEARCH ---------- */
.srch{position:relative;margin-bottom:16px}
.srch input{width:100%;background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
     padding:12px 38px 12px 40px;color:var(--tx);font-size:14px;outline:none;font-family:inherit}
.srch input:focus{border-color:var(--red)}
.srch .a{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--mut)}
.srch .b{position:absolute;right:9px;top:50%;transform:translateY(-50%);background:none;
         border:none;color:var(--mut);padding:5px}

/* ---------- GAMES GRID ---------- */
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.gm{background:var(--pane);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;
    animation:up .25s both}
.gm:active{border-color:var(--red)}
.gm .ph{position:relative;width:100%;aspect-ratio:1;background:var(--pane2);overflow:hidden}
.gm .ph img{width:100%;height:100%;object-fit:cover;display:block}
.gm .ph:after{content:'';position:absolute;inset:0;
  background:linear-gradient(180deg,transparent 45%,rgba(8,8,9,.9))}
.gm .nm{padding:7px 8px 9px}
.gm .nm b{font-size:10.5px;font-weight:700;line-height:1.25;display:-webkit-box;
          -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.gm .nm i{font-style:normal;font-size:9px;color:var(--red);font-weight:800;
          display:block;margin-top:3px}
.gm .no{position:absolute;left:0;top:0;background:var(--red);color:#fff;font-size:8px;
        font-weight:900;padding:2px 5px;letter-spacing:.6px}

/* ---------- DETAIL ---------- */
.bk{display:inline-flex;align-items:center;gap:5px;background:none;border:none;
    color:var(--mut);font-size:12px;font-weight:700;padding:0 0 14px;letter-spacing:.5px}
.ghd{display:flex;gap:13px;align-items:center;background:var(--pane);border:1px solid var(--line);
     border-radius:var(--r);padding:13px;margin-bottom:16px}
.ghd img{width:56px;height:56px;object-fit:cover;border-radius:var(--r)}
.ghd b{font-size:15px;font-weight:800;display:block}
.ghd span{font-size:10px;color:var(--mut);letter-spacing:1px;font-weight:700}

.chips{display:flex;gap:7px;overflow-x:auto;padding-bottom:12px;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chip{background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
      padding:9px 13px;font-size:11px;font-weight:800;letter-spacing:.8px;color:var(--mut);
      white-space:nowrap;flex:none;display:flex;align-items:center;gap:6px}
.chip.on{border-color:var(--red);color:var(--red);background:rgba(255,45,61,.08)}
.chip u{text-decoration:none;font-size:9.5px;opacity:.65}
.rgs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px}
.rg{position:relative;background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
    padding:12px 5px;color:var(--tx);text-align:center}
.rg.on{border-color:var(--red);background:rgba(255,45,61,.09)}
.rg i{font-style:normal;font-size:21px;line-height:1;display:block;margin-bottom:5px}
.rg b{font-size:11.5px;font-weight:900;letter-spacing:.9px;display:block;color:var(--tx)}
.rg.on b{color:var(--red)}
.rg u{text-decoration:none;font-size:9px;color:var(--mut);display:block;margin-top:2px;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rg .tk{position:absolute;top:5px;right:5px;color:var(--red)}
.gm .rg2{position:absolute;right:0;bottom:0;background:rgba(8,8,9,.85);color:var(--tx);
         font-size:8px;font-weight:800;padding:2px 5px;letter-spacing:.5px}
.fld{margin-bottom:11px}
.fld label{display:flex;align-items:center;gap:7px;font-size:9.5px;color:var(--mut);
           letter-spacing:1.5px;font-weight:800;margin-bottom:6px}
.hlp{width:16px;height:16px;border-radius:50%;border:1px solid var(--line);background:var(--pane);
     color:var(--mut);font-size:10px;font-weight:900;line-height:1;padding:0;
     display:grid;place-items:center}
.hlp:active{border-color:var(--red);color:var(--red)}
.gd{background:var(--pane2);border-left:2px solid var(--red);border-radius:var(--r);
    padding:12px 13px;margin-bottom:9px}
.gd b{display:block;font-size:12px;font-weight:800;margin-bottom:5px}
.gd div{font-size:12px;color:var(--mut);line-height:1.6}
.gd .num{display:flex;gap:9px;margin-bottom:6px;align-items:flex-start}
.gd .num i{font-style:normal;width:18px;height:18px;border-radius:50%;background:var(--red);
           color:#fff;font-size:10px;font-weight:900;display:grid;place-items:center;flex:none}
.fld input{width:100%;background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
     padding:13px 14px;color:var(--tx);font-size:15px;outline:none;font-family:inherit;
     font-variant-numeric:tabular-nums}
.fld input:focus,.fld select:focus{border-color:var(--red)}
.fld select{width:100%;background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
     padding:13px 14px;color:var(--tx);font-size:15px;outline:none;font-family:inherit;
     -webkit-appearance:none;appearance:none}
.fld .rowi{display:flex;gap:8px}
.fld .rowi input{flex:1}
.fld .cb{background:var(--red);border:none;color:#fff;border-radius:var(--r);padding:0 16px;
         font-size:11px;font-weight:800;letter-spacing:1px;flex:none}
.fld .cb:disabled{opacity:.4}
.fnd{display:flex;align-items:center;gap:11px;background:rgba(34,197,94,.08);
     border:1px solid rgba(34,197,94,.35);border-radius:var(--r);padding:11px 13px;margin-bottom:11px}
.fnd .c{width:30px;height:30px;border-radius:var(--r);background:rgba(34,197,94,.2);color:var(--ok);
        display:grid;place-items:center;flex:none}
.fnd .n{flex:1;min-width:0}
.fnd .n b{display:block;font-size:14px;font-weight:800;overflow:hidden;
          text-overflow:ellipsis;white-space:nowrap}
.fnd .n span{display:block;font-size:10.5px;color:var(--ok);font-weight:600}
.fnd .e{background:none;border:none;color:var(--mut);font-size:10.5px;font-weight:700;flex:none}

/* ---------- PACKS ---------- */
.pk{display:flex;align-items:center;gap:12px;background:var(--pane);border:1px solid var(--line);
    border-radius:var(--r);padding:12px 13px;margin-bottom:8px;animation:up .22s both}
.pk:active{border-color:var(--red)}
.pk.on{border-color:var(--red);background:rgba(255,45,61,.07)}
.pk .n{width:30px;height:30px;border:1px solid var(--line);border-radius:var(--r);
       display:grid;place-items:center;font-size:11px;font-weight:900;color:var(--mut);flex:none}
.pk .pic{width:42px;height:42px;flex:none;display:grid;place-items:center;
         background:var(--bg);border-radius:var(--r);overflow:hidden}
.pk .pic img{width:100%;height:100%;object-fit:contain;display:block}
.pk .pic svg{width:26px;height:26px}
.pk.on .n{background:var(--red);border-color:var(--red);color:#fff}
.pk .t{flex:1;min-width:0}
.pk .t b{font-size:13.5px;font-weight:700;display:block;display:flex;align-items:center;gap:6px}
.pk .t b .pv{font-size:15px;font-weight:800}
.pk .t b .uc{font-size:11px;font-weight:900;color:#f0b429;letter-spacing:.5px}
.pk .t b svg{flex:none}
.pk .t s{font-size:10.5px;color:var(--mut);margin-right:6px}
.pk .p{font-size:15px;font-weight:800;text-align:right;white-space:nowrap}
.pk .p em{font-style:normal;font-size:10px;color:var(--mut);display:block;font-weight:600}

.promo{background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
       padding:13px;margin-top:14px}
.promo .lb{font-size:9.5px;color:var(--mut);letter-spacing:1.5px;font-weight:800;margin-bottom:8px}
.promo .rw{display:flex;gap:8px}
.promo input{flex:1;background:var(--bg);border:1px solid var(--line);border-radius:var(--r);
      padding:12px 13px;color:var(--tx);font-size:14px;outline:none;font-family:inherit;
      text-transform:uppercase;letter-spacing:1px;font-weight:700}
.promo input:focus{border-color:var(--red)}
.promo .go{background:var(--red);border:none;color:#fff;border-radius:var(--r);padding:0 16px;
      font-size:11px;font-weight:800;letter-spacing:1px;flex:none}
.promo .go:disabled{opacity:.4}
.promo.ok{border-color:var(--ok);background:rgba(34,197,94,.06)}
.promo .res{display:flex;align-items:center;gap:9px}
.promo .res .c{width:28px;height:28px;border-radius:var(--r);background:rgba(34,197,94,.2);
      color:var(--ok);display:grid;place-items:center;flex:none}
.promo .res b{flex:1;font-size:13px}
.promo .res .x{background:none;border:none;color:var(--mut);font-size:11px;font-weight:700}
.pk .qb2{display:flex;align-items:center;gap:0;border:1px solid var(--line);
        border-radius:var(--r);overflow:hidden;flex:none}
.pk .qb2 button{width:30px;height:30px;background:var(--bg);border:none;color:var(--tx);
        display:grid;place-items:center;padding:0}
.pk .qb2 button:active{background:var(--red)}
.pk .qb2 .v{min-width:26px;text-align:center;font-size:13px;font-weight:800}
.bar .cx{background:none;border:none;color:var(--mut);font-size:11px;font-weight:700;flex:none}
.qty{display:flex;align-items:center;gap:0;border:1px solid var(--line);border-radius:var(--r);
     overflow:hidden;margin:12px 0 0}
.qty button{width:44px;height:42px;background:var(--pane);border:none;color:var(--tx);
            display:grid;place-items:center}
.qty button:active{background:var(--red)}
.qty .v{flex:1;text-align:center;font-size:16px;font-weight:800}

/* ---------- BUY BAR ---------- */
.bar{position:fixed;left:0;right:0;bottom:62px;z-index:50;background:rgba(8,8,9,.96);
     backdrop-filter:blur(14px);border-top:1px solid var(--line);padding:11px 16px;
     display:flex;align-items:center;gap:12px;animation:up .2s both}
.bar .s{flex:1;line-height:1.2}
.bar .s i{font-style:normal;font-size:9px;color:var(--mut);letter-spacing:1.3px;
          font-weight:800;display:block}
.bar .s b{font-size:18px;font-weight:800}
.btn{background:linear-gradient(100deg,var(--red2),var(--red));color:#fff;border:none;
     border-radius:var(--r);padding:13px 20px;font-size:12.5px;font-weight:800;letter-spacing:1.2px;
     display:inline-flex;align-items:center;justify-content:center;gap:8px;white-space:nowrap}
.btn:active{filter:brightness(.86)}
.btn:disabled{opacity:.35}
.btn.w{width:100%;padding:15px}
.btn.gh{background:var(--pane);border:1px solid var(--line);color:var(--tx)}

/* ---------- ORDERS ---------- */
.or{background:var(--pane);border:1px solid var(--line);border-left:2px solid var(--mut);
    border-radius:var(--r);padding:12px 13px;margin-bottom:8px;animation:up .22s both}
.or.done{border-left-color:var(--ok)}
.or.new{border-left-color:var(--warn)}
.or.refund{border-left-color:#38bdf8}
.or.bad{border-left-color:var(--red)}
.or .r{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.or b{font-size:13px}
.or .m{font-size:10.5px;color:var(--mut);margin-top:3px}
.or .st{font-size:8.5px;font-weight:900;letter-spacing:1.1px;padding:3px 7px;
        border-radius:var(--r);white-space:nowrap}
.st.done{background:rgba(34,197,94,.14);color:var(--ok)}
.st.new{background:rgba(245,165,36,.14);color:var(--warn)}
.st.refund{background:rgba(56,189,248,.14);color:#38bdf8}
.st.bad{background:rgba(255,45,61,.14);color:var(--red)}
.code{background:var(--pane2);border:1px dashed var(--line);border-radius:var(--r);
      padding:9px 11px;margin-top:9px;font-size:13px;font-weight:700;
      user-select:all;-webkit-user-select:all}

/* ---------- ROWS / SETTINGS ---------- */
.card{background:var(--pane);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;
      margin-bottom:13px}
.row{display:flex;align-items:center;gap:12px;padding:14px 14px;border-bottom:1px solid var(--line)}
.row:last-child{border:none}
.row .ic{color:var(--red)}
.row{color:var(--tx)}
.row .t{flex:1;font-size:13.5px;font-weight:600;color:var(--tx)}
.row .v{font-size:12px;color:var(--mut);font-weight:600}
.row .ic{color:var(--red)}
.stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:var(--line)}
.stats div{background:var(--pane);padding:14px 8px;text-align:center}
.stats i{font-style:normal;display:block;font-size:8.5px;color:var(--mut);
         letter-spacing:1.2px;font-weight:800;margin-bottom:5px}
.stats b{font-size:15px;font-weight:800}
.prof{display:flex;align-items:center;gap:13px;padding:16px 14px}
.ava{width:52px;height:52px;border-radius:var(--r);object-fit:cover;
     background:linear-gradient(135deg,var(--red2),var(--red));flex:none}

/* ---------- HISTORY ---------- */
.tx{display:flex;align-items:center;gap:12px;padding:13px 14px;border-bottom:1px solid var(--line)}
.tx:last-child{border:none}
.tx .sg{width:34px;height:34px;border-radius:var(--r);flex:none;display:flex;
        align-items:center;justify-content:center;font-size:17px;font-weight:800}
.tx .sg.p{background:rgba(46,190,120,.14);color:#2EBE78}
.tx .sg.m{background:rgba(255,255,255,.06);color:var(--mut)}
.tx .x{flex:1;min-width:0}
.tx .x b{display:block;font-size:13px;font-weight:700;white-space:nowrap;
         overflow:hidden;text-overflow:ellipsis}
.tx .x i{font-style:normal;display:block;font-size:10.5px;color:var(--mut);margin-top:2px}
.tx .am{text-align:right;flex:none}
.tx .am b{font-size:13.5px;font-weight:800;white-space:nowrap}
.tx .am b.p{color:#2EBE78}
.tx .am i{font-style:normal;display:block;font-size:9.5px;color:var(--mut);margin-top:2px}

/* ---------- SHEET ---------- */
.msk{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:100;display:flex;
     align-items:flex-end;backdrop-filter:blur(2px)}
.sh{background:var(--pane);width:100%;border-top:2px solid var(--red);padding:20px 16px 28px;
    animation:sl .25s cubic-bezier(.2,.9,.3,1);max-height:88vh;overflow-y:auto}
.bhd{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.bhd img{width:46px;height:46px;border-radius:var(--r);object-fit:contain;background:var(--pane2);
         flex:none;padding:4px}
.sh h3{margin:0 0 4px;font-size:15px;font-weight:800;letter-spacing:1.4px}
.sh .sub{font-size:11px;color:var(--mut);margin-bottom:16px}
.amts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}
.amts button{background:var(--pane2);border:1px solid var(--line);border-radius:var(--r);
             padding:13px 4px;font-size:14px;font-weight:800;color:var(--tx)}
.amts button:active{border-color:var(--red);color:var(--red)}
.way{display:flex;align-items:center;gap:12px;background:var(--pane2);border:1px solid var(--line);
     border-radius:var(--r);padding:13px;margin-bottom:8px;width:100%;text-align:left;color:var(--tx)}
.way:active{border-color:var(--red)}
.way .lg{width:44px;height:44px;border-radius:var(--r);display:grid;place-items:center;
         background:var(--bg);color:var(--red);font-weight:900;font-size:13px;flex:none;
         overflow:hidden}
.way .lg img{width:100%;height:100%;object-fit:contain;display:block}
.way .x{flex:1;min-width:0}
.way{color:var(--tx)}
.way .x b{font-size:13.5px;display:block;color:var(--tx)}
.way .x span{font-size:10.5px;color:var(--mut)}
.steps{display:flex;gap:8px;margin-bottom:16px}
.step{flex:1;display:flex;align-items:center;gap:8px;background:var(--pane2);
      border:1px solid var(--line);border-radius:var(--r);padding:9px 10px}
.step.on{border-color:var(--red);background:rgba(255,45,61,.08)}
.step.ok{border-color:var(--ok);background:rgba(34,197,94,.08)}
.step i{width:20px;height:20px;border-radius:50%;background:var(--line);color:var(--tx);
        font-style:normal;font-size:10px;font-weight:900;display:grid;place-items:center;flex:none}
.step.on i{background:var(--red);color:#fff}
.step.ok i{background:var(--ok);color:#fff}
.step b{font-size:10px;font-weight:800;letter-spacing:.7px;color:var(--mut)}
.step.on b{color:var(--tx)}
.det{background:var(--pane2);border:1px solid var(--line);border-radius:var(--r);
     padding:12px 13px;margin-bottom:9px}
.det .k{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:7px}
.det .k i{font-style:normal;font-size:9px;color:var(--mut);letter-spacing:1.3px;font-weight:800}
.det .k u{text-decoration:none;font-size:10px;color:var(--red);font-weight:700;
          max-width:52%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.det .r{display:flex;align-items:center;gap:10px}
.det .r .val{flex:1;font-size:17px;font-weight:800;word-break:break-all;letter-spacing:.4px}
.det.sum .val{color:var(--red);font-size:20px}
.det.cmt{border-color:rgba(245,165,36,.45);background:rgba(245,165,36,.06)}
.det.cmt .val{color:var(--warn);font-size:17px;font-weight:800}
.cp{background:var(--red);border:none;color:#fff;border-radius:var(--r);padding:9px 12px;flex:none}
.cp.ok{background:var(--ok)}

/* ---------- NAV ---------- */
.nav{position:fixed;left:0;right:0;bottom:0;z-index:60;display:flex;
     background:rgba(8,8,9,.97);backdrop-filter:blur(14px);border-top:1px solid var(--line)}
.nav button{flex:1;background:none;border:none;padding:10px 4px 12px;color:var(--mut);
            display:grid;gap:4px;justify-items:center;position:relative}
.nav button.on{color:var(--red)}
.nav button.on:before{content:'';position:absolute;top:0;left:26%;right:26%;height:2px;
                      background:var(--red)}
.nav span{font-size:8.5px;font-weight:800;letter-spacing:1.1px}

.msg{background:var(--pane);border-left:2px solid var(--red);border-radius:var(--r);
     padding:11px 13px;font-size:12.5px;margin-top:10px;display:flex;gap:9px;align-items:center}
.msg.ok{border-left-color:var(--ok)}
.mut{color:var(--mut);font-size:11.5px;line-height:1.5}
.empty{text-align:center;padding:60px 20px;color:var(--mut);font-size:12.5px}
.empty div{color:var(--line);margin-bottom:14px;display:flex;justify-content:center}
.ld{text-align:center;padding:50px;color:var(--mut);font-size:11px;letter-spacing:2px}
.sk{background:var(--pane);border:1px solid var(--line);border-radius:var(--r);
    animation:pl 1.1s infinite}
@keyframes up{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
@keyframes sl{from{transform:translateY(100%)}to{transform:none}}
@keyframes pl{0%,100%{opacity:.4}50%{opacity:.75}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
</style>
</head>
<body>

<div class="top"><div class="tin">
  <div class="logo">Z<i>V</i>ER<i>·</i>TAJ</div>
  <div class="tbal"><div class="l">BALANCE</div><div class="v" id="tb">—</div></div>
  <button class="iconb" id="lb" onclick="langSheet()"></button>
</div></div>

<div id="app" class="wrap"><div class="ld">LOADING</div></div>

<div class="nav">
  <button id="n0" class="on" onclick="go(0)"><i></i><span>SHOP</span></button>
  <button id="n1" onclick="go(1)"><i></i><span>ORDERS</span></button>
  <button id="n2" onclick="go(2)"><i></i><span>PROFILE</span></button>
</div>

<script>
// --- ХАТОҲО НИШОН ДОДА МЕШАВАНД (то ки LOADING беохир нашавад) ---
window.onerror = function (msg, src, line, col) {
  var a = document.getElementById('app');
  if (a) a.innerHTML =
    '<div style="padding:26px 16px;color:#FF5A5A;font:600 12px/1.7 ui-monospace,monospace;'
    + 'word-break:break-word">JS ERROR<br><br>' + String(msg)
    + '<br><br>' + String(src || '').split('/').pop() + ' : ' + line + ':' + col
    + '<br><br><span style="color:#888">ин матнро ба админ фиристед</span></div>';
  return false;
};
window.addEventListener('unhandledrejection', function (e) {
  var a = document.getElementById('app');
  if (a && /LOADING/.test(a.textContent))
    a.innerHTML = '<div style="padding:26px 16px;color:#FF5A5A;font:600 12px/1.7 monospace">'
      + 'PROMISE ERROR<br><br>' + String(e.reason) + '</div>';
});

const TG = window.Telegram?.WebApp;
TG?.ready(); TG?.expand();
try { TG?.setHeaderColor?.('#080809'); TG?.setBackgroundColor?.('#080809'); } catch(e){}

const API = '<?= $API ?>';
const EMPTY_USER = { id:0, name:'', username:null, photo:null, phone:null,
  balance:0, spent:0, orders:0, lang:'tj', ref_link:'', ref_cnt:0, ref_sum:0, ref_bonus:0 };

let S = { user:null, cur:'TJS', shop:'ZVER TAJ', support:'', wa:'', tab:0,
          games:[], detail:null, pick:null, qty:1, orders:[], filter:'all',
          lang:'tj', q:'', vals:{} };

/* ---------------- ICONS ---------------- */
const IC = {
  shop:'<path d="M3 8h18l-1.4 11.2a2 2 0 0 1-2 1.8H6.4a2 2 0 0 1-2-1.8z" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8.5 8V6a3.5 3.5 0 0 1 7 0v2" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  list:'<path d="M4 6h16M4 12h16M4 18h11" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  user:'<circle cx="12" cy="8.5" r="3.6" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4.5 20.5c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  wallet:'<rect x="3" y="6" width="18" height="13" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M16 12h5" stroke="currentColor" stroke-width="1.8"/><circle cx="16.5" cy="12.5" r="1.2" fill="currentColor"/>',
  chat:'<path d="M4 5h16v11H9l-5 4z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
  users:'<circle cx="9" cy="8" r="3.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M3 20c0-3.4 2.7-5.5 6-5.5s6 2.1 6 5.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M16 5.5a3.2 3.2 0 0 1 0 6M18 20c0-2.6-.8-4.3-2-5.2" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  search:'<circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M16 16l4.5 4.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  x:'<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
  back:'<path d="M14 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  chk:'<path d="M5 12.5l4.5 4.5L19 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
  plus:'<path d="M12 6v12M6 12h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  minus:'<path d="M6 12h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  copy:'<rect x="9" y="9" width="11" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M5 15V6a1 1 0 0 1 1-1h8" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  cam:'<path d="M3 8h4l1.5-2h7L17 8h4v11H3z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="12" cy="13" r="3.4" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  glob:'<circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.4 3.6 8.5S14.4 18.1 12 20.5c-2.4-2.4-3.6-5.4-3.6-8.5S9.6 5.9 12 3.5z" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  arr:'<path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  bolt:'<path d="M13 2L4 14h6l-1 8 9-12h-6z" fill="currentColor"/>',
  box:'<path d="M12 2.8l8.5 4v10.4L12 21.2 3.5 17.2V6.8z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M3.5 6.8l8.5 4 8.5-4M12 10.8v10.4" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  share:'<path d="M12 3v12M12 3L8 7M12 3l4 4M5 13v6h14v-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  moon:'<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" fill="currentColor"/>',
  coins:'<ellipse cx="12" cy="7" rx="8" ry="3.2" fill="#f0b429"/><path d="M4 7v5c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2V7" fill="#d99516"/><ellipse cx="12" cy="12" rx="8" ry="3.2" fill="#ffd76e"/><path d="M4 12v4c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2v-4" fill="#d99516"/>',
  ticket:'<path d="M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2.2a2.8 2.8 0 0 0 0 5.6V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2.2a2.8 2.8 0 0 0 0-5.6z" fill="#a78bfa"/>',
  crown:'<path d="M3 8l4 3.2L12 4l5 7.2L21 8l-1.6 10.4H4.6z" fill="#ffd76e"/>',
  gift:'<rect x="3" y="9" width="18" height="12" rx="2" fill="#ff6b9d"/><path d="M2 8h20v4H2z" fill="#e0356f"/><path d="M12 8v13" stroke="#fff" stroke-width="1.8" opacity=".8"/>',
  star:'<path d="M12 3l2.7 5.9 6.3.7-4.7 4.3 1.3 6.3L12 17l-5.6 3.2 1.3-6.3L3 9.6l6.3-.7z" fill="#cfd6ff"/>',
  diamond:'<path d="M6 3h12l4 6-10 12L2 9z" fill="#4ea8ff"/><path d="M6 3l-4 6h20l-4-6z" fill="#8ed0ff"/>',
  refresh:'<path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  wa:'<path d="M12 2.6a9.3 9.3 0 0 0-8 14l-1.3 4.8 4.9-1.3A9.3 9.3 0 1 0 12 2.6z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M9 8.2c.3-.1.6 0 .8.4l.7 1.4c.1.3.1.5-.1.8l-.4.5c-.2.2-.2.4-.1.6.5.9 1.3 1.7 2.2 2.2.2.1.4.1.6-.1l.5-.4c.3-.2.5-.2.8-.1l1.4.7c.4.2.5.5.4.8-.2.8-1 1.4-1.9 1.3-2.8-.3-5.4-2.9-5.7-5.7-.1-.9.5-1.7 1.3-1.9z" fill="currentColor"/>',
};
const ico = (n, s = 20) =>
  `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none">${IC[n] || ''}</svg>`;

/* ---------------- I18N ---------------- */
const T = {
tj:{hist:'ТАЪРИХ',histS:'Ҳамаи амалиёт',histNo:'Ҳанӯз амалиёт нест',histIn:'ДОХИЛ',histOut:'ХАРОҶОТ',kTopup:'Пур кардан',kBuy:'Харид',kRefund:'Баргашт',kRef:'Бонуси дӯст',kAdd:'Илова аз админ',kSub:'Кам аз админ',errSlow:'Интернет суст аст — такрор кунед',errNet:'Алоқа нест',errAlready:'Ин чек аллакай фиристода шуд',errImg:'Расм хонда нашуд',errBig:'Расм хеле калон аст',errRate:'Каме сабр кунед',pendWait:'Шумо аллакай як чек фиристодаед — интизори тасдиқи админ бошед. Баъди ҷавоб метавонед боз фиристед.',okBtn:'Фаҳмидам',queued:'Фармоиш дар навбат аст — ба зудӣ иҷро мешавад',agoNow:'ҳозир',agoM:' дақ',agoH:' соат',agoD:' рӯз',online:'ОНЛАЙН',bought:'ХАРИДААНД',promoL:'РАМЗИ ПРОМО',promoP:'Рамзро ворид кунед',apply:'САНҶИДАН',remove:'Хориҷ',hlpId:'ID-и бозингар',hlpIdT:'ID-ро аз куҷо гирем?',hlpId1:'Бозиро кушоед ва ба профили худ ворид шавед',hlpId2:'Дар боло рақами ID навишта шудааст — онро нусха кунед',hlpId3:'Рақамро дар ин ҷо гузоред ва «Санҷидан» пахш кунед',hlpChk:'Баъди санҷиш номи бозингар нишон дода мешавад — тафтиш кунед!',hlpPay:'Чӣ тавр пардохт кунам?',hlpP1:'Рақами корт ва маблағро нусха кунед',hlpP2:'Ба барномаи бонк гузаред ва пулро фиристед',hlpP3:'Дар шарҳ рақами дархостро нависед — ҳатмӣ!',hlpP4:'Баргардед ва расми чекро фиристед',hlpP5:'Бе шарҳ пулро ёфтан душвор мешавад',cmtWhy:'то пулатон зуд ёфт шавад',nickHint:'Ном метавонад кӯҳна бошад — Garena онро дер нав мекунад. Муҳим ID аст: донат ба ҳамин ҳисоб меояд.',step1:'ПАРДОХТ',step2:'ЧЕК',payNow:'ПАРДОХТ КАРДАН',paid:'МАН ПАРДОХТ КАРДАМ',comment:'ШАРҲ (ҳатмӣ)',sendShot:'Акнун расми чекро фиристед',noChk:'Ин бозӣ санҷиши ID надорад',idOk:'ID қабул шуд — метавонед харед',errTitle:'Хатогӣ рух дод',again:'Аз нав кушоед',gone:'Ин пакет дигар дастрас нест',check:'САНҶИДАН',checking:'Санҷида истодааст',found:'Бозингар',bad:'ID нодуруст аст',change:'Иваз кардан',reg:'Минтақа',shop:'МАҒОЗА',ord:'ФАРМОИШҲО',prof:'ПРОФИЛ',games:'БОЗИҲО',search:'Ҷустуҷӯи бозӣ',
 nofound:'Ёфт нашуд',nogames:'Бозӣ нест',from:'аз',topup:'ПУР КАРДАН',topupS:'Ҳамёнро пур кунед',
 supp:'ДАСТГИРӢ',suppS:'Ба мо нависед',invite:'ДӮСТОН',inviteS:'Бонус гиред',
 pid:'ID-И БОЗИНГАР',srv:'SERVER ID',enter:'Ворид кунед',pack:'ПАКЕТҲО',pick:'Пакетро интихоб кунед',
 buy:'ХАРИДАН',total:'ҲАМАГӢ',qty:'ШУМОРА',back:'Бозгашт',
 all:'Ҳама',new:'Интизор',done:'Иҷро шуд',bad:'Бекор',stRefund:'Пул баргашт',refundBack:'Пул ба ҳамён баргардонида шуд',inProcess:'Дар коркард — ба зудӣ иҷро мешавад',noord:'Фармоиш нест',
 bal:'БАЛАНС',spent:'ХАРОҶОТ',cnt:'ФАРМОИШ',lang:'ЗАБОН',
 need:'Ҳама майдонҳоро пур кунед',nobal:'Баланс нокифоя',
 ok:'Фармоиш қабул шуд! Админ тасдиқ мекунад',
 amount:'МАБЛАҒ',next:'ИДОМА',way:'УСУЛИ ПАРДОХТ',card:'Рақами корт',phone:'Рақами телефон',
 owner:'Соҳиб',payAmt:'МАБЛАҒИ ПАРДОХТ',copy:'Нусха',noreq:'Реквизит нест',
 upl:'РАСМИ ЧЕК',uplBtn:'ИНТИХОБИ РАСМ',uplOk:'Чек фиристода шуд',uplErr:'Хато, такрор кунед',
 sending:'ФИРИСТОДА ИСТОДААМ',refT:'ДАЪВАТИ ДӮСТОН',refS:'Барои ҳар дӯст',
 refC:'ДӮСТОН',refM:'БОНУС',refL:'ЛИНКИ ШУМО',share:'ФИРИСТОДАН',
 code:'КОД',auth:'Барномаро аз бот кушоед',neterr:'Алоқа нест'},
ru:{hist:'ИСТОРИЯ',histS:'Все операции',histNo:'Операций пока нет',histIn:'ПОСТУПИЛО',histOut:'ПОТРАЧЕНО',kTopup:'Пополнение',kBuy:'Покупка',kRefund:'Возврат',kRef:'Бонус за друга',kAdd:'Начислено админом',kSub:'Списано админом',errSlow:'Медленный интернет — попробуйте ещё раз',errNet:'Нет связи',errAlready:'Этот чек уже отправлен',errImg:'Не удалось прочитать фото',errBig:'Фото слишком большое',errRate:'Подождите немного',pendWait:'Вы уже отправили чек — дождитесь ответа админа. После решения можно отправить снова.',okBtn:'Понятно',queued:'Заказ в очереди — скоро выполнится',agoNow:'сейчас',agoM:' мин',agoH:' ч',agoD:' дн',online:'ОНЛАЙН',bought:'ПОКУПОК',promoL:'ПРОМОКОД',promoP:'Введите код',apply:'ПРИМЕНИТЬ',remove:'Убрать',hlpId:'ID игрока',hlpIdT:'Где взять ID?',hlpId1:'Откройте игру и зайдите в свой профиль',hlpId2:'Сверху написан номер ID — скопируйте его',hlpId3:'Вставьте номер сюда и нажмите «Проверить»',hlpChk:'После проверки покажется ник — обязательно сверьте!',hlpPay:'Как оплатить?',hlpP1:'Скопируйте номер карты и сумму',hlpP2:'Перейдите в приложение банка и отправьте деньги',hlpP3:'В комментарии укажите номер заявки — обязательно!',hlpP4:'Вернитесь и отправьте скриншот чека',hlpP5:'Без комментария платёж сложно найти',cmtWhy:'чтобы платёж нашли быстро',nickHint:'Имя может быть старым — Garena обновляет его с задержкой. Главное ID: донат придёт на этот аккаунт.',step1:'ОПЛАТА',step2:'ЧЕК',payNow:'ОПЛАТИТЬ',paid:'Я ОПЛАТИЛ',comment:'КОММЕНТАРИЙ (обязательно)',sendShot:'Теперь отправьте скриншот чека',noChk:'У этой игры нет проверки ID',idOk:'ID принят — можно покупать',errTitle:'Произошла ошибка',again:'Открыть заново',gone:'Этот пакет больше недоступен',check:'ПРОВЕРИТЬ',checking:'Проверяем',found:'Игрок',bad:'Неверный ID',change:'Изменить',reg:'Регион',shop:'МАГАЗИН',ord:'ЗАКАЗЫ',prof:'ПРОФИЛЬ',games:'ИГРЫ',search:'Поиск игры',
 nofound:'Не найдено',nogames:'Игр нет',from:'от',topup:'ПОПОЛНИТЬ',topupS:'Пополните кошелёк',
 supp:'ПОДДЕРЖКА',suppS:'Напишите нам',invite:'ДРУЗЬЯ',inviteS:'Получайте бонус',
 pid:'ID ИГРОКА',srv:'SERVER ID',enter:'Введите',pack:'ПАКЕТЫ',pick:'Выберите пакет',
 buy:'КУПИТЬ',total:'ИТОГО',qty:'КОЛИЧЕСТВО',back:'Назад',
 all:'Все',new:'В ожидании',done:'Выполнен',bad:'Отменён',stRefund:'Деньги возвращены',refundBack:'Деньги вернулись на кошелёк',inProcess:'В обработке — скоро выполнится',noord:'Заказов нет',
 bal:'БАЛАНС',spent:'ПОТРАЧЕНО',cnt:'ЗАКАЗЫ',lang:'ЯЗЫК',
 need:'Заполните все поля',nobal:'Недостаточно средств',
 ok:'Заказ принят! Админ подтвердит',
 amount:'СУММА',next:'ДАЛЕЕ',way:'СПОСОБ ОПЛАТЫ',card:'Номер карты',phone:'Номер телефона',
 owner:'Владелец',payAmt:'СУММА К ОПЛАТЕ',copy:'Копия',noreq:'Реквизитов нет',
 upl:'ФОТО ЧЕКА',uplBtn:'ВЫБРАТЬ ФОТО',uplOk:'Чек отправлен',uplErr:'Ошибка, повторите',
 sending:'ОТПРАВЛЯЕМ',refT:'ПРИГЛАШЕНИЕ ДРУЗЕЙ',refS:'За каждого друга',
 refC:'ДРУЗЬЯ',refM:'БОНУС',refL:'ВАША ССЫЛКА',share:'ОТПРАВИТЬ',
 code:'КОД',auth:'Откройте приложение из бота',neterr:'Нет связи'},
uz:{hist:'TARIX',histS:'Barcha amallar',histNo:'Hozircha amal yoʻq',histIn:'KIRIM',histOut:'CHIQIM',kTopup:'Toʻldirish',kBuy:'Xarid',kRefund:'Qaytarish',kRef:'Doʻst bonusi',kAdd:'Admin qoʻshdi',kSub:'Admin yechdi',errSlow:'Internet sekin — qayta urinib koʻring',errNet:'Aloqa yoʻq',errAlready:'Bu chek allaqachon yuborilgan',errImg:'Rasm oʻqilmadi',errBig:'Rasm juda katta',errRate:'Biroz kuting',pendWait:'Siz allaqachon chek yubordingiz — admin javobini kuting. Javobdan soʻng qayta yuborishingiz mumkin.',okBtn:'Tushundim',queued:'Buyurtma navbatda — tez orada bajariladi',agoNow:'hozir',agoM:' daq',agoH:' soat',agoD:' kun',online:'ONLAYN',bought:'XARID',promoL:'PROMOKOD',promoP:'Kodni kiriting',apply:'QOʻLLASH',remove:'Olib tashlash',hlpId:'Oʻyinchi ID',hlpIdT:'ID qayerdan olinadi?',hlpId1:'Oʻyinni oching va profilingizga kiring',hlpId2:'Yuqorida ID raqami yozilgan — nusxa oling',hlpId3:'Raqamni shu yerga qoʻying va «Tekshirish» bosing',hlpChk:'Tekshiruvdan soʻng ism koʻrsatiladi — tekshiring!',hlpPay:'Qanday toʻlash kerak?',hlpP1:'Karta raqami va summani nusxalang',hlpP2:'Bank ilovasiga oʻting va pul yuboring',hlpP3:'Izohda ariza raqamini yozing — majburiy!',hlpP4:'Qayting va chek rasmini yuboring',hlpP5:'Izohsiz toʻlovni topish qiyin',cmtWhy:'toʻlov tez topilishi uchun',nickHint:'Ism eski bo\'lishi mumkin — Garena uni kech yangilaydi. Asosiysi ID: donat shu hisobga tushadi.',step1:'TO\'LOV',step2:'CHEK',payNow:'TO\'LASH',paid:'MEN TO\'LADIM',comment:'IZOH (majburiy)',sendShot:'Endi chek rasmini yuboring',noChk:'Bu o\'yinda ID tekshiruvi yo\'q',idOk:'ID qabul qilindi — sotib olish mumkin',errTitle:'Xatolik yuz berdi',again:'Qaytadan oching',gone:'Bu paket endi mavjud emas',check:'TEKSHIRISH',checking:'Tekshirilmoqda',found:'O\'yinchi',bad:'ID noto\'g\'ri',change:'O\'zgartirish',reg:'Mintaqa',shop:'DO\'KON',ord:'BUYURTMALAR',prof:'PROFIL',games:'O\'YINLAR',search:'O\'yin qidirish',
 nofound:'Topilmadi',nogames:'O\'yin yo\'q',from:'dan',topup:'TO\'LDIRISH',topupS:'Hamyonni to\'ldiring',
 supp:'YORDAM',suppS:'Bizga yozing',invite:'DO\'STLAR',inviteS:'Bonus oling',
 pid:'O\'YINCHI ID',srv:'SERVER ID',enter:'Kiriting',pack:'PAKETLAR',pick:'Paketni tanlang',
 buy:'SOTIB OLISH',total:'JAMI',qty:'SONI',back:'Orqaga',
 all:'Hammasi',new:'Kutilmoqda',done:'Bajarildi',bad:'Bekor',stRefund:'Pul qaytdi',refundBack:'Pul hamyonga qaytarildi',inProcess:'Ishlanmoqda — tez bajariladi',noord:'Buyurtma yo\'q',
 bal:'BALANS',spent:'SARFLANDI',cnt:'BUYURTMA',lang:'TIL',
 need:'Barcha maydonlarni to\'ldiring',nobal:'Mablag\' yetarli emas',
 ok:'Buyurtma qabul qilindi! Admin tasdiqlaydi',
 amount:'SUMMA',next:'DAVOM',way:'TO\'LOV USULI',card:'Karta raqami',phone:'Telefon raqami',
 owner:'Egasi',payAmt:'TO\'LOV SUMMASI',copy:'Nusxa',noreq:'Rekvizit yo\'q',
 upl:'CHEK RASMI',uplBtn:'RASM TANLASH',uplOk:'Chek yuborildi',uplErr:'Xato, qayta urining',
 sending:'YUBORILMOQDA',refT:'DO\'STLARNI TAKLIF',refS:'Har bir do\'st uchun',
 refC:'DO\'STLAR',refM:'BONUS',refL:'HAVOLANGIZ',share:'YUBORISH',
 code:'KOD',auth:'Ilovani botdan oching',neterr:'Aloqa yo\'q'},
ky:{hist:'ТАРЫХ',histS:'Бардык операциялар',histNo:'Азырынча операция жок',histIn:'КИРИМ',histOut:'ЧЫГЫМ',kTopup:'Толтуруу',kBuy:'Сатып алуу',kRefund:'Кайтаруу',kRef:'Дос бонусу',kAdd:'Админ кошту',kSub:'Админ алды',errSlow:'Интернет жай — кайра аракет кылыңыз',errNet:'Байланыш жок',errAlready:'Бул чек жөнөтүлгөн',errImg:'Сүрөт окулган жок',errBig:'Сүрөт өтө чоң',errRate:'Бир аз күтө туруңуз',pendWait:'Сиз мурдатан чек жибергенсиз — админдин жообун күтүңүз. Жооптон кийин кайра жибере аласыз.',okBtn:'Түшүндүм',queued:'Буйрутма кезекте — жакында аткарылат',agoNow:'азыр',agoM:' мүн',agoH:' саат',agoD:' күн',online:'ОНЛАЙН',bought:'САТЫП АЛУУ',promoL:'ПРОМОКОД',promoP:'Кодду киргизиңиз',apply:'КОЛДОНУУ',remove:'Алып салуу',hlpId:'Оюнчу ID',hlpIdT:'ID кайдан алынат?',hlpId1:'Оюнду ачып, профилиңизге кириңиз',hlpId2:'Жогоруда ID номери жазылган — көчүрүңүз',hlpId3:'Номерди бул жерге коюп, «Текшерүү» басыңыз',hlpChk:'Текшерүүдөн кийин ат көрсөтүлөт — салыштырыңыз!',hlpPay:'Кантип төлөө керек?',hlpP1:'Карта номерин жана сумманы көчүрүңүз',hlpP2:'Банк колдонмосуна өтүп, акча жөнөтүңүз',hlpP3:'Комментарийде арыз номерин жазыңыз — милдеттүү!',hlpP4:'Кайтып келип, чектин сүрөтүн жөнөтүңүз',hlpP5:'Комментарийсиз төлөмдү табуу кыйын',cmtWhy:'төлөм тез табылышы үчүн',nickHint:'Ат эски болушу мүмкүн — Garena аны кечиктирип жаңыртат. Негизгиси ID: донат ушул эсепке келет.',step1:'ТӨЛӨМ',step2:'ЧЕК',payNow:'ТӨЛӨӨ',paid:'МЕН ТӨЛӨДҮМ',comment:'КОММЕНТАРИЙ (милдеттүү)',sendShot:'Эми чектин сүрөтүн жөнөтүңүз',noChk:'Бул оюнда ID текшерүү жок',idOk:'ID кабыл алынды — сатып алса болот',errTitle:'Ката кетти',again:'Кайра ачыңыз',gone:'Бул пакет мындан ары жеткиликсиз',check:'ТЕКШЕРҮҮ',checking:'Текшерилүүдө',found:'Оюнчу',bad:'ID туура эмес',change:'Өзгөртүү',reg:'Аймак',shop:'ДҮКӨН',ord:'БУЙРУТМАЛАР',prof:'ПРОФИЛЬ',games:'ОЮНДАР',search:'Оюн издөө',
 nofound:'Табылган жок',nogames:'Оюн жок',from:'дан',topup:'ТОЛТУРУУ',topupS:'Капчыкты толтуруңуз',
 supp:'КОЛДОО',suppS:'Бизге жазыңыз',invite:'ДОСТОР',inviteS:'Бонус алыңыз',
 pid:'ОЮНЧУ ID',srv:'SERVER ID',enter:'Киргизиңиз',pack:'ПАКЕТТЕР',pick:'Пакетти тандаңыз',
 buy:'САТЫП АЛУУ',total:'ЖАЛПЫ',qty:'САНЫ',back:'Артка',
 all:'Баары',new:'Күтүүдө',done:'Аткарылды',bad:'Жокко чыгарылды',stRefund:'Акча кайтты',refundBack:'Акча капчыкка кайтарылды',inProcess:'Иштелууде — жакында аткарылат',noord:'Буйрутма жок',
 bal:'БАЛАНС',spent:'ЖУМШАЛДЫ',cnt:'БУЙРУТМА',lang:'ТИЛ',
 need:'Бардык талааларды толтуруңуз',nobal:'Каражат жетишсиз',
 ok:'Буйрутма кабыл алынды! Админ ырастайт',
 amount:'СУММА',next:'УЛАНТУУ',way:'ТӨЛӨМ ЫКМАСЫ',card:'Карта номери',phone:'Телефон номери',
 owner:'Ээси',payAmt:'ТӨЛӨМ СУММАСЫ',copy:'Көчүрүү',noreq:'Реквизит жок',
 upl:'ЧЕК СҮРӨТҮ',uplBtn:'СҮРӨТ ТАНДОО',uplOk:'Чек жөнөтүлдү',uplErr:'Ката, кайталаңыз',
 sending:'ЖӨНӨТҮЛҮҮДӨ',refT:'ДОСТОРДУ ЧАКЫРУУ',refS:'Ар бир дос үчүн',
 refC:'ДОСТОР',refM:'БОНУС',refL:'ШИЛТЕМЕҢИЗ',share:'ЖӨНӨТҮҮ',
 code:'КОД',auth:'Колдонмону боттон ачыңыз',neterr:'Байланыш жок'},
en:{hist:'HISTORY',histS:'All transactions',histNo:'No transactions yet',histIn:'IN',histOut:'OUT',kTopup:'Top up',kBuy:'Purchase',kRefund:'Refund',kRef:'Referral bonus',kAdd:'Added by admin',kSub:'Removed by admin',errSlow:'Slow connection — please try again',errNet:'No connection',errAlready:'This receipt was already sent',errImg:'Could not read the image',errBig:'Image is too large',errRate:'Please wait a moment',pendWait:'You already sent a receipt — please wait for the admin to respond. After the decision you can send again.',okBtn:'Got it',queued:'Order queued — will be completed shortly',agoNow:'now',agoM:'m',agoH:'h',agoD:'d',online:'ONLINE',bought:'PURCHASES',promoL:'PROMO CODE',promoP:'Enter code',apply:'APPLY',remove:'Remove',hlpId:'Player ID',hlpIdT:'Where to find your ID?',hlpId1:'Open the game and go to your profile',hlpId2:'Your ID number is shown at the top — copy it',hlpId3:'Paste the number here and tap «Check»',hlpChk:'After the check your nickname appears — please verify it!',hlpPay:'How to pay?',hlpP1:'Copy the card number and the amount',hlpP2:'Open your bank app and send the money',hlpP3:'Put the request number in the comment — required!',hlpP4:'Come back and send the receipt photo',hlpP5:'Without a comment the payment is hard to find',cmtWhy:'so we find your payment fast',nickHint:'The name may be outdated — Garena updates it with a delay. The ID is what matters: the top-up goes to this account.',step1:'PAYMENT',step2:'RECEIPT',payNow:'PAY NOW',paid:'I HAVE PAID',comment:'COMMENT (required)',sendShot:'Now send the receipt photo',noChk:'This game has no ID check',idOk:'ID accepted — you can buy',errTitle:'An error occurred',again:'Reopen',gone:'This package is no longer available',check:'CHECK',checking:'Checking',found:'Player',bad:'Invalid ID',change:'Change',reg:'Region',shop:'SHOP',ord:'ORDERS',prof:'PROFILE',games:'GAMES',search:'Search games',
 nofound:'Not found',nogames:'No games',from:'from',topup:'TOP UP',topupS:'Fund your wallet',
 supp:'SUPPORT',suppS:'Write to us',invite:'FRIENDS',inviteS:'Earn bonus',
 pid:'PLAYER ID',srv:'SERVER ID',enter:'Enter',pack:'PACKAGES',pick:'Select a package',
 buy:'BUY NOW',total:'TOTAL',qty:'QUANTITY',back:'Back',
 all:'All',new:'Pending',done:'Completed',bad:'Cancelled',stRefund:'Refunded',refundBack:'Money returned to wallet',inProcess:'Processing — will complete soon',noord:'No orders',
 bal:'BALANCE',spent:'SPENT',cnt:'ORDERS',lang:'LANGUAGE',
 need:'Fill in all fields',nobal:'Insufficient balance',
 ok:'Order accepted! Admin will confirm',
 amount:'AMOUNT',next:'CONTINUE',way:'PAYMENT METHOD',card:'Card number',phone:'Phone number',
 owner:'Holder',payAmt:'AMOUNT TO PAY',copy:'Copy',noreq:'No payment details',
 upl:'RECEIPT PHOTO',uplBtn:'CHOOSE PHOTO',uplOk:'Receipt sent',uplErr:'Error, try again',
 sending:'SENDING',refT:'INVITE FRIENDS',refS:'Per friend',
 refC:'FRIENDS',refM:'BONUS',refL:'YOUR LINK',share:'SHARE',
 code:'CODE',auth:'Open the app from the bot',neterr:'No connection'},
kk:{hist:'ТАРИХ',histS:'Барлық операциялар',histNo:'Әзірге операция жоқ',histIn:'КІРІС',histOut:'ШЫҒЫС',kTopup:'Толтыру',kBuy:'Сатып алу',kRefund:'Қайтарым',kRef:'Дос бонусы',kAdd:'Админ қосты',kSub:'Админ шешті',errSlow:'Интернет баяу — қайталап көріңіз',errNet:'Байланыс жоқ',errAlready:'Бұл чек жіберілген',errImg:'Сурет оқылмады',errBig:'Сурет тым үлкен',errRate:'Сәл күте тұрыңыз',pendWait:'Сіз әлдеқашан чек жібердіңіз — админнің жауабын күтіңіз. Шешімнен кейін қайта жібере аласыз.',okBtn:'Түсіндім',queued:'Тапсырыс кезекте — жақында орындалады',agoNow:'қазір',agoM:' мин',agoH:' сағ',agoD:' күн',online:'ОНЛАЙН',bought:'САТЫП АЛУ',promoL:'ПРОМОКОД',promoP:'Кодты енгізіңіз',apply:'ҚОЛДАНУ',remove:'Алып тастау',hlpId:'Ойыншы ID',hlpIdT:'ID қайдан алынады?',hlpId1:'Ойынды ашып, профиліңізге кіріңіз',hlpId2:'Жоғарыда ID нөмірі жазылған — көшіріңіз',hlpId3:'Нөмірді осында қойып, «Тексеру» басыңыз',hlpChk:'Тексеруден кейін аты көрсетіледі — салыстырыңыз!',hlpPay:'Қалай төлеу керек?',hlpP1:'Карта нөмірі мен соманы көшіріңіз',hlpP2:'Банк қолданбасына өтіп, ақша жіберіңіз',hlpP3:'Пікірде өтінім нөмірін жазыңыз — міндетті!',hlpP4:'Қайтып келіп, чек фотосын жіберіңіз',hlpP5:'Пікірсіз төлемді табу қиын',cmtWhy:'төлем тез табылуы үшін',nickHint:'Аты ескі болуы мүмкін — Garena оны кешігіп жаңартады. Ең бастысы ID: донат осы тіркелгіге түседі.',step1:'ТӨЛЕМ',step2:'ЧЕК',payNow:'ТӨЛЕУ',paid:'МЕН ТӨЛЕДІМ',comment:'ПІКІР (міндетті)',sendShot:'Енді чек фотосын жіберіңіз',noChk:'Бұл ойында ID тексеру жоқ',idOk:'ID қабылданды — сатып алуға болады',errTitle:'Қате шықты',again:'Қайта ашыңыз',gone:'Бұл пакет енді қолжетімсіз',check:'ТЕКСЕРУ',checking:'Тексерілуде',found:'Ойыншы',bad:'ID қате',change:'Өзгерту',reg:'Аймақ',shop:'ДҮКЕН',ord:'ТАПСЫРЫСТАР',prof:'ПРОФИЛЬ',games:'ОЙЫНДАР',search:'Ойын іздеу',
 nofound:'Табылмады',nogames:'Ойын жоқ',from:'бастап',topup:'ТОЛТЫРУ',topupS:'Әмиянды толтырыңыз',
 supp:'ҚОЛДАУ',suppS:'Бізге жазыңыз',invite:'ДОСТАР',inviteS:'Бонус алыңыз',
 pid:'ОЙЫНШЫ ID',srv:'SERVER ID',enter:'Енгізіңіз',pack:'ПАКЕТТЕР',pick:'Пакетті таңдаңыз',
 buy:'САТЫП АЛУ',total:'БАРЛЫҒЫ',qty:'САНЫ',back:'Артқа',
 all:'Барлығы',new:'Күтуде',done:'Орындалды',bad:'Бас тартылды',stRefund:'Ақша қайтты',refundBack:'Ақша әмиянге қайтарылды',inProcess:'Өңделуде — жақында орындалады',noord:'Тапсырыс жоқ',
 bal:'БАЛАНС',spent:'ЖҰМСАЛДЫ',cnt:'ТАПСЫРЫС',lang:'ТІЛ',
 need:'Барлық өрістерді толтырыңыз',nobal:'Қаражат жеткіліксіз',
 ok:'Тапсырыс қабылданды! Админ растайды',
 amount:'СОМА',next:'ЖАЛҒАСТЫРУ',way:'ТӨЛЕМ ӘДІСІ',card:'Карта нөмірі',phone:'Телефон нөмірі',
 owner:'Иесі',payAmt:'ТӨЛЕМ СОМАСЫ',copy:'Көшіру',noreq:'Деректеме жоқ',
 upl:'ЧЕК ФОТОСЫ',uplBtn:'ФОТО ТАҢДАУ',uplOk:'Чек жіберілді',uplErr:'Қате, қайталаңыз',
 sending:'ЖІБЕРІЛУДЕ',refT:'ДОСТАРДЫ ШАҚЫРУ',refS:'Әр дос үшін',
 refC:'ДОСТАР',refM:'БОНУС',refL:'СІЛТЕМЕҢІЗ',share:'ЖІБЕРУ',
 code:'КОД',auth:'Қолданбаны боттан ашыңыз',neterr:'Байланыс жоқ'},
};
const CAT_ICO = { diamond:'diamond', uc:'coins', coin:'coins', gem:'diamond', star:'star',
                  token:'coins', credit:'wallet', pass:'ticket', pack:'box', sub:'crown',
                  voucher:'gift', main:'star' };

const LN = { tj:'ТҶ', ru:'RU', uz:'UZ', ky:'KG', en:'EN', kk:'KZ' };
const LNAME = { tj:'Тоҷикӣ', ru:'Русский', uz:"O'zbekcha", ky:'Кыргызча', en:'English', kk:'Қазақша' };

/* ---------------- ТАРҶУМАИ НОМИ ПАКЕТҲО ---------------- */
const PT = {
tj:{diamonds:'Алмос',diamond:'Алмос',gems:'Гавҳар',gem:'Гавҳар',coins:'Танга',coin:'Танга',
 gold:'Тилло',tokens:'Жетон',stars:'Ситора',star:'Ситора',credits:'Баланс',
 weekly:'Ҳафтаина',monthly:'Моҳона',daily:'Рӯзона',yearly:'Солона',
 week:'ҳафта',month:'моҳ',day:'рӯз',days:'рӯз',year:'сол',
 lite:'Лайт',light:'Лайт',membership:'Обуна',member:'Обуна',subscription:'Обуна',
 voucher:'Ваучер',pass:'Пропуск',elite:'Элит',royale:'Роял',
 'level up package':'Level Up','level up':'Level Up',level:'Дараҷа',access:'Дастрасӣ',pack:'Набор',bundle:'Набор',
 box:'Қуттӣ',kit:'Набор',set:'Набор',special:'Махсус',premium:'Премиум',
 'gift card':'Корти тӯҳфа',gift:'Тӯҳфа',card:'Корт','top up':'Пур кардан',
 'first purchase':'Хариди аввал',bonus:'Бонус',season:'Мавсим'},
ru:{diamonds:'Алмазы',diamond:'Алмаз',gems:'Кристаллы',gem:'Кристалл',coins:'Монеты',coin:'Монета',
 gold:'Золото',tokens:'Жетоны',stars:'Звёзды',star:'Звезда',credits:'Баланс',
 weekly:'Недельный',monthly:'Месячный',daily:'Дневной',yearly:'Годовой',
 week:'неделя',month:'месяц',day:'день',days:'дней',year:'год',
 lite:'Лайт',light:'Лайт',membership:'Подписка',member:'Подписка',subscription:'Подписка',
 voucher:'Ваучер',pass:'Пропуск',elite:'Элитный',royale:'Рояль',
 'level up package':'Level Up','level up':'Level Up',level:'Уровень',access:'Доступ',pack:'Набор',bundle:'Набор',
 box:'Ящик',kit:'Набор',set:'Набор',special:'Особый',premium:'Премиум',
 'gift card':'Подарочная карта',gift:'Подарок',card:'Карта','top up':'Пополнение',
 'first purchase':'Первая покупка',bonus:'Бонус',season:'Сезон'},
uz:{diamonds:'Olmos',diamond:'Olmos',gems:'Gavhar',gem:'Gavhar',coins:'Tanga',coin:'Tanga',
 gold:'Oltin',tokens:'Token',stars:'Yulduz',star:'Yulduz',credits:'Balans',
 weekly:'Haftalik',monthly:'Oylik',daily:'Kunlik',yearly:'Yillik',
 week:'hafta',month:'oy',day:'kun',days:'kun',year:'yil',
 lite:'Lite',light:'Lite',membership:'Obuna',member:'Obuna',subscription:'Obuna',
 voucher:'Vaucher',pass:'Pass',elite:'Elit',royale:'Royal',
 'level up package':'Level Up','level up':'Level Up',level:'Daraja',access:'Kirish',pack:"To'plam",bundle:"To'plam",
 box:'Quti',kit:"To'plam",set:"To'plam",special:'Maxsus',premium:'Premium',
 'gift card':"Sovg'a kartasi",gift:"Sovg'a",card:'Karta','top up':"To'ldirish",
 'first purchase':'Birinchi xarid',bonus:'Bonus',season:'Mavsum'},
ky:{diamonds:'Алмаз',diamond:'Алмаз',gems:'Асыл таш',gem:'Асыл таш',coins:'Монета',coin:'Монета',
 gold:'Алтын',tokens:'Токен',stars:'Жылдыз',star:'Жылдыз',credits:'Баланс',
 weekly:'Жумалык',monthly:'Айлык',daily:'Күндүк',yearly:'Жылдык',
 week:'жума',month:'ай',day:'күн',days:'күн',year:'жыл',
 lite:'Лайт',light:'Лайт',membership:'Жазылуу',member:'Жазылуу',subscription:'Жазылуу',
 voucher:'Ваучер',pass:'Пропуск',elite:'Элит',royale:'Роял',
 'level up package':'Level Up','level up':'Level Up',level:'Деңгээл',access:'Кирүү',pack:'Топтом',bundle:'Топтом',
 box:'Кутуча',kit:'Топтом',set:'Топтом',special:'Өзгөчө',premium:'Премиум',
 'gift card':'Белек карта',gift:'Белек',card:'Карта','top up':'Толтуруу',
 'first purchase':'Биринчи сатып алуу',bonus:'Бонус',season:'Сезон'},
en:{},
kk:{diamonds:'Алмаз',diamond:'Алмаз',gems:'Кристалл',gem:'Кристалл',coins:'Монета',coin:'Монета',
 gold:'Алтын',tokens:'Токен',stars:'Жұлдыз',star:'Жұлдыз',credits:'Баланс',
 weekly:'Апталық',monthly:'Айлық',daily:'Күндік',yearly:'Жылдық',
 week:'апта',month:'ай',day:'күн',days:'күн',year:'жыл',
 lite:'Лайт',light:'Лайт',membership:'Жазылым',member:'Жазылым',subscription:'Жазылым',
 voucher:'Ваучер',pass:'Пропуск',elite:'Элит',royale:'Роял',
 'level up package':'Level Up','level up':'Level Up',level:'Деңгей',access:'Қатынау',pack:'Жиынтық',bundle:'Жиынтық',
 box:'Қорап',kit:'Жиынтық',set:'Жиынтық',special:'Арнайы',premium:'Премиум',
 'gift card':'Сыйлық картасы',gift:'Сыйлық',card:'Карта','top up':'Толтыру',
 'first purchase':'Алғашқы сатып алу',bonus:'Бонус',season:'Маусым'},
};

/** Номи пакетро тарҷума мекунад */
function tp(name){
  const d = PT[S.lang];
  if (!d || !Object.keys(d).length) return name;
  let out = String(name);
  const done = [];
  // аввал ибораҳои дароз, баъд калимаҳои кӯтоҳ
  const keys = Object.keys(d).sort((a, b) => b.length - a.length);
  for (const k of keys) {
    const rx = new RegExp('\\b' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi');
    out = out.replace(rx, () => {
      done.push(d[k]);
      return '\u0000' + (done.length - 1) + '\u0000';
    });
  }
  out = out.replace(/\u0000(\d+)\u0000/g, (_, i) => done[+i]);
  return out.replace(/\s{2,}/g, ' ').trim();
}

/** Номи файли икона: free-fire-diamond.png */
function slugOf(x){
  return String(x || '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/** Иконаи пакет: расми шумо → SVG */
function packIcon(p){
  const g = (S.detail && S.detail.game) ? S.detail.game : {};
  const cat = p.cat || 'main';
  const names = [];
  const push = v => { const x = slugOf(v); if (x && !names.includes(x)) names.push(x); };

  push(S.grp ? S.grp.name : '');
  push(g.title || '');
  push(g.name || '');
  // "Free Fire (CIS)" → "free-fire"
  push(String(g.name || '').replace(/\s*\(.*?\)\s*/g, ''));

  const paths = [];
  for (const n of names) paths.push(`icons/${n}-${cat}.png`);
  paths.push(`icons/${cat}.png`);

  const svg = ico(CAT_ICO[cat] || 'star', 26);
  return `<div class="pic">
    <img src="${paths[0]}" alt="" loading="lazy"
         data-list="${esc(paths.slice(1).join('|'))}" data-svg="${esc(svg)}"
         onerror="pIconErr(this)">
  </div>`;
}
function pIconErr(el){
  if (!el || el.dataset.done === '1') return;   // такрори onerror-ро пешгирӣ мекунем
  const list = (el.dataset.list || '').split('|').filter(Boolean);
  if (list.length) {
    el.dataset.list = list.slice(1).join('|');
    el.src = list[0];
    return;
  }
  // расмҳо тамом шуданд → SVG-ро мегузорем
  el.dataset.done = '1';
  el.onerror = null;                            // дигар onerror сар намезанад
  const box = el.closest('.pic') || el.parentNode;
  if (box) box.innerHTML = el.dataset.svg || '';
  else el.remove();                             // агар аллакай аз DOM берун бошад
}

/** Fallback барои логои банк — бехатар, бе краши parentNode */
function bankLogoErr(el, txt){
  if (!el || el.dataset.done === '1') return;
  el.dataset.done = '1';
  el.onerror = null;
  const box = el.closest('.lg') || el.parentNode;
  if (box) box.textContent = txt || '?';
  else el.remove();
}

/** Агар пакет "110 Diamonds" бошад — "110 💎" */
function packTitle(p){
  const raw = String(p.name || '');
  const m = raw.match(/^(\\d[\\d\\s.,]*)\\s*(diamonds?|алмаз\\w*)\\b/i);
  if (m && p.cat === 'diamond') return `<span class="pv">${esc(m[1].trim())}</span>`;
  const u = raw.match(/^(\\d[\\d\\s.,]*)\\s*(uc)\\b/i);
  if (u) return `<span class="pv">${esc(u[1].trim())}</span> <b class="uc">UC</b>`;
  return esc(tp(raw));
}

const t = k => (T[S.lang] || T.tj)[k] || k;
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num = v => Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
const money = v => num(v) + ' ' + S.cur;

async function api(m, body = {}, ms = 25000) {
  const c = new AbortController(); const tm = setTimeout(() => c.abort(), ms);
  try {
    const r = await fetch(API + m, { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ ...body, initData: TG?.initData || '' }), signal: c.signal });
    return await r.json();
  } catch (e) { return { ok:false, error: e.name === 'AbortError' ? 'TIMEOUT' : 'NET' }; }
  finally { clearTimeout(tm); }
}
const buzz = k => { try { TG?.HapticFeedback?.impactOccurred(k || 'light'); } catch(e){} };

/* ---------------- START ---------------- */
function skeleton(){
  const b = h => `<div class="sk" style="height:${h}px;margin-bottom:9px"></div>`;
  document.getElementById('app').innerHTML =
    b(56) + b(44) + `<div class="grid">${Array(9).fill(0).map(() =>
      `<div class="sk" style="aspect-ratio:.8"></div>`).join('')}</div>`;
}

let LAST_ERR = '';

(async function(){
 try {
  skeleton();
  let [r, g] = await Promise.all([api('init'), api('games')]);

  // як маротиба такрор мекунем — шояд шабака лаппид
  if (!r.ok && r.error !== 'AUTH') {
    await new Promise(x => setTimeout(x, 900));
    [r, g] = await Promise.all([api('init'), api('games')]);
  }
  LAST_ERR = r.ok ? '' : (String(r.error || '') + (r.detail ? ' · ' + r.detail : ''));
  if (!r.ok && r.error === 'SUB') {
    document.getElementById('app').innerHTML = `
      <div style="padding:30px 6px;text-align:center">
        <div style="color:var(--red);display:flex;justify-content:center">${ico('users', 44)}</div>
        <div style="height:16px"></div>
        <div style="font-size:17px;font-weight:900;letter-spacing:1.4px">${esc(r.title || '')}</div>
        <div style="height:10px"></div>
        <div class="mut" style="font-size:13px">${esc(r.text || '')}</div>
        <div style="height:6px"></div>
        <div class="mut" style="font-size:11.5px">${esc(r.why || '')}</div>
        <div style="height:20px"></div>
        ${(r.channels && r.channels.length
            ? r.channels.map(c => c.link
                ? `<a class="btn w" style="text-decoration:none;margin-bottom:9px"
                     href="${esc(c.link)}" target="_blank">${ico('arr', 16)} ${esc(c.title || '')}</a>`
                : `<div class="btn w" style="opacity:.5;margin-bottom:9px">${esc(c.title || '')}</div>`).join('')
            : (r.channel ? `<a class="btn w" style="text-decoration:none"
                 href="${esc(r.channel)}" target="_blank">${ico('arr', 16)} ${esc(r.go || '')}</a>` : ''))}
        <div style="height:9px"></div>
        <button class="btn gh w" onclick="location.reload()">${ico('chk', 16)} ${esc(r.chk || '')}</button>
      </div>`;
    return;
  }
  if (!r.ok) {
    const code = String(r.error || 'UNKNOWN');
    const msg = code === 'AUTH' ? T.tj.auth
              : code === 'BLOCKED' ? '⛔️' : T.tj.neterr;
    document.getElementById('app').innerHTML =
      `<div class="empty"><div>${ico(code === 'AUTH' ? 'user' : 'refresh', 40)}</div>${msg}
       <div style="height:10px"></div>
       <div class="mono" style="font-size:10px;color:var(--red);padding:0 20px;
            word-break:break-all">${esc(LAST_ERR || code)}</div>
       <div style="height:14px"></div>
       <button class="btn" onclick="location.reload()">${ico('refresh', 16)}</button></div>`;
    return;
  }
  S.user = { ...EMPTY_USER, ...(r.user || {}) };
  S.cur = r.cur || 'TJS'; S.shop = r.shop || 'ZVER TAJ';
  S.support = r.support || ''; S.wa = r.wa || '';
  S.lang = r.user.lang || 'tj';
  if (g.ok) S.games = g.items;
  render();
  loadLive();
  setInterval(loadLive, 60000);
 } catch (e) {
  document.getElementById('app').innerHTML =
    '<div style="padding:26px 16px;color:#FF5A5A;font:600 12px/1.7 monospace;word-break:break-word">'
    + 'START ERROR<br><br>' + String(e && e.message || e)
    + '<br><br><span style="color:#888">' + String(e && e.stack || '').split('\n')[1]
    + '</span></div>';
 }
})();

function idHelp(){
  const g = (S.detail && S.detail.game) ? S.detail.game : {};
  buzz();
  sheet(`<h3>${t('hlpId')}</h3><div class="sub">${esc(g.title || g.name || '')}</div>
    <div class="gd">
      <b>${t('hlpIdT')}</b>
      <div class="num"><i>1</i><span>${t('hlpId1')}</span></div>
      <div class="num"><i>2</i><span>${t('hlpId2')}</span></div>
      <div class="num"><i>3</i><span>${t('hlpId3')}</span></div>
    </div>
    ${g.can_check ? `<div class="msg ok">${ico('chk', 15)} ${t('hlpChk')}</div>` : ''}
    <div style="height:12px"></div>
    <button class="btn w" onclick="document.getElementById('msk').remove()">OK</button>`);
}

function payHelp(){
  buzz();
  sheet(`<h3>${t('hlpPay')}</h3>
    <div class="gd">
      <div class="num"><i>1</i><span>${t('hlpP1')}</span></div>
      <div class="num"><i>2</i><span>${t('hlpP2')}</span></div>
      <div class="num"><i>3</i><span>${t('hlpP3')}</span></div>
      <div class="num"><i>4</i><span>${t('hlpP4')}</span></div>
    </div>
    <div class="msg">${ico('x', 15)} ${t('hlpP5')}</div>
    <div style="height:12px"></div>
    <button class="btn w" onclick="document.getElementById('msk').remove()">OK</button>`);
}

async function showDebug(){
  const box = document.getElementById('app');
  box.innerHTML = '<div class="ld">···</div>';
  const has = !!(TG && TG.initData);
  const r = await api('init');
  box.innerHTML = `<div style="padding:6px">
    <div class="hd"><b>DEBUG</b><span></span></div>
    <div class="card" style="padding:13px;font-size:11px;line-height:1.9" class="mono">
      <div>API · <b>${esc(API)}</b></div>
      <div>initData · <b style="color:${has ? 'var(--ok)' : 'var(--red)'}">
        ${has ? 'ҳаст (' + TG.initData.length + ')' : 'НЕСТ'}</b></div>
      <div>TG version · <b>${esc(TG?.version || '—')}</b></div>
      <div>platform · <b>${esc(TG?.platform || '—')}</b></div>
      <div>icons · <b>${esc(location.href.replace(/[^/]*$/, ''))}icons/</b></div>
      <div style="height:9px"></div>
      <div style="color:var(--mut);word-break:break-all">${esc(JSON.stringify(r).slice(0, 600))}</div>
    </div>
    <button class="btn w" onclick="location.reload()">${ico('refresh', 16)}</button></div>`;
}

function shortGame(x){ return String(x || '').replace(/\s*\(.*?\)\s*/g, '').trim(); }
function shortPack(x){
  const v = String(x || '');
  const m = v.match(/^(\d[\d\s.,]*)\s*(diamonds?|uc)\b/i);
  if (m) return m[1].trim() + (m[2].toLowerCase() === 'uc' ? ' UC' : ' 💎');
  return v.length > 22 ? v.slice(0, 21) + '…' : v;
}
function ago(ts){
  const d = Math.max(0, Math.floor(Date.now() / 1000) - (ts || 0));
  if (d < 90) return t('agoNow');
  if (d < 3600) return Math.floor(d / 60) + t('agoM');
  if (d < 86400) return Math.floor(d / 3600) + t('agoH');
  return Math.floor(d / 86400) + t('agoD');
}

async function loadLive(){
  const r = await api('live');
  if (!r.ok) return;
  S.live = r;
  if (S.tab === 0 && !S.detail) { render(); rotateFeed(); }
}

let FEED_T = null;
function rotateFeed(){
  clearInterval(FEED_T);
  const box = document.getElementById('feed');
  if (!box) return;
  const items = [...box.children];
  if (items.length < 2) return;
  let i = 0;
  FEED_T = setInterval(() => {
    if (!document.getElementById('feed')) { clearInterval(FEED_T); return; }
    items[i].classList.remove('on');
    i = (i + 1) % items.length;
    items[i].classList.add('on');
  }, 3800);
}

function go(i){ S.tab = i; S.detail = null; S.q = ''; buzz(); render(); }

// ҲИМОЯ: агар дар render хато шавад — экрани сафед намешавад,
// балки паём + тугмаи "Аз нав" нишон дода мешавад.
function render(){
  try { renderInner(); }
  catch (e) {
    try {
      const el = document.getElementById('app');
      if (el) el.innerHTML =
        `<div class="msg" style="margin:20px 0">${t('errTitle') || 'Хатогӣ'}</div>
         <button class="btn w" onclick="location.reload()">${t('again') || 'Аз нав'}</button>`;
    } catch (e2) {}
    try { console.error('render:', e); } catch (e3) {}
  }
}

function renderInner(){
  ['shop','list','user'].forEach((n, i) => {
    const b = document.getElementById('n' + i);
    b.classList.toggle('on', S.tab === i);
    b.querySelector('i').innerHTML = ico(n, 19);
    b.querySelector('span').textContent = [t('shop'), t('ord'), t('prof')][i];
  });
  document.getElementById('tb').innerHTML =
    S.user ? `${num(S.user.balance || 0)}<u>${S.cur}</u>` : '—';
  document.getElementById('lb').innerHTML =
    `<b style="font-size:10px;font-weight:900">${LN[S.lang] || 'ТҶ'}</b>`;

  const a = document.getElementById('app');
  if (!S.user) {
    a.innerHTML = `<div class="empty"><div>${ico('refresh', 38)}</div>${t('neterr')}
      <div style="height:10px"></div>
      <div class="mono" style="font-size:11px;color:var(--red)">${esc(LAST_ERR || 'NO_USER')}</div>
      <div style="height:14px"></div>
      <button class="btn" onclick="location.reload()">${ico('refresh', 16)}</button>
      <div style="height:10px"></div>
      <button class="btn gh" onclick="showDebug()" style="font-size:10px">DEBUG</button></div>`;
    return;
  }
  try {
    if (S.detail) a.innerHTML = viewGame();
    else if (S.tab === 0) a.innerHTML = viewShop();
    else if (S.tab === 1) { a.innerHTML = viewOrders(); loadOrders(); }
    else a.innerHTML = viewProfile();
    if (S.tab === 0 && !S.detail && S.live) setTimeout(rotateFeed, 60);
  } catch (e) {
    a.innerHTML = `<div class="empty"><div>${ico('x', 40)}</div>${esc(e.message || e)}</div>`;
  }
}

/* ---------------- SHOP ---------------- */
function viewShop(){
  const q = (S.q || '').trim().toLowerCase();
  const list = q ? S.games.filter(g => g.name.toLowerCase().includes(q)
      || g.regions.some(r => (r.full || '').toLowerCase().includes(q))) : S.games;
  S.list = list;
  const cards = list.length ? list.map((g, i) => `
    <div class="gm" style="animation-delay:${Math.min(i, 11) * 24}ms" onclick="openGroup(${i})">
      <div class="ph">
        ${g.image ? `<img src="${esc(g.image)}" loading="lazy"
           onerror="this.style.display='none'">` : ''}
        ${g.top && !q ? '<div class="no">TOP</div>' : ''}
        ${g.regions.length > 1 ? `<div class="rg2">${g.regions.length} ✦</div>` : ''}
      </div>
      <div class="nm"><b>${esc(g.name)}</b><i>${t('from')} ${num(g.min)}</i></div>
    </div>`).join('')
    : `<div class="empty" style="grid-column:1/-1"><div>${ico('search', 38)}</div>
       ${q ? t('nofound') : t('nogames')}</div>`;

  return `
  ${S.live ? `
    <div class="live">
      <div class="top2">
        <span class="dot"></span>
        <span class="on"><b>${num(S.live.online)}</b><span>${t('online')}</span></span>
        <span class="sep"></span>
        <span class="cnt"><b>${num(S.live.total)}</b><span>${t('bought')}</span></span>
      </div>
      ${(S.live.feed || []).length ? `
      <div class="feed" id="feed">
        ${S.live.feed.map((f, i) => `
          <div class="${i === 0 ? 'on' : ''}">
            <span class="ok">${ico('chk', 11)}</span>
            <span class="tx"><b>${esc(f.n)}</b> · ${esc(shortGame(f.g))}
              <em>${esc(shortPack(f.p))}</em></span>
            <span class="ago">${ago(f.at)}</span>
          </div>`).join('')}
      </div>` : ''}
    </div>` : ''}

  <div class="acts">
    <button class="act full" onclick="topup()">
      <span class="ic">${ico('bolt', 22)}</span>
      <span style="flex:1"><b>${t('topup')}</b><span>${t('topupS')}</span></span>
      ${ico('arr', 17)}
    </button>
    <button class="act" onclick="invite()">
      <span class="ic">${ico('users', 19)}</span>
      <span><b>${t('invite')}</b><span>${t('inviteS')}</span></span>
    </button>
    ${S.wa ? `
    <a class="act" href="${esc(S.wa)}" target="_blank" style="text-decoration:none">
      <span class="ic" style="color:#25D366">${ico('wa', 20)}</span>
      <span><b>WHATSAPP</b><span>${t('suppS')}</span></span>
    </a>` : `
    <button class="act" onclick="support()">
      <span class="ic">${ico('chat', 19)}</span>
      <span><b>${t('supp')}</b><span>${t('suppS')}</span></span>
    </button>`}
  </div>

  <div class="srch">
    <span class="a">${ico('search', 17)}</span>
    <input id="sq" placeholder="${t('search')}" value="${esc(S.q)}"
           oninput="onSearch(this.value)" autocomplete="off">
    ${S.q ? `<button class="b" onclick="onSearch('')">${ico('x', 15)}</button>` : ''}
  </div>

  <div class="hd"><b>${t('games')}</b><span></span><em>${list.length}</em></div>
  <div class="grid">${cards}</div>
  <div style="height:20px"></div>`;
}

let SQ = null;
function onSearch(v){
  S.q = v;
  clearTimeout(SQ);
  SQ = setTimeout(() => {
    const e = document.getElementById('sq'); const p = e ? e.selectionStart : 0;
    render();
    const e2 = document.getElementById('sq');
    if (e2) { e2.focus(); try { e2.setSelectionRange(p, p); } catch(x){} }
  }, 170);
}

/* ---------------- GAME ---------------- */
async function openGroup(i){
  const g = (S.list || S.games)[i];
  if (!g) return;
  S.grp = g;
  const pref = ['CIS', 'RU', 'KZ', 'GLOBAL'];
  let pick = g.regions[0];
  for (const p of pref) {
    const f = g.regions.find(r => r.code === p);
    if (f) { pick = f; break; }
  }
  await openGame(pick.id);
}
async function switchReg(id){
  buzz(); S.pick = null; S.nick = null;
  await openGame(id, true);
}

async function openGame(id, keep){
  buzz();
  S.pick = null; S.qty = 1; S.cart = {}; S.promo = null;
  S.nick = null; S.region = ''; S.chkSupported = false; S.idOk = false; S.idBad = false;
  if (!keep) { S.vals = {}; S.cat = null; }
  document.getElementById('app').innerHTML = '<div class="ld">···</div>';
  const r = await api('game', { id });
  if (!r.ok) { render(); return; }
  S.detail = r;
  S.curId = id;
  const cs = (r.cats || []).map(c => c.key);
  if (!S.cat || !cs.includes(S.cat)) S.cat = cs[0] || 'main';
  render();
}

function viewGame(){
  const g = S.detail.game;
  const cats = S.detail.cats || [];
  const regs = S.detail.regions || [];
  const ps = (S.detail.packs || []).filter(p => cats.length < 2 || p.cat === S.cat);

  const cnt = cartCount();
  const tot = cartTotal();

  const packs = ps.map((p, i) => {
    const q = (S.cart || {})[p.id] || 0;
    return `
    <div class="pk ${q ? 'on' : ''}" style="animation-delay:${Math.min(i, 9) * 20}ms"
         ${q ? '' : `onclick="cartAdd(${p.id},1)"`}>
      ${packIcon(p)}
      <div class="n">${q ? q : (i + 1)}</div>
      <div class="t"><b>${packTitle(p)}</b>
        ${p.tag ? `<s>${esc(p.tag)}</s>` : ''}</div>
      ${q ? `<div class="qb2">
        <button onclick="event.stopPropagation();cartAdd(${p.id},-1)">${ico('minus', 14)}</button>
        <span class="v">${q}</span>
        <button onclick="event.stopPropagation();cartAdd(${p.id},1)">${ico('plus', 14)}</button>
      </div>` : ''}
      <div class="p">${num(p.price * (q || 1))}<em>${S.cur}</em></div>
    </div>`;
  }).join('');

  return `
  <button class="bk" onclick="S.detail=null;S.grp=null;render()">${ico('back', 15)} ${t('back')}</button>

  <div class="ghd">
    ${(S.grp && S.grp.image) || g.image
      ? `<img src="${esc((S.grp && S.grp.image) || g.image)}"
             onerror="this.style.display='none'">` : ''}
    <div><b>${esc(S.grp ? S.grp.name : (g.title || g.name))}</b>
      <span>${(S.detail.packs || []).length} ${t('pack')}</span></div>
  </div>

  ${regs.length > 1 ? `
  <div class="hd"><b>${t('reg')}</b><span></span><em>${regs.length}</em></div>
  <div class="rgs">
    ${regs.map(r => `<button class="rg ${r.id === S.curId ? 'on' : ''}" onclick="switchReg(${r.id})">
        ${r.id === S.curId ? `<span class="tk">${ico('chk', 13)}</span>` : ''}
        <i>${r.flag}</i><b>${esc(r.code)}</b><u>${esc(r.label || r.code)}</u>
      </button>`).join('')}
  </div>` : ''}

  ${S.nick ? `
  <div class="fnd">
    <div class="c">${ico('chk', 17)}</div>
    <div class="n"><b>${esc(S.nick)}</b>
      <span>${esc(Object.values(S.vals || {})[0] || '')}${
        S.region ? ' · ' + esc(String(S.region).toUpperCase()) : ''}</span></div>
    <button class="e" onclick="S.nick=null;render()">${t('change')}</button>
  </div>
  <div class="mut" style="margin:-6px 0 12px;font-size:10.5px;line-height:1.5">
    ${t('nickHint')}
  </div>` : `
  ${(g.fields || []).map((f, fi) => `
    <div class="fld">
      <label>${esc(f.label || f.key)}
        ${fi === 0 ? `<button class="hlp" onclick="idHelp()">?</button>` : ''}</label>
      ${f.type === 'select' && (f.options || []).length ? `
        <select onchange="S.vals['${esc(f.key)}']=this.value;S.nick=null;S.idOk=false;S.idBad=false">
          <option value="">${t('enter')}</option>
          ${(f.options || []).map(o => `<option value="${esc(o.value)}"
            ${(S.vals || {})[f.key] === o.value ? 'selected' : ''}>${esc(o.label || o.value)}</option>`).join('')}
        </select>` : `
        <div class="rowi">
          <input inputmode="${f.type === 'number' ? 'numeric' : 'text'}" placeholder="${t('enter')}"
                 value="${esc((S.vals || {})[f.key] || '')}"
                 oninput="S.vals['${esc(f.key)}']=this.value;S.nick=null;S.idOk=false;S.idBad=false">
          ${(fi === (g.fields.length - 1))
            ? `<button class="cb" id="cbn" onclick="checkId()">${t('check')}</button>` : ''}
        </div>`}
    </div>`).join('')}
  <div id="ce"></div>`}
  ${g.hint ? `<div class="mut" style="margin:-4px 0 12px">${esc(g.hint)}</div>` : ''}

  <div class="hd"><b>${t('pack')}</b><span></span><em>${ps.length}</em></div>
  ${cats.length > 1 ? `
  <div class="chips">
    ${cats.map(c => `<button class="chip ${S.cat === c.key ? 'on' : ''}"
       onclick="S.cat='${c.key}';S.pick=null;buzz();render()">
       ${ico(CAT_ICO[c.key] || 'star', 14)}${esc(c.name)}<u>${c.n}</u></button>`).join('')}
  </div>` : ''}
  ${packs}


  ${cnt ? `
    <div class="promo ${S.promo ? 'ok' : ''}" id="pmbox">
      ${S.promo ? `
        <div class="res">
          <div class="c">${ico('chk', 15)}</div>
          <b>${esc(S.promo.code)} · −${money(S.promo.off)}</b>
          <button class="x" onclick="S.promo=null;render()">${t('remove')}</button>
        </div>` : `
        <div class="lb">${t('promoL')}</div>
        <div class="rw">
          <input id="pmi" placeholder="${t('promoP')}" autocomplete="off"
                 value="${esc(S.pmText || '')}" oninput="S.pmText=this.value">
          <button class="go" id="pmb" onclick="applyPromo()">${t('apply')}</button>
        </div>
        <div id="pmr"></div>`}
    </div>` : ''}

  <div style="height:${cnt ? 126 : 30}px"></div>

  ${cnt ? `
  <div class="bar">
    <div class="s"><i>${t('selected')}: ${cnt} ${t('pcs')}</i>
      ${S.promo ? `<b>${money(Math.max(0, tot - S.promo.off))}
        <s style="font-size:12px;color:var(--mut);font-weight:600;margin-left:6px">
        ${money(tot)}</s></b>` : `<b>${money(tot)}</b>`}</div>
    <button class="cx" onclick="S.cart={};S.promo=null;buzz();render()">${t('clear')}</button>
    <button class="btn" onclick="buy()">${ico('cart', 16)} ${t('buy')}</button>
  </div>` : ''}`;
}

let CHK = false;
async function checkId(){
  if (CHK) return;
  const g = S.detail.game;
  const ce = document.getElementById('ce');
  const f = {};
  for (const x of (g.fields || [])) {
    const v = ((S.vals || {})[x.key] || '').trim();
    if (!v) { if (ce) ce.innerHTML = `<div class="msg">${ico('x', 15)} ${t('need')}</div>`; return; }
    f[x.key] = v;
  }

  CHK = true;
  const b = document.getElementById('cbn');
  if (b) { b.disabled = true; b.textContent = '···'; }
  if (ce) ce.innerHTML = `<div class="msg">${t('checking')}···</div>`;

  let r;
  try { r = await api('check', { game_id: g.id, fields: f }); }
  catch (e) { r = { ok: true, skip: true }; }   // алоқа канд — ID-ро қабул мекунем, харид иҷозат
  CHK = false;
  if (b) { b.disabled = false; b.textContent = t('check'); }

  // 1) ник ёфт шуд — нишон медиҳем
  if (r.ok && r.nick) {
    S.nick = r.nick; S.region = r.region || ''; S.idOk = true; S.idBad = false; S.chkSupported = true;
    buzz('medium'); render(); return;
  }
  // 2) провайдер санҷида наметавонад — ID қабул, харид иҷозат
  if (r.ok && r.skip) {
    S.chkSupported = false; S.nick = null; S.idOk = true; S.idBad = false;
    if (ce) ce.innerHTML = `<div class="msg ok">${ico('chk', 15)} ${t('idOk')}</div>`;
    buzz('medium'); return;
  }
  // 3) ID нодуруст (провайдер гуфт) — харид манъ
  if (!r.ok && (r.error === 'INVALID' || r.error === 'ID_EMPTY')) {
    S.chkSupported = true; S.nick = null; S.idOk = false; S.idBad = true;
    if (ce) ce.innerHTML = `<div class="msg">${ico('x', 15)} ${t('bad')}</div>`;
    return;
  }
  // 4) хатои дигар (сервис лёг, RATE ...) — ID қабул, то клиент дар тупик намонад
  S.chkSupported = false; S.nick = null; S.idOk = true; S.idBad = false;
  if (ce) ce.innerHTML = `<div class="msg ok">${ico('chk', 15)} ${t('idOk')}</div>`;
}

function cartCount(){ return Object.values(S.cart || {}).reduce((a, b) => a + b, 0); }
function cartTotal(){
  if (!S.detail) return 0;
  let t = 0;
  for (const [id, q] of Object.entries(S.cart || {})) {
    const p = (S.detail.packs || []).find(x => x.id === +id);
    if (p) t += p.price * q;
  }
  return Math.round(t * 100) / 100;
}
function cartAdd(id, d){
  S.cart = S.cart || {};
  const cur = S.cart[id] || 0;
  // ФАҚАТ ЯК пакет ҳамзамон: агар пакети дигар интихоб шавад — қаблӣ пок мешавад
  if (d > 0 && cur === 0) S.cart = {};
  const nv = cur + d;
  if (nv <= 0) delete S.cart[id]; else S.cart[id] = Math.min(10, nv);
  S.promo = null;
  buzz(); render();
}

function pickPack(id){
  S.pick = (S.pick === id ? null : id);
  S.qty = 1; S.promo = null;
  buzz(); render();
}
function setQty(d){
  S.qty = Math.max(1, Math.min(10, S.qty + d));
  buzz(); render();
}

async function applyPromo(){
  const sum = cartTotal();
  if (!sum) return;
  const code = (S.pmText || '').trim();
  const box = document.getElementById('pmr');
  const btn = document.getElementById('pmb');
  if (!code) return;
  btn.disabled = true;
  const r = await api('promo', { code, sum });
  btn.disabled = false;
  if (r.ok) {
    S.promo = { code: r.code, off: r.off };
    buzz('medium');
    render();
    return;
  }
  if (box) box.innerHTML = `<div class="msg" style="margin-top:9px">
    ${ico('x', 15)} ${esc(r.msg || r.error || '')}</div>`;
}

async function buy(){
  const g = S.detail.game;
  const cnt = cartCount();
  if (!cnt) return;

  const f = {};
  for (const x of (g.fields || [])) {
    const v = ((S.vals || {})[x.key] || '').trim();
    if (!v) { alert(t('need')); return; }
    f[x.key] = v;
  }
  // Харид манъ — ТАНҲО агар провайдер гуфт "ID нодуруст". Ник набошад — манъ нест.
  if (S.idBad) { alert(t('bad')); return; }
  // Агар санҷиш ҳаст ва ҳанӯз пахш нашуда — як бор мепурсем (то хатои ID-ро пеш аз пул бигирем)
  if (g.can_check && S.chkSupported !== false && !S.nick && !S.idOk) {
    alert(t('check') + ' → ' + (g.id_label || t('pid'))); return;
  }

  let tot = cartTotal();
  if (S.promo) tot = Math.max(0, Math.round((tot - S.promo.off) * 100) / 100);
  const bal = (S.user && S.user.balance) || 0;
  if (bal < tot) { topup(tot - bal); return; }

  const entries = Object.entries(S.cart);
  if (!entries.length) return;
  const [pid, pq] = entries[0];          // ФАҚАТ як пакет
  const pack = (S.detail.packs || []).find(x => x.id === +pid);
  const line = pack ? `${pack.name}${pq > 1 ? ' × ' + pq : ''}` : '';

  if (!confirm(`${line}\n\n${t('total')}: ${money(tot)}`)) return;

  const b = document.querySelector('.bar .btn');
  if (b) { b.disabled = true; b.textContent = t('sending'); }

  const r = await api('buy', { pack_id: +pid, qty: pq, fields: f,
                               promo: S.promo ? S.promo.code : ((S.user && S.user.promo) || '') });
  if (typeof r.balance === 'number') S.user.balance = r.balance;

  if (r.ok) {
    buzz('heavy');
    if (!r.queued) flash();
    alert(r.queued > 0
      ? `${t('queued')}`
      : (r.processing > 0 ? t('inProcess') : t('ok')));
    S.cart = {}; S.promo = null; S.pmText = '';
    if (S.user) S.user.promo = null;
    S.detail = null; S.tab = 1; render();
  } else {
    if (b) { b.disabled = false; b.innerHTML = ico('cart', 16) + ' ' + t('buy'); }
    if (r.error === 'NO_BALANCE') topup((r.need || tot) - bal);
    else if (r.error === 'GONE' || r.error === 'NO_PACK') {
      alert('× ' + t('gone')); openGame(S.curId, true); return;
    } else if (r.error === 'SUB') { location.reload(); return; }
    else alert('× ' + (r.error || ''));
    render();
  }
}

function flash(){
  const d = document.createElement('div');
  d.style.cssText = 'position:fixed;inset:0;z-index:300;pointer-events:none;overflow:hidden';
  for (let i = 0; i < 34; i++) {
    const p = document.createElement('i');
    const c = i % 3 ? '#ff2d3d' : '#ffffff';
    p.style.cssText = `position:absolute;top:-20px;left:${Math.random()*100}%;
      width:${4+Math.random()*4}px;height:${10+Math.random()*10}px;background:${c};
      animation:fl ${1400+Math.random()*900}ms ${Math.random()*300}ms cubic-bezier(.3,.6,.4,1) forwards`;
    d.appendChild(p);
  }
  document.body.appendChild(d);
  setTimeout(() => d.remove(), 2800);
}

/* ---------------- ORDERS ---------------- */
function viewOrders(){
  const F = [['all', t('all')], ['new', t('new')], ['done', t('done')], ['bad', t('bad')]];
  return `<div class="hd"><b>${t('ord')}</b><span></span></div>
  <div style="display:flex;gap:7px;overflow-x:auto;padding-bottom:12px">
    ${F.map(([k, v]) => `<button class="btn ${S.filter === k ? '' : 'gh'}"
      style="padding:9px 14px;font-size:10.5px" onclick="S.filter='${k}';render()">${v}</button>`).join('')}
  </div><div id="ol"><div class="ld">···</div></div>`;
}

const kind = s => s === 'done' ? 'done'
              : (s === 'new' || s === 'wait' || s === 'processing' || s === 'queue') ? 'new'
              : (s === 'refund') ? 'refund'
              : 'bad';

async function loadOrders(){
  const r = await api('orders');
  S.orders = r.ok ? r.items : [];
  if (r.ok && typeof r.balance === 'number') { S.user.balance = r.balance;
    document.getElementById('tb').innerHTML = `${num(r.balance)}<u>${S.cur}</u>`; }
  const el = document.getElementById('ol');
  if (!el) return;
  const list = S.orders.filter(o => S.filter === 'all' || kind(o.status) === S.filter);
  if (!list.length) { el.innerHTML = `<div class="empty"><div>${ico('box', 38)}</div>${t('noord')}</div>`; return; }
  if (list.some(o => kind(o.status) === 'new')) {
    clearTimeout(S.pt); S.pt = setTimeout(() => { if (S.tab === 1 && !S.detail) loadOrders(); }, 8000);
  }
  const L = { done: t('done'), new: t('new'), bad: t('bad'), refund: t('stRefund') };
  el.innerHTML = list.map((o, i) => {
    const k = kind(o.status);
    const d = new Date(o.date * 1000).toLocaleString('ru-RU',
      { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' });
    return `<div class="or ${k}" style="animation-delay:${Math.min(i, 9) * 22}ms">
      <div class="r">
        <div><b>${esc(o.game)}</b>
          <div class="m">${esc(o.pack)}${o.pid ? ' · ID ' + esc(o.pid) : ''}</div>
          <div class="m mono">${d} · ${money(o.sum)} · #${String(o.id).padStart(5, '0')}</div></div>
        <div class="st ${k}">${L[k]}</div>
      </div>
      ${o.code ? `<div class="code mono">${esc(o.code)}</div>` : ''}
      ${k === 'refund' ? `<div class="m" style="margin-top:7px;color:#4ade80">${t('refundBack')} · ${money(o.sum)}</div>` : ''}
      ${k === 'new' ? `<div class="m" style="margin-top:7px;opacity:.7">${t('inProcess')}</div>` : ''}
      ${(o.note && o.note !== 'null' && !/^[\[{]/.test(o.note) && k !== 'refund')
        ? `<div class="m" style="margin-top:7px">${esc(o.note)}</div>` : ''}
    </div>`;
  }).join('');
}

/* ---------------- PROFILE ---------------- */
function viewProfile(){
  const u = S.user || EMPTY_USER;
  return `
  <div class="hd"><b>${t('prof')}</b><span></span></div>
  <div class="card">
    <div class="prof">
      ${u.photo ? `<img class="ava" src="${esc(u.photo)}">` : '<div class="ava"></div>'}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;font-weight:800">${esc(u.name || '')}</div>
        <div class="mut">${esc(u.phone || (u.username ? '@' + u.username : ''))}</div>
        <div class="mut mono" style="font-size:10px">ID ${u.id}</div>
      </div>
    </div>
    <div class="stats">
      <div><i>${t('bal')}</i><b>${num(u.balance)}</b></div>
      <div><i>${t('spent')}</i><b>${num(u.spent)}</b></div>
      <div><i>${t('cnt')}</i><b>${u.orders}</b></div>
    </div>
  </div>

  <button class="btn w" onclick="topup()">${ico('bolt', 17)} ${t('topup')}</button>
  <div style="height:9px"></div>
  <button class="btn gh w" onclick="txHistory()">${ico('list', 17)} ${t('hist')}</button>
  <div style="height:13px"></div>

  <div class="card">
    <button class="row" style="width:100%;background:none;border:none;border-bottom:1px solid var(--line)"
            onclick="langSheet()">
      <span class="ic">${ico('glob', 19)}</span>
      <span class="t" style="text-align:left">${t('lang')}</span>
      <span class="v">${LNAME[S.lang]}</span>
    </button>
    <button class="row" style="width:100%;background:none;border:none;border-bottom:1px solid var(--line)"
            onclick="invite()">
      <span class="ic">${ico('users', 19)}</span>
      <span class="t" style="text-align:left">${t('invite')}</span>
      <span class="v">${u.ref_cnt || 0}</span>
    </button>
    <button class="row" style="width:100%;background:none;border:none;
            ${S.wa ? 'border-bottom:1px solid var(--line)' : ''}" onclick="support()">
      <span class="ic">${ico('chat', 19)}</span>
      <span class="t" style="text-align:left">${t('supp')}</span>
      <span class="v">${ico('arr', 15)}</span>
    </button>
    ${S.wa ? `
    <a class="row" href="${esc(S.wa)}" target="_blank"
       style="text-decoration:none;color:var(--tx)">
      <span class="ic" style="color:#25D366">${ico('wa', 19)}</span>
      <span class="t">WhatsApp</span>
      <span class="v">${ico('arr', 15)}</span>
    </a>` : ''}
  </div>
  <div class="mut" style="text-align:center;padding:10px 0 4px;font-size:9.5px;letter-spacing:1.5px">
    <?= $VER ?> · ${esc(S.shop)}
  </div>
  <div style="height:16px"></div>`;
}

function support(){ if (S.support) TG?.openTelegramLink('https://t.me/' + S.support.replace('@', '')); }

/* ---------------- SHEETS ---------------- */
function sheet(html){
  document.getElementById('msk')?.remove();
  const d = document.createElement('div');
  d.className = 'msk'; d.id = 'msk';
  d.onclick = e => { if (e.target === d) d.remove(); };
  d.innerHTML = `<div class="sh">${html}</div>`;
  document.body.appendChild(d);
}

function langSheet(){
  buzz();
  sheet(`<h3>${t('lang')}</h3><div class="sub">Language / Забон / Тил</div>
    ${Object.keys(LNAME).map(l => `
      <button class="way" onclick="setLang('${l}')">
        <div class="lg" style="${l === S.lang ? 'background:var(--red);color:#fff' : ''}">${LN[l]}</div>
        <div class="x"><b>${LNAME[l]}</b></div>
        ${l === S.lang ? `<span style="color:var(--red)">${ico('chk', 18)}</span>`
                       : `<span style="color:var(--mut)">${ico('arr', 16)}</span>`}
      </button>`).join('')}`);
}
async function setLang(l){
  S.lang = l; buzz('medium');
  document.getElementById('msk')?.remove();
  render();
  await api('lang', { lang: l });
}

function invite(){
  const u = S.user || EMPTY_USER;
  if (!u.ref_link) { alert(t('neterr')); return; }
  buzz();
  sheet(`<h3>${t('refT')}</h3>
    <div class="sub">${t('refS')} — <b style="color:var(--red)">${money(u.ref_bonus)}</b></div>
    <div class="stats" style="margin-bottom:13px">
      <div><i>${t('refC')}</i><b>${u.ref_cnt || 0}</b></div>
      <div><i>${t('refM')}</i><b style="color:var(--red)">${num(u.ref_sum || 0)}</b></div>
      <div><i>${t('bal')}</i><b>${num(u.balance)}</b></div>
    </div>
    <div class="det">
      <div class="k"><i>${t('refL')}</i></div>
      <div class="r"><div class="val" id="rl" style="font-size:12px">${esc(u.ref_link)}</div>
        <button class="cp" onclick="cp('rl',this)">${ico('copy', 15)}</button></div>
    </div>
    <button class="btn w" onclick="shareRef()">${ico('share', 17)} ${t('share')}</button>`);
}
function shareRef(){
  const u = S.user || EMPTY_USER;
  if (!u.ref_link) return;
  TG?.openTelegramLink('https://t.me/share/url?url=' + encodeURIComponent(u.ref_link)
    + '&text=' + encodeURIComponent(S.shop));
}

/* ---------------- ТАЪРИХИ ҲАМЁН / ИСТОРИЯ ---------------- */
const KIND = { topup:'kTopup', buy:'kBuy', refund:'kRefund', ref:'kRef',
               admin_add:'kAdd', admin_sub:'kSub' };

function fdate(ts){
  const d = new Date((ts || 0) * 1000);
  const p = n => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

async function txHistory(){
  buzz();
  sheet(`<h3>${t('hist')}</h3><div class="sub">${t('histS')}</div>
    <div class="msg" id="hl">${t('checking')}...</div>`);

  const r = await api('history', { limit: 60 });
  const box = document.getElementById('hl');
  if (!box) return;

  if (!r.ok) { box.textContent = t('neterr'); return; }

  if (!r.items || !r.items.length) {
    box.outerHTML = `<div class="msg">${t('histNo')}</div>
      <button class="btn w" onclick="topup()">${ico('bolt', 17)} ${t('topup')}</button>`;
    return;
  }

  box.outerHTML = `
    <div class="stats" style="margin-bottom:13px">
      <div><i>${t('histIn')}</i><b style="color:#2EBE78">+${num(r.in)}</b></div>
      <div><i>${t('histOut')}</i><b>−${num(r.out)}</b></div>
      <div><i>${t('bal')}</i><b>${num(r.balance)}</b></div>
    </div>
    <div class="card">
      ${r.items.map(x => {
        const p = x.sum >= 0;
        return `<div class="tx">
          <div class="sg ${p ? 'p' : 'm'}">${p ? '+' : '−'}</div>
          <div class="x">
            <b>${esc(x.title || t(KIND[x.kind] || 'kBuy'))}</b>
            <i>${t(KIND[x.kind] || 'kBuy')} · ${fdate(x.date)}</i>
          </div>
          <div class="am">
            <b class="${p ? 'p' : ''}">${p ? '+' : '−'}${num(Math.abs(x.sum))}</b>
            <i>${num(x.bal)} ${esc(S.cur)}</i>
          </div>
        </div>`;
      }).join('')}
    </div>`;
}

/* ---------------- TOPUP ---------------- */
let TA = 50, TREQ = [];
function topup(need){
  TA = need ? Math.ceil(need) : 50;
  buzz();
  sheet(`<h3>${t('topup')}</h3>
    <div class="sub">${S.shop}</div>
    ${need ? `<div class="msg">${ico('x', 16)} ${t('nobal')}</div><div style="height:12px"></div>` : ''}
    <div class="fld"><label>${t('amount')}</label>
      <input id="ta" type="number" inputmode="decimal" value="${TA}"></div>
    <div class="amts">${[20, 50, 100, 200, 500, 1000].map(v =>
      `<button onclick="document.getElementById('ta').value=${v};buzz()">${v}</button>`).join('')}</div>
    <button class="btn w" onclick="pickWay()">${t('next')} ${ico('arr', 16)}</button>`);
}

async function pickWay(){
  const v = parseFloat(document.getElementById('ta').value);
  if (!v || v < 1) return;
  TA = v; buzz();
  sheet('<div class="ld">···</div>');
  const r = await api('reqs');
  if (!r.ok || !r.items.length) { sheet(`<h3>${t('topup')}</h3><div class="msg">${t('noreq')}</div>`); return; }
  TREQ = r.items;
  sheet(`<h3>${t('way')}</h3><div class="sub">${money(TA)}</div>
    ${TREQ.map(w => `
      <button class="way" onclick="useWay(${w.id})">
        <div class="lg">${w.logo
          ? `<img src="${esc(w.logo)}" alt="" onerror="bankLogoErr(this,'${esc((w.bank||'?').substring(0,2).toUpperCase())}')">`
          : esc((w.bank || '?').substring(0, 2).toUpperCase())}</div>
        <div class="x"><b>${esc(w.bank)}</b>
          <span>${w.kind === 'phone' ? t('phone') : t('card')}</span></div>
        <span style="color:var(--mut)">${ico('arr', 16)}</span>
      </button>`).join('')}
    <div style="height:6px"></div>
    <button class="btn gh w" onclick="topup()">${ico('back', 15)} ${t('back')}</button>`);
}

async function useWay(rid){
  buzz();
  sheet('<div class="ld">···</div>');
  const r = await api('topup', { amount: TA, req_id: rid });
  if (!r.ok) {
    if (r.error === 'HAS_PENDING') {
      sheet(`<h3>${t('topup')}</h3>
        <div class="msg">${ico('bolt', 16)} ${t('pendWait')}</div>
        <div style="height:14px"></div>
        <button class="btn w" onclick="document.getElementById('msk')?.remove()">${t('okBtn')}</button>`);
      return;
    }
    sheet(`<h3>${t('topup')}</h3><div class="msg">${esc(r.error)}</div>`);
    return;
  }
  PAY = r;
  buzz('medium');
  payStep(1);
}

let PAY = null;

function payStep(n){
  if (!PAY) return;
  const w = PAY.req;
  const amt = Number(PAY.amount).toFixed(2).replace(/\.00$/, '');
  const head = `
    <div class="bhd">
      ${w.logo ? `<img src="${esc(w.logo)}" onerror="this.style.display='none'">` : ''}
      <div>
        <h3 style="margin:0">${esc(w.bank)}</h3>
        <div class="sub" style="margin:2px 0 0">#TOP${PAY.tid}</div>
      </div>
      <button class="hlp" style="width:22px;height:22px;font-size:12px;margin-left:auto"
              onclick="payHelp()">?</button>
    </div>
    <div class="steps">
      <div class="step ${n === 1 ? 'on' : 'ok'}"><i>${n === 1 ? '1' : '✓'}</i><b>${t('step1')}</b></div>
      <div class="step ${n === 2 ? 'on' : ''}"><i>2</i><b>${t('step2')}</b></div>
    </div>`;

  if (n === 1) {
    sheet(head + `
      <div class="det">
        <div class="k"><i>${w.kind === 'phone' ? t('phone') : t('card')}</i></div>
        <div class="r"><div class="val mono" id="pn">${esc(w.number)}</div>
          <button class="cp" onclick="cp('pn',this)">${ico('copy', 15)}</button></div>
      </div>

      <div class="det">
        <div class="k"><i>${t('owner')}</i></div>
        <div class="r"><div class="val" id="po" style="font-size:15px">
          ${esc(w.fname || '')} ${esc(w.lname || '')}</div>
          <button class="cp" onclick="cp('po',this)">${ico('copy', 15)}</button></div>
      </div>

      <div class="det sum">
        <div class="k"><i>${t('payAmt')}</i></div>
        <div class="r"><div class="val mono"><span id="pa">${amt}</span> ${S.cur}</div>
          <button class="cp" onclick="cp('pa',this)">${ico('copy', 15)}</button></div>
      </div>

      <div class="det cmt">
        <div class="k"><i>${t('comment')}</i><u>${t('cmtWhy')}</u></div>
        <div class="r"><div class="val mono" id="pc">${esc(PAY.comment || '')}</div>
          <button class="cp" onclick="cp('pc',this)">${ico('copy', 15)}</button></div>
      </div>

      ${w.url ? `<a class="btn w" style="text-decoration:none;margin-bottom:9px"
         href="${esc(w.url)}" target="_blank" onclick="setTimeout(()=>payStep(2),1200)">
         ${ico('bolt', 16)} ${t('payNow')}</a>` : ''}

      <button class="btn ${w.url ? 'gh' : ''} w" onclick="payStep(2)">
        ${t('paid')} ${ico('arr', 16)}</button>`);
    return;
  }

  sheet(head + `
    <div class="msg ok" style="margin-bottom:14px">${ico('chk', 16)} ${t('sendShot')}</div>
    <div class="det">
      <div class="k"><i>${t('payAmt')}</i></div>
      <div class="r"><div class="val mono">${amt} ${S.cur}</div></div>
    </div>
    <input type="file" accept="image/*" id="rf" style="display:none" onchange="sendReceipt(${PAY.tid})">
    <button class="btn w" id="rb" onclick="document.getElementById('rf').click()">
      ${ico('cam', 17)} ${t('uplBtn')}</button>
    <div id="rs"></div>
    <div style="height:9px"></div>
    <button class="btn gh w" onclick="payStep(1)">${ico('back', 15)} ${t('back')}</button>`);
}

function rejectView(r){
  buzz('heavy');
  sheet(`
    <div style="text-align:center;padding:6px 0 4px">
      <div style="color:var(--red);display:flex;justify-content:center">${ico('x', 40)}</div>
      <div style="height:12px"></div>
      <div style="font-size:15px;font-weight:900;letter-spacing:1.4px;color:var(--red)">
        ${esc(r.title || '')}</div>
      <div style="height:10px"></div>
      <div style="font-size:13.5px">${esc(r.why || '')}</div>
    </div>
    <div class="gd" style="margin-top:16px;border-left-color:var(--red)">
      <div>${esc(r.warn || '')}</div>
    </div>
    <div class="gd" style="border-left-color:var(--warn)">
      <div>${esc(r.maybe || '')}</div>
    </div>
    ${r.wa ? `<a class="btn w" style="text-decoration:none;background:#25D366"
       href="${esc(r.wa)}" target="_blank">${ico('wa', 17)} WHATSAPP</a>
      <div style="height:9px"></div>` : ''}
    <button class="btn gh w" onclick="document.getElementById('msk').remove()">OK</button>`);
}

/* Расмро дар телефон хурд мекунем — то ки зуд фиристода шавад.
   Аксари чекҳо 4-6 МБ мешаванд, баъди фишурдан ~200 КБ. */
function shrinkPhoto(file, maxSide = 1400, quality = 0.72){
  return new Promise((res) => {
    const done = fb => res(fb);
    try {
      const fr = new FileReader();
      fr.onerror = () => done(null);
      fr.onload = () => {
        const img = new Image();
        img.onerror = () => done(String(fr.result));
        img.onload = () => {
          try {
            let { width: w, height: h } = img;
            const k = Math.min(1, maxSide / Math.max(w, h));
            w = Math.round(w * k); h = Math.round(h * k);
            const c = document.createElement('canvas');
            c.width = w; c.height = h;
            const cx = c.getContext('2d');
            cx.fillStyle = '#fff'; cx.fillRect(0, 0, w, h);
            cx.drawImage(img, 0, 0, w, h);
            const out = c.toDataURL('image/jpeg', quality);
            // агар фишурдан кор накард — аслиро мефиристем
            done(out && out.length > 2000 ? out : String(fr.result));
          } catch (e) { done(String(fr.result)); }
        };
        img.src = String(fr.result);
      };
      fr.readAsDataURL(file);
    } catch (e) { done(null); }
  });
}

async function sendReceipt(tid){
  const f = document.getElementById('rf').files[0];
  if (!f) return;
  const b = document.getElementById('rb'), s = document.getElementById('rs');
  b.disabled = true; b.textContent = t('sending') + '...';
  if (s) s.innerHTML = `<div class="msg" style="margin-top:9px">${t('checking')}···</div>`;
  try {
    const b64 = await shrinkPhoto(f);
    if (!b64) { throw new Error('read'); }
    const r = await api('receipt', { tid, photo: b64 }, 90000);

    if (!r.ok && r.error === 'REJECTED') { PAY = null; rejectView(r); return; }

    if (r.ok) {
      buzz('heavy');
      b.style.display = 'none';
      s.innerHTML = `<div class="msg ok">${ico('chk', 16)} ${t('uplOk')}</div>`;
      PAY = null;
      setTimeout(() => { document.getElementById('msk')?.remove(); go(1); }, 1800);
    } else {
      b.disabled = false; b.innerHTML = ico('cam', 17) + ' ' + t('uplBtn');
      const map = { TIMEOUT: t('errSlow'), NET: t('errNet'), ALREADY: t('errAlready'),
                    BAD_IMAGE: t('errImg'), TOO_BIG: t('errBig'), RATE: t('errRate'),
                    TOO_FAST: t('errRate') };
      s.innerHTML = `<div class="msg">${ico('x', 16)}
        ${esc(map[r.error] || r.error || t('uplErr'))}</div>`;
    }
  } catch (e) {
    b.disabled = false; b.innerHTML = ico('cam', 17) + ' ' + t('uplBtn');
    s.innerHTML = `<div class="msg">${ico('x', 16)} ${t('uplErr')}</div>`;
  }
}

function cp(id, btn){
  const el = document.getElementById(id);
  if (!el) return;
  const txt = el.innerText.trim();
  const done = () => {
    const o = btn.innerHTML;
    btn.innerHTML = ico('chk', 15); btn.classList.add('ok'); buzz('medium');
    setTimeout(() => { btn.innerHTML = o; btn.classList.remove('ok'); }, 1300);
  };
  if (navigator.clipboard) navigator.clipboard.writeText(txt).then(done).catch(done);
  else {
    const ta = document.createElement('textarea');
    ta.value = txt; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch(e){}
    ta.remove(); done();
  }
}
</script>
<style>@keyframes fl{to{transform:translateY(105vh) rotate(600deg);opacity:0}}</style>
</body>
</html>
