# -*- coding: utf-8 -*-
"""Fixed foreign/loss fixtures for native tests only. No public execution endpoint."""
import scriptengine as se
import invt_operations as ops
import invt_runtime as rt
import invt_debugger as dbg
import invt_trace as tr
from System import Array, String

_foreign = None
_loss_thread = None


def run(request, stage):
    global _foreign, _loss_thread
    project=ops.owned()
    app=ops.choose_application(list(project.get_children(True)),request)
    rt.checked(project,app,request)
    if stage=='foreign_create':
        if _foreign is not None:
            raise RuntimeError('Fixture already exists')
        wrapper=se.trace.create(app,'ForeignTraceFixture','MainTask')
        wrapper.auto_start=False
        wrapper.trigger_enabled=False
        variable=wrapper.variable_list.add();variable.variable_name='PLC_PRG.nCycle';variable.enabled=True
        node=[o for o in app.get_children(True) if o.get_name()=='ForeignTraceFixture'][0]
        record={'wrapper':wrapper,'editor':None}
        record.update(node=node)
        _foreign=record
        project.save()
        return {'guid':str(node.guid)}
    if stage=='foreign_start':
        if _foreign is None:
            raise RuntimeError('No foreign fixture')
        record=_foreign
        editor,manager,data,name=tr.editor_parts(record)
        if tr.packet_online(manager,name):
            raise RuntimeError('Fixture will not replace an existing packet')
        editor.download();editor.start();tr.wait_running(editor,True)
        record.update(name=name)
        return {'guid':str(record['node'].guid),'name':name,'running':editor.is_running}
    if stage in ('foreign_status','foreign_clear'):
        if _foreign is None:
            raise RuntimeError('No foreign fixture')
        editor,manager,data,name=tr.editor_parts(_foreign)
        if stage=='foreign_clear':
            if editor.is_running:editor.stop();tr.wait_running(editor,False)
            manager.DeletePacket(name)
        return {'guid':str(_foreign['node'].guid),'name':name,'online':tr.packet_online(manager,name),
                'running':bool(editor.is_running)}
    if stage=='arm_capture_logout':
        # Inject real logout only after capture START is confirmed. The capture
        # implementation remains otherwise unchanged and must retain its ledger.
        from System.Threading import Thread,ThreadStart
        original=tr.wait_running
        used=[False]
        native=rt.with_executor(lambda:rt.use_online(app,lambda obj:dbg.core(obj,app)))
        def wrapped(editor,expected):
            original(editor,expected)
            if expected and not used[0]:
                used[0]=True
                tr.wait_running=original
                def worker():
                    Thread.Sleep(300)
                    def logout():
                        rt.checked(project,app,request)
                        dbg.logout_core(native)
                    se.system.execute_on_primary_thread(logout)
                global _loss_thread
                _loss_thread=Thread(ThreadStart(worker));_loss_thread.IsBackground=True;_loss_thread.Start()
        tr.wait_running=wrapped
        return {'armed':True}
    if stage=='arm_capture_signal':
        import os,json
        original=tr.wait_running
        def wrapped(editor,expected):
            original(editor,expected)
            if expected:
                tr.wait_running=original
                with open(os.path.join(os.path.dirname(__file__),'trace-started.json'),'w') as target:
                    json.dump({'running':True,'mode':'simulation','application_guid':str(app.guid)},target)
        tr.wait_running=wrapped
        return {'armed':True}
    if stage=='native_continue':
        def action(obj):
            native=dbg.core(obj,app)
            dbg.validate_generation(request,app,dbg.context(app),native)
            field=native.GetType().GetField('_uiLastChangeOfAppState',dbg.flags())
            before={'hit_count':int(native.CurrentHitCount),'state_stamp':str(field.GetValue(native))}
            native.Start()  # No invt_frames.invalidate: tests observed native events.
            se.system.delay(500)
            return {'state':unicode(obj.application_state),'before':before,
                    'after':{'hit_count':int(native.CurrentHitCount),'state_stamp':str(field.GetValue(native))}}
        return rt.with_executor(lambda:rt.use_online(app,action))
    if stage=='recursive_fixture':
        rt.assert_offline()
        fb=app.create_pou(name='FB_Recursive',type=se.PouType.FunctionBlock,language=None,
                          return_type=None,base_type=None,interfaces=None)
        fb.textual_declaration.replace('FUNCTION_BLOCK FB_Recursive\nVAR END_VAR')
        fb.textual_implementation.replace('')
        method=fb.create_method(name='Walk',return_type='DINT',language=None)
        method.textual_declaration.replace("{attribute 'estimated-stack-usage' := '256'}\nMETHOD PUBLIC Walk : DINT\nVAR_INPUT iDepth : DINT; END_VAR\nVAR nLocal : DINT; END_VAR")
        method.textual_implementation.replace('nLocal := iDepth;\nIF iDepth > 0 THEN\n    Walk := THIS^.Walk(iDepth - 1);\nELSE\n    Walk := nLocal + 1;\nEND_IF;')
        program=[o for o in app.get_children(True) if o.get_name()=='PLC_PRG' and hasattr(o,'textual_implementation')][0]
        program.textual_declaration.replace('PROGRAM PLC_PRG\nVAR fbRec : FB_Recursive; nResult : DINT; END_VAR')
        program.textual_implementation.replace('nResult := fbRec.Walk(2);')
        project.save()
        return {'method_guid':str(method.guid)}
    raise ValueError('Unknown fixed fixture stage')
