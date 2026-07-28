from io_scene_usdz.value_types import *

try:
    from pxr import Usd, UsdGeom, UsdShade, UsdSkel, Sdf, Gf
    pxr_included = True
except ImportError:
    pxr_included = False


def pxrUsdAvailable():
    return pxr_included


def writeUsdFile(filePath, usdData):
    stage = Usd.Stage.CreateNew(filePath)
    _setDataToStage(usdData, stage)
    stage.GetRootLayer().Export(filePath)


def _setDataToStage(data, stage):
    for key in data.metadata:
        stage.SetMetadata(key, data.metadata[key])
    for prim in data.children:
        _addPrimToStage(prim, stage)


def _addPrimToStage(usdPrim, stage):
    # Create usd prim
    if usdPrim.classType == ClassType.Scope:
        prim = UsdGeom.Scope.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.Xform:
        prim = UsdGeom.Xform.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.Mesh:
        prim = UsdGeom.Mesh.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.SkelRoot:
        prim = UsdSkel.Root.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.Skeleton:
        prim = UsdSkel.Skeleton.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.SkelAnimation:
        prim = UsdSkel.Animation.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.Material:
        prim = UsdShade.Material.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.Shader:
        prim = UsdShade.Shader.Define(stage, usdPrim.getPathStr())
    elif usdPrim.classType == ClassType.GeomSubset:
        prim = UsdGeom.Subset.Define(stage, usdPrim.getPathStr())
    else:
        print(f'Warning: unknown class type {usdPrim.classType}, using Xform in place')
        prim = UsdGeom.Xform.Define(stage, usdPrim.getPathStr())
    # Add Attributes
    for attr in usdPrim.attributes:
        _addAttrToPrim(attr, prim)
    # Add Children
    for child in usdPrim.children:
        _addPrimToStage(child, stage)


def _addAttrToPrim(usdAttr, prim):
    valueType = getattr(Sdf.ValueTypeNames, _getValueTypeRegString(usdAttr), Sdf.ValueTypeNames.Token)
    if usdAttr.isConnection():
        attr = prim.GetPrim().CreateAttribute(usdAttr.name, valueType)
        attr.SetConnections([Sdf.Path(usdAttr.value.getPathStr())])
        attr.SetCustom('custom' in usdAttr.qualifiers)
        if not 'uniform' in usdAttr.qualifiers:
            attr.SetVariability(Sdf.VariabilityVarying)
    elif usdAttr.isRelationship():
        rel = prim.GetPrim().CreateRelationship(usdAttr.name)
        rel.SetTargets([Sdf.Path(usdAttr.value.getPathStr())])
        rel.SetCustom('custom' in usdAttr.qualifiers)
    elif usdAttr.type == AttrType.Primvar:
        primVar = UsdGeom.PrimvarsAPI(prim).CreatePrimvar(usdAttr.name, valueType)
        primVar.SetInterpolation(usdAttr.interpolation.name)
        primVar.Set(_getAttrValue(usdAttr))
        if usdAttr.indices:
            primVar.SetIndices(usdAttr.indices)
    else:
        attr = prim.GetPrim().CreateAttribute(usdAttr.name, valueType)
        attr.SetCustom('custom' in usdAttr.qualifiers)
        if not 'uniform' in usdAttr.qualifiers:
            attr.SetVariability(Sdf.VariabilityVarying)
        if usdAttr.value != None:
            attr.Set(_getAttrValue(usdAttr))


def _getAttrValue(attr):
    if attr.valueType == ValueType.matrix4d:
        return [Gf.Matrix4d(m) for m in attr.value] if attr.isArray() else Gf.Matrix4d(attr.value)
    return attr.value


def _getValueTypeRegString(attr):
    if attr.valueTypeStr != None:
        regStr = attr.valueTypeStr + ('Array' if attr.isArray() else '')
    else:
        regStr = attr.valueType.toString() + ('Array' if attr.isArray() else '')
    return regStr[:1].upper() + regStr[1:]
