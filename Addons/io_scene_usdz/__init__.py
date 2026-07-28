bl_info = {
  "name":        "USDZ Export",
  "author":      "Robert Crosby",
  "version":     (0, 0, 7),
  "blender":     (4, 5, 0),
  "location":    "File > Import-Export",
  "description": "Import/Export USDZ Files",
  "category":    "Import-Export"
}

if "bpy" in locals():
  import importlib
  if "import_usdz" in locals():
    importlib.reload(import_usdz)
  if "export_usdz" in locals():
    importlib.reload(export_usdz)

import bpy
from bpy.props import (
  BoolProperty,
  FloatProperty,
  IntProperty,
  StringProperty,
)
from bpy_extras.io_utils import (
  ImportHelper,
  ExportHelper,
  poll_file_object_drop,
)
from bpy.types import (
  Operator,
)


class ImportUSDZ(bpy.types.Operator, ImportHelper):
  """Import a USDZ File"""

  bl_idname = "import_scene.usdz"
  bl_label = "Import USDZ File"
  bl_options = {'PRESET', 'UNDO'}

  filename_ext = ""
  filter_glob: StringProperty(
    default="*.usdz;*.usda;*.usdc",
    options={'HIDDEN'},
  )

  materials: BoolProperty(
    name="Materials",
    description="Import Materials and textures",
    default=True,
  )
  animations: BoolProperty(
    name="Animations",
    description="Import Animations",
    default=True,
  )
  
  def draw(self, context):
    layout = self.layout
    layout.use_property_split = True
    layout.use_property_decorate = False  # No animation.
    import_panel_include(layout, self)

  def execute(self, context):
    from . import import_usdz
    keywords = self.as_keywords(ignore=("filter_glob",))
    return import_usdz.import_usdz(context, **keywords)


def import_panel_include(layout, operator):
  header, body = layout.panel("USDZ_import_include", default_closed=False)
  header.label(text="Include")
  if body:
    body.prop(operator, 'materials')
    body.prop(operator, 'animations')


class ExportUSDZ(bpy.types.Operator, ExportHelper):
  """Save a USDZ File"""

  bl_idname = "export_scene.usdz"
  bl_label = "Export USDZ File"
  bl_options = {'PRESET'}

  filename_ext = ".usdz"
  filter_glob: StringProperty(
    default="*.usdz;*.usda;*.usdc",
    options={'HIDDEN'},
  )
  collection: StringProperty(
    name="Source Collection",
    description="Export only objects from this collection (and its children)",
    default="",
  )
  exportMaterials: BoolProperty(
    name="Materials",
    description="Export Materials from Objects",
    default=True,
  )
  exportAnimations: BoolProperty(
    name="Animations",
    description="Export Animations",
    default=False,
  )
  bakeTextures: BoolProperty(
    name="Textures",
    description="Bake Diffuse, Roughness, Normal, etc",
    default=True,
  )
  bakeDiffuse: BoolProperty(
    name="Diffuse",
    description="Bake Diffuse Textures",
    default=True,
  )
  bakeRoughness: BoolProperty(
    name="Roughness",
    description="Bake Roughness Textures",
    default=True,
  )
  bakeMetallic: BoolProperty(
    name="Metallic",
    description="Bake Metal Textures",
    default=True,
  )
  bakeOpacity: BoolProperty(
    name="Opacity",
    description="Bake Opacity Textures",
    default=False,
  )
  bakeEmission: BoolProperty(
    name="Emission",
    description="Bake Emission Textures",
    default=False,
  )
  bakeNormals: BoolProperty(
    name="Normals",
    description="Bake Normal Textures",
    default=False,
  )
  bakeAO: BoolProperty(
    name="Ambiant Occlusion",
    description="Bake Ambiant Occlusion Textures",
    default=False,
  )
  bakeAOSamples: IntProperty(
    name="AO Samples",
    description="Number of Samples for Ambiant Occlusion",
    min=1,
    max=1000,
    default= 64,
  )
  useGpu: BoolProperty(
    name="Use GPU Compute",
    description="Use Cycles GPU Compute for baking textures",
    default=True,
  )
  bakeTextureSize: IntProperty(
    name="Image Size",
    description="Default Size of any Baked Images",
    min=16,
    max=4096,
    default= 1024,
  )
  globalScale: FloatProperty(
    name="Scale",
    min=0.01,
    max=1000.0,
    default=1.0,
  )
  debugMode: BoolProperty(
    name="Debug Enabled",
    description="Enable various debug features.",
    default=False,
  )
  
  def draw(self, context):
    layout = self.layout
    layout.use_property_split = True
    layout.use_property_decorate = False  # No animation.

    # Are we inside the File browser
    #is_file_browser = context.space_data.type == 'FILE_BROWSER'
    export_panel_include(layout, self)
    export_panel_textures(layout, self)

  def execute(self, context):
    from . import export_usdz
    keywords = self.as_keywords(ignore=("axis_forward",
                                        "axis_up",
                                        "global_scale",
                                        "check_existing",
                                        "filter_glob",
                                        ))
    return export_usdz.export_usdz(context, **keywords)


def export_panel_include(layout, operator):
  header, body = layout.panel("USDZ_export_include", default_closed=False)
  header.label(text="Include")
  if body:
    body.prop(operator, 'exportAnimations')
    body.prop(operator, 'globalScale')
    body.prop(operator, 'debugMode')

def export_panel_textures(layout, operator):
  header, body = layout.panel("USDZ_export_textures", default_closed=False)
  header.use_property_split = False
  header.label(text="Bake Textures")
  if body:
    body.prop(operator, 'useGpu')
    body.prop(operator, 'bakeTextureSize')
    body.separator()
    body.prop(operator, 'bakeDiffuse')
    body.prop(operator, 'bakeRoughness')
    body.prop(operator, 'bakeMetallic')
    body.prop(operator, 'bakeOpacity')
    body.prop(operator, 'bakeEmission')
    body.prop(operator, 'bakeNormals')
    body.prop(operator, 'bakeAO')
    body.prop(operator, 'bakeAOSamples')


class IO_FH_usdz(bpy.types.FileHandler):
  bl_idname = "IO_FH_usdz"
  bl_label = "USDZ"
  bl_import_operator = "import_scene.usdz"
  bl_export_operator = "export_scene.usdz"
  bl_file_extensions = ".usdz"

  @classmethod
  def poll_drop(cls, context):
    return poll_file_object_drop(context)


def menu_func_usdz_import(self, context):
  self.layout.operator(ImportUSDZ.bl_idname, text="USDZ (.usdz)")

def menu_func_usdz_export(self, context):
  self.layout.operator(ExportUSDZ.bl_idname, text="USDZ (.usdz)")


classes = (
  ImportUSDZ,
  ExportUSDZ,
  IO_FH_usdz,
)

def register():
  for cls in classes:
    bpy.utils.register_class(cls)

  bpy.types.TOPBAR_MT_file_import.append(menu_func_usdz_import)
  bpy.types.TOPBAR_MT_file_export.append(menu_func_usdz_export)

def unregister():
  bpy.types.TOPBAR_MT_file_import.remove(menu_func_usdz_import)
  bpy.types.TOPBAR_MT_file_export.remove(menu_func_usdz_export)

  for cls in classes:
    bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
