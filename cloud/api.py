"""Personal S3 JSON archive API. Authenticated requests, conditional writes, worker leases."""
import base64
import copy
import gzip
import hashlib
import html
import json
import logging
import os
import random
import re
import secrets
import time
import urllib.parse
import urllib.request

import boto3
from botocore.exceptions import ClientError

from botocore.config import Config
logger = logging.getLogger()
logger.setLevel(logging.INFO)
S3 = boto3.client('s3', config=Config(signature_version='s3v4',s3={'addressing_style':'path'}))
LAMBDA_CLIENT = boto3.client('lambda')
BUCKET = os.environ['DATA_BUCKET']
KEY = 'data/cards.json'
PUBLIC_FIELDS = ('id','url','title','summary','folder','tags','thumbnail','status','source','note','created','error','transcript','place_url','attachment_url','reason','topic')

class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def read():
    try:
        r = S3.get_object(Bucket=BUCKET, Key=KEY)
        return json.loads(r['Body'].read()), r['ETag']
    except ClientError as e:
        if e.response['Error']['Code'] in ('NoSuchKey','404'):
            return {'version':1,'items':[]}, None
        raise

def transact(change):
    for attempt in range(8):
        data, etag = read()
        before = copy.deepcopy(data)
        result = change(data)
        if data == before:
            return result
        body = json.dumps(data, ensure_ascii=False).encode()
        if len(body) > 5_000_000:
            raise Problem(413,'저장 파일이 5MB를 초과했습니다. 저장 구조 확장이 필요합니다.')
        try:
            S3.put_object(Bucket=BUCKET, Key=KEY, Body=body, ContentType='application/json',
                          **({'IfMatch':etag} if etag else {'IfNoneMatch':'*'}))
            return result
        except ClientError as e:
            if e.response['Error']['Code'] not in ('PreconditionFailed','ConditionalRequestConflict','412','409'):
                raise
            time.sleep(random.uniform(.02,.1) * (attempt+1))
    raise Problem(409,'동시에 다른 변경이 저장됐습니다. 다시 시도해 주세요.')

def find(data, item_id):
    for item in data['items']:
        if item['id'] == item_id: return item
    raise Problem(404,'북마크가 없습니다.')

def photo_url(key):
    return f'https://{BUCKET}/{key}'

def visible(item):
    result={k:item.get(k,'') for k in PUBLIC_FIELDS}
    if item.get('image_key'):
        result.update(kind='photo',url=photo_url(item['image_key']),thumbnail=photo_url(item['image_key']))
    if item.get('kind')=='collection':result['kind']='collection'
    if item.get('entries'):
        result['entries']=[{'thumbnail':photo_url(e['image_key'])} if 'image_key' in e
                            else {'kind':'link','url':e['url'],'title':e.get('title',''),**({'thumbnail':e['thumbnail']} if e.get('thumbnail') else {})} for e in item['entries']]
    return result

