"""Isolates whether 'Add to Variable' (appendvariable) actually accumulates
across repeat.each iterations, with no mixing of Variable+ActionOutput refs
in one text token (that combo is the untested part of the previous debug
round). No network calls. Delete after use."""
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
append_id = uid()
loop_id = uid()
repeat = attachment({'Type': 'Variable', 'VariableName': 'Repeat Item'})

actions = [
    action('is.workflow.actions.repeat.each', WFInput=attachment({'Type': 'ExtensionInput'}), WFControlFlowMode=0, GroupingIdentifier=loop_id),
    action('is.workflow.actions.appendvariable', WFInput=text_token('사진하나'), WFVariableName='photoList', UUID=append_id),
    action('is.workflow.actions.repeat.each', WFControlFlowMode=2, GroupingIdentifier=loop_id),
    action('is.workflow.actions.alert', WFAlertActionTitle='서랍 디버그(추가)',
        WFAlertActionMessage=text_token(named_var('photoList')),
        WFAlertActionCancelButtonShown=False),
]
workflow = {
    'WFWorkflowName': '서랍 디버그(추가)', 'WFWorkflowActions': actions,
    'WFWorkflowClientVersion': '2600', 'WFWorkflowMinimumClientVersion': 900,
    'WFWorkflowMinimumClientVersionString': '900',
    'WFWorkflowIcon': {'WFWorkflowIconStartColor': 12365311, 'WFWorkflowIconGlyphNumber': 59511},
    'WFWorkflowTypes': ['ActionExtension'],
    'WFWorkflowInputContentItemClasses': ['WFURLContentItem', 'WFStringContentItem', 'WFSafariWebPageContentItem', 'WFImageContentItem'],
}
with tempfile.TemporaryDirectory() as tmp:
    unsigned = Path(tmp) / 'unsigned.shortcut'
    unsigned.write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_BINARY))
    signed_path = DEST / 'Shelf-Debug-Append.shortcut'
    binary = shutil.which('shortcuts') or '/usr/bin/shortcuts'
    result = subprocess.run([binary, 'sign', '--mode', 'anyone', '--input', str(unsigned), '--output', str(signed_path)],
                             capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit('shortcuts sign 실패: ' + (result.stderr or result.stdout))
print(signed_path)
