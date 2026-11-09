# SPDX-License-Identifier: Apache-2.0
"""Compile contextual attachment source rules from real editable GLIF anchors."""
from io import StringIO
from collections import OrderedDict
from fontTools.feaLib import ast
from fontTools.feaLib.parser import Parser
from ufoLib2.objects import Anchor as UfoAnchor

KEY='org.opentransitinformation.anchorDefinitions'
POLICY='org.opentransitinformation.attachmentLookups'
SCHEMA='org.opentransitinformation.featureAnchorSchemaVersion'

def _tree(ufo):return Parser(StringIO(ufo.features.text),glyphNames=ufo.keys()).parse()

def _inline_old_anchors(ufo,tree):
    bindings=ufo.lib.get(KEY,{})
    def value(anchor):
        if anchor is None or anchor.name is None:return
        row=bindings[anchor.name];stored=next(a for a in ufo[row['glyph']].anchors if a.name==row['anchor'])
        anchor.x,anchor.y,anchor.name=stored.x,stored.y,None
    def visit(statements):
        result=[]
        for item in statements:
            if isinstance(item,ast.AnchorDefinition) and item.name in bindings:continue
            if isinstance(item,ast.MarkClassDefinition):value(item.anchor)
            elif isinstance(item,(ast.MarkBasePosStatement,ast.MarkMarkPosStatement)):
                for anchor,klass in item.marks:value(anchor)
            if hasattr(item,'statements'):item.statements=visit(item.statements)
            result.append(item)
        return result
    tree.statements=visit(tree.statements)

def link_anchors(ufo):
    tree=_tree(ufo)
    if KEY in ufo.lib:_inline_old_anchors(ufo,tree)
    for glyph in ufo:glyph.anchors.clear()
    bindings={};defs=[];names={};policies={}
    def ref(glyph_name,anchor_name,old):
        if old is None:return None
        assert old.name is None and old.contourpoint is None and old.xDeviceTable is None and old.yDeviceTable is None
        glyph=ufo[glyph_name];key=(glyph_name,anchor_name)
        if key in names:
            name=names[key];existing=next(a for a in glyph.anchors if a.name==anchor_name);assert (existing.x,existing.y)==(old.x,old.y)
        else:
            name='anchor'+str(len(defs)).zfill(5);names[key]=name;glyph.anchors.append(UfoAnchor(old.x,old.y,name=anchor_name))
            defs.append(ast.AnchorDefinition(name,old.x,old.y));bindings[name]={'glyph':glyph_name,'anchor':anchor_name}
        return ast.Anchor(None,None,name=name)
    def visit(statements,lookup=None):
        result=[]
        for item in statements:
            if isinstance(item,ast.MarkClassDefinition):
                for glyph in item.glyphs.glyphSet():result.append(ast.MarkClassDefinition(item.markClass,ref(glyph,'_'+item.markClass.name,item.anchor),ast.GlyphName(glyph)))
            elif isinstance(item,(ast.MarkBasePosStatement,ast.MarkMarkPosStatement)):
                assert lookup is not None
                kind='base' if isinstance(item,ast.MarkBasePosStatement) else 'mark2';policy=policies.setdefault(lookup,{'kind':kind,'classes':{}});assert policy['kind']==kind
                for glyph in (item.base if kind=='base' else item.baseMarks).glyphSet():
                    marks=[]
                    for anchor,klass in item.marks:
                        anchor_name=kind+'__'+lookup+'__'+klass.name;policy['classes'][klass.name]=anchor_name
                        marks.append((ref(glyph,anchor_name,anchor),klass))
                    result.append(ast.MarkBasePosStatement(ast.GlyphName(glyph),marks) if kind=='base' else ast.MarkMarkPosStatement(ast.GlyphName(glyph),marks))
            elif isinstance(item,(ast.MarkLigPosStatement,ast.CursivePosStatement)):raise NotImplementedError(type(item).__name__)
            else:
                if hasattr(item,'statements'):item.statements=visit(item.statements,item.name if isinstance(item,ast.LookupBlock) else lookup)
                result.append(item)
        return result
    tree.statements=visit(tree.statements);tree.statements=[ast.Comment('# Attachment coordinates and coverage are controlled by GLIF anchors and the build script.'),*defs,*tree.statements]
    ufo.lib[KEY]=bindings;ufo.lib[POLICY]=policies;ufo.lib[SCHEMA]=2;ufo.features.text=tree.asFea()
    return len(bindings)