def shared_page(data, token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise Problem(404, '공유가 종료되었거나 없는 링크입니다.')
    key = hashlib.sha256(token.encode()).hexdigest()
    share = data.get('shares', {}).get(key)
    if not share:
        raise Problem(404, '공유가 종료되었거나 없는 링크입니다.')
    item = find(data, share['item_id'])
    if item.get('deleted'):
        raise Problem(404, '공유가 종료된 링크입니다.')
    item = visible(item)
    e = lambda value: html.escape(str(value or ''), quote=True)
    url = item.get('url', '')
    if urllib.parse.urlsplit(url).scheme not in ('http','https'):
        raise Problem(404, '원본 주소가 올바르지 않습니다.')
    thumb = item.get('thumbnail', '')
    cover = '<img src="'+e(thumb)+'" alt="" referrerpolicy="no-referrer">' if thumb.startswith('https://') else ''
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow"><title>'+e(item['title'])+' · 서랍</title>'
            '<style>body{margin:0;padding:24px;background:#f7f7f2;color:#232b28;font:16px -apple-system,sans-serif}'
            'article{max-width:560px;margin:24px auto;background:white;border:1px solid #dbe0d7;border-radius:20px;overflow:hidden}'
            'img{width:100%;max-height:300px;object-fit:cover}.body{padding:24px}h1{font-size:24px;line-height:1.4}'
            'p{line-height:1.7;white-space:pre-wrap}a{color:#314f3a}.badge{color:#65735f;font-size:14px}</style>'
            '<article>'+cover+'<div class="body"><span class="badge">공유받은 북마크 · '+e(item['folder'])+'</span>'
            '<h1>'+e(item['title'])+'</h1><p>'+e(item.get('summary') or '아직 요약이 없습니다. 원본에서 내용을 확인하세요.')+'</p>'
            '<a href="'+e(url)+'" target="_blank" rel="noreferrer noopener">원본 보기 ↗</a></div></article></html>')
    return {'statusCode':200, 'headers':{'content-type':'text/html; charset=utf-8','cache-control':'no-store',
        'referrer-policy':'no-referrer','x-content-type-options':'nosniff','x-robots-tag':'noindex, nofollow',
        'content-security-policy':"default-src 'none'; img-src https:; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}, 'body':page}

def url_section(url):
    u=urllib.parse.urlsplit(url)
    path=u.path.strip('/')
    return (u.hostname, path.split('/')[0] if path else '')

def new_item(body):
    text = str(body.get('url') or body.get('text') or '')
    match = re.search(r'https?://[^\s<>"\u201c\u201d]+',text)
    if not match: raise Problem(400,'공유한 내용에 웹 링크가 없습니다.')
    url = match.group(0).rstrip(').,')
    u = urllib.parse.urlsplit(url)
    if not u.hostname or u.username or u.password: raise Problem(400,'올바른 링크가 아닙니다.')
    query = [(k,v) for k,v in urllib.parse.parse_qsl(u.query,keep_blank_values=True)
             if not k.startswith('utm_') and k not in ('igsh','igshid')]
    url = urllib.parse.urlunsplit((u.scheme,u.netloc.lower(),u.path,urllib.parse.urlencode(query),''))
    if len(url)>4000: raise Problem(400,'링크가 너무 깁니다.')
    note = str(body.get('note') or text.replace(match.group(0),'').strip())[:20000]
    is_youtube = (u.hostname or '').lower() in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be')
    return dict(id=hashlib.sha256(url.encode()).hexdigest()[:20],url=url,title=u.hostname,
                summary='',folder='나중에 다시 보기' if is_youtube else '받은 편지함',tags='[]',thumbnail='',
                status='ready' if is_youtube else 'queued',source='',
                note=note,created=time.time(),error='',revision=1,deleted=False)

def fetch_tweet_oembed_title(url):
    try:
        api_url='https://publish.twitter.com/oembed?url='+urllib.parse.quote(url,safe='')
        req=urllib.request.Request(api_url,headers={'User-Agent':'Mozilla/5.0 (compatible; LinkShelfBot/1.0)'})
        with urllib.request.urlopen(req,timeout=5) as r:
            obj=json.loads(r.read(200_000))
    except Exception:
        return ''
    text=re.sub(r'<[^>]+>','',obj.get('html',''))
    text=html.unescape(text).split('&mdash;')[0].split('—')[0]
    text=re.sub(r'\s*(?:pic\.twitter\.com|https?://t\.co)/\S+\s*$','',text)
    return re.sub(r'\s+',' ',text).strip()[:160]

def fetch_link_preview(url):
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LinkShelfBot/1.0)'})
        with urllib.request.urlopen(req,timeout=5) as r:
            text=r.read(200_000).decode('utf-8','ignore')
    except Exception:
        return '',''
    img=(re.search(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',text,re.I)
         or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',text,re.I))
    title=(re.search(r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',text,re.I)
           or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:title["\']',text,re.I)
           or re.search(r'<title[^>]*>([^<]+)</title>',text,re.I))
    thumb=urllib.parse.urljoin(url,img.group(1)) if img else ''
    ttl=html.unescape(title.group(1)).strip()[:160] if title else ''
    host=urllib.parse.urlsplit(url).hostname or ''
    if host.endswith('twitter.com') or host.endswith('x.com'):
        tweet_title=fetch_tweet_oembed_title(url)
        if tweet_title:
            ttl=tweet_title
    return thumb,ttl

def clean_entry_url(raw):
    u=urllib.parse.urlsplit(str(raw).strip())
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
        raise Problem(400,'http 또는 https 링크만 추가할 수 있습니다.')
    return urllib.parse.urlunsplit((u.scheme,u.netloc.lower(),u.path,u.query,'')), u.hostname

def change(data, path, body):
    now=time.time()
    if path=='/api/habits/save':
        habits=data.setdefault('habits',[])
        habit_id=body.get('id')
        old=next((h for h in habits if h['id']==habit_id),None)
        if habit_id and not old:raise Problem(404,'해빗트래커가 없습니다.')
        title=str(body.get('title','')).strip()[:100]
        if not title:raise Problem(400,'제목을 입력해 주세요.')
        description=str(body.get('description','')).strip()[:2000]
        duration_days=body.get('duration_days')
        if not isinstance(duration_days,int) or isinstance(duration_days,bool) or not 1<=duration_days<=3650:
            raise Problem(400,'기간(일)을 1~3650 사이로 입력해 주세요.')
        habit={'id':habit_id or secrets.token_hex(10),'title':title,'description':description,'duration_days':duration_days,
               'created':old['created'] if old else now,'stamps':old.get('stamps',{}) if old else {}}
        if old:habits[habits.index(old)]=habit
        else:habits.append(habit)
        return habit
    if path=='/api/ledger/save':
        ledger=data.setdefault('ledger',[])
        entry_id=body.get('id')
        old=next((e for e in ledger if e['id']==entry_id),None)
        if entry_id and not old:raise Problem(404,'가계부 내역이 없습니다.')
        date=str(body.get('date',''))
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):raise Problem(400,'날짜를 확인해 주세요.')
        kind=body.get('kind','expense')
        if kind not in ('expense','income'):raise Problem(400,'지출/수입을 선택해 주세요.')
        amount=body.get('amount')
        if not isinstance(amount,int) or isinstance(amount,bool) or not 0<amount<=10_000_000_000:
            raise Problem(400,'금액을 확인해 주세요.')
        entry={'id':entry_id or secrets.token_hex(10),'date':date,'kind':kind,'amount':amount,
               'category':str(body.get('category','')).strip()[:30] or '기타','memo':str(body.get('memo','')).strip()[:200],
               'created':old['created'] if old else now}
        if old:ledger[ledger.index(old)]=entry
        else:ledger.append(entry)
        return entry
    if path=='/api/ledger/delete':
        ledger=data.setdefault('ledger',[])
        old=next((e for e in ledger if e['id']==body.get('id')),None)
        if not old:raise Problem(404,'가계부 내역이 없습니다.')
        ledger.remove(old)
        for plan in data.get('ledger_plans',[]):
            if plan.get('entry_id')==old['id']:plan.update(done=False,entry_id='',done_date='')
        return {'message':'삭제했어요.'}
    if path=='/api/ledger/plans/save':
        plans=data.setdefault('ledger_plans',[])
        plan_id=body.get('id')
        old=next((p for p in plans if p['id']==plan_id),None)
        if plan_id and not old:raise Problem(404,'지출 계획이 없습니다.')
        cycle=str(body.get('cycle',''))
        if not re.fullmatch(r'\d{4}-\d{2}',cycle):raise Problem(400,'기간을 확인해 주세요.')
        title=str(body.get('title','')).strip()[:100]
        if not title:raise Problem(400,'계획 이름을 입력해 주세요.')
        amount=body.get('amount')
        if not isinstance(amount,int) or isinstance(amount,bool) or not 0<amount<=10_000_000_000:
            raise Problem(400,'금액을 확인해 주세요.')
        plan={'id':plan_id or secrets.token_hex(10),'cycle':cycle,'title':title,'amount':amount,
              'category':str(body.get('category','')).strip()[:30] or '기타',
              'done':old['done'] if old else False,'entry_id':old.get('entry_id','') if old else '',
              'done_date':old.get('done_date','') if old else '','created':old['created'] if old else now}
        if old:plans[plans.index(old)]=plan
        else:plans.append(plan)
        return plan
    if path=='/api/ledger/plans/delete':
        plans=data.setdefault('ledger_plans',[])
        old=next((p for p in plans if p['id']==body.get('id')),None)
        if not old:raise Problem(404,'지출 계획이 없습니다.')
        plans.remove(old)
        return {'message':'삭제했어요.'}
    if path=='/api/ledger/plans/check':
        plans=data.setdefault('ledger_plans',[]);ledger=data.setdefault('ledger',[])
        plan=next((p for p in plans if p['id']==body.get('id')),None)
        if not plan:raise Problem(404,'지출 계획이 없습니다.')
        if body.get('checked'):
            date=str(body.get('date',''))
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):raise Problem(400,'날짜를 확인해 주세요.')
            if not plan.get('done'):
                entry={'id':secrets.token_hex(10),'date':date,'kind':'expense','amount':plan['amount'],
                       'category':plan['category'],'memo':plan['title'],'created':now,'plan_id':plan['id']}
                ledger.append(entry)
                plan.update(done=True,entry_id=entry['id'],done_date=date)
        elif plan.get('done'):
            ledger[:]=[e for e in ledger if e['id']!=plan.get('entry_id')]
            plan.update(done=False,entry_id='',done_date='')
        return {'plan':plan,'ledger':sorted(ledger,key=lambda e:(e['date'],e['created']),reverse=True)}
    if path=='/api/habits/delete':
        habits=data.setdefault('habits',[])
        old=next((h for h in habits if h['id']==body.get('id')),None)
        if not old:raise Problem(404,'해빗트래커가 없습니다.')
        habits.remove(old)
        return {'message':'삭제했어요.'}
    if path=='/api/habits/stamp':
        habits=data.setdefault('habits',[])
        habit=next((h for h in habits if h['id']==body.get('id')),None)
        if not habit:raise Problem(404,'해빗트래커가 없습니다.')
        date=str(body.get('date',''))
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):raise Problem(400,'날짜 형식이 올바르지 않습니다.')
        stamps=habit.setdefault('stamps',{})
        if body.get('stamped'):stamps[date]=True
        else:stamps.pop(date,None)
        return {'id':habit['id'],'stamps':stamps}
    if path=='/api/collections':
        title=str(body.get('title','')).strip()[:160] or '새 모음'
        folder=str(body.get('folder','')).strip()[:100] or '모음'
        topic=str(body.get('topic','')).strip()[:100]
        item=dict(id=secrets.token_hex(10),url='',title=title,summary='',folder=folder,tags='[]',
                   thumbnail='',status='ready',source='',note='',created=now,error='',revision=1,deleted=False,
                   kind='collection',entries=[],topic=topic)
        data['items'].append(item)
        return {'id':item['id']}
    if path=='/api/items/to-collection':
        item=find(data,body.get('id'))
        if item.get('kind') in ('collection','photo'):raise Problem(400,'모음으로 전환할 수 없는 카드입니다.')
        entries=[{'kind':'link','url':item['url'],'title':item.get('title') or urllib.parse.urlsplit(item['url']).hostname}]
        entries+=[e for e in item.get('entries') or [] if e.get('kind')=='link']
        item['entries']=entries
        item['topic']=str(body.get('topic','')).strip()[:100]
        item['kind']='collection'
        item['url']=''
        item['revision']=item.get('revision',1)+1
        return {'id':item['id']}
    if path=='/api/items/merge-photos':
        item=find(data,body.get('id'))
        other=find(data,body.get('with'))
        if item['id']==other['id']:raise Problem(400,'같은 카드는 합칠 수 없습니다.')
        if item.get('kind')!='photo' or other.get('kind')!='photo':raise Problem(400,'사진 카드끼리만 합칠 수 있습니다.')
        if item.get('deleted') or other.get('deleted'):raise Problem(404,'삭제된 카드입니다.')
        entries=item.get('entries') or ([{'image_key':item['image_key']}] if item.get('image_key') else [])
        other_entries=other.get('entries') or ([{'image_key':other['image_key']}] if other.get('image_key') else [])
        if len(entries)+len(other_entries)>10:raise Problem(400,'사진은 최대 10장까지 합칠 수 있습니다.')
        item['entries']=entries+other_entries
        item['revision']=item.get('revision',1)+1
        other['deleted']=True
        other['revision']=other.get('revision',1)+1
        return {'id':item['id'],'entries':item['entries'],'message':'사진을 합쳤어요.'}
    if path in ('/api/collections/entries','/api/collections/entries/remove'):
        item=find(data,body.get('id'))
        entries=item.setdefault('entries',[])
        if path=='/api/collections/entries/remove':
            idx=body.get('index')
            if not isinstance(idx,int) or not 0<=idx<len(entries):raise Problem(400,'잘못된 항목입니다.')
            entries.pop(idx)
        else:
            if len(entries)>=50:raise Problem(400,'모음은 링크 50개까지 담을 수 있습니다.')
            url,host=clean_entry_url(body.get('url',''))
            label=str(body.get('title','')).strip()[:160] or str(body.get('_preview_title') or '')[:160] or host
            thumb=str(body.get('_thumbnail') or '')[:2000]
            entries.append({'kind':'link','url':url,'title':label,**({'thumbnail':thumb} if thumb else {})})
        item['revision']=item.get('revision',1)+1
        return {'id':item['id'],'entries':entries}
    if path in ('/api/memos/save','/api/memos/delete'):
        memos=data.setdefault('memos',[])
        memo_id=body.get('id')
        old=next((m for m in memos if m['id']==memo_id),None)
        if memo_id and not old:raise Problem(404,'메모가 없습니다.')
        if old and old.get('content_revision') is not None and body.get('content_revision')!=old.get('content_revision'):
            raise Problem(409,'다른 기기에서 메모가 변경됐습니다. 작성 내용은 유지됩니다. 목록에서 최신 메모를 확인하세요.')
        if path=='/api/memos/delete':
            if not old:raise Problem(404,'메모가 없습니다.')
            memos.remove(old)
            return {'message':'메모를 삭제했어요.'}
        title=body.get('title','');content=body.get('content','');folder=body.get('folder','')
        refs=body.get('bookmark_ids',[])
        if not all(isinstance(v,str) for v in (title,content,folder)) or not isinstance(refs,list) or any(not isinstance(x,str) for x in refs):
            raise Problem(400,'메모 형식이 올바르지 않습니다.')
        if len(title)>160 or len(content)>100000 or len(folder)>100 or len(refs)>100:
            raise Problem(400,'메모는 제목 160자, 본문 10만 자, 북마크 100개까지 저장할 수 있습니다.')
        refs=list(dict.fromkeys(refs))
        valid={x['id'] for x in data['items'] if not x.get('deleted')}
        previous=set(old.get('bookmark_ids',[])) if old else set()
        if any(x not in valid and x not in previous for x in refs):raise Problem(400,'추가할 북마크를 찾을 수 없습니다.')
        memo={'id':memo_id or secrets.token_hex(16),'title':title.strip() or '제목 없는 메모',
              'content':content,'folder':folder.strip() or '기본','bookmark_ids':refs,
              'created':old['created'] if old else now,'updated':now,'revision':old.get('revision',1)+1 if old else 1,
              'content_revision':old.get('content_revision',0)+1 if old else 1,
              'summary':old.get('summary','') if old else ''}
        if old:memos[memos.index(old)]=memo
        else:memos.append(memo)
        return memo
    if path=='/api/memos/summarize':
        memos=data.setdefault('memos',[])
        memo=next((m for m in memos if m['id']==body.get('id')),None)
        if not memo:raise Problem(404,'메모가 없습니다.')
        if not memo.get('content','').strip():raise Problem(400,'요약할 본문이 없습니다.')
        memo['kind']='memo-summary';memo['status']='queued';memo['revision']=memo.get('revision',1)+1
        return memo
    if path=='/api/memos/extract':
        memos=data.setdefault('memos',[])
        source=next((m for m in memos if m['id']==body.get('id')),None)
        if not source:raise Problem(404,'메모가 없습니다.')
        instruction=str(body.get('instruction','')).strip()
        if not instruction:raise Problem(400,'추출할 내용을 설명해 주세요.')
        if len(instruction)>200:raise Problem(400,'요청은 200자 이내로 적어 주세요.')
        job={'id':secrets.token_hex(16),'title':'AI 추출 준비 중','content':'','folder':source['folder'],
             'bookmark_ids':[],'created':now,'updated':now,'revision':1,'status':'queued','kind':'memo-extract',
             'instruction':instruction,'source_snapshot':source['content'][:90000],'source_memo_id':source['id'],'error':''}
        memos.append(job)
        return job
    if path=='/api/attach-photo':
        item=find(data,body.get('id'))
        if item.get('deleted'):raise Problem(404,'삭제된 카드입니다.')
        entries=item.get('entries')
        if entries is None:
            entries=[{'image_key':item['image_key']}] if item.get('image_key') else []
            item['entries']=entries
        if len(entries)>=10:raise Problem(400,'사진은 최대 10장까지 첨부할 수 있습니다.')
        entries.append({'image_key':body['_photo_key']})
        item['revision']=item.get('revision',1)+1
        return {'id':item['id'],'entries':entries,'message':'사진을 추가했어요.'}
    if path=='/api/photos':
        key=body['_photo_key'];note=body['_note']
        recent=[x for x in data['items'] if x.get('kind')=='photo' and not x.get('deleted') and now-x.get('created',0)<8]
        candidate=max(recent,key=lambda x:x['created']) if recent else None
        if candidate and len(candidate.get('entries') or [candidate])<10:
            candidate.setdefault('entries',[{'image_key':candidate['image_key']}])
            candidate['entries'].append({'image_key':key})
            candidate['status']='queued';candidate['error']=''
            candidate['revision']=candidate.get('revision',1)+1
            return {'id':candidate['id'],'message':'사진을 추가했어요. 맥에서 자동 분류합니다.'}
        item=dict(id=secrets.token_hex(16),url='',title='사진 정리 대기',summary='',folder='받은 편지함',tags='[]',
             thumbnail='',status='queued',source='사진',note=note,created=now,error='',revision=1,deleted=False,
             kind='photo',image_key=key)
        data['items'].append(item)
        return {'id':item['id'],'message':'사진을 저장했어요. 맥에서 자동 분류합니다.'}
    if path=='/api/items':
        item=new_item(body)
        old=next((x for x in data['items'] if x['url']==item['url']
                   or (x.get('kind')=='collection' and any(e.get('kind')=='link' and e.get('url')==item['url'] for e in x.get('entries') or []))),None)
        if old:
            if old.get('deleted'):
                old['deleted']=False;old['revision']=old.get('revision',1)+1
                if old['status']=='processing':old['status']='queued'
            return {'id':old['id'],'message':'이미 저장된 링크를 확인했어요.'}
        new_key=url_section(item['url'])
        recent=[x for x in data['items'] if not x.get('deleted') and x.get('kind') not in ('photo','collection')
                and not x.get('image_key') and now-x.get('created',0)<12
                and url_section(x['url'])==new_key]
        if recent:
            candidate=max(recent,key=lambda x:x['created'])
            entries=candidate.setdefault('entries',[])
            if len(entries)<50:
                host=urllib.parse.urlsplit(item['url']).hostname or item['url']
                thumb,title=fetch_link_preview(item['url'])
                entries.append({'kind':'link','url':item['url'],'title':title or host,**({'thumbnail':thumb} if thumb else {})})
                candidate['revision']=candidate.get('revision',1)+1
                candidate['created']=now
                return {'id':candidate['id'],'message':'이어지는 글로 추가했어요.'}
        data['items'].append(item)
        if item['status']=='ready':return {'id':item['id'],'message':'"나중에 다시 보기"에 저장했어요.'}
        return {'id':item['id'],'message':'저장했어요. 자동 정리합니다.'}
    if path=='/worker/claim':
        def pending(x):
            return (x['status']=='queued' or
                (x['status']=='processing' and x.get('lease_until',0)<now) or
                (x['status']=='ai_waiting' and x.get('retry_at',0)<now))
        candidates=[x for x in data['items'] if not x.get('deleted') and pending(x)]
        candidates+=[m for m in data.get('memos',[]) if m.get('kind') in ('memo-extract','memo-summary') and pending(m)]
        if not candidates:return {'item':None}
        item=min(candidates,key=lambda x:x['created'])
        item.update(status='processing',lease=secrets.token_urlsafe(24),lease_until=now+600)
        return {'item':copy.deepcopy(item),'folders':sorted(set(x['folder'] for x in data['items'] if not x.get('deleted')))}
    if path=='/worker/complete' and body.get('kind')=='memo-extract':
        memo=next((m for m in data.get('memos',[]) if m['id']==body.get('id')),None)
        if not memo or memo.get('lease')!=body.get('lease') or memo.get('revision',1)!=body.get('revision'):
            raise Problem(409,'삭제 또는 수정된 메모라 이전 처리 결과를 적용하지 않았습니다.')
        result=body.get('result',{})
        status=result.get('status')
        if status not in ('ready','needs_content','ai_waiting'):raise Problem(400,'잘못된 처리 상태입니다.')
        if status=='ready':
            memo['title']=str(result.get('title') or memo['title'])[:160]
            memo['content']=str(result.get('content',''))[:100000]
            memo['updated']=now
        memo['status']=status
        memo['error']=str(result.get('error',''))[:250]
        memo['retry_at']=now+3600 if status=='ai_waiting' else 0
        memo.pop('lease',None);memo.pop('lease_until',None)
        memo['revision']=memo.get('revision',1)+1
        return {'message':'추출 결과를 저장했어요.'}
    if path=='/worker/complete' and body.get('kind')=='memo-summary':
        memo=next((m for m in data.get('memos',[]) if m['id']==body.get('id')),None)
        if not memo or memo.get('lease')!=body.get('lease') or memo.get('revision',1)!=body.get('revision'):
            raise Problem(409,'삭제 또는 수정된 메모라 이전 처리 결과를 적용하지 않았습니다.')
        result=body.get('result',{})
        status=result.get('status')
        if status not in ('ready','ai_waiting'):raise Problem(400,'잘못된 처리 상태입니다.')
        memo['summary']=str(result.get('summary',''))[:300]
        memo.pop('lease',None);memo.pop('lease_until',None)
        if status=='ready':
            memo.pop('kind',None);memo.pop('status',None);memo.pop('retry_at',None)
        else:
            memo['status']=status;memo['retry_at']=now+3600
        memo['revision']=memo.get('revision',1)+1
        return {'message':'요약을 저장했어요.'}
    item=find(data,body.get('id'))
    if path in ('/api/share', '/api/unshare'):
        if item.get('deleted'):raise Problem(404,'삭제된 카드입니다.')
        shares=data.setdefault('shares',{})
        if path=='/api/unshare':
            for key in [k for k,v in shares.items() if v['item_id']==item['id']]:del shares[key]
            return {'message':'공유를 종료했어요.'}
        existing=next((v for v in shares.values() if v['item_id']==item['id'] and 'token' in v),None)
        if existing:
            return {'token':existing['token'],'message':'이 링크를 가진 사람은 이 북마크를 볼 수 있어요.'}
        token=secrets.token_urlsafe(32)
        shares[hashlib.sha256(token.encode()).hexdigest()]={'item_id':item['id'],'created':now,'token':token}
        return {'token':token,'message':'이 링크를 가진 사람은 이 북마크를 볼 수 있어요.'}
    if path=='/worker/complete':
        if item.get('deleted') or item.get('lease')!=body.get('lease') or item.get('revision',1)!=body.get('revision'):
            raise Problem(409,'삭제 또는 수정된 카드라 이전 처리 결과를 적용하지 않았습니다.')
        result=body.get('result',{})
        status=result.get('status')
        if status not in ('ready','needs_content','ai_waiting'):raise Problem(400,'잘못된 처리 상태입니다.')
        for key,limit in [('title',160),('summary',2000),('folder',100),('tags',2000),('thumbnail',4000),('source',100),('error',250),('transcript',4000),('place_url',300)]:
            if key in result:item[key]=str(result[key])[:limit]
        if item.get('thumbnail') and not item['thumbnail'].startswith('https://'):item['thumbnail']=''
        item['status']=status
        item['retry_at']=now+3600 if status=='ai_waiting' else 0
        item.pop('lease',None);item.pop('lease_until',None)
        return {'message':'처리 결과를 저장했어요.'}
    if path=='/api/delete':
        item['deleted']=True;item['deleted_at']=now
        shares=data.get('shares',{})
        for key in [k for k,v in shares.items() if v['item_id']==item['id']]:del shares[key]
    elif path=='/api/restore':
        item['deleted']=False
        if item['status']=='processing':item['status']='queued'
    elif path=='/api/update':
        if item.get('deleted'):raise Problem(404,'삭제된 카드입니다.')
        if 'attachment_url' in body:
            url=str(body['attachment_url']).strip()[:2000]
            if url and urllib.parse.urlsplit(url).scheme not in ('http','https'):raise Problem(400,'http 또는 https 링크만 추가할 수 있습니다.')
            item['attachment_url']=url
        if 'reason' in body:item['reason']=str(body['reason'])[:2000]
        if 'topic' in body:item['topic']=str(body['topic']).strip()[:100]
        if 'folder' in body or 'title' in body:
            item['folder']=str(body.get('folder',item['folder'])).strip()[:100] or '받은 편지함'
            item['title']=str(body.get('title',item['title']))[:160]
            if item['status']=='processing':item['status']='queued'
        if 'note' in body:item.update(note=str(body['note'])[:20000],status='queued',error='')
    else:raise Problem(404,'없는 주소입니다.')
    item['revision']=item.get('revision',1)+1
    return {'message':'반영했어요.'}

def handler(event, context):
    try:
        path=event.get('rawPath','')
        method=event.get('requestContext',{}).get('http',{}).get('method','GET')
        if method=='GET' and path.startswith('/s/'):
            data,_=read()
            return shared_page(data,path[3:])
        allowed=('/api/memos','/api/memos/save','/api/memos/delete','/api/memos/extract','/api/memos/summarize','/api/memos/photo','/api/photos','/api/attach-photo','/api/share','/api/unshare','/api/items','/api/update','/api/delete','/api/restore','/api/collections','/api/collections/entries','/api/collections/entries/remove','/api/items/to-collection','/api/items/merge-photos','/api/habits','/api/habits/save','/api/habits/delete','/api/habits/stamp','/api/ledger','/api/ledger/save','/api/ledger/delete','/api/ledger/plans','/api/ledger/plans/save','/api/ledger/plans/delete','/api/ledger/plans/check','/worker/claim','/worker/complete')
        if path not in allowed:raise Problem(404,'없는 주소입니다.')
        expected=os.environ['WORKER_TOKEN_HASH'] if path.startswith('/worker/') else os.environ['CLIENT_TOKEN_HASH']
        supplied=event.get('headers',{}).get('authorization','')
        if not supplied.startswith('Bearer ') or not secrets.compare_digest(hashlib.sha256(supplied[7:].encode()).hexdigest(),expected):
            raise Problem(401,'접속 키를 확인하세요.')
        accept_encoding=event.get('headers',{}).get('accept-encoding','')
        if method=='GET' and path=='/api/memos':
            data,_=read();return response(200,sorted(data.get('memos',[]),key=lambda m:m['updated'],reverse=True),accept_encoding)
        if method=='GET' and path=='/api/ledger/plans':
            data,_=read();return response(200,sorted(data.get('ledger_plans',[]),key=lambda p:p['created']),accept_encoding)
        if method=='GET' and path=='/api/ledger':
            data,_=read();return response(200,sorted(data.get('ledger',[]),key=lambda e:(e['date'],e['created']),reverse=True),accept_encoding)
        if method=='GET' and path=='/api/habits':
            data,_=read();return response(200,sorted(data.get('habits',[]),key=lambda h:h['created']),accept_encoding)
        if method=='GET' and path=='/api/items':
            data,_=read();return response(200,sorted([visible(x) for x in data['items'] if not x.get('deleted')],key=lambda x:x['created'],reverse=True),accept_encoding)
        if method!='POST':raise Problem(405,'지원하지 않는 요청입니다.')
        raw=event.get('body') or '{}'
        if event.get('isBase64Encoded'):raw=base64.b64decode(raw).decode()
        if len(raw.encode())>(14_000_000 if path in ('/api/photos','/api/attach-photo','/api/memos/photo') else 650000):raise Problem(413,'요청이 너무 큽니다.')
        body=json.loads(raw)
        if not isinstance(body,dict):raise Problem(400,'JSON 객체가 필요합니다.')
        if path in ('/api/photos','/api/attach-photo','/api/memos/photo'):
            blob=base64.b64decode(body.get('image',''),validate=True)
            if not 0<len(blob)<=10_000_000 or not blob.startswith(b'\xff\xd8\xff') or not blob.endswith(b'\xff\xd9'):
                raise Problem(400,'10MB 이하의 JPEG 사진이 필요합니다.')
            key='photos/'+secrets.token_hex(16)+'.jpg'
            S3.put_object(Bucket=BUCKET,Key=key,Body=blob,ContentType='image/jpeg',CacheControl='public, max-age=31536000, immutable')
            if path=='/api/memos/photo':return response(200,{'url':photo_url(key)})
            body={'id':body.get('id'),'_photo_key':key} if path=='/api/attach-photo' else {'_photo_key':key,'_note':str(body.get('note',''))[:20000]}
        if path=='/api/collections/entries':
            body['_thumbnail'],body['_preview_title']=fetch_link_preview(str(body.get('url','')).strip())
        result=transact(lambda data:change(data,path,body))
        if path in ('/api/items','/api/photos','/api/memos/extract','/api/memos/save','/api/memos/summarize'):
            try:
                LAMBDA_CLIENT.invoke(FunctionName=os.environ.get('WORKER_FUNCTION','<WORKER_LAMBDA_NAME>'),InvocationType='Event',Payload=b'{}')
            except Exception:
                pass
        if path=='/worker/claim' and result.get('item',{} ) and result['item'].get('image_key'):
            result['item']['image_download']=photo_url(result['item']['image_key'])
            if result['item'].get('entries'):
                result['item']['entries_download']=[photo_url(e['image_key']) for e in result['item']['entries']]
        return response(200,result)
    except Problem as e:return response(e.status,{'error':e.message})
    except (ValueError,TypeError,KeyError) as e:
        logger.warning('%s %s: %s: %s',event.get('requestContext',{}).get('http',{}).get('method','?'),event.get('rawPath','?'),type(e).__name__,str(e)[:300])
        return response(400,{'error':'요청 형식이 올바르지 않습니다.'})
    except Exception as e:
        logger.exception('%s %s: %s',event.get('requestContext',{}).get('http',{}).get('method','?'),event.get('rawPath','?'),type(e).__name__)
        return response(503,{'error':'저장소 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.'})

def response(status,body,accept_encoding=''):
    text=json.dumps(body,ensure_ascii=False)
    headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store'}
    if 'gzip' in accept_encoding and len(text)>800:
        headers['content-encoding']='gzip'
        return {'statusCode':status,'headers':headers,'isBase64Encoded':True,
                'body':base64.b64encode(gzip.compress(text.encode(),compresslevel=6)).decode()}
    return {'statusCode':status,'headers':headers,'body':text}
