import os, re, base64, json
here = os.path.dirname(os.path.abspath(__file__))  # libos/bonus/src
REPO = '/home/user/AlijonMahmadjonov'
rd = lambda p: open(p, encoding='utf-8').read()
API = 'https://qxwivnwzpbiewptaskzq.supabase.co/rest/v1/rpc/'
KEY = 'sb_publishable_vfe4cA46bAE7RQubAcfzZg_21bBgbeh'
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Onest:wght@500;600;700;800&family=Unbounded:wght@600;700&family=Montserrat:wght@700;800&display=swap">'
def style_of(path):
    s = rd(path); return s[s.index('<style>') + 7:s.index('</style>')].strip()
def page(title, css, body, js):
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#0B0B0B">
<title>{title}</title>
{FONTS}
<style>
{css}
</style>
</head>
<body>
{body.strip()}
<script>
{js.strip()}
</script>
</body>
</html>
'''
bags = 'data:image/png;base64,' + base64.b64encode(open(REPO + '/libos/app/img/bags.png', 'rb').read()).decode()
common = rd(here + '/extra-common.css')
cjs = rd(here + '/client.js').replace('__API__', API).replace('__KEY__', KEY).replace('__BAGS__', bags)
kjs = rd(here + '/kassa.js').replace('__API__', API).replace('__KEY__', KEY)
ccss = style_of(REPO + '/libos/app/istanbul-app.html') + '\n' + rd(here + '/extra-client.css') + common
kcss = style_of(REPO + '/libos/cashier/istanbul-cashier.html') + '\n' + rd(here + '/extra-kassa.css') + common
out = REPO + '/libos/bonus/web'
os.makedirs(out, exist_ok=True)
open(out + '/client.html', 'w', encoding='utf-8').write(page('ISTANBUL', ccss, rd(here + '/client-body.html'), cjs))
open(out + '/kassa.html', 'w', encoding='utf-8').write(page('ISTANBUL Касса', kcss, rd(here + '/kassa-body.html'), kjs))
# the Android apps load the same pages from their assets
import shutil
for n in ('client', 'kassa'):
    shutil.copy(out + f'/{n}.html', REPO + f'/libos/bonus/app/assets/web/{n}.html')
print('ok', os.path.getsize(out + '/client.html'), os.path.getsize(out + '/kassa.html'))
