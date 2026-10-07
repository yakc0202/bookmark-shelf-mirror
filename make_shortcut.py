"""Build an importable share-sheet shortcut without embedding any credentials.

iOS no longer accepts unsigned .shortcut files, so this always signs the
output via the macOS `shortcuts sign --mode anyone` CLI (no Apple ID/device
import round-trip needed). Never ship the unsigned intermediate file."""
import plistlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

DEST = Path(__file__).parent / 'shortcuts'
# 기본(v12): 저장 후 '서랍에서 보기 / 닫기' 선택 창(서랍에서 보기 → 사이트의 해당 카드로 이동) → shortcuts/Save-to-Shelf.shortcut
# --v11: 예전처럼 저장 완료 알림만 → shortcuts/Save-to-Shelf-v11.shortcut (롤백용 보관본)
import sys
OPEN_CHOICE = '--v11' not in sys.argv
SITE = 'https://<SITE_DOMAIN>'
DEST.mkdir(exist_ok=True)

def action(identifier, **parameters):
    return {'WFWorkflowActionIdentifier': identifier, 'WFWorkflowActionParameters': parameters}

def ref(uid, name):
    return {'Type': 'ActionOutput', 'OutputUUID': uid, 'OutputName': name}

def named_var(name):
    return {'Type': 'Variable', 'VariableName': name}

def attachment(value):
    return {'WFSerializationType': 'WFTextTokenAttachment', 'Value': value}

def text_token(*parts):
    s, attachments = '', {}
    for p in parts:
        if isinstance(p, str):
            s += p
        else:
            attachments['{%d, 1}' % len(s)] = p
            s += '\ufffc'
    return {'WFSerializationType': 'WFTextTokenString', 'Value': {'string': s, 'attachmentsByRange': attachments}}

def dictionary(fields):
    return {'Value': {'WFDictionaryFieldValueItems': [
        {'WFItemType': 0, 'WFKey': key, 'WFValue': value} for key, value in fields.items()]},
        'WFSerializationType': 'WFDictionaryFieldValue'}

def uid(): return str(uuid.uuid4()).upper()
key_id, type_id, match_id, resized_id, jpg_id, b64_id, text_id, page_match_id, page_url_id, result_id, message_id = [uid() for _ in range(11)]
file_match_id, combined_match_id = uid(), uid()
loop_id, branch_id, branch_result, page_branch_id = uid(), uid(), uid(), uid()
photo_result=uid()
links_id, has_link_id, link_branch = uid(), uid(), uid()
base=json.loads((DEST.parent/'data/cloud-build/outputs.json').read_text())['ApiURL'].rstrip('/')
repeat=attachment({'Type':'Variable','VariableName':'Repeat Item'})
def post(path,fields,output):
    return action('is.workflow.actions.downloadurl',WFURL=base+path,WFHTTPMethod='POST',WFHTTPBodyType='JSON',
        WFHTTPHeaders=dictionary({'Authorization':text_token('Bearer ',ref(key_id,'텍스트'))}),
        WFJSONValues=dictionary(fields),UUID=output)
def open_choice(result_key,label):
    menu=uid()
    return [
        action('is.workflow.actions.choosefrommenu',WFMenuPrompt=label+' 서랍에 저장했어요',WFMenuItems=['서랍에서 보기','닫기'],WFControlFlowMode=0,GroupingIdentifier=menu),
        action('is.workflow.actions.choosefrommenu',WFMenuItemTitle='서랍에서 보기',WFControlFlowMode=1,GroupingIdentifier=menu),
        action('is.workflow.actions.openurl',WFInput=text_token(SITE+'/#item/',ref(result_key,'저장 ID'))),
        action('is.workflow.actions.choosefrommenu',WFMenuItemTitle='닫기',WFControlFlowMode=1,GroupingIdentifier=menu),
        action('is.workflow.actions.choosefrommenu',WFControlFlowMode=2,GroupingIdentifier=menu),
    ]
def acknowledge(output,label):
    result_key,group=uid(),uid()
    return [
        action('is.workflow.actions.getvalueforkey',WFInput=attachment(ref(output,'URL 콘텐츠')),WFDictionaryKey='id',WFGetDictionaryValueType='Value',UUID=result_key),
        action('is.workflow.actions.conditional',WFInput={'Type':'Variable','Variable':attachment(ref(result_key,'저장 ID'))},WFCondition=100,WFControlFlowMode=0,GroupingIdentifier=group),
        *(open_choice(result_key,label) if OPEN_CHOICE else [
            action('is.workflow.actions.notification',WFNotificationActionTitle='서랍 · 저장 완료',WFNotificationActionBody=label+' 저장했어요. 분류·요약은 자동으로 진행돼요.',WFNotificationActionSound=False)]),
        action('is.workflow.actions.conditional',WFControlFlowMode=1,GroupingIdentifier=group),
        action('is.workflow.actions.alert',WFAlertActionTitle='서랍 저장 실패',WFAlertActionMessage=text_token('저장되지 않았습니다. 서버 응답: ',ref(output,'서버 응답')),WFAlertActionCancelButtonShown=False),
        action('is.workflow.actions.conditional',WFControlFlowMode=2,GroupingIdentifier=group),
    ]
