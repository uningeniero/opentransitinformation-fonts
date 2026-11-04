# SPDX-License-Identifier: Apache-2.0
"""Build one source-owned optional numeral-profile cut from its full raw carrier."""
from pathlib import Path
import argparse
import bisect
import hashlib
import io
import json

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import buildLookup, buildSingleSubstSubtable
from fontTools.misc.xmlWriter import XMLWriter

HERE = Path(__file__).resolve().parents[1]
PROFILE = HERE / "sources/screen/numeral-profile.json"
PROFILE_SHA = "0ccd3f89787d8858e22695d7d89813bb718c64ed23ea551f27f1dbcffbb88b86"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml(value, font):
    stream = io.BytesIO()
    value.toXML(XMLWriter(stream), font)
    return stream.getvalue()


def languages(table):
    for script in table.ScriptList.ScriptRecord:
        if script.Script.DefaultLangSys is not None:
            yield script.ScriptTag, "dflt", script.Script.DefaultLangSys
        for lang in script.Script.LangSysRecord:
            yield script.ScriptTag, lang.LangSysTag, lang.LangSys


def build(style, target):
    assert digest(PROFILE) == PROFILE_SHA, "Source profile changed; bind a new explicit revision."
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    cut = next(x for x in profile["cuts"] if x["style"] == style)
    source = Path(cut["input"]["path"])
    assert digest(source) == cut["input"]["sha256"]
    assert not target.exists()
    font = TTFont(source, lazy=True, recalcBBoxes=False, recalcTimestamp=False)
    family = profile["familyNaming"]["family"]
    ps_family = family.replace(" ", "")
    own_version = profile["familyNaming"]["ownVersion"]
    names = font["name"]
    for name in names.names:
        if name.nameID in {1, 4, 6, 16, 18, 21, 22}:
            text = name.toUnicode().replace("Fira Sans", family).replace("FiraSans", ps_family)
            name.string = text.encode(name.getEncoding())
        elif name.nameID == 3:
            name.string = ("OTI-ReferenceScreenFull-" + own_version + "-" + style).encode(name.getEncoding())
        elif name.nameID == 5:
            name.string = ("Version " + own_version + "; Fira Sans4.301-derived numeral-profile research family").encode(name.getEncoding())
    label_id = names.addName(profile["featurePolicy"]["label"])
    table = font["GSUB"].table
    old_lookups = [xml(x, font) for x in table.LookupList.Lookup]
    old_features = [xml(x.Feature, font) for x in table.FeatureList.FeatureRecord]
    old_tags = [x.FeatureTag for x in table.FeatureList.FeatureRecord]
    assert old_tags == sorted(old_tags) and "ss20" not in old_tags
    old_languages = [(script, lang, list(obj.FeatureIndex), obj.ReqFeatureIndex) for script, lang, obj in languages(table)]
    mapping = cut["mapping"]
    glyphs = set(font.getGlyphOrder())
    assert set(mapping).union(mapping.values()).issubset(glyphs)
    lookup_index = len(table.LookupList.Lookup)
    table.LookupList.Lookup.append(buildLookup([buildSingleSubstSubtable(mapping)], table="GSUB"))
    table.LookupList.LookupCount = len(table.LookupList.Lookup)
    feature = otTables.FeatureRecord()
    feature.FeatureTag = "ss20"
    feature.Feature = otTables.Feature()
    feature.Feature.LookupListIndex = [lookup_index]
    feature.Feature.LookupCount = 1
    params = otTables.FeatureParamsStylisticSet()
    params.Version = 0
    params.UINameID = label_id
    feature.Feature.FeatureParams = params
    index = bisect.bisect_right(old_tags, "ss20")
    table.FeatureList.FeatureRecord.insert(index, feature)
    table.FeatureList.FeatureCount = len(table.FeatureList.FeatureRecord)
    for script, language, lang in languages(table):
        lang.FeatureIndex = sorted([i + (i >= index) for i in lang.FeatureIndex] + [index])
        lang.FeatureCount = len(lang.FeatureIndex)
        if lang.ReqFeatureIndex != 0xFFFF:
            lang.ReqFeatureIndex += lang.ReqFeatureIndex >= index
    font["head"].fontRevision = float(own_version)
    font.save(target, reorderTables=False)
    font.close()
    # Exact stored-table conservation and logical conservation of every inherited lookup/feature.
    original = TTFont(source, lazy=True, recalcBBoxes=False, recalcTimestamp=False)
    after = TTFont(target, lazy=True, recalcBBoxes=False, recalcTimestamp=False)
    changed = [str(t) for t in original.reader.keys() if original.reader[t] != after.reader[t]]
    assert set(changed) == {"GSUB", "head", "name"}, changed
    assert [xml(x, after) for x in after["GSUB"].table.LookupList.Lookup[:lookup_index]] == old_lookups
    inherited_features = [x for x in after["GSUB"].table.FeatureList.FeatureRecord if x.FeatureTag != "ss20"]
    assert [x.FeatureTag for x in inherited_features] == old_tags
    assert [xml(x.Feature, after) for x in inherited_features] == old_features
    new_languages = list(languages(after["GSUB"].table))
    assert len(new_languages) == len(old_languages)
    for (script, lang, indices, required), (script2, lang2, obj) in zip(old_languages, new_languages):
        assert (script, lang) == (script2, lang2)
        assert [i - (i > index) for i in obj.FeatureIndex if i != index] == indices
        assert obj.ReqFeatureIndex == (required if required == 0xFFFF else required + (required >= index))
    assert after.getGlyphOrder() == original.getGlyphOrder()
    assert after.getBestCmap() == original.getBestCmap()
    assert original["name"].getDebugName(0) == after["name"].getDebugName(0)
    original.close()
    after.close()
    return {"style": style, "file": str(target), "sha256": digest(target),
            "inputSha256": cut["input"]["sha256"], "profileSha256": PROFILE_SHA,
            "intentionalStoredTableChanges": changed, "newFeature": "ss20",
            "allInheritedLookupFeatureAndLanguageRoutesConserved": True,
            "allGlyphProgramsAndOtherRawTablesExact": True,
            "scope": "Actual eight-cut profile production component; 1718input scalars retained. Mandatory five legacy additions and full design/application QA remain separate target obligations."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.style, args.output.resolve())))