def refresh_anchors(ufo):
    assert ufo.lib[SCHEMA]==2;tree=_tree(ufo);policies=ufo.lib[POLICY]
    definitions=[];bindings={};registered={};classes={}
    def collect(statements):
        for item in statements:
            if isinstance(item,ast.MarkClassDefinition):classes[item.markClass.name]=item.markClass
            if hasattr(item,'statements'):collect(item.statements)
    collect(tree.statements)
    def ref(glyph,anchor):
        key=(glyph.name,anchor.name)
        if key not in registered:
            name='anchor'+str(len(definitions)).zfill(5);registered[key]=name;definitions.append(ast.AnchorDefinition(name,anchor.x,anchor.y));bindings[name]={'glyph':glyph.name,'anchor':anchor.name}
        return ast.Anchor(None,None,name=registered[key])
    markdefs=[]
    for name,klass in classes.items():
        for glyph in ufo:
            anchor=next((a for a in glyph.anchors if a.name=='_'+name),None)
            if anchor is not None:markdefs.append(ast.MarkClassDefinition(klass,ref(glyph,anchor),ast.GlyphName(glyph.name)))
    def visit(statements):
        result=[]
        for item in statements:
            if isinstance(item,(ast.AnchorDefinition,ast.MarkClassDefinition)):continue
            if isinstance(item,ast.LookupBlock) and item.name in policies:
                policy=policies[item.name];kept=[x for x in item.statements if not isinstance(x,(ast.MarkBasePosStatement,ast.MarkMarkPosStatement))]
                for glyph in ufo:
                    anchors={a.name:a for a in glyph.anchors};marks=[(ref(glyph,anchors[a]),classes[c]) for c,a in policy['classes'].items() if a in anchors]
                    if marks:kept.append(ast.MarkBasePosStatement(ast.GlyphName(glyph.name),marks) if policy['kind']=='base' else ast.MarkMarkPosStatement(ast.GlyphName(glyph.name),marks))
                item.statements=kept
            elif hasattr(item,'statements'):item.statements=visit(item.statements)
            result.append(item)
        return result
    body=visit(tree.statements)
    categories=ufo.lib.get('public.openTypeCategories',{})
    for table in body:
        if isinstance(table,ast.TableBlock) and table.name=='GDEF':
            retained=[s for s in table.statements if not isinstance(s,ast.GlyphClassDefStatement)]
            groups={kind:ast.GlyphClass([g.name for g in ufo if categories.get(g.name)==kind]) for kind in ['base','mark','ligature','component']}
            table.statements=[ast.GlyphClassDefStatement(groups['base'],groups['mark'],groups['ligature'],groups['component']),*retained]
    tree.statements=[*definitions,*markdefs,*body];ufo.lib[KEY]=bindings;ufo.features.text=tree.asFea()
    return len(bindings)


