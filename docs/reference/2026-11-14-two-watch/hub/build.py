import re,sys
D='<scratch>/twowatch'
PAGES=[('lineup','index.html','The Lineup','Who picked what, and how it placed'),
       ('taxonomy','taxonomy.html','Collection Taxonomy','The concepts and tests behind a two-watch collection'),
       ('judges','inference.html','What the Judges Rewarded','The criteria that reproduce the ranking'),
       ('wearers','tastes.html',"The Pickers' Own Watches",'What each enthusiast wore, and why they picked')]
def split_blocks(css):
    out=[];i=0;n=len(css)
    while i<n:
        j=css.find('{',i)
        if j<0: break
        sel=css[i:j].strip(); depth=1;k=j+1
        while depth and k<n:
            if css[k]=='{': depth+=1
            elif css[k]=='}': depth-=1
            k+=1
        out.append((sel,css[j+1:k-1])); i=k
    return out
def scope(css,pid):
    css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
    res=[]
    for sel,body in split_blocks(css):
        if sel.startswith('@media') or sel.startswith('@supports'):
            inner=scope(body,pid)
            if inner.strip(): res.append(f'{sel} {{\n{inner}\n}}')
            continue
        if sel.startswith('@'): res.append(f'{sel}{{{body}}}'); continue
        parts=[]
        for s in sel.split(','):
            s=s.strip()
            if s.startswith(':root') or s in ('html','body') : parts=None; break
            parts.append(f'#v-{pid} {s}')
        if parts: res.append(', '.join(parts)+' {'+body+'}')
    return '\n'.join(res)
views=[];styles=[]
for pid,fn,title,sub in PAGES:
    t=open(f'{D}/{fn}',encoding='utf-8').read()
    css='\n'.join(re.findall(r'<style>(.*?)</style>',t,flags=re.S))
    body=t[t.rfind('</style>')+len('</style>'):]
    body=body.replace('https://claude.ai/artifact/SuwkhmofAHidQ6dko5SsgW','#lineup').replace('https://claude.ai/artifact/7yWxiKfWGM7Yq4Uf1qapMU','#taxonomy')
    styles.append(f'/* ---- {pid} ---- */\n'+scope(css,pid))
    views.append(f'<section class="view" id="v-{pid}" data-title="{title}" hidden>\n{body.strip()}\n</section>')
tpl=open(f'{D}/hub/shell.html',encoding='utf-8').read()
nav='\n'.join(f'<li><a href="#{pid}" data-view="{pid}"><span class="nt">{title}</span><span class="ns">{sub}</span></a></li>' for pid,fn,title,sub in PAGES)
out=tpl.replace('/*PAGE_STYLES*/','\n'.join(styles)).replace('<!--NAV-->',nav).replace('<!--VIEWS-->','\n'.join(views))
open(f'{D}/hub/index.html','w',encoding='utf-8').write(out)
print(len(out),'bytes')
