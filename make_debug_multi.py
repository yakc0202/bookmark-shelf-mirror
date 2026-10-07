"""One-off diagnostic: mirrors the real shortcut's repeat+type-match logic for
a MULTI-ITEM share (e.g. several photos at once) and shows, per shared item,
what 'Get Type of Input' returns and whether our image-match pattern caught
it — with no network calls. Use this to find out why multi-photo sharing
isn't producing a card, then delete it."""
import plistlib
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

DEST = Path(__file__).parent / 'shortcuts'
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
            s += '￼'
    return {'WFSerializationType': 'WFTextTokenString', 'Value': {'string': s, 'attachmentsByRange': attachments}}

def uid(): return str(uuid.uuid4()).upper()
type_id, match_id, log_set_id, init_id, count_id = [uid() for _ in range(5)]
loop_id = uid()
repeat = attachment({'Type': 'Variable', 'VariableName': 'Repeat Item'})

actions = [
    action('is.workflow.actions.setvariable', WFInput=text_token(''), WFVariableName='log', UUID=init_id),
    action('is.workflow.actions.count', Input=attachment({'Type': 'ExtensionInput'}), WFCountType='Items', UUID=count_id),
    action('is.workflow.actions.repeat.each', WFInput=attachment({'Type': 'ExtensionInput'}), WFControlFlowMode=0, GroupingIdentifier=loop_id),
    action('is.workflow.actions.getitemtype', WFInput=repeat, UUID=type_id),
    action('is.workflow.actions.text.match', WFMatchTextPattern='(?i)(image|photo|이미지|사진)', WFMatchTextCaseSensitive=False,
           text=text_token(ref(type_id, '유형')), UUID=match_id),
    action('is.workflow.actions.setvariable',
        WFInput=text_token(named_var('log'), '\n유형=', ref(type_id, '유형'), ' 사진매치=[', ref(match_id, '일치하는 텍스트'), ']'),
        WFVariableName='log', UUID=log_set_id),
    action('is.workflow.actions.repeat.each', WFControlFlowMode=2, GroupingIdentifier=loop_id),
    action('is.workflow.actions.alert', WFAlertActionTitle='서랍 디버그(여러 장)',
        WFAlertActionMessage=text_token('항목 수: ', ref(count_id, 'Count'), '\n로그 시작>', named_var('log'), '<로그 끝'),
        WFAlertActionCancelButtonShown=False),
]
workflow = {
    'WFWorkflowName': '서랍 디버그(여러 장)', 'WFWorkflowActions': actions,
    'WFWorkflowClientVersion': '2600', 'WFWorkflowMinimumClientVersion': 900,
    'WFWorkflowMinimumClientVersionString': '900',
    'WFWorkflowIcon': {'WFWorkflowIconStartColor': 12365311, 'WFWorkflowIconGlyphNumber': 59511},
    'WFWorkflowTypes': ['ActionExtension'],
    'WFWorkflowInputContentItemClasses': ['WFURLContentItem', 'WFStringContentItem', 'WFSafariWebPageContentItem', 'WFImageContentItem'],
}
with tempfile.TemporaryDirectory() as tmp:
    unsigned = Path(tmp) / 'unsigned.shortcut'
    unsigned.write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_BINARY))
    signed_path = DEST / 'Shelf-Debug-Multi.shortcut'
    binary = shutil.which('shortcuts') or '/usr/bin/shortcuts'
    result = subprocess.run([binary, 'sign', '--mode', 'anyone', '--input', str(unsigned), '--output', str(signed_path)],
                             capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit('shortcuts sign 실패: ' + (result.stderr or result.stdout))
print(signed_path)
