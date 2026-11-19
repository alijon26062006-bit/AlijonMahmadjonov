import re,sys,os
S=os.path.dirname(os.path.abspath(__file__))
ICONS={'box':'package','code':'code-xml','dash':'layout-dashboard','zap':'zap','gift':'gift','head':'headphones','globe':'globe','shield':'shield','pad':'gamepad-2','key':'key-round','music':'music','tablet':'tablet','send':'send','plus':'plus','redo':'refresh-cw','menu':'menu','close':'x','up':'arrow-up','arrow':'arrow-right','chev':'chevron-right','check':'check','copy':'copy','info':'info','alert':'circle-alert','lock':'lock','clock':'clock','search':'search','listp':'list-plus','help':'circle-help','chevl':'chevron-left','msg':'message-square-text','eye':'eye','eyeoff':'eye-off','trash':'trash-2','doc':'file-text','boxs':'package-search','warn':'triangle-alert','undo':'undo-2','house':'house','bag':'shopping-bag','swap':'arrow-right-left','wallet':'wallet','gem':'gem','clip':'clipboard-list','card':'credit-card','chartl':'chart-line','user':'user','gear':'settings','logout':'log-out','bell':'bell','moon':'moon','back':'arrow-left','grid2':'layout-grid','userplus':'user-plus','plug':'plug','grid':'layout-grid','trend':'trending-up','star':'star','compare':'git-compare','rocket':'rocket','compass':'compass','book':'book-text','chart':'chart-column','down':'chevron-down','shake':'handshake','cart':'shopping-cart','cloud':'cloud-upload','bulb':'lightbulb'}
sym=[]
for k,f in ICONS.items():
    s=open(os.path.join(os.environ.get('LUCIDE_DIR',f'{S}/lucide'),'package/icons',f+'.svg')).read()
    inner=re.search(r'<svg[^>]*>(.*)</svg>',s,re.S).group(1)
    inner=re.sub(r'\s+',' ',inner).strip()
    sym.append(f'  <symbol id="i-{k}" viewBox="0 0 24 24">{inner}</symbol>')
sprite='<!-- Icons: Lucide (ISC License) -->\n<svg width="0" height="0" style="position:absolute" aria-hidden="true">\n'+'\n'.join(sym)+'\n</svg>'
src=open(f'{S}/index.src.html').read()
out=src.replace('{{SPRITE}}',sprite)
open(sys.argv[1],'w').write(out)
print('built',len(out))
