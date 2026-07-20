# Blender UDSZ file import/export add-on

USDZ file import and export plugin for [Blender](https://www.blender.org), that provides a simple method of importing and exporting models used with Augmented Reality applications.


## Installation

1. Download io_scene_usdz.zip file from the root of this repository.
2. Open Blender 4.5 or later and Go to edit -> User Preferences...
3. In User Preferences select Add-ons on the left hand menu and then select the Install button on the top right side of the window.
4. Navigate to and select the downloaded zip file from step 1.
5. Select the check mark next to Import-Export: UDSZ format to activate the plugin.


## Usage

Always be sure to save your work before using this tool.
The export functions of this add-on can be found either under the File -> Export -> USDZ (.usdz) menu or the Exporters pannel in the Collection Propterties.
When using the file menu export, use object selection to determine what gets exported.
When used in the Expoters pannel the add-on exports the items in the selected collection.


## Add-on Options

### Import Options

Import Materials - By selecting this option, the add-on will attempt to import materials associated with objects.

### Export Options

Export Materials - The exporter will export object materials as USD Principled shader materials which share many of the same properties as the Principled BSDF shader for Eevee and Cycles in Blender. Mix and Add shader nodes are not supported yet in this add-on.

Export Animations - When selected, the active object/bone animation will be exported to the usdz file. Currently any animations are baked per-frame.

Scale - This value is used to scale the objects exported to the usdz file.

Bake Textures - When enabled, any textures associated with materials will be baked out to image files that will be bundled into the usdz file. Currently the add-on will automatically switch to Cycles to bake images which could take a significant amount of time. This option is ignored if Export Materials is unchecked.

Use Gpu Compute - Enabled by default to use Cycles GPU Compute for texture baking, disable to fall back to CPU Cycles.

Bake AO - This options bakes ambient occlusion textures that are applied to the USD Principled shader materials in the usdz file. Activating this option can add a significant amount of time to export. This option is ignored if Export Materials is unchecked.

Samples - The number of samples used in baking the ambient occlusion textures. A higher number generates higher quality occlusion textures with added time to export. This option is ignored if either Export Materials or Bake AO options are unchecked.


## Notes

This add-on was only intended for exporting Apple's usdz files which is not intended as an interchange format. For full USD interchange functionality, be sure to look into Blender's built-in USD options.

The generated binary usd file used in the exported usdz file could potentially be incompatible to some augmented reality applications. This add-on provides a compleatly seperate python-only implentation for reading/writing binary USD files. It is possible there could be incompatibilities between this and offical implentations of the binary USD format.

The import functionality is currently limited to simple static models with no animations.

