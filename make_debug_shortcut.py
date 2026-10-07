"""One-off diagnostic shortcut: shows what Shortcuts actually extracts from a
Safari share (type / detected text / detected links), with no network calls.
Use this to find out why a specific share (e.g. Notion) fails, then delete it."""
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
type_id, text_id, link_id = uid(), uid(), uid()
ext_input = attachment({'Type': 'ExtensionInput'})

actions = [
    action('is.workflow.actions.getitemtype', WFInput=ext_input, UUID=type_id),
    action('is.workflow.actions.detect.text', WFInput=ext_input, UUID=text_id),
    action('is.workflow.actions.detect.link', WFInput=ext_input, UUID=link_id),
    action('is.workflow.actions.alert',
        WFAlertActionTitle='서랍 디버그',
        WFAlertActionMessage=text_token(
            '유형: ', ref(type_id, '유형'),
            '\n\n텍스트: ', ref(text_id, '입력에서 텍스트 가져오기'),
            '\n\n링크: ', ref(link_id, 'URL 가져오기')),
        WFAlertActionCancelButtonShown=False),
]
workflow = {
    'WFWorkflowName': '서랍 디버그', 'WFWorkflowActions': actions,
    'WFWorkflowClientVersion': '2600', 'WFWorkflowMinimumClientVersion': 900,
    'WFWorkflowMinimumClientVersionString': '900',
    'WFWorkflowIcon': {'WFWorkflowIconStartColor': 12365311, 'WFWorkflowIconGlyphNumber': 59511},
    'WFWorkflowTypes': ['ActionExtension'],
    'WFWorkflowInputContentItemClasses': ['WFURLContentItem', 'WFStringContentItem', 'WFSafariWebPageContentItem', 'WFImageContentItem'],
}
with tempfile.TemporaryDirectory() as tmp:
    unsigned = Path(tmp) / 'unsigned.shortcut'
    unsigned.write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_BINARY))
    signed_path = DEST / 'Shelf-Debug.shortcut'
    binary = shutil.which('shortcuts') or '/usr/bin/shortcuts'
    result = subprocess.run([binary, 'sign', '--mode', 'anyone', '--input', str(unsigned), '--output', str(signed_path)],
                             capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit('shortcuts sign 실패: ' + (result.stderr or result.stdout))
print(signed_path)