def inherit_kerning(ufo,aliases):
    """Extend only pair-positioning coverage for explicit source-glyph roles."""
    assert all(new in ufo and old in ufo and new!=old for new,old in aliases.items())
    tree=_tree(ufo);definitions=[];classes={};changed=0
    used={s.name for s in tree.statements if isinstance(s,ast.GlyphClassDefinition)}
    def expand(expression):
        original=list(expression.glyphSet());extra=[new for new,old in aliases.items() if old in original and new not in original]
        if not extra:return expression,False
        key=tuple(original+extra)
        if key not in classes:
            index=len(definitions)
            while 'SourceKern'+str(index) in used:index+=1
            name='SourceKern'+str(index);used.add(name)
            definition=ast.GlyphClassDefinition(name,ast.GlyphClass(list(key)));definitions.append(definition);classes[key]=definition
        return ast.GlyphClassName(classes[key]),True
    def visit(statements):
        nonlocal changed
        for item in statements:
            if isinstance(item,ast.PairPosStatement):
                specific=item.enumerated or (isinstance(item.glyphs1,ast.GlyphName) and isinstance(item.glyphs2,ast.GlyphName))
                item.glyphs1,left=expand(item.glyphs1);item.glyphs2,right=expand(item.glyphs2)
                if (left or right) and specific:item.enumerated=True
                changed+=int(left or right)
            elif hasattr(item,'statements'):visit(item.statements)
    visit(tree.statements)
    tree.statements=[*definitions,*tree.statements];ufo.features.text=tree.asFea()
    bindings=ufo.lib.setdefault('org.opentransitinformation.kerningSourceGlyphs',{})
    for new,old in aliases.items():
        assert new not in bindings or bindings[new]==old
        bindings[new]=old
    return {'changedPairRules':changed,'newSourceClasses':len(definitions),'glyphRoles':len(aliases)}


def add_scoped_attachment(ufo,name,marks,bases):
    """Add an explicit finite mark/base lookup backed by editable GLIF anchors."""
    tree=_tree(ufo);assert name not in ufo.lib[POLICY]
    assert not any(isinstance(s,ast.LookupBlock) and s.name==name for s in tree.statements)
    klass=ast.MarkClass(name+'Class');lookup=ast.LookupBlock(name);definitions=[]
    base_anchor='base__'+name+'__'+klass.name
    for glyph_name,xy in marks.items():
        glyph=ufo[glyph_name];anchor_name='_'+klass.name;assert not any(a.name==anchor_name for a in glyph.anchors)
        glyph.anchors.append(UfoAnchor(*xy,name=anchor_name))
        definitions.append(ast.MarkClassDefinition(klass,ast.Anchor(*xy),ast.GlyphName(glyph_name)))
    for glyph_name,xy in bases.items():
        glyph=ufo[glyph_name];assert not any(a.name==base_anchor for a in glyph.anchors)
        glyph.anchors.append(UfoAnchor(*xy,name=base_anchor))
        lookup.statements.append(ast.MarkBasePosStatement(ast.GlyphName(glyph_name),[(ast.Anchor(*xy),klass)]))
    feature=ast.FeatureBlock('mark');feature.statements.append(ast.LookupReferenceStatement(lookup))
    tree.statements.extend([*definitions,lookup,feature]);ufo.features.text=tree.asFea()
    ufo.lib[POLICY][name]={'kind':'base','classes':{klass.name:base_anchor}}


def retain_default_feature_fallback(ufo,tag,script,language):
    """Retain an inherited default route when a new lookup materialises a language."""
    tree=_tree(ufo);references=[]
    for block in tree.statements:
        if not isinstance(block,ast.FeatureBlock) or block.name!=tag:continue
        current_script=current_language=None
        for item in block.statements:
            if isinstance(item,ast.ScriptStatement):current_script=item.script
            elif isinstance(item,ast.LanguageStatement):current_language=item.language
            elif isinstance(item,ast.LookupReferenceStatement) and current_script==script and current_language=='dflt':
                if item.lookup not in references:references.append(item.lookup)
    assert references,(tag,script,language)
    block=ast.FeatureBlock(tag);block.statements=[ast.ScriptStatement(script),ast.LanguageStatement(language),*[ast.LookupReferenceStatement(r) for r in references]]
    tree.statements.append(block);ufo.features.text=tree.asFea()
    key=tag+'/'+script+'/'+language
    bindings=ufo.lib.setdefault('org.opentransitinformation.featureFallbackBindings',{});assert key not in bindings;bindings[key]=[r.name for r in references]
    return bindings[key]