actions = [
    action('is.workflow.actions.gettext',WFTextActionText='접속 키를 입력하세요',UUID=key_id),
    action('is.workflow.actions.repeat.each',WFInput=attachment({'Type':'ExtensionInput'}),WFControlFlowMode=0,GroupingIdentifier=loop_id),
    action('is.workflow.actions.getitemtype',WFInput=repeat,UUID=type_id),
    action('is.workflow.actions.detect.text',WFInput=repeat,UUID=text_id),
    action('is.workflow.actions.text.match',WFMatchTextPattern='(?i)(image|photo|이미지|사진)',WFMatchTextCaseSensitive=False,
        text=text_token(ref(type_id,'유형')),UUID=match_id),
    action('is.workflow.actions.text.match',WFMatchTextPattern=r'^file:.*\.(jpe?g|png|heic|heif)$',WFMatchTextCaseSensitive=False,
        text=text_token(ref(text_id,'입력에서 텍스트 가져오기')),UUID=file_match_id),
    action('is.workflow.actions.text.match',WFMatchTextPattern=r'.+',WFMatchTextCaseSensitive=False,
        text=text_token(ref(match_id,'일치하는 텍스트'),ref(file_match_id,'일치하는 텍스트')),UUID=combined_match_id),
    action('is.workflow.actions.conditional',WFInput={'Type':'Variable','Variable':attachment(ref(combined_match_id,'일치하는 텍스트'))},WFCondition=100,WFControlFlowMode=0,GroupingIdentifier=branch_id),
    action('is.workflow.actions.image.convert',WFInput=repeat,WFImageFormat='JPEG',WFImageCompressionQuality=0.65,WFImagePreserveMetadata=False,UUID=jpg_id),
    action('is.workflow.actions.base64encode',WFInput=attachment(ref(jpg_id,'변환된 이미지')),WFEncodeMode='Encode',WFBase64LineBreakMode='None',UUID=b64_id),
    post('/api/photos',{'image':text_token(ref(b64_id,'Base64 인코딩'))},photo_result),
    *acknowledge(photo_result,'사진을'),
    action('is.workflow.actions.conditional',WFControlFlowMode=1,GroupingIdentifier=branch_id),
    action('is.workflow.actions.text.match',WFMatchTextPattern='Safari',WFMatchTextCaseSensitive=False,text=text_token(ref(type_id,'유형')),UUID=page_match_id),
    action('is.workflow.actions.conditional',WFInput={'Type':'Variable','Variable':attachment(ref(page_match_id,'일치하는 텍스트'))},WFCondition=100,WFControlFlowMode=0,GroupingIdentifier=page_branch_id),
    action('is.workflow.actions.properties.safariwebpage',WFInput=repeat,WFContentItemPropertyName='Page URL',UUID=page_url_id),
    action('is.workflow.actions.conditional',WFControlFlowMode=2,GroupingIdentifier=page_branch_id),
    # 맥은 웹 페이지를 주소·제목 등 여러 항목으로 넘기므로, 항목마다 링크를 뽑고 링크가 없는 항목은 건너뛴다
    action('is.workflow.actions.detect.link',WFInput=repeat,UUID=links_id),
    action('is.workflow.actions.text.match',WFMatchTextPattern=r'https?://',WFMatchTextCaseSensitive=False,
        text=text_token(ref(page_url_id,'페이지 URL'),'\n',ref(links_id,'URL'),'\n',ref(text_id,'입력에서 텍스트 가져오기')),UUID=has_link_id),
    action('is.workflow.actions.conditional',WFInput={'Type':'Variable','Variable':attachment(ref(has_link_id,'일치하는 텍스트'))},WFCondition=100,WFControlFlowMode=0,GroupingIdentifier=link_branch),
    post('/api/items',{'url':text_token(ref(page_url_id,'페이지 URL'),'\n',ref(links_id,'URL'),'\n',ref(text_id,'입력에서 텍스트 가져오기')),'note':text_token(ref(text_id,'입력에서 텍스트 가져오기'))},result_id),
    *acknowledge(result_id,'링크를'),
    action('is.workflow.actions.conditional',WFControlFlowMode=2,GroupingIdentifier=link_branch),
    action('is.workflow.actions.conditional',WFControlFlowMode=2,GroupingIdentifier=branch_id,UUID=branch_result),
    action('is.workflow.actions.repeat.each',WFControlFlowMode=2,GroupingIdentifier=loop_id),
]
workflow = {
    'WFWorkflowName':'서랍에 저장(링크·사진 v12)' if OPEN_CHOICE else '서랍에 저장(링크·사진 v11)', 'WFWorkflowActions':actions,
    'WFWorkflowClientVersion':'2600', 'WFWorkflowMinimumClientVersion':900,
    'WFWorkflowMinimumClientVersionString':'900',
    'WFWorkflowIcon':{'WFWorkflowIconStartColor':4282601983, 'WFWorkflowIconGlyphNumber':59511},
    'WFWorkflowTypes':['ActionExtension'],
    # 공유 없이 직접 실행하면(맥 단축어 앱·메뉴 막대) 클립보드의 링크를 저장
    'WFWorkflowNoInputBehavior':{'Name':'WFWorkflowNoInputBehaviorGetClipboard','Parameters':{}},
    'WFWorkflowInputContentItemClasses':['WFURLContentItem','WFStringContentItem','WFSafariWebPageContentItem','WFImageContentItem'],
    'WFWorkflowImportQuestions':[
        {'ActionIndex':0, 'Category':'Parameter', 'ParameterKey':'WFTextActionText',
         'Text':'맥의 link-shelf/data/token 파일에 있는 접속 키를 붙여 넣으세요. Bearer는 붙이지 않습니다.', 'DefaultValue':''},
    ],
}
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    unsigned = Path(tmp) / 'unsigned.shortcut'
    unsigned.write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_BINARY))
    signed_path = DEST / ('Save-to-Shelf.shortcut' if OPEN_CHOICE else 'Save-to-Shelf-v11.shortcut')
    binary = shutil.which('shortcuts') or '/usr/bin/shortcuts'
    result = subprocess.run([binary, 'sign', '--mode', 'anyone', '--input', str(unsigned), '--output', str(signed_path)],
                             capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit('shortcuts sign 실패: ' + (result.stderr or result.stdout))
print(signed_path)
